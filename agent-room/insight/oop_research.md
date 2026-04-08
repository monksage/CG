# OOP Decomposition for Graph-Based Code Storage — Research Findings

## Preamble

This document proposes three distinct strategies for decomposing object-oriented code into a flat graph of function-nodes in Contour Graph. Each strategy is a complete proposal with taxonomy, extraction rules, edge types, framework handling, builder requirements, boundary rules, and a worked example against the 900-line patterns codebase.

The core tension: OOP bundles state, identity, dispatch, and framework obligations into classes. The graph wants atomic, reusable, testable function-nodes. Full decomposition maximizes reuse but loses OOP semantics. No decomposition preserves semantics but defeats the graph's purpose. The three approaches draw the line at different places.

---

# Approach A: Maximum Decomposition with Explicit State Threading

## A.1 Proposal

Every class decomposes completely. There are no class-nodes in the graph — only function-nodes and data-schema-nodes.

**Core mechanism:** `self` is a data structure, not a hidden dependency. Every method becomes a standalone function whose first argument is a typed dict/dataclass representing the object's state. The class ceases to exist as a graph entity — it becomes a *build-time projection*, assembled from nodes by the builder using a reconstruction template stored as edge metadata.

**State threading:** Methods that read `self.x` become functions that receive `state: T` and return `state: T` (or a new version of it). Mutation is explicit: `def confirm_order(state: OrderState) -> OrderState`. No hidden side effects through `self`.

**Polymorphism:** Abstract methods become *contract nodes* — nodes with kind="contract" that have code=None but have a full accepts/returns specification. Concrete implementations are regular function-nodes linked to the contract via `implements` edges. Runtime dispatch is a *dispatch node* — a function that selects among implementations based on a discriminant.

**Framework glue:** Framework-bound classes (Qt, Django) are handled by *adapter nodes* — thin function-nodes whose sole purpose is to satisfy framework requirements by delegating to graph functions. The adapter node's code contains the class definition with method bodies that are one-line calls to graph nodes.

## A.2 Taxonomy of irreducible class elements

Under Approach A, **nothing is irreducible** — everything decomposes. But some elements transform rather than extract:

| Element | Transformation | Result node kind |
|---|---|---|
| `class Foo(Bar):` declaration | Becomes metadata on reconstruction template | No node — edge metadata |
| `__init__` body | Becomes `create_foo(args) -> FooState` factory function | function-node |
| Class attributes (`x = 5`) | Become fields in FooState schema | data-schema-node |
| Instance attributes | Become fields in FooState schema | data-schema-node |
| Regular methods | Become `fn(state: FooState, ...) -> ...` | function-node |
| `@staticmethod` | Becomes free function-node directly | function-node |
| `@classmethod` | Becomes `fn(class_config: FooClassState, ...)` | function-node |
| `@property` | Becomes `get_x(state: FooState) -> T` | function-node |
| `__dunder__` methods | Become function-nodes; builder wires them back | function-node |
| `@abstractmethod` | Becomes contract-node (no code, only spec) | contract-node |
| Metaclass `__call__` | Becomes a factory/interceptor function-node | function-node |
| Descriptors (`__get__`/`__set__`) | Become accessor function-nodes | function-node |
| `__slots__` | Becomes constraint metadata on FooState schema | data-schema-node metadata |
| Class decorators | Become wrapper function-nodes applied at build time | function-node |

**Data-schema-node** is a new node kind: it holds no executable code, only a typed schema (field names, types, defaults). It represents the state that was previously hidden inside `self`. This is the key innovation of Approach A — making implicit state explicit and visible in the graph.

## A.3 Extraction rules

**Always extract:**
- Any method where `self` is used only for attribute read access. Convert `self.x` to parameter `x` or `state.x`.
- Any `@staticmethod` — it's already a free function.
- Any `@classmethod` that only reads class-level configuration.
- Properties that compute derived values (`raw_total`, `total`) — become pure functions on state.

**Extract with state threading:**
- Methods that mutate `self` (e.g., `_set_state`): become `fn(state) -> new_state`. The caller receives the new state.
- Pipeline methods (method A calls method B which calls method C, all mutating self): each becomes a function; the pipeline is a composition node that threads state through them.
- `__init__`: becomes a factory function that returns the initial state.

**Extract with contract binding:**
- Abstract methods: become contract-nodes. Each concrete override becomes a function-node with `implements` edge to the contract.
- Template Method pattern: the skeleton becomes a function that takes strategy functions as parameters (higher-order function).

**When extraction technically breaks:**
- Methods using `super()` in cooperative MRO chains — `super()` is a runtime mechanism that depends on the class being in an MRO. **Solution:** explicit parent call via function reference: `parent_fn(state)` instead of `super().method()`.
- `__init_subclass__`, `__set_name__` — metaclass protocol hooks that fire at class definition time, not call time. **Solution:** these become build-time hooks — the builder executes them during class assembly.
- Descriptor protocol methods — depend on being accessed as class attributes. **Solution:** accessor functions + builder wiring.

**Never extract (Approach A says: still extract, but mark):**
Under radical decomposition, nothing stays in a class. But some nodes get tagged `framework_glue=true` to signal they exist solely to satisfy an external framework's class expectations.

## A.4 Edge types

| Edge type | Meaning | Example |
|---|---|---|
| `calls` | Function A calls function B | `confirm_order` calls `set_order_state` |
| `implements` | Function implements a contract | `card_execute` implements `payment_execute` contract |
| `dispatches` | Function routes to one of several implementations | `dispatch_payment` dispatches to card/crypto/invoice |
| `composes` | Function is part of a composition pipeline | `place_order` composes confirm → reserve → pay |
| `reads_state` | Function reads from a data-schema | `get_total` reads OrderState |
| `writes_state` | Function produces/mutates a data-schema | `create_order` writes OrderState |
| `reconstructs` | Template edge: "these nodes form class X" | Builder metadata |
| `extends` | Schema A extends schema B (inheritance) | OrderState might extend BaseEntityState |
| `tests` | Existing edge type — test node for target | (unchanged) |
| `alternative_to` | Two nodes are alternative implementations of same contract | `card_execute` alternative_to `crypto_execute` |

## A.5 Framework-bound code

**General solution: Adapter Pattern at the graph boundary.**

A framework-bound class (e.g., `class MyWindow(QMainWindow)`) becomes:

1. **Business logic nodes** — all real logic extracted as free functions with explicit state.
2. **A data-schema-node** for the window's state (what was `self.*`).
3. **An adapter node** (kind="adapter") — contains the actual class definition with minimal code. Each method body is a one-line delegation:

```python
class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._state = create_my_window_state()

    def on_click(self):
        self._state = handle_click(self._state)

    def paintEvent(self, event):
        paint_my_window(self._state, event)
```

The adapter node is special: it has kind="adapter", it references the framework class in metadata (`framework_base: "QMainWindow"`), and it has `delegates_to` edges pointing to the real logic nodes. The adapter is **not reusable** — it exists solely as framework glue. But the logic nodes it delegates to **are reusable**.

This generalizes beyond Qt/Django. Any framework that demands a class gets an adapter node. The adapter is thin (no logic, only delegation), framework-specific (carries the inheritance), and explicitly marked as non-reusable glue.

**Limitation:** If the framework's virtual dispatch calls 50 methods on your class, you get 50 one-liner delegations in the adapter. This is verbose but mechanically simple. The adapter node may be large (by line count) but has zero decision points — it's pure wiring.

## A.6 Builder requirements

To reconstruct a class from Approach A's decomposition, the builder needs:

1. **Reconstruction template** (stored as metadata on `reconstructs` edges):
   - Target class name
   - Base classes (inheritance chain)
   - Class decorators (ordered list)
   - Method ordering (cosmetic, for human projection)

2. **Per-node metadata** for nodes participating in a class:
   - `bind_as`: what name the method gets in the class (`"confirm"`, `"__init__"`, `"total"` for property)
   - `bind_type`: `"method"` | `"classmethod"` | `"staticmethod"` | `"property"` | `"property.setter"`
   - `indent_level`: always 1 for class body methods (builder handles this)

3. **Data-schema-node → `__init__`** mapping:
   - Builder reads the data-schema-node to generate `__init__` or `__init__` body
   - For dataclasses: builder generates `@dataclass` decoration + field declarations
   - For regular classes: builder generates `__init__` from factory function's return schema

