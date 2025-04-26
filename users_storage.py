import json
import os

USERS_FILE = 'users.json'


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

# Функция обновления баланса
def update_user_balance(address, amount):
    users = load_users()
    # Если пользователя нет — создаём запись с нулевым базисом
    if address not in users:
        users[address] = {
            "username": "",
            "password": "",
            "email": "",
            "name": "",
            "nonce": 0,
            "wallet_private_key": "",
            "wallet_public_key": address,
            "balance": 0
        }
    users[address]["balance"] = users[address].get("balance", 0) + amount
    save_users(users)
    print(f"[DEBUG] Баланс пользователя {address} обновлён до {users[address]['balance']}")
    return users[address]["balance"]

# Изначальное хранилище
users = load_users()

