#!/usr/bin/env python3
"""Build a labeled Quasimorph cursor-reference atlas from cursor_manifest.json.

Place this file in <project>\\tools\\build_cursor_atlas.py and run it with the
project virtual-environment Python. The newest sample for each category is used,
so the atlas stays compact as the collection grows.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    raise SystemExit(
        "Не найдена библиотека Pillow. Установи её командой:\n"
        '  .venv\\Scripts\\python.exe -m pip install pillow'
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "knowledge" / "cursor_examples" / "cursor_manifest.json"
OUTPUT_PATH = PROJECT_ROOT / "knowledge" / "cursor_examples" / "cursor_atlas.png"

CATEGORY_ORDER = [
    "floor",
    "movement",
    "enemy_hover",
    "ally_hover",
    "corpse_hover",
    "blocked_tile",
    "interactable_hover",
    "inventory_hover",
    "aim_attack",
    "other",
]

CATEGORY_LABELS = {
    "floor": "Обычная клетка",
    "movement": "Доступная клетка / маршрут",
    "enemy_hover": "Наведение на врага",
    "ally_hover": "Наведение на союзника",
    "corpse_hover": "Наведение на труп",
    "blocked_tile": "Недоступная клетка",
    "interactable_hover": "Интерактивный объект",
    "inventory_hover": "Предмет инвентаря",
    "aim_attack": "Прицеливание / атака",
    "other": "Другое состояние",
}

# One latest example per category gives a compact few-shot reference image.
CARD_COLUMNS = 4
CARD_WIDTH = 460
CARD_HEIGHT = 410
IMAGE_BOX = (436, 327)
MARGIN = 24
GAP = 20
HEADER_HEIGHT = 78


def load_font(size: int) -> ImageFont.ImageFont:
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = [
        windows / "Fonts" / "arial.ttf",
        windows / "Fonts" / "segoeui.ttf",
        windows / "Fonts" / "tahoma.ttf",
        windows / "Fonts" / "verdana.ttf",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def read_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Не найден манифест: {path}")
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("Ожидался JSON-массив записей в cursor_manifest.json")
    return [entry for entry in data if isinstance(entry, dict)]


def resolve_project_path(raw_path: str) -> Path:
    # Manifest stores relative Windows paths with backslashes.
    normalized = raw_path.replace("\\", os.sep).replace("/", os.sep)
    candidate = Path(normalized)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def newest_examples_by_category(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for entry in entries:
        category = str(entry.get("category", "")).strip()
        if not category:
            continue
        previous = selected.get(category)
        stamp = str(entry.get("captured_at", entry.get("id", "")))
        old_stamp = str((previous or {}).get("captured_at", (previous or {}).get("id", "")))
        if previous is None or stamp >= old_stamp:
            selected[category] = entry

    ordered = [selected.pop(category) for category in CATEGORY_ORDER if category in selected]
    # Preserve unknown future categories instead of silently dropping them.
    ordered.extend(selected[key] for key in sorted(selected))
    return ordered


def draw_card(
    canvas: Image.Image,
    entry: dict[str, Any],
    x: int,
    y: int,
    regular_font: ImageFont.ImageFont,
    small_font: ImageFont.ImageFont,
) -> bool:
    draw = ImageDraw.Draw(canvas)
    category = str(entry.get("category", "unknown"))
    label = CATEGORY_LABELS.get(category, category)
    files = entry.get("files") if isinstance(entry.get("files"), dict) else {}
    raw_image_path = files.get("cursor_zoom")
    if not isinstance(raw_image_path, str) or not raw_image_path.strip():
        print(f"[ПРОПУСК] У записи {entry.get('id', '?')} нет files.cursor_zoom")
        return False

    image_path = resolve_project_path(raw_image_path)
    if not image_path.is_file():
        print(f"[ПРОПУСК] Не найдено изображение: {image_path}")
        return False

    card_box = (x, y, x + CARD_WIDTH, y + CARD_HEIGHT)
    draw.rounded_rectangle(card_box, radius=14, fill=(38, 43, 51), outline=(92, 102, 116), width=2)

    # Keep title text inside the card even for longer category names.
    title = label
    max_title_width = CARD_WIDTH - 28
    while title and draw.textbbox((0, 0), title, font=regular_font)[2] > max_title_width:
        title = title[:-2].rstrip() + "…"
    draw.text((x + 14, y + 10), title, fill=(246, 248, 251), font=regular_font)

    image_x = x + (CARD_WIDTH - IMAGE_BOX[0]) // 2
    image_y = y + 56
    try:
        with Image.open(image_path) as source:
            reference = source.convert("RGB")
            resampling = getattr(Image, "Resampling", Image)
            lanczos = getattr(resampling, "LANCZOS")
            reference = ImageOps.contain(reference, IMAGE_BOX, method=lanczos)
    except (OSError, ValueError) as exc:
        print(f"[ПРОПУСК] Не удалось открыть {image_path}: {exc}")
        return False

    # Center the crop in the reserved image area; preserve its aspect ratio.
    paste_x = image_x + (IMAGE_BOX[0] - reference.width) // 2
    paste_y = image_y + (IMAGE_BOX[1] - reference.height) // 2
    canvas.paste(reference, (paste_x, paste_y))
    draw.rectangle(
        (image_x - 1, image_y - 1, image_x + IMAGE_BOX[0], image_y + IMAGE_BOX[1]),
        outline=(126, 137, 151),
        width=2,
    )

    sample_id = str(entry.get("id", ""))
    captured = str(entry.get("captured_at", ""))
    footer = f"ID: {sample_id}"
    if captured:
        footer += f"   |   {captured[:16].replace('T', ' ')}"
    draw.text((x + 14, y + CARD_HEIGHT - 24), footer, fill=(190, 198, 208), font=small_font)
    return True


def main() -> int:
    try:
        entries = read_manifest(MANIFEST_PATH)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ОШИБКА: {exc}")
        return 1

    selected = newest_examples_by_category(entries)
    if not selected:
        print("В манифесте пока нет записей для построения атласа.")
        return 1

    missing_categories = [category for category in CATEGORY_ORDER if not any(
        str(item.get("category", "")).strip() == category for item in entries
    )]

    rows = (len(selected) + CARD_COLUMNS - 1) // CARD_COLUMNS
    canvas_width = MARGIN * 2 + CARD_COLUMNS * CARD_WIDTH + (CARD_COLUMNS - 1) * GAP
    canvas_height = HEADER_HEIGHT + MARGIN + rows * CARD_HEIGHT + (rows - 1) * GAP + MARGIN
    canvas = Image.new("RGB", (canvas_width, canvas_height), (23, 27, 33))
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(30)
    card_font = load_font(24)
    small_font = load_font(14)

    draw.text((MARGIN, 16), "QUASIMORPH — CURSOR REFERENCE ATLAS", fill=(245, 247, 250), font=title_font)
    draw.text(
        (MARGIN, 52),
        f"Примеров в атласе: {len(selected)}   |   Записей в манифесте: {len(entries)}",
        fill=(180, 190, 202),
        font=small_font,
    )

    successful = 0
    for index, entry in enumerate(selected):
        col = index % CARD_COLUMNS
        row = index // CARD_COLUMNS
        x = MARGIN + col * (CARD_WIDTH + GAP)
        y = HEADER_HEIGHT + row * (CARD_HEIGHT + GAP)
        if draw_card(canvas, entry, x, y, card_font, small_font):
            successful += 1

    if successful == 0:
        print("Не удалось добавить ни одного изображения. Проверь пути files.cursor_zoom в манифесте.")
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        canvas.save(OUTPUT_PATH, format="PNG", optimize=True)
    except OSError as exc:
        print(f"Не удалось сохранить атлас: {exc}")
        return 1

    print(f"\nГотово: {OUTPUT_PATH}")
    print(f"Добавлено карточек: {successful}")
    if missing_categories:
        print("Нет примеров для категорий: " + ", ".join(missing_categories))
        print("Это не ошибка: атлас построен из доступных примеров.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
