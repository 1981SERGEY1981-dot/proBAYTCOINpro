# deploy_oracle_contract.py

from smart_contract import deploy_contract, update_price, increment, smart_contracts, vote

# Определяем код смарт‑контракта (словарь с методами)
code = {
    "update_price": update_price,
    "increment": increment,  # другой метод, если требуется
    "vote": vote  # Добавлен новый метод голосования
}

# Определяем начальное состояние контракта (например, цена Bitcoin изначально равна 0)
state = {
    "bitcoin_price_usd": 0,
    "votes": {}  # Начальное состояние для голосования, пустой словарь
}

# Вызываем функцию для деплоя контракта
address = deploy_contract(code, state)
print("Смарт‑контракт задеплоен по адресу:", address)
