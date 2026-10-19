import logging
import os
import torch
from bioclip import BIOCLIP_V1_MODEL_STR, BIOCLIP_V2_MODEL_STR, Rank
from bioclip.predict import TreeOfLifeClassifier
from pathlib import Path
from PIL import Image, UnidentifiedImageError

os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

_classifier = None
_model_label = "BioCLIP 2"

RANK_LABELS = (
    ("kingdom", "царство"),
    ("phylum", "тип"),
    ("class", "клас"),
    ("order", "ряд"),
    ("family", "родина"),
    ("genus", "рід"),
)


def get_classifier():
    global _classifier, _model_label
    if _classifier is not None:
        return _classifier

    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Завантаження BioCLIP 2")
    try:
        _classifier = TreeOfLifeClassifier(model_str=BIOCLIP_V2_MODEL_STR, device=device)
        _model_label = "BioCLIP 2"
    except (MemoryError, RuntimeError) as exc:
        if not isinstance(exc, MemoryError) and "memory" not in str(exc).lower():
            raise
        print("BioCLIP 2 не вмістилась у пам'ять. Завантажую BioCLIP 1.")
        _classifier = TreeOfLifeClassifier(model_str=BIOCLIP_V1_MODEL_STR, device=device)
        _model_label = "BioCLIP 1"
    return _classifier


def identify_photo(path: Path, k: int = 5):
    if not readable_image(path):
        print("Помилка: файл не читається як зображення.")
        return None

    try:
        predictions = get_classifier().predict(
            str(path),
            Rank.SPECIES,
            k=k,
            callback=lambda _processed, _total: None,
        )
    except Exception as exc:
        print(f"Не вдалося проаналізувати фото: {exc}")
        return None

    if isinstance(predictions, dict):
        predictions = [predictions]
    predictions = list(predictions or [])
    print_predictions(path, predictions)
    return predictions


def readable_image(path: Path):
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.convert("RGB").load()
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    return True


def print_predictions(path: Path, predictions: list[dict]):
    print(f"\n===== Фото: {_model_label} =====")
    print(path)
    if not predictions:
        print("Модель не повернула жодного виду.")
        return

    top_class = str(predictions[0].get("class") or "")
    if top_class and top_class.lower() != "aves":
        print(f"Найімовірніший клас — {top_class}. На фото, ймовірно, не птах.")

    for index, prediction in enumerate(predictions, start=1):
        print(format_prediction(index, prediction))


def format_prediction(index: int, prediction: dict):
    species = prediction.get("species") or "невідомий вид"
    common_name = prediction.get("common_name") or ""
    title = f"{index}. {species}"
    if common_name:
        title += f" — {common_name}"

    lines = [title]
    score = prediction.get("score")
    if isinstance(score, (int, float)):
        lines.append(f"   впевненість: {score * 100:.1f}%")

    taxa = [
        f"{label} {prediction[key]}"
        for key, label in RANK_LABELS
        if prediction.get(key)
    ]
    if taxa:
        lines.append("   " + ", ".join(taxa))
    return "\n".join(lines)
