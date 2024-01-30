from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import os
from utils import load_schedule, filter_groups, get_schedule_for_day, get_schedule_for_week, GROUPS_PER_PAGE
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
        if selected_group not in groups_list:
            groups_list.append(selected_group)
            groups_list = groups_list[-3:]  # Оставляем только последние три группы
        recent_groups = ",".join(groups_list)
    else:
        recent_groups = selected_group

    cursor.execute('''
    INSERT INTO users (id, telegram_login, recent_groups) VALUES (?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET telegram_login = excluded.telegram_login, recent_groups = excluded.recent_groups
    ''', (user_id, telegram_login, recent_groups))
    conn.commit()

def get_user(user_id):
    """Получение информации о пользователе по ID."""
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    return cursor.fetchone()



SEARCH, UPDATE_SCHEDULE, CHOOSING_GROUP = range(3)
schedule_data = {} 

def start_update_schedule(update: Update, context: CallbackContext):
    update.message.reply_text("Пожалуйста, отправьте файл с расписанием.")
    return UPDATE_SCHEDULE

def update_schedule(update: Update, context: CallbackContext):
    global schedule_data
    document = update.message.document
    if document:
        file = context.bot.get_file(document.file_id)
        temp_file_path = file.download()
        try:
            schedule_data = load_schedule() 
            update.message.reply_text("Расписание успешно обновлено.")
        finally:
            os.remove(temp_file_path) 
    else:
        update.message.reply_text("Ошибка загрузки файла.")
    return ConversationHandler.END
        
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
        
    return CHOOSING_GROUP


        
def handle_day_schedule(query, group_name, day_offset):
    schedule_text = f"Расписание на день для группы {group_name}:\n\n"
    schedule_text += get_schedule_for_day(schedule_data, group_name, day_offset)
    keyboard = [
        [InlineKeyboardButton("Назад 🔙", callback_data='back_to_day_selection')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=schedule_text, reply_markup=reply_markup, parse_mode='HTML')

def handle_week_schedule(query, group_name):
    schedule_text = f"Расписание на неделю для группы {group_name}:\n\n"
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
    return ConversationHandler.END

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
        
        return CHOOSING_GROUP
        
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
            return
    
    elif data == 'start_search':
        query.edit_message_text(text="Введите название группы для поиска:")
        return SEARCH
                
    else:
        query.edit_message_text(text="Неизвестная команда.")   
        

    
def main():
    global schedule_data
    schedule_data = load_schedule()
    updater = Updater("6818826799:AAF2xKtBprs9f_N0L0jVl9fQ3KupmOpr3MI", use_context=True)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, search_group_result))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('update_schedule', start_update_schedule), CommandHandler('start', start)],
        states={
            UPDATE_SCHEDULE: [MessageHandler(Filters.document, update_schedule)]
        },
        fallbacks=[]
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()