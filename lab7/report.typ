#set page(paper: "a4")
#set figure(supplement: [Рисунок])
#show heading: set text(size: 14pt)

#align(center, text(14pt)[
  *Лабораторна робота №7*\
  Lamport One-Time Password:\
  автентифікація на основі одноразових паролів
])

= Середовище виконання

Лабораторну роботу виконано з використанням таких технологій та інструментів:

- *Мова програмування:* Python 3.12
- *Операційна система:* macOS (Tahoe 26.2)
- *Основні бібліотеки:*
  - `multiprocessing` — для запуску окремих процесів і організації міжпроцесних черг
  - `hashlib` — SHA-256 як однонаправлена хеш-функція $H$
  - `json` — для структурованого логування подій

= Загальний опис проєкту

У проєкті реалізовано симуляцію протоколу автентифікації Лемпорта (Lamport OTP). Учасники A (автентифікатор) і B (верифікатор) взаємодіють через пари черг повідомлень `mp.Queue`. Кожен із них працює як окремий процес ОС (`multiprocessing.Process`), а координатор у головному процесі ініціалізує сесію та керує виконанням сценарію.

== Структура проєкту

Код поділено на окремі модулі:

- `models.py` — моделі повідомлень (`SetupMsg`, `AuthenticateMsg`, `AuthTokenMsg`, `AuthResultMsg`, `ShutdownMsg`)
- `auth.py` — хеш-функція `h()` і побудова ланцюга `hash_chain()`
- `party_a.py` — клас `PartyA(mp.Process)`: обчислює одноразові токени та надсилає їх B
- `party_b.py` — клас `PartyB(mp.Process)`: перевіряє кожен токен і відповідає A
- `logger.py` — функції `log_event()` (JSON у stdout) та `print_result()` (підсумок сценарію)
- `main.py` — точка входу та три сценарії виконання

== Моделі повідомлень

Чергу кожного учасника типізовано як `mp.Queue[PartyMsg]`:

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

Класичні схеми автентифікації за паролем вразливі до атак перехоплення: якщо зловмисник отримає пароль, він зможе використати його повторно. Протокол Лемпорта усуває цю проблему за допомогою *ланцюга хешів*: кожен переданий токен є дійсним лише один раз і не дає змоги відновити жоден наступний токен.

== Фаза 1: Ініціалізація

Перед початком автентифікації відбуваються такі дії:

1. A обирає секретний пароль $w$ і кількість раундів $t$.
2. A обчислює якір: $w_0 = H^t(w)$ — тобто застосовує $H$ рівно $t$ разів поспіль.
3. A *надійно* передає $w_0$ та $t$ стороні B, наприклад через захищений канал або за участю довіреної третьої сторони.
4. B зберігає $w_("prev") <- w_0$ та встановлює лічильник $i_("expected") <- 1$.

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

У кожному раунді $i$ виконується такий обмін:

1. *A* обчислює $w_i = H^{t-i}(w)$ і надсилає B пакет $(A, i, w_i)$.
2. *B* перевіряє дві умови:
  - $i = i_("expected")$ — номер раунду правильний,
  - $H(w_i) = w_("prev")$ — ланцюг не порушено.
3. Якщо обидві умови виконуються, B приймає токен, оновлює $w_("prev") <- w_i$ та збільшує $i_("expected")$.
4. Якщо хоча б одна умова не виконується, B відхиляє токен і *не змінює* свій внутрішній стан.

Важливо: A ніколи не надсилає раунд $t$, оскільки це означало б передачу сирого пароля $w = H^0(w)$. У `PartyA` цей випадок явно заборонено.

== Чому атаки не спрацьовують

*Повторне використання токена (replay):* якщо зловмисник перехопив $w_i$ і повторно надсилає його в раунді $i+1$, B перевіряє умову $H(w_i) = w_("prev")$. Але після успішного раунду $i$ значення $w_("prev")$ уже дорівнює $w_i$, тому перевірка зводиться до $H(w_i) =?= w_i$, що є хибним за відсутності колізій у $H$.

*Підробка (impersonation):* зловмисник, не знаючи $w$, не може обчислити коректне $w_i = H^{t-i}(w)$, оскільки функція $H$ є однонаправленою, і практично неможливо виконати зворотне обчислення.

= Реалізація

== PartyA — автентифікатор

`PartyA` зберігає лічильник `round_counter` і обчислює токени за запитом координатора. Захист від вичерпання ланцюга реалізовано через явну перевірку:

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

`PartyB` очікує `SetupMsg` як перше повідомлення, після чого зберігає $w_("prev")$ та $i_("expected")$. Стан змінюється *лише після успішної верифікації*:

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

Кожна подія записується у вигляді окремого JSON-рядка.

