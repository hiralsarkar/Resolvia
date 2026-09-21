"""
render_scanned_images.py

Renders a subset of the generated broker_confirms/*.txt documents as
actual scanned-style images (not text pretending to be a scan), so the
OCR step has genuine image input to process. Adds realistic noise:
slight rotation, paper-texture speckle, and JPEG compression artifacts.

The original .txt content IS the OCR ground truth (per schema.md) -
no separate mapping needed, just match doc_id -> filename.

Output: scanned_images/doc_XXXX.jpg
"""

import os
import random
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter

random.seed(11)

FONT_PATH = r"C:\Windows\Fonts\consola.ttf"
FONT_SIZE = 18
PAGE_SIZE = (1000, 1300)
MARGIN = 60


def render_text_to_image(text, font):
    img = Image.new("L", PAGE_SIZE, color=250)
    draw = ImageDraw.Draw(img)
    y = MARGIN
    for line in text.splitlines():
        draw.text((MARGIN, y), line, font=font, fill=20)
        y += FONT_SIZE + 8
    return img


def add_paper_texture(img):
    """Light speckle noise to mimic paper grain / scan artifacts."""
    noise = Image.effect_noise(img.size, 18).convert("L")
    return Image.blend(img.convert("L"), noise, alpha=0.04)


def add_scan_artifacts(img):
    img = img.rotate(random.uniform(-1.2, 1.2), fillcolor=250, expand=False)
    img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 0.6)))
    return img


def to_jpeg_with_compression(img, path, quality=None):
    quality = quality or random.randint(45, 70)
    img.convert("RGB").save(path, "JPEG", quality=quality)


def main(src_dir="broker_confirms", out_dir="scanned_images", n=30):
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    all_docs = sorted(f for f in os.listdir(src_dir) if f.endswith(".txt"))
    sample = random.sample(all_docs, min(n, len(all_docs)))

    os.makedirs(out_dir, exist_ok=True)
    for fname in sample:
        with open(os.path.join(src_dir, fname), encoding="utf-8") as f:
            text = f.read()

        img = render_text_to_image(text, font)
        img = add_paper_texture(img)
        img = add_scan_artifacts(img)

        doc_id = fname.replace(".txt", "")
        out_path = os.path.join(out_dir, f"{doc_id}.jpg")
        to_jpeg_with_compression(img, out_path)

    print(f"Rendered {len(sample)} scanned-style images to ./{out_dir}/")
    print("Ground truth for each is the matching broker_confirms/<doc_id>.txt "
          "(same doc_id, and broker_confirms_mapping.csv has the structured fields).")


if __name__ == "__main__":
    main()