4. **State threading → self rewriting:**
   - Builder converts `fn(state: FooState, x) -> FooState` back to `def method(self, x):`
   - Replaces `state.x` with `self.x`, `state = ...` with `self.x = ...`
   - This is the most complex builder operation — essentially de-functionalizing

**Builder complexity: HIGH.** This is Approach A's main cost. The builder must understand state threading, de-functionalization, adapter assembly, property wrapping, decorator application, and MRO-correct inheritance chain assembly.

## A.7 The boundary rule

**Approach A has no boundary — everything decomposes.** This is its defining feature.

The only exception is adapter nodes for framework-bound code, but even these contain no logic — they're pure delegation. The question "should this class stay as one node?" is always answered "no."

**Justification:** Any class that stays whole is a reusability black hole. The F∩C problem is solved by eliminating C entirely from the graph. Classes exist only as build-time projections.

**Risk:** Over-decomposition of simple data classes (dataclass with 3 fields and no methods) creates 3 nodes (schema + factory + test) where 1 would suffice. The overhead is real but bounded — data-schema-nodes are small.

## A.8 Worked example (900-line patterns code)

### Decomposition of ConfigManager (Singleton)

**Original:** SingletonMeta metaclass + ConfigManager class with `__init__`, `get`, `set`, `__repr__`.

**Decomposed nodes:**
1. `create_config_state() -> ConfigState` — factory, returns default settings dict. (function-node)
2. `ConfigState` — data-schema: `{settings: dict[str, Any]}` (data-schema-node)
3. `config_get(state: ConfigState, key: str, default: Any) -> Any` — pure function. (function-node)
4. `config_set(state: ConfigState, key: str, value: Any) -> ConfigState` — returns new state. (function-node)
5. `format_config(state: ConfigState) -> str` — the `__repr__`. (function-node)
6. `ensure_singleton(factory_fn) -> wrapped_fn` — the metaclass behavior as a function decorator/wrapper. (function-node)

**Edges:**
- `config_get` reads_state `ConfigState`
- `config_set` writes_state `ConfigState`
- `create_config_state` writes_state `ConfigState`
- `ensure_singleton` calls `create_config_state`
- `config_get`, `config_set`, `format_config`, `create_config_state` all have `reconstructs` edges to class "ConfigManager" template

**Reconstruction template:** `{class: "ConfigManager", metaclass: "SingletonMeta", bases: [], decorators: []}`

**Note:** SingletonMeta itself decomposes into `ensure_singleton` — a higher-order function that memoizes instance creation. The metaclass disappears; singleton behavior is expressed as a function-node wrapping the factory.

### Decomposition of EventBus (Observer)

**Nodes:**
1. `EventBusState` — schema: `{subscribers: dict[str, list[Callable]]}` (data-schema-node)
2. `create_event_bus() -> EventBusState` (function-node)
3. `subscribe_event(state: EventBusState, event: str, callback: Callable) -> EventBusState` (function-node)
4. `unsubscribe_event(state: EventBusState, event: str, callback: Callable) -> EventBusState` (function-node)
5. `publish_event(state: EventBusState, event: str, **data) -> None` (function-node)

All standard. EventBus has no polymorphism, no inheritance complexity. Clean decomposition.

### Decomposition of Strategy pattern (DiscountStrategy hierarchy)

**Contract node:**
- `calculate_discount` — contract-node, spec: `(total: float) -> float`

**Implementation nodes:**
- `no_discount(total: float) -> float` — returns total. (function-node, implements calculate_discount)
- `percent_discount(total: float, percent: float) -> float` — (function-node, implements calculate_discount)
- `fixed_discount(total: float, amount: float) -> float` — (function-node, implements calculate_discount)
- `tiered_discount(total: float, tiers: list[tuple]) -> float` — (function-node, implements calculate_discount)

**Dispatch node:**
- `apply_discount(strategy_name: str, total: float, **params) -> float` — dispatches to the correct implementation. (function-node, dispatches to all four)

**Edges:**
- `no_discount` implements `calculate_discount`
- `percent_discount` implements `calculate_discount`
- `fixed_discount` implements `calculate_discount`
- `tiered_discount` implements `calculate_discount`
- `no_discount` alternative_to `percent_discount` alternative_to `fixed_discount` alternative_to `tiered_discount`
- `apply_discount` dispatches to all four

**Key observation:** The Strategy pattern decomposes beautifully under Approach A. Each strategy is already a pure function — `self` carries only configuration (percent, amount, tiers), which becomes an explicit parameter. No state threading needed.

### Decomposition of State pattern (OrderState hierarchy)

**Contract nodes:**
- `state_confirm` — contract: `(order_state: OrderData) -> OrderData`
- `state_pay` — contract
- `state_ship` — contract
- `state_deliver` — contract
- `state_cancel` — contract

**Implementation nodes (per state):**
- `draft_confirm(order: OrderData) -> OrderData` — transitions to Confirmed
- `draft_pay(order: OrderData) -> OrderData` — raises error
- `draft_cancel(order: OrderData) -> OrderData` — transitions to Cancelled
- ... (6 states x 5 transitions = 30 nodes, most of which are one-line error raisers)

**Dispatch node:**
- `dispatch_order_action(order: OrderData, action: str) -> OrderData` — reads current state, dispatches to correct implementation

**Problem:** 30 nodes for a state machine that was 70 lines of code. Most nodes are trivial (`raise InvalidStateTransition`). This is over-decomposition.

**Mitigation:** The trivial deny methods become micro-nodes (kind="micro") — not standalone, inlined by the builder. Only the actually meaningful transitions (draft→confirmed, confirmed→paid, paid→shipped+refund, shipped→delivered) become real nodes. This reduces to ~8 real nodes + 1 dispatch + 1 deny-micro.

### Decomposition of Order (central entity)

**Nodes:**
1. `OrderData` — data-schema: `{order_id, items, status, discount_strategy_name, created_at, metadata, current_state_name}`
2. `create_order() -> OrderData`
3. `order_raw_total(order: OrderData) -> float` — pure computation
4. `order_total(order: OrderData) -> float` — calls dispatch to discount strategy
5. `order_set_state(order: OrderData, new_state: str, new_status: OrderStatus) -> OrderData` — state threading, publishes event
6. `order_confirm(order: OrderData) -> OrderData` — delegates to state dispatch
7. `order_pay(order: OrderData) -> OrderData` — delegates to state dispatch
8. ... (thin delegation nodes, could be micros)
9. `format_order(order: OrderData) -> str` — `__repr__`

### Decomposition of OrderBuilder (Builder pattern)

**Nodes:**
1. `create_order_builder() -> BuilderState` — where BuilderState wraps OrderData
2. `builder_add_item(state: BuilderState, name, price, qty) -> BuilderState`
3. `builder_with_discount(state: BuilderState, strategy_name) -> BuilderState`
4. `builder_with_metadata(state: BuilderState, **kw) -> BuilderState`
5. `builder_build(state: BuilderState) -> OrderData` — validates and returns

The fluent interface disappears — each step is a pure function. Builder pattern becomes function composition: `build(with_metadata(with_discount(add_item(create(), ...), ...), ...))`.

### Decomposition of Payment hierarchy (Factory + Decorator + Proxy)

**Contract nodes:**
- `payment_execute` — contract: `(amount: float) -> bool`
- `payment_refund` — contract: `(amount: float) -> bool`
- `payment_name` — contract: `() -> str`

**Implementation nodes:**
- `card_execute(amount) -> bool`, `card_refund(amount) -> bool`, `card_name() -> str`
- `crypto_execute(amount) -> bool`, `crypto_refund(amount) -> bool`, `crypto_name() -> str`
- `invoice_execute(amount) -> bool`, `invoice_refund(amount) -> bool`, `invoice_name() -> str`

**Factory node:**
- `create_payment(method: str) -> PaymentFunctions` — returns a struct of (execute_fn, refund_fn, name_fn)

**Decorator node (LoggingPaymentDecorator):**
- `logging_payment_execute(wrapped_execute, wrapped_name, amount) -> bool` — higher-order function
- `logging_payment_refund(wrapped_refund, wrapped_name, amount) -> bool` — higher-order function
- `wrap_payment_with_logging(payment_fns) -> PaymentFunctions` — wraps all three functions

**Proxy node (PaymentProxy):**
- `ProxyState` — data-schema: `{method: str, real: PaymentFunctions | None}`
- `proxy_execute(state: ProxyState, amount) -> (ProxyState, bool)` — lazy init + fraud check
- `proxy_refund(state: ProxyState, amount) -> (ProxyState, bool)` — lazy init + delegate

