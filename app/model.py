from ultralytics import YOLO
from huggingface_hub import hf_hub_download
import os

def load_model(hf_token=None):
    try:
        if hf_token:
            path = hf_hub_download(
                repo_id="cazzz307/yolov8-crack-detection",
                filename="best.pt",
                token=hf_token
            )
            return YOLO(path)
    except:
        pass

    if os.path.exists("models/best.pt"):
        return YOLO("models/best.pt")

    return YOLO("yolov8n.pt")