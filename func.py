import pandas as pd
import json

def replicate_discipline_info(schedule):
    for day, sessions in schedule.items():
        # Loop through all sessions, including the last one
        for i in range(len(sessions)):
            current_session = sessions[i]
            
            # For all but the last session
            if i < len(sessions) - 1:
                next_session = sessions[i + 1]
                # Check if the current session has a discipline and the next one lacks it but has a teacher and auditorium
                if current_session['Discipline'] != 'nan' and next_session['Discipline'] == 'nan' and next_session['Teacher'] and next_session['Auditorium']:
                    # Replicate discipline information to the next session
                    next_session['Discipline'] = current_session['Discipline']
                    sessions[i + 2]['Discipline'] = current_session['Discipline']

def extract_schedule_to_json(file_path):
    # Define weekdays
    week_days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]

    df = pd.read_excel(file_path, sheet_name='Колледж ВятГУ', header=None, skiprows=23, nrows=44, usecols='A:HN')
    groups = {}

    class_times_first_five_days = [
        "8.20-9.50", "10.00-11.30", "11.45-13.15", "14.00-15.30", "15.45-17.15", "17.20-18.50", "18.55 - 20.25"
    ]
    class_times_sixth_day = [
        "8.20-9.50", "10.00-11.30", "11.45-13.15", "13.20-14.50", "14.55-16.25", "16.30-18.00"
    ]

    # Extract group names and data
    for col in range(df.shape[1]):
        cell_value = df.iloc[0, col]
        if pd.notnull(cell_value):
            if "\n" in str(cell_value):
                group_names = str(cell_value).split("\n")
            else:
                group_names = [str(cell_value)]

            for group_name in group_names:
                group_name = group_name.strip()
                if "Группа" in group_name:
                    start_col, end_col = col, min(col + 3, df.shape[1] - 1)
                    schedule_data = df.iloc[1:43, start_col:end_col + 1].copy()
                    groups[group_name] = schedule_data

    structured_data = {}

    # Read dates from Excel
    dates_df = pd.read_excel(file_path, sheet_name='Колледж ВятГУ', header=None, usecols="G:H", nrows=41, skiprows=25)
    dates = dates_df.iloc[::7, 0].dropna().tolist()
    dates = [date.split()[1] for date in dates]  # Extracting dates

    for group_name, schedule in groups.items():
        structured_group_data = {}
        day_counter = 0  # Reset day counter for each group
        time_index = 0

        for index, row in schedule.iterrows():
            if str(row.iloc[0]).strip() == "Дисциплина,модуль":
                time_index = 0  # Reset time index at the start of each day
                day_schedule = []
                continue

            class_times = class_times_first_five_days if day_counter < 5 else class_times_sixth_day
            time = class_times[time_index] if time_index < len(class_times) else ""

            class_session = {
                "Time": time,
                "Discipline": str(row.iloc[0]).strip(),
                "Type of Class": str(row.iloc[1]).strip() if pd.notnull(row.iloc[1]) else "",
                "Teacher": str(row.iloc[2]).strip() if pd.notnull(row.iloc[2]) else "",
                "Auditorium": str(row.iloc[3]).strip() if pd.notnull(row.iloc[3]) else ""
            }
            day_schedule.append(class_session)
            time_index += 1

            # Check if we need to move to the next day
            if (time_index == len(class_times) and day_counter < 5) or (time_index == len(class_times_sixth_day) and day_counter == 5) or index == schedule.index[-1]:
                # Use the day_counter to index into week_days
                day_key = f"{week_days[day_counter % len(week_days)]}, {dates[day_counter]}"  # Combine day and date
                structured_group_data[day_key] = day_schedule
                day_schedule = []  # Reset day schedule for the next day
                day_counter += 1  # Move to the next day
                time_index = 0  # Reset time index for the new day

        structured_data[group_name] = structured_group_data

    for group_name, structured_group_data in structured_data.items():
        replicate_discipline_info(structured_group_data)

    json_data = json.dumps(structured_data, ensure_ascii=False, indent=4)
    return json_data