import json
from datetime import datetime
# from pprint import pprint

cur_data_file = datetime.now().strftime("%m.%Y")
cur_data_file = '12.2025'
with open('data_12.2025_Modus.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
data_new_modus = []
print(data)
for i in range(len(data)):
    try:
        if (data[i]['Материал'] != 'стекло' or data[i]['Материал'] != 'металл' or data[i]['Материал']):
            try:
                full_name = data[i]['Полное наименование']
            except:
                full_name = 'Не указано'
            try:
                price = data[i]['Действующая цена'].replace('.', ',')
            except:
                price = 'Не указано'
            try:
                unit_of_price = data[i]['Единица измерения цены'].replace('*', '')
            except:
                unit_of_price = 'Не указано'
            try:
                link = data[i]['Ссылка']
            except:
                link = None
            try:
                store = data[i]['Магазин']
            except:
                store = None
            try:
                date = data[i]['Дата мониторинга']
            except:
                date = None
            try:
                time = data[i]['Время мониторинга']
            except:
                time = None
            try:
                colour = data[i]['Цвета']
            except:
                colour = None
            try:
                collection = data[i]['Коллекция']
            except:
                collection = None
            try:
                brand = data[i]['Бренд']
            except:
                brand = None
            try:
                country = data[i]['Страна']
            except:
                country = None
            try:
                original_format = data[i]['Формат'].replace('х', 'x')
            except:
                try:
                    original_format = str(data[i]['Ширина']) + 'x' + str(data[i]['Длина (см.)'])
                except:
                    original_format = None
            try:
                side_1 = round(float(original_format[0, original_format.find('x') - 1]) / 5) * 5
                side_2 = round(float(original_format[original_format.find('x') + 1, len(original_format)]) / 5) * 5
                long_side = str(max(side_1, side_2))
                short_side = str(min(side_1, side_2))
                format_group = long_side + 'x' + short_side
            except:
                try:
                    long_side = int(round(max(float(data[i]['Ширина']), float(data[i]['Длина (см.)'])) / 5) * 5)
                    short_side = int(round(min(float(data[i]['Ширина']), float(data[i]['Длина (см.)'])) / 5) * 5)
                    format_group = str(long_side) + 'x' + str(short_side)
                except:
                    format_group = None
            try:
                texture = data[i]['Текстура плитки']
            except:
                texture = None
            try:
                in_stock = data[i]['Наличие товара']
            except:
                in_stock = None

            try:
                pin = data[i]["Место в коллекции"]
            except:
                pin = None

            try:
                if data[i]['Покрытие'] in ['глазурованная', 'глазурованный']:
                    glaz = 'Глазурованная'
                elif data[i]['Покрытие'] in ['неглазурованная', 'неглазурованный']:
                    glaz = 'Неглазурованная'
            except:
                glaz = None

            try:
                strukture = data[i]['Наличие структурной поверхности']
            except:
                strukture = None

            brand_country = brand + ' (' + country + ')'

            try:
                if data[i]['Материал'] == 'керамика':
                    material = 'керамика'
                elif data[i]['Материал'] == 'керамический гранит':
                    material = 'керамогранит'
                elif data[i]['Материал'] == 'клинкер':
                    material = 'клинкер'
                else:
                    material = None
            except:
                material = None

            try:
                surplace = data[i]['Вид поверхности плитки']
            except:
                surplace = None

            data_new_modus_append = {
                'Полное наименивание': full_name,
                'Действующая цена': price,
                'Цена без скидки': None,
                'Единица измерения цены': unit_of_price,
                'Ссылка': link,
                'Магазин': store,
                'Дата': date,
                'Время': time,
                'Цвет': colour,
                'Коллекция': collection,
                'Бренд': brand,
                'Страна': country,
                'Формат': original_format,
                'Группа форматов': format_group,
                'Текстура': texture,
                'Наличие': in_stock,
                'Бренд-Страна': brand_country,
                'Материал': material,
                'Тип поверхности': surplace,
                'Покрытие': glaz,
                'Структура': strukture,
                'Место в коллекции': pin
            }

            data_new_modus.append(data_new_modus_append)
    except:
        continue

with open(f"data_finally_Modus_{cur_data_file}.json", 'w', encoding="utf-8") as json_file:
    json.dump(data_new_modus, json_file, indent=4, ensure_ascii=False)
