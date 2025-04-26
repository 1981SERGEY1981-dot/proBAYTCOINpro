import requests
import os

# Рекомендуется хранить URL вебхука в переменной окружения для безопасности,
# например, SLACK_WEBHOOK_URL. Если переменная не задана, можно использовать строку по умолчанию.
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/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")

def notify_slack(message, webhook_url=SLACK_WEBHOOK_URL):
    payload = {"text": message}
    response = requests.post(webhook_url, json=payload)
    if response.status_code != 200:
        print("Ошибка отправки уведомления в Slack:", response.text)

