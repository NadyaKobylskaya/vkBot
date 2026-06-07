import random
import json
import asyncio
import time
import re
from pathlib import Path

from vkbottle.bot import Bot, Message, BotLabeler
from vkbottle import BaseStateGroup, CtxStorage
from vkbottle_types.events import GroupEventType

import tempfile, os, aiohttp as _aiohttp
from app.neural.inference import neural_checker

import app.keyboards as kb
from app.deepseek_service import DeepSeekMathHelper
from app.config import DEEPSEEK_API_KEY, VK_TOKEN
from app.export_variant import export_variant_from_dicts
from app.database import (
    get_or_create_user, record_attempt,
    get_user_stats, get_summary_stats, get_weak_topics, get_random_task,
    mark_onboarding_done
)
from app.progress_chart import send_progress_chart

# -----------------------------------------------------------------------
# Инициализация
# -----------------------------------------------------------------------

bot = Bot(token=VK_TOKEN)
router = bot.labeler
ctx = CtxStorage()

# -----------------------------------------------------------------------
# Защита от двойной обработки callback-кнопок VK
# -----------------------------------------------------------------------
# VK иногда присылает один и тот же message_event дважды, из-за этого меню
# и экспорт файла могут отправляться повторно. Храним последнюю команду
# пользователя на короткое время и игнорируем дубль.
CALLBACK_DEDUP_SECONDS = 2.5


def is_duplicate_callback(user_id: int, cmd: str) -> bool:
    now = time.monotonic()
    key = f"last_callback_{user_id}"
    prev = ctx.get(key)

    if prev:
        prev_cmd, prev_time = prev
        if prev_cmd == cmd and now - prev_time < CALLBACK_DEDUP_SECONDS:
            return True

    ctx.set(key, (cmd, now))
    return False


math_helper = DeepSeekMathHelper(DEEPSEEK_API_KEY)

# -----------------------------------------------------------------------
# Загрузка задач
# -----------------------------------------------------------------------

with open("app/tasks.json", "r", encoding="utf-8") as f:
    all_tasks = json.load(f)

task6_ordinary_fractions       = all_tasks.get("task6_ordinary_fractions", [])
task6_decimal_fractions        = all_tasks.get("task6_decimal_fractions", [])
task9_linear_equations         = all_tasks.get("task9_linear_equations", [])
task9_quadratic_equations      = all_tasks.get("task9_quadratic_equations", [])
task13_linear_inequalities     = all_tasks.get("task13_linear_inequalities", [])
task13_quadratic_inequalities  = all_tasks.get("task13_quadratic_inequalities", [])
task13_systems_linear_ineq     = all_tasks.get("task13_systems_linear_ineq", [])
task7                          = all_tasks.get("task7", [])
task8_degrees                  = all_tasks.get("task8_degrees", [])
task8_arithmetic_square_root   = all_tasks.get("task8_arithmetic_square_root", [])
task10_probability_problems    = all_tasks.get("task10_probability_problems", [])

# -----------------------------------------------------------------------
# Состояния
# -----------------------------------------------------------------------

class TaskStates(BaseStateGroup):
    # Уже существующие
    task6_ordinary               = "task6_ordinary"
    task6_decimal                = "task6_decimal"
    task9_linear                 = "task9_linear"
    task9_quadratic              = "task9_quadratic"
    task13_linear_ineq           = "task13_linear_ineq"
    task13_quadratic_ineq        = "task13_quadratic_ineq"
    task13_systems_linear_ineq   = "task13_systems_linear_ineq"
    task7                        = "task7"
    task8_degrees                = "task8_degrees"
    task8_arithmetic_square_root = "task8_arithmetic_square_root"
    task10_probability_problems  = "task10_probability_problems"
    # Задания 1-5 (набор)
    set_1_5                      = "set_1_5"
    # Новые задания 1 части
    n11_linear    = "n11_linear"
    n11_quadratic = "n11_quadratic"
    n11_hyperbola = "n11_hyperbola"
    n11_mixed     = "n11_mixed"
    n12                          = "n12"
    arith_prog                   = "arith_prog"
    geom_prog                    = "geom_prog"
    n15                          = "n15"
    n16                          = "n16"
    n17                          = "n17"
    n18                          = "n18"
    n19                          = "n19"
    # 2-я часть
    n20                          = "n20"
    n21                          = "n21"
    n22                          = "n22"
    n23                          = "n23"
    n24                          = "n24"
    n25                          = "n25"
    e1 = "e1"
    e2 = "e2"
    e3 = "e3"
    e4 = "e4"
    e5 = "e5"
    e6 = "e6"
    e7 = "e7"
    e8 = "e8"
    e9 = "e9"
    e10 = "e10"
    e11 = "e11"
    e12 = "e12"
    e13 = "e13"
    e14 = "e14"
    e15 = "e15"
    e16 = "e16"
    e17 = "e17"
    e18 = "e18"
    e19 = "e19"
    e20 = "e20"
    e21 = "e21"
    p1 = "p1"
    p2 = "p2"
    p3 = "p3"
    p4 = "p4"
    p5 = "p5"
    p6 = "p6"
    p7 = "p7"
    p8 = "p8"
    p9 = "p9"
    p10 = "p10"
    p11 = "p11"
    p12 = "p12"
    p13 = "p13"
    p14 = "p14"
    p15 = "p15"
    p16 = "p16"
    p17 = "p17"
    p18 = "p18"
    p19 = "p19"
    AI_HELP_MODE                 = "ai_help_mode"
    p13_a = "p13_a"  # ждём ответ на пункт а
    p13_b = "p13_b"  # ждём ответ на пункт б

# -----------------------------------------------------------------------
# Хелперы
# -----------------------------------------------------------------------

def get_answer(user_id: int):
    return ctx.get(f"answer_{user_id}")

def set_answer(user_id: int, answer):
    ctx.set(f"answer_{user_id}", str(answer))

def get_task_context(user_id: int):
    return ctx.get(f"task_context_{user_id}")

def set_task_context(user_id: int, task_text: str):
    ctx.set(f"task_context_{user_id}", task_text)

def get_task_id(user_id: int):
    return ctx.get(f"task_id_{user_id}")

def set_task_id(user_id: int, task_id):
    ctx.set(f"task_id_{user_id}", task_id)

def get_peeked(user_id: int) -> bool:
    """Пользователь подсмотрел правильный ответ."""
    return bool(ctx.get(f"peeked_{user_id}"))

def set_peeked(user_id: int, val: bool = True):
    ctx.set(f"peeked_{user_id}", val)

def get_task_meta(user_id: int):
    """Возвращает (exam_type, task_number, topic) текущего задания."""
    return ctx.get(f"task_meta_{user_id}")

def set_task_meta(user_id: int, exam_type: str, task_number: int, topic: str):
    ctx.set(f"task_meta_{user_id}", (exam_type, task_number, topic))

def set_p13_answers(user_id: int, answer_a: str, answer_b: str):
    ctx.set(f"p13_a_{user_id}", answer_a)
    ctx.set(f"p13_b_{user_id}", answer_b)

def get_p13_answer_a(user_id: int) -> str:
    return ctx.get(f"p13_a_{user_id}") or ""

def get_p13_answer_b(user_id: int) -> str:
    return ctx.get(f"p13_b_{user_id}") or ""

async def send_photo(peer_id: int, image_path: str):
    import os
    from vkbottle.tools import PhotoMessageUploader
    from app.database import cache_image_path

    uploader = PhotoMessageUploader(bot.api)
    paths = [p.strip() for p in image_path.split("|") if p.strip()]
    attachments = []
    new_paths = []

    for path in paths:
        try:
            if path.startswith("photo") or path.startswith("doc"):
                attachments.append(path)
                new_paths.append(path)

            elif path.startswith("http://") or path.startswith("https://"):
                async with _aiohttp.ClientSession() as session:
                    async with session.get(path) as resp:
                        data = await resp.read()
                att = await _upload_with_retry(uploader, data, peer_id, is_bytes=True)
                if att:
                    attachments.append(att)
                    new_paths.append(att)

            else:
                # Проверяем есть ли уже кэшированный photo_id
                if "::" in path:
                    local_path, cached_photo = path.split("::", 1)
                    attachments.append(cached_photo)
                    new_paths.append(path)  # сохраняем оба
                    continue

                if not os.path.exists(path):
                    # Пробуем с префиксом app/
                    alt_path = os.path.join("app", path)
                    if os.path.exists(alt_path):
                        path = alt_path
                    else:
                        print(f"⚠️  send_photo: файл не найден: {path!r}")
                        new_paths.append(path)
                        continue
                print(f"[send_photo] загружаю: {path!r}  ({os.path.getsize(path)} байт)")
                att = await _upload_with_retry(uploader, path, peer_id, is_bytes=False)
                if att:
                    attachments.append(att)
                    new_paths.append(f"{path}::{att}")  # локальный::photo_id
                else:
                    print(f"⚠️  send_photo: VK не принял файл {path!r}")
                    new_paths.append(path)

        except Exception as e:
            print(f"⚠️  send_photo: ошибка {path!r}: {e}")
            continue

    if not attachments:
        print(f"⚠️  send_photo: ни одно изображение не загружено для {image_path!r}")
        return

    try:
        await bot.api.messages.send(
            peer_id=peer_id,
            attachment=",".join(attachments),
            random_id=0
        )
        new_image_path = "|".join(new_paths)
        if new_image_path != image_path:
            await cache_image_path(image_path, new_image_path)
    except Exception as e:
        print(f"⚠️  send_photo: ошибка отправки: {e}")


async def _upload_with_retry(uploader, file_source, peer_id: int,
                             is_bytes: bool = False,
                             retries: int = 4, delay: float = 3.0) -> str | None:
    import asyncio, io

    # Небольшая пауза перед первой попыткой — VK иногда не успевает
    await asyncio.sleep(0.5)

    for attempt in range(1, retries + 1):
        try:
            if is_bytes:
                data = io.BytesIO(file_source)
            else:
                with open(file_source, "rb") as f:
                    data = io.BytesIO(f.read())

            att = await uploader.upload(file_source=data, peer_id=peer_id)
            if att:
                return att
            print(f"⚠️  _upload_with_retry: попытка {attempt}/{retries} — пустой att")
        except Exception as e:
            print(f"⚠️  _upload_with_retry: попытка {attempt}/{retries} — {e}")
        if attempt < retries:
            await asyncio.sleep(delay)
    return None



async def download_vk_photo(message: Message) -> str | None:
    """
    Скачивает первое фото из сообщения ВКонтакте во временный файл.
    Возвращает путь к файлу или None, если фото нет.
    """
    if not message.attachments:
        return None

    for att in message.attachments:
        if att.type.value == "photo":
            photo = att.photo
            # Берём наибольшее доступное разрешение
            sizes = sorted(photo.sizes, key=lambda s: s.width * s.height, reverse=True)
            url = sizes[0].url

            # Скачиваем во временный файл
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            try:
                async with _aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        tmp.write(await resp.read())
                tmp.close()
                return tmp.name
            except Exception as e:
                print(f"Ошибка загрузки фото: {e}")
                tmp.close()
                os.unlink(tmp.name)

    return None
async def check_numeric_answer(message: Message, correct_answer, retry_kb, help_kb) -> bool:
    user_input = message.text.strip()
    user_normalized = user_input.replace(',', '.').replace('−', '-')
    if correct_answer is None:
        await message.answer("Сначала выбери задание.")
        return False
    try:
        correct_variants = [v.strip().replace(',', '.').replace('−', '-')
                            for v in str(correct_answer).split('|')]

        is_correct = False
        for variant in correct_variants:
            try:
                user_val = float(user_normalized)
                correct_val = float(variant)
                if abs(user_val - correct_val) < 1e-6:
                    is_correct = True
                    break
            except ValueError:
                if user_normalized.strip() == variant.strip():
                    is_correct = True
                    break

        # ── АНТИШПАРГАЛКА ────────────────────────────────────────
        # Если пользователь подсмотрел ответ — не засчитываем,
        # даже если введённое значение верно.
        peeked = get_peeked(message.from_id)
        if peeked:
            set_peeked(message.from_id, False)  # сбрасываем флаг
            is_correct = False  # принудительно неверно

        # Записываем попытку в БД
        task_id = get_task_id(message.from_id)
        task_meta = get_task_meta(message.from_id)
        if task_meta:
            exam_type, task_number, topic = task_meta
            await record_attempt(
                vk_id=message.from_id,
                task_id=task_id or 0,
                user_answer=user_input,
                is_correct=is_correct,
                exam_type=exam_type,
                task_number=task_number,
                topic=topic
            )

        if is_correct:
            await message.answer("✅ Верно! Хочешь ещё аналогичное задание?", keyboard=retry_kb)
            return True
        else:
            if peeked:
                # Отдельное сообщение — пользователь сам подсмотрел
                await message.answer(
                    "🙈 Ответ не засчитан — ты подсмотрел(а).\n"
                    "Попробуй решить следующее задание самостоятельно!",
                    keyboard=retry_kb
                )
            else:
                await message.answer(
                    "❌ Неправильно. Попробуй снова или воспользуйся подсказкой:",
                    keyboard=help_kb
                )
            return False
    except ValueError:
        await message.answer("Введите числовой ответ.")
        return False

async def answer_callback(event_id, user_id, peer_id):
    """Подтверждение нажатия callback-кнопки."""
    try:
        await bot.api.messages.send_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id
        )
    except Exception:
        pass

# -----------------------------------------------------------------------
# Текстовые команды
# -----------------------------------------------------------------------

@router.message(text=["Начать", "начать", "/start", "start"])
async def cmd_start(message: Message):
    bot.state_dispenser.dictionary.pop(message.from_id, None)
    user, is_new = await get_or_create_user(message.from_id)
    is_first = is_new or not user.get("onboarding_done")
    if is_first:
        await message.answer(
            "👋 Привет! Я бот для подготовки к ЕГЭ и ОГЭ по математике.\n\n"
            "Вот что я умею:\n"
            "📝 Задания — тренируйся по любой теме в удобном темпе\n"
            "🎲 Вариант — реши полный экзаменационный вариант и узнай свой балл\n"
            "🧠 AI Help — разбор решения с объяснением от нейросети\n"
            "📥 Экспорт — скачай вариант в PDF или DOCX\n"
            "📊 Прогресс — смотри статистику и слабые темы\n\n"
            "Кнопки главного меню всегда под рукой — они закреплены внизу экрана. 👇"
        )
        await mark_onboarding_done(message.from_id)
    await message.answer(
        "Выбери экзамен и начнём! 👇",
        keyboard=kb.exam
    )


@router.message(text=["ℹ️ Как пользоваться", "как пользоваться", "/help", "помощь"])
async def cmd_help(message: Message):
    await message.answer(
        "📖 Как пользоваться ботом:\n\n"
        "1️⃣ Выбери экзамен — ОГЭ или ЕГЭ\n"
        "2️⃣ Выбери задание и тему\n"
        "3️⃣ Решай и вводи ответ числом\n"
        "4️⃣ Если не знаешь — нажми ✅ Верный ответ\n\n"
        "🎲 Вариант — полный экзамен из всех заданий с итоговым баллом\n"
        "🧠 AI Help — нейросеть объяснит решение\n"
        "📊 Мой прогресс — статистика и слабые темы\n"
        "📥 Экспорт — скачай вариант в PDF или DOCX\n\n"
        "Кнопки главного меню всегда под рукой — они закреплены внизу экрана. 👇",
        keyboard=kb.exam
    )

from vkbottle_types.events import GroupEventType

@router.raw_event(GroupEventType.MESSAGE_ALLOW, dataclass=dict)
async def on_message_allow(event: dict):
    user_id = event["object"]["user_id"]
    peer_id = user_id
    await get_or_create_user(user_id)
    await bot.api.messages.send(
        peer_id=peer_id,
        message=(
            "👋 Привет! Я бот для подготовки к ЕГЭ и ОГЭ по математике.\n\n"
            "Вот что я умею:\n"
            "📝 Задания — тренируйся по любой теме в удобном темпе\n"
            "🎲 Вариант — реши полный экзаменационный вариант и узнай свой балл\n"
            "🧠 AI Help — разбор решения с объяснением от нейросети\n"
            "📥 Экспорт — скачай вариант в PDF или DOCX\n"
            "📊 Прогресс — смотри статистику и слабые темы\n\n"
            "Кнопки главного меню всегда под рукой — они закреплены внизу экрана. 👇"
        ),
        random_id=0,
    )
    await mark_onboarding_done(user_id)
    await bot.api.messages.send(
        peer_id=peer_id,
        message="Выбери экзамен и начнём! 👇",
        keyboard=kb.exam,
        random_id=0,
    )

@router.message(text=["Мой прогресс", "мой прогресс", "/stats", "прогресс"])
async def show_progress(message: Message):
    await get_or_create_user(message.from_id)
    await message.answer(
        "📊 По какому экзамену показать статистику?",
        keyboard=kb.progress_exam_choice
    )

