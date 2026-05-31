"""
Импорт датасета из Excel в SQLite.

Использование:
    python import_from_excel.py dataset.xlsx

Структура Excel (лист «labels»):
    image_file, task_number, task_condition, solution_type, K1, K2, comment
"""

import sys
import sqlite3
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("❌ Установи зависимости: pip install pandas openpyxl")
    sys.exit(1)

ROOT    = Path(__file__).resolve().parent
DB_PATH = ROOT / "app" / "bot_database.db"

TOPICS = {
    20: "Алгебраические выражения, уравнения и неравенства",
    21: "Текстовая задача",
    22: "Функции и графики",
    23: "Геометрия — вычисление",
    24: "Геометрия — доказательство",
    25: "Геометрия — комплексная задача",
}


def init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dataset_labels (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            image_file     TEXT    NOT NULL UNIQUE,
            task_number    INTEGER NOT NULL,
            task_condition TEXT,
            solution_type  TEXT,
            K1             INTEGER NOT NULL CHECK(K1 IN (0, 1)),
            K2             INTEGER NOT NULL CHECK(K2 IN (0, 1)),
            comment        TEXT
        );
    """)


def import_labels(conn: sqlite3.Connection, df: pd.DataFrame) -> tuple[int, int]:
    added   = 0
    skipped = 0
    errors  = []

    for i, row in df.iterrows():
        image_file = str(row.get("image_file", "")).strip()
        if not image_file or image_file == "nan":
            continue

        try:
            task_number    = int(float(str(row["task_number"])))
            task_condition = str(row.get("task_condition", "")).strip()
            solution_type  = str(row.get("solution_type",  "")).strip()
            k1             = int(float(str(row["K1"])))
            k2             = int(float(str(row["K2"])))
            comment        = str(row.get("comment", "")).strip()

            if task_condition == "nan": task_condition = ""
            if solution_type  == "nan": solution_type  = ""
            if comment        == "nan": comment        = "без комментария"

            if k1 not in (0, 1) or k2 not in (0, 1):
                errors.append(f"  Строка {i + 4}: K1={k1}, K2={k2} — должно быть 0 или 1")
                continue

            cursor = conn.execute("""
                INSERT OR IGNORE INTO dataset_labels
                    (image_file, task_number, task_condition, solution_type, K1, K2, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (image_file, task_number, task_condition, solution_type, k1, k2, comment))

            if cursor.rowcount:
                added += 1
            else:
                skipped += 1

        except Exception as e:
            errors.append(f"  Строка {i + 4}: {e}")

    conn.commit()

    if errors:
        print(f"\n⚠️  Ошибки ({len(errors)} строк):")
        for err in errors:
            print(err)

    return added, skipped


def print_stats(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT task_number, K1, K2 FROM dataset_labels"
    ).fetchall()

    if not rows:
        print("📊 Датасет пуст.")
        return

    stats: dict = {}
    for tn, k1, k2 in rows:
        score = k1 + k2
        stats.setdefault(tn, {"total": 0, "scores": {0: 0, 1: 0, 2: 0}})
        stats[tn]["total"] += 1
        stats[tn]["scores"][score] = stats[tn]["scores"].get(score, 0) + 1

    total_all = sum(s["total"] for s in stats.values())
    print(f"\n📊 Итого в БД: {total_all} примеров")
    print("─" * 55)
    for tn in sorted(stats):
        s = stats[tn]
        print(f"  Задание {tn} ({TOPICS.get(tn, '')}): {s['total']} примеров")
        for score, count in sorted(s["scores"].items()):
            if count > 0:
                bar = "█" * count + "░" * max(0, 10 - count)
                print(f"    {score} балл(а): {bar} {count}")
    print("─" * 55)


def main():
    if len(sys.argv) < 2:
        print("Использование: python import_from_excel.py dataset.xlsx")
        sys.exit(1)

    xlsx_path = Path(sys.argv[1])
    if not xlsx_path.exists():
        print(f"❌ Файл не найден: {xlsx_path}")
        sys.exit(1)

    print(f"📂 Читаю: {xlsx_path}")
    print(f"🗄️  БД:   {DB_PATH}")
    print("─" * 55)

    try:
        df = pd.read_excel(xlsx_path, sheet_name="labels", skiprows=1, dtype=str)
    except Exception as e:
        print(f"❌ Ошибка чтения Excel: {e}")
        sys.exit(1)

    # Первая строка — строка подсказок, пропускаем
    df = df.iloc[1:].reset_index(drop=True)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    added, skipped = import_labels(conn, df)
    print(f"✅ Добавлено: {added}, пропущено дубликатов: {skipped}")

    print_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
