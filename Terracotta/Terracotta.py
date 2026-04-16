import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import csv
import time

start_time = time.time()
cur_data_file = datetime.now().strftime("%m.%Y")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}


def get_url_tile():
    url = 'https://terracotta.by/catalog/plitka/'
    q = requests.get(url=url, headers=headers)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    pages_counts = int(soup.find('div', class_='nums').find_all('a', class_='dark_link')[-1].text)
    url_list = []
    for i in range(1, pages_counts + 1):
        url = f'https://terracotta.by/catalog/plitka/?PAGEN_1={i}'
        q = requests.get(url=url, headers=headers)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('a', class_='dark_link js-notice-block__title option-font-bold font_sm')
        for page in pages:
            page_url = str("https://terracotta.by" + page.get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_counts} страниц')
    with open(f'url_list_{cur_data_file}_terracotta.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


def get_data():
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(f'url_list_{cur_data_file}_terracotta.txt') as file:
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
                    name = "None"

                try:
                    price_units = soup.find('div', class_='price font-bold font_mxs').find("span",
                                                                                           class_="price_measure").text.strip()
                except:
                    price_units = 'Error'

                try:
                    new_price = soup.find("div", class_='price_value_block values_wrapper').find('span',
                                                                                                 class_='price_value').text.replace(
                        f'{price_units}', '').strip()
                except:
                    new_price = 'Error'

                try:
                    old_price = soup.find("span", class_='discount values_wrapper font_xs muted').find('span',
                                                                                                       class_='price_value').text.replace(
                        f'{price_units}', '').strip()
                except:
                    old_price = 'Error'

                try:
                    stocs = " ".join(soup.find("span", class_="store_view dotted").text.strip().split())
                except:
                    stocs = "Error"

                left_spec = []
                right_spec = []
                specs = soup.find_all('div', class_="props_item")
                for spec in specs:
                    spec = " ".join(spec.find('span').text.strip().split())
                    left_spec.append(spec)
                rspecs = soup.find_all('td', class_="char_value")
                for rspec in rspecs:
                    rspec = " ".join(rspec.find('span').text.strip().split())
                    right_spec.append(rspec)
                specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}
                data = {
                    "Полное наименование": name,
                    "Действующая цена": new_price,
                    "Цена без скидки": old_price,
                    "Единица измерения цены": price_units,
                    "В наличии": stocs,
                    "Ссылка": line,
                    "Дата мониторинга": cur_data,
                    "Время мониторинга": cur_time,
                    "Магазин": "Terracotta",
                }
                data_dict.append(data | specs_dict)
                print(f'Обработано карточек: {n}')
            except:
                break_line_count += 1
                break_line.append(line)
                print(f'Карточка пропущена. Обработано карточек: {n}')
            n += 1
        print(f'Сломанных ссылок: {break_line_count}')
        with open(f"data_{cur_data_file}_terracotta.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(f'url_break_list_{cur_data_file}_terracotta.txt', 'a') as file:
            for line in break_line:
                file.write(f'{line}\n')


def main():
    get_url_tile()
    get_data()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное {round(finish_time)} секунд на работу скрипта")
