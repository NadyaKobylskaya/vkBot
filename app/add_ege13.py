"""
Добавление задания 13 ЕГЭ профиль «Уравнения» в БД.

Источник: Е. А. Ширяева «Задачник ЕГЭпроф 2026» (тренажёр), Блок 1 ФИПИ.
Разделы:
  II  — Показательные уравнения      (задания 4.1–7.4)
  III — Тригонометрические уравнения (задания 8.1–59.2)
  IV  — Смешанные уравнения          (задания 60.1–80.2)

Изображения (app/images/ege13/img_NNN.png):
  001–012  → Показательные (4.1–7.4)            12 заданий
  013–140  → Тригонометрические (8.1–59.2)     128 заданий
  141–184  → Смешанные (60.1–80.2)              44 задания
  Итого: 184 задания

Каждое изображение содержит полное условие (уравнение + интервал).
Поле question хранит только короткую подпись — бот показывает её текстом,
затем отправляет картинку отдельным сообщением.

Ответы добавить через add_ege13_answers.py.
Запуск: из папки app/ → python ../add_ege13.py
"""

import asyncio
import aiosqlite
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "app", "bot_database.db")
IMG_DIR  = "images_p/ege13"

EXP  = "exponential_equations"
TRIG = "trigonometric_equations"
MIX  = "mixed_equations"

STD  = "Задание 13 ЕГЭ. Реши уравнение и найди корни на указанном отрезке."
OBZ  = "Задание 13 ЕГЭ (повышенный уровень). Реши уравнение и найди корни на указанном промежутке."
DEMO = "Задание 13 ЕГЭ (демовариант). Реши уравнение и найди корни на указанном отрезке."


def img(n: int) -> str:
    return f"{IMG_DIR}/img_{n:03d}.png"


# ════════════════════════════════════════════════════════════════════════════
# ЗАДАНИЯ: (topic, img_path, question, answer, difficulty)
# answer = None  →  заполняется позднее через add_ege13_answers.py
# difficulty: 2 = стандартное, 3 = ОБЗ / Демо
# ════════════════════════════════════════════════════════════════════════════

TASKS: list[tuple] = []

# ── II. ПОКАЗАТЕЛЬНЫЕ (img 001–012) ─────────────────────────────────────────
for _n, _cap in [
    ( 1, STD),   # 4.1
    ( 2, STD),   # 4.2
    ( 3, STD),   # 5.1
    ( 4, STD),   # 5.2
    ( 5, OBZ),   # 6.1
    ( 6, OBZ),   # 6.2
    ( 7, OBZ),   # 6.3
    ( 8, OBZ),   # 6.4
    ( 9, STD),   # 7.1
    (10, STD),   # 7.2
    (11, STD),   # 7.3
    (12, STD),   # 7.4
]:
    _d = 3 if _cap == OBZ else 2
    TASKS.append((EXP, img(_n), _cap, None, _d))

