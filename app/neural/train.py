"""
Обучение модели MathSolutionChecker.

Запуск:
    python -m app.neural.train --data_dir data/solutions --epochs 30 --image_size 224
"""

import argparse
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import cohen_kappa_score, f1_score
import numpy as np

from app.neural.model   import MathSolutionChecker, create_model
from app.neural.dataset import create_dataloaders


def train_epoch(
    model: MathSolutionChecker,
    loader,
    optimizer: optim.Optimizer,
    criterion: nn.Module,
    device: str,
    scaler,
) -> dict:
    """Один шаг обучения."""
    model.train()

    total_loss = 0.0
    correct    = [0] * model.num_criteria
    total      = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()

        with torch.amp.autocast(device_type=device, enabled=(device == "cuda")):
            outputs = model(images)

            loss = sum(
                criterion(outputs[i], labels[:, i])
                for i in range(model.num_criteria)
            )

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item()
        total      += images.size(0)

        for i in range(model.num_criteria):
            preds = outputs[i].argmax(dim=1)
            correct[i] += (preds == labels[:, i]).sum().item()

    n_batches = len(loader)
    return {
        "loss":     total_loss / n_batches,
        "accuracy": [c / total for c in correct],
        "avg_acc":  sum(c / total for c in correct) / model.num_criteria,
    }


@torch.no_grad()
def evaluate(
    model: MathSolutionChecker,
    loader,
    criterion: nn.Module,
    device: str,
) -> dict:
    """Оценка на val/test — accuracy, F1, Cohen's kappa."""
    model.eval()

    total_loss = 0.0
    all_preds  = [[] for _ in range(model.num_criteria)]
    all_labels = [[] for _ in range(model.num_criteria)]

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        loss = sum(
            criterion(outputs[i], labels[:, i])
            for i in range(model.num_criteria)
        )
        total_loss += loss.item()

        for i in range(model.num_criteria):
            preds = outputs[i].argmax(dim=1)
            all_preds[i].extend(preds.cpu().numpy())
            all_labels[i].extend(labels[:, i].cpu().numpy())

    results = {"loss": total_loss / len(loader)}

    kappas     = []
    f1_scores  = []
    accuracies = []

    for i in range(model.num_criteria):
        p = np.array(all_preds[i])
        l = np.array(all_labels[i])

        acc   = (p == l).mean()
        kappa = cohen_kappa_score(l, p)
        f1    = f1_score(l, p, average="weighted", zero_division=0)

        results[f"K{i+1}_accuracy"] = acc
        results[f"K{i+1}_kappa"]    = kappa
        results[f"K{i+1}_f1"]       = f1

        kappas.append(kappa)
        f1_scores.append(f1)
        accuracies.append(acc)

    results["avg_accuracy"] = np.mean(accuracies)
    results["avg_kappa"]    = np.mean(kappas)
    results["avg_f1"]       = np.mean(f1_scores)
    results["kappa_interpretation"] = _interpret_kappa(results["avg_kappa"])

    return results


def _interpret_kappa(kappa: float) -> str:
    if kappa < 0.0:  return "Хуже случайного"
    if kappa < 0.2:  return "Незначительное согласие"
    if kappa < 0.4:  return "Слабое согласие"
    if kappa < 0.6:  return "Умеренное согласие"
    if kappa < 0.8:  return "Существенное согласие ✅"
    return "Почти идеальное согласие 🏆"


