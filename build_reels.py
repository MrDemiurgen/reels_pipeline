import os
import argparse
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageOps, ImageDraw
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

PRESET = "slow"          # баланс скорости кодирования и качества
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
REVEAL_DURATION = 8.0     # длительность анимации "проявления" превью

# =========================
# CARD VISUAL SETTINGS
# =========================

CARD_SCALE = 0.78   # ширина карточки относительно ширины видео (0.78 = 78%)
CARD_RADIUS = 36    # радиус скругления углов карточек
CARD_GAP = 50       # расстояние между карточками по вертикали

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
    img = fit_image_cover(img, size)
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


def make_frame_factory(background: Image.Image, cards: List[CardPair], progress_callback=None):
    bg_np = np.array(background.convert("RGBA"))

    total_frames = max(1, int(TOTAL_DURATION * FPS))
    last_reported_frame = {"value": 0}

    def make_frame(t: float):
        progress = get_progress(t)

        current_frame = min(total_frames, int(t * FPS) + 1)

        if progress_callback and current_frame > last_reported_frame["value"]:
            last_reported_frame["value"] = current_frame
            percent = int((current_frame / total_frames) * 100)
            progress_callback(percent)

        canvas = Image.fromarray(bg_np.copy())

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

    args = parser.parse_args()

    build_video(
        input_dir=args.input,
        background_path=args.background,
        music_path=args.music,
        output_path=args.output,
    )