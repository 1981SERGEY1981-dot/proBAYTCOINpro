import unittest

from src.transaction import \
    Transaction  # Предполагаем, что у вас есть класс Transaction


class TestTransaction(unittest.TestCase):
    def test_transaction_creation(self):
        transaction = Transaction("Alice", "Bob", 10)
        self.assertEqual(transaction.sender, "Alice")
        self.assertEqual(transaction.recipient, "Bob")
        self.assertEqual(transaction.amount, 10)


if __name__ == "__main__":
    unittest.main()
