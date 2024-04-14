# File path: test.py
# Импортируем модуль работы с базой данных
from db import add_or_update_user

# Добавляем 20 пользователей
users = [
    (1, "user1", "group1"),
    (2, "user2", "group2"),
    (3, "user3", "group3"),
    (4, "user4", "group1"),
    (5, "user5", "group2"),
    (6, "user6", "group3"),
    (7, "user7", "group1"),
    (8, "user8", "group2"),
    (9, "user9", "group3"),
    (10, "user10", "group1"),
    (11, "user11", "group2"),
    (12, "user12", "group3"),
    (13, "user13", "group1"),
    (14, "user14", "group2"),
    (15, "user15", "group3"),
    (16, "user16", "group1"),
    (17, "user17", "group2"),
    (18, "user18", "group3"),
    (19, "user19", "group1"),
    (20, "user20", "group2")
]

# Добавляем пользователей в базу данных
for user in users:
    add_or_update_user(*user)
