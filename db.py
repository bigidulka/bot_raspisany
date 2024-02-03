import sqlite3

conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_login TEXT,
    recent_groups TEXT  -- Строка с последними группами, разделенными запятыми
)
''')
conn.commit()

def add_or_update_user(user_id, telegram_login, selected_group):
    """Добавление или обновление пользователя в базе данных с тремя последними группами."""
    user_info = get_user(user_id)
    if user_info:
        recent_groups = user_info[2] or ""
        groups_list = recent_groups.split(",") if recent_groups else []
        # Добавляем selected_group в список, только если он не None и не уже присутствует в списке
        if selected_group and selected_group not in groups_list:
            groups_list.append(selected_group)
            groups_list = groups_list[-3:]  # Оставляем только последние три группы
        recent_groups = ",".join(groups_list)
    else:
        recent_groups = selected_group if selected_group else ""

    cursor.execute('''
    INSERT INTO users (id, telegram_login, recent_groups) VALUES (?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET telegram_login = excluded.telegram_login, recent_groups = excluded.recent_groups
    ''', (user_id, telegram_login, recent_groups))
    conn.commit()


def get_user(user_id):
    """Получение информации о пользователе по ID."""
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    return cursor.fetchone()

def get_all_users():
    """Получить всех пользователей и их группы из базы данных."""
    cursor.execute('SELECT telegram_login, recent_groups FROM users')
    return cursor.fetchall()