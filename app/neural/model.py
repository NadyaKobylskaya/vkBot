"""
Нейронная сеть для оценки рукописных математических решений.

Архитектура:
  - Backbone: EfficientNet-B3 (предобучен на ImageNet, веса замораживаются)
  - Spatial Attention: фокусируется на значимых областях листа
  - Multi-head классификатор: отдельная голова для каждого критерия
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import efficientnet_b3, EfficientNet_B3_Weights


class SpatialAttention(nn.Module):
    """
    Механизм пространственного внимания.
    Позволяет сети фокусироваться на значимых областях изображения
    (например, на финальном ответе, на конкретном шаге решения).
    """
    def __init__(self, in_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, in_channels // 8, kernel_size=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels // 8, 1, kernel_size=1),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Карта внимания: [B, 1, H, W]
        attention_map = self.conv(x)
        # Применяем к признакам
        return x * attention_map


class CriterionHead(nn.Module):
    """
    Классификационная голова для одного критерия оценивания.
    Выдаёт вероятности классов (0 баллов / 1 балл).
    """
    def __init__(self, in_features: int, dropout: float = 0.4):
        super().__init__()
        self.classifier = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout / 2),
            nn.Linear(64, 2)   # 2 класса: 0 баллов / 1 балл
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(x)


class MathSolutionChecker(nn.Module):
    """
    Основная модель проверки математических решений.

    Args:
        num_criteria:   количество критериев оценивания (обычно 2–3)
        freeze_backbone: заморозить ли первые слои backbone
        dropout:        dropout для регуляризации
    """

    def __init__(
        self,
        num_criteria: int = 2,
        freeze_backbone: bool = True,
        dropout: float = 0.4,
    ):
        super().__init__()
        self.num_criteria = num_criteria

        # ── Backbone: EfficientNet-B3 ────────────────────────────────────
        backbone = efficientnet_b3(weights=EfficientNet_B3_Weights.DEFAULT)

        # Берём всё кроме последнего классификатора
        self.backbone = backbone.features  # [B, 1536, H/32, W/32]
        backbone_out_channels = 1536

        # Замораживаем первые 5 блоков backbone (transfer learning)
        if freeze_backbone:
            for i, block in enumerate(self.backbone):
                if i < 5:
                    for param in block.parameters():
                        param.requires_grad = False

        # ── Spatial Attention ────────────────────────────────────────────
        self.attention = SpatialAttention(backbone_out_channels)

        # ── Global Average Pooling → вектор признаков ───────────────────
        self.gap = nn.AdaptiveAvgPool2d(1)

        # ── Shared representation (общее для всех критериев) ────────────
        feature_dim = 512
        self.shared_fc = nn.Sequential(
            nn.Linear(backbone_out_channels, feature_dim),
            nn.BatchNorm1d(feature_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
        )

        # ── Отдельная голова для каждого критерия ───────────────────────
        self.criterion_heads = nn.ModuleList([
            CriterionHead(feature_dim, dropout)
            for _ in range(num_criteria)
        ])

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        """
        Args:
            x: [B, 3, H, W] — батч изображений

        Returns:
            list из num_criteria тензоров, каждый [B, 2]
            (логиты классов 0 и 1 для каждого критерия)
        """
        # Извлекаем признаки backbone
        features = self.backbone(x)          # [B, 1536, H', W']

        # Применяем attention
        features = self.attention(features)   # [B, 1536, H', W']

        # Global Average Pooling
        pooled = self.gap(features)           # [B, 1536, 1, 1]
        pooled = pooled.flatten(1)            # [B, 1536]

        # Общее представление
        shared = self.shared_fc(pooled)       # [B, 512]

        # Оценка по каждому критерию
        outputs = [head(shared) for head in self.criterion_heads]
        return outputs

    def predict_scores(self, x: torch.Tensor) -> dict:
        """
        Удобный метод для инференса.

        Returns:
            dict с оценками и вероятностями по каждому критерию
        """
        self.eval()
        with torch.no_grad():
            logits_list = self.forward(x)

        results = {}
        total = 0

        for i, logits in enumerate(logits_list):
            probs      = F.softmax(logits, dim=1)[0]
            score      = torch.argmax(probs).item()
            confidence = probs[score].item()

            results[f"K{i+1}"] = {
                "score":      score,
                "confidence": round(confidence, 3),
                "prob_0":     round(probs[0].item(), 3),
                "prob_1":     round(probs[1].item(), 3),
            }
            total += score

        results["total_score"] = total
        results["max_score"]   = self.num_criteria
        return results


def create_model(num_criteria: int = 2,
                 checkpoint_path: str = None,
                 device: str = "cpu") -> MathSolutionChecker:
    """
    Создаёт и при необходимости загружает модель из чекпоинта.
    """
    model = MathSolutionChecker(num_criteria=num_criteria)
    model = model.to(device)

    if checkpoint_path:
        state = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(state["model_state_dict"])
        print(f"✅ Загружена модель из {checkpoint_path}")
        print(f"   Эпоха: {state.get('epoch', '?')}")
        print(f"   Val accuracy: {state.get('val_accuracy', '?')}")

    return model