from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(r"D:\AI\QuasimorphAssistant")
SOURCE = PROJECT_ROOT / "app" / "screen_watcher.py"
CONTACT_DIR = PROJECT_ROOT / "knowledge" / "contact_examples"
CONTACT_ATLAS = CONTACT_DIR / "contact_atlas.jpg"
PATCH_MARKER = "# CURSOR_INTELLIGENCE_PATCH_V1"


def stop(message: str) -> None:
    raise RuntimeError(message)


def replace_exact(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        stop(f"{label}: найдено совпадений {count}, ожидалось ровно 1. Ничего не изменено.")
    return text.replace(old, new, 1)


def replace_regex(text: str, pattern: str, replacement, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        stop(f"{label}: найдено совпадений {count}, ожидалось ровно 1. Ничего не изменено.")
    return updated


def create_contact_atlas() -> Path:
    if not CONTACT_DIR.is_dir():
        stop(f"Не найдена папка с примерами контактов: {CONTACT_DIR}")

    images = [p for p in CONTACT_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    green = sorted((p for p in images if "зелен" in p.name.casefold()), key=lambda p: p.stat().st_mtime)
    red = sorted((p for p in images if "красн" in p.name.casefold()), key=lambda p: p.stat().st_mtime)
    if len(green) < 2 or len(red) < 2:
        stop(f"Нужно минимум 2 зелёных и 2 красных скриншота. Найдено: {len(green)} и {len(red)}.")

    tile_w, tile_h, label_h, gap = 800, 450, 36, 10
    atlas = Image.new("RGB", (tile_w * 2 + gap * 3, (tile_h + label_h) * 2 + gap * 3), (18, 22, 27))
    draw = ImageDraw.Draw(atlas)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default()

    samples = [
        (green[0], "GREEN CONTACT A"),
        (green[1], "GREEN CONTACT B"),
        (red[0], "RED CONTACT A"),
        (red[1], "RED CONTACT B"),
    ]
    resampling = getattr(Image, "Resampling", Image)
    for i, (path, label) in enumerate(samples):
        col, row = i % 2, i // 2
        x = gap + col * (tile_w + gap)
        y = gap + row * (tile_h + label_h + gap)
        draw.text((x + 8, y + 7), label, fill=(245, 245, 245), font=font)
        with Image.open(path) as opened:
            sample = opened.convert("RGB")
        sample.thumbnail((tile_w, tile_h), resampling.LANCZOS)
        px = x + (tile_w - sample.width) // 2
        py = y + label_h + (tile_h - sample.height) // 2
        atlas.paste(sample, (px, py))

    temp = CONTACT_DIR / "contact_atlas.tmp.jpg"
    atlas.save(temp, format="JPEG", quality=90, optimize=True)
    temp.replace(CONTACT_ATLAS)
    return CONTACT_ATLAS


def patch_source(source: str) -> str:
    if PATCH_MARKER in source:
        stop("Этот патч уже установлен. Повторное применение отменено.")
    if "CURSOR REFERENCE ATLAS — IMAGE 2:" not in source:
        stop("Не найден ожидаемый блок подключённого атласа курсора. Файл не изменён.")

    # The monitor-relative Windows cursor coordinates are captured with every frame.
    capture_helpers = '''


def get_cursor_position(monitor: dict) -> tuple[int, int] | None:
    """Получить позицию мыши относительно выбранного монитора."""
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_cursor_pos = user32.GetCursorPos
        get_cursor_pos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        get_cursor_pos.restype = wintypes.BOOL
        point = wintypes.POINT()
        if not get_cursor_pos(ctypes.byref(point)):
            return None
        x = int(point.x) - int(monitor.get("left", 0))
        y = int(point.y) - int(monitor.get("top", 0))
        if 0 <= x < int(monitor.get("width", 0)) and 0 <= y < int(monitor.get("height", 0)):
            return (x, y)
        return None
    except Exception:
        return None


def encode_cursor_crop_for_model(
    image: Image.Image, cursor_pos: tuple[int, int] | None
) -> bytes | None:
    """Увеличенный фрагмент того же кадра вокруг положения игрового курсора."""
    if cursor_pos is None:
        return None
    try:
        x, y = int(cursor_pos[0]), int(cursor_pos[1])
        crop_w, crop_h = min(360, image.width), min(270, image.height)
        left = max(0, min(image.width - crop_w, x - crop_w // 2))
        top = max(0, min(image.height - crop_h, y - crop_h // 2))
        crop = image.crop((left, top, left + crop_w, top + crop_h))
        resampling = getattr(Image, "Resampling", Image)
        crop = crop.resize((crop.width * 2, crop.height * 2), resampling.LANCZOS)
        buffer = io.BytesIO()
        crop.save(buffer, format="JPEG", quality=92, optimize=True)
        return buffer.getvalue()
    except Exception:
        return None
'''
    source = replace_exact(
        source,
        '    return Image.frombytes("RGB", shot.size, shot.rgb)\n',
        '    return Image.frombytes("RGB", shot.size, shot.rgb)\n' + capture_helpers,
        "Добавление получения координат и увеличенного фрагмента курсора",
    )

    source = replace_exact(
        source,
        '        self.image: Image.Image | None = None\n',
        '        self.image: Image.Image | None = None\n        self.cursor_pos: tuple[int, int] | None = None\n',
        "Поле cursor_pos в SharedFrame",
    )
    source = replace_exact(
        source,
        '    def set_image(self, image: Image.Image) -> None:\n',
        '    def set_image(\n        self, image: Image.Image, cursor_pos: tuple[int, int] | None = None\n    ) -> None:\n',
        "Сигнатура SharedFrame.set_image",
    )
    source = replace_regex(
        source,
        r'(?m)^(?P<indent>[ \t]+)self\.image = image\.copy\(\)[ \t]*\n(?:[ \t]*\n)*[ \t]*self\.captured_at = time\.monotonic\(\)[ \t]*$',
        lambda m: f'{m.group("indent")}self.image = image.copy()\n{m.group("indent")}self.cursor_pos = cursor_pos\n{m.group("indent")}self.captured_at = time.monotonic()',
        "Сохранение координат мыши с кадром",
    )
    get_return = '            return self.image.copy() if self.image is not None else None, self.captured_at\n'
    get_cursor_method = '''

    def get_with_cursor(
        self,
    ) -> tuple[Image.Image | None, float, tuple[int, int] | None]:
        with self.lock:
            image = self.image.copy() if self.image is not None else None
            return image, self.captured_at, self.cursor_pos
'''
    source = replace_exact(source, get_return, get_return + get_cursor_method, "Новый метод SharedFrame.get_with_cursor")

    source = replace_exact(
        source,
        '                shared.set_image(capture_rgb(sct, monitor))\n',
        '                frame = capture_rgb(sct, monitor)\n'
        '                cursor_pos = get_cursor_position(monitor)\n'
        '                shared.set_image(frame, cursor_pos)\n',
        "Передача координат из capture_worker",
    )
    source = replace_exact(source, '        image, reason = job\n', '        image, reason, cursor_pos = job\n', "Формат задания model_worker")
    source = replace_exact(
        source,
        '            report = ask_model(client, image, reason)\n',
        '            report = ask_model(client, image, reason, cursor_pos)\n',
        "Передача координат в ask_model",
    )
    source = replace_exact(
        source,
        'def ask_model(client: ollama.Client, image: Image.Image, reason: str) -> str:\n',
        'def ask_model(\n'
        '    client: ollama.Client,\n'
        '    image: Image.Image,\n'
        '    reason: str,\n'
        '    cursor_pos: tuple[int, int] | None = None,\n'
        ') -> str:\n',
        "Сигнатура ask_model",
    )

    source = replace_exact(
        source,
        '    initial_image, initial_ts = shared.get()\n',
        '    initial_image, initial_ts, initial_cursor_pos = shared.get_with_cursor()\n',
        "Начальный кадр и координаты",
    )
    source = replace_exact(
        source,
        '            current_image, captured_at = shared.get()\n',
        '            current_image, captured_at, current_cursor_pos = shared.get_with_cursor()\n',
        "Текущий кадр и координаты",
    )
    source = replace_exact(
        source,
        '                    latest_image, _ = shared.get()\n',
        '                    latest_image, _, latest_cursor_pos = shared.get_with_cursor()\n',
        "Периодический кадр и координаты",
    )

    source = replace_regex(
        source,
        r'(?m)^(    )pending_reason = ""[ \t]*$',
        '    pending_reason = ""\n    pending_cursor_pos: tuple[int, int] | None = None',
        "Инициализация координат отложенного кадра",
    )
    source = replace_exact(
        source,
        '    def submit(image: Image.Image, reason: str) -> None:\n',
        '    def submit(\n'
        '        image: Image.Image,\n'
        '        reason: str,\n'
        '        cursor_pos: tuple[int, int] | None = None,\n'
        '    ) -> None:\n',
        "Сигнатура submit",
    )
    source = replace_exact(
        source,
        '        nonlocal analysis_busy, last_analysis_at, reference_small, consecutive_hits, pending_image, pending_reason\n',
        '        nonlocal analysis_busy, last_analysis_at, reference_small, consecutive_hits, pending_image, pending_reason, pending_cursor_pos\n',
        "nonlocal pending_cursor_pos",
    )
    source = replace_exact(
        source,
        '            jobs.put_nowait((image.copy(), reason))\n',
        '            jobs.put_nowait((image.copy(), reason, cursor_pos))\n',
        "Передача координат в очередь",
    )

    source, reset_count = re.subn(
        r'(?m)^(\s*)pending_image = None[ \t]*$',
        lambda m: f'{m.group(1)}pending_image = None\n{m.group(1)}pending_cursor_pos = None',
        source,
    )
    if reset_count < 2:
        stop(f"Сброс pending_image: найдено только {reset_count} мест, ожидалось минимум 2.")

    source, set_count = re.subn(
        r'(?m)^(\s*)pending_image = current_image\.copy\(\)[ \t]*$',
        lambda m: f'{m.group(1)}pending_image = current_image.copy()\n{m.group(1)}pending_cursor_pos = current_cursor_pos',
        source,
    )
    if set_count != 2:
        stop(f"Сохранение отложенных кадров: найдено {set_count} присваиваний, ожидалось ровно 2.")

    source = replace_regex(
        source,
        r'(?m)^(\s*)submit\(initial_image, ("[^"]*")\)[ \t]*$',
        r'\1submit(initial_image, \2, initial_cursor_pos)',
        "Отправка первичного кадра",
    )
    source = replace_regex(
        source,
        r'(?m)^(\s*)submit\(pending_image, pending_reason or ("[^"]*")\)[ \t]*$',
        r'\1submit(pending_image, pending_reason or \2, pending_cursor_pos)',
        "Отправка отложенного кадра",
    )
    source = replace_regex(
        source,
        r'(?m)^(\s*)submit\(latest_image, ("[^"]*")\)[ \t]*$',
        r'\1submit(latest_image, \2, latest_cursor_pos)',
        "Отправка периодического кадра",
    )

    reference_helper = '''def encode_reference_atlas_for_model(path: Path, max_width: int = 1280) -> bytes:
    with Image.open(path) as source_image:
        reference = source_image.convert("RGB")
    if reference.width > max_width:
        resampling = getattr(Image, "Resampling", Image)
        height = max(1, int(reference.height * max_width / reference.width))
        reference = reference.resize((max_width, height), resampling.LANCZOS)
    buffer = io.BytesIO()
    reference.save(buffer, format="JPEG", quality=88, optimize=True)
    return buffer.getvalue()


'''
    source = replace_exact(source, 'def ask_model(\n', reference_helper + 'def ask_model(\n', "Кодировщик атласа контактов")

    insertion_point = '    # Gameplay gets the full screenshot and, when available, the cursor atlas.\n'
    scene_additions = '''    # CURSOR_INTELLIGENCE_PATCH_V1
    # The crop and cursor coordinates belong to this exact submitted frame.
    cursor_crop_bytes = encode_cursor_crop_for_model(image, cursor_pos)
    if cursor_crop_bytes:
        cursor_image_number = len(scene_images) + 1
        scene_images.append(cursor_crop_bytes)
        scene_system += (
            f"\\n\\nCURRENT CURSOR CROP — IMAGE {cursor_image_number}:\\n"
            "An enlarged crop of the CURRENT screenshot around the Windows "
            "mouse position. Inspect the rendered IN-GAME cursor and the "
            "tile/object under it. The crop is from this same frame, not a "
            "separate Windows cursor picture. If no in-game cursor is visible, "
            "say so; do not guess.\\n"
        )
        scene_prompt += (
            f"\\n\\nInspect IMAGE {cursor_image_number} as the enlarged current "
            "cursor area. Report the cursor state and hovered target only "
            "when visually supported. Cursor appearance never replaces a "
            "directly linked health bar.\\n"
            "Курсор: состояние и объект под ним, если различимы.\\n"
        )

    contact_atlas_path = (
        Path(__file__).resolve().parents[1]
        / "knowledge" / "contact_examples" / "contact_atlas.jpg"
    )
    try:
        contact_atlas_bytes = encode_reference_atlas_for_model(contact_atlas_path)
        contact_image_number = len(scene_images) + 1
        scene_images.append(contact_atlas_bytes)
        scene_system += (
            f"\\n\\nSNEAK CONTACT REFERENCE ATLAS — IMAGE {contact_image_number}:\\n"
            "Reference-only examples from the user's Quasimorph screenshots. "
            "GREEN examples represent friendly detected contacts outside "
            "direct line of sight; RED examples represent hostile detected "
            "contacts. The atlas itself is NOT evidence that a contact exists "
            "in the current scene. Report only markers actually visible in "
            "the CURRENT gameplay screenshot. A contact icon is not a body "
            "and must not be counted as a visible NPC.\\n"
            "Do not confuse contact icons with health bars, cursor icons, "
            "inventory indicators or unrelated minimap symbols. If shape or "
            "color is unclear, mark the contact as ambiguous. If the body "
            "is visible, classify it from its own directly linked health bar.\\n"
        )
        scene_prompt += (
            f"\\n\\nSIXTH: compare the CURRENT screenshot with IMAGE {contact_image_number}. "
            "List clearly visible red/green contact icons separately from "
            "visible NPC bodies. Give approximate screen position only; do "
            "not invent world coordinates. Do not copy contacts from the "
            "reference atlas into the current scene. If an entity is both "
            "visible as a body and represented by a marker, do not count it "
            "twice.\\n"
            "If '?' or '!' is clearly attached to an enemy, report the symbol "
            "and its state separately: '?' means investigating; '!' means "
            "alerted/engaging. Report only symbols actually visible, not "
            "inferred reactions to sounds.\\n"
            "Add concise Russian sections:\\n"
            "Контакты вне прямой видимости: красные / зелёные / неоднозначные "
            "маркеры и примерное положение, либо нет.\\n"
            "Состояние тревоги: видимые '?'/'!' и связанный NPC, либо не видно.\\n"
        )
    except (OSError, ValueError) as exc:
        if not getattr(ask_model, "_contact_atlas_warning_shown", False):
            print(
                f"[WARN] Contact atlas unavailable ({contact_atlas_path}): {exc}. "
                "Gameplay analysis will continue without contact references.",
                flush=True,
            )
            ask_model._contact_atlas_warning_shown = True

'''
    source = replace_exact(source, insertion_point, scene_additions + insertion_point, "Добавление анализа курсора и обнаруженных контактов")

    source = replace_regex(
        source,
        r'(?s)(    scene_report\s*=\s*run_one\(\s*"gameplay"\s*,\s*scene_system\s*,\s*scene_prompt\s*,\s*scene_images\s*,\s*)400(\s*,?\s*\))',
        r'\g<1>520\g<2>',
        "Лимит токенов игрового анализа",
    )

    if PATCH_MARKER not in source:
        stop("Внутренняя проверка не обнаружила маркер патча.")
    return source


def main() -> int:
    print("Quasimorph Assistant — интеграция курсора и обнаруженных контактов")
    if not SOURCE.is_file():
        print(f"ОШИБКА: не найден {SOURCE}")
        return 1

    raw = SOURCE.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    try:
        original = raw.decode("utf-8-sig")
        normalized = original.replace("\r\n", "\n").replace("\r", "\n")
        patched = patch_source(normalized)
        compile(patched, str(SOURCE), "exec")
        atlas_path = create_contact_atlas()
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        print("screen_watcher.py не изменён.")
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = SOURCE.with_name(f"screen_watcher.py.bak_cursor_intelligence_{stamp}")
    shutil.copy2(SOURCE, backup)
    output = (b"\xef\xbb\xbf" if has_bom else b"") + patched.replace("\n", newline).encode("utf-8")
    temp = SOURCE.with_suffix(SOURCE.suffix + ".tmp")
    try:
        temp.write_bytes(output)
        check = temp.read_bytes().decode("utf-8-sig")
        compile(check, str(SOURCE), "exec")
        temp.replace(SOURCE)
    except Exception:
        temp.unlink(missing_ok=True)
        shutil.copy2(backup, SOURCE)
        print("ОШИБКА записи: исходник восстановлен из резервной копии.")
        return 1

    print("Готово: интеграция установлена.")
    print(f"Резервная копия: {backup}")
    print(f"Атлас контактов: {atlas_path}")
    print("Добавлено: координаты курсора вместе с кадром, увеличенный фрагмент, отдельный атлас контактов Sneak,")
    print("раздельный вывод видимых NPC и контактов вне прямой видимости, отдельное чтение '?' и '!'.")
    print("HUD, фильтр фокуса окна и num_ctx не менялись; синтаксис проверен.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Критическая ошибка патчера: {exc}")
        raise SystemExit(1)
