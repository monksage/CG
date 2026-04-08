# Contour Graph — код как граф в БД

## Что это

Форк MCGK. Система из трёх слоёв:

1. **CodeGraph** — SQLite БД, в которой живёт весь код проекта. Не файлы, а ноды графа с рёбрами.
2. **Coordinator** — управляет агентами, claim/release, golden builds, версии нод.
3. **MCGK Gate** — единый прокси между всеми сервисами. Ни один сервис не знает адресов других.

За MCGK Gate стоят сервисы: CodeGraph API, Coordinator, Builder, Tester. Каждый регистрируется через паспорт, общается только по имени.

## CodeGraph — схема БД

### Таблица `nodes`

Нода — минимальная единица кода, содержащая хотя бы одно решение (if/try/loop с условием). Если нет решения — это micro, инлайн в родительскую ноду.

```sql
CREATE TABLE nodes (
    id          TEXT PRIMARY KEY,       -- "auth_check", "calc_r2", не UUID
    code        TEXT NOT NULL,          -- чистый код без импортов
    language    TEXT NOT NULL,          -- "python", "typescript", "rust"
    kind        TEXT NOT NULL,          -- "contour" | "micro" | "config"
    
    -- спеки четырёх уровней гранулярности (данбаровские круги)
    spec_name   TEXT NOT NULL,          -- 1 предложение: "проверка авторизации по JWT"
    spec_ticket TEXT NOT NULL,          -- 10-15 строк: что делает, контракт, edge cases
    spec_summary TEXT NOT NULL,         -- полное описание: входы, выходы, зависимости, решения
    -- spec_as_is = сам код + все три спека выше
    
    -- метаданные
    status      TEXT DEFAULT 'draft',   -- "draft" | "golden" | "deprecated"
    version     INTEGER DEFAULT 1,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    created_by  TEXT DEFAULT '',        -- agent id / task id
    
    -- контракт (чтобы соседи знали что ожидать)
    accepts     TEXT DEFAULT '{}',      -- JSON: параметры
    returns     TEXT DEFAULT '{}',      -- JSON: возвращаемое значение
    
    -- для билда
    imports     TEXT DEFAULT '[]'       -- JSON: ["from datetime import datetime", ...]
);
```

### Таблица `edges`

```sql
CREATE TABLE edges (
    source_id   TEXT NOT NULL REFERENCES nodes(id),
    target_id   TEXT NOT NULL REFERENCES nodes(id),
    edge_type   TEXT NOT NULL,          -- "calls" | "uses" | "extends" | "tests"
    PRIMARY KEY (source_id, target_id, edge_type)
);
```

### Таблица `versions`

```sql
CREATE TABLE versions (
    node_id     TEXT NOT NULL REFERENCES nodes(id),
    version     INTEGER NOT NULL,
    code        TEXT NOT NULL,
    spec_ticket TEXT NOT NULL,
    task_id     TEXT DEFAULT '',
    timestamp   REAL NOT NULL,
    status      TEXT DEFAULT 'draft',   -- "draft" | "tested" | "golden" | "rejected"
    PRIMARY KEY (node_id, version)
);
```

### Таблица `products`

Один граф — много продуктов. Продукт = подмножество нод + свои точки входа.

```sql
CREATE TABLE products (
    id          TEXT PRIMARY KEY,       -- "mvp_crm", "landing_v2"
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    entry_nodes TEXT NOT NULL,          -- JSON: ["app_main", "api_router"]
    created_at  REAL NOT NULL
);

CREATE TABLE product_nodes (
    product_id  TEXT NOT NULL REFERENCES products(id),
    node_id     TEXT NOT NULL REFERENCES nodes(id),
    PRIMARY KEY (product_id, node_id)
);
```

## CodeGraph API — сервис за MCGK

Регистрируется в MCGK как `codegraph`. Агенты обращаются только через гейт.

### Чтение

```
GET /node/{id}                          -- код + спеки + контракт
GET /node/{id}?depth=ticket             -- только spec_ticket + accepts/returns (для соседей)
GET /node/{id}?depth=name               -- только spec_name (для дальних)
GET /node/{id}/versions                 -- все версии ноды
GET /node/{id}/neighbors                -- рёбра + спеки соседей на уровне ticket
GET /graph?product={id}                 -- полный граф продукта (id + edges, без кода)
GET /search?query=auth                  -- поиск по spec_name и spec_ticket
```

### Запись

```
POST   /node                            -- создать ноду (код + спеки + контракт)
PUT    /node/{id}                       -- обновить ноду (создаёт новую версию)
POST   /node/{id}/promote               -- draft → golden (только после тестов)
POST   /node/{id}/reject                -- draft → rejected
DELETE /node/{id}                       -- только если нет входящих рёбер
POST   /edge                            -- добавить ребро
DELETE /edge                            -- убрать ребро
```

### Реиспользование

```
GET /similar?spec="{описание}"          -- поиск существующих нод по описанию
```

Координатор вызывает `/similar` ПЕРЕД тем как разрешить агенту создать новую ноду. Если есть подходящая — агент получает её id и должен обосновать зачем писать новую.

## Coordinator — сервис за MCGK

Регистрируется как `coordinator`. Управляет агентами и процессом.

### Claims (из ida-procon)

```
POST /claim     {"node_id": "auth_check", "agent_id": "soldier_03"}
POST /release   {"node_id": "auth_check"}
GET  /claimed                           -- список захваченных нод
```

