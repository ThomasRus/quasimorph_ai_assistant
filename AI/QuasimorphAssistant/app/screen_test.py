from __future__ import annotations

import io
import sys
import traceback
from typing import Any

import mss
import ollama
from PIL import Image

MODEL = "qwen3-vl:4b"
MAX_IMAGE_SIDE = 1600
JPEG_QUALITY = 88


def choose_monitor(sct: mss.mss) -> dict[str, int]:
    monitors = sct.monitors
    print("\nДоступные области захвата:")
    for index, monitor in enumerate(monitors):
        label = "Все мониторы (единый рабочий стол)" if index == 0 else f"Монитор {index}"
        print(
            f"  {index}: {label} — "
            f"{monitor['width']}x{monitor['height']} "
            f"(x={monitor['left']}, y={monitor['top']})"
        )

    default_index = 1 if len(monitors) > 1 else 0
    raw = input(f"\nНомер области для захвата [Enter = {default_index}]: ").strip()
    if not raw:
        selected = default_index
    else:
        try:
            selected = int(raw)
        except ValueError as exc:
            raise ValueError("Нужно ввести номер монитора из списка.") from exc

    if selected < 0 or selected >= len(monitors):
        raise ValueError("Такого номера монитора нет в списке.")
    return monitors[selected]


def capture_image() -> bytes:
    with mss.mss() as sct:
        monitor = choose_monitor(sct)
        shot = sct.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.rgb)

    original_size = image.size
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    data = buffer.getvalue()

    print(f"\nСкриншот захвачен: {original_size[0]}x{original_size[1]}")
    if image.size != original_size:
        print(f"Уменьшен для анализа: {image.width}x{image.height}")
    print(f"Размер изображения: {len(data) / 1024:.0f} КБ")
    return data


def ask_model(image_bytes: bytes) -> str:
    prompt = (
        "Ты — локальный игровой наблюдатель для Quasimorph. "
        "Опиши только то, что действительно видно на скриншоте. "
        "Сначала определи экран/ситуацию (например, меню, инвентарь, бой, карта, "
        "контракт или интерфейс станции). Затем перечисли читаемые важные данные: "
        "здоровье, ранения, голод, оружие, предметы, противников и цели — "
        "только если они различимы. Если текст мелкий или элемент неясен, "
        "прямо скажи об этом и не угадывай. В конце дай один краткий полезный совет, "
        "основанный исключительно на видимом. Отвечай по-русски."
    )

    response: Any = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": [image_bytes],
            }
        ],
        options={"temperature": 0.2},
        keep_alive="5m",
    )
    return response.message.content or "Модель вернула пустой ответ."


def main() -> int:
    print("=" * 62)
    print("Quasimorph Assistant — первый тест зрения")
    print(f"Модель: {MODEL}")
    print("Изображение отправляется локальному Ollama на этом компьютере.")
    print("Скриншот не сохраняется в файл этой программой.")
    print("=" * 62)

    try:
        image_bytes = capture_image()
        print("\nПередаю изображение локальной модели. Это может занять некоторое время...\n")
        answer = ask_model(image_bytes)
        print("\n" + "=" * 62)
        print("ОТВЕТ QWEN3-VL")
        print("=" * 62)
        print(answer)
        print("\n" + "=" * 62)
        return 0
    except ollama.ResponseError as exc:
        print(f"Ошибка Ollama: {exc}", file=sys.stderr)
        print("Проверь, что Ollama запущена и модель доступна командой: ollama list", file=sys.stderr)
        return 2
    except (ConnectionError, OSError) as exc:
        print(f"Не удалось захватить экран или подключиться к Ollama: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"Неожиданная ошибка: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
