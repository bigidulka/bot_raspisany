from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import os
from utils import load_schedule, filter_groups, get_schedule_for_day, get_schedule_for_week, GROUPS_PER_PAGE
from db import *

schedule_data = {} 
USERS_PER_PAGE = 10
SCHEDULE_FILE = 'schedule_file.xlsx'

def list_users(update: Update, context: CallbackContext):
    page = context.user_data.get('user_list_page', 0)  # Текущая страница, по умолчанию 0
    users = get_all_users()
    
    # Рассчитываем количество страниц
    total_pages = len(users) // USERS_PER_PAGE + (1 if len(users) % USERS_PER_PAGE > 0 else 0)
    
    # Получаем пользователей для текущей страницы
    page_users = users[page * USERS_PER_PAGE:(page + 1) * USERS_PER_PAGE]

    # Формируем текст сообщения
    message_text = "Список пользователей:\n\n"
    for user in page_users:
        telegram_login, recent_groups = user
        message_text += f"@{telegram_login}: {recent_groups}\n"

    # Создаем кнопки для листания
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data='list_users_prev_page'))
    if page + 1 < total_pages:
        buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data='list_users_next_page'))

    # Добавляем кнопки в разметку
    keyboard = [buttons] if buttons else []
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(message_text, reply_markup=reply_markup)

def update_schedule(update: Update, context: CallbackContext):
    global schedule_data
    document = update.message.document
    if document:
        file = context.bot.get_file(document.file_id)
        temp_file_path = file.download()  # Загружаем новый файл
        try:
            # Загружаем расписание из нового файла
            schedule_data = load_schedule(temp_file_path)  # Используем новый путь к файлу
            update.message.reply_text("Расписание успешно обновлено.")
        finally:
            os.remove(temp_file_path)  # Удаляем временный файл
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

    keyboard = [[InlineKeyboardButton(marked_groups.get(group, group), callback_data='group_' + group)] for group in keyboard_groups]
    keyboard.append([InlineKeyboardButton("Поиск 🔍", callback_data='start_search')])

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data='prev_page'))
    if page < max_page:
        navigation_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data='next_page'))
    if navigation_buttons:
        keyboard.append(navigation_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        query.edit_message_text(text="Выберите группу или начните поиск:", reply_markup=reply_markup)
    else:
        update.message.reply_text("Выберите группу или начните поиск:", reply_markup=reply_markup)

def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    data = query.data
    
    
    if data.startswith('group_'):
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

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()