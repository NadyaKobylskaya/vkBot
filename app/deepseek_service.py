import aiohttp


class DeepSeekMathHelper:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1/chat/completions"

    async def ask_math_question(self, question: str, task_context: str = None) -> str:
        system_prompt = (
            "Ты — эксперт по подготовке к ЕГЭ и ОГЭ по математике. Правила:\n"
            "1. Всегда давай подробные пошаговые решения\n"
            "2. ВАЖНО: НЕ используй LaTeX, Markdown, звёздочки (**), решётки (#) и обратные слэши. "
            "Вместо этого пиши формулы обычным текстом с Unicode-символами:\n"
            "   — дроби: ½ ⅓ ¼ или a/b\n"
            "   — степени: x² x³ или x^2\n"
            "   — корень: √x или sqrt(x)\n"
            "   — умножение: ×\n"
            "   — неравенства: ≤ ≥ ≠\n"
            "   — принадлежность: ∈\n"
            "   — бесконечность: ∞\n"
            "3. Оформляй шаги так:\n"
            "   📌 Шаг 1: [название]\n"
            "   [действие]\n"
            "   = [результат]\n\n"
            "4. Для задач указывай тип экзамена и номер задания\n"
            "5. Отвечай только на вопросы по математике\n"
            "6. Объясняй сложные понятия простыми словами\n"
            "7. Для графиков используй текстовые описания\n"
            "8. В конце всегда выдели ответ так:\n"
            "   ✅ Ответ: [ответ]"
        )

        messages = [{"role": "system", "content": system_prompt}]

        if task_context:
            messages.append({
                "role": "user",
                "content": f"Я решал(а) следующую задачу:\n\n{task_context}\n\nЯ не смог(ла) её решить. Помоги мне разобраться."
            })
            messages.append({
                "role": "assistant",
                "content": "Конечно, давай разберём эту задачу вместе! Что именно непонятно или ты хочешь увидеть полное решение?"
            })

        messages.append({"role": "user", "content": question})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"DeepSeek API error {resp.status}: {text}")
                data = await resp.json()
                raw = data["choices"][0]["message"]["content"]
                return self._clean_response(raw)

    def _clean_response(self, text: str) -> str:
        """Убираем остатки LaTeX и Markdown на случай если модель всё же их использовала."""
        import re

        # Убираем LaTeX-окружения \[ ... \] и \( ... \)
        text = re.sub(r'\\\[|\\\]|\\\(|\\\)', '', text)

        # Убираем \frac{a}{b} -> a/b
        text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', text)

        # Убираем \sqrt{x} -> √x
        text = re.sub(r'\\sqrt\{([^}]+)\}', r'√\1', text)
        text = re.sub(r'\\sqrt', '√', text)

        # Убираем \boxed{x} -> x
        text = re.sub(r'\\boxed\{([^}]+)\}', r'\1', text)

        # Убираем прочие LaTeX-команды типа \cdot \times \leq и т.д.
        replacements = {
            r'\cdot': '×',
            r'\times': '×',
            r'\leq': '≤',
            r'\geq': '≥',
            r'\neq': '≠',
            r'\infty': '∞',
            r'\in': '∈',
            r'\pm': '±',
            r'\approx': '≈',
            r'---': '──────────',
            r'--': '─',
        }
        for latex, symbol in replacements.items():
            text = text.replace(latex, symbol)

        # Убираем оставшиеся одиночные обратные слэши перед буквами
        text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)

        # Markdown: **жирный** -> просто текст (убираем **)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)

        # Markdown заголовки ## -> убираем решётки
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)

        return text.strip()