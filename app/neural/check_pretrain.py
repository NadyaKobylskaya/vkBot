# check_pretrain.py
import torch
import numpy as np
from PIL import Image
from torchvision import transforms
from app.neural.model import MathSolutionChecker

device = "cuda" if torch.cuda.is_available() else "cpu"
# Стало — используем Path и сырые строки:
from pathlib import Path

# Корень проекта — два уровня вверх от app/neural/
ROOT = Path(__file__).resolve().parent.parent.parent  # → C:\MY\chast2_neur

PRETRAINED = ROOT / "app" / "models" / "pretrain" / "pretrained_backbone.pt"
img_path = ROOT / "data" / "solutions" / "images" / "task20_001.png"

# ── 1. Проверка загрузки весов ──────────────────────────────────────────────
print("=" * 50)
print("1. Загрузка весов")

model = MathSolutionChecker(num_criteria=2).to(device)
state_dict = torch.load(PRETRAINED, map_location=device)
missing, unexpected = model.backbone.load_state_dict(state_dict, strict=False)

print(f"   Missing keys:    {missing}     ← должно быть пусто []")
print(f"   Unexpected keys: {unexpected}  ← должно быть пусто []")
print("   ✅ OK" if not missing and not unexpected else "   ⚠️  Есть расхождения!")


# ── 2. Проверка активаций: шум vs реальное фото ─────────────────────────────
print("\n2. Активации: шум vs фото")

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

model.eval()
noise = torch.randn(1, 3, 224, 224).to(device)

# Возьми любое фото из data/inbox/ или data/solutions/images/
real = transform(Image.open(img_path).convert("RGB")).unsqueeze(0).to(device)

with torch.no_grad():
    feat_noise = model.backbone(noise)
    feat_real  = model.backbone(real)

diff = (feat_real.mean() - feat_noise.mean()).abs().item()
print(f"   Шум:  mean={feat_noise.mean():.4f}  std={feat_noise.std():.4f}")
print(f"   Фото: mean={feat_real.mean():.4f}   std={feat_real.std():.4f}")
print(f"   Разница средних: {diff:.4f}")
print("   ✅ Backbone различает фото от шума" if diff > 0.1
      else "   ⚠️  Слишком мало различий — backbone мог не загрузиться")


# ── 3. Проверка замороженности весов ────────────────────────────────────────
print("\n3. Заморожен ли backbone?")

frozen   = sum(1 for p in model.backbone.parameters() if not p.requires_grad)
unfrozen = sum(1 for p in model.backbone.parameters() if p.requires_grad)
print(f"   Заморожено слоёв:    {frozen}")
print(f"   Обучаемых слоёв:     {unfrozen}")
# В твоём train.py backbone размораживается на epochs//2 эпохе
# Значит в начале он должен быть заморожен — это нормально


# ── 4. Итог ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
print("ИТОГ: предобучение загружено корректно ✅" if diff > 0.1 and not missing
      else "ИТОГ: есть проблемы, смотри пункты выше ⚠️")