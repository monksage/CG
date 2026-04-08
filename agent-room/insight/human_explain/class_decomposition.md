# Как мы пришли к декомпозиции классов

## Откуда мы начали

Contour Graph хранит код как граф нод. Нода — это функция с хотя бы одним решением (if/try/loop). Ноды связаны рёбрами (кто кого вызывает). Builder собирает ноды обратно в запускаемый код.

Мы загрузили в граф процедурный код (SignalProcessor, unit_divide) и всё работало. Агент получал контекст через /context, видел соседей, писал код. Данбар подтвердился двумя экспериментами — сфокусированный контекст даёт лучший результат чем полный файл.

Потом мы попробовали собрать код обратно через build.py и увидели проблему: метод класса содержит `self`, но вне класса `self` не определён. Код синтаксически валиден, но не запустится. Так мы поняли что граф не умеет работать с классами.


## Первая реакция — классы не нужны

Первая мысль была простая: классы — это проекция, как файлы. Файлы мы уже убрали. Классы тоже можно убрать. Развернуть все методы в обычные функции, self заменить на явные аргументы, наследование заменить на вызовы. В рантайме всё равно всё плоское.

Мы проверили это на 900 строках кода с 13 паттернами проектирования (Singleton, Factory, Strategy, Observer, Decorator, Builder, State, Iterator, Proxy, Chain of Responsibility, Adapter, Template Method, Command). Каждый паттерн разворачивался в функции. Strategy — вообще идеально: каждый класс-стратегия это одна функция `(total) -> float`. State Machine — таблица переходов вместо шести классов. Chain of Responsibility — список функций вместо linked list объектов.

Всё разворачивалось. Теоретически.


## Где это сломалось

PyQt. `class MyWindow(QMainWindow)` — ты наследуешь от класса Qt. Qt ожидает объект. Когда пользователь нажимает кнопку, Qt вызывает `self.on_click()` на твоём объекте. Ты не можешь дать Qt функцию вместо класса. Фреймворк построен на наследовании — это его контракт.

То же самое с Django, Flask и любым фреймворком, который говорит "унаследуйся от моего класса и переопредели методы". Это не абстракция для удобства — это требование фреймворка.

Значит "все классы — проекция" не работает. Некоторые классы обязаны оставаться классами.


## Твоя теория: тесные и нетесные связи

Ты предложил разделить содержимое класса на две категории.

Тесные элементы — неотделимы от класса. Без них класс не существует как класс:
- строка `class MyWindow(QMainWindow):` — декларация и наследование
- атрибуты класса: `path_to_origin = pyqtSignal(str)`
- атрибуты экземпляра: то что в `__init__` присваивается к `self`

Нетесные элементы — методы, которые можно вынести:
- если метод использует `self` только чтобы читать атрибуты — его можно переписать как функцию с явными аргументами
- `@staticmethod` — уже функция, просто лежит внутри класса
- большие методы дробятся на подметоды, часть из которых может стать статическими

Флоу декомпозиции который ты описал:
1. Собрать атрибуты экземпляра и методы
2. Статические методы вынести сразу
3. Большие методы раздробить, подметоды которые не зависят от self — вынести
4. Пересчитать какие атрибуты ещё нужны после выноса
5. Сформировать тесную ноду — инициализатор атрибутов
6. Сформировать тесную ноду — блок атрибутов класса

При сборке builder берёт тесные ноды и собирает из них "шапку" класса, а вынесенные функции ставит рядом.


## Проблема: это работает для конкретных случаев, но не обобщается

Твоя теория хорошо работает для классов типа SignalProcessor или Qt-виджета. Но что делать с:
- Decorator pattern (класс оборачивает другой класс)
- Proxy (ленивая инициализация + контроль доступа)
- Command (хранит state для undo)
- State Machine (6 классов, каждый с 5 методами, большинство — однострочные отказы)

Для каждого паттерна нужен свой подход. Это не масштабируется — нельзя писать правило на каждый паттерн.


