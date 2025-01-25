import hashlib
import time
import json
import ecdsa

class Transaction:
    def __init__(self, sender, recipient, amount, signature=""):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.signature = signature

    def __str__(self):
        return f"{self.sender} -> {self.recipient}: {self.amount}"

    def to_dict(self):
        return {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'signature': self.signature
        }

    def sign_transaction(self, private_key):
        private_key_bytes = bytes.fromhex(private_key)
        sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
        message = json.dumps(self.to_dict(), sort_keys=True).encode('utf-8')
        self.signature = sk.sign(message).hex()

    def is_valid(self):
        if self.sender == "0":  # Генезис-блок
            return True
        if not self.signature:
            return False
        public_key_bytes = bytes.fromhex(self.sender)
        vk = ecdsa.VerifyingKey.from_string(public_key_bytes, curve=ecdsa.SECP256k1)
        message = json.dumps(self.to_dict(), sort_keys=True).encode('utf-8')
        try:
            return vk.verify(bytes.fromhex(self.signature), message)
        except ecdsa.BadSignatureError:
            return False