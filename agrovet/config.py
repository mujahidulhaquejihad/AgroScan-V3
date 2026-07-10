"""Central configuration: dataset paths, model list, hyperparameters."""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "Datasets"
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Stage 1 - leaf vs non-leaf gate
LEAF_DATA = DATASETS / "Leaf_Checker_Zips" / "leaf-vs-non-leaf-images-002"
# Extra "non-leaf" imagery to harden the gate against arbitrary photos.
EXTRA_NON_LEAF = [
    DATASETS / "Leaf_Checker_Zips" / "natural-images" / "natural_images",
    DATASETS / "Leaf_Checker_Zips" / "fashion-product-images-small" / "images",
]

# Stage 2 - plant disease classifier (PlantVillage augmented)
_DISEASE_ROOT = (
    DATASETS
    / "disease_classifier_zips"
    / "new-plant-diseases-dataset-003"
    / "New Plant Diseases Dataset(Augmented)"
    / "New Plant Diseases Dataset(Augmented)"
)
DISEASE_TRAIN = _DISEASE_ROOT / "train"
DISEASE_VALID = _DISEASE_ROOT / "valid"

# Additional disease datasets (combined training)
PLANTVILLAGE_RAW = DATASETS / "PlantVillage Dataset"
BD_EXPORT_DIR = DATASETS / "bd_crop_disease"
PLANTDOC_ROOT = DATASETS / "PlantDoc-Dataset-master"
ARCHIVE_DISEASE = DATASETS / "archive" / "CropDisease" / "Crop___DIsease"
MANGIFERA_ROOT = (
    DATASETS
    / "Mangifera2012 An Image Dataset of Various Bangladeshi Mangoes"
    / "Mango_Dataset_2012"
)

# Bangladeshi Leaf Disease Detection Dataset (local zip, 3 crop classes).
BD_LEAF_DATASET_DIR = DATASETS / "Bangladeshi Leaf Disease Detection Dataset"
BD_LEAF_EXPORT_DIR = DATASETS / "bd_leaf_disease"
BD_LEAF_ZIP = (
    BD_LEAF_DATASET_DIR
    / "Bangladeshi Leaf Disease Detection Dataset"
    / "Leaf Disease detection Dataset.zip"
)

# Bangladesh multi-crop disease dataset (Hugging Face, gated).
# https://huggingface.co/datasets/Saon110/bd-crop-vegetable-plant-disease-dataset
BD_HF_DATASET = "Saon110/bd-crop-vegetable-plant-disease-dataset"

# Extra non-leaf negatives for the leaf gate.
ARCHIVE_INVALID = ARCHIVE_DISEASE / "Invalid"

# Training data source: plantvillage | bd | combined
DEFAULT_DISEASE_SOURCE = "combined"
# Include disease imagery as extra positive leaf examples in the gate.
LEAF_USE_DISEASE_IMAGES = True

# Checkpoint file names
LEAF_CKPT = MODELS_DIR / "leaf_gate.pt"


def disease_ckpt(arch: str) -> Path:
    return MODELS_DIR / f"disease_{arch}.pt"


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
# Disease classifier — only EfficientNet-B3 shown in the web app for now.
DISEASE_ARCHS = ["efficientnet_b3"]

# Leaf gate uses a single fast backbone.
LEAF_ARCH = "mobilenet_v3_large"

# Cap non-leaf samples to this multiple of the leaf count (avoids the
# huge fashion set swamping the ~6.5k leaf images and biasing the gate).
LEAF_NON_LEAF_RATIO = 1.5

# Per-architecture input resolution (EfficientNet-B3 prefers 300px).
INPUT_SIZE = {
    "efficientnet_b3": 300,
    "resnet50": 224,
    "densenet121": 224,
    "mobilenet_v3_large": 224,
}
DEFAULT_INPUT_SIZE = 224

# ImageNet normalization (all backbones are pretrained on ImageNet).
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]

# --------------------------------------------------------------------------- #
# Training hyperparameters
# --------------------------------------------------------------------------- #
SEED = 42
# Each DataLoader worker imports torch + CUDA DLLs, which commit a lot of
# memory on Windows. With 16GB RAM + ~15GB pagefile, keep this small to avoid
# "[WinError 1455] paging file too small". Raise it only after enlarging the
# Windows pagefile (see README).
# 0 = load images in the main process (safest on Windows with large phone photos).
# Raise to 2–4 only after enlarging the pagefile if you want faster loading.
NUM_WORKERS = 0
PREFETCH_FACTOR = 2

LEAF_EPOCHS = 4
LEAF_BATCH = 64
LEAF_LR = 1e-3

DISEASE_EPOCHS = 6
DISEASE_BATCH = 32          # fits EfficientNet-B3 @300px on a 12GB RTX 3060
DISEASE_LR = 1e-3

# Confidence below which the disease prediction is flagged as "uncertain".
UNCERTAIN_THRESHOLD = 0.45
# Below this, the UI tells the user to retake a clearer photo or contact a vet.
LOW_CONFIDENCE_THRESHOLD = 0.80
# Leaf-gate probability above which an image is accepted as a leaf.
LEAF_ACCEPT_THRESHOLD = 0.5

# Friendly names shown in the web UI and API responses.
MODEL_DISPLAY_NAMES = {
    "efficientnet_b3": "EfficientNet-B3",
    "resnet50": "ResNet-50",
    "mobilenet_v3_large": "MobileNetV3",
    "densenet121": "DenseNet-121",
}


def model_display_name(arch: str) -> str:
    return MODEL_DISPLAY_NAMES.get(arch, arch)
