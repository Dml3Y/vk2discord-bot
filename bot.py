import os
import sys
import time
import json
import yaml
import logging
from datetime import datetime
from typing import Dict, List
from urllib.parse import urlparse

import vk_api
import requests
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class VK2DiscordBot:
    def __init__(self, use_proxy: bool = True):
        """Инициализация бота"""
        load_dotenv()

        # Загрузка конфигурации
        with open('config.yaml', 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # Настройки ВК
        self.vk_token = os.getenv('VK_TOKEN')
        if not self.vk_token:
            raise ValueError("VK_TOKEN не найден в .env")

        # Настройки Discord
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK')
        if not self.discord_webhook:
            raise ValueError("DISCORD_WEBHOOK не найден в .env")

        # Настройки прокси (если нужно)
        self.use_proxy = use_proxy
        self.proxies = self.get_proxies() if use_proxy else {}

        # Инициализация VK API
        self.vk_session = vk_api.VkApi(token=self.vk_token)
        self.vk = self.vk_session.get_api()

        # Состояние бота
        self.last_posts = {}

        # Логирование будет в main()

    def get_proxies(self) -> Dict:
        """Получение списка прокси для обхода блокировок"""
        # Бесплатные прокси (могут быть нестабильны)
        free_proxies = [
            'http://45.61.187.67:4001',
            'http://45.61.188.24:4002',
            'http://45.61.188.15:4003',
        ]

        return {
            'http': free_proxies[0],
            'https': free_proxies[0]
        }

    def test_discord_connection(self) -> bool:
        """Тестирование подключения к Discord"""
        logger.info("Тестирование подключения к Discord...")

        test_message = {
            "content": "✅ VK2DiscordBot запущен и работает!",
            "username": "VK Bot Tester"
        }

        try:
            response = requests.post(
                self.discord_webhook,
                json=test_message,
                headers={'Content-Type': 'application/json'},
                timeout=30,
                proxies=self.proxies if self.use_proxy else None
            )

            if response.status_code in [200, 204]:
                logger.info(f"✅ Discord webhook работает! Статус: {response.status_code}")
                return True
            else:
                logger.error(f"❌ Discord вернул ошибку: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.Timeout:
            logger.error("❌ Таймаут при подключении к Discord")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Discord: {e}")
            return False

    def get_group_info(self, group_id: str) -> Dict:
        """Получение информации о группе"""
        try:
            if isinstance(group_id, str) and not group_id.isdigit():
                group_info = self.vk.groups.getById(group_id=group_id)
            else:
                group_info = self.vk.groups.getById(group_id=int(group_id))

            return group_info[0] if group_info else {}
        except Exception as e:
            logger.error(f"Ошибка получения информации о группе {group_id}: {e}")
            return {}

    def get_last_posts(self, group_id: str, count: int = 3) -> List[Dict]:
        """Получение последних постов из группы"""
        try:
            group_info = self.get_group_info(group_id)
            vk_group_id = f"-{group_info['id']}" if group_info else f"-{group_id}"

            posts = self.vk.wall.get(
                owner_id=vk_group_id,
                count=count,
                filter='owner'
            )

            return posts['items']
        except Exception as e:
            logger.error(f"Ошибка получения постов из {group_id}: {e}")
            return []

    # def format_post_combo(self, post: Dict, group_info: Dict) -> Dict:
    #     """Комбинированное форматирование"""
    #     text = post.get('text', '')
    #
    #     if len(text) > 1500:
    #         text = text[:1500] + "..."
    #
    #     # Получаем фото
    #     photo_urls = []
    #     if 'attachments' in post:
    #         for attachment in post['attachments']:
    #             if attachment.get('type') == 'photo':
    #                 photo = attachment['photo']
    #                 sizes = photo.get('sizes', [])
    #                 if sizes:
    #                     max_size = sizes[-1]
    #                     photo_urls.append(max_size['url'])
    #
    #     post_url = f"https://vk.com/wall{post['owner_id']}_{post['id']}"
    #     content = f"**📢 Новый пост из {group_info.get('name', 'Группа')}**\n\n{text}"
    #
    #     # Добавляем ссылки на фото
    #     for i, url in enumerate(photo_urls[:5]):
    #         content += f"\n\n📸 {url}"
    #
    #     content += f"\n\n🔗 {post_url}"
    #
    #     # Очищаем username
    #     username = group_info.get('name', 'VK Bot')
    #     username = ''.join(c for c in username if c.isalnum() or c in ' _-')
    #     if not username.strip():
    #         username = 'VK Bot'
    #     username = username[:32].strip()
    #
    #     return {
    #         "content": content,
    #         "username": username
    #     }
    # def format_post_best(self, post: Dict, group_info: Dict) -> Dict:
    #     """Лучший вариант форматирования"""
    #     text = post.get('text', '')
    #
    #     # Обрезаем текст если слишком длинный
    #     if len(text) > 1500:
    #         text = text[:1500] + "..."
    #
    #     # Получаем фото
    #     photo_urls = []
    #     if 'attachments' in post:
    #         for attachment in post['attachments']:
    #             if attachment.get('type') == 'photo':
    #                 photo = attachment['photo']
    #                 sizes = photo.get('sizes', [])
    #                 if sizes:
    #                     # Ищем размер с максимальным качеством (тип 'w', 'z', 'y')
    #                     size_order = ['w', 'z', 'y', 'x', 'r', 'q', 'p', 'o', 'm', 's']
    #                     max_size = sizes[-1]  # по умолчанию последний
    #                     for size_type in size_order:
    #                         for size in sizes:
    #                             if size['type'] == size_type:
    #                                 max_size = size
    #                                 break
    #                         else:
    #                             continue
    #                         break
    #                     photo_urls.append(max_size['url'])
    #
    #     post_url = f"https://vk.com/wall{post['owner_id']}_{post['id']}"
    #
    #     # Создаем основной embed
    #     embed = {
    #         "title": f"📢 Новый пост из {group_info.get('name', 'Группа')}",
    #         "description": text,
    #         "url": post_url,
    #         "color": 0x0077FF,
    #         "timestamp": datetime.fromtimestamp(post.get('date', time.time())).isoformat(),
    #         "footer": {
    #             "text": group_info.get('name', 'VK')
    #         }
    #     }
    #
    #     # Добавляем первое фото как image в embed
    #     if photo_urls:
    #         embed["image"] = {"url": photo_urls[0]}
    #
    #     message = {
    #         "embeds": [embed],
    #         "username": group_info.get('name', 'VK Bot')[:32]
    #     }
    #
    #     # Добавляем дополнительную информацию в content если много фото
    #     if len(photo_urls) > 1:
    #         message["content"] = f"📸 В посте {len(photo_urls)} фото"
    #
    #     return message
    def format_post_hidden(self, post: Dict, group_info: Dict) -> Dict:
        """Форматирование со скрытыми ссылками на фото"""
        text = post.get('text', '')

        if len(text) > 1000:
            text = text[:1000] + "..."

        # Получаем фото
        photo_urls = []
        if 'attachments' in post:
            for attachment in post['attachments']:
                if attachment.get('type') == 'photo':
                    photo = attachment['photo']
                    sizes = photo.get('sizes', [])
                    if sizes:
                        max_size = sizes[-1]
                        photo_urls.append(max_size['url'])

        post_url = f"https://vk.com/wall{post['owner_id']}_{post['id']}"
        content = f"**📢 Новый пост из {group_info.get('name', 'Группа')}**\n\n{text}"

        # Добавляем невидимые ссылки на фото (используя невидимый символ)
        # или просто не добавляем их вообще
        if photo_urls:
            # Способ 1: Невидимые ссылки
            for i, url in enumerate(photo_urls[:3]):  # Ограничиваем 3 фото
                content += f"\n\n[\u200B]({url})"  # Zero-width space как текст ссылки

            # Способ 2: Уведомление о фото без ссылок
            content += f"\n\n📸 В посте {len(photo_urls)} фото"

        content += f"\n\n🔗 [Ссылка на пост в ВК]({post_url})"

        # Очищаем username
        username = group_info.get('name', 'VK Bot')
        username = ''.join(c for c in username if c.isalnum() or c in ' _-')
        if not username.strip():
            username = 'VK Bot'
        username = username[:32].strip()

        return {
            "content": content,
            "username": username
        }

    def send_to_discord_with_retry(self, message: Dict, max_retries: int = 3) -> bool:
        """Отправка сообщения в Discord с повторными попытками"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Попытка {attempt + 1} отправки в Discord...")
                logger.info(f"Отправляем сообщение: {message.get('username', 'No username')}")

                response = requests.post(
                    self.discord_webhook,
                    json=message,
                    headers={'Content-Type': 'application/json'},
                    timeout=30,
                    proxies=self.proxies if self.use_proxy else None
                )

                logger.info(f"Ответ Discord: {response.status_code}")

                if response.status_code in [200, 204]:
                    logger.info(f"✅ Сообщение отправлено в Discord")
                    return True
                else:
                    logger.error(f"❌ Discord вернул ошибку {response.status_code}: {response.text}")
                    time.sleep(5)

            except requests.exceptions.Timeout:
                logger.error(f"⚠️ Таймаут при попытке {attempt + 1}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"⚠️ Ошибка при попытке {attempt + 1}: {str(e)}")
                time.sleep(5)

        logger.error(f"❌ Не удалось отправить сообщение после {max_retries} попыток")
        return False

    def run(self):
        """Запуск основного цикла бота"""
        logger.info("=" * 50)
        logger.info("ЗАПУСК VK2DISCORD BOT")
        logger.info("=" * 50)

        # Инициализация групп
        groups = self.config.get('groups', [])
        for group_config in groups:
            group_id = group_config['id']
            posts = self.get_last_posts(group_id, count=1)
            if posts:
                post_key = f"{group_id}_{posts[0]['id']}"
                self.last_posts[post_key] = datetime.now()
                logger.info(f"Инициализирована группа: {group_config.get('name', group_id)}")

        interval = self.config.get('bot', {}).get('interval', 60)
        logger.info(f"Начинаем проверку с интервалом {interval} секунд")

        # Основной цикл
        while True:
            try:
                for group_config in groups:
                    group_id = group_config['id']
                    group_name = group_config.get('name', group_id)

                    logger.info(f"Проверяем группу: {group_name}")

                    posts = self.get_last_posts(group_id, count=2)
                    if not posts:
                        continue

                    latest_post = posts[0]
                    post_key = f"{group_id}_{latest_post['id']}"

                    if post_key not in self.last_posts:
                        logger.info(f"Найден новый пост: {latest_post['id']}")

                        # Получаем информацию о группе
                        group_info = self.get_group_info(group_id)

                        # Форматируем пост
                        discord_message = self.format_post_hidden(latest_post, group_info)

                        # Отправляем в Discord
                        if self.send_to_discord_with_retry(discord_message):
                            self.last_posts[post_key] = datetime.now()
                            logger.info(f"✅ Пост {latest_post['id']} успешно опубликован в Discord")
                        else:
                            logger.warning(f"⚠️ Пост {latest_post['id']} не был отправлен в Discord")

                    time.sleep(2)

                # Ждем перед следующей проверкой
                logger.info(f"Ожидание {interval} секунд до следующей проверки...")
                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Бот остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(30)


def main():
    """Точка входа"""
    try:
        bot = None

        # Сначала пробуем без прокси
        logger.info("Пробуем запустить без прокси...")
        bot_without_proxy = VK2DiscordBot(use_proxy=False)

        # Тестируем Discord
        if bot_without_proxy.test_discord_connection():
            bot = bot_without_proxy
            logger.info("✅ Бот запущен без прокси")
        else:
            logger.warning("Discord недоступен. Пробуем с прокси...")
            bot_with_proxy = VK2DiscordBot(use_proxy=True)
            if bot_with_proxy.test_discord_connection():
                bot = bot_with_proxy
                logger.info("✅ Бот запущен с прокси")
            else:
                logger.error(
                    "Не удалось подключиться к Discord даже с прокси. Бот будет работать, но отправка сообщений может не работать.")
                bot = bot_with_proxy  # Все равно запускаем, но предупреждаем

        if bot:
            bot.run()
        else:
            logger.error("Не удалось инициализировать бота.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()