## Что предложил исследователь: три подхода

Мы запустили Опуса-исследователя с заданием: предложи три разных способа декомпозиции классов для графа. Он прочитал твою теорию, наши обсуждения, описание системы, и предложил три подхода. Каждый — полное решение с примерами на тех же 900 строках.


### Подход A: полное растворение

Никаких классов в графе. Вообще. Каждый метод становится функцией. `self` заменяется на явный аргумент `state`:

```
# было
def confirm(self):
    self._state.confirm(self)

# стало
def confirm_order(state: OrderData) -> OrderData:
    return dispatch_order_action(state, "confirm")
```

`OrderData` — это не класс, а схема данных (описание полей: order_id, items, status и т.д.). Отдельная нода в графе без кода — только описание типа.

Плюсы: максимальная реиспользуемость. Каждая функция полностью самостоятельна. Тестируется без создания объекта — просто передай данные.

Минусы: builder должен уметь собрать класс обратно из функций. Это сложно — нужно заменить `state.x` обратно на `self.x`, обернуть функции в методы, восстановить `__init__` из схемы данных. Builder становится очень умным.

Из 900 строк получается ~108 нод. Максимальная гранулярность.


### Подход B: разрезание по контрактам

Класс разрезается не на отдельные методы, а на группы методов, которые вместе решают одну задачу.

Пример: класс Order. Он делает две вещи — управляет статусом (confirm/pay/ship/cancel) и считает деньги (raw_total/total). Это два "контракта". Методы статуса — одна группа. Методы расчёта — другая. Каждая группа становится набором нод. "Шапка" класса (декларация, __init__, атрибуты) остаётся как отдельная нода.

`self` сохраняется. Методы остаются методами. Но класс разрезан на логические куски.

Плюсы: умеренная сложность. Builder проще — он собирает шапку + методы, не нужно переписывать self.

Минусы: нужно вручную определять "контракты" — какие методы к какой группе относятся. Это субъективное решение. Два разных агента разрежут по-разному.

Из 900 строк получается ~70 нод.


### Подход C: двойное представление

Каждый метод — отдельная нода в графе (как в подходе A). Но `self` остаётся (как в подходе B). Плюс добавляется новая сущность — class_template.

class_template — это не код. Это JSON-рецепт сборки:

```json
{
  "class_name": "Order",
  "bases": ["object"],
  "class_attributes": [{"name": "_counter", "value": "0"}],
  "method_order": ["__init__", "confirm", "pay", "ship", "cancel", "_set_state", "raw_total", "total", "__repr__"]
}
```

Рецепт говорит builder'у: "возьми эти методы-ноды, сложи в класс Order, расставь в таком порядке, добавь атрибут _counter". Builder делает ровно это — берёт код каждого метода-ноды, добавляет отступ в 4 пробела, оборачивает в `class Order:`. Всё.

Связь между методом и классом — ребро `member_of`. Метод `order_confirm` member_of `Order`. Это значит builder знает что этот метод нужно вставить внутрь класса Order.

Плюсы: builder тривиальный — indent + concatenate. Ноль потери информации — класс восстанавливается точно как был. Фреймворки работают из коробки (PyQt, Django) — builder собирает настоящий класс с наследованием.

Минусы: методы с `self` менее реиспользуемы чем чистые функции. Но для ключевых методов можно создать "компаньон" — свободную функцию-ноду которая делает то же самое без self. Метод вызывает компаньона, компаньон реиспользуется.

Из 900 строк получается ~89 нод + 18 templates.


## Рекомендация исследователя

Начать с подхода C. Причины:

Первая — builder. У нас builder это скрипт на 86 строк. Подход A требует builder который умеет переписывать `state.x` обратно в `self.x` — это отдельный проект. Подход C требует indent + concatenate — это уже почти работает.

Вторая — фреймворки. Подход C собирает настоящие классы. PyQt, Django — всё работает без специальной обработки.

