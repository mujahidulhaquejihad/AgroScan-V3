"""Train the Stage-1 leaf-vs-non-leaf gate."""
from __future__ import annotations

import argparse

import torch

from . import config
from .data import leaf_loaders
from .engine import train_model
from .models import build_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=config.LEAF_EPOCHS)
    ap.add_argument("--batch", type=int, default=config.LEAF_BATCH)
    ap.add_argument("--lr", type=float, default=config.LEAF_LR)
    ap.add_argument("--arch", default=config.LEAF_ARCH)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(config.SEED)
    size = config.INPUT_SIZE.get(args.arch, config.DEFAULT_INPUT_SIZE)

    print(f"Device={device} | arch={args.arch} | input={size}")
    train_dl, val_dl, class_names = leaf_loaders(size, args.batch)
    print(f"Leaf classes: {class_names} | train={len(train_dl.dataset)} val={len(val_dl.dataset)}")

    model = build_model(args.arch, num_classes=len(class_names), pretrained=True)
    train_model(
        model, train_dl, val_dl,
        epochs=args.epochs, lr=args.lr, device=device,
        class_names=class_names, arch=args.arch, ckpt_path=config.LEAF_CKPT,
    )


if __name__ == "__main__":
    main()
