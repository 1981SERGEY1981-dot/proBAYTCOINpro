import os
import ecdsa
import hashlib
from blockchain import Blockchain

class Wallet:
    def __init__(self):
        self.private_key, self.public_key = self.create_wallet()

    def create_wallet(self):
        private_key = os.urandom(32).hex()
        sk = ecdsa.SigningKey.from_string(bytes.fromhex(private_key), curve=ecdsa.SECP256k1)
        public_key = sk.verifying_key.to_string().hex()
        return private_key, public_key
    
    def get_balance(self, blockchain):
        balance = 0
        for block in blockchain.chain:
            for tx in block.transactions:
                if tx.recipient == self.public_key:
                    balance += tx.amount
                if tx.sender == self.public_key:
                    balance -= tx.amount
        return balance

if __name__ == "__main__":
    private_key, public_key = create_wallet()
    print(f"Private Key: {private_key}")
    print(f"Public Key: {public_key}")