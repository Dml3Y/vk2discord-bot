import os
import requests
from dotenv import load_dotenv

load_dotenv()


def test_discord():
    webhook = os.getenv('DISCORD_WEBHOOK')

    if not webhook:
        print("❌ DISCORD_WEBHOOK не найден в .env")
        return False

    print(f"Webhook URL: {webhook[:50]}...")

    # Пробуем разные типы сообщений
    test_messages = [
        {"content": "✅ Тест 1: Простое сообщение"},
        {"content": "✅ Тест 2: Сообщение с именем", "username": "VK Test Bot"},
        {"content": "✅ Тест 3: Длинное " + "сообщение " * 50}
    ]

    for i, message in enumerate(test_messages, 1):
        print(f"\nТест {i}: {message['content'][:30]}...")

        try:
            # Без прокси
            print("  Без прокси...")
            response = requests.post(webhook, json=message, timeout=10)
            print(f"    Статус: {response.status_code}")

            # # С прокси
            # print("  С прокси...")
            # proxies = {'http': 'http://45.61.187.67:4001', 'https': 'http://45.61.187.67:4001'}
            # response = requests.post(webhook, json=message, timeout=10, proxies=proxies)
            # print(f"    Статус: {response.status_code}")

        except Exception as e:
            print(f"    Ошибка: {e}")

    return True


if __name__ == "__main__":
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ DISCORD WEBHOOK")
    print("=" * 50)
    test_discord()