### Decomposition of Chain of Responsibility

**Nodes:**
- `validate_not_empty(order: OrderData) -> list[str]`
- `validate_max_items(order: OrderData, limit: int) -> list[str]`
- `validate_positive_price(order: OrderData) -> list[str]`
- `validate_stock(order: OrderData, stock: dict) -> list[str]`
- `run_validation_chain(order: OrderData, validators: list[Callable]) -> list[str]` — runs all, collects errors

The chain pattern completely dissolves — it becomes a list of validator functions iterated by a runner. No `_next` pointer, no handler base class. The graph represents this as: `run_validation_chain` calls each validator (edges), validators are `alternative_to` each other (same contract: order → errors).

### Decomposition of Adapter, Command, Iterator, Template Method

**Adapter (LegacyWarehouse):**
- `legacy_reserve_goods(sku_list) -> dict` — the old API, as-is
- `adapt_reserve(order: OrderData) -> str` — translates Order → sku_list, calls legacy, returns reservation_id
- `adapt_release(reservation_id: str) -> bool` — translates

**Command (PlaceOrderCommand):**
- `PlaceOrderCommandState` — data-schema: `{order, payment, warehouse, reservation_id}`
- `execute_place_order(state) -> state` — confirm → reserve → pay
- `undo_place_order(state) -> state` — refund → release → cancel
- `CommandHistoryState` — data-schema: `{history: list}`
- `push_command(history, execute_fn, state) -> (history, state)`
- `pop_undo(history, undo_fn) -> history`

**Iterator (OrderHistory):**
- `OrderHistoryState` — data-schema: `{orders: list[OrderData]}`
- `add_to_history(state, order) -> state`
- `filter_by_status(orders: list, status) -> list`
- `total_revenue(orders: list) -> float`

**Template Method (ReportGenerator):**
- `generate_report(header_fn, body_fn, footer_fn, history) -> str` — the skeleton as a higher-order function
- `plain_text_header() -> str`
- `plain_text_body(history) -> str`
- `plain_text_footer(history) -> str`
- `markdown_header() -> str`
- `markdown_body(history) -> str`
- `markdown_footer(history) -> str`

Template Method becomes function composition — pass the step functions as arguments.

### Total node count for Approach A

| Category | Function-nodes | Data-schema-nodes | Contract-nodes | Micro-nodes |
|---|---|---|---|---|
| Singleton/Config | 5 | 1 | 0 | 0 |
| Observer/EventBus | 4 | 1 | 0 | 0 |
| Strategy/Discount | 5 | 0 | 1 | 0 |
| State/OrderState | 8 | 0 | 5 | ~22 |
| Order entity | 7 | 1 | 0 | 0 |
| OrderBuilder | 5 | 1 | 0 | 0 |
| Payment (Factory+Decorator+Proxy) | 12 | 1 | 3 | 0 |
| Chain of Responsibility | 5 | 0 | 1 | 0 |
| Adapter | 3 | 0 | 0 | 0 |
| Command | 4 | 2 | 0 | 0 |
| Iterator | 3 | 1 | 0 | 0 |
| Template Method | 7 | 0 | 0 | 0 |
| **Total** | **~68** | **~8** | **~10** | **~22** |

**~108 nodes** from ~900 lines (30 classes). Average: 8.3 lines per node. High granularity.

---

# Approach B: Contract-Boundary Decomposition

## B.1 Proposal

Classes decompose **at contract boundaries**, not at method boundaries. A "contract" is a cohesive set of methods that together fulfill one responsibility. A class that implements one contract stays mostly together. A class that implements multiple contracts splits along contract lines.

**Core mechanism:** Identify the contracts (explicit ABCs, implicit duck-typing protocols, or logical groupings) that a class participates in. Each contract's implementation becomes a *contour* — a group of related nodes. Methods that serve multiple contracts stay in a *bridge node* within the class.

**State model:** Unlike Approach A, `self` is allowed to exist. Methods keep their `self` parameter. But the class is split into sub-groups, each of which is testable independently because it only depends on a subset of `self`'s attributes.

**Polymorphism:** Same contract-node concept as Approach A, but implementations are groups of nodes (contours), not individual functions.

**Key difference from A:** Approach B keeps methods as methods (with `self`) when they have non-trivial interaction with instance state. Only truly standalone logic is extracted to free functions.

## B.2 Taxonomy of irreducible class elements

| Element | Treatment | Stays in class? |
|---|---|---|
| Class declaration + inheritance | Irreducible. Part of class-shell. | Yes |
| `__init__` | Irreducible for classes with state. | Yes |
| Class attributes | Irreducible. Part of class-shell. | Yes |
| Instance attributes | Irreducible. Defined in `__init__`. | Yes |
| Methods serving one contract | Extracted as contract-implementation contour | Extracted |
| Methods serving multiple contracts | Stays as bridge in class-shell | Yes |
| `@staticmethod` | Always extracted | No |
| `@classmethod` using only class state | Extracted with class config as param | No |
| `@property` (pure computation) | Extracted | No |
| `@property` (state-dependent) | Stays unless serves single contract | Depends |
| Dunder methods (`__repr__`, `__len__`, etc.) | Usually stay — they define class identity | Yes |
| Abstract methods | Become contract-nodes | N/A |
| Metaclass | Stays as infrastructure node | Special |
| Descriptors | Stay — they're class-level mechanisms | Yes |
| `__slots__` | Part of class-shell | Yes |

**The irreducible set is larger than in Approach A:** class declaration, inheritance, `__init__`, class attributes, instance attributes, dunder methods that define identity (`__repr__`, `__hash__`, `__eq__`), cross-contract bridge methods, and metaclass interactions.

## B.3 Extraction rules

**Extract when:**
1. A method clearly serves one contract and no other method in the class depends on it through shared mutable state.
2. A method is `@staticmethod` — always extract.
3. A method uses `self` only for attribute read access AND those attributes are logically part of one contract.
4. A group of methods forms a coherent sub-behavior (e.g., all Observer methods, all State-transition methods).

**Keep when:**
1. A method mutates state that other methods in different contracts also read — it's a bridge.
2. A method is a dunder that defines the class's external behavior (`__repr__`, `__iter__`, `__len__`).
3. A method uses `super()` in a cooperative inheritance chain.
4. A method is part of a framework's virtual dispatch contract (overridden for Qt/Django).

**The contract identification step is crucial.** For each class, before decomposition:
1. List all ABCs/protocols the class explicitly implements.
2. Identify implicit contracts: groups of methods that always change together, share the same subset of `self` attributes, or are tested together.
3. If a class has only one contract → it's a single-contract class → keep as contour (group of nodes) but still decompose methods within the contour.
4. If a class has multiple contracts → split along contract boundaries.

## B.4 Edge types

