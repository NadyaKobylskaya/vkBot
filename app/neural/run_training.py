"""
Запуск обучения модели OGE Checker.

Что исправлено по сравнению с оригинальным train.py:
  1. Группировка split по task_condition (одно условие — только в train ИЛИ val)
  2. Взвешенный CrossEntropyLoss (борьба с дисбалансом меток)
  3. Early stopping с patience=7
  4. Пониженный batch_size=8 (оптимально для ~260 train примеров)
  5. История сохраняется в checkpoint — совместима с monitor_training.py
  6. --resume: продолжить обучение с лучшего чекпоинта
  7. --try_seeds: перебрать несколько seed и взять лучший split
  8. Резервная копия: best_model_backup.pt не перезаписывается новыми запусками

Требования:
  - data/solutions/labels.csv     (создаётся через export_labels.py)
  - data/solutions/images/*.png   (фото решений)
  - app/models/pretrain/pretrained_backbone.pt  (опционально)

Запуск:
  python run_training.py                        # обычный запуск
  python run_training.py --resume               # продолжить с чекпоинта
  python run_training.py --try_seeds            # перебрать seed 42,7,13,99,2024
  python run_training.py --epochs 40 --lr 5e-5
"""

import argparse
import csv
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import cohen_kappa_score, f1_score, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import transforms
from PIL import Image

# ──────────────────────────────────────────────────────────────────────────────
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# ──────────────────────────────────────────────────────────────────────────────

DEFAULTS = dict(
    data_dir   = "data/solutions",
    save_dir   = "app/models/checkpoints",
    pretrain   = "app/models/pretrain/pretrained_backbone.pt",
    epochs     = 35,
    batch_size = 8,
    lr         = 1e-4,
    image_size = 224,
    patience   = 7,
    val_ratio  = 0.18,
    seed       = 42,
    resume     = False,
    try_seeds  = False,
)

# Набор seed для перебора (--try_seeds)
SEED_CANDIDATES = [42, 7, 13, 99, 2024]

CRITERIA_NAMES = ["K1", "K2"]
NUM_CRITERIA   = 2


# ──────────────────────────────────────────────────────────────────────────────
# ШАГ 1: ПРАВИЛЬНЫЙ SPLIT (по группам условий, без утечки)
# ──────────────────────────────────────────────────────────────────────────────

def load_csv(data_dir: str) -> list[dict]:
    """Читает labels.csv, возвращает список записей."""
    path = Path(data_dir) / "labels.csv"
    if not path.exists():
        sys.exit(
            f"\n❌ Файл не найден: {path}\n"
            "   Сначала запусти:\n"
            "     python import_from_excel.py dataset_template.xlsx\n"
            "     python export_labels.py\n"
        )

    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Оставляем только те, у которых есть изображение
    images_dir = Path(data_dir) / "images"
    valid = []
    missing = 0
    for row in rows:
        img = images_dir / row["image_file"]
        if img.exists():
            valid.append(row)
        else:
            missing += 1

    if missing:
        print(f"⚠️  Не найдено изображений: {missing} шт. (пропускаем)")

    if not valid:
        sys.exit("\n❌ Ни одного изображения не найдено в data/solutions/images/\n"
                 "   Положи фото решений в эту папку и перезапусти.")

    return valid


def grouped_split(rows: list[dict], val_ratio: float, seed: int):
    """
    Делит данные на train/val по группам task_condition.
    Одно и то же условие задачи попадает ТОЛЬКО в одну часть.
    """
    # Группируем по условию
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        key = row.get("task_condition", row["image_file"])
        groups[key].append(row)

    keys = list(groups.keys())
    rng = random.Random(seed)
    rng.shuffle(keys)

    n_val  = max(1, int(len(keys) * val_ratio))
    val_keys   = set(keys[:n_val])
    train_keys = set(keys[n_val:])

    train_rows = [r for k in train_keys for r in groups[k]]
    val_rows   = [r for k in val_keys   for r in groups[k]]

    return train_rows, val_rows


