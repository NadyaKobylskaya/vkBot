"""
Скрипт для добавления заданий в базу данных.
Запуск: python add_tasks.py

Как использовать:
1. Открой PDF с заданиями
2. Перепиши задание в поле question
3. Укажи правильный ответ в поле answer
4. Запусти скрипт
"""

import asyncio
import aiosqlite

DB_PATH = "app/bot_database.db"


async def add_task(
    exam_type: str,      # 'oge' или 'ege'
    task_number: int,    # номер задания: 6, 7, 8 ... 25
    topic: str,          # тема (см. список ниже)
    question: str,       # текст задания (или "" если только картинка)
    answer: str,         # правильный ответ
    image_path: str = None,    # путь к картинке: "app/images/task6_1.jpg"
    solution_path: str = None, # путь к файлу решения для 2й части
    answer_type: str = "number",  # 'number' или 'text'
    difficulty: int = 1,          # 1=лёгкое, 2=среднее, 3=сложное
    set_id: int = None,  # для заданий 1-5: номер набора (1, 2, 3...)
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO tasks
                (exam_type, task_number, topic, question, answer,
                 image_path, solution_path, answer_type, difficulty, set_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exam_type, task_number, topic, question, answer,
              image_path, solution_path, answer_type, difficulty, set_id))
        await db.commit()
        print(f"✅ Добавлено: задание {task_number} | тема: {topic} | ответ: {answer}")


async def main():

    # ================================================================
    # СПРАВОЧНИК ТЕМ
    # ================================================================
    #
    # ЗАДАНИЯ 1-5 (наборы по 5 штук, одна тема):
    #   topic = "kvartira" | "uchastok" | "plan" | "listy" | "shiny" | "tarify" | "pech"
    #   set_id = номер набора (1, 2, 3...) — у всех 5 заданий одного набора одинаковый set_id
    #
    # ЗАДАНИЕ 6:   "ordinary_fractions" | "decimal_fractions"
    # ЗАДАНИЕ 7:   "general"
    # ЗАДАНИЕ 8:   "degrees" | "arithmetic_square_root"
    # ЗАДАНИЕ 9:   "linear_equations" | "quadratic_equations"
    # ЗАДАНИЕ 10:  "probability"
    # ЗАДАНИЕ 11:  "general"  (или другая тема)
    # ЗАДАНИЕ 12:  "general"
    # ЗАДАНИЕ 13:  "linear_inequalities" | "quadratic_inequalities" | "systems_linear_inequalities"
    # ЗАДАНИЕ 14:  "arithmetic_progression" | "geometric_progression"
    # ЗАДАНИЕ 15:  "triangles"
    # ЗАДАНИЕ 16:  "circles"
    # ЗАДАНИЕ 17:  "parallelogram" | "trapezoid" | "rectangle" | "rhombus" | "square"
    # ЗАДАНИЕ 18:  "grid"
    # ЗАДАНИЕ 19:  "general"
    # ЗАДАНИЕ 20:  "systems" | "equations" | "inequalities"
    # ЗАДАНИЕ 21:  "motion_line" | "motion_water" | "work" | "percent"
    # ЗАДАНИЕ 22:  "functions"
    # ЗАДАНИЕ 23:  "geometry"
    # ЗАДАНИЕ 24:  "geometry_proof"
    # ЗАДАНИЕ 25:  "geometry_proof"
    #
    # ================================================================

    # ----------------------------------------------------------------
    # ПРИМЕР: Задание 12
    # ----------------------------------------------------------------
    await add_task(
        exam_type="oge",
        task_number=12,
        topic="general",
        question="На координатной прямой отмечены точки A и B. "
                 "Найдите длину отрезка AB, если A = -3, B = 5.",
        answer="8",
    )

    # ----------------------------------------------------------------
    # ПРИМЕР: Задание 15 (треугольники) — с картинкой
    # ----------------------------------------------------------------
    await add_task(
        exam_type="oge",
        task_number=15,
        topic="triangles",
        question="В треугольнике ABC угол A = 90°, AB = 6, AC = 8. Найдите BC.",
        answer="10",
        # image_path="app/images/task15_1.jpg",  # раскомментировать если есть картинка
    )

    # ----------------------------------------------------------------
    # ПРИМЕР: Задание 17 (четырёхугольники)
    # ----------------------------------------------------------------
    await add_task(
        exam_type="oge",
        task_number=17,
        topic="rectangle",
        question="Периметр прямоугольника равен 28 см, одна из сторон равна 6 см. "
                 "Найдите площадь прямоугольника.",
        answer="48",
    )

    # ----------------------------------------------------------------
    # ПРИМЕР: Набор заданий 1-5 (тема "Квартира", набор №1)
    # Все 5 заданий имеют set_id=1 и topic="kvartira"
    # ----------------------------------------------------------------
    await add_task(
        exam_type="oge", task_number=1, topic="kvartira",
        question="В квартире 3 комнаты площадью 12, 15 и 18 кв.м. "
                 "Найдите общую площадь комнат.",
        answer="45", set_id=1,
    )
    await add_task(
        exam_type="oge", task_number=2, topic="kvartira",
        question="Стоимость ремонта 1 кв.м составляет 2500 руб. "
                 "Сколько стоит ремонт комнаты площадью 15 кв.м?",
        answer="37500", set_id=1,
    )
    await add_task(
        exam_type="oge", task_number=3, topic="kvartira",
        question="На покраску 1 кв.м уходит 0.3 кг краски. "
                 "Сколько краски нужно на комнату 18 кв.м?",
        answer="5.4", set_id=1,
    )
    await add_task(
        exam_type="oge", task_number=4, topic="kvartira",
        question="Высота потолка 2.7 м, площадь пола 15 кв.м. "
                 "Найдите объём комнаты.",
        answer="40.5", set_id=1,
    )
    await add_task(
        exam_type="oge", task_number=5, topic="kvartira",
        question="Квартира сдаётся за 25000 руб/мес. "
                 "Сколько заплатит жилец за 8 месяцев?",
        answer="200000", set_id=1,
    )

    # ================================================================
    # ДОБАВЛЯЙ СВОИ ЗАДАНИЯ НИЖЕ ПО АНАЛОГИИ
    # ================================================================


asyncio.run(main())