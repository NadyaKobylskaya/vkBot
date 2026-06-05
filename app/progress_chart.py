"""
Модуль построения графика прогресса пользователя.
Подключается в handlers.py.
"""

import os
import aiosqlite
import asyncio
import matplotlib
matplotlib.use("Agg")  # без GUI — обязательно до import pyplot
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from vkbottle.tools import PhotoMessageUploader

DB_PATH    = "app/bot_database.db"
CHARTS_DIR = Path("data/progress_charts")

TOPIC_NAMES_RU = {
    # ── ОГЭ задания 1–5 (наборы) ──────────────────────────────────────
    "kvartira":                    "Квартира",
    "uchastok":                    "Участок",
    "listy":                       "Листы",
    "pech":                        "Печь",
    "plan":                        "План",
    "shiny":                       "Шины",
    "tarify":                      "Тарифы",
    # ── ОГЭ задания 6–19 ──────────────────────────────────────────────
    "ordinary_fractions":          "Обыкн. дроби",
    "decimal_fractions":           "Дес. дроби",
    "general":                     "Общее",
    "numbers_coordinate_line":     "Коорд. прямая",
    "degrees":                     "Степени",
    "arithmetic_square_root":      "Корни",
    "linear_equations":            "Лин. уравн.",
    "quadratic_equations":         "Кв. уравн.",
    "n09_linear":                  "Лин. уравн.",
    "n09_quadratic":               "Кв. уравн.",
    "probability":                 "Вероятность",
    "linear_function":             "Лин. функция",
    "quadratic_function":          "Парабола",
    "hyperbola":                   "Гипербола",
    "mixed_graphs":                "Смеш. графики",
    "linear_inequalities":         "Лин. нерав.",
    "quadratic_inequalities":      "Кв. нерав.",
    "systems_linear_inequalities": "Сист. нерав.",
    "n13_linear":                  "Лин. нерав.",
    "n13_quadratic":               "Кв. нерав.",
    "n13_systems":                 "Системы нерав.",
    "arithmetic_progression":      "Ариф. прогр.",
    "geometric_progression":       "Геом. прогр.",
    "triangles":                   "Треугольники",
    "circles":                     "Окружности",
    "parallelogram":               "Параллелогр.",
    "trapezoid":                   "Трапеция",
    "rectangle":                   "Прямоугольник",
    "rhombus":                     "Ромб",
    "square":                      "Квадрат",
    "grid":                        "Клетч. плоск.",
    # ── ОГЭ задания 20–25 ─────────────────────────────────────────────
    "equations":                   "Уравнения",
    "systems":                     "Системы",
    "inequalities":                "Неравенства",
    "n21_motion_line":             "Движение (прям.)",
    "n21_motion_water":            "Движение (вода)",
    "n21_percent":                 "Проценты",
    "n21_work":                    "Работа",
    "functions":                   "Функции",
    "n23_parallelogram":           "Параллелогр.",
    "n23_rhombus":                 "Ромб",
    "n23_triangle":                "Треугольник",
    "n23_circle":                  "Окружность",
    "proof_parallelogram":         "Доказат. (парал.)",
    "proof_quadrilateral":         "Доказат. (четыр.)",
    "proof_area":                  "Доказат. (площ.)",
    "proof_similarity":            "Подобие",
    "proof_angles":                "Углы",
    "proof_circle":                "Окружность",
    "proof_triangle":              "Треугольник",
    "n25_trapezoid":               "Трапеция",
    "n25_parallelogram":           "Параллелогр.",
    "n25_triangle":                "Треугольник",
    "n25_circle":                  "Окружность",
    # ── ЕГЭ профиль — часть 1 (p1–p12) ───────────────────────────────
    "ege_p01_planim":              "Планиметрия",
    "ege_p01_planimetry":          "Планиметрия",
    "ege_p02_vectors":             "Векторы",
    "ege_p03_stereo":              "Стереометрия",
    "ege_p03_stereometry":         "Стереометрия",
    "ege_p04_probability":         "Вероятность",
    "ege_p05_probability_complex": "Вероятность (сл.)",
    "ege_p06_stereometry":         "Стереометрия",
    "ege_p07_expr":                "Значение выражения",
    "ege_p08_equations":           "Уравнения",
    "ege_p09_applied":             "Прикл. задача",
    "ege_p09_word_problems":       "Текст. задача",
    "ege_p10_text_problems":       "Текст. задача",
    "ege_p10_word":                "Текст. задача",
    "ege_p11_func":                "Функции",
    "ege_p11_functions":           "Функции",
    "ege_p12_research":            "Исслед. функций",
    "ege_p12_derivative":          "Производная",
    # ── ЕГЭ профиль — часть 2 (p13–p19) ──────────────────────────────
    "ege_p13_eq":                  "Уравнения (разв.)",
    "ege_p13_equations":           "Уравнения (разв.)",
    "ege_p14_stereo2":             "Стереометрия",
    "ege_p14_stereometry":         "Стереометрия",
    "ege_p15_ineq":                "Неравенства",
    "ege_p15_inequalities":        "Неравенства",
    "ege_p16_finance":             "Финансы",
    "ege_p16_planimetry":          "Планиметрия",
    "ege_p17_planim2":             "Планиметрия",
    "ege_p17_economics":           "Экономика",
    "ege_p18_param":               "Параметры",
    "ege_p18_parameters":          "Параметры",
    "ege_p19_numbers":             "Числа",
    # ── ЕГЭ база (e1–e21) ─────────────────────────────────────────────
    "ege_b01_text":                "Текст. задачи",
    "ege_b01_units":               "Единицы изм.",
    "ege_b02_units":               "Единицы изм.",
    "ege_b02_reading_graphs":      "Чтение графиков",
    "ege_b03_graphs":              "Графики",
    "ege_b03_tables_graphs":       "Таблицы/графики",
    "ege_b04_algebra":             "Алгебра",
    "ege_b04_probability":         "Вероятность",
    "ege_b05_prob":                "Вероятность",
    "ege_b05_practical_calculus":  "Прикл. задачи",
    "ege_b06_optimal":             "Оптим. выбор",
    "ege_b06_geometry":            "Планиметрия",
    "ege_b07_analysis":            "Анализ граф.",
    "ege_b07_graphs":              "Графики",
    "ege_b08_logic":               "Утверждения",
    "ege_b08_statements":          "Утверждения",
    "ege_b09_area":                "Площадь",
    "ege_b09_calculations":        "Вычисления",
    "ege_b10_planim":              "Планиметрия",
    "ege_b10_planimetry":          "Прикл. планим.",
    "ege_b11_stereo":              "Стереометрия",
    "ege_b11_stereometry":         "Стереометрия",
    "ege_b12_planim2":             "Планиметрия",
    "ege_b12_functions":           "Функции",
    "ege_b13_stereo2":             "Стереометрия",
    "ege_b13_equations":           "Уравнения",
    "ege_b14_fracs":               "Дроби",
    "ege_b14_inequalities":        "Неравенства",
    "ege_b15_percent":             "Проценты",
    "ege_b15_finance":             "Финансы",
    "ege_b16_calc":                "Вычисления",
    "ege_b16_progressions":        "Прогрессии",
    "ege_b17_eq":                  "Уравнения",
    "ege_b17_geometry":            "Геометрия",
    "ege_b18_ineq":                "Числа/нерав.",
    "ege_b18_inequalities":        "Числа/нерав.",
    "ege_b18_equation":            "Уравнения",
    "ege_b18_systems":             "Системы",
    "ege_b19_digits":              "Числа/цифры",
    "ege_b19_digits2":             "Числа/цифры",
    "ege_b20_word":                "Текст. задача",
    "ege_b20_text_problems":       "Текст. задача",
    "ege_b21_logic":               "Смекалка",
}