Третья — обратимость. Из подхода C можно восстановить оригинальный класс точно. Из подхода A — только приблизительно (builder аппроксимирует).

Четвёртая — постепенность. Можно начать с C, а для конкретных случаев применять A. Strategy-классы (которые по сути функции) — растворять полностью. Qt-виджеты — оставлять как template + методы. Не нужно выбирать один подход на всё.


## Что мы узнали про версионирование шаблонов

Это следующий вопрос, который мы задали исследователю: если метод-нода получает новую версию (v2), что происходит с class_template?

Ответ: ничего. Template — это рецепт. Рецепт говорит "в классе Order есть метод confirm". Какая версия confirm — решает builder в момент сборки. Если мы собираем golden-продукт, builder берёт golden-версию confirm. Если тестируем draft, builder берёт draft-версию confirm. Template не меняется.

Template версионируется только когда меняется структура класса: добавили новый метод, удалили метод, поменяли наследование. Это бывает редко. Изменения кода методов — часто. Значит template стабильный якорь, а методы меняются вокруг него.

Ребро `member_of` указывает на ноду (identity), а не на конкретную версию. "confirm принадлежит Order" — это факт независимо от того, какая версия confirm сейчас golden.


## Результат эксперимента 08: какой подход даёт лучший Данбар-контекст

Мы запустили эксперимент. Три инстанса codegraph на разных портах, в каждом — Order декомпозирован одним из трёх подходов. Девять солдат (по три на подход) получили одну и ту же задачу: написать функцию process_refund. Каждый солдат видел только Данбар-контекст из своего графа. Оценка по пяти осям: управление статусом, платёж, события, edge cases, сложность кода.

Результаты (медиана по трём солдатам на подход):

Подход A (полное растворение): 19 из 25. Подход B (по контрактам): 17 из 25. Подход C (двойное представление): 18 из 25.

Подход A победил по медиане — но интереснее детали.

Самый ровный — подход A. Все три солдата написали почти одинаковый код (разброс 1 балл). Функциональный стиль не оставляет места для разночтений: state — это dict, переходы — через dispatch, всё явно. Агенту не нужно угадывать что внутри self.

Самый высокий пик — подход B. Один из трёх солдат (B2) набрал 24 из 25 — лучший результат среди всех девяти. Он понял spec_summary метода `_set_state`, увидел связь между State и Observer паттернами, и написал код с накоплением частичных возвратов и раздельными событиями для полного и частичного refund. Но два других солдата (B1, B3) набрали по 17 — они не вчитались в спеки и написали generic код.

Подход C — середина. Парадокс: у C было больше всего информации в Данбар-пакете (10 нод на depth 1, у A — 5, у B — 6). Но результат средний. Причина: на depth 0 (самый детальный уровень, целевая нода) у C лежал JSON-шаблон — метаданные без кода. А у A — реальный код dispatch-функции. А у B — реальный код __init__ класса.

Главный вывод эксперимента: то что лежит на depth 0 (полный код целевой ноды) важнее чем количество нод на depth 1. Код якорит понимание агента. Метаданные — нет. Если используем подход C, entry point для /context должен быть метод-нодой (с кодом), а не template-нодой (с JSON).

Второй вывод: подход A даёт предсказуемость, подход B даёт потенциал. A — для задач где важна надёжность (9 из 10 солдат напишут ок). B — для задач где важен лучший результат (1 из 10 напишет отлично, остальные — средне).


## Что узнал исследователь про версионирование шаблонов (расширение)

Исследователь дополнил своё исследование секцией про то, как версионирование работает с class_template в подходе C. Разобрал четыре сценария.

Первый сценарий — один агент меняет один метод. Самый простой. Агент создаёт новую версию метода confirm (v2). Template не трогается. Builder при test_build берёт confirm v2 + все остальные методы golden. Если тесты прошли — confirm v2 становится golden. Template всё время оставался неизменным.

