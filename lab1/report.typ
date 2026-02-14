#set page(paper: "a4")
#set text(font: "STIX Two Text", size: 14pt)
#show heading: set text(size: 14pt)

#align(center, text(14pt)[
  *Лабораторна робота №1*\
  Реалізація алгоритму Hirschberg-Sinclair (HS)\
  для виборів лідера в розподіленій системі
])

= Середовище виконання

Лабораторна робота виконана з використанням наступних технологій та інструментів:

- *Мова програмування:* Python 3.12
- *Операційна система:* macOS (Tahoe 26.2)
- *Основні бібліотеки:*
  - `multiprocessing` - для створення процесів та міжпроцесної комунікації
  - `dataclasses` - для визначення структур даних
  - `enum` - для визначення типів повідомлень та статусів
  - `typing` - для статичної типізації

Проєкт не вимагає додаткових зовнішніх залежностей і використовує лише стандартну бібліотеку Python.

= Загальний опис проєкту

Проєкт реалізує алгоритм Hirschberg-Sinclair для виборів лідера в розподіленій системі з кільцевою топологією. Алгоритм дозволяє процесам в кільці обрати лідера (процес з найбільшим UID) за допомогою обміну повідомленнями.

== Структура проєкту

Проєкт складається з трьох основних файлів:

=== `models.py`
Визначає базові моделі даних та типи:

- *`UID`* - тип для унікального ідентифікатора процесу (NewType на базі int)
- *`Flag`* - перелічення для напрямку повідомлень:
  - `IN` - повідомлення повертається назад
  - `OUT` - повідомлення йде вперед
- *`Status`* - статус процесу:
  - `UNKNOWN` - процес ще не визначив лідера
  - `LEADER` - процес є лідером
- *`Message`* - основне повідомлення алгоритму HS:
  - `uid` - ідентифікатор процесу-ініціатора
  - `flag` - напрямок (IN/OUT)
  - `hop_count` - кількість кроків до проходження
- *`LeaderMessage`* - повідомлення про обраного лідера:
  - `leader_uid` - UID процесу-лідера
- *`RingMessage`* - об'єднаний тип для всіх повідомлень

=== `main.py`
Відповідає за ініціалізацію та запуск системи:

- *`create_ring_processes()`* - створює кільцеву топологію з n процесів:
  - Створює двосторонні з'єднання (`Pipe`) між сусідніми процесами
  - Ініціалізує процеси з відповідними з'єднаннями
  - Повертає список запущених процесів
- *`_process()`* - функція, що виконується кожним процесом:
  - Отримує UID з PID процесу
  - Створює екземпляр `ProcessNode`
  - Запускає основний цикл алгоритму

=== `process_node.py`
Містить основну логіку алгоритму в класі `ProcessNode`:

- *Поля класу:*
  - `uid` - унікальний ідентифікатор процесу
  - `status` - поточний статус (UNKNOWN/LEADER)
  - `phase` - поточна фаза алгоритму
  - `ccw`, `cw` - з'єднання з сусідами (counter-clockwise/clockwise)
  - `got_in_from_cw`, `got_in_from_ccw` - прапорці для відстеження IN повідомлень
  - `leader_uid` - UID обраного лідера
  - Статистика: `cw_sent`, `ccw_sent`, `rounds`

- *Методи:*
  - `run()` - основний цикл виконання
  - `_broadcast_out()` - розсилає OUT повідомлення в обидва напрямки
  - `_handle_message()` - обробляє отримане повідомлення
  - `_out_message()` - обробляє OUT повідомлення
  - `_handle_leader()` - обробляє повідомлення про лідера
  - `_send_leader()` - відправляє повідомлення про лідера

= Детальний опис обробки повідомлень

== Обробка OUT повідомлень

Коли процес отримує OUT повідомлення (`_out_message()` в `process_node.py:61-82`), він виконує наступну логіку:

```python
def _out_message(self, msg: Message, forward_to: Connection, return_to: Connection):
    if msg.uid > self.uid:
        if msg.hop_count > 1:
            # Пересилаємо повідомлення далі
            forwarded_message = Message(msg.uid, msg.flag, msg.hop_count - 1)
            forward_to.send(forwarded_message)
        elif msg.hop_count == 1:
            # Досягнуто максимальної відстані, повертаємо IN
            return_message = Message(msg.uid, Flag.IN, 1)
            return_to.send(return_message)
    elif msg.uid == self.uid:
        # Повідомлення повернулось до ініціатора - він лідер!
        self.status = Status.LEADER
        self.leader_uid = self.uid
        self._send_leader()
```

