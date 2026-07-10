"""
Download Bangladesh crop disease dataset → Datasets/bd_crop_disease/

HOW TO RUN IN VS CODE
---------------------
1. Open this folder in VS Code:  File → Open Folder → Agrovet V2
2. Accept dataset on Hugging Face (browser, one time):
   https://huggingface.co/datasets/Saon110/bd-crop-vegetable-plant-disease-dataset
   → Log in → click Agree
3. Get a token: https://huggingface.co/settings/tokens  (Read access is enough)
4. VS Code terminal (Ctrl+`):

       python -m pip install datasets huggingface_hub tqdm
       $env:HF_TOKEN="hf_YOUR_TOKEN_HERE"
       python download_bd_dataset.py --check

   Or press F5 → "BD dataset: check access" (uses HF_TOKEN from launch env if set)

5. Test download:  python download_bd_dataset.py --max-per-class 5
6. Full download:  python download_bd_dataset.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "Datasets" / "bd_crop_disease"
HF_REPOS = (
    "Saon110/bd-crop-vegetable-plant-disease-dataset",
    "Saon110/bd-crop-veg-plant-disease-dataset",
)
HF_PAGE = "https://huggingface.co/datasets/Saon110/bd-crop-vegetable-plant-disease-dataset"


def _ensure_deps():
    try:
        import datasets  # noqa: F401
        import huggingface_hub  # noqa: F401
        from tqdm import tqdm  # noqa: F401
    except ImportError:
        print("Installing datasets, huggingface_hub, tqdm ...")
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "datasets", "huggingface_hub", "tqdm"]
        )


def _ensure_hf_login(cli_token: str | None = None):
    from huggingface_hub import get_token, login

    token = cli_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        login(token=token.strip(), add_to_git_credential=True)
        print("Using token from HF_TOKEN environment variable.")
        return

    saved = get_token()
    if saved:
        print("Using saved Hugging Face token.")
        return

    print("\n" + "=" * 60)
    print("HUGGING FACE LOGIN REQUIRED")
    print("=" * 60)
    print(f"1) Open in browser and click Agree:\n   {HF_PAGE}")
    print("2) Create a token (Read):\n   https://huggingface.co/settings/tokens")
    print("3) Paste the token below (starts with hf_):\n")
    pasted = input("HF token: ").strip()
    if not pasted:
        raise SystemExit("No token entered. Set HF_TOKEN or paste a token when prompted.")
    login(token=pasted, add_to_git_credential=True)








    print("Logged in.\n")


def _load_dataset():
    from datasets import load_dataset

    last_err = None
    for repo in HF_REPOS:
        try:
            print(f"Loading from Hub: {repo} ...")
            return load_dataset(repo), repo
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "gated" in msg or "authenticated" in msg or "401" in msg:
                print("\nERROR: Dataset access denied (gated).\n")
                print(f"  -> Open {HF_PAGE}")
                print("  -> Log in and click Agree to the terms")
                print("  -> Run this script again and paste your token\n")
                raise SystemExit(1) from e
            if "doesn't exist" in msg or "not found" in msg:
                continue
            raise
    raise SystemExit(f"Could not load dataset. Last error: {last_err}")


def _safe_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").strip() or "unknown"


def _label_names_from_dataset(train_ds) -> list[str]:
    """Resolve class names (ClassLabel.names or label_name column)."""
    label_feat = train_ds.features.get("label")
    if label_feat is not None and hasattr(label_feat, "names") and label_feat.names:
        return list(label_feat.names)
    if "label_name" in train_ds.column_names:
        return sorted(set(train_ds.unique("label_name")))
    raise ValueError("Dataset has no label names (expected ClassLabel or label_name column).")


def _row_class_name(row, names: list[str]) -> str:
    if "label_name" in row and row["label_name"]:
        return str(row["label_name"])
    return names[int(row["label"])]


def cmd_check(cli_token: str | None = None):
    _ensure_deps()
    _ensure_hf_login(cli_token)
    ds, repo = _load_dataset()
    names = _label_names_from_dataset(ds["train"])
    print(f"\nOK - access works for: {repo}")
    print(f"Total classes: {len(names)}")
    for split in ("train", "valid", "test"):
        if split in ds:
            print(f"  {split}: {len(ds[split])} samples")
    print(f"\nReady to download. Run with:  python download_bd_dataset.py")
    print("Or F5 -> 'BD dataset: test download' in VS Code")


def cmd_download(out: Path, max_per_class: int | None, cli_token: str | None = None):
    from tqdm import tqdm

    _ensure_deps()
    _ensure_hf_login(cli_token)
    ds, repo = _load_dataset()
    names = _label_names_from_dataset(ds["train"])
    out.mkdir(parents=True, exist_ok=True)

    print(f"\nExporting to: {out.resolve()}")
    if max_per_class:
        print(f"(Test mode: max {max_per_class} images per class per split)\n")
    else:
        print("Full download (~123k images, 15–40 GB). This takes a long time.\n")

    for split in ("train", "valid", "test"):
        if split not in ds:
            continue
        split_ds = ds[split]
        counts: dict[int, int] = {}
        for i, row in enumerate(tqdm(split_ds, desc=split, unit="img")):
            lid = int(row["label"])
            if max_per_class and counts.get(lid, 0) >= max_per_class:
                continue
            folder = out / split / _safe_name(_row_class_name(row, names))
            folder.mkdir(parents=True, exist_ok=True)
            row["image"].convert("RGB").save(folder / f"{split}_{i:06d}.jpg", quality=92)
            counts[lid] = counts.get(lid, 0) + 1

    manifest = {
        "hub_repo": repo,
        "num_classes": len(names),
        "class_names": names,
        "splits": {s: len(ds[s]) for s in ds.keys()},
        "export_dir": str(out),
    }
    (out / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nDone!")
    print(f"  {out / 'train'}")
    print(f"  {out / 'valid'}")
    print(f"  {out / 'test'}")


def main():
    ap = argparse.ArgumentParser(description="Download BD crop dataset (VS Code friendly)")
    ap.add_argument("--check", action="store_true", help="Only verify Hugging Face access")
    ap.add_argument("--token", type=str, default=None, help="HF token (or set HF_TOKEN env var)")
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="Output folder")
    ap.add_argument("--max-per-class", type=int, default=None, help="Test: limit images per class")
    args = ap.parse_args()

    if args.check:
        cmd_check(args.token)
    else:
        cmd_download(args.out, args.max_per_class, args.token)


if __name__ == "__main__":
    main()
