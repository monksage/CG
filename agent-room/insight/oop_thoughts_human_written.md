 Итак, вот что я думаю: 
  1)База любого это методы и атрибуты класса.                                                                        
  2)Методы бывают двух типов - статик и классметод.                                                                  
  3)Атрибуты - неизвлекаемы из класса - должны находиться внутри сто из ста. Поэтому порождаю новую сущность -       
  class-node, это нода, которая имеет супертесные ребра, которые нельзя переиспользовать - это как раз таки:         
  А)инициализации класса, с наследованиями и тд                                                                      
  Б)атрибуты класса    
  В)Атрибуты экземпляра                                                                                              
  В)работает с датаклассами тоже.                                                                                    
  То есть мы впервые пилим код не на функциональные блоки, а на нефункциональные детали, которые сами по себе        
  ничего не могут, Пример:    

class PCRMainWindow(QMainWindow):
    path_to_origin = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        screen = QDesktopWidget().screenGeometry()
        self.setWindowIcon(QIcon(self.resource_path('./icons/main.ico')))
        self._width = screen.width()
        self._height = screen.height()
        self.setWindowTitle("MBU PCR")
        self.setMinimumSize(int(self._width * 0.8), int(self._height * 0.8))

Строка class PCRMainWindow(QMainWindow): это отдельная нода
Строки типа path_to_origin = pyqtSignal(str) это отдельная нода
Строки с атрибутами экземпляра перепихиваются в функциональную ноду. Также принадлежащую ноде класса супертесно, создает все атрибуты экзмепляра.

4)Методы бывают двух типов - статик и классметод. 
Это значит что мы может вынести часть классметодов в статикметод если это допустимо. Если self, используется исключительно как доступ к аргументам, а так чаще всего и происходит - мы способны развернуть этот клубок и переписать ребро на аргументный вызов, без использования self, тогда реиспользование доступно на те функции, которые способны на это.

Тогда получается что класс берется в обработку и примерно такой флоу:
1)проходка по классу и сбор атрибутов экзмепляра и методов
2)Разбор каждого метода по отдельности - статик выносится сразу в нетесную связь.
3)классметоды дробятся на подметоды, если слишком большие, а затем некоторые подметоды смогут перейти в раздел статик, если это возможно.
4)После того как все это произошло - надобность в некоторых атрибутах отпадает
5)Формируется новая тесная нода - функция инициализатор экзмемплярных атрибутов, которая УЖЕ СОДЕРЖИТ СОБСТВЕННЫЙ ВЫЗОВ. ПРим:
```
self.attr_init()

def attr_init(self):
    self.a = 0
    self.b = None

```
6)формируется новая тесная нода - блок с текстом инициализацией атрибутов класса.

```
    a = 0
    b = 123
    g = '123'
```

В итоге при сборке кода - эти тесные связи собираются в функциональный блок.




## Patterns example block

