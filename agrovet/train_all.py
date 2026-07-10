"""Orchestrate full training: leaf gate + all 3 disease models."""
from __future__ import annotations

import argparse

from . import config
from .train_disease import train_one
from .train_leaf import main as train_leaf_main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-leaf", action="store_true")
    ap.add_argument("--disease-source", default=config.DEFAULT_DISEASE_SOURCE, choices=("plantvillage", "bd", "combined"))
    ap.add_argument("--disease-epochs", type=int, default=config.DISEASE_EPOCHS)
    ap.add_argument("--disease-batch", type=int, default=config.DISEASE_BATCH)
    args = ap.parse_args()

    if not args.skip_leaf:
        print("########## STAGE 1: LEAF GATE ##########")
        train_leaf_main()

    print("\n########## STAGE 2: DISEASE ENSEMBLE ##########")
    results = {}
    for arch in config.DISEASE_ARCHS:
        results[arch] = train_one(
            arch, args.disease_epochs, args.disease_batch, config.DISEASE_LR,
            source=args.disease_source,
        )

    print("\n========== SUMMARY ==========")
    for arch, acc in results.items():
        print(f"{arch:>22}: best val_acc = {acc:.4f}")


if __name__ == "__main__":
    main()