# ──────────────────────────────────────────────────────────────────────────────
# ШАГ 2: ДАТАСЕТ
# ──────────────────────────────────────────────────────────────────────────────

def make_transforms(image_size: int, augment: bool):
    if augment:
        return transforms.Compose([
            transforms.Resize((image_size + 64, image_size + 64)),
            transforms.RandomCrop(image_size),
            transforms.RandomRotation(10),
            transforms.RandomPerspective(distortion_scale=0.1, p=0.3),
            transforms.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.2),
            transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406],
                                 [0.229, 0.224, 0.225]),
            transforms.RandomErasing(p=0.15, scale=(0.02, 0.1)),
        ])
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406],
                             [0.229, 0.224, 0.225]),
    ])


class SolutionDataset(Dataset):
    def __init__(self, rows: list[dict], data_dir: str,
                 image_size: int, augment: bool):
        self.rows      = rows
        self.images_dir = Path(data_dir) / "images"
        self.transform  = make_transforms(image_size, augment)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        row = self.rows[idx]
        img_path = self.images_dir / row["image_file"]

        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            # Если файл битый — белый лист
            img = Image.new("RGB", (224, 224), (255, 255, 255))

        tensor = self.transform(img)
        labels = torch.tensor(
            [int(row.get("K1", 0)), int(row.get("K2", 0))],
            dtype=torch.long,
        )
        return tensor, labels


# ──────────────────────────────────────────────────────────────────────────────
# ШАГ 3: ВЗВЕШЕННЫЙ LOSS (борьба с дисбалансом)
# ──────────────────────────────────────────────────────────────────────────────

def make_criterion(train_rows: list[dict], device: str) -> nn.Module:
    """
    Вычисляет веса классов по обучающей выборке.
    Редкий класс получает больший вес → модель не игнорирует его.
    """
    weights_per_criterion = []
    for ki in ["K1", "K2"]:
        labels = [int(r.get(ki, 0)) for r in train_rows]
        unique = sorted(set(labels))
        w = compute_class_weight("balanced", classes=np.array(unique),
                                 y=np.array(labels))
        # Гарантируем длину 2 (на случай если только один класс в train)
        full_w = np.ones(2)
        for cls, weight in zip(unique, w):
            full_w[cls] = weight
        weights_per_criterion.append(
            torch.tensor(full_w, dtype=torch.float).to(device)
        )

    class MultiCritLoss(nn.Module):
        def __init__(self, weights):
            super().__init__()
            self.crits = nn.ModuleList([
                nn.CrossEntropyLoss(weight=w, label_smoothing=0.05)
                for w in weights
            ])
        def forward(self, outputs, labels):
            return sum(
                self.crits[i](outputs[i], labels[:, i])
                for i in range(len(self.crits))
            )

    criterion = MultiCritLoss(weights_per_criterion)
    print("⚖️  Веса классов:")
    for i, w in enumerate(weights_per_criterion):
        print(f"   K{i+1}: класс 0 → {w[0]:.3f}, класс 1 → {w[1]:.3f}")
    return criterion


# ──────────────────────────────────────────────────────────────────────────────
# ШАГ 4: МОДЕЛЬ
# ──────────────────────────────────────────────────────────────────────────────

