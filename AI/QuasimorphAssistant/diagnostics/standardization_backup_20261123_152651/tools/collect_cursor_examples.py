from pathlib import Path
from datetime import datetime
import ctypes
import json
import time
from ctypes import wintypes

import mss
from PIL import Image


PROJECT = Path(r"D:\AI\QuasimorphAssistant")
OUTPUT_DIR = PROJECT / "knowledge" / "cursor_examples"
MANIFEST = OUTPUT_DIR / "cursor_manifest.json"

GAME_PROCESS = "Quasimorph"
MONITOR_INDEX = 1

COUNTDOWN = 8

CROP_WIDTH = 480
CROP_HEIGHT = 360
CROP_SCALE = 2

CATEGORIES = {
    "1": ("floor", "Обычная клетка"),
    "2": ("movement", "Доступная клетка / маршрут движения"),
    "3": ("enemy_hover", "Наведение на врага"),
    "4": ("ally_hover", "Наведение на союзника"),
    "5": ("corpse_hover", "Наведение на труп"),
    "6": ("interactable_hover", "Наведение на интерактивный объект"),
    "7": ("inventory_hover", "Наведение на предмет инвентаря"),
    "8": ("blocked_tile", "Недоступная клетка"),
    "9": ("aim_attack", "Прицеливание / атака"),
    "10": ("other", "Другой вариант"),
}


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


if __name__ == "__main__":
    if not hasattr(ctypes, "WinDLL"):
        raise SystemExit("This collector requires Windows.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.GetForegroundWindow.restype = wintypes.HWND

    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE

    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL


    def foreground_process():
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        if not pid.value:
            return None

        handle = kernel32.OpenProcess(
            0x1000, False, pid.value
        )

        if not handle:
            return None

        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))

            success = kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(size)
            )

            if not success:
                return None

            return Path(buffer.value).stem

        finally:
            kernel32.CloseHandle(handle)


    def cursor_position():
        point = POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            raise RuntimeError("Unable to read pointer position")
        return int(point.x), int(point.y)


    def load_manifest():
        if not MANIFEST.exists():
            return []

        try:
            data = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise RuntimeError(
                f"Cannot read existing manifest: {exc}"
            )

        if not isinstance(data, list):
            raise RuntimeError("Manifest has unexpected format")

        return data


    def make_cursor_crop(image, x, y):
        width, height = image.size

        crop_w = min(CROP_WIDTH, width)
        crop_h = min(CROP_HEIGHT, height)

        left = max(0, min(width - crop_w, x - crop_w // 2))
        top = max(0, min(height - crop_h, y - crop_h // 2))

        crop = image.crop((
            left,
            top,
            left + crop_w,
            top + crop_h,
        ))

        enlarged = crop.resize(
            (
                crop.width * CROP_SCALE,
                crop.height * CROP_SCALE,
            ),
            Image.Resampling.LANCZOS,
        )

        return enlarged, (left, top, left + crop_w, top + crop_h)


    def save_sample(sct, monitor, category, label, notes):
        if foreground_process() != GAME_PROCESS:
            print(
                "SKIPPED: Quasimorph is not the active window. "
                "No image saved."
            )
            return False

        screen_x, screen_y = cursor_position()

        relative_x = screen_x - monitor["left"]
        relative_y = screen_y - monitor["top"]

        if not (
            0 <= relative_x < monitor["width"]
            and 0 <= relative_y < monitor["height"]
        ):
            print("SKIPPED: Cursor is outside the selected monitor.")
            return False

        shot = sct.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.rgb)

        enlarged, crop_box = make_cursor_crop(
            image, relative_x, relative_y
        )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        category_dir = OUTPUT_DIR / category
        category_dir.mkdir(parents=True, exist_ok=True)

        full_path = category_dir / f"full_{stamp}.png"
        crop_path = category_dir / f"cursor_zoom_{stamp}.png"

        image.save(full_path, format="PNG")
        enlarged.save(crop_path, format="PNG")

        record = {
            "id": stamp,
            "category": category,
            "label": label,
            "captured_at": datetime.now().astimezone().isoformat(),
            "foreground_process": GAME_PROCESS,
            "monitor": {
                "index": MONITOR_INDEX,
                "width": monitor["width"],
                "height": monitor["height"],
                "left": monitor["left"],
                "top": monitor["top"],
            },
            "cursor_position": {
                "screen": [screen_x, screen_y],
                "monitor": [relative_x, relative_y],
            },
            "crop_box": list(crop_box),
            "notes": notes,
            "files": {
                "full_screen": str(full_path.relative_to(PROJECT)),
                "cursor_zoom": str(crop_path.relative_to(PROJECT)),
            },
        }

        manifest = load_manifest()
        manifest.append(record)

        MANIFEST.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print()
        print("SAVED:", label)
        print("Full screen:", full_path)
        print("Cursor zoom:", crop_path)
        print("Manifest:", MANIFEST)
        print()

        return True


    def main():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        print("=" * 65)
        print("QUASIMORPH — CURSOR EXAMPLE COLLECTOR")
        print("=" * 65)
        print("Output:", OUTPUT_DIR)
        print("Monitor:", MONITOR_INDEX)
        print("Cursor zoom:", CROP_WIDTH, "x", CROP_HEIGHT, "at 2x")
        print()
        print("Windows cursor image is NOT captured.")
        print("Its position is used only to center the image crop.")
        print("The screenshots contain whatever cursor Quasimorph renders.")
        print()

        with mss.MSS() as sct:
            monitors = sct.monitors

            if len(monitors) <= MONITOR_INDEX:
                print("ERROR: Selected monitor not found.")
                return 1

            monitor = dict(monitors[MONITOR_INDEX])

            print(
                f"Selected monitor: "
                f"{monitor['width']}x{monitor['height']}"
            )

            while True:
                print()
                for key, (_, label) in CATEGORIES.items():
                    print(f"  {key:>2}. {label}")
                print("   0. Завершить сбор")

                choice = input("\nВыбери состояние курсора: ").strip()

                if choice == "0":
                    break

                if choice not in CATEGORIES:
                    print("Неизвестный номер. Попробуй ещё раз.")
                    continue

                category, label = CATEGORIES[choice]

                notes = input(
                    "Дополнительная пометка (Enter — пропустить): "
                ).strip()

                print()
                print(f"Состояние: {label}")
                print("Переключись в Quasimorph и установи курсор ")
                print("в нужное положение.")
                print(f"Захват через {COUNTDOWN} секунд:")

                for remaining in range(COUNTDOWN, 0, -1):
                    print(f"  {remaining}...", flush=True)
                    time.sleep(1)

                save_sample(
                    sct,
                    monitor,
                    category,
                    label,
                    notes,
                )

                input(
                    "Нажми Enter в PowerShell для следующего примера..."
                )

        print()
        print("Сбор завершён.")
        print("Примеры находятся в:", OUTPUT_DIR)
        return 0


    if __name__ == "__main__":
        try:
            raise SystemExit(main())
        except KeyboardInterrupt:
            print("\nСбор прерван пользователем.")
