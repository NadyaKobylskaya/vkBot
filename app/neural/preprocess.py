"""
Предобработка рукописных решений перед подачей в сеть.
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import torch
from torchvision import transforms


def preprocess_handwriting(image: np.ndarray) -> np.ndarray:
    """
    Полный пайплайн предобработки рукописного текста.

    1. Конвертация в grayscale
    2. Удаление шума (денойзинг)
    3. Адаптивная бинаризация (Otsu)
    4. Коррекция наклона (deskew)
    5. Нормализация размера
    """
    # 1. Grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # 2. Денойзинг — убираем зернистость фото
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # 3. Улучшение контраста (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # 4. Адаптивная бинаризация
    binary = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # 5. Коррекция наклона листа
    deskewed = _deskew(binary)

    # 6. Убираем рамки и поля (crop)
    cropped = _crop_content(deskewed)

    return cropped


def _deskew(image: np.ndarray) -> np.ndarray:
    """Выравнивает наклоненное изображение."""
    coords = np.column_stack(np.where(image < 128))
    if len(coords) == 0:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Корректируем только значительный наклон
    if abs(angle) < 0.5:
        return image

    h, w = image.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def _crop_content(image: np.ndarray, margin: int = 10) -> np.ndarray:
    """Обрезает пустые поля вокруг содержимого."""
    # Инвертируем: текст = белый фон для поиска контуров
    inv = cv2.bitwise_not(image)
    coords = cv2.findNonZero(inv)

    if coords is None:
        return image

    x, y, w, h = cv2.boundingRect(coords)
    # Добавляем отступ
    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(image.shape[1] - x, w + 2 * margin)
    h = min(image.shape[0] - y, h + 2 * margin)

    return image[y:y + h, x:x + w]


def load_and_preprocess(image_path: str,
                        target_size: tuple = (512, 512)) -> torch.Tensor:
    """
    Загружает изображение, применяет предобработку
    и возвращает тензор для подачи в модель.
    """
    # Читаем
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Не удалось прочитать изображение: {image_path}")

    # Предобработка
    processed = preprocess_handwriting(img)

    # Конвертируем обратно в RGB PIL для torchvision
    if len(processed.shape) == 2:
        processed_rgb = cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB)
    else:
        processed_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)

    pil_img = Image.fromarray(processed_rgb)

    # Нормализация под ImageNet (т.к. используем предобученный backbone)
    transform = transforms.Compose([
        transforms.Resize(target_size),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])

    return transform(pil_img).unsqueeze(0)  # добавляем batch dim