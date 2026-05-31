"""
Инференс: загружаем обученную модель и проверяем решения.
"""

import torch
import numpy as np
from pathlib import Path

from app.neural.model      import create_model
from app.neural.preprocess import load_and_preprocess


# Пороги уверенности для предупреждений
CONFIDENCE_THRESHOLD = 0.65


class NeuralChecker:
    """
    Обёртка над обученной моделью для использования в боте.
    Загружается один раз при старте.
    """

    _instance = None  # Singleton

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        checkpoint_path: str = "app/models/checkpoints/best_model.pt",
        num_criteria: int = 2,
        device: str = None,
    ):
        if self._initialized:
            return

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.num_criteria = num_criteria

        if Path(checkpoint_path).exists():
            self.model = create_model(
                num_criteria=num_criteria,
                checkpoint_path=checkpoint_path,
                device=self.device,
            )
            self.available = True
            print(f"🤖 NeuralChecker готов (device={self.device})")
        else:
            self.model     = None
            self.available = False
            print(f"⚠️ Чекпоинт не найден: {checkpoint_path}")

        self._initialized = True

    async def check_image(
        self,
        image_path: str,
        task_number: int,
    ) -> dict:
        """
        Проверяет решение по изображению.

        Returns:
            dict с оценками по критериям и уверенностью
        """
        if not self.available:
            return {
                "status": "model_not_available",
                "message": "Нейросеть ещё не обучена. "
                           "Твоё решение будет добавлено в датасет для обучения.",
            }

        try:
            tensor = load_and_preprocess(image_path)
            tensor = tensor.to(self.device)

            scores = self.model.predict_scores(tensor)
            scores["status"]      = "ok"
            scores["task_number"] = task_number

            # Проверяем уверенность модели
            min_conf = min(
                v["confidence"]
                for k, v in scores.items()
                if isinstance(v, dict) and "confidence" in v
            )
            scores["low_confidence"] = min_conf < CONFIDENCE_THRESHOLD

            return scores

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def format_result(self, result: dict, criteria_names: list[str]) -> str:
        """Форматирует результат проверки для отправки в ВКонтакте."""
        if result["status"] != "ok":
            return f"⚠️ {result.get('message', 'Ошибка проверки')}"

        total    = result["total_score"]
        max_scr  = result["max_score"]
        low_conf = result.get("low_confidence", False)

        emoji = "🏆" if total == max_scr else ("📝" if total > 0 else "❌")
        lines = [f"{emoji} Оценка нейросети: {total} / {max_scr} баллов"]

        if low_conf:
            lines.append(
                "⚠️ Уверенность модели низкая — "
                "сфотографируй чётче или используй 🧠 AI Help"
            )

        lines.append("")
        for i, name in enumerate(criteria_names, start=1):
            key  = f"K{i}"
            info = result.get(key, {})
            sc   = info.get("score", 0)
            conf = info.get("confidence", 0)
            icon = "✅" if sc else "❌"
            lines.append(f"{icon} {name}: {sc} балл (уверенность {conf:.0%})")

        return "\n".join(lines)


# Глобальный инстанс (создаётся при импорте модуля)
neural_checker = NeuralChecker()

"""
Инференс: загружаем обученную модель и проверяем решения.
"""

import torch
import numpy as np
from pathlib import Path

from app.neural.model      import create_model
from app.neural.preprocess import load_and_preprocess


# Пороги уверенности для предупреждений
CONFIDENCE_THRESHOLD = 0.65


class NeuralChecker:
    """
    Обёртка над обученной моделью для использования в боте.
    Загружается один раз при старте.
    """

    _instance = None  # Singleton

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        checkpoint_path: str = "app/models/checkpoints/best_model.pt",
        num_criteria: int = 2,
        device: str = None,
    ):
        if self._initialized:
            return

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.num_criteria = num_criteria

        if Path(checkpoint_path).exists():
            self.model = create_model(
                num_criteria=num_criteria,
                checkpoint_path=checkpoint_path,
                device=self.device,
            )
            self.available = True
            print(f"🤖 NeuralChecker готов (device={self.device})")
        else:
            self.model     = None
            self.available = False
            print(f"⚠️ Чекпоинт не найден: {checkpoint_path}")

        self._initialized = True

    async def check_image(
        self,
        image_path: str,
        task_number: int,
    ) -> dict:
        """
        Проверяет решение по изображению.

        Returns:
            dict с оценками по критериям и уверенностью
        """
        if not self.available:
            return {
                "status": "model_not_available",
                "message": "Нейросеть ещё не обучена. "
                           "Твоё решение будет добавлено в датасет для обучения.",
            }

        try:
            tensor = load_and_preprocess(image_path)
            tensor = tensor.to(self.device)

            scores = self.model.predict_scores(tensor)
            scores["status"]      = "ok"
            scores["task_number"] = task_number

            # Проверяем уверенность модели
            min_conf = min(
                v["confidence"]
                for k, v in scores.items()
                if isinstance(v, dict) and "confidence" in v
            )
            scores["low_confidence"] = min_conf < CONFIDENCE_THRESHOLD

            return scores

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def format_result(self, result: dict, criteria_names: list[str]) -> str:
        """Форматирует результат проверки для отправки в ВКонтакте."""
        if result["status"] != "ok":
            return f"⚠️ {result.get('message', 'Ошибка проверки')}"

        total    = result["total_score"]
        max_scr  = result["max_score"]
        low_conf = result.get("low_confidence", False)

        emoji = "🏆" if total == max_scr else ("📝" if total > 0 else "❌")
        lines = [f"{emoji} Оценка нейросети: {total} / {max_scr} баллов"]

        if low_conf:
            lines.append(
                "⚠️ Уверенность модели низкая — "
                "сфотографируй чётче или используй 🧠 AI Help"
            )

        lines.append("")
        for i, name in enumerate(criteria_names, start=1):
            key  = f"K{i}"
            info = result.get(key, {})
            sc   = info.get("score", 0)
            conf = info.get("confidence", 0)
            icon = "✅" if sc else "❌"
            lines.append(f"{icon} {name}: {sc} балл (уверенность {conf:.0%})")

        return "\n".join(lines)


# Глобальный инстанс (создаётся при импорте модуля)
neural_checker = NeuralChecker()


