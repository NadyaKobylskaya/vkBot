"""
hybrid_check.py — Гибридная проверка второй части ОГЭ/ЕГЭ профиль.

Сценарий:
1. Пользователь отправляет фото → нейросеть оценивает K1/K2
2. Если оценка не 2/2 → бот просит описать ход решения текстом
3. Текст + условие задачи → DeepSeek → разбор ошибки

Подключение в handlers.py:
    from app.hybrid_check import HybridChecker
    hybrid = HybridChecker(math_helper)

Вместо прямого вызова neural_checker в check_part2_answer используй:
    await hybrid.check_and_explain(message, task_number, task_context)
"""

import os
import base64
import tempfile
from pathlib import Path

from vkbottle.bot import Message
from vkbottle import CtxStorage

# Номера заданий второй части где применяется гибридная проверка
PART2_OGE     = set(range(20, 26))   # ОГЭ 20–25
PART2_EGE_P   = set(range(13, 20))   # ЕГЭ профиль 13–19

# Пример описания хода решения — отправляется пользователю как подсказка
EXPLANATION_HINT = """📝 Опиши кратко что ты делал в решении.

Например:
• составил уравнение / неравенство
• нашёл дискриминант D = ...
• получил корни x₁ = ..., x₂ = ...
• проверил подстановкой
• ответ: ...

Чем подробнее — тем точнее разбор от AI 🧠"""


def image_to_base64(image_path: str) -> str:
    """Конвертирует изображение в base64 для передачи в API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class HybridChecker:
    """
    Гибридный проверяющий: нейросеть → запрос хода решения → DeepSeek.
    """

    def __init__(self, math_helper, neural_checker_instance, ctx: CtxStorage):
        self.math_helper    = math_helper
        self.neural_checker = neural_checker_instance
        self.ctx            = ctx

    def is_part2_task(self, exam_type: str, task_number: int) -> bool:
        """Проверяет что задание относится ко второй части."""
        if exam_type == "oge" and task_number in PART2_OGE:
            return True
        if exam_type == "ege_profile" and task_number in PART2_EGE_P:
            return True
        return False

    async def check_photo(
        self,
        photo_path: str,
        task_number: int,
        peer_id: int,
        user_id: int,
    ) -> dict:
        """
        Шаг 1: нейросетевая проверка фото.
        Сохраняет путь к фото в ctx для последующей передачи в DeepSeek.
        """
        result = await self.neural_checker.check_image(photo_path, task_number)

        # Сохраняем base64 фото в ctx — понадобится если пользователь
        # попросит разбор через DeepSeek VL2
        try:
            img_b64 = image_to_base64(photo_path)
            self.ctx.set(f"last_photo_b64_{user_id}", img_b64)
        except Exception:
            pass

        return result

    async def request_explanation(self, peer_id: int, bot) -> None:
        """
        Шаг 2: просим пользователя описать ход решения.
        Устанавливает флаг ожидания объяснения.
        """
        await bot.api.messages.send(
            peer_id=peer_id,
            message=EXPLANATION_HINT,
            random_id=0
        )

    async def explain_with_deepseek(
        self,
        user_explanation: str,
        task_context: str,
        task_number: int,
        user_id: int,
        neural_result: dict,
        task_image_path: str = None,
    ) -> str:
        """
        Шаг 3: передаём в DeepSeek условие + ход решения + результат нейросети.
        Если задание содержит изображение — пробуем передать через deepseek-vl2.
        """
        # Формируем информацию о результате нейросети
        k1 = neural_result.get("K1", {})
        k2 = neural_result.get("K2", {})
        neural_summary = (
            f"Нейросеть оценила: "
            f"K1={k1.get('score', '?')} ({k1.get('confidence', 0):.0%}), "
            f"K2={k2.get('score', '?')} ({k2.get('confidence', 0):.0%})"
        )

        # Базовый промт
        prompt = (
            f"Задание №{task_number} ОГЭ/ЕГЭ по математике.\n\n"
            f"Условие задачи:\n{task_context}\n\n"
            f"Ход решения ученика:\n{user_explanation}\n\n"
            f"{neural_summary}\n\n"
            f"Пожалуйста:\n"
            f"1. Укажи конкретно где именно допущена ошибка\n"
            f"2. Объясни как правильно выполнить этот шаг\n"
            f"3. Если ответ неверный — покажи верный ответ пошагово\n\n"
            f"Отвечай без LaTeX, используй Unicode: x², √, ≤, ·"
        )

        # Пробуем deepseek-vl2 если есть изображение задания
        if task_image_path and Path(task_image_path).exists():
            try:
                img_b64 = image_to_base64(task_image_path)
                response = await self._ask_with_image(prompt, img_b64)
                return response
            except Exception as e:
                print(f"⚠️ deepseek-vl2 недоступен: {e}, fallback на text")

        # Fallback — обычный текстовый запрос
        return await self.math_helper.ask_math_question(prompt, task_context)

    async def _ask_with_image(self, prompt: str, img_base64: str) -> str:
        """
        Запрос к deepseek-vl2 с изображением условия задачи.
        """
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self.math_helper.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-vl2",
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }],
            "max_tokens": 1000,
            "temperature": 0.7
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.math_helper.base_url,
                headers=headers,
                json=payload
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"deepseek-vl2 error {resp.status}")
                data = await resp.json()
                raw = data["choices"][0]["message"]["content"]
                return self.math_helper._clean_response(raw)


# ── Состояние ожидания объяснения ────────────────────────────────────────────

def set_awaiting_explanation(ctx: CtxStorage, user_id: int,
                              task_number: int, neural_result: dict,
                              task_context: str, task_image_path: str = None):
    """Сохраняет контекст для последующего вызова explain_with_deepseek."""
    ctx.set(f"awaiting_explanation_{user_id}", {
        "task_number":    task_number,
        "neural_result":  neural_result,
        "task_context":   task_context,
        "task_image_path": task_image_path,
    })


def get_awaiting_explanation(ctx: CtxStorage, user_id: int) -> dict | None:
    """Возвращает сохранённый контекст или None."""
    return ctx.get(f"awaiting_explanation_{user_id}")


def clear_awaiting_explanation(ctx: CtxStorage, user_id: int):
    """Очищает флаг ожидания."""
    ctx.set(f"awaiting_explanation_{user_id}", None)
