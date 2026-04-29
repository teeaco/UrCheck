# Data Layer (UrCheck)

Этот README описывает data-слой проекта, ключевые методы и минимально нужные Python-файлы.

рабочая локальная БД: `data/chroma_db/`.

## Вклад как Data Engineer

- Спроектирована структура данных рисков, норм и связей (`risks.json`, `norms.json`, `connections.json`).
- Реализован пайплайн сборки базы знаний (`knowledge_base.json`) и поискового индекса (`search_index.json`).
- Настроен векторный слой на Chroma и формат выдачи для RAG.
- Поддержаны скрипты загрузки, проверки и переиндексации данных.

## Структура папки data

### Директории

- `chroma_db/` — рабочая локальная Chroma БД.
- `parsed_data/` — копии подготовленных JSON-артефактов.
- `__pycache__/` — служебный кеш Python.

### Файлы

- `vector_db.py` — основной модуль доступа к векторной БД.
- `main.py` — интерактивный data-менеджер и загрузка данных.
- `chroma_manager.py` — утилитный менеджер загрузки/поиска в Chroma.
- `load_to_chroma.py` — скрипт быстрой загрузки и smoke-проверки.
- `schema_db.py` — dataclass/enum структуры рисков и норм.
- `users.py` — заготовка для пользовательской БД.
- `main_user.py` — вспомогательный пользовательский сценарий.
- `test.py` — тестовый скрипт.
- `__init__.py` — marker файла пакета.

- `risks.json`, `norms.json`, `connections.json`, `knowledge_base.json`, `search_index.json` — основные data-артефакты.
- `doc_authorization.ipynb`, `документация.ipynb` — ноутбуки с документацией и исследованиями.

## Ключевые методы (внутри файлов)

### `vector_db.py` (`ContractRiskDB`)

- `add_risks`, `add_norms`, `add_connections` — загрузка данных в коллекции.
- `search_risks`, `search_norms` — семантический поиск.
- `get_risk_by_id`, `get_norm_by_id`, `get_norm_by_article`, `get_risks_for_norm` — точечные выборки.
- `_format_query_results`, `_format_get_results` — приведение ответов Chroma к единому формату.
- `_build_where_clause` — фильтры для поиска.
- `get_stats`, `clear_database` — обслуживание базы.

### `main.py`

- `DataLoader.load_all_data` — чтение JSON из `parsed_data`.
- `DataLoader.fix_duplicate_ids` — нормализация дубликатов ID.
- `DataLoader.add_to_database` — запись в Chroma через `ContractRiskDB`.
- `SimpleRiskManager.analyze_contract_text` — базовый анализ текста по найденным рискам/нормам.
- `SimpleRiskManager.search_risks_by_query` — удобный поиск рисков.
- `create_risk_manager` / `main` — точки входа для запуска утилиты.

### `chroma_manager.py` (`RiskChromaManager`)

- `add_risks_from_json` — загрузка рисков в коллекцию `contract_risks`.
- `search_risks` — запрос по тексту с optional фильтром категории.
- `get_statistics` — статистика коллекции.

### `load_to_chroma.py`

- `main` — быстрая загрузка, тестовый поиск, запись статистики.

### `schema_db.py`

- `RiskEntry.to_dict`, `NormEntry.to_dict` — сериализация сущностей.
- `_create_search_text` в `RiskEntry` и `NormEntry` — подготовка текста для индексации.

### Для работы backend API (минимум)

- `backend/main.py`
- `backend/config/setting.py`
- `backend/dependencies.py`
- `backend/routes/auth.py`
- `backend/routes/document.py`
- `backend/services/auth.py`
- `backend/services/file_handler.py`
- `backend/services/llm_service.py`
- `backend/models/user.py`
- `backend/models/schemas.py`
- `backend/schemas/auth.py`
- `data/vector_db.py` (используется из `llm_service.py`)

### Для пересборки data-базы/парсинга

- `parsing/parse_gk.py`
- `parsing/risk_extractor.py`
- `parsing/maindb.py`
- `data/vector_db.py`
- `data/main.py`

### Необязательные (утилиты/черновые)

- `backend/services/llm_rag_service.py` (сейчас не основной путь).
- `data/chroma_manager.py`, `data/load_to_chroma.py` (удобные утилиты, но не обязательны для API).
- `data/test.py`, `data/main_user.py`, `data/users.py`, `data/schema_db.py` (вспомогательные/экспериментальные).
