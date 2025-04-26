import uuid
import time

# Глобальное хранилище для смарт-контрактов
smart_contracts = {}

class SmartContract:
    def __init__(self, code, state=None):
        """
        code: словарь, где ключ – имя метода, а значение – функция.
              Функция должна принимать первым параметром экземпляр контракта (self) и словарь параметров.
        state: начальное состояние контракта (словарь)
        """
        self.address = str(uuid.uuid4())
        self.code = code  # Пример: {"increment": increment_function, ...}
        self.state = state or {}
        self.events = []  # Список событий, эмитированных контрактом
        # После создания контракта добавляем его в глобальное хранилище:
        smart_contracts[self.address] = self

    def execute(self, method, params):
        if method in self.code:
            # Вызываем функцию, передавая текущее состояние и параметры вызова
            return self.code[method](self, params)
        else:
            raise Exception("Method not found")

    def emit_event(self, event_name, event_data):
        """
        Регистрирует событие с именем event_name и данными event_data.
        Возвращает объект события.
        """
        event = {
            "event_name": event_name,
            "event_data": event_data,
            "timestamp": int(time.time())
        }
        self.events.append(event)
        # Здесь можно добавить интеграцию с внешней системой (например, отправку через HTTP)
        return event



def deploy_contract(code, state=None):
    """
    Деплой смарт-контракта.
    code: словарь с методами (функциями). Например:
          {
              "increment": increment_function,
              "decrement": decrement_function
          }
    state: начальное состояние контракта (опционально)
    Возвращает адрес задеплоенного контракта.
    """
    contract = SmartContract(code, state)
    smart_contracts[contract.address] = contract
    return contract.address

def call_contract(address, method, params):
    """
    Вызывает метод смарт‑контракта по его адресу.
    """
    contract = smart_contracts.get(address)
    if not contract:
        raise Exception("Смарт‑контракт не найден.")
    return contract.execute(method, params)

# Пример метода смарт‑контракта "increment"
def increment(contract, params):
    # Получаем значение, на которое нужно увеличить счетчик (по умолчанию 1)
    increment_value = params.get("value", 1)
    current = contract.state.get("counter", 0)
    new_value = current + increment_value
    contract.state["counter"] = new_value
    # Эмитируем событие "Increment"
    contract.emit_event("Increment", {"old_value": current, "new_value": new_value})
    return new_value

def update_price(contract, params):
    # params должно содержать поле "price"
    new_price = params.get("price")
    if new_price is None:
        raise Exception("Цена не передана")
    contract.state["bitcoin_price_usd"] = new_price
    # Эмитируем событие обновления
    contract.emit_event("PriceUpdate", {"new_price": new_price})
    return new_price

def vote(contract, params):
    # Ожидается, что params содержит поле "candidate"
    candidate = params.get("candidate")
    if not candidate:
        raise Exception("Имя кандидата не указано")
    
    # Получаем или создаём словарь голосов в состоянии контракта
    votes = contract.state.get("votes", {})
    votes[candidate] = votes.get(candidate, 0) + 1
    contract.state["votes"] = votes
    
    # Эмитируем событие голосования
    contract.emit_event("Vote", {"candidate": candidate, "votes": votes[candidate]})
    return votes[candidate]
