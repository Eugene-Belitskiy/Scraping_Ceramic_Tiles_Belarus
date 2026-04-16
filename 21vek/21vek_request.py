import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time

start_time = time.time()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}
cur_data_file = datetime.now().strftime("%m.%Y")


def get_url_tile():
    url = f'https://www.21vek.by/tile/'
    q = requests.get(url=url, headers=headers)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    # print(soup)
    pages_counts = int(soup.find_all('div', class_='Pagination-module__pageText')[-1].text)
    print(pages_counts)

    url_list = []
    UNP_list = []
    # for i in range(1, 2):
    for i in range(1, pages_counts + 1):
        url = f'https://www.21vek.by/tile/page:{i}/'
        q = requests.get(url=url, headers=headers)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        # print(soup)
        pages = soup.find_all('div', class_='ListingProduct_product__WBPsd')
        # print(pages)
        for page in pages:
            name_base = page.find('a', {'data-testid': 'card-info'}).text.strip()
            page_url = page.find('a', {'data-testid': 'card-info'}).get('href')
            # print(page_url)
            try:
                price_base = page.find('span', {'data-testid': 'card-current-price'}).text.strip().replace(' р.',
                                                                                                           '').replace(
                    ' ', '')
            except:
                price_base = page.find('span',
                                       class_='CardStatus_statusText__u1LeJ Text-module__text Text-module__tiny Text-module__bold').text.strip()

            try:
                old_price_base = page.find('span', {'data-testid': 'card-old-price'}).text.strip().replace(' р.',
                                                                                                           '').replace(
                    ' ', '')
            except:
                old_price_base = price_base

            url_list.append('https://www.21vek.by' + str(page_url))

            UNP_list.append(
                {
                    'Наименование': name_base,
                    'Ссылка': 'https://www.21vek.by' + str(page_url),
                    f'Действующая цена_{cur_data_file}': price_base,
                    f'Цена без скидки_{cur_data_file}': old_price_base
                }
            )
        print(f'Обработал {i} из {pages_counts} страниц')


    with open(f'url_list_{cur_data_file}_21_vek_Tile.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')
    with open(f"data_{cur_data_file}_21_vek_Tile_BASE.json", 'w', encoding="utf-8") as json_file:
        json.dump(UNP_list, json_file, indent=4, ensure_ascii=False)