# Словарь для отображения тем на русском
TOPIC_NAMES = {
    # Задания из tasks.json (старый формат)
    "ordinary_fractions":          "Обыкновенные дроби",
    "decimal_fractions":           "Десятичные дроби",
    "general":                     "Общее",
    "degrees":                     "Степени",
    "arithmetic_square_root":      "Арифметические корни",
    "linear_equations":            "Линейные уравнения",
    "quadratic_equations":         "Квадратные уравнения",
    "probability":                 "Теория вероятностей",
    "linear_inequalities":         "Линейные неравенства",
    "quadratic_inequalities":      "Квадратные неравенства",
    "systems_linear_inequalities": "Системы линейных неравенств",
    # Задания 1–5 (тематические наборы)
    "kvartira":                    "Квартира",
    "uchastok":                    "Участок",
    "listy":                       "Листы бумаги",
    "pech":                        "Печь для бани",
    "plan":                        "План местности",
    "shiny":                       "Шины",
    "tarify":                      "Тарифы",
    # Задание 11
    "linear_function":             "Линейная функция",
    "quadratic_function":          "Квадратичная функция",
    "hyperbola":                   "Обратная пропорциональность",
    "mixed_graphs":                "Смешанные графики",
    # Задания 14–16
    "arithmetic_progression":      "Арифметическая прогрессия",
    "geometric_progression":       "Геометрическая прогрессия",
    "triangles":                   "Треугольники",
    "circles":                     "Окружности",
    "grid":                        "Клетчатая плоскость",
    # Задание 17
    "parallelogram":               "Параллелограмм",
    "trapezoid":                   "Трапеция",
    "rectangle":                   "Прямоугольник",
    "rhombus":                     "Ромб",
    "square":                      "Квадрат",
    "ege_b01_text":     "Простейшие текстовые задачи",
    "ege_b02_units":    "Размеры и единицы измерения",
    "ege_b03_graphs":   "Графики и диаграммы",
    "ege_b04_algebra":  "Преобразование выражений",
    "ege_b05_prob":        "Теория вероятностей",
    "ege_b05_probability": "Теория вероятностей",
    "ege_b06_optimal":  "Выбор оптимального варианта",
    "ege_b07_analysis": "Анализ графиков и таблиц",
    "ege_b08_logic":       "Анализ утверждений",
    "ege_b08_statements":  "Анализ утверждений",
    "ege_b09_area":     "Площадь",
    "ege_b10_planim":                    "Прикладная планиметрия",
    "ege_b11_stereo":                    "Прикладная стереометрия",
    "ege_b12_planim2":                   "Планиметрия",
    "ege_b13_stereo2":                   "Стереометрия",
    # Реальные topic-ключи из БД (задание 10)
    # Задание 10 — Прикладная планиметрия
    "area":                              "Площадь",
    "circle":                            "Окружность",
    "perimeter":                         "Периметр",
    "pythagoras":                        "Теорема Пифагора",
    "similar_triangles":                 "Подобные треугольники",
    "trapezoid_midline":                 "Средняя линия трапеции",
    # Задание 11 — Прикладная стереометрия
    "parallelepiped_prism":              "Параллелепипед/призма",
    "pyramid":                           "Пирамида",
    "cylinder":                          "Цилиндр",
    "cone":                              "Конус",
    "sphere":                            "Шар",
    "polyhedra_other":                   "Многогранники",
    # Задание 12 — Планиметрия
    "angles":                            "Углы",
    "area_pythagor":                     "Площадь. Теорема Пифагора",
    "circle_length":                     "Длина окружности",
    "circles":                           "Окружность",
    "midline_trapezoid":                 "Средняя линия трапеции",
    "quadrilaterals":                    "Четырёхугольники",
    "ratios":                            "Соотношение площадей",
    "regular_polygons":                  "Правильные многоугольники",
    "triangles":                         "Треугольники",
    "trigonometry":                      "Тригонометрия",
    # Задание 13 — Стереометрия
    "parallelepiped":                    "Параллелепипед",
    "prism":                             "Призма",
    # Реальные topic-ключи из БД (задание 11)
    "parallelepiped_prism":              "Параллелепипед/призма",
    "pyramid":                           "Пирамида",
    "cylinder":                          "Цилиндр",
    "cone":                              "Конус",
    "sphere":                            "Шар",
    "polyhedra_other":                   "Многогранники",
    # Реальные topic-ключи из БД (задание 13)
    "parallelepiped":                    "Параллелепипед",
    "ege_b14_fracs":                     "Действия с дробями",
    "ege_b14_fractions":                 "Действия с дробями",
    "ege_b15_percent":                   "Текстовые задачи на проценты",
    "ege_b15_percent_text":              "Текстовые задачи на проценты",
    "ege_b16_calc":                      "Вычисления и преобразования",
    "ege_b16_calculations_transformations": "Вычисления и преобразования",
    "ege_b17_eq":                        "Уравнения",
    "ege_b17_equations":                 "Уравнения",
    "ege_b18_ineq":                      "Числа и неравенства",
    "ege_b19_digits":                    "Цифровая запись числа",
    "ege_b20_word":                      "Текстовая задача",
    "ege_b20_text_problems":             "Текстовая задача",
    "ege_b21_logic":                     "Задачи на смекалку",
    "ege_p01_planim":   "Планиметрия",
    "ege_p02_vectors":  "Векторы",
    "ege_p03_stereo":   "Стереометрия",
    "ege_p04_prob":     "Определение вероятности",
    "ege_p05_prob2":    "Теоремы о вероятностях",
    "ege_p06_eq":       "Простейшие уравнения",
    "ege_p07_expr":     "Значение выражения",
    "ege_p08_deriv":    "Производная и первообразная",
    "ege_p09_applied":  "Задачи с прикладным содержанием",
    "ege_p10_word":     "Текстовые задачи",
    "ege_p11_func":     "Функции",
    "ege_p12_research": "Исследование функций",
    # Часть 2 (развёрнутый ответ)
    "ege_p13_eq":       "Уравнения (развёрнутый ответ)",
    "ege_p14_stereo2":  "Стереометрическая задача",
    "ege_p15_ineq":     "Неравенства",
    "ege_p16_finance":  "Финансовая математика",
    "ege_p17_planim2":  "Планиметрическая задача",
    "ege_p18_param":    "Параметры",
    "ege_p19_numbers":  "Числа и их свойства",
}

EGE_BASE_TASK_MAP = {
    # topic=None для заданий с несколькими топиками — выбирается случайное из всех
    "e1":  (1,  "ege_b01_text",                          "Задание 1 — Простейшие текстовые задачи"),
    "e2":  (2,  "ege_b02_units",                         "Задание 2 — Размеры и единицы измерения"),
    "e3":  (3,  "ege_b03_graphs",                        "Задание 3 — Графики и диаграммы"),
    "e4":  (4,  "ege_b04_algebra",                       "Задание 4 — Преобразование выражений"),
    "e5":  (5,  "ege_b05_probability",                   "Задание 5 — Теория вероятностей"),
    "e6":  (6,  "ege_b06_optimal",                       "Задание 6 — Выбор оптимального варианта"),
    "e7":  (7,  "ege_b07_analysis",                      "Задание 7 — Анализ графиков и таблиц"),
    "e8":  (8,  "ege_b08_statements",                    "Задание 8 — Анализ утверждений"),
    "e9":  (9,  "ege_b09_area",                          "Задание 9 — Площадь"),
    "e10": (10, None,                                    "Задание 10 — Прикладная планиметрия"),
    "e11": (11, None,                                    "Задание 11 — Прикладная стереометрия"),
    "e12": (12, None,                                    "Задание 12 — Планиметрия"),
    "e13": (13, None,                                    "Задание 13 — Стереометрия"),
    "e14": (14, "ege_b14_fractions",                     "Задание 14 — Действия с дробями"),
    "e15": (15, "ege_b15_percent_text",                  "Задание 15 — Текстовые задачи на проценты"),
    "e16": (16, "ege_b16_calculations_transformations",  "Задание 16 — Вычисления и преобразования"),
    "e17": (17, "ege_b17_equations",                     "Задание 17 — Уравнения"),
    "e18": (18, "ege_b18_ineq",                          "Задание 18 — Числа и неравенства"),
    "e19": (19, "ege_b19_digits",                        "Задание 19 — Цифровая запись числа"),
    "e20": (20, "ege_b20_text_problems",                 "Задание 20 — Текстовая задача"),
    "e21": (21, "ege_b21_logic",                         "Задание 21 — Задачи на смекалку"),
}

EGE_PROFILE_TASK_MAP = {
    # Часть 1 — числовые ответы
    "p1":  (1,  "ege_p01_planim",   "Задание 1 — Планиметрия",                   "part1"),
    "p2":  (2,  "ege_p02_vectors",  "Задание 2 — Векторы",                        "part1"),
    "p3":  (3,  "ege_p03_stereo",   "Задание 3 — Стереометрия",                   "part1"),
    "p4":  (4,  "ege_p04_prob",     "Задание 4 — Определение вероятности",        "part1"),
    "p5":  (5,  "ege_p05_prob_th",  "Задание 5 — Теоремы о вероятностях",         "part1"),
    "p6":  (6,  "ege_p06_eq",       "Задание 6 — Простейшие уравнения",           "part1"),
    "p7":  (7,  "ege_p07_expr",     "Задание 7 — Значение выражения",             "part1"),
    "p8":  (8,  "ege_p08_deriv",    "Задание 8 — Производная и первообразная",    "part1"),
    "p9":  (9,  "ege_p09_applied",  "Задание 9 — Задачи с прикладным содержанием","part1"),
    "p10": (10, "ege_p10_word",     "Задание 10 — Текстовые задачи",              "part1"),
    "p11": (11, "ege_p11_functions","Задание 11 — Функции",                       "part1"),
    "p12": (12, "ege_p12_research", "Задание 12 — Исследование функций",          "part1"),
    # Часть 2 — развёрнутый ответ (фото → нейросеть)
    "p13": (13, "ege_p13_eq",       "Задание 13 — Уравнения",                     "part2"),
    "p14": (14, "ege_p14_stereo2",  "Задание 14 — Стереометрическая задача",      "part2"),
    "p15": (15, "ege_p15_ineq",     "Задание 15 — Неравенства",                   "part2"),
    "p16": (16, None,               "Задание 16 — Финансовая математика",         "part2"),
    "p17": (17, "ege_p17_planim2",  "Задание 17 — Планиметрическая задача",       "part2"),
    "p18": (18, "ege_p18_param",    "Задание 18 — Параметры",                     "part2"),
    "p19": (19, "ege_p19_numbers",  "Задание 19 — Числа и их свойства",           "part2"),
}

# Критерии оценивания ЕГЭ профиль часть 2
# max_score — максимальный балл за задание
EGE_PROFILE_PART2_CRITERIA = {
    13: {
        "max_score": 2,
        "criteria": [
            "Верный ответ в обоих пунктах с обоснованием (K1)",
            "Верный ответ только в пункте а или вычислительная ошибка при верном ходе (K2)",
        ]
    },
    14: {
        "max_score": 3,
        "criteria": [
            "Верное доказательство пункта а (K1)",
            "Обоснованный верный ответ в пункте б (K2)",
            "Оба пункта выполнены верно (K3)",
        ]
    },
    15: {
        "max_score": 2,
        "criteria": [
            "Верная последовательность шагов решения (K1)",
            "Обоснованно получен верный ответ (K2)",
        ]
    },
    16: {
        "max_score": 2,
        "criteria": [
            "Верно построена математическая модель (K1)",
            "Обоснованно получен верный ответ (K2)",
        ]
    },
    17: {
        "max_score": 3,
        "criteria": [
            "Верное доказательство пункта а (K1)",
            "Обоснованный верный ответ в пункте б (K2)",
            "Оба пункта выполнены верно (K3)",
        ]
    },
    18: {
        "max_score": 4,
        "criteria": [
            "Задача верно сведена к исследованию параболы и прямых (K1)",
            "Получен промежуток значений a, возможно с ошибкой в граничных точках (K2)",
            "Верное множество значений a с возможной ошибкой в граничных точках (K3)",
            "Обоснованно получен полностью верный ответ (K4)",
        ]
    },
    19: {
        "max_score": 4,
        "criteria": [
            "Верный ответ в пункте а или б (K1)",
            "Верные ответы в пунктах а и б или только в пункте в (K2)",
            "Верный ответ в пункте в и один из пунктов а/б (K3)",
            "Верные ответы во всех трёх пунктах (K4)",
        ]
    },
}

def _progress_bar(accuracy: float, length: int = 8) -> str:
    """Текстовый прогресс-бар: ██░░░░░░"""
    filled = round(accuracy / 100 * length)
    return "█" * filled + "░" * (length - filled)

@router.message(text="ОГЭ")
async def oge_menu(message: Message):
    await message.answer("👇 Выбери раздел:", keyboard=kb.oge)

@router.message(text="ЕГЭ")
async def ege_menu(message: Message):
    await message.answer("👇 Выбери уровень:", keyboard=kb.ege)

@router.message(text="/cancel")
async def cancel_handler(message: Message):
    bot.state_dispenser.dictionary.pop(message.from_id, None)
    await message.answer("Режим AI Help деактивирован.", keyboard=kb.oge)



@router.message(state=TaskStates.p13_a)
async def check_p13_a(message: Message):
    user_id = message.from_id
    peer_id = message.peer_id
    user_answer = message.text.strip()
    correct_a = get_p13_answer_a(user_id)
    correct_b = get_p13_answer_b(user_id)

    retry_kb, help_kb = kb.ege_profile_part2_keyboards["p13"]

    # Проверка через DeepSeek
    prompt = (
        f"Правильный ответ на уравнение: {correct_a}\n"
        f"Ответ ученика: {user_answer}\n"
        f"Являются ли эти два множества решений эквивалентными (математически одинаковыми)? "
        f"Ответь ТОЛЬКО одним словом: да или нет."
    )
    result = await math_helper.ask_math_question(prompt)
    is_correct = "да" in result.lower()

    if is_correct:
        await bot.state_dispenser.set(peer_id, TaskStates.p13_b)
        await bot.api.messages.send(
            peer_id=peer_id,
            message=(
                "✅ Пункт а) — верно!\n\n"
                "Теперь введи ответ на пункт б) — корни в порядке возрастания через точку с запятой:\n"
                f"Например: π/2; π; 3π/2"
            ),
            random_id=0
        )
    else:
        await bot.api.messages.send(
            peer_id=peer_id,
            message="❌ Пункт а) — неверно. Попробуй ещё раз или посмотри правильный ответ:",
            keyboard=retry_kb,
            random_id=0
        )



@router.message(state=TaskStates.p13_b)
async def check_p13_b(message: Message):
    user_id = message.from_id
    peer_id = message.peer_id
    user_answer = message.text.strip()
    correct_b = get_p13_answer_b(user_id)

    retry_kb, help_kb = kb.ege_profile_part2_keyboards["p13"]

    # Нормализация: убираем пробелы вокруг ; и приводим к нижнему регистру
    def normalize(s):
        return ";".join(p.strip() for p in s.replace(",", ";").split(";")).lower()

    if normalize(user_answer) == normalize(correct_b):
        bot.state_dispenser.dictionary.pop(user_id, None)
        await bot.api.messages.send(
            peer_id=peer_id,
            message="✅ Пункт б) — верно! Задание решено полностью 🎉",
            keyboard=kb.ege_p13_success,
            random_id=0
        )
        from app.database import record_attempt
        await record_attempt(user_id, get_task_id(user_id), True)
    else:
        await bot.api.messages.send(
            peer_id=peer_id,
            message=(
                "❌ Пункт б) — неверно.\n"
                "Проверь порядок корней (по возрастанию) и формат записи.\n"
                "Попробуй ещё раз или посмотри правильный ответ:"
            ),
            keyboard=retry_kb,
            random_id=0
        )
@router.message(state=TaskStates.p15)
async def check_p15(message: Message):
    user_id = message.from_id
    peer_id = message.peer_id
    user_answer = message.text.strip()
    correct = get_answer(user_id)

    retry_kb, help_kb = kb.ege_profile_part2_keyboards["p15"]

    # Нормализация: убираем пробелы для сравнения
    def normalize(s):
        return s.replace(" ", "").replace(",", ".").lower()

    if normalize(user_answer) == normalize(str(correct)):
        bot.state_dispenser.dictionary.pop(user_id, None)
        await bot.api.messages.send(
            peer_id=peer_id,
            message="✅ Верно! Задание решено 🎉",
            keyboard=kb.ege_p15_success,
            random_id=0
        )
        await record_attempt(user_id, get_task_id(user_id), True)
    else:
        await bot.api.messages.send(
            peer_id=peer_id,
            message=(
                "❌ Неверно. Попробуй ещё раз или посмотри правильный ответ:\n"
                "Формат ответа: (-∞; 2) ∪ (3; +∞)"
            ),
            keyboard=help_kb,
            random_id=0
        )


@router.message(state=TaskStates.p16)
async def check_p16(message: Message):
    retry_kb, help_kb = kb.ege_profile_part2_keyboards["p16"]
    await check_part2_answer(message, 16, retry_kb, help_kb)


# -----------------------------------------------------------------------
# Callback-обработчик — единая точка входа для message_event
# -----------------------------------------------------------------------


# -----------------------------------------------------------------------
# ЭКСПОРТ ВАРИАНТОВ В VK
# -----------------------------------------------------------------------

VARIANT_EXAM_TITLES = {
    "oge": "ОГЭ",
    "ege_base": "ЕГЭ база",
    "ege_profile": "ЕГЭ профиль",
}


def get_exam_menu_keyboard(exam_type: str):
    if exam_type == "oge":
        return kb.oge
    if exam_type == "ege_base":
        return kb.ege_base
    if exam_type == "ege_profile":
        return kb.ege_profile
    return kb.oge


async def build_random_variant_for_export(exam_type: str) -> list[dict]:
    """
    Собрать случайный вариант для экспорта.

    Сначала пробуем универсальную функцию get_random_exam_variant.
    Если её нет в database.py, для ОГЭ используем старую get_random_variant().
    """
    try:
        from app.database import get_random_exam_variant
        return await get_random_exam_variant(exam_type)
    except Exception:
        if exam_type == "oge":
            from app.database import get_random_variant
            return await get_random_variant()
        return []

