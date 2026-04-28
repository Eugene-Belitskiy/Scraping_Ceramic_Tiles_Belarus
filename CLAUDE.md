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
│   ├── Main_scraping_Belarus.py     # Объединение всех источников → products.json + prices.json
│   ├── harmonization.py             # Гармонизация полей
│   ├── migrate_to_two_tables.py     # Устарел — оставлен для ручной миграции старых данных
│   ├── products.json                # (в .gitignore)
│   └── prices.json                  # (в .gitignore)
├── dashboard/
│   ├── dashboard.py                 # Streamlit-дашборд (6 табов)
│   ├── upload_to_supabase.py        # Загрузка в Supabase (только текущий месяц)
│   ├── create_tables_v2.sql         # SQL-схема таблиц + вью tiles_v2
│   └── .env                         # Ключи Supabase (в .gitignore)
├── ChromeDriver/
└── requirements.txt
```

---

## Источники данных — Phase 1 (реализовано)

| Источник           | Остатки | Примечания                                                            |
|--------------------|---------|-----------------------------------------------------------------------|
| **Altagamma**      | Нет     | Ключи с двоеточием (`"Вид материала:"`); цена — числовая строка      |
| **21 век**         | Нет     | Поле цены динамическое: `"Действующая цена_MM.YYYY"`; "20,78 р./м²" |
| **Модус керамика** | Нет     | Цена вида `"128.94 р./м2"`; скидка `"-25%"` или `"Error"`           |

## Источники данных — Phase 2 (планируется)

| Источник       | Остатки | Примечания                         |
|----------------|---------|------------------------------------|
| **Keramin**    | Нет     | Официальный сайт клиента           |
| **Materik**    | TBD     | diy.by                             |
| **Mile**       | TBD     | mile.by                            |
| **Oma**        | TBD     | oma.by — есть остатки по магазинам |
| **Terracotta** | TBD     | terracotta.by                      |

---

## Первичная настройка (один раз)

```bash
# 1. Применить схему в Supabase (SQL Editor)
#    Выполнить содержимое dashboard/create_tables_v2.sql

# 2. Включить анонимный доступ к таблицам products и prices в Supabase:
#    Table Editor → products → RLS → New Policy → SELECT for anon
#    (аналогично для prices)

# 3. Создать файл dashboard/.env с ключами Supabase:
#    SUPABASE_URL=https://xxx.supabase.co
#    SUPABASE_KEY=your-anon-key

# 4. Собрать первые данные (раскомментировать cur_data_file = "01.2026")
python MERGED_BELARUS/Main_scraping_Belarus.py

# 5. Загрузить в Supabase
python dashboard/upload_to_supabase.py
```

## Ежемесячный мониторинг

```bash
# 1. Парсинг источников (по отдельности)
python Altagamma/Altagamma.py
python 21vek/21vek_request.py
python Modus_Keramica/Modus.py

# 2. Объединение и гармонизация → пишет напрямую в products.json + prices.json
python MERGED_BELARUS/Main_scraping_Belarus.py

# 3. Загрузить только данные текущего месяца в Supabase
python dashboard/upload_to_supabase.py
```

## Запуск дашборда локально

```bash
pip install -r requirements.txt
streamlit run dashboard/dashboard.py
```

Дашборд откроется по адресу `http://localhost:8501`

---

## Архитектура данных

### Пайплайн

```
Scrapers (JSON) → Main_scraping_Belarus.py → products.json + prices.json
                                           → upload_to_supabase.py → Supabase
                                                                    → dashboard.py
```

`Main_scraping_Belarus.py` пишет **напрямую** в две таблицы — `data_finally.json` больше не используется.

### Таблицы в Supabase

**`products`** — уникальные карточки товаров (один раз на URL):
- Идентификатор: `product_id = md5(url)[:16]`
- Статичные характеристики: name, brand, country, format, material, design, color, ...

**`prices`** — история цен (одна запись на товар на дату):
- Идентификатор: `price_id = f"{product_id}_{date}_{time}"`
- Динамические поля: price, discount, availability, date, time

**`tiles_v2`** — вью для дашборда: JOIN products + prices, только **последние цены** каждого товара.
Используется как фолбэк в `load_data()` если прямой доступ к таблицам недоступен.

### Дедупликация в Main_scraping_Belarus.py

1. `dedup_by_url(data)` — убирает дублирующиеся URL **внутри** одного сырого JSON-файла (скрапер мог работать несколько дней подряд). Оставляет последнее вхождение.
2. В `save_to_two_tables()` — полные дубликаты из `total_base` убираются перед записью.
3. Товар попадает в `products.json` **один раз** (по product_id).
4. Цена добавляется, если `price_id` (product_id + дата + время) ещё не существует.

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

### Загрузка в Supabase (upload_to_supabase.py)
Загружает только данные **текущего месяца** (`CUR_MONTH = datetime.now().strftime("%m.%Y")`).
Для загрузки конкретного месяца — раскомментировать `# CUR_MONTH = "04.2026"`.
Использует upsert — повторный запуск безопасен.

### load_data() в дашборде
Двухуровневая загрузка:
1. **Приоритет**: таблицы `products` + `prices` → полная история, работает таб «Динамика»
2. **Фолбэк**: вью `tiles_v2` → только последний период (если RLS блокирует прямой доступ)

### Форматы по материалам (MATERIAL_FORMATS)
```python
"Керамика":     ["90x30", "60x30", "40x25", "30x10"]
"Керамогранит": ["120x60", "60x60", "60x30", "40x40", "30x30"]
"Клинкер":      ["40x40", "30x30", "25x5"]
```

### Материалы (только эти три)
`['Керамогранит', 'Керамика', 'Клинкер']` — всё остальное фильтруется.

---

## Дашборд — структура табов

| Таб | Содержание |
|-----|------------|
| **Ценовой ландшафт** | Метрики, Violin chart, Histogram |
| **Угрозы КЕРАМИН** | Bubble chart, Heatmap, Band chart |
| **Позиция по форматам** | Таблица позиций, Violin с пузырьками |
| **Поиск аналогов** | Фильтрация + таблица аналогов |
| **Данные** | Все отфильтрованные данные + Excel |
| **Динамика** | Блок 1: сравнение двух периодов (новые/ушедшие товары, изменение цен). Блок 2: тренды за N периодов (SKU, цены, тепловая карта) |

**Селектор периода** в сайдбаре (над всеми фильтрами) управляет табами 1–5.
Таб «Динамика» использует полную историю (`df_sidebar` — все периоды).

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
| `KeyError: 'period_label'` в дашборде | RLS в Supabase блокирует доступ к `products`/`prices` — включить политику SELECT для anon |
| Поле цены 21vek не найдено (`price = None`) | Ключ динамический — искать через `startswith('Действующая цена_')` |
| Толщина Modus неверная (в 10 раз больше) | Поле в СМ, умножить на 10 для мм |
| Материал Modus = None | Нормализовать `"керамический гранит"` → `"керамогранит"` до вызова `determine_material()` |
| Дубликаты цен в prices.json | `price_id` включает время — повторный запуск Main без перескрапинга не задваивает |
| `Slider min_value must be less than max_value` | Происходит при ровно 2 периодах — слайдер не показывается, используется `n_periods=2` |