Второй сценарий — два агента меняют два разных метода одного класса одновременно. Агент A меняет confirm, агент B меняет pay. Каждый тестируется независимо: confirm v2 + остальные golden, pay v2 + остальные golden. Оба прошли, оба promote. Но потом нужна проверка комбинации: confirm v2 + pay v2 + остальные golden. Потому что новый confirm может конфликтовать с новым pay, даже если каждый по отдельности работает.

Третий сценарий — один агент меняет метод, другой добавляет новый метод. Тут метод и структура меняются параллельно. Изменение метода — контентное (template не трогается). Добавление метода — структурное (template получает v2 с новым method_order). Они не конфликтуют: контентное и структурное — ортогональные изменения.

Четвёртый сценарий — два агента оба добавляют разные новые методы. Оба стартовали от template v1. Каждый создал свой template v2. Это настоящий конфликт. Решение: если изменения непересекающиеся (оба добавили по методу в method_order) — автоматический мерж в template v3 (просто добавить оба метода). Если изменения пересекаются (оба поменяли bases или один и тот же атрибут) — эскалация человеку или сержанту. Исследователь сравнил это с git merge — для структурных JSON-данных большинство мержей тривиальны.


## Гибрид A+B: стабильный пол с высоким потолком

После эксперимента 08 стало ясно что подход A даёт стабильность (все солдаты пишут ровно на 19/25), а подход B даёт потенциал (один солдат написал на 24/25, но два других — на 17/25). Возник вопрос: можно ли получить и то и другое одновременно?

Идея оказалась проще чем казалась. Граф и спеки — это два разных слоя, которые не мешают друг другу.

Граф — это структура. Как ноды хранятся, как они связаны рёбрами, как builder их собирает обратно в код. Это слой хранения. Тут мы используем подход A: все методы развёрнуты в функции, state явный, dispatch явный. Это даёт стабильность — агент видит код без двусмысленностей.

Спеки — это контекст. Что агент читает когда получает Данбар-пакет. Это слой понимания. Тут мы можем добавить информацию в стиле подхода B: какому паттерну принадлежит функция, какие у неё "сёстры" (альтернативные реализации того же контракта), какие мосты она строит между паттернами, какие инварианты должны выполняться.

Пример. Функция `order_confirm` в подходе A хранится просто: принимает OrderState, возвращает OrderState, внутри меняет статус. Обычный spec_summary говорит ровно это: "переводит заказ из DRAFT в CONFIRMED". Агент получает это и пишет корректный но простой код.

Обогащённый spec_summary говорит больше: "это переход State-паттерна DRAFT→CONFIRMED. Один из пяти переходов (confirm, pay, ship, deliver, cancel). Роутится через dispatch_order_action. После перехода публикует событие order_status_changed через publish_event — на него подписаны обработчики уведомлений и возвратов. Из DRAFT допустимы только два перехода: confirm и cancel."

Агент, прочитавший обогащённый спек, понимает не только что функция делает, но как она вписывается в систему. Это то что сделал солдат B2 в эксперименте — он увидел связь между State и Observer и написал код, который правильно интегрировался с обоими паттернами.

Обогащать имеет смысл не все ноды, а только те что стоят на границах паттернов — dispatch-точки, мосты между паттернами, publisher/subscriber, entry-точки пайплайнов. Это примерно 25% от всех нод. Остальные 75% — простые функции, которым хватает обычного спека.

Турнир делает это безрисковым. На задачу которая затрагивает обогащённую ноду координатор запускает двух солдат: один с обычным Данбар-контекстом, второй с обогащённым. Оба пишут код, оба проходят тесты. Выбирается лучший. Если обогащённый солдат написал лучше — берём его (потолок B2). Если обогащённый солдат написал хуже или запутался — берём базового (пол A). Мы платим токенами за второго солдата (~25% больше на задачах с обогащёнными нодами), но гарантируем что результат никогда не хуже чем чистый подход A.

