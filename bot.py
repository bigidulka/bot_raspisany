# File path: bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import os
from utils import *
from db import *

schedule_data = {} 
teacher_days = {}
USERS_PER_PAGE = 10
SCHEDULE_FILE = 'schedule_file.xlsx'

def list_users(update: Update, context: CallbackContext):
    query = update.callback_query
    # Check if user_list_page is initialized, if not, initialize it to 0
    if 'user_list_page' not in context.user_data:
        context.user_data['user_list_page'] = 0
    
    page = context.user_data['user_list_page']  # Current page, default to 0
    users = get_all_users()
    
    # Calculate total number of pages
    total_pages = len(users) // USERS_PER_PAGE + (1 if len(users) % USERS_PER_PAGE > 0 else 0)
    
    # Get users for the current page
    page_users = users[page * USERS_PER_PAGE:(page + 1) * USERS_PER_PAGE]

    # Form the message text
    message_text = f"Список пользователей ({page + 1}/{total_pages}):\n\n"
    for user in page_users:
        telegram_login, recent_groups = user
        message_text += f"@{telegram_login}: {recent_groups}\n"

    # Create buttons for pagination
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data='list_users_prev_page'))
    if page + 1 < total_pages:
        buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data='list_users_next_page'))

    # Add buttons to the markup
    keyboard = [buttons] if buttons else []
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        query.edit_message_text(text=message_text, reply_markup=reply_markup)
    else:
        update.message.reply_text(message_text, reply_markup=reply_markup)

def update_schedule(update: Update, context: CallbackContext):
    global schedule_data
    document = update.message.document
    if document:
        file = context.bot.get_file(document.file_id)
        # Загружаем файл под постоянным именем 'schedule_file.xlsx'
        file.download(custom_path='schedule_file.xlsx')  # Сохраняем файл под нужным именем
        
        # Загружаем расписание из обновленного файла
        schedule_data = load_schedule('schedule_file.xlsx')
        update.message.reply_text("Расписание успешно обновлено.")
    else:
        update.message.reply_text("Ошибка загрузки файла.")
        
def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    telegram_login = update.message.from_user.username

    user_info = get_user(user_id)
    if user_info:
        add_or_update_user(user_id, telegram_login, user_info[2])
    else:
        add_or_update_user(user_id, telegram_login, None)

    if not schedule_data:
        update.message.reply_text("Расписание отсутствует. Пожалуйста, загрузите файл с расписанием с помощью команды /update_schedule.")
    else:
        context.user_data['page'] = 0
        send_group_keyboard(update, context)
        

        
