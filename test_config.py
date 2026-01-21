import os
import yaml
from dotenv import load_dotenv

load_dotenv()

print("=" * 50)
print("ПРОВЕРКА КОНФИГУРАЦИИ")
print("=" * 50)

# Проверка .env
print("\n🔍 Проверка .env файла:")
vk_token = os.getenv('VK_TOKEN')
discord_webhook = os.getenv('DISCORD_WEBHOOK')

if vk_token:
    print(f"✅ VK_TOKEN: {vk_token[:20]}...")
else:
    print("❌ VK_TOKEN не найден")

if discord_webhook:
    print(f"✅ DISCORD_WEBHOOK: {discord_webhook[:50]}...")
else:
    print("❌ DISCORD_WEBHOOK не найден")

# Проверка config.yaml
print("\n🔍 Проверка config.yaml файла:")
try:
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print(f"✅ Файл загружен")

    # Проверка групп
    groups = config.get('groups', [])
    print(f"✅ Найдено групп: {len(groups)}")

    for i, group in enumerate(groups, 1):
        print(f"  {i}. {group.get('name', 'Без имени')} (id: {group.get('id')})")

except Exception as e:
    print(f"❌ Ошибка загрузки config.yaml: {e}")

print("\n" + "=" * 50)
print("РЕКОМЕНДАЦИИ:")
if not vk_token:
    print("1. Получите токен ВК по инструкции")
if not discord_webhook:
    print("2. Создайте Discord webhook")
if not groups:
    print("3. Добавьте группы в config.yaml")
print("=" * 50)