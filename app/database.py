import aiosqlite
import json
import random

DB_PATH = "app/bot_database.db"

# ═══════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ
# ═══════════════════════════════════════════════

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_type     TEXT    NOT NULL,
                task_number   INTEGER NOT NULL,
                topic         TEXT    NOT NULL,
                set_id        INTEGER DEFAULT NULL,  -- для наборов заданий 1-5
                question      TEXT,
                image_path    TEXT,
                answer        TEXT    NOT NULL,
                solution_path TEXT    DEFAULT NULL,  -- путь к файлу с решением (2-я часть)
                question_type TEXT    DEFAULT 'text',
                answer_type   TEXT    DEFAULT 'number',
                difficulty    INTEGER DEFAULT 1,
                created_at    TEXT    DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id         INTEGER UNIQUE NOT NULL,
                username      TEXT,
                exam_target   TEXT    DEFAULT 'oge',
                registered_at TEXT    DEFAULT (datetime('now')),
                last_active   TEXT    DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                task_id      INTEGER NOT NULL,
                user_answer  TEXT,
                is_correct   INTEGER NOT NULL,
                attempted_at TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                exam_type    TEXT    NOT NULL,
                task_number  INTEGER NOT NULL,
                topic        TEXT    NOT NULL,
                total        INTEGER DEFAULT 0,
                correct      INTEGER DEFAULT 0,
                last_attempt TEXT    DEFAULT (datetime('now')),
                UNIQUE(user_id, exam_type, task_number, topic),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.commit()
    print("✅ База данных инициализирована")

# ═══════════════════════════════════════════════
# ПОЛЬЗОВАТЕЛИ
# ═══════════════════════════════════════════════

async def get_or_create_user(vk_id: int, username: str = None) -> tuple[dict, bool]:
    """Возвращает (user_dict, is_new). is_new=True если пользователь только что создан."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Добавляем поле onboarding_done если его нет (миграция)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN onboarding_done INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # колонка уже есть
        await db.execute("""
            UPDATE users SET last_active = datetime('now'), username = COALESCE(?, username)
            WHERE vk_id = ?
        """, (username, vk_id))
        await db.execute("INSERT OR IGNORE INTO users (vk_id, username) VALUES (?, ?)", (vk_id, username))
        await db.commit()
        cursor = await db.execute("SELECT changes()")
        (changes,) = await cursor.fetchone()
        is_new = changes > 0
        cursor = await db.execute("SELECT * FROM users WHERE vk_id = ?", (vk_id,))
        row = await cursor.fetchone()
        return dict(row), is_new


async def mark_onboarding_done(vk_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET onboarding_done = 1 WHERE vk_id = ?", (vk_id,))
        await db.commit()

async def set_exam_target(vk_id: int, exam_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET exam_target = ? WHERE vk_id = ?", (exam_type, vk_id))
        await db.commit()

# ═══════════════════════════════════════════════
# ЗАДАНИЯ — ОБЫЧНЫЕ
# ═══════════════════════════════════════════════

async def get_random_task(exam_type: str, task_number: int, topic: str | None) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if topic is None:
            cursor = await db.execute("""
                SELECT * FROM tasks
                WHERE exam_type = ? AND task_number = ?
                ORDER BY RANDOM() LIMIT 1
            """, (exam_type, task_number))
        else:
            cursor = await db.execute("""
                SELECT * FROM tasks
                WHERE exam_type = ? AND task_number = ? AND topic = ?
                ORDER BY RANDOM() LIMIT 1
            """, (exam_type, task_number, topic))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_tasks_count(exam_type: str, task_number: int, topic: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM tasks
            WHERE exam_type = ? AND task_number = ? AND topic = ?
        """, (exam_type, task_number, topic))
        row = await cursor.fetchone()
        return row[0]

async def add_task(exam_type: str, task_number: int, topic: str,
                   question: str, answer: str,
                   image_path: str = None, solution_path: str = None,
                   question_type: str = "text", answer_type: str = "number",
                   difficulty: int = 1, set_id: int = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO tasks (exam_type, task_number, topic, question, answer,
                               image_path, solution_path, question_type, answer_type, difficulty, set_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exam_type, task_number, topic, question, answer,
              image_path, solution_path, question_type, answer_type, difficulty, set_id))
        await db.commit()
        return cursor.lastrowid

