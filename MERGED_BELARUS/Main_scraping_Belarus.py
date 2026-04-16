import json
import re
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

def get_data_Altagamma():
    """Загрузка и обработка данных Altagamma (altagamma.by)"""
    file_path = BASE_DIR / 'Altagamma' / f'data_{cur_data_file}_altagamma.json'

    if not file_path.exists():
        print(f"[!] Файл не найден: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[+] Altagamma: Загружено {len(data)} записей")
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

    print(f"[+] 21vek: Загружено {len(data)} записей")
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

    print(f"[+] Modus: Загружено {len(data)} записей")
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

def append_data():
    """Добавление данных в финальный файл"""
    output_file = MERGED_DIR / 'data_finally.json'

    if not output_file.exists():
        print(f"\n[*] Создаю новый файл: data_finally.json")
        existing_data = []
    else:
        try:
            with open(output_file, 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
        except json.JSONDecodeError:
            print(f"[!] Файл data_finally.json поврежден. Создаю новый...")
            existing_data = []

    existing_data.extend(total_base)

    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(existing_data, file, ensure_ascii=False, indent=4)

    print(f"\n[OK] Добавлено {len(total_base)} объектов. Всего в файле: {len(existing_data)} объектов")


def remove_full_duplicates(filename='data_finally.json'):
    """Удаление полных дубликатов"""
    file_path = MERGED_DIR / filename

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        unique_data = []
        seen = set()

        for item in data:
            item_tuple = tuple(sorted(item.items()))
            if item_tuple not in seen:
                seen.add(item_tuple)
                unique_data.append(item)

        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(unique_data, file, ensure_ascii=False, indent=4)

        removed = len(data) - len(unique_data)
        print(f"[-] Удалено {removed} полных дубликатов. Осталось {len(unique_data)} записей.")

    except FileNotFoundError:
        print(f"[!] Файл {filename} не найден.")
    except json.JSONDecodeError:
        print(f"[!] Ошибка чтения файла {filename}")


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

    append_data()
    remove_full_duplicates()

    print("\n[OK] ОБРАБОТКА ЗАВЕРШЕНА УСПЕШНО!")


if __name__ == '__main__':
    main()
    finish_time = round(time.time() - start_time, 1)
    print(f"\nВремя выполнения: {finish_time} секунд")
