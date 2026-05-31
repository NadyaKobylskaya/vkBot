"""
Просмотр состояния базы данных по ОГЭ, ЕГЭ профиль и ЕГЭ база.

Показывает:
  • общее количество заданий;
  • сводку по exam_type и task_number;
  • отсутствующие номера заданий;
  • детализацию по темам;
  • статистику image_path;
  • пользователей и попытки.

Запуск: python check_db.py
"""
import asyncio
import aiosqlite
import os
from collections import defaultdict

_dir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_dir)
DB_PATH = os.path.join(BASE_DIR, "app", "bot_database.db")


EXAMS = {
    "oge": {
        "title": "ОГЭ",
        "expected": range(1, 26),
    },
    "ege_profile": {
        "title": "ЕГЭ профиль",
        "expected": range(1, 20),
    },
    "ege_base": {
        "title": "ЕГЭ база",
        "expected": range(1, 22),
    },
}


async def table_exists(db: aiosqlite.Connection, table_name: str) -> bool:
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    row = await cur.fetchone()
    return row is not None


async def get_count_safe(db: aiosqlite.Connection, table_name: str) -> int:
    if not await table_exists(db, table_name):
        return 0
    cur = await db.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}")
    row = await cur.fetchone()
    return row["cnt"]


def print_line(char: str = "=", width: int = 80) -> None:
    print(char * width)


async def print_exam_summary(db: aiosqlite.Connection, exam_type: str, title: str, expected) -> None:
    print_line()
    print(f"{title} ({exam_type})")
    print_line()

    cur = await db.execute(
        """
        SELECT task_number,
               COUNT(*) AS cnt,
               COUNT(DISTINCT topic) AS topics,
               SUM(CASE WHEN image_path IS NOT NULL AND TRIM(image_path) != '' THEN 1 ELSE 0 END) AS with_img,
               GROUP_CONCAT(DISTINCT topic) AS topic_list
        FROM tasks
        WHERE exam_type = ?
        GROUP BY task_number
        ORDER BY task_number
        """,
        (exam_type,),
    )
    rows = await cur.fetchall()

    if not rows:
        print("❌ Заданий этого типа пока нет.\n")
        return

    total = sum(r["cnt"] for r in rows)
    loaded_numbers = {r["task_number"] for r in rows}
    expected_numbers = set(expected)
    missing = sorted(expected_numbers - loaded_numbers)
    extra = sorted(loaded_numbers - expected_numbers)

    print(f"Всего заданий: {total}")
    print(f"Загружено номеров: {len(loaded_numbers)} из {len(expected_numbers)}")
    if missing:
        print(f"❌ Не загружены номера: {missing}")
    else:
        print("✅ Все ожидаемые номера загружены.")
    if extra:
        print(f"⚠️ Есть номера вне ожидаемого диапазона: {extra}")

    print()
    print(f"{'№':<5} {'Заданий':<10} {'Тем':<6} {'С карт.':<9} Темы")
    print("-" * 80)
    for r in rows:
        topics = r["topic_list"] or ""
        print(
            f"{r['task_number']:<5} "
            f"{r['cnt']:<10} "
            f"{r['topics']:<6} "
            f"{r['with_img']:<9} "
            f"{topics}"
        )

    print()


async def print_exam_topics_detail(db: aiosqlite.Connection, exam_type: str, title: str) -> None:
    print_line("-")
    print(f"{title}: детализация по темам")
    print_line("-")

    cur = await db.execute(
        """
        SELECT task_number,
               topic,
               COUNT(*) AS cnt,
               SUM(CASE WHEN image_path IS NOT NULL AND TRIM(image_path) != '' THEN 1 ELSE 0 END) AS with_img
        FROM tasks
        WHERE exam_type = ?
        GROUP BY task_number, topic
        ORDER BY task_number, topic
        """,
        (exam_type,),
    )
    rows = await cur.fetchall()

    if not rows:
        print("Нет данных.\n")
        return

    prev = None
    for r in rows:
        if r["task_number"] != prev:
            print(f"\nЗадание №{r['task_number']}:")
            prev = r["task_number"]
        print(f"  {r['topic']:<45} {r['cnt']:>5} шт.  | с картинкой: {r['with_img']}")

    print()


