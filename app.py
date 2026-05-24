"""Local YOLO annotation review tool.

Run:
    python app.py <images_dir> [labels_dir]
    # then open http://127.0.0.1:5000

If labels_dir is omitted, the images folder is also used for labels.
Writes go to labels_dir (creates .txt files there as needed).
"""
import argparse
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
BOOKMARK_FILE = ".bookmark"

app = Flask(__name__)
images_dir: Path = Path()
labels_dir: Path = Path()


def list_images() -> list[str]:
    return sorted(p.name for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def label_path(image_name: str) -> Path:
    return labels_dir / (Path(image_name).stem + ".txt")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/browse")
def browse():
    return render_template("browse.html")


@app.route("/api/images")
def api_images():
    return jsonify(list_images())


@app.route("/api/image/<path:name>", methods=["GET", "DELETE"])
def api_image(name):
    if name not in list_images():
        abort(404)
    if request.method == "DELETE":
        (images_dir / name).unlink(missing_ok=True)
        label_path(name).unlink(missing_ok=True)
        # If the bookmark pointed to this image, clear it so the next
        # session starts cleanly rather than failing to find a stale ref.
        bm = labels_dir / BOOKMARK_FILE
        if bm.exists() and bm.read_text(encoding="utf-8").strip() == name:
            bm.unlink()
        return jsonify({"ok": True, "deleted": name})
    return send_from_directory(images_dir, name)


@app.route("/api/annotations/<path:name>", methods=["GET", "POST"])
def api_annotations(name):
    lp = label_path(name)
    if request.method == "GET":
        boxes = []
        if lp.exists():
            for line in lp.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                # Accept 5-col YOLO (gt) or 6-col YOLO-with-confidence (predictions).
                if len(parts) not in (5, 6):
                    continue
                c, x, y, w, h = parts[:5]
                box = {
                    "class_id": int(c),
                    "x": float(x), "y": float(y),
                    "w": float(w), "h": float(h),
                }
                if len(parts) == 6:
                    box["score"] = float(parts[5])
                boxes.append(box)
        return jsonify(boxes)

    boxes = request.get_json() or []
    lines = [
        f"{int(b['class_id'])} {b['x']:.6f} {b['y']:.6f} {b['w']:.6f} {b['h']:.6f}"
        for b in boxes
    ]
    lp.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    return jsonify({"ok": True, "count": len(lines)})


@app.route("/api/bookmark", methods=["GET", "POST"])
def api_bookmark():
    p = labels_dir / BOOKMARK_FILE
    if request.method == "GET":
        name = p.read_text(encoding="utf-8").strip() if p.exists() else ""
        return jsonify({"image": name or None})
    name = ((request.get_json() or {}).get("image") or "").strip()
    if name:
        p.write_text(name, encoding="utf-8")
    else:
        p.unlink(missing_ok=True)
    return jsonify({"ok": True})


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("images", nargs="?", default="images",
                        help="folder containing source images (default: ./images)")
    parser.add_argument("labels", nargs="?", default="labels",
                        help="folder containing YOLO .txt label files; writes go here "
                             "(default: ./labels)")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    global images_dir, labels_dir
    images_dir = Path(args.images).resolve()
    labels_dir = Path(args.labels).resolve()
    if not images_dir.is_dir():
        raise SystemExit(f"Not a directory: {images_dir}")
    if not labels_dir.is_dir():
        raise SystemExit(f"Not a directory: {labels_dir}")
    print(f"Images: {images_dir}")
    print(f"Labels: {labels_dir}")
    print(f"  {len(list_images())} images")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
