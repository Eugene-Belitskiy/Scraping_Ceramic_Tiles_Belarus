import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

start_time = time.time()
cur_data_file = datetime.now().strftime("%m.%Y")


def get_url_tile():
    url_list = []
    pages_count_keramogranit = int(
        input('Введите количество страниц группы "Керамогранит" на сайте https://diy.by/keramogranit - '))
    pages_count_bathroom = int(
        input('Введите количество страниц группы "Плитка для ванной" на сайте https://diy.by/plitka-dlya-vannoy - '))
    pages_count_kitchen = int(
        input('Введите количество страниц группы "Плитка для кухни" на сайте https://diy.by/plitka-dlya-kukhni/ - '))
    pages_count_porch = int(input(
        'Введите количество страниц группы "Клинкер для крыльца" на сайте https://diy.by/klinker-dlya-kryltsa/ - '))
    pages_count_clinker = int(
        input('Введите количество страниц группы "Клинкер для фасада" на сайте https://diy.by/klinker-dlya-fasada/ - '))

    for i in range(1, pages_count_keramogranit + 1):
        if i == 1:
            url = f'https://diy.by/keramogranit/'
        else:
            url = f'https://diy.by/keramogranit/page{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('a', class_='product-card__title fz_regular')
        for page in pages:
            page_url = str("https://diy.by" + page.get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count_keramogranit} страниц группы "Керамогранит"')

    for i in range(1, pages_count_bathroom + 1):
        if i == 1:
            url = f'https://diy.by/plitka-dlya-vannoy'
        else:
            url = f'https://diy.by/plitka-dlya-vannoy/page{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('a', class_='product-card__title fz_regular')
        for page in pages:
            page_url = str("https://diy.by" + page.get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count_bathroom} страниц группы "Плитки для ванной комнаты"')

    for i in range(1, pages_count_kitchen + 1):
        if i == 1:
            url = f'https://diy.by/plitka-dlya-kukhni/'
        else:
            url = f'https://diy.by/plitka-dlya-kukhni/page{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('a', class_='product-card__title fz_regular')
        for page in pages:
            page_url = str("https://diy.by" + page.get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count_kitchen} страниц группы "Плитка для кухни"')

    for i in range(1, pages_count_porch + 1):
        if i == 1:
            url = f'https://diy.by/klinker-dlya-kryltsa'
        else:
            url = f'https://diy.by/klinker-dlya-kryltsa/page{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('a', class_='product-card__title fz_regular')
        for page in pages:
            page_url = str("https://diy.by" + page.get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count_porch} страниц группы "Клинкер для крыльца"')

    for i in range(1, pages_count_clinker + 1):
        if i == 1:
            url = f'https://diy.by/klinker-dlya-fasada/'
        else:
            url = f'https://diy.by/klinker-dlya-fasada/page{i}/'
        q = requests.get(url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        pages = soup.find_all('a', class_='product-card__title fz_regular')
        for page in pages:
            page_url = str("https://diy.by" + page.get('href'))
            url_list.append(page_url)
        print(f'Обработал {i} из {pages_count_clinker} страниц группы "Клинкер для фасада"')

    with open(f'url_list_{cur_data_file}_materik.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


def get_data():
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(f'url_list_{cur_data_file}_materik.txt') as file:
        lines = [line.strip() for line in file.readlines()]
        for line in lines:
            try:
                q = requests.post(url=line)
                result = q.content
                soup = BeautifulSoup(result, 'lxml')
                cur_data = datetime.now().strftime("%d.%m.%Y")
                cur_time = datetime.now().strftime("%H:%M")

                try:
                    name = soup.find("h1").text.strip()
                except:
                    name = "Null"


                try:
                    new_price = soup.find('div',
                                          _class='product-price__price-current product-price__price--discount fz_heading_4').text.strip()
                except:
                    try:
                        new_price = soup.find("div",
                                              _class='product-price__price-current fz_heading_4').text.strip()
                    except:
                        new_price = "Null"

                try:
                    old_price = soup.find("div", class_="product-price__price-old").text.strip()
                except:
                    old_price = new_price

                try:
                    price_units = soup.find("div", class_="product-total__switch active").text.strip()
                except:
                    price_units = "Null"

                left_spec = []
                right_spec = []
                specs = soup.find_all('div', class_="product-features__prop")
                for spec in specs:
                    spec = " ".join(spec.find("span").text.strip().split())
                    left_spec.append(spec)

                rspecs = soup.find_all('div', class_="product-features__val")
                for rspec in rspecs:
                    rspec = " ".join(rspec.text.strip().split())
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
                    "Магазин": "Materik",
                }

                data_dict.append(data | specs_dict)
                print(f'Обработано карточек: {n}')
            except:
                break_line_count += 1
                break_line.append(line)
                print(f'Карточка пропущена. Обработано карточек: {n}')
            n += 1
        print(f'Сломанных ссылок: {break_line_count}')

        with open(f"data_{cur_data_file}_materik.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        if break_line_count != 0:
            with open(f"urls_break_{cur_data_file}_materik.json", 'w', encoding="utf-8") as json_file:
                json.dump(break_line, json_file, indent=4, ensure_ascii=False)


def get_data_with_selenium():
    service = Service(
        executable_path="C:\\Users\\belit\\PycharmProjects\\undetected_chromedriver\\chromedriver.exe")

    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)

    try:
        data_dict = []
        n = 1
        break_line = []
        break_line_count = 0
        with open(f'url_list_{cur_data_file}_materik.txt') as file:
            lines = [line.strip() for line in file.readlines()]
            for line in lines:
                try:
                    driver.get(url=line)
                    content = driver.page_source
                    soup = BeautifulSoup(content, 'lxml')
                    cur_data = datetime.now().strftime("%d.%m.%Y")
                    cur_time = datetime.now().strftime("%H:%M")

                    try:
                        name = soup.find("h1").text.strip()
                    except:
                        name = "Null"

                    try:
                        new_price = driver.find_element(By.XPATH,
                                                        "//div[@class='product-price__price-current product-price__price--discount fz_heading_4']").text.strip()
                    except:
                        try:
                            new_price = driver.find_element(By.XPATH,
                                                            "//div[@class='product-price__price-current fz_heading_4']").text.strip()
                        except:
                            new_price = "Null"
                    new_price = new_price.replace('\n', '.')


                    try:
                        old_price = driver.find_element(By.XPATH,
                                                        "//div[@class='product-price__price-old']").text.strip()
                    except:
                        old_price = new_price

                    try:
                        new_price, old_price = float(new_price), float(old_price)
                    except:
                        print('Нет')

                    try:
                        price_units = soup.find("div", class_="product-total__switch active").text.strip()
                    except:
                        price_units = "Null"

                    left_spec = []
                    right_spec = []
                    specs = soup.find_all('div', class_="product-features__prop")
                    for spec in specs:
                        spec = " ".join(spec.find("span").text.strip().split())
                        left_spec.append(spec)

                    rspecs = soup.find_all('div', class_="product-features__row")
                    for rspec in rspecs:
                        if " ".join(rspec.find('div', class_="product-features__val").text.strip().split()) != '':
                            rspec = " ".join(rspec.find('div', class_="product-features__val").text.strip().split())
                        else:
                            try:
                                if '#i-cross' in rspec.find('use').get('xlink:href'):
                                    rspec = 'Да'
                                elif '#i-mark' in rspec.find('use').get('xlink:href'):
                                    rspec = 'Нет'
                            except:
                                rspec = 'НА САЙТЕ УКАЗАН СИМВОЛ'
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
                        "Магазин": "Materik",
                    }

                    data_dict.append(data | specs_dict)
                    print(f'Обработано карточек: {n}')
                except:
                    break_line_count += 1
                    break_line.append(line)
                    print(f'Карточка пропущена. Обработано карточек: {n}')
                n += 1
            print(f'Сломанных ссылок: {break_line_count}')

            with open(f"data_{cur_data_file}_materik.json", 'w', encoding="utf-8") as json_file:
                json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

            if break_line_count != 0:
                with open(f"urls_break_{cur_data_file}_materik.json", 'w', encoding="utf-8") as json_file:
                    json.dump(break_line, json_file, indent=4, ensure_ascii=False)

    except Exception as ex:
        print(ex)

    finally:
        driver.close()
        driver.quit()


def main():
    get_url_tile()
    get_data()
    get_data_with_selenium()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное {round(finish_time)} секунд на работу скрипта")
