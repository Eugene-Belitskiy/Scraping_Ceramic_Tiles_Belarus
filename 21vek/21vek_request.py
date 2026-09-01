import random
import requests
from bs4 import BeautifulSoup
import json
from collections import Counter
from datetime import datetime
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).parent
start_time = time.time()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}
cur_data_file = datetime.now().strftime("%m.%Y")

# Параллелизм убран совсем: даже на 2 потоках 21vek.by не отпускал rate-limit по
# 3 раунда повтора подряд, а без конкурентности код и так работает быстро (счёт
# на минуты, не часы) — не стоит того риска. Ретраи внутри одной карточки и целыми
# раундами (ниже) остаются на случай отдельных сетевых сбоев.
MAX_WORKERS = 1
MAX_RETRIES = 8
RETRY_ROUNDS = 3
ROUND_PAUSE = 45


def make_session():
    session = requests.Session()
    session.headers.update(headers)
    adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def get_with_retry(session, url, timeout=30, max_retries=MAX_RETRIES):
    """GET с ретраями при rate-limit (429), 5xx и обрывах соединения."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            r = session.get(url, timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exc = e
            delay = min(2 ** attempt, 40) + random.uniform(0, 1)
            print(f'[retry {attempt + 1}/{max_retries}] {type(e).__name__} на {url}, жду {delay:.0f}с')
            time.sleep(delay)
            continue

        if r.status_code == 429 or r.status_code >= 500:
            # Retry-After от сервера уважаем, но не безгранично: сайт может
            # прислать что-то вроде "3600" (час) и 8 попыток растянутся на
            # полдня. delta-seconds по HTTP-спеке, но иногда это ещё и
            # HTTP-дата — на нечисловое значение просто откатываемся к бэкоффу.
            retry_after = r.headers.get('Retry-After')
            try:
                delay = min(float(retry_after), 60) if retry_after else min(2 ** attempt, 40)
            except ValueError:
                delay = min(2 ** attempt, 40)
            delay += random.uniform(0, 1)
            print(f'[retry {attempt + 1}/{max_retries}] HTTP {r.status_code} на {url}, жду {delay:.0f}с')
            time.sleep(delay)
            continue

        r.raise_for_status()
        return r

    if last_exc:
        raise last_exc
    raise RuntimeError(f'Не удалось получить {url}: rate-limit не снялся за {max_retries} попыток')


def get_url_tile():
    session = make_session()
    url = f'https://www.21vek.by/tile/'
    q = get_with_retry(session, url)
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
        q = get_with_retry(session, url)
        result = q.content
        soup = BeautifulSoup(result, 'lxml')
        # print(soup)
        pages = soup.find_all('div', class_='ProductCard_product__jsAgo')
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
                price_base = page.find('div', {'data-testid': 'card-status'}).text.strip()

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
        time.sleep(REQUEST_DELAY)

    with open(BASE_DIR / f'url_list_{cur_data_file}_21_vek_Tile.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')
    with open(BASE_DIR / f"data_{cur_data_file}_21_vek_Tile_BASE.json", 'w', encoding="utf-8") as json_file:
        json.dump(UNP_list, json_file, indent=4, ensure_ascii=False)


REQUEST_DELAY = 1.0     # пауза между карточками (секунды) - снижает риск rate-limit
CARD_RETRY_ATTEMPTS = 3  # попыток на одну карточку прямо на месте, прежде чем сдаться
CARD_RETRY_PAUSE = 3.0   # пауза между этими попытками (секунды)


def fetch_card(session, line):
    """Обёртка над _fetch_card: несколько попыток на одной карточке с паузой
    между ними (закрывает случаи мимо get_with_retry - например, парсинг не
    нашёл нужные блоки на 200-ответе), затем пауза перед следующей карточкой
    независимо от итогового результата."""
    try:
        result = None
        for attempt in range(1, CARD_RETRY_ATTEMPTS + 1):
            result = _fetch_card(session, line)
            if result[0]:  # success
                return result
            if attempt < CARD_RETRY_ATTEMPTS:
                time.sleep(CARD_RETRY_PAUSE)
        return result
    finally:
        time.sleep(REQUEST_DELAY)


def _fetch_card(session, line):
    """Забирает и парсит одну карточку товара. Возвращает (True, data, None) либо (False, line, reason)."""
    try:
        q = get_with_retry(session, line)
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else '?'
        return False, line, f'HTTP {status} (запрос)'
    except Exception as e:
        return False, line, f'{type(e).__name__} (запрос)'

    try:
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

        return True, data | specs_dict, None
    except Exception as e:
        return False, line, f'{type(e).__name__} (парсинг, status={q.status_code})'


def get_data():
    result_path = BASE_DIR / f"data_{cur_data_file}_21_vek_Tile.json"
    if result_path.exists():
        with open(result_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
        already_done = {r['Ссылка'] for r in data_dict}
    else:
        data_dict = []
        already_done = set()
    with open(BASE_DIR / f'url_list_{cur_data_file}_21_vek_Tile.txt') as file:
        lines = list(dict.fromkeys(line.strip() for line in file if line.strip()))

    to_fetch = [line for line in lines if line not in already_done]
    n = len(lines) - len(to_fetch)

    reasons = {}

    session = make_session()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_card, session, line) for line in to_fetch]
        for future in as_completed(futures):
            n += 1
            success, result, reason = future.result()
            if success:
                data_dict.append(result)
                print(f'Обработано карточек: {n}')
            else:
                reasons[result] = reason
                print(f'Карточка пропущена ({reason}). Обработано карточек: {n}')

    break_line = [line for line in to_fetch if line not in {r['Ссылка'] for r in data_dict}]

    # get_with_retry() уже пытается пережить кратковременный rate-limit внутри одной
    # карточки, но если сайт держит 429 дольше, чем хватает её ретраев, карточка
    # попадает в break_line. Даём ей ещё несколько отдельных раундов - с паузой между
    # ними, чтобы застать момент, когда лимит на сайте отпустит - прежде чем сдаться.
    for round_num in range(1, RETRY_ROUNDS + 1):
        if not break_line:
            break
        print(f'[Раунд повтора {round_num}/{RETRY_ROUNDS}] Пауза {ROUND_PAUSE}с, затем повтор {len(break_line)} сломанных ссылок...')
        time.sleep(ROUND_PAUSE)
        still_broken = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_card, session, line): line for line in break_line}
            for future in as_completed(futures):
                success, result, reason = future.result()
                if success:
                    data_dict.append(result)
                    reasons.pop(result['Ссылка'], None)
                    print(f'[Раунд повтора {round_num}] Восстановлено: {result["Ссылка"]}')
                else:
                    reasons[result] = reason
                    still_broken.append(result)
        break_line = still_broken

    reason_counts = Counter(reasons.values())
    print(f'Сломанных ссылок: {len(break_line)} | Причины: {dict(reason_counts)}')
    with open(BASE_DIR / f"data_{cur_data_file}_21_vek_Tile.json", 'w', encoding="utf-8") as json_file:
        json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

    with open(BASE_DIR / f'urls_break_{cur_data_file}_21_vek-WC.txt', 'a') as file:
        for line in break_line:
            file.write(f'{line}\n')


def get_new_data():
    data_dict = []
    n = 1
    break_line = []
    break_line_count = 0
    with open(BASE_DIR / f'new_url_list_{cur_data_file}_21_vek_Tile.txt') as file:
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
        with open(BASE_DIR / f"new_data_{cur_data_file}_21_vek_Tile.json", 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

        with open(BASE_DIR / f'new_urls_break_{cur_data_file}_21_vek-WC.txt', 'a') as file:
            for line in break_line:
                file.write(f'{line}\n')


def new_url_list(prev_month):
    with open(BASE_DIR / f"data_{prev_month}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
        data_prev = json.load(f)
    with open(BASE_DIR / f"data_{cur_data_file}_21_vek_Tile_BASE.json", 'r', encoding='utf-8') as f:
        data_new = json.load(f)

    base_of_url = []
    new_url_list = []

    for i in range(len(data_prev)):
        base_of_url.append(data_prev[i]['Ссылка'])
    for i_ in data_new:
        if i_['Ссылка'] not in base_of_url:
            new_url_list.append(i_['Ссылка'])

    with open(BASE_DIR / f'new_url_list_{cur_data_file}_21_vek_Tile.txt', 'a') as file:
        for line in new_url_list:
            file.write(f'{line}\n')


def add_def(prev_month):
    try:
        with open(BASE_DIR / f"data_finally_{prev_month}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
            data_prev = json.load(f)
    except:
        with open(BASE_DIR / f"data_{prev_month}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
            data_prev = json.load(f)
    with open(BASE_DIR / f"data_{cur_data_file}_21_vek_Tile_BASE.json", 'r', encoding='utf-8') as f:
        data_new = json.load(f)
    for i in range(len(data_prev)):
        for i_ in data_new:
            if data_prev[i]['Ссылка'] == i_['Ссылка']:
                data_prev[i][f'Действующая цена_{cur_data_file}'] = i_[f'Действующая цена_{cur_data_file}']
                data_prev[i][f'Цена без скидки_{cur_data_file}'] = i_[f'Цена без скидки_{cur_data_file}']

                break
            else:
                continue

    with open(BASE_DIR / f"data_{cur_data_file}_21_vek_Tile.json", 'w', encoding="utf-8") as json_file:
        json.dump(data_prev, json_file, indent=4, ensure_ascii=False)


def get_finally_data():
    with open(BASE_DIR / f"data_{cur_data_file}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
        data_prev = json.load(f)
    with open(BASE_DIR / f"new_data_{cur_data_file}_21_vek_Tile.json", 'r', encoding='utf-8') as f:
        data_new = json.load(f)

    for i in data_new:
        data_prev.append(i)

    with open(BASE_DIR / f"data_finally_{cur_data_file}_21_vek_Tile_finally.json", 'w', encoding="utf-8") as json_file:
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