async def print_image_summary(db: aiosqlite.Connection) -> None:
    print_line()
    print("Статистика изображений image_path")
    print_line()

    cur = await db.execute(
        """
        SELECT exam_type,
               COUNT(*) AS total,
               SUM(CASE WHEN image_path IS NULL OR TRIM(image_path) = '' THEN 1 ELSE 0 END) AS no_img,
               SUM(CASE WHEN image_path LIKE 'doc%' THEN 1 ELSE 0 END) AS vk_doc,
               SUM(CASE WHEN image_path LIKE 'photo%' THEN 1 ELSE 0 END) AS vk_photo,
               SUM(CASE WHEN image_path LIKE 'http%' THEN 1 ELSE 0 END) AS url,
               SUM(CASE WHEN image_path LIKE 'app/%'
                         OR image_path LIKE 'C:%'
                         OR image_path LIKE '/%' THEN 1 ELSE 0 END) AS local
        FROM tasks
        GROUP BY exam_type
        ORDER BY exam_type
        """
    )
    rows = await cur.fetchall()

    print(f"{'Тип':<14} {'Всего':<8} {'Без':<8} {'VK doc':<8} {'VK photo':<10} {'URL':<8} {'Локал.':<8}")
    print("-" * 80)
    for r in rows:
        print(
            f"{r['exam_type']:<14} "
            f"{r['total']:<8} "
            f"{r['no_img'] or 0:<8} "
            f"{r['vk_doc'] or 0:<8} "
            f"{r['vk_photo'] or 0:<10} "
            f"{r['url'] or 0:<8} "
            f"{r['local'] or 0:<8}"
        )

    cur = await db.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM tasks
        WHERE image_path LIKE 'app/%'
           OR image_path LIKE 'C:%'
           OR image_path LIKE '/%'
        """
    )
    local_total = (await cur.fetchone())["cnt"]

    if local_total:
        print(f"\n⚠️ Локальных путей: {local_total}. Их нужно загрузить в VK или убедиться, что бот умеет отправлять локальные файлы.")
    else:
        print("\n✅ Локальных путей нет.")

    print()


async def print_local_image_missing(db: aiosqlite.Connection) -> None:
    """
    Проверяет существование локальных изображений относительно BASE_DIR.
    Например: app/images_b/n10/img_001.png -> BASE_DIR/app/images_b/n10/img_001.png
    """
    cur = await db.execute(
        """
        SELECT exam_type, task_number, id, image_path
        FROM tasks
        WHERE image_path LIKE 'app/%'
           OR image_path LIKE 'C:%'
           OR image_path LIKE '/%'
        ORDER BY exam_type, task_number, id
        """
    )
    rows = await cur.fetchall()

    if not rows:
        return

    missing = []
    for r in rows:
        image_path = r["image_path"]
        if image_path.startswith("app/"):
            full_path = os.path.join(BASE_DIR, image_path)
        else:
            full_path = image_path

        if not os.path.exists(full_path):
            missing.append((r["exam_type"], r["task_number"], r["id"], image_path))

    print_line()
    print("Проверка локальных файлов изображений")
    print_line()

    if not missing:
        print("✅ Все локальные изображения найдены.\n")
        return

    print(f"⚠️ Не найдено локальных изображений: {len(missing)}")
    for exam_type, task_number, task_id, image_path in missing[:30]:
        print(f"  {exam_type}, №{task_number}, id={task_id}: {image_path}")
    if len(missing) > 30:
        print(f"  … и ещё {len(missing) - 30}")
    print()


async def print_users_attempts(db: aiosqlite.Connection) -> None:
    print_line()
    print("Пользователи и попытки")
    print_line()

    users = await get_count_safe(db, "users")
    attempts = await get_count_safe(db, "attempts")

    print(f"Пользователей: {users}")
    print(f"Попыток ответов: {attempts}")
    print()


async def main() -> None:
    print(f"\nБаза данных: {DB_PATH}")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if not await table_exists(db, "tasks"):
            print("❌ Таблица tasks не найдена.")
            return

        cur = await db.execute("SELECT COUNT(*) AS cnt FROM tasks")
        total = (await cur.fetchone())["cnt"]

        print_line()
        print(f"ВСЕГО заданий в БД: {total}")
        print_line()

        cur = await db.execute(
            """
            SELECT exam_type, COUNT(*) AS cnt
            FROM tasks
            GROUP BY exam_type
            ORDER BY exam_type
            """
        )
        print("\nПо типам экзамена:")
        for r in await cur.fetchall():
            print(f"  {r['exam_type']:<14} {r['cnt']}")

        print()

        for exam_type, info in EXAMS.items():
            await print_exam_summary(
                db,
                exam_type=exam_type,
                title=info["title"],
                expected=info["expected"],
            )

        for exam_type, info in EXAMS.items():
            await print_exam_topics_detail(
                db,
                exam_type=exam_type,
                title=info["title"],
            )

        await print_image_summary(db)
        await print_local_image_missing(db)
        await print_users_attempts(db)


if __name__ == "__main__":
    asyncio.run(main())
