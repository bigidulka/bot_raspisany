from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import json
import os
from func import extract_schedule_to_json
import re
import telegram


schedule_data = {}
GROUPS_PER_PAGE = 5  
SCHEDULE_FILE = 'schedule_file.xlsx'

def normalize_string(s):
    return re.sub(r'\s+', '', s).lower()

def split_string(s):
    return re.findall(r'[а-яА-Яa-zA-Z]+|\d+', s)

def filter_groups(user_input, groups):
    normalized_input = normalize_string(user_input)
    input_parts = split_string(normalized_input)
    filtered_groups = []

    for group in groups:
        normalized_group = normalize_string(group)
        if all(part in normalized_group for part in input_parts):
            filtered_groups.append(group)

    return filtered_groups

def format_schedule_for_group(group_schedule):
    schedule_text = ""
    for day, classes in group_schedule.items():
        schedule_text += f"\n{day}:\n"
        for class_session in classes:
            schedule_text += f"{class_session['Time']} - {class_session['Discipline']} ({class_session['Type of Class']})\n"
    return schedule_text



def select_day_of_week(update: Update, context: CallbackContext):
    
    group_name = context.user_data.get('selected_group')
    group_schedule = schedule_data.get(group_name, {})

    
    dates = list(group_schedule.keys())

    
    keyboard = [
        [InlineKeyboardButton(date, callback_data=f'day_{i}')] for i, date in enumerate(dates)
    ]

    
    keyboard.append([InlineKeyboardButton("Назад 🔙", callback_data='back_to_schedule_options')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    query.edit_message_text(text="Выберите день:", reply_markup=reply_markup)


    
def send_schedule_options(update: Update, context: CallbackContext):
    group_name = context.user_data.get('selected_group')
    group_schedule = schedule_data.get(group_name, {})

    
    dates = list(group_schedule.keys())
    start_date = dates[0] if dates else "Н/Д"
    end_date = dates[5] if len(dates) > 5 else dates[-1] if dates else "Н/Д"

    week_button_text = f"На неделю ({start_date} - {end_date})"

    keyboard = [
        [InlineKeyboardButton(week_button_text, callback_data='week')],
        [InlineKeyboardButton("Выбрать день", callback_data='select_day')],
        [InlineKeyboardButton("Назад 🔙", callback_data='back_to_group_selection')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    query.edit_message_text(text='Выберите опцию расписания:', reply_markup=reply_markup)






def format_class_session(class_session):
    if class_session['Discipline'] == 'день самостоятельной подготовки':
        return "День самостоятельной подготовки"
    else:
        type_of_class = f"[{class_session['Type of Class']}]" if class_session['Type of Class'] else ""
        
        if 'УЧЕБНАЯ ПРАКТИКА' in class_session['Discipline'] and not class_session['Teacher'] and not class_session['Auditorium']:
            return f"{class_session['Time']} - {class_session['Discipline']}"
        else:
            details = [type_of_class]
            if class_session['Teacher']:
                details.append(f"Преп: {class_session['Teacher']}")
            if class_session['Auditorium']:
                details.append(f"Ауд: {class_session['Auditorium']}")
            details_str = ", ".join(detail for detail in details if detail)  

            return f"{class_session['Time']} - {class_session['Discipline']} {details_str}".strip()

def get_schedule_for_day(group_name, day_offset, query):
    if group_name is None:
        query.edit_message_text(text="Группа не выбрана. Пожалуйста, выберите группу.")
        return
    
    week_days = list(schedule_data[group_name].keys())
    
    if day_offset < 0 or day_offset >= len(week_days):
        schedule_text = "Информация для этого дня недоступна."
    else:
        day_name = week_days[day_offset]
        day_schedule = schedule_data[group_name][day_name]
        
        schedule_text = f"<b>{day_name}:</b>\n"
        for class_session in day_schedule:
            if class_session['Discipline'] != 'nan':  
                formatted_session = format_class_session(class_session)  
                schedule_text += f"{formatted_session}\n"
        
        schedule_text = schedule_text.strip() if schedule_text != f"<b>{day_name}:</b>\n" else f"<b>{day_name}:</b>\n: Нет запланированных занятий."

    
    keyboard = [[InlineKeyboardButton("Назад 🔙", callback_data='back_to_schedule_options')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        query.edit_message_text(text=schedule_text, reply_markup=reply_markup, parse_mode='HTML')
    except telegram.error.BadRequest as e:
        print(f"Ошибка при редактировании сообщения: {e}")
    
def get_schedule_for_week(group_name, query):
    
    if group_name is None:
        query.edit_message_text(text="Группа не выбрана. Пожалуйста, выберите группу.")
        return

    
    week_days = list(schedule_data[group_name].keys())
    
    schedule_text = ""
    for day_name in week_days:
        day_schedule = schedule_data[group_name][day_name]
        day_text = f"<b>{day_name}:</b>\n"  
        for class_session in day_schedule:
            if class_session['Discipline'] != 'nan':  
                formatted_session = format_class_session(class_session)  
                day_text += f"{formatted_session}\n"
        if day_text != f"<b>{day_name}:</b>\n":
            schedule_text += day_text + "\n"  
    
    schedule_text = schedule_text.strip() if schedule_text else "На эту неделю занятий нет."

    
    keyboard = [[InlineKeyboardButton("Назад 🔙", callback_data='back_to_schedule_options')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        query.edit_message_text(text=schedule_text, reply_markup=reply_markup, parse_mode='HTML')
    except telegram.error.BadRequest as e:
        print(f"Ошибка при редактировании сообщения: {e}")




def send_back_button(query, text, callback_data):
    keyboard = [[InlineKeyboardButton("Назад", callback_data=callback_data)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=text, reply_markup=reply_markup)


def load_schedule():
    global schedule_data
    if os.path.exists(SCHEDULE_FILE):
        try:
            schedule_json = extract_schedule_to_json(SCHEDULE_FILE)
            schedule_data = json.loads(schedule_json)
            print("Расписание успешно загружено из файла.")
        except Exception as e:
            print(f"Ошибка при загрузке расписания: {e}")
    else:
        print("Файл с расписанием не найден. Пожалуйста, загрузите файл.")

def start(update: Update, context: CallbackContext) -> None:
    if not schedule_data:
        update.message.reply_text("Расписание отсутствует. Пожалуйста, загрузите файл с расписанием с помощью команды /update_schedule.")
    else:
        context.user_data['page'] = 0
        send_group_keyboard(update, context)

def send_group_keyboard(update: Update, context: CallbackContext):
    page = context.user_data.get('page', 0)
    group_keys = list(schedule_data.keys())
    max_page = (len(group_keys) - 1) // GROUPS_PER_PAGE
    start_index = page * GROUPS_PER_PAGE
    end_index = min(start_index + GROUPS_PER_PAGE, len(group_keys))
    keyboard_groups = group_keys[start_index:end_index]

    keyboard = [[InlineKeyboardButton(group, callback_data='group_' + group)] for group in keyboard_groups]

    
    keyboard.append([InlineKeyboardButton("Поиск 🔍", callback_data='search')])

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data='prev_page'))
    if page < max_page:
        navigation_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data='next_page'))

    if navigation_buttons:
        keyboard.append(navigation_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        query = update.callback_query
        query.edit_message_text(text="Выберите группу или начните поиск:", reply_markup=reply_markup)
    else:
        update.message.reply_text("Выберите группу или начните поиск:", reply_markup=reply_markup)


def search_group_result(update: Update, context: CallbackContext):
    user_input = update.message.text
    filtered_groups = filter_groups(user_input, schedule_data.keys())

    if filtered_groups:
        keyboard = [[InlineKeyboardButton(group, callback_data='group_' + group)] for group in filtered_groups]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Выберите группу из найденных:", reply_markup=reply_markup)
    else:
        update.message.reply_text("Группы не найдены.")


def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    data = query.data

    if data == 'search':
        
        query.edit_message_text(text="Введите название группы для поиска:")
        
    elif data == 'back_to_group_selection':
        send_group_keyboard(update, context)
    elif data == 'back_to_schedule_options':
        send_schedule_options(update, context)
    elif data.startswith('group_'):
        
        selected_group = data.split('_', 1)[1]
        context.user_data['selected_group'] = selected_group
        send_schedule_options(update, context)
    elif data == 'week':
        
        get_schedule_for_week(context.user_data.get('selected_group'), query)
    elif data.startswith('day_'):
        
        day_offset = int(data.split('_')[1])
        get_schedule_for_day(context.user_data.get('selected_group'), day_offset, query)
    elif data == 'select_day':
        select_day_of_week(update, context)
    elif data in ['prev_page', 'next_page']:
        
        page = context.user_data.get('page', 0)
        if data == 'prev_page':
            context.user_data['page'] = max(0, page - 1)
        else:  
            context.user_data['page'] = page + 1
        send_group_keyboard(update, context)
    else:
        
        query.edit_message_text(text="Неизвестная команда.")



def update_schedule(update: Update, context: CallbackContext) -> None:
    document = update.message.document
    if document:
        file = context.bot.get_file(document.file_id)
        file.download(SCHEDULE_FILE)
        load_schedule()
        update.message.reply_text("Расписание успешно обновлено.")
    else:
        update.message.reply_text("Пожалуйста, отправьте файл с расписанием.")
    

def main():
    load_schedule()
    updater = Updater("6668495629:AAGlmeOCtw9dQxSXr31UugK9bLGfsimw-Xg", use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("update_schedule", update_schedule))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.document, update_schedule))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, search_group_result))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
