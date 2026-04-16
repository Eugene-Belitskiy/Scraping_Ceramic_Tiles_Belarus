import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time

start_time = time.time()

cur_data_file = datetime.now().strftime("%m.%Y")


def get_url_tile():
    url = 'https://keramika.by/catalog/plitka/keramicheskaya-plitka-keramogranit/?set_filter=y&PAGEN_1=5'

    q = requests.get(url=url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    # print(soup)
    pages_count = int(soup.find_all('a', class_='pagination')[-1].text)
    print(pages_count)

    url_list = []
    for i in range(1, pages_count + 1):
        url = f'https://keramika.by/catalog/plitka/keramicheskaya-plitka-keramogranit/?PAGEN_1={i}'
        q = requests.get(url=url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('div', class_='top-block')
        for page in pages:
            page_url = str("https://keramika.by" + page.find('a').get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')
    url_list = list(set(url_list))
    with open(f'url_{cur_data_file}_Modus.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


def get_data():
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(f'url_{cur_data_file}_Modus.txt') as file:

        lines = [line.strip() for line in file.readlines()]

        for line in lines:

            try:
                q = requests.get(url=line)
                result = q.content
                soup = BeautifulSoup(result, 'lxml')
                cur_data = datetime.now().strftime("%d.%m.%Y")
                cur_time = datetime.now().strftime("%H:%M")

                try:
                    name = soup.find("h1").text.strip()
                except:
                    name = "None"

                try:
                    stocks = soup.find("div", class_ = 'availability').text.strip()
                except:
                    stocks = None

                try:
                    new_price = soup.find("div", class_='price-block').find('div',
                                                                            class_='price').text.strip()  # .replace(f'{price_units}','').
                except:
                    new_price = 'Error'

                try:
                    price_sale = soup.find('div', class_='price-sale').text
                except:
                    price_sale = 'Error'

                try:
                    price_units = soup.find("div", class_='price-block').find('div', class_='price').find(
                        'span').text.strip()
                except:
                    price_units = 'Error'

                left_spec = []
                right_spec = []

                specs = soup.find_all('p', class_="characteristic-name")
                for spec in specs:
                    spec = spec.text.strip()
                    left_spec.append(spec)

                rspecs = soup.find_all('p', class_="characteristic-value")
                for rspec in rspecs:
                    rspec = rspec.text.strip()
                    right_spec.append(rspec)
                specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}

                data = {
                    "Полное наименование": name,
                    "Действующая цена": new_price,
                    "Размер скидки": price_sale,
                    "Единица измерения цены": price_units,
                    "В наличии": stocks,
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
        with open(f"data_{cur_data_file}_Modus.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(f"urls_break_{cur_data_file}_Modus.json", 'w', encoding="utf-8") as json_file:
            json.dump(break_line, json_file, indent=4, ensure_ascii=False)


def main():
    get_url_tile()
    get_data()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное на работу скрипта время: {finish_time}")
