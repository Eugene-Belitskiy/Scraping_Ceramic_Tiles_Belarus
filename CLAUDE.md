# CLAUDE.md — Scraping_Belarus_v2

Мониторинг рынка керамической плитки Беларуси для **ОАО "КЕРАМИН"**.
Phase 1: 3 магазина (Altagamma, 21vek, Modus Keramica) → объединение → гармонизация → Supabase → Streamlit-дашборд.

---

## Структура проекта

```
Scraping_Belarus_v2/
├── 21vek/            21vek_request.py + data_MM.YYYY_21_vek_Tile.json
├── Altagamma/        Altagamma.py + data_MM.YYYY_altagamma.json
├── Modus_Keramica/   Modus.py + data_MM.YYYY_Modus.json
├── [Phase 2]/        Keramin, Materik, Mile, Oma, Terracotta
├── MERGED_BELARUS/
│   ├── Main_scraping_Belarus.py     # Объединение всех источников
│   ├── harmonization.py             # Гармонизация полей
│   ├── migrate_to_two_tables.py     # data_finally.json → products.json + prices.json
│   ├── data_finally.json            # (в .gitignore)
│   ├── products.json                # (в .gitignore)
│   └── prices.json                  # (в .gitignore)
├── dashboard/
│   ├── dashboard.py                 # Streamlit-дашборд
│   ├── upload_to_supabase.py        # Загрузка в Supabase
│   ├── create_tables_v2.sql         # SQL-схема таблиц
│   └── .env                         # Ключи Supabase (в .gitignore)
├── ChromeDriver/
└── requirements.txt
```

---

## Источники данных — Phase 1 (реализовано)

| Источник         | Остатки | Примечания                                                            |
|------------------|---------|-----------------------------------------------------------------------|
| **Altagamma**    | Нет     | Ключи с двоеточием (`"Вид материала:"`); цена — числовая строка      |
| **21 век**       | Нет     | Поле цены динамическое: `"Действующая цена_MM.YYYY"`; "20,78 р./м²" |
| **Модус керамика** | Нет   | Цена вида `"128.94 р./м2"`; скидка `"-25%"` или `"Error"`           |

## Источники данных — Phase 2 (планируется)

| Источник         | Остатки | Примечания                        |
|------------------|---------|-----------------------------------|
| **Keramin**      | Нет     | Официальный сайт клиента          |
| **Materik**      | TBD     | diy.by                            |
| **Mile**         | TBD     | mile.by                           |
| **Oma**          | TBD     | oma.by — есть остатки по магазинам |
| **Terracotta**   | TBD     | terracotta.by                     |

---

## Первичная настройка (один раз)

```bash
# 1. Применить схему в Supabase (SQL Editor)
#    Выполнить содержимое dashboard/create_tables_v2.sql

# 2. Создать файл dashboard/.env с ключами Supabase:
#    SUPABASE_URL=https://xxx.supabase.co
#    SUPABASE_KEY=your-anon-key

# 3. Собрать первые данные (раскомментировать cur_data_file = "01.2026")
python MERGED_BELARUS/Main_scraping_Belarus.py

# 4. Мигрировать data_finally.json → products.json + prices.json
python MERGED_BELARUS/migrate_to_two_tables.py

# 5. Загрузить в Supabase
python dashboard/upload_to_supabase.py
```

## Ежемесячный мониторинг

```bash
# 1. Парсинг источников (по отдельности)
python Altagamma/Altagamma.py
python 21vek/21vek_request.py
python Modus_Keramica/Modus.py

# 2. Объединение и гармонизация → записывает data_finally.json
python MERGED_BELARUS/Main_scraping_Belarus.py

# 3. Мигрировать обновлённые данные
python MERGED_BELARUS/migrate_to_two_tables.py

# 4. Загрузить в Supabase
python dashboard/upload_to_supabase.py
```

## Запуск дашборда локально

```bash
pip install -r requirements.txt
streamlit run dashboard/dashboard.py
```

Дашборд откроется по адресу `http://localhost:8501`

---

## Ключевые решения в коде

### Период данных
`cur_data_file = datetime.now().strftime("%m.%Y")` — определяет, какие JSON-файлы загружать.
Для работы с конкретным месяцем — раскомментировать строку вида `# cur_data_file = "01.2026"`.

### Безопасные преобразования
```python
safe_float(value)  # None / '' → None; убирает пробелы, запятые→точку
safe_int(value)    # аналогично для int
```
Никогда не делать `line.get('field', '').replace(...)` — `get()` может вернуть `None`.
Правильно: `(line.get('field', '') or '').replace(...)`.

### Валюта и диапазон цен
Белорусский рубль (BYN). Диапазон цен — шаг **10 BYN** (не 100 как в России):
```python
lower = int(price // 10) * 10
upper = lower + 10
```
Типичные цены: 8–440 BYN/м².

### Динамическое поле цены (21vek)
Поле называется `"Действующая цена_MM.YYYY"` — имя меняется каждый месяц. Поиск:
```python
price_key = next((k for k in line if k.startswith('Действующая цена_')), None)
```
Парсинг цены из строки `"20,78 р./м²"`:
```python
m = re.match(r'^([\d\.]+)', price_str.replace(',', '.'))
price = float(m.group(1)) if m else None
```

