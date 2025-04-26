# mining_tasks.py
from users_storage import users
from baytcoin import Blockchain
from p2p import publish_new_block
from extensions import socketio

blockchain = Blockchain()


def scheduled_mining():
    if blockchain.active_miner:
        block = blockchain.mine_block(blockchain.active_miner)
        publish_new_block(block)
        socketio.emit('new_block', block)

def perform_mining_for_all(active_miners):
    for username in active_miners:
        miner_address = users.get(username, {}).get("wallet_public_key", "")
        if not miner_address:
            print(f"Wallet address not set for {username}")
            continue
        try:
            block = blockchain.mine_block(miner_address)
            publish_new_block(block)
            socketio.emit('new_block', block)
            print(f"Automatic mining for {username}: new block mined, index: {block['index']}")
        except Exception as e:
            print(f"Error mining for {username}: {e}")