async def send_vk_document(peer_id: int, file_path: Path, title: str = ""):
    import ssl as _ssl
    import aiohttp as _aio
    import json as _json

    file_path = Path(file_path)
    title = title or file_path.name

    _ctypes = {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    content_type = _ctypes.get(file_path.suffix.lower(), "application/octet-stream")

    _ssl_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE

    MAX_RETRIES = 3

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            upload_server = await bot.api.docs.get_messages_upload_server(
                peer_id=peer_id, type="doc"
            )
            upload_url = upload_server.upload_url

            connector = _aio.TCPConnector(ssl=_ssl_ctx)
            async with _aio.ClientSession(connector=connector) as session:
                with open(file_path, "rb") as fobj:
                    form = _aio.FormData()
                    form.add_field(
                        "file", fobj,
                        filename=file_path.name,
                        content_type=content_type,
                    )
                    async with session.post(upload_url, data=form) as resp:
                        raw = await resp.text()

            if not raw or not raw.strip():
                print(f"⚠️  попытка {attempt}/{MAX_RETRIES} — пустой ответ VK")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2)
                    continue
                raise RuntimeError("VK upload server вернул пустой ответ")

            upload_result = _json.loads(raw)

            if "file" not in upload_result:
                raise RuntimeError(f"Неожиданный ответ VK: {upload_result}")

            save_result = await bot.api.docs.save(
                file=upload_result["file"],
                title=title,
            )

            doc = getattr(save_result, "doc", None)
            if doc is None and isinstance(save_result, list) and save_result:
                doc = save_result[0]
            if doc is None:
                raise RuntimeError(f"docs.save вернул неожиданный ответ: {save_result}")

            attachment = f"doc{doc.owner_id}_{doc.id}"

            await bot.api.messages.send(
                peer_id=peer_id,
                message=f"📎 Готово! Отправляю файл: {title}",
                attachment=attachment,
                random_id=0,
            )
            return  # ← успех, выходим

        except Exception as e:
            print(f"⚠️  попытка {attempt}/{MAX_RETRIES} — {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2)
                continue
            # Все попытки исчерпаны
            await bot.api.messages.send(
                peer_id=peer_id,
                message=(
                    f"⚠️ Не удалось отправить файл в VK.\n"
                    f"Файл создан локально: {file_path}\n"
                    f"Ошибка: {e}"
                ),
                random_id=0,
            )


async def export_variant_to_vk(
    peer_id: int,
    user_id: int,
    exam_type: str,
    variant: list[dict],
    fmt: str = "pdf",
    include_answers: bool = False,
):
    """Создать PDF/DOCX варианта и отправить файл прямо в VK."""
    if not variant:
        await bot.api.messages.send(
            peer_id=peer_id,
            message="⚠️ Вариант не найден. Сначала начни решение варианта или скачай случайный вариант из меню экзамена.",
            random_id=0,
        )
        return

    import random

    exam_title = VARIANT_EXAM_TITLES.get(exam_type, exam_type)
    variant_number = random.randint(1, 999)

    outdir = Path("app") / "exports"
    outdir.mkdir(parents=True, exist_ok=True)

    file_path = export_variant_from_dicts(
        items=variant,
        exam_type=exam_type,
        fmt=fmt,
        include_answers=include_answers,
        variant_number=variant_number,
        outdir=outdir,
    )

    suffix_str = " с ответами" if include_answers else ""
    title = f"{exam_title} Вариант №{variant_number}{suffix_str}.{fmt}"
    await send_vk_document(peer_id, file_path, title=title)


@router.raw_event(GroupEventType.MESSAGE_EVENT)
async def handle_callback(event: dict):
    obj      = event.get("object", {})
    user_id  = obj.get("user_id")
    peer_id  = obj.get("peer_id")
    event_id = obj.get("event_id")
    payload  = obj.get("payload") or {}
    cmd = payload.get("cmd", "")

    # Если VK прислал тот же callback второй раз — только подтверждаем событие
    # и ничего больше не отправляем.
    if is_duplicate_callback(user_id, cmd):
        await answer_callback(event_id, user_id, peer_id)
        return

    await answer_callback(event_id, user_id, peer_id)

    # Сначала проверяем вариантные команды
    if await handle_variant_callbacks(cmd, peer_id, user_id):
        return

    async def send(text="", keyboard=None):
        kwargs = {"peer_id": peer_id, "message": text, "random_id": 0}
        if keyboard:
            kwargs["keyboard"] = keyboard
        await bot.api.messages.send(**kwargs)

    # ── Меню экспорта варианта ───────────────────────────────────────
    if cmd == "export_menu_oge":
        await send("Выбери формат экспорта ОГЭ:", keyboard=kb.export_menu_oge)
        return True

    if cmd == "export_menu_ege_base":
        await send("Выбери формат экспорта ЕГЭ база:", keyboard=kb.export_menu_ege_base)
        return True

    if cmd == "export_menu_ege_profile":
        await send("Выбери формат экспорта ЕГЭ профиль:", keyboard=kb.export_menu_ege_profile)
        return True

    # ── Экспорт текущего варианта ────────────────────────────────────
    if cmd in {"variant_export_pdf", "variant_export_pdf_answers", "variant_export_docx", "variant_export_docx_answers"}:
        variant = ctx.get(f"variant_{user_id}") or []
        exam_type = ctx.get(f"variant_exam_type_{user_id}") or (variant[0].get("exam_type") if variant else "oge")
        fmt = "docx" if "docx" in cmd else "pdf"
        include_answers = cmd.endswith("_answers")
        await send("⏳ Формирую файл варианта: " + ("с ответами..." if include_answers else "без ответов..."))
        await export_variant_to_vk(peer_id, user_id, exam_type, variant, fmt=fmt, include_answers=include_answers)
        return True

    # ── Экспорт случайного варианта из меню экзамена ─────────────────
    m = re.fullmatch(r"export_variant_(oge|ege_base|ege_profile)_(pdf|docx)(_answers)?", cmd)
    if m:
        exam_type, fmt, answers_suffix = m.groups()
        include_answers = bool(answers_suffix)
        exam_title = VARIANT_EXAM_TITLES.get(exam_type, exam_type)

        await send(
            f"⏳ Собираю случайный вариант {exam_title} и формирую файл: "
            + ("с ответами..." if include_answers else "без ответов...")
        )

        variant = await build_random_variant_for_export(exam_type)
        if not variant:
            await send(
                f"⚠️ В базе пока недостаточно заданий для варианта {exam_title}.",
                keyboard=get_exam_menu_keyboard(exam_type)
            )
            return True

        await export_variant_to_vk(peer_id, user_id, exam_type, variant, fmt=fmt, include_answers=include_answers)
        return True

    # ---- Навигация ----
    if cmd == "back_to_tasks_oge":
        await send("Выбери раздел ОГЭ:", keyboard=kb.oge)

    elif cmd == "oge_part1":
        await send("Первая часть ОГЭ:", keyboard=kb.oge_part1)

    elif cmd == "oge_algebra":
        await send("Алгебра — задания 1–8:", keyboard=kb.oge_algebra)

    elif cmd == "oge_algebra2":
        await send("Алгебра — задания 9–14:", keyboard=kb.oge_algebra2)

    elif cmd == "oge_geo":
        await send("Геометрия — задания 15–19:", keyboard=kb.oge_geo)

    elif cmd == "oge_part2":
        await send("Вторая часть ОГЭ — задания 20–25:", keyboard=kb.oge_part2)
        # ── ЕГЭ навигация ──────────────────────────────────────────────────────
    elif cmd == "back_to_ege":
        await send("Выбери уровень ЕГЭ:", keyboard=kb.ege)

    elif cmd == "ege":
        await send("👇 Выбери уровень:", keyboard=kb.ege)

    elif cmd == "ege_base":
        await send("ЕГЭ База — задания 1–21:", keyboard=kb.ege_base)
    elif cmd == "ege_base1":
        await send("ЕГЭ База — задания 1–7:", keyboard=kb.ege_base1)
    elif cmd == "ege_base2":
        await send("ЕГЭ База — задания 8–14:", keyboard=kb.ege_base2)
    elif cmd == "ege_base3":
        await send("ЕГЭ База — задания 15–21:", keyboard=kb.ege_base3)

    elif cmd == "ege_profile":
        await send("ЕГЭ Профиль — выбери часть:", keyboard=kb.ege_profile)
    elif cmd == "ege_p_part1_menu":
        await send("ЕГЭ Профиль — Часть 1:", keyboard=kb.ege_p_part1_menu)

    # ── ЕГЭ база: выдача задания e1–e21 ────────────────────────────────────
    elif cmd in kb.ege_base_keyboards:
        task_num, topic, label = EGE_BASE_TASK_MAP[cmd]
        await send_db_task(
            peer_id, user_id, "ege_base", task_num, topic,
            getattr(TaskStates, cmd),
            f"📝 {label}\n\n",
            show_photo_hint=False  # ← добавь
        )



    elif cmd == "ege_p_part1":
        await send("ЕГЭ Профиль — Часть 1 (задания 1–6):", keyboard=kb.ege_p_part1)

    elif cmd == "ege_p_part1b":
        await send("ЕГЭ Профиль — Часть 1 (задания 7–12):", keyboard=kb.ege_p_part1b)

    elif cmd == "ege_p_part2":
        await send(
            "ЕГЭ Профиль — Часть 2 (задания 13–19):",
            keyboard=kb.ege_p_part2
        )


    elif cmd == "ai_help":
        task_ctx = get_task_context(user_id)

        # Определяем тип экзамена из task_meta (заполняется при любом задании)
        task_meta = get_task_meta(user_id)
        if task_meta:
            exam_type_now = task_meta[0]  # ("oge"/"ege_base"/"ege_profile", task_num, topic)
        else:
            exam_type_now = ctx.get(f"variant_exam_type_{user_id}") or "oge"

        ctx.set(f"ai_help_exam_type_{user_id}", exam_type_now)
        await bot.state_dispenser.set(peer_id, TaskStates.AI_HELP_MODE)
        if task_ctx:
            await send(
                f"🧠 DeepSeek AI подключён! Я вижу задачу:\n\n"
                f"{task_ctx}\n\n"
                f"Напиши 'как решить?' или задай любой вопрос.\n"
                f"Для выхода нажми кнопку ниже.",
                keyboard=kb.ai_cancel_kb
            )
        else:
            await send(
                "🧠 Режим DeepSeek AI активирован! Задай любой вопрос.\n"
                "Для выхода нажми кнопку ниже.",
                keyboard=kb.ai_cancel_kb
            )

    elif cmd == "ai_cancel":
        bot.state_dispenser.dictionary.pop(user_id, None)
        await send(
            "Режим AI Help деактивирован.",
            keyboard=_get_return_kb(user_id)
        )

    elif cmd.startswith("show_right_e") or cmd.startswith("show_right_p"):
        task_cmd = cmd.replace("show_right_", "")

        if task_cmd == "p13":
            bot.state_dispenser.dictionary.pop(user_id, None)
            answer_a = get_p13_answer_a(user_id)
            answer_b = get_p13_answer_b(user_id)
            await send(
                f"✅ Правильный ответ:\nа) {answer_a}\nб) {answer_b}\n\n"
                f"⚠️ Задание не засчитано.",
                keyboard=kb.ege_p13_success
            )
            return

        if task_cmd == "p15":
            bot.state_dispenser.dictionary.pop(user_id, None)
            correct = get_answer(user_id)
            await send(
                f"✅ Правильный ответ: {correct}\n\n⚠️ Задание не засчитано.",
                keyboard=kb.ege_p15_success
            )
            return

        # Определяем клавиатуру "ещё задание" для нужного раздела
        if task_cmd in kb.ege_base_keyboards:
            retry_kb, _ = kb.ege_base_keyboards[task_cmd]
        elif task_cmd in kb.ege_profile_part1_keyboards:
            retry_kb, _ = kb.ege_profile_part1_keyboards[task_cmd]
        elif task_cmd in kb.ege_profile_part2_keyboards:
            retry_kb, _ = kb.ege_profile_part2_keyboards[task_cmd]
        else:
            retry_kb = kb.ege_base

        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=retry_kb
        )

    # ── ЕГЭ профиль часть 1: числовые ответы p1–p12 ───────────────────────
    elif cmd in kb.ege_profile_part1_keyboards:
        task_num, topic, label, _ = EGE_PROFILE_TASK_MAP[cmd]
        await send_db_task(
            peer_id, user_id, "ege_profile", task_num, topic,
            getattr(TaskStates, cmd),
            f"📝 ЕГЭ Профиль · {label}\n\n",
            show_photo_hint=False
        )


    elif cmd in kb.ege_profile_part2_keyboards and cmd not in ("p13", "p15", "p16"):
        task_num, topic, label, _ = EGE_PROFILE_TASK_MAP[cmd]
        await send_db_task(
            peer_id, user_id, "ege_profile", task_num, topic,
            getattr(TaskStates, cmd),
            f"📝 ЕГЭ Профиль · {label}\n\n",
            show_photo_hint=True
        )

    elif cmd == "p16":
        from app.database import get_random_task as _get
        task = await _get("ege_profile", 16, None)
        if not task:
            await send("⚠️ Заданий по этой теме пока нет. Скоро добавим!", keyboard=kb.ege_p_part2)
            return
        set_answer(user_id, task["answer"])
        set_task_context(user_id, task.get("question") or "Задание №16")
        set_task_id(user_id, task["id"])
        set_task_meta(user_id, "ege_profile", 16, task.get("topic") or "financial_math")
        await bot.state_dispenser.set(peer_id, TaskStates.p16)
        text = (
            "📝 ЕГЭ Профиль · Задание 16 — Финансовая математика\n\n"
            + (task.get("question") or "Реши задание на картинке.")
            + "\n\n📸 Пришли фото своего решения — нейросеть проверит его!\n"
              "💬 Или введи числовой ответ, если хочешь проверить только итог."
        )
        await bot.api.messages.send(peer_id=peer_id, message=text, random_id=0)
        if task.get("image_path"):
            await send_photo(peer_id, task["image_path"])

    elif cmd == "p13":
        await send("Выбери тему задания №13 ЕГЭ профиль:", keyboard=kb.ege_p13)

    elif cmd in {"p13_exp", "p13_trig", "p13_mix", "p13_rand"}:
        topic_map = {
            "p13_exp": "exponential_equations",
            "p13_trig": "trigonometric_equations",
            "p13_mix": "mixed_equations",
            "p13_rand": None,
        }
        topic = topic_map[cmd]
        from app.database import get_random_task as _get
        task = await _get("ege_profile", 13, topic)
        if not task:
            await send("⚠️ Заданий по этой теме пока нет. Скоро добавим!", keyboard=kb.ege_p_part2)
            return
        # Разбиваем ответ на а) и б)
        answer_full = task["answer"]
        parts = answer_full.split("\n")
        answer_a = parts[0].replace("а) ", "").strip() if len(parts) > 0 else ""
        answer_b = parts[1].replace("б) ", "").strip() if len(parts) > 1 else ""
        set_p13_answers(user_id, answer_a, answer_b)
        set_task_context(user_id, task.get("question") or "Задание №13")
        set_task_id(user_id, task["id"])
        set_task_meta(user_id, "ege_profile", 13, topic or "mixed")
        await bot.state_dispenser.set(peer_id, TaskStates.p13_a)
        text = (
                "📝 ЕГЭ Профиль · Задание 13 — Уравнения\n\n"
                + (task.get("question") or "Реши задание на картинке.")
                + "\n\n📸 Пришли фото своего решения — нейросеть проверит его!\n"
                  "💬 Или введи ответ текстом.\n\n"
                  "Сначала введи ответ на пункт а) в формате:\n"
                  "πk; π/3 + 2πm,  k,m∈ℤ"
        )
        await bot.api.messages.send(peer_id=peer_id, message=text, random_id=0)
        if task.get("image_path"):
            await send_photo(peer_id, task["image_path"])

    # ── ЕГЭ профиль задание 15: неравенства ───────────────────────────────
    elif cmd == "p15":
        await send("Выбери тему задания №15 ЕГЭ профиль:", keyboard=kb.ege_p15)

    elif cmd in {"p15_exp", "p15_log", "p15_rand"}:
        topic_map = {
            "p15_exp":  "exponential_inequalities",
            "p15_log":  "logarithmic_inequalities",
            "p15_rand": None,
        }
        topic = topic_map[cmd]
        from app.database import get_random_task as _get
        task = await _get("ege_profile", 15, topic)
        if not task:
            await send("⚠️ Заданий по этой теме пока нет. Скоро добавим!", keyboard=kb.ege_p_part2)
            return
        set_answer(user_id, task["answer"])
        set_task_context(user_id, task.get("question") or "Задание №15")
        set_task_id(user_id, task["id"])
        set_task_meta(user_id, "ege_profile", 15, topic or "exponential_inequalities")
        await bot.state_dispenser.set(peer_id, TaskStates.p15)
        text = (
            "📝 ЕГЭ Профиль · Задание 15 — Неравенства\n\n"
            + (task.get("question") or "Реши неравенство. Запиши ответ в виде промежутка.")
            + "\n\n📸 Пришли фото своего решения — нейросеть проверит его!\n"
              "💬 Или введи ответ в виде промежутка, например: (-∞; 2) ∪ (3; +∞)"
        )
        await bot.api.messages.send(peer_id=peer_id, message=text, random_id=0)
        if task.get("image_path"):
            await send_photo(peer_id, task["image_path"])



    # ---- Прогресс ----
    elif cmd == "my_stats":
        await get_or_create_user(user_id)
        await send(
            "📊 По какому экзамену показать статистику?",
            keyboard=kb.progress_exam_choice
        )

    elif cmd in {"progress_oge", "progress_ege_base", "progress_ege_profile", "progress_all"}:
        await get_or_create_user(user_id)
        exam_map = {
            "progress_oge": "oge",
            "progress_ege_base": "ege_base",
            "progress_ege_profile": "ege_profile",
            "progress_all": None,
        }
        exam_type = exam_map[cmd]
        await send_progress_chart(peer_id, user_id, bot.api, exam_type=exam_type)

    # ---- Набор 1-5: показать верный ответ ----
    elif cmd.startswith("set_show_right_"):
        topic_cmd_hint = cmd[len("set_show_right_"):]
        correct_raw    = get_answer(user_id)
        variants       = [v.strip() for v in str(correct_raw).split("|")]
        display        = variants[0] if len(variants) == 1 else " или ".join(variants)
        tasks_set      = ctx.get(f"set_{user_id}") or []
        pos            = ctx.get(f"set_pos_{user_id}") or 0
        topic_name     = SET_TOPIC_NAMES.get(topic_cmd_hint, "")
        next_pos       = pos + 1
        await send(f"✅ Верный ответ: {display}\n\nПереходим к следующему заданию.")
        if next_pos < len(tasks_set):
            ctx.set(f"set_pos_{user_id}", next_pos)
            await send_set_task(peer_id, user_id, tasks_set, next_pos, topic_name)
        else:
            bot.state_dispenser.dictionary.pop(user_id, None)
            await send(f"🎉 Набор завершён! Тема «{topic_name}».", keyboard=kb.make_set_result_kb(topic_cmd_hint))

    # ---- Набор 1-5: пропустить задание ----
    elif cmd.startswith("set_skip_"):
        topic_cmd_hint = cmd[len("set_skip_"):]
        tasks_set      = ctx.get(f"set_{user_id}") or []
        pos            = ctx.get(f"set_pos_{user_id}") or 0
        topic_name     = SET_TOPIC_NAMES.get(topic_cmd_hint, "")
        next_pos       = pos + 1
        if next_pos < len(tasks_set):
            ctx.set(f"set_pos_{user_id}", next_pos)
            await send(f"➡️ Переходим к заданию {next_pos + 1} из {len(tasks_set)}:")
            await send_set_task(peer_id, user_id, tasks_set, next_pos, topic_name)
        else:
            bot.state_dispenser.dictionary.pop(user_id, None)
            await send(f"🎉 Набор завершён! Тема «{topic_name}».", keyboard=kb.make_set_result_kb(topic_cmd_hint))

    # ---- Набор 1-5: справочник ----
    elif cmd.startswith("set_show_ref_"):
        await send(
            "📖 Памятка по форматам бумаги:\n"
            "• А0 = 1189×841 мм (площадь 1 кв.м)\n"
            "• А1 = 841×594 мм\n"
            "• А2 = 594×420 мм\n"
            "• А3 = 420×297 мм\n"
            "• А4 = 297×210 мм\n"
            "• А5 = 210×148 мм\n"
            "• А6 = 148×105 мм\n"
            "• Каждый следующий формат = предыдущий ÷ 2\n"
            "• Площадь АN = 1 / 2ᴺ кв.м\n"
            "• Из А0 получается 2ᴺ листов формата АN"
        )



    # ---- Меню заданий ----
    elif cmd == "n6":
        await send("Выбери тему из задания №6:", keyboard=kb.oge_n6)
    elif cmd == "n8":
        await send("Выбери тему из задания №8:", keyboard=kb.oge_n8)
    elif cmd == "n9":
        await send("Выбери тему из задания №9:", keyboard=kb.oge_n9)

    elif cmd == "n11":
        await send("📈 Задание №11 — Графики функций\nВыбери тему:", keyboard=kb.oge_n11)

    # ── Задание 11: линейная функция ──────────────────────────
    elif cmd == "n11_linear":
        await send_db_task(peer_id, user_id, "oge", 11, "linear_function",
                            TaskStates.n11_linear,
                        "📈 Задание 11 — Линейная функция y = kx + b\n\n")


    elif cmd == "show_right_n11_linear":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n11_linear
        )
    elif cmd == "show_help_n11_linear":
        await send(
              "📖 Памятка — Линейная функция y = kx + b:\n"
              "• k > 0 → прямая возрастает (наклон вправо-вверх)\n"
              "• k < 0 → прямая убывает (наклон вправо-вниз)\n"
              "• b > 0 → пересекает ось Y выше нуля\n"
              "• b < 0 → пересекает ось Y ниже нуля\n"
              "• b = 0 → прямая проходит через начало координат\n"
              "• y = b (k=0) — горизонтальная прямая"
          )

    # ── Задание 11: квадратичная функция ──────────────────────
    elif cmd == "n11_quadratic":
         await send_db_task(peer_id, user_id, "oge", 11, "quadratic_function",
                             TaskStates.n11_quadratic,
                             "📈 Задание 11 — Квадратичная функция y = ax² + bx + c\n\n")


    elif cmd == "show_right_n11_quadratic":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n11_quadratic
        )
    elif cmd == "show_help_n11_quadratic":
         await send(
              "📖 Памятка — Парабола y = ax² + bx + c:\n"
              "• a > 0 → ветви вверх (∪)\n"
              "• a < 0 → ветви вниз (∩)\n"
              "• c = f(0) → точка пересечения с осью Y\n"
              "  c > 0 → выше нуля; c < 0 → ниже нуля\n"
              "• Ось симметрии: x = −b / (2a)"
          )

    # ── Задание 11: обратная пропорциональность ───────────────
    elif cmd == "n11_hyperbola":
        await send_db_task(peer_id, user_id, "oge", 11, "hyperbola",
                             TaskStates.n11_hyperbola,
                             "📈 Задание 11 — Обратная пропорциональность y = k/x\n\n")


    elif cmd == "show_right_n11_hyperbola":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n11_hyperbola
        )
    elif cmd == "show_help_n11_hyperbola":
        await send(
              "📖 Памятка — Гипербола y = k/x:\n"
              "• k > 0 → ветви в I и III четвертях\n"
              "• k < 0 → ветви во II и IV четвертях\n"
              "• |k| больше → ветви дальше от начала координат\n"
              "• y = 1/(kx) — гипербола, «сжатая» к осям"
          )

     # ── Задание 11: смешанные задания ─────────────────────────
    elif cmd == "n11_mixed":
        await send_db_task(peer_id, user_id, "oge", 11, "mixed_graphs",
                             TaskStates.n11_mixed,
                             "📈 Задание 11 — Смешанные типы функций\n\n")


    elif cmd == "show_right_n11_mixed":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n11_mixed
        )
    elif cmd == "show_help_n11_mixed":
        await send(
              "📖 Типы функций в задании:\n"
              "• Прямая:  y = kx + b\n"
              "• Парабола: y = ax² + bx + c  (∪ или ∩)\n"
              "• Гипербола: y = k/x  (I+III или II+IV)\n"
              "• Корень: y = √x  (только x ≥ 0, возрастает)\n"
              "Сначала определи тип по форме графика,\n"
              "затем уточни знаки из формулы."
          )

    # ── Задание 11: случайная тема ────────────────────────────
    elif cmd == "n11_random":
        import random as _r
        _topic = _r.choice(["linear_function", "quadratic_function",
                              "hyperbola", "mixed_graphs"])
        _state = {
              "linear_function":   TaskStates.n11_linear,
              "quadratic_function": TaskStates.n11_quadratic,
              "hyperbola":         TaskStates.n11_hyperbola,
              "mixed_graphs":      TaskStates.n11_mixed,
        }[_topic]
        await send_db_task(peer_id, user_id, "oge", 11, _topic, _state,
                             "📈 Задание 11 — Случайный тип функции\n\n")

    #Задание 12
    elif cmd == "n12":
        await send_db_task(
            peer_id, user_id,
            "oge", 12, "general",
            TaskStates.n12,
            intro_text="📐 Задание 12 — «Расчёты по формулам»\nПодставьте данные в формулу и вычислите результат."
        )


    elif cmd == "show_right_n12":
        set_peeked(user_id, True)  # ← ставим флаг
        ans = get_answer(user_id) or "не найден"
        await send(
            f"✅ Правильный ответ: {ans}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n12  # ← показываем клавиатуру
        )

    elif cmd == "show_help_n12":
        await send(
            "📖 Справочник: Задание 12 — Расчёты по формулам\n\n"
            "Алгоритм решения:\n"
            "1️⃣ Выпишите формулу и обозначьте все известные величины.\n"
            "2️⃣ Определите, что именно нужно найти.\n"
            "3️⃣ Если нужно найти не ту переменную, которая стоит в левой части, "
            "выразите её через остальные (обратная задача).\n"
            "4️⃣ Подставьте числа и вычислите результат.\n\n"
            "⚠️ Следите за единицами измерения и знаками (минус у температуры).\n"
            "💡 Дробные ответы вводите через запятую: например, −9,4 или 0,0196."
        )

    elif cmd == "n13":
        await send("Выбери тему из задания №13:", keyboard=kb.oge_n13)



    elif cmd == "n14":
        await send("Выбери тему задания №14:", keyboard=kb.oge_n14)

    elif cmd == "arithmetic_progression":
        await send_db_task(
            peer_id, user_id,
            "oge", 14, "arithmetic_progression",
            TaskStates.arith_prog,
            "📈 Задание 14 — Арифметическая прогрессия\n\n"
        )

    elif cmd == "show_right_arith_prog":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            "⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_arith_prog
        )

    elif cmd == "show_help_arith_prog":
        await send(
            "📖 Справочник — Арифметическая прогрессия\n\n"
            "Формулы:\n"
            "• n-й член:  aₙ = a₁ + d·(n − 1)\n"
            "• Разность:  d = aₙ − aₙ₋₁\n"
            "• Сумма первых n членов:\n"
            "  Sₙ = n·(a₁ + aₙ) / 2\n"
            "  Sₙ = n·(2a₁ + d·(n − 1)) / 2\n\n"
            "Признак арифм. прогрессии:\n"
            "  aₙ₊₁ − aₙ = const (одинаковая разность)"
        )

    elif cmd == "geometric_progression":
        await send_db_task(
            peer_id, user_id,
            "oge", 14, "geometric_progression",
            TaskStates.geom_prog,
            "📉 Задание 14 — Геометрическая прогрессия\n\n"
        )

    elif cmd == "show_right_geom_prog":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            "⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_geom_prog
        )

    elif cmd == "show_help_geom_prog":
        await send(
            "📖 Справочник — Геометрическая прогрессия\n\n"
            "Формулы:\n"
            "• n-й член:  bₙ = b₁ · qⁿ⁻¹\n"
            "• Знаменатель:  q = bₙ / bₙ₋₁\n"
            "• Сумма первых n членов (q ≠ 1):\n"
            "  Sₙ = b₁ · (qⁿ − 1) / (q − 1)\n\n"
            "Признак геом. прогрессии:\n"
            "  bₙ₊₁ / bₙ = const (одинаковый знаменатель)\n\n"
            "💡 Если масса/количество уменьшается вдвое каждые T минут,\n"
            "то за t минут делений = t / T,\n"
            "итоговое значение = начальное / 2^(t/T)"
        )

    # ---- Задание 6: Обыкновенные дроби ----
    elif cmd == "ordinary_fractions":
        task = random.choice(task6_ordinary_fractions)
        set_answer(user_id, task["answer"])
        set_task_context(user_id, task['question'])
        set_task_meta(user_id, "oge", 6, "ordinary_fractions")
        await bot.state_dispenser.set(peer_id, TaskStates.task6_ordinary)
        await send(f"Вот тебе задачка: {task['question']}\nНапиши ответ в виде десятичной дроби.")

    elif cmd == "show_right_ordinary":
        set_peeked(user_id, True)
        await send(f"Правильный ответ: {get_answer(user_id) or 'не найден'}")

    elif cmd == "show_help_ordinary":
        await send(
            "📖 Справочник — Обыкновенные дроби\n\n"
            "Действия с дробями:\n"
            "• Сложение/вычитание: привести к общему знаменателю\n"
            "• Умножение: числитель × числитель, знаменатель × знаменатель\n"
            "• Деление: умножить на перевёрнутую дробь\n"
            "• Смешанное число → неправильная дробь:\n"
            "  2¾ = (2·4 + 3)/4 = 11/4\n\n"
            "💡 Ответ вводи в виде десятичной дроби через запятую: 0,75"
        )

    # ---- Задание 6: Десятичные дроби ----
    elif cmd == "decimal_fractions":
        task = random.choice(task6_decimal_fractions)
        set_answer(user_id, task["answer"])
        set_task_context(user_id, task['question'])
        set_task_meta(user_id, "oge", 6, "decimal_fractions")
        await bot.state_dispenser.set(peer_id, TaskStates.task6_decimal)
        await send(f"Вот тебе задачка: {task['question']}\nНапиши ответ в виде десятичной дроби.")

    elif cmd == "show_right_decimal":
        set_peeked(user_id, True)
        await send(f"Правильный ответ: {get_answer(user_id) or 'не найден'}")

    elif cmd == "show_help_decimal":
        await send(
            "📖 Справочник — Десятичные дроби\n\n"
            "• Сложение/вычитание: выравнивай запятые в столбик\n"
            "• Умножение: перемножь как целые, затем отсчитай знаки после запятой\n"
            "• Деление на 10, 100, 1000: сдвинь запятую влево\n"
            "• Умножение на 10, 100, 1000: сдвинь запятую вправо\n\n"
            "Перевод обыкновенной в десятичную:\n"
            "  3/4 = 3 ÷ 4 = 0,75\n"
            "  1/8 = 0,125\n\n"
            "💡 Ответ вводи через запятую: 3,14 (не точку!)"
        )

    # ---- Задание 7 ----
    elif cmd == "n7":
        await send_db_task(
            peer_id, user_id, "oge", 7, "numbers_coordinate_line",
            TaskStates.task7,
            intro_text="",
            show_photo_hint=False,
        )
        await send("Выбери верный вариант ответа и напиши в чат числом.")

    elif cmd == "show_right_task7":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"Выбери, что сделать дальше:",
            keyboard=kb.retry_or_menu_task7
        )

    elif cmd == "show_help_task7":
        await send(
            "📖 Справочник — Задание 7: Числа на координатной прямой\n\n"
            "Порядок чисел:\n"
            "• Любое отрицательное < любого положительного\n"
            "• Чем правее на прямой — тем больше число\n"
            "• |a| — расстояние от нуля: |−3| = 3\n\n"
            "Сравнение дробей:\n"
            "• Привести к общему знаменателю или перевести в десятичные\n"
            "• √2 ≈ 1,41;  √3 ≈ 1,73;  π ≈ 3,14\n\n"
            "Степени:\n"
            "• (−2)² = 4  (чётная степень → положительный результат)\n"
            "• (−2)³ = −8 (нечётная → сохраняет знак)"
        )

    # ---- Задание 8: Степени ----
    elif cmd == "task8_degrees":
        set_task_meta(user_id, "oge", 8, "degrees")
        await send_db_task(
            peer_id, user_id, "oge", 8, "degrees",
            TaskStates.task8_degrees,
            "✏️ Задание №8 ОГЭ — Степенные выражения\n\n",
            show_photo_hint=False
        )


    # ── Задание 8 — показать правильный ответ ────────────────────────────────

    elif cmd == "show_right_task8_degrees":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or '—'}\n\n"
            "⚠️ Следующий ответ не будет засчитан.",
            keyboard=kb.retry_or_menu_task8_degrees
        )


    elif cmd == "show_right_task8_arithmetic_square_root":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or '—'}\n\n"
            "⚠️ Следующий ответ не будет засчитан.",
            keyboard=kb.retry_or_menu_task8_arithmetic_square_root
        )

    elif cmd == "show_help_task8_degrees":
        await send(
            "📖 Справочник — Задание 8: Степени\n\n"
            "Основные свойства:\n"
            "• aᵐ · aⁿ = aᵐ⁺ⁿ\n"
            "• aᵐ / aⁿ = aᵐ⁻ⁿ\n"
            "• (aᵐ)ⁿ = aᵐⁿ\n"
            "• (a · b)ⁿ = aⁿ · bⁿ\n"
            "• a⁰ = 1  (при a ≠ 0)\n"
            "• a⁻ⁿ = 1 / aⁿ\n\n"
            "Стандартный вид числа:\n"
            "  a · 10ⁿ, где 1 ≤ a < 10\n"
            "  Пример: 0,00045 = 4,5 · 10⁻⁴"
        )

    # ---- Задание 8: Корни ----
    # Стало — из БД:


    elif cmd == "task8_arithmetic_square_root":
        set_task_meta(user_id, "oge", 8, "arithmetic_square_root")
        await send_db_task(
            peer_id, user_id, "oge", 8, "arithmetic_square_root",
            TaskStates.task8_arithmetic_square_root,
            "✏️ Задание №8 ОГЭ — Арифметические корни\n\n",
            show_photo_hint=False
        )



    elif cmd == "show_help_task8_arithmetic_square_root":
        await send(
            "📖 Справочник — Задание 8: Арифметические корни\n\n"
            "Свойства квадратного корня:\n"
            "• √(a · b) = √a · √b\n"
            "• √(a / b) = √a / √b\n"
            "• (√a)² = a  (при a ≥ 0)\n"
            "• √(a²) = |a|\n\n"
            "Табличные значения:\n"
            "  √4=2, √9=3, √16=4, √25=5\n"
            "  √36=6, √49=7, √64=8, √81=9, √100=10\n\n"
            "Вынесение за знак корня:\n"
            "  √12 = √(4·3) = 2√3\n"
            "  √75 = √(25·3) = 5√3"
        )

    # ---- Задание 9: Линейные уравнения ----
    elif cmd == "linear_equations":
        await send_db_task(
            peer_id, user_id, "oge", 9, "n09_linear",
            TaskStates.task9_linear,
            intro_text="",
            show_photo_hint=False,
        )
        await send("Напиши ответ числом.")

    elif cmd == "show_right_linear":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"Выбери, что сделать дальше:",
            keyboard=kb.retry_or_menu_linear
        )

    elif cmd == "show_help_linear":
        await send(
            "📖 Справочник — Задание 9: Линейные уравнения\n\n"
            "Алгоритм решения ax + b = 0:\n"
            "1️⃣ Перенеси все с x влево, числа — вправо\n"
            "2️⃣ Раскрой скобки и приведи подобные\n"
            "3️⃣ x = −b / a\n\n"
            "Примеры:\n"
            "  2x − 6 = 0  →  x = 3\n"
            "  3(x − 1) = 2x + 5  →  3x − 3 = 2x + 5  →  x = 8\n\n"
            "💡 Проверь подстановкой в исходное уравнение."
        )

    # ---- Задание 9: Квадратные уравнения ----
    elif cmd == "quadratic_equations":
        await send_db_task(
            peer_id, user_id, "oge", 9, "n09_quadratic",
            TaskStates.task9_quadratic,
            intro_text="",
            show_photo_hint=False,
        )
        await send("Напиши ответ числом.")

    elif cmd == "show_right_quadratic":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"Выбери, что сделать дальше:",
            keyboard=kb.retry_or_menu_quadratic
        )

    elif cmd == "show_help_quadratic":
        await send(
            "📖 Справочник — Задание 9: Квадратные уравнения\n\n"
            "Формула дискриминанта:\n"
            "  D = b² − 4ac\n"
            "  • D > 0 → два корня: x = (−b ± √D) / 2a\n"
            "  • D = 0 → один корень: x = −b / 2a\n"
            "  • D < 0 → нет действительных корней\n\n"
            "Теорема Виета (для x² + px + q = 0):\n"
            "  x₁ + x₂ = −p\n"
            "  x₁ · x₂ = q\n\n"
            "Пример:  x² − 5x + 6 = 0\n"
            "  D = 25 − 24 = 1\n"
            "  x₁ = 3,  x₂ = 2"
        )

    # ---- Задание 10 ----
    elif cmd == "n10":
        task = random.choice(task10_probability_problems)
        set_answer(user_id, task["answer"])
        set_task_context(user_id, task['question'])
        set_task_meta(user_id, "oge", 10, "probability")
        await bot.state_dispenser.set(peer_id, TaskStates.task10_probability_problems)
        await send(f"Вот тебе задачка: {task['question']}\nВведи ответ в виде десятичной дроби или целого числа.")

    elif cmd == "show_right_task10_probability_problems":
        set_peeked(user_id, True)
        await send(f"Правильный ответ: {get_answer(user_id) or 'не найден'}")

    elif cmd == "show_help_task10_probability_problems":
        await send(
            "📖 Справочник — Задание 10: Теория вероятностей\n\n"
            "Классическая вероятность:\n"
            "  P(A) = m / n\n"
            "  m — число благоприятных исходов\n"
            "  n — общее число равновозможных исходов\n\n"
            "Свойства:\n"
            "  • 0 ≤ P(A) ≤ 1\n"
            "  • P(A) + P(Ā) = 1  (противоположное событие)\n\n"
            "Пример: в урне 3 красных и 7 синих шаров.\n"
            "  P(красный) = 3/10 = 0,3\n\n"
            "💡 Ответ вводи десятичной дробью: 0,3 или 0,75"
        )

    # ---- Задание 13: Линейные неравенства ----
    elif cmd == "linear_inequalities":
        await send_db_task(
            peer_id, user_id, "oge", 13, "n13_linear",
            TaskStates.task13_linear_ineq,
            intro_text="",
            show_photo_hint=False,
        )
        await send("Выбери верный вариант ответа и напиши в чат числом.")

    elif cmd == "show_right_linear_ineq":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"Выбери, что сделать дальше:",
            keyboard=kb.retry_or_menu_linear_ineq
        )

    elif cmd == "show_help_linear_ineq":
        await send(
            "📖 Справочник — Задание 13: Линейные неравенства\n\n"
            "Алгоритм решения ax + b > 0:\n"
            "1️⃣ Перенеси члены так же, как в уравнении\n"
            "2️⃣ При делении/умножении на отрицательное — знак меняется!\n"
            "  −2x > 6  →  x < −3\n\n"
            "Запись ответа:\n"
            "  x > 3  →  промежуток (3; +∞)\n"
            "  x ≤ 5  →  промежуток (−∞; 5]\n\n"
            "Числовая прямая:\n"
            "  ● — закрашенная точка (≤ или ≥, входит в ответ)\n"
            "  ○ — незакрашенная точка (< или >, не входит)"
        )

    # ---- Задание 13: Квадратные неравенства ----
    elif cmd == "quadratic_inequalities":
        await send_db_task(
            peer_id, user_id, "oge", 13, "n13_quadratic",
            TaskStates.task13_quadratic_ineq,
            intro_text="",
            show_photo_hint=False,
        )
        await send("Выбери верный вариант ответа и напиши в чат числом.")

    elif cmd == "show_right_quadratic_ineq":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"Выбери, что сделать дальше:",
            keyboard=kb.retry_or_menu_quadratic_ineq
        )

    elif cmd == "show_help_quadratic_ineq":
        await send(
            "📖 Справочник — Задание 13: Квадратные неравенства\n\n"
            "Алгоритм:\n"
            "1️⃣ Найди корни: x₁, x₂ (x₁ < x₂)\n"
            "2️⃣ Нарисуй параболу (a > 0 — ветви вверх)\n"
            "3️⃣ Парабола выше оси X вне корней, ниже — между корнями\n\n"
            "Правила:\n"
            "  ax² + bx + c > 0, a > 0  →  x < x₁ или x > x₂\n"
            "  ax² + bx + c < 0, a > 0  →  x₁ < x < x₂\n\n"
            "Пример: x² − 5x + 6 > 0\n"
            "  Корни: x=2, x=3\n"
            "  Ответ: x < 2 или x > 3"
        )

    # ---- Задание 13: Системы неравенств ----
    elif cmd == "systems_linear_inequalities":
        await send_db_task(
            peer_id, user_id, "oge", 13, "n13_systems",
            TaskStates.task13_systems_linear_ineq,
            intro_text="",
            show_photo_hint=False,
        )
        await send("Выбери верный вариант ответа и напиши в чат числом.")

    elif cmd == "show_right_systems_linear_ineq":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"Выбери, что сделать дальше:",
            keyboard=kb.retry_or_menu_systems_linear_ineq
        )

    elif cmd == "show_help_systems_linear_ineq":
        await send(
            "📖 Справочник — Задание 13: Системы линейных неравенств\n\n"
            "Алгоритм:\n"
            "1️⃣ Реши каждое неравенство отдельно\n"
            "2️⃣ Изобрази оба решения на одной числовой прямой\n"
            "3️⃣ Ответ — пересечение промежутков (где оба выполнены)\n\n"
            "Пример:\n"
            "  x > 1\n"
            "  x ≤ 4\n"
            "  Ответ: 1 < x ≤ 4  →  промежуток (1; 4]\n\n"
            "Если пересечения нет — система не имеет решений."
        )


    # ---- Задания 1-5 ----
    elif cmd == "n1_5":
        await send("Выбери тему:", keyboard=kb.oge_n1_5)

    elif cmd in ("t1_5_kvartira","t1_5_uchastok","t1_5_plan",
                 "t1_5_listy","t1_5_shiny","t1_5_tarify","t1_5_pech"):
        await start_set_1_5(peer_id, user_id, cmd)

    elif cmd.startswith("next_t1_5_"):
        topic_cmd = cmd[len("next_"):]
        await start_set_1_5(peer_id, user_id, topic_cmd)

    # ---- Задание 11 ----
    elif cmd == "n11":
        await send("Выбери тему из задания №11:", keyboard=kb.oge_n11)

    # ---- Задание 12 ----
    elif cmd == "n12":
        await send_db_task(peer_id, user_id, "oge", 12, "general", TaskStates.n12)

    elif cmd == "show_right_n12":
        await send(f"Правильный ответ: {get_answer(user_id) or 'не найден'}")

    elif cmd == "show_help_n12":
        await send(
            "📖 Справочник — Задание 12: Расчёты по формулам\n\n"
            "Алгоритм:\n"
            "1️⃣ Выпиши формулу, обозначь все величины\n"
            "2️⃣ Определи, что нужно найти\n"
            "3️⃣ Вырази искомую переменную (обратная задача)\n"
            "4️⃣ Подставь числа и вычисли\n\n"
            "⚠️ Следи за единицами измерения!\n"
            "💡 Дробные ответы вводи через запятую: −9,4"
        )

    # ---- Задание 14 ----
    elif cmd == "n14":
        await send("Выбери тему из задания №14:", keyboard=kb.oge_n14)

    elif cmd == "arithmetic_progression":
        await send_db_task(peer_id, user_id, "oge", 14, "arithmetic_progression", TaskStates.arith_prog)

    elif cmd == "geometric_progression":
        await send_db_task(peer_id, user_id, "oge", 14, "geometric_progression", TaskStates.geom_prog)

    elif cmd == "show_right_arith_prog":
        await send(f"Правильный ответ: {get_answer(user_id) or 'не найден'}")
    elif cmd == "show_help_arith_prog":
        await send(
            "📖 Справочник — Арифметическая прогрессия\n\n"
            "• n-й член:  aₙ = a₁ + d·(n − 1)\n"
            "• Разность:  d = aₙ − aₙ₋₁\n"
            "• Сумма первых n членов:\n"
            "  Sₙ = n·(a₁ + aₙ) / 2"
        )

    elif cmd == "show_right_geom_prog":
        await send(f"Правильный ответ: {get_answer(user_id) or 'не найден'}")
    elif cmd == "show_help_geom_prog":
        await send(
            "📖 Справочник — Геометрическая прогрессия\n\n"
            "• n-й член:  bₙ = b₁ · qⁿ⁻¹\n"
            "• Знаменатель:  q = bₙ / bₙ₋₁\n"
            "• Сумма первых n членов (q ≠ 1):\n"
            "  Sₙ = b₁ · (qⁿ − 1) / (q − 1)"
        )

    # ---- Задание 15 (треугольники) ----
    elif cmd == "n15":
        await send_db_task(
            peer_id, user_id,
            "oge", 15, "triangles",
            TaskStates.n15
        )

    elif cmd == "show_right_n15":
        answer = get_answer(user_id)
        set_peeked(user_id, True)
        await send(f"✅ Правильный ответ: {answer or 'не найден'}")

    elif cmd == "show_help_n15":
        await send(
            "📖 Справочник — Треугольники\n\n"
            "• Биссектриса делит угол пополам\n"
            "• Медиана делит сторону пополам\n"
            "• Сумма углов треугольника = 180°\n"
            "• Внешний угол = 180° − внутренний\n"
            "• В равнобедренном: углы при основании равны\n"
            "• S = ½ · a · h\n"
            "• S = ½ · a · b · sin(C)\n"
            "• Теорема Пифагора: c² = a² + b²\n"
            "• Средняя линия = ½ · AC\n"
            "• sinB = AC/AB, cosB = BC/AB, tgB = AC/BC\n"
            "• R описанной окружности прямоуг. треугольника = гипотенуза / 2"
        )

    # ---- Задание 16 (окружности) ----
    elif cmd == "n16":
        await send_db_task(peer_id, user_id, "oge", 16, "circles", TaskStates.n16,
                           "⭕ Задание 16 — Окружности\n\n")

    elif cmd == "show_right_n16":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n16
        )

    elif cmd == "show_help_n16":
        await send(
            "📖 Справочник — Окружность\n\n"
            "Касательная:\n"
            "• Касательная ⊥ радиусу в точке касания\n"
            "• Два отрезка касательных из одной точки равны\n"
            "• Угол между касательными: ∠ABO = α/2, где α — угол между ними\n\n"
            "Вписанный и центральный углы:\n"
            "• Вписанный угол = ½ · центрального угла\n"
            "• Если O и C по одну сторону от AB: ∠ACB = ∠AOB / 2\n"
            "• Два диаметра AC и BD: ∠AOD = 180° − 2·∠ACB\n"
            "• Угол в полукруге = 90°\n\n"
            "Вписанная окружность:\n"
            "• r трапеции: h = 2r\n"
            "• r квадрата: r = a/2\n"
            "• Описанный четырёхугольник: AB+CD = BC+AD\n"
            "• S треугольника = r · (P/2)\n"
            "• Равносторонний треугольник: r = a√3/6\n\n"
            "Описанная окружность:\n"
            "• Вписанный четырёхугольник: ∠A + ∠C = 180°\n"
            "• R квадрата = a√2/2\n"
            "• R равностороннего треугольника = a/√3\n\n"
            "Теорема синусов:\n"
            "• R = AB / (2·sin∠C)"
        )

        # ---- Задание 17 (четырёхугольники) ----
    elif cmd == "n17":
        await send("🔷 Задание 17 — Четырёхугольники\nВыбери тему:", keyboard=kb.oge_n17)

    elif cmd in ("n17_parallelogram", "n17_trapezoid", "n17_rectangle",
                 "n17_rhombus", "n17_square", "n17_random", "n17_retry"):

        # Определяем тему
        if cmd == "n17_retry":
            cmd = ctx.get(f"n17_last_cmd_{user_id}") or "n17_random"

        N17_TOPICS = {
            "n17_parallelogram": ("parallelogram", "Параллелограмм"),
            "n17_trapezoid": ("trapezoid", "Трапеция"),
            "n17_rectangle": ("rectangle", "Прямоугольник"),
            "n17_rhombus": ("rhombus", "Ромб"),
            "n17_square": ("square", "Квадрат"),
            "n17_random": (None, "Случайная тема"),
        }
        topic, label = N17_TOPICS[cmd]

        # Запоминаем выбранную тему (кроме случайной — не перезаписываем)
        if cmd != "n17_random":
            ctx.set(f"n17_last_cmd_{user_id}", cmd)

        await send_db_task(peer_id, user_id, "oge", 17, topic,
                           TaskStates.n17, f"🔷 Задание 17 — {label}\n\n")

    elif cmd == "show_right_n17":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n17
        )

    elif cmd == "show_help_n17":
        await send(
            "📖 Справочник — Четырёхугольники\n\n"
            "Параллелограмм:\n"
            "• Противоположные углы равны, смежные в сумме = 180°\n"
            "• Диагонали точкой пересечения делятся пополам\n"
            "• Биссектриса угла A ⊥ стороне BC ⇒ острый угол = 2β\n"
            "• S = основание × высота\n\n"
            "Трапеция:\n"
            "• Равнобедренная: углы при каждом основании равны\n"
            "• Сумма углов при боковой стороне = 180°\n"
            "• Средняя линия = (a + b) / 2\n"
            "• S = (a + b) / 2 × h\n"
            "• Диагональ под 45° ⇒ h = (a + b) / 2\n\n"
            "Прямоугольник:\n"
            "• Диагонали равны и делятся пополам\n"
            "• Угол между диагоналями = |180° − 2α|\n\n"
            "Ромб:\n"
            "• Все стороны равны; диагонали ⊥ и делятся пополам\n"
            "• Смежные углы в сумме = 180°\n"
            "• S = a² × sin(α), при α = 30°: S = a² / 2\n"
            "• Высота: h = a × sin(α)\n\n"
            "Квадрат:\n"
            "• Диагональ = a√2\n"
            "• S = a²"
        )

    # ---- Задание 18 (клетчатая плоскость) ----
    elif cmd == "n18":
        await send_db_task(peer_id, user_id, "oge", 18, "grid",
                           TaskStates.n18,
                           "📐 Задание 18 — Фигуры на квадратной решётке\n\n")

    elif cmd == "show_right_n18":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n18
        )

    elif cmd == "show_help_n18":
        await send(
            "📖 Справочник — Фигуры на квадратной решётке\n\n"

            "Длина отрезка:\n"
            "• Горизонтальный/вертикальный — считай клетки\n"
            "• Наклонный — теорема Пифагора: d = √(a² + b²),\n"
            "  где a, b — катеты по клеткам\n\n"

            "Площадь:\n"
            "• Прямоугольник: S = a × b\n"
            "• Треугольник: S = ½ × основание × высота\n"
            "• Параллелограмм: S = основание × высота\n"
            "• Трапеция: S = (a + b) / 2 × h\n"
            "• Ромб: S = d₁ × d₂ / 2\n"
            "• Сложная фигура: вписать в прямоугольник,\n"
            "  вычесть лишние треугольники\n\n"

            "Средняя линия:\n"
            "• Треугольника = ½ × параллельная сторона\n"
            "• Трапеции = (a + b) / 2\n\n"

            "Теорема Фалеса:\n"
            "• Если прямая параллельна стороне треугольника,\n"
            "  она делит две другие стороны пропорционально\n\n"

            "Площадь круга:\n"
            "• S = π × r²\n"
            "• Если R = k × r, то S_бол / S_мал = k²\n\n"

            "Тангенс угла:\n"
            "• tg(∠AOB) = противолежащий катет / прилежащий катет\n"
            "• По клеткам: tg = Δy / Δx"
        )

    # ---- Задание 19 ----
    elif cmd == "n19":
        await send_db_task(peer_id, user_id, "oge", 19, "general",
                           TaskStates.n19,
                           "📝 Задание 19 — Анализ геометрических высказываний\n\n"
                           "Выбери верные утверждения и запиши их номера без пробелов.\n\n")


    elif cmd == "show_right_n19":
        set_peeked(user_id, True)
        await send(
            f"✅ Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующий введённый ответ не будет засчитан.",
            keyboard=kb.after_peek_n19
        )
    elif cmd == "show_help_n19":
        await send(
            "📖 Справочник — Задание 19: Геометрические утверждения\n\n"
            "Ключевые факты:\n"
            "Треугольники:\n"
            "• Сумма углов = 180°\n"
            "• Внешний угол = сумма двух несмежных внутренних\n"
            "• Медиана делит треугольник на 2 равные части\n\n"
            "Четырёхугольники:\n"
            "• Сумма углов = 360°\n"
            "• В параллелограмме: противоположные стороны равны и параллельны\n"
            "• Диагонали ромба перпендикулярны и делятся пополам\n\n"
            "Окружность:\n"
            "• Вписанный угол = ½ центрального\n"
            "• Вписанный угол, опирающийся на диаметр = 90°\n"
            "• Касательная перпендикулярна радиусу в точке касания\n\n"
            "💡 Проверяй каждое утверждение отдельно, рисуй контрпример если сомневаешься."
        )

    # ---- Задание 20 (2-я часть) ----
    elif cmd == "n20":
        await send("Выбери тему из задания №20:", keyboard=kb.oge_n20)

    elif cmd in ("n20_systems","n20_equations","n20_inequalities"):
        topic_20 = {"n20_systems": "systems", "n20_equations": "equations", "n20_inequalities": "inequalities"}[cmd]
        set_task_meta(user_id, "oge", 20, cmd)
        await send_db_task(peer_id, user_id, "oge", 20, topic_20, TaskStates.n20,
                           "✏️ Задание 20 (2-я часть)\n\n", show_photo_hint=True)


    elif cmd == "n20_random":
        set_task_meta(user_id, "oge", 20, "random")
        await send_db_task(peer_id, user_id, "oge", 20, None, TaskStates.n20,
                           "✏️ Задание 20 (2-я часть)\n\n")

    elif cmd == "n21_random":
        set_task_meta(user_id, "oge", 21, "random")
        await send_db_task(peer_id, user_id, "oge", 21, None, TaskStates.n21,
                           "✏️ Задание 21 (2-я часть)\n\n")

    elif cmd == "show_right_n20":
        set_peeked(user_id, True)
        await send(
            f"Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующая попытка не будет засчитана.",
            keyboard=kb.after_peek_n20
        )

    elif cmd == "show_solution_n20":
        task_id = get_task_id(user_id)
        await send("📄 Подробное решение: отправьте запрос преподавателю или воспользуйтесь 🧠 AI Help!")

    # ---- Задание 21 (2-я часть) ----
    elif cmd == "n21":
        await send("Выбери тему из задания №21:", keyboard=kb.oge_n21)

    elif cmd in ("n21_motion_line", "n21_motion_water", "n21_work", "n21_percent"):
        set_task_meta(user_id, "oge", 21, cmd)
        await send_db_task(peer_id, user_id, "oge", 21, cmd, TaskStates.n21,
                           "✏️ Задание 21 (2-я часть)\n\n", show_photo_hint=True)

    elif cmd == "show_right_n21":
        set_peeked(user_id, True)
        await send(
            f"Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующая попытка не будет засчитана.",
            keyboard=kb.after_peek_n21
        )

    elif cmd == "show_solution_n21":
        await send("📄 Подробное решение: воспользуйтесь 🧠 AI Help для разбора этой задачи!")

    # ---- Задания 22-25 (2-я часть) ----
    elif cmd == "n22":
        await send_db_task(peer_id, user_id, "oge", 22, "functions", TaskStates.n22,
                           "📈 Задание 22 — Графики функций (2-я часть)\n\n", show_photo_hint=True)

    elif cmd == "show_right_n22":
        set_peeked(user_id, True)
        await send(
            f"Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"
            f"⚠️ Следующая попытка не будет засчитана.",
            keyboard=kb.after_peek_n22
        )

    elif cmd == "show_solution_n22": await send("📄 Воспользуйтесь 🧠 AI Help для разбора!")


    elif cmd == "n23":

        await send("Выбери тему задания №23:", keyboard=kb.oge_n23)

    elif cmd in ("n23_parallelogram", "n23_rhombus", "n23_triangle", "n23_circle", "random_n23"):
        import random as _random
        N23_TOPICS = {
            "n23_parallelogram": "n23_parallelogram",
            "n23_rhombus":       "n23_rhombus",
            "n23_triangle":      "n23_triangle",
            "n23_circle":        "n23_circle",
        }
        if cmd == "random_n23":
            topic_23 = _random.choice(list(N23_TOPICS.values()))
        else:
            topic_23 = cmd
        await send_db_task(peer_id, user_id, "oge", 23, topic_23, TaskStates.n23,
                           "📐 Задание 23 — Геометрия (2-я часть)\n\n", show_photo_hint=True)



    elif cmd == "show_right_n23":

        set_peeked(user_id, True)

        await send(

            f"Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"

            f"⚠️ Следующая попытка не будет засчитана.",

            keyboard=kb.after_peek_n23

        )


    elif cmd == "show_solution_n23": await send("📄 Воспользуйтесь 🧠 AI Help для разбора!")

    elif cmd == "n24":
        await send("Выбери тему задания №24:", keyboard=kb.oge_n24)

    elif cmd.startswith("proof_"):
        # proof_parallelogram, proof_triangle, proof_circle и т.д.
        await send_db_task(peer_id, user_id, "oge", 24, cmd, TaskStates.n24,
                           "📐 Задание 24 — Доказательство (2-я часть)\n\n", show_photo_hint=True)


    elif cmd == "show_right_n24":

        set_peeked(user_id, True)

        await send(

            f"Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"

            f"⚠️ Следующая попытка не будет засчитана.",

            keyboard=kb.after_peek_n24

        )
    elif cmd == "show_solution_n24": await send("📄 Воспользуйтесь 🧠 AI Help для разбора доказательства!")


    elif cmd == "n25":

        await send_db_task(peer_id, user_id, "oge", 25, None, TaskStates.n25,
                           "📐 Задание 25 — Геометрия (2-я часть)\n\n", show_photo_hint=True)



    elif cmd == "show_right_n25":

        set_peeked(user_id, True)

        await send(

            f"Правильный ответ: {get_answer(user_id) or 'не найден'}\n\n"

            f"⚠️ Следующая попытка не будет засчитана.",

            keyboard=kb.after_peek_n25

        )
    elif cmd == "show_solution_n25": await send("📄 Воспользуйтесь 🧠 AI Help для разбора!")

    elif cmd == "noop":
        pass  # разделитель меню — ничего не делаем

    else:
        print(f"Неизвестный cmd: {cmd!r}")