async def get_user_progress_stats(vk_id: int, exam_type: str = None) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM users WHERE vk_id = ?", (vk_id,))
        user = await cursor.fetchone()
        if not user:
            return None
        user_id = user["id"]

        if exam_type:
            cursor = await db.execute("""
                SELECT SUM(total) as total, SUM(correct) as correct
                FROM progress WHERE user_id = ? AND exam_type = ?
            """, (user_id, exam_type))
        else:
            cursor = await db.execute("""
                SELECT SUM(total) as total, SUM(correct) as correct
                FROM progress WHERE user_id = ?
            """, (user_id,))

        summary = await cursor.fetchone()
        if not summary or not summary["total"]:
            return None

        total   = summary["total"]
        correct = summary["correct"]

        if exam_type:
            cursor = await db.execute("""
                SELECT task_number, topic,
                       SUM(total)   as total,
                       SUM(correct) as correct,
                       ROUND(SUM(correct) * 100.0 / SUM(total), 1) as accuracy
                FROM progress
                WHERE user_id = ? AND exam_type = ?
                GROUP BY task_number, topic
                ORDER BY task_number, topic
            """, (user_id, exam_type))
        else:
            cursor = await db.execute("""
                SELECT task_number, topic,
                       SUM(total)   as total,
                       SUM(correct) as correct,
                       ROUND(SUM(correct) * 100.0 / SUM(total), 1) as accuracy
                FROM progress
                WHERE user_id = ?
                GROUP BY task_number, topic
                ORDER BY task_number, topic
            """, (user_id,))

        rows = [dict(r) for r in await cursor.fetchall()]

    return {
        "total":    total,
        "correct":  correct,
        "accuracy": round(correct * 100.0 / total, 1) if total else 0,
        "by_task":  rows,
    }