def load_model(pretrain_path: str, device: str,
               resume_path: str = None):
    """Загружает модель. При --resume грузит веса из чекпоинта."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from app.neural.model import MathSolutionChecker
        model = MathSolutionChecker(num_criteria=NUM_CRITERIA).to(device)
    except ImportError:
        sys.exit(
            "\n❌ Не могу импортировать MathSolutionChecker.\n"
            "   Убедись, что запускаешь скрипт из корня проекта:\n"
            "     cd /path/to/project && python run_training.py\n"
        )

    # Режим resume: грузим полные веса модели
    if resume_path and Path(resume_path).exists():
        try:
            ckpt = torch.load(resume_path, map_location=device,
                              weights_only=False)
            model.load_state_dict(ckpt["model_state_dict"])
            prev_kappa = ckpt.get("val_kappa", 0.0)
            print(f"✅ Resume: загружен чекпоинт {resume_path}")
            print(f"   Предыдущая лучшая kappa: {prev_kappa:.4f}")
            return model, prev_kappa
        except Exception as e:
            print(f"⚠️  Resume не удался ({e}), стартуем заново")

    # Обычный режим: грузим только backbone
    if Path(pretrain_path).exists():
        try:
            state = torch.load(pretrain_path, map_location=device,
                               weights_only=True)
            model.backbone.load_state_dict(state)
            print(f"✅ Загружен предобученный backbone: {pretrain_path}")
        except Exception as e:
            print(f"⚠️  Backbone не загружен ({e}), стартуем с ImageNet весами")
    else:
        print(f"⚠️  Pretrain не найден ({pretrain_path}), используем ImageNet")

    return model, -1.0


# ──────────────────────────────────────────────────────────────────────────────
# ШАГ 5: ЦИКЛ ОБУЧЕНИЯ
# ──────────────────────────────────────────────────────────────────────────────

def train_epoch(model, loader, optimizer, criterion, device, scaler) -> dict:
    model.train()
    total_loss = 0.0
    correct    = [0] * NUM_CRITERIA
    total      = 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()

        with torch.amp.autocast(device_type=device,
                                enabled=(device == "cuda")):
            outputs = model(images)
            loss    = criterion(outputs, labels)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item()
        total      += images.size(0)
        for i in range(NUM_CRITERIA):
            preds = outputs[i].argmax(dim=1)
            correct[i] += (preds == labels[:, i]).sum().item()

    n = len(loader)
    return {
        "loss":    total_loss / n,
        "avg_acc": sum(c / total for c in correct) / NUM_CRITERIA,
    }


@torch.no_grad()
def evaluate(model, loader, criterion, device) -> dict:
    model.eval()
    total_loss = 0.0
    all_preds  = [[] for _ in range(NUM_CRITERIA)]
    all_labels = [[] for _ in range(NUM_CRITERIA)]

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        total_loss += criterion(outputs, labels).item()

        for i in range(NUM_CRITERIA):
            preds = outputs[i].argmax(dim=1)
            all_preds[i].extend(preds.cpu().numpy())
            all_labels[i].extend(labels[:, i].cpu().numpy())

    results = {"loss": total_loss / len(loader)}
    kappas, f1s, accs = [], [], []

    for i in range(NUM_CRITERIA):
        p = np.array(all_preds[i])
        l = np.array(all_labels[i])

        acc   = float((p == l).mean())
        kappa = float(cohen_kappa_score(l, p))
        f1    = float(f1_score(l, p, average="macro", zero_division=0))

        results[f"K{i+1}_accuracy"] = acc
        results[f"K{i+1}_kappa"]    = kappa
        results[f"K{i+1}_f1"]       = f1
        # Confusion matrix для диагностики
        results[f"K{i+1}_cm"]       = confusion_matrix(l, p).tolist()

        kappas.append(kappa)
        f1s.append(f1)
        accs.append(acc)

    results["avg_kappa"]    = float(np.mean(kappas))
    results["avg_f1"]       = float(np.mean(f1s))
    results["avg_accuracy"] = float(np.mean(accs))

    def interp(k):
        if k < 0.0:  return "хуже случайного 🔴"
        if k < 0.2:  return "незначительное 🔴"
        if k < 0.4:  return "слабое 🟠"
        if k < 0.6:  return "умеренное 🟡"
        if k < 0.8:  return "существенное 🟢"
        return "почти идеальное 🏆"

    results["kappa_interpretation"] = interp(results["avg_kappa"])
    return results


def print_confusion(cm: list, criterion_name: str):
    """Печатает confusion matrix в читаемом виде."""
    print(f"\n   {criterion_name} Confusion matrix:")
    print(f"              Предсказано 0  Предсказано 1")
    for i, row in enumerate(cm):
        label = "Реально 0    " if i == 0 else "Реально 1    "
        print(f"   {label}  {str(row[0]):>6}         {str(row[1]):>6}")


# ──────────────────────────────────────────────────────────────────────────────
# ГЛАВНАЯ ФУНКЦИЯ
# ──────────────────────────────────────────────────────────────────────────────

def train(cfg: dict):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(cfg["seed"])
    random.seed(cfg["seed"])

    print("\n" + "═" * 62)
    print("  OGE Checker — Запуск обучения")
    print("═" * 62)
    print(f"  Устройство:    {device}")
    print(f"  Эпох:          {cfg['epochs']}  (early stop через {cfg['patience']})")
    print(f"  Batch size:    {cfg['batch_size']}")
    print(f"  Learning rate: {cfg['lr']:.2e}")
    print(f"  Image size:    {cfg['image_size']}×{cfg['image_size']}")
    if cfg.get("resume"):
        print(f"  Режим:         RESUME (продолжение с чекпоинта)")
    if cfg.get("try_seeds"):
        print(f"  Режим:         MULTI-SEED (перебор {SEED_CANDIDATES})")
    print("═" * 62 + "\n")

    # ── Данные ──────────────────────────────────────────────────────────
    print("📂 Загрузка данных...")
    all_rows = load_csv(cfg["data_dir"])

    # ── Выбор лучшего seed ──────────────────────────────────────────────
    if cfg.get("try_seeds"):
        print("\n🔍 Подбор лучшего seed по балансу val выборки...")
        best_seed, best_score = cfg["seed"], -1.0
        for s in SEED_CANDIDATES:
            tr, vl = grouped_split(all_rows, cfg["val_ratio"], s)
            # Оцениваем баланс: чем ближе к 50/50 по K1 и K2 в val — тем лучше
            scores = []
            for ki in ["K1", "K2"]:
                vals = [int(r.get(ki, 0)) for r in vl]
                if len(vals) == 0: continue
                ratio = min(vals.count(0), vals.count(1)) / len(vals)
                scores.append(ratio)
            score = float(np.mean(scores)) if scores else 0.0
            print(f"   seed={s}: val={len(vl)} шт, баланс={score:.3f} "
                  f"({'⭐' if score > best_score else ''})")
            if score > best_score:
                best_score = score
                best_seed  = s
        cfg["seed"] = best_seed
        torch.manual_seed(best_seed)
        random.seed(best_seed)
        print(f"\n   ✅ Выбран seed={best_seed} (баланс={best_score:.3f})\n")

    train_rows, val_rows = grouped_split(
        all_rows, cfg["val_ratio"], cfg["seed"]
    )

    print(f"\n📊 Размер выборок (seed={cfg['seed']}, группировка по условию):")
    print(f"   Train: {len(train_rows)} примеров")
    print(f"   Val:   {len(val_rows)} примеров")

    print("\n📊 Баланс меток в train:")
    for ki in ["K1", "K2"]:
        vals = [int(r.get(ki, 0)) for r in train_rows]
        n0, n1 = vals.count(0), vals.count(1)
        print(f"   {ki}: 0→{n0}  1→{n1}  "
              f"(соотношение {n0/(n0+n1)*100:.0f}% / {n1/(n0+n1)*100:.0f}%)")

    # DataLoader
    train_ds = SolutionDataset(train_rows, cfg["data_dir"],
                               cfg["image_size"], augment=True)
    val_ds   = SolutionDataset(val_rows,   cfg["data_dir"],
                               cfg["image_size"], augment=False)

    nw = min(2, os.cpu_count() or 1)
    train_loader = DataLoader(train_ds, batch_size=cfg["batch_size"],
                              shuffle=True, num_workers=nw, pin_memory=False)
    val_loader   = DataLoader(val_ds,   batch_size=cfg["batch_size"],
                              shuffle=False, num_workers=nw, pin_memory=False)

    # ── Модель ──────────────────────────────────────────────────────────
    print("\n🧠 Загрузка модели...")
    save_path   = Path(cfg["save_dir"]) / "best_model.pt"
    resume_path = str(save_path) if cfg.get("resume") else None

    model, prev_best_kappa = load_model(
        cfg["pretrain"], device, resume_path=resume_path
    )

    total = sum(p.numel() for p in model.parameters())
    print(f"   Параметров: {total:,}")

    # ── Loss с весами ───────────────────────────────────────────────────
    print("\n⚖️  Вычисление весов классов...")
    criterion = make_criterion(train_rows, device)

    # ── Оптимизатор ─────────────────────────────────────────────────────
    if cfg.get("resume"):
        # Resume: все слои обучаемы, но backbone с маленьким lr
        for p in model.backbone.parameters():
            p.requires_grad = True
        optimizer = optim.AdamW([
            {"params": [p for n, p in model.named_parameters()
                        if "backbone" not in n], "lr": cfg["lr"] * 0.5},
            {"params": model.backbone.parameters(),  "lr": cfg["lr"] * 0.05},
        ], weight_decay=1e-4)
        backbone_unfrozen = True
        print("   Режим resume: backbone разморожен с lr×0.05")
    else:
        # Обычный: backbone заморожен до середины обучения
        for p in model.backbone.parameters():
            p.requires_grad = False
        head_params = [p for p in model.parameters() if p.requires_grad]
        optimizer   = optim.AdamW([
            {"params": head_params,                 "lr": cfg["lr"]},
            {"params": model.backbone.parameters(), "lr": 0.0},
        ], weight_decay=1e-4)
        backbone_unfrozen = False

    scheduler = CosineAnnealingLR(optimizer, T_max=cfg["epochs"], eta_min=1e-6)
    scaler    = torch.amp.GradScaler(device, enabled=(device == "cuda"))

    # ── Пути сохранения ─────────────────────────────────────────────────
    Path(cfg["save_dir"]).mkdir(parents=True, exist_ok=True)
    # Резервная копия — не перезаписывается следующими запусками
    backup_path = Path(cfg["save_dir"]) / "best_model_backup.pt"

    best_kappa     = prev_best_kappa  # стартуем с предыдущей kappa при resume
    patience_count = 0
    history        = []

    print("\n🚀 Начало обучения\n" + "─" * 62)

    for epoch in range(1, cfg["epochs"] + 1):

        # Размораживаем backbone на середине (только в обычном режиме)
        if not backbone_unfrozen and epoch >= cfg["epochs"] // 2:
            for p in model.backbone.parameters():
                p.requires_grad = True
            optimizer.param_groups[1]["lr"] = cfg["lr"] * 0.1
            backbone_unfrozen = True
            print(f"\n🔓 Эпоха {epoch}: размораживаем backbone "
                  f"(lr={cfg['lr']*0.1:.2e})\n")

        train_m = train_epoch(model, train_loader, optimizer,
                              criterion, device, scaler)
        val_m   = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        rec = {
            "epoch":        epoch,
            "loss":         train_m["loss"],
            "avg_acc":      train_m["avg_acc"],
            "avg_kappa":    val_m["avg_kappa"],
            "avg_f1":       val_m["avg_f1"],
            "avg_accuracy": val_m["avg_accuracy"],
            **{f"K{i+1}_kappa":    val_m[f"K{i+1}_kappa"]    for i in range(NUM_CRITERIA)},
            **{f"K{i+1}_accuracy": val_m[f"K{i+1}_accuracy"] for i in range(NUM_CRITERIA)},
            **{f"K{i+1}_f1":       val_m[f"K{i+1}_f1"]       for i in range(NUM_CRITERIA)},
        }
        history.append(rec)

        is_best = val_m["avg_kappa"] > best_kappa
        marker  = " ⭐" if is_best else ""

        print(
            f"Эп {epoch:3d}/{cfg['epochs']} | "
            f"train loss={train_m['loss']:.4f} acc={train_m['avg_acc']:.3f} | "
            f"val kappa={val_m['avg_kappa']:.3f} "
            f"({val_m['kappa_interpretation']}) "
            f"f1={val_m['avg_f1']:.3f}{marker}"
        )

        if is_best:
            best_kappa     = val_m["avg_kappa"]
            patience_count = 0

            for i in range(NUM_CRITERIA):
                print_confusion(val_m[f"K{i+1}_cm"], f"K{i+1}")
            print()

            checkpoint = {
                "epoch":            epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state":  optimizer.state_dict(),
                "val_kappa":        best_kappa,
                "val_accuracy":     val_m["avg_accuracy"],
                "num_criteria":     NUM_CRITERIA,
                "image_size":       cfg["image_size"],
                "history":          history,
                "config":           cfg,
            }
            torch.save(checkpoint, save_path)
            print(f"   💾 Сохранено: {save_path} (kappa={best_kappa:.4f})\n")

            # Резервная копия — перезаписываем только если лучше глобального рекорда
            if not backup_path.exists():
                torch.save(checkpoint, backup_path)
                print(f"   🔒 Резервная копия: {backup_path}\n")
            else:
                try:
                    prev = torch.load(backup_path, map_location="cpu",
                                      weights_only=False)
                    if best_kappa > prev.get("val_kappa", 0.0):
                        torch.save(checkpoint, backup_path)
                        print(f"   🔒 Резервная копия обновлена: "
                              f"{prev.get('val_kappa',0):.4f} → {best_kappa:.4f}\n")
                except Exception:
                    torch.save(checkpoint, backup_path)
        else:
            patience_count += 1
            if patience_count >= cfg["patience"]:
                print(f"\n⏹️  Early stopping на эпохе {epoch} "
                      f"(нет улучшений {cfg['patience']} эпох подряд)")
                break

    # ── Итог ────────────────────────────────────────────────────────────
    print("\n" + "═" * 62)
    print("✅ ОБУЧЕНИЕ ЗАВЕРШЕНО")
    print("═" * 62)
    print(f"   Лучшая Kappa:     {best_kappa:.4f}")
    print(f"   Чекпоинт:         {save_path}")
    print(f"   Резервная копия:  {backup_path}")
    print()

    if best_kappa >= 0.6:
        verdict = "Отличный результат — существенное согласие с экспертом 🟢"
    elif best_kappa >= 0.4:
        verdict = "Хороший результат для диплома — умеренное согласие 🟡"
    elif best_kappa >= 0.2:
        verdict = "Слабый результат, нужно больше данных 🟠"
    else:
        verdict = "Плохой результат — проверь разметку и данные 🔴"

    print(f"   Оценка: {verdict}")
    print()
    print("   Следующие шаги:")
    print("   1. Дашборд:    python monitor_training.py")
    if best_kappa < 0.4:
        print("   2. Продолжи:   python run_training.py --resume")
        print("   3. Или добавь данные и переобучи заново")
    else:
        print("   2. Тестируй:   python inference.py")
    print("═" * 62 + "\n")

    return history


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Обучение OGE Checker с исправленным split и взвешенным loss"
    )
    parser.add_argument("--data_dir",   default=DEFAULTS["data_dir"])
    parser.add_argument("--save_dir",   default=DEFAULTS["save_dir"])
    parser.add_argument("--pretrain",   default=DEFAULTS["pretrain"])
    parser.add_argument("--epochs",     type=int,   default=DEFAULTS["epochs"])
    parser.add_argument("--batch_size", type=int,   default=DEFAULTS["batch_size"])
    parser.add_argument("--lr",         type=float, default=DEFAULTS["lr"])
    parser.add_argument("--image_size", type=int,   default=DEFAULTS["image_size"])
    parser.add_argument("--patience",   type=int,   default=DEFAULTS["patience"])
    parser.add_argument("--val_ratio",  type=float, default=DEFAULTS["val_ratio"])
    parser.add_argument("--seed",       type=int,   default=DEFAULTS["seed"])
    parser.add_argument("--resume",     action="store_true",
                        help="Продолжить обучение с лучшего чекпоинта")
    parser.add_argument("--try_seeds",  action="store_true",
                        help="Перебрать несколько seed и выбрать лучший split")
    args = parser.parse_args()

    train(vars(args))