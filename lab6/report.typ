#set page(paper: "a4")
#set figure(supplement: [Рисунок])
#show heading: set text(size: 14pt)

#align(center, text(14pt)[
  *Лабораторна робота №6*\
  Atomic Swap:\
  тристоронній обмін умовною криптовалютою на основі HTLC
])

= Середовище виконання

Лабораторна робота виконана з використанням наступних технологій та інструментів:

- *Мова програмування:* Python 3.12
- *Операційна система:* macOS (Tahoe 26.2)
- *Основні бібліотеки:*
  - `multiprocessing` — для створення окремих процесів та синхронізації
  - `multiprocessing.managers` — `Manager()` для розподіленого спільного стану
  - `threading` — фоновий потік спостереження за леджером у кожному процесі-учасникові
  - `hashlib` — SHA-256 для хешування секрету
  - `json` — структуроване логування подій

= Загальний опис проєкту

Проєкт реалізує симуляцію тристороннього атомарного обміну умовною криптовалютою. Три учасники — A, B та C — обмінюються монетами за циклічною схемою:

- A передає CoinA → B
- B передає CoinB → C
- C передає CoinC → A

Кожна передача захищена смарт-контрактом типу HTLC (Hash Time-Locked Contract). Кожен учасник виконується як окремий процес ОС (`multiprocessing.Process`). Спільний стан (баланси та контракти) зберігається через `multiprocessing.Manager`.

== Структура проєкту

Код розподілено по окремих модулях:

- `models.py` — перерахування `ContractStatus`, `Asset`, `PartyName`; моделі повідомлень (`CreateHtlcMsg`, `RedeemMsg`, `RefundMsg`, `WatchMsg`, `ShutdownMsg`); `TypedDict` `Contract`
- `htlc.py` — хешування секрету, верифікація, функції `create_contract()`, `redeem_contract()`, `refund_contract()`
- `ledger.py` — клас `Ledger`: операції з балансами та контрактами через Manager-проксі
- `party.py` — клас `Party(mp.Process)`: цикл обробки повідомлень + фоновий потік спостереження за леджером
- `logger.py` — функції `log_event()` (JSON до stdout) та `print_state()` (підсумок сценарію)
- `main.py` — точка входу; три сценарії виконання

== Типи (Enum)

Замість рядкових констант визначено перерахування з наслідуванням від `str`, що дозволяє використовувати значення безпосередньо у рядках та зберігати їх у Manager-проксі без додаткової серіалізації:

```python
class Asset(str, Enum):
    COIN_A = "CoinA"
    COIN_B = "CoinB"
    COIN_C = "CoinC"

class PartyName(str, Enum):
    A = "A"
    B = "B"
    C = "C"

class ContractStatus(str, Enum):
    PENDING  = "pending"
    REDEEMED = "redeemed"
    REFUNDED = "refunded"
```

== Моделі повідомлень

Вхідна черга кожного учасника типізована як `mp.Queue[PartyMsg]`, де `PartyMsg` — об'єднання п'яти заморожених датакласів:

```python
@dataclass(frozen=True)
class CreateHtlcMsg:
    sender: PartyName
    receiver: PartyName
    asset: Asset
    amount: float
    hash_value: str   # H(x) — хеш секрету
    timeout: float    # відносний час у секундах
    contract_id: str

@dataclass(frozen=True)
class RedeemMsg:
    contract_id: str
    secret: str

@dataclass(frozen=True)
class RefundMsg:
    contract_id: str

@dataclass(frozen=True)
class WatchMsg:
    contract_id: str  # контракт, який цей учасник має погасити
    hash_value: str   # спостерігати за будь-яким контрактом з цим хешем

@dataclass(frozen=True)
class ShutdownMsg:
    pass

PartyMsg = CreateHtlcMsg | RedeemMsg | RefundMsg | WatchMsg | ShutdownMsg
```

`frozen=True` гарантує незмінність повідомлень після створення та робить їх hashable.

== Контракт та Ledger

