"""Train the YOLO pose model (gate box + 4 opening corners) on the self-labelled dataset.

  python -m autopilot.train_detector [epochs] [--fresh]
Result: autopilot/models/gates.pt. If a model exists, training continues from it (fine-tuning);
--fresh starts from the generic yolov8n-pose weights. Afterwards the model is evaluated on the
test split (environments held out with `dataset label --holdout ...`): models/gates_eval.json.
"""
import os
import shutil
import sys
from pathlib import Path

from .dataset import DATA

MODELS = Path(__file__).resolve().parent / "models"


def main(argv):
    from ultralytics import YOLO
    fresh = "--fresh" in argv
    argv = [a for a in argv if not a.startswith("--")]
    epochs = int(argv[0]) if argv else 60
    start = MODELS / "gates.pt"
    model = YOLO(str(start) if start.exists() and not fresh else "yolov8n-pose.pt")
    if start.exists():
        shutil.copy2(start, MODELS / "gates-previous.pt")
    res = model.train(data=str(DATA / "gates.yaml"), epochs=epochs, imgsz=640, batch=32, device=0,
                      project=str(DATA / "train"), name="gates", exist_ok=True, fliplr=0.5,
                      mosaic=1.0, hsv_v=0.3, degrees=10.0, verbose=False,
                      # 4 loader processes died on Windows when validation started (16.11.)
                      workers=int(os.environ.get("EASYPILOT_WORKERS", "2")))
    MODELS.mkdir(exist_ok=True)
    best = Path(res.save_dir) / "weights" / "best.pt"
    shutil.copy2(best, MODELS / "gates.pt")
    print("saved", MODELS / "gates.pt")
    evaluate()


def evaluate():
    """Box and corner mAP on val (known maps) and test (held-out environments)."""
    import json
    from ultralytics import YOLO
    model = YOLO(str(MODELS / "gates.pt"))
    out = {}
    for split in ("val", "test"):
        if not any((DATA / "images" / split).glob("*.jpg")):
            continue
        m = model.val(data=str(DATA / "gates.yaml"), split=split, imgsz=640, batch=32, device=0, verbose=False,
                      project=str(DATA / "train"), name=f"eval-{split}", exist_ok=True)
        out[split] = {"box_map50": round(float(m.box.map50), 3), "pose_map50": round(float(m.pose.map50), 3),
                      "precision": round(float(m.box.mp), 3), "recall": round(float(m.box.mr), 3),
                      "images": len(list((DATA / "images" / split).glob("*.jpg")))}
        print(split, out[split])
    (MODELS / "gates_eval.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    if sys.argv[1:] == ["eval"]:
        evaluate()
    else:
        main(sys.argv[1:])
