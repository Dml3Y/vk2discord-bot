#!/usr/bin/env python3
"""
VK to Discord Bot для облачного развертывания
"""

import os
import sys
import time
import signal
import json
import yaml
import logging
from datetime import datetime
from typing import Dict, List

import vk_api
import requests
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class VK2DiscordBot:
    def __init__(self):
        """Инициализация бота"""
        # Загрузка конфигурации из переменных окружения
        self.vk_token = os.getenv('VK_TOKEN')
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK')

        if not self.vk_token:
            raise ValueError("VK_TOKEN не установлен в переменных окружения")
        if not self.discord_webhook:
            raise ValueError("DISCORD_WEBHOOK не установлен в переменных окружения")

        # Загрузка конфигурации групп
        self.config = self.load_config()

        # Инициализация VK API
        self.vk_session = vk_api.VkApi(token=self.vk_token)
        self.vk = self.vk_session.get_api()

        # Состояние бота
        self.last_posts = {}
        self.running = True

        # Обработка сигналов для graceful shutdown
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)

        logger.info("Бот инициализирован для облачного запуска")

    def load_config(self):
        """Загрузка конфигурации"""
        # Сначала пытаемся загрузить из переменной окружения (для Railway/Fly.io)
        config_yaml = os.getenv('CONFIG_YAML')
        if config_yaml:
            return yaml.safe_load(config_yaml)

        # Затем из файла (для локального запуска)
        config_paths = ['/app/config.yaml', 'config.yaml', './config.yaml']
        for path in config_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)

        # Если конфиг не найден, используем минимальную конфигурацию
        logger.warning("Конфигурационный файл не найден, используем настройки по умолчанию")
        return {
            'groups': [],
            'bot': {'interval': 60},
            'options': {
                'include_photos': True,
                'include_videos': True,
                'include_links': True,
                'truncate_text': True,
                'show_post_link': True
            }
        }

    def handle_shutdown(self, signum, frame):
        """Обработка сигнала завершения"""
        logger.info(f"Получен сигнал завершения {signum}, останавливаем бота...")
        self.running = False

    def get_group_info(self, group_id: str) -> Dict:
        """Получение информации о группе"""
        try:
            # Убираем 'vk.com/' если есть в начале
            if group_id.startswith('vk.com/'):
                group_id = group_id.replace('vk.com/', '')

            # Пробуем получить по screen_name
            try:
                group_info = self.vk.groups.getById(group_id=group_id, fields='description,photo_200')
                return group_info[0]
            except:
                # Пробуем по ID
                group_info = self.vk.groups.getById(group_id=int(group_id), fields='description,photo_200')
                return group_info[0]
        except Exception as e:
            logger.error(f"Ошибка получения информации о группе {group_id}: {e}")
            return {}

    def get_last_posts(self, group_id: str, count: int = 5) -> List[Dict]:
        """Получение последних постов из группы"""
        try:
            # Определяем ID группы
            if isinstance(group_id, str) and not group_id.isdigit():
                group_info = self.get_group_info(group_id)
                group_id = f"-{group_info['id']}"
            else:
                group_id = f"-{group_id}"

            # Получаем посты
            posts = self.vk.wall.get(
                owner_id=group_id,
                count=count,
                filter='owner'
            )

            return posts['items']
        except Exception as e:
            logger.error(f"Ошибка получения постов из {group_id}: {e}")
            return []

    def format_post(self, post: Dict, group_info: Dict) -> Dict:
        """Форматирование поста для Discord"""
        content = f"**📢 Новый пост из [{group_info.get('name', 'Группа')}](https://vk.com/{group_info.get('screen_name', '')})**\n\n"

        if post.get('text'):
            text = post['text']
            if len(text) > 1800:
                text = text[:1800] + "..."
            content += text + "\n\n"

        # Добавляем ссылку на пост
        post_id = post['id']
        owner_id = post['owner_id']
        content += f"[🔗 Ссылка на пост](https://vk.com/wall{owner_id}_{post_id})"

        embed = {
            "content": content,
            "username": group_info.get('name', 'VK Bot')[:32],
            "embeds": []
        }

        # Обработка вложений (только первая картинка)
        attachments = post.get('attachments', [])
        for attach in attachments:
            if attach['type'] == 'photo':
                photo = attach['photo']
                sizes = photo.get('sizes', [])
                if sizes:
                    # Ищем картинку хорошего качества
                    for quality in ['z', 'y', 'x', 'w', 'r']:
                        for size in sizes:
                            if size['type'] == quality:
                                embed["embeds"].append({
                                    "image": {"url": size['url']}
                                })
                                return embed
                    # Если не нашли нужного качества, берем последнюю (обычно самую большую)
                    embed["embeds"].append({
                        "image": {"url": sizes[-1]['url']}
                    })
                break

        return embed

    def send_to_discord(self, embed: Dict) -> bool:
        """Отправка сообщения в Discord через webhook"""
        try:
            response = requests.post(
                self.discord_webhook,
                json=embed,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            if response.status_code in [200, 204]:
                return True
            else:
                logger.error(f"Ошибка Discord: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Ошибка отправки в Discord: {e}")
            return False

    def check_new_posts(self):
        """Проверка новых постов"""
        groups = self.config.get('groups', [])

        for group_config in groups:
            if not self.running:
                break

            group_id = group_config['id']

            try:
                # Получаем информацию о группе
                group_info = self.get_group_info(group_id)
                if not group_info:
                    continue

                # Получаем последние посты
                posts = self.get_last_posts(group_id, count=2)
                if not posts:
                    continue

                # Проверяем последний пост
                latest_post = posts[0]
                post_key = f"{group_id}_{latest_post['id']}"

                if post_key not in self.last_posts:
                    logger.info(f"Найден новый пост: {latest_post['id']} из {group_info.get('name')}")

                    # Форматируем и отправляем
                    embed = self.format_post(latest_post, group_info)

                    # Отправляем в Discord
                    if self.send_to_discord(embed):
                        logger.info(f"Пост {latest_post['id']} отправлен в Discord")

                    # Сохраняем ID поста
                    self.last_posts[post_key] = datetime.now()

                    # Ограничиваем размер словаря
                    if len(self.last_posts) > 50:
                        # Удаляем самые старые записи
                        oldest = sorted(self.last_posts.items(), key=lambda x: x[1])[:10]
                        for key, _ in oldest:
                            del self.last_posts[key]

                time.sleep(1)  # Задержка между группами

            except Exception as e:
                logger.error(f"Ошибка обработки группы {group_id}: {e}")
                time.sleep(2)

    def run(self):
        """Запуск основного цикла бота"""
        logger.info("Запуск бота в облаке...")

        # Инициализация - получаем текущие посты
        groups = self.config.get('groups', [])
        for group_config in groups:
            if not self.running:
                break

            group_id = group_config['id']
            posts = self.get_last_posts(group_id, count=1)
            if posts:
                post_key = f"{group_id}_{posts[0]['id']}"
                self.last_posts[post_key] = datetime.now()
                logger.info(f"Инициализирована группа {group_id}, последний пост: {posts[0]['id']}")
            time.sleep(1)

        interval = self.config.get('bot', {}).get('interval', 60)
        logger.info(f"Начинаем проверку с интервалом {interval} секунд")

        # Основной цикл
        while self.running:
            try:
                self.check_new_posts()

                # Ждем указанный интервал, но проверяем флаг running каждую секунду
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                if self.running:
                    time.sleep(30)


def main():
    """Точка входа"""
    try:
        bot = VK2DiscordBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()