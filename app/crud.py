from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from .facts import lookup_bird
from .models import Analysis


def save_analysis(db: Session, filename: str, scientific_name: str | None, common_name: str = "", confidence: float | None = None):
    if not scientific_name:
        return None

    facts = lookup_bird(scientific_name)
    display_common = facts["common_name"] or common_name
    bird_name = scientific_name
    if display_common:
        bird_name = f"{scientific_name} — {display_common}"
    description = facts["description"]
    details = facts["details"]
    if not description and not details:
        details = "Додаткові відомості недоступні: немає відповіді від Вікіпедії."
    return add_analysis(db, filename, bird_name, _confidence(confidence), description, details)


def _confidence(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def add_analysis(db: Session, filename: str, bird_name: str, confidence: float | None, description: str, source_details: str):
    row = Analysis(
        filename=filename,
        bird_name=bird_name,
        confidence=confidence,
        analyzed_at=datetime.now().astimezone(),
        description=description,
        source_details=source_details,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def statistics(db: Session):
    rows = list_analyses(db)
    species: dict[str, dict] = {}
    for row in rows:
        key = species_key(row.bird_name)
        bucket = species.setdefault(key, {"label": row.bird_name, "count": 0})
        bucket["count"] += 1
        if " — " in row.bird_name and " — " not in bucket["label"]:
            bucket["label"] = row.bird_name
    ranked = sorted(
        species.values(),
        key=lambda item: (-item["count"], item["label"].casefold()),
    )
    scored = [row for row in rows if row.confidence is not None]
    highest: list[Analysis] = []
    lowest: list[Analysis] = []
    if scored:
        max_score = max(row.confidence for row in scored)
        min_score = min(row.confidence for row in scored)
        highest = sorted(
            (row for row in scored if row.confidence == max_score),
            key=lambda row: row.id,
        )
        lowest = sorted(
            (row for row in scored if row.confidence == min_score),
            key=lambda row: row.id,
        )
    same_confidence = bool(scored) and {row.id for row in highest} == {row.id for row in lowest}
    return {
        "record_count": len(rows),
        "species": ranked,
        "highest": highest,
        "lowest": lowest,
        "same_confidence": same_confidence,
    }


def species_key(bird_name: str):
    return bird_name.split(" — ", 1)[0].strip().casefold()


def list_analyses(db: Session):
    statement = select(Analysis).order_by(Analysis.analyzed_at.desc(), Analysis.id.desc())
    return list(db.scalars(statement).all())


def search_analyses(db: Session, name: str):
    needle = name.casefold().strip()
    if not needle:
        return []
    return [row for row in list_analyses(db) if needle in row.bird_name.casefold()]


def get_analysis(db: Session, record_id: int):
    return db.get(Analysis, record_id)


def delete_analysis(db: Session, record_id: int, *, commit: bool = True):
    row = db.get(Analysis, record_id)
    if row is None:
        return False
    db.delete(row)
    if commit:
        db.commit()
    return True


def delete_analyses(db: Session, record_ids: list[int]):
    removed = 0
    for record_id in record_ids:
        if delete_analysis(db, record_id, commit=False):
            removed += 1
    db.commit()
    return removed