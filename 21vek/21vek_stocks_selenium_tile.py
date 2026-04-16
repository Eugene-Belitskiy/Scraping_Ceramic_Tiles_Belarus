import json
import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
)

start_time = time.time()

cur_data_file = datetime.now().strftime("%d.%m.%Y")

options = uc.ChromeOptions()
driver_executable_path = "C:\\Users\\belit\\PycharmProjects\\undetected_chromedriver\\chromedriver.exe"
prefs = {
    "profile.managed_default_content_settings.images": 2,
    "profile.default_content_setting_values.images": 2,
    "profile.managed_default_content_settings.media": 2
}
options.add_experimental_option("prefs", prefs)
driver = uc.Chrome(driver_executable_path=driver_executable_path, options=options)
time.sleep(5)


def end_driver():
    driver.close()
    driver.quit()


def get_cart_buttons():
    """Находит кнопки 'В корзину' внутри product-list, исключая product-block."""
    all_buttons = driver.find_elements(
        By.CSS_SELECTOR,
        "div[data-testid='product-list'] button[data-testid='card-basket-action']"
    )
    exclude_buttons = driver.find_elements(
        By.CSS_SELECTOR,
        "div[data-testid='product-block'] button[data-testid='card-basket-action']"
    )
    exclude_ids = {b.id for b in exclude_buttons}
    return [b for b in all_buttons if b.id not in exclude_ids]


def click_button_safe(button, index, max_retries=3):
    """Скроллит к кнопке, кликает через JS, проверяет изменение текста."""
    for attempt in range(max_retries):
        try:
            text_before = button.text.strip()

            # Скроллим кнопку в центр экрана
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
                button
            )
            time.sleep(0.3)

            # Кликаем через JavaScript - обходит проблемы с overlay
            driver.execute_script("arguments[0].click();", button)
            time.sleep(0.5)

            # Проверяем что текст изменился
            text_after = button.text.strip()
            if text_after != text_before:
                return True

            # Текст не изменился - пробуем обычный клик
            if attempt < max_retries - 1:
                time.sleep(0.5)
                button.click()
                time.sleep(0.5)
                text_after = button.text.strip()
                if text_after != text_before:
                    return True

        except StaleElementReferenceException:
            print(f"  [!] Кнопка {index} стала stale, пропускаю")
            return False
        except Exception as ex:
            if attempt == max_retries - 1:
                print(f"  [!] Кнопка {index} - ошибка: {ex}")
                return False
            time.sleep(0.5)

    return False


