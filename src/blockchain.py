import time
import json
from block import Block
from transaction import Transaction
import os
import hashlib
import ecdsa

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.difficulty = 4
        self.pending_transactions = []
        self.mining_reward = 50
        self.balances = {}

    def create_genesis_block(self):
        return Block(0, "0", "Genesis Block", [])

    def get_last_block(self):
        return self.chain[-1]

    def mine_pending_transactions(self, mining_reward_address):
        reward_tx = Transaction("System", mining_reward_address, self.mining_reward)
        self.pending_transactions.append(reward_tx)

        new_block = Block(len(self.chain), self.get_last_block().hash, self.pending_transactions)
        new_block.mine_block(self.difficulty)

        print(f"Блок # {new_block.index} добавлен в блокчейн")
        self.chain.append(new_block)
        self.pending_transactions = []
        self.update_balances(new_block)

    def add_transaction(self, transaction):
        if self.balances.get(transaction.sender, 0) < transaction.amount:
            print(f"Недостаточно средств у {transaction.sender}")
            return False
        self.pending_transactions.append(transaction)
        return True

    def update_balances(self, block):
        try:
            for tx in block.transactions:
                # Если transaction - это строка, выведем соответствующее сообщение об ошибке
                if isinstance(tx, str):
                    print(f"Transaction is string instead of Transaction object: {tx}")
                    continue
                # Проверка на наличие атрибутов
                if not hasattr(tx, 'recipient') or not hasattr(tx, 'amount'):
                    raise AttributeError("Transaction is missing 'recipient' or 'amount'")
                if not isinstance(tx.amount, (int, float)):
                    raise TypeError("Transaction 'amount' must be a number")
                self.balances[tx.recipient] = self.balances.get(tx.recipient, 0) + tx.amount
                if not hasattr(tx, 'sender'):
                    raise AttributeError("Transaction is missing 'sender'")
                self.balances[tx.sender] = self.balances.get(tx.sender, 0) - tx.amount
        except (AttributeError, TypeError) as e:
            print(f"Error in transaction")

    def get_balance(self, address):
        return self.balances.get(address, 0)

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            if current_block.hash != current_block.calculate_hash():
                return False

            if current_block.previous_hash != previous_block.hash:
                return False

        return True

    def add_block(self, new_block):
        new_block.previous_hash = self.get_last_block().hash
        new_block.mine_block(self.difficulty)
        self.chain.append(new_block)
