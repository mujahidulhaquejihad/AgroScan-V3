"""Train a single Stage-2 disease classifier (one of the 3 ensemble members)."""
from __future__ import annotations

import argparse

import torch

from . import config
from .data import disease_loaders
from .engine import train_model
from .models import build_model


def train_one(arch: str, epochs: int, batch: int, lr: float, source: str | None = None) -> float:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(config.SEED)
    size = config.INPUT_SIZE.get(arch, config.DEFAULT_INPUT_SIZE)
    src = source or config.DEFAULT_DISEASE_SOURCE

    print(f"\n=== Training disease model: {arch} (input={size}, device={device}, source={src}) ===")
    train_dl, val_dl, class_names = disease_loaders(size, batch, source=src)
    print(f"Disease classes: {len(class_names)} | train={len(train_dl.dataset)} val={len(val_dl.dataset)}")

    model = build_model(arch, num_classes=len(class_names), pretrained=True)
    return train_model(
        model, train_dl, val_dl,
        epochs=epochs, lr=lr, device=device,
        class_names=class_names, arch=arch, ckpt_path=config.disease_ckpt(arch),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", required=True, choices=config.DISEASE_ARCHS)
    ap.add_argument("--source", default=config.DEFAULT_DISEASE_SOURCE, choices=("plantvillage", "bd", "combined"))
    ap.add_argument("--epochs", type=int, default=config.DISEASE_EPOCHS)
    ap.add_argument("--batch", type=int, default=config.DISEASE_BATCH)
    ap.add_argument("--lr", type=float, default=config.DISEASE_LR)
    args = ap.parse_args()
    train_one(args.arch, args.epochs, args.batch, args.lr, source=args.source)


if __name__ == "__main__":
    main()
