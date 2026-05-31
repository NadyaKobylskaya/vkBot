"""
Скрипт для ручного добавления размеченных решений в датасет.

Использование:
    python -m app.neural.add_to_dataset

Хранение:
    app/bot_database.db    — таблицы task_conditions и dataset_labels
    data/solutions/images/ — фотографии решений
"""

import os
import sys
import shutil
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Пути ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent.parent
DB_PATH    = ROOT / "app" / "bot_database.db"
IMAGES_DIR = ROOT / "data" / "solutions" / "images"
INBOX_DIR  = ROOT / "data" / "inbox"

# ── Типы решений по заданию ───────────────────────────────────────────────────
SOLUTION_TYPES = {
    20: ["уравнение", "неравенство", "система уравнений"],
    21: ["текстовая_задача"],
    22: ["функция_и_график"],
    23: ["геометрия_вычисление"],       # 23 = вычислительная задача
    24: ["геометрия_доказательство"],   # 24 = доказательство
    25: ["геометрия_комплексная"],
}

# ── Критерии оценивания ───────────────────────────────────────────────────────
TASK_CRITERIA = {
    20: {
        "name":     "Алгебраические выражения, уравнения и неравенства",
        "criteria": [
            "К1 (0/1): Верно составлено уравнение/неравенство, выполнено преобразование",
            "К2 (0/1): Получен верный ответ, все шаги обоснованы",
        ],
        "examples": {
            (0, 0): "Неверный подход, грубые ошибки",
            (1, 0): "Верное преобразование, но ошибка в вычислениях",
            (1, 1): "Полное верное решение",
        },
    },
    21: {
        "name":     "Текстовая задача",
        "criteria": [
            "К1 (0/1): Верно составлена математическая модель задачи",
            "К2 (0/1): Верно выполнены вычисления, дан ответ",
        ],
        "examples": {
            (0, 0): "Модель не составлена или неверна",
            (1, 0): "Модель верна, но вычисления содержат ошибку",
            (1, 1): "Полное верное решение с ответом",
        },
    },
    22: {
        "name":     "Функции и графики",
        "criteria": [
            "К1 (0/1): Верно исследована функция / построен график",
            "К2 (0/1): Верно выполнено задание по графику / найден ответ",
        ],
        "examples": {
            (0, 0): "График неверный, задание не выполнено",
            (1, 0): "График верный, но ответ на вопрос неверен",
            (1, 1): "Полное верное решение",
        },
    },
    23: {
        "name":     "Геометрия — вычисление",   # ← исправлено
        "criteria": [
            "К1 (0/1): Верно выполнены построения, применена нужная формула/теорема",
            "К2 (0/1): Верно найдена искомая величина",
        ],
        "examples": {
            (0, 0): "Решение отсутствует или формула применена неверно",
            (1, 0): "Подход верный, но вычислительная ошибка в ответе",
            (1, 1): "Полное верное решение с ответом",
        },
    },
    24: {
        "name":     "Геометрия — доказательство",   # ← исправлено
        "criteria": [
            "К1 (0/1): Верно выполнены построения, введены обозначения",
            "К2 (0/1): Приведено полное обоснованное доказательство",
        ],
        "examples": {
            (0, 0): "Доказательство отсутствует или полностью неверно",
            (1, 0): "Построения верны, доказательство неполное или без обоснования",
            (1, 1): "Полное верное доказательство",
        },
    },
    25: {
        "name":     "Геометрия — комплексная задача",
        "criteria": [
            "К1 (0/1): Верно выполнена первая часть (доказательство)",
            "К2 (0/1): Верно выполнена вторая часть (вычисление)",
        ],
        "examples": {
            (0, 0): "Решение отсутствует",
            (1, 0): "Только первая часть решена верно",
            (1, 1): "Обе части решены верно",
        },
    },
}


# ── База данных ───────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_conditions (
                task_number  INTEGER PRIMARY KEY,
                condition    TEXT NOT NULL,
                topic        TEXT,
                source       TEXT
            );

            CREATE TABLE IF NOT EXISTS dataset_labels (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                image_file     TEXT    NOT NULL UNIQUE,
                task_number    INTEGER NOT NULL
                               REFERENCES task_conditions(task_number),
                solution_type  TEXT,
                K1             INTEGER NOT NULL CHECK(K1 IN (0, 1)),
                K2             INTEGER NOT NULL CHECK(K2 IN (0, 1)),
                comment        TEXT,
                added_at       TEXT    NOT NULL
            );
        """)

        # ── Миграция: добавляем колонки если их нет ──────────────────
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(dataset_labels)")
        }
        if "task_condition" not in existing:
            conn.execute("ALTER TABLE dataset_labels ADD COLUMN task_condition TEXT")
            print("🔧 Миграция: добавлена колонка task_condition")
        if "added_at" not in existing:
            conn.execute("ALTER TABLE dataset_labels ADD COLUMN added_at TEXT")
            print("🔧 Миграция: добавлена колонка added_at")

    print(f"✅ БД готова: {DB_PATH}")


def save_label(record: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO dataset_labels
                (image_file, task_number, solution_type, K1, K2, comment, added_at)
            VALUES
                (:image_file, :task_number, :solution_type, :K1, :K2, :comment, :added_at)
        """, record)


