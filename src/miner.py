from blockchain import Blockchain

blockchain = Blockchain()

def mine_block(miner_address):
    blockchain.mine_pending_transactions(miner_address)

if __name__ == "__main__":
    miner_address = input("Enter your wallet address: ")
    mine_block(miner_address)
    print("Mining complete.")