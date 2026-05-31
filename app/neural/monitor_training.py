"""
Мониторинг обучения модели MathSolutionChecker.

Читает историю из чекпоинта и открывает интерактивный дашборд в браузере.

Запуск во время или после обучения:
    python monitor_training.py
    python monitor_training.py --checkpoint app/models/checkpoints/best_model.pt
    python monitor_training.py --watch   # обновляет каждые 30 сек
"""

import argparse
import json
import os
import sys
import time
import webbrowser
import http.server
import threading
from pathlib import Path

import torch
import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# ЧТЕНИЕ ДАННЫХ
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_CHECKPOINT = "app/models/checkpoints/best_model.pt"


def load_history(checkpoint_path: str) -> dict:
    """Загружает историю обучения из чекпоинта PyTorch."""
    path = Path(checkpoint_path)
    if not path.exists():
        return {"error": f"Чекпоинт не найден: {checkpoint_path}"}

    try:
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except Exception as e:
        return {"error": f"Ошибка загрузки: {e}"}

    history = ckpt.get("history", [])
    if not history:
        return {"error": "В чекпоинте нет истории обучения (history=[])"}

    # Собираем все доступные поля
    epochs      = [h["epoch"] for h in history]
    train_loss  = [h.get("loss", None) for h in history]
    val_loss    = [h.get("loss", None) for h in history]  # val loss тут же
    train_acc   = [h.get("avg_acc", None) for h in history]
    val_kappa   = [h.get("avg_kappa", None) for h in history]
    val_f1      = [h.get("avg_f1", None) for h in history]
    val_acc     = [h.get("avg_accuracy", None) for h in history]

    # K1 / K2 по отдельности
    k1_kappa = [h.get("K1_kappa", None) for h in history]
    k2_kappa = [h.get("K2_kappa", None) for h in history]
    k1_acc   = [h.get("K1_accuracy", None) for h in history]
    k2_acc   = [h.get("K2_accuracy", None) for h in history]

    # Лучшая эпоха
    best_epoch = ckpt.get("epoch", None)
    best_kappa = ckpt.get("val_kappa", None)

    # Интерпретация kappa
    def interpret(k):
        if k is None: return "—"
        if k < 0.0:   return "Хуже случайного 🔴"
        if k < 0.2:   return "Незначительное 🔴"
        if k < 0.4:   return "Слабое 🟠"
        if k < 0.6:   return "Умеренное 🟡"
        if k < 0.8:   return "Существенное 🟢"
        return "Почти идеальное 🏆"

    # Определяем признаки переобучения
    overfit_warning = False
    if len(train_acc) >= 5 and len(val_acc) >= 5:
        recent_train = np.mean([x for x in train_acc[-5:] if x is not None])
        recent_val   = np.mean([x for x in val_acc[-5:] if x is not None])
        if recent_train - recent_val > 0.15:
            overfit_warning = True

    # Динамика kappa — растёт или стагнирует?
    kappa_trend = "—"
    if len(val_kappa) >= 4:
        valid = [x for x in val_kappa if x is not None]
        if len(valid) >= 4:
            first_half = np.mean(valid[:len(valid)//2])
            second_half = np.mean(valid[len(valid)//2:])
            diff = second_half - first_half
            if diff > 0.05:   kappa_trend = "📈 Растёт"
            elif diff < -0.03: kappa_trend = "📉 Падает"
            else:              kappa_trend = "➡️ Стагнирует"

    return {
        "epochs":          epochs,
        "train_loss":      train_loss,
        "val_loss":        val_loss,
        "train_acc":       train_acc,
        "val_acc":         val_acc,
        "val_kappa":       val_kappa,
        "val_f1":          val_f1,
        "k1_kappa":        k1_kappa,
        "k2_kappa":        k2_kappa,
        "k1_acc":          k1_acc,
        "k2_acc":          k2_acc,
        "best_epoch":      best_epoch,
        "best_kappa":      best_kappa,
        "kappa_label":     interpret(best_kappa),
        "overfit_warning": overfit_warning,
        "kappa_trend":     kappa_trend,
        "total_epochs":    len(epochs),
        "checkpoint_path": checkpoint_path,
    }


# ──────────────────────────────────────────────────────────────────────────────
# HTML ДАШБОРД
# ──────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Мониторинг обучения — OGE Checker</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Unbounded:wght@400;700&display=swap');

  :root {
    --bg:       #0d0f14;
    --surface:  #151820;
    --border:   #252a35;
    --accent:   #6ee7b7;
    --accent2:  #f59e0b;
    --accent3:  #818cf8;
    --red:      #f87171;
    --text:     #e2e8f0;
    --muted:    #64748b;
    --good:     #34d399;
    --warn:     #fbbf24;
    --bad:      #f87171;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    min-height: 100vh;
    padding: 24px;
  }

  header {
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 28px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }

  header h1 {
    font-family: 'Unbounded', sans-serif;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: -0.02em;
  }

  .checkpoint-path {
    font-size: 0.7rem;
    color: var(--muted);
  }

  .refresh-badge {
    margin-left: auto;
    font-size: 0.65rem;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 20px;
  }

  /* ── КАРТОЧКИ МЕТРИК ── */
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
    margin-bottom: 28px;
  }

  .metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    position: relative;
    overflow: hidden;
  }

  .metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--card-color, var(--accent));
  }

  .metric-label {
    font-size: 0.65rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
  }

  .metric-value {
    font-family: 'Unbounded', sans-serif;
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--card-color, var(--accent));
    line-height: 1;
  }

  .metric-sub {
    font-size: 0.7rem;
    color: var(--muted);
    margin-top: 6px;
  }

  /* ── АЛЕРТЫ ── */
  .alerts {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 24px;
  }

  .alert {
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 0.75rem;
    border: 1px solid;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .alert-warn { background: #1c1500; border-color: #92400e; color: var(--warn); }
  .alert-good { background: #051a10; border-color: #065f46; color: var(--good); }
  .alert-info { background: #0f1229; border-color: #312e81; color: var(--accent3); }

  /* ── ГРАФИКИ ── */
  .charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 24px;
  }

  @media (max-width: 900px) {
    .charts-grid { grid-template-columns: 1fr; }
  }

  .chart-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }

  .chart-title {
    font-size: 0.7rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  canvas { max-height: 260px; }

  /* ── ТАБЛИЦА ЭПОХ ── */
  .table-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
    overflow-x: auto;
  }

  .table-title {
    font-size: 0.7rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 16px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.72rem;
  }

  th {
    text-align: left;
    padding: 8px 12px;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    font-weight: 400;
  }

  td {
    padding: 8px 12px;
    border-bottom: 1px solid #1a1f2a;
  }

  tr.best-row td { color: var(--accent); background: #0a1a12; }
  tr:hover td { background: #1a1f2a; }

  .kappa-cell { font-weight: 600; }
  .kappa-good  { color: var(--good); }
  .kappa-ok    { color: var(--warn); }
  .kappa-bad   { color: var(--bad); }

  /* ── РЕКОМЕНДАЦИИ ── */
  .recs-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }

  .recs-title {
    font-size: 0.7rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 14px;
  }

  .rec-item {
    display: flex;
    gap: 10px;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.75rem;
    line-height: 1.5;
  }

  .rec-item:last-child { border-bottom: none; }
  .rec-icon { font-size: 1rem; flex-shrink: 0; }
  .rec-text { color: var(--text); }
  .rec-note { color: var(--muted); font-size: 0.68rem; }

  /* ── ПРОГРЕСС-БАР ── */
  .progress-bar {
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    margin-top: 8px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    border-radius: 3px;
    background: var(--accent);
    transition: width 0.5s ease;
  }
</style>
</head>
<body>

<header>
  <h1>📊 OGE Checker — Мониторинг обучения</h1>
  <span class="checkpoint-path">DATA_CHECKPOINT_PATH</span>
  <span class="refresh-badge" id="refresh-timer">обновление через DATA_REFRESH_SEC с</span>
</header>

<div class="alerts" id="alerts">DATA_ALERTS</div>

<div class="metrics-grid">
  <div class="metric-card" style="--card-color: var(--accent)">
    <div class="metric-label">Лучшая Kappa</div>
    <div class="metric-value">DATA_BEST_KAPPA</div>
    <div class="metric-sub">DATA_KAPPA_LABEL</div>
    <div class="metric-sub">Эпоха DATA_BEST_EPOCH · Тренд: DATA_KAPPA_TREND</div>
  </div>
  <div class="metric-card" style="--card-color: var(--accent3)">
    <div class="metric-label">K1 kappa / K2 kappa</div>
    <div class="metric-value" style="font-size:1.3rem">DATA_K1_KAPPA / DATA_K2_KAPPA</div>
    <div class="metric-sub">последняя эпоха</div>
  </div>
  <div class="metric-card" style="--card-color: var(--accent2)">
    <div class="metric-label">F1 macro (val)</div>
    <div class="metric-value">DATA_LAST_F1</div>
    <div class="metric-sub">последняя эпоха · цель ≥ 0.55</div>
    <div class="progress-bar">
      <div class="progress-fill" style="width: DATA_F1_PCT%; background: var(--accent2)"></div>
    </div>
  </div>
  <div class="metric-card" style="--card-color: var(--good)">
    <div class="metric-label">Всего эпох / обучено</div>
    <div class="metric-value" style="font-size:1.3rem">DATA_TOTAL_EPOCHS</div>
    <div class="metric-sub">DATA_TRAIN_ACC_LAST → DATA_VAL_ACC_LAST train/val acc</div>
  </div>
</div>

<div class="charts-grid">
  <div class="chart-card">
    <div class="chart-title">
      <span>Cohen's Kappa по эпохам</span>
      <span style="color: var(--accent)">цель ≥ 0.4</span>
    </div>
    <canvas id="kappaChart"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">
      <span>Accuracy: train vs val</span>
      <span style="color: var(--red)" id="overfit-badge"></span>
    </div>
    <canvas id="accChart"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title"><span>Loss: train</span></div>
    <canvas id="lossChart"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title"><span>K1 vs K2 kappa</span></div>
    <canvas id="k1k2Chart"></canvas>
  </div>
</div>

<div class="table-card">
  <div class="table-title">История по эпохам</div>
  <table>
    <thead>
      <tr>
        <th>Эпоха</th>
        <th>Train acc</th>
        <th>Val acc</th>
        <th>Val kappa</th>
        <th>K1 kappa</th>
        <th>K2 kappa</th>
        <th>F1</th>
        <th>Loss</th>
        <th>Статус</th>
      </tr>
    </thead>
    <tbody id="history-table"></tbody>
  </table>
</div>

<div class="recs-card">
  <div class="recs-title">Рекомендации по результатам</div>
  <div id="recommendations"></div>
</div>

<script>
const DATA = DATA_JSON;
const BEST_EPOCH = DATA.best_epoch;

// ── Заполняем таблицу истории ──
const tbody = document.getElementById('history-table');
for (let i = 0; i < DATA.epochs.length; i++) {
  const e   = DATA.epochs[i];
  const k   = DATA.val_kappa[i];
  const isB = e === BEST_EPOCH;

  const kClass = k >= 0.6 ? 'kappa-good' : k >= 0.4 ? 'kappa-ok' : 'kappa-bad';
  const kStr   = k != null ? k.toFixed(3) : '—';
  const k1Str  = DATA.k1_kappa[i] != null ? DATA.k1_kappa[i].toFixed(3) : '—';
  const k2Str  = DATA.k2_kappa[i] != null ? DATA.k2_kappa[i].toFixed(3) : '—';
  const f1Str  = DATA.val_f1[i] != null ? DATA.val_f1[i].toFixed(3) : '—';
  const lStr   = DATA.train_loss[i] != null ? DATA.train_loss[i].toFixed(4) : '—';
  const taStr  = DATA.train_acc[i] != null ? (DATA.train_acc[i]*100).toFixed(1)+'%' : '—';
  const vaStr  = DATA.val_acc[i] != null ? (DATA.val_acc[i]*100).toFixed(1)+'%' : '—';

  const tr = document.createElement('tr');
  if (isB) tr.className = 'best-row';
  tr.innerHTML = `
    <td>${e}</td>
    <td>${taStr}</td>
    <td>${vaStr}</td>
    <td class="kappa-cell ${kClass}">${kStr}</td>
    <td>${k1Str}</td>
    <td>${k2Str}</td>
    <td>${f1Str}</td>
    <td>${lStr}</td>
    <td>${isB ? '⭐ лучшая' : ''}</td>
  `;
  tbody.appendChild(tr);
}

// ── Настройки Chart.js ──
Chart.defaults.color = '#64748b';
Chart.defaults.borderColor = '#252a35';
Chart.defaults.font.family = "'JetBrains Mono', monospace";
Chart.defaults.font.size = 11;

function makeChart(id, datasets, yMin, yMax, refLine) {
  const annotations = {};
  if (refLine != null) {
    annotations.goal = {
      type: 'line',
      yMin: refLine, yMax: refLine,
      borderColor: '#6ee7b740',
      borderWidth: 1,
      borderDash: [6, 4],
    };
  }

  return new Chart(document.getElementById(id), {
    type: 'line',
    data: { labels: DATA.epochs, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { boxWidth: 12, padding: 16, color: '#94a3b8' } },
      },
      scales: {
        x: { grid: { color: '#1a1f2a' }, ticks: { color: '#475569' } },
        y: {
          min: yMin, max: yMax,
          grid: { color: '#1a1f2a' },
          ticks: { color: '#475569' }
        }
      }
    }
  });
}

// Kappa
makeChart('kappaChart', [
  {
    label: 'Avg Kappa',
    data: DATA.val_kappa,
    borderColor: '#6ee7b7',
    backgroundColor: '#6ee7b715',
    borderWidth: 2,
    fill: true,
    tension: 0.3,
    pointRadius: 4,
    pointBackgroundColor: DATA.epochs.map(e => e === BEST_EPOCH ? '#6ee7b7' : 'transparent'),
    pointBorderWidth: DATA.epochs.map(e => e === BEST_EPOCH ? 3 : 1),
  }
], -0.1, 1.0, 0.4);

// Accuracy
makeChart('accChart', [
  {
    label: 'Train acc',
    data: DATA.train_acc,
    borderColor: '#818cf8',
    backgroundColor: 'transparent',
    borderWidth: 2,
    tension: 0.3,
    pointRadius: 3,
  },
  {
    label: 'Val acc',
    data: DATA.val_acc,
    borderColor: '#f59e0b',
    backgroundColor: '#f59e0b10',
    borderWidth: 2,
    fill: true,
    tension: 0.3,
    pointRadius: 3,
  }
], 0, 1.05, null);

// Loss
makeChart('lossChart', [
  {
    label: 'Train loss',
    data: DATA.train_loss,
    borderColor: '#f87171',
    backgroundColor: '#f8717110',
    borderWidth: 2,
    fill: true,
    tension: 0.3,
    pointRadius: 3,
  }
], null, null, null);

// K1 vs K2
makeChart('k1k2Chart', [
  {
    label: 'K1 kappa',
    data: DATA.k1_kappa,
    borderColor: '#6ee7b7',
    backgroundColor: 'transparent',
    borderWidth: 2,
    tension: 0.3,
    pointRadius: 3,
  },
  {
    label: 'K2 kappa',
    data: DATA.k2_kappa,
    borderColor: '#f59e0b',
    backgroundColor: 'transparent',
    borderWidth: 2,
    tension: 0.3,
    pointRadius: 3,
  }
], -0.1, 1.0, 0.4);

// ── Рекомендации ──
const recs = [];
const lastKappa  = DATA.val_kappa.at(-1) ?? 0;
const lastF1     = DATA.val_f1.at(-1) ?? 0;
const lastTrainA = DATA.train_acc.at(-1) ?? 0;
const lastValA   = DATA.val_acc.at(-1) ?? 0;

if (DATA.overfit_warning) {
  recs.push({
    icon: '🔥',
    text: 'Переобучение: train acc значительно выше val acc',
    note: 'Увеличь dropout (0.5→0.6), добавь аугментацию, уменьши lr или уменьши число обучаемых слоёв backbone'
  });
}

if (lastKappa < 0.2) {
  recs.push({
    icon: '🚨',
    text: 'Kappa < 0.2 — модель почти не лучше случайного',
    note: 'Проверь: правильно ли загружается checkpoint, правильно ли передаются метки, нет ли утечки данных'
  });
} else if (lastKappa < 0.4) {
  recs.push({
    icon: '🟠',
    text: 'Kappa 0.2–0.4 — слабое согласие с экспертом',
    note: 'Добавь weighted loss (class_weight=\'balanced\'), проверь баланс меток в train/val, добей 50+ примеров по заданиям 24–25'
  });
} else if (lastKappa >= 0.4) {
  recs.push({
    icon: '✅',
    text: 'Kappa ≥ 0.4 — умеренное согласие, результат допустим для диплома',
    note: 'Для дальнейшего улучшения: добавь примеры, попробуй ансамбль из 2–3 моделей'
  });
}

if (lastF1 < 0.45) {
  recs.push({
    icon: '⚠️',
    text: 'F1 < 0.45 — класс "1 балл" почти не распознаётся',
    note: 'Это ожидаемо при дисбалансе — добавь примеры оценки "1 балл" или используй oversampling (SMOTE)'
  });
}

const k1Last = DATA.k1_kappa.at(-1) ?? 0;
const k2Last = DATA.k2_kappa.at(-1) ?? 0;
if (Math.abs(k1Last - k2Last) > 0.15) {
  const weaker = k1Last < k2Last ? 'K1' : 'K2';
  recs.push({
    icon: '📌',
    text: `Критерий ${weaker} работает значительно хуже второго`,
    note: `Проверь: сбалансированы ли метки ${weaker} в датасете, нет ли ошибок разметки`
  });
}

if (DATA.total_epochs < 5) {
  recs.push({
    icon: '⏳',
    text: 'Мало эпох — выводы делать рано',
    note: 'Дай модели поучиться минимум 10–15 эпох прежде чем оценивать результат'
  });
}

recs.push({
  icon: '📋',
  text: 'Что показать на защите',
  note: 'Confusion matrix + лучшая kappa + таблица примеров с правильными и неправильными оценками. Honest baseline: "без модели — случайное угадывание (kappa≈0)"'
});

const recsEl = document.getElementById('recommendations');
recs.forEach(r => {
  const div = document.createElement('div');
  div.className = 'rec-item';
  div.innerHTML = `
    <span class="rec-icon">${r.icon}</span>
    <div>
      <div class="rec-text">${r.text}</div>
      <div class="rec-note">${r.note}</div>
    </div>
  `;
  recsEl.appendChild(div);
});

// ── Обратный отсчёт автообновления ──
const REFRESH_SEC = DATA_REFRESH_VAR;
let countdown = REFRESH_SEC;
const timerEl = document.getElementById('refresh-timer');
if (REFRESH_SEC > 0) {
  setInterval(() => {
    countdown--;
    if (countdown <= 0) {
      window.location.reload();
    } else {
      timerEl.textContent = `обновление через ${countdown} с`;
    }
  }, 1000);
} else {
  timerEl.textContent = 'статичный режим';
}
</script>
</body>
</html>
"""


# ──────────────────────────────────────────────────────────────────────────────
# ГЕНЕРАЦИЯ HTML
# ──────────────────────────────────────────────────────────────────────────────

def build_html(data: dict, refresh_sec: int = 0) -> str:
    if "error" in data:
        return f"""<html><body style="background:#0d0f14;color:#f87171;
            font-family:monospace;padding:40px;font-size:1.2rem">
            ❌ {data['error']}</body></html>"""

    def fmt(v, digits=3):
        if v is None: return "—"
        return f"{v:.{digits}f}"

    # Последние значения
    last_kappa  = data["val_kappa"][-1]  if data["val_kappa"]  else None
    last_f1     = data["val_f1"][-1]     if data["val_f1"]     else None
    last_train  = data["train_acc"][-1]  if data["train_acc"]  else None
    last_val    = data["val_acc"][-1]    if data["val_acc"]    else None
    last_k1     = data["k1_kappa"][-1]   if data["k1_kappa"]  else None
    last_k2     = data["k2_kappa"][-1]   if data["k2_kappa"]  else None

    # Алерты
    alerts_html = ""
    if data["overfit_warning"]:
        alerts_html += '<div class="alert alert-warn">🔥 Возможное переобучение — train acc >> val acc</div>'
    if last_kappa is not None and last_kappa >= 0.4:
        alerts_html += '<div class="alert alert-good">✅ Kappa ≥ 0.4 — умеренное согласие с экспертом</div>'
    if last_kappa is not None and last_kappa < 0.2:
        alerts_html += '<div class="alert alert-warn">🚨 Kappa < 0.2 — пересмотри разметку или гиперпараметры</div>'
    alerts_html += f'<div class="alert alert-info">📁 Эпох обучено: {data["total_epochs"]} · Лучшая: #{data["best_epoch"]}</div>'

    f1_pct = int((last_f1 or 0) * 100 * (100/55))  # нормализуем к цели 0.55
    f1_pct = min(f1_pct, 100)

    html = HTML_TEMPLATE
    html = html.replace("DATA_JSON",           json.dumps(data))
    html = html.replace("DATA_CHECKPOINT_PATH", data["checkpoint_path"])
    html = html.replace("DATA_REFRESH_SEC",    str(refresh_sec))
    html = html.replace("DATA_REFRESH_VAR",    str(refresh_sec))
    html = html.replace("DATA_ALERTS",         alerts_html)
    html = html.replace("DATA_BEST_KAPPA",     fmt(data["best_kappa"]))
    html = html.replace("DATA_KAPPA_LABEL",    data["kappa_label"])
    html = html.replace("DATA_BEST_EPOCH",     str(data["best_epoch"] or "—"))
    html = html.replace("DATA_KAPPA_TREND",    data["kappa_trend"])
    html = html.replace("DATA_K1_KAPPA",       fmt(last_k1))
    html = html.replace("DATA_K2_KAPPA",       fmt(last_k2))
    html = html.replace("DATA_LAST_F1",        fmt(last_f1))
    html = html.replace("DATA_F1_PCT",         str(f1_pct))
    html = html.replace("DATA_TOTAL_EPOCHS",   str(data["total_epochs"]))
    html = html.replace("DATA_TRAIN_ACC_LAST", f"{(last_train or 0)*100:.1f}%")
    html = html.replace("DATA_VAL_ACC_LAST",   f"{(last_val or 0)*100:.1f}%")

    return html


# ──────────────────────────────────────────────────────────────────────────────
# HTTP-СЕРВЕР (для авто-обновления)
# ──────────────────────────────────────────────────────────────────────────────

class MonitorHandler(http.server.BaseHTTPRequestHandler):
    checkpoint_path = DEFAULT_CHECKPOINT
    refresh_sec     = 30

    def log_message(self, *args): pass  # тихий режим

    def do_GET(self):
        data = load_history(self.checkpoint_path)
        html = build_html(data, self.refresh_sec)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


# ──────────────────────────────────────────────────────────────────────────────
# ТОЧКА ВХОДА
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Мониторинг обучения OGE Checker")
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT,
                        help="Путь к чекпоинту (.pt)")
    parser.add_argument("--watch", action="store_true",
                        help="Запустить HTTP-сервер с автообновлением")
    parser.add_argument("--port", type=int, default=8765,
                        help="Порт для --watch режима")
    parser.add_argument("--refresh", type=int, default=30,
                        help="Интервал обновления в секундах (--watch)")
    parser.add_argument("--output", default="training_monitor.html",
                        help="Куда сохранить HTML (без --watch)")
    args = parser.parse_args()

    if args.watch:
        # ── Режим живого сервера ──────────────────────────────────────────
        MonitorHandler.checkpoint_path = args.checkpoint
        MonitorHandler.refresh_sec     = args.refresh

        server = http.server.HTTPServer(("localhost", args.port), MonitorHandler)
        url    = f"http://localhost:{args.port}"

        print(f"\n🚀 Монитор запущен: {url}")
        print(f"📁 Чекпоинт:        {args.checkpoint}")
        print(f"🔄 Обновление:      каждые {args.refresh} с")
        print("   Ctrl+C для остановки\n")

        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n⏹️  Монитор остановлен")

    else:
        # ── Режим статичного HTML ─────────────────────────────────────────
        print(f"📖 Читаю чекпоинт: {args.checkpoint}")
        data = load_history(args.checkpoint)

        if "error" in data:
            print(f"❌ {data['error']}")
            sys.exit(1)

        html = build_html(data, refresh_sec=0)
        out  = Path(args.output)
        out.write_text(html, encoding="utf-8")

        print(f"✅ Дашборд сохранён: {out.resolve()}")
        print(f"   Лучшая kappa: {data['best_kappa']:.4f} ({data['kappa_label']})")
        print(f"   Эпоха: {data['best_epoch']} из {data['total_epochs']}")

        webbrowser.open(str(out.resolve()))


if __name__ == "__main__":
    main()