def handle_day_schedule(query, group_name, day_offset):
    schedule_text = f"Расписание на день для группы {group_name.replace("Группа", "").strip()}:\n\n"
    schedule_text += get_schedule_for_day(schedule_data, group_name, day_offset)
    keyboard = [
        [InlineKeyboardButton("Назад 🔙", callback_data='back_to_day_selection')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=schedule_text, reply_markup=reply_markup, parse_mode='HTML')

def handle_week_schedule(query, group_name):
    schedule_text = f"Расписание на неделю для группы {group_name.replace("Группа", "").strip()}:\n\n"
    schedule_text += get_schedule_for_week(schedule_data, group_name)
    keyboard = [[InlineKeyboardButton("Назад 🔙", callback_data='back_to_schedule_options')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=schedule_text, reply_markup=reply_markup, parse_mode='HTML')

def select_day_of_week(update: Update, context: CallbackContext):
    group_name = context.user_data.get('selected_group')
    text = f"Выберите день для группы {group_name.replace("Группа", "").strip()}:\n"
    group_schedule = schedule_data.get(group_name, {})
    dates = list(group_schedule.keys())

    keyboard = [[InlineKeyboardButton(date, callback_data=f'day_{i}')] for i, date in enumerate(dates)]
    keyboard.append([InlineKeyboardButton("Назад 🔙", callback_data='back_to_schedule_options')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    query.edit_message_text(text=text, reply_markup=reply_markup)

def send_schedule_options(update: Update, context: CallbackContext):
    group_name = context.user_data.get('selected_group')
    group_schedule = schedule_data.get(group_name, {})
    dates = list(group_schedule.keys())
    start_date = dates[0] if dates else "Н/Д"
    end_date = dates[-1] if dates else "Н/Д"
    text = f"Расписание для группы {group_name.replace("Группа", "").strip()}. Выберите опцию расписания:"

    week_button_text = f"На неделю ({start_date.split(', ')[1]} - {end_date.split(', ')[1]})"

    keyboard = [
        [InlineKeyboardButton(week_button_text, callback_data='week')],
        [InlineKeyboardButton("Выбрать день", callback_data='select_day')],
        [InlineKeyboardButton("Назад 🔙", callback_data='back_to_group_selection')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    query.edit_message_text(text=text, reply_markup=reply_markup)

def search_group_result(update: Update, context: CallbackContext):
    user_input = update.message.text
    filtered_groups = filter_groups(user_input, schedule_data.keys())

    if filtered_groups:
        keyboard = [[InlineKeyboardButton(group, callback_data='group_' + group)] for group in filtered_groups]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Выберите группу из найденных:", reply_markup=reply_markup)
    else:
        update.message.reply_text("Группы не найдены.")

def send_group_keyboard(update: Update, context: CallbackContext):
    query = update.callback_query
    page = context.user_data.get('page', 0)
    user_id = update.effective_user.id

    user_info = get_user(user_id)
    recent_groups = user_info[2].split(",") if user_info and user_info[2] else []

    group_keys = list(schedule_data.keys())

    marked_groups = {group: f"★ {group}" for group in recent_groups}
    sorted_groups = sorted(group_keys, key=lambda x: (x not in marked_groups, x))

    max_page = (len(sorted_groups) - 1) // GROUPS_PER_PAGE
    start_index = page * GROUPS_PER_PAGE
    end_index = min(start_index + GROUPS_PER_PAGE, len(sorted_groups))
    keyboard_groups = sorted_groups[start_index:end_index]

    # Form the message text with current page number and total pages
    message_text = f"Выберите группу или начните поиск ({page + 1}/{max_page + 1}):\n"

    keyboard = [[InlineKeyboardButton(marked_groups.get(group, group), callback_data='group_' + group)] for group in keyboard_groups]
    keyboard.append([InlineKeyboardButton("Поиск 🔍", callback_data='start_search')])
    
    keyboard.append([InlineKeyboardButton("Поиск преподавателя 🔍", callback_data='search_teacher_prompt')])

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data='prev_page'))
    if page < max_page:
        navigation_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data='next_page'))
    if navigation_buttons:
        keyboard.append(navigation_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        query.edit_message_text(text=message_text, reply_markup=reply_markup)
    else:
        update.message.reply_text(message_text, reply_markup=reply_markup)

def button(update: Update, context: CallbackContext) -> None:
    
    
    query = update.callback_query
    query.answer()

    data = query.data
    
    
    if data == 'search_teacher_prompt':
        query.edit_message_text("Введите команду в формате: /search_teacher <Фамилия преподавателя>")
    elif data.startswith("show_day_"):
        day_name = data.split("show_day_")[1]
        schedule_for_day = show_teacher_schedule_for_day(teacher_days, day_name)
        query.edit_message_text(text=schedule_for_day, parse_mode='HTML')
    elif data.startswith('group_'):
        selected_group = data.split('_', 1)[1].replace(' ★', '')  # Убираем звездочку, если она есть
        context.user_data['selected_group'] = selected_group
        
        user_id = query.from_user.id
        telegram_login = query.from_user.username
        add_or_update_user(user_id, telegram_login, selected_group)
        send_schedule_options(update, context)
        
    elif data == 'week':
        selected_group = context.user_data.get('selected_group')
        if selected_group:
            handle_week_schedule(query, selected_group)
        else:
            query.edit_message_text(text="Не выбрана группа.")
            
    elif data.startswith('day_'):
        selected_group = context.user_data.get('selected_group')
        day_offset = int(data.split('_')[1])
        handle_day_schedule(query, selected_group, day_offset)
        
    elif data in ['prev_page', 'next_page']:
        page = context.user_data.get('page', 0)
        if data == 'prev_page':
            context.user_data['page'] = max(0, page - 1)
        else:
            context.user_data['page'] = page + 1
        send_group_keyboard(update, context)
        
    elif data in ['back_to_group_selection', 'back_to_schedule_options', 'select_day', 'back_to_day_selection']:
        if data == 'back_to_group_selection':
            send_group_keyboard(update, context)
        elif data == 'back_to_schedule_options':
            send_schedule_options(update, context)
        elif data == 'select_day':
            select_day_of_week(update, context)
        elif data == 'back_to_day_selection':
            select_day_of_week(update, context)
    elif data == 'list_users_next_page':
        context.user_data['user_list_page'] += 1
        list_users(update, context)
    elif data == 'list_users_prev_page':
        context.user_data['user_list_page'] = max(0, context.user_data.get('user_list_page', 1) - 1)
        list_users(update, context)
    elif data == 'start_search':
        query.edit_message_text(text="Введите название для поиска:")
                
    else:
        query.edit_message_text(text="Неизвестная команда.")   
        
message_command_allowed = True

def toggle_message_command(update: Update, context: CallbackContext):
    global message_command_allowed  # Используем глобальную переменную
    
    chat_id = update.message.chat_id
    # Переключаем состояние команды
    message_command_allowed = not message_command_allowed
    
    if message_command_allowed:
        update.message.reply_text("Теперь команда /message включена.")
    else:
        update.message.reply_text("Теперь команда /message отключена.")

def message_all_users(update: Update, context: CallbackContext):
    global message_command_allowed  # Используем глобальную переменную
    
    # Проверяем, разрешено ли использование команды /message
    if not message_command_allowed:
        update.message.reply_text("Команда /message отключена.")
        return
    
    # Получаем текст сообщения из аргумента команды
    text = ' '.join(context.args)
    # Получаем список всех пользователей из базы данных
    all_users = get_all_user_ids()
    # Отправляем сообщение каждому пользователю
    for user_id in all_users:
        try:
            context.bot.send_message(user_id, text)
        except Exception as e:
            update.message.reply_text(f"Ошибка при отправке сообщения пользователю {user_id}: {e}, @{get_user(user_id)}")
    # Ответим на команду в чате
    update.message.reply_text("Сообщение разослано всем участникам бота.")
    
def day_sort_key(day):
    # Словарь для определения порядка дней недели
    week_days_order = {
        'Понедельник': 1,
        'Вторник': 2,
        'Среда': 3,
        'Четверг': 4,
        'Пятница': 5,
        'Суббота': 6,
        'Воскресенье': 7
    }
    day_name, date = day.split(', ')
    # Возвращаем кортеж с порядковым номером дня недели и датой
    return (week_days_order[day_name], date)    

def search_teacher(update: Update, context: CallbackContext):
    global teacher_days
    text = ' '.join(context.args)
    
    if not text:
        update.message.reply_text("Для этого преподавателя занятий не найдено.")
        return
    
    teacher_days = find_teacher_days(schedule_data, text)

    # Создание кнопок с датами, отсортированных по порядку дней недели
    keyboard = []
    sorted_days = sorted(teacher_days.keys(), key=day_sort_key)
    for day_name in sorted_days:
        # Создаем кнопку для каждого дня
        button = InlineKeyboardButton(day_name, callback_data=f"show_day_{day_name}")
        keyboard.append([button])
    
    # Если нет занятий, отправляем сообщение об этом
    if not keyboard:
        update.message.reply_text("Для этого преподавателя занятий не найдено.")
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите день:", reply_markup=reply_markup)

    
    
def main():
    global schedule_data
    schedule_data = load_schedule(SCHEDULE_FILE)
    updater = Updater("6668495629:AAGlmeOCtw9dQxSXr31UugK9bLGfsimw-Xg", use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.document, update_schedule))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, search_group_result))
    dispatcher.add_handler(CommandHandler('list_users', list_users))
    dispatcher.add_handler(CommandHandler("message", message_all_users, pass_args=True))
    dispatcher.add_handler(CommandHandler("toggle_message", toggle_message_command))

    dispatcher.add_handler(CommandHandler("search_teacher", search_teacher, pass_args=True))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()