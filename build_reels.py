import os
import argparse
import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageEnhance
from moviepy import VideoClip, AudioFileClip

# =========================
# RENDER SETTINGS
# =========================

VIDEO_CODEC = "libx264"  # кодек видео (H.264 — стандарт для Instagram / TikTok / YouTube)

AUDIO_CODEC = "aac"      # кодек аудио (лучше всего совместим с mp4)

BITRATE = "9000k"        # битрейт видео
                         # влияет на качество и размер файла
                         # 6000k  — минимально нормальное качество
                         # 8000k  — хорошее качество
                         # 9000k+ — почти без потерь для Reels

THREADS = 8              # количество потоков рендера
                         # обычно = количеству ядер CPU
                         # можно поставить 6–8 для 8-ядерного процессора

PRESET = "medium"        # баланс скорости кодирования и качества
                         # ultrafast — максимально быстро, хуже сжатие
                         # veryfast  — очень быстро
                         # fast      — быстрый рендер
                         # medium    — стандарт FFmpeg
                         # slow      — лучшее качество при хорошем CPU
                         # slower    — ещё лучше, но заметно медленнее

# =========================
# VIDEO SETTINGS
# =========================

VIDEO_W = 1080     # ширина итогового видео (формат Reels / Shorts)
VIDEO_H = 1920     # высота итогового видео (вертикальный формат 9:16)
FPS = 30           # количество кадров в секунду

# =========================
# ANIMATION SETTINGS
# =========================

TOTAL_DURATION = 10.0     # общая длительность ролика в секундах
REVEAL_DURATION = 9.0     # длительность анимации "проявления" превью
PARALLAX_ENABLED = True
PARALLAX_STRENGTH = 0.66
SLOW_ZOOM_ENABLED = True
SLOW_ZOOM_STRENGTH = 1.0
EXPOSURE_PULSE_ENABLED = True
EXPOSURE_PULSE_STRENGTH = 0.15
EXPOSURE_PULSE_SPEED = 2.0

# =========================
# CARD VISUAL SETTINGS
# =========================

CARD_SCALE = 0.75   # ширина карточки относительно ширины видео (0.78 = 78%)
CARD_RADIUS = 36    # радиус скругления углов карточек
CARD_GAP = 40       # расстояние между карточками по вертикали

def recalculate_layout() -> None:
    global CARD_W, CARD_H, CARD_X, TOTAL_BLOCK_HEIGHT, START_Y, CARD_LAYOUTS

    CARD_W = int(VIDEO_W * CARD_SCALE)
    CARD_H = int(CARD_W * 9 / 16)

    CARD_X = (VIDEO_W - CARD_W) // 2

    TOTAL_BLOCK_HEIGHT = CARD_H * 3 + CARD_GAP * 2
    START_Y = (VIDEO_H - TOTAL_BLOCK_HEIGHT) // 2

    CARD_LAYOUTS = [
        {"x": CARD_X, "y": START_Y, "w": CARD_W, "h": CARD_H},
        {"x": CARD_X, "y": START_Y + CARD_H + CARD_GAP, "w": CARD_W, "h": CARD_H},
        {"x": CARD_X, "y": START_Y + (CARD_H + CARD_GAP) * 2, "w": CARD_W, "h": CARD_H},
    ]

recalculate_layout()

@dataclass
class CardPair:
    sketch: Image.Image
    result: Image.Image
    position: Tuple[int, int]
    size: Tuple[int, int]


def ensure_file_exists(path: str) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл не найден: {path}")


def load_rgba(path: str) -> Image.Image:
    ensure_file_exists(path)
    return Image.open(path).convert("RGBA")