# -----------------------------------------------------------------------
# AI Help — обработка текста в режиме AI
# -----------------------------------------------------------------------

def _get_return_kb(user_id: int):
    """Вернуть клавиатуру того раздела, из которого был вызван AI Help."""
    exam_type = ctx.get(f"variant_exam_type_{user_id}") or \
                ctx.get(f"ai_help_exam_type_{user_id}") or "oge"
    return {
        "oge":         kb.oge,
        "ege_profile": kb.ege_profile,
        "ege_base":    kb.ege_base,
    }.get(exam_type, kb.oge)


@router.message(state=TaskStates.AI_HELP_MODE)
async def handle_ai_help(message: Message):
    if message.text and message.text.strip() in ("/cancel", "cancel"):
        bot.state_dispenser.dictionary.pop(message.from_id, None)
        await message.answer(
            "Режим AI Help деактивирован.",
            keyboard=_get_return_kb(message.from_id)
        )
        return
    try:
        task_ctx = get_task_context(message.from_id)
        response = await math_helper.ask_math_question(message.text, task_context=task_ctx)
        await message.answer(
            f"🤖 DeepSeek Assistant:\n\n{response}",
            keyboard=kb.ai_cancel_kb
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}", keyboard=kb.ai_cancel_kb)

# -----------------------------------------------------------------------
# Проверка ответов по состояниям
# -----------------------------------------------------------------------

