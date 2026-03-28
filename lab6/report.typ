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

- `models.py` — перерахування `ContractStatus`, `Asset`, `PartyName`; моделі повідомлень (`CreateHtlcMsg`, `RedeemMsg`, `RefundMsg`, `ShutdownMsg`); `TypedDict` `Contract`
- `htlc.py` — хешування секрету, верифікація, функції `create_contract()`, `redeem_contract()`, `refund_contract()`
- `ledger.py` — клас `Ledger`: операції з балансами та контрактами через Manager-проксі
- `party.py` — клас `Party(mp.Process)`: цикл обробки повідомлень
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

Вхідна черга кожного учасника типізована як `mp.Queue[PartyMsg]`, де `PartyMsg` — об'єднання чотирьох заморожених датакласів:

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
class ShutdownMsg:
    pass

PartyMsg = CreateHtlcMsg | RedeemMsg | RefundMsg | ShutdownMsg
```

`frozen=True` гарантує незмінність повідомлень після створення та дозволяє їх pickle-серіалізацію для передачі між процесами через чергу.

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

`Ledger` є єдиним місцем мутації Manager-проксі. Це важливо: `Manager().dict()` перехоплює лише присвоєння верхнього рівня (`proxy[key] = value`), але *не* мутацію вкладених об'єктів (`proxy[key]["nested"] = x` не поширюється). Тому всі методи `Ledger` використовують патерн знімок–мутація–перепризначення:

```python
def debit(self, party: PartyName, asset: Asset, amount: float) -> None:
    snapshot = dict(self._balances.get(party, {}))   # копія
    snapshot[asset] = snapshot.get(asset, 0.0) - amount
    self._balances[party] = snapshot                  # перепризначення верхнього рівня
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

Кожен учасник є підкласом `mp.Process`. Метод `run()` запускається у дочірньому процесі і входить у цикл обробки повідомлень:

```python
class Party(mp.Process):
    def run(self) -> None:
        set_log_lock(self._log_lock)  # ініціалізація у дочірньому процесі
        log_event(self._party_name, EV_PARTY_START)
        self._loop()

    def _loop(self) -> None:
        while True:
            msg: PartyMsg = self._inbox.get()
            log_event(self._party_name, EV_MSG_RECEIVED,
                      msg_type=type(msg).__name__,
                      contract_id=getattr(msg, "contract_id", None))
            match msg:
                case CreateHtlcMsg(): self._handle_create(msg)
                case RedeemMsg():     self._handle_redeem(msg)
                case RefundMsg():     self._handle_refund(msg)
                case ShutdownMsg():
                    log_event(self._party_name, EV_PARTY_SHUTDOWN)
                    return
```

`set_log_lock()` *обов'язково* викликається всередині `run()`, а не в `__init__()`: `__init__()` виконується у батьківському процесі, тоді як глобальна змінна `_LOG_LOCK` у дочірньому процесі ініціалізується незалежно.

Диспетчеризація виконується через `match/case` на типі повідомлення (Python 3.10+), що усуває магічні рядки та вимагає явного опрацювання кожного типу.

== Логування

Кожна подія записується як один рядок JSON до stdout. Спільний `mp.Lock` запобігає перемішуванню рядків від різних процесів:

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

*Потік:*

1. Координатор генерує секрет `x` та `H(x)`.
2. A, B, C створюють контракти з однаковим `H(x)` і таймаутами T₁=9s, T₂=6s, T₃=3s.
3. A погашає `C→A` з секретом `x` → `redeem_ok`.
4. B погашає `B→C` з тим самим `x` → `redeem_ok`.
5. C погашає `A→B` з `x` → `redeem_ok`.

*Очікуваний результат:* A.CoinC = 100, B.CoinA = 100, C.CoinB = 100. Всі контракти — `REDEEMED`.

== Сценарій 2: Таймаут і рефанд

*Потік:*

1. A створює `A→B` (T₁=9s), B створює `B→C` (T₂=6s). C не створює свого контракту.
2. Секрет `x` ніколи не розкривається — нікому немає що погашати.
3. Після 6.5s координатор надсилає B команду рефанду → B повертає CoinB.
4. Після ще 3s координатор надсилає A команду рефанду → A повертає CoinA.

*Очікуваний результат:* всі баланси без змін (100 у кожного). Обидва контракти — `REFUNDED`.

== Сценарій 3: Невірний секрет

*Потік:*

1. Всі три контракти створюються як у сценарії 1.
2. A намагається погасити `C→A` з невірним секретом → `redeem_fail` (WARN).
3. Контракт залишається у стані `PENDING`.
4. A повторює спробу з правильним секретом → `redeem_ok`.
5. B та C погашають свої контракти → `redeem_ok`.

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
{"ts":1774696553.574,"party":"COORD","level":"INFO","event":"scenario_start",
 "scenario":"success","secret_hash":"cb975c...","timeouts":{"A->B":9,"B->C":6,"C->A":3}}
{"ts":1774696553.825,"party":"A","level":"INFO","event":"contract_created",
 "contract_id":"A->B:CoinA:0e89ef","sender":"A","receiver":"B",
 "asset":"CoinA","amount":100.0,"deadline":1774696562.825}
{"ts":1774696554.21, "party":"A","level":"INFO","event":"redeem_ok",
 "contract_id":"C->A:CoinC:6b2a27","secret":"lab6_secret_alpha",
 "asset":"CoinC","amount":100.0,"receiver":"A"}
{"ts":1774696554.413,"party":"B","level":"INFO","event":"redeem_ok",
 "contract_id":"B->C:CoinB:e18aee","secret":"lab6_secret_alpha",
 "asset":"CoinB","amount":100.0,"receiver":"C"}
{"ts":1774696554.617,"party":"C","level":"INFO","event":"redeem_ok",
 "contract_id":"A->B:CoinA:0e89ef","secret":"lab6_secret_alpha",
 "asset":"CoinA","amount":100.0,"receiver":"B"}
```

Фрагмент сценарію 3 (невірний секрет → WARN, потім успіх):

```
{"ts":1774696566.066,"party":"A","level":"WARN","event":"redeem_fail",
 "contract_id":"C->A:CoinC:64a527","secret":"definitely_not_the_secret",
 "reason":"Cannot redeem: wrong secret 'definitely_not_the_secret'"}
{"ts":1774696566.267,"party":"A","level":"INFO","event":"redeem_ok",
 "contract_id":"C->A:CoinC:64a527","secret":"lab6_secret_gamma",
 "asset":"CoinC","amount":100.0,"receiver":"A"}
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
    [REDEEMED]  A->B:CoinA:...  A->B  CoinA 100
    [REDEEMED]  B->C:CoinB:...  B->C  CoinB 100
    [REDEEMED]  C->A:CoinC:...  C->A  CoinC 100
================================================================
  RESULT: Scenario 2 — Timeout Refund (C absent)
================================================================
  Balances:
    A.CoinA = 100.0     B.CoinB = 100.0     C.CoinC = 100.0
  Contracts:
    [REFUNDED]  A->B:CoinA:...  A->B  CoinA 100
    [REFUNDED]  B->C:CoinB:...  B->C  CoinB 100
================================================================
```

= Порівняння сценаріїв

#table(
  columns: (1fr, 1fr, 1fr, 1fr),
  [*Характеристика*], [*Сценарій 1*], [*Сценарій 2*], [*Сценарій 3*],
  [Усі 3 контракти створено], [Так], [Ні (C відсутній)], [Так],
  [Секрет розкрито], [Так], [Ні], [Так (після WARN)],
  [Підсумковий стан контрактів], [REDEEMED ×3], [REFUNDED ×2], [REDEEMED ×3],
  [Баланси змінились], [Так (ротація)], [Ні (рефанд)], [Так (ротація)],
  [Атомарність дотримана], [Так], [Так], [Так],
  [Подія WARN у лозі], [Ні], [Ні], [Так (`redeem_fail`)],
)

= Посилання

GitHub репозиторій: #link("https://github.com/Kentoso/distr-info-processing")

Репозиторій містить повний вихідний код проєкту, включаючи реалізацію протоколу HTLC та цей звіт.
