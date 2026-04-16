import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException

start_time = time.time()
cur_data_file = datetime.now().strftime("%m.%Y")


def get_urls_tile():
    url = f'https://www.altagamma.by/catalog/plitka'
    q = requests.get(url)
    result = q.content
    soup = BeautifulSoup(result, 'lxml')
    pages_count = int(soup.find_all('a', class_='pag-link pag-link_num')[-1].text)
    url_list = []
    for i in range(1, pages_count + 1):
        url = f'https://www.altagamma.by/catalog/plitka/page-{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all(class_='grid-4__link')
        for page in pages:
            page_url = str("https://www.altagamma.by" + page.get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count} страниц')
    with open(f'url_list_{cur_data_file}_altagamma.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


def get_data():
    options = uc.ChromeOptions()
    driver_executable_path = "C:\\Users\\belit\\PycharmProjects\\undetected_chromedriver\\chromedriver.exe"
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.images": 2,
        "profile.managed_default_content_settings.media": 2
    }
    options.add_experimental_option("prefs", prefs)
    driver = uc.Chrome(driver_executable_path=driver_executable_path, options=options)

    try:
        data_dict = []
        n = 1
        break_line = []
        break_line_count = 0
        with open(f'url_list_{cur_data_file}_altagamma.txt') as file:
            lines = [line.strip() for line in file.readlines()]

            for line in lines:

                try:
                    driver.get(url=line)
                    content = driver.page_source
                    soup = BeautifulSoup(content, 'lxml')
                    cur_data = datetime.now().strftime("%d.%m.%Y")
                    cur_time = datetime.now().strftime("%H:%M")

                    try:
                        name = soup.find("h1", class_="pb__right__title").text.strip()
                    except:
                        name = "None"

                    try:
                        collection = soup.find("a", class_="collection-link").text.strip()
                    except:
                        collection = "None"

                    try:
                        new_price = soup.find("div", class_="rf-bold").text.strip()
                    except:
                        new_price = "None"

                    try:
                        old_price = soup.find('div', class_ = 'pb__price pb__price_big').find("div", class_="old-price").text.strip()
                    except:
                        old_price = new_price

                    try:
                        price_units = soup.find("div", class_="measure").text.strip().replace(' ', '')
                    except:
                        price_units = "None"

                    try:
                        stocs = " ".join(soup.find("p", class_="status").text.strip().split())
                    except:
                        stocs = "None"

                    left_spec = []
                    right_spec = []

                    specs = soup.find_all('li', class_="pb__list__item new-ico-wrap")
                    for spec in specs:
                        spec = " ".join(spec.find("div", class_='pb__list__title').text.strip().split())
                        left_spec.append(spec)

                    rspecs = soup.find_all('li', class_="pb__list__item new-ico-wrap")
                    for rspec in rspecs:
                        rspec = " ".join(rspec.find("div", class_='pb__list__desc').text.strip().split())
                        right_spec.append(rspec)

                    specs_dict = {left_spec[i].strip(): right_spec[i].strip() for i in range(len(left_spec))}
                    data = {
                        "Полное наименование": name,
                        "Коллекция": collection,
                        "Действующая цена": new_price,
                        "Цена без скидки": old_price,
                        "Единица измерения цены": price_units,
                        "Ссылка": line,
                        "Дата мониторинга": cur_data,
                        "Время мониторинга": cur_time,
                        "Магазин": "Altagamma",
                        "В наличии": stocs
                    }

                    data_dict.append(data | specs_dict)
                    print(f'Обработано карточек: {n}')
                except:
                    break_line_count += 1
                    break_line.append(line)
                    print(f'Карточка пропущена. Обработано карточек: {n}')
                n += 1

            print(f'Сломанных ссылок: {break_line_count}')

        with open(f"data_{cur_data_file}_altagamma.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        if break_line_count != 0:
            with open(f"urls_break_{cur_data_file}_altagamma.json", 'w', encoding="utf-8") as json_file:
                json.dump(break_line, json_file, indent=4, ensure_ascii=False)

    except Exception as ex:
        print(ex)

    finally:
        driver.close()
        driver.quit()


def main():
    get_urls_tile()
    get_data()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное на работу скрипта время: {finish_time}")
