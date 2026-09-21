"""
verify_ocr.py

Runs EasyOCR (frozen/pretrained, no LLM call needed) against every
scanned_images/*.jpg and checks the extracted text against the known
ground truth (the matching broker_confirms/<doc_id>.txt, per schema.md -
the .txt IS the ground truth, same doc_id). Doesn't call any LLM
(no key needed) - just verifies the OCR layer in isolation.
"""

import os
import re
import easyocr

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")


def key_tokens(text):
    """Trade IDs, symbols, quantities - the fields that matter for
    downstream extraction, not prose. Case/whitespace-insensitive."""
    return set(re.findall(r"TRD\d+|[A-Z]{2,}\d*|\b\d{2,}\b", text.upper()))


def main():
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    scanned_dir = os.path.join(DATA_DIR, "scanned_images")
    confirms_dir = os.path.join(DATA_DIR, "broker_confirms")

    results = []
    for fname in sorted(os.listdir(scanned_dir)):
        doc_id = fname.replace(".jpg", "")
        gt_path = os.path.join(confirms_dir, f"{doc_id}.txt")
        if not os.path.exists(gt_path):
            print(f"{doc_id}: no ground truth found, skipping")
            continue

        with open(gt_path, encoding="utf-8") as f:
            ground_truth = f.read()

        lines = reader.readtext(os.path.join(scanned_dir, fname), detail=0)
        ocr_text = "\n".join(lines)

        gt_tokens = key_tokens(ground_truth)
        ocr_tokens = key_tokens(ocr_text)
        recovered = gt_tokens & ocr_tokens
        rate = len(recovered) / len(gt_tokens) if gt_tokens else 0.0
        results.append(rate)
        missed = gt_tokens - ocr_tokens
        print(f"{doc_id}: {len(recovered)}/{len(gt_tokens)} key tokens recovered "
              f"({rate:.0%}){' missed: ' + str(missed) if missed else ''}")

    if results:
        print(f"\nMean key-token recovery across {len(results)} scanned docs: "
              f"{sum(results)/len(results):.0%}")


if __name__ == "__main__":
    main()
