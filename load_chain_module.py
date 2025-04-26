import json
from models import Session, Block

def load_chain_from_db():
    session = Session()
    blocks = session.query(Block).order_by(Block.index).all()
    session.close()

    # Преобразуем объекты Block в словари, соответствующие формату цепочки
    chain = []
    for b in blocks:
        block_dict = {
            'index': b.index,
            'timestamp': b.timestamp,
            'proof': b.proof,
            'difficulty': b.difficulty,
            'previous_hash': b.previous_hash,
            'merkle_root': b.merkle_root,
            'transactions': json.loads(b.transactions)
        }
        chain.append(block_dict)
    return chain