### Цена Modus Keramica
Строка вида `"128.94 р./м2"` или `"6.20 р./шт"` — извлекаем число:
```python
m = re.match(r'^([\d\.]+)', price_str)
price = float(m.group(1)) if m else None
```

### Поля Altagamma с двоеточием
Поля реально называются `"Вид материала:"`, `"Тип поверхности плитки:"` и т.д.
Читать как есть: `line.get('Вид материала:', '')` — двоеточие входит в ключ.

### Толщина Modus Keramica
Поле `"Толщина, см"` содержит значение в сантиметрах (напр. `"0.9"`).
Конвертация: `thickness = round(thickness_cm * 10, 1)`.

### Материал Modus Keramica
Поле `"Вид плитки"` содержит `"керамический гранит"` (не `"керамогранит"`).
Нормализация перед `determine_material()`:
```python
if 'гранит' in material_raw:
    material_raw = 'керамогранит'
```

### Нормализация формата плитки
- Разделители `×`, `х`, `X` → `x`
- Округление до кратного 5
- Сортировка по убыванию (60x30, не 30x60)
- Словарь `replacements` для нестандартных замен

### Материалы (только эти три)
`['Керамогранит', 'Керамика', 'Клинкер']` — всё остальное фильтруется.

---

## Модуль harmonization.py

Вызывается из `create_data_card()` для каждой записи:
```python
harmonized = harmonize_record(raw_card)
harmonized['primary_design'] = get_primary_design(harmonized.get('design', ''))
harmonized['primary_color'] = get_primary_color(harmonized.get('color', ''))
```

Что гармонизируется:
- **Единицы измерения** → `м²`, `шт.`, `упаковка`, `комплект`, `коробка`
- **Дизайн** — синонимы объединены, комбинации сохранены (`"Мрамор, Камень"`)
- **Цвет** — оттенки убраны (`"светло-серый"` → `"Серый"`), комбинации сохранены
- **Тип поверхности** → женский род, капитализация (`"матовая"` → `"Матовая"`)
- **Бренды** — суффиксы удалены (`CERAMICA`, `CERAMICHE` и др.)
- **Наличие** — `"Остаток X м2"` → `"В наличии"`, `"Предзаказ..."` → `"Под заказ"`
- **primary_design** / **primary_color** — первый элемент из комбинации (для фильтрации)

---

## Структура данных

Промежуточный файл: `MERGED_BELARUS/data_finally.json`
Финальные файлы (после `migrate_to_two_tables.py`): `products.json` + `prices.json`

Формат записи (те же поля, что и в Russia-версии):

| Поле | Описание |
|------|----------|
| `name` | Полное наименование |
| `price` | Цена (float, BYN) |
| `price_range` | Диапазон цены ("10-20", шаг 10 BYN) |
| `discount` | Скидка (%) |
| `discount_range` | Диапазон скидки (шаг 10%) |
| `price_unit` | Единица измерения (`м²`, `шт.`) |
| `url` | Ссылка |
| `store` | Магазин |
| `availability` | Наличие (`В наличии`, `Под заказ`, `Нет в наличии`) |
| `date` / `time` | Дата и время мониторинга |
| `color` / `primary_color` | Цвет (полный / основной) |
| `collection` | Коллекция |
| `brand` | Бренд (ВЕРХНИЙ РЕГИСТР) |
| `country` | Страна производства (ВЕРХНИЙ РЕГИСТР) |
| `brand_country` | Комбинация "БРЕНД (СТРАНА)" |
| `thickness` | Толщина, мм |
| `original_format` | Исходный формат из источника |
| `format` | Нормализованный формат ("60x60") |
| `design` / `primary_design` | Дизайн (полный / основной) |
| `material` | Материал (`Керамогранит`, `Керамика`, `Клинкер`) |
| `surface_type` | Тип поверхности (`Матовая`, `Глянцевая`, ...) |
| `surface_finish` | Покрытие (`Полированный`, `Не полированный`) |
| `structure` | Структура (`Гладкая`, `Рельефная`) |
| `total_stock` | Остатки (Phase 1: всегда None) |

---

## Windows-специфичные проблемы

- **Эмодзи в print()** вызывают `UnicodeEncodeError` — использовать `[+]`, `[!]`, `[OK]`
- JSON-файлы данных в `.gitignore` (не хранятся в репозитории)
- ChromeDriver управляется через `undetected-chromedriver`
- При запуске `python MERGED_BELARUS/Main_scraping_Belarus.py` из корня проекта — импорт `harmonization` работает корректно (cwd = MERGED_BELARUS при запуске через `cd MERGED_BELARUS && python ...`)

---

## Типичные ошибки

| Ошибка | Решение |
|--------|---------|
| `AttributeError: 'NoneType' has no attribute 'replace'` | Добавить `or ''` после `line.get(...)` |
| `MERGED_DIR` указывает на `MERGED_RUSSIA` | Исправить на `BASE_DIR / "MERGED_BELARUS"` |
| Поле цены 21vek не найдено (`price = None`) | Ключ динамический — искать через `startswith('Действующая цена_')` |
| Толщина Modus неверная (в 10 раз больше) | Поле в СМ, умножить на 10 для мм |
| Материал Modus = None | Нормализовать `"керамический гранит"` → `"керамогранит"` до вызова `determine_material()` |
| Функция не вызывается в `main()` | Все функции `get_data_*()` должны быть в `main()` |
