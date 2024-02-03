import re
import json
import os
from func import extract_schedule_to_json

SCHEDULE_FILE = 'schedule_file.xlsx'
GROUPS_PER_PAGE = 5 

def normalize_string(s):
    """Normalize strings by removing spaces and converting to lowercase."""
    return re.sub(r'\s+', '', s).lower()

def split_string(s):
    """Split strings into alphanumeric parts."""
    return re.findall(r'[а-яА-Яa-zA-Z]+|\d+', s)

def filter_groups(user_input, groups):
    """Filter group names based on user input."""
    normalized_input = normalize_string(user_input)
    input_parts = split_string(normalized_input)
    filtered_groups = [group for group in groups if all(part in normalize_string(group) for part in input_parts)]
    return filtered_groups

def format_schedule_for_group(group_schedule):
    """Format the schedule for a specific group."""
    schedule_text = ""
    for day, classes in group_schedule.items():
        schedule_text += f"\n{day}:\n"
        for class_session in classes:
            schedule_text += f"{class_session['Time']} - {class_session['Discipline']} ({class_session['Type of Class']})\n"
    return schedule_text

def format_class_session(class_session):
    """Format individual class sessions for display, skipping 'nan' entries."""
    if class_session['Discipline'].strip().lower() == 'nan':
        return None

    # Проверка на самостоятельную подготовку
    if 'самостоятельной подготовки' in class_session['Discipline'].lower():
        time = ""  # Не отображаем время для самостоятельной подготовки
    else:
        time = f"<u>{class_session['Time']}</u>"  # Подчеркиваем время для обычных занятий

    discipline = class_session['Discipline']
    type_of_class = f"[{class_session['Type of Class']}]" if class_session['Type of Class'] else ""
    teacher = f"Преп: {class_session['Teacher']}" if class_session['Teacher'] else ""
    auditorium = f"Ауд: {class_session['Auditorium']}" if class_session['Auditorium'] else ""

    details = ", ".join(detail for detail in [type_of_class, teacher, auditorium] if detail)
    formatted_session = f"{time} - {discipline} {details}".strip()

    return formatted_session

def load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        try:
            schedule_json = extract_schedule_to_json(SCHEDULE_FILE)  
            schedule_data = json.loads(schedule_json)
            print("Расписание успешно загружено из файла.")
            return schedule_data  
        except Exception as e:
            print(f"Ошибка при загрузке расписания: {e}")
            return {}  
    else:
        print("Файл с расписанием не найден. Пожалуйста, загрузите файл.")
        return {} 

def get_schedule_for_day(schedule_data, group_name, day_offset):
    """Generate schedule text for a specific day."""
    if group_name not in schedule_data:
        return "Группа не найдена."

    week_days = list(schedule_data[group_name].keys())
    
    if day_offset < 0 or day_offset >= len(week_days):
        return "Информация для этого дня недоступна.", False
    
    day_name = week_days[day_offset]
    day_schedule = schedule_data[group_name][day_name]
    
    schedule_text = f"<b>{day_name}:</b>\n"
    for class_session in day_schedule:
        formatted_session = format_class_session(class_session)
        if formatted_session:  
            schedule_text += f"{formatted_session}\n"
    
    return schedule_text

def get_schedule_for_week(schedule_data, group_name):
    """Generate schedule text for the entire week."""
    if group_name not in schedule_data:
        return "Группа не найдена."

    week_schedule = schedule_data[group_name]
    schedule_text = ""
    
    for day_name, day_schedule in week_schedule.items():
        schedule_text += f"<b>{day_name}:</b>\n"
        for class_session in day_schedule:
            formatted_session = format_class_session(class_session)
            if formatted_session:  
                schedule_text += f"{formatted_session}\n"
        schedule_text += "\n"
        
    return schedule_text