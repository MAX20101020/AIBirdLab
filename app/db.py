import sqlite3
from datetime import datetime
from pathlib import Path
from facts import lookup_bird

DB_PATH = Path(__file__).resolve().parent.parent / "birds.db"


def init_db():
    with _connect():
        return


def save_analysis(filename: str, scientific_name: str, common_name: str = "", confidence: float | None = None,):
    print("Шукаю опис у Вікіпедії та Вікіданих...")
    facts = lookup_bird(scientific_name)
    display_common = facts["common_name"] or common_name
    bird_name = scientific_name
    if display_common:
        bird_name = f"{scientific_name} — {display_common}"
    description = facts["description"]
    details = facts["details"]
    if not description and not details:
        details = "Додаткові відомості недоступні: немає відповіді від Вікіпедії."

    record_id = add_analysis(filename, bird_name, confidence, description, details)
    print(f"Збережено в базу, id={record_id}.")
    if description:
        print(f"Опис: {description}")
    if details:
        print(details)
    return record_id


def add_analysis(
    filename: str,
    bird_name: str,
    confidence: float | None,
    description: str,
    source_details: str,
):
    analyzed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO analyses (
                filename, bird_name, confidence, analyzed_at, description, source_details
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (filename, bird_name, confidence, analyzed_at, description, source_details),
        )
        return int(cursor.lastrowid)


def statistics() -> dict:
    rows = list_analyses()
    species: dict[str, dict] = {}
    for row in rows:
        key = species_key(row["bird_name"])
        bucket = species.setdefault(key, {"label": row["bird_name"], "count": 0})
        bucket["count"] += 1
        if " — " in row["bird_name"] and " — " not in bucket["label"]:
            bucket["label"] = row["bird_name"]
    ranked = sorted(
        species.values(),
        key=lambda item: (-item["count"], item["label"].casefold()),
    )
    scored = [row for row in rows if row["confidence"] is not None]
    highest = []
    lowest = []
    if scored:
        max_score = max(row["confidence"] for row in scored)
        min_score = min(row["confidence"] for row in scored)
        highest = sorted(
            (row for row in scored if row["confidence"] == max_score),
            key=lambda row: row["id"],
        )
        lowest = sorted(
            (row for row in scored if row["confidence"] == min_score),
            key=lambda row: row["id"],
        )
    return {
        "record_count": len(rows),
        "species": ranked,
        "scored": scored,
        "highest": highest,
        "lowest": lowest,
    }

def species_key(bird_name: str):
    return bird_name.split(" — ", 1)[0].strip().casefold()


def list_analyses():
    with _connect() as conn:
        return list(conn.execute(
            "SELECT * FROM analyses ORDER BY analyzed_at DESC, id DESC"
        ))


def search_analyses(name: str):
    needle = name.casefold().strip()
    if not needle:
        return []
    return [
        row for row in list_analyses()
        if needle in row["bird_name"].casefold()
    ]


def get_analysis(record_id: int):
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM analyses WHERE id = ?",
            (record_id,),
        ).fetchone()


def delete_analysis(record_id: int):
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (record_id,))
        return cursor.rowcount > 0


def delete_analyses(record_ids: list[int]):
    removed = 0
    for record_id in record_ids:
        if delete_analysis(record_id):
            removed += 1
    return removed


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            bird_name TEXT NOT NULL,
            confidence REAL,
            analyzed_at TEXT NOT NULL,
            description TEXT,
            source_details TEXT
        )
        """
    )
    return conn