@router.message(state=TaskStates.task6_ordinary)
async def check_ordinary(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_ordinary, kb.help_or_retry_ordinary)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task6_decimal)
async def check_decimal(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_decimal, kb.help_or_retry_decimal)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task9_linear)
async def check_linear(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_linear, kb.help_or_retry_linear)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task9_quadratic)
async def check_quadratic(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_quadratic, kb.help_or_retry_quadratic)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task13_linear_ineq)
async def check_linear_ineq(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_linear_ineq, kb.help_or_retry_linear_ineq)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task13_quadratic_ineq)
async def check_quadratic_ineq(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_quadratic_ineq, kb.help_or_retry_quadratic_ineq)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task13_systems_linear_ineq)
async def check_systems_linear_ineq(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_systems_linear_ineq, kb.help_or_retry_systems_linear_ineq)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task7)
async def check_task7(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_task7, kb.help_or_retry_task7)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task8_degrees)
async def check_task8_degrees(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_task8_degrees, kb.help_or_retry_task8_degrees)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task8_arithmetic_square_root)
async def check_task8_root(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_task8_arithmetic_square_root,
                                    kb.help_or_retry_task8_arithmetic_square_root)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

@router.message(state=TaskStates.task10_probability_problems)
async def check_task10(message: Message):
    ok = await check_numeric_answer(message, get_answer(message.from_id),
                                    kb.retry_or_menu_task10_probability_problems,
                                    kb.help_or_retry_task10_probability_problems)
    if ok:
        bot.state_dispenser.dictionary.pop(message.from_id, None)