*Логіка:*
1. Якщо `msg.uid > self.uid` - повідомлення від процесу з більшим UID:
  - Якщо `hop_count > 1` - пересилаємо далі, зменшивши лічильник
  - Якщо `hop_count == 1` - досягнуто максимальної відстані, повертаємо IN повідомлення назад
2. Якщо `msg.uid == self.uid` - власне повідомлення повернулось:
  - Процес оголошує себе лідером
  - Розсилає LeaderMessage всім
3. Якщо `msg.uid < self.uid` - повідомлення від процесу з меншим UID:
  - Повідомлення відкидається (не пересилається)

== Обробка IN повідомлень

Обробка IN повідомлень (`_handle_message()` в `process_node.py:95-120`):

```python
if msg.flag == Flag.IN:
    # Відстежуємо отримання своїх IN повідомлень
    self.got_in_from_ccw = self.got_in_from_ccw or (
        msg.uid == self.uid and from_ccw
    )
    self.got_in_from_cw = self.got_in_from_cw or (
        msg.uid == self.uid and from_cw
    )

    # Якщо отримали IN з обох напрямків - переходимо до наступної фази
    if self.got_in_from_ccw and self.got_in_from_cw:
        self.phase += 1
        self.got_in_from_ccw = False
        self.got_in_from_cw = False
        self._broadcast_out()
        return

    # Якщо це наше IN повідомлення - не пересилаємо
    if msg.uid == self.uid:
        return

    # Пересилаємо чуже IN повідомлення далі
    forward_to = self.cw if from_ccw else self.ccw
    forward_to.send(Message(msg.uid, Flag.IN, 1))
```

*Логіка:*
1. Відстежуємо отримання власних IN повідомлень з обох напрямків
2. Коли отримано IN з обох сторін:
  - Збільшуємо номер фази (`phase += 1`)
  - Скидаємо прапорці
  - Розсилаємо нові OUT повідомлення з подвоєною відстанню (2^phase)
3. Чужі IN повідомлення пересилаємо в тому ж напрямку

== Обробка LeaderMessage

Коли процес отримує повідомлення про лідера (`_handle_leader()` в `process_node.py:38-46`):

```python
def _handle_leader(self, msg: LeaderMessage):
    if self.uid == msg.leader_uid:
        # Це ми лідер, повідомлення пройшло коло
        self._log("everyone knows that I'm the leader now!")
        return

    # Запам'ятовуємо лідера та пересилаємо далі
    self.leader_uid = msg.leader_uid
    self._send_leader()
    self._log(f"did you know that {self.leader_uid} is the leader?")
```

*Логіка:*
1. Якщо процес сам є лідером - повідомлення пройшло коло, завершуємо
2. Інакше - запам'ятовуємо лідера та пересилаємо повідомлення далі по кільцю
3. Після отримання LeaderMessage процес припиняє виконання алгоритму

= Опис алгоритму Hirschberg-Sinclair

== Загальна ідея

Алгоритм HS працює у фазах, де кожна фаза подвоює відстань пошуку. Процес з найбільшим UID врешті-решт виявить, що його повідомлення пройшли максимальну відстань і повернулись назад, після чого оголошує себе лідером.

== Робота алгоритму

1. *Ініціалізація* (`run()` в `process_node.py:132-154`):
  - Кожен процес починає з фази 0
  - Розсилає OUT повідомлення з `hop_count = 2^0 = 1` в обидва напрямки

2. *Фази алгоритму:*
  - У фазі k процес розсилає OUT повідомлення на відстань 2^k
  - OUT повідомлення пересилаються, якщо uid повідомлення більший за uid поточного процесу
  - Коли повідомлення досягає максимальної відстані, воно перетворюється на IN
  - IN повідомлення повертається до ініціатора

3. *Перехід між фазами:*
  - Процес чекає на IN повідомлення з обох напрямків
  - Коли отримано обидва IN - переходить до фази k+1
  - Розсилає нові OUT з `hop_count = 2^(k+1)`

4. *Визначення лідера:*
  - Якщо OUT повідомлення процесу робить повне коло і повертається до нього
  - Це означає, що всі інші процеси мають менші UID
  - Процес оголошує себе лідером

== Логіка лідера

Коли процес визначає себе як лідер (в `_out_message()` в `process_node.py:77-81`):

