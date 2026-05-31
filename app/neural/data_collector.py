"""
Модуль сбора датасета через бот.

Схема сбора:
  1. Ученик отправляет фото решения
  2. Бот сохраняет изображение
  3. Учитель/эксперт через специальный интерфейс выставляет оценку
  4. Пара (изображение, оценка) попадает в датасет
"""

import csv
import os
import hashlib
import asyncio
import aiohttp
import aiosqlite
from pathlib import Path
from datetime import datetime


DATA_DIR   = Path("data/solutions")
IMAGES_DIR = DATA_DIR / "images"
LABELS_CSV = DATA_DIR / "labels.csv"

# ── SQL для хранения неразмеченных решений ──────────────────────────────
CREATE_PENDING_TABLE = """
CREATE TABLE IF NOT EXISTS pending_solutions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vk_user_id   INTEGER NOT NULL,
    task_number  INTEGER NOT NULL,
    task_text    TEXT,
    image_path   TEXT    NOT NULL,
    image_url    TEXT,
    submitted_at TEXT    DEFAULT (datetime('now')),
    is_labeled   INTEGER DEFAULT 0,
    K1           INTEGER DEFAULT NULL,
    K2           INTEGER DEFAULT NULL,
    K3           INTEGER DEFAULT NULL,
    annotator    TEXT    DEFAULT NULL,
    labeled_at   TEXT    DEFAULT NULL
)
"""


async def save_solution_image(
    image_url: str,
    user_id: int,
    task_number: int,
) -> str:
    """
    Скачивает изображение из ВКонтакте и сохраняет локально.
    Возвращает путь к сохранённому файлу.
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Уникальное имя файла на основе hash
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_hash  = hashlib.md5(image_url.encode()).hexdigest()[:8]
    filename  = f"sol_{user_id}_{task_number}_{timestamp}_{url_hash}.jpg"
    filepath  = IMAGES_DIR / filename

    import ssl
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url, ssl=ssl_ctx) as resp:
            content = await resp.read()

    filepath.write_bytes(content)
    return str(filepath)


async def register_solution(
    db_path: str,
    vk_user_id: int,
    task_number: int,
    task_text: str,
    image_url: str,
) -> int:
    """
    Сохраняет решение в БД как неразмеченное.
    Возвращает ID записи.
    """
    image_path = await save_solution_image(image_url, vk_user_id, task_number)

    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_PENDING_TABLE)
        cursor = await db.execute(
            """INSERT INTO pending_solutions
               (vk_user_id, task_number, task_text, image_path, image_url)
               VALUES (?, ?, ?, ?, ?)""",
            (vk_user_id, task_number, task_text, image_path, image_url)
        )
        await db.commit()
        return cursor.lastrowid


async def label_solution(
    db_path: str,
    solution_id: int,
    scores: dict,           # {"K1": 1, "K2": 0}
    annotator: str = "teacher",
) -> None:
    """
    Добавляет разметку к решению и экспортирует в CSV.
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """UPDATE pending_solutions
               SET K1=?, K2=?, K3=?, annotator=?,
                   is_labeled=1, labeled_at=datetime('now')
               WHERE id=?""",
            (
                scores.get("K1", 0),
                scores.get("K2", 0),
                scores.get("K3", None),
                annotator,
                solution_id,
            )
        )
        await db.commit()

    # Экспорт в CSV для обучения
    await export_to_csv(db_path)


async def export_to_csv(db_path: str) -> int:
    """
    Экспортирует все размеченные решения в labels.csv.
    Возвращает количество экспортированных записей.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_number,
                      image_path,
                      K1, K2, K3, annotator
               FROM pending_solutions
               WHERE is_labeled = 1
               ORDER BY id"""
        )
        rows = await cursor.fetchall()

    with open(LABELS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["task_number", "image_file", "K1", "K2", "K3", "annotator"]
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "task_number": row["task_number"],
                "image_file":  Path(row["image_path"]).name,
                "K1":          row["K1"] or 0,
                "K2":          row["K2"] or 0,
                "K3":          row["K3"] or 0,
                "annotator":   row["annotator"] or "",
            })

    print(f"📁 Экспортировано {len(rows)} размеченных решений → {LABELS_CSV}")
    return len(rows)


async def get_unlabeled_count(db_path: str) -> int:
    """Возвращает количество решений, ожидающих разметки."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM pending_solutions WHERE is_labeled=0"
        )
        (count,) = await cursor.fetchone()
        return count