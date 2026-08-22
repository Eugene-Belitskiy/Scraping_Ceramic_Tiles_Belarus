# Автоматизация парсинга Беларуси (GitHub Actions + Supabase) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Парсеры 21vek, Altagamma, Modus Keramica запускаются сами раз в месяц в GitHub Actions, результат сам сливается, гармонизируется и грузится в Supabase upsert'ом — без ручного запуска скриптов с ноутбука.

**Architecture:** Один workflow-файл `.github/workflows/monthly-scrape.yml` с тремя независимыми `scrape-*` job'ами (каждый `continue-on-error`, публикует свой JSON как artifact) и одним `merge-and-upload` job'ом (`if: always()`), который скачивает все доступные artifacts, запускает существующие `Main_scraping_Belarus.py` и `upload_to_supabase.py` без изменений в их логике. Единственная правка прикладного кода — headless-режим для Selenium-скрапера Altagamma, включающийся только внутри CI.

**Tech Stack:** GitHub Actions (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`, `browser-actions/setup-chrome@v1`), Python 3.11, pytest (для юнит-теста headless-режима), существующие requests/undetected-chromedriver/Supabase-скрипты проекта.

---

## Task 1: Headless-режим для Altagamma.py в CI

**Files:**
- Modify: `Altagamma/Altagamma.py:1-56`
- Modify: `requirements.txt`
- Create: `tests/test_altagamma_headless.py`

- [ ] **Step 1: Добавить pytest в зависимости**

В `requirements.txt` в самый конец файла добавить:

```txt

# Testing
pytest>=7.4.0
```

Установить: `pip install -r requirements.txt`

- [ ] **Step 2: Написать падающий тест**

Создать `tests/test_altagamma_headless.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "Altagamma"))

import Altagamma


def test_make_options_headless_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    options = Altagamma.make_options()
    assert "--headless=new" in options.arguments


