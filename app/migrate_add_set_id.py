"""
Миграция: добавляет колонку set_id в таблицу tasks.
Запуск: python migrate_add_set_id.py
"""
import asyncio
import aiosqlite
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "app", "bot_database.db")

async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем — есть ли уже колонка
        cursor = await db.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if "set_id" in columns:
            print("✅ Колонка set_id уже есть, ничего делать не нужно.")
            return
        
        await db.execute("ALTER TABLE tasks ADD COLUMN set_id INTEGER")
        await db.commit()
        print("✅ Колонка set_id успешно добавлена!")
        
        # Показываем текущую структуру таблицы
        cursor = await db.execute("PRAGMA table_info(tasks)")
        rows = await cursor.fetchall()
        print("\nСтруктура таблицы tasks:")
        for row in rows:
            print(f"  {row[1]:20} {row[2]}")

asyncio.run(main())
