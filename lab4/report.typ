#set page(paper: "a4")
#show heading: set text(size: 14pt)

#align(center, text(14pt)[
  *Лабораторна робота №4*\
  Задача про обідаючих філософів:\
  лічильний семафор та м'ютекс з семафорами виделок
])

= Середовище виконання

Лабораторна робота виконана з використанням наступних технологій та інструментів:

- *Мова програмування:* Python 3.12
- *Операційна система:* macOS (Tahoe 26.2)
- *Основні бібліотеки:*
  - `multiprocessing` — для створення процесів, семафорів та м'ютексів
  - `dataclasses` — для визначення структури статистики
  - `enum` — для визначення станів філософа
  - `random`, `time` — для симуляції роздумів та їжі

Проєкт не вимагає зовнішніх залежностей і використовує лише стандартну бібліотеку Python.

= Загальний опис проєкту

Проєкт розв'язує класичну задачу про обідаючих філософів (Dining Philosophers Problem) двома способами:

1. *Рішення 1* — лічильний семафор (N−1) як контроль допуску до столу
2. *Рішення 2* — м'ютекс для атомарного захоплення виделок + 5 бінарних семафорів виделок

== Умова задачі

П'ятеро філософів сидять за круглим столом. Між кожними двома тарілками лежить одна виделка (всього 5 виделок). Щоб їсти, філософу потрібні обидві виделки — ліва та права. Задача — розробити алгоритм, при якому жоден філософ не голодуватиме (відсутність deadlock та starvation).

== Структура проєкту

=== `models.py`
Визначає базові типи даних:

- *`PhilosopherState`* — стани філософа (`THINKING`, `HUNGRY`, `EATING`)
- *`PhilosopherStats`* — статистика філософа:
  - `philosopher_id` — ідентифікатор
  - `times_eaten` — скільки разів поїв
  - `total_thinking_time` — загальний час роздумів
  - `total_eating_time` — загальний час їжі

=== `philosopher.py`
Клас `Philosopher` — логіка поведінки одного філософа:

- *`think()`* — переходить у стан `THINKING`, спить випадковий час від 0.1 до 0.5 с
- *`eat()`* — переходить у стан `EATING`, спить випадковий час від 0.1 до 0.3 с
- *`run()`* — основний цикл: think → hungry → acquire → eat → release
- *`_print_final_report()`* — виводить статистику після завершення

=== `main.py`
Містить стратегії синхронізації та точку входу:

- *`CountingSemaphoreStrategy`* — рішення 1
- *`MutexForkStrategy`* — рішення 2
- *`run_with_counting_semaphore()`* — запускає 5 процесів з рішенням 1
- *`run_with_mutex_and_fork_semaphores()`* — запускає 5 процесів з рішенням 2

= Детальний опис рішень

== Рішення 1: лічильний семафор (N−1)

*Ідея:* до столу одночасно допускається щонайбільше N−1 = 4 філософи. Це гарантує, що завжди знайдеться хоча б один філософ, який може захопити обидві свої виделки, оскільки при 4 філософах на 5 виделках хоча б одна пара сусідніх виделок вільна.

Клас `CountingSemaphoreStrategy` у `main.py:8-22`:

```python
class CountingSemaphoreStrategy:
    def __init__(self, room, forks, n):
        self.room = room      # Semaphore(N - 1)
        self.forks = forks    # [Lock() for _ in range(N)]
        self.n = n

    def acquire(self, pid):
        self.room.acquire()              # займаємо місце в "кімнаті"
        self.forks[pid].acquire()        # захоплюємо ліву виделку
        self.forks[(pid + 1) % self.n].acquire()  # захоплюємо праву виделку

    def release(self, pid):
        self.forks[pid].release()
        self.forks[(pid + 1) % self.n].release()
        self.room.release()              # звільняємо місце в "кімнаті"
```

*Ресурси:*
- `room = mp.Semaphore(N - 1)` — лічильний семафор, що обмежує кількість філософів за столом
- `forks = [mp.Lock() for _ in range(N)]` — 5 м'ютексів для виделок

*Deadlock:*
Deadlock неможливий: при N−1 філософах хоча б один завжди зможе взяти обидві виделки

== Рішення 2: м'ютекс + бінарні семафори виделок

*Ідея:* захоплення обох виделок відбувається атомарно під захистом глобального м'ютекса. Це виключає ситуацію, коли кілька філософів одночасно захоплюють по одній виделці та взаємно блокують один одного.

Клас `MutexForkStrategy` у `main.py:25-38`:

```python
class MutexForkStrategy:
    def __init__(self, mutex, forks, n):
        self.mutex = mutex    # Lock()
        self.forks = forks    # [Semaphore(1) for _ in range(N)]
        self.n = n

    def acquire(self, pid):
        with self.mutex:                              # атомарно захоплюємо обидві виделки
            self.forks[pid].acquire()
            self.forks[(pid + 1) % self.n].acquire()

    def release(self, pid):
        self.forks[pid].release()
        self.forks[(pid + 1) % self.n].release()
```

*Ресурси:*
- `mutex = mp.Lock()` — глобальний м'ютекс для атомарності
- `forks = [mp.Semaphore(1) for _ in range(N)]` — 5 бінарних семафорів для виделок

*Deadlock:*
Deadlock неможливий: захоплення завжди відбувається під м'ютексом — не може бути часткового захоплення виделок

= Логіка роботи філософа

Метод `run()` у `philosopher.py:34-44`:

```python
def run(self):
    for _ in range(self.meals):
        self.think()
        self.state = PhilosopherState.HUNGRY
        self._log("hungry, waiting for forks")
        self.acquire_forks(self.id)
        self.eat()
        self.release_forks(self.id)
        self._log("released forks")

    self._print_final_report()
```

Кожен філософ виконує `meals` (за замовчуванням 5) циклів їжа–роздуми. Стратегія синхронізації передається через `acquire_forks` та `release_forks` — це дозволяє використовувати обидва рішення з одним і тим самим класом `Philosopher`.

= Запуск та вихідні дані

== Інструкції з запуску

```bash
git clone https://github.com/Kentoso/distr-info-processing.git
cd distr-info-processing/lab4
uv run main.py
```

== Вихідні дані

Програма послідовно виконує обидва рішення. Нижче наведено приклад виводу для `MEALS = 1`:

```
=== Solution 1: Counting Semaphore ===
[Philosopher 0]: thinking
[Philosopher 3]: thinking
[Philosopher 1]: thinking
[Philosopher 2]: thinking
[Philosopher 4]: thinking
[Philosopher 3]: hungry, waiting for forks
[Philosopher 3]: eating
[Philosopher 3]: released forks

=== Final Report for Philosopher 3 ===
Times eaten: 1
Total thinking time: 0.113s
Total eating time: 0.187s
========================================
[Philosopher 2]: hungry, waiting for forks
[Philosopher 2]: eating
[Philosopher 1]: hungry, waiting for forks
[Philosopher 0]: hungry, waiting for forks
[Philosopher 4]: hungry, waiting for forks
[Philosopher 2]: released forks
[Philosopher 1]: eating

=== Final Report for Philosopher 2 ===
Times eaten: 1
Total thinking time: 0.331s
Total eating time: 0.163s
========================================
[Philosopher 1]: released forks
[Philosopher 0]: eating

=== Final Report for Philosopher 1 ===
Times eaten: 1
Total thinking time: 0.345s
Total eating time: 0.250s
========================================
[Philosopher 0]: released forks
[Philosopher 4]: eating

=== Final Report for Philosopher 0 ===
Times eaten: 1
Total thinking time: 0.433s
Total eating time: 0.131s
========================================
[Philosopher 4]: released forks

=== Final Report for Philosopher 4 ===
Times eaten: 1
Total thinking time: 0.418s
Total eating time: 0.217s
========================================

=== Solution 2: Mutex + Fork Semaphores ===
[Philosopher 4]: thinking
[Philosopher 0]: thinking
[Philosopher 1]: thinking
[Philosopher 2]: thinking
[Philosopher 3]: thinking
[Philosopher 4]: hungry, waiting for forks
[Philosopher 4]: eating
[Philosopher 2]: hungry, waiting for forks
[Philosopher 2]: eating
[Philosopher 3]: hungry, waiting for forks
[Philosopher 1]: hungry, waiting for forks
[Philosopher 2]: released forks

=== Final Report for Philosopher 2 ===
Times eaten: 1
Total thinking time: 0.235s
Total eating time: 0.183s
========================================
[Philosopher 4]: released forks

=== Final Report for Philosopher 4 ===
[Philosopher 3]: eating
Times eaten: 1
Total thinking time: 0.220s
Total eating time: 0.242s
========================================
[Philosopher 1]: eating
[Philosopher 0]: hungry, waiting for forks
[Philosopher 3]: released forks

=== Final Report for Philosopher 3 ===
Times eaten: 1
Total thinking time: 0.247s
Total eating time: 0.101s
========================================
[Philosopher 1]: released forks

=== Final Report for Philosopher 1 ===
Times eaten: 1
[Philosopher 0]: eating
Total thinking time: 0.356s
Total eating time: 0.296s
========================================
[Philosopher 0]: released forks

=== Final Report for Philosopher 0 ===
Times eaten: 1
Total thinking time: 0.495s
Total eating time: 0.263s
========================================
```

Для кожного філософа після завершення виводиться фінальний звіт з кількістю прийомів їжі та загальним часом у кожному стані.

= Порівняння рішень

#table(
  columns: (1fr, 1fr, 1fr),
  [*Характеристика*], [*Рішення 1*], [*Рішення 2*],
  [Синхронізація], [Лічильний семафор + м'ютекси виделок], [М'ютекс + бінарні семафори],
  [Паралельність], [До N−1 філософів одночасно], [Один за раз захоплює виделки],
  [Deadlock], [Виключено семафором кімнати], [Виключено глобальним м'ютексом],
)

= Посилання

*GitHub репозиторій:* #link("https://github.com/Kentoso/distr-info-processing")

Репозиторій містить повний вихідний код проєкту, включаючи обидві реалізації та цей звіт.
