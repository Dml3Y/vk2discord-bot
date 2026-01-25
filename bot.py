import os
import sys
import time
import json
import yaml
import logging
from datetime import datetime
from typing import Dict, List, Optional
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

        # Настройки Discord - ДВА вебхука
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK')  # Для обычных постов
        self.discord_thread_webhook_base = os.getenv('DISCORD_THREAD_WEBHOOK')  # Для постов с 🗓 (без параметров)
        self.thread_id = os.getenv('DISCORD_THREAD_ID')  # ID треда для форум-канала

        if not self.discord_webhook:
            raise ValueError("DISCORD_WEBHOOK не найден в .env")
        if not self.discord_thread_webhook_base:
            raise ValueError("DISCORD_THREAD_WEBHOOK не найден в .env")

        # Формируем URL вебхука для треда с thread_id
        if self.thread_id:
            self.discord_thread_webhook = f"{self.discord_thread_webhook_base}?thread_id={self.thread_id}"
            logger.info(f"Webhook для треда сформирован с thread_id: {self.thread_id}")
        else:
            self.discord_thread_webhook = self.discord_thread_webhook_base
            logger.warning("DISCORD_THREAD_ID не указан. Календарные посты могут не отправляться.")

        # Настройки прокси (если нужно)
        self.use_proxy = use_proxy
        self.proxies = self.get_proxies() if use_proxy else {}

        # Инициализация VK API
        self.vk_session = vk_api.VkApi(token=self.vk_token)
        self.vk = self.vk_session.get_api()

        # Состояние бота
        self.last_posts = {}

    def get_proxies(self) -> Dict:
        """Получение списка прокси для обхода блокировок"""
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
        """Тестирование подключения к Discord для обоих вебхуков"""
        logger.info("Тестирование подключения к Discord...")

        success = True

        # Тестируем основной вебхук
        logger.info("Тестируем основной вебхук для обычных постов...")
        test_message_normal = {
            "content": "✅ Основной вебхук работает! Обычные посты будут здесь.",
            "username": "VK Bot Tester"
        }

        try:
            response = requests.post(
                self.discord_webhook,
                json=test_message_normal,
                headers={'Content-Type': 'application/json'},
                timeout=30,
                proxies=self.proxies if self.use_proxy else None
            )

            if response.status_code in [200, 204]:
                logger.info(f"✅ Основной вебхук работает! Статус: {response.status_code}")
            else:
                logger.error(f"❌ Основной вебхук вернул ошибку: {response.status_code} - {response.text}")
                success = False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к основному вебхуку: {e}")
            success = False

        # Тестируем вебхук для треда
        logger.info("Тестируем вебхук для постов с 🗓...")
        test_message_thread = {
            "content": "✅ Вебхук для постов с 🗓 работает! Календарные посты будут здесь.",
            "username": "VK Calendar Bot"
        }

        try:
            response = requests.post(
                self.discord_thread_webhook,  # Используем уже сформированный URL с thread_id
                json=test_message_thread,
                headers={'Content-Type': 'application/json'},
                timeout=30,
                proxies=self.proxies if self.use_proxy else None
            )

            if response.status_code in [200, 204]:
                logger.info(f"✅ Вебхук для треда работает! Статус: {response.status_code}")
                if self.thread_id:
                    logger.info(f"📌 Thread ID: {self.thread_id}")
            else:
                logger.error(f"❌ Вебхук для треда вернул ошибку: {response.status_code} - {response.text}")
                success = False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к вебхуку для треда: {e}")
            success = False

        return success

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

    def get_last_posts(self, group_id: str, count: int = 10) -> List[Dict]:
        """Получение последних постов из группы с отладкой"""
        try:
            logger.info(f"🔄 Получение постов для группы {group_id}")

            group_info = self.get_group_info(group_id)
            vk_group_id = f"-{group_info['id']}" if group_info else f"-{group_id}"

            logger.info(f"📊 VK ID группы: {vk_group_id}")
            logger.info(f"🎯 Используем filter='all' (все посты)")

            # Получаем посты
            posts = self.vk.wall.get(
                owner_id=vk_group_id,
                count=count,
                filter='all',  # ВСЕ посты
                extended=0
            )

            logger.info(f"✅ Получено {len(posts['items'])} постов")

            # Логируем информацию о каждом посте
            for i, post in enumerate(posts['items'], 1):
                from_id = post['from_id']
                post_type = "🏢 От группы" if from_id < 0 else f"👤 От пользователя (ID: {from_id})"
                logger.info(f"   {i}. Пост {post['id']}: {post_type}")
                if post.get('text'):
                    logger.info(f"      Текст: {post['text'][:100]}...")

            return posts['items']

        except Exception as e:
            logger.error(f"❌ Ошибка получения постов из {group_id}: {e}")
            return []

    def contains_video_emoji(self, post: Dict) -> bool:
        """Проверяет, содержит ли пост видео-эмодзи"""
        video_emojis = ['🎥', '📽️']
        text = post.get('text', '')

        for emoji in video_emojis:
            if emoji in text:
                return True
        return False

    def contains_calendar_emoji(self, post: Dict) -> bool:
        """Проверяет, содержит ли пост календарный эмодзи"""
        calendar_emojis = ['🗓️', '📅', '🗓']
        text = post.get('text', '')

        for emoji in calendar_emojis:
            if emoji in text:
                return True
        return False

    def format_post_multiple_embeds(self, post: Dict, group_info: Dict, is_calendar_post: bool = False) -> Dict:
        """Форматирование с несколькими embeds"""
        text = post.get('text', '')

        if len(text) > 2000:
            text = text[:1997] + "..."

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

        # Основной embed с текстом
        embed_title = "📅 Race Day Post" if is_calendar_post else "📝 New Post"

        embeds = [{
            "title": f"{embed_title} from {group_info.get('name', 'Group')}",
            "description": text,
            "url": post_url,
            "color": 0x0099ff if is_calendar_post else 0xc4400f,
            "timestamp": datetime.fromtimestamp(post.get('date', time.time())).isoformat(),
            "footer": {
                "text": group_info.get('name', 'VK')
            }
        }]

        # Добавляем embeds для фото
        for i, photo_url in enumerate(photo_urls[:9]):
            embeds.append({
                "image": {"url": photo_url},
                "color": 0x0099ff if is_calendar_post else 0xc4400f
            })

        # Если фото больше 9, показываем количество
        if len(photo_urls) > 9:
            embeds.append({
                "description": f"📸 ...и еще {len(photo_urls) - 9} фото",
                "color": 0x0099ff if is_calendar_post else 0xc4400f
            })

        message = {
            "embeds": embeds,
            "username": group_info.get('name', 'VK Bot')[:32]
        }

        return message

    def send_to_discord_with_retry(self, message: Dict, is_calendar_post: bool = False, max_retries: int = 3) -> bool:
        """Отправка сообщения в Discord с повторными попытками"""
        # Выбираем правильный вебхук
        webhook_url = self.discord_thread_webhook if is_calendar_post else self.discord_webhook
        post_type = "календарный" if is_calendar_post else "обычный"

        logger.info(f"Отправляем {post_type} пост. Вебхук: {webhook_url[:80]}...")

        for attempt in range(max_retries):
            try:
                logger.info(f"Попытка {attempt + 1} отправки {post_type} поста в Discord...")
                logger.info(f"Отправляем сообщение: {message.get('username', 'No username')}")

                response = requests.post(
                    webhook_url,
                    json=message,
                    headers={'Content-Type': 'application/json'},
                    timeout=30,
                    proxies=self.proxies if self.use_proxy else None
                )

                logger.info(f"Ответ Discord: {response.status_code}")

                if response.status_code in [200, 204]:
                    logger.info(f"✅ {post_type.capitalize()} пост отправлен в Discord")
                    return True
                else:
                    logger.error(f"❌ Discord вернул ошибку {response.status_code}: {response.text}")
                    time.sleep(5)

            except requests.exceptions.Timeout:
                logger.error(f"⚠️ Таймаут при попытке {attempt + 1} отправки {post_type} поста")
                time.sleep(5)
            except Exception as e:
                logger.error(f"⚠️ Ошибка при попытке {attempt + 1} отправки {post_type} поста: {str(e)}")
                time.sleep(5)

        logger.error(f"❌ Не удалось отправить {post_type} пост после {max_retries} попыток")
        return False

    def run(self):
        """Запуск основного цикла бота"""
        logger.info("=" * 50)
        logger.info("ЗАПУСК VK2DISCORD BOT (с разделением постов)")
        logger.info("=" * 50)
        logger.info(f"Обычные посты: {self.discord_webhook[:50]}...")
        logger.info(f"Календарные посты: {self.discord_thread_webhook[:80]}...")

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

                        # Проверяем, является ли пост закрепленным
                        if latest_post.get('is_pinned') == 1:
                            logger.info(f"📌 Пропускаем закрепленный пост (ID: {latest_post['id']})")
                            self.last_posts[post_key] = datetime.now()
                            continue

                        # Проверяем, содержит ли пост эмодзи 🎥
                        if self.contains_video_emoji(latest_post):
                            logger.info(f"⏭️ Пропускаем видео-пост с эмодзи 🎥 (ID: {latest_post['id']})")
                            self.last_posts[post_key] = datetime.now()
                            continue

                        # Проверяем, содержит ли пост эмодзи 🗓
                        is_calendar_post = self.contains_calendar_emoji(latest_post)

                        if is_calendar_post:
                            logger.info(f"📅 Обнаружен календарный пост с эмодзи 🗓 (ID: {latest_post['id']})")
                        else:
                            logger.info(f"📝 Обнаружен обычный пост (ID: {latest_post['id']})")

                        # Получаем информацию о группе
                        group_info = self.get_group_info(group_id)

                        # Форматируем пост
                        discord_message = self.format_post_multiple_embeds(latest_post, group_info, is_calendar_post)

                        # Отправляем в Discord
                        if self.send_to_discord_with_retry(discord_message, is_calendar_post):
                            self.last_posts[post_key] = datetime.now()
                            post_type = "календарный" if is_calendar_post else "обычный"
                            logger.info(
                                f"✅ {post_type.capitalize()} пост {latest_post['id']} успешно опубликован в Discord")
                        else:
                            post_type = "календарный" if is_calendar_post else "обычный"
                            logger.warning(
                                f"⚠️ {post_type.capitalize()} пост {latest_post['id']} не был отправлен в Discord")

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

        # Тестируем Discord подключения
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