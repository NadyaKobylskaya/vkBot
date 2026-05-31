"""
Добавление заданий №11 «Графики функций» в БД.
Запуск: python add_n11.py  (из папки app/)

Картинки положи в app/images/n11/:
  Блок 1, Задание 1 (соответствие, линейные): b1_z1_s1.png … b1_z1_s6.png
  Блок 1, Задание 2 (соответствие, линейные): b1_z2_s1.png … b1_z2_s6.png
  Блок 1, Задания 3–14 (знаки, линейные):    b1_z3.png … b1_z14.png
  Блок 1, Задания 15–26 (знаки, параболы):   b1_z15.png … b1_z26.png
  Блок 1, Задание 27 (смешанные):            b1_z27_s1.png … b1_z27_s6.png
  Блок 1, Задание 28 (смешанные):            b1_z28_s1.png … b1_z28_s6.png
  Блок 2, Задание 5 (параболы полные):       b2_z5_s1.png … b2_z5_s6.png
  Блок 2, Задание 6 (параболы полные):       b2_z6_s1.png … b2_z6_s6.png
  Блок 2, Задание 7 (гиперболы):             b2_z7_s1.png … b2_z7_s6.png
  Блок 2, Задание 8 (гиперболы):             b2_z8_s1.png … b2_z8_s6.png

Итого: 72 задания.
Задания Блок 2 Задание 1–4 НЕ включены (требуют развёрнутого ответа).
"""
import asyncio
import aiosqlite
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "app", "bot_database.db")

IMG = "app/images/n11"

# ── Темы ─────────────────────────────────────────────────────────────────────
LINEAR    = "linear_function"      # Линейная функция (прямая)
QUADRATIC = "quadratic_function"   # Квадратичная функция (парабола)
HYPERBOLA = "hyperbola"            # Обратная пропорциональность (гипербола)
MIXED     = "mixed_graphs"         # Смешанные задания

# ── Шаблоны вопросов ─────────────────────────────────────────────────────────
_q_match = (
    "Установите соответствие между графиками функций и формулами, "
    "которые их задают. Запишите последовательность цифр "
    "(номера формул для графиков А, Б, В) без пробелов, запятых "
    "и других символов."
)
_q_signs_lin = (
    "На рисунке изображены графики функций вида y = kx + b. "
    "Установите соответствие между графиками и знаками коэффициентов. "
    "Запишите последовательность цифр (номер характеристики для "
    "графиков А, Б, В) без пробелов."
)
_q_signs_quad = (
    "На рисунке изображены графики функций вида y = ax² + bx + c. "
    "Установите соответствие между графиками и знаками коэффициентов. "
    "Запишите последовательность цифр (номер характеристики для "
    "графиков А, Б, В) без пробелов."
)
_q_match_mix = (
    "Установите соответствие между графиками функций и формулами, "
    "которые их задают. Запишите последовательность цифр "
    "(номера формул для графиков А, Б, В) без пробелов."
)

# ── Список заданий: (topic, image_path, question_suffix, answer) ─────────────
# question = шаблон + "\n" + question_suffix (формулы/коэффициенты конкретной задачи)