def add_all_to_cart():
    """Проходит по всем страницам каталога и добавляет товары в корзину."""
    groups = ["tile"]

    for group in groups:
        url = f'https://www.21vek.by/{group}/'
        driver.get(url=url)
        time.sleep(3)

        # Определяем количество страниц
        content = driver.page_source
        soup = BeautifulSoup(content, 'lxml')
        pages_count = int(
            soup.find_all('div', class_='Pagination-module__pageText')[-1].text
        )
        print(f"Каталог '{group}': {pages_count} страниц")

        total_clicked = 0
        total_failed = 0

        for page_num in range(1, pages_count + 1):
            url = f'https://www.21vek.by/{group}/page:{page_num}/'
            driver.get(url=url)
            time.sleep(2)

            # Ждем загрузки product-list
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[data-testid='product-list']")
                    )
                )
            except TimeoutException:
                print(f"[!] Страница {page_num}: product-list не загрузился, пропускаю")
                continue

            # Прокручиваем всю страницу вниз чтобы подгрузить lazy-элементы
            driver.execute_script(
                "window.scrollTo({top: document.body.scrollHeight, behavior: 'instant'});"
            )
            time.sleep(1)
            driver.execute_script("window.scrollTo({top: 0, behavior: 'instant'});")
            time.sleep(0.5)

            buttons = get_cart_buttons()
            page_total = len(buttons)
            page_clicked = 0
            page_failed = 0

            print(f"\n--- Страница {page_num}/{pages_count} --- Найдено кнопок: {page_total}")

            for i, btn in enumerate(buttons, 1):
                if click_button_safe(btn, i):
                    page_clicked += 1
                else:
                    page_failed += 1

                # Каждые 10 кнопок - промежуточный отчет
                if i % 10 == 0:
                    print(f"  Прогресс: {i}/{page_total} (OK: {page_clicked}, fail: {page_failed})")

            # --- Верификация перед переходом на следующую страницу ---
            # Повторно находим кнопки и проверяем, не остались ли некликнутые
            buttons_recheck = get_cart_buttons()
            not_clicked = []
            for j, btn in enumerate(buttons_recheck):
                try:
                    text = btn.text.strip()
                    # Если текст содержит типичные маркеры некликнутой кнопки
                    # (не изменился после клика), пробуем ещё раз
                    if btn in buttons and not any(
                        marker in text.lower() for marker in ['корзин', 'оформ', 'добавлен']
                    ):
                        not_clicked.append((j, btn))
                except StaleElementReferenceException:
                    pass

            if not_clicked:
                print(f"  [Повторная попытка] Осталось некликнутых: {len(not_clicked)}")
                for j, btn in not_clicked:
                    if click_button_safe(btn, j):
                        page_clicked += 1
                        page_failed -= 1

            total_clicked += page_clicked
            total_failed += page_failed
            print(
                f"  Итог страницы {page_num}: "
                f"OK={page_clicked}/{page_total}, fail={page_failed}"
            )

        print(f"\n=== ИТОГО каталог '{group}' ===")
        print(f"  Добавлено в корзину: {total_clicked}")
        print(f"  Не удалось: {total_failed}")


def get_pages():
    try:
        groups = [
            "tile",
        ]

        for group in groups:
            url = f'https://www.21vek.by/{group}/'
            driver.get(url=url)
            time.sleep(2)
            content = driver.page_source
            soup = BeautifulSoup(content, 'lxml')
            pages_count = int(
                soup.find_all('div', class_='Pagination-module__pageText')[-1].text)
            print(pages_count)
            url_list = []

            for i in range(1, pages_count + 1):
                print(f'Обрабатываю {i} страницу каталога {group}')
                url = f'https://www.21vek.by/{group}/page:{i}/'
                driver.get(url=url)
                content = driver.page_source
                soup = BeautifulSoup(content, 'lxml')
                pages = soup.find_all('div', class_='ListingProductV2_middlePanel__rvued')

                for page in pages:
                    url = page.get('href')

                url_list.append('https://21vek.by' + page.get('href'))

        url_list = list(set(url_list))

        with open(f'url_list_{cur_data_file}_Tiles_21vek.txt', 'a') as file:
            for line in url_list:
                file.write(f'{line}\n')

    except Exception as ex:
        print(f"Ошибка: {ex}")


def get_data():
    try:
        data_dict = []
        n = 1
        break_line = []
        break_line_count = 0
        with open(f'url_list_{cur_data_file}_Tiles_21vek.txt') as file:
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
                        f"Действующая цена": new_price,
                        f"Цена без скидки": old_price,
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

        with open(f"data_{cur_data_file}_Tiles_21vek.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        if break_line_count != 0:
            with open(f'url_break_list_{cur_data_file}_Tiles_21vek.txt', 'a') as file:
                for line in break_line:
                    file.write(f'{line}\n')


    except Exception as ex:
        with open(f"data_{cur_data_file}_Tiles_21vek_break.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        if break_line_count != 0:
            with open(f'url_break_list_{cur_data_file}_Tiles_21vek.txt', 'a') as file:
                for line in break_line:
                    file.write(f'{line}\n')
        print(ex)

    finally:

        if break_line_count != 0:
            with open(f'url_break_list_{cur_data_file}_Tiles_21vek.txt', 'a') as file:
                for line in break_line:
                    file.write(f'{line}\n')


def main():
    add_all_to_cart()
    # get_pages()
    # get_data()
    end_driver()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное на работу скрипта время: {finish_time}")
