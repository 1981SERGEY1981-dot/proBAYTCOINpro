import pytest
from app import Blockchain

@pytest.fixture
def blockchain():
    return Blockchain()

def test_genesis_block(blockchain):
    """У генезис-блока есть правильные поля."""
    assert len(blockchain.chain) >= 1
    g = blockchain.chain[0]
    # убедимся, что previous_hash — строка из 64 hex-символов
    prev = g["previous_hash"]
    assert isinstance(prev, str) and len(prev) == 64 and all(c in "0123456789abcdef" for c in prev)

def test_new_block(blockchain):
    cnt = len(blockchain.chain)
    blockchain.new_block(proof=123, previous_hash="foo")
    assert len(blockchain.chain) == cnt + 1

def test_proof_of_work(blockchain):
    p = blockchain.proof_of_work(100)
    assert isinstance(p, int)
    assert blockchain.valid_proof(last_proof=100, proof=p)

