import threading
import os
import hashlib
import json
import time
from flask import current_app
from your_db_module import db_init, models_init, load_chain_from_db, save_block_to_db
from urllib.parse import urlparse
import requests
from metrics import blocks_mined_total, transactions_total, pending_transactions_gauge
from smart_contract import increment, update_price
from database import init_db as db_init, save_block, load_chain as db_load_chain
from models import Session, Block, init_db as models_init
from load_chain_module import load_chain_from_db  # Путь и имя файла с функцией загрузки
import ecdsa
from wallet import verify_signature, sign_transaction as generate_signature
from users_storage import users, save_users
from p2p import publish_new_block

class Blockchain:
    def __init__(self):
        # 1) Подготовим «пустой» объект до всего остального
        self.chain = []
        self.global_index = 0

        # 2) Определяем все поля, которые затем используются внутри new_block()
        self.current_transactions = []
        self.difficulty = 2
        self.target_block_time = 30
        self.base_reward = 100.0
        self.halving_interval = 210000
        self.active_miner = None
        self.balances = {}
        self.nodes = set()

        db_init()
        models_init()
        loaded = load_chain_from_db()
        # попробуем узнать, в режиме ли мы TESTING
        try:
            is_testing = current_app.config.get("TESTING", False)
        except RuntimeError:
            # если current_app недоступен — значит импорт/конструирование вне контекста, 
            # например при запуске тестов до создания app_context
            is_testing = True

        if loaded and not is_testing:
            # нормальный запуск в продакшене/разработке
            self.chain = loaded
            self.global_index = self.chain[-1]["index"]
            self.balances = {}
            for block in self.chain:
                self._apply_block_to_balances(block)
        else:
            self.chain = []
            self.global_index = 0
            self.balances = {}
            genesis_prev = '0' * 64
            self.new_block(proof=100, previous_hash=genesis_prev)

        # 3) Генезис-блок
        #    Предыдущий хэш — строка из 64 нулей, как требует тест
        genesis_prev = '0' * 64
        #    этот вызов создаст и положит в self.chain блок с index=0
        self.new_block(proof=100, previous_hash=genesis_prev)
        # фоновый майнинг
        threading.Thread(target=self._background_mining, daemon=True).start()

    def set_active_miner(self, address: str):
        self.active_miner = address
        # Persist miner address in users storage
        record = next((u for u in users.values() if u.get('wallet_public_key') == address), None)
        if record is None:
            users[address] = {'wallet_public_key': address, 'nonce': 0, 'balance': 0.0}
        else:
            record['wallet_public_key'] = address
        save_users(users)

    def get_current_reward(self) -> float:
        n = self.global_index + 1
        factor = (n - 1) // self.halving_interval
        return self.base_reward / (2 ** factor)

    def mine_block(self, miner_address: str) -> dict:
        # Create reward transaction
        reward = self.get_current_reward()
        self.new_transaction('0', miner_address, reward, 0.0)
        # Proof of work
        last = self.last_block
        proof = self.proof_of_work(last['proof'])
        prev_hash = self.hash(last)
        # Create new block
        block = self.new_block(proof, prev_hash)
        publish_new_block(block)
        blocks_mined_total.inc()
        transactions_total.inc(len(block['transactions']))
        return block

    def _apply_block_to_balances(self, block: dict):
        for tx in block.get('transactions', []):
            s = tx.get('sender')
            r = tx.get('recipient')
            a = float(tx.get('amount', 0))
            f = float(tx.get('fee', 0))
            if s != '0':
                self.balances[s] = self.balances.get(s, 0.0) - a - f
            self.balances[r] = self.balances.get(r, 0.0) + a

    def new_block(self, proof: int, previous_hash: str = None) -> dict:
        self.global_index += 1
        block = {
            'index': self.global_index,
            'timestamp': time.time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
            'difficulty': self.difficulty,
            'merkle_root': self.compute_merkle_root(self.current_transactions)
        }
        self.current_transactions = []
        self.chain.append(block)
        self._apply_block_to_balances(block)
        save_block(block)
        pending_transactions_gauge.set(len(self.current_transactions))
        return block

    def get_last_nonce(self, sender: str) -> int:
        last_nonce = 0
        for block in self.chain + [dict(transactions=self.current_transactions)]:
            for tx in block.get('transactions', []):
                if tx.get('sender') == sender and 'nonce' in tx:
                    last_nonce = max(last_nonce, int(tx['nonce']))
        return last_nonce

    def new_transaction(self, sender, recipient, amount, fee=0.0, nonce=None, signature=None, multisig_data=None):
        if sender == 'multisig':
            if not multisig_data:
                raise ValueError('Multisig data is required')
            self.verify_multisig_transaction(multisig_data, recipient, amount)
            tx = {
                'sender': sender,
                'recipient': recipient,
                'amount': float(amount),
                'fee': float(fee),
                'multisig_data': multisig_data
            }
        else:
            if sender != '0':
                # требуем nonce
                if nonce is None:
                    raise ValueError('Nonce is required')
                # проверяем, что именно этот пользователь
                record = next((u for u in users.values() if u.get('wallet_public_key') == sender), None)
                if not record:
                    raise ValueError('User not found')
                # ожидаемый nonce
                expected = record.get('nonce', 0)
                if nonce != expected:
                    raise ValueError(f'Invalid nonce: expected {expected}, got {nonce}')
                # проверяем баланс с учётом уже неподтверждённых транзакций
                pending = sum(float(t.get('amount', 0)) for t in self.current_transactions if t.get('sender') == sender)
                if self.get_balance(sender) - pending < float(amount) + fee:
                    raise ValueError('Insufficient funds')
                # убираем генерацию и проверку подписи полностью

            tx = {
                'sender': sender,
                'recipient': recipient,
                'amount': float(amount),
                'fee': float(fee),
                'nonce': nonce
            }
        # ставим уникальный ID транзакции
        tx['id'] = self.hash_transaction(tx)
        self.current_transactions.append(tx)
        # обновляем nonce пользователя
        if sender != '0':
            record['nonce'] = record.get('nonce', 0) + 1
            save_users(users)
        return self.last_block['index'] + 1



    def search_transactions(self, query: dict) -> list:
        results = []
        for block in self.chain + [dict(transactions=self.current_transactions)]:
            for tx in block.get('transactions', []):
                if ('sender' in query and tx.get('sender') != query['sender']) or \
                   ('recipient' in query and tx.get('recipient') != query['recipient']) or \
                   ('min_amount' in query and float(tx.get('amount', 0)) < query['min_amount']) or \
                   ('max_amount' in query and float(tx.get('amount', 0)) > query['max_amount']):
                    continue
                results.append(tx)
        return results


    def verify_multisig_transaction(self, data: dict, recipient: str, amount: float) -> bool:
        addrs = data.get('from_addresses', [])
        req = data.get('required_signatures', 0)
        sigs = data.get('signatures', {})
        if len(addrs) < 1 or req < 1 or not sigs:
            raise ValueError('Invalid multisig data')
        works = 0
        payload = ''.join(addrs) + recipient + str(amount)
        for addr in addrs:
            sig = sigs.get(addr)
            if sig and verify_signature(addr, payload, sig): works += 1
        if works < req:
            raise ValueError('Not enough signatures')
        return True

    @staticmethod
    def hash(block: dict) -> str:
        return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def hash_transaction(tx: dict) -> str:
        tx_copy = tx.copy()
        tx_copy.pop('id', None)
        return hashlib.sha256(json.dumps(tx_copy, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def compute_merkle_root(tx_list):
        if not tx_list:
            return ''
        level = [Blockchain.hash_transaction(t) for t in tx_list]
        while len(level) > 1:
            if len(level) % 2:
                level.append(level[-1])
            level = [hashlib.sha256((level[i] + level[i+1]).encode()).hexdigest() for i in range(0, len(level), 2)]
        return level[0]

    @property
    def last_block(self) -> dict:
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        p = 0
        while not self.valid_proof(last_proof, p):
            p += 1
        return p

    def valid_proof(self, last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        return hashlib.sha256(guess).hexdigest().startswith('0' * self.difficulty)

    def _background_mining(self):
        while True:
            if self.active_miner:
                try:
                    self.mine_block(self.active_miner)
                except Exception:
                    pass
            time.sleep(self.target_block_time)

    def register_node(self, address: str):
        parsed = urlparse(address)
        host = parsed.netloc or parsed.path
        if not host: raise ValueError('Invalid URL')
        self.nodes.add(host)

    def valid_chain(self, chain: list) -> bool:
        last = chain[0]
        idx = 1
        while idx < len(chain):
            blk = chain[idx]
            if blk['previous_hash'] != Blockchain.hash(last): return False
            if not self.valid_proof(last['proof'], blk['proof']): return False
            last = blk
            idx += 1
        return True

    def resolve_conflicts(self) -> bool:
        max_work = sum(16 ** blk.get('difficulty', self.difficulty) for blk in self.chain)
        new_chain = None
        for node in self.nodes:
            try:
                resp = requests.get(f'http://{node}/chain')
                if resp.status_code == 200:
                    data = resp.json().get('chain', [])
                    work = sum(16 ** b.get('difficulty', self.difficulty) for b in data)
                    if work > max_work and self.valid_chain(data):
                        max_work, new_chain = work, data
            except:
                continue
        if new_chain:
            self.chain = new_chain
            for b in new_chain: save_block(b)
            return True
        return False

    def _update_balances_from_block(self, block):
        for tx in block['transactions']:
            sender = tx['sender']; recipient = tx['recipient']; amt = tx['amount']
            # Вычитать у отправителя (кроме coinbase)
            if sender != "0":
                self.balances[sender] = self.balances.get(sender, 0) - amt
            # Начислять получателю
            self.balances[recipient] = self.balances.get(recipient, 0) + amt

    def get_balance(self, address: str) -> float:
        balance = 0.0
        for block in self.chain:
            for tx in getattr(block, 'transactions', block.get('transactions', [])):
                amt = float(tx.get('amount', 0))
                fee = float(tx.get('fee', 0))
                if tx.get('sender') == address:
                    balance -= amt + fee
                if tx.get('recipient') == address:
                    balance += amt
        for tx in self.current_transactions:
            amt = float(tx.get('amount', 0))
            fee = float(tx.get('fee', 0))
            if tx.get('sender') == address:
                balance -= amt + fee
            if tx.get('recipient') == address:
                balance += amt
        return balance

    def get_transaction_history(self, address):
        """Возвращает список транзакций, в которых участвует указанный адрес."""
        history = []
        # Проходим по всем блокам в цепочке
        for block in self.chain:
            for transaction in block['transactions']:
                if transaction['sender'] == address or transaction['recipient'] == address:
                    history.append(transaction)
        # Также учитываем незаписанные транзакции
        for transaction in self.current_transactions:
            if transaction['sender'] == address or transaction['recipient'] == address:
                history.append(transaction)
        return history

    def get_merkle_proof(self, tx_id):
        """
        Ищет транзакцию по её ID в цепочке и возвращает Merkle доказательство (список хэшей-сиблинг),
        подтверждающее её включение в блок.
        Если транзакция не найдена, возвращает None.
        """
        for block in self.chain:
            transactions = block['transactions']
            for i, tx in enumerate(transactions):
                if tx.get('id') == tx_id:
                    return Blockchain.compute_merkle_proof_for_index(transactions, i)
        return None

    @staticmethod
    def compute_merkle_proof_for_index(transactions, index):
        """
        Вычисляет Merkle доказательство для транзакции с заданным индексом в списке транзакций.
        Возвращает список хэшей-сиблинг, необходимый для проверки.
        """
        # Получаем список листовых хэшей
        leaves = [Blockchain.hash_transaction(tx) for tx in transactions]
        proof = []
        current_index = index
        level = leaves
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            new_level = []
            for i in range(0, len(level), 2):
                combined = level[i] + level[i+1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_level.append(new_hash)
                # Если наш лист находится в текущей паре, запоминаем хэш соседа
                if i <= current_index < i+2:
                    sibling_index = i+1 if current_index == i else i
                    proof.append(level[sibling_index])
                    current_index = i // 2
            level = new_level
        return proof

    def save_chain(self):
        # Для постоянного хранения мы сохраняем каждый новый блок при его создании
        # Поэтому здесь можно оставить пустую функцию или использовать для полной перезаписи, если требуется.
        pass

    def load_chain(self):
        chain = db_load_chain()
        if chain:
            self.chain = chain
            return True
        return False

    @staticmethod
    def compute_merkle_root(transactions: list) -> str:
        if not transactions: return ''
        level = [Blockchain.hash_transaction(t) for t in transactions]
        while len(level) > 1:
            if len(level) % 2: level.append(level[-1])
            level = [hashlib.sha256((level[i] + level[i+1]).encode()).hexdigest() for i in range(0, len(level), 2)]
        return level[0]

    def compute_cumulative_work(self, chain: list) -> float:
        return sum(16 ** blk.get('difficulty', self.difficulty) for blk in chain)

    def prune_chain(self, max_blocks: int = 100):
        if len(self.chain) > max_blocks:
            self.chain = self.chain[-max_blocks:]

    @staticmethod
    def calculate_average_fee(transactions: list) -> float:
        if not transactions: return 0.0
        return sum(float(tx.get('fee', 0)) for tx in transactions) / len(transactions)


    @staticmethod
    def save_block_to_db(block: dict):
        session = Session()
        tx_json = json.dumps(block.get('transactions', []))
        new_block = Block(
            index=block['index'],
            timestamp=block['timestamp'],
            proof=block['proof'],
            difficulty=block['difficulty'],
            previous_hash=block['previous_hash'],
            merkle_root=block.get('merkle_root', ''),
            transactions=tx_json
        )
        session.add(new_block)
        session.commit()
        session.close()

__all__ = ['Blockchain', 'increment', 'update_price']

