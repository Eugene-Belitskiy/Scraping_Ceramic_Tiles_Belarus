import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import subprocess
from pathlib import Path
import os

BASE_DIR = Path(__file__).parent
import re
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException, ElementNotInteractableException,
    InvalidSessionIdException, NoSuchWindowException, TimeoutException,
)
from collections import Counter

start_time = time.time()
cur_data_file = datetime.now().strftime("%m.%Y")


def get_chrome_major_version():
    # CI (browser-actions/setup-chrome) сообщает точную установленную версию напрямую
    env_version = os.environ.get("CHROME_VERSION")
    if env_version:
        match = re.search(r'(\d+)', env_version)
        if match:
            return int(match.group(1))

    # Windows: версия из реестра
    registry_paths = [
        r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon',
        r'HKEY_LOCAL_MACHINE\SOFTWARE\Google\Chrome\BLBeacon',
    ]
    for path in registry_paths:
        try:
            result = subprocess.run(
                ['reg', 'query', path, '/v', 'version'],
                capture_output=True, text=True
            )
            match = re.search(r'(\d+)\.\d+\.\d+\.\d+', result.stdout)
            if match:
                return int(match.group(1))
        except Exception:
            continue

    # Linux/macOS: спросить бинарник напрямую
    for binary in ('google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium'):
        try:
            result = subprocess.run(
                [binary, '--version'],
                capture_output=True, text=True
            )
            match = re.search(r'(\d+)\.\d+\.\d+\.\d+', result.stdout)
            if match:
                return int(match.group(1))
        except Exception:
            continue

    return None


def make_options():
    options = uc.ChromeOptions()
    options.add_argument('--blink-settings=imagesEnabled=false')
    if os.environ.get("CI"):
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    return options


def create_driver():
    # В CI browser-actions/setup-chrome ставит Chrome и (install-chromedriver: true)
    # ChromeDriver ТОЙ ЖЕ сборки одним шагом — это единственный надёжный вариант.
    # Автодетект версии внутри undetected-chromedriver (version_main=N) неоднократно
    # промахивался мимо реально установленного Chrome в CI (качал driver на 1 major
    # версию вперёд), поэтому в CI он больше не используется.
    driver_path = os.environ.get("CHROMEDRIVER_PATH")
    browser_path = os.environ.get("CHROME_PATH")
    print(f'[i] CHROMEDRIVER_PATH={driver_path!r} CHROME_PATH={browser_path!r} CHROME_VERSION={os.environ.get("CHROME_VERSION")!r}')
    if driver_path:
        if not os.path.isfile(driver_path):
            raise FileNotFoundError(
                f'CHROMEDRIVER_PATH указывает на несуществующий файл: {driver_path} '
                f'(проверь output "chromedriver-path" шага setup-chrome в логе)'
            )
        kwargs = {'options': make_options(), 'driver_executable_path': driver_path}
        if browser_path:
            kwargs['browser_executable_path'] = browser_path
        return uc.Chrome(**kwargs)

    if os.environ.get("CI"):
        raise RuntimeError(
            'В CI ожидался CHROMEDRIVER_PATH из шага setup-chrome, но переменная пуста — '
            'автодетект версии внутри undetected-chromedriver ненадёжен, останавливаюсь, '
            'а не пытаюсь угадать версию.'
        )

    # Локальный запуск (Windows) — прежнее поведение с автодетектом версии.
    version = get_chrome_major_version()
    try:
        if version:
            return uc.Chrome(options=make_options(), version_main=version)
        return uc.Chrome(options=make_options())
    except Exception as e:
        print(f'[!] Запуск не удался: {e}')
        if version:
            raise
        version = get_chrome_major_version()
        if version:
            print(f'[+] Chrome {version} обнаружен, скачиваю ChromeDriver {version}...')
            return uc.Chrome(options=make_options(), version_main=version)
        raise


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
    with open(BASE_DIR / f'url_list_{cur_data_file}_altagamma.txt', 'a') as file:
        for line in url_list:
            file.write(f'{line}\n')


# --- Устойчивость к сбоям браузера и блокировкам -----------------------------
MAX_CARD_ATTEMPTS = 3       # попыток на одну карточку
CONSEC_FAIL_LIMIT = 5       # столько пропусков подряд = блокировка/мёртвый браузер
LONG_PAUSE = 120            # пауза после серии пропусков (секунды)
DRIVER_RESTART_EVERY = 300  # плановый перезапуск Chrome (утечки памяти в headless)
SAVE_EVERY = 50             # как часто сохранять результат на диск
RETRY_ROUNDS = 2            # раунды повтора по пропущенным ссылкам в конце
ROUND_PAUSE = 60
PAGE_LOAD_TIMEOUT = 60


def is_dead_session(e):
    """Браузер/сессия упали: дальше driver.get() будет падать на каждой карточке."""
    if isinstance(e, (InvalidSessionIdException, NoSuchWindowException, TimeoutException)):
        return True
    msg = str(e).lower()
    return any(s in msg for s in (
        'invalid session id', 'chrome not reachable', 'disconnected',
        'target window already closed', 'session deleted', 'tab crashed',
    ))


