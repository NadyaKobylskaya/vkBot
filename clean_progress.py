"""
clean_progress.py — Очистка некорректных записей в таблице progress.

Удаляет записи где exam_type не соответствует теме задания:
  - oge + тема ege_p* (темы ЕГЭ профиль попали в ОГЭ)
  - oge + тема ege_b* (темы ЕГЭ база попали в ОГЭ)

Запуск:
    python clean_progress.py
    python clean_progress.py --dry-run  # только показать что будет удалено
"""

import asyncio
import aiosqlite
import argparse

DB_PATH = "app/bot_database.db"


async def clean(dry_run: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Показываем что будет удалено
        cursor = await db.execute("""
            SELECT exam_type, task_number, topic, total, correct
            FROM progress
            WHERE (exam_type = 'oge' AND (topic LIKE 'ege_p%' OR topic LIKE 'ege_b%'))
               OR (exam_type = 'ege_base' AND topic LIKE 'ege_p%')
            ORDER BY exam_type, task_number, topic
        """)
        rows = await cursor.fetchall()

        if not rows:
            print("✅ Грязных записей не найдено — база чистая.")
            return

        print(f"{'[DRY RUN] ' if dry_run else ''}Найдено {len(rows)} некорректных записей:\n")
        for r in rows:
            print(f"  exam_type={r['exam_type']}  task={r['task_number']}  "
                  f"topic={r['topic']}  попыток={r['total']}  верно={r['correct']}")

        if dry_run:
            print("\n⚠️  Запусти без --dry-run чтобы удалить.")
            return

        # Удаляем
        await db.execute("""
            DELETE FROM progress
            WHERE (exam_type = 'oge' AND (topic LIKE 'ege_p%' OR topic LIKE 'ege_b%'))
               OR (exam_type = 'ege_base' AND topic LIKE 'ege_p%')
        """)
        await db.commit()
        print(f"\n✅ Удалено {len(rows)} записей.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Только показать что будет удалено, не удалять")
    args = parser.parse_args()
    asyncio.run(clean(dry_run=args.dry_run))