Единственная реальная цена — поддержание обогащённых спеков. Когда паттерн меняется (например, кто-то переписал event-систему), все спеки которые упоминают publish_event устаревают. Нужен периодический sweep — агент проходит по обогащённым спекам, проверяет актуальность, обновляет. Это не опционально — без этого обогащённые спеки станут "красивой ложью" которая запутает агентов.


## Версионирование: что мы построили

Параллельно с исследованием OOP мы добавили в codegraph систему версий. Это конкретный код, не теория — капрал написал, прошёл верификацию 12 из 12, работает.

Раньше нода хранила одну версию кода. PUT перезаписывал ноду — старый код терялся. Не было понятия "черновик" или "стабильная версия". Агент мог случайно сломать ноду и откатиться было некуда.

Теперь рядом с таблицей nodes появилась таблица versions. Каждое изменение кода — новая строка в versions с номером версии и статусом.

Жизненный цикл версии: draft → golden (или rejected) → deprecated.

Draft — черновик. Агент написал новый код, он лежит как draft. Его ещё не приняли, никто кроме автора его не увидит. GET /node/{id} по умолчанию возвращает golden-версию — draft виден только если golden не существует.

Golden — рабочая версия. Принята, протестирована, используется для сборки и в Данбар-контексте. Когда агент хочет узнать код ноды, он видит golden.

Rejected — отклонена. Не прошла тесты или ревью. Лежит в истории как напоминание "так делать не надо" (помним failure-indexed memory из essence — отклонённые версии хранятся 7 дней перед удалением).

Deprecated — устарела. Была golden, но её заменила новая golden. Предыдущая версия переходит в deprecated. Не удаляется сразу — остаётся в истории.

Как это работает технически. Таблица nodes осталась как была, со всеми колонками (code, specs, contracts, status). Она работает как кэш активной версии. Когда вызывается promote (draft → golden), codegraph копирует поля из promoted версии в ноду. Все существующие read-пути (GET /node, GET /context, GET /search) читают из nodes — им не нужно знать про versions. Versions — это source of truth и аудит-лог, а nodes — быстрый кэш для чтения.

При миграции все 66 существующих нод получили version 1 со статусом golden и task_id "migration". Это idempotent — повторный запуск не создаёт дубликатов.

PUT /node/{id} убран. Вместо него — POST /node/{id}/version (создать новый черновик). Это сознательное решение: нельзя "перезаписать" ноду, можно только создать новую версию. История всегда сохраняется.

Откат тоже через новую версию. Если v2 golden оказалась плохой и нужно вернуться к v1 — создаёшь v3 с кодом из v1, promote v3. В истории видно: v1 golden → v2 golden → v2 deprecated → v3 golden (содержит код v1). Всё явно, всё аудируемо.

Пять решений, которые капрал поднял и мы закрепили:

Первое — nodes как кэш. Капрал предложил не убирать code/specs из таблицы nodes, а синхронизировать при promote/reject. Альтернатива (убрать колонки) потребовала бы переписать все read-запросы на JOIN с versions. Кэш — проще, быстрее, нулевой blast radius.

Второе — rejected-only ноды. Если у ноды единственная версия и она rejected, GET /node/{id} возвращает ноду со status "rejected". Не 404 — нода существует. Вызывающий сам решает что делать с rejected нодой.

Третье — при создании нового draft, если golden нет, draft синхронизируется в nodes-кэш. Иначе кэш показывал бы устаревшую rejected-версию вместо свежего draft.

Четвёртое — при удалении ноды сначала удаляются все её версии (явный DELETE FROM versions WHERE node_id=?), потом сама нода. Без каскадов — всё explicit.

Пятое — task_id остаётся свободным текстом. Координатора ещё нет, формат задач не определён. Когда появится — решим.


## Как выглядит граф для агента: три подхода на примере Order

Ниже — реальные данные из эксперимента 08. Три инстанса CodeGraph, в каждом класс Order декомпозирован одним из трёх подходов. Для каждого вызван `GET /context/{entry_node}` — это то, что агент получает как Данбар-пакет. Данные не отредактированы — скопированы из API.


