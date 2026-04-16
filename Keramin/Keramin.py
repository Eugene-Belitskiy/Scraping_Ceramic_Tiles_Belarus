import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time

start_time = time.time()
cur_data_file = datetime.now().strftime("%m.%Y")


def get_url_tile():
    url = f'https://keramin.by/produkciya/plitka/all?page=1'
    q = requests.get(url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    url_pages_count = str(soup.find('li', class_='pager-last last').find('a').get('href'))
    pages_count = int(url_pages_count[url_pages_count.find('=') + 1:len(url_pages_count)])
    url_list = []
    for i in range(0, pages_count + 1):
        url = f'https://keramin.by/produkciya/plitka/all?page={i}'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('div', class_='views-field views-field-title')
        for page in pages:
            page_url = str("https://keramin.by" + page.find('span', class_='field-content').find('a').get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')

    url = f'https://keramin.by/produkciya/keramogranit/all?page=1'
    q = requests.get(url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    url_pages_count = str(soup.find('li', class_='pager-last last').find('a').get('href'))
    pages_count = int(url_pages_count[url_pages_count.find('=') + 1:len(url_pages_count)])
    for i in range(0, pages_count + 1):
        url = f'https://keramin.by/produkciya/keramogranit/all?page={i}'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('div', class_='views-field views-field-title')
        for page in pages:
            page_url = str("https://keramin.by" + page.find('span', class_='field-content').find('a').get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')

    url = f'https://keramin.by/produkciya/clinker/all?page=1'
    q = requests.get(url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    try:
        url_pages_count = str(soup.find('li', class_='pager-last last').find('a').get('href'))
        pages_count = int(url_pages_count[url_pages_count.find('=') + 1:len(url_pages_count)])
    except:
        pages_count = 1
    for i in range(0, pages_count + 1):
        url = f'https://keramin.by/produkciya/clinker/all?page={i}'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('div', class_='views-field views-field-title')
        for page in pages:
            page_url = str("https://keramin.by" + page.find('span', class_='field-content').find('a').get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')

    with open(f'url_list_{cur_data_file}_keramin.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


def get_data():
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(f'url_list_{cur_data_file}_keramin.txt') as file:
        lines = [line.strip() for line in file.readlines()]
        for line in lines:
            try:
                q = requests.get(line)
                result = q.content
                soup = BeautifulSoup(result, 'lxml')
                cur_data = datetime.now().strftime("%d.%m.%Y")
                cur_time = datetime.now().strftime("%H:%M")

                try:
                    name = soup.find("h1", class_='entry-title').text.strip()
                except:
                    name = None

                try:
                    new_price = soup.find("div", class_='price sale-price').text.strip()
                    new_price = new_price[:new_price.find(' ')]
                except:
                    new_price = None

                try:
                    stocs = soup.find("a",
                                      class_="btn black-button ctools-use-modal ctools-modal-modal-popup-large ctools-use-modal-processed").text.strip()
                except:
                    stocs = 'В наличии'

                try:
                    old_price = soup.find("div", class_="old-price").text.strip()
                    old_price = old_price[:old_price.find(' ')]

                except:
                    old_price = new_price

                try:
                    price_units = soup.find("div", class_='price sale-price').text.strip()
                    price_units = price_units[price_units.find(' ')::]
                except:
                    price_units = None

                left_spec = []
                right_spec = []
                specs = soup.find('li',
                                  class_='views-row views-row-1 views-row-odd views-row-first views-row-last').find_all(
                    'span', class_="views-label-wrapper")
                for spec in specs:
                    spec = ' '.join(spec.text.strip().split())
                    left_spec.append(spec)

                rspecs = soup.find('li',
                                   class_='views-row views-row-1 views-row-odd views-row-first views-row-last').find_all(
                    class_='field-content')
                for rspec in rspecs:
                    rspec = ' '.join(rspec.text.strip().split())

                    right_spec.append(rspec)
                specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}

                data = {
                    "Полное наименование": name,
                    "Действующая цена": new_price,
                    "Цена без скидки": old_price,
                    "Единица измерения цены": price_units,
                    'Наличие': stocs,
                    "Ссылка": line,
                    "Дата мониторинга": cur_data,
                    "Время мониторинга": cur_time,
                    "Магазин": "Keramin",
                }

                data_dict.append(data | specs_dict)
                print(f'Обработано карточек: {n}')
            except:
                break_line_count += 1
                break_line.append(line)
                print(f'Карточка пропущена. Обработано карточек: {n}')
            n += 1

        print(f'Сломанных ссылок: {break_line_count}')
        with open(f"data_{cur_data_file}_keramin.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(f'url_break_list_{cur_data_file}_keramin.txt', 'a') as file:
            for line in break_line:
                file.write(f'{line}\n')


def main():
    get_url_tile()
    get_data()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное {round(finish_time)} секунд на работу скрипта")
