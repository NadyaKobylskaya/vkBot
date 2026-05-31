from vkbottle import Keyboard, Text, KeyboardButtonColor, Callback

# ═══════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════════════

exam = (
    Keyboard(one_time=False)
    .add(Text("ОГЭ"), color=KeyboardButtonColor.PRIMARY)
    .add(Text("ЕГЭ"), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text("Мой прогресс"), color=KeyboardButtonColor.SECONDARY)
    .add(Text("ℹ️ Как пользоваться"), color=KeyboardButtonColor.SECONDARY)
    .get_json()
)

# ═══════════════════════════════════════════════
# МЕНЮ ЗАДАНИЙ ОГЭ — ПОЛНОЕ
# ═══════════════════════════════════════════════

oge = (
    Keyboard(inline=True)
    .add(Callback("📘 Первая часть", {"cmd": "oge_part1"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📗 Вторая часть", {"cmd": "oge_part2"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("🎲 Решить вариант",    {"cmd": "solve_variant"}),      color=KeyboardButtonColor.POSITIVE)
    .add(Callback("📥 Экспорт варианта",  {"cmd": "export_menu_oge"}),    color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Callback("🧠 AI Help",           {"cmd": "ai_help"}),            color=KeyboardButtonColor.POSITIVE)
    .add(Callback("📊 Мой прогресс",      {"cmd": "my_stats"}),           color=KeyboardButtonColor.SECONDARY)
    .get_json()
)

def make_variant_next_kb() -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("➡️ Следующее задание", {"cmd": "variant_next"}), color=KeyboardButtonColor.POSITIVE)
        .add(Callback("⛔ Завершить вариант",  {"cmd": "variant_finish"}))
        .get_json()
    )

def make_variant_wrong_kb() -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("✅ Правильный ответ", {"cmd": "variant_show_right"}))
        .add(Callback("➡️ Дальше",          {"cmd": "variant_next"}), color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Callback("⛔ Завершить",         {"cmd": "variant_finish"}))
        .get_json()
    )

variant_next_kb  = make_variant_next_kb()
variant_wrong_kb = make_variant_wrong_kb()