#table(
  columns: (auto, auto, 1fr),
  [*`event`*], [*`level`*], [*Значення*],
  [`party_start`], [`INFO`], [Процес учасника запущено],
  [`setup_done`], [`INFO`], [B отримав $w_0$ і готовий до автентифікації],
  [`auth_send`], [`INFO`], [A надсилає токен $w_i$ для раунду $i$],
  [`auth_verify`], [`INFO`/`WARN`], [B перевірив токен: ACCEPTED або REJECTED],
  [`auth_result_received`], [`INFO`/`WARN`], [A отримав відповідь від B],
  [`attack_inject`], [`INFO`], [Координатор вводить атакувальний токен],
  [`auth_exhausted`], [`WARN`], [A відмовився надсилати токен: ланцюг вичерпано],
  [`party_shutdown`], [`INFO`], [Учасник завершив роботу],
)

= Сценарії

Усі три сценарії виконуються послідовно в `main()`. Для кожного створюється нова пара процесів A і B з незалежними чергами, тому стан між сценаріями повністю ізольований.

== Сценарій 1: Успішна автентифікація (5 раундів)

*Хід сценарію:*

1. Координатор обчислює $w_0 = H^{10}("lamport_secret")$ і надсилає `SetupMsg` до B.
2. Координатор 5 разів надсилає `AuthenticateMsg` до A.
3. A обчислює $w_i = H^{10-i}(w)$ і передає `AuthTokenMsg` до B.
4. B перевіряє умови $H(w_i) = w_{i-1}$ та правильність номера раунду — обидві виконуються.
5. B відповідає повідомленням `AuthResultMsg(accepted=True)` до A.

*Очікуваний результат:* 5 послідовних успішних раундів; після кожного з них B оновлює свій стан.

== Сценарій 2: Атака повторного використання (replay)

*Хід сценарію:*

1. У раунді 1 A успішно проходить автентифікацію — значення $w_1$ стає відомим спостерігачеві.
2. Eve перехоплює $w_1$ і надсилає його до B з номером раунду 2.
3. B перевіряє: $H(w_1) = w_0 != w_1$ → *REJECTED*. Стан B при цьому не змінюється.
4. У раунді 2 A надсилає справжній $w_2$, і B перевіряє $H(w_2) = w_1$ → *ACCEPTED*.

*Чому відхилення є правильним:* після успішного першого раунду $w_("prev") = w_1$. Eve надсилає токен $w_i = w_1$, тому перевірка набуває вигляду $H(w_1) =?= w_1$. Оскільки $H(w_1) = w_0 != w_1$, умова не виконується.

== Сценарій 3: Підробка (impersonation)

*Хід сценарію:*

1. Mallory, не знаючи $w$, підставляє довільний 64-символьний рядок `"deadbeef" * 8` і надсилає його до B як $w_1$.
2. B перевіряє: $H("fake") != w_0$ → *REJECTED*. Стан B залишається $i_("expected") = 1$.
3. A надсилає справжній $w_1$, після чого B перевіряє $H(w_1) = w_0$ → *ACCEPTED*.

*Ключовий момент:* невдала атакувальна спроба не змінює лічильник B, тому легітимний автентифікатор A може успішно пройти той самий раунд.

= Запуск та вихідні дані

== Інструкції з запуску

```bash
git clone https://github.com/Kentoso/distr-info-processing.git
cd distr-info-processing/lab7
uv run python main.py
```

== Фрагмент вихідних даних

Повний вивід складається зі структурованих JSON-рядків від усіх процесів та координатора. Нижче наведено фрагмент сценарію 1 (успішна автентифікація):

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

Фрагмент сценарію 2 (replay — WARN, далі успіх):

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

Фрагмент сценарію 3 (impersonation — WARN, далі успіх):

```
{"ts":1774720873.12,"party":"COORD","level":"INFO","event":"scenario_start",
 "scenario":"impersonation",
 "note":"Mallory forges a token without knowing the password"}
{"ts":1774720873.227,"party":"COORD","level":"INFO","event":"attack_inject",
 "attacker":"MALLORY","round_i":1,"w_i_prefix":"deadbeefdeadbeef…",
 "note":"fabricated hash; H(fake) != w_0 so check will fail"}
{"ts":1774720873.228,"party":"B","level":"WARN","event":"auth_verify",
 "sender":"MALLORY","round_i":1,"status":"REJECTED",
 "reason":"hash check failed: H(w_i) != w_{i-1}"}
{"ts":1774720873.532,"party":"A","level":"INFO","event":"auth_send",
 "round_i":1,"w_i_prefix":"5eb020401963ac51…"}
{"ts":1774720873.533,"party":"B","level":"INFO","event":"auth_verify",
 "sender":"A","round_i":1,"status":"ACCEPTED","reason":"ok"}
{"ts":1774720873.533,"party":"A","level":"INFO","event":"auth_result_received",
 "round_i":1,"status":"ACCEPTED","reason":"ok"}
```

Після завершення кожного сценарію виводяться підсумкові таблиці:

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

= Посилання

GitHub репозиторій: #link("https://github.com/Kentoso/distr-info-processing/tree/main/lab7")

Репозиторій містить повний вихідний код проєкту, включаючи реалізацію протоколу Лемпорта та цей звіт.