# ── III. ТРИГОНОМЕТРИЧЕСКИЕ (img 013–140) ────────────────────────────────────
for _n, _cap in [
    ( 13, STD),  # 8.1
    ( 14, STD),  # 8.2
    ( 15, STD),  # 8.3
    ( 16, STD),  # 8.4
    ( 17, STD),  # 9.1
    ( 18, STD),  # 9.2
    ( 19, STD),  # 9.3
    ( 20, STD),  # 9.4
    ( 21, OBZ),  # 10.1
    ( 22, OBZ),  # 10.2
    ( 23, STD),  # 11.1
    ( 24, STD),  # 11.2
    ( 25, STD),  # 11.3
    ( 26, STD),  # 11.4
    ( 27, STD),  # 12.1
    ( 28, STD),  # 12.2
    ( 29, OBZ),  # 13.1
    ( 30, OBZ),  # 13.2
    ( 31, OBZ),  # 14.1
    ( 32, OBZ),  # 14.2
    ( 33, STD),  # 15.1
    ( 34, STD),  # 15.2
    ( 35, STD),  # 16.1
    ( 36, STD),  # 16.2
    ( 37, STD),  # 16.3
    ( 38, STD),  # 16.4
    ( 39, STD),  # 17.1
    ( 40, STD),  # 17.2
    ( 41, STD),  # 17.3
    ( 42, STD),  # 18.1
    ( 43, STD),  # 18.2
    ( 44, STD),  # 18.3
    ( 45, STD),  # 19.1
    ( 46, STD),  # 19.2
    ( 47, OBZ),  # 20.1
    ( 48, OBZ),  # 20.2
    ( 49, OBZ),  # 20.3
    ( 50, OBZ),  # 20.4
    ( 51, STD),  # 21.1
    ( 52, STD),  # 21.2
    ( 53, STD),  # 22.1
    ( 54, STD),  # 22.2
    ( 55, OBZ),  # 23.1
    ( 56, OBZ),  # 23.2
    ( 57, OBZ),  # 24.1
    ( 58, OBZ),  # 24.2
    ( 59, STD),  # 25.1
    ( 60, STD),  # 25.2
    ( 61, STD),  # 26.1
    ( 62, STD),  # 26.2
    ( 63, STD),  # 26.3
    ( 64, STD),  # 26.4
    ( 65, OBZ),  # 27.1
    ( 66, OBZ),  # 27.2
    ( 67, OBZ),  # 28.1
    ( 68, OBZ),  # 28.2
    ( 69, OBZ),  # 29.1
    ( 70, OBZ),  # 29.2
    ( 71, OBZ),  # 30.1
    ( 72, OBZ),  # 30.2
    ( 73, STD),  # 31.1
    ( 74, STD),  # 31.2
    ( 75, STD),  # 32.1
    ( 76, STD),  # 32.2
    ( 77, STD),  # 33.1
    ( 78, STD),  # 33.2
    ( 79, STD),  # 34.1
    ( 80, STD),  # 34.2
    ( 81, STD),  # 35.1
    ( 82, STD),  # 35.2
    ( 83, STD),  # 36.1
    ( 84, STD),  # 36.2
    ( 85, OBZ),  # 37.1
    ( 86, OBZ),  # 37.2
    ( 87, OBZ),  # 38.1
    ( 88, OBZ),  # 38.2
    ( 89, OBZ),  # 39.1
    ( 90, OBZ),  # 39.2
    ( 91, OBZ),  # 39.3
    ( 92, OBZ),  # 40.1
    ( 93, OBZ),  # 40.2
    ( 94, OBZ),  # 40.3
    ( 95, STD),  # 41.1
    ( 96, STD),  # 41.2
    ( 97, STD),  # 41.3
    ( 98, STD),  # 42.1
    ( 99, STD),  # 42.2
    (100, STD),  # 42.3
    (101, STD),  # 43.1
    (102, STD),  # 43.2
    (103, STD),  # 44.1
    (104, STD),  # 44.2
    (105, OBZ),  # 45.1
    (106, OBZ),  # 45.2
    (107, STD),  # 46.1
    (108, STD),  # 46.2
    (109, STD),  # 46.3
    (110, STD),  # 46.4
    (111, STD),  # 47.1
    (112, STD),  # 47.2
    (113, STD),  # 47.3
    (114, STD),  # 47.4
    (115, STD),  # 48.1
    (116, STD),  # 48.2
    (117, STD),  # 49.1
    (118, STD),  # 49.2
    (119, STD),  # 49.3
    (120, STD),  # 49.4
    (121, STD),  # 50.1
    (122, STD),  # 50.2
    (123, OBZ),  # 51.1
    (124, OBZ),  # 51.2
    (125, STD),  # 52.1
    (126, STD),  # 52.2
    (127, OBZ),  # 53.1
    (128, OBZ),  # 53.2
    (129, OBZ),  # 54.1
    (130, OBZ),  # 54.2
    (131, DEMO), # 55.1
    (132, DEMO), # 55.2
    (133, OBZ),  # 56.1
    (134, OBZ),  # 56.2
    (135, OBZ),  # 57.1
    (136, OBZ),  # 57.2
    (137, OBZ),  # 58.1
    (138, OBZ),  # 58.2
    (139, OBZ),  # 59.1
    (140, OBZ),  # 59.2
]:
    _d = 2 if _cap == STD else 3
    TASKS.append((TRIG, img(_n), _cap, None, _d))

# ── IV. СМЕШАННЫЕ (img 141–184) ──────────────────────────────────────────────
for _n, _cap in [
    (141, STD),  # 60.1
    (142, STD),  # 60.2
    (143, STD),  # 61.1
    (144, STD),  # 61.2
    (145, STD),  # 62.1
    (146, STD),  # 62.2
    (147, STD),  # 63.1
    (148, STD),  # 63.2
    (149, STD),  # 64.1
    (150, STD),  # 64.2
    (151, STD),  # 65.1
    (152, STD),  # 65.2
    (153, STD),  # 66.1
    (154, STD),  # 66.2
    (155, STD),  # 67.1
    (156, STD),  # 67.2
    (157, STD),  # 68.1
    (158, STD),  # 68.2
    (159, OBZ),  # 69.1
    (160, OBZ),  # 69.2
    (161, OBZ),  # 70.1
    (162, OBZ),  # 70.2
    (163, STD),  # 71.1
    (164, STD),  # 71.2
    (165, STD),  # 72.1
    (166, STD),  # 72.2
    (167, STD),  # 72.3
    (168, STD),  # 72.4
    (169, OBZ),  # 73.1
    (170, OBZ),  # 73.2
    (171, OBZ),  # 74.1
    (172, OBZ),  # 74.2
    (173, STD),  # 75.1
    (174, STD),  # 75.2
    (175, STD),  # 76.1
    (176, STD),  # 76.2
    (177, OBZ),  # 77.1
    (178, OBZ),  # 77.2
    (179, OBZ),  # 78.1
    (180, OBZ),  # 78.2
    (181, OBZ),  # 79.1
    (182, OBZ),  # 79.2
    (183, OBZ),  # 80.1
    (184, OBZ),  # 80.2
]:
    _d = 2 if _cap == STD else 3
    TASKS.append((MIX, img(_n), _cap, None, _d))


# ════════════════════════════════════════════════════════════════════════════
# ЗАПИСЬ В БД
# ════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    print(f"База данных: {DB_PATH}")
    print(f"Всего заданий к добавлению: {len(TASKS)}")

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            "SELECT COUNT(*) FROM tasks WHERE exam_type='ege' AND task_number=13"
        )
        (count,) = await cursor.fetchone()

        if count > 0:
            print(f"\nВ БД уже есть {count} заданий ЕГЭ №13.")
            ans = input("Удалить и перезалить? (y/n): ").strip().lower()
            if ans == "y":
                await db.execute(
                    "DELETE FROM tasks WHERE exam_type='ege' AND task_number=13"
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
                ("ege", 13, topic, question, answer or "",
                 image_path, difficulty, None)
            )
            inserted += 1

        await db.commit()

    exp_count   = sum(1 for t in TASKS if t[0] == EXP)
    trig_count  = sum(1 for t in TASKS if t[0] == TRIG)
    mixed_count = sum(1 for t in TASKS if t[0] == MIX)
    obz_count   = sum(1 for t in TASKS if t[4] == 3)

    print(f"\n✅ Добавлено {inserted} заданий ЕГЭ №13.")
    print(f"   Показательные:      {exp_count:3d}  (img 001–012)")
    print(f"   Тригонометрические: {trig_count:3d}  (img 013–140)")
    print(f"   Смешанные:          {mixed_count:3d}  (img 141–184)")
    print(f"   Из них ОБЗ/Демо:    {obz_count:3d}  (difficulty=3)")
    print()
    print("⚠️  Ответы пусты — запустите add_ege13_answers.py")
    print("⚠️  Изображения → app/images/ege13/img_001.png … img_184.png")


if __name__ == "__main__":
    asyncio.run(main())
