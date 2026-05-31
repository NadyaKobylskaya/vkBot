"""
Предобучение backbone на открытых датасетах рукописной математики.

Этапы:
  1. MNIST Extended — цифры + математические символы
  2. Синтетические математические выражения (генерируем сами)

Запуск:
  python -m app.neural.pretrain
"""

import os
import math
import random
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, ConcatDataset
from torchvision import transforms, datasets
from torchvision.models import efficientnet_b3, EfficientNet_B3_Weights
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from tqdm import tqdm


PRETRAIN_DIR    = Path("app/models/pretrain")
CHECKPOINT_PATH = PRETRAIN_DIR / "pretrained_backbone.pt"
DATA_CACHE_DIR  = Path("data/pretrain_cache")


# ════════════════════════════════════════════════════════════════════════
# ДАТАСЕТ 1: MNIST — рукописные цифры
# Загружается автоматически через torchvision
# ════════════════════════════════════════════════════════════════════════

def get_mnist_dataset(split: str = "train") -> Dataset:
    """
    MNIST: 70 000 изображений рукописных цифр 0–9.
    Загружается автоматически в data/pretrain_cache/mnist/
    """
    transform = transforms.Compose([
        # Расширяем до 64x64 (цифры маленькие, нам нужнее контекст)
        transforms.Resize((64, 64)),
        # Переводим в RGB (backbone ожидает 3 канала)
        transforms.Grayscale(num_output_channels=3),
        # Случайные трансформации для имитации рукописи на листе
        transforms.RandomRotation(degrees=15),
        transforms.RandomAffine(
            degrees=0,
            translate=(0.1, 0.1),
            scale=(0.8, 1.2),
        ),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
    ])

    is_train = (split == "train")
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    return datasets.MNIST(
        root=str(DATA_CACHE_DIR / "mnist"),
        train=is_train,
        download=True,
        transform=transform,
    )


# ════════════════════════════════════════════════════════════════════════
# ДАТАСЕТ 2: Синтетические математические выражения
# Генерируем сами — не нужен интернет
# ════════════════════════════════════════════════════════════════════════

# Классы: что умеет распознавать сеть после предобучения
MATH_SYMBOLS = [
    # Цифры (дублируем из MNIST для баланса)
    "0","1","2","3","4","5","6","7","8","9",
    # Операции
    "+", "-", "×", "÷", "=", "≠", "≤", "≥", "<", ">",
    # Переменные
    "x", "y", "z", "a", "b", "c", "n",
    # Спецсимволы
    "√", "²", "³", "(", ")", "[", "]", "/", ".",
    # Буквы греческого алфавита (в геометрии)
    "α", "β", "γ", "π",
]

# Шаблоны выражений для обучения распознаванию контекста
EXPRESSION_TEMPLATES = [
    # Линейные уравнения
    "2x + 3 = 7",   "5x - 2 = 13",  "x/3 = 4",
    "3(x+1) = 12",  "-2x + 6 = 0",  "x + 7 = 15",

    # Квадратные уравнения
    "x² + 5x + 6 = 0",   "x² - 9 = 0",
    "2x² + 3x - 2 = 0",  "x² - 4x + 4 = 0",
    "(x-2)(x+3) = 0",    "x² = 16",

    # Неравенства
    "2x + 1 > 5",   "x - 3 ≤ 7",
    "x² - 4 ≥ 0",   "-x + 2 < 0",

    # Дроби
    "x/2 + 1/3 = 5/6",  "(x+1)/3 = 2",
    "1/x = 0.5",         "3/4 · x = 6",

    # Корни
    "√(x+1) = 3",   "√x = 5",
    "√(2x-1) = x",  "√25 = 5",

    # Степени
    "x³ + x² - x - 1 = 0",
    "2x³ - 8x = 0",
    "x⁴ = 16",

    # Геометрия
    "S = a × b",     "P = 2(a + b)",
    "c² = a² + b²",  "S = πr²",
    "tg α = a/b",    "sin²α + cos²α = 1",

    # Системы уравнений (записываем в строку)
    "x + y = 5; x - y = 1",
    "2x + y = 7; x - y = 2",
    "x² + y² = 25; y = x + 1",

    # Прогрессии
    "aₙ = a₁ + d(n-1)",
    "Sₙ = n(a₁ + aₙ)/2",
    "bₙ = b₁ · qⁿ⁻¹",

    # Ответы (часто встречаются в рукописных решениях)
    "Ответ: x = -3",     "Ответ: x₁=2, x₂=-1",
    "x = (-b ± √D) / 2a","D = b² - 4ac",
]