```python
elif msg.uid == self.uid:
    self.status = Status.LEADER
    self._log("I'm the leader!")
    self.leader_uid = self.uid
    self._send_leader()
```

Після цього:
1. Лідер змінює свій статус на `LEADER`
2. Відправляє `LeaderMessage` з своїм UID
3. Інші процеси отримують це повідомлення та пересилають далі по кільцю
4. Коли `LeaderMessage` повертається до лідера - всі процеси знають про лідера
5. Всі процеси завершують роботу та виводять фінальний звіт

= Інструкції з запуску

== Вимоги

- Python 3.12 або новіший
- Стандартна бібліотека Python (без додаткових залежностей)

== Запуск

1. Клонуйте репозиторій:
```bash
git clone https://github.com/Kentoso/distr-info-processing.git
cd distr-info-processing/lab1
```

2. Запустіть програму:
```bash
uv run main.py
```
або
```bash
python main.py
```

3. За замовчуванням створюється кільце з 5 процесів. Для зміни кількості процесів відредагуйте рядок 41 в `main.py`:
```python
procs = create_ring_processes(5, _process)  # Змініть 5 на потрібну кількість
```

== Вихідні дані

При запуску програма виводить:
1. PID всіх створених процесів через кому
2. Логи роботи кожного процесу (отримані повідомлення, визначення лідера)
3. Фінальний звіт для кожного процесу:
  - UID лідера
  - Кількість відправлених повідомлень по годинниковій стрілці (CW)
  - Кількість відправлених повідомлень проти годинникової стрілки (CCW)
  - Загальна кількість відправлених повідомлень
  - Кількість раундів виконання

== Приклад виводу

Нижче наведено приклад виводу програми для кільця з 3 процесів:

```
42045,42046,42047
[42046]: got message: Message(uid=42045, flag=<Flag.OUT: 'out'>, hop_count=1)
[42045]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=1)
[42047]: got message: Message(uid=42046, flag=<Flag.OUT: 'out'>, hop_count=1)
[42046]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=1)
[42047]: got message: Message(uid=42045, flag=<Flag.OUT: 'out'>, hop_count=1)
[42045]: got message: Message(uid=42046, flag=<Flag.OUT: 'out'>, hop_count=1)
[42047]: got message: Message(uid=42047, flag=<Flag.IN: 'in'>, hop_count=1)
[42047]: got message: Message(uid=42047, flag=<Flag.IN: 'in'>, hop_count=1)
[42046]: got message: Message(uid=42046, flag=<Flag.IN: 'in'>, hop_count=1)
[42046]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=2)
[42045]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=2)
[42045]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=1)
[42046]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=1)
[42045]: got message: Message(uid=42047, flag=<Flag.IN: 'in'>, hop_count=1)
[42046]: got message: Message(uid=42047, flag=<Flag.IN: 'in'>, hop_count=1)
[42047]: got message: Message(uid=42047, flag=<Flag.IN: 'in'>, hop_count=1)
[42047]: got message: Message(uid=42047, flag=<Flag.IN: 'in'>, hop_count=1)
[42046]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=4)
[42045]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=4)
[42045]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=3)
[42046]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=3)
[42047]: got message: Message(uid=42047, flag=<Flag.OUT: 'out'>, hop_count=2)
[42047]: I'm the leader!
[42045]: did you know that 42047 is the leader?

=== Final Report for Node 42045 ===
Leader UID: 42047
Messages sent CW: 6
Messages sent CCW: 4
Total messages sent: 10
Total rounds: 7
========================================
[42046]: did you know that 42047 is the leader?

=== Final Report for Node 42046 ===
Leader UID: 42047
Messages sent CW: 5
Messages sent CCW: 4
Total messages sent: 9
Total rounds: 8
========================================
[42047]: everyone knows that I'm the leader now!

=== Final Report for Node 42047 ===
Leader UID: 42047
Messages sent CW: 4
Messages sent CCW: 3
Total messages sent: 7
Total rounds: 6
========================================
```

У цьому прикладі процес з UID 42047 (найбільший UID) був обраний лідером. Видно роботу алгоритму через фази з різними значеннями `hop_count` (1, 2, 4), поки повідомлення процесу 42047 не повернулось до нього, після чого він оголосив себе лідером та розіслав `LeaderMessage` всім іншим процесам.

= Посилання

*GitHub репозиторій:* #link("https://github.com/Kentoso/distr-info-processing")

Репозиторій містить повний вихідний код проєкту, включаючи всі файли реалізації алгоритму HS та цей звіт.
