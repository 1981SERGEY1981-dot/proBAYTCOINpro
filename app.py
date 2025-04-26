import werkzeug
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash, make_response
from flasgger import Swagger
from baytcoin import Blockchain
from p2p import publish_new_block, subscribe_to_channel, NEW_BLOCK_CHANNEL
from smart_contract import deploy_contract, update_price, increment, call_contract, smart_contracts 
import hashlib
import json
from time import time
from urllib.parse import urlparse
import requests 
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from notifications import notify_slack
from auth import token_required, generate_token
from models import init_db as models_init
from metrics import blocks_mined_total, transactions_total, pending_transactions_gauge, transactions_processed
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, set_access_cookies
from werkzeug.security import generate_password_hash, check_password_hash
from users_storage import users, save_users, update_user_balance, load_users # Импортируем пользователей из модуля, где они сохраняются # Обратите внимание, что мы используем одно хранилище
from users_db import register_user  # Если регистрация нужна тоже

from mining_tasks import perform_mining_for_all
from extensions import socketio
import signal
import atexit
import threading
from database import init_db as db_init

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "2.3.7"

logging.basicConfig(level=logging.INFO)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

# Предположим, у вас есть глобальная переменная, где хранится адрес контракта-оракула:
oracle_contract_address = "7cc87e6e-c127-474f-b911-097abe758485"

app = Flask(__name__)

app.config['SWAGGER'] = {
    'title': 'BAYTCOIN API',
    'uiversion': 3
}

# Настройка секретного ключа для JWT
app.config['JWT_SECRET_KEY'] = 'ваш-секретный-ключ-здесь'  # Укажите реальный и надежный 
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)  # Устанавливаем срок действия токена в 1 день
jwt = JWTManager(app)

swagger = Swagger(app)
socketio = SocketIO(app)
socketio.init_app(app)
db_init()
models_init()
blockchain = Blockchain()
balances = blockchain.balances

active_miners = []  # Например, список активных майнеров
active_miner_username = None  # Устанавливается при входе пользователя (например, в endpoint /login)


# Глобальный флаг для автоматического майнинга
auto_mining = False
mining_job = None

# Если контракты пусты, деплойте контракт-оракул
if not smart_contracts:
    oracle_contract_address = deploy_contract(
        {"update_price": update_price, "increment": increment},
        {"bitcoin_price_usd": 0}
    )
    print("Смарт‑контракт оракула задеплоен по адресу:", oracle_contract_address)
else:
    # Если контракты уже есть, возьмите существующий адрес
    oracle_contract_address = list(smart_contracts.keys())[0]
    print("Используем существующий смарт‑контракт оракула по адресу:", oracle_contract_address)