TTL на claim — 600 секунд. Истёк — автоматический release. Агент упал — нода свободна.

### Назначение задач

```
GET  /next-task?product={id}            -- следующая незакрытая нода для работы
POST /submit    {"node_id": "...", "agent_id": "...", "task_id": "..."}
```

`/next-task` выбирает по аналогии с `/next-entry` в ida-procon: нода с наибольшим количеством непокрытых соседей. Самая "богатая" незакрытая зона графа.

### Контексты для агентов (данбаровские круги)

Когда координатор выдаёт задачу агенту, он формирует контекст:

- **Своя нода** — spec_as_is (код + все спеки + контракт)
- **Прямые соседи (K=2-3)** — spec_summary (полное описание без кода)
- **Соседи соседей (10-15)** — spec_ticket (15 строк)
- **Остальной граф (50-150)** — spec_name (одно предложение)

Агент получает ровно тот объём контекста, который ему нужен. Не больше.

## Builder — сервис за MCGK

Регистрируется как `builder`.

```
POST /build             {"product": "mvp_crm"}
POST /build_contour     {"node_id": "auth_check"}
POST /test_build        {"node_id": "auth_check", "version": 3}
```

### Что делает build

1. Получает граф продукта из codegraph (`GET /graph?product=X`)
2. Для каждой ноды берёт golden-версию кода (`GET /node/{id}`)
3. Резолвит зависимости, генерирует импорты из манифестов
4. Собирает файлы в формате целевого фреймворка
5. Запускает бандлер/компилятор
6. Возвращает результат: ok или ошибки

### Что делает test_build

То же самое, но подставляет конкретную версию конкретной ноды вместо golden. Остальной граф — golden. Изолированный тест одного изменения.

### Что делает build_contour

Собирает standalone-запускаемый фрагмент: одна нода + её прямые зависимости. Для быстрой проверки без сборки всего продукта.

## Tester — сервис за MCGK

Регистрируется как `tester`.

```
POST /test              {"product": "mvp_crm"}
POST /test_node         {"node_id": "auth_check", "version": 3}
```

Тестер получает собранный артефакт от builder, прогоняет тесты. Тесты — это тоже ноды в графе (edge_type = "tests"). Результат возвращается координатору.

## Жизненный цикл ноды

```
1. Координатор даёт агенту задачу (/next-task)
2. Агент проверяет есть ли похожая нода (/similar)
3. Если нет — агент claim'ит зону, пишет код, POST /node
4. Если есть — агент реюзает или обосновывает зачем новая
5. Builder делает test_build с новой версией
6. Tester прогоняет тесты
7. Если ок — координатор делает promote (draft → golden)
8. Если нет — координатор отдаёт субагенту на починку
9. Субагент читает контур целиком, чинит, PUT /node/{id}
10. Цикл 5-9 повторяется
11. Старый golden — deprecated, новый — golden
```

## Жизненный цикл версий (турнир)

Когда несколько агентов решают одну задачу параллельно:

```
A (golden) → [B1, B2, B3] (draft) → C (golden)

1. Каждая Bi проходит test_build с golden A и C
2. Которая прошла тесты — кандидат
3. Из кандидатов выбирается по минимальной сложности
4. Победитель → golden. Остальные → rejected
5. Rejected не удаляются сразу (failure-indexed memory)
6. TTL на rejected — 7 дней, потом мусорщик чистит
```

## Garbage collection

- Нода без входящих рёбер + без golden статуса + старше TTL → удалить
- Rejected версии старше 7 дней → удалить
- Claims с истёкшим TTL → автоматический release

## Проекция для человека

Человек не видит граф нод. Человек видит:

```
GET /human/product/{id}                 -- карта контуров с spec_ticket
GET /human/product/{id}/contour/{name}  -- spec_summary + код на человеческом языке
GET /human/product/{id}/export          -- полный проект в виде файлов (для скачивания)
```

`/export` — билдер собирает нормальный проект с файлами, папками, README. Это проекция, не источник правды. Источник правды — граф в БД.

## Bootstrap (курица → яйцо)

Первая версия пишется руками, как обычный код:

```
Phase 0: Написать MCGK + CodeGraph API + Coordinator + Builder + Tester
         Обычные файлы, обычный git. Это зародыш.

Phase 1: Система запущена. Первый продукт собирается в графе
         силами агентов через API. Зародыш не трогаем.

Phase 2: Код зародыша мигрируется в собственную БД.
         С этого момента система модифицирует сама себя
         через свой же API. Змея кусает хвост.
```

## Порядок реализации Phase 0

1. Форкнуть MCGK → это уже готовый гейт
2. Написать CodeGraph API (SQLite + FastAPI, ~200 строк) → зарегистрировать в MCGK
3. Написать Coordinator (claim/release из ida-procon + /next-task) → зарегистрировать в MCGK
4. Написать Builder (обход графа → генерация файлов → запуск бандлера) → зарегистрировать в MCGK
5. Написать Tester (запуск тестов на собранном артефакте) → зарегистрировать в MCGK
6. Написать агентские промты (солдат, сержант) по образцу ida-procon
7. Собрать первый продукт: API на три эндпоинта, целиком из контуров в графе

## Зачем всё это

Файлы — костыль под человеческую навигацию.
Агентам нужен граф с API, а не файловая система.
Один граф — много продуктов.
Контур — единица смысла, а не единица хранения.
Код хранится, версионируется и переиспользуется на уровне решений, а не на уровне текста.