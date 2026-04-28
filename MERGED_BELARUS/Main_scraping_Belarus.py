import json
import re
import hashlib
from datetime import datetime
import time
from pathlib import Path
from typing import Dict, Optional
from harmonization import harmonize_record, get_primary_design, get_primary_color

start_time = time.time()

# Определяем базовую директорию проекта
BASE_DIR = Path(__file__).parent.parent
MERGED_DIR = BASE_DIR / "MERGED_BELARUS"

cur_data_file = datetime.now().strftime("%m.%Y")
# cur_data_file = "01.2026"

# Словарь замены нестандартных форматов
replacements = {
    "35x35": "30x30",
    "45x45": "50x50",
    "65x30": "60x30",
    "60x25": "60x30",
    "40x20": "40x25",
    "40x30": "40x25",
    '60x35': '60x30',
    '120x35': '120x30',
    '55x55': '60x60',
    '120x55': '120x50',
    '115x55': '120x60'
}

total_base = []


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

def safe_float(value, default=None) -> Optional[float]:
    """Безопасное преобразование в float"""
    if value is None or value == '':
        return default
    try:
        if isinstance(value, str):
            value = value.replace(' ', '').replace(',', '.').replace('₽', '').replace('−', '').replace('%', '').replace('-', '')
        return float(value)
    except (ValueError, AttributeError):
        return default


def safe_int(value, default=None) -> Optional[int]:
    """Безопасное преобразование в int"""
    if value is None or value == '':
        return default
    try:
        if isinstance(value, str):
            value = value.replace(' ', '').replace(',', '.').replace('−', '').replace('%', '').replace('-', '')
        return int(float(value))
    except (ValueError, AttributeError):
        return default