# Scheduler setup
events = (EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
scheduler = BackgroundScheduler()

def peer_discovery():
    if not SEED_NODE:
        return
    try:
        # Обращаемся к эндпоинту /nodes/list у seed-узла
        response = requests.get(f'{SEED_NODE}/nodes/list')
        if response.status_code == 200:
            data = response.json()
            new_nodes = data.get('nodes', [])
            for node in new_nodes:
                blockchain.register_node(node)
            print("Peer discovery: список узлов обновлён:", blockchain.nodes)
        else:
            print("Peer discovery: не удалось получить список узлов, статус:", response.status_code)
    except Exception as e:
        print("Peer discovery ошибка:", e)

def periodic_consensus():
    try:
        updated = blockchain.resolve_conflicts()
        if updated:
            socketio.emit('chain_updated', blockchain.chain, broadcast=True)
            print("Цепочка обновлена в результате автоматического консенсуса.")
        else:
            # Если хотите считать отсутствие обновления как failure, раскомментируйте следующую строку:
            # consensus_failures.inc()
            print("Цепочка авторитетна, обновлений не требуется.")
    except Exception as e:
        consensus_failures.inc()
        print("Ошибка консенсуса:", e)

@app.after_request
def add_no_cache_headers(resp):
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

# Маршрут для главной страницы с HTML-интерфейсом
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/explorer')
def explorer():
    return render_template('explorer.html')

@app.route('/login', methods=['GET'])
def login_page():
    return render_template("login.html")

@app.route('/events_page', methods=['GET'])
def events_page():
    return render_template("events.html")

@app.route('/wallet_page', methods=['GET'])
def wallet_page():
    return render_template('wallet.html')

@app.route('/contracts_page', methods=['GET'])
def contracts_page():
    return render_template("contracts.html")

@app.route('/admin', methods=['GET'])
def admin_panel():
    return render_template("admin.html")

@app.route('/vote')
def vote_page():
    return render_template('vote.html')

@app.route('/register', methods=['GET'])
def register_page():
    return render_template("register.html")

@app.route('/profile_page', methods=['GET'])
def profile_page():
    return render_template("profile.html")

@app.route('/update_wallet', methods=['GET'])
def update_wallet_page():
    return render_template("update_wallet.html")

@app.route('/mine', methods=['GET'])
def mine_page():
    return render_template("mine.html")

@app.route('/set_miner', methods=['POST'])
@jwt_required()
def set_miner():
    cu = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    addr = data.get('miner_address') or users[cu].get('wallet_public_key')
    if not addr:
        return jsonify({'msg':'miner_address обязателен'}),400
    blockchain.set_active_miner(addr)
    return '',204

@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/trades')
def trades():
    """
    Возвращает список OHLC-данных за последние N дней.
    Параметр days берётся из query-строки (по умолчанию 30).
    Формат ответа:
      [
        {"timestamp": 1682006400000, "open": 0.5, "high": 0.7, "low": 0.4, "close": 0.6},
        ...
      ]
    """
    days = int(request.args.get('days', 30))
    # Здесь собираем все транзакции типа Buy/Sell за период,
    # группируем по дню и считаем OHLC.
    # Пример «заглушки»:
    data = []
    # TODO: заменить на реальную агрегацию из БД
    for i in range(days):
        ts = datetime.utcnow().date() - timedelta(days=days - i - 1)
        data.append({
            "timestamp": int(datetime(ts.year, ts.month, ts.day).timestamp() * 1000),
            "open": 1.0 + i * 0.01,
            "high": 1.0 + i * 0.02,
            "low": 1.0 + i * 0.005,
            "close": 1.0 + i * 0.015
        })
    return jsonify(data)

# Вспомогательная функция: получаем последнюю рыночную цену из OHLC
def get_last_price():
    # Тут просто берём цену закрытия последнего дня из вашего /trades
    import requests
    trades = requests.get('http://localhost:5000/trades?days=1').json()
    if not trades:
        raise RuntimeError("Нет данных по торговле")
    return trades[-1]['close']

@app.route('/trade/buy', methods=['POST'])
@jwt_required()
def trade_buy():
    """
    Покупка BAYT за USD.
    Ожидает JSON { "amount_usd": <сумма в долларах> }.
    Списывает у пользователя amount_usd USD и начисляет amount_bayt = amount_usd / price.
    """
    current_user = get_jwt_identity()
    record = users.get(current_user)
    if not record:
        return jsonify({"msg": "User not found"}), 404

    data = request.get_json(force=True)
    amount_usd = float(data.get("amount_usd", 0))
    if amount_usd <= 0:
        return jsonify({"msg": "Неверная сумма для покупки"}), 400

    # Убедимся, что у пользователя есть USD
    record.setdefault("balance_usd", 0.0)
    if record["balance_usd"] < amount_usd:
        return jsonify({"msg": "Недостаточно USD на балансе"}), 400

    # Получаем последнюю цену
    try:
        price = get_last_price()
    except Exception as e:
        return jsonify({"msg": str(e)}), 500

    # Сколько BAYT коинов купим
    amount_bayt = amount_usd / price

    # Обновляем балансы
    record["balance_usd"] -= amount_usd
    record.setdefault("balance_bayt", 0.0)
    record["balance_bayt"] += amount_bayt
    save_users(users)

    return jsonify({
        "msg": "Успешная покупка",
        "spent_usd": amount_usd,
        "acquired_bayt": amount_bayt,
        "new_balance_usd": record["balance_usd"],
        "new_balance_bayt": record["balance_bayt"],
        "price": price
    }), 200

@app.route('/trade/sell', methods=['POST'])
@jwt_required()
def trade_sell():
    """
    Продажа BAYT за USD.
    Ожидает JSON { "amount_bayt": <количество BAYT> }.
    Списывает у пользователя amount_bayt BAYT и начисляет amount_usd = amount_bayt * price.
    """
    current_user = get_jwt_identity()
    record = users.get(current_user)
    if not record:
        return jsonify({"msg": "User not found"}), 404

    data = request.get_json(force=True)
    amount_bayt = float(data.get("amount_bayt", 0))
    if amount_bayt <= 0:
        return jsonify({"msg": "Неверное количество BAYT для продажи"}), 400

    # Убедимся, что у пользователя есть BAYT
    record.setdefault("balance_bayt", 0.0)
    if record["balance_bayt"] < amount_bayt:
        return jsonify({"msg": "Недостаточно BAYT на балансе"}), 400

    # Получаем последнюю цену
    try:
        price = get_last_price()
    except Exception as e:
        return jsonify({"msg": str(e)}), 500

    # Сколько USD получим
    amount_usd = amount_bayt * price

    # Обновляем балансы
    record["balance_bayt"] -= amount_bayt
    record.setdefault("balance_usd", 0.0)
    record["balance_usd"] += amount_usd
    save_users(users)

    return jsonify({
        "msg": "Успешная продажа",
        "sold_bayt": amount_bayt,
        "acquired_usd": amount_usd,
        "new_balance_bayt": record["balance_bayt"],
        "new_balance_usd": record["balance_usd"],
        "price": price
    }), 200

# Пример фоновой задачи, больше не нуждается в active_miner_username
def perform_mining():
    print("Фоновая задача майнинга запущена.")
    miner = blockchain.active_miner
    if not miner:
        print("Невозможно запустить майнинг: активный майнер не установлен.")
        return

    try:
        block = blockchain.mine_block(miner)
        print(f"[INFO] Автоматический майнинг: блок #{block['index']}, вознаграждение получено.")
    except Exception as e:
        print(f"[ERROR] Ошибка майнинга: {e}")


# Эндпоинт для добавления транзакции (POST)
@app.route('/transaction', methods=['POST'])
@jwt_required()
def create_transaction():
    current_user = get_jwt_identity()
    sender = users[current_user].get('wallet_public_key')
    if not sender:
        return jsonify({'msg': 'У пользователя не задан публичный ключ'}), 400

    data = request.get_json() or {}
    recipient = data.get('recipient')
    amount = data.get('amount')
    if not recipient or amount is None:
        return jsonify({'msg': 'Нужны recipient и amount'}), 400

    # Берём nonce из профиля и увеличиваем его
    nonce = users[current_user].get('nonce', 0)
    try:
        index = blockchain.new_transaction(
            sender=sender,
            recipient=recipient,
            amount=amount,
            fee=0.0,
            nonce=nonce
        )
    except ValueError as e:
        return jsonify({'msg': str(e)}), 400

    users[current_user]['nonce'] = nonce + 1

    # Сразу корректируем баланс в памяти
    blockchain.balances[sender] = blockchain.balances.get(sender, 0.0) - amount
    blockchain.balances[recipient] = blockchain.balances.get(recipient, 0.0) + amount

    return jsonify({'index': index}), 201

@app.route('/transactions/search', methods=['GET'])
def search_transactions():
    q = {}
    for p in ('sender','recipient'):
        v = request.args.get(p)
        if v: q[p]=v
    if request.args.get('min_amount',type=float) is not None:
        q['min_amount']=request.args.get('min_amount',type=float)
    if request.args.get('max_amount',type=float) is not None:
        q['max_amount']=request.args.get('max_amount',type=float)
    res = blockchain.search_transactions(q)
    return jsonify({'results':res}),200


def update_user_balance(address, amount):
    """
    Обновляет баланс пользователя в users.json.
    address: публичный ключ (wallet_public_key)
    amount: сумма для прибавления
    """
    # найдём запись пользователя по его публичному ключу
    user_record = None
    for uname, udata in users.items():
        if udata.get("wallet_public_key") == address:
            user_record = udata
            break
    if not user_record:
        print(f"[WARN] Не найден пользователь с адресом {address} для обновления баланса")
        return
    current = user_record.get("balance", 0)
    new = current + amount
    user_record["balance"] = new
    save_users(users)
    print(f"[INFO] Баланс для {address} обновлен: {current} → {new}")
    return new

# Подписываемся на канал новых блоков
def handle_new_block(data):
    # Если полученный блок отличается от локальной цепочки, запускаем консенсус или обновляем цепочку
    print("Получен новый блок через P2P:", data)
    # Здесь можно добавить логику для сравнения и обновления цепочки
    subscribe_to_channel(NEW_BLOCK_CHANNEL, handle_new_block)

# Эндпоинт для майнинга нового блока
@app.route('/mine', methods=['POST'])
@jwt_required()
def mine():
    cu = get_jwt_identity()
    addr = users[cu].get('wallet_public_key')
    if not addr:
        return jsonify({'msg':'Wallet address not set'}), 400

    # вознаграждение майнеру
    blockchain.new_transaction(
        sender="0",
        recipient=addr,
        amount=blockchain.get_current_reward()
    )

    last = blockchain.last_block
    proof = blockchain.proof_of_work(last['proof'])
    prev_hash = blockchain.hash(last)
    block = blockchain.new_block(proof, prev_hash)

    return jsonify(block), 200



# Endpoint для запуска автоматического майнинга
@app.route('/start_mining', methods=['POST'])
def start_mining():
    global auto_mining, mining_job
    auto_mining = True
    if mining_job is None:
        mining_job = scheduler.add_job(func=perform_mining, trigger="interval", seconds=30)
    return jsonify({"message": "Automatic mining started"}), 200

# Endpoint для остановки автоматического майнинга
@app.route('/stop_mining', methods=['POST'])
def stop_mining():
    global auto_mining, mining_job
    auto_mining = False
    if mining_job is not None:
        mining_job.remove()
        mining_job = None
    return jsonify({"message": "Automatic mining stopped"}), 200

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


# Функция для рассылки нового блока
def broadcast_new_block(block):
    for node in blockchain.nodes:
        url = f'http://{node}/block/receive'
        try:
            requests.post(url, json=block)
        except Exception:
            continue

# Эндпоинт для приёма блока от другого узла
@app.route('/block/receive', methods=['POST'])
def receive_block():
    new_block = request.get_json()
    last_block = blockchain.last_block
    # Простой механизм проверки: если новый блок – следующий по индексу и с корректным previous_hash, то принимаем его
    if new_block['index'] == last_block['index'] + 1 and new_block['previous_hash'] == blockchain.hash(last_block):
        blockchain.chain.append(new_block)
        blockchain.save_chain()
        return jsonify({'message': 'Блок принят'}), 200
    else:
        return jsonify({'message': 'Блок отклонён'}), 400

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify({
        "chain": blockchain.chain,
        "length": len(blockchain.chain)
    }), 200

@app.route('/chain/reload', methods=['GET'])
def reload_chain():
    if blockchain.load_chain():
        return jsonify({
            "message": "Цепочка загружена с диска",
            "chain": blockchain.chain
        }), 200
    else:
        return jsonify({
            "message": "Сохранённая цепочка не найдена"
        }), 404


# Эндпоинт для регистрации новых узлов (POST)
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Ошибка: требуется указать список узлов", 400
    for node in nodes:
        blockchain.register_node(node)
    response = {
        'message': "Новые узлы успешно добавлены",
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

# Эндпоинт для разрешения конфликтов (консенсус) (GET)
@app.route('/nodes/resolve', methods=['GET'])
@app.route('/consensus',      methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        return jsonify({
            "message":   "Наша цепочка была заменена",
            "new_chain": blockchain.chain
        }), 200
    else:
        return jsonify({
            "message": "Наша цепочка авторитетна",
            "chain":   blockchain.chain
        }), 200


@app.route('/wallet/new', methods=['GET'])
def new_wallet():
    from wallet import generate_keys
    private_key, public_key = generate_keys()
    response = {
        'private_key': private_key,
        'public_key': public_key
    }
    return jsonify(response), 200 


@app.route('/wallet/balance', methods=['GET'])
def wallet_balance():
    addr = request.args.get('address')
    if not addr:
        return "Не указан адрес",400
    bal = blockchain.balances.get(addr,0.0)
    return jsonify({'balance':bal}),200

@app.route('/wallet/history', methods=['GET'])
def wallet_history():
    address = request.args.get('address')
    if not address:
        return "Не указан адрес кошелька", 400
    history = blockchain.get_transaction_history(address)
    return jsonify({'history': history}), 200

@app.route('/wallet/keys', methods=['PUT'])
@jwt_required()
def update_wallet_keys():
    cu = get_jwt_identity()
    data = request.get_json() or {}
    priv = data.get('private_key'); pub = data.get('public_key')
    if not priv or not pub:
        return jsonify({'msg':'Нужны private_key и public_key'}),400
    users[cu]['wallet_private_key'] = priv
    users[cu]['wallet_public_key'] = pub
    if pub not in blockchain.balances:
        blockchain.balances[pub] = 0.0
    return jsonify({'wallet': {
        'private_key': priv, 'public_key': pub,
        'balance': blockchain.balances[pub]
    }}),200

# Новый эндпоинт для получения блока по индексу
@app.route('/block/<int:index>', methods=['GET'])
def get_block(index):
    if index < 1 or index > len(blockchain.chain):
        return jsonify({'message': 'Блок с таким индексом не найден'}), 404
    block = blockchain.chain[index - 1]
    return jsonify(block), 200

# Новый эндпоинт для получения транзакции по её id
@app.route('/transaction/<string:txid>', methods=['GET'])
def get_transaction(txid):
    for block in blockchain.chain:
        for tx in block['transactions']:
            if tx.get('id') == txid:
                return jsonify(tx), 200
    for tx in blockchain.current_transactions:
        if tx.get('id') == txid:
            return jsonify(tx), 200
    return jsonify({'message': 'Транзакция не найдена'}), 404

# Новый эндпоинт для получения статистики блокчейна
@app.route('/stats', methods=['GET'])
def stats():
    total_blocks = blockchain.global_index  # общее число добытых блоков (глобальный счётчик)
    total_transactions = sum(len(block['transactions']) for block in blockchain.chain)
    pending = len(blockchain.current_transactions)
    response = {
        'total_blocks': total_blocks,
        'total_transactions': total_transactions,
        'pending_transactions': pending
    }
    return jsonify(response), 200


# Новый эндпоинт для получения текущей сложности майнинга
@app.route('/difficulty', methods=['GET'])
def get_difficulty():
    return jsonify({'difficulty': blockchain.difficulty}), 200

# Новый эндпоинт для получения текущего базового вознаграждения (с учетом halving)
@app.route('/reward', methods=['GET'])
def get_reward():
    return jsonify({'current_reward': blockchain.get_current_reward()}), 200

@app.route('/transactions/pending', methods=['GET'])
def pending_transactions():
    response = {
        'pending_transactions': blockchain.current_transactions
    }
    return jsonify(response), 200

@app.route('/contract/deploy', methods=['POST'])
def deploy_contract_endpoint():
    """
    Эндпоинт для деплоя смарт-контракта.
    Ожидает JSON с полем "code", содержащим описание методов контракта.
    Например:
      {
         "code": {
            "increment": "def increment(state, params):\n    state['counter'] = state.get('counter', 0) + params.get('value', 1)\n    return state['counter']"
         },
         "state": {"counter": 0}   // опционально
      }
    Для простоты мы будем ожидать, что код передается не как строка, а как объект, содержащий уже готовые функции.
    В реальном проекте код можно компилировать или интерпретировать из строки.
    """
    values = request.get_json()
    code = values.get("code")
    state = values.get("state", {})
    if not code:
        return jsonify({"message": "Не передан код смарт‑контракта"}), 400
    try:
        # Здесь предполагается, что code — это словарь, где функции уже доступны.
        # В реальной среде потребуется безопасное выполнение кода.
        address = deploy_contract(code, state)
        return jsonify({"message": "Смарт-контракт задеплоен", "address": address}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/contract/call', methods=['POST'])
def call_contract_endpoint():
    """
    Эндпоинт для вызова метода смарт-контракта.
    Ожидает JSON с полями "address" (адрес контракта), "method" (имя метода) и "params" (параметры вызова).
    """
    values = request.get_json()
    address = values.get("address")
    method = values.get("method")
    params = values.get("params", {})
    if not address or not method:
        return jsonify({"message": "Не указаны необходимые параметры"}), 400
    try:
        result = call_contract(address, method, params)
        return jsonify({"result": result}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/contract/list', methods=['GET'])
def list_contracts():
    """
    Эндпоинт для получения списка задеплоенных смарт‑контрактов.
    Здесь мы просто возвращаем адреса контрактов из глобального хранилища.
    """
    from smart_contract import smart_contracts
    return jsonify({"contracts": list(smart_contracts.keys())}), 200

@app.route('/transaction/<string:txid>/merkle_proof', methods=['GET'])
def merkle_proof(txid):
    proof = blockchain.get_merkle_proof(txid)
    if proof is None:
        return jsonify({'message': 'Транзакция не найдена или не включена в блок'}), 404
    return jsonify({'merkle_proof': proof}), 200

def broadcast_new_block(block):
    for node in blockchain.nodes:
        url = f'http://{node}/block/receive'
        try:
            requests.post(url, json=block)
        except Exception:
            continue

@app.route('/nodes/list', methods=['GET'])
def list_nodes():
    """
    Получение списка зарегистрированных узлов.
    ---
    responses:
      200:
        description: Список узлов
    """
    return jsonify({'nodes': list(blockchain.nodes)}), 200

@app.route('/ping', methods=['GET'])
def ping():
    """
    Ping API endpoint.
    ---
    responses:
      200:
        description: Pong response
    """
    return jsonify({"message": "pong"}), 200

def check_peer_health():
    unhealthy_nodes = []
    for node in list(blockchain.nodes):
        try:
            response = requests.get(f'http://{node}/ping', timeout=5)
            if response.status_code != 200:
                unhealthy_nodes.append(node)
        except Exception:
            unhealthy_nodes.append(node)
    for node in unhealthy_nodes:
        blockchain.nodes.remove(node)
    if unhealthy_nodes:
        print("Removed unhealthy nodes:", unhealthy_nodes)

@app.route('/exchange_rate', methods=['GET'])
def exchange_rate():
    """
    Эндпоинт для получения курса Bitcoin к USD с использованием API CoinGecko.
    """
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        data = r.json()
        rate = data.get("bitcoin", {}).get("usd")
        if rate:
            return jsonify({"bitcoin_usd": rate}), 200
        else:
            return jsonify({"error": "Нет данных"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    u = data.get('username')
    p = data.get('password')
    rec = users.get(u)
    if not rec or not check_password_hash(rec['password'], p):
        return jsonify({'msg': 'Неверное имя или пароль'}), 401
    token = create_access_token(identity=u)
    return jsonify({'access_token': token}), 200

# ------------ ПРОФИЛЬ ---------------
@app.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current = get_jwt_identity()
    user = users.get(current)
    if not user:
        return jsonify({"msg": "User not found"}), 404
    return jsonify(user), 200

@app.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    current = get_jwt_identity()
    if current not in users:
        return jsonify({"msg": "User not found"}), 404
    data = request.get_json() or {}
    email = data.get("email")
    name  = data.get("name")
    if email:
        users[current]["email"] = email
    if name:
        users[current]["name"] = name
    from users_storage import save_users
    save_users(users)
    return jsonify({"profile": users[current]}), 200


@app.route('/events', methods=['GET'])
def get_events():
    # Здесь предполагается, что вы храните события централизованно или собираете их из всех смарт-контрактов.
    # Для простоты можно пройтись по всем контрактам в глобальном хранилище smart_contracts.
    events = []
    from smart_contract import smart_contracts  # предполагается, что это глобальная переменная
    for contract in smart_contracts.values():
        events = events.concat(contract.events)  # или используйте другой способ объединения списков
    return jsonify({"events": events}), 200

def periodic_prune():
    blockchain.prune_chain(max_blocks=100)


# Mine one block per interval if active miner set
def scheduled_mining():
    if blockchain.active_miner:
        try:
            block = blockchain.mine_block(blockchain.active_miner)
            publish_new_block(block)
            blocks_mined_total.inc()
            transactions_total.inc(len(block['transactions']))
            socketio.emit('new_block', block)
            logging.info(f"Mined block #{block['index']} by {blockchain.active_miner}")
        except Exception as e:
            logging.error(f"Mining error: {e}")

@app.route('/oracle/price', methods=['GET'])
def get_bitcoin_price():
    try:
        # Запрос к CoinGecko API для получения курса Bitcoin в USD
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        data = response.json()
        price = data.get("bitcoin", {}).get("usd")
        if price is None:
            return jsonify({"message": "Нет данных о цене Bitcoin"}), 500
        return jsonify({"price_usd": price}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

def update_contract_price():
    try:
        # Запрашиваем курс Bitcoin
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        data = response.json()
        price = data.get("bitcoin", {}).get("usd")
        if price is None:
            print("Нет данных по цене Bitcoin.")
            return
        # Вызываем метод update_price смарт‑контракта
        from smart_contract import call_contract  # убедитесь, что эта функция доступна
        result = call_contract(oracle_contract_address, "update_price", {"price": price})
        print(f"Обновлена цена в смарт‑контракте: {result}")
    except Exception as e:
        print("Ошибка при обновлении цены в контракте:", e)

@app.route('/contract/<address>/events', methods=['GET'])
def get_contract_events(address):
    # Предполагаем, что смарт‑контракты хранятся в глобальной переменной smart_contracts
    from smart_contract import smart_contracts
    contract = smart_contracts.get(address)
    if not contract:
        return jsonify({"message": "Смарт‑контракт не найден"}), 404
    return jsonify({"events": contract.events}), 200


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    u = data.get('username')
    p = data.get('password')
    if not u or not p or u in users:
        return jsonify({'msg': 'Нужны и username, и password или пользователь уже существует'}), 400
    users[u] = {'username': u, 'password': generate_password_hash(p), 'email': '', 'name': '',
                'nonce': 0, 'wallet_private_key': '', 'wallet_public_key': ''}
    token = create_access_token(identity=u)
    return jsonify({'access_token': token}), 201


@app.route('/scheduler/status', methods=['GET'])
def scheduler_status():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": str(job.next_run_time),
            "trigger": str(job.trigger)
        })
    return jsonify({
        "running": scheduler.running,
        "jobs": jobs
    }), 200

# Листенер для логирования результатов и ошибок
def scheduler_listener(event: JobExecutionEvent):
    job = scheduler.get_job(event.job_id)
    if event.exception:
        app.logger.error(f"[APS] Job {event.job_id} ({job.name if job else 'n/a'}) failed: {event.exception}")
    else:
        app.logger.info(f"[APS] Job {event.job_id} ({job.name if job else 'n/a'}) succeeded")



scheduler.add_listener(
    scheduler_listener,
    mask=EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
)

# Задаем адрес seed-узла
SEED_NODE = 'http://localhost:5000'

# Планировщик задач
# Запускаем фоновые задачи через APScheduler

scheduler.add_job(func=periodic_consensus, trigger="interval", seconds=30)
scheduler.add_job(func=peer_discovery, trigger="interval", seconds=60)
scheduler.add_job(func=check_peer_health, trigger="interval", seconds=60)
scheduler.add_job(func=periodic_prune, trigger="interval", seconds=120)  # каждые 2 минуты
scheduler.add_job(func=update_contract_price, trigger='interval', seconds=60)  # обновлять раз в минуту
scheduler.add_job(func=scheduled_mining, trigger='interval', seconds=30)
scheduler.start()
app.logger.info("[APS] Scheduler started")


def handle_exit(signum, frame):
    print("Shutting down scheduler…")
    scheduler.shutdown(wait=False)
    # после этого можно sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

atexit.register(lambda: scheduler.shutdown(wait=False))



if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='Порт для запуска сервера')
    args = parser.parse_args()
    port = args.port
    socketio.run(app, host='0.0.0.0', port=port)
