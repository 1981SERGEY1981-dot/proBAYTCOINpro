from flask import Flask, jsonify, request, render_template
from blockchain import Blockchain, Transaction
from wallet import Wallet

app = Flask(__name__)
blockchain = Blockchain()
wallets = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/mine', methods=['POST'])
def mine_block():
    miner_address = request.json.get('miner_address')
    if not miner_address:
        return jsonify({'message': 'Miner address missing'}), 400
    blockchain.mine_pending_transactions(miner_address)
    response = {
        'message': 'New block mined successfully',
        'block': blockchain.get_last_block().to_dict()
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.json
    required = ['sender', 'recipient', 'amount', 'private_key']
    if not all(k in values for k in required):
        return jsonify({'message': 'Missing values'}), 400
    sender_wallet = wallets.get(values['sender'])
    if not sender_wallet:
        return jsonify({'message': 'Sender wallet not found'}), 404
    transaction = Transaction(values['sender'], values['recipient'], values['amount'])
    transaction.sign_transaction(values['private_key'])
    if not transaction.is_valid():
        return jsonify({'message': 'Invalid transaction'}), 
    blockchain.add_transaction(transaction)
    response = {'message': 'Transaction added to the blockchain'}
    return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': [block.to_dict() for block in blockchain.chain],
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200

@app.route('/wallet/new', methods=['GET'])
def new_wallet():
    wallet = Wallet()
    wallets[wallet.public_key] = wallet
    response = {
        'private_key': wallet.private_key,
        'public_key': wallet.public_key
    }
    return jsonify(response), 200

@app.route('/wallet/balance', methods=['POST'])
def wallet_balance():
    public_key = request.json['public_key']
    wallet = wallets.get(public_key)
    if not wallet:
        return jsonify({'message': 'Wallet not found'}), 404
    balance = wallet.get_balance(blockchain)
    return jsonify({'balance': balance}), 200

if __name__ == '__main__':
    app.run(debug=True)