Контракт представлено як `TypedDict` — це звичайний словник на рівні виконання, що дозволяє зберігати його безпосередньо у `Manager().dict()` без додаткової серіалізації:

```python
class Contract(TypedDict):
    contract_id: str
    sender:      PartyName
    receiver:    PartyName
    asset:       Asset
    amount:      float
    hash_value:  str             # SHA-256 хеш секрету
    timeout:     float           # абсолютний deadline (time.time())
    status:      ContractStatus
    secret:      str | None      # заповнюється при погашенні
```

= Протокол Atomic Swap і HTLC

== Проблема довірчого обміну

Якщо A та B хочуть обмінятися активами напряму, виникає ризик: одна зі сторін може отримати актив і відмовитися від зустрічної передачі. Надійний посередник вирішує проблему, але вимагає довіри. *Atomic swap* — обмін без посередника та без довіри: або обидві передачі відбуваються, або жодна.

== HTLC — Hash Time-Locked Contract

HTLC — контракт з двома умовами розблокування коштів:

1. *Hashlock:* отримувач може забрати кошти, якщо надасть секрет `x` такий, що `H(x) = h` (де `h` — хеш, зафіксований у контракті).
2. *Timelock:* якщо `x` не надано до часу `T`, відправник може повернути кошти.

Хешування виконується через SHA-256:

```python
def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()

def verify_secret(secret: str, hash_value: str) -> bool:
    return hash_secret(secret) == hash_value
```

Погашення контракту (`redeem`) перевіряє три умови і повертає оновлений контракт або кидає `ValueError`:

```python
def redeem_contract(contract: Contract, secret: str) -> Contract:
    if contract["status"] != ContractStatus.PENDING:
        raise ValueError(f"Cannot redeem: status={contract['status']}")
    if time.time() > contract["timeout"]:
        raise ValueError("Cannot redeem: contract expired")
    if not verify_secret(secret, contract["hash_value"]):
        raise ValueError(f"Cannot redeem: wrong secret '{secret}'")
    updated = dict(contract)
    updated["status"] = ContractStatus.REDEEMED
    updated["secret"] = secret
    return cast(Contract, updated)
```

== Тристоронній обмін

Учасник A генерує секрет `x` і обчислює `H(x)`. Всі три контракти використовують *один і той самий* `H(x)` як hashlock:

#table(
  columns: (auto, 1fr, 1fr, auto, auto),
  [*Контракт*], [*Відправник*], [*Отримувач*], [*Актив*], [*Timeout*],
  [`A→B`], [A], [B], [CoinA], [T₁ = 9s],
  [`B→C`], [B], [C], [CoinB], [T₂ = 6s],
  [`C→A`], [C], [A], [CoinC], [T₃ = 3s],
)

Один і той самий хеш `H(x)` координує всі три передачі: розкриття `x` у будь-якому контракті робить його доступним для решти.

== Порядок часових блокувань і розкриття секрету

Таймаути *обов'язково* мають бути впорядковані за спаданням вздовж ланцюга: T₁ > T₂ > T₃. Це гарантує безпеку рефандів.

*Порядок погашення при успішному обміні:*

1. A погашає `C→A` (найкоротший таймаут T₃ = 3s), розкриваючи `x` у ланцюгу.
2. C бачить `x` у контракті `C→A` та погашає `B→C`.
3. B бачить `x` та погашає `A→B`.

*Чому таймаути мають зменшуватися:* якщо C поспішає погасити `B→C` (T₂ = 6s), C ще не знає `x` (A ще не погасив `C→A`). Порядок T₃ < T₂ < T₁ гарантує, що після розкриття `x` кожна сторона має достатньо часу для погашення свого контракту до його таймауту.

*Чому атомарність гарантована:* якщо `x` не розкрито до T₃, A не погашає `C→A`. Без розкриття `x` ніхто інший не може погасити свій контракт. Після T₁, T₂, T₃ кожна сторона виконує рефанд і отримує свої кошти назад.

= Реалізація

== Процес-учасник (Party)