def train(
    data_dir: str,
    save_dir: str = "app/models/checkpoints",
    num_criteria: int = 2,
    epochs: int = 30,
    batch_size: int = 16,
    lr: float = 1e-4,
    device: str = None,
    image_size: int = 224,
    early_stopping_patience: int = 10,
):
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🖥️  Устройство: {device}")
    print(f"🖼️  Размер изображения: {image_size}×{image_size}")

    # Данные
    train_loader, val_loader, _ = create_dataloaders(
        data_dir=data_dir,
        batch_size=batch_size,
        num_criteria=num_criteria,
        image_size=image_size,
    )

    # Модель
    model = MathSolutionChecker(num_criteria=num_criteria).to(device)

    pretrained_path = "app/models/pretrain/pretrained_backbone.pt"
    if os.path.exists(pretrained_path):
        model.backbone.load_state_dict(
            torch.load(pretrained_path, map_location=device)
        )
        print("✅ Загружен предобученный backbone")
    else:
        print("⚠️  Предобученный backbone не найден — обучаем с нуля")

    total_params = sum(p.numel() for p in model.parameters())
    train_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"📊 Параметров всего: {total_params:,}")
    print(f"📊 Обучаемых: {train_params:,}")

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

    # ── Две группы параметров с самого начала ──────────────────────────────
    # Backbone сначала заморожен (lr=0.0), размораживается на середине
    for param in model.backbone.parameters():
        param.requires_grad = False

    head_params = [p for p in model.parameters() if p.requires_grad]

    optimizer = optim.AdamW([
        {"params": head_params,                 "lr": lr},
        {"params": model.backbone.parameters(), "lr": 0.0},
    ], weight_decay=1e-4)
    # ───────────────────────────────────────────────────────────────────────

    scheduler      = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler         = torch.amp.GradScaler(device, enabled=(device == "cuda"))
    best_kappa     = -1.0
    patience_count = 0
    history        = []

    Path(save_dir).mkdir(parents=True, exist_ok=True)

    print("\n🚀 Начало обучения\n" + "=" * 60)

    for epoch in range(1, epochs + 1):

        # ── Размораживаем backbone на середине — только меняем lr ──────────
        if epoch == epochs // 2:
            print("\n🔓 Размораживаем backbone для fine-tuning")
            for param in model.backbone.parameters():
                param.requires_grad = True
            optimizer.param_groups[1]["lr"] = lr * 0.1
            print(f"   backbone lr = {lr * 0.1:.2e}")
        # ───────────────────────────────────────────────────────────────────

        train_metrics = train_epoch(
            model, train_loader, optimizer, criterion, device, scaler
        )
        val_metrics = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        history.append({**train_metrics, **val_metrics, "epoch": epoch})

        print(
            f"Эпоха {epoch:3d}/{epochs} | "
            f"Train loss: {train_metrics['loss']:.4f} "
            f"acc: {train_metrics['avg_acc']:.3f} | "
            f"Val loss: {val_metrics['loss']:.4f} "
            f"kappa: {val_metrics['avg_kappa']:.3f} "
            f"({val_metrics['kappa_interpretation']})"
        )

        if val_metrics["avg_kappa"] > best_kappa:
            best_kappa     = val_metrics["avg_kappa"]
            patience_count = 0
            torch.save({
                "epoch":            epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state":  optimizer.state_dict(),
                "val_kappa":        best_kappa,
                "val_accuracy":     val_metrics["avg_accuracy"],
                "num_criteria":     num_criteria,
                "image_size":       image_size,
                "history":          history,
            }, f"{save_dir}/best_model.pt")
            print(f"  💾 Сохранена лучшая модель (kappa={best_kappa:.4f})")
        else:
            patience_count += 1
            if patience_count >= early_stopping_patience:
                print(f"\n⏹️  Early stopping на эпохе {epoch} "
                      f"(нет улучшений {early_stopping_patience} эпох)")
                break

    print(f"\n✅ Обучение завершено. Лучшая kappa: {best_kappa:.4f}")
    return history


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir",     default="data/solutions")
    parser.add_argument("--save_dir",     default="app/models/checkpoints")
    parser.add_argument("--num_criteria", type=int,   default=2)
    parser.add_argument("--epochs",       type=int,   default=30)
    parser.add_argument("--batch_size",   type=int,   default=16)
    parser.add_argument("--lr",           type=float, default=1e-4)
    parser.add_argument("--image_size",   type=int,   default=224)
    parser.add_argument("--patience",     type=int,   default=10)
    args = parser.parse_args()

    train(
        data_dir=args.data_dir,
        save_dir=args.save_dir,
        num_criteria=args.num_criteria,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        image_size=args.image_size,
        early_stopping_patience=args.patience,
    )