#!/usr/bin/env python3
"""
Тестирование конфигурации VK2Discord Bot
Запуск: python test_config.py
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

print("=" * 50)
print("🔧 ТЕСТИРОВАНИЕ КОНФИГУРАЦИИ VK2Discord BOT")
print("=" * 50)

# Проверка обязательных переменных
required_vars = [
    'VK_TOKEN',
    'DISCORD_WEBHOOK',
    'DISCORD_THREAD_WEBHOOK'
]

optional_vars = [
    'DISCORD_THREAD_ID'
]

print("\n📋 Проверка переменных окружения:")
print("-" * 30)

all_good = True

# Проверка обязательных переменных
for var in required_vars:
    value = os.getenv(var)
    if value:
        masked = value[:10] + "..." + value[-10:] if len(value) > 20 else value
        print(f"✅ {var}: {masked}")
    else:
        print(f"❌ {var}: НЕ НАЙДЕН")
        all_good = False

# Проверка опциональных переменных
print("\n📋 Опциональные переменные:")
print("-" * 30)
for var in optional_vars:
    value = os.getenv(var)
    if value:
        masked = value[:10] + "..." + value[-10:] if len(value) > 20 else value
        print(f"✅ {var}: {masked}")
    else:
        print(f"⚠️  {var}: не указан (опционально)")

# Проверка config.yaml
print("\n📋 Проверка config.yaml:")
print("-" * 30)
try:
    import yaml

    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if 'groups' in config and len(config['groups']) > 0:
        print(f"✅ Группы для отслеживания: {len(config['groups'])}")
        for group in config['groups']:
            print(f"   • {group.get('name', 'Без имени')} (ID: {group.get('id', 'N/A')})")
    else:
        print("❌ Нет групп для отслеживания в config.yaml")
        all_good = False

    if 'bot' in config and 'interval' in config['bot']:
        print(f"✅ Интервал проверки: {config['bot']['interval']} секунд")
    else:
        print("⚠️  Интервал проверки не указан (будет использоваться значение по умолчанию: 60 сек)")

except Exception as e:
    print(f"❌ Ошибка при чтении config.yaml: {e}")
    all_good = False

# Тестирование подключений
print("\n📡 Тестирование подключений:")
print("-" * 30)


def test_discord_webhook(webhook_url, name):
    """Тестирует Discord вебхук"""
    try:
        test_message = {
            "content": f"✅ Тестовое сообщение от VK2Discord Bot ({name})",
            "username": "VK Bot Tester"
        }

        response = requests.post(
            webhook_url,
            json=test_message,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        if response.status_code in [200, 204]:
            return True, f"✅ {name}: Работает (статус: {response.status_code})"
        else:
            return False, f"❌ {name}: Ошибка {response.status_code} - {response.text[:100]}"
    except Exception as e:
        return False, f"❌ {name}: Ошибка подключения - {str(e)}"


# Тестируем основной вебхук
webhook1 = os.getenv('DISCORD_WEBHOOK')
if webhook1:
    success, message = test_discord_webhook(webhook1, "Основной вебхук (обычные посты)")
    print(message)
    if not success:
        all_good = False
else:
    print("❌ Основной вебхук не найден")

# Тестируем вебхук для треда
webhook2 = os.getenv('DISCORD_THREAD_WEBHOOK')
thread_id = os.getenv('DISCORD_THREAD_ID')

if webhook2:
    if thread_id:
        # Формируем URL с thread_id
        webhook_url_with_thread = f"{webhook2}?thread_id={thread_id}"
        success, message = test_discord_webhook(webhook_url_with_thread, "Вебхук для треда (посты с 🗓)")
        print(message)
        if not success:
            all_good = False
    else:
        print("⚠️  Вебхук для треда найден, но DISCORD_THREAD_ID не указан")
        # Тестируем без thread_id
        success, message = test_discord_webhook(webhook2, "Вебхук для треда (без thread_id)")
        print(message)
        if not success:
            print("   ℹ️  Это может быть нормально, если вебхук не для форум-канала")
else:
    print("❌ Вебхук для треда не найден")

# Тестирование VK API (базовое)
print("\n🔗 Тестирование VK API:")
print("-" * 30)
vk_token = os.getenv('VK_TOKEN')
if vk_token:
    try:
        import vk_api

        vk_session = vk_api.VkApi(token=vk_token)
        vk = vk_session.get_api()
        # Простой запрос для проверки токена
        user_info = vk.users.get()
        print(f"✅ VK API: Токен работает. ID пользователя: {user_info[0]['id']}")
    except Exception as e:
        print(f"❌ VK API: Ошибка - {str(e)}")
        all_good = False
else:
    print("❌ VK_TOKEN не найден")

# Итог
print("\n" + "=" * 50)
if all_good:
    print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("Бот готов к запуску!")
else:
    print("⚠️  НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
    print("Пожалуйста, проверьте конфигурацию и попробуйте снова.")
print("=" * 50)

# Рекомендации
print("\n📝 РЕКОМЕНДАЦИИ:")
print("-" * 30)
print("1. Убедитесь, что вебхуки созданы в правильных каналах:")
print("   • DISCORD_WEBHOOK - обычный текстовый канал")
print("   • DISCORD_THREAD_WEBHOOK - форум-канал")
print("2. DISCORD_THREAD_ID нужен, если вебхук для форум-канала")
print("3. Для получения Thread ID в Discord:")
print("   • Настройки → Дополнительно → Режим разработчика (включить)")
print("   • Правой кнопкой на тред → Копировать ID")
print("4. Для Railway добавьте все переменные в разделе 'Variables'")

if __name__ == "__main__":
    sys.exit(0 if all_good else 1)