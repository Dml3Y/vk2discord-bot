import vk_api


def test_group_access(token, group_id):
    """Тестирование доступа к группе"""

    vk = vk_api.VkApi(token=token).get_api()

    print("=" * 50)
    print(f"Тестирование доступа к группе ID: {group_id}")
    print("=" * 50)

    try:
        # 1. Проверяем информацию о группе
        print("\n1. Информация о группе:")
        group_info = vk.groups.getById(group_id=group_id, fields='is_closed,type,name')
        if group_info:
            group = group_info[0]
            print(f"   Название: {group.get('name')}")
            print(f"   Тип: {group.get('type')}")
            print(f"   Закрытая: {'Да' if group.get('is_closed') else 'Нет'}")

        # 2. Пробуем получить посты
        print("\n2. Пробуем получить посты:")
        try:
            posts = vk.wall.get(owner_id=f"-{group_id}", count=2, filter='owner')
            print(f"   ✅ Успешно! Найдено постов: {len(posts['items'])}")

            for post in posts['items']:
                print(f"   - Пост {post['id']}: {post.get('text', '')[:50]}...")

        except vk_api.exceptions.ApiError as e:
            print(f"   ❌ Ошибка: {e}")

        # 3. Проверяем права администратора
        print("\n3. Проверка прав администратора:")
        try:
            # Этот метод доступен только для администраторов
            members = vk.groups.getMembers(group_id=group_id, count=1)
            print(f"   ✅ Вы администратор/модератор группы")
        except:
            print("   ⚠️  Вы не администратор или нет прав")

        # 4. Проверяем подписку
        print("\n4. Проверка подписки на группу:")
        try:
            # Проверяем, подписан ли пользователь
            is_member = vk.groups.isMember(group_id=group_id, user_id=YOUR_VK_ID)
            print(f"   {'✅ Вы подписаны на группу' if is_member else '❌ Вы не подписаны'}")
        except:
            print("   ⚠️  Не удалось проверить подписку")

    except Exception as e:
        print(f"\n❌ Общая ошибка: {e}")


# Замените на ваши данные
YOUR_TOKEN = "vk1.a.M0wEsGoVi_aFoSMM8tDo_d1udD6tom0Kh-AvjDrJYKVjKIkaT2OHd67xTXysB9N5hAVnR_znW4SXeMX5R4ZC3Q5OI9HVdeJEainzJUXy_bLvegeGzXrkv6aiKPJdQ95bHPnfcqNvwQ7Vk6Kd-EHKvsc47_tANF0m2Q6xcCKzT64EDYFqXd-AxboDQB_iiGSviO9yWz51smiDscokeiIb5g"
GROUP_ID = "223393123"  # ID группы (только цифры)
YOUR_VK_ID = "194449436"  # Можно получить через vk.users.get()[0]['id']

test_group_access(YOUR_TOKEN, GROUP_ID)