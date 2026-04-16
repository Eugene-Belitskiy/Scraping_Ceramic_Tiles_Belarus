import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import asyncio
import aiohttp

start_time = time.time()

async def gather_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    pages_counts = 100
    cur_data_file = datetime.now().strftime("%d.%m.%Y")
    url_list = []


def get_url_collection():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    pages_counts = 100
    cur_data_file = datetime.now().strftime("%d.%m.%Y")
    url_list = []

        for i in range(1, pages_counts + 1):
            url = f'https://keramika.by/catalog/keramicheskaya-plitka-i-keramicheskij-granit?page={i}'
            q = requests.get(url=url, headers=headers)
            result = q.content
            soup = BeautifulSoup(result, 'lxml')
            pages = soup.find_all('a', style='text-decoration: none; color: #000;')
            for page in pages:
                page_url = str("https://keramika.by/" + page.get('href'))
                url_list.append(page_url)
            print(f'Обработал {i} из {pages_counts} страниц')
            url_list = list(set(url_list))
        with open(f'url_list_{cur_data_file}_Modus_Collections.txt', 'a') as file:
            for line in url_list:
                file.write(f'{line}\n')

        pages_counts = 10
        cur_data_file = datetime.now().strftime("%d.%m.%Y")
        url_list = []
        for i in range(1, pages_counts + 1):
            url = f'https://keramika.by/catalog/klinker?page={i}'
            q = requests.get(url=url, headers=headers)
            result = q.content
            soup = BeautifulSoup(result, 'lxml')
            pages = soup.find_all('a', style='text-decoration: none; color: #000;')
            for page in pages:
                page_url = str("https://keramika.by/" + page.get('href'))
                url_list.append(page_url)
            print(f'Обработал {i} из {pages_counts} страниц')
            url_list = list(set(url_list))
        with open(f'url_list_{cur_data_file}_Modus_Collections.txt', 'a') as file:
            for line in url_list:
                file.write(f'{line}\n')


def get_url_tile():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    ni = 1
    urls_all = []
    cur_data_file = datetime.now().strftime("%d.%m.%Y")
    with open(f'url_list_{cur_data_file}_Modus_Collections.txt') as file:
        lines = [line.strip() for line in file.readlines()]
        for line in lines:
            q = requests.get(url=line, headers=headers)
            result = q.content
            soup = BeautifulSoup(result, 'lxml')
            pages = soup.find_all('a', style='text-decoration: none; color: #000;')
            for page in pages:
                page_url_prod = str("https://keramika.by/" + page.get('href'))
                urls_all.append(page_url_prod)
            print(f'Обработал {ni} коллекций')
            ni += 1
        urls_all = list(set(urls_all))
        with open(f'url_{cur_data_file}_Modus_Product.txt', 'a') as file:
            for line in urls_all:
                file.write(f'{line}\n')


def get_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    cur_data_file = datetime.now().strftime("%d.%m.%Y")
    with open(f'url_{cur_data_file}_Modus_Product.txt') as file:

        lines = [line.strip() for line in file.readlines()]

        for line in lines:

            try:
                q = requests.get(url=line, headers=headers)
                result = q.content
                soup = BeautifulSoup(result, 'lxml')
                # print(soup)
                cur_data = datetime.now().strftime("%d.%m.%Y")
                cur_time = datetime.now().strftime("%H:%M")

                try:
                    name = soup.find("h1").text.strip()
                except:
                    name = "None"

                try:
                    new_price = soup.find("span", class_='price').text.strip()  # .replace(f'{price_units}','').
                except:
                    new_price = 'Error'

                try:
                    price_units = soup.find("div", class_="price-wrapper f24 bold orange").text.strip().replace(
                        f'{new_price}', '').strip()
                except:
                    price_units = 'Error'

                left_spec = []
                right_spec = []

                specs = soup.find_all('div', class_="black")
                # print(specs)
                for spec in specs:
                    spec = " ".join(spec.text.strip().split())
                    left_spec.append(spec)
                # print(left_spec)

                rspecs = soup.find_all('div', class_="text-right-xs text-left-md light")
                # print(rspecs)
                for rspec in rspecs:
                    rspec = " ".join(rspec.text.strip().split())
                    right_spec.append(rspec)
                # print(right_spec)
                specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}

                data = {
                    "Полное наименование": name,
                    "Действующая цена": new_price,
                    "Единица измерения цены": price_units,
                    "Ссылка": line,
                    "Дата мониторинга": cur_data,
                    "Время мониторинга": cur_time,
                    "Магазин": "Модус керамика",
                }

                data_dict.append(data | specs_dict)
                print(f'Обработано карточек: {n}')

            except:
                break_line_count += 1
                break_line.append(line)
                print(f'Карточка пропущена. Обработано карточек: {n}')
            n += 1

        print(f'Сломанных ссылок: {break_line_count}')
        with open(f"data_{cur_data}_Modus.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(f"urls_break_{cur_data}_Modus.json", 'w', encoding="utf-8") as json_file:
            json.dump(break_line, json_file, indent=4, ensure_ascii=False)
    pass


def main():
    get_url_collection()
    get_url_tile()
    get_data()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное на работу скрипта время: {finish_time}")
