import asyncio
import bcrypt
from users import UserDatabase

DATABASE_URL = "postgresql://postgres:111@localhost:5432/authorization"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def print_user(user):
    if not user:
        print("Пользователь не найден")
        return
    print(f"ID: {user['id']}")
    print(f"Username: {user['username']}")
    print(f"Email: {user['email']}")
    print(f"Role: {user['role']}")
    print(f"Active: {user['is_active']}")
    print(f"Created: {user['created_at']}")

async def main():
    db = UserDatabase(DATABASE_URL)
    await db.connect()
    print("Подключено к базе данных")

    while True:
        print("\n" + "="*50)
        print("МЕНЮ ТЕСТИРОВАНИЯ ПОЛЬЗОВАТЕЛЕЙ")
        print("="*50)
        print("1. Создать пользователя")
        print("2. Найти по ID")
        print("3. Найти по email")
        print("4. Найти по username")
        print("5. Обновить пользователя")
        print("6. Деактивировать пользователя")
        print("7. Проверить существование")
        print("0. Выйти")
        
        choice = input("\nВыберите действие: ").strip()
        
        if choice == "1":
            username = input("Username: ")
            email = input("Email: ")
            password = input("Пароль (будет хэширован): ")
            role = input("Роль (user/admin/moderator, по умолчанию user): ").strip() or "user"
            try:
                pwd_hash = hash_password(password)
                user_id = await db.create_user(username, email, pwd_hash, role)
                print(f"Пользователь создан! ID: {user_id}")
            except Exception as e:
                print(f"Ошибка: {e}")

        elif choice == "2":
            try:
                uid = int(input("ID: "))
                user = await db.get_user_by_id(uid)
                print_user(user)
            except ValueError:
                print("Неверный ID")
            except Exception as e:
                print(f"Ошибка: {e}")

        elif choice == "3":
            email = input("Email: ")
            user = await db.get_user_by_email(email)
            print_user(user)

        elif choice == "4":
            username = input("Username: ")
            user = await db.get_user_by_username(username)
            print_user(user)

        elif choice == "5":
            try:
                uid = int(input("ID пользователя для обновления: "))
                field = input("Поле для обновления (email, username, role): ").strip()
                if field not in ("email", "username", "role"):
                    print("Доступные поля: email, username, role")
                    continue
                value = input(f"Новое значение для {field}: ")
                success = await db.update_user(uid, **{field: value})
                print("Успешно обновлено" if success else "Не найдено или ошибка")
            except Exception as e:
                print(f"Ошибка: {e}")

        elif choice == "6":
            try:
                uid = int(input("ID пользователя для деактивации: "))
                success = await db.deactivate_user(uid)
                print("Пользователь деактивирован" if success else "Не найден")
            except Exception as e:
                print(f"Ошибка: {e}")

        elif choice == "7":
            email = input("Email (оставьте пустым, если не нужен): ").strip() or None
            username = input("Username (оставьте пустым, если не нужен): ").strip() or None
            exists = await db.user_exists(email=email, username=username)
            print("Существует" if exists else "Не существует")

        elif choice == "0":
            break
        else:
            print("Неверный выбор")

    await db.close()
    print("Соединение закрыто")

if __name__ == "__main__":
    asyncio.run(main())