Кожен учасник є підкласом `mp.Process`. При запуску він створює фоновий потік-спостерігач і входить у цикл обробки повідомлень:

```python
class Party(mp.Process):
    def run(self) -> None:
        # threading.Lock не можна серіалізувати для spawn —
        # примітиви синхронізації ініціалізуються у дочірньому процесі.
        self._pending_watches: list[tuple[str, str]] = []
        self._refund_watch: list[str] = []
        self._state_lock = threading.Lock()
        set_log_lock(self._log_lock)
        log_event(self._party_name, EV_PARTY_START)
        watcher = threading.Thread(target=self._watch_loop, daemon=True)
        watcher.start()
        self._loop()

    def _loop(self) -> None:
        while True:
            msg: PartyMsg = self._inbox.get()
            match msg:
                case CreateHtlcMsg(): self._handle_create(msg)
                case RedeemMsg():     self._handle_redeem(msg)
                case RefundMsg():     self._handle_refund(msg)
                case WatchMsg():      self._handle_watch(msg)
                case ShutdownMsg():
                    log_event(self._party_name, EV_PARTY_SHUTDOWN)
                    return
```

`set_log_lock()` *обов'язково* викликається всередині `run()`, а не в `__init__()`: `__init__()` виконується у батьківському процесі, тоді як глобальна змінна `_LOG_LOCK` у дочірньому процесі ініціалізується незалежно.

== Авто-погашення та авто-рефанд

Фоновий потік `_watch_loop` опитує леджер кожні 100 мс і виконує дві перевірки.

*Погашення за спостереженням:* якщо секрет з'явився у будь-якому контракті з відповідним `hash_value`, учасник погашає свій контракт. Це моделює реальну поведінку в блокчейн-протоколі: кожен вузол стежить за ланцюгом і реагує на розкриття секрету, не покладаючись на зовнішній сигнал.

*Рефанд за таймаутом:* якщо `PENDING`-контракт, створений цим учасником, прострочений (`time.time() > timeout`), учасник повертає кошти.

```python
def _watch_loop(self) -> None:
    while True:
        time.sleep(0.1)
        self._try_auto_redeem()
        self._try_auto_refund()

def _try_auto_redeem(self) -> None:
    # Збираємо дії під локом, виконуємо поза ним —
    # щоб _handle_redeem не тримав лок під час роботи.
    with self._state_lock:
        all_contracts = self._ledger.snapshot_contracts()
        to_redeem, still_pending = [], []
        for contract_id, hash_value in self._pending_watches:
            secret = next((c["secret"] for c in all_contracts
                           if c["hash_value"] == hash_value
                           and c["secret"] is not None), None)
            if secret is not None:
                to_redeem.append((contract_id, secret))
            else:
                still_pending.append((contract_id, hash_value))
        self._pending_watches = still_pending
    for contract_id, secret in to_redeem:
        self._handle_redeem(RedeemMsg(contract_id=contract_id, secret=secret))

def _try_auto_refund(self) -> None:
    with self._state_lock:
        now = time.time()
        to_refund, still_pending = [], []
        for contract_id in self._refund_watch:
            contract = self._ledger.get_contract(contract_id)
            if contract is None or contract["status"] != ContractStatus.PENDING:
                continue
            if now > contract["timeout"]:
                to_refund.append(contract_id)
            else:
                still_pending.append(contract_id)
        self._refund_watch = still_pending
    for contract_id in to_refund:
        self._handle_refund(RefundMsg(contract_id=contract_id))
```

== Логування

Кожна подія записується як один рядок JSON до stdout.

```python
def log_event(party: str, event: str, *, level: str = "INFO", **kwargs) -> None:
    record = {"ts": round(time.time(), 3), "party": party,
              "level": level, "event": event, **kwargs}
    line = json.dumps(record, default=str)
    with _LOG_LOCK:
        print(line, flush=True)
```

Схема події:

#table(
  columns: (auto, auto, 1fr),
  [*`event`*], [*`level`*], [*Значення*],
  [`party_start`], [`INFO`], [Процес учасника запущено],
  [`contract_created`], [`INFO`], [HTLC-контракт створено і кошти заблоковано],
  [`redeem_ok`], [`INFO`], [Контракт успішно погашено, секрет розкрито],
  [`redeem_fail`], [`WARN`], [Спроба погашення невдала (невірний секрет, таймаут, не знайдено)],
  [`refund_ok`], [`INFO`], [Кошти повернено відправнику після таймауту],
  [`refund_fail`], [`WARN`], [Спроба рефанду невдала (таймаут ще не минув)],
  [`party_shutdown`], [`INFO`], [Учасник завершив роботу],
  [`scenario_start`], [`INFO`], [Координатор починає сценарій],
  [`scenario_end`], [`INFO`], [Координатор завершив сценарій],
)

= Сценарії

Всі три сценарії виконуються послідовно у `main()`. Кожен використовує власний `mp.Manager()` контекст — повністю ізольований стан.

== Сценарій 1: Успішний обмін

1. Координатор генерує секрет `x` та `H(x)`.
2. A, B, C створюють контракти з однаковим `H(x)` і таймаутами T₁=9s, T₂=6s, T₃=3s.
3. B отримує `WatchMsg` для `B→C`, C — для `A→B`.
4. A погашає `C→A` з секретом `x`, розкриваючи його у леджері.
5. B і C спостерігають за леджером і погашають свої контракти.

*Очікуваний результат:* A.CoinC = 100, B.CoinA = 100, C.CoinB = 100. Всі контракти — `REDEEMED`.

== Сценарій 2: Таймаут і рефанд

1. A створює `A→B` (T₁=9s), B створює `B→C` (T₂=6s). C не створює свого контракту.
2. B отримує `WatchMsg` для `B→C`.
3. Секрет `x` ніколи не розкривається.
4. Після T₂ B повертає CoinB; після T₁ — A повертає CoinA.

*Очікуваний результат:* всі баланси без змін (100 у кожного). Обидва контракти — `REFUNDED`.

== Сценарій 3: Невірний секрет

1. Всі три контракти створюються як у сценарії 1; B та C отримують `WatchMsg`.
2. A намагається погасити `C→A` з невірним секретом → `redeem_fail` (WARN).
3. Контракт залишається у стані `PENDING`.
4. A повторює спробу з правильним секретом → `redeem_ok`.
5. B і C спостерігають за леджером і погашають свої контракти.

*Очікуваний результат:* такий самий, як у сценарії 1; у лозі є один рядок `WARN` з `event: "redeem_fail"`.

= Запуск та вихідні дані

== Інструкції з запуску

```bash
git clone https://github.com/Kentoso/distr-info-processing.git
cd distr-info-processing/lab6
uv run python main.py
```

== Фрагмент вихідних даних

Повний вивід — структуровані JSON-рядки від усіх трьох процесів та координатора. Фрагмент сценарію 1:

```
{"ts":1774719186.268,"party":"COORD","level":"INFO","event":"scenario_start",
 "scenario":"success","secret_hash":"cb975c...","timeouts":{"A->B":9,"B->C":6,"C->A":3}}
{"ts":1774719186.892,"party":"A","level":"INFO","event":"redeem_ok",
 "contract_id":"C->A:CoinC:dfbe39","secret":"lab6_secret_alpha",
 "asset":"CoinC","amount":100.0,"receiver":"A"}
{"ts":1774719186.926,"party":"B","level":"INFO","event":"redeem_ok",
 "contract_id":"B->C:CoinB:0dc152","secret":"lab6_secret_alpha",
 "asset":"CoinB","amount":100.0,"receiver":"C"}
{"ts":1774719186.926,"party":"C","level":"INFO","event":"redeem_ok",
 "contract_id":"A->B:CoinA:061225","secret":"lab6_secret_alpha",
 "asset":"CoinA","amount":100.0,"receiver":"B"}
```

Фрагмент сценарію 2 (таймаут → рефанд):

