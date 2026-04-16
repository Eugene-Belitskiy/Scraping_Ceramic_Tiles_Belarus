import json
from datetime import datetime
import time

start_time = time.time()
cur_data_file = datetime.now().strftime("%d.%m.%Y")


def choice_group():
    available_groups = [
        "keramicheskaya-plitka-c",
        "unitazy-c",
        "rakoviny-c",
        'tumby-pod-rakovinu-c',
        'sistemy-installyatsii-c'
    ]

    # Список для выбранных групп
    selected_groups = []

    print("Доступные группы для выбора:")
    for i, group in enumerate(available_groups, 1):
        print(f"{i}. {group}")

    print("\nВведите номера групп, которые хотите включить (через пробел):")
    user_input = input("> ")

    try:
        # Преобразуем ввод пользователя в список номеров
        chosen_indices = list(map(int, user_input.split()))

        # Добавляем выбранные группы в список
        for index in chosen_indices:
            if 1 <= index <= len(available_groups):
                selected_groups.append(available_groups[index - 1])
            else:
                print(f"Предупреждение: номер {index} недопустим и будет пропущен")

        print("\nВыбранные группы:")
        for group in selected_groups:
            print(f"- {group}")
        print()
        print("Начинаю работать...\n")

    except ValueError:
        print("Ошибка: пожалуйста, вводите только числа, разделенные пробелами")
    return selected_groups


def merged_dictionary(group):
    data_finally = []

    for day in range(18, 26):
        with open(f'data_{day}.08.2025_{group}_oma.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        data_finally = data_finally + data

    with open(f"data_finally_{cur_data_file}_{group}_oma.json", 'w', encoding="utf-8") as json_file:
        json.dump(data_finally, json_file, indent=4, ensure_ascii=False)


def main():
    selected_groups = choice_group()
    for group in selected_groups:
        merged_dictionary(group)


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное {round(finish_time)} секунд на работу скрипта")
