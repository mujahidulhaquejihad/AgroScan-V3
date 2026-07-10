"""Reusable training / evaluation loop (mixed precision, cosine LR)."""
from __future__ import annotations

import time
from typing import List

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from .models import save_checkpoint


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: str) -> float:
    model.eval()
    correct = total = 0
    for x, y in tqdm(loader, desc="eval", leave=False):
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        preds = model(x).argmax(1)
        correct += (preds == y).sum().item()
        total += y.numel()
    return correct / max(total, 1)


def train_model(
    model: nn.Module,
    train_dl: DataLoader,
    val_dl: DataLoader,
    *,
    epochs: int,
    lr: float,
    device: str,
    class_names: List[str],
    arch: str,
    ckpt_path,
) -> float:
    model.to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    use_amp = device.startswith("cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best_acc = 0.0
    for epoch in range(1, epochs + 1):
        model.train()
        running, seen, t0 = 0.0, 0, time.time()
        pbar = tqdm(train_dl, desc=f"{arch} epoch {epoch}/{epochs}")
        for x, y in pbar:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=use_amp):
                out = model(x)
                loss = criterion(out, y)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            running += loss.item() * x.size(0)
            seen += x.size(0)
            pbar.set_postfix(loss=f"{running / seen:.3f}")
        scheduler.step()

        acc = evaluate(model, val_dl, device)
        dt = time.time() - t0
        print(f"[{arch}] epoch {epoch}: val_acc={acc:.4f}  ({dt:.0f}s)")
        if acc >= best_acc:
            best_acc = acc
            save_checkpoint(
                ckpt_path, model, arch, class_names,
                meta={"val_acc": acc, "epoch": epoch},
            )
            print(f"   -> saved best checkpoint ({acc:.4f}) to {ckpt_path}")
    print(f"[{arch}] best val_acc = {best_acc:.4f}")
    return best_acc
