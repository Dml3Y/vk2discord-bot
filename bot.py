import os
import sys
import time
import json
import yaml
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

import vk_api
import requests
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('vk2discord.log')
    ]
)
logger = logging.getLogger(__name__)


class VK2DiscordBot:
    def __init__(self, config_path: str = "config.yaml"):
        """Инициализация бота"""
        load_dotenv()

        # Загрузка конфигурации
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # Настройки ВК
        self.vk_token = os.getenv('VK_TOKEN') or self.config.get('vk', {}).get('token')
        if not self.vk_token:
            raise ValueError("VK_TOKEN не найден в .env или config.yaml")

        # Настройки Discord
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK') or self.config.get('discord', {}).get('webhook')
        if not self.discord_webhook:
            raise ValueError("DISCORD_WEBHOOK не найден в .env или config.yaml")

        # Инициализация VK API
        self.vk_session = vk_api.VkApi(token=self.vk_token)
        self.vk = self.vk_session.get_api()

        # Состояние бота
        self.last_posts = {}
        self.initialized = False

        logger.info("Бот инициализирован")

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
        # Базовое сообщение
        content = f"**📢 Новый пост из [{group_info.get('name', 'Группа')}](https://vk.com/{group_info.get('screen_name', '')})**\n\n"

        if post.get('text'):
            # Обрезаем текст если слишком длинный
            text = post['text']
            if len(text) > 1800:
                text = text[:1800] + "..."
            content += text + "\n\n"

        # Добавляем ссылку на пост
        post_id = post['id']
        owner_id = post['owner_id']
        content += f"[🔗 Ссылка на пост](https://vk.com/wall{owner_id}_{post_id})"

        # Формируем embed
        embed = {
            "content": content,
            "username": group_info.get('name', 'VK Bot'),
            "avatar_url": group_info.get('photo_200'),
            "embeds": []
        }

        # Обработка вложений
        attachments = post.get('attachments', [])
        images = []

        for attach in attachments:
            attach_type = attach['type']

            if attach_type == 'photo':
                # Получаем картинку максимального качества
                photo = attach['photo']
                sizes = photo.get('sizes', [])
                if sizes:
                    # Ищем размеры с качеством z, y, x, w
                    for quality in ['z', 'y', 'x', 'w', 'r', 'q', 'p', 'o']:
                        for size in sizes:
                            if size['type'] == quality:
                                images.append(size['url'])
                                break
                        if images:
                            break

            elif attach_type == 'video':
                video = attach['video']
                embed["embeds"].append({
                    "title": f"🎬 {video.get('title', 'Видео')}",
                    "description": video.get('description', ''),
                    "url": f"https://vk.com/video{video['owner_id']}_{video['id']}"
                })

            elif attach_type == 'link':
                link = attach['link']
                embed["embeds"].append({
                    "title": f"🔗 {link.get('title', 'Ссылка')}",
                    "description": link.get('description', ''),
                    "url": link['url']
                })

        # Добавляем первую картинку как embed
        if images:
            embed["embeds"].insert(0, {
                "image": {"url": images[0]}
            })

        return embed

    def send_to_discord(self, embed: Dict) -> bool:
        """Отправка сообщения в Discord через webhook"""
        try:
            response = requests.post(
                self.discord_webhook,
                json=embed,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code in [200, 204]:
                logger.info("Сообщение успешно отправлено в Discord")
                return True
            else:
                logger.error(f"Ошибка Discord: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Ошибка отправки в Discord: {e}")
            return False

    def check_new_posts(self):
        """Проверка новых постов"""
        groups = self.config.get('groups', [])

        for group_config in groups:
            group_id = group_config['id']
            discord_channel = group_config.get('discord_channel')

            logger.info(f"Проверяем группу: {group_id}")

            # Получаем информацию о группе
            group_info = self.get_group_info(group_id)
            if not group_info:
                continue

            # Получаем последние посты
            posts = self.get_last_posts(group_id, count=3)
            if not posts:
                continue

            # Проверяем последний пост
            latest_post = posts[0]
            post_key = f"{group_id}_{latest_post['id']}"

            if post_key not in self.last_posts:
                logger.info(f"Найден новый пост: {latest_post['id']}")

                # Форматируем и отправляем
                embed = self.format_post(latest_post, group_info)

                # Если указан отдельный webhook для группы
                if discord_channel:
                    embed['webhook_url'] = discord_channel
                    self.send_to_discord(embed)
                else:
                    self.send_to_discord(embed)

                # Сохраняем ID поста
                self.last_posts[post_key] = datetime.now()

                # Ограничиваем размер словаря
                if len(self.last_posts) > 100:
                    # Удаляем самые старые записи
                    oldest = sorted(self.last_posts.items(), key=lambda x: x[1])[:20]
                    for key, _ in oldest:
                        del self.last_posts[key]

            time.sleep(1)  # Задержка между группами

    def run(self):
        """Запуск основного цикла бота"""
        logger.info("Запуск бота...")

        # Первоначальная инициализация - получаем текущие посты
        groups = self.config.get('groups', [])
        for group_config in groups:
            group_id = group_config['id']
            posts = self.get_last_posts(group_id, count=1)
            if posts:
                post_key = f"{group_id}_{posts[0]['id']}"
                self.last_posts[post_key] = datetime.now()
                logger.info(f"Инициализирована группа {group_id}, последний пост: {posts[0]['id']}")

        self.initialized = True

        # Основной цикл
        import schedule
        import time as t

        interval = self.config.get('interval', 60)  # секунды

        logger.info(f"Начинаем проверку с интервалом {interval} секунд")

        # Немедленная проверка
        self.check_new_posts()

        # Планировщик
        schedule.every(interval).seconds.do(self.check_new_posts)

        while True:
            try:
                schedule.run_pending()
                t.sleep(1)
            except KeyboardInterrupt:
                logger.info("Бот остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                t.sleep(30)


def main():
    """Точка входа"""
    try:
        bot = VK2DiscordBot()
        bot.run()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()