### Подход A: полное растворение (11 нод, 12 рёбер)

Entry node: `dispatch_order_action`

**Depth 0 — полный код + спеки:**

```
dispatch_order_action
  code:
    def dispatch_order_action(state, action, event_bus, state_registry):
        """Route action to correct OrderState handler based on current_state_name."""
        name = state["current_state_name"]
        handler = state_registry.get(name)
        if handler is None:
            raise ValueError("Unknown state: " + name)
        method = getattr(handler, action, None)
        if method is None:
            raise ValueError("Unknown action: " + action)
        return method(state, event_bus, order_set_state)

  spec_ticket: Central dispatcher replacing State pattern delegation in the
    original Order class. Each action method (confirm/pay/ship/cancel) delegates
    here. Looks up current OrderState handler from registry by current_state_name,
    invokes the action. Single choke point for all state machine transitions.

  accepts: {state: OrderData, action: str, event_bus: EventBus, state_registry: dict}
  returns: {result: OrderData}
```

**Depth 1 — spec_summary + accepts/returns (5 нод):**

```
order_confirm    — order_confirm(state, event_bus, state_registry) -> dict.
                   Calls dispatch_order_action(state, confirm, ...).
                   Raises InvalidStateTransition if not in valid source state.

order_pay        — order_pay(state, event_bus, state_registry) -> dict.
                   Calls dispatch_order_action(state, pay, ...).

order_ship       — order_ship(state, event_bus, state_registry) -> dict.
                   Calls dispatch_order_action(state, ship, ...).

order_cancel     — order_cancel(state, event_bus, state_registry) -> dict.
                   Calls dispatch_order_action(state, cancel, ...).

order_set_state  — order_set_state(state, new_state_name, new_status, event_bus) -> dict.
                   Captures old_status. Returns {**state, current_state_name: ...,
                   status: ...}. Calls event_bus.publish("order_status_changed",
                   order_id=..., old=old_status, new=new_status).
                   Does not mutate input.
```

**Depth 2 — только spec_ticket (1 нода):**

```
order_data       — "Data schema for Order entity. The Order class is dissolved into
                   free functions; all accept an explicit OrderData state parameter."
```

**Depth 3 — только имена (4 ноды):**

```
create_order, format_order, order_raw_total, order_total
```

**Граф:**

```
  order_confirm ──calls──→ dispatch_order_action ──dispatches──→ order_set_state
  order_pay ─────calls──→ dispatch_order_action                     │
  order_ship ────calls──→ dispatch_order_action                writes_state
  order_cancel ──calls──→ dispatch_order_action                     │
                                                                    ▼
  create_order ──writes_state──→ order_data ←──reads_state── order_raw_total
                                    ▲                              ▲
                                    │                            calls
                               reads_state                         │
                                    │                         order_total
                               format_order ──calls──→ order_total
```

Что видит агент: на depth 0 — реальный Python-код диспетчера. Видно как работает state machine: берём handler из registry, вызываем action. Все action-функции на depth 1 — видны их сигнатуры и что они делают. Стиль полностью функциональный — всё через dict, никакого self.


---


### Подход B: разрезание по контрактам (9 нод, 12 рёбер)

Entry node: `order_shell`

**Depth 0 — полный код + спеки:**

```
order_shell (kind: class_shell)
  code:
    class Order:
        """Main entity. Uses State for status management."""
        _counter: int = 0

        def __init__(self):
            Order._counter += 1
            self.order_id: int = Order._counter
            self.items: list[OrderItem] = []
            self.status: OrderStatus = OrderStatus.DRAFT
            self.discount_strategy: DiscountStrategy = NoDiscount()
            self.created_at: datetime = datetime.now()
            self.metadata: dict[str, Any] = {}
            self._state: OrderState = DraftState()

  spec_ticket: Order is the central aggregate entity. Two contracts:
    (1) state management — confirm, pay, ship, cancel, delegated to OrderState
    via State pattern. (2) order data — items, totals, metadata.
    The class-shell contains the irreducible core: declaration, counter, __init__.

  spec_summary: __init__ initializes: order_id (auto-increment), items ([]),
    status (DRAFT), discount_strategy (NoDiscount()), created_at, metadata ({}),
    _state (DraftState()). Dependencies: OrderStatus, OrderState, DiscountStrategy.
```

