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

cur_data_file = datetime.now().strftime("%m.%Y")

# 21vek.by (тот же паттерн скрапинга) начинает отвечать 429 уже при умеренном
# параллелизме — держим параллелизм умеренным и полагаемся на retry с backoff
# как на основную защиту от rate-limit. У Modus на MAX_WORKERS=5 пока проблем
# не наблюдалось, но раунды повтора ниже подстрахуют и его на будущее.
MAX_WORKERS = 5
MAX_RETRIES = 8
RETRY_ROUNDS = 3
ROUND_PAUSE = 45


def make_session():
    session = requests.Session()
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
            time.sleep(min(2 ** attempt, 40) + random.uniform(0, 1))
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
            time.sleep(delay + random.uniform(0, 1))
            continue

        r.raise_for_status()
        return r

    if last_exc:
        raise last_exc
    raise RuntimeError(f'Не удалось получить {url}: rate-limit не снялся за {max_retries} попыток')


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
    with open(BASE_DIR / f'url_{cur_data_file}_Modus.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


CARD_RETRY_ATTEMPTS = 3  # попыток на одну карточку прямо на месте, прежде чем сдаться
CARD_RETRY_PAUSE = 3.0   # пауза между этими попытками (секунды)


def fetch_card(session, line):
    """Обёртка над _fetch_card: несколько попыток на одной карточке с паузой
    между ними (закрывает случаи мимо get_with_retry - например, парсинг не
    нашёл нужные блоки на 200-ответе)."""
    result = None
    for attempt in range(1, CARD_RETRY_ATTEMPTS + 1):
        result = _fetch_card(session, line)
        if result[0]:  # success
            return result
        if attempt < CARD_RETRY_ATTEMPTS:
            time.sleep(CARD_RETRY_PAUSE)
    return result


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
            name = "None"

        try:
            stocks = soup.find("div", class_='availability').text.strip()
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

        return True, data | specs_dict, None
    except Exception as e:
        return False, line, f'{type(e).__name__} (парсинг, status={q.status_code})'


def get_data():
    result_path = BASE_DIR / f"data_{cur_data_file}_Modus.json"
    if result_path.exists():
        with open(result_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
        already_done = {r['Ссылка'] for r in data_dict}
    else:
        data_dict = []
        already_done = set()
    with open(BASE_DIR / f'url_{cur_data_file}_Modus.txt') as file:
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
    with open(BASE_DIR / f"data_{cur_data_file}_Modus.json", 'w', encoding="utf-8") as json_file:
        json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

    with open(BASE_DIR / f"urls_break_{cur_data_file}_Modus.json", 'w', encoding="utf-8") as json_file:
        json.dump(break_line, json_file, indent=4, ensure_ascii=False)


def main():
    get_url_tile()
    get_data()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное на работу скрипта время: {finish_time}")
