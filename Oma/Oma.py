import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time

start_time = time.time()
cur_data_file = datetime.now().strftime("%d.%m.%Y")
    

def keep_only_digits_as_int(input_string):
    digits_str = ''.join(filter(str.isdigit, input_string))
    return int(digits_str) if digits_str else 0  # Если цифр нет, вернёт 0


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


def get_url_tile(group):
    q = requests.get(f'https://www.oma.by/{group}')
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    pages_count = int(soup.find('div', class_='page-title_title-cell').find('sup').text) / 24
    pages_count = int(pages_count) + (pages_count > int(pages_count))
    url_list = []
    for i in range(1, pages_count + 1):
        url = f'https://www.oma.by/{group}?PAGEN_1={i}'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('a', class_='area-link area-link-table')
        for page in pages:
            page_url = str("https://www.oma.by" + page.get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц группы {group}')
    url_list = list(set(url_list))
    with open(f'url_list_{cur_data_file}_{group}_oma.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


def get_data(group):
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(f'url_list_{cur_data_file}_{group}_oma.txt') as file:
        lines = [line.strip() for line in file.readlines()]
        for line in lines:
            try:
                q = requests.get(line)
                result = q.content
                soup = BeautifulSoup(result, 'lxml')
                cur_data = datetime.now().strftime("%d.%m.%Y")
                cur_time = datetime.now().strftime("%H:%M")

                try:
                    name = soup.find("h1").text.strip()
                except:
                    name = None

                try:
                    price_per_piece = soup.find('div', class_='product-info-box').find('div',
                                                                                       class_='product-info-box_price strong-price 1').text.strip()
                    old_price_piece = None
                except:
                    try:
                        price_per_piece = soup.find('div', class_='product-info-box').find('div',
                                                                                           class_='product-info-box_price strong-price red').text.strip()
                        old_price_piece = soup.find('div', class_='product-info-box').find('span',
                                                                                           class_='price__old').text.strip()
                    except:
                        price_per_piece = None
                        old_price_piece = None

                try:
                    price_per_square_meter = soup.find_all('div', class_='product-info-box_price strong-price 1')[
                        1].text.strip()
                    old_price_per_meter = None
                except:
                    try:
                        price_per_square_meter = soup.find('div', class_='product-info-box').find_all('div',
                                                                                                      class_='product-info-box_price strong-price red')[
                            1].text.strip()
                        old_price_per_meter = soup.find('div', class_='product-info-box').find_all('span',
                                                                                                   class_='price__old')[
                            1].text.strip()
                    except:
                        price_per_square_meter = None
                        old_price_per_meter = None

                try:
                    stocs = " ".join(soup.find("div",
                                               class_="product-item_delivery-row padding-card no-available-product-card").text.strip().split())
                except:
                    stocs = "Yes"

                try:
                    manufacturer = soup.find_all("div", class_="catalog-item-description_footer-item")[0].text.strip()
                except:
                    manufacturer = None

                try:
                    country_of_manufacture = soup.find_all("div", class_="catalog-item-description_footer-item")[
                        1].text.strip()
                except:
                    country_of_manufacture = None

                try:
                    сountry_of_import = soup.find_all("div", class_="catalog-item-description_footer-item")[
                        2].text.strip()
                except:
                    сountry_of_import = None

                try:
                    guarantee = soup.find_all("div", class_="catalog-item-description_footer-item")[3].text.strip()
                except:
                    guarantee = None

                left_spec = []
                right_spec = []
                specs = soup.find_all('span', class_="param-item_name")
                for spec in specs:
                    spec = " ".join(spec.text.strip().split())
                    left_spec.append(spec)
                rspecs = soup.find_all('span', class_="param-item_value-col")
                for rspec in rspecs:
                    rspec = " ".join(rspec.text.strip().split())
                    right_spec.append(rspec)
                specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}

                try:
                    internet_stocs = soup.find('div', class_='qty-stock').text.strip()
                except:
                    internet_stocs = 0

                try:
                    stocks_mesure = soup.find('div', class_='measure-stock').text.strip()
                except:
                    stocks_mesure = None

                stocks_counter = 0
                left_stocks = []
                right_stocks = []
                try:
                    quant_stock = soup.find_all('ul', class_='catalog-delivery_list')[-1].find_all('li')
                    for spec in quant_stock:
                        lspec = spec.find("span", class_='text-list_name').text.strip()
                        left_stocks.append(lspec)
                        rspec = spec.find("span", class_='text-list_value').text.replace(stocks_mesure, '').strip()
                        if rspec == "нет":
                            rspec = 0
                        else:
                            rspec = float(rspec)
                        right_stocks.append(rspec)
                        stocks_counter += (rspec)

                    quant_stock_dict = {left_stocks[i]: right_stocks[i] for i in
                                        range(len(right_stocks))}
                except:
                    quant_stock_dict = {}

                data = {
                    "Полное наименование": name,
                    "Действующая цена за шт.": price_per_piece,
                    "Цена без скидки за шт.": old_price_piece,
                    "Действующая цена за м2.": price_per_square_meter,
                    "Цена без скидки за м2.": old_price_per_meter,
                    "В наличии": stocs,
                    "Ссылка": line,
                    "Дата мониторинга": cur_data,
                    "Время мониторинга": cur_time,
                    "Магазин": "Oma",
                    'Производитель': manufacturer,
                    'Страна производства': country_of_manufacture,
                    'Страна импорта': сountry_of_import,
                    'Гарантийный срок': guarantee,
                    'Единица хранения на складе': stocks_mesure,
                    'Наличие в интернет-магазине:': internet_stocs,
                    'Суммарное наличие в магазинах': stocks_counter
                }

                data_dict.append(data | quant_stock_dict | specs_dict)
                print(f'Обработано карточек: {n}')
                n += 1

            except:
                break_line_count += 1
                break_line.append(line)
                print(f'Карточка пропущена. Обработано карточек: {n}')

        print(f'Сломанных ссылок: {break_line_count}')
        with open(f"data_{cur_data_file}_{group}_oma.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(f'url_break_list_{cur_data_file}_{group}_oma.txt', 'a') as file:
            for line in break_line:
                file.write(f'{line}\n')


def main():
    selected_groups = choice_group()
    for group in selected_groups:
        get_url_tile(group)
    for group in selected_groups:
        get_data(group)


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное {round(finish_time)} секунд на работу скрипта")