```
{"ts":1774719187.571,"party":"COORD","level":"INFO","event":"scenario_start",
 "scenario":"timeout","note":"C will not create its contract"}
{"ts":1774719187.768,"party":"A","level":"INFO","event":"contract_created",
 "contract_id":"A->B:CoinA:fc13a9","sender":"A","receiver":"B",
 "asset":"CoinA","amount":100.0,"deadline":1774719196.766}
{"ts":1774719187.779,"party":"B","level":"INFO","event":"contract_created",
 "contract_id":"B->C:CoinB:2593c2","sender":"B","receiver":"C",
 "asset":"CoinB","amount":100.0,"deadline":1774719193.778}
{"ts":1774719193.879,"party":"B","level":"INFO","event":"refund_ok",
 "contract_id":"B->C:CoinB:2593c2","asset":"CoinB","amount":100.0,"sender":"B"}
{"ts":1774719196.807,"party":"A","level":"INFO","event":"refund_ok",
 "contract_id":"A->B:CoinA:fc13a9","asset":"CoinA","amount":100.0,"sender":"A"}
```

Фрагмент сценарію 3 (невірний секрет → WARN, потім успіх):

```
{"ts":1774719198.091,"party":"A","level":"WARN","event":"redeem_fail",
 "contract_id":"C->A:CoinC:94e26a","secret":"definitely_not_the_secret",
 "reason":"Cannot redeem: wrong secret 'definitely_not_the_secret'"}
{"ts":1774719198.293,"party":"A","level":"INFO","event":"redeem_ok",
 "contract_id":"C->A:CoinC:94e26a","secret":"lab6_secret_gamma",
 "asset":"CoinC","amount":100.0,"receiver":"A"}
{"ts":1774719198.353,"party":"B","level":"INFO","event":"redeem_ok",
 "contract_id":"B->C:CoinB:5753b2","secret":"lab6_secret_gamma",
 "asset":"CoinB","amount":100.0,"receiver":"C"}
{"ts":1774719198.356,"party":"C","level":"INFO","event":"redeem_ok",
 "contract_id":"A->B:CoinA:17c95c","secret":"lab6_secret_gamma",
 "asset":"CoinA","amount":100.0,"receiver":"B"}
```

Підсумкові таблиці після кожного сценарію:

```
================================================================
  RESULT: Scenario 1 — Successful Swap
================================================================
  Balances:
    A.CoinA = 0.0       A.CoinC = 100.0
    B.CoinA = 100.0     B.CoinB = 0.0
    C.CoinB = 100.0     C.CoinC = 0.0
  Contracts:
    [REDEEMED]  A->B:CoinA:6c23a9  A->B  CoinA 100
    [REDEEMED]  B->C:CoinB:6aec1a  B->C  CoinB 100
    [REDEEMED]  C->A:CoinC:696915  C->A  CoinC 100
================================================================
  RESULT: Scenario 2 — Timeout Refund (C absent)
================================================================
  Balances:
    A.CoinA = 100.0     B.CoinB = 100.0     C.CoinC = 100.0
  Contracts:
    [REFUNDED]  A->B:CoinA:99ced5  A->B  CoinA 100
    [REFUNDED]  B->C:CoinB:80fb2b  B->C  CoinB 100
================================================================
  RESULT: Scenario 3 — Wrong Secret then Correct Redemption
================================================================
  Balances:
    A.CoinA = 0.0       A.CoinC = 100.0
    B.CoinA = 100.0     B.CoinB = 0.0
    C.CoinB = 100.0     C.CoinC = 0.0
  Contracts:
    [REDEEMED]  A->B:CoinA:e2a1a6  A->B  CoinA 100
    [REDEEMED]  B->C:CoinB:2c3afb  B->C  CoinB 100
    [REDEEMED]  C->A:CoinC:14d95d  C->A  CoinC 100
================================================================
```

= Посилання

GitHub репозиторій: #link("https://github.com/Kentoso/distr-info-processing")

Репозиторій містить повний вихідний код проєкту, включаючи реалізацію протоколу HTLC та цей звіт.