# ═══════════════════════════════════════════════════════════════════════
# НОВЫЕ ОБРАБОТЧИКИ ЗАДАНИЙ
# ═══════════════════════════════════════════════════════════════════════

# Импорт get_random_set для заданий 1-5
from app.database import get_random_set

# -----------------------------------------------------------------------
# ЗАДАНИЯ 1-5 — набор из 5 заданий по теме
# -----------------------------------------------------------------------

# Маппинг cmd темы -> название для отображения
SET_TOPIC_NAMES = {
    "t1_5_kvartira": "Квартира",
    "t1_5_uchastok": "Участок",
    "t1_5_plan":     "План местности",
    "t1_5_listy":    "Листы",
    "t1_5_shiny":    "Шины",
    "t1_5_tarify":   "Тарифы",
    "t1_5_pech":     "Печь для бани",
}

# Маппинг cmd -> topic в БД
SET_TOPIC_DB = {
    "t1_5_kvartira": "kvartira",
    "t1_5_uchastok": "uchastok",
    "t1_5_plan":     "plan",
    "t1_5_listy":    "listy",
    "t1_5_shiny":    "shiny",
    "t1_5_tarify":   "tarify",
    "t1_5_pech":     "pech",
}

async def start_set_1_5(peer_id: int, user_id: int, topic_cmd: str):
    """Загрузить набор из 5 заданий и отправить первое."""
    topic_db   = SET_TOPIC_DB.get(topic_cmd, topic_cmd)
    topic_name = SET_TOPIC_NAMES.get(topic_cmd, topic_cmd)
    tasks_set  = await get_random_set(topic_db)

    if not tasks_set:
        await bot.api.messages.send(
            peer_id=peer_id,
            message=f"⚠️ Заданий по теме «{topic_name}» пока нет. Скоро добавим!",
            keyboard=kb.oge, random_id=0
        )
        return

    # Сохраняем набор и позицию в ctx
    ctx.set(f"set_{user_id}", tasks_set)
    ctx.set(f"set_pos_{user_id}", 0)
    ctx.set(f"set_topic_{user_id}", topic_cmd)

    await bot.state_dispenser.set(peer_id, TaskStates.set_1_5)
    await send_set_task(peer_id, user_id, tasks_set, 0, topic_name)


async def send_set_task(peer_id: int, user_id: int, tasks_set: list, pos: int, topic_name: str):
    """Отправить задание из набора по позиции."""
    task = tasks_set[pos]
    set_answer(user_id, task["answer"])
    set_task_id(user_id, task["id"])
    set_task_meta(user_id, "oge", task["task_number"], task["topic"])
    set_task_context(user_id, task.get("question", f"Задание {task['task_number']} — {topic_name}"))

    text = (
        f"📋 Тема: {topic_name} — Задание {pos + 1} из {len(tasks_set)}\n"
        f"(Задание №{task['task_number']} ОГЭ)\n\n"
    )
    if task.get("question"):
        text += task["question"] + "\n\nВведи ответ числом:"
    else:
        text += "Реши задание на картинке и введи ответ числом:"

    await bot.api.messages.send(peer_id=peer_id, message=text, random_id=0)

    if task.get("image_path"):
        await send_photo(peer_id, task["image_path"])


@router.message(state=TaskStates.set_1_5)
async def check_set_answer(message: Message):
    user_id    = message.from_id
    peer_id    = message.peer_id
    tasks_set  = ctx.get(f"set_{user_id}") or []
    pos        = ctx.get(f"set_pos_{user_id}") or 0
    topic_cmd  = ctx.get(f"set_topic_{user_id}") or ""
    topic_name = SET_TOPIC_NAMES.get(topic_cmd, "")

    correct    = get_answer(user_id)
    user_input = message.text.strip()
    user_norm  = user_input.replace(",", ".").replace("−", "-")

    if not user_norm:
        await message.answer("Введи числовой ответ.")
        return

    # Поддержка нескольких правильных ответов через |
    correct_variants = [v.strip().replace(",", ".") for v in str(correct).split("|")]
    is_correct = False
    for variant in correct_variants:
        try:
            if abs(float(user_norm) - float(variant)) < 1e-6:
                is_correct = True
                break
        except ValueError:
            if user_norm.strip() == variant.strip():
                is_correct = True
                break

    # Записываем попытку
    task_meta = get_task_meta(user_id)
    if task_meta:
        await record_attempt(user_id, get_task_id(user_id) or 0,
                             user_input, is_correct, *task_meta)

    next_pos = pos + 1

    if is_correct:
        if next_pos < len(tasks_set):
            ctx.set(f"set_pos_{user_id}", next_pos)
            await message.answer(f"✅ Верно! Переходим к заданию {next_pos + 1} из {len(tasks_set)}.")
            await send_set_task(peer_id, user_id, tasks_set, next_pos, topic_name)
        else:
            bot.state_dispenser.dictionary.pop(user_id, None)
            await message.answer(
                f"🎉 Набор завершён! Ты решил(а) все {len(tasks_set)} заданий темы «{topic_name}».\n"
                f"Хочешь попробовать другой набор?",
                keyboard=kb.make_set_result_kb(topic_cmd)
            )
    else:
        # Показываем подсказки и даём повторную попытку
        await message.answer(
            f"❌ Неверно, попробуй ещё раз!\n"
            f"💡 Можешь воспользоваться подсказками:",
            keyboard=kb.make_set_hint_kb(topic_cmd)
        )
        # НЕ переходим к следующему заданию — ждём правильного ответа

# -----------------------------------------------------------------------
# Вспомогательная функция — отправить задание из БД
# -----------------------------------------------------------------------

async def send_db_task(peer_id: int, user_id: int,
                       exam_type: str, task_number: int, topic: str | None,
                       state, intro_text: str = None, show_photo_hint: bool = False,
                       keyboard: str = None):
    set_peeked(user_id, False)
    from app.database import get_random_task as _get
    task = await _get(exam_type, task_number, topic)

    if not task:
        await bot.api.messages.send(
            peer_id=peer_id,
            message="⚠️ Заданий по этой теме пока нет. Скоро добавим!",
            keyboard=kb.oge, random_id=0
        )
        return

    actual_topic = task.get("topic") or topic or "general"
    set_answer(user_id, task["answer"])
    set_task_id(user_id, task["id"])
    set_task_meta(user_id, exam_type, task_number, actual_topic)
    set_task_context(user_id, task.get("question") or f"Задание №{task_number}")
    await bot.state_dispenser.set(peer_id, state)

    text = intro_text or ""
    if task.get("question"):
        text += task["question"]
    else:
        text += "Реши задание на картинке."
    if show_photo_hint:
        text += "\n\n📸 Пришли фото своего решения — нейросеть проверит его!\n💬 Или введи числовой ответ, если хочешь проверить только итог."
    else:
        text += "\n\n💬 Введи числовой ответ:"

    await bot.api.messages.send(peer_id=peer_id, message=text, random_id=0)
    if task.get("image_path"):
        await send_photo(peer_id, task["image_path"])
    if keyboard:
        await bot.api.messages.send(peer_id=peer_id, message="👇", keyboard=keyboard, random_id=0)
# -----------------------------------------------------------------------
# Обработчики проверки ответов — новые задания 1 части
# -----------------------------------------------------------------------

def make_check_handler(state, retry_kb, help_kb):
    @router.message(state=state)
    async def _check(message: Message):
        ok = await check_numeric_answer(message, get_answer(message.from_id), retry_kb, help_kb)
        if ok:
            bot.state_dispenser.dictionary.pop(message.from_id, None)
    return _check

check_n12 = make_check_handler(
    TaskStates.n12,
    kb.retry_or_menu_n12,   # клавиатура при верном ответе
    kb.help_or_retry_n12    # клавиатура при неверном ответе
)
check_arith     = make_check_handler(TaskStates.arith_prog, kb.retry_or_menu_arith_prog, kb.help_or_retry_arith_prog)
check_geom      = make_check_handler(TaskStates.geom_prog,  kb.retry_or_menu_geom_prog,  kb.help_or_retry_geom_prog)
check_n15       = make_check_handler(TaskStates.n15,       kb.retry_or_menu_n15,       kb.help_or_retry_n15)
check_n16       = make_check_handler(TaskStates.n16,       kb.retry_or_menu_n16,       kb.help_or_retry_n16)
check_n17       = make_check_handler(TaskStates.n17,       kb.retry_or_menu_n17,       kb.help_or_retry_n17)
check_n18       = make_check_handler(TaskStates.n18,       kb.retry_or_menu_n18,       kb.help_or_retry_n18)
check_n19       = make_check_handler(TaskStates.n19,       kb.retry_or_menu_n19,       kb.help_or_retry_n19)
check_n11_linear    = make_check_handler(TaskStates.n11_linear,
                          kb.retry_or_menu_n11_linear,
                          kb.help_or_retry_n11_linear)
check_n11_quadratic = make_check_handler(TaskStates.n11_quadratic,
                          kb.retry_or_menu_n11_quadratic,
                          kb.help_or_retry_n11_quadratic)
check_n11_hyperbola = make_check_handler(TaskStates.n11_hyperbola,
                          kb.retry_or_menu_n11_hyperbola,
                          kb.help_or_retry_n11_hyperbola)
check_n11_mixed     = make_check_handler(TaskStates.n11_mixed,
                          kb.retry_or_menu_n11_mixed,
                          kb.help_or_retry_n11_mixed)

# ── Имена критериев по номеру задания ──────────────────────────────────
PART2_CRITERIA = {
    20: ["Верный метод решения (K1)", "Верный ответ (K2)"],
    21: ["Верная математическая модель (K1)", "Верный ответ (K2)"],
    22: ["График построен верно (K1)", "Параметр найден верно (K2)"],
    23: ["Ход решения верный (K1)", "Верный ответ (K2)"],
    24: ["Доказательство верное (K1)", "Все шаги обоснованы (K2)"],
    25: ["Ход решения верный (K1)", "Верный ответ (K2)"],
}


async def check_part2_answer_result(message: Message, task_number: int) -> dict:
    """
    Выполняет проверку ответа на задание 2-й части и возвращает результат.
    Не управляет состоянием и не отправляет сообщений — только проверяет.

    Возвращает:
      mode:        "photo" | "text" | "invalid"
      is_correct:  bool
      score:       0 / 1 / 2  (только для фото; для текста 0 или 2)
      result_text: готовый текст для отправки пользователю
      need_retry:  True = ввод не распознан, ждём повторного ввода
    """
    user_id    = message.from_id
    photo_path = await download_vk_photo(message)

    # ── ФОТО → нейросеть ─────────────────────────────────────────────
    if photo_path:
        try:
            await bot.api.messages.send(
                peer_id=message.peer_id,
                message="🔍 Проверяю твоё решение...",
                random_id=0
            )
            result = await neural_checker.check_image(photo_path, task_number)
        finally:
            os.unlink(photo_path)

        if result["status"] == "model_not_available":
            return {
                "mode": "photo", "is_correct": False, "score": 0,
                "result_text": (
                    "📥 Нейросеть ещё обучается.\n"
                    "Твоё решение добавлено в датасет — спасибо!\n\n"
                    "Пока введи числовой ответ для быстрой проверки."
                ),
                "need_retry": True,
            }

        if result["status"] == "error":
            return {
                "mode": "photo", "is_correct": False, "score": 0,
                "result_text": "⚠️ Не удалось обработать фото. Убедись, что оно чёткое, и попробуй снова.",
                "need_retry": True,
            }

        criteria = PART2_CRITERIA.get(task_number, ["K1", "K2"])
        total    = result["total_score"]
        text     = neural_checker.format_result(result, criteria)

        # Записываем попытку
        task_meta = get_task_meta(user_id)
        if task_meta:
            exam_type, task_num, topic = task_meta
            await record_attempt(
                vk_id=user_id,
                task_id=get_task_id(user_id) or 0,
                user_answer=f"photo:score={total}",
                is_correct=(total == 2),
                exam_type=exam_type,
                task_number=task_num,
                topic=topic,
            )

        return {
            "mode": "photo", "is_correct": (total == 2), "score": total,
            "result_text": text, "need_retry": False,
        }

    # ── ТЕКСТ → числовая проверка ────────────────────────────────────
    correct    = get_answer(user_id)
    user_input = message.text.strip()

    def parse_nums(s: str) -> list[float]:
        """Извлечь числа из строки любого формата: (4; 1) и (4; -1), 4 1 4 -1 итд."""
        cleaned = re.sub(r"[^\d\-\.\s,;]", " ", s.replace("−", "-").replace(",", "."))
        nums = []
        for p in re.split(r"[\s,;]+", cleaned.strip()):
            p = p.strip()
            if not p:
                continue
            try:
                nums.append(float(p))
            except ValueError:
                pass
        return nums

    correct_nums = parse_nums(str(correct).replace("|", " "))
    user_nums    = parse_nums(user_input)

    if not user_nums:
        return {
            "mode": "invalid", "is_correct": False, "score": 0,
            "result_text": (
                "Введи числовой ответ.\n"
                "Если пар несколько — вводи числа через пробел: 4 1 4 -1"
            ),
            "need_retry": True,
        }

    is_correct = (
        len(user_nums) == len(correct_nums) and
        all(abs(a - b) < 1e-6
            for a, b in zip(sorted(user_nums), sorted(correct_nums)))
    )

    # Записываем попытку
    task_meta = get_task_meta(user_id)
    if task_meta:
        exam_type, task_num, topic = task_meta
        await record_attempt(
            vk_id=user_id,
            task_id=get_task_id(user_id) or 0,
            user_answer=user_input,
            is_correct=is_correct,
            exam_type=exam_type,
            task_number=task_num,
            topic=topic,
        )

    result_text = "✅ Верно!" if is_correct else "❌ Неверно. Попробуй ещё раз или посмотри правильный ответ:"
    return {
        "mode": "text", "is_correct": is_correct, "score": 2 if is_correct else 0,
        "result_text": result_text, "need_retry": False,
    }

async def check_part2_answer(message: Message, task_number: int, retry_kb, help_kb):
    """
    Проверка 2-й части в одиночном режиме.
      • Фото  → нейросеть (K1/K2)
      • Текст → числовой ответ с поддержкой пар
    """
    user_id = message.from_id

    # ── Антишпаргалка ────────────────────────────────────────────────
    peeked = get_peeked(user_id)
    if peeked:
        set_peeked(user_id, False)
        task_meta = get_task_meta(user_id)
        exam_type, task_num_meta, topic = task_meta if task_meta else ("oge", task_number, None)
        await record_attempt(
            vk_id=user_id,
            task_id=get_task_id(user_id) or 0,
            user_answer="[просмотр ответа]",
            is_correct=False,
            exam_type=exam_type,
            task_number=task_num_meta,
            topic=topic or "general",
        )
        await bot.api.messages.send(
            peer_id=message.peer_id,
            message="❌ Попытка не засчитана — ты посмотрел(а) правильный ответ.\n"
                    "Попробуй аналогичное задание!",
            keyboard=help_kb,
            random_id=0,
        )
        return

    res = await check_part2_answer_result(message, task_number)

    if res["need_retry"]:
        await bot.api.messages.send(
            peer_id=message.peer_id, message=res["result_text"],
            keyboard=help_kb, random_id=0
        )
        return

    if res["mode"] == "photo":
        score = res["score"]
        text  = res["result_text"]
        if score == 2:
            text += "\n\n✅ Отличная работа! Попробуй следующее задание."
            await bot.api.messages.send(
                peer_id=message.peer_id, message=text,
                keyboard=retry_kb, random_id=0
            )
            bot.state_dispenser.dictionary.pop(user_id, None)
        elif score == 1:
            text += "\n\n📝 Почти! Есть одна ошибка. Хочешь разобрать с AI?"
            await bot.api.messages.send(
                peer_id=message.peer_id, message=text,
                keyboard=help_kb, random_id=0
            )
        else:
            text += "\n\n❌ Решение содержит существенные ошибки. Воспользуйся AI Help!"
            await bot.api.messages.send(
                peer_id=message.peer_id, message=text,
                keyboard=help_kb, random_id=0
            )
    else:
        # text / invalid уже отфильтрован выше
        if res["is_correct"]:
            await message.answer(res["result_text"], keyboard=retry_kb)
            bot.state_dispenser.dictionary.pop(user_id, None)
        else:
            await message.answer(res["result_text"], keyboard=help_kb)


# ── Обработчики состояний 20–25 ────────────────────────────────────────

@router.message(state=TaskStates.n20)
async def check_n20(message: Message):
    task_meta = get_task_meta(message.from_id)
    topic = task_meta[2] if task_meta else "systems"
    retry_map = {
        "n20_systems":      kb.retry_or_menu_n20_systems,
        "n20_equations":    kb.retry_or_menu_n20_equations,
        "n20_inequalities": kb.retry_or_menu_n20_inequalities,
    }
    help_map = {
        "n20_systems":      kb.help_or_retry_n20_systems,
        "n20_equations":    kb.help_or_retry_n20_equations,
        "n20_inequalities": kb.help_or_retry_n20_inequalities,
    }
    await check_part2_answer(message, 20,
        retry_map.get(topic, kb.retry_or_menu_n20_systems),
        help_map.get(topic,  kb.help_or_retry_n20_systems))

@router.message(state=TaskStates.n21)
async def check_n21(message: Message):
    task_meta = get_task_meta(message.from_id)
    topic = task_meta[2] if task_meta else "n21_motion_line"
    retry_map = {
        "n21_motion_line":  kb.retry_or_menu_n21_motion_line,
        "n21_motion_water": kb.retry_or_menu_n21_motion_water,
        "n21_work":         kb.retry_or_menu_n21_work,
        "n21_percent":      kb.retry_or_menu_n21_percent,
    }
    help_map = {
        "n21_motion_line":  kb.help_or_retry_n21_motion_line,
        "n21_motion_water": kb.help_or_retry_n21_motion_water,
        "n21_work":         kb.help_or_retry_n21_work,
        "n21_percent":      kb.help_or_retry_n21_percent,
    }
    await check_part2_answer(message, 21,
        retry_map.get(topic, kb.retry_or_menu_n21_motion_line),
        help_map.get(topic,  kb.help_or_retry_n21_motion_line))

@router.message(state=TaskStates.n22)
async def check_n22(message: Message):
    await check_part2_answer(message, 22, kb.retry_or_menu_n22, kb.help_or_retry_n22)

@router.message(state=TaskStates.n23)
async def check_n23(message: Message):
    await check_part2_answer(message, 23, kb.retry_or_menu_n23, kb.help_or_retry_n23)

@router.message(state=TaskStates.n24)
async def check_n24(message: Message):
    await check_part2_answer(message, 24, kb.retry_or_menu_n24, kb.help_or_retry_n24)

@router.message(state=TaskStates.n25)
async def check_n25(message: Message):
    await check_part2_answer(message, 25, kb.retry_or_menu_n25, kb.help_or_retry_n25)

