"""
Датасет для обучения модели проверки решений.

Структура директории с данными:
  data/solutions/
    images/
      sol_001.jpg
      sol_002.jpg
      ...
    labels.csv       ← task_number, image_file, K1, K2, K3
"""

import os
import csv
import random
from pathlib import Path

import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image, ImageOps, ImageFilter
import numpy as np
import cv2

from app.neural.preprocess import preprocess_handwriting


class MathSolutionDataset(Dataset):
    """
    Датасет рукописных решений с разметкой по критериям.

    Args:
        data_dir:      путь к директории с данными
        task_numbers:  список номеров заданий (None = все)
        split:         'train', 'val' или 'test'
        augment:       применять ли аугментацию (только для train)
    """

    def __init__(
        self,
        data_dir: str,
        task_numbers: list[int] | None = None,
        split: str = "train",
        augment: bool = True,
        image_size: int = 512,
        num_criteria: int = 2,
    ):
        self.data_dir     = Path(data_dir)
        self.split        = split
        self.augment      = augment and (split == "train")
        self.image_size   = image_size
        self.num_criteria = num_criteria

        self.samples: list[dict] = []
        self._load_labels(task_numbers)

        # Разбиваем на train/val/test (70/15/15)
        random.seed(42)
        random.shuffle(self.samples)
        n = len(self.samples)
        if split == "train":
            self.samples = self.samples[:int(0.70 * n)]
        elif split == "val":
            self.samples = self.samples[int(0.70 * n):int(0.85 * n)]
        else:
            self.samples = self.samples[int(0.85 * n):]

        print(f"📦 {split}: {len(self.samples)} примеров")

        # Трансформации
        self.base_transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

        # Аугментации для train — имитируем реальные условия фото
        self.aug_transform = transforms.Compose([
            transforms.Resize((image_size + 64, image_size + 64)),
            transforms.RandomCrop(image_size),
            transforms.RandomRotation(degrees=8),       # лист немного повёрнут
            transforms.RandomPerspective(distortion_scale=0.1, p=0.3),
            transforms.ColorJitter(
                brightness=0.4,   # разное освещение
                contrast=0.4,
                saturation=0.2,
            ),
            transforms.RandomGrayscale(p=0.1),
            transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    def _load_labels(self, task_numbers: list[int] | None):
        """Читает labels.csv и наполняет self.samples."""
        labels_path = self.data_dir / "labels.csv"

        if not labels_path.exists():
            raise FileNotFoundError(
                f"Файл разметки не найден: {labels_path}\n"
                "Создайте его с помощью data_collector.py"
            )

        with open(labels_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                task_num = int(row["task_number"])
                if task_numbers and task_num not in task_numbers:
                    continue

                image_path = self.data_dir / "images" / row["image_file"]
                if not image_path.exists():
                    continue

                # Метки по критериям (K1, K2, K3 — бинарные)
                labels = []
                for i in range(1, self.num_criteria + 1):
                    key = f"K{i}"
                    labels.append(int(row.get(key, 0)))

                self.samples.append({
                    "image_path":  str(image_path),
                    "task_number": task_num,
                    "labels":      labels,
                    "annotator":   row.get("annotator", ""),
                })

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        sample = self.samples[idx]

        # Загружаем и предобрабатываем изображение
        img_cv = cv2.imread(sample["image_path"])
        processed = preprocess_handwriting(img_cv)

        # В PIL
        if len(processed.shape) == 2:
            pil_img = Image.fromarray(processed).convert("RGB")
        else:
            pil_img = Image.fromarray(
                cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            )

        # Применяем трансформации
        if self.augment:
            tensor = self.aug_transform(pil_img)
        else:
            tensor = self.base_transform(pil_img)

        labels = torch.tensor(sample["labels"], dtype=torch.long)
        return tensor, labels


def create_dataloaders(
    data_dir: str,
    batch_size: int = 16,
    num_workers: int = 2,
    task_numbers: list[int] | None = None,
    num_criteria: int = 2,
    image_size: int = 224,             # ← добавь
) -> tuple[DataLoader, DataLoader, DataLoader]:

    kwargs = dict(
        data_dir=data_dir,
        task_numbers=task_numbers,
        num_criteria=num_criteria,
        image_size=image_size,         # ← добавь
    )

    train_ds = MathSolutionDataset(**kwargs, split="train", augment=True)
    val_ds   = MathSolutionDataset(**kwargs, split="val",   augment=False)
    test_ds  = MathSolutionDataset(**kwargs, split="test",  augment=False)

    loader_kwargs = dict(
        batch_size=batch_size,
        num_workers=num_workers,
        pin_memory=True,
    )

    train_loader = DataLoader(train_ds, shuffle=True,  **loader_kwargs)
    val_loader   = DataLoader(val_ds,   shuffle=False, **loader_kwargs)
    test_loader  = DataLoader(test_ds,  shuffle=False, **loader_kwargs)

    return train_loader, val_loader, test_loader