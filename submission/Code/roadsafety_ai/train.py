"""
Fine-tune YOLOv8 on custom pothole / road damage data.

Dataset format (YOLO):
  data.yaml  ← class names + train/val paths
  images/train/*.jpg
  labels/train/*.txt   ← one line per object: class_id cx cy w h (normalized)

Example data.yaml:
  path: /absolute/path/to/dataset
  train: images/train
  val:   images/val
  names:
    0: pothole
    1: road_crack
    2: debris
    3: flooding

Usage:
  python train.py --data data.yaml --epochs 100 --device cpu
  python train.py --data data.yaml --epochs 100 --device 0   # GPU
"""
import argparse
from pathlib import Path
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="Fine-tune YOLOv8 for road hazards")
    parser.add_argument("--data",    required=True,            help="Path to data.yaml")
    parser.add_argument("--base",    default="yolov8n.pt",     help="Base YOLOv8 weights")
    parser.add_argument("--epochs",  type=int, default=100)
    parser.add_argument("--imgsz",   type=int, default=640)
    parser.add_argument("--batch",   type=int, default=16)
    parser.add_argument("--device",  default="cpu",            help="cpu | 0 | 0,1")
    parser.add_argument("--name",    default="pothole_model",  help="Run name (saved under runs/detect/)")
    parser.add_argument("--output",  default="models/pothole.pt", help="Copy best.pt here after training")
    args = parser.parse_args()

    if not Path(args.data).exists():
        raise FileNotFoundError(f"data.yaml not found: {args.data}")

    model = YOLO(args.base)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        name=args.name,
        patience=20,
        save=True,
    )

    # Copy best weights to models/ for immediate use by main.py
    best = Path(f"runs/detect/{args.name}/weights/best.pt")
    if best.exists():
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(best, out)
        print(f"\nBest weights copied to {out}")
        print("Restart main.py — it will auto-load models/pothole.pt")
    else:
        print(f"\nTraining done. Weights at: runs/detect/{args.name}/weights/best.pt")


if __name__ == "__main__":
    main()