**Depth 1 — spec_summary + accepts/returns (6 нод):**

```
order_confirm    — Bound method on Order. self._state.confirm(self).
                   State object calls back into Order._set_state().
                   Indirectly publishes order_status_changed via EventBus.

order_pay        — Bound method. self._state.pay(self).
                   OrderState calls back _set_state(PaidState(), OrderStatus.PAID).

order_ship       — Bound method. self._state.ship(self).
                   PaidState calls back _set_state(ShippedState(), OrderStatus.SHIPPED).

order_cancel     — Bound method. self._state.cancel(self).
                   Calls back _set_state(CancelledState(), OrderStatus.CANCELLED).

order_set_state  — Bound method. Parameters: self, state (OrderState), status (OrderStatus).
                   (1) snapshot old = self.status, (2) assign self._state and self.status,
                   (3) EventBus().publish("order_status_changed", order_id=..., old=..., new=...).
                   Tagged bridge: intersection of State pattern and Observer pattern.

order_repr       — Bound method. Returns f-string with order_id, status.name,
                   len(items), self.total (invokes discount chain).
```

**Depth 2 — только spec_ticket (1 нода):**

```
order_total      — "Extracted pure function. Composes order_raw_total with
                   a DiscountStrategy to yield amount owed. Supports all variants:
                   NoDiscount, PercentDiscount, FixedDiscount, TieredDiscount."
```

**Depth 3 — только имена (1 нода):**

```
order_raw_total
```

**Граф:**

```
  order_confirm ──binds──→ order_shell ←──binds── order_set_state
  order_pay ─────binds──→ order_shell ←──binds── order_repr
  order_ship ────binds──→ order_shell
  order_cancel ──binds──→ order_shell

  order_confirm ──calls──→ order_set_state
  order_pay ─────calls──→ order_set_state
  order_ship ────calls──→ order_set_state
  order_cancel ──calls──→ order_set_state

  order_repr ────calls──→ order_total ──calls──→ order_raw_total
```

Что видит агент: на depth 0 — настоящий `__init__` класса Order. Видно все атрибуты: items, status, discount_strategy, _state. Агент понимает что Order — это объект с `self`, а не dict. Все bound-методы на depth 1 — видно что они делегируют через `self._state`. Ключевой спек — `order_set_state` (bridge между State и Observer).


---


### Подход C: двойное представление (13 нод, 15 рёбер)

Entry node: `order_template`

**Depth 0 — полный код + спеки:**

```
order_template (kind: class_template)
  code: (пустой — это не код, а рецепт)

  spec_ticket: Class template for Order. Structure: class Order, bases=[],
    _counter:int=0. Method order: __init__, confirm, pay, ship, deliver, cancel,
    _set_state, raw_total, total, __repr__. Uses State pattern for lifecycle,
    Strategy pattern for discounts, Observer pattern (EventBus) for notifications.

  spec_summary: Template metadata: {class_name: 'Order', bases: ['object'],
    metaclass: null, decorators: [], class_attributes: [{name: '_counter',
    value: '0', type: 'int'}], method_order: [...], docstring: '...'}.
    Dependencies: OrderItem, OrderStatus, OrderState hierarchy,
    DiscountStrategy hierarchy, EventBus.
```

**Depth 1 — spec_summary + accepts/returns (10 нод):**

