import threading
import redis
import json

# Настройте подключение к Redis (используем настройки по умолчанию)
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Каналы для обмена событиями
NEW_BLOCK_CHANNEL = "new_block"
NEW_TRANSACTION_CHANNEL = "new_transaction"

def publish_new_block(block):
    # Публикуем сообщение в канал, преобразуя объект блока в JSON
    redis_client.publish(NEW_BLOCK_CHANNEL, json.dumps(block))
    print(f"Блок с индексом {block['index']} опубликован через P2P.")

def publish_new_transaction(transaction):
    redis_client.publish(NEW_TRANSACTION_CHANNEL, json.dumps(transaction))

def subscribe_to_channel(channel, callback):
    pubsub = redis_client.pubsub()
    pubsub.subscribe(channel)

    # Функция обработки сообщений в отдельном потоке
    def listen():
        for message in pubsub.listen():
            # Сообщения с типом 'message' содержат полезные данные
            if message['type'] == 'message':
                data = json.loads(message['data'])
                callback(data)
    thread = threading.Thread(target=listen)
    thread.daemon = True
    thread.start()
    return pubsub