class SyntheticMathDataset(Dataset):
    """
    Датасет синтетических изображений математических выражений.

    Генерирует изображения текста с имитацией:
    - разного почерка (разные шрифты, размеры)
    - разного освещения и шума
    - разных углов наклона листа
    - тетрадной бумаги в фоне
    """

    def __init__(
        self,
        num_samples: int = 5000,
        image_size:  int = 224,
        split:       str = "train",
    ):
        self.num_samples = num_samples
        self.image_size  = image_size
        self.split       = split

        # Фиксируем seed для воспроизводимости val/test
        if split != "train":
            random.seed(42 + hash(split))

        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        # Генерируем изображение
        text  = random.choice(EXPRESSION_TEMPLATES)
        image = self._generate_image(text)

        # Метка: сложность выражения (0=простое, 1=среднее, 2=сложное)
        # Используется как surrogate task для предобучения
        label = self._estimate_complexity(text)

        tensor = self.transform(image)
        return tensor, torch.tensor(label, dtype=torch.long)

    def _generate_image(self, text: str) -> Image.Image:
        """Генерирует изображение с рукописным математическим текстом."""
        size = (self.image_size * 2, self.image_size * 2)

        # Фон: тетрадный лист (белый с голубыми линиями)
        bg_color = (
            random.randint(245, 255),
            random.randint(245, 255),
            random.randint(240, 252),
        )
        img  = Image.new("RGB", size, color=bg_color)
        draw = ImageDraw.Draw(img)

        # Рисуем линии тетради
        line_color = (
            random.randint(180, 210),
            random.randint(200, 230),
            random.randint(220, 245),
        )
        line_spacing = random.randint(28, 36)
        for y in range(line_spacing, size[1], line_spacing):
            y_jitter = random.randint(-1, 1)
            draw.line(
                [(10, y + y_jitter), (size[0] - 10, y + y_jitter)],
                fill=line_color, width=1
            )

        # Цвет текста (тёмно-синий или чёрный — как ручка)
        text_color = (
            random.randint(0, 40),
            random.randint(0, 40),
            random.randint(30, 80),
        )

        # Позиция текста
        x = random.randint(20, 80)
        y = random.randint(40, size[1] // 3)

        # Пробуем разные шрифты
        font_size = random.randint(28, 52)
        font = self._get_font(font_size)

        # Рисуем текст (возможно многострочный)
        lines = text.split(";")
        for line in lines:
            # Небольшое дрожание — имитация руки
            x_off = random.randint(-4, 4)
            y_off = random.randint(-2, 2)
            draw.text((x + x_off, y + y_off), line.strip(),
                      fill=text_color, font=font)
            y += font_size + random.randint(8, 16)

        # Добавляем шум
        img = self._add_noise(img)

        # Случайный поворот (лист немного наклонён)
        angle = random.uniform(-8, 8)
        img = img.rotate(angle, fillcolor=bg_color)

        # Случайный перспективный сдвиг (фото под углом)
        if random.random() < 0.3:
            img = self._random_perspective(img)

        return img.resize((self.image_size, self.image_size), Image.LANCZOS)

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        """Пробует загрузить системный шрифт."""
        # Список стандартных шрифтов на разных ОС
        font_candidates = [
            # Windows
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/courier.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
            # Mac
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
        for path in font_candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue

        return ImageFont.load_default()

    def _add_noise(self, image: Image.Image) -> Image.Image:
        """Добавляет реалистичный шум фотографирования."""
        arr = np.array(image, dtype=np.float32)

        # Гауссов шум
        noise = np.random.normal(0, random.uniform(3, 12), arr.shape)
        arr   = np.clip(arr + noise, 0, 255).astype(np.uint8)

        result = Image.fromarray(arr)

        # Пятна от ручки / стирания
        draw = ImageDraw.Draw(result)
        for _ in range(random.randint(0, 8)):
            x = random.randint(0, image.width)
            y = random.randint(0, image.height)
            r = random.randint(1, 5)
            alpha = random.randint(30, 120)
            color = (
                random.randint(0, 60),
                random.randint(0, 60),
                random.randint(0, 80),
            )
            draw.ellipse([x-r, y-r, x+r, y+r], fill=color)

        return result

    def _random_perspective(self, image: Image.Image) -> Image.Image:
        """Лёгкое перспективное искажение."""
        import torchvision.transforms.functional as F
        tensor = transforms.ToTensor()(image)
        tensor = transforms.RandomPerspective(
            distortion_scale=0.15, p=1.0
        )(tensor)
        return transforms.ToPILImage()(tensor)

    def _estimate_complexity(self, text: str) -> int:
        """
        Оценивает сложность выражения как surrogate label.
        0 = простое (цифры, простые операции)
        1 = среднее (уравнения, неравенства)
        2 = сложное (системы, степени, корни)
        """
        if any(s in text for s in ["√", "²", "³", "⁴", ";"]):
            return 2
        if any(s in text for s in ["x²", "x³", "(", "≤", "≥"]):
            return 1
        return 0


# ════════════════════════════════════════════════════════════════════════
# BACKBONE для предобучения
# ════════════════════════════════════════════════════════════════════════

class PretrainBackbone(nn.Module):
    """
    Модель для предобучения.
    Тот же EfficientNet-B3, но с простой классификационной головой.
    После предобучения backbone переносится в MathSolutionChecker.
    """

    def __init__(self, num_classes: int = 3):
        super().__init__()

        backbone = efficientnet_b3(weights=EfficientNet_B3_Weights.DEFAULT)
        self.features = backbone.features   # [B, 1536, H', W']

        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(1536, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.features(x)
        return self.head(features)

    def get_backbone_state(self) -> dict:
        """Возвращает только веса backbone для переноса."""
        return self.features.state_dict()


# ════════════════════════════════════════════════════════════════════════
# ЦИКЛ ПРЕДОБУЧЕНИЯ
# ════════════════════════════════════════════════════════════════════════

def pretrain(
    epochs_mnist:     int   = 5,
    epochs_synthetic: int   = 10,
    batch_size:       int   = 32,
    lr:               float = 3e-4,
    device:           str   = None,
):
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"🖥️  Устройство: {device}")
    PRETRAIN_DIR.mkdir(parents=True, exist_ok=True)

    # ── Этап 1: MNIST ───────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("📦 ЭТАП 1: Предобучение на MNIST (цифры 0–9)")
    print("   Загрузка датасета...")
    print("═" * 60)

    mnist_train = get_mnist_dataset("train")
    mnist_val   = get_mnist_dataset("test")

    mnist_train_loader = DataLoader(
        mnist_train, batch_size=batch_size,
        shuffle=True, num_workers=0, pin_memory=(device=="cuda")
    )
    mnist_val_loader = DataLoader(
        mnist_val, batch_size=batch_size,
        shuffle=False, num_workers=0
    )

    print(f"   Train: {len(mnist_train):,} примеров")
    print(f"   Val:   {len(mnist_val):,} примеров")

    # Модель для MNIST (10 классов — цифры 0–9)
    model_mnist = PretrainBackbone(num_classes=10).to(device)

    optimizer = optim.AdamW(
        model_mnist.parameters(), lr=lr, weight_decay=1e-4
    )
    scheduler = optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr=lr,
        steps_per_epoch=len(mnist_train_loader),
        epochs=epochs_mnist,
    )
    criterion = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler(device, enabled=(device == "cuda"))

    best_acc = 0.0

    for epoch in range(1, epochs_mnist + 1):
        # Train
        model_mnist.train()
        train_loss   = 0.0
        train_correct = 0
        train_total   = 0

        pbar = tqdm(
            mnist_train_loader,
            desc=f"MNIST Эпоха {epoch}/{epochs_mnist}",
            leave=False
        )
        for images, labels in pbar:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()

            with torch.amp.autocast(device_type=device, enabled=(device=="cuda")):
                outputs = model_mnist(images)
                loss    = criterion(outputs, labels)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()

            train_loss    += loss.item()
            preds          = outputs.argmax(dim=1)
            train_correct += (preds == labels).sum().item()
            train_total   += labels.size(0)

            pbar.set_postfix(
                loss=f"{loss.item():.4f}",
                acc=f"{train_correct/train_total:.3f}"
            )

        # Val
        model_mnist.eval()
        val_correct = 0
        val_total   = 0
        with torch.no_grad():
            for images, labels in mnist_val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs        = model_mnist(images)
                preds          = outputs.argmax(dim=1)
                val_correct   += (preds == labels).sum().item()
                val_total     += labels.size(0)

        val_acc   = val_correct / val_total
        train_acc = train_correct / train_total
        avg_loss  = train_loss / len(mnist_train_loader)

        print(
            f"MNIST Эпоха {epoch:2d}/{epochs_mnist} | "
            f"Loss: {avg_loss:.4f} | "
            f"Train acc: {train_acc:.3f} | "
            f"Val acc: {val_acc:.3f}"
        )

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(
                model_mnist.get_backbone_state(),
                PRETRAIN_DIR / "backbone_mnist.pt"
            )
            print(f"  💾 Сохранён backbone (val_acc={val_acc:.4f})")

    print(f"\n✅ MNIST завершён. Лучшая точность: {best_acc:.4f}")

    # ── Этап 2: Синтетические математические выражения ──────────────────
    print("\n" + "═" * 60)
    print("📦 ЭТАП 2: Предобучение на математических выражениях")
    print("   Генерация датасета (это займёт ~1 минуту)...")
    print("═" * 60)

    synth_train = SyntheticMathDataset(num_samples=8000, split="train")
    synth_val   = SyntheticMathDataset(num_samples=1000, split="val")

    synth_train_loader = DataLoader(
        synth_train, batch_size=batch_size,
        shuffle=True, num_workers=0
    )
    synth_val_loader = DataLoader(
        synth_val, batch_size=batch_size,
        shuffle=False, num_workers=0
    )

    print(f"   Train: {len(synth_train):,} примеров")
    print(f"   Val:   {len(synth_val):,} примеров")
    print(f"   Классы: 0=простое, 1=среднее, 2=сложное выражение")

    # Загружаем backbone с MNIST
    model_synth = PretrainBackbone(num_classes=3).to(device)
    if (PRETRAIN_DIR / "backbone_mnist.pt").exists():
        model_synth.features.load_state_dict(
            torch.load(
                PRETRAIN_DIR / "backbone_mnist.pt",
                map_location=device
            )
        )
        print("   ✅ Загружены веса backbone с MNIST")

    optimizer = optim.AdamW(
        model_synth.parameters(), lr=lr * 0.5, weight_decay=1e-4
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs_synthetic, eta_min=1e-6
    )

    best_acc_synth = 0.0

    for epoch in range(1, epochs_synthetic + 1):
        # Train
        model_synth.train()
        train_loss    = 0.0
        train_correct = 0
        train_total   = 0

        pbar = tqdm(
            synth_train_loader,
            desc=f"Synth Эпоха {epoch}/{epochs_synthetic}",
            leave=False
        )
        for images, labels in pbar:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()

            with torch.amp.autocast(device_type=device, enabled=(device=="cuda")):
                outputs = model_synth(images)
                loss    = criterion(outputs, labels)

            scaler.scale(loss).backward()
            torch.nn.utils.clip_grad_norm_(
                model_synth.parameters(), max_norm=1.0
            )
            scaler.step(optimizer)
            scaler.update()

            train_loss    += loss.item()
            preds          = outputs.argmax(dim=1)
            train_correct += (preds == labels).sum().item()
            train_total   += labels.size(0)

            pbar.set_postfix(
                loss=f"{loss.item():.4f}",
                acc=f"{train_correct/train_total:.3f}"
            )

        scheduler.step()

        # Val
        model_synth.eval()
        val_correct = 0
        val_total   = 0
        with torch.no_grad():
            for images, labels in synth_val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs        = model_synth(images)
                preds          = outputs.argmax(dim=1)
                val_correct   += (preds == labels).sum().item()
                val_total     += labels.size(0)

        val_acc   = val_correct / val_total
        train_acc = train_correct / train_total
        avg_loss  = train_loss / len(synth_train_loader)

        print(
            f"Synth Эпоха {epoch:2d}/{epochs_synthetic} | "
            f"Loss: {avg_loss:.4f} | "
            f"Train acc: {train_acc:.3f} | "
            f"Val acc: {val_acc:.3f}"
        )

        if val_acc > best_acc_synth:
            best_acc_synth = val_acc
            torch.save(
                model_synth.get_backbone_state(),
                CHECKPOINT_PATH
            )
            print(
                f"  💾 Сохранён финальный backbone"
                f" (val_acc={val_acc:.4f})"
            )

    print(f"\n✅ Синтетика завершена. Лучшая точность: {best_acc_synth:.4f}")
    print(f"\n🎉 Предобучение завершено!")
    print(f"   Финальный backbone: {CHECKPOINT_PATH}")
    print(f"\n   Следующий шаг:")
    print(f"   python -m app.neural.add_to_dataset")
    print(f"   (собери размеченные решения, затем запусти train.py)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Предобучение backbone на MNIST и синтетических данных"
    )
    parser.add_argument(
        "--epochs_mnist",     type=int,   default=5,
        help="Эпохи на MNIST (default: 5)"
    )
    parser.add_argument(
        "--epochs_synthetic", type=int,   default=10,
        help="Эпохи на синтетике (default: 10)"
    )
    parser.add_argument(
        "--batch_size",       type=int,   default=32,
        help="Размер батча (default: 32, уменьши до 8 если мало RAM)"
    )
    parser.add_argument(
        "--lr",               type=float, default=3e-4,
        help="Learning rate (default: 0.0003)"
    )
    args = parser.parse_args()

    pretrain(
        epochs_mnist=args.epochs_mnist,
        epochs_synthetic=args.epochs_synthetic,
        batch_size=args.batch_size,
        lr=args.lr,
    )