TASKS = [

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 1, Задание 1 — соответствие формулам (линейные функции)
    # ══════════════════════════════════════════════════════════════════════════
    (LINEAR, f"{IMG}/b1_z1_s1.png",
     _q_match + "\n1) y = x+3   2) y = 3   3) y = 3x",
     "123"),
    (LINEAR, f"{IMG}/b1_z1_s2.png",
     _q_match + "\n1) y = −2x−1   2) y = 2x+1   3) y = −2x+1",
     "321"),
    (LINEAR, f"{IMG}/b1_z1_s3.png",
     _q_match + "\n1) y = −x   2) y = −1   3) y = x−1",
     "312"),
    (LINEAR, f"{IMG}/b1_z1_s4.png",
     _q_match + "\n1) y = 2x+4   2) y = −2x+4   3) y = −2x−4",
     "123"),
    (LINEAR, f"{IMG}/b1_z1_s5.png",
     _q_match + "\n1) y = 2/5·x+2   2) y = 2/5·x−2   3) y = −2/5·x+2",
     "123"),
    (LINEAR, f"{IMG}/b1_z1_s6.png",
     _q_match + "\nА) y = −2/3·x−5   Б) y = 2/3·x+5   В) y = 2/3·x−5",
     "231"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 1, Задание 2 — соответствие формулам (линейные функции)
    # ══════════════════════════════════════════════════════════════════════════
    (LINEAR, f"{IMG}/b1_z2_s1.png",
     _q_match + "\nА) y = 2x+6   Б) y = −2x+6   В) y = −2x−6",
     "123"),
    (LINEAR, f"{IMG}/b1_z2_s2.png",
     _q_match + "\nА) y = −3x   Б) y = −1/3·x   В) y = 1/3·x",
     "132"),
    (LINEAR, f"{IMG}/b1_z2_s3.png",
     _q_match + "\nА) y = −2x−4   Б) y = 2x−4   В) y = −2x+4",
     "132"),
    (LINEAR, f"{IMG}/b1_z2_s4.png",
     _q_match + "\nА) y = 3x   Б) y = −3x   В) y = 1/3·x",
     "231"),
    (LINEAR, f"{IMG}/b1_z2_s5.png",
     _q_match + "\nА) y = 1/2·x−2   Б) y = −1/2·x+2   В) y = −1/2·x−2",
     "231"),
    (LINEAR, f"{IMG}/b1_z2_s6.png",
     _q_match + "\nА) y = −1/2·x+3   Б) y = 1/2·x+3   В) y = 1/2·x−3",
     "312"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 1, Задания 3–14 — знаки коэффициентов (линейные)
    # ══════════════════════════════════════════════════════════════════════════
    (LINEAR, f"{IMG}/b1_z3.png",
     _q_signs_lin + "\n1) k>0, b<0   2) k<0, b<0   3) k>0, b>0",
     "312"),
    (LINEAR, f"{IMG}/b1_z4.png",
     _q_signs_lin + "\n1) k<0, b<0   2) k<0, b>0   3) k>0, b>0",
     "132"),
    (LINEAR, f"{IMG}/b1_z5.png",
     _q_signs_lin + "\n1) k<0, b>0   2) k<0, b<0   3) k>0, b>0",
     "123"),
    (LINEAR, f"{IMG}/b1_z6.png",
     _q_signs_lin + "\n1) k<0, b>0   2) k<0, b<0   3) k>0, b<0",
     "312"),
    (LINEAR, f"{IMG}/b1_z7.png",
     _q_signs_lin + "\n1) k>0, b>0   2) k<0, b>0   3) k>0, b<0",
     "213"),
    (LINEAR, f"{IMG}/b1_z8.png",
     _q_signs_lin + "\n1) k<0, b<0   2) k>0, b>0   3) k>0, b<0",
     "231"),
    (LINEAR, f"{IMG}/b1_z9.png",
     _q_signs_lin + "\nА) k<0, b<0   Б) k<0, b>0   В) k>0, b<0",
     "213"),
    (LINEAR, f"{IMG}/b1_z10.png",
     _q_signs_lin + "\nА) k<0, b<0   Б) k<0, b>0   В) k>0, b>0",
     "231"),
    (LINEAR, f"{IMG}/b1_z11.png",
     _q_signs_lin + "\nА) k<0, b<0   Б) k<0, b>0   В) k>0, b<0",
     "123"),
    (LINEAR, f"{IMG}/b1_z12.png",
     _q_signs_lin + "\nА) k<0, b<0   Б) k<0, b>0   В) k>0, b<0",
     "321"),
    (LINEAR, f"{IMG}/b1_z13.png",
     _q_signs_lin + "\nА) k<0, b<0   Б) k>0, b>0   В) k<0, b>0",
     "123"),
    (LINEAR, f"{IMG}/b1_z14.png",
     _q_signs_lin + "\nА) k<0, b<0   Б) k>0, b<0   В) k>0, b>0",
     "312"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 1, Задания 15–26 — знаки коэффициентов (параболы)
    # ══════════════════════════════════════════════════════════════════════════
    (QUADRATIC, f"{IMG}/b1_z15.png",
     _q_signs_quad + "\n1) a<0, c>0   2) a>0, c<0   3) a>0, c>0",
     "321"),
    (QUADRATIC, f"{IMG}/b1_z16.png",
     _q_signs_quad + "\n1) a>0, c<0   2) a>0, c>0   3) a<0, c>0",
     "231"),
    (QUADRATIC, f"{IMG}/b1_z17.png",
     _q_signs_quad + "\n1) a<0, c>0   2) a>0, c<0   3) a<0, c<0",
     "321"),
    (QUADRATIC, f"{IMG}/b1_z18.png",
     _q_signs_quad + "\n1) a<0, c>0   2) a>0, c>0   3) a>0, c<0",
     "132"),
    (QUADRATIC, f"{IMG}/b1_z19.png",
     _q_signs_quad + "\n1) a<0, c>0   2) a>0, c>0   3) a>0, c<0",
     "312"),
    (QUADRATIC, f"{IMG}/b1_z20.png",
     _q_signs_quad + "\n1) a<0, c<0   2) a>0, c>0   3) a<0, c>0",
     "132"),
    (QUADRATIC, f"{IMG}/b1_z21.png",
     _q_signs_quad + "\nА) a<0, c>0   Б) a>0, c>0   В) a>0, c<0",
     "213"),
    (QUADRATIC, f"{IMG}/b1_z22.png",
     _q_signs_quad + "\nА) a>0, c>0   Б) a<0, c>0   В) a>0, c<0",
     "321"),
    (QUADRATIC, f"{IMG}/b1_z23.png",
     _q_signs_quad + "\nА) a<0, c>0   Б) a>0, c<0   В) a>0, c>0",
     "132"),
    (QUADRATIC, f"{IMG}/b1_z24.png",
     _q_signs_quad + "\nА) a<0, c>0   Б) a>0, c>0   В) a>0, c<0",
     "231"),
    (QUADRATIC, f"{IMG}/b1_z25.png",
     _q_signs_quad + "\nА) a<0, c>0   Б) a>0, c>0   В) a>0, c<0",
     "132"),
    (QUADRATIC, f"{IMG}/b1_z26.png",
     _q_signs_quad + "\nА) a<0, c<0   Б) a>0, c>0   В) a<0, c>0",
     "321"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 1, Задание 27 — смешанные (прямая / парабола / корень / гипербола)
    # ══════════════════════════════════════════════════════════════════════════
    (MIXED, f"{IMG}/b1_z27_s1.png",
     _q_match_mix + "\n1) y=−1/2·x   2) y=√x   3) y=−x²−2",
     "231"),
    (MIXED, f"{IMG}/b1_z27_s2.png",
     _q_match_mix + "\n1) y=−2/x   2) y=2x   3) y=x²−2",
     "321"),
    (MIXED, f"{IMG}/b1_z27_s3.png",
     _q_match_mix + "\n1) y=6/x   2) y=−2x+4   3) y=−2x²",
     "132"),
    (MIXED, f"{IMG}/b1_z27_s4.png",
     _q_match_mix + "\n1) y=1/2·x   2) y=2−x²   3) y=√x",
     "132"),
    (MIXED, f"{IMG}/b1_z27_s5.png",
     _q_match_mix + "\n1) y=−x²−4   2) y=√x   3) y=−2x−4",
     "123"),
    (MIXED, f"{IMG}/b1_z27_s6.png",
     _q_match_mix + "\n1) y=−1/x   2) y=4−x²   3) y=2x+4",
     "312"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 1, Задание 28 — смешанные
    # ══════════════════════════════════════════════════════════════════════════
    (MIXED, f"{IMG}/b1_z28_s1.png",
     _q_match_mix + "\nА) y=−x²−x+5   Б) y=−3/4·x−1   В) y=−12/x",
     "123"),
    (MIXED, f"{IMG}/b1_z28_s2.png",
     _q_match_mix + "\nА) y=1/x   Б) y=x+1   В) y=2x²+14x+24",
     "132"),
    (MIXED, f"{IMG}/b1_z28_s3.png",
     _q_match_mix + "\nА) y=4x²+4x−3   Б) y=1/2·x+6   В) y=1/(2x)",
     "312"),
    (MIXED, f"{IMG}/b1_z28_s4.png",
     _q_match_mix + "\nА) y=2x²+16x+29   Б) y=5/3·x+6   В) y=−4/x",
     "132"),
    (MIXED, f"{IMG}/b1_z28_s5.png",
     _q_match_mix + "\nА) y=−x²−5x−2   Б) y=−1/(3x)   В) y=−1/4·x−6",
     "312"),
    (MIXED, f"{IMG}/b1_z28_s6.png",
     _q_match_mix + "\nА) y=−3x²+9x−4   Б) y=−6/x   В) y=2/3·x−5",
     "321"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 2, Задание 5 — соответствие формулам (параболы, полное уравнение)
    # ══════════════════════════════════════════════════════════════════════════
    (QUADRATIC, f"{IMG}/b2_z5_s1.png",
     _q_match_mix + "\nА) y=2x²−10x+8   Б) y=−2x²+10x−8   В) y=−2x²−10x−8",
     "123"),
    (QUADRATIC, f"{IMG}/b2_z5_s2.png",
     _q_match_mix + "\n1) y=x²−7x+14   2) y=x²+7x+14   3) y=−x²−7x−14",
     "213"),
    (QUADRATIC, f"{IMG}/b2_z5_s3.png",
     _q_match_mix + "\n1) y=−3x²+3x+1   2) y=3x²−3x−1   3) y=−3x²−3x+1",
     "312"),
    (QUADRATIC, f"{IMG}/b2_z5_s4.png",
     _q_match_mix + "\nА) y=x²+8x+12   Б) y=x²−8x+12   В) y=−x²+8x−12",
     "123"),
    (QUADRATIC, f"{IMG}/b2_z5_s5.png",
     _q_match_mix + "\n1) y=x²−7x+9   2) y=−x²−7x−9   3) y=−x²+7x−9",
     "312"),
    (QUADRATIC, f"{IMG}/b2_z5_s6.png",
     _q_match_mix + "\n1) y=−3x²+24x−42   2) y=3x²−24x+42   3) y=−3x²−24x−42",
     "312"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 2, Задание 6 — соответствие формулам (параболы, полное уравнение)
    # ══════════════════════════════════════════════════════════════════════════
    (QUADRATIC, f"{IMG}/b2_z6_s1.png",
     _q_match_mix + "\n1) y=2x²−16x+29   2) y=2x²+16x+29   3) y=−2x²−16x−29",
     "123"),
    (QUADRATIC, f"{IMG}/b2_z6_s2.png",
     _q_match_mix + "\n1) y=−x²+6x−8   2) y=x²+6x+8   3) y=−x²−6x−8",
     "321"),
    (QUADRATIC, f"{IMG}/b2_z6_s3.png",
     _q_match_mix + "\n1) y=2x²−14x+22   2) y=−2x²−14x−22   3) y=−2x²+14x−22",
     "312"),
    (QUADRATIC, f"{IMG}/b2_z6_s4.png",
     _q_match_mix + "\n1) y=−x²−x−2   2) y=x²+x+2   3) y=x²−x+2",
     "321"),
    (QUADRATIC, f"{IMG}/b2_z6_s5.png",
     _q_match_mix + "\nА) y=−x²+2x+5   Б) y=x²+2x−5   В) y=−x²−2x+5",
     "123"),
    (QUADRATIC, f"{IMG}/b2_z6_s6.png",
     _q_match_mix + "\nА) y=−4x²−28x−46   Б) y=4x²−28x+46   В) y=−4x²+28x−46",
     "213"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 2, Задание 7 — гиперболы (обратная пропорциональность)
    # ══════════════════════════════════════════════════════════════════════════
    (HYPERBOLA, f"{IMG}/b2_z7_s1.png",
     _q_match_mix + "\n1) y=−1/(2x)   2) y=−2/x   3) y=2/x",
     "213"),
    (HYPERBOLA, f"{IMG}/b2_z7_s2.png",
     _q_match_mix + "\n1) y=−1/(3x)   2) y=3/x   3) y=−3/x",
     "213"),
    (HYPERBOLA, f"{IMG}/b2_z7_s3.png",
     _q_match_mix + "\n1) y=6/x   2) y=1/(6x)   3) y=−6/x",
     "321"),
    (HYPERBOLA, f"{IMG}/b2_z7_s4.png",
     _q_match_mix + "\n1) y=8/x   2) y=−1/(8x)   3) y=−8/x",
     "231"),
    (HYPERBOLA, f"{IMG}/b2_z7_s5.png",
     _q_match_mix + "\n1) y=1/(9x)   2) y=9/x   3) y=−9/x",
     "312"),
    (HYPERBOLA, f"{IMG}/b2_z7_s6.png",
     _q_match_mix + "\nА) y=12/x   Б) y=−12/x   В) y=−1/(12x)",
     "231"),

    # ══════════════════════════════════════════════════════════════════════════
    # БЛОК 2, Задание 8 — гиперболы
    # ══════════════════════════════════════════════════════════════════════════
    (HYPERBOLA, f"{IMG}/b2_z8_s1.png",
     _q_match_mix + "\n1) y=−4/x   2) y=4/x   3) y=1/(4x)",
     "213"),
    (HYPERBOLA, f"{IMG}/b2_z8_s2.png",
     _q_match_mix + "\n1) y=9/x   2) y=−9/x   3) y=−1/(9x)",
     "312"),
    (HYPERBOLA, f"{IMG}/b2_z8_s3.png",
     _q_match_mix + "\n1) y=10/x   2) y=1/(10x)   3) y=−10/x",
     "321"),
    (HYPERBOLA, f"{IMG}/b2_z8_s4.png",
     _q_match_mix + "\n1) y=2/x   2) y=1/(2x)   3) y=−2/x",
     "132"),
    (HYPERBOLA, f"{IMG}/b2_z8_s5.png",
     _q_match_mix + "\nА) y=−12/x   Б) y=1/(12x)   В) y=12/x",
     "123"),
    (HYPERBOLA, f"{IMG}/b2_z8_s6.png",
     _q_match_mix + "\nА) y=1/(6x)   Б) y=−6/x   В) y=6/x",
     "132"),
]


async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM tasks WHERE exam_type='oge' AND task_number=11"
        ) as cursor:
            count = (await cursor.fetchone())[0]

        if count > 0:
            print(f"В БД уже есть {count} заданий №11.")
            ans = input("Удалить и перезалить? (y/n): ").strip().lower()
            if ans == 'y':
                await db.execute(
                    "DELETE FROM tasks WHERE exam_type='oge' AND task_number=11"
                )
                await db.commit()
                print("Старые записи удалены.")
            else:
                print("Отмена.")
                return

        inserted = 0
        for (topic, image_path, question, answer) in TASKS:
            await db.execute(
                "INSERT INTO tasks "
                "(exam_type, task_number, topic, question, answer, image_path, set_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ('oge', 11, topic, question, answer, image_path, None)
            )
            inserted += 1

        await db.commit()
        print(f"Успешно добавлено {inserted} заданий №11.")
        print(f"  Линейная функция:           "
              f"{sum(1 for t in TASKS if t[0]==LINEAR)} заданий")
        print(f"  Квадратичная функция:        "
              f"{sum(1 for t in TASKS if t[0]==QUADRATIC)} заданий")
        print(f"  Обратная пропорциональность: "
              f"{sum(1 for t in TASKS if t[0]==HYPERBOLA)} заданий")
        print(f"  Смешанные задания:           "
              f"{sum(1 for t in TASKS if t[0]==MIXED)} заданий")


if __name__ == "__main__":
    asyncio.run(main())