def save_condition(task_number: int, condition: str, source: str = ""):
    topic = TASK_CRITERIA.get(task_number, {}).get("name", "")
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO task_conditions (task_number, condition, topic, source)
            VALUES (?, ?, ?, ?)
        """, (task_number, condition, topic, source))


def load_existing_images() -> set:
    with get_connection() as conn:
        rows = conn.execute("SELECT image_file FROM dataset_labels").fetchall()
    return {row["image_file"] for row in rows}


def get_stats() -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT task_number, K1, K2 FROM dataset_labels"
        ).fetchall()
    stats: dict = {}
    for row in rows:
        tn    = row["task_number"]
        score = row["K1"] + row["K2"]
        stats.setdefault(tn, {"total": 0, "scores": {0: 0, 1: 0, 2: 0}})
        stats[tn]["total"] += 1
        stats[tn]["scores"][score] = stats[tn]["scores"].get(score, 0) + 1
    return stats


def print_stats():
    stats = get_stats()
    if not stats:
        print("📊 Датасет пока пуст.")
        return
    total_all = sum(s["total"] for s in stats.values())
    print(f"\n📊 Датасет в БД (всего: {total_all} примеров):")
    print("─" * 60)
    for task_num in sorted(stats):
        s    = stats[task_num]
        name = TASK_CRITERIA.get(task_num, {}).get("name", "")
        print(f"  Задание {task_num} ({name}): {s['total']} примеров")
        for score, count in sorted(s["scores"].items()):
            if count > 0:
                bar = "█" * count + "░" * max(0, 10 - count)
                print(f"    {score} балл(а): {bar} {count}")
    print("─" * 60)


def export_to_csv(output_path: str = "dataset_export.csv"):
    import csv
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                l.id, l.image_file, l.task_number,
                c.condition AS task_condition,
                c.source,
                l.solution_type, l.K1, l.K2,
                (l.K1 + l.K2) AS total_score,
                l.comment, l.added_at
            FROM dataset_labels l
            LEFT JOIN task_conditions c USING(task_number)
            ORDER BY l.task_number, l.added_at
        """).fetchall()
    if not rows:
        print("⚠️  Датасет пуст.")
        return
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])
    print(f"📤 Экспортировано {len(rows)} записей → {output_path}")


# ── Вспомогательные функции ───────────────────────────────────────────────────

def show_image(image_path: str):
    if PIL_AVAILABLE:
        try:
            Image.open(image_path).show()
            return
        except Exception:
            pass
    if sys.platform == "win32":
        os.startfile(image_path)
    elif sys.platform == "darwin":
        os.system(f"open '{image_path}'")
    else:
        os.system(f"xdg-open '{image_path}' &")


def copy_to_dataset(source_path: str, task_number: int) -> str:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ext       = Path(source_path).suffix.lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    h         = hashlib.md5(source_path.encode()).hexdigest()[:6]
    filename  = f"task{task_number}_{timestamp}_{h}{ext}"
    shutil.copy2(source_path, IMAGES_DIR / filename)
    return filename


# ── Интерактивный ввод ────────────────────────────────────────────────────────

def ask_task_number() -> int:
    available = sorted(TASK_CRITERIA.keys())
    print(f"\nДоступные задания: {available}")
    while True:
        raw = input("Номер задания (20–25): ").strip()
        try:
            n = int(raw)
            if n in TASK_CRITERIA:
                return n
            print(f"❌ Допустимые номера: {available}")
        except ValueError:
            print("❌ Введи число.")


def ask_task_condition() -> tuple[str, str]:
    print("\n" + "─" * 60)
    print("📝 Текст условия задания (из варианта КИМ).")
    print("   Пример: 'Решите уравнение 2x²-5x+3=0'")
    print("   Завершить ввод — пустая строка.")
    lines = []
    while True:
        line = input("   > ").strip()
        if line == "" and lines:
            break
        if line:
            lines.append(line)
    condition = " ".join(lines) or "не указано"
    source = input("Источник (напр. 'ФИПИ 2024 вариант 7', или Enter): ").strip()
    return condition, source