def fit_image_cover(img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    target_w, target_h = target_size

    img.thumbnail((target_w, target_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))

    x = (target_w - img.width) // 2
    y = (target_h - img.height) // 2

    canvas.paste(img, (x, y))

    return canvas

def fit_image_stretch(img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    return img.resize(target_size, Image.LANCZOS)


def add_rounded_corners(img: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return img

    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=radius, fill=255)

    out = img.copy()
    out.putalpha(mask)
    return out


def prepare_card_image(path: str, size: Tuple[int, int]) -> Image.Image:
    img = load_rgba(path)
    img = fit_image_stretch(img, size)
    img = add_rounded_corners(img, CARD_RADIUS)
    return img


def paste_rgba(base: Image.Image, overlay: Image.Image, xy: Tuple[int, int]) -> None:
    base.alpha_composite(overlay, dest=xy)


def get_progress(t: float) -> float:
    if t <= 0:
        return 0.0
    if t >= REVEAL_DURATION:
        return 1.0
    return t / REVEAL_DURATION


def build_reveal_card(sketch: Image.Image, result: Image.Image, progress: float) -> Image.Image:
    progress = max(0.0, min(1.0, progress))

    w, h = sketch.size
    reveal_w = int(w * progress)

    frame = sketch.copy()

    if reveal_w > 0:
        revealed_part = result.crop((0, 0, reveal_w, h))
        frame.alpha_composite(revealed_part, dest=(0, 0))

    return frame


def apply_parallax_right(background: Image.Image, t: float, strength: float) -> Image.Image:
    strength = max(0.0, min(float(strength), 2.0))
    if strength <= 0.0:
        return background.copy()

    phase = t / max(TOTAL_DURATION, 0.001)
    pad_x = max(8, int(VIDEO_W * (0.02 * strength)))
    extended_bg = background.resize((VIDEO_W + pad_x, VIDEO_H), Image.LANCZOS)
    max_shift = extended_bg.width - VIDEO_W
    left = int(max_shift * (1.0 - phase))
    top = 0
    return extended_bg.crop((left, top, left + VIDEO_W, top + VIDEO_H))


def apply_slow_zoom(background: Image.Image, t: float, strength: float) -> Image.Image:
    strength = max(0.0, min(float(strength), 2.0))
    if strength <= 0.0:
        return background.copy()

    phase = t / max(TOTAL_DURATION, 0.001)
    zoom = 1.0 + (0.025 * strength * phase)
    scaled_w = max(VIDEO_W, int(VIDEO_W * zoom))
    scaled_h = max(VIDEO_H, int(VIDEO_H * zoom))
    scaled_bg = background.resize((scaled_w, scaled_h), Image.LANCZOS)

    left = (scaled_w - VIDEO_W) // 2
    top = (scaled_h - VIDEO_H) // 2
    return scaled_bg.crop((left, top, left + VIDEO_W, top + VIDEO_H))


def apply_exposure_pulse(background: Image.Image, t: float, strength: float) -> Image.Image:
    strength = max(0.0, min(float(strength), 2.0))
    if strength <= 0.0:
        return background.copy()

    # Fast flicker: roughly half the time "on", half "off", with softened edges.
    phase = t / max(TOTAL_DURATION, 0.001)
    speed = max(0.0, min(float(EXPOSURE_PULSE_SPEED), 2.0))
    min_hz = 2.0
    max_hz = max(min_hz, float(FPS))
    flicker_hz = min_hz + (max_hz - min_hz) * (speed / 2.0)
    cycle = math.sin(2.0 * math.pi * phase * flicker_hz)
    pulse = 1.0 if cycle > 0.0 else 0.0
    pulse = 0.7 * pulse + 0.3 * max(0.0, cycle)
    brightness = 1.0 + (0.06 * strength) * pulse - (0.01 * strength) * (1.0 - pulse)
    contrast = 1.0 + (0.09 * strength) * pulse

    frame = ImageEnhance.Brightness(background).enhance(brightness)
    frame = ImageEnhance.Contrast(frame).enhance(contrast)
    return frame


def render_background_frame(background: Image.Image, t: float) -> Image.Image:
    frame = background.copy()

    if PARALLAX_ENABLED:
        frame = apply_parallax_right(frame, t, PARALLAX_STRENGTH)

    if SLOW_ZOOM_ENABLED:
        frame = apply_slow_zoom(frame, t, SLOW_ZOOM_STRENGTH)

    if EXPOSURE_PULSE_ENABLED:
        frame = apply_exposure_pulse(frame, t, EXPOSURE_PULSE_STRENGTH)

    return frame


def make_frame_factory(background: Image.Image, cards: List[CardPair], progress_callback=None):
    total_frames = max(1, int(TOTAL_DURATION * FPS))
    last_reported_frame = {"value": 0}

    def make_frame(t: float):
        progress = get_progress(t)

        current_frame = min(total_frames, int(t * FPS) + 1)

        if progress_callback and current_frame > last_reported_frame["value"]:
            last_reported_frame["value"] = current_frame
            percent = int((current_frame / total_frames) * 100)
            progress_callback(percent)

        canvas = render_background_frame(background, t)

        for card in cards:
            reveal_card = build_reveal_card(card.sketch, card.result, progress)
            paste_rgba(canvas, reveal_card, card.position)

        return np.array(canvas.convert("RGB"))

    return make_frame


def build_video(
    input_dir: str,
    background_path: str,
    music_path: str,
    output_path: str,
    logger=None,
    progress_callback=None,
) -> None:
    ensure_file_exists(background_path)

    for i in range(1, 4):
        ensure_file_exists(os.path.join(input_dir, f"sketch{i}.png"))
        ensure_file_exists(os.path.join(input_dir, f"result{i}.png"))

    background = load_rgba(background_path)
    background = fit_image_cover(background, (VIDEO_W, VIDEO_H))

    cards: List[CardPair] = []

    for i, layout in enumerate(CARD_LAYOUTS, start=1):
        sketch_path = os.path.join(input_dir, f"sketch{i}.png")
        result_path = os.path.join(input_dir, f"result{i}.png")

        size = (layout["w"], layout["h"])
        position = (layout["x"], layout["y"])

        sketch = prepare_card_image(sketch_path, size)
        result = prepare_card_image(result_path, size)

        cards.append(
            CardPair(
                sketch=sketch,
                result=result,
                position=position,
                size=size,
            )
        )

    make_frame = make_frame_factory(background, cards, progress_callback=progress_callback)
    video = VideoClip(frame_function=make_frame, duration=TOTAL_DURATION)

    if os.path.exists(music_path):
        audio = AudioFileClip(music_path)

        if audio.duration > TOTAL_DURATION:
            audio = audio.subclipped(0, TOTAL_DURATION)

        video = video.with_audio(audio)

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    video.write_videofile(
        output_path,
        fps=FPS,
        codec=VIDEO_CODEC,
        audio_codec=AUDIO_CODEC,
        bitrate=BITRATE,
        threads=THREADS,
        preset=PRESET,
        logger=None,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a 10-second reels video from 3 sketch/result pairs.")

    parser.add_argument(
        "--input",
        required=True,
        help="Папка с файлами sketch1.png ... sketch3.png и result1.png ... result3.png",
    )
    parser.add_argument(
        "--background",
        default="assets/background.png",
        help="Путь к background.png",
    )
    parser.add_argument(
        "--music",
        default="assets/music.mp3",
        help="Путь к music.mp3",
    )
    parser.add_argument(
        "--output",
        default="output/reels_001.mp4",
        help="Путь к итоговому mp4",
    )

    parser.add_argument(
        "--parallax",
        action=argparse.BooleanOptionalAction,
        default=PARALLAX_ENABLED,
        help="Enable or disable rightward parallax background motion",
    )
    parser.add_argument(
        "--parallax-strength",
        type=float,
        default=max(0.0, min(PARALLAX_STRENGTH / 2.0, 1.0)),
        help="Parallax strength in range 0.0-1.0",
    )
    parser.add_argument(
        "--slow-zoom",
        action=argparse.BooleanOptionalAction,
        default=SLOW_ZOOM_ENABLED,
        help="Enable or disable slow zoom background effect",
    )
    parser.add_argument(
        "--slow-zoom-strength",
        type=float,
        default=max(0.0, min(SLOW_ZOOM_STRENGTH / 2.0, 1.0)),
        help="Slow zoom strength in range 0.0-1.0",
    )
    parser.add_argument(
        "--exposure-pulse",
        action=argparse.BooleanOptionalAction,
        default=EXPOSURE_PULSE_ENABLED,
        help="Enable or disable exposure pulse background effect",
    )
    parser.add_argument(
        "--exposure-pulse-strength",
        type=float,
        default=max(0.0, min(EXPOSURE_PULSE_STRENGTH / 2.0, 1.0)),
        help="Exposure pulse strength in range 0.0-1.0",
    )
    parser.add_argument(
        "--exposure-pulse-speed",
        type=float,
        default=max(0.0, min(EXPOSURE_PULSE_SPEED / 2.0, 1.0)),
        help="Exposure pulse speed in range 0.0-1.0",
    )

    args = parser.parse_args()
    PARALLAX_ENABLED = bool(args.parallax)
    PARALLAX_STRENGTH = max(0.0, min(args.parallax_strength, 1.0)) * 2.0
    SLOW_ZOOM_ENABLED = bool(args.slow_zoom)
    SLOW_ZOOM_STRENGTH = max(0.0, min(args.slow_zoom_strength, 1.0)) * 2.0
    EXPOSURE_PULSE_ENABLED = bool(args.exposure_pulse)
    EXPOSURE_PULSE_STRENGTH = max(0.0, min(args.exposure_pulse_strength, 1.0)) * 2.0
    EXPOSURE_PULSE_SPEED = max(0.0, min(args.exposure_pulse_speed, 1.0)) * 2.0

    build_video(
        input_dir=args.input,
        background_path=args.background,
        music_path=args.music,
        output_path=args.output,
    )