def get_data():
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(f'url_list_{cur_data_file}_21_vek_Tile.txt') as file:
        lines = [line.strip() for line in file.readlines()]
        for line in lines:
            try:
                q = requests.get(url=line, headers=headers)
                result = q.content
                soup = BeautifulSoup(result, 'lxml')
                cur_data = datetime.now().strftime("%d.%m.%Y")
                cur_time = datetime.now().strftime("%H:%M")

                try:
                    name = soup.find("h1").text.strip()
                except:
                    name = "Не_указано"

                try:
                    new_price = soup.find('div', {'data-testid': 'squarePrice'}).find('span').text.strip()
                    price_units = 'м2'

                except:
                    try:
                        new_price = soup.find('div', {'data-testid': 'unitPrice'}).find('span').text.strip()
                        price_units = 'шт'
                    except:
                        new_price = None
                        price_units = None

                try:
                    old_price = soup.find('div', {'data-testid': 'squarePrice'}).find('div').text.strip()

                except:
                    try:
                        old_price = soup.find('div', {'data-testid': 'unitPrice'}).find('div').text.strip()
                    except:
                        old_price = new_price

                if new_price == "Нет в наличии":
                    stocs = new_price
                else:
                    stocs = "В наличии"

                Manufacture_Info = None
                try:
                    Manufacture_Info = soup.find('div', {'data-testid': 'bottomBlockProducerInfo'}).find_all('p')
                    for i in range(len(Manufacture_Info)):
                        if 'Страна производства' in Manufacture_Info[i].text:
                            country = Manufacture_Info[i].text.replace('Страна производства:', '').strip()
                        if 'Производитель' in Manufacture_Info[i].text:
                            manufacturer = Manufacture_Info[i].text.replace('Производитель:', '').strip()
                        if 'Поставщик' in Manufacture_Info[i].text:
                            supplier = Manufacture_Info[i].text.replace('Поставщик:', '').strip()
                except:
                    country, manufacturer, supplier = 'Не указано / ошибка', 'Не указано / ошибка', 'Не указано / ошибка'

                left_spec = []
                right_spec = []

                specs = soup.find('div', {'id': 'attributesBlock'}).find_all('dt', class_="Attribute_title__rQ5Dp")
                for spec in specs:
                    spec = spec.text.strip()
                    left_spec.append(spec)

                rspecs = soup.find('div', {'id': 'attributesBlock'}).find_all('dd', class_="Attribute_value__re9Rr")
                for rspec in rspecs:
                    rspec = rspec.text.strip()
                    right_spec.append(rspec)

                specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}
                data = {
                    "Полное наименование": name,
                    f"Действующая цена_{cur_data_file}": new_price,
                    f"Цена без скидки_{cur_data_file}": old_price,
                    "Единица измерения цены": price_units,
                    "Ссылка": line,
                    "Дата мониторинга": cur_data,
                    "Время мониторинга": cur_time,
                    "Магазин": "21 век",
                    "В наличии": stocs,
                    "Страна производства": country,
                    "Производитель": manufacturer,
                    "Поставщик": supplier
                }

                data_dict.append(data | specs_dict)
                print(f'Обработано карточек: {n}')
            except:
                break_line_count += 1
                break_line.append(line)
                print(f'Карточка пропущена. Обработано карточек: {n}')
            n += 1

        print(f'Сломанных ссылок: {break_line_count}')
        with open(f"data_{cur_data_file}_21_vek_Tile.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(f'urls_break_{cur_data_file}_21_vek-WC.txt', 'a') as file:
            for line in break_line:
                file.write(f'{line}\n')


def get_new_data():
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(f'new_url_list_{cur_data_file}_21_vek_Tile.txt') as file:
        lines = [line.strip() for line in file.readlines()]
        for line in lines:
            try:
                q = requests.get(url=line, headers=headers)
                result = q.content
                soup = BeautifulSoup(result, 'lxml')
                cur_data = datetime.now().strftime("%d.%m.%Y")
                cur_time = datetime.now().strftime("%H:%M")

                try:
                    name = soup.find("h1").text.strip()
                except:
                    name = "Не_указано"

                try:
                    new_price = soup.find('span',
                                          class_='ProductPrice_productPrice__thjM7 Prices_price__41d3a Text-module__text Text-module__body').text.replace(
                        ' р.', '').strip()
                except:
                    new_price = "Нет в наличии"

                try:
                    old_price = soup.find("div",
                                          class_="Prices_oldPrice__YS0WI Text-module__text Text-module__caption Text-module__strikethrough").text.replace(
                        ' р.', '').replace(' ', '').strip()
                except:
                    old_price = new_price

                # try:
                #     price_units = soup.find("span", class_="g-price__unit item__priceunit").text.strip()
                # except:
                #     price_units = "Не_указано"

                if new_price == "Нет в наличии":
                    stocs = new_price
                else:
                    stocs = "В наличии"

                try:
                    Manufacture_Info = soup.find('div', {'data-testid': 'bottomBlockProducerInfo'}).find_all('p')
                    for i in range(len(Manufacture_Info)):
                        if 'Страна производства' in Manufacture_Info[i].text:
                            country = Manufacture_Info[i].text.replace('Страна производства:', '').strip()
                        if 'Производитель' in Manufacture_Info[i].text:
                            manufacturer = Manufacture_Info[i].text.replace('Производитель:', '').strip()
                        if 'Поставщик' in Manufacture_Info[i].text:
                            supplier = Manufacture_Info[i].text.replace('Поставщик:', '').strip()
                except:
                    country, manufacturer, supplier = 'Не указано / ошибка', 'Не указано / ошибка', 'Не указано / ошибка'

                left_spec = []
                right_spec = []

                specs = soup.find('div', {'id': 'attributesBlock'}).find_all('dt', class_="Attribute_title__rQ5Dp")
                for spec in specs:
                    spec = spec.text.strip()
                    left_spec.append(spec)

                rspecs = soup.find('div', {'id': 'attributesBlock'}).find_all('dd', class_="Attribute_value__re9Rr")
                for rspec in rspecs:
                    rspec = rspec.text.strip()
                    right_spec.append(rspec)

                specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}
                data = {
                    "Полное наименование": name,
                    f"Действующая цена_{cur_data_file}": new_price,
                    f"Цена без скидки_{cur_data_file}": old_price,
                    # "Единица измерения цены": price_units,
                    "Ссылка": line,
                    "Дата мониторинга": cur_data,
                    "Время мониторинга": cur_time,
                    "Магазин": "21 век",
                    "В наличии": stocs,
                    "Страна производства": country,
                    "Производитель": manufacturer,
                    "Поставщик": supplier
                }

                data_dict.append(data | specs_dict)
                print(f'Обработано карточек: {n}')
            except:
                break_line_count += 1
                break_line.append(line)
                print(f'Карточка пропущена. Обработано карточек: {n}')
            n += 1

        print(f'Сломанных ссылок: {break_line_count}')
        with open(f"new_data_{cur_data_file}_21_vek_Tile.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(f'new_urls_break_{cur_data_file}_21_vek-WC.txt', 'a') as file:
            for line in break_line:
                file.write(f'{line}\n')


def new_url_list(prev_month):
    with open(f"data_{prev_month}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
        data_prev = json.load(f)
    with open(f"data_{cur_data_file}_21_vek_Tile_BASE.json", 'r', encoding='utf-8') as f:
        data_new = json.load(f)

    base_of_url = []
    new_url_list = []

    for i in range(len(data_prev)):
        base_of_url.append(data_prev[i]['Ссылка'])
    for i_ in data_new:
        if i_['Ссылка'] not in base_of_url:
            new_url_list.append(i_['Ссылка'])

    with open(f'new_url_list_{cur_data_file}_21_vek_Tile.txt', 'a') as file:
        for line in new_url_list:
            file.write(f'{line}\n')


def add_def(prev_month):
    try:
        with open(f"data_finally_{prev_month}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
            data_prev = json.load(f)
    except:
        with open(f"data_{prev_month}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
            data_prev = json.load(f)
    with open(f"data_{cur_data_file}_21_vek_Tile_BASE.json", 'r', encoding='utf-8') as f:
        data_new = json.load(f)
    for i in range(len(data_prev)):
        for i_ in data_new:
            if data_prev[i]['Ссылка'] == i_['Ссылка']:
                data_prev[i][f'Действующая цена_{cur_data_file}'] = i_[f'Действующая цена_{cur_data_file}']
                data_prev[i][f'Цена без скидки_{cur_data_file}'] = i_[f'Цена без скидки_{cur_data_file}']

                break
            else:
                continue

    with open(f"data_{cur_data_file}_21_vek_Tile.json", 'w', encoding="utf-8") as json_file:
        json.dump(data_prev, json_file, indent=4, ensure_ascii=False)


def get_finally_data():
    with open(f"data_{cur_data_file}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
        data_prev = json.load(f)
    with open(f"new_data_{cur_data_file}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
        data_new = json.load(f)

    for i in data_new:
        data_prev.append(i)

    with open(f"data_finally_{cur_data_file}_21_vek_Tile_finally.json", 'w', encoding="utf-8") as json_file:
        json.dump(data_prev, json_file, indent=4, ensure_ascii=False)


# def main():
#     get_url_tile()
#     add_def(prev_month)
#     new_url_list(prev_month)
#     get_new_data()
#     get_finally_data()
#     pass


def main_first():
    get_url_tile()
    get_data()


# answer = input(
#     'Вы хотите дополнить последнюю базу данных? (Укажите "Да"), если запустить код в первый раз, то укажите "Нет"')
#
# if answer == "Да":
#     prev_month = input('Введите месяц крайнего мониторинга данного сайта в формате "MM.ГГГГ" ')
#
#     if __name__ == '__main__':
#         main()
#         finish_time = time.time() - start_time
#         print(f"Затраченное на работу скрипта время: {finish_time}")
# else:
#     if __name__ == '__main__':
#         main_first()
#         finish_time = time.time() - start_time
#         print(f"Затраченное на работу скрипта время: {finish_time}")

if __name__ == '__main__':
    main_first()
    finish_time = time.time() - start_time
    print(f"Затраченное на работу скрипта время: {finish_time}")