# ═══════════════════════════════════════════════════════════════════════
# ВАРИАНТ ОГЭ
# ═══════════════════════════════════════════════════════════════════════

from app.database import get_random_variant

class VariantStates(BaseStateGroup):
    solving = "variant_solving"

TOPIC_NAMES_ALL = {
    **TOPIC_NAMES,
    "general":                     "Общее",
    "probability":                 "Теория вероятностей",
    "degrees":                     "Степени",
    "arithmetic_square_root":      "Арифметические корни",
    "triangles":                   "Треугольники",
    "circles":                     "Окружности",
    "parallelogram":               "Параллелограмм",
    "trapezoid":                   "Трапеция",
    "rectangle":                   "Прямоугольник",
    "rhombus":                     "Ромб",
    "square":                      "Квадрат",
    "grid":                        "Клетчатая плоскость",
    "arithmetic_progression":      "Арифметическая прогрессия",
    "geometric_progression":       "Геометрическая прогрессия",
    "linear_function":             "Линейная функция",
    "quadratic_function":          "Квадратичная функция",
    "hyperbola":                   "Обратная пропорциональность",
    "mixed_graphs":                "Смешанные графики",
    # ЕГЭ профиль
    "ege_p09_applied":      "Прикладная задача",
    "ege_p10_word":         "Текстовая задача",
    "ege_p11_functions":    "Функции",
    "ege_p12_research":     "Исследование",
    "ege_p13_geometry":     "Геометрия",
    "ege_p14_geometry":     "Геометрия 3D",
    "ege_p15_finance":      "Финансы",
    "ege_p16_combinatorics":"Комбинаторика",
    "ege_p05_prob_th":   "Теоремы о вероятностях",
    "ege_p05_prob2":     "Теоремы о вероятностях",
    # ЕГЭ база
    "ege_b18_ineq":         "Неравенства",
    "ege_b18_equation":     "Уравнения",
    "ege_b18_systems":      "Системы",
    # Дополнительные ОГЭ
    "n13_linear":           "Лин. нерав.",
    "n13_quadratic":        "Кв. нерав.",
    "n13_systems":          "Системы нерав.",
    "n09_linear":           "Лин. уравн.",
    "n09_quadratic":        "Кв. уравн.",
    "n21_motion_line":      "Движение (прям.)",
    "n21_motion_water":     "Движение (вода)",
    "n21_percent":          "Проценты",
    "n21_work":             "Работа",
    "n23_parallelogram":    "Параллелогр.",
    "n23_rhombus":          "Ромб",
    "n23_triangle":         "Треугольник",
    "n23_circle":           "Окружность",
    "n25_trapezoid":        "Трапеция",
    "n25_parallelogram":    "Параллелогр.",
    "n25_triangle":         "Треугольник",
    "n25_circle":           "Окружность",
    "functions":       "Графики функций",
    "geometry":        "Геометрия",
    "geometry_proof":  "Доказательство",
    "equations":       "Уравнения",
    "systems":         "Системы уравнений",
    "inequalities":    "Неравенства",
    "motion_line":     "Движение по прямой",
    "motion_water":    "Движение по воде",
    "work":            "Работа",
    "percent":         "Проценты",
    "n20_systems":     "Системы уравнений",
    "n20_equations":   "Уравнения",
    "n20_inequalities":"Неравенства",


}


# Баллы за задания ЕГЭ профиль (часть 2)
EGE_PROFILE_PART2_SCORES = {
    13: 2,
    14: 3,
    15: 2,
    16: 2,
    17: 3,
    18: 4,
    19: 4,
}

# Перевод первичных баллов в вторичные (ЕГЭ профиль 2025)
EGE_PROFILE_SECONDARY = {
    0:0, 1:6, 2:11, 3:17, 4:22, 5:27, 6:34, 7:40, 8:46, 9:52,
    10:58, 11:64, 12:70, 13:72, 14:74, 15:76, 16:78, 17:80,
    18:82, 19:84, 20:86, 21:88, 22:90, 23:92, 24:94, 25:95,
    26:96, 27:97, 28:98, 29:99, 30:100, 31:100, 32:100,
}

GEO_TASKS = {15, 16, 17, 18, 19}  # номера геометрических заданий ОГЭ
GEO_TASKS_EGE_BASE = {9, 10, 11, 12, 13}  # номера геометрических заданий ЕГЭ база

# Константы баллов 2-й части
PART2_TASK_SCORES = {20: 2, 21: 2, 22: 2, 23: 2, 24: 2, 25: 2}
PART2_TASKS       = set(PART2_TASK_SCORES.keys())

async def send_variant_task(peer_id: int, user_id: int, variant: list, pos: int):
    """Отправить задание варианта по позиции."""
    task      = variant[pos]
    task_num  = task["task_number"]
    exam_type = ctx.get(f"variant_exam_type_{user_id}") or task.get("exam_type", "oge")
    topic_ru  = TOPIC_NAMES_ALL.get(task["topic"], task["topic"])
    is_geo    = (task_num in GEO_TASKS_EGE_BASE) if exam_type == "ege_base" else (task_num in GEO_TASKS)
    section   = "📐 Геометрия" if is_geo else "🔢 Алгебра"
    is_set_task = exam_type == "oge" and 1 <= task_num <= 5

    EXAM_LABEL = {
        "oge":         "ОГЭ",
        "ege_base":    "ЕГЭ база",
        "ege_profile": "ЕГЭ профиль",
    }
    exam_label = EXAM_LABEL.get(exam_type, exam_type.upper())

    set_answer(user_id, task["answer"])
    set_task_id(user_id, task["id"])
    set_task_meta(user_id, exam_type, task_num, task["topic"])
    set_task_context(user_id, task.get("question") or f"Задание №{task_num}")

    if is_set_task:
        text = (
            f"📝 Вариант · Задание {pos + 1} из {len(variant)}\n"
            f"№{task_num} {exam_label} · {section}\n"
            f"Тема набора: {TOPIC_NAMES_ALL.get(task['topic'], task['topic'])}\n\n"
        )
    else:
        text = (
            f"📝 Вариант · Задание {pos + 1} из {len(variant)}\n"
            f"№{task_num} {exam_label} · {section} — {topic_ru}\n\n"
        )

    if task.get("question"):
        text += task["question"] + "\n\nВведи ответ числом:"
    else:
        text += "Реши задание на картинке и введи ответ числом:"

    await bot.api.messages.send(peer_id=peer_id, message=text, random_id=0)
    if task.get("image_path"):
        await send_photo(peer_id, task["image_path"])


@router.message(state=VariantStates.solving)
async def check_variant_answer(message: Message):
    user_id  = message.from_id
    peer_id  = message.peer_id
    variant  = ctx.get(f"variant_{user_id}") or []
    pos      = ctx.get(f"variant_pos_{user_id}") or 0
    score    = ctx.get(f"variant_score_{user_id}") or 0

    if not variant:
        await message.answer("Вариант не найден. Начни заново.", keyboard=kb.oge)
        return

    correct      = get_answer(user_id)
    user_input   = message.text.strip()
    peeked       = get_peeked(user_id)
    current_task = variant[pos]
    task_num     = current_task["task_number"]

    # ── Вспомогательная функция для заданий 20-25 ────────────────────
    def parse_nums(s: str) -> list[float]:
        """Извлечь все числа из строки; разделители: пробел, запятая, точка с запятой."""
        parts = re.split(r"[\s,;]+", s.strip().replace('−', '-').replace(',', '.'))
        result = []
        for p in parts:
            try:
                result.append(float(p))
            except ValueError:
                pass
        return result

    # ── Проверка ответа ───────────────────────────────────────────────
    if task_num >= 20:
        max_score = PART2_TASK_SCORES.get(task_num, 2)

        # ── Антишпаргалка ─────────────────────────────────────────────
        if peeked:
            set_peeked(user_id, False)
            result_text = "🙈 Ответ не засчитан — ты подсмотрел(а)."
            is_correct = False

        else:
            # Задание 24 — только фото (доказательство)
            if task_num == 24 and not message.attachments:
                await message.answer(
                    "📸 Задание 24 — это доказательство.\n"
                    "Пришли фото своего решения."
                )
                return

            res = await check_part2_answer_result(message, task_num)

            if res["need_retry"]:
                await message.answer(res["result_text"])
                return  # ждём корректного ввода, позицию не двигаем

            is_correct = res["is_correct"]
            result_text = res["result_text"]

            if res["mode"] == "photo":
                got = res["score"]
                # Для фото пересчитываем is_correct по реальному максимуму
                is_correct = (got >= max_score)
                if got >= max_score:
                    result_text += f"\n\n✅ Отличная работа! {got}/{max_score} балл(а)"
                elif got > 0:
                    result_text += f"\n\n📝 Частично верно: {got}/{max_score} балл(а)"
                else:
                    result_text += f"\n\n❌ Есть существенные ошибки: {got}/{max_score}"

            # ── Сохраняем результат 2-й части для итогового отчёта ────
            part2_results = ctx.get(f"variant_part2_results_{user_id}") or {}
            part2_results[task_num] = {
                "correct": is_correct,
                "mode": res["mode"],
                "score": res.get("score", 2 if is_correct else 0),
                "max": max_score,
            }
            ctx.set(f"variant_part2_results_{user_id}", part2_results)

    else:
        # ── Задания 1–19: числовой ответ ──────────────────────────────

        # ── Антишпаргалка (как для заданий 20+) ───────────────────────
        if peeked:
            set_peeked(user_id, False)
            is_correct  = False
            result_text = "🙈 Ответ не засчитан — ты подсмотрел(а)."
        else:
            user_norm = user_input.replace(',', '.').replace('−', '-')
            correct_variants = [
                v.strip().replace(',', '.').replace('−', '-')
                for v in str(correct).split('|')
            ]
            is_correct = False
            for cv in correct_variants:
                try:
                    if abs(float(user_norm) - float(cv)) < 1e-6:
                        is_correct = True
                        break
                except ValueError:
                    if user_norm == cv:
                        is_correct = True
                        break

            if not is_correct and not any(
                    p.replace('.', '', 1).replace('-', '', 1).isdigit()
                    for p in re.split(r"[\s,;]+", user_input.replace('−', '-'))
            ):
                await message.answer("Введи числовой ответ.")
                return

            result_text = (
                f"✅ Верно! Счёт: {score + 1}/{pos + 1}"
                if is_correct
                else f"❌ Неверно."
            )

    # ── Записываем попытку (только если не peeked) ─────────────────────
    task_meta = get_task_meta(user_id)
    if task_meta and not peeked:
        await record_attempt(
            user_id, get_task_id(user_id) or 0,
            user_input, is_correct, *task_meta
        )

    # После проверки ответа, перед подсчётом счёта:
    user_answers = ctx.get(f"variant_user_answers_{user_id}") or {}
    user_answers[task_num] = {
        "user": user_input.replace(',', '.'),  # ← нормализуем для отображения
        "correct": str(correct).replace(',', '.'),
        "is_ok": is_correct,
        "skipped": False,
    }
    ctx.set(f"variant_user_answers_{user_id}", user_answers)


    # ── Счёт и продвижение ─────────────────────────────────────────────
    if is_correct and not peeked:
        score += 1
        ctx.set(f"variant_score_{user_id}", score)
        if task_num in GEO_TASKS:
            geo = (ctx.get(f"variant_geo_score_{user_id}") or 0) + 1
            ctx.set(f"variant_geo_score_{user_id}", geo)

    next_pos = pos + 1
    if next_pos >= len(variant):
        await _finish_variant(peer_id, user_id)
    else:
        ctx.set(f"variant_pos_{user_id}", next_pos)
        await message.answer(
            result_text,
            keyboard=kb.variant_next_kb if is_correct else kb.variant_wrong_kb
        )


# Callback-кнопки варианта — добавим в конец существующего callback-обработчика
# (обрабатываются через handle_callback, добавим ниже через отдельную проверку)

async def handle_variant_callbacks(cmd: str, peer_id: int, user_id: int):
    """Возвращает True если cmd был обработан как вариантный."""

    async def send(text="", keyboard=None):
        kwargs = {"peer_id": peer_id, "message": text, "random_id": 0}
        if keyboard:
            kwargs["keyboard"] = keyboard
        await bot.api.messages.send(**kwargs)

    # ── Меню экспорта варианта ───────────────────────────────────────
    if cmd == "export_menu_oge":
        await send("Выбери формат экспорта ОГЭ:", keyboard=kb.export_menu_oge)
        return True

    if cmd == "export_menu_ege_base":
        await send("Выбери формат экспорта ЕГЭ база:", keyboard=kb.export_menu_ege_base)
        return True

    if cmd == "export_menu_ege_profile":
        await send("Выбери формат экспорта ЕГЭ профиль:", keyboard=kb.export_menu_ege_profile)
        return True

    # ── Экспорт текущего варианта ────────────────────────────────────
    if cmd in {"variant_export_pdf", "variant_export_pdf_answers", "variant_export_docx", "variant_export_docx_answers"}:
        variant = ctx.get(f"variant_{user_id}") or []
        exam_type = ctx.get(f"variant_exam_type_{user_id}") or (variant[0].get("exam_type") if variant else "oge")
        fmt = "docx" if "docx" in cmd else "pdf"
        include_answers = cmd.endswith("_answers")
        await send("⏳ Формирую файл варианта: " + ("с ответами..." if include_answers else "без ответов..."))
        await export_variant_to_vk(peer_id, user_id, exam_type, variant, fmt=fmt, include_answers=include_answers)
        return True

    # ── Экспорт случайного варианта из меню экзамена ─────────────────
    m = re.fullmatch(r"export_variant_(oge|ege_base|ege_profile)_(pdf|docx)(_answers)?", cmd)
    if m:
        exam_type, fmt, answers_suffix = m.groups()
        include_answers = bool(answers_suffix)
        exam_title = VARIANT_EXAM_TITLES.get(exam_type, exam_type)

        await send(
            f"⏳ Собираю случайный вариант {exam_title} и формирую файл: "
            + ("с ответами..." if include_answers else "без ответов...")
        )

        variant = await build_random_variant_for_export(exam_type)
        if not variant:
            await send(
                f"⚠️ В базе пока недостаточно заданий для варианта {exam_title}.",
                keyboard=get_exam_menu_keyboard(exam_type)
            )
            return True

        await export_variant_to_vk(peer_id, user_id, exam_type, variant, fmt=fmt, include_answers=include_answers)
        return True

    if cmd in {"solve_variant", "solve_variant_oge"}:
        variant = await get_random_variant()
        if not variant:
            await send("⚠️ В базе пока недостаточно заданий для варианта.", keyboard=kb.oge)
            return True

        ctx.set(f"variant_{user_id}", variant)
        ctx.set(f"variant_exam_type_{user_id}", "oge")
        ctx.set(f"variant_pos_{user_id}", 0)
        ctx.set(f"variant_score_{user_id}", 0)
        ctx.set(f"variant_geo_score_{user_id}", 0)
        set_peeked(user_id, False)
        await bot.state_dispenser.set(peer_id, VariantStates.solving)

        await send(
            f"🎲 Случайный вариант ОГЭ\n"
            f"Задания: {', '.join(str(t['task_number']) for t in variant)}\n"
            f"Всего заданий: {len(variant)}\n\n"
            f"Отвечай на каждое задание числом. Начинаем!"
        )
        await send_variant_task(peer_id, user_id, variant, 0)
        return True

        # ── ЕГЭ профиль ──────────────────────────────────────────────────
    elif cmd == "solve_variant_ege_profile":
        variant = await build_random_variant_for_export("ege_profile")
        if not variant:
            await send("⚠️ В базе пока недостаточно заданий для варианта ЕГЭ профиль.",
                       keyboard=kb.ege_profile)
            return True

        ctx.set(f"variant_{user_id}", variant)
        ctx.set(f"variant_exam_type_{user_id}", "ege_profile")
        ctx.set(f"variant_pos_{user_id}", 0)
        ctx.set(f"variant_score_{user_id}", 0)
        ctx.set(f"variant_geo_score_{user_id}", 0)
        set_peeked(user_id, False)
        await bot.state_dispenser.set(peer_id, VariantStates.solving)

        await send(
            f"🎲 Случайный вариант ЕГЭ профиль\n"
            f"Заданий: {len(variant)}\n\n"
            f"Часть 1 (задания 1–12) — числовой ответ.\n"
            f"Часть 2 (задания 13–19) — фото решения или числовой ответ.\n\n"
            f"Начинаем!"
        )
        await send_variant_task(peer_id, user_id, variant, 0)
        return True

    # ── ЕГЭ база ─────────────────────────────────────────────────────
    elif cmd == "solve_variant_ege_base":
        variant = await build_random_variant_for_export("ege_base")
        if not variant:
            await send("⚠️ В базе пока недостаточно заданий для варианта ЕГЭ база.",
                       keyboard=kb.ege_base)
            return True

        ctx.set(f"variant_{user_id}", variant)
        ctx.set(f"variant_exam_type_{user_id}", "ege_base")
        ctx.set(f"variant_pos_{user_id}", 0)
        ctx.set(f"variant_score_{user_id}", 0)
        ctx.set(f"variant_geo_score_{user_id}", 0)
        set_peeked(user_id, False)
        await bot.state_dispenser.set(peer_id, VariantStates.solving)

        await send(
            f"🎲 Случайный вариант ЕГЭ база\n"
            f"Заданий: {len(variant)}\n\n"
            f"Все задания — числовой ответ. Начинаем!"
        )
        await send_variant_task(peer_id, user_id, variant, 0)
        return True


    elif cmd == "variant_next":
        variant = ctx.get(f"variant_{user_id}") or []
        pos = ctx.get(f"variant_pos_{user_id}") or 0
        if variant and pos < len(variant):
            await send_variant_task(peer_id, user_id, variant, pos)
        else:
            await _finish_variant(peer_id, user_id)  # ← правильный финиш
        return True


    elif cmd == "variant_show_right":
        correct = get_answer(user_id) or "—"
        # Записываем как неверный ответ (подсмотрел)
        user_answers = ctx.get(f"variant_user_answers_{user_id}") or {}
        variant = ctx.get(f"variant_{user_id}") or []
        pos = ctx.get(f"variant_pos_{user_id}") or 0
        if variant and pos > 0:
            task_num = variant[pos - 1]["task_number"]
            user_answers[task_num] = {
                "user": "подсмотрел",
                "correct": correct,
                "is_ok": False,
                "skipped": False,
            }
            ctx.set(f"variant_user_answers_{user_id}", user_answers)
        # Показываем ответ и сразу предлагаем идти дальше
        await send(
            f"✅ Правильный ответ: {correct}\n\n"
            f"Задание не засчитано.",
            keyboard=kb.variant_next_kb
        )
        return True



    elif cmd == "variant_finish":
        variant = ctx.get(f"variant_{user_id}") or []
        pos = ctx.get(f"variant_pos_{user_id}") or 0

        user_answers = ctx.get(f"variant_user_answers_{user_id}") or {}
        skipped = ctx.get(f"variant_skipped_{user_id}") or []

        for i in range(pos, len(variant)):
            tn = variant[i]["task_number"]
            if tn not in user_answers:
                user_answers[tn] = {
                    "user": "—",
                    "correct": "—",  # ← было "?"
                    "is_ok": False,
                    "skipped": True,
                }
                skipped.append(tn)

        print(f"[DEBUG finish] user_answers keys: {list(user_answers.keys())}")
        print(f"[DEBUG finish] pos={pos}, variant tasks: {[t['task_number'] for t in variant]}")

        ctx.set(f"variant_user_answers_{user_id}", user_answers)
        ctx.set(f"variant_skipped_{user_id}", skipped)

        await _finish_variant(peer_id, user_id)
        return True

    elif cmd == "variant_skip":
        variant = ctx.get(f"variant_{user_id}") or []
        pos = ctx.get(f"variant_pos_{user_id}") or 0

        # Сохраняем пропуск в историю ответов
        if variant and pos < len(variant):
            task_num = variant[pos]["task_number"]
            correct = get_answer(user_id)
            user_answers = ctx.get(f"variant_user_answers_{user_id}") or {}
            user_answers[task_num] = {
                "user": "—",
                "correct": str(correct),
                "is_ok": False,
                "skipped": True,
            }
            ctx.set(f"variant_user_answers_{user_id}", user_answers)

            skipped = ctx.get(f"variant_skipped_{user_id}") or []
            skipped.append(task_num)
            ctx.set(f"variant_skipped_{user_id}", skipped)

        next_pos = pos + 1
        ctx.set(f"variant_pos_{user_id}", next_pos)

        if next_pos >= len(variant):
            # Передаём управление финишу — вызываем через message-like объект невозможно,
            # поэтому дублируем финишную логику здесь
            await _finish_variant(peer_id, user_id)
        else:
            await send(f"⏭️ Задание пропущено.")
            await send_variant_task(peer_id, user_id, variant, next_pos)
        return True

    return False

