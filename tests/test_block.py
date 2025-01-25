import unittest

from src.block import Block


class TestBlock(unittest.TestCase):
    def test_block_creation(self):
        block = Block(0, "0", 1610000000, [], 0, 3)
        self.assertEqual(block.index, 0)
        self.assertEqual(block.previous_hash, "0")


if __name__ == "__main__":
    unittest.main()
