import pytest
import json
import app as application  # ваше приложение лежит в app.py

@pytest.fixture
def client():
    application.app.config['TESTING'] = True
    # очищаем пользователей между тестами
    application.users.clear()
    with application.app.test_client() as c:
        yield c

def test_ping(client):
    """Проверяем, что /ping отдаёт {'message': 'pong'}."""
    rv = client.get('/ping')
    assert rv.status_code == 200
    assert rv.get_json() == {"message": "pong"}

def test_register_and_login_and_profile_flow(client):
    """Регистрация → вход → просмотр/обновление профиля."""
    username = "testuser"
    password = "testpass"

    # Регистрация
    rv = client.post('/register', json={"username": username, "password": password})
    assert rv.status_code == 201
    token = rv.get_json()["access_token"]

    # Повторная регистрация того же приводит к 400
    rv2 = client.post('/register', json={"username": username, "password": password})
    assert rv2.status_code == 400

    # Вход
    rv = client.post('/login', json={"username": username, "password": password})
    assert rv.status_code == 200
    token = rv.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # GET /profile
    rv = client.get('/profile', headers=headers)
    assert rv.status_code == 200
    profile = rv.get_json()
    assert profile["username"] == username

    # PUT /profile
    new_email = "alice@example.com"
    new_name = "Alice"
    rv = client.put('/profile', headers=headers,
                    data=json.dumps({"email": new_email, "name": new_name}))
    assert rv.status_code == 200
    updated = rv.get_json()["profile"]
    assert updated["email"] == new_email
    assert updated["name"] == new_name

def test_wallet_key_update_and_balance(client):
    """Обновление ключей и баланс."""
    # Регистрация + логин
    rv = client.post('/register', json={"username": "walletuser", "password": "pw"})
    assert rv.status_code == 201
    token = rv.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # PUT /wallet/keys
    priv, pub = "priv_key_example", "pub_key_example"
    rv = client.put('/wallet/keys', headers=headers,
                    data=json.dumps({"private_key": priv, "public_key": pub}))
    assert rv.status_code == 200
    w = rv.get_json()["wallet"]
    assert w["private_key"] == priv
    assert w["public_key"] == pub

    # GET /wallet/balance
    rv = client.get(f'/wallet/balance?address={pub}')
    assert rv.status_code == 200
    bal = rv.get_json()["balance"]
    assert isinstance(bal, (int, float))

def test_transaction_and_mining(client):
    """Транзакция alice→bob и майнинг."""
    # готовим alice
    rv1 = client.post('/register', json={"username": "alice", "password": "pw1"})
    tok1 = rv1.get_json()['access_token']
    h1 = {"Authorization": f"Bearer {tok1}", "Content-Type": "application/json"}
    client.put('/wallet/keys', headers=h1, json={"private_key":"a_priv","public_key":"a_pub"})

    # готовим bob
    rv2 = client.post('/register', json={"username": "bob", "password": "pw2"})
    tok2 = rv2.get_json()['access_token']
    h2 = {"Authorization": f"Bearer {tok2}", "Content-Type": "application/json"}
    client.put('/wallet/keys', headers=h2, json={"private_key":"b_priv","public_key":"b_pub"})

    # alice назначается майнером
    rv = client.post('/set_miner', headers=h1)
    assert rv.status_code == 204

    # alice майнит
    rv = client.post('/mine', headers=h1)
    assert rv.status_code == 200
    blk = rv.get_json()
    assert "index" in blk

    # баланс alice > 0
    bal_alice = client.get('/wallet/balance?address=a_pub').get_json()["balance"]
    assert bal_alice > 0

    # транзакция alice→bob
    amount = bal_alice / 2
    rv = client.post('/transaction', headers=h1,
                     json={"recipient": "b_pub", "amount": amount})
    assert rv.status_code == 201

    # консенсус
    rv = client.get('/consensus')
    assert rv.status_code == 200

    # проверяем, что балансы скорректировались
    ra = client.get('/wallet/balance?address=a_pub').get_json()["balance"]
    rb = client.get('/wallet/balance?address=b_pub').get_json()["balance"]
    assert rb >= amount
    assert ra <= bal_alice - amount

def test_chain_structure(client):
    """Проверяем, что /chain возвращает список блоков."""
    rv = client.get('/chain')
    assert rv.status_code == 200
    js = rv.get_json()
    assert isinstance(js.get("chain"), list)
    # у каждого блока обязательные поля
    for blk in js["chain"]:
        for key in ("index","timestamp","transactions","proof","previous_hash"):
            assert key in blk