# ═══════════════════════════════════════════════
# ЗАДАНИЯ 1-5 — НАБОРЫ ПО 5 ШТУК
# ═══════════════════════════════════════════════

async def get_random_set(topic: str) -> list[dict]:
    """
    Вернуть случайный набор из 5 заданий по теме (задания 1-5).
    Набор — это 5 заданий с одинаковым set_id.
    Если наборов нет — вернуть 5 случайных заданий по теме.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Получаем все доступные set_id по теме
        cursor = await db.execute("""
            SELECT DISTINCT set_id FROM tasks
            WHERE exam_type = 'oge' AND task_number BETWEEN 1 AND 5
              AND topic = ? AND set_id IS NOT NULL
        """, (topic,))
        set_ids = [r[0] for r in await cursor.fetchall()]

        if set_ids:
            chosen_set = random.choice(set_ids)
            cursor = await db.execute("""
                SELECT * FROM tasks
                WHERE exam_type = 'oge' AND task_number BETWEEN 1 AND 5
                  AND topic = ? AND set_id = ?
                ORDER BY task_number
            """, (topic, chosen_set))
        else:
            # Фолбэк: просто 5 рандомных заданий
            cursor = await db.execute("""
                SELECT * FROM tasks
                WHERE exam_type = 'oge' AND task_number BETWEEN 1 AND 5
                  AND topic = ?
                ORDER BY RANDOM() LIMIT 5
            """, (topic,))

        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

# ═══════════════════════════════════════════════
# ПОПЫТКИ И ПРОГРЕСС
# ═══════════════════════════════════════════════

async def record_attempt(vk_id: int, task_id: int, user_answer: str,
                          is_correct: bool, exam_type: str,
                          task_number: int, topic: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM users WHERE vk_id = ?", (vk_id,))
        user = await cursor.fetchone()
        if not user:
            return
        user_id = user["id"]

        await db.execute("""
            INSERT INTO attempts (user_id, task_id, user_answer, is_correct)
            VALUES (?, ?, ?, ?)
        """, (user_id, task_id, user_answer, 1 if is_correct else 0))

        await db.execute("""
            INSERT INTO progress (user_id, exam_type, task_number, topic, total, correct, last_attempt)
            VALUES (?, ?, ?, ?, 1, ?, datetime('now'))
            ON CONFLICT(user_id, exam_type, task_number, topic) DO UPDATE SET
                total        = total + 1,
                correct      = correct + ?,
                last_attempt = datetime('now')
        """, (user_id, exam_type, task_number, topic,
              1 if is_correct else 0, 1 if is_correct else 0))

        await db.commit()

# ═══════════════════════════════════════════════
# СТАТИСТИКА
# ═══════════════════════════════════════════════

async def get_user_stats(vk_id: int, exam_type: str = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM users WHERE vk_id = ?", (vk_id,))
        user = await cursor.fetchone()
        if not user:
            return []
        if exam_type:
            cursor = await db.execute("""
                SELECT exam_type, task_number, topic, total, correct,
                       ROUND(correct * 100.0 / total, 1) as accuracy
                FROM progress WHERE user_id = ? AND exam_type = ?
                ORDER BY task_number, topic
            """, (user["id"], exam_type))
        else:
            cursor = await db.execute("""
                SELECT exam_type, task_number, topic, total, correct,
                       ROUND(correct * 100.0 / total, 1) as accuracy
                FROM progress WHERE user_id = ?
                ORDER BY exam_type, task_number, topic
            """, (user["id"],))
        return [dict(r) for r in await cursor.fetchall()]

async def get_summary_stats(vk_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM users WHERE vk_id = ?", (vk_id,))
        user = await cursor.fetchone()
        if not user:
            return {}
        cursor = await db.execute("""
            SELECT SUM(total) as total, SUM(correct) as correct,
                   COUNT(DISTINCT exam_type || task_number || topic) as topics_tried
            FROM progress WHERE user_id = ?
        """, (user["id"],))
        row = await cursor.fetchone()
        data = dict(row)
        data["accuracy"] = round(data["correct"] * 100.0 / data["total"], 1) if data["total"] else 0
        return data

async def get_weak_topics(vk_id: int, exam_type: str, limit: int = 3) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM users WHERE vk_id = ?", (vk_id,))
        user = await cursor.fetchone()
        if not user:
            return []
        cursor = await db.execute("""
            SELECT task_number, topic, ROUND(correct * 100.0 / total, 1) as accuracy
            FROM progress WHERE user_id = ? AND exam_type = ? AND total >= 3
            ORDER BY accuracy ASC LIMIT ?
        """, (user["id"], exam_type, limit))
        return [dict(r) for r in await cursor.fetchall()]

# ═══════════════════════════════════════════════
# ИМПОРТ ИЗ tasks.json
# ═══════════════════════════════════════════════

TASKS_JSON_MAP = {
    "task6_ordinary_fractions":      ("oge", 6,  "ordinary_fractions"),
    "task6_decimal_fractions":       ("oge", 6,  "decimal_fractions"),
    "task7":                         ("oge", 7,  "general"),
    "task8_degrees":                 ("oge", 8,  "degrees"),
    "task8_arithmetic_square_root":  ("oge", 8,  "arithmetic_square_root"),
    "task9_linear_equations":        ("oge", 9,  "linear_equations"),
    "task9_quadratic_equations":     ("oge", 9,  "quadratic_equations"),
    "task10_probability_problems":   ("oge", 10, "probability"),
    "task13_linear_inequalities":    ("oge", 13, "linear_inequalities"),
    "task13_quadratic_inequalities": ("oge", 13, "quadratic_inequalities"),
    "task13_systems_linear_ineq":    ("oge", 13, "systems_linear_inequalities"),
}

async def import_from_json(json_path: str = "app/tasks.json"):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM tasks")
        count = (await cursor.fetchone())[0]
        if count > 0:
            print(f"ℹ️  В БД уже {count} заданий, импорт пропущен")
            return

    with open(json_path, "r", encoding="utf-8") as f:
        all_tasks = json.load(f)

    imported = 0
    for json_key, (exam_type, task_number, topic) in TASKS_JSON_MAP.items():
        for task in all_tasks.get(json_key, []):
            qt = "image" if task.get("image") and not task.get("question") else \
                 "text_and_image" if task.get("image") and task.get("question") else "text"
            await add_task(
                exam_type=exam_type, task_number=task_number, topic=topic,
                question=task.get("question", ""), answer=str(task.get("answer", "")),
                image_path=task.get("image"), question_type=qt,
            )
            imported += 1
    print(f"✅ Импортировано {imported} заданий из {json_path}")

# ═══════════════════════════════════════════════
# ВАРИАНТ ОГЭ — случайный набор заданий 1-19
# ═══════════════════════════════════════════════

# Структура варианта: номер задания -> тема (None = любая)
# Задания 1-5 идут набором по одной теме (5 заданий)
# Задания 6-25 — по одному заданию каждое
VARIANT_PART1_STRUCTURE = [
    (6,  None),
    (7,  "general"),
    (8,  None),
    (9,  None),
    (10, "probability"),
    (11, None),
    (12, "general"),
    (13, None),
    (14, None),
    (15, "triangles"),
    (16, "circles"),
    (17, None),
    (18, "grid"),
    (19, "general"),
]

VARIANT_PART2_STRUCTURE = [
    (20, None),
    (21, None),
    (22, None),
    (23, None),
    (24, None),
    (25, None),
]

async def get_random_variant() -> list[dict]:
    """
    Собрать полный вариант ОГЭ:
    — Задания 1-5: случайный набор из 5 заданий одной темы
    — Задания 6-25: по одному случайному заданию
    Итого до 25 заданий, каждое по 1 баллу.
    """
    import random
    variant = []

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # ── Задания 1-5: случайный набор по одной теме ──────────────
        cursor = await db.execute("""
            SELECT DISTINCT topic FROM tasks
            WHERE exam_type = 'oge' AND task_number BETWEEN 1 AND 5
              AND set_id IS NOT NULL
        """)
        set_topics = [r[0] for r in await cursor.fetchall()]

        if set_topics:
            chosen_topic = random.choice(set_topics)
            # Берём случайный set_id по этой теме
            cursor = await db.execute("""
                SELECT DISTINCT set_id FROM tasks
                WHERE exam_type = 'oge' AND task_number BETWEEN 1 AND 5
                  AND topic = ? AND set_id IS NOT NULL
            """, (chosen_topic,))
            set_ids = [r[0] for r in await cursor.fetchall()]
            if set_ids:
                chosen_set = random.choice(set_ids)
                cursor = await db.execute("""
                    SELECT * FROM tasks
                    WHERE exam_type = 'oge' AND task_number BETWEEN 1 AND 5
                      AND topic = ? AND set_id = ?
                    ORDER BY task_number
                """, (chosen_topic, chosen_set))
                for row in await cursor.fetchall():
                    variant.append(dict(row))

        # ── Задания 6-25: по одному заданию ─────────────────────────
        for task_number, topic in VARIANT_PART1_STRUCTURE + VARIANT_PART2_STRUCTURE:
            if topic is None:
                cursor = await db.execute("""
                    SELECT DISTINCT topic FROM tasks
                    WHERE exam_type = 'oge' AND task_number = ?
                """, (task_number,))
                topics = [r[0] for r in await cursor.fetchall()]
                if not topics:
                    print(f"⚠️  Вариант: нет заданий №{task_number} в БД — пропущено")
                    continue
                topic = random.choice(topics)
            else:
                # Проверяем, есть ли задания с указанной темой
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM tasks
                    WHERE exam_type = 'oge' AND task_number = ? AND topic = ?
                """, (task_number, topic))
                count = (await cursor.fetchone())[0]
                if count == 0:
                    # Фолбэк: берём любую доступную тему
                    cursor = await db.execute("""
                        SELECT DISTINCT topic FROM tasks
                        WHERE exam_type = 'oge' AND task_number = ?
                    """, (task_number,))
                    fallback = [r[0] for r in await cursor.fetchall()]
                    if not fallback:
                        print(f"⚠️  Вариант: нет заданий №{task_number} в БД — пропущено")
                        continue
                    topic = random.choice(fallback)

            cursor = await db.execute("""
                SELECT * FROM tasks
                WHERE exam_type = 'oge' AND task_number = ? AND topic = ?
                ORDER BY RANDOM() LIMIT 1
            """, (task_number, topic))
            row = await cursor.fetchone()
            if row:
                variant.append(dict(row))

    return variant


async def get_random_exam_variant(exam_type: str) -> list[dict]:
    """
    Собрать случайный вариант для любого типа экзамена.

    ОГЭ:
      1–5 стараемся брать одним связанным набором set_id,
      6–25 берём по одному заданию каждого номера.

    ЕГЭ база:
      1–21 по одному заданию каждого номера.

    ЕГЭ профиль:
      1–19 по одному заданию каждого номера.
    """
    if exam_type == "oge":
        return await get_random_variant()

    ranges = {
        "ege_base": range(1, 22),
        "ege_profile": range(1, 20),
    }

    expected = ranges.get(exam_type)
    if expected is None:
        return []

    variant: list[dict] = []

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        for task_number in expected:
            cursor = await db.execute(
                """
                SELECT * FROM tasks
                WHERE exam_type = ? AND task_number = ?
                ORDER BY RANDOM()
                LIMIT 1
                """,
                (exam_type, task_number),
            )
            row = await cursor.fetchone()
            if row:
                variant.append(dict(row))

    return variant


async def cache_image_path(old_path: str, new_path: str):
    """Обновляет image_path в БД после первой успешной загрузки в VK."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET image_path = ? WHERE image_path = ?",
            (new_path, old_path)
        )
        await db.commit()