def test_make_options_not_headless_locally(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    options = Altagamma.make_options()
    assert "--headless=new" not in options.arguments
```

- [ ] **Step 3: Запустить тест и убедиться, что он падает**

Run: `pytest tests/test_altagamma_headless.py -v`
Expected: `test_make_options_headless_in_ci` — **FAIL** (`AssertionError: assert '--headless=new' in []`), `test_make_options_not_headless_locally` — **PASS** (текущий `make_options()` никогда не добавляет headless-флаг).

- [ ] **Step 4: Реализовать headless-режим**

В `Altagamma/Altagamma.py` добавить `import os` к существующему блоку импортов (после `from pathlib import Path` на строке 7):

```python
from pathlib import Path
import os
```

Заменить существующую функцию `make_options()` (строки 40-43):

```python
def make_options():
    options = uc.ChromeOptions()
    options.add_argument('--blink-settings=imagesEnabled=false')
    return options
```

на:

```python
def make_options():
    options = uc.ChromeOptions()
    options.add_argument('--blink-settings=imagesEnabled=false')
    if os.environ.get("CI"):
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    return options
```

- [ ] **Step 5: Запустить тест и убедиться, что он проходит**

Run: `pytest tests/test_altagamma_headless.py -v`
Expected: оба теста — **PASS**.

- [ ] **Step 6: Коммит**

```bash
git add Altagamma/Altagamma.py requirements.txt tests/test_altagamma_headless.py
git commit -m "feat: headless Chrome mode for Altagamma scraper in CI"
```

---

## Task 2: Workflow GitHub Actions — сбор, слияние, загрузка

**Files:**
- Create: `.github/workflows/monthly-scrape.yml`

- [ ] **Step 1: Создать файл workflow**

Создать `.github/workflows/monthly-scrape.yml`:

```yaml
name: Monthly scrape and upload

on:
  schedule:
    - cron: '0 3 1 * *'
  workflow_dispatch:
    inputs:
      run_21vek:
        description: 'Запустить парсер 21vek'
        type: boolean
        default: true
      run_altagamma:
        description: 'Запустить парсер Altagamma'
        type: boolean
        default: true
      run_modus:
        description: 'Запустить парсер Modus Keramica'
        type: boolean
        default: true

env:
  PYTHON_VERSION: '3.11'

jobs:
  scrape-21vek:
    if: github.event_name != 'workflow_dispatch' || inputs.run_21vek == true
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - run: pip install -r requirements.txt

      - run: python 21vek/21vek_request.py

      - uses: actions/upload-artifact@v4
        with:
          name: data-21vek
          path: 21vek/data_*_21_vek_Tile.json
          retention-days: 30
          if-no-files-found: warn

  scrape-altagamma:
    if: github.event_name != 'workflow_dispatch' || inputs.run_altagamma == true
    runs-on: ubuntu-latest
    continue-on-error: true
    env:
      CI: 'true'
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - uses: browser-actions/setup-chrome@v1
        with:
          chrome-version: stable

      - run: pip install -r requirements.txt

      - run: python Altagamma/Altagamma.py

      - uses: actions/upload-artifact@v4
        with:
          name: data-altagamma
          path: Altagamma/data_*_altagamma.json
          retention-days: 30
          if-no-files-found: warn

  scrape-modus:
    if: github.event_name != 'workflow_dispatch' || inputs.run_modus == true
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - run: pip install -r requirements.txt

      - run: python Modus_Keramica/Modus.py

      - uses: actions/upload-artifact@v4
        with:
          name: data-modus
          path: Modus_Keramica/data_*_Modus.json
          retention-days: 30
          if-no-files-found: warn

  merge-and-upload:
    needs: [scrape-21vek, scrape-altagamma, scrape-modus]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - run: pip install -r requirements.txt

      - name: Download 21vek data
        uses: actions/download-artifact@v4
        continue-on-error: true
        with:
          name: data-21vek
          path: .

      - name: Download Altagamma data
        uses: actions/download-artifact@v4
        continue-on-error: true
        with:
          name: data-altagamma
          path: .

      - name: Download Modus data
        uses: actions/download-artifact@v4
        continue-on-error: true
        with:
          name: data-modus
          path: .

      - name: Merge and harmonize
        working-directory: MERGED_BELARUS
        run: python Main_scraping_Belarus.py

      - name: Upload to Supabase
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: python dashboard/upload_to_supabase.py

      - uses: actions/upload-artifact@v4
        with:
          name: merged-data
          path: |
            MERGED_BELARUS/products.json
            MERGED_BELARUS/prices.json
          retention-days: 30
```

- [ ] **Step 2: Проверить синтаксис YAML**

Run: `python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/monthly-scrape.yml', encoding='utf-8')); print('OK')"`
Expected: `OK`. Если `yaml` не установлен: `pip install pyyaml` и повторить.

- [ ] **Step 3: Коммит**

```bash
git add .github/workflows/monthly-scrape.yml
git commit -m "feat: monthly GitHub Actions workflow for scraping and Supabase upload"
```

---

## Task 3: Обновить документацию проекта

**Files:**
- Modify: `CLAUDE.md:74-97`

- [ ] **Step 1: Заменить раздел "Ежемесячный мониторинг"**

В `CLAUDE.md` заменить блок (строки 74-87):

```markdown
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
```

на:

```markdown
## Ежемесячный мониторинг

Автоматизировано через `.github/workflows/monthly-scrape.yml` — запускается сам 1-го числа каждого месяца
(парсинг трёх источников → слияние и гармонизация → upsert в Supabase). Ручной перезапуск (например, если
один источник упал) — на вкладке Actions репозитория → **Run workflow**, с чекбоксами по каждому источнику.
Детали и план внедрения — `docs/superpowers/specs/2026-08-22-parser-automation-rollout-plan.md`.

Ручной запуск локально (для отладки конкретного источника):

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
```

- [ ] **Step 2: Коммит**

```bash
git add CLAUDE.md
git commit -m "docs: document monthly scrape automation in CLAUDE.md"
```

---

## Task 4: [РУЧНОЙ ШАГ] Настроить GitHub Secrets

Не выполняется агентом — требует доступа к веб-интерфейсу GitHub с правами администратора репозитория. Выполняется один раз.

- [ ] Открыть `https://github.com/Eugene-Belitskiy/Scraping_Ceramic_Tiles_Belarus/settings/secrets/actions`
- [ ] **New repository secret** → имя `SUPABASE_URL`, значение — как в `dashboard/.env` (`SUPABASE_URL=...`)
- [ ] **New repository secret** → имя `SUPABASE_KEY`, значение — как в `dashboard/.env` (`SUPABASE_KEY=...`)
- [ ] Проверить `https://github.com/settings/notifications` → раздел **Actions** → включено уведомление о падении workflow на email, привязанный к аккаунту (используется автоматически, ничего дополнительно в коде указывать не нужно)

---

## Task 5: Push и сквозная проверка workflow

**Требует явного согласия пользователя перед `git push`** — это первый реальный запуск в облаке с реальными Supabase-секретами.

- [ ] **Step 1: Push веток и файлов из Task 1-3**

```bash
git push origin master
```

- [ ] **Step 2: Ручной запуск через workflow_dispatch**

На вкладке **Actions** репозитория → **Monthly scrape and upload** → **Run workflow** → оставить все три чекбокса включёнными → **Run workflow**.

- [ ] **Step 3: Проверить, что все job'ы завершились ожидаемо**

Открыть запуск: `scrape-21vek`, `scrape-altagamma`, `scrape-modus` — каждый успешен или явно упал (без падения всего workflow); `merge-and-upload` — запустился при любом исходе предыдущих трёх (`if: always()`) и завершился успешно.

- [ ] **Step 4: Проверить artifacts**

В деталях запуска, раздел **Artifacts** — должны быть `data-21vek`, `data-altagamma`, `data-modus` (для успешных job'ов) и `merged-data` (`products.json`, `prices.json`).

- [ ] **Step 5: Проверить отсутствие дублей в Supabase**

В Supabase → Table Editor → `products` и `prices` — посчитать число строк, запустить workflow ещё раз вручную, снова посчитать число строк. Ожидаемо: количество не увеличилось (upsert идемпотентен).

- [ ] **Step 6: (опционально) Симулировать падение одного источника**

Временно закомментировать шаг `run: python 21vek/21vek_request.py` в workflow, закоммитить, запустить `workflow_dispatch`, убедиться что `scrape-altagamma` и `scrape-modus` всё равно доезжают до `merge-and-upload` и Supabase получает их данные, и что на почту приходит письмо о неуспешном job'е `scrape-21vek`. После проверки — вернуть шаг обратно и закоммитить.

---

## Task 6: [РУЧНОЙ ШАГ] Подключить дашборд к Streamlit Community Cloud

Не выполняется агентом — требует аккаунта на share.streamlit.io, привязанного к GitHub. Выполняется один раз.

- [ ] Открыть `https://share.streamlit.io` → **New app**
- [ ] Repository: `Eugene-Belitskiy/Scraping_Ceramic_Tiles_Belarus`, Branch: `master`, Main file path: `dashboard/dashboard.py`
- [ ] **Advanced settings → Secrets** — вставить в TOML-формате:
  ```toml
  SUPABASE_URL = "..."
  SUPABASE_KEY = "..."
  ```
- [ ] **Deploy** — дождаться первого билда, открыть URL приложения и убедиться, что данные подтягиваются из Supabase
- [ ] Сделать любой тривиальный push в `master` (например, из Task 3) и убедиться, что приложение передеплоилось само — без ручных действий на share.streamlit.io

---

## Self-Review

- **Spec coverage:** headless-режим (Task 1), workflow с 3 scrape-jobs + continue-on-error + artifacts (Task 2), merge-and-upload с always() + скачиванием artifacts + запуском существующих скриптов + секретами через env (Task 2), triggers schedule+workflow_dispatch с тремя boolean-инпутами (Task 2), ручные шаги GitHub Secrets и Streamlit Cloud вынесены отдельными задачами с пометкой "ручной шаг" (Task 4, Task 6) — всё покрыто, Казахстан/Россия сознательно не включены (следующий этап по плану-роадмапу).
- **Placeholder scan:** пройден, конкретный код и команды в каждом шаге, без "TBD"/"добавить обработку ошибок" без реализации.
- **Type consistency:** имя функции `make_options()` и её сигнатура одинаковы в Task 1 (реализация) и тесте; имена artifacts (`data-21vek`, `data-altagamma`, `data-modus`, `merged-data`) одинаковы между upload- и download-шагами в Task 2.