def build_progress_chart(vk_id: int, stats: dict, exam_type: str = None) -> list[str]:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.close("all")

    by_task = stats["by_task"]
    if by_task is None:
        by_task = []

    # Структура частей по экзамену
    EXAM_PARTS = {
        "oge": [
            ("Задания 1–4",   list(range(1,  5))),
            ("Задания 5–8",   list(range(5,  9))),
            ("Задания 9–17",  list(range(9,  18))),
            ("Задания 18–25", list(range(18, 26))),
        ],
        "ege_base": [
            ("Задания 1–7",   list(range(1,  8))),
            ("Задания 8–14",  list(range(8,  15))),
            ("Задания 15–19", list(range(15, 20))),
        ],
        "ege_profile": [
            ("Задания 1–6",   list(range(1,  7))),
            ("Задания 7–13",  list(range(7,  14))),
            ("Задания 14–19", list(range(14, 20))),
        ],
    }

    # Если экзамен не указан — разбиваем по 8 как раньше
    if exam_type not in EXAM_PARTS:
        from collections import defaultdict
        groups = defaultdict(list)
        for row in by_task:
            groups[row["task_number"]].append(row)
        task_numbers = sorted(groups.keys())
        parts = [
            (f"Задания {task_numbers[i]}–{task_numbers[min(i+7, len(task_numbers)-1)]}",
             task_numbers[i:i+8])
            for i in range(0, len(task_numbers), 8)
        ]
    else:
        parts = EXAM_PARTS[exam_type]

    # Индексируем реальные данные: (task_number, topic) -> accuracy
    real_data = {}
    for row in by_task:
        key = (row["task_number"], row["topic"])
        real_data[key] = (row["accuracy"], row["total"])

    # Все темы по каждому номеру задания из реальных данных
    from collections import defaultdict
    task_topics = defaultdict(set)
    for row in by_task:
        task_topics[row["task_number"]].add(row["topic"])

    import time
    timestamp = int(time.time())
    chart_paths = []
    total_parts = len(parts)

    for part_idx, (part_title, task_numbers) in enumerate(parts):
        labels, values, colors, alphas = [], [], [], []

        for num in task_numbers:
            topics = task_topics.get(num)
            if topics:
                for topic in sorted(topics):
                    topic_ru = TOPIC_NAMES_RU.get(topic, topic)
                    labels.append(f"№{num}\n{topic_ru}")
                    acc, total = real_data.get((num, topic), (0, 0))
                    values.append(acc)
                    alphas.append(1.0)
                    if total == 0:
                        colors.append("#94a3b8")   # серый — не решалось
                    elif acc < 50:
                        colors.append("#ef4444")   # красный
                    elif acc < 75:
                        colors.append("#f59e0b")   # жёлтый
                    else:
                        colors.append("#22c55e")   # зелёный
            else:
                # Задание не решалось — показываем серым
                labels.append(f"№{num}\n—")
                values.append(0)
                colors.append("#cbd5e1")
                alphas.append(0.5)

        if not labels:
            continue

        n = len(labels)
        fig, ax = plt.subplots(figsize=(max(8, n * 1.1), 6))

        # Белый фон
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")

        bars = ax.bar(range(n), values, color=colors, width=0.6,
                      edgecolor="#e2e8f0", linewidth=0.8)

        # Подписи значений над столбцами
        for bar, val, alpha in zip(bars, values, alphas):
            label_text = f"{val:.0f}%" if val > 0 else "—"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.5,
                label_text,
                ha="center", va="bottom",
                fontsize=9, color="#1e293b", fontweight="bold"
            )

        # Линия цели
        ax.axhline(y=75, color="#6366f1", linewidth=1,
                   linestyle="--", alpha=0.7, label="Цель: 75%")

        ax.set_xticks(list(range(n)))
        ax.set_xticklabels(labels, fontsize=8.5, color="#1e293b", ha="center")
        ax.set_ylim(0, 120)
        ax.set_ylabel("Точность, %", color="#1e293b", fontsize=10)
        ax.tick_params(axis="y", colors="#1e293b")
        ax.tick_params(axis="x", colors="#1e293b")

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["bottom", "left"]:
            ax.spines[spine].set_color("#cbd5e1")

        ax.yaxis.grid(True, color="#e2e8f0", linewidth=0.8, alpha=0.9)
        ax.set_axisbelow(True)

        exam_title = {
            "oge":         "ОГЭ",
            "ege_base":    "ЕГЭ база",
            "ege_profile": "ЕГЭ профиль",
        }.get(exam_type, "")

        ax.set_title(
            f"Прогресс {exam_title} — {part_title} "
            f"({part_idx + 1}/{total_parts})\n"
            f"Всего: {stats['total']} попыток  |  "
            f"Верно: {stats['correct']}  |  "
            f"Точность: {stats['accuracy']}%",
            color="#0f172a", fontsize=11, fontweight="bold", pad=12
        )

        patches = [
            mpatches.Patch(color="#22c55e", label="Хорошо (≥75%)"),
            mpatches.Patch(color="#f59e0b", label="Средне (50–74%)"),
            mpatches.Patch(color="#ef4444", label="Слабо (<50%)"),
            mpatches.Patch(color="#cbd5e1", label="Не решалось"),
        ]
        ax.legend(handles=patches, loc="upper right",
                  facecolor="#ffffff", edgecolor="#e2e8f0",
                  labelcolor="#1e293b", fontsize=8)

        plt.tight_layout(pad=1.5)
        chart_path = CHARTS_DIR / f"progress_{vk_id}_{timestamp}_part{part_idx+1}.png"
        plt.savefig(chart_path, dpi=130, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        chart_paths.append(str(chart_path))

    return chart_paths


async def send_progress_chart(peer_id: int, user_id: int, bot_api, exam_type: str = None):

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    stats = await get_user_progress_stats(user_id, exam_type=exam_type)
    if not stats:
        await bot_api.messages.send(
            peer_id=peer_id,
            message=(
                "📊 Пока нет статистики.\n"
                "Реши несколько заданий — и я построю график прогресса!"
            ),
            random_id=0
        )
        return

    # Строим графики — используем vk_id (user_id здесь и есть vk_id, переданный из handlers)
    chart_paths = build_progress_chart(user_id, stats, exam_type=exam_type)
    if not chart_paths:
        await bot_api.messages.send(
            peer_id=peer_id,
            message="⚠️ Не удалось построить график. Попробуй позже.",
            random_id=0
        )
        return

    # Слабые темы (решались, но плохо)
    weak = [r for r in stats["by_task"] if r["accuracy"] < 50 and r["total"] >= 3]
    weak_text = ""
    if weak:
        lines = [
            f"  • №{r['task_number']} "
            f"{TOPIC_NAMES_RU.get(r['topic'], r['topic'])}"
            f" — {r['accuracy']}%"
            for r in sorted(weak, key=lambda x: x["accuracy"])[:3]
        ]
        weak_text = "\n\n⚠️ Стоит подтянуть:\n" + "\n".join(lines)

    # Задания которые ни разу не решались
    if exam_type and exam_type != "all":
        EXAM_ALL_TASKS = {
            "oge": list(range(1, 26)),
            "ege_base": list(range(1, 22)),
            "ege_profile": list(range(1, 20)),
        }
        all_task_numbers = EXAM_ALL_TASKS.get(exam_type, [])
        solved_numbers = {r["task_number"] for r in stats["by_task"]}
        not_tried = [n for n in all_task_numbers if n not in solved_numbers]

        if not_tried:
            if len(not_tried) <= 8:
                nums = ", ".join(f"№{n}" for n in not_tried)
                not_tried_text = f"\n\n📌 Ещё не решал:\n  {nums}\n  Стоит приступить к ним!"
            else:
                nums = ", ".join(f"№{n}" for n in not_tried[:8])
                not_tried_text = (
                    f"\n\n📌 Ещё не решал {len(not_tried)} заданий:\n"
                    f"  {nums} и ещё {len(not_tried) - 8}...\n"
                    f"  Стоит приступить к ним!"
                )
            weak_text += not_tried_text

    caption = (
        f"📊 Твой прогресс:\n"
        f"✅ Верно: {stats['correct']} из {stats['total']}\n"
        f"🎯 Точность: {stats['accuracy']}%"
        f"{weak_text}"
    )

    await bot_api.messages.send(
        peer_id=peer_id, message=caption, random_id=0
    )

    # Загружаем и отправляем каждый график
    uploader = PhotoMessageUploader(bot_api)
    for i, path in enumerate(chart_paths):
        if not os.path.exists(path):
            continue
        if i > 0:
            await asyncio.sleep(1.5)
        try:
            attachment = await uploader.upload(
                file_source=path,
                peer_id=peer_id
            )
            if not attachment:
                await bot_api.messages.send(
                    peer_id=peer_id,
                    message=f"⚠️ График {i + 1} не загрузился в VK (пустой ответ).",
                    random_id=0
                )
                continue
            await bot_api.messages.send(
                peer_id=peer_id,
                attachment=attachment,
                random_id=0
            )
        except Exception as e:
            await bot_api.messages.send(
                peer_id=peer_id,
                message=f"⚠️ График {i + 1} не загрузился: {e}",
                random_id=0
            )

    # Удаляем файлы только ПОСЛЕ того как все графики отправлены
    for path in chart_paths:
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass