"""
Исправление неверных exam_type в БД.

Проблемы:
  1. exam_type='ege'  (184 задания, №13) → должно быть 'ege_profile'
     Это задание 13 ЕГЭ профиль (уравнения), добавленное скриптом add_ege13.py
     с неверным exam_type.

  2. exam_type='egb'  (78 заданий, №18) → должно быть 'ege_base'
     Это задание 18 ЕГЭ база (неравенства), добавленное с опечаткой в exam_type.

Запуск: из любой папки → python fix_exam_types.py
"""

import asyncio
import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_database.db")


async def main() -> None:
    print(f"База данных: {DB_PATH}")

    async with aiosqlite.connect(DB_PATH) as db:

        # ── Статистика ДО ───────────────────────────────────────────────
        print("\n=== Статистика ДО исправления ===")
        cursor = await db.execute(
            "SELECT exam_type, COUNT(*) FROM tasks GROUP BY exam_type ORDER BY exam_type"
        )
        for row in await cursor.fetchall():
            print(f"  {row[0]}: {row[1]} заданий")

        # ── Исправление 1: ege → ege_profile ───────────────────────────
        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE exam_type='ege'")
        (cnt,) = await cursor.fetchone()

        if cnt > 0:
            print(f"\n[1] Исправляю {cnt} заданий: 'ege' → 'ege_profile'")
            await db.execute("UPDATE tasks SET exam_type='ege_profile' WHERE exam_type='ege'")
            print(f"    ✅ Готово")
        else:
            print("\n[1] Заданий с exam_type='ege' не найдено — пропускаю")
        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE exam_type='egb'")
        (cnt,) = await cursor.fetchone()

        if cnt > 0:
            print(f"\n[2] Исправляю {cnt} заданий: 'egb' → 'ege_base'")
            await db.execute("UPDATE tasks SET exam_type='ege_base' WHERE exam_type='egb'")
            print(f"    ✅ Готово")
        else:
            print("\n[2] Заданий с exam_type='egb' не найдено — пропускаю")

        # ── Исправление 3: ege (task_number=13) → ege_profile ──────────
        # Задание 13 ЕГЭ профиль было записано с exam_type='ege' вместо 'ege_profile'
        cursor = await db.execute(
            "SELECT COUNT(*) FROM tasks WHERE exam_type='ege' AND task_number=13"
        )
        (cnt,) = await cursor.fetchone()

        if cnt > 0:
            print(f"\n[3] Исправляю {cnt} заданий: exam_type='ege', task_number=13 → 'ege_profile'")
            await db.execute(
                "UPDATE tasks SET exam_type='ege_profile' WHERE exam_type='ege' AND task_number=13"
            )
            print(f"    ✅ Готово")
        else:
            print("\n[3] Заданий с exam_type='ege' task_number=13 не найдено — пропускаю")

        # ── Исправление 4: topic для ege_profile task_number=13 ──────────
        # Топики exponential_equations / trigonometric_equations / mixed_equations
        # нужно привести к единому ege_p13_eq (или оставить как есть — запрос
        # через topic=None будет работать при любых топиках)
        cursor = await db.execute(
            "SELECT COUNT(*) FROM tasks "
            "WHERE exam_type='ege_profile' AND task_number=13 AND topic != 'ege_p13_eq'"
        )
        (cnt,) = await cursor.fetchone()
        if cnt > 0:
            print(f"\n[4] Унифицирую топик: {cnt} заданий task_number=13 → topic='ege_p13_eq'")
            await db.execute(
                "UPDATE tasks SET topic='ege_p13_eq' "
                "WHERE exam_type='ege_profile' AND task_number=13"
            )
            print(f"    ✅ Готово")
        else:
            print("\n[4] Топик task_number=13 уже унифицирован — пропускаю")

        await db.commit()

        # ── Статистика ПОСЛЕ ────────────────────────────────────────────
        print("\n=== Статистика ПОСЛЕ исправления ===")
        cursor = await db.execute(
            "SELECT exam_type, COUNT(*) FROM tasks GROUP BY exam_type ORDER BY exam_type"
        )
        for row in await cursor.fetchall():
            print(f"  {row[0]}: {row[1]} заданий")

        # ── Проверка ege_profile по номерам ─────────────────────────────
        print("\n=== ege_profile по номерам задания ===")
        cursor = await db.execute(
            "SELECT task_number, COUNT(*) FROM tasks "
            "WHERE exam_type='ege_profile' GROUP BY task_number ORDER BY task_number"
        )
        for row in await cursor.fetchall():
            print(f"  №{row[0]}: {row[1]} шт.")

        # ── Проверка ege_base по номерам ────────────────────────────────
        print("\n=== ege_base по номерам задания ===")
        cursor = await db.execute(
            "SELECT task_number, COUNT(*) FROM tasks "
            "WHERE exam_type='ege_base' GROUP BY task_number ORDER BY task_number"
        )
        rows = await cursor.fetchall()
        for row in rows:
            print(f"  №{row[0]}: {row[1]} шт.")

        existing = {row[0] for row in rows}
        missing = set(range(1, 22)) - existing
        if missing:
            print(f"\n  ⚠️  Отсутствуют в ege_base: задания {sorted(missing)}")
            print("     Нужно добавить эти задания в БД отдельным скриптом.")
        else:
            print("\n  ✅ Все задания 1–21 присутствуют в ege_base")


if __name__ == "__main__":
    asyncio.run(main())
