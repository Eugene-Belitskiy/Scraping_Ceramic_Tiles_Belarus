import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time

start_time = time.time()
cur_data_file = datetime.now().strftime("%m.%Y")


def get_url_tile():
    url = f'https://mile.by/catalog/gres/'
    q = requests.get(url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    pages_count = int(soup.find('a', class_='pagin-number poi1').text)
    url_list = []
    for i in range(1, pages_count + 1):
        url = f'https://mile.by/catalog/gres/page-{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('div', class_='anons-wrap item-')
        for page in pages:
            page_url = str("https://mile.by" + page.find('div', class_='anons-name').find('a').get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')

    url = f'https://mile.by/catalog/napolnaya-plitka_/'
    q = requests.get(url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    pages_count = int(soup.find('div', class_='pagination-wrap').find_all('a')[-2].text)
    for i in range(1, pages_count + 1):
        url = f'https://mile.by/catalog/napolnaya-plitka_/page-{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('div', class_='anons-wrap item-')
        for page in pages:
            page_url = str("https://mile.by" + page.find('div', class_='anons-name').find('a').get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')

    url = f'https://mile.by/catalog/plitka-dlya-vannoy/'
    q = requests.get(url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    pages_count = int(soup.find('div', class_='pagination-wrap').find_all('a')[-2].text)
    for i in range(1, pages_count + 1):
        url = f'https://mile.by/catalog/plitka-dlya-vannoy/page-{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('div', class_='anons-wrap item-')
        for page in pages:
            page_url = str("https://mile.by" + page.find('div', class_='anons-name').find('a').get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')

    url = f'https://mile.by/catalog/plitka-dlya-kukhni/'
    q = requests.get(url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    pages_count = int(soup.find('div', class_='pagination-wrap').find_all('a')[-2].text)
    for i in range(1, pages_count + 1):
        url = f'https://mile.by/catalog/plitka-dlya-kukhni/page-{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('div', class_='anons-wrap item-')
        for page in pages:
            page_url = str("https://mile.by" + page.find('div', class_='anons-name').find('a').get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')

    with open(f'url_list_{cur_data_file}_mile.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


def get_data():
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(f'url_list_{cur_data_file}_mile.txt') as file:
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
                    name = "Null"

                try:
                    new_price = soup.find("span", {"itemprop": "price"}).text.strip()
                except:
                    new_price = "Null"

                try:
                    old_price = soup.find("div", class_="card-price-old").find('span', class_='tahoma').text.strip()
                except:
                    old_price = new_price

                try:
                    price_units = soup.find("div", class_="card-price").text.strip().replace(' ', '').replace(
                        f'{new_price}', '')
                except:
                    price_units = "Null"

                left_spec = []
                right_spec = []
                specs = soup.find_all('div', class_="characteristic-name")
                for spec in specs:
                    spec = " ".join(spec.text.strip().split())
                    left_spec.append(spec)

                rspecs = soup.find_all('div', class_="characteristic-value")
                for rspec in rspecs:
                    rspec = " ".join(rspec.find("span").text.strip().split())
                    right_spec.append(rspec)
                specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}
                data = {
                    "Полное наименование": name,
                    "Действующая цена": new_price,
                    "Цена без скидки": old_price,
                    "Единица измерения цены": price_units,
                    "Ссылка": line,
                    "Дата мониторинга": cur_data,
                    "Время мониторинга": cur_time,
                    "Магазин": "Mile",
                }

                data_dict.append(data | specs_dict)
                print(f'Обработано карточек: {n}')
            except:
                break_line_count += 1
                break_line.append(line)
                print(f'Карточка пропущена. Обработано карточек: {n}')
            n += 1
        print(f'Сломанных ссылок: {break_line_count}')
        with open(f"data_{cur_data_file}_mile.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(f"urls_break_{cur_data_file}_mile.json", 'w', encoding="utf-8") as json_file:
            json.dump(break_line, json_file, indent=4, ensure_ascii=False)


def main():
    get_url_tile()
    get_data()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное {round(finish_time)} секунд на работу скрипта")