```
"""
Демонстрация паттернов проектирования в одной связанной системе.
Сценарий: система обработки заказов в интернет-магазине.

Паттерны:
  - Singleton          (ConfigManager)
  - Factory Method     (PaymentFactory)
  - Strategy           (DiscountStrategy)
  - Observer           (EventBus)
  - Decorator          (LoggingDecorator для Payment)
  - Builder            (OrderBuilder)
  - State              (OrderState)
  - Iterator           (OrderHistory)
  - Proxy              (PaymentProxy — ленивая инициализация + контроль доступа)
  - Chain of Resp.     (ValidationHandler)
  - Adapter            (LegacyWarehouseAdapter)
  - Template Method    (ReportGenerator)
  - Command            (OrderCommand + Undo)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Iterator
from functools import wraps
import copy


# ╔══════════════════════════════════════════════════════════════════╗
# ║  1. SINGLETON — глобальная конфигурация (потокобезопасный)      ║
# ╚══════════════════════════════════════════════════════════════════╝

class SingletonMeta(type):
    """Метакласс-одиночка. Любой класс с metaclass=SingletonMeta
    будет существовать в единственном экземпляре."""
    _instances: dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class ConfigManager(metaclass=SingletonMeta):
    """Единственный объект конфигурации во всей системе."""

    def __init__(self):
        self._settings: dict[str, Any] = {
            "currency": "RUB",
            "max_order_items": 50,
            "fraud_threshold": 100_000,
            "tax_rate": 0.20,
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value

    def __repr__(self):
        return f"ConfigManager({self._settings})"


# ╔══════════════════════════════════════════════════════════════════╗
# ║  2. OBSERVER / EVENT BUS — подписка на события                 ║
# ╚══════════════════════════════════════════════════════════════════╝

class EventBus(metaclass=SingletonMeta):
    """Глобальная шина событий. Компоненты подписываются и реагируют,
    не зная друг о друге — полная развязка (decoupling)."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}

    def subscribe(self, event: str, callback: Callable) -> None:
        self._subscribers.setdefault(event, []).append(callback)

    def unsubscribe(self, event: str, callback: Callable) -> None:
        if event in self._subscribers:
            self._subscribers[event].remove(callback)

    def publish(self, event: str, **data) -> None:
        for callback in self._subscribers.get(event, []):
            callback(**data)


# ╔══════════════════════════════════════════════════════════════════╗
# ║  3. STRATEGY — сменяемые алгоритмы скидок                     ║
# ╚══════════════════════════════════════════════════════════════════╝

class DiscountStrategy(ABC):
    """Базовый интерфейс стратегии."""
    @abstractmethod
    def calculate(self, total: float) -> float: ...


class NoDiscount(DiscountStrategy):
    def calculate(self, total: float) -> float:
        return total


class PercentDiscount(DiscountStrategy):
    def __init__(self, percent: float):
        self._percent = percent

    def calculate(self, total: float) -> float:
        return total * (1 - self._percent / 100)


class FixedDiscount(DiscountStrategy):
    def __init__(self, amount: float):
        self._amount = amount

    def calculate(self, total: float) -> float:
        return max(0, total - self._amount)


class TieredDiscount(DiscountStrategy):
    """Прогрессивная скидка: чем больше сумма, тем больше процент."""
    _tiers = [(50_000, 15), (20_000, 10), (10_000, 5)]

    def calculate(self, total: float) -> float:
        for threshold, percent in self._tiers:
            if total >= threshold:
                return total * (1 - percent / 100)
        return total


# ╔══════════════════════════════════════════════════════════════════╗
# ║  4. STATE — жизненный цикл заказа                              ║
# ╚══════════════════════════════════════════════════════════════════╝

class OrderStatus(Enum):
    DRAFT = auto()
    CONFIRMED = auto()
    PAID = auto()
    SHIPPED = auto()
    DELIVERED = auto()
    CANCELLED = auto()


class OrderState(ABC):
    """Каждое состояние знает, какие переходы из него допустимы."""

    @abstractmethod
    def confirm(self, order: Order) -> None: ...

    @abstractmethod
    def pay(self, order: Order) -> None: ...

    @abstractmethod
    def ship(self, order: Order) -> None: ...

    @abstractmethod
    def deliver(self, order: Order) -> None: ...

    @abstractmethod
    def cancel(self, order: Order) -> None: ...

    def _deny(self, action: str, current: str):
        raise InvalidStateTransition(
            f"Нельзя '{action}' из состояния '{current}'"
        )


class InvalidStateTransition(Exception):
    pass


class DraftState(OrderState):
    def confirm(self, order):
        order._set_state(ConfirmedState(), OrderStatus.CONFIRMED)

    def pay(self, order):     self._deny("pay", "DRAFT")
    def ship(self, order):    self._deny("ship", "DRAFT")
    def deliver(self, order): self._deny("deliver", "DRAFT")

    def cancel(self, order):
        order._set_state(CancelledState(), OrderStatus.CANCELLED)


class ConfirmedState(OrderState):
    def confirm(self, order): self._deny("confirm", "CONFIRMED")

    def pay(self, order):
        order._set_state(PaidState(), OrderStatus.PAID)

    def ship(self, order):    self._deny("ship", "CONFIRMED")
    def deliver(self, order): self._deny("deliver", "CONFIRMED")

    def cancel(self, order):
        order._set_state(CancelledState(), OrderStatus.CANCELLED)


class PaidState(OrderState):
    def confirm(self, order): self._deny("confirm", "PAID")
    def pay(self, order):     self._deny("pay", "PAID")

    def ship(self, order):
        order._set_state(ShippedState(), OrderStatus.SHIPPED)

    def deliver(self, order): self._deny("deliver", "PAID")

    def cancel(self, order):
        order._set_state(CancelledState(), OrderStatus.CANCELLED)
        EventBus().publish("refund_requested", order_id=order.order_id)


class ShippedState(OrderState):
    def confirm(self, order): self._deny("confirm", "SHIPPED")
    def pay(self, order):     self._deny("pay", "SHIPPED")
    def ship(self, order):    self._deny("ship", "SHIPPED")

    def deliver(self, order):
        order._set_state(DeliveredState(), OrderStatus.DELIVERED)

    def cancel(self, order):  self._deny("cancel", "SHIPPED")


class DeliveredState(OrderState):
    def confirm(self, order): self._deny("confirm", "DELIVERED")
    def pay(self, order):     self._deny("pay", "DELIVERED")
    def ship(self, order):    self._deny("ship", "DELIVERED")
    def deliver(self, order): self._deny("deliver", "DELIVERED")
    def cancel(self, order):  self._deny("cancel", "DELIVERED")


class CancelledState(OrderState):
    def confirm(self, order): self._deny("confirm", "CANCELLED")
    def pay(self, order):     self._deny("pay", "CANCELLED")
    def ship(self, order):    self._deny("ship", "CANCELLED")
    def deliver(self, order): self._deny("deliver", "CANCELLED")
    def cancel(self, order):  self._deny("cancel", "CANCELLED")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  5. BUILDER — пошаговая сборка заказа                          ║
# ╚══════════════════════════════════════════════════════════════════╝

@dataclass
class OrderItem:
    name: str
    price: float
    quantity: int = 1


class Order:
    """Основная сущность. Использует State для управления статусом."""
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

    # --- State-делегирование ---
    def confirm(self):  self._state.confirm(self)
    def pay(self):      self._state.pay(self)
    def ship(self):     self._state.ship(self)
    def deliver(self):  self._state.deliver(self)
    def cancel(self):   self._state.cancel(self)

    def _set_state(self, state: OrderState, status: OrderStatus):
        old = self.status
        self._state = state
        self.status = status
        EventBus().publish(
            "order_status_changed",
            order_id=self.order_id, old=old, new=status,
        )

    @property
    def raw_total(self) -> float:
        return sum(i.price * i.quantity for i in self.items)

    @property
    def total(self) -> float:
        return self.discount_strategy.calculate(self.raw_total)

    def __repr__(self):
        return (
            f"Order(id={self.order_id}, status={self.status.name}, "
            f"items={len(self.items)}, total={self.total:.2f})"
        )


class OrderBuilder:
    """Fluent-интерфейс для сборки заказа по шагам."""

    def __init__(self):
        self._order = Order()

    def add_item(self, name: str, price: float, qty: int = 1) -> OrderBuilder:
        self._order.items.append(OrderItem(name, price, qty))
        return self

    def with_discount(self, strategy: DiscountStrategy) -> OrderBuilder:
        self._order.discount_strategy = strategy
        return self

    def with_metadata(self, **kw) -> OrderBuilder:
        self._order.metadata.update(kw)
        return self

    def build(self) -> Order:
        if not self._order.items:
            raise ValueError("Заказ не может быть пустым")
        order = self._order
        self._order = Order()  # сбрасываем для повторного использования
        return order


# ╔══════════════════════════════════════════════════════════════════╗
# ║  6. FACTORY METHOD — создание платёжных обработчиков            ║
# ╚══════════════════════════════════════════════════════════════════╝

class Payment(ABC):
    """Базовый интерфейс оплаты."""
    @abstractmethod
    def execute(self, amount: float) -> bool: ...

    @abstractmethod
    def refund(self, amount: float) -> bool: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class CardPayment(Payment):
    def execute(self, amount: float) -> bool:
        print(f"  💳 Списание {amount:.2f} с карты")
        return True

    def refund(self, amount: float) -> bool:
        print(f"  💳 Возврат {amount:.2f} на карту")
        return True

    @property
    def name(self): return "Card"


class CryptoPayment(Payment):
    def execute(self, amount: float) -> bool:
        print(f"  ₿ Перевод {amount:.2f} крипто-кошелёк")
        return True

    def refund(self, amount: float) -> bool:
        print(f"  ₿ Возврат {amount:.2f} на крипто-кошелёк")
        return True

    @property
    def name(self): return "Crypto"


class InvoicePayment(Payment):
    def execute(self, amount: float) -> bool:
        print(f"  📄 Выставлен счёт на {amount:.2f}")
        return True

    def refund(self, amount: float) -> bool:
        print(f"  📄 Сторно счёта на {amount:.2f}")
        return True

    @property
    def name(self): return "Invoice"


class PaymentFactory:
    """Фабрика — маппинг строки на конкретный класс."""
    _registry: dict[str, type[Payment]] = {
        "card": CardPayment,
        "crypto": CryptoPayment,
        "invoice": InvoicePayment,
    }

    @classmethod
    def register(cls, key: str, klass: type[Payment]):
        cls._registry[key] = klass

    @classmethod
    def create(cls, method: str) -> Payment:
        klass = cls._registry.get(method)
        if not klass:
            raise ValueError(f"Неизвестный метод оплаты: {method}")
        return klass()


# ╔══════════════════════════════════════════════════════════════════╗
# ║  7. DECORATOR — логирование поверх любого Payment              ║
# ╚══════════════════════════════════════════════════════════════════╝

class LoggingPaymentDecorator(Payment):
    """Оборачивает любой Payment, добавляя логирование.
    Можно вкладывать несколько декораторов друг в друга."""

    def __init__(self, wrapped: Payment):
        self._wrapped = wrapped

    def execute(self, amount: float) -> bool:
        print(f"  [LOG] → {self._wrapped.name}.execute({amount:.2f})")
        result = self._wrapped.execute(amount)
        print(f"  [LOG] ← результат: {result}")
        return result

    def refund(self, amount: float) -> bool:
        print(f"  [LOG] → {self._wrapped.name}.refund({amount:.2f})")
        result = self._wrapped.refund(amount)
        print(f"  [LOG] ← результат: {result}")
        return result

    @property
    def name(self):
        return f"Logged({self._wrapped.name})"


# ╔══════════════════════════════════════════════════════════════════╗
# ║  8. PROXY — ленивая инициализация + проверка прав              ║
# ╚══════════════════════════════════════════════════════════════════╝

class PaymentProxy(Payment):
    """Прокси: создаёт реальный объект только при первом вызове,
    а также проверяет лимит по конфигу (fraud_threshold)."""

    def __init__(self, method: str):
        self._method = method
        self._real: Payment | None = None

    def _get_real(self) -> Payment:
        if self._real is None:
            print(f"  [PROXY] Ленивое создание {self._method}-платежа")
            self._real = LoggingPaymentDecorator(
                PaymentFactory.create(self._method)
            )
        return self._real

    def execute(self, amount: float) -> bool:
        threshold = ConfigManager().get("fraud_threshold", float("inf"))
        if amount > threshold:
            print(f"  [PROXY] ⛔ Сумма {amount:.2f} превышает лимит {threshold}")
            EventBus().publish("fraud_alert", amount=amount)
            return False
        return self._get_real().execute(amount)

    def refund(self, amount: float) -> bool:
        return self._get_real().refund(amount)

    @property
    def name(self):
        return f"Proxy({self._method})"


# ╔══════════════════════════════════════════════════════════════════╗
# ║  9. CHAIN OF RESPONSIBILITY — валидация заказа                 ║
# ╚══════════════════════════════════════════════════════════════════╝

class ValidationHandler(ABC):
    """Цепочка обработчиков: каждый проверяет своё условие
    и передаёт дальше, если всё ОК."""

    def __init__(self):
        self._next: ValidationHandler | None = None

    def set_next(self, handler: ValidationHandler) -> ValidationHandler:
        self._next = handler
        return handler  # для цепочки вызовов

    def handle(self, order: Order) -> list[str]:
        errors = self._validate(order)
        if self._next:
            errors += self._next.handle(order)
        return errors

    @abstractmethod
    def _validate(self, order: Order) -> list[str]: ...


class NotEmptyValidator(ValidationHandler):
    def _validate(self, order):
        if not order.items:
            return ["Заказ пуст"]
        return []


class MaxItemsValidator(ValidationHandler):
    def _validate(self, order):
        limit = ConfigManager().get("max_order_items", 50)
        if len(order.items) > limit:
            return [f"Превышен лимит: {len(order.items)} > {limit}"]
        return []


class PositivePriceValidator(ValidationHandler):
    def _validate(self, order):
        bad = [i.name for i in order.items if i.price <= 0]
        if bad:
            return [f"Некорректная цена у: {', '.join(bad)}"]
        return []


class StockValidator(ValidationHandler):
    """Имитация проверки наличия на складе."""
    _stock = {"Ноутбук": 10, "Мышь": 200, "Монитор": 5, "Клавиатура": 50}

    def _validate(self, order):
        errors = []
        for item in order.items:
            available = self._stock.get(item.name, 0)
            if item.quantity > available:
                errors.append(
                    f"'{item.name}': запрошено {item.quantity}, на складе {available}"
                )
        return errors


def build_validation_chain() -> ValidationHandler:
    """Собираем цепочку один раз и переиспользуем."""
    chain = NotEmptyValidator()
    chain.set_next(MaxItemsValidator()) \
         .set_next(PositivePriceValidator()) \
         .set_next(StockValidator())
    return chain


# ╔══════════════════════════════════════════════════════════════════╗
# ║  10. ADAPTER — интеграция со старым API склада                 ║
# ╚══════════════════════════════════════════════════════════════════╝

class LegacyWarehouseAPI:
    """Старая система: другой формат данных, другие методы."""
    def reserve_goods(self, sku_list: list[dict]) -> dict:
        reserved = [s["sku"] for s in sku_list]
        return {"status": "OK", "reserved": reserved}

    def cancel_reservation(self, reservation_id: str) -> dict:
        return {"status": "CANCELLED", "id": reservation_id}


class WarehousePort(ABC):
    """Порт — наш «чистый» интерфейс для работы со складом."""
    @abstractmethod
    def reserve(self, order: Order) -> str: ...

    @abstractmethod
    def release(self, reservation_id: str) -> bool: ...


class LegacyWarehouseAdapter(WarehousePort):
    """Адаптер: оборачивает старый API в новый интерфейс."""

    def __init__(self, legacy: LegacyWarehouseAPI):
        self._legacy = legacy

    def reserve(self, order: Order) -> str:
        sku_list = [
            {"sku": item.name, "qty": item.quantity}
            for item in order.items
        ]
        result = self._legacy.reserve_goods(sku_list)
        reservation_id = f"RES-{order.order_id}"
        print(f"  [ADAPTER] Зарезервировано: {result['reserved']}")
        return reservation_id

    def release(self, reservation_id: str) -> bool:
        result = self._legacy.cancel_reservation(reservation_id)
        return result["status"] == "CANCELLED"


# ╔══════════════════════════════════════════════════════════════════╗
# ║  11. COMMAND + UNDO — отменяемые операции                      ║
# ╚══════════════════════════════════════════════════════════════════╝

class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...


class PlaceOrderCommand(Command):
    """Команда: подтвердить + оплатить заказ. Undo = отменить."""

    def __init__(self, order: Order, payment: Payment, warehouse: WarehousePort):
        self._order = order
        self._payment = payment
        self._warehouse = warehouse
        self._reservation_id: str | None = None

    def execute(self) -> None:
        # Подтверждаем
        self._order.confirm()
        # Резервируем на складе
        self._reservation_id = self._warehouse.reserve(self._order)
        # Оплачиваем
        success = self._payment.execute(self._order.total)
        if success:
            self._order.pay()
        else:
            raise RuntimeError("Платёж отклонён")

    def undo(self) -> None:
        if self._order.status == OrderStatus.PAID:
            self._payment.refund(self._order.total)
        if self._reservation_id:
            self._warehouse.release(self._reservation_id)
        self._order.cancel()


class CommandHistory:
    """Хранит выполненные команды для undo."""

    def __init__(self):
        self._history: list[Command] = []

    def push(self, cmd: Command) -> None:
        cmd.execute()
        self._history.append(cmd)

    def pop_undo(self) -> None:
        if not self._history:
            raise IndexError("Нечего отменять")
        cmd = self._history.pop()
        cmd.undo()


# ╔══════════════════════════════════════════════════════════════════╗
# ║  12. ITERATOR — история заказов с фильтрацией                  ║
# ╚══════════════════════════════════════════════════════════════════╝

class OrderHistory:
    """Коллекция заказов с кастомным итератором."""

    def __init__(self):
        self._orders: list[Order] = []

    def add(self, order: Order):
        self._orders.append(order)

    def __iter__(self) -> Iterator[Order]:
        return iter(self._orders)

    def __len__(self) -> int:
        return len(self._orders)

    def filter_by_status(self, status: OrderStatus) -> Iterator[Order]:
        return (o for o in self._orders if o.status == status)

    def total_revenue(self) -> float:
        return sum(
            o.total for o in self._orders
            if o.status in (OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED)
        )


# ╔══════════════════════════════════════════════════════════════════╗
# ║  13. TEMPLATE METHOD — генерация отчётов                       ║
# ╚══════════════════════════════════════════════════════════════════╝

class ReportGenerator(ABC):
    """Шаблонный метод: скелет алгоритма фиксирован,
    а конкретные шаги переопределяются подклассами."""

    def generate(self, history: OrderHistory) -> str:
        lines = []
        lines.append(self._header())
        lines.append(self._body(history))
        lines.append(self._footer(history))
        return "\n".join(lines)

    @abstractmethod
    def _header(self) -> str: ...

    @abstractmethod
    def _body(self, history: OrderHistory) -> str: ...

    def _footer(self, history: OrderHistory) -> str:
        return f"Всего заказов: {len(history)} | Выручка: {history.total_revenue():.2f}"


class PlainTextReport(ReportGenerator):
    def _header(self):
        return "=" * 50 + "\n  ОТЧЁТ ПО ЗАКАЗАМ (текст)\n" + "=" * 50

    def _body(self, history):
        rows = []
        for o in history:
            rows.append(
                f"  #{o.order_id:<4} | {o.status.name:<10} | "
                f"{len(o.items)} позиц. | {o.total:>10.2f}"
            )
        return "\n".join(rows)


class MarkdownReport(ReportGenerator):
    def _header(self):
        return "# Отчёт по заказам\n"

    def _body(self, history):
        lines = ["| ID | Статус | Позиции | Сумма |",
                 "|---:|--------|--------:|------:|"]
        for o in history:
            lines.append(
                f"| {o.order_id} | {o.status.name} | "
                f"{len(o.items)} | {o.total:.2f} |"
            )
        return "\n".join(lines)

    def _footer(self, history):
        return f"\n> **Итого:** {len(history)} заказов, " \
               f"выручка {history.total_revenue():.2f}"


# ╔══════════════════════════════════════════════════════════════════╗
# ║                     ЗАПУСК ДЕМОНСТРАЦИИ                        ║
# ╚══════════════════════════════════════════════════════════════════╝

def main():
    bus = EventBus()
    history = OrderHistory()
    cmd_history = CommandHistory()
    warehouse = LegacyWarehouseAdapter(LegacyWarehouseAPI())
    validator = build_validation_chain()

    # --- Подписки Observer ---
    bus.subscribe("order_status_changed", lambda **kw: print(
        f"  [EVENT] Заказ #{kw['order_id']}: {kw['old'].name} → {kw['new'].name}"
    ))
    bus.subscribe("fraud_alert", lambda **kw: print(
        f"  [EVENT] ⚠️  Фрод-алерт! Сумма: {kw['amount']:.2f}"
    ))
    bus.subscribe("refund_requested", lambda **kw: print(
        f"  [EVENT] 💰 Запрос возврата для заказа #{kw['order_id']}"
    ))

    print("\n" + "─" * 60)
    print("  🛒  ЗАКАЗ 1: Обычный заказ с процентной скидкой")
    print("─" * 60)

    order1 = (
        OrderBuilder()
        .add_item("Ноутбук", 75_000)
        .add_item("Мышь", 2_500, qty=2)
        .with_discount(PercentDiscount(10))
        .with_metadata(customer="Иван", priority="high")
        .build()
    )
    print(f"  Собран: {order1}")
    print(f"  До скидки: {order1.raw_total:.2f}, после: {order1.total:.2f}")

    errors = validator.handle(order1)
    if errors:
        print(f"  ❌ Валидация: {errors}")
    else:
        print("  ✅ Валидация пройдена")
        payment1 = PaymentProxy("card")
        cmd = PlaceOrderCommand(order1, payment1, warehouse)
        cmd_history.push(cmd)

    history.add(order1)

    print("\n" + "─" * 60)
    print("  🛒  ЗАКАЗ 2: Крупный заказ — сработает фрод-фильтр прокси")
    print("─" * 60)

    order2 = (
        OrderBuilder()
        .add_item("Монитор", 120_000, qty=1)
        .with_discount(NoDiscount())
        .build()
    )
    print(f"  Собран: {order2}")

    errors = validator.handle(order2)
    if errors:
        print(f"  ❌ Валидация: {errors}")
    else:
        print("  ✅ Валидация пройдена")
        payment2 = PaymentProxy("crypto")
        try:
            cmd2 = PlaceOrderCommand(order2, payment2, warehouse)
            cmd_history.push(cmd2)
        except RuntimeError as e:
            print(f"  ❌ {e}")
            order2.cancel()

    history.add(order2)

    print("\n" + "─" * 60)
    print("  ↩️  UNDO последней успешной команды (Command)")
    print("─" * 60)
    cmd_history.pop_undo()

    print("\n" + "─" * 60)
    print("  🛒  ЗАКАЗ 3: Заказ с прогрессивной скидкой → доставка")
    print("─" * 60)

    order3 = (
        OrderBuilder()
        .add_item("Клавиатура", 8_000, qty=3)
        .add_item("Мышь", 2_500, qty=4)
        .with_discount(TieredDiscount())
        .build()
    )
    print(f"  Собран: {order3}")

    payment3 = PaymentProxy("invoice")
    cmd3 = PlaceOrderCommand(order3, payment3, warehouse)
    cmd_history.push(cmd3)
    order3.ship()
    order3.deliver()
    history.add(order3)

    print("\n" + "─" * 60)
    print("  📊 ОТЧЁТ — Template Method (PlainText)")
    print("─" * 60)
    print(PlainTextReport().generate(history))

    print("\n" + "─" * 60)
    print("  📊 ОТЧЁТ — Template Method (Markdown)")
    print("─" * 60)
    print(MarkdownReport().generate(history))

    print("\n" + "─" * 60)
    print("  🔍 ITERATOR — фильтр по статусу DELIVERED")
    print("─" * 60)
    for o in history.filter_by_status(OrderStatus.DELIVERED):
        print(f"  → {o}")

    print("\n" + "─" * 60)
    print("  ⚙️  SINGLETON — конфиг один и тот же объект?")
    print("─" * 60)
    c1 = ConfigManager()
    c2 = ConfigManager()
    print(f"  id(c1) == id(c2)  →  {id(c1) == id(c2)}  ({id(c1)})")
    print()


if __name__ == "__main__":
    main()
```