def calculate_price_range(price: Optional[float]) -> Optional[str]:
    """Расчет диапазона цены (шаг 10 BYN)"""
    if price is None:
        return None
    try:
        lower = int(price // 10) * 10
        upper = lower + 10
        return f'{lower}-{upper}'
    except:
        return None


def calculate_sale_range(sale: Optional[float]) -> Optional[str]:
    """Расчет диапазона скидки"""
    if sale is None:
        return None
    try:
        lower = (round(sale // 10) * 10)
        upper = lower + 10
        return f'{lower}-{upper}'
    except:
        return None


def normalize_format(original_format: Optional[str]) -> Optional[str]:
    """Нормализация формата плитки"""
    if not original_format:
        return None
    try:
        # Заменяем различные разделители на 'x'
        original_format = original_format.replace('×', 'x').replace('х', 'x').replace('X', 'x')

        list_of_sizes = original_format.split('x')
        # Округляем до ближайшего значения кратного 5
        float_list_of_sizes = [round(float(x) / 5) * 5 for x in list_of_sizes]
        # Сортируем по убыванию
        format_str = 'x'.join(map(str, sorted(float_list_of_sizes, reverse=True)))
        # Применяем замены нестандартных форматов
        return replacements.get(format_str, format_str)
    except:
        return None


def determine_surface_type(type_of_surface: str, name: str) -> str:
    """Определение типа покрытия поверхности"""
    if not type_of_surface and not name:
        return "Не полированный"

    type_lower = type_of_surface.lower() if type_of_surface else ''
    name_lower = name.lower() if name else ''

    if 'полирован' in type_lower or 'полирован' in name_lower:
        return 'Полированный'
    elif 'лаппатирован' in type_lower or 'лаппатирован' in name_lower:
        return 'Лаппатированный'
    else:
        return "Не полированный"


def determine_material(name: str, material_field: str = '') -> Optional[str]:
    """Определение материала плитки"""
    name_lower = name.lower() if name else ''
    material_lower = material_field.lower() if material_field else ''

    if 'линкер' in name_lower or 'клинкер' in material_lower:
        return 'Клинкер'
    elif 'керамогранит' in name_lower or 'напольная' in name_lower or 'керамогранит' in material_lower:
        return 'Керамогранит'
    elif 'керамик' in material_lower or 'глина' in material_lower or 'плитка' in name_lower:
        return 'Керамика'

    return material_field if material_field else None


def create_data_card(line: Dict, store: str) -> Dict:
    """
    Создание финальной карточки товара в едином формате
    Применяет гармонизацию данных для приведения к единому стилю
    """
    raw_card = {
        'name': line.get('name', ''),
        'price': line.get('price'),
        'price_range': line.get('price_range'),
        'discount': line.get('sale'),
        'discount_range': line.get('sale_range'),
        'price_unit': line.get('mesure', ''),
        'url': line.get('link', ''),
        'store': store,
        'availability': line.get('availability', ''),
        'date': line.get('date_scrap', ''),
        'time': line.get('time_scrap', ''),
        'color': line.get('colour', ''),
        'collection': line.get('collection', ''),
        'brand': line.get('brand', ''),
        'country': line.get('country', ''),
        'brand_country': line.get('brand_country', ''),
        'thickness': line.get('thickness'),
        'original_format': line.get('original_format', ''),
        'format': line.get('format'),
        'design': line.get('design', ''),
        'material': line.get('material', ''),
        'surface_type': line.get('type_of_surface', ''),
        'surface_finish': line.get('surface', ''),
        'structure': line.get('structure', ''),
        'patterns_count': line.get('number_of_pictures', ''),
        'total_stock': line.get('total_base_stock', ''),
        'package_size': line.get('packaging'),
        'total_stock_units': line.get('total_stock')
    }

    # Применяем гармонизацию данных
    harmonized = harmonize_record(raw_card)

    # Добавляем поля с основными (первыми) значениями для комбинаций
    harmonized['primary_design'] = get_primary_design(harmonized.get('design', ''))
    harmonized['primary_color'] = get_primary_color(harmonized.get('color', ''))

    return harmonized


# ============= ФУНКЦИИ ЗАГРУЗКИ ДАННЫХ =============

def dedup_by_url(data: list, url_key: str = 'Ссылка') -> list:
    """Оставляет последнее вхождение каждого URL (актуальные данные при повторных запусках)."""
    seen = {}
    for item in data:
        url = item.get(url_key, '')
        if url:
            seen[url] = item
    return list(seen.values())

def get_data_Altagamma():
    """Загрузка и обработка данных Altagamma (altagamma.by)"""
    file_path = BASE_DIR / 'Altagamma' / f'data_{cur_data_file}_altagamma.json'

    if not file_path.exists():
        print(f"[!] Файл не найден: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data = dedup_by_url(data)
    print(f"[+] Altagamma: Загружено {len(data)} уникальных записей")
    processed = 0

    for line in data:
        name = line.get('Полное наименование', '')
        if not name:
            continue

        # Материал — ключ с двоеточием
        material_raw = (line.get('Вид материала:', '') or '').lower()
        material = determine_material(name, material_raw)
        if material not in ['Керамогранит', 'Керамика', 'Клинкер']:
            continue

        # Цена — числовая строка "54.00"
        price = safe_float(line.get('Действующая цена', ''))
        old_price = safe_float(line.get('Цена без скидки', ''))
        price_range = calculate_price_range(price)
        sale = round((1 - price / old_price) * 100) if price and old_price and old_price > price else None
        sale_range = calculate_sale_range(sale)

        mesure = (line.get('Единица измерения цены', '') or '')

        # Формат: приоритет "Размер плитки, см:", fallback "Размер фактический, см:"
        original_format = (line.get('Размер плитки, см:', '') or
                           line.get('Размер фактический, см:', '') or '')
        format_normalized = normalize_format(original_format) if original_format else None

        thickness = safe_float(line.get('Толщина плитки, мм:', ''))
        type_of_surface = (line.get('Тип поверхности плитки:', '') or '')
        surface = determine_surface_type(type_of_surface, name)

        brand = (line.get('Бренд плитки:', '') or '').upper()
        country = (line.get('Страна производителя:', '') or '').upper()
        brand_country = f'{brand} ({country})' if brand and country else brand or country

        processed_line = {
            'name': name,
            'price': price,
            'price_range': price_range,
            'sale': sale,
            'sale_range': sale_range,
            'mesure': mesure,
            'link': line.get('Ссылка', ''),
            'availability': (line.get('В наличии', '') or ''),
            'date_scrap': line.get('Дата мониторинга', ''),
            'time_scrap': line.get('Время мониторинга', ''),
            'colour': (line.get('Цвет плитки:', '') or ''),
            'collection': line.get('Коллекция', ''),
            'brand': brand,
            'country': country,
            'brand_country': brand_country,
            'thickness': thickness,
            'original_format': original_format,
            'format': format_normalized,
            'design': (line.get('Текстура плитки:', '') or ''),
            'material': material,
            'type_of_surface': type_of_surface,
            'surface': surface,
            'structure': '',
            'number_of_pictures': (line.get('Количество рисунков:', '') or ''),
            'total_base_stock': None,
            'packaging': None,
            'total_stock': None
        }

        total_base.append(create_data_card(processed_line, 'Altagamma'))
        processed += 1

    print(f"    Обработано {processed} записей")


def get_data_21vek():
    """Загрузка и обработка данных 21 век (21vek.by)"""
    file_path = BASE_DIR / '21vek' / f'data_{cur_data_file}_21_vek_Tile.json'

    if not file_path.exists():
        print(f"[!] Файл не найден: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data = dedup_by_url(data)
    print(f"[+] 21vek: Загружено {len(data)} уникальных записей")
    processed = 0

    for line in data:
        name = line.get('Полное наименование', '')
        if not name:
            continue

        # Материал — значения типа "керамогранит (грес)", "керамика"
        material_raw = (line.get('Материал', '') or '').lower()
        if 'керамогранит' in material_raw or 'грес' in material_raw:
            material = 'Керамогранит'
        elif 'керамик' in material_raw:
            material = 'Керамика'
        elif 'клинкер' in material_raw:
            material = 'Клинкер'
        else:
            continue  # фильтруем зеркала, стекло, металл и т.п.

        # Динамический ключ цены — имя меняется каждый месяц
        price_key = next((k for k in line if k.startswith('Действующая цена_')), None)
        old_price_key = next((k for k in line if k.startswith('Цена без скидки_')), None)

        price = None
        if price_key:
            m = re.match(r'^([\d\.]+)', (line.get(price_key, '') or '').replace(',', '.'))
            price = float(m.group(1)) if m else None

        old_price = None
        if old_price_key:
            m2 = re.match(r'^([\d\.]+)', (line.get(old_price_key, '') or '').replace(',', '.'))
            old_price = float(m2.group(1)) if m2 else None

        price_range = calculate_price_range(price)
        sale = round((1 - price / old_price) * 100) if price and old_price and old_price > price else None
        sale_range = calculate_sale_range(sale)

        mesure = (line.get('Единица измерения цены', '') or '')

        # Формат: Длина и Ширина в мм → конвертируем в см
        original_format = None
        try:
            length_cm = float((line.get('Длина', '') or '').replace(' мм', '').strip()) / 10
            width_cm = float((line.get('Ширина', '') or '').replace(' мм', '').strip()) / 10
            original_format = f"{max(length_cm, width_cm)}x{min(length_cm, width_cm)}"
        except (ValueError, TypeError):
            pass
        format_normalized = normalize_format(original_format) if original_format else None

        # Толщина: "8 мм" → 8.0
        thickness = safe_float((line.get('Толщина', '') or '').replace(' мм', '').strip())

        type_of_surface = (line.get('Поверхность', '') or '')
        surface = determine_surface_type(type_of_surface, name)

        # Бренд: нет прямого поля — берём слова [1] и [2] из названия
        # Структура: "Плитка Beryoza Ceramica Marble белый (300x600)"
        name_parts = name.split()
        if len(name_parts) >= 3:
            brand = f"{name_parts[1]} {name_parts[2]}".upper()
        elif len(name_parts) == 2:
            brand = name_parts[1].upper()
        else:
            brand = ''

        country = (line.get('Страна производства', '') or '').upper()
        brand_country = f'{brand} ({country})' if brand and country else brand or country

        processed_line = {
            'name': name,
            'price': price,
            'price_range': price_range,
            'sale': sale,
            'sale_range': sale_range,
            'mesure': mesure,
            'link': line.get('Ссылка', ''),
            'availability': (line.get('В наличии', '') or ''),
            'date_scrap': line.get('Дата мониторинга', ''),
            'time_scrap': line.get('Время мониторинга', ''),
            'colour': (line.get('Цвет', '') or ''),
            'collection': (line.get('Коллекция', '') or ''),
            'brand': brand,
            'country': country,
            'brand_country': brand_country,
            'thickness': thickness,
            'original_format': original_format,
            'format': format_normalized,
            'design': (line.get('Дизайн плитки', '') or ''),
            'material': material,
            'type_of_surface': type_of_surface,
            'surface': surface,
            'structure': (line.get('Рельеф', '') or ''),
            'number_of_pictures': '',
            'total_base_stock': None,
            'packaging': None,
            'total_stock': None
        }

        total_base.append(create_data_card(processed_line, '21 век'))
        processed += 1

    print(f"    Обработано {processed} записей")


def get_data_Modus():
    """Загрузка и обработка данных Modus Keramica (keramika.by)"""
    file_path = BASE_DIR / 'Modus_Keramica' / f'data_{cur_data_file}_Modus.json'

    if not file_path.exists():
        print(f"[!] Файл не найден: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data = dedup_by_url(data)
    print(f"[+] Modus: Загружено {len(data)} уникальных записей")
    processed = 0

    for line in data:
        name = line.get('Полное наименование', '')
        if not name:
            continue

        # Материал — "керамический гранит" нужно нормализовать до вызова determine_material
        material_raw = (line.get('Вид плитки', '') or '').lower()
        if 'гранит' in material_raw:
            material_raw = 'керамогранит'
        material = determine_material(name, material_raw)
        if material not in ['Керамогранит', 'Керамика', 'Клинкер']:
            continue

        # Цена: "128.94 р./м2" или "6.20 р./шт" — извлечь число
        price_str = (line.get('Действующая цена', '') or '')
        m = re.match(r'^([\d\.]+)', price_str)
        price = float(m.group(1)) if m else None
        price_range = calculate_price_range(price)

        # Скидка: "-25%" или "Error"
        skidka_str = (line.get('Размер скидки', '') or '')
        sale = None
        if skidka_str and skidka_str != 'Error':
            m2 = re.match(r'[-]?(\d+)', skidka_str)
            if m2:
                sale = int(m2.group(1))
        sale_range = calculate_sale_range(sale)

        mesure = (line.get('Единица измерения цены', '') or '')

        # Формат: приоритет "Формат", fallback "Длина, см" + "Ширина, см"
        original_format = (line.get('Формат', '') or '')
        if not original_format:
            try:
                length = safe_float(line.get('Длина, см', ''))
                width = safe_float(line.get('Ширина, см', ''))
                if length and width:
                    original_format = f"{max(length, width)}x{min(length, width)}"
            except (TypeError, ValueError):
                pass
        format_normalized = normalize_format(original_format) if original_format else None

        # Толщина в СМ → конвертируем в мм
        thickness_cm = safe_float(line.get('Толщина, см', ''))
        thickness = round(thickness_cm * 10, 1) if thickness_cm else None

        type_of_surface = (line.get('Вид поверхности плитки', '') or '')
        surface = determine_surface_type(type_of_surface, name)

        brand = (line.get('Бренд', '') or '').upper()
        country = (line.get('Страна производитель', '') or '').upper()
        brand_country = f'{brand} ({country})' if brand and country else brand or country

        processed_line = {
            'name': name,
            'price': price,
            'price_range': price_range,
            'sale': sale,
            'sale_range': sale_range,
            'mesure': mesure,
            'link': line.get('Ссылка', ''),
            'availability': (line.get('В наличии', '') or ''),
            'date_scrap': line.get('Дата мониторинга', ''),
            'time_scrap': line.get('Время мониторинга', ''),
            'colour': (line.get('Цвет (сайт)', '') or ''),
            'collection': (line.get('Коллекция', '') or ''),
            'brand': brand,
            'country': country,
            'brand_country': brand_country,
            'thickness': thickness,
            'original_format': original_format,
            'format': format_normalized,
            'design': (line.get('Текстура плитки', '') or ''),
            'material': material,
            'type_of_surface': type_of_surface,
            'surface': surface,
            'structure': '',
            'number_of_pictures': '',
            'total_base_stock': None,
            'packaging': None,
            'total_stock': None
        }

        total_base.append(create_data_card(processed_line, 'Модус керамика'))
        processed += 1

    print(f"    Обработано {processed} записей")


# ============= ФУНКЦИИ РАБОТЫ С ФАЙЛАМИ =============

def make_product_id(url: str) -> str:
    return hashlib.md5(url.encode('utf-8')).hexdigest()[:16]


def save_to_two_tables():
    """Записывает данные напрямую в products.json и prices.json.

    products.json — уникальные карточки товаров (идентифицируются по URL).
    prices.json   — полная история цен (price_id = product_id + дата).
    Повторный запуск безопасен: добавляются только новые записи.
    """
    products_file = MERGED_DIR / 'products.json'
    prices_file = MERGED_DIR / 'prices.json'

    # Загружаем существующие данные
    existing_products = []
    seen_ids = set()
    if products_file.exists():
        try:
            with open(products_file, 'r', encoding='utf-8') as f:
                existing_products = json.load(f)
            seen_ids = {p['product_id'] for p in existing_products}
        except json.JSONDecodeError:
            print("[!] products.json поврежден. Создаю новый...")

    existing_prices = []
    seen_price_ids = set()
    if prices_file.exists():
        try:
            with open(prices_file, 'r', encoding='utf-8') as f:
                existing_prices = json.load(f)
            seen_price_ids = {p['price_id'] for p in existing_prices}
        except json.JSONDecodeError:
            print("[!] prices.json поврежден. Создаю новый...")

    # Убираем полные дубликаты из сырых данных текущего запуска
    seen_raw = set()
    deduped_base = []
    for r in total_base:
        key = tuple(sorted((k, str(v)) for k, v in r.items()))
        if key not in seen_raw:
            seen_raw.add(key)
            deduped_base.append(r)
    skipped_raw = len(total_base) - len(deduped_base)
    if skipped_raw:
        print(f"[*] Пропущено {skipped_raw} полных дубликатов в сырых данных")

    new_products = 0
    new_prices = 0
    skipped_no_url = 0
    skipped_dup_price = 0

    for record in deduped_base:
        url = record.get('url', '')
        if not url:
            skipped_no_url += 1
            continue

        pid = make_product_id(url)
        date = record.get('date', '')
        time_val = record.get('time', '')
        price_id = f"{pid}_{date}_{time_val}"

        if pid not in seen_ids:
            existing_products.append({
                'product_id':      pid,
                'date_added':      date,
                'url':             url,
                'store':           record.get('store', ''),
                'name':            record.get('name', ''),
                'color':           record.get('color', ''),
                'primary_color':   record.get('primary_color', ''),
                'collection':      record.get('collection', ''),
                'brand':           record.get('brand', ''),
                'country':         record.get('country', ''),
                'brand_country':   record.get('brand_country', ''),
                'thickness':       record.get('thickness'),
                'original_format': record.get('original_format', ''),
                'format':          record.get('format'),
                'design':          record.get('design', ''),
                'primary_design':  record.get('primary_design', ''),
                'material':        record.get('material', ''),
                'surface_type':    record.get('surface_type', ''),
                'surface_finish':  record.get('surface_finish', ''),
                'structure':       record.get('structure', ''),
                'patterns_count':  record.get('patterns_count', ''),
                'package_size':    record.get('package_size'),
                'price_unit':      record.get('price_unit', ''),
            })
            seen_ids.add(pid)
            new_products += 1

        if price_id not in seen_price_ids:
            existing_prices.append({
                'price_id':          price_id,
                'product_id':        pid,
                'store':             record.get('store', ''),
                'date':              date,
                'time':              record.get('time', ''),
                'price':             record.get('price'),
                'price_range':       record.get('price_range'),
                'discount':          record.get('discount'),
                'discount_range':    record.get('discount_range'),
                'availability':      record.get('availability', ''),
                'total_stock':       record.get('total_stock'),
                'total_stock_units': record.get('total_stock_units'),
            })
            seen_price_ids.add(price_id)
            new_prices += 1
        else:
            skipped_dup_price += 1

    with open(products_file, 'w', encoding='utf-8') as f:
        json.dump(existing_products, f, ensure_ascii=False, indent=4)

    with open(prices_file, 'w', encoding='utf-8') as f:
        json.dump(existing_prices, f, ensure_ascii=False, indent=4)

    print(f"\n[OK] products.json: +{new_products} новых товаров (всего {len(existing_products)})")
    print(f"[OK] prices.json:   +{new_prices} новых записей цен (всего {len(existing_prices)})")
    if skipped_no_url:
        print(f"[!] Пропущено {skipped_no_url} записей без URL")
    if skipped_dup_price:
        print(f"[*] Пропущено {skipped_dup_price} дублирующихся записей цен")


# ============= ГЛАВНАЯ ФУНКЦИЯ =============

def main():
    """Главная функция запуска обработки всех источников"""
    print("=" * 60)
    print("НАЧАЛО ОБРАБОТКИ ДАННЫХ")
    print(f"Период данных: {cur_data_file}")
    print("=" * 60)

    get_data_Altagamma()
    get_data_21vek()
    get_data_Modus()

    print("\n" + "=" * 60)
    print(f"ИТОГО обработано: {len(total_base)} записей")
    print("=" * 60)

    save_to_two_tables()

    print("\n[OK] ОБРАБОТКА ЗАВЕРШЕНА УСПЕШНО!")


if __name__ == '__main__':
    main()
    finish_time = round(time.time() - start_time, 1)
    print(f"\nВремя выполнения: {finish_time} секунд")