```
order_init       — Constructor. Creates: order_id (auto-increment), items ([]),
                   status (DRAFT), discount_strategy (NoDiscount), created_at,
                   metadata ({}), _state (DraftState).

order_confirm    — Delegates to self._state.confirm(self). State object calls
                   _set_state() or raises InvalidStateTransition via _deny().

order_pay        — Delegates to self._state.pay(self). Valid only in ConfirmedState.

order_ship       — Delegates to self._state.ship(self). Valid only in PaidState.

order_deliver    — Delegates to self._state.deliver(self). Valid only in ShippedState.

order_cancel     — Delegates to self._state.cancel(self). Allowed in Draft,
                   Confirmed, Paid. Denied in Shipped, Delivered.

order_set_state  — Internal transition. Parameters: state (OrderState), status
                   (OrderStatus). Stores old=self.status, sets new state/status.
                   Calls EventBus().publish("order_status_changed", order_id=...,
                   old=..., new=...). Integration point: State + Observer.

order_raw_total  — Property. sum(i.price * i.quantity for i in self.items).
                   Stateless equivalent: calc_raw_total(items).

order_total      — Property. self.discount_strategy.calculate(self.raw_total).
                   Stateless equivalent: calc_total(items, discount_strategy).

order_repr       — Returns Order(id=..., status=..., items=..., total=...).
                   Calls order_total → order_raw_total → discount_strategy.
```

**Depth 2 — только spec_ticket (2 ноды):**

```
calc_raw_total   — "Companion free function for order_raw_total. Sums
                   price*quantity for all items without self/Order instance."

calc_total       — "Companion free function for order_total. Takes items list
                   and DiscountStrategy, returns final total without Order instance."
```

**Граф:**

```
  order_init ─────member_of──→ order_template ←──member_of── order_set_state
  order_confirm ──member_of──→ order_template ←──member_of── order_raw_total
  order_pay ─────member_of──→ order_template ←──member_of── order_total
  order_ship ────member_of──→ order_template ←──member_of── order_repr
  order_deliver ─member_of──→ order_template
  order_cancel ──member_of──→ order_template

  order_total ───calls──→ order_raw_total
  order_repr ────calls──→ order_total

  calc_raw_total ──alias_of──→ order_raw_total
  calc_total ──────alias_of──→ order_total
  calc_total ──────calls─────→ calc_raw_total
```

Что видит агент: на depth 0 — JSON-рецепт. Нет кода, но есть полная структура класса: имя, атрибуты, порядок методов, зависимости. На depth 1 — все 10 методов с spec_summary. Это самый широкий обзор из трёх подходов — агент видит весь класс целиком. Но нет якоря в виде реального кода.


---


### Сравнение: что агент реально получает

```
                    Подход A            Подход B            Подход C
                    (растворение)       (контракты)         (двойное)
─────────────────────────────────────────────────────────────────────────
Depth 0             Python-код          Python-код          JSON-метаданные
                    dispatch-функция    __init__ класса     template рецепт

Depth 1 (кол-во)    5 нод               6 нод               10 нод
Depth 1 (стиль)     fn(state) -> state  self.method()       self.method()

Depth 2 (кол-во)    1 нода              1 нода              2 ноды
Depth 3+ (кол-во)   4 ноды              1 нода              0 нод
─────────────────────────────────────────────────────────────────────────
Всего нод в графе   11                  9                   13
Всего рёбер         12                  12                  15
Видимых нод         11                  9                   13
  из них с кодом    1                   1                   0 (!)
  с spec_summary    5                   6                   10
  с spec_ticket     1                   1                   2
  только имя        4                   1                   0
─────────────────────────────────────────────────────────────────────────
```

Ключевое наблюдение: подход C даёт агенту больше всего spec_summary (10 против 5-6), но ноль реального кода. Подходы A и B дают меньше текста, но есть якорь — настоящий Python, по которому агент понимает как система работает.

Это объясняет результаты эксперимента: A (код на depth 0) → стабильно хорошо. B (код на depth 0) → нестабильно но с высоким потолком. C (нет кода на depth 0) → много контекста но слабая привязка.

Если использовать подход C, entry point для /context должен быть методом (order_confirm, order_set_state), а не template. Тогда агент получит реальный код на depth 0 и template на depth 1.
