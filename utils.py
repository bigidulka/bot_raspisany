# File path: utils.py
import re
import json
import os
from func import extract_schedule_to_json

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

    # Разделение информации о нескольких подгруппах
    disciplines = class_session['Discipline'].split('\n')
    teachers = class_session['Teacher'].split('\n')
    auditoriums = class_session['Auditorium'].split('\n')
    
    formatted_session = ""
    time = f"<u>{class_session['Time']}</u>"  # Подчеркиваем время для обычных занятий

    # Обходим каждую подгруппу
    for idx, discipline in enumerate(disciplines):
        if discipline.lower() == 'nan':
            continue

        type_of_class = f"[{class_session['Type of Class']}]" if class_session['Type of Class'] else ""
        teacher = f"Преп: {teachers[idx]}" if idx < len(teachers) and teachers[idx] else ""
        auditorium = f"Ауд: {auditoriums[idx]}" if idx < len(auditoriums) and auditoriums[idx] else ""
        
        details = ", ".join(detail for detail in [type_of_class, teacher, auditorium] if detail)
        
        if idx == 0:
            formatted_session += f"{time} - {discipline} {details}"
        else:
            formatted_session += f"\n    {discipline} {details}"  # Для подгрупп добавляем отступ

    return formatted_session.strip()

def load_schedule(file_path):
    if os.path.exists(file_path):
        try:
            schedule_json = extract_schedule_to_json(file_path)
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





def find_teacher_days(schedule_data, teacher_lastname):
    """Найти все дни с занятиями для указанного учителя."""
    teacher_days = {}
    for group_name, week_schedule in schedule_data.items():
        for day_name, day_schedule in week_schedule.items():
            for class_session in day_schedule:
                teachers = class_session['Teacher'].split('\n')
                formatted_session = format_class_session(class_session)
                if formatted_session and any(teacher_lastname.lower() in teacher.lower() for teacher in teachers):
                    if day_name not in teacher_days:
                        teacher_days[day_name] = []
                    # Добавляем проверку на вхождение имени преподавателя в отформатированную сессию
                    if teacher_lastname.lower() in formatted_session.lower():
                        teacher_days[day_name].append(formatted_session)
    return teacher_days

from datetime import datetime
import re

def parse_time(time_str):
    """Parse time from the formatted session string, removing HTML tags."""
    # Удаление HTML тегов
    clean_time_str = re.sub(r'<[^>]*>', '', time_str)
    # Извлечение времени начала
    time_range = clean_time_str.split('-')[0].strip()
    start_time_str = time_range.split(' ')[0]
    return datetime.strptime(start_time_str, "%H.%M").time()

def show_teacher_schedule_for_day(teacher_days, day_name):
    """Вывести расписание для учителя в выбранный день, отсортированное по времени."""
    if day_name in teacher_days:
        # Сортируем список занятий по времени начала
        sorted_sessions = sorted(teacher_days[day_name], key=lambda x: parse_time(x))
        return "\n".join(sorted_sessions)
    else:
        return "В этот день занятий у указанного учителя нет."
