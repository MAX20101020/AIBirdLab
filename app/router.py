import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from .crud import (
    delete_analyses,
    delete_analysis,
    get_analysis,
    list_analyses,
    save_analysis,
    search_analyses,
    statistics,
)
from .database import get_db
from .schemas import AnalysisOut, AnalysisResult, DeleteResult, StatisticsOut
from .photo import identify_photo
from .audio import identify_audio

router = APIRouter(prefix="/birds", tags=["birds"])
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png"}
AUDIO_SUFFIXES = {".mp3"}


@router.post("/photo", response_model=AnalysisResult)
def analyze_photo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    path = _write_temp(file, PHOTO_SUFFIXES)
    try:
        predictions = identify_photo(path)
    finally:
        path.unlink(missing_ok=True)

    saved = None
    if predictions:
        top = predictions[0]
        saved = save_analysis(
            db,
            _original_name(file),
            top.get("species"),
            top.get("common_name") or "",
            top.get("score"),
        )
    return AnalysisResult(predictions=_plain(predictions), saved=saved)


@router.post("/audio", response_model=AnalysisResult)
def analyze_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    path = _write_temp(file, AUDIO_SUFFIXES)
    try:
        predictions = identify_audio(path)
    finally:
        path.unlink(missing_ok=True)

    saved = None
    if predictions:
        top = predictions[0]
        saved = save_analysis(
            db,
            _original_name(file),
            top.get("scientific_name"),
            "",
            top.get("score"),
        )
    return AnalysisResult(predictions=_plain(predictions), saved=saved)


@router.get("/", response_model=list[AnalysisOut])
def show_history(db: Session = Depends(get_db)):
    return list_analyses(db)


@router.get("/search", response_model=list[AnalysisOut])
def search_bird(name: str = "", db: Session = Depends(get_db)):
    query = name.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Введіть назву.")
    return search_analyses(db, query)


@router.get("/statistics", response_model=StatisticsOut)
def show_statistics(db: Session = Depends(get_db)):
    return statistics(db)


@router.delete("/by-name", response_model=DeleteResult)
def delete_bird_by_name(name: str = "", db: Session = Depends(get_db)):
    query = name.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Нічого не введено.")
    rows = search_analyses(db, query)
    if not rows:
        raise HTTPException(status_code=404, detail="Нічого не знайдено.")
    removed = delete_analyses(db, [row.id for row in rows])
    return DeleteResult(removed=removed)


@router.get("/{record_id}", response_model=AnalysisOut)
def get_bird(record_id: int, db: Session = Depends(get_db)):
    row = get_analysis(db, record_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Запис не знайдено.")
    return row


@router.delete("/{record_id}", response_model=DeleteResult)
def delete_bird(record_id: int, db: Session = Depends(get_db)):
    if not delete_analysis(db, record_id):
        raise HTTPException(status_code=404, detail="Запис не знайдено.")
    return DeleteResult(removed=1)


def _identify_photo(path: Path):
    try:
        from photo import identify_photo
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Модуль розпізнавання фото недоступний: {exc}",
        ) from exc
    predictions = identify_photo(path)
    if predictions is None:
        raise HTTPException(status_code=400, detail="Не вдалося проаналізувати фото.")
    return list(predictions)


def _identify_audio(path: Path):
    try:
        from audio import identify_audio
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Модуль розпізнавання аудіо недоступний: {exc}",
        ) from exc
    predictions = identify_audio(path)
    if predictions is None:
        raise HTTPException(status_code=400, detail="Не вдалося проаналізувати аудіо.")
    return list(predictions)


def _plain(value):
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    as_item = getattr(value, "item", None)
    if callable(as_item):
        try:
            return _plain(as_item())
        except Exception:
            return str(value)
    return str(value)


def _original_name(file: UploadFile):
    raw = (file.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not raw or raw in {".", ".."}:
        raise HTTPException(status_code=400, detail="Не вказано ім'я файлу.")
    return raw


def _write_temp(file: UploadFile, allowed: set[str]):
    name = _original_name(file)
    suffix = Path(name).suffix.lower()
    if suffix not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=400,
            detail=f"Недозволене розширення. Дозволено: {allowed_text}",
        )
    payload = file.file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Порожній файл.")
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        handle.write(payload)
    finally:
        handle.close()
    return Path(handle.name)