oge_part1 = (
    Keyboard(inline=True)
    .add(Callback("🔢 Алгебра (зад. 1–14)", {"cmd": "oge_algebra"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📐 Геометрия (зад. 15–19)", {"cmd": "oge_geo"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

oge_algebra = (
    Keyboard(inline=True)
    .add(Callback("📋 Задания 1–5", {"cmd": "n1_5"}))
    .row()
    .add(Callback("№6", {"cmd": "n6"}))
    .add(Callback("№7", {"cmd": "n7"}))
    .add(Callback("№8", {"cmd": "n8"}))
    .row()
    .add(Callback("➡️ Задания 9–14", {"cmd": "oge_algebra2"}), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "oge_part1"}))
    .get_json()
)

oge_algebra2 = (
    Keyboard(inline=True)
    .add(Callback("№9",  {"cmd": "n9"}))
    .add(Callback("№10", {"cmd": "n10"}))
    .add(Callback("№11", {"cmd": "n11"}))
    .row()
    .add(Callback("№12", {"cmd": "n12"}))
    .add(Callback("№13", {"cmd": "n13"}))
    .add(Callback("№14", {"cmd": "n14"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "oge_algebra"}))
    .get_json()
)

oge_geo = (
    Keyboard(inline=True)
    .add(Callback("№15", {"cmd": "n15"}))
    .add(Callback("№16", {"cmd": "n16"}))
    .add(Callback("№17", {"cmd": "n17"}))
    .row()
    .add(Callback("№18", {"cmd": "n18"}))
    .add(Callback("№19", {"cmd": "n19"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "oge_part1"}))
    .get_json()
)

oge_part2 = (
    Keyboard(inline=True)
    .add(Callback("№20", {"cmd": "n20"}))
    .add(Callback("№21", {"cmd": "n21"}))
    .add(Callback("№22", {"cmd": "n22"}))
    .row()
    .add(Callback("№23", {"cmd": "n23"}))
    .add(Callback("№24", {"cmd": "n24"}))
    .add(Callback("№25", {"cmd": "n25"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .row()
    .add(Callback("🧠 AI Help",      {"cmd": "ai_help"}),   color=KeyboardButtonColor.POSITIVE)
    .add(Callback("📊 Мой прогресс", {"cmd": "my_stats"}),  color=KeyboardButtonColor.SECONDARY)
    .get_json()
)

oge_with_stats = oge


# ═══════════════════════════════════════════════
# МЕНЮ ЕГЭ
# ═══════════════════════════════════════════════

# Главное меню выбора уровня ЕГЭ
ege = (
    Keyboard(inline=True)
    .add(Callback("📘 ЕГЭ База",    {"cmd": "ege_base"}),    color=KeyboardButtonColor.PRIMARY)
    .add(Callback("📗 ЕГЭ Профиль", {"cmd": "ege_profile"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("🧠 AI Help",      {"cmd": "ai_help"}),     color=KeyboardButtonColor.POSITIVE)
    .add(Callback("📊 Мой прогресс", {"cmd": "my_stats"}),    color=KeyboardButtonColor.SECONDARY)
    .get_json()
)

# ЕГЭ База — главное меню (группы заданий)
ege_base = (
    Keyboard(inline=True)
    .add(Callback("Задания 1–7 ▶",   {"cmd": "ege_base1"}))
    .row()
    .add(Callback("Задания 8–14 ▶",  {"cmd": "ege_base2"}))
    .row()
    .add(Callback("Задания 15–21 ▶", {"cmd": "ege_base3"}))
    .row()
    .add(Callback("🎲 Решить вариант",   {"cmd": "solve_variant_ege_base"}), color=KeyboardButtonColor.POSITIVE)
    .add(Callback("📥 Экспорт варианта", {"cmd": "export_menu_ege_base"}),   color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege"}))
    .get_json()
)

# ЕГЭ База — задания 1–7
ege_base1 = (
    Keyboard(inline=True)
    .add(Callback("№1", {"cmd": "e1"}))
    .add(Callback("№2", {"cmd": "e2"}))
    .add(Callback("№3", {"cmd": "e3"}))
    .row()
    .add(Callback("№4", {"cmd": "e4"}))
    .add(Callback("№5", {"cmd": "e5"}))
    .row()
    .add(Callback("№6", {"cmd": "e6"}))
    .add(Callback("№7", {"cmd": "e7"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_base"}))
    .get_json()
)

ege_base2 = (
    Keyboard(inline=True)
    .add(Callback("№8",  {"cmd": "e8"}))
    .add(Callback("№9",  {"cmd": "e9"}))
    .add(Callback("№10", {"cmd": "e10"}))
    .row()
    .add(Callback("№11", {"cmd": "e11"}))
    .add(Callback("№12", {"cmd": "e12"}))
    .add(Callback("№13", {"cmd": "e13"}))
    .add(Callback("№14", {"cmd": "e14"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_base"}))
    .get_json()
)

ege_base3 = (
    Keyboard(inline=True)
    .add(Callback("№15", {"cmd": "e15"}))
    .add(Callback("№16", {"cmd": "e16"}))
    .add(Callback("№17", {"cmd": "e17"}))
    .row()
    .add(Callback("№18", {"cmd": "e18"}))
    .add(Callback("№19", {"cmd": "e19"}))
    .add(Callback("№20", {"cmd": "e20"}))
    .add(Callback("№21", {"cmd": "e21"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_base"}))
    .get_json()
)

# ЕГЭ Профиль — главное меню (Часть 1 / Часть 2)
ege_profile = (
    Keyboard(inline=True)
    .add(Callback("📋 Часть 1 (1–12)",  {"cmd": "ege_p_part1_menu"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📝 Часть 2 (13–19)", {"cmd": "ege_p_part2"}),      color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("🎲 Решить вариант",   {"cmd": "solve_variant_ege_profile"}), color=KeyboardButtonColor.POSITIVE)
    .add(Callback("📥 Экспорт варианта", {"cmd": "export_menu_ege_profile"}),   color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege"}))
    .get_json()
)

# ЕГЭ Профиль — Часть 1: выбор группы заданий (1-6 или 7-12)
ege_p_part1_menu = (
    Keyboard(inline=True)
    .add(Callback("Задания 1–6 ▶",  {"cmd": "ege_p_part1"}),  color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("Задания 7–12 ▶", {"cmd": "ege_p_part1b"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_profile"}))
    .get_json()
)

# ЕГЭ Профиль — Часть 1, задания 1–6
ege_p_part1 = (
    Keyboard(inline=True)
    .add(Callback("№1", {"cmd": "p1"}))
    .add(Callback("№2", {"cmd": "p2"}))
    .add(Callback("№3", {"cmd": "p3"}))
    .row()
    .add(Callback("№4", {"cmd": "p4"}))
    .add(Callback("№5", {"cmd": "p5"}))
    .add(Callback("№6", {"cmd": "p6"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_p_part1_menu"}))
    .get_json()
)

ege_p_part1b = (
    Keyboard(inline=True)
    .add(Callback("№7",  {"cmd": "p7"}))
    .add(Callback("№8",  {"cmd": "p8"}))
    .add(Callback("№9",  {"cmd": "p9"}))
    .row()
    .add(Callback("№10", {"cmd": "p10"}))
    .add(Callback("№11", {"cmd": "p11"}))
    .add(Callback("№12", {"cmd": "p12"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_p_part1_menu"}))
    .get_json()
)

ege_p_part2 = (
    Keyboard(inline=True)
    .add(Callback("№13", {"cmd": "p13"}))
    .add(Callback("№14", {"cmd": "p14"}))
    .add(Callback("№15", {"cmd": "p15"}))
    .row()
    .add(Callback("№16", {"cmd": "p16"}))
    .add(Callback("№17", {"cmd": "p17"}))
    .row()
    .add(Callback("№18", {"cmd": "p18"}))
    .add(Callback("№19", {"cmd": "p19"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_profile"}))
    .get_json()
)

# ═══════════════════════════════════════════════
# МЕНЮ ЭКСПОРТА ВАРИАНТОВ
# ═══════════════════════════════════════════════

export_menu_oge = (
    Keyboard(inline=True)
    .add(Callback("📄 PDF без ответов",              {"cmd": "export_variant_oge_pdf"}),          color=KeyboardButtonColor.PRIMARY)
    .add(Callback("📄 PDF с ответами",   {"cmd": "export_variant_oge_pdf_answers"}),  color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📝 DOCX без ответов",             {"cmd": "export_variant_oge_docx"}),         color=KeyboardButtonColor.SECONDARY)
    .add(Callback("📝 DOCX с ответами",  {"cmd": "export_variant_oge_docx_answers"}), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

export_menu_ege_base = (
    Keyboard(inline=True)
    .add(Callback("📄 PDF без ответов",              {"cmd": "export_variant_ege_base_pdf"}),          color=KeyboardButtonColor.PRIMARY)
    .add(Callback("📄 PDF с ответами",   {"cmd": "export_variant_ege_base_pdf_answers"}),  color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📝 DOCX без ответов",             {"cmd": "export_variant_ege_base_docx"}),         color=KeyboardButtonColor.SECONDARY)
    .add(Callback("📝 DOCX с ответами",  {"cmd": "export_variant_ege_base_docx_answers"}), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_base"}))
    .get_json()
)

export_menu_ege_profile = (
    Keyboard(inline=True)
    .add(Callback("📄 PDF без ответов",              {"cmd": "export_variant_ege_profile_pdf"}),          color=KeyboardButtonColor.PRIMARY)
    .add(Callback("📄 PDF с ответами",   {"cmd": "export_variant_ege_profile_pdf_answers"}),  color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📝 DOCX без ответов",             {"cmd": "export_variant_ege_profile_docx"}),         color=KeyboardButtonColor.SECONDARY)
    .add(Callback("📝 DOCX с ответами",  {"cmd": "export_variant_ege_profile_docx_answers"}), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "ege_profile"}))
    .get_json()
)

# ═══════════════════════════════════════════════
# ПРОЧИЕ ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ
# ═══════════════════════════════════════════════

ai_cancel_kb = (
    Keyboard(inline=True)
    .add(Callback("❌ Отмена", {"cmd": "ai_cancel"}), color=KeyboardButtonColor.NEGATIVE)
    .get_json()
)

progress_exam_choice = (
    Keyboard(inline=True)
    .add(Callback("📘 ОГЭ",          {"cmd": "progress_oge"}))
    .add(Callback("📗 ЕГЭ База",     {"cmd": "progress_ege_base"}))
    .row()
    .add(Callback("📙 ЕГЭ Профиль",  {"cmd": "progress_ege_profile"}))
    .add(Callback("📊 Все",          {"cmd": "progress_all"}))
    .get_json()
)

# Задание 24 ОГЭ — выбор темы доказательства
oge_n24 = (
    Keyboard(inline=True)
    .add(Callback("Параллелограмм", {"cmd": "proof_parallelogram"}))
    .add(Callback("Треугольник",    {"cmd": "proof_triangle"}))
    .row()
    .add(Callback("Окружность",     {"cmd": "proof_circle"}))
    .add(Callback("🎲 Случайная",   {"cmd": "proof_random"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "oge_part2"}))
    .get_json()
)

# after_peek для заданий 2-й части ОГЭ — объявляются ниже после def make_after_peek_kb


def make_after_peek_kb(retry_cmd: str):
    """
   n
    """
    return (
        Keyboard(inline=True)
        .add(Callback("🔄 Новое задание", payload={"cmd": retry_cmd}),
             color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Callback("🤖 AI Help", payload={"cmd": "ai_help"}))
        .add(Callback("🏠 В меню", payload={"cmd": "back_to_tasks_oge"}),
             color=KeyboardButtonColor.NEGATIVE)
        .get_json()
    )


# Создать экземпляры для n12 (и для остальных заданий по аналогии):
after_peek_n6_ordinary_fractions = make_after_peek_kb("ordinary_fractions")
after_peek_n6_decimal_fractions = make_after_peek_kb("decimal_fractions")
after_peek_n8_decimal_fractions = make_after_peek_kb("task8_degrees")
after_peek_n8_task8_arithmetic_square_root = make_after_peek_kb("task8_arithmetic_square_root")
after_peek_n9_linear_equations = make_after_peek_kb("linear_equations")
after_peek_n9_quadratic_equations = make_after_peek_kb("quadratic_equations")

after_peek_n12 = make_after_peek_kb("n12")

# Для задания 11 (по аналогии):
after_peek_n11_linear = make_after_peek_kb("n11_linear")
after_peek_n11_quadratic = make_after_peek_kb("n11_quadratic")
after_peek_n11_hyperbola = make_after_peek_kb("n11_hyperbola")
after_peek_n11_mixed = make_after_peek_kb("n11_mixed")

# После подсматривания в заданиях 2-й части ОГЭ
after_peek_n23 = make_after_peek_kb("n23")
after_peek_n24 = make_after_peek_kb("n24")
after_peek_n25 = make_after_peek_kb("n25")


# ═══════════════════════════════════════════════
# ПОДМЕНЮ ЗАДАНИЙ
# ═══════════════════════════════════════════════

oge_n1_5 = (
    Keyboard(inline=True)
    .add(Callback("🏠 Квартира",   {"cmd": "t1_5_kvartira"}))
    .add(Callback("🌿 Участок",    {"cmd": "t1_5_uchastok"}))
    .row()
    .add(Callback("🗺️ План",       {"cmd": "t1_5_plan"}))
    .add(Callback("📄 Листы",      {"cmd": "t1_5_listy"}))
    .row()
    .add(Callback("🚗 Шины",       {"cmd": "t1_5_shiny"}))
    .add(Callback("📱 Тарифы",     {"cmd": "t1_5_tarify"}))
    .row()
    .add(Callback("🔥 Печь для бани", {"cmd": "t1_5_pech"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

oge_n6 = (
    Keyboard(inline=True)
    .add(Callback("Обыкновенные дроби", {"cmd": "ordinary_fractions"}))
    .row()
    .add(Callback("Десятичные дроби",   {"cmd": "decimal_fractions"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

oge_n8 = (
    Keyboard(inline=True)
    .add(Callback("Степенные выражения", {"cmd": "task8_degrees"}))
    .row()
    .add(Callback("Арифметические корни", {"cmd": "task8_arithmetic_square_root"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

oge_n9 = (
    Keyboard(inline=True)
    .add(Callback("Линейные уравнения",   {"cmd": "linear_equations"}))
    .row()
    .add(Callback("Квадратные уравнения", {"cmd": "quadratic_equations"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

# ── Задание 11 — Графики функций ────────────────────────────────────────────
oge_n11 = (
    Keyboard(inline=True)
    .add(Callback("📈 Линейная функция",    {"cmd": "n11_linear"}),    color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📈 Парабола",            {"cmd": "n11_quadratic"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📈 Гипербола",           {"cmd": "n11_hyperbola"}), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("📈 Смешанные задания",   {"cmd": "n11_mixed"}),     color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Callback("🎲 Случайная тема",      {"cmd": "n11_random"}),    color=KeyboardButtonColor.POSITIVE)
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

oge_n13 = (
    Keyboard(inline=True)
    .add(Callback("Линейные неравенства",        {"cmd": "linear_inequalities"}))
    .row()
    .add(Callback("Квадратные неравенства",      {"cmd": "quadratic_inequalities"}))
    .row()
    .add(Callback("Системы линейных неравенств", {"cmd": "systems_linear_inequalities"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

oge_n14 = (
    Keyboard(inline=True)
    .add(Callback("Арифметическая прогрессия", {"cmd": "arithmetic_progression"}))
    .row()
    .add(Callback("Геометрическая прогрессия", {"cmd": "geometric_progression"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

# Меню тем задания 17
oge_n17 = (
    Keyboard(inline=True)
    .add(Callback("Параллелограмм",  {"cmd": "n17_parallelogram"}))
    .add(Callback("Трапеция",        {"cmd": "n17_trapezoid"}))
    .row()
    .add(Callback("Прямоугольник",   {"cmd": "n17_rectangle"}))
    .add(Callback("Ромб",            {"cmd": "n17_rhombus"}))
    .row()
    .add(Callback("Квадрат",         {"cmd": "n17_square"}))
    .add(Callback("🎲 Случайная",    {"cmd": "n17_random"}))
    .row()
    .add(Callback("◀️ Назад",        {"cmd": "oge_geo"}))
    .get_json()
)

oge_n20 = (
    Keyboard(inline=True)
    .add(Callback("Системы уравнений", {"cmd": "n20_systems"}))
    .row()
    .add(Callback("Уравнения",         {"cmd": "n20_equations"}))
    .row()
    .add(Callback("Неравенства",       {"cmd": "n20_inequalities"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

oge_n21 = (
    Keyboard(inline=True)
    .add(Callback("Движение по прямой", {"cmd": "n21_motion_line"}))
    .row()
    .add(Callback("Движение по воде",   {"cmd": "n21_motion_water"}))
    .row()
    .add(Callback("Задачи на работу",   {"cmd": "n21_work"}))
    .row()
    .add(Callback("Проценты",           {"cmd": "n21_percent"}))
    .row()
    .add(Callback("◀️ Назад", {"cmd": "back_to_tasks_oge"}))
    .get_json()
)

# ═══════════════════════════════════════════════
# КЛАВИАТУРЫ ДЛЯ НАБОРА ЗАДАНИЙ 1–5
# ═══════════════════════════════════════════════

def make_next_in_set_kb(topic_cmd: str) -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("➡️ Следующее задание", {"cmd": f"next_{topic_cmd}"}), color=KeyboardButtonColor.POSITIVE)
        .get_json()
    )

def make_set_hint_kb(topic_cmd: str) -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("✅ Верный ответ",  {"cmd": f"set_show_right_{topic_cmd}"}), color=KeyboardButtonColor.NEGATIVE)
        .add(Callback("🧠 Помощь ИИ",    {"cmd": "ai_help"}),                     color=KeyboardButtonColor.POSITIVE)
        .row()
        .add(Callback("📖 Справочник",   {"cmd": f"set_show_ref_{topic_cmd}"}))
        .add(Callback("➡️ Дальше",       {"cmd": f"set_skip_{topic_cmd}"}))
        .get_json()
    )

def make_set_result_kb(topic_cmd: str) -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("🔁 Новый набор",  {"cmd": topic_cmd}), color=KeyboardButtonColor.POSITIVE)
        .add(Callback("📋 В меню",       {"cmd": "back_to_tasks_oge"}))
        .get_json()
    )

# ═══════════════════════════════════════════════
# КЛАВИАТУРА ДЛЯ ВТОРОЙ ЧАСТИ
# ═══════════════════════════════════════════════

def make_part2_help_kb(show_right_cmd: str, show_solution_cmd: str) -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("✅ Правильный ответ",  {"cmd": show_right_cmd}))
        .row()
        .add(Callback("📄 Подробное решение", {"cmd": show_solution_cmd}))
        .row()
        .add(Callback("🧠 Помощь ИИ",         {"cmd": "ai_help"}), color=KeyboardButtonColor.POSITIVE)
        .get_json()
    )

def make_part2_retry_kb(retry_cmd: str) -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("🔁 Ещё задание", {"cmd": retry_cmd}), color=KeyboardButtonColor.POSITIVE)
        .add(Callback("📋 В меню",       {"cmd": "back_to_tasks_oge"}))
        .get_json()
    )

# ═══════════════════════════════════════════════
# УНИВЕРСАЛЬНЫЕ КЛАВИАТУРЫ (retry / help)
# ═══════════════════════════════════════════════

def make_retry_or_menu(retry_cmd: str) -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("🔁 Ещё задание", {"cmd": retry_cmd}), color=KeyboardButtonColor.POSITIVE)
        .add(Callback("📋 В меню",       {"cmd": "back_to_tasks_oge"}))
        .get_json()
    )

def make_help_kb(show_right_cmd: str, show_help_cmd: str) -> str:
    return (
        Keyboard(inline=True)
        .add(Callback("✅ Правильный ответ", {"cmd": show_right_cmd}))
        .row()
        .add(Callback("📖 Справочник",       {"cmd": show_help_cmd}))
        .row()
        .add(Callback("🧠 Помощь ИИ",        {"cmd": "ai_help"}), color=KeyboardButtonColor.POSITIVE)
        .get_json()
    )

# ═══════════════════════════════════════════════
# ЭКЗЕМПЛЯРЫ КЛАВИАТУР
# ═══════════════════════════════════════════════

# Задание 6
retry_or_menu_ordinary = make_retry_or_menu("ordinary_fractions")
help_or_retry_ordinary = make_help_kb("show_right_ordinary", "show_help_ordinary")

retry_or_menu_decimal  = make_retry_or_menu("decimal_fractions")
help_or_retry_decimal  = make_help_kb("show_right_decimal", "show_help_decimal")

# Задание 7
retry_or_menu_task7 = make_retry_or_menu("n7")
help_or_retry_task7 = make_help_kb("show_right_task7", "show_help_task7")

# Задание 8
retry_or_menu_task8_degrees = make_retry_or_menu("task8_degrees")
help_or_retry_task8_degrees = make_help_kb("show_right_task8_degrees", "show_help_task8_degrees")

retry_or_menu_task8_arithmetic_square_root = make_retry_or_menu("task8_arithmetic_square_root")
help_or_retry_task8_arithmetic_square_root = make_help_kb(
    "show_right_task8_arithmetic_square_root", "show_help_task8_arithmetic_square_root")

# Задание 9
retry_or_menu_linear    = make_retry_or_menu("linear_equations")
help_or_retry_linear    = make_help_kb("show_right_linear", "show_help_linear")

retry_or_menu_quadratic = make_retry_or_menu("quadratic_equations")
help_or_retry_quadratic = make_help_kb("show_right_quadratic", "show_help_quadratic")

# Задание 10
retry_or_menu_task10_probability_problems = make_retry_or_menu("n10")
help_or_retry_task10_probability_problems = make_help_kb(
    "show_right_task10_probability_problems", "show_help_task10_probability_problems")

# Задание 11 — Графики функций
retry_or_menu_n11_linear    = make_retry_or_menu("n11_linear")
help_or_retry_n11_linear    = make_help_kb("show_right_n11_linear",    "show_help_n11_linear")

retry_or_menu_n11_quadratic = make_retry_or_menu("n11_quadratic")
help_or_retry_n11_quadratic = make_help_kb("show_right_n11_quadratic", "show_help_n11_quadratic")

retry_or_menu_n11_hyperbola = make_retry_or_menu("n11_hyperbola")
help_or_retry_n11_hyperbola = make_help_kb("show_right_n11_hyperbola", "show_help_n11_hyperbola")

retry_or_menu_n11_mixed     = make_retry_or_menu("n11_mixed")
help_or_retry_n11_mixed     = make_help_kb("show_right_n11_mixed",     "show_help_n11_mixed")

# Задание 12
retry_or_menu_n12 = make_retry_or_menu("n12")
help_or_retry_n12 = make_help_kb("show_right_n12", "show_help_n12")

# Задание 13
retry_or_menu_linear_ineq         = make_retry_or_menu("linear_inequalities")
help_or_retry_linear_ineq         = make_help_kb("show_right_linear_ineq", "show_help_linear_ineq")

retry_or_menu_quadratic_ineq      = make_retry_or_menu("quadratic_inequalities")
help_or_retry_quadratic_ineq      = make_help_kb("show_right_quadratic_ineq", "show_help_quadratic_ineq")

retry_or_menu_systems_linear_ineq = make_retry_or_menu("systems_linear_inequalities")
help_or_retry_systems_linear_ineq = make_help_kb(
    "show_right_systems_linear_ineq", "show_help_systems_linear_ineq")

# Задание 14
retry_or_menu_arith_prog = make_retry_or_menu("arithmetic_progression")
help_or_retry_arith_prog = make_help_kb("show_right_arith_prog", "show_help_arith_prog")

retry_or_menu_geom_prog  = make_retry_or_menu("geometric_progression")
help_or_retry_geom_prog  = make_help_kb("show_right_geom_prog", "show_help_geom_prog")

after_peek_arith_prog = make_after_peek_kb("arithmetic_progression")
after_peek_geom_prog  = make_after_peek_kb("geometric_progression")

# Задания 15–19
retry_or_menu_n15 = make_retry_or_menu("n15")
help_or_retry_n15 = make_help_kb("show_right_n15", "show_help_n15")

retry_or_menu_n16 = make_retry_or_menu("n16")
help_or_retry_n16 = make_help_kb("show_right_n16", "show_help_n16")
after_peek_n16     = make_retry_or_menu("n16")

retry_or_menu_n17 = make_retry_or_menu("n17_retry")
after_peek_n17    = make_retry_or_menu("n17_retry")
help_or_retry_n17 = make_help_kb("show_right_n17", "show_help_n17")


retry_or_menu_n18 = make_retry_or_menu("n18")
help_or_retry_n18 = make_help_kb("show_right_n18", "show_help_n18")
after_peek_n18     = make_retry_or_menu("n18")

retry_or_menu_n19 = make_retry_or_menu("n19")
help_or_retry_n19 = make_help_kb("show_right_n19", "show_help_n19")
after_peek_n19     = make_retry_or_menu("n19")

# 2-я часть
retry_or_menu_n20_systems      = make_part2_retry_kb("n20_systems")
help_or_retry_n20_systems      = make_part2_help_kb("show_right_n20", "show_solution_n20")

retry_or_menu_n20_equations    = make_part2_retry_kb("n20_equations")
help_or_retry_n20_equations    = make_part2_help_kb("show_right_n20", "show_solution_n20")

retry_or_menu_n20_inequalities = make_part2_retry_kb("n20_inequalities")
help_or_retry_n20_inequalities = make_part2_help_kb("show_right_n20", "show_solution_n20")

retry_or_menu_n21_motion_line  = make_part2_retry_kb("n21_motion_line")
help_or_retry_n21_motion_line  = make_part2_help_kb("show_right_n21", "show_solution_n21")

retry_or_menu_n21_motion_water = make_part2_retry_kb("n21_motion_water")
help_or_retry_n21_motion_water = make_part2_help_kb("show_right_n21", "show_solution_n21")

retry_or_menu_n21_work         = make_part2_retry_kb("n21_work")
help_or_retry_n21_work         = make_part2_help_kb("show_right_n21", "show_solution_n21")

retry_or_menu_n21_percent      = make_part2_retry_kb("n21_percent")
help_or_retry_n21_percent      = make_part2_help_kb("show_right_n21", "show_solution_n21")

retry_or_menu_n22 = make_part2_retry_kb("n22")
help_or_retry_n22 = make_part2_help_kb("show_right_n22", "show_solution_n22")

oge_n23 = (
    Keyboard(inline=True)
    .add(Callback("Параллелограмм",  {"cmd": "n23_parallelogram"}))
    .add(Callback("Ромб",            {"cmd": "n23_rhombus"}))
    .row()
    .add(Callback("Треугольник",     {"cmd": "n23_triangle"}))
    .add(Callback("Окружность",      {"cmd": "n23_circle"}))
    .row()
    .add(Callback("🎲 Случайная",    {"cmd": "random_n23"}))
    .row()
    .add(Callback("◀️ Назад",        {"cmd": "oge_part2"}))
    .get_json()
)

retry_or_menu_n23 = make_part2_retry_kb("n23")
help_or_retry_n23 = make_part2_help_kb("show_right_n23", "show_solution_n23")

retry_or_menu_n24 = make_part2_retry_kb("n24")
help_or_retry_n24 = make_part2_help_kb("show_right_n24", "show_solution_n24")

retry_or_menu_n25 = make_part2_retry_kb("n25")
help_or_retry_n25 = make_part2_help_kb("show_right_n25", "show_solution_n25")

# ── ЕГЭ БАЗА: словарь клавиатур e1–e21 ─────────────────────────────────────
# Формат: {cmd: (retry_kb, help_kb)}
# retry_kb — клавиатура после неверного ответа
# help_kb  — клавиатура с кнопками «Показать ответ» и «Помощь ИИ»

def _make_ege_base_kbs() -> dict:
    result = {}
    for cmd in [f"e{i}" for i in range(1, 22)]:
        retry_kb = (
            Keyboard(inline=True)
            .add(Callback("🔁 Ещё задание",       {"cmd": cmd}),   color=KeyboardButtonColor.POSITIVE)
            .add(Callback("✅ Показать ответ",     {"cmd": f"show_right_{cmd}"}))
            .row()
            .add(Callback("🧠 Помощь ИИ",          {"cmd": "ai_help"}), color=KeyboardButtonColor.POSITIVE)
            .add(Callback("📋 В меню",              {"cmd": "ege_base"}))
            .get_json()
        )
        help_kb = (
            Keyboard(inline=True)
            .add(Callback("🔁 Ещё задание",        {"cmd": cmd}),   color=KeyboardButtonColor.POSITIVE)
            .add(Callback("📋 В меню",              {"cmd": "ege_base"}))
            .get_json()
        )
        result[cmd] = (retry_kb, help_kb)
    return result

ege_base_keyboards: dict = _make_ege_base_kbs()


# ── ЕГЭ ПРОФИЛЬ ЧАСТЬ 1: словарь клавиатур p1–p12 ──────────────────────────

def _make_ege_p1_kbs() -> dict:
    result = {}
    for cmd in [f"p{i}" for i in range(1, 13)]:
        retry_kb = (
            Keyboard(inline=True)
            .add(Callback("🔁 Ещё задание",    {"cmd": cmd}),             color=KeyboardButtonColor.POSITIVE)
            .add(Callback("✅ Показать ответ", {"cmd": f"show_right_{cmd}"}))
            .row()
            .add(Callback("🧠 Помощь ИИ",     {"cmd": "ai_help"}),        color=KeyboardButtonColor.POSITIVE)
            .add(Callback("📋 В меню",         {"cmd": "ege_profile"}))
            .get_json()
        )
        help_kb = (
            Keyboard(inline=True)
            .add(Callback("🔁 Ещё задание",    {"cmd": cmd}),              color=KeyboardButtonColor.POSITIVE)
            .add(Callback("📋 В меню",         {"cmd": "ege_profile"}))
            .get_json()
        )
        result[cmd] = (retry_kb, help_kb)
    return result

ege_profile_part1_keyboards: dict = _make_ege_p1_kbs()


# ── ЕГЭ ПРОФИЛЬ ЧАСТЬ 2: словарь клавиатур p13–p19 ─────────────────────────

def _make_ege_p2_kbs() -> dict:
    result = {}
    for cmd in [f"p{i}" for i in range(13, 20)]:
        retry_kb = (
            Keyboard(inline=True)
            .add(Callback("🔁 Ещё задание",    {"cmd": cmd}),             color=KeyboardButtonColor.POSITIVE)
            .add(Callback("✅ Показать ответ", {"cmd": f"show_right_{cmd}"}))
            .row()
            .add(Callback("🧠 Помощь ИИ",     {"cmd": "ai_help"}),        color=KeyboardButtonColor.POSITIVE)
            .add(Callback("📋 В меню",         {"cmd": "ege_p_part2"}))
            .get_json()
        )
        help_kb = (
            Keyboard(inline=True)
            .add(Callback("🔁 Ещё задание",    {"cmd": cmd}),              color=KeyboardButtonColor.POSITIVE)
            .add(Callback("📋 В меню",         {"cmd": "ege_p_part2"}))
            .get_json()
        )
        result[cmd] = (retry_kb, help_kb)
    return result

ege_profile_part2_keyboards: dict = _make_ege_p2_kbs()
