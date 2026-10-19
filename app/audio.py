import logging
import os
from pathlib import Path
import miniaudio
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

REPO_ID = "tphakala/Perch-v2"
MODEL_FILE = "perch_v2_no_dft.onnx"
LABELS_FILE = "labels.txt"
LABELS_HEADER = "inat2024_fsd50k"

SAMPLE_RATE = 32_000
WINDOW_SAMPLES = SAMPLE_RATE * 5
MIN_TAIL_SAMPLES = SAMPLE_RATE
MAX_WINDOWS = 24

_session = None
_labels: list[str] | None = None


def identify_audio(path: Path, k: int = 5) -> list[dict] | None:
    try:
        audio = _decode_mp3(path)
    except RuntimeError as exc:
        print(f"Помилка: {exc}")
        return None

    if audio.size == 0:
        print("Помилка: у файлі немає звуку.")
        return None

    windows, starts, truncated = _windows(audio)
    if not windows:
        print("Помилка: у файлі немає звуку.")
        return None

    if float(np.max(np.abs(audio))) < 0.01:
        print("Запис майже тихий. Результат може бути випадковим.")

    try:
        session, labels = _get_model()
        print(f"Аналізую {len(windows)} вікон по 5 с.")
        scores = _predict(session, windows)
    except Exception as exc:
        print(f"Не вдалося проаналізувати аудіо: {exc}")
        return None

    if scores.shape[1] != len(labels):
        print(
            "Помилка: кількість міток не збігається з виходом моделі "
            f"({len(labels)} і {scores.shape[1]})."
        )
        return None

    predictions = _top_predictions(scores, labels, starts, k)
    _print_predictions(path, predictions, len(windows), truncated, audio.size)
    return predictions


def _get_model():
    global _session, _labels
    if _session is not None and _labels is not None:
        return _session, _labels

    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    print(
        "Завантаження Perch v2. Якщо моделі ще немає в кеші, "
        "зараз скачається близько 400 МБ."
    )
    model_path = hf_hub_download(REPO_ID, MODEL_FILE)
    labels_path = hf_hub_download(REPO_ID, LABELS_FILE)
    _labels = _read_labels(Path(labels_path))

    options = ort.SessionOptions()
    options.intra_op_num_threads = os.cpu_count() or 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    _session = ort.InferenceSession(
        model_path,
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    return _session, _labels


def _read_labels(path: Path) -> list[str]:
    labels = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name == LABELS_HEADER:
            continue
        labels.append(name)
    return labels


def _decode_mp3(path: Path) -> np.ndarray:
    try:
        decoded = miniaudio.decode_file(
            str(path),
            output_format=miniaudio.SampleFormat.FLOAT32,
            nchannels=1,
            sample_rate=SAMPLE_RATE,
        )
    except (miniaudio.DecodeError, miniaudio.MiniaudioError) as exc:
        raise RuntimeError("файл не читається як mp3.") from exc
    return np.asarray(decoded.samples, dtype=np.float32)


def _windows(audio: np.ndarray) -> tuple[list[np.ndarray], list[int], bool]:
    windows = []
    starts = []
    start = 0
    truncated = False
    while start < audio.size:
        if len(windows) >= MAX_WINDOWS:
            truncated = True
            break
        chunk = audio[start:start + WINDOW_SAMPLES]
        if chunk.size < WINDOW_SAMPLES:
            if chunk.size < MIN_TAIL_SAMPLES and windows:
                break
            chunk = np.pad(chunk, (0, WINDOW_SAMPLES - chunk.size))
        windows.append(chunk.astype(np.float32, copy=False))
        starts.append(start)
        start += WINDOW_SAMPLES
    return windows, starts, truncated


def _predict(session, windows: list[np.ndarray]) -> np.ndarray:
    input_name = session.get_inputs()[0].name
    label_name = _label_output_name(session)
    pieces = []
    for start in range(0, len(windows), 4):
        batch = np.stack(windows[start:start + 4])
        logits = session.run([label_name], {input_name: batch})[0]
        pieces.append(_softmax(np.asarray(logits, dtype=np.float32)))
    return np.concatenate(pieces, axis=0)


def _label_output_name(session) -> str:
    for output in session.get_outputs():
        if output.name == "label":
            return output.name
    raise RuntimeError("у моделі Perch немає виходу label.")


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def _top_predictions(scores: np.ndarray, labels: list[str], starts: list[int], k: int) -> list[dict]:
    peak = scores.max(axis=0)
    order = np.argsort(peak)[::-1][:k]
    predictions = []
    for index in order:
        window = int(scores[:, index].argmax())
        name = labels[int(index)]
        predictions.append({
            "scientific_name": name,
            "score": float(peak[index]),
            "start_seconds": starts[window] / SAMPLE_RATE,
            "is_species": _is_species(name),
        })
    return predictions


def _is_species(name: str) -> bool:
    parts = name.split()
    if len(parts) != 2 or "_" in name:
        return False
    genus, species = parts
    return (
        genus[:1].isupper()
        and genus[1:].isalpha()
        and genus[1:].islower()
        and species.isalpha()
        and species.islower()
    )


def _print_predictions(path: Path, predictions: list[dict], window_count: int, truncated: bool, samples: int) -> None:
    duration = samples / SAMPLE_RATE
    print("\n===== Аудіо: Perch v2 =====")
    print(path)
    print("Модель дає наукову назву.")
    print(f"тривалість: {_clock(duration)}, вікон: {window_count}")
    if truncated:
        analyzed = window_count * 5
        print(f"Проаналізовано перші {analyzed} с. Решта запису пропущена.")
    if not predictions:
        print("Модель не повернула жодного варіанту.")
        return
    if not predictions[0]["is_species"]:
        print("Найгучніший клас — звукова подія, не біологічний вид.")

    for index, prediction in enumerate(predictions, start=1):
        print(_format_prediction(index, prediction))


def _format_prediction(index: int, prediction: dict) -> str:
    name = prediction["scientific_name"].replace("_", " ")
    start = prediction["start_seconds"]
    lines = [
        f"{index}. {name}",
        f"   впевненість: {prediction['score'] * 100:.1f}%",
        f"   найсильніше у {_clock(start)}–{_clock(start + 5)}",
    ]
    if not prediction["is_species"]:
        lines.append("   звукова подія, не вид")
    return "\n".join(lines)


def _clock(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"