def generate_variant_results_image(variant: list, user_answers: dict) -> bytes:
    """Генерирует PNG-таблицу с результатами варианта."""
    from PIL import Image as PILImage, ImageDraw, ImageFont
    import io

    ROW_H   = 30
    COL_W   = [45, 200, 200]
    PAD     = 12
    HEAD_H  = 44
    n_rows  = len(variant)
    W = sum(COL_W) + PAD * 2
    H = HEAD_H + ROW_H * (n_rows + 1) + PAD

    img  = PILImage.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except Exception:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 13)
            font_bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 13)
        except Exception:
            font = font_bold = ImageFont.load_default()

    DARK   = (44,  62,  80)
    GREEN  = (39, 174,  96)
    RED    = (231, 76,  60)
    GREY   = (149, 165, 166)
    LINE   = (200, 200, 200)
    WHITE  = (255, 255, 255)
    LIGHT  = (245, 245, 245)

    # Шапка
    draw.rectangle([0, 0, W, HEAD_H], fill=DARK)
    draw.text((PAD, 13), "Результаты варианта", font=font_bold, fill=WHITE)

    # Заголовки столбцов
    y = HEAD_H
    for i, (label, w) in enumerate(zip(["№", "Ваш ответ", "Правильный ответ"], COL_W)):
        x = PAD + sum(COL_W[:i])
        draw.rectangle([x, y, x + w, y + ROW_H], fill=LIGHT, outline=LINE)
        draw.text((x + 5, y + 7), label, font=font_bold, fill=DARK)

    # Строки
    for ri, task in enumerate(variant):
        tn  = task["task_number"]
        ans = user_answers.get(tn, {})
        u   = str(ans.get("user", "—"))[:22]
        c   = str(ans.get("correct", "?"))[:22]
        ok  = ans.get("is_ok", False)
        sk  = ans.get("skipped", False)

        bg = WHITE if ri % 2 == 0 else (250, 250, 250)
        y  = HEAD_H + ROW_H * (ri + 1)

        # №
        x = PAD
        draw.rectangle([x, y, x + COL_W[0], y + ROW_H], fill=bg, outline=LINE)
        draw.text((x + 5, y + 7), str(tn), font=font, fill=DARK)
        x += COL_W[0]

        # Ответ пользователя
        if sk:
            label, color = "-- пропущено", GREY
        elif ok:
            label, color = u, GREEN  # ← только ответ, без +
        else:
            label, color = u, RED  # ← только ответ, без -
        draw.rectangle([x, y, x + COL_W[1], y + ROW_H], fill=bg, outline=LINE)
        draw.text((x + 5, y + 7), label, font=font, fill=color)
        x += COL_W[1]

        # Правильный ответ
        draw.rectangle([x, y, x + COL_W[2], y + ROW_H], fill=bg, outline=LINE)
        draw.text((x + 5, y + 7), c, font=font, fill=DARK)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

async def _finish_variant(peer_id: int, user_id: int):
    """Завершить вариант и показать итоги."""
    variant   = ctx.get(f"variant_{user_id}") or []
    score     = ctx.get(f"variant_score_{user_id}") or 0
    geo_score = ctx.get(f"variant_geo_score_{user_id}") or 0
    part2_results = ctx.get(f"variant_part2_results_{user_id}") or {}
    skipped   = ctx.get(f"variant_skipped_{user_id}") or []
    exam_type = ctx.get(f"variant_exam_type_{user_id}") or "oge"

    bot.state_dispenser.dictionary.pop(user_id, None)

    # ── ЕГЭ профиль ──────────────────────────────────────────────────
    if exam_type == "ege_profile":
        primary = min(score, 32)
        secondary = EGE_PROFILE_SECONDARY.get(primary, 0)

        if secondary >= 72:
            grade, grade_comment = "5 🏆", "Отличный результат!"
        elif secondary >= 61:
            grade, grade_comment = "4 👍", "Хороший результат!"
        elif secondary >= 27:
            grade, grade_comment = "3 😐", "Минимальный порог пройден."
        else:
            grade, grade_comment = "2 😔", "Нужно больше практики"

        part2_lines = ""
        if part2_results:
            part2_lines = "\n📗 Часть 2:\n"
            for t_num in sorted(part2_results):
                r = part2_results[t_num]
                icon = "✅" if r["correct"] else "❌"
                mode = "фото" if r["mode"] == "photo" else "ответ"
                pts = r.get("score", 0)
                max_p = EGE_PROFILE_PART2_SCORES.get(t_num, 2)
                part2_lines += f"  {icon} Задание {t_num}: {pts}/{max_p} ({mode})\n"

        if skipped:
            part2_lines += f"\n⏭️ Пропущены: {', '.join(str(n) for n in skipped)}"

        result_msg = (
            f"🏁 Вариант ЕГЭ профиль завершён!\n"
            f"{'─' * 20}\n"
            f"📊 Первичный балл: {primary} из 32\n"
            f"📈 Вторичный балл: {secondary} из 100\n"
            f"{part2_lines}"
            f"{'─' * 20}\n"
            f"Оценка: {grade}\n"
            f"{grade_comment}\n\n"
            f"📋 Критерии ЕГЭ профиль:\n"
            f"  «3» — от 27 вторичных баллов\n"
            f"  «4» — от 61 вторичного балла\n"
            f"  «5» — от 72 вторичных баллов"
        )

        user_answers = ctx.get(f"variant_user_answers_{user_id}") or {}
        if user_answers and variant:
            try:
                img_bytes = generate_variant_results_image(variant, user_answers)
                tmp_path = Path("app/exports") / f"results_{user_id}.png"
                tmp_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.write_bytes(img_bytes)
                await send_photo(peer_id, str(tmp_path))
            except Exception as e:
                import traceback
                print(f"⚠️ results image ege_profile: {e}")
                traceback.print_exc()

        await bot.api.messages.send(
            peer_id=peer_id, message=result_msg,
            keyboard=kb.ege_profile, random_id=0
        )
        return

    # ── ЕГЭ база ──────────────────────────────────────────────────────
    if exam_type == "ege_base":
        primary = min(score, 21)

        if primary >= 18:
            grade, grade_comment = "5 🏆", "Отличный результат!"
        elif primary >= 12:
            grade, grade_comment = "4 👍", "Хороший результат!"
        elif primary >= 7:
            grade, grade_comment = "3 😐", "Минимальный порог пройден."
        else:
            grade, grade_comment = "2 😔", "Нужно больше практики"

        result_msg = (
            f"🏁 Вариант ЕГЭ база завершён!\n"
            f"{'─' * 20}\n"
            f"📊 Первичный балл: {primary} из 21\n"
            f"{'─' * 20}\n"
            f"Оценка: {grade}\n"
            f"{grade_comment}\n\n"
            f"📋 Критерии ЕГЭ база:\n"
            f"  «3» — от 7 баллов\n"
            f"  «4» — от 12 баллов\n"
            f"  «5» — от 18 баллов"
        )

        user_answers = ctx.get(f"variant_user_answers_{user_id}") or {}
        if user_answers and variant:
            try:
                img_bytes = generate_variant_results_image(variant, user_answers)
                tmp_path = Path("app/exports") / f"results_{user_id}.png"
                tmp_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.write_bytes(img_bytes)
                await send_photo(peer_id, str(tmp_path))
            except Exception as e:
                print(f"⚠️ results image ege_base: {e}")

        await bot.api.messages.send(
            peer_id=peer_id, message=result_msg,
            keyboard=kb.ege_base, random_id=0
        )
        return



    total_max  = 31  # 19 (часть 1) + 12 (часть 2)
    part1_max  = 19
    part2_max  = 12

    geo_ok = geo_score >= 2
    if score >= 22 and geo_ok:
        grade, grade_comment = "5 🏆", "Отличный результат!"
    elif score >= 15 and geo_ok:
        grade, grade_comment = "4 👍", "Хороший результат!"
    elif score >= 15 and not geo_ok:
        grade, grade_comment = "3 😐", f"Алгебра сдана, но геометрия подвела ({geo_score}/2 мин. балла)"
    elif score >= 8 and geo_ok:
        grade, grade_comment = "3 😐", "Есть над чем поработать."
    elif score >= 8 and not geo_ok:
        grade, grade_comment = "3 😐", f"Подтяни геометрию! ({geo_score}/2 мин. балла)"
    else:
        grade, grade_comment = "2 😔", "Нужно больше практики"

    # Итог по 2-й части
    part2_lines = ""
    if part2_results:
        part2_lines = "\n📗 Вторая часть:\n"
        for t_num in sorted(part2_results):
            r      = part2_results[t_num]
            icon   = "✅" if r["correct"] else "❌"
            mode   = "фото" if r["mode"] == "photo" else "ответ"
            pts    = r.get("score", 0)
            max_p  = PART2_TASK_SCORES.get(t_num, 2)
            part2_lines += f"  {icon} Задание {t_num}: {pts}/{max_p} ({mode})\n"

    if skipped:
        skip_str = ", ".join(str(n) for n in skipped)
        part2_lines += f"\n⏭️ Пропущены: задания {skip_str}"

    result_msg = (
        f"🏁 Вариант завершён!\n"
        f"{'─' * 20}\n"
        f"📊 Итого: {score} из {total_max}\n"
        f"📘 Часть 1: {min(score, part1_max)} из {part1_max}\n"
        f"  📐 Геометрия: {geo_score} баллов\n"
        f"  🔢 Алгебра: {min(score, part1_max) - geo_score} баллов\n"
        f"{part2_lines}"
        f"{'─' * 20}\n"
        f"Оценка: {grade}\n"
        f"{grade_comment}\n\n"
        f"📋 Критерии ОГЭ по математике:\n"
        f"  «2» — 0–7 баллов\n"
        f"  «3» — 8–14 баллов + мин. 2 по геометрии\n"
        f"  «4» — 15–21 балл + мин. 2 по геометрии\n"
        f"  «5» — 22–31 балл + мин. 2 по геометрии"
    )

    # ── Картинка с результатами — отправляем первой ───────────────────
    user_answers = ctx.get(f"variant_user_answers_{user_id}") or {}
    print(f"[DEBUG finish] user_answers={user_answers}")
    print(f"[DEBUG finish] variant len={len(variant)}")
    if user_answers and variant:
        try:
            img_bytes = generate_variant_results_image(variant, user_answers)
            tmp_path = Path("app/exports") / f"results_{user_id}.png"
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(img_bytes)
            await send_photo(peer_id, str(tmp_path))
        except Exception as e:
            import traceback
            print(f"⚠️ results image: {e}")
            traceback.print_exc()

    await bot.api.messages.send(
        peer_id=peer_id, message=result_msg,
        keyboard=kb.oge, random_id=0
    )




async def _check_ege_base_answer(message: Message, cmd: str):
    task_num, topic, label = EGE_BASE_TASK_MAP[cmd]
    retry_kb, help_kb = kb.ege_base_keyboards[cmd]

    correct = get_answer(message.from_id)
    user_answer = (message.text or "").strip()

    # Нормализация: заменяем запятую на точку для сравнения дробей
    def normalize(s: str) -> str:
        return s.replace(",", ".").strip()

    is_correct = normalize(user_answer) == normalize(correct or "")

    await record_attempt(
        vk_id=message.from_id,
        task_id=get_task_id(message.from_id) or 0,
        user_answer=user_answer,
        is_correct=is_correct,
        exam_type="ege_base",
        task_number=task_num,
        topic=topic,
    )

    if is_correct:
        await message.answer(
            f"✅ Верно! {label} — отличная работа!",
            keyboard=retry_kb
        )
        bot.state_dispenser.dictionary.pop(message.from_id, None)
    else:
        await message.answer(
            f"❌ Неверно. Правильный ответ ты узнаешь через AI Help.\n"
            f"Попробуй ещё раз или воспользуйся подсказкой:",
            keyboard=help_kb
        )



async def _check_ege_profile_part1(message: Message, cmd: str):
    task_num, topic, label, _ = EGE_PROFILE_TASK_MAP[cmd]
    retry_kb, help_kb = kb.ege_profile_part1_keyboards[cmd]

    correct = get_answer(message.from_id)
    user_answer = (message.text or "").strip()

    def normalize(s: str) -> str:
        return s.replace(",", ".").strip()

    is_correct = normalize(user_answer) == normalize(correct or "")

    await record_attempt(
        vk_id=message.from_id,
        task_id=get_task_id(message.from_id) or 0,
        user_answer=user_answer,
        is_correct=is_correct,
        exam_type="ege_profile",
        task_number=task_num,
        topic=topic,
    )

    if is_correct:
        await message.answer(f"✅ Верно! {label} — отлично!", keyboard=retry_kb)
        bot.state_dispenser.dictionary.pop(message.from_id, None)
    else:
        await message.answer(
            "❌ Неверно. Попробуй ещё раз или воспользуйся AI Help:",
            keyboard=help_kb
        )


async def _check_ege_profile_part2(message: Message, cmd: str):
    task_num, topic, label, _ = EGE_PROFILE_TASK_MAP[cmd]
    retry_kb, help_kb = kb.ege_profile_part2_keyboards[cmd]
    task_criteria = EGE_PROFILE_PART2_CRITERIA.get(task_num, {})
    criteria_labels = task_criteria.get("criteria", ["K1", "K2"])
    max_score = task_criteria.get("max_score", 2)

    photo_path = await download_vk_photo(message)

    if photo_path:
        try:
            await bot.api.messages.send(
                peer_id=message.peer_id,
                message="🔍 Проверяю твоё решение...",
                random_id=0
            )
            result = await neural_checker.check_image(photo_path, task_num)
        finally:
            import os; os.unlink(photo_path)

        if result["status"] == "model_not_available":
            await bot.api.messages.send(
                peer_id=message.peer_id,
                message="📥 Нейросеть обучается. Введи числовой ответ для быстрой проверки.",
                keyboard=help_kb, random_id=0
            )
            return

        if result["status"] == "error":
            await bot.api.messages.send(
                peer_id=message.peer_id,
                message="⚠️ Не удалось обработать фото. Попробуй снова.",
                keyboard=help_kb, random_id=0
            )
            return

        # Для заданий с max > 2 — масштабируем оценку нейросети
        k1 = result["K1"]["score"]
        k2 = result["K2"]["score"]
        neural_score = k1 + k2  # 0, 1 или 2

        # Масштабируем к реальному максимуму
        estimated_score = round(neural_score * max_score / 2)

        # Формируем текст результата
        conf_k1 = result["K1"]["confidence"]
        conf_k2 = result["K2"]["confidence"]
        low_conf = result.get("low_confidence", False)

        text = f"📊 Оценка нейросети: {estimated_score} / {max_score} баллов"
        if low_conf:
            text += "\n⚠️ Уверенность модели низкая — сфотографируй чётче или используй AI Help"
        text += "\n"

        # Показываем критерии
        for i, crit in enumerate(criteria_labels[:2], 1):
            score = k1 if i == 1 else k2
            conf = conf_k1 if i == 1 else conf_k2
            icon = "✅" if score == 1 else "❌"
            text += f"\n{icon} {crit}: {score} балл (уверенность {conf:.0%})"

        if max_score > 2:
            text += (
                f"\n\n💡 Задание оценивается до {max_score} баллов.\n"
                f"Нейросеть даёт примерную оценку — точную проверь через AI Help."
            )

        await record_attempt(
            vk_id=message.from_id,
            task_id=get_task_id(message.from_id) or 0,
            user_answer=f"photo:score={estimated_score}/{max_score}",
            is_correct=(estimated_score == max_score),
            exam_type="ege_profile",
            task_number=task_num,
            topic=topic,
        )

        if estimated_score == max_score:
            text += "\n\n✅ Отличная работа!"
            await bot.api.messages.send(
                peer_id=message.peer_id, message=text,
                keyboard=retry_kb, random_id=0
            )
            bot.state_dispenser.dictionary.pop(message.from_id, None)
        elif estimated_score >= max_score // 2:
            text += "\n\n📝 Неплохо! Разбери ошибки через AI Help."
            await bot.api.messages.send(
                peer_id=message.peer_id, message=text,
                keyboard=help_kb, random_id=0
            )
        else:
            text += "\n\n❌ Есть существенные ошибки. Воспользуйся AI Help!"
            await bot.api.messages.send(
                peer_id=message.peer_id, message=text,
                keyboard=help_kb, random_id=0
            )
    else:
        # Числовой ответ (только для задания 13 актуально)
        correct = get_answer(message.from_id)
        user_answer = (message.text or "").strip()
        def normalize(s): return s.replace(",", ".").strip()
        is_correct = normalize(user_answer) == normalize(correct or "")

        await record_attempt(
            vk_id=message.from_id,
            task_id=get_task_id(message.from_id) or 0,
            user_answer=user_answer,
            is_correct=is_correct,
            exam_type="ege_profile",
            task_number=task_num,
            topic=topic,
        )

        if is_correct:
            await message.answer(f"✅ Верно! {label}", keyboard=retry_kb)
            bot.state_dispenser.dictionary.pop(message.from_id, None)
        else:
            await message.answer(
                f"❌ Неверно. Пришли фото решения для полной проверки нейросетью:",
                keyboard=help_kb
            )


## ── ЕГЭ БАЗА: обработчики e1–e21 ───────────────────────────────────────────
for _cmd in [f"e{i}" for i in range(1, 22)]:
    def _make_ege_base(cmd=_cmd):
        retry_kb, help_kb = kb.ege_base_keyboards[cmd]
        return make_check_handler(getattr(TaskStates, cmd), retry_kb, help_kb)
    _make_ege_base()

# ── ЕГЭ ПРОФИЛЬ часть 1: обработчики p1–p12 ───────────────────────────────
for _cmd in [f"p{i}" for i in range(1, 13)]:
    def _make_ege_p1(cmd=_cmd):
        retry_kb, help_kb = kb.ege_profile_part1_keyboards[cmd]
        return make_check_handler(getattr(TaskStates, cmd), retry_kb, help_kb)
    _make_ege_p1()