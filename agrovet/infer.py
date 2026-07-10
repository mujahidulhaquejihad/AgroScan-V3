"""Two-stage inference: leaf gate -> 3-model disease ensemble.

Produces a structured result with a section per model plus an ensemble
"best answer". Consumed by the FastAPI backend (web + mobile).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import torch
import torch.nn.functional as F
from PIL import Image

from . import config
from .data import infer_transform
from .image_io import load_rgb_image
from .knowledge import advice_for
from .models import load_checkpoint


def _pretty(class_name: str) -> Dict[str, str]:
    """Parse canonical labels like 'Tomato___Late_blight' or 'Rice___Blast'."""
    if "___" in class_name:
        plant, cond = class_name.split("___", 1)
    elif "_" in class_name:
        plant, cond = class_name.split("_", 1)
    else:
        plant, cond = class_name, ""
    plant = plant.replace("_", " ").replace("(", "(").strip()
    cond_clean = cond.replace("_", " ").strip()
    if cond_clean.lower().startswith("variety "):
        return {
            "plant": plant,
            "condition": cond_clean,
            "is_healthy": False,
        }
    is_healthy = cond_clean.lower() in ("healthy", "normal")
    return {
        "plant": plant,
        "condition": "Healthy" if is_healthy else cond_clean,
        "is_healthy": is_healthy,
    }


class LoadedModel:
    def __init__(self, path: Path, device: str):
        self.model, self.class_names, self.meta = load_checkpoint(path, device)
        self.arch = self.meta["arch"]
        self.size = config.INPUT_SIZE.get(self.arch, config.DEFAULT_INPUT_SIZE)
        self.tf = infer_transform(self.size)
        self.device = device

    @torch.no_grad()
    def probs(self, img: Image.Image) -> torch.Tensor:
        x = self.tf(img).unsqueeze(0).to(self.device)
        return F.softmax(self.model(x), dim=1).squeeze(0).cpu()


class InferenceEngine:
    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Stage 1 - leaf gate (optional but recommended)
        self.leaf: Optional[LoadedModel] = None
        if config.LEAF_CKPT.exists():
            self.leaf = LoadedModel(config.LEAF_CKPT, self.device)

        # Stage 2 - disease ensemble
        self.disease: List[LoadedModel] = []
        for arch in config.DISEASE_ARCHS:
            p = config.disease_ckpt(arch)
            if p.exists():
                self.disease.append(LoadedModel(p, self.device))
        if self.disease:
            self.disease_classes = self.disease[0].class_names
        else:
            self.disease_classes = []

    # ------------------------------------------------------------------ #
    @property
    def ready(self) -> bool:
        return len(self.disease) > 0

    def status(self) -> dict:
        return {
            "device": self.device,
            "leaf_gate_loaded": self.leaf is not None,
            "disease_models_loaded": [config.model_display_name(m.arch) for m in self.disease],
            "num_disease_classes": len(self.disease_classes),
        }

    # ------------------------------------------------------------------ #
    def _leaf_stage(self, img: Image.Image) -> dict:
        if self.leaf is None:
            return {
                "available": False,
                "is_leaf": True,  # no gate trained -> don't block
                "note": "Leaf gate model not trained; skipping leaf check.",
            }
        p = self.leaf.probs(img)
        leaf_idx = self.leaf.class_names.index("leaf")
        leaf_prob = float(p[leaf_idx])
        return {
            "available": True,
            "model": config.model_display_name(self.leaf.arch),
            "is_leaf": leaf_prob >= config.LEAF_ACCEPT_THRESHOLD,
            "leaf_probability": round(leaf_prob, 4),
            "label": "leaf" if leaf_prob >= config.LEAF_ACCEPT_THRESHOLD else "non_leaf",
        }

    def _disease_stage(self, img: Image.Image) -> dict:
        per_model = []
        prob_stack = []
        for m in self.disease:
            p = m.probs(img)
            prob_stack.append(p)
            conf, idx = torch.max(p, dim=0)
            top = torch.topk(p, k=min(3, p.numel()))
            cls = m.class_names[int(idx)]
            info = _pretty(cls)
            per_model.append(
                {
                    "model": config.model_display_name(m.arch),
                    "prediction": cls,
                    "plant": info["plant"],
                    "condition": info["condition"],
                    "is_healthy": info["is_healthy"],
                    "confidence": round(float(conf), 4),
                    "top3": [
                        {
                            "label": m.class_names[int(i)],
                            **_pretty(m.class_names[int(i)]),
                            "confidence": round(float(v), 4),
                        }
                        for v, i in zip(top.values, top.indices)
                    ],
                }
            )

        # Confidence-weighted ensemble = mean of softmax probabilities.
        mean_p = torch.stack(prob_stack).mean(0)
        conf, idx = torch.max(mean_p, dim=0)
        best_cls = self.disease_classes[int(idx)]
        info = _pretty(best_cls)
        agree = sum(1 for pm in per_model if pm["prediction"] == best_cls)
        top = torch.topk(mean_p, k=min(3, mean_p.numel()))
        if len(per_model) == 1:
            method = per_model[0]["model"]
            agreement = ""
        else:
            method = "আত্মবিশ্বাস-ভিত্তিক সম্মিলিত ফলাফল (গড় সফটম্যাক্স)"
            agreement = f"{agree}/{len(per_model)}টি মডেল একমত"
        best = {
            "prediction": best_cls,
            "plant": info["plant"],
            "condition": info["condition"],
            "is_healthy": info["is_healthy"],
            "confidence": round(float(conf), 4),
            "method": method,
            "agreement": agreement,
            "uncertain": float(conf) < config.UNCERTAIN_THRESHOLD,
            "low_confidence": float(conf) < config.LOW_CONFIDENCE_THRESHOLD,
            "recommendation": (
                "আত্মবিশ্বাস ৮০% এর নিচে। পরিষ্কার, কাছ থেকে একটি পাতার ছবি তুলুন "
                "(সাদা ব্যাকগ্রাউন্ড, ভালো আলো), অথবা কৃষি কর্মকর্তা/পশুচিকিৎসকের সাথে "
                "যোগাযোগ করুন (কৃষি: ১৬১২৩, পশুচিকিৎসা: ১৬৩৫৮)।"
                if float(conf) < config.LOW_CONFIDENCE_THRESHOLD
                else None
            ),
            "advice": advice_for(best_cls, "bn"),
            "top3": [
                {
                    "label": self.disease_classes[int(i)],
                    **_pretty(self.disease_classes[int(i)]),
                    "confidence": round(float(v), 4),
                }
                for v, i in zip(top.values, top.indices)
            ],
        }
        return {"models": per_model, "best_answer": best}

    # ------------------------------------------------------------------ #
    def predict(self, img: Image.Image) -> dict:
        img = load_rgb_image(img, fallback_size=None)
        leaf = self._leaf_stage(img)
        result = {"stage1_leaf_gate": leaf, "stage2_disease": None}
        if not leaf["is_leaf"]:
            result["message"] = (
                "এই ছবিটি পাতা বলে মনে হয় না, তাই রোগ বিশ্লেষণ করা হয়নি।"
            )
            return result
        if not self.disease:
            result["message"] = "No disease models trained yet."
            return result
        result["stage2_disease"] = self._disease_stage(img)
        return result
