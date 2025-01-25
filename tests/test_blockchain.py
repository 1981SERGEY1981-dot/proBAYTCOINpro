import unittest

from src.blockchain import Blockchain


class TestBlockchain(unittest.TestCase):
    def setUp(self):
        self.blockchain = Blockchain(difficulty=2, mining_reward=50)

    def test_create_genesis_block(self):
        self.assertEqual(len(self.blockchain.chain), 1)
        self.assertEqual(self.blockchain.chain[0].index, 0)
        print("Количество блоков в блокчейне:", len(self.blockchain.chain))

    def test_create_transaction(self):
        self.blockchain.create_transaction("Alice", "Bob", 10)
        self.assertEqual(len(self.blockchain.pending_transactions), 1)

    def test_mine_block(self):
        self.blockchain.mine_pending_transactions("Miner1")

        # Добавляем транзакцию
        self.blockchain.add_transaction(
            {"sender": "Alice", "recipient": "Bob", "amount": 10}
        )
        self.assertEqual(
            len(self.blockchain.pending_transactions),
            1,
            "Транзакция не добавлена в список ожидания.",
        )

        # Добавление транзакций
        self.blockchain.create_transaction("Alice", "Bob", 10)
        self.blockchain.create_transaction("Bob", "Charlie", 20)

        # Майнинг блока
        self.blockchain.mine_block("Miner1", ignore_time_limit=True)

        # Выполняем майнинг
        block = self.blockchain.mine_block("Miner1")
        self.assertIsNotNone(block, "Майнинг не создал блок.")
        self.assertEqual(len(self.blockchain.chain), 2,
                         "Блок не добавлен в цепочку.")

        # Проверяем длину цепочки
        self.assertEqual(len(self.blockchain.chain), 2)

        # Проверяем наградную транзакцию
        last_block = self.blockchain.get_latest_block()
        reward_transaction = last_block.transactions[-1]
        self.assertEqual(reward_transaction["recipient"], "Miner1")
        self.assertEqual(reward_transaction["amount"], 50)

        # Проверяем транзакции в блоке
        self.assertEqual(
            block.transactions[0]["sender"], "Alice", "Неверный отправитель."
        )
        self.assertEqual(
            block.transactions[0]["recipient"], "Bob", "Неверный получатель."
        )
        self.assertEqual(
            block.transactions[0]["amount"],
            10,
            "Неверная сумма.")

    def test_validate_chain(self):
        blockchain = Blockchain()
        blockchain.add_transaction("Alice", "Bob", 10)
        blockchain.mine_block("Miner1")
        self.assertTrue(
            blockchain.validate_chain(),
            "Цепочка блоков невалидна.")
        self.blockchain.create_transaction("Alice", "Bob", 10)
        self.blockchain.mine_block("Miner1")
        self.assertTrue(self.blockchain.validate_chain())

    def test_multiple_blocks_mining(self):
        # Создание первого блока
        self.blockchain.create_transaction("Alice", "Bob", 10)
        self.blockchain.mine_block("Miner1", ignore_time_limit=True)

        # Создание второго блока
        self.blockchain.create_transaction("Charlie", "Alice", 5)
        self.blockchain.mine_block("Miner1", ignore_time_limit=True)

        # Проверка длины цепочки
        self.assertEqual(len(self.blockchain.chain), 3)

        # Проверка содержимого последнего блока
        last_block = self.blockchain.get_latest_block()
        print("Текущие транзакции в последнем блоке:", last_block.transactions)

        # Убедитесь, что транзакция Charlie -> Alice присутствует
        found_transaction = any(
            tx["recipient"] == "Alice" and tx["sender"] == "Charlie"
            for tx in last_block.transactions
        )
        self.assertTrue(
            found_transaction,
            "Транзакция Charlie -> Alice отсутствует в последнем блоке",
        )

    def test_mining_block_with_transactions(self):
        # Шаг 1: Добавляем транзакцию
        self.blockchain.create_transaction("Alice", "Bob", 10)
        self.assertEqual(
            len(self.blockchain.pending_transactions),
            1,
            "Транзакция не добавлена в список.",
        )

        # Шаг 2: Запускаем майнинг
        mined_block = self.blockchain.mine_block(
            "Miner1", ignore_time_limit=True)
        self.assertIsNotNone(mined_block, "Майнинг не создал блок.")

        # Шаг 3: Проверяем длину цепочки блоков
        self.assertEqual(len(self.blockchain.chain), 2,
                         "Блок не добавлен в цепочку.")

        # Шаг 4: Проверяем содержимое последнего блока
        last_block = self.blockchain.get_latest_block()
        self.assertEqual(
            last_block.transactions[0]["sender"],
            "Alice",
            "Неверный отправитель в транзакции.",
        )
        self.assertEqual(
            last_block.transactions[0]["recipient"],
            "Bob",
            "Неверный получатель в транзакции.",
        )
        self.assertEqual(
            last_block.transactions[0]["amount"], 10, "Неверная сумма транзакции."
        )
        self.assertEqual(
            last_block.transactions[-1]["recipient"],
            "Miner1",
            "Неверный адрес получателя награды.",
        )
        self.assertEqual(
            last_block.transactions[-1]["amount"], 50, "Неверная сумма награды майнеру."
        )

    def test_add_transaction(self):
        blockchain = Blockchain()
        blockchain.add_transaction("Alice", "Bob", 10)
        self.assertEqual(
            len(blockchain.pending_transactions), 1, "Транзакция не была добавлена."
        )
        self.assertEqual(
            blockchain.pending_transactions[0]["sender"],
            "Alice",
            "Некорректный отправитель.",
        )
        self.assertEqual(
            blockchain.pending_transactions[0]["recipient"],
            "Bob",
            "Некорректный получатель.",
        )
        self.assertEqual(
            blockchain.pending_transactions[0]["amount"], 10, "Некорректная сумма."
        )

    def test_api_mine(self):
        with self.node.app.test_client() as client:
            # Добавляем транзакцию
            response = client.post(
                "/transaction/new",
                json={"sender": "Alice", "recipient": "Bob", "amount": 10},
            )
            self.assertEqual(
                response.status_code,
                201,
                "Транзакция не добавлена.")
            # Запускаем майнинг
            response = client.get(
                "/mine",
                query_string={
                    "miner_address": "Miner1"})
            self.assertEqual(response.status_code, 200, "Майнинг не выполнен.")
            data = response.get_json()
            self.assertIn("Блок успешно замайнен!", data["message"])
            self.assertIn("block", data)


if __name__ == "__main__":
    unittest.main()
