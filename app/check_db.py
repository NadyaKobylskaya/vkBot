"""
Просмотр состояния базы данных.
Запуск: python check_db.py  (из папки app/)
"""
import asyncio
import aiosqlite
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "app", "bot_database.db")

async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Общее количество
        cur = await db.execute("SELECT COUNT(*) as cnt FROM tasks")
        total = (await cur.fetchone())["cnt"]
        print(f"\n{'='*60}")
        print(f"  ВСЕГО заданий в БД: {total}")
        print(f"{'='*60}\n")

        # ── По заданиям ОГЭ ──────────────────────────────────────
        print("ОГЭ — сводка по номерам заданий:")
        print(f"{'Задание':<10} {'Тем':<6} {'Заданий':<10} Темы")
        print("-"*60)
        cur = await db.execute("""
            SELECT task_number,
                   COUNT(DISTINCT topic) as topics,
                   COUNT(*) as cnt,
                   GROUP_CONCAT(DISTINCT topic) as topic_list
            FROM tasks
            WHERE exam_type = 'oge'
            GROUP BY task_number
            ORDER BY task_number
        """)
        rows = await cur.fetchall()
        loaded = set()
        for r in rows:
            loaded.add(r["task_number"])
            topics = r["topic_list"] or ""
            print(f"  №{r['task_number']:<8} {r['topics']:<6} {r['cnt']:<10} {topics}")

        # Что не загружено
        all_tasks = set(range(1, 26))
        missing = sorted(all_tasks - loaded)
        print(f"\n{'='*60}")
        if missing:
            print(f"❌ НЕ ЗАГРУЖЕНЫ задания ОГЭ: {missing}")
        else:
            print("✅ Все задания ОГЭ (1-25) загружены!")
        print(f"{'='*60}\n")

        # ── Наборы 1-5 по темам ──────────────────────────────────
        print("Наборы 1-5 (по темам и set_id):")
        print(f"{'Тема':<25} {'Наборов':<10} {'Заданий'}")
        print("-"*50)
        cur = await db.execute("""
            SELECT topic,
                   COUNT(DISTINCT set_id) as sets,
                   COUNT(*) as cnt
            FROM tasks
            WHERE exam_type = 'oge' AND task_number BETWEEN 1 AND 5
            GROUP BY topic
            ORDER BY topic
        """)
        for r in await cur.fetchall():
            print(f"  {r['topic']:<25} {r['sets']:<10} {r['cnt']}")

        # Какие темы 1-5 вообще отсутствуют
        all_topics = {"kvartira","uchastok","plan","listy","shiny","tarify","pech"}
        cur = await db.execute("""
            SELECT DISTINCT topic FROM tasks
            WHERE exam_type='oge' AND task_number BETWEEN 1 AND 5
        """)
        loaded_topics = {r["topic"] for r in await cur.fetchall()}
        missing_topics = all_topics - loaded_topics
        if missing_topics:
            print(f"\n❌ Отсутствуют темы 1-5: {missing_topics}")
        else:
            print("\n✅ Все темы заданий 1-5 загружены!")

        # ── Задания 6-25 по темам ────────────────────────────────
        print(f"\n{'='*60}")
        print("Задания 6-25 — детали по темам:")
        print("-"*60)
        cur = await db.execute("""
            SELECT task_number, topic, COUNT(*) as cnt
            FROM tasks
            WHERE exam_type = 'oge' AND task_number >= 6
            GROUP BY task_number, topic
            ORDER BY task_number, topic
        """)
        prev = None
        for r in await cur.fetchall():
            if r["task_number"] != prev:
                print(f"\n  Задание №{r['task_number']}:")
                prev = r["task_number"]
            print(f"    {r['topic']:<35} {r['cnt']} шт.")


        # ── Статистика картинок ──────────────────────────────────────
        print(f"\n{'='*60}")
        print("Картинки (image_path):")
        print("-"*60)
        cur = await db.execute("""
            SELECT
              SUM(CASE WHEN image_path IS NULL THEN 1 ELSE 0 END)           as no_img,
              SUM(CASE WHEN image_path LIKE 'doc%' THEN 1 ELSE 0 END)       as vk_doc,
              SUM(CASE WHEN image_path LIKE 'photo%' THEN 1 ELSE 0 END)     as vk_photo,
              SUM(CASE WHEN image_path LIKE 'http%' THEN 1 ELSE 0 END)      as url,
              SUM(CASE WHEN image_path LIKE 'app/%'
                        OR image_path LIKE 'C:%'
                        OR image_path LIKE '/%' THEN 1 ELSE 0 END)          as local
            FROM tasks
        """)
        img = await cur.fetchone()
        print(f"  ✅ VK doc (загружено в VK)   : {img['vk_doc']} заданий")
        print(f"  🌐 URL (внешняя ссылка)      : {img['url']} заданий")
        print(f"  💻 Локальный путь (нужно загрузить в VK): {img['local']} заданий")
        print(f"  📷 VK photo                  : {img['vk_photo']} заданий")
        print(f"  ➖ Без картинки              : {img['no_img']} заданий")
        if img['local'] and img['local'] > 0:
            print(f"\n  ⚠️  Запусти upload_docs_to_vk.py чтобы загрузить {img['local']} файлов в VK")
        else:
            print("\n  ✅ Все картинки загружены в VK!")
        print(f"{'='*60}\n")

        # ── Пользователи и попытки ───────────────────────────────
        print(f"\n{'='*60}")
        cur = await db.execute("SELECT COUNT(*) as cnt FROM users")
        users = (await cur.fetchone())["cnt"]
        cur = await db.execute("SELECT COUNT(*) as cnt FROM attempts")
        attempts = (await cur.fetchone())["cnt"]
        print(f"  Пользователей: {users}")
        print(f"  Попыток ответов: {attempts}")
        print(f"{'='*60}\n")

asyncio.run(main())