| Edge type | Meaning |
|---|---|
| `calls` | Standard |
| `implements` | Node implements a contract |
| `binds` | Node is a method of a class-shell (same as human's proposal) |
| `bridges` | Node connects two contracts within same class |
| `extends` | Class-shell extends another class-shell |
| `part_of_contract` | Node belongs to a contract-implementation contour |
| `alternative_to` | Same contract, different implementation |
| `tests` | Standard |

**Fewer new edge types than Approach A.** No `reads_state`/`writes_state` because state stays implicit in `self`. No `dispatches` because dispatch is handled by contract-node → implementations pattern.

## B.5 Framework-bound code

**General solution: Framework classes are single-contract classes.**

A `QMainWindow` subclass has one contract: "Qt widget." All its methods serve that contract. Therefore it doesn't split — it stays as one contour with `binds` edges.

But: extract any business logic that doesn't touch Qt APIs into free function-nodes. The Qt methods call those free functions. This is the same adapter pattern as Approach A, but less extreme — the class stays as a real class-shell node, not an adapter.

```python
# class-shell node (kind="class_shell")
class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._state = initial_state()

    def on_click(self):           # binds edge to class-shell
        self._state = handle_click(self._state)  # calls edge to handle_click
```

`handle_click` is a free function-node. `on_click` is a bound method-node. The class-shell holds the Qt contract; free functions hold reusable logic.

**Limitation:** If the business logic IS the Qt interaction (painting, layout, event handling), nothing can be extracted. The whole thing is framework-bound. In that case, the class stays as one contour-node.

## B.6 Builder requirements

1. **Class-shell metadata:**
   - Class name, bases, decorators, metaclass
   - `__init__` body (stored in class-shell node or in a bound init-node)
   - Class attributes (stored in class-shell)

2. **Bound method ordering:**
   - `binds` edges carry `method_name` and `position` (integer for ordering)
   - Builder collects all `binds` edges, sorts by position, indents, places inside class body

3. **Contract membership:**
   - `part_of_contract` edges group nodes into logical units
   - Builder doesn't need this for reconstruction — it's for agent navigation, not code assembly

**Builder complexity: MODERATE.** The builder reassembles classes from shells + bound methods. No state threading de-functionalization. No accessor rewriting. Simpler than Approach A.

## B.7 The boundary rule

**Decompose a class if and only if it serves more than one contract.**

- Single-contract class (e.g., `PercentDiscount` — only implements `DiscountStrategy`) → extract methods as free functions if possible, but keep as one contour. Class-shell + bound methods.
- Multi-contract class (e.g., `Order` — State management + calculations + building interface) → split along contract boundaries.
- Pure data class (e.g., `OrderItem` dataclass) → stays as one node (kind="data"). No decomposition. It's already atomic.
- Framework-bound class → extract business logic, keep framework glue.

**The F∩C balance:** Single-contract classes with few methods can stay as contours without greatly reducing F, because their methods, even if bound, are individually visible as nodes and can be found via search. A developer looking for "calculate discount" will find the bound method-node in a discount contour, not a black-box class-node.

## B.8 Worked example (900-line patterns code)

### ConfigManager + SingletonMeta

**Contracts identified:** 1 — "configuration store"

Single-contract → stays as contour. SingletonMeta is infrastructure → separate node.

**Nodes:**
1. `singleton_meta_call` — the `__call__` method as a standalone meta-function (function-node, free)
2. `ConfigManager` class-shell (class_shell node): declaration, `__init__`, class attrs
3. `config_get` — bound method (function-node, binds to shell)
4. `config_set` — bound method (function-node, binds to shell)
5. `config_repr` — bound method (function-node, binds to shell)

**5 nodes.** Simpler than Approach A's 6.

### EventBus

Single contract. 4 nodes: shell + subscribe + unsubscribe + publish.

### Strategy (DiscountStrategy)

**Contract node:** `calculate_discount` (contract-node)

Each implementation class is so small it becomes one node:
- `NoDiscount` → `no_discount(total) -> float` (function-node, implements contract) — no class needed
- `PercentDiscount` → `percent_discount(total, percent) -> float` (function-node)
- `FixedDiscount` → `fixed_discount(total, amount) -> float` (function-node)
- `TieredDiscount` → `tiered_discount(total) -> float` (function-node)

**5 nodes.** Same as Approach A — strategies are inherently functional.

### State pattern (OrderState)

**Contract nodes:** 5 (confirm, pay, ship, deliver, cancel)

Each state class is a single-contract implementation → stays as contour but methods are individually bound.

However, most deny methods are trivial. Under Approach B, each state class becomes a **single node** because:
- Single contract
- Methods are one-liners
- No extractable business logic

So: `DraftState` is one node, `ConfirmedState` is one node, etc.

**Nodes:**
- 5 contract-nodes
- 6 state-class nodes (one per state)
- 1 `deny_transition` utility function-node (shared)

**12 nodes** vs Approach A's ~35 (including micros). Much less granular.

### Order

**Contracts identified:** 2 — "state management" (confirm/pay/ship/cancel, _set_state) and "order data" (items, totals, metadata, repr).

Split along contracts:
1. `Order` class-shell (class_shell node): declaration, `__init__`, class attrs
2. `order_confirm` — binds, delegates to state (bridge between state management and state pattern)
3. `order_pay` — binds
4. `order_ship` — binds
5. `order_deliver` — binds
6. `order_cancel` — binds
7. `order_set_state` — binds (bridge method, publishes event)
8. `order_raw_total` — extracted as free function (pure computation, no self-mutation)
9. `order_total` — extracted as free function (delegates to discount strategy)
10. `order_repr` — binds

**10 nodes.**

### OrderBuilder

Single contract. Shell + 4 bound methods = 5 nodes.

### Payment hierarchy

Same as Approach A for the concrete implementations (they're single-method classes → become free functions). Factory node. Decorator becomes a wrapper contour. Proxy becomes a small class-shell with bound methods.

~14 nodes total.

### Chain of Responsibility

Each validator: single contract, one meaningful method → 4 free function-nodes + 1 runner. Same as Approach A.

### Adapter, Command, Iterator, Template Method

Adapter: 2 nodes (adapt_reserve, adapt_release) + 1 legacy API node.
Command: class-shell + execute + undo = 3 nodes per command + CommandHistory shell + 2 methods = 5 more.
Iterator: class-shell + filter_by_status + total_revenue = 3 nodes.
Template Method: contract-nodes for _header/_body/_footer + generate as free function + 2 implementations (PlainText, Markdown) as contours. ~9 nodes.

### Total node count for Approach B

~70 nodes from 900 lines. Less granular than Approach A's ~108.

---

# Approach C: Dual Representation — Graph + Class Template

## C.1 Proposal

Store **every method as a node** in the graph (maximizing searchability and reuse potential), but also store a **class template** as a first-class graph entity that describes how to reassemble the class. The class template is not code — it's a structural recipe.

**Core insight:** The graph and the class are two views of the same code. Neither is "the truth." The graph is the truth for the agent (searchable, granular, testable). The class is the truth for the runtime (dispatch, inheritance, framework compatibility). Instead of choosing one, maintain both and keep them synchronized.

**Class template node** (kind="class_template"):
```json
{
  "class_name": "Order",
  "bases": ["object"],
  "metaclass": null,
  "decorators": [],
  "class_attributes": [
    {"name": "_counter", "value": "0", "type": "int"}
  ],
  "method_order": ["__init__", "confirm", "pay", "ship", "deliver", "cancel", "_set_state", "raw_total", "total", "__repr__"],
  "slots": null,
  "docstring": "Main entity. Uses State for status management."
}
```

Every method exists as a **regular function-node** in the graph. The function-node stores the method's code as-is (with `self`), preserving it exactly as it would appear inside the class. The class_template links to its methods via `member_of` edges.

**Key difference from A and B:** Methods keep their `self` syntax. No state threading. No de-functionalization at build time. The builder reads the template, collects member nodes in order, indents them into the class body, and adds class attributes from the template. Trivially reversible.

**Reusability:** A method-node is findable by name, tags, and spec — even though it uses `self`. If an agent wants to reuse the logic, it can: (a) call the method through its class instance, or (b) the decomposition agent proactively extracts the pure logic into a companion free function-node at decomposition time.

## C.2 Taxonomy of irreducible class elements

Under Approach C, the class template absorbs all structural metadata:

| Element | Where it lives |
|---|---|
| Class declaration | class_template node |
| Inheritance | class_template.bases |
| Metaclass | class_template.metaclass |
| Class attributes | class_template.class_attributes |
| Class decorators | class_template.decorators |
| `__slots__` | class_template.slots |
| Docstring | class_template.docstring |
| Method ordering | class_template.method_order |
| Instance attributes | Visible in `__init__` method-node |
| Methods (all types) | Individual function-nodes |

**Nothing is irreducible in the sense of "can't be in the graph."** Everything is in the graph. The class_template is a structural node, not a code node. Methods are code nodes. The template tells the builder how to combine them.

## C.3 Extraction rules

**Default behavior: every method becomes its own node, keeping `self`.**

**Additionally extract (proactive duplication for reuse):**
- If a method contains pure logic that could be reused outside this class, the decomposition agent creates a companion free function-node and rewrites the method to call it. The method-node stays (for class reconstruction) but becomes a thin wrapper.
- `@staticmethod` methods are stored both as the method-node (member_of class) and as a free function-node (no class dependency). Two nodes, same code, `alias_of` edge between them.

**Never extract:**
- Nothing is never extracted — everything is a node. The question is whether an additional free-function companion is created.

**Companion extraction heuristic:**
- Method uses `self` only for reads → create companion.
- Method is a pure computation → create companion.
- Method is a framework callback or dunder → don't create companion (unlikely to be reused).
- Method mutates `self` in domain-specific ways → don't create companion (the mutation semantics are class-bound).

## C.4 Edge types

| Edge type | Meaning |
|---|---|
| `calls` | Standard |
| `member_of` | Method-node belongs to a class_template |
| `implements` | Method implements a contract-node |
| `extends` | class_template extends another class_template |
| `alias_of` | Free function is the extracted twin of a method |
| `alternative_to` | Same contract, different class's implementation |
| `tests` | Standard |

**Simpler edge vocabulary than A or B.** The `member_of` edge replaces both `binds` and `reconstructs`. No `dispatches`, `reads_state`, `writes_state`, `bridges` — those are Approach A/B concerns.

**member_of edge metadata:**
```json
{
  "method_name": "confirm",
  "method_type": "method",  // or "classmethod", "staticmethod", "property"
  "position": 5  // ordering in method_order
}
```

## C.5 Framework-bound code

**General solution: class_template handles it natively.**

Framework-bound classes work identically to any other class. The class_template records `bases: ["QMainWindow"]`. Methods are nodes. Builder reconstructs the class. No special adapter nodes, no special shell nodes.

**This is Approach C's strongest advantage for framework code.** The class template was designed to represent classes faithfully, so framework requirements are naturally satisfied.

**Business logic extraction:** Same as the companion function strategy. A Qt callback's pure logic becomes a free companion function. The callback method-node stays, calling the companion.

## C.6 Builder requirements

1. **Read class_template node** — get class name, bases, metaclass, decorators, class attributes, method order, slots, docstring.
2. **Collect all member_of edges** — get method-nodes, sorted by position.
3. **Assemble:**
   - Write class declaration line from template
   - Write docstring if present
   - Write class attributes from template
   - For each method (in order): indent the method-node's code by 4 spaces, place in class body
   - Apply decorators to class
   - If metaclass specified, add `metaclass=` to class declaration

**Builder complexity: LOW.** This is essentially string concatenation with indentation. No de-functionalization, no state rewriting, no bridge resolution. The builder is a glorified `cat` with indent.

**Reconstruction is trivially correct** because method-nodes store their code in the exact form they'll appear in the class. The builder just wraps them.

## C.7 The boundary rule

**Every class gets a class_template. Every method becomes a node. The question is only: which methods get companion free-function nodes?**

- Companion created: pure logic, read-only `self`, reuse-likely methods
- Companion not created: framework callbacks, dunders, bridge methods, heavily stateful methods

**The F∩C balance:** F is maximized because every method is a node (findable, testable). C doesn't reduce F because class_templates are structural metadata, not code-containing nodes that compete with function-nodes. A method bound to a class via `member_of` is still a function-node with all the graph properties (search, tags, specs, versions).

**When to NOT create a class_template:** When a class has zero state, one or two methods, and is essentially a function in a trenchcoat (e.g., `NoDiscount` which is `return total`). In that case: just make it a function-node, no template. The threshold: if the class has <=2 methods and no instance attributes, it's a disguised function.

## C.8 Worked example (900-line patterns code)

### ConfigManager + SingletonMeta

**SingletonMeta:**
- class_template: `{name: "SingletonMeta", bases: ["type"], class_attributes: [{name: "_instances", value: "{}"}]}`
- `singleton_meta_call` method-node (the `__call__` override)

**ConfigManager:**
- class_template: `{name: "ConfigManager", bases: [], metaclass: "SingletonMeta"}`
- `config_init` method-node (`__init__`)
- `config_get` method-node
- `config_set` method-node
- `config_repr` method-node
- *Companion:* `get_from_dict(settings, key, default) -> Any` free function (alias_of `config_get`)

**6 nodes + 2 templates.**

### Strategy pattern

`DiscountStrategy` is an ABC → class_template with abstract methods as contract-nodes.

`NoDiscount`, `PercentDiscount`, `FixedDiscount` each have <=2 methods → **disguised functions, no template.** Become free function-nodes directly.

`TieredDiscount` has class attribute `_tiers` → class_template + 1 method-node. Or: `_tiers` becomes a parameter, and it too is a free function.

**Decision:** All four concrete strategies become free function-nodes. The ABC becomes a contract-node. **5 nodes**, same as A and B.

### State pattern

Each state class (DraftState, etc.) has 5 methods but most are one-line denials. Under Approach C:

Option 1: Each state class gets a template + 5 method-nodes = 6 entities per state = 36 entities. Too many.

Option 2: State classes with mostly trivial methods → treat as single nodes (each state is one function-node containing all 5 methods in one block). The class_template is optional here.

**Decision:** Each state class is small enough to be a single node. 6 state-nodes + 5 contract-nodes + 1 base class template = **12 entities**.

### Order

- class_template for Order
- method-nodes: `__init__`, confirm, pay, ship, deliver, cancel, `_set_state`, raw_total (property), total (property), `__repr__`
- Companion free functions: `calc_raw_total(items) -> float`, `calc_total(raw_total, strategy) -> float`

**12 nodes + 1 template.**

### Full system

| Category | Method-nodes | Templates | Companions | Contract-nodes | Free function-nodes |
|---|---|---|---|---|---|
| Singleton/Config | 5 | 2 | 1 | 0 | 0 |
| Observer/EventBus | 3 | 1 | 0 | 0 | 0 |
| Strategy | 0 | 0 | 0 | 1 | 4 |
| State | 0 | 0 | 0 | 5 | 6 (whole class nodes) |
| Order | 10 | 1 | 2 | 0 | 0 |
| OrderBuilder | 4 | 1 | 0 | 0 | 0 |
| Payment (all) | 12 | 2 | 0 | 3 | 3 (small impls) |
| Chain of Resp. | 4 | 4 | 0 | 1 | 1 |
| Adapter | 4 | 2 | 0 | 1 | 0 |
| Command | 5 | 2 | 0 | 1 | 0 |
| Iterator | 4 | 1 | 0 | 0 | 0 |
| Template Method | 6 | 2 | 0 | 2 | 1 |
| **Total** | **~57** | **~18** | **~3** | **~14** | **~15** |

**~107 entities** (89 code-containing nodes + 18 templates). Templates are lightweight (JSON metadata, not code), so effective complexity is closer to ~89 code nodes.

---

# 9. Comparison Table

| Axis | A: Maximum Decomposition | B: Contract-Boundary | C: Dual Representation |
|---|---|---|---|
| **Reusability** | 10/10 — every function is free, all logic visible | 7/10 — bound methods less reusable than free functions | 8/10 — methods are nodes (findable) + companions for key logic |
| **Builder complexity** | 9/10 (very complex) — state threading, de-functionalization, accessor rewriting | 4/10 (moderate) — shell + bound methods, no rewriting | 2/10 (trivial) — indent and concatenate |
| **Framework compatibility** | 6/10 — adapter nodes work but require explicit delegation layer | 8/10 — class-shell preserves framework structure | 10/10 — classes reconstructed exactly as-is |
| **Information loss** | 7/10 — loses method ordering, implicit self semantics, fluent interfaces | 3/10 — preserves most OOP semantics | 1/10 — loses nothing (both views maintained) |
| **Decomposition cost** | 9/10 (very expensive) — every method rewritten, state made explicit, contracts identified | 6/10 (moderate) — contract identification + selective extraction | 3/10 (cheap) — split methods into nodes, optionally create companions |
| **Node count (900-line example)** | ~108 | ~70 | ~89 code + 18 templates |
| **Preserves OOP semantics** | No — OOP is fully dissolved | Partially — contracts preserved, some classes intact | Yes — full class structure in templates |
| **Agent context efficiency** | High — every node is self-contained | High — contours are focused | Medium — method-nodes with `self` need class context to understand |
| **Testability of individual nodes** | 10/10 — every function takes explicit args | 7/10 — bound methods need class instance to test | 6/10 — method-nodes need class or mocking of self |
| **Handles GoF patterns** | All 13 dissolved cleanly | All 13 handled but some stay as contours | All 13 represented as nodes; class structure preserved |

Scoring: higher = more of that quality. For builder complexity and decomposition cost, higher = MORE costly.

---

# 10. Recommendation

**I recommend Approach C (Dual Representation) as the starting strategy, with elements of Approach A applied selectively.**

### Why C first

1. **Builder simplicity.** Contour Graph doesn't have a builder yet. Starting with the simplest possible builder (indent + concatenate) means the system can be operational sooner. A complex builder (Approach A) is a major engineering effort that blocks everything downstream.

2. **Zero information loss.** The class template preserves the exact original structure. This means decomposition is reversible — you can always get back the original class. With Approach A, the original class is gone; reconstruction is an approximation.

3. **Framework compatibility is automatic.** No adapter nodes, no special handling. Qt, Django, PyQt — all work because the builder reconstructs real classes.

4. **Dunbar context works naturally.** A method-node's spec_summary can describe what it does without needing the full class context. The class_template provides the structural context at the ticket level. An agent seeing `order_confirm` method-node + `Order` template ticket has enough context.

5. **Progressive enhancement.** You can start with C and selectively apply A's techniques (companion free functions, state threading) for specific high-value cases. The graph doesn't prevent you from having both a bound method-node AND a free companion.

### When to use Approach A's techniques within C

- When a method's logic is clearly reusable outside its class → create a companion free function.
- When a class is a "function in a trenchcoat" (1-2 methods, no state) → skip the template, just make function-nodes.
- When the Strategy pattern is used → always dissolve to free functions (strategies are inherently functional).
- When the State pattern is used → each state class can be a single node (no template needed if small enough).

### When Approach B is relevant

- Approach B's contract identification is valuable as an analytical tool even within Approach C. Before decomposing a class, identifying its contracts helps decide which methods get companion functions and how to group them in tags.

### Caveats

1. **Approach C's testability weakness.** Method-nodes with `self` are harder to test in isolation than Approach A's pure functions. Mitigation: the companion strategy. Key methods get companion free functions that ARE testable. The method-node itself is tested through the class (integration test), while the companion is unit-tested.

2. **The F∩C concern is partially unresolved.** Method-nodes bound to a class via `member_of` are more reusable than whole-class nodes (they're individually searchable) but less reusable than Approach A's free functions. The companion strategy is the escape valve — but it depends on agent judgment at decomposition time.

3. **Template synchronization.** If an agent modifies a method-node, the class_template must stay consistent (method_order, method_type). This is a constraint the coordinator must enforce. Edge consistency is harder with two representations.

4. **Approach A is the theoretical optimum for reuse.** If the builder engineering cost were zero, A would be strictly better for reuse. C is a pragmatic choice, not a theoretical one. As the system matures and builder capabilities grow, migrating individual classes from C-style to A-style decomposition is possible and should be considered.

### The gradient

In practice, a real codebase would use a mix:
- **Pure functions / strategies / validators** → Approach A (dissolve to free functions, no class template)
- **Domain entities with state** → Approach C (template + method-nodes + companion functions for key logic)
- **Framework-bound classes** → Approach C (template preserves framework structure exactly)
- **Large multi-responsibility classes** → Approach B's analysis (identify contracts) + Approach C's representation (template + method-nodes grouped by contract tags)

This gradient is not a compromise — it's the natural consequence of different code having different decomposition economics. A Strategy class and a QMainWindow subclass should not be decomposed the same way.

---

# 11. Versioning and Class Templates

## The problem

In Contour Graph, versioning is at the node level. An agent modifies a node → new version with `task_id`. Multiple agents can produce competing versions → tournament selects the best via behavioral testing. The lifecycle: `draft → test_build → test → golden` or `rejected`.

Class templates introduce a coupling problem: a `class_template` node references N method-nodes via `member_of` edges. When method-node M gets a new version (v2 draft), the template still points to M. Which version of M does the builder use? Who keeps things in sync? What happens when two method-nodes of the same class are modified by independent agents simultaneously?

## Principle: the template is structural, not versioned per-method-change

**The class_template does not version when a method changes. It versions only when the class structure changes.**

A method getting a v2 is a content change to an existing node — the node's identity (name, position in class, type) doesn't change. The template describes structure: "class Order has methods [__init__, confirm, pay, ...] in this order, with these bases and these class attributes." That structure is unaffected by `confirm` getting a new implementation.

**Version resolution is the builder's job, not the template's.** The builder already knows about the version lifecycle (golden, draft, etc.). When building:
- `build` mode: builder picks the **golden** version of each `member_of` method-node.
- `test_build` mode: builder picks **one draft** method-node (the one being tested) + **golden** for all others.
- No template change needed in either case.

This means the template is a **stable structural anchor**. It changes rarely — only when the class's shape changes (new method added, method removed, inheritance changed, class attribute modified).

## When the template DOES version

Structural changes require a new template version:

| Change | Template version needed? | Why |
|---|---|---|
| Method implementation rewritten | No | Same method name, same position, same type. Builder resolves version. |
| New method added to class | **Yes** | `method_order` changes. New `member_of` edge. |
| Method removed from class | **Yes** | `method_order` changes. `member_of` edge removed. |
| Method renamed | **Yes** | `method_order` changes. `member_of` edge metadata changes. |
| Method type changed (method → property) | **Yes** | `member_of` edge metadata changes. |
| Inheritance changed | **Yes** | `bases` changes. |
| Class attribute added/removed/changed | **Yes** | `class_attributes` changes. |
| Metaclass changed | **Yes** | `metaclass` changes. |
| Method reordering (cosmetic) | **Yes** (minor) | `method_order` changes. |

Template versioning follows the same lifecycle as method-nodes: draft → test_build → golden. A template draft means: "I propose that class Order should now have this new structure." The builder test_builds the new structure, tester validates, coordinator promotes or rejects.

## Scenario: single method change

Agent A modifies `order_confirm` (method-node), producing `order_confirm` v2 (draft).

1. Coordinator triggers `test_build`: builder constructs class Order using **template golden** + **order_confirm v2** + **all other methods golden**.
2. Tester runs tests against the built class.
3. If pass: `order_confirm` v2 → golden. Template unchanged. `member_of` edge still points to `order_confirm` (by node identity, not version ID).
4. If fail: `order_confirm` v2 → rejected. Nothing else affected.

**No template involvement.** Clean and simple.

## Scenario: two methods changed simultaneously by different agents

Agent A modifies `order_confirm` → v2 draft.
Agent B modifies `order_pay` → v2 draft.

These are independent — neither agent knows about the other's work.

1. **Independent test_builds:**
   - Test_build for Agent A: template golden + `order_confirm` v2 + `order_pay` v1 (golden) + rest golden.
   - Test_build for Agent B: template golden + `order_confirm` v1 (golden) + `order_pay` v2 + rest golden.

2. **Both pass independently.** Each is promoted to golden.

3. **Combination validation (critical step):** After both promotions, the coordinator triggers a **full class rebuild**: template golden + `order_confirm` v2 (new golden) + `order_pay` v2 (new golden) + rest golden. This catches interaction bugs — method A's new behavior might conflict with method B's.

4. **If combination fails:** One or both versions must be demoted. The coordinator can:
   - Roll back the later promotion (LIFO — the second-to-be-promoted goes back to draft).
   - Or trigger a tournament: test each independently against the other's new golden, find which one is incompatible.

**This is the same problem as two agents modifying two nodes that `calls` each other.** It's not specific to class templates — it's a general concurrent-modification problem in the graph. The class template doesn't make it worse or better; it just makes the coupling explicit (both methods are `member_of` the same template).

## Scenario: structural change + method change simultaneously

Agent A modifies `order_confirm` → v2 draft (content change).
Agent C adds a new method `order_refund` to Order → template v2 draft + new `order_refund` node.

1. Agent A's test_build uses template v1 (golden) + `order_confirm` v2. Works normally.
2. Agent C's test_build uses template v2 (draft, with `order_refund` in method_order) + `order_refund` v1 + all other methods golden.
3. Both pass independently. Agent A's method is promoted. Agent C's template v2 + `order_refund` are promoted.
4. Now the golden state is: template v2 (includes `order_refund`) + `order_confirm` v2 (golden) + `order_refund` v1 (golden). Consistent.

**No conflict** — structural changes and content changes are orthogonal. The template version added a method; the method version changed an implementation. They compose cleanly.

**Conflict case:** Agent C's new method `order_refund` calls `order_confirm`. Agent A changed `order_confirm`'s contract (different return value). Now `order_refund` works with old `order_confirm` but breaks with new. Same solution as above: combination validation catches it.

## Scenario: two agents both make structural changes

Agent C adds `order_refund` → template v2a draft.
Agent D adds `order_archive` → template v2b draft.

Both agents started from template v1 golden. They produced competing structural versions.

**This is a genuine conflict.** Template v2a has `method_order: [..., order_refund]`. Template v2b has `method_order: [..., order_archive]`. Neither includes the other's method.

**Resolution options:**

**Option 1: Tournament (default).** One template wins. The losing agent's method-node still exists in the graph but isn't `member_of` any golden template. The coordinator can then create template v3 that merges both — but this requires either an agent to do the merge or an automated merge (append both methods to method_order, which is safe if they're independent).

**Option 2: Structural merge rule.** Since templates are JSON metadata (not code), many structural changes are mechanically mergeable:
- Two additions to `method_order` → append both (order is cosmetic anyway).
- One addition + one removal → apply both.
- Two modifications to the same field (e.g., both change `bases`) → conflict, needs agent resolution.

**Proposed rule:** The coordinator attempts auto-merge for template conflicts. If the merge is mechanical (non-overlapping additions/removals), it produces a merged template v3 automatically. If the merge is ambiguous (same field changed differently), it escalates to the sergeant.

**This is analogous to git merge for structured data.** JSON templates are simpler than code — most merges are trivially safe.

## The `member_of` edge: identity vs. version

A key design decision: does the `member_of` edge point to a **node identity** (all versions) or a **specific version**?

**Recommendation: point to node identity.** The edge says: "method `confirm` of class `Order` is implemented by node `order_confirm`." It doesn't say which version. The builder resolves versions at build time based on the build mode (golden, draft, etc.).

This means:
- `member_of` edges are stable — they don't change when methods are versioned.
- The builder needs a version-resolution strategy (already exists in the system for all node types).
- A method-node that is `member_of` a class_template can have 5 versions; the edge doesn't care.

**If the edge pointed to specific versions,** every method version change would require updating the edge, which would require updating the template (since edges are associated with nodes), which would require template versioning. This creates a cascade of versions for every content change — exactly what we want to avoid.

## Template lifecycle summary

```
Template created (v1 golden) — defines class structure
    │
    ├── Method-node content changes → template unchanged, builder resolves versions
    │
    ├── Structural change (add/remove method, change bases) → template v2 draft
    │       │
    │       ├── test_build with new structure → pass → template v2 golden
    │       │
    │       └── test_build fails → template v2 rejected, v1 stays golden
    │
    └── Two structural changes conflict → auto-merge if possible, escalate if not
```

## Impact on Dunbar context

For Dunbar context packages, the class_template at different granularities:

| Dunbar level | What the agent sees |
|---|---|
| **as_is** | Full template JSON + all member method-nodes (full code) |
| **summary** | Template structure (class name, bases, method names) + method summaries |
| **ticket** | "Class Order: 10 methods, extends object, manages order lifecycle with state pattern" |
| **name** | "Order" |

The template at `ticket` level is a powerful orientation tool — it tells the agent "this is a class with these methods" without loading any code. An agent working on `order_confirm` sees the template ticket and knows the class context without reading 9 other methods.

## Open question: template garbage collection

If all methods of a class are deprecated/removed, should the template be auto-removed? Or does it persist as a historical record?

**Proposed rule:** A template with zero `member_of` edges pointing to golden nodes → status changes to `deprecated`. After TTL (same as node GC), it's removed. This follows the existing GC pattern: nodes without incoming edges and without golden status are cleaned up.

---

# 12. Hybrid A+B: Stability Floor with Potential Ceiling

## Context: Experiment 08 findings

Experiment 08 tested all three approaches on Order class decomposition (process_refund task, 9 soldiers, Dunbar context from API):

- **Approach A** (Max Decomposition): median 19/25, variance low (19-20 range). Functional decomposition gives the agent unambiguous code — explicit state, explicit dispatch. No guesswork.
- **Approach B** (Contract-Boundary): median 17/25, but one soldier (B2) scored 24/25. B2 understood the State-Observer bridge from spec descriptions and wrote architecturally superior code. B1/B3 wrote generic code — they didn't "see" the patterns.
- **Approach C** (Dual Representation): median 18/25. Most information in Dunbar package (10 depth-1 nodes) but the class_template JSON at depth 0 carries no code — weaker anchoring.

**Critical insight:** Code at depth 0 (the node the agent is directly working on) matters more than quantity at depth 1. Approach A placed real dispatch logic at depth 0 = consistent performance. Approach C placed JSON metadata at depth 0 = weaker despite more total information.

**The B2 phenomenon:** Soldier B2 outperformed all 9 soldiers (including A's consistent 19-20) because it received contract-level architectural descriptions in spec_summary. It didn't just know "this function calculates discount" — it knew "this function is the Strategy dispatch point; Observer fires on state transitions; the State pattern controls which transitions are valid." This primed B2 to think architecturally, producing code that correctly integrated with the State-Observer bridge without ever seeing that bridge's code.

## The question: can we get A's floor with B2's ceiling?

The human's proposal: decompose using Approach A (stable, functional graph). But enrich `spec_summary` with B-style architectural descriptions — contract relationships, pattern semantics, interaction bridges. Run tournaments: one soldier with pure A context, one with A + enriched specs. The enriched soldier has B2 potential; the pure-A soldier is the safety net.

## 12.1 Is this coherent?

**Yes, and it's not even a compromise — it's orthogonal.**

Approach A defines the **graph structure**: how code is stored, how nodes connect, how the builder reconstructs classes. This is a storage and build-time concern.

Spec_summary is a **context-time concern**: what the agent sees when it receives a Dunbar package. Specs describe nodes — they don't change node structure. A spec_summary that says "this function is part of the State pattern" doesn't add a `state_pattern` edge or a class-shell node. It adds information for the agent's reasoning, not for the builder's assembly.

**The potential contradiction:** If enriched specs describe class-level concepts ("Order is a class with confirm/pay/ship methods") but the graph contains only free functions (`order_confirm`, `order_pay`, `order_ship`), the agent might be confused — "the spec says this is a method but I see a standalone function."

**Resolution:** The enriched spec must be written from the graph's perspective, not the class's perspective. Instead of "Order.confirm() transitions state," write:

> `order_confirm` is the state-transition function for Draft→Confirmed in the Order state machine. It is one of 5 transition functions (order_confirm, order_pay, order_ship, order_deliver, order_cancel) that share the `OrderState` schema and interact with `publish_event` for Observer notification. The transition rules are enforced by `dispatch_order_action`, which routes to the appropriate transition function based on current state.

This is A-structured (functions, schemas, dispatch) but B-enriched (pattern names, interaction semantics, architectural role). The agent sees the big picture without any structural contradiction.

## 12.2 What enriched spec_summary should contain

The regular spec_summary for an A-decomposed node answers: **what does this function do?**

The enriched spec_summary additionally answers:
1. **What pattern does this function participate in?** (State, Observer, Strategy, etc.)
2. **What is its architectural role within that pattern?** (transition function, dispatch point, event publisher, strategy implementation)
3. **What are its siblings?** Not just "calls X, Y, Z" (that's edges) but "is one of N alternative implementations" or "is one step in a pipeline of M steps."
4. **What invariants does it maintain?** "After calling this function, the state must be in {CONFIRMED, CANCELLED} — no other states are valid."
5. **What is the interaction bridge?** "When this function changes state, it calls publish_event, which triggers any subscribed handlers — including refund_requested listeners when cancelling from PAID state."

### Concrete examples for Order system

**Regular A-spec for `order_confirm`:**
```
Transitions an order from DRAFT to CONFIRMED status.
Accepts: order state (OrderState schema).
Returns: updated OrderState with status=CONFIRMED.
Raises: InvalidStateTransition if current state is not DRAFT.
```

**Enriched A+B spec for `order_confirm`:**
```
State pattern transition: DRAFT → CONFIRMED. One of 5 state transitions
for Order (confirm, pay, ship, deliver, cancel). Routed by
dispatch_order_action based on current status.

Accepts: order state (OrderState schema).
Returns: updated OrderState with status=CONFIRMED.
Raises: InvalidStateTransition if current state is not DRAFT.

Observer bridge: calls publish_event("order_status_changed") with
old and new status. Downstream handlers may trigger side effects
(e.g., warehouse reservation, notification).

Sibling transitions from DRAFT: confirm (→CONFIRMED), cancel (→CANCELLED).
No other transitions valid from DRAFT.
```

**Regular A-spec for `proxy_execute`:**
```
Executes a payment through a lazy-initialized proxy.
Checks fraud threshold before delegating.
Accepts: proxy state (ProxyState), amount (float).
Returns: (updated ProxyState, bool success).
```

**Enriched A+B spec for `proxy_execute`:**
```
Proxy pattern: lazy initialization + fraud guard for payment execution.
Wraps any payment implementation (card, crypto, invoice) via
create_payment factory. First call triggers initialization and
logging decorator wrapping.

Accepts: proxy state (ProxyState), amount (float).
Returns: (updated ProxyState, bool success).

Guard: if amount > config.fraud_threshold, publishes fraud_alert
event and returns False without initializing real payment.
Observer bridge: fraud_alert event may trigger external handlers.

Chain: proxy_execute → (lazy init) → logging_payment_execute → concrete payment.
Three layers of wrapping, each with distinct responsibility.
```

### The pattern

Enriched specs follow a template:

```
[Pattern name]: [role of this function in the pattern]. [Sibling/alternative
functions in the same pattern].

[Regular spec: accepts, returns, raises]

[Interaction bridges]: [what events/calls connect this to other patterns]
[Invariants]: [what must be true before/after this function]
[Chain/pipeline position]: [where this sits in the execution flow]
```

This is 3-5 extra lines per spec. Not expensive to write. An agent or a senior-rank can generate enriched specs from the graph structure + pattern recognition.

## 12.3 Does enriched spec degrade A stability?

**In theory, yes — a misleading spec is worse than no spec.** If the enriched spec describes a pattern that doesn't exist, or describes an interaction bridge incorrectly, the agent will write code that integrates with a phantom architecture.

**In practice, the tournament catches it.** The design explicitly runs two soldiers:
- Soldier 1: pure A context (regular specs). Baseline.
- Soldier 2: A context + enriched specs. Potentially better, potentially confused.

Three outcomes:
1. **Enriched wins.** Soldier 2 produced architecturally superior code (B2 effect). Enriched spec worked.
2. **Tie or pure-A wins.** Enriched spec didn't help or slightly confused. Pure-A result is used. No harm done — the tournament absorbed the risk.
3. **Both fail.** The task is hard regardless. Escalate.

**The tournament is the safety mechanism.** It guarantees that enriched specs can never produce a *worse* outcome than pure A — because pure A is always the alternative. The worst case is: enriched soldier fails, pure-A soldier produces A's baseline (19/25). The system pays the cost of one extra soldier (tokens, time) for the option of B2-level output.

**When the tournament might fail to catch it:** If the enriched spec causes subtle architectural misalignment that passes tests but creates maintenance debt. Example: enriched spec says "Observer fires on state change" but doesn't mention that the handler for `refund_requested` expects the order to still be in PAID state when it runs. Soldier 2 writes code that changes state before publishing the event. Tests pass (they don't test handler ordering). But the code is wrong.

**Mitigation:** This is a spec quality problem, not a structural problem. The enriched spec should capture the invariant ("state must still be PAID when refund_requested fires"). If the spec is wrong, the code will be wrong — but that's true for any spec, enriched or not.

## 12.4 Is there a simpler mechanism?

Three alternatives considered:

### Alternative 1: Richer tags instead of enriched specs

Add pattern tags to nodes: `order_confirm` gets tags `[state_pattern, order, transition]`. Agent infers pattern membership from tags.

**Problem:** Tags say "what" but not "how" or "why." Knowing that `order_confirm` is tagged `state_pattern` tells the agent it's related to state management, but not that it's a Draft→Confirmed transition, not that Observer fires after it, not that only confirm and cancel are valid from Draft. Tags are too thin to capture B2's insight.

**Verdict:** Tags are complementary (use them for search/discovery) but insufficient as the sole enrichment mechanism.

### Alternative 2: Architecture notes as separate nodes

Create `architecture_note` nodes (kind="note") that describe patterns, bridges, and invariants. Link them to relevant function-nodes via `describes` edges. Agent's Dunbar context includes architecture notes at depth 1.

**Problem:** This adds a new node kind that isn't code, isn't a spec, and isn't a template. It's a free-floating text blob that the agent may or may not read. Spec_summary is already part of the Dunbar context pipeline — architecture notes would need to be grafted into it.

**Verdict:** Over-engineered. Spec_summary already exists, already flows through Dunbar, already has four granularity levels. Enriching it is cheaper than creating a new node kind.

### Alternative 3: Just write better regular specs

Instead of splitting "regular" and "enriched" specs, just make all specs rich from the start. Every spec_summary includes pattern membership, bridges, and invariants. No "two tiers" of specs.

**Problem:** Writing enriched specs for every node is expensive. Most nodes don't participate in interesting patterns — `format_config` doesn't need an architecture paragraph. The enrichment is high-value only for nodes at pattern boundaries (dispatch points, state transitions, event publishers, adapter interfaces). Enriching every node dilutes the signal and wastes decomposition effort.

**Verdict:** This is the simpler mechanism — but apply it selectively. Enrich specs for pattern-boundary nodes only. Leave simple nodes with simple specs. This is effectively the hybrid proposal, minus the "two tiers" framing.

## 12.5 Concrete design proposal

### Which nodes get enriched specs?

A node qualifies for enrichment if it meets any of these criteria:
1. **Dispatch point:** routes to multiple implementations (Strategy dispatch, State dispatch, Factory create).
2. **Pattern bridge:** connects two patterns (state transition that fires Observer events, Command that uses Payment and Warehouse).
3. **Contract implementation with siblings:** one of N alternative implementations of the same contract (card_execute vs crypto_execute vs invoice_execute).
4. **Event publisher/subscriber:** calls `publish_event` or is registered as a handler.
5. **Pipeline entry point:** first function in a multi-step chain (proxy_execute → logging → concrete payment).

Rough estimate for the 900-line example: ~15-20 of the ~68 function-nodes qualify. The rest keep regular specs.

### Who writes enriched specs?

**Option A: Decomposition agent.** When the corporal decomposes a class, it identifies patterns and writes enriched specs for boundary nodes. This is natural — the corporal already understands the class's architecture during decomposition.

**Option B: Dedicated spec-enrichment pass.** After decomposition, a sergeant-level agent reviews the graph, identifies pattern-boundary nodes, and enriches their specs. This decouples decomposition from enrichment.

**Recommendation: Option A** for initial decomposition (the corporal already has the context), **Option B** for periodic review (specs drift as the graph evolves — a periodic enrichment sweep catches stale pattern descriptions).

### Tournament protocol

For tasks on pattern-boundary nodes:

1. Coordinator identifies the target node as enriched (has enriched spec_summary).
2. Coordinator spawns two soldiers:
   - **Soldier-baseline:** Dunbar context with regular spec (strip enrichment from spec_summary at context assembly time).
   - **Soldier-enriched:** Dunbar context with enriched spec (full spec_summary).
3. Both soldiers produce draft versions.
4. Both go through test_build → test.
5. If both pass: pick the one with higher quality score (from tester's evaluation, or from a judge-agent comparison).
6. If only one passes: use it.
7. If neither passes: escalate.

**Cost:** 2x tokens for enriched-node tasks. But enriched nodes are ~25% of all nodes, and not all tasks target enriched nodes. Average cost increase: ~25% more soldier-tokens, for a potential 20% quality improvement on critical nodes.

### Spec_summary schema

```
spec_summary:
  what: "Transitions order from DRAFT to CONFIRMED"      # always present
  contract: "accepts OrderState, returns OrderState"       # always present
  pattern: "State pattern, DRAFT→CONFIRMED transition"     # enriched only
  siblings: ["order_pay", "order_cancel"]                  # enriched only
  bridges: ["publish_event(order_status_changed)"]         # enriched only
  invariants: ["input state must be DRAFT"]                # enriched only
  chain: null                                              # enriched only
```

Or as free text (cheaper, harder to parse but sufficient for LLM consumption):

```
spec_summary: |
  Transitions order from DRAFT to CONFIRMED.
  Accepts: OrderState. Returns: OrderState. Raises: InvalidStateTransition.

  [Pattern] State: DRAFT→CONFIRMED. Siblings: order_pay, order_cancel (from DRAFT).
  [Bridge] Publishes order_status_changed via publish_event after transition.
  [Invariant] Input state must be DRAFT; output state is always CONFIRMED.
```

**Recommendation: free text.** Structured fields are harder to maintain and the consumer is an LLM, not a parser. Free text with lightweight conventions (`[Pattern]`, `[Bridge]`, `[Invariant]` prefixes) is sufficient and cheaper to write.

## 12.6 Summary

The hybrid A+B is not a contradiction — it's separation of concerns. The graph structure (A) is optimized for storage, versioning, building, and testing. The spec content (B-enriched) is optimized for agent reasoning. They operate at different layers and don't interfere.

The tournament mechanism makes this zero-risk: enriched specs can only improve outcomes (if they work) or be ignored (if they don't, because the baseline soldier's output is used). The cost is bounded (2x tokens on ~25% of tasks = ~25% total token increase).

The real question is not "does this work?" but "is enrichment worth maintaining?" Specs drift. Patterns evolve. An enriched spec that describes a State pattern bridge is only accurate as long as the state dispatch and Observer are wired the same way. When someone rewrites the event system, every enriched spec mentioning `publish_event` becomes stale. The periodic spec-enrichment sweep (Option B above) is not optional — it's the maintenance cost of this approach.
