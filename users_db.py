from werkzeug.security import generate_password_hash
from users_storage import users, save_users

def register_user(username, password, email="", name=""):
    # Выводим текущие пользователи для отладки
    print("Попытка регистрации для", username)
    print("Текущие пользователи до регистрации:", users)
    if username in users:
        print(f"Пользователь {username} уже существует.")
        return None  # Или выбросьте исключение
    hashed_password = generate_password_hash(password)
    # При регистрации добавляем поле nonce со значением 0
    users[username] = {
        "username": username,
        "password": hashed_password,
        "email": email,
        "name": name,
        "nonce": 0,
        "wallet_private_key": "",
        "wallet_public_key": ""
    }
    save_users(users)  # Этот вызов должен записать данные в файл users.json
    print("После регистрации, пользователи:", users)
    return users[username]
