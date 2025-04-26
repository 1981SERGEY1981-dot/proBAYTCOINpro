from smart_contract import deploy_contract, call_contract, increment

code = {
    "increment": increment
}
state = {"counter": 0}
contract_address = deploy_contract(code, state)
print("Контракт задеплоен по адресу:", contract_address)

# Вызов метода "increment":
result = call_contract(contract_address, "increment", {"value": 5})
print("Новый счетчик:", result)
