#!/usr/bin/env python3
"""Read-only print preflight for one PDF page. Never changes source files."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

from PIL import Image


def run_tool(args):
    env = dict(os.environ, LC_ALL="C")
    result = subprocess.run(args, capture_output=True, timeout=20, env=env)
    if result.returncode:
        raise ValueError(f"{args[0]} could not read the requested PDF page")
    return result.stdout


def parse_images(output):
    images = []
    for line in output.splitlines():
        fields = line.split()
        if not fields or fields[0] in {"page", "---"} or set(fields[0]) == {"-"}:
            continue
        if len(fields) < 16:
            raise ValueError("Unrecognized pdfimages output; refusing to infer resolution")
        try:
            row = {
                "page": int(fields[0]), "image_number": int(fields[1]),
                "kind": fields[2], "width_px": int(fields[3]),
                "height_px": int(fields[4]), "color": fields[5],
                "x_ppi": float(fields[12]), "y_ppi": float(fields[13]),
            }
        except (ValueError, IndexError) as exc:
            raise ValueError("Unrecognized pdfimages numeric fields") from exc
        row["below_150_ppi"] = min(row["x_ppi"], row["y_ppi"]) < 150
        images.append(row)
    return images


def edge_statistics(image):
    gray = image.convert("L")
    width, height = gray.size
    if width < 2 or height < 2:
        raise ValueError("Page rendering is too small")
    pixels = gray.load()
    # Sample the outside border. A border/background finding needs human review.
    xs = range(0, width, max(1, width // 256))
    ys = range(0, height, max(1, height // 256))
    values = [pixels[x, y] for x in xs for y in (0, height - 1)]
    values += [pixels[x, y] for y in ys for x in (0, width - 1)]
    median = statistics.median(values)
    white_ratio = sum(v >= 250 for v in values) / len(values)
    return {
        "edge_median_luminance_0_to_255": median,
        "edge_white_pixel_ratio": round(white_ratio, 4),
        "possible_gray_background": median < 245 and white_ratio < 0.5,
        "basis": "Outer border of a bounded page render; artwork/borders can trigger this flag.",
    }


def inspect_pdf(path, page=1):
    source = Path(path).resolve(strict=True)
    if not source.is_file() or source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Use a regular PDF file no larger than 32 MiB")
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("Page must be a positive integer")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    info = run_tool(["pdfinfo", str(source)]).decode("utf-8", "replace")
    pages = next((int(line.split(":", 1)[1]) for line in info.splitlines()
                  if line.startswith("Pages:")), None)
    if pages is None or page > pages:
        raise ValueError("Requested page is outside the PDF")
    images = parse_images(run_tool([
        "pdfimages", "-f", str(page), "-l", str(page), "-list", str(source)
    ]).decode("utf-8", "replace"))
    rendered = run_tool([
        "pdftoppm", "-f", str(page), "-l", str(page), "-singlefile",
        "-r", "150", "-scale-to", "1536", "-png", str(source)
    ])
    with Image.open(io.BytesIO(rendered)) as image:
        edges = edge_statistics(image)
        render_size = list(image.size)
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    if before != after:
        raise ValueError("Source changed while being inspected")
    return {
        "schema_version": 1, "page": page, "total_pages": pages,
        "source_sha256": before, "source_unchanged": True,
        "embedded_images": images, "render_size_px": render_size,
        "background_check": edges, "human_review_required": True,
        "limitations": [
            "This is a diagnostic, not a repaired PDF or a guarantee of sharp printing.",
            "Low PPI may refer to a small logo rather than the page text.",
            "Increasing export DPI cannot recover detail absent from the original scan.",
            "Vector-text blur, printer settings and interior-only backgrounds are not diagnosed.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf")
    parser.add_argument("--page", type=int, default=1)
    args = parser.parse_args()
    try:
        report = inspect_pdf(args.pdf, args.page)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc), "repair_performed": False}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
