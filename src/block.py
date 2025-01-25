import hashlib
import json
import time

class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp or time.time()
        self.transactions = transactions
        self.nonce = 0
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_string = f"{self.index}{self.previous_hash}{self.transactions}{self.timestamp}{self.nonce}".encode()
        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self):
        return {
            'index': self.index,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'transactions': [tx.to_dict() if hasattr(tx, 'to_dict') else tx for tx in self.transactions],
            'nonce': self.nonce,
            'hash': self.hash
        }

    def mine_block(self, difficulty):
        target = '0' * difficulty
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
        print(f"Блок смайнен: {self.hash}")

    def add_transaction(self, transaction):
        if not isinstance(transaction, Transaction):
            print("Этот объект не является транзакцией")
            return False
        if self.balances.get(transaction.sender, 0) < transaction.amount:
            print(f"Недостаточно средств у {transaction.sender}")
            return False
        self.pending_transactions.append(transaction)
        return True

