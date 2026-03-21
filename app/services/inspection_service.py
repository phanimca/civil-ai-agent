from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from openai import OpenAI
from PIL import Image

from ai_report import generate_report
from data.repository import SQLiteRepository
from model import load_model
from pdf import create_pdf
from severity import calculate_severity


@dataclass
class InspectionRunResult:
    image_name: str
    detections: list[str]
    total_cracks: int
    high_severity: int
    report: str
    final_pdf_path: str


class InspectionService:
    def __init__(
        self,
        repository: SQLiteRepository,
        upload_dir: str,
        report_dir: str,
        openai_token: str,
        model_name: str,
        hf_token: str,
    ) -> None:
        self.repository = repository
        self.upload_dir = upload_dir
        self.report_dir = report_dir
        self.openai_token = openai_token
        self.model_name = model_name
        self.hf_token = hf_token

    def load_detection_model(self):
        return load_model(self.hf_token)

    def run_detection(self, model, image_np: np.ndarray):
        return model(image_np)[0]

    def build_detection_lines(self, boxes, img_shape) -> list[str]:
        lines = []
        for box in boxes:
            conf = float(box.conf[0])
            severity = calculate_severity(box, conf, img_shape)
            lines.append(f"Crack | Confidence: {conf:.2f} | Severity: {severity}")
        return lines

    def summarize_counts(self, boxes, img_shape) -> tuple[int, int]:
        total = len(boxes)
        high = sum(
            1
            for box in boxes
            if calculate_severity(box, float(box.conf[0]), img_shape).lower().startswith("high")
        )
        return total, high

    def generate_ai_report(self, detections: list[str]) -> str:
        if not detections:
            detections = ["Minor surface anomaly detected"]

        try:
            client = OpenAI(api_key=self.openai_token, base_url="https://models.github.ai/inference")
            return generate_report(client, self.model_name, detections)
        except Exception as exc:
            return f"AI report generation failed: {exc}"

    def save_user_files(self, user_id: int, uploaded_file_name: str, image: Image.Image, temp_pdf_path: str) -> tuple[str, str]:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = f"{ts}_{uploaded_file_name}"
        user_upload_dir = os.path.join(self.upload_dir, str(user_id))
        user_report_dir = os.path.join(self.report_dir, str(user_id))
        os.makedirs(user_upload_dir, exist_ok=True)
        os.makedirs(user_report_dir, exist_ok=True)

        image_path = os.path.join(user_upload_dir, safe_name)
        image.save(image_path)

        pdf_name = f"{ts}_{os.path.splitext(uploaded_file_name)[0]}.pdf"
        pdf_path = os.path.join(user_report_dir, pdf_name)
        shutil.copyfile(temp_pdf_path, pdf_path)
        return image_path, pdf_path

    def create_and_persist_report(
        self,
        user_id: int,
        uploaded_file_name: str,
        image: Image.Image,
        total_cracks: int,
        high_severity: int,
        report: str,
    ) -> tuple[str, str]:
        pdf_file = create_pdf(
            report,
            image,
            summary={
                "image_name": uploaded_file_name,
                "total_cracks": total_cracks,
                "high_severity": high_severity,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        image_path, final_pdf = self.save_user_files(user_id, uploaded_file_name, image, pdf_file)
        self.repository.log_inspection(user_id, uploaded_file_name, image_path, final_pdf, total_cracks, high_severity, report)
        return image_path, final_pdf