def ask_solution_type(task_number: int) -> str:
    options = SOLUTION_TYPES.get(task_number, ["другое"])
    if len(options) == 1:
        print(f"\n🏷️  Тип решения: {options[0]} (задан автоматически)")
        return options[0]
    print("\n🏷️  Выбери тип решения:")
    for i, opt in enumerate(options, start=1):
        print(f"   {i} — {opt}")
    while True:
        raw = input(f"Тип (1–{len(options)}): ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
            print(f"❌ Введи число от 1 до {len(options)}")
        except ValueError:
            print("❌ Введи число.")


def ask_criteria_scores(task_number: int) -> tuple[int, int]:
    info = TASK_CRITERIA[task_number]
    print(f"\n{'─' * 60}")
    print(f"📋 Критерии — задание {task_number}: {info['name']}")
    print("─" * 60)
    print("\nПримеры:")
    for combo, desc in info["examples"].items():
        print(f"  К1={combo[0]}, К2={combo[1]} → {desc}")
    print("─" * 60)
    scores = []
    for i, criterion_desc in enumerate(info["criteria"], start=1):
        print(f"\n{criterion_desc}")
        while True:
            raw = input(f"  К{i} = (0 или 1): ").strip()
            if raw in ("0", "1"):
                scores.append(int(raw))
                break
            print("  ❌ Введи 0 или 1.")
    return scores[0], scores[1]


def ask_comment() -> str:
    """Произвольный комментарий эксперта — описание ошибки или подтверждение верного решения."""
    print("\n💬 Комментарий эксперта (произвольная фраза):")
    print("   Примеры: 'не раскрыты скобки в левой части'")
    print("            'неверно определено направление неравенства'")
    print("            'верное решение'")
    comment = input("   > ").strip()
    return comment or "без комментария"


# ── Обработка одного файла ────────────────────────────────────────────────────

def process_single_file(image_path: str, existing: set) -> bool:
    print(f"\n{'═' * 60}")
    print(f"📄 Файл: {Path(image_path).name}")

    if Path(image_path).name in existing:
        print("⚠️  Уже в датасете — пропускаем.")
        return False

    print("🖼️  Открываю изображение...")
    show_image(image_path)

    task_number            = ask_task_number()
    task_condition, source = ask_task_condition()
    solution_type          = ask_solution_type(task_number)
    k1, k2                 = ask_criteria_scores(task_number)

    print(f"\n{'─' * 60}")
    print(f"✅ Итог: задание {task_number} | {solution_type}")
    print(f"   {'✅' if k1 else '❌'} К1 = {k1}")
    print(f"   {'✅' if k2 else '❌'} К2 = {k2}")
    print(f"   Сумма: {k1 + k2}/2 балла")
    short = task_condition[:60] + ("..." if len(task_condition) > 60 else "")
    print(f"   Условие: {short}")

    confirm = input("\nСохранить? (Enter = да, n = нет): ").strip().lower()
    if confirm == "n":
        print("⏭️  Пропускаем.")
        return False

    comment       = ask_comment()
    dest_filename = copy_to_dataset(image_path, task_number)

    save_condition(task_number, task_condition, source)
    save_label({
        "image_file":    dest_filename,
        "task_number":   task_number,
        "solution_type": solution_type,
        "K1":            k1,
        "K2":            k2,
        "comment":       comment,
        "added_at":      datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    existing.add(dest_filename)
    print(f"💾 Сохранено в БД → {dest_filename}")
    return True


# ── Режимы запуска ────────────────────────────────────────────────────────────

def run_interactive_mode():
    existing = load_existing_images()
    added    = 0
    print(f"\n{'═' * 60}")
    print("📂 Режим: ручной ввод пути к файлу")
    print("═" * 60)
    while True:
        print_stats()
        raw = input("\nПуть к файлу (или q): ").strip().strip('"').strip("'")
        if raw.lower() in ("q", "quit", "exit", ""):
            break
        if not Path(raw).exists():
            print(f"❌ Файл не найден: {raw}")
            continue
        if process_single_file(raw, existing):
            added += 1
    print(f"\n✅ Сессия завершена. Добавлено: {added} записей.")
    print_stats()


def run_inbox_mode():
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    done_dir = INBOX_DIR / "done"
    done_dir.mkdir(exist_ok=True)

    extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    files = sorted(f for f in INBOX_DIR.iterdir() if f.suffix.lower() in extensions)

    if not files:
        print(f"📭 Папка {INBOX_DIR} пуста.")
        return

    existing       = load_existing_images()
    added, skipped = 0, 0

    print(f"\n📦 Найдено {len(files)} файлов в {INBOX_DIR}/")
    print_stats()

    for i, filepath in enumerate(files, start=1):
        print(f"\n[{i}/{len(files)}]")
        result = process_single_file(str(filepath), existing)
        shutil.move(str(filepath), str(done_dir / filepath.name))
        if result:
            added += 1
        else:
            skipped += 1

    print(f"\n{'═' * 60}")
    print(f"✅ Готово! Добавлено: {added}, пропущено: {skipped}")
    print_stats()


def main():
    print("═" * 60)
    print("  📚 Добавление решений в датасет нейросети")
    print("═" * 60)

    init_db()

    print("\nВыбери режим:")
    print("  1 — Ручной ввод пути к файлу")
    print(f"  2 — Пакетная обработка из {INBOX_DIR}/")
    print("  3 — Только статистика")
    print("  4 — Экспорт в CSV (для Excel / научного руководителя)")

    choice = input("\nРежим (1/2/3/4): ").strip()

    if choice == "1":
        run_interactive_mode()
    elif choice == "2":
        run_inbox_mode()
    elif choice == "3":
        print_stats()
    elif choice == "4":
        export_path = input("Имя файла (Enter = dataset_export.csv): ").strip()
        export_to_csv(export_path or "dataset_export.csv")
    else:
        print("❌ Неверный выбор.")


if __name__ == "__main__":
    main()