#set page(paper: "a4")
#set figure(supplement: [Рисунок])
#show heading: set text(size: 14pt)

#align(center, text(14pt)[
  *Лабораторна робота №7*\
  Lamport One-Time Password:\
  автентифікація на основі одноразових паролів
])

= Середовище виконання

Лабораторна робота виконана з використанням наступних технологій та інструментів:

- *Мова програмування:* Python 3.12
- *Операційна система:* macOS (Tahoe 26.2)
- *Основні бібліотеки:*
  - `multiprocessing` — для створення окремих процесів та міжпроцесних черг
  - `hashlib` — SHA-256 як однонаправлена хеш-функція $H$
  - `json` — структуроване логування подій

= Загальний опис проєкту

Проєкт реалізує симуляцію протоколу автентифікації Лемпорта (Lamport OTP). Два учасники — A (автентифікатор) та B (верифікатор) — комунікують через пари черг повідомлень `mp.Queue`. Кожен з них виконується як окремий процес ОС (`multiprocessing.Process`). Координатор (головний процес) ініціалізує сесію та керує ходом сценарію.

== Структура проєкту

Код розподілено по окремих модулях:

- `models.py` — моделі повідомлень (`SetupMsg`, `AuthenticateMsg`, `AuthTokenMsg`, `AuthResultMsg`, `ShutdownMsg`)
- `auth.py` — хеш-функція `h()` та побудова ланцюга `hash_chain()`
- `party_a.py` — клас `PartyA(mp.Process)`: обчислює одноразові токени та надсилає їх B
- `party_b.py` — клас `PartyB(mp.Process)`: верифікує кожен токен і відповідає A
- `logger.py` — функції `log_event()` (JSON до stdout) та `print_result()` (підсумок сценарію)
- `main.py` — точка входу; три сценарії виконання

== Моделі повідомлень

Черга кожного учасника типізована як `mp.Queue[PartyMsg]`:

```python
@dataclass(frozen=True)
class SetupMsg:
    w0: str   # H^t(password) — початковий якір
    t:  int   # загальна кількість раундів

@dataclass(frozen=True)
class AuthenticateMsg:
    pass      # координатор просить A виконати наступний раунд

@dataclass(frozen=True)
class AuthTokenMsg:
    sender:  str   # ім'я відправника (або зловмисника)
    round_i: int   # номер поточного раунду
    w_i:     str   # H^(t-i)(password)

@dataclass(frozen=True)
class AuthResultMsg:
    round_i:  int
    accepted: bool
    reason:   str

PartyMsg = SetupMsg | AuthenticateMsg | AuthTokenMsg | AuthResultMsg | ShutdownMsg
```

= Протокол Лемпорта

== Ідея та мотивація

Класичні схеми автентифікації паролем вразливі до атак підслуховування: якщо зловмисник перехопить пароль, він зможе використати його повторно. Протокол Лемпорта вирішує цю проблему за допомогою *ланцюга хешів*: кожен переданий токен є дійсним рівно один раз і не дозволяє відновити жодний майбутній токен.

== Фаза 1: Ініціалізація

Перед початком автентифікації:

1. A обирає секретний пароль $w$ та кількість раундів $t$.
2. A обчислює якір: $w_0 = H^t(w)$ — застосування $H$ рівно $t$ разів поспіль.
3. A *надійно* передає $w_0$ та $t$ стороні B (наприклад, через захищений канал або довірену третю сторону).
4. B зберігає $w_\text{prev} \leftarrow w_0$ та встановлює лічильник $i_\text{expected} \leftarrow 1$.

```python
def hash_chain(value: str, n: int) -> str:
    for _ in range(n):
        value = h(value)
    return value

# Ініціалізація: w_0 = H^t(password)
w0 = hash_chain(password, t)
b_inbox.put(SetupMsg(w0=w0, t=t))
```

== Фаза 2: Автентифікація (раунди 1 … t−1)

У кожному раунді $i$:

1. *A* обчислює $w_i = H^{t-i}(w)$ і надсилає B пакет $(A,\, i,\, w_i)$.
2. *B* перевіряє дві умови:
   - $i = i_\text{expected}$ — правильний номер раунду,
   - $H(w_i) = w_\text{prev}$ — цілісність ланцюга.
3. Якщо обидві умови виконані: B приймає, оновлює $w_\text{prev} \leftarrow w_i$ та збільшує $i_\text{expected}$.
4. Якщо хоча б одна умова порушена: B відхиляє токен і *не змінює* свій стан.

Зауваження: A ніколи не надсилає раунд $t$ (це означало б відправку сирого пароля $w = H^0(w)$). `PartyA` явно захищає від цього.

== Чому атаки не спрацьовують

*Повторне використання токена (replay):* якщо зловмисник перехопив $w_i$ і повторно відправляє його у раунді $i+1$, B перевіряє $H(w_i) = w_\text{prev}$. Але $w_\text{prev}$ після успішного раунду $i$ вже дорівнює $w_i$, тому умова стає $H(w_i) \stackrel{?}{=} w_i$ — хибна (за умови відсутності колізій у $H$).

*Підробка (impersonation):* зловмисник без знання $w$ не може обчислити $w_i = H^{t-i}(w)$, оскільки $H$ є однонаправленою: зворотне обчислення практично неможливе.

= Реалізація

== PartyA — автентифікатор

`PartyA` зберігає лічильник `round_counter` та обчислює токени за запитом координатора. Захист від вичерпання ланцюга реалізовано явною перевіркою:

```python
class PartyA(mp.Process):
    def run(self) -> None:
        set_log_lock(self._log_lock)
        round_counter = 1
        while True:
            msg = self._inbox.get()
            match msg:
                case ShutdownMsg():
                    return
                case AuthenticateMsg():
                    if round_counter >= self._t:  # захист: не надсилати w = H^0(w)
                        log_event("A", EV_EXHAUSTED, level="WARN")
                        continue
                    i   = round_counter
                    w_i = hash_chain(self._password, self._t - i)
                    self._b_inbox.put(AuthTokenMsg(sender="A", round_i=i, w_i=w_i))
                    round_counter += 1
                case AuthResultMsg():
                    status = "ACCEPTED" if msg.accepted else "REJECTED"
                    log_event("A", EV_AUTH_RESULT, round_i=msg.round_i, status=status)
```

== PartyB — верифікатор

`PartyB` очікує `SetupMsg` як перше повідомлення, після чого зберігає $w_\text{prev}$ та $i_\text{expected}$. Стан оновлюється *лише при успішній верифікації*:

```python
class PartyB(mp.Process):
    def run(self) -> None:
        set_log_lock(self._log_lock)
        setup = self._inbox.get()          # перше повідомлення — ініціалізація
        w_prev, i_expected = setup.w0, 1

        while True:
            msg = self._inbox.get()
            match msg:
                case ShutdownMsg():
                    return
                case AuthTokenMsg():
                    round_ok = msg.round_i == i_expected
                    hash_ok  = h(msg.w_i) == w_prev

                    accepted = round_ok and hash_ok
                    if accepted:
                        w_prev     = msg.w_i   # оновлення лише при успіху
                        i_expected += 1
                    self._a_inbox.put(
                        AuthResultMsg(round_i=msg.round_i, accepted=accepted, ...)
                    )
```

== Логування

Аналогічно до Lab 6, кожна подія записується як JSON-рядок. Спільний `mp.Lock` запобігає перемішуванню виводу між процесами.

#table(
  columns: (auto, auto, 1fr),
  [*`event`*], [*`level`*], [*Значення*],
  [`party_start`],          [`INFO`], [Процес учасника запущено],
  [`setup_done`],           [`INFO`], [B отримав $w_0$ і готовий до автентифікації],
  [`auth_send`],            [`INFO`], [A надсилає токен $w_i$ для раунду $i$],
  [`auth_verify`],          [`INFO`/`WARN`], [B перевірив токен: ACCEPTED або REJECTED],
  [`auth_result_received`], [`INFO`/`WARN`], [A отримав відповідь від B],
  [`attack_inject`],        [`INFO`], [Координатор вводить атакуючий токен],
  [`auth_exhausted`],       [`WARN`], [A відмовився надсилати: ланцюг вичерпано],
  [`party_shutdown`],       [`INFO`], [Учасник завершив роботу],
)

= Сценарії

Всі три сценарії виконуються послідовно у `main()`. Кожен використовує свіжу пару процесів A і B з незалежними чергами — повністю ізольований стан.

== Сценарій 1: Успішна автентифікація (5 раундів)

*Потік:*

1. Координатор обчислює $w_0 = H^{10}(\texttt{"lamport\_secret"})$ і надсилає `SetupMsg` до B.
2. Координатор 5 разів надсилає `AuthenticateMsg` до A.
3. A обчислює $w_i = H^{10-i}(w)$ і передає `AuthTokenMsg` до B.
4. B перевіряє $H(w_i) = w_{i-1}$ та номер раунду — обидві умови виконуються.
5. B відповідає `AuthResultMsg(accepted=True)` до A.

*Очікуваний результат:* 5 послідовних прийнятих раундів; B оновлює свій стан після кожного.

== Сценарій 2: Атака повторного використання (replay)

*Потік:*

1. Раунд 1: A автентифікується успішно — $w_1$ стає відомим спостерігачеві.
2. Eve перехоплює $w_1$ і надсилає його до B з номером раунду 2.
3. B перевіряє: $H(w_1) = w_0 \neq w_1$ → *REJECTED*. Стан B не змінюється.
4. Раунд 2: A надсилає справжній $w_2$; B перевіряє $H(w_2) = w_1$ → *ACCEPTED*.

