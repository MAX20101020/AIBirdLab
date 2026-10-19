import os
from dotenv import load_dotenv
from pathlib import Path
from db import statistics

load_dotenv()

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
token = os.getenv("TOKEN")

if token:
    os.environ["HF_TOKEN"] = token


def main():
    from db import init_db
    init_db()
    while True:
        try:
            menu = int(input(
                "===== AI Bird Lab =====\n"
                "1. Аналізувати за фотографією\n"
                "2. Аналізувати за аудіо\n"
                "3. Історія\n"
                "4. Пошук за назвою\n"
                "5. Видалення птаха із бд\n"
                "6. Статистика\n"
                "0. Вихід\n"
            ))
        except ValueError:
            print("Введіть номер пункту.")
            continue
        match menu:
            case 0:
                break
            case 1:
                analyze_photo()
            case 2:
                analyze_audio()
            case 3:
                show_history()
            case 4:
                search_bird()
            case 5:
                delete_bird()
            case 6:
                show_statistics()
        input("Press Enter to continue: ")


def input_file(type):
    photo_suffixes = [".jpg", ".png", ".jpeg"]
    path = Path(input("Enter the path of file: "))

    if not path.exists():
        print("Error: file is not found")
        return None
    if type == "photo":
        if not path.suffix.lower() in photo_suffixes:
            print(f"Error: suffix of photo not allowed! Allowed: {photo_suffixes}")
            return None
    elif type == "audio":
        if path.suffix.lower() != ".mp3":
            print("Error: suffix of audio not allowed! Allowed: .mp3")
            return None
    else:
        print("error")
        return None

    return path


def analyze_photo():
    path = input_file("photo")
    if path is None:
        return
    from photo import identify_photo
    predictions = identify_photo(path)
    if not predictions:
        return
    top = predictions[0]
    store(path, top.get("species"), top.get("common_name"), top.get("score"))


def analyze_audio():
    path = input_file("audio")
    if path is None:
        return
    from audio import identify_audio
    predictions = identify_audio(path)
    if not predictions:
        return
    top = predictions[0]
    store(path, top.get("scientific_name"), "", top.get("score"))


def show_history():
    from db import list_analyses
    rows = list_analyses()
    if not rows:
        print("Історія порожня.")
        return
    print(f"Записів: {len(rows)}")
    for row in rows:
        print_record(row)


def search_bird():
    from db import search_analyses
    name = input("Назва птаха: ").strip()
    if not name:
        print("Введіть назву.")
        return
    rows = search_analyses(name)
    if not rows:
        print("Нічого не знайдено.")
        return
    print(f"Знайдено: {len(rows)}")
    for row in rows:
        print_record(row)


def delete_bird():
    from db import delete_analyses, get_analysis, search_analyses
    raw = input("Введіть id запису або частину назви: ").strip()
    if not raw:
        print("Нічого не введено.")
        return
    if raw.isdigit():
        row = get_analysis(int(raw))
        if row is None:
            print("Запис не знайдено.")
            return
        print_record(row)
        if confirmed("Видалити цей запис?"):
            delete_analyses([row["id"]])
            print("Запис видалено.")
        else:
            print("Скасовано.")
        return

    rows = search_analyses(raw)
    if not rows:
        print("Нічого не знайдено.")
        return
    for row in rows:
        print_record(row)
    if confirmed(f"Видалити записи: {len(rows)}?"):
        removed = delete_analyses([row["id"] for row in rows])
        print(f"Видалено: {removed}.")
    else:
        print("Скасовано.")


def show_statistics():
    report = statistics()
    print("\n===== Статистика =====")
    print(f"Записів у базі: {report['record_count']}")
    if report["record_count"] == 0:
        print("У базі ще немає записів.")
        return

    print("\nНайчастіші види:")
    for index, species in enumerate(report["species"], start=1):
        print(f"{index}. {species['label']} — {species['count']}")

    if not report["scored"]:
        print("\nРівнів упевненості немає.")
        return

    highest = report["highest"]
    lowest = report["lowest"]
    if {row["id"] for row in highest} == {row["id"] for row in lowest}:
        print(f"\nУсі записи з упевненістю мають однаковий рівень: {percent(highest[0])}")
        for row in highest:
            print_confidence_row(row)
        return

    print(f"\nНайвища впевненість: {percent(highest[0])}")
    for row in highest:
        print_confidence_row(row)
    print(f"\nНайнижча впевненість: {percent(lowest[0])}")
    for row in lowest:
        print_confidence_row(row)


def percent(row):
    return f"{row['confidence'] * 100:.1f}%"


def print_confidence_row(row):
    print(f"#{row['id']}  {row['filename']}")
    print(f"   {row['bird_name']}")


def store(path: Path, scientific_name, common_name, score):
    if not scientific_name:
        return
    from db import save_analysis
    confidence = float(score) if isinstance(score, (int, float)) else None
    save_analysis(path.name, str(scientific_name), str(common_name or ""), confidence)


def confirmed(question: str):
    answer = input(f"{question} так/ні: ").strip().casefold()
    return answer in {"так", "т", "yes", "y"}


def print_record(row):
    confidence = row["confidence"]
    if confidence is None:
        shown = "немає"
    else:
        shown = f"{confidence * 100:.1f}%"
    when = row["analyzed_at"].replace("T", " ")
    print(f"\n#{row['id']}  {when}  {row['filename']}")
    print(f"   {row['bird_name']}")
    print(f"   впевненість: {shown}")
    if row["description"]:
        print(f"   опис: {row['description']}")
    if row["source_details"]:
        for index, line in enumerate(row["source_details"].splitlines()):
            prefix = "   відомості: " if index == 0 else "   "
            print(f"{prefix}{line}")


if __name__ == "__main__":
    main()