"""
Добавление задания 15 ЕГЭ профиль «Неравенства» в БД.

Источник: Е. А. Ширяева «Задачник ЕГЭпроф 2026», Блок 1 ФИПИ.
Разделы:
  I  — Показательные неравенства   (задания 1–14)
  II — Логарифмические неравенства (задания 15–32)

Нумерация изображений (images_p/ege15/img_NNN.png):
  001–010  Задание 1  (ОБЗ)         10 шт.
  011–018  Задание 2                  8 шт.
  019–020  Задание 3  (ОБЗ)          2 шт.
  021–024  Задание 4  (ОБЗ, Демо)    4 шт.
  025–026  Задание 5                  2 шт.
  027–034  Задание 6                  8 шт.
  035–040  Задание 7  (ОБЗ)          6 шт.
  041–048  Задание 8  (ОБЗ)          8 шт.
  049–050  Задание 9                  2 шт.
  051–054  Задание 10                 4 шт.
  055–056  Задание 11                 2 шт.
  057–060  Задание 12 (ОБЗ)          4 шт.
  061–062  Задание 13 (ОБЗ)          2 шт.
  063–066  Задание 14                 4 шт.
  067–072  Задание 15 (ОБЗ)          6 шт.
  073–074  Задание 16                 2 шт.
  075–080  Задание 17 (ОБЗ)          6 шт.
  081–084  Задание 18 (ОБЗ)          4 шт.
  085–096  Задание 19 (ОБЗ)         12 шт.
  097–098  Задание 20                 2 шт.
  099–102  Задание 21                 4 шт.
  103–112  Задание 22 (ОБЗ)         10 шт.
  113–118  Задание 23 (ОБЗ)          6 шт.
  119–122  Задание 24 (ОБЗ)          4 шт.
  123–126  Задание 25 (ОБЗ)          4 шт.
  127–128  Задание 26 (ОБЗ)          2 шт.
  129–130  Задание 27 (ОБЗ)          2 шт.
  131–134  Задание 28                 4 шт.
  135–138  Задание 29 (ОБЗ)          4 шт.
  139–142  Задание 30                 4 шт.
  143–144  Задание 31 (Демо)          2 шт.
  145–146  Задание 32                 2 шт.
  Итого: 146 заданий

Ответы добавить через add_ege15_answers.py.
Запуск: из папки app/ → python ../add_ege15.py
"""

import asyncio
import aiosqlite
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "app", "bot_database.db")
IMG_DIR  = "images_p/ege15"

EXP = "exponential_inequalities"
LOG = "logarithmic_inequalities"

STD  = "Задание 15 ЕГЭ. Реши неравенство. Запиши ответ в виде промежутка или объединения промежутков."
OBZ  = "Задание 15 ЕГЭ (повышенный уровень). Реши неравенство."
DEMO = "Задание 15 ЕГЭ (демовариант). Реши неравенство."


def img(n: int) -> str:
    return f"{IMG_DIR}/img_{n:03d}.png"


# ════════════════════════════════════════════════════════════════════════════
# ЗАДАНИЯ: (topic, img_path, question, answer, difficulty)
# answer = None  →  заполняется через add_ege15_answers.py
# difficulty: 2 = стандартное, 3 = ОБЗ / Демо
# ════════════════════════════════════════════════════════════════════════════

TASKS: list[tuple] = []

# ── I. ПОКАЗАТЕЛЬНЫЕ НЕРАВЕНСТВА ────────────────────────────────────────────

# Задание 1 (ОБЗ): img 001–010
for _n in range(1, 11):
    TASKS.append((EXP, img(_n), OBZ, None, 3))

# Задание 2: img 011–018
for _n in range(11, 19):
    TASKS.append((EXP, img(_n), STD, None, 2))

# Задание 3 (ОБЗ): img 019–020
for _n in range(19, 21):
    TASKS.append((EXP, img(_n), OBZ, None, 3))

# Задание 4 (ОБЗ, Демо): img 021–024
# 4.1–4.2 ОБЗ, 4.3–4.4 тоже ОБЗ, но в условии написано "Демо" для всего задания
for _n in range(21, 25):
    TASKS.append((EXP, img(_n), DEMO, None, 3))

# Задание 5: img 025–026
for _n in range(25, 27):
    TASKS.append((EXP, img(_n), STD, None, 2))

# Задание 6: img 027–034
for _n in range(27, 35):
    TASKS.append((EXP, img(_n), STD, None, 2))

# Задание 7 (ОБЗ): img 035–040
for _n in range(35, 41):
    TASKS.append((EXP, img(_n), OBZ, None, 3))

# Задание 8 (ОБЗ): img 041–048
for _n in range(41, 49):
    TASKS.append((EXP, img(_n), OBZ, None, 3))

# Задание 9: img 049–050
for _n in range(49, 51):
    TASKS.append((EXP, img(_n), STD, None, 2))

# Задание 10: img 051–054
for _n in range(51, 55):
    TASKS.append((EXP, img(_n), STD, None, 2))

# Задание 11: img 055–056
for _n in range(55, 57):
    TASKS.append((EXP, img(_n), STD, None, 2))

# Задание 12 (ОБЗ): img 057–060
for _n in range(57, 61):
    TASKS.append((EXP, img(_n), OBZ, None, 3))

# Задание 13 (ОБЗ): img 061–062
for _n in range(61, 63):
    TASKS.append((EXP, img(_n), OBZ, None, 3))

# Задание 14: img 063–066
for _n in range(63, 67):
    TASKS.append((EXP, img(_n), STD, None, 2))

# ── II. ЛОГАРИФМИЧЕСКИЕ НЕРАВЕНСТВА ─────────────────────────────────────────

# Задание 15 (ОБЗ): img 067–072
for _n in range(67, 73):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 16: img 073–074
for _n in range(73, 75):
    TASKS.append((LOG, img(_n), STD, None, 2))

# Задание 17 (ОБЗ): img 075–080
for _n in range(75, 81):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 18 (ОБЗ): img 081–084
for _n in range(81, 85):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 19 (ОБЗ): img 085–096
for _n in range(85, 97):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 20: img 097–098
for _n in range(97, 99):
    TASKS.append((LOG, img(_n), STD, None, 2))

# Задание 21: img 099–102
for _n in range(99, 103):
    TASKS.append((LOG, img(_n), STD, None, 2))

# Задание 22 (ОБЗ): img 103–112
for _n in range(103, 113):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 23 (ОБЗ): img 113–118
for _n in range(113, 119):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 24 (ОБЗ): img 119–122
for _n in range(119, 123):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 25 (ОБЗ): img 123–126
for _n in range(123, 127):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 26 (ОБЗ): img 127–128
for _n in range(127, 129):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 27 (ОБЗ): img 129–130
for _n in range(129, 131):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 28: img 131–134
for _n in range(131, 135):
    TASKS.append((LOG, img(_n), STD, None, 2))

# Задание 29 (ОБЗ): img 135–138
for _n in range(135, 139):
    TASKS.append((LOG, img(_n), OBZ, None, 3))

# Задание 30: img 139–142
for _n in range(139, 143):
    TASKS.append((LOG, img(_n), STD, None, 2))

# Задание 31 (Демо): img 143–144
for _n in range(143, 145):
    TASKS.append((LOG, img(_n), DEMO, None, 3))

# Задание 32: img 145–146
for _n in range(145, 147):
    TASKS.append((LOG, img(_n), STD, None, 2))


# ════════════════════════════════════════════════════════════════════════════
# ЗАПИСЬ В БД
# ════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    print(f"База данных: {DB_PATH}")
    print(f"Всего заданий к добавлению: {len(TASKS)}")

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            "SELECT COUNT(*) FROM tasks WHERE exam_type=\'ege\' AND task_number=15"
        )
        (count,) = await cursor.fetchone()

        if count > 0:
            print(f"\nВ БД уже есть {count} заданий ЕГЭ №15.")
            ans = input("Удалить и перезалить? (y/n): ").strip().lower()
            if ans == "y":
                await db.execute(
                    "DELETE FROM tasks WHERE exam_type=\'ege\' AND task_number=15"
                )
                await db.commit()
                print("Старые записи удалены.")
            else:
                print("Отмена.")
                return

        inserted = 0
        for (topic, image_path, question, answer, difficulty) in TASKS:
            await db.execute(
                "INSERT INTO tasks "
                "(exam_type, task_number, topic, question, answer, "
                "image_path, difficulty, set_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("ege", 15, topic, question, answer or "",
                 image_path, difficulty, None)
            )
            inserted += 1

        await db.commit()

    exp_count  = sum(1 for t in TASKS if t[0] == EXP)
    log_count  = sum(1 for t in TASKS if t[0] == LOG)
    obz_count  = sum(1 for t in TASKS if t[4] == 3)
    std_count  = sum(1 for t in TASKS if t[4] == 2)

    print(f"\n✅ Добавлено {inserted} заданий ЕГЭ №15.")
    print(f"   Показательные неравенства:   {exp_count:3d}  (img 001–066)")
    print(f"   Логарифмические неравенства: {log_count:3d}  (img 067–146)")
    print(f"   Стандартные (difficulty=2):  {std_count:3d}")
    print(f"   ОБЗ / Демо  (difficulty=3):  {obz_count:3d}")
    print()
    print("⚠️  Ответы пусты — запустите add_ege15_answers.py")
    print("⚠️  Изображения → images_p/ege15/img_001.png … img_146.png")


if __name__ == "__main__":
    asyncio.run(main())