def short_reason(e):
    text = str(e).strip().splitlines()[0][:140] if str(e).strip() else ''
    return f'{type(e).__name__}: {text}' if text else type(e).__name__


def restart_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass
    time.sleep(5)
    new_driver = create_driver()
    new_driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return new_driver


def parse_card(content, line):
    """Парсит карточку. Бросает ValueError, если вместо товара пришла заглушка/блокировка."""
    soup = BeautifulSoup(content, 'lxml')
    cur_data = datetime.now().strftime("%d.%m.%Y")
    cur_time = datetime.now().strftime("%H:%M")

    title = soup.find("h1", class_="pb__right__title")
    if title is None:
        raise ValueError('нет заголовка товара: вероятно блокировка или страница-заглушка')
    name = title.text.strip()

    try:
        collection = soup.find("a", class_="collection-link").text.strip()
    except:
        collection = "None"

    try:
        new_price = soup.find("div", class_="rf-bold").text.strip()
    except:
        new_price = "None"

    try:
        old_price = soup.find('div', class_='pb__price pb__price_big').find("div", class_="old-price").text.strip()
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

    specs_dict = {}
    for spec in soup.find_all('li', class_="pb__list__item new-ico-wrap"):
        t = spec.find("div", class_='pb__list__title')
        d = spec.find("div", class_='pb__list__desc')
        if t is None or d is None:
            continue
        specs_dict[" ".join(t.text.split())] = " ".join(d.text.split())

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
    return data | specs_dict


def get_data():
    driver = create_driver()
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    result_path = BASE_DIR / f"data_{cur_data_file}_altagamma.json"
    data_dict = []
    break_line = []

    def save():
        with open(result_path, 'w', encoding="utf-8") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)

    try:
        if result_path.exists():
            with open(result_path, 'r', encoding='utf-8') as f:
                data_dict = json.load(f)
        already_done = {r['Ссылка'] for r in data_dict}

        with open(BASE_DIR / f'url_list_{cur_data_file}_altagamma.txt') as file:
            lines = list(dict.fromkeys(line.strip() for line in file if line.strip()))

        pending = [line for line in lines if line not in already_done]
        n = len(lines) - len(pending)
        reasons = {}
        fails_in_row = 0
        since_restart = 0
        saved_since = 0

        for round_num in range(RETRY_ROUNDS + 1):
            if round_num:
                if not pending:
                    break
                print(f'[Раунд повтора {round_num}/{RETRY_ROUNDS}] Пауза {ROUND_PAUSE}с, затем {len(pending)} пропущенных ссылок...')
                time.sleep(ROUND_PAUSE)
                driver = restart_driver(driver)
                since_restart = 0
                fails_in_row = 0

            still_broken = []
            for line in pending:
                data, reason = None, None
                for attempt in range(1, MAX_CARD_ATTEMPTS + 1):
                    try:
                        driver.get(url=line)
                        data = parse_card(driver.page_source, line)
                        break
                    except Exception as e:
                        reason = short_reason(e)
                        if is_dead_session(e):
                            print(f'[!] Сбой браузера ({reason}), перезапускаю Chrome')
                            driver = restart_driver(driver)
                            since_restart = 0
                        else:
                            time.sleep(3 * attempt)

                if round_num == 0:
                    n += 1
                if data is not None:
                    data_dict.append(data)
                    reasons.pop(line, None)
                    fails_in_row = 0
                    since_restart += 1
                    saved_since += 1
                    print(f'Обработано карточек: {n}')
                    if saved_since >= SAVE_EVERY:
                        save()
                        saved_since = 0
                else:
                    reasons[line] = reason
                    still_broken.append(line)
                    fails_in_row += 1
                    print(f'Карточка пропущена ({reason}). Обработано карточек: {n}')
                    if fails_in_row >= CONSEC_FAIL_LIMIT:
                        print(f'[!] {fails_in_row} пропусков подряд: пауза {LONG_PAUSE}с и перезапуск Chrome')
                        time.sleep(LONG_PAUSE)
                        driver = restart_driver(driver)
                        since_restart = 0
                        fails_in_row = 0

                if since_restart >= DRIVER_RESTART_EVERY:
                    print('[i] Плановый перезапуск Chrome')
                    driver = restart_driver(driver)
                    since_restart = 0

            pending = still_broken

        break_line = pending
        print(f'Сломанных ссылок: {len(break_line)} | Причины: {dict(Counter(reasons.values()))}')

        if break_line:
            with open(BASE_DIR / f"urls_break_{cur_data_file}_altagamma.json", 'w', encoding="utf-8") as json_file:
                json.dump(break_line, json_file, indent=4, ensure_ascii=False)

    except Exception as ex:
        print(f'[!] Остановка: {short_reason(ex)}')

    finally:
        # сохраняем всё собранное, даже если скрипт прервали или он упал
        try:
            save()
        except Exception as e:
            print(f'[!] Не удалось сохранить результат: {short_reason(e)}')
        try:
            driver.quit()
        except Exception:
            pass


def main():
    get_urls_tile()
    get_data()


if __name__ == '__main__':
    main()
    finish_time = time.time() - start_time
    print(f"Затраченное на работу скрипта время: {finish_time}")
