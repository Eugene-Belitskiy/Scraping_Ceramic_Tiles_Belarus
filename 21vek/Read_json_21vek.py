import json
from pprint import pprint
import csv

with open('data_02.2025_21_vek_Tile.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
data_new_21vek = []
n = 0
brand_list = []
for i in range(len(data)):
    try:
        if data[i]['Материал'] in ['керамика', 'керамика (глазурованная керамика)', 'керамика (глазурованная)',
                                   'керамогранит (грес)', 'керамогранит (грес) (глазурованный)',
                                   'керамогранит (грес) (неглазурованный)', 'клинкер'] and 'Материал' in data[i] and \
                data[i]['В наличии'] == 'В наличии':

            try:
                num_ = data[i]['Коллекция'].find('(')
                collection = data[i]['Коллекция'][:num_ - 1]
            except:
                collection = None
            try:
                brand_uniq = data[i]['Коллекция'][num_ + 1:len(data[i]['Коллекция']) - 1]
            except:
                brand_uniq = None
    except:
        continue

    if brand_uniq not in brand_list and brand_uniq is not None:
        brand_list.append(brand_uniq)
# записали список брендов


for i in range(len(data)):
    # for i in range(2):
    try:
        if data[i]['Материал'] in ['керамика', 'керамика (глазурованная керамика)', 'керамика (глазурованная)',
                                   'керамогранит (грес)', 'керамогранит (грес) (глазурованный)',
                                   'керамогранит (грес) (неглазурованный)', 'клинкер'] and 'Материал' in data[i] and \
                data[i]['В наличии'] == 'В наличии':

            try:
                full_name = data[i]['Полное наименование']
            except:
                full_name = 'Не указано'


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
                colour = data[i]['Цвет']
            except:
                colour = None
            try:
                num_ = data[i]['Коллекция'].find('(')
                collection = data[i]['Коллекция'][:num_ - 1]
            except:
                collection = None
            try:
                x = 0
                while True:
                    if brand_list[x] in data[i]['Полное наименование']:
                        brand = brand_list[x]
                        break
                    x += 1
            except:
                try:
                    brand = data[i]['Коллекция'][num_+1:len(data[i]['Коллекция']-1)]
                except:
                    try:
                        brand = data[i]['Производитель'][0:data[i]['Производитель'].find(',')].replace('Производитель: ','')
                    except:
                        brand = 'Не указано'

            try:
                country = data[i]['Страна производства'].replace('Страна производства: ', '')
            except:
                country = None

            try:
                original_format = str(data[i]['Ширина'].replace(' ', '').replace('мм', '')) + 'x' + str(data[i]['Длина'].replace(' ', '').replace('мм', ''))
            except:
                try:
                    original_format = data[i]['Полное наименование'][data[i]['Полное наименование'].find('('):data[i]['Полное наименование'].find(')')]
                except:
                    original_format = None
            original_format = original_format.replace('х', 'x')

            try:
                side_1 = round(float(original_format[0:original_format.find('x')]) / 50) * 5
                side_2 = round(float(original_format[original_format.find('x') + 1:len(original_format)]) / 50) * 5
                long_side = str(max(side_1, side_2))
                short_side = str(min(side_1, side_2))
                format_group = long_side + 'x' + short_side
            except:
                format_group = None
                print('error')

            original_format = original_format.replace('х', 'x') + ' мм'

            try:
                texture = data[i]['Дизайн плитки'].replace('имитация ','')
            except:
                texture = None

            try:
                in_stock = data[i]['В наличии']
            except:
                in_stock = None

            try:
                brand_country = brand + ' (' + country + ')'
            except:
                brand_country = None
            try:
                if 'керамика' in data[i]['Материал']:
                    material = 'керамика'
                elif 'керамогранит' in data[i]['Материал']:
                    material = 'керамогранит'
                elif 'клинкер' in data[i]['Материал']:
                    material = 'клинкер'
                else:
                    material = 'Другое'
            except:
                material = None

            try:
                surplace = data[i]['Поверхность']
            except:
                surplace = None

            try:
                if material == 'керамогранит':
                    pin = 'керамогранит'
                else:
                    pin = data[i]["Тип"]
            except:
                pin = None

            try:
                if 'неглазур' in data[i]['Материал']:
                    glaz = 'Неглазурованная'
                elif 'глазур' in data[i]['Материал'] or 'керамика' in data[i]['Материал']:
                    glaz = 'Глазурованная'
                elif data[i]['Материал'] in ['моноколор', 'моноколор, соль-перец', 'соль-перец']:
                    glaz = 'Неглазурованная'
                else:
                    glaz = 'Глазурованная*'
            except:
                glaz = None

            try:
                if 'есть' in data[i]['Рельеф']:
                    strukture = 'Да'
                else:
                    strukture = 'Нет'
            except:
                strukture = 'Нет'


            data_new_21vek_append = {
                'Полное наименивание': full_name,
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

            data_new_21vek.append(data_new_21vek_append)
    except:
        continue
with open(f"data_finally_21vek_feb.json", 'w', encoding="utf-8") as json_file:
    json.dump(data_new_21vek, json_file, indent=4, ensure_ascii=False)



def merged_dictionary():
    with open('data_finally_21vek.json', 'r', encoding='utf-8') as f:
        data_1 = json.load(f)
    with open('data_finally_modus.json', 'r', encoding='utf-8') as f:
        data_2 = json.load(f)

    merged_dict = data_1 + data_2

    with open(f"data_finally_feb_21vek.json", 'w', encoding="utf-8") as json_file:
    # with open(f"data_finally.json", 'w') as json_file:
        json.dump(merged_dict, json_file, indent=4, ensure_ascii=False)


    field_names = ['Полное наименивание',
                'Действующая цена',
                "Диапазон действующей цены",
                "Размер скидки",
                "Диапазон размера скидки",
                'Единица измерения цены',
                'Ссылка',
                'Магазин',
                'Наличие',
                'Дата мониторинга',
                'Время мониторинга',
                'Цвет',
                'Коллекция',
                'Бренд',
                'Страна',
                'Бренд-Страна',
                'Толщина',
                'Оригинальный формат',
                'Группа форматов',
                'Дизайн',
                'Материал',
                'Тип поверхности',
                'Тип покрытия (полир/ не полир)',
                'Структура',
                "Количество лиц",
                "Город"]


    with open('Names.csv', 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(merged_dict)



# merged_dictionary()
