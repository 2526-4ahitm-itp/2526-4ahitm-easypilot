"""Train the YOLO pose model (gate box + 4 opening corners) on the self-labelled dataset.

  python -m autopilot.train_detector [epochs]
Result: autopilot/models/gates.pt
"""
import shutil
import sys
from pathlib import Path

from .dataset import DATA

MODELS = Path(__file__).resolve().parent / "models"


def main(argv):
    from ultralytics import YOLO
    epochs = int(argv[0]) if argv else 60
    model = YOLO("yolov8n-pose.pt")
    res = model.train(data=str(DATA / "gates.yaml"), epochs=epochs, imgsz=640, batch=32, device=0,
                      project=str(DATA / "train"), name="gates", exist_ok=True, fliplr=0.5,
                      mosaic=1.0, hsv_v=0.3, degrees=10.0, workers=4, verbose=False)
    MODELS.mkdir(exist_ok=True)
    best = Path(res.save_dir) / "weights" / "best.pt"
    shutil.copy2(best, MODELS / "gates.pt")
    print("saved", MODELS / "gates.pt")


if __name__ == "__main__":
    main(sys.argv[1:])