*Чому відхилення коректне:* після успішного раунду 1 $w_\text{prev} = w_1$. Eve надсилає $w_i = w_1$, тому перевірка стає $H(w_1) \stackrel{?}{=} w_1$. Оскільки $H(w_1) = w_0 \neq w_1$, умова хибна.

== Сценарій 3: Підробка (impersonation)

*Потік:*

1. Mallory без знання $w$ підбирає довільний 64-символьний рядок `"deadbeef" * 8` і надсилає його до B як $w_1$.
2. B перевіряє: $H(\texttt{fake}) \neq w_0$ → *REJECTED*. Стан B залишається $i_\text{expected} = 1$.
3. A надсилає справжній $w_1$ → B: $H(w_1) = w_0$ → *ACCEPTED*.

*Ключовий момент:* невдала спроба не просуває лічильник B, тому легітимний автентифікатор A може успішно пройти той самий раунд.

= Запуск та вихідні дані

== Інструкції з запуску

```bash
git clone https://github.com/Kentoso/distr-info-processing.git
cd distr-info-processing/lab7
uv run python main.py
```

== Фрагмент вихідних даних

Повний вивід — структуровані JSON-рядки від усіх процесів та координатора. Фрагмент сценарію 1 (успішна автентифікація):

```
{"ts":1774698812.299,"party":"COORD","level":"INFO","event":"scenario_start",
 "scenario":"success"}
{"ts":1774698812.464,"party":"B","level":"INFO","event":"setup_done",
 "w0_prefix":"febf8f805b211b9f…","t":10}
{"ts":1774698812.464,"party":"A","level":"INFO","event":"auth_send",
 "round_i":1,"w_i_prefix":"5eb020401963ac51…"}
{"ts":1774698812.464,"party":"B","level":"INFO","event":"auth_verify",
 "sender":"A","round_i":1,"status":"ACCEPTED","reason":"ok"}
{"ts":1774698812.465,"party":"A","level":"INFO","event":"auth_result_received",
 "round_i":1,"status":"ACCEPTED","reason":"ok"}
```

Фрагмент сценарію 2 (replay — WARN, потім успіх):

```
{"ts":1774698814.072,"party":"COORD","level":"INFO","event":"attack_inject",
 "attacker":"EVE","round_i":2,"w_i_prefix":"5eb020401963ac51…",
 "note":"replaying captured w_1; H(w_1)=w_0 != w_1 so check will fail"}
{"ts":1774698814.073,"party":"B","level":"WARN","event":"auth_verify",
 "sender":"EVE","round_i":2,"status":"REJECTED",
 "reason":"hash check failed: H(w_i) != w_{i-1}"}
{"ts":1774698814.378,"party":"A","level":"INFO","event":"auth_send",
 "round_i":2,"w_i_prefix":"bc30aecf71b9f5d3…"}
{"ts":1774698814.378,"party":"B","level":"INFO","event":"auth_verify",
 "sender":"A","round_i":2,"status":"ACCEPTED","reason":"ok"}
```

Підсумкові таблиці після кожного сценарію:

```
================================================================
  RESULT: Scenario 1 — Successful 5-Round Authentication
================================================================
    [ACCEPTED]  round=1  sender=A  ok
    [ACCEPTED]  round=2  sender=A  ok
    [ACCEPTED]  round=3  sender=A  ok
    [ACCEPTED]  round=4  sender=A  ok
    [ACCEPTED]  round=5  sender=A  ok
================================================================
  RESULT: Scenario 2 — Replay Attack
================================================================
    [ACCEPTED]  round=1  sender=A     ok
    [REJECTED]  round=2  sender=EVE   hash check failed: H(w_i) != w_{i-1}
    [ACCEPTED]  round=2  sender=A     ok
================================================================
  RESULT: Scenario 3 — Impersonation Attempt
================================================================
    [REJECTED]  round=1  sender=MALLORY  hash check failed: H(w_i) != w_{i-1}
    [ACCEPTED]  round=1  sender=A        ok
================================================================
```

= Порівняння сценаріїв

#table(
  columns: (1fr, 1fr, 1fr, 1fr),
  [*Характеристика*], [*Сценарій 1*], [*Сценарій 2*], [*Сценарій 3*],
  [Тип атаки], [—], [Replay (Eve)], [Impersonation (Mallory)],
  [Кількість раундів A], [5], [2], [1],
  [Атакуючих спроб], [0], [1], [1],
  [Стан B після атаки], [—], [Не змінився], [Не змінився],
  [Всі токени A прийнято], [Так], [Так], [Так],
  [Атаку відхилено], [—], [Так], [Так],
  [Подія WARN у лозі], [Ні], [Так (`auth_verify`)], [Так (`auth_verify`)],
)

= Посилання

GitHub репозиторій: #link("https://github.com/Kentoso/distr-info-processing")

Репозиторій містить повний вихідний код проєкту, включаючи реалізацію протоколу Лемпорта та цей звіт.
