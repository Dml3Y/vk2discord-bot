import vk_api
import os
from dotenv import load_dotenv

load_dotenv()


def debug_group_posts():
    token = os.getenv('VK_TOKEN')
    group_id = "223393123"

    vk = vk_api.VkApi(token=token).get_api()

    print("=" * 60)
    print(f"ДЕБАГ ПОСТОВ ГРУППЫ {group_id}")
    print("=" * 60)

    # Тестируем разные фильтры
    filters = ['all', 'owner', 'others']

    for filter_type in filters:
        print(f"\n🔍 Фильтр: '{filter_type}'")
        try:
            posts = vk.wall.get(
                owner_id=f"-{group_id}",
                count=5,
                filter=filter_type
            )

            print(f"   Найдено постов: {len(posts['items'])}")

            for post in posts['items']:
                author = "ГРУППА" if post['from_id'] < 0 else "ПОЛЬЗОВАТЕЛЬ"
                text_preview = post.get('text', 'Без текста')[:50]
                print(f"   - ID: {post['id']} | От: {author} | Текст: {text_preview}...")

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")

    print("\n" + "=" * 60)
    print("РЕКОМЕНДАЦИИ:")
    print("1. Используйте filter='all' для всех постов")
    print("2. Если постов от группы нет, проверьте настройки публикации")
    print("3. Убедитесь, что вы администратор группы")
    print("=" * 60)


if __name__ == "__main__":
    debug_group_posts()