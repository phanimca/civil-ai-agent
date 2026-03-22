from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from openai import OpenAI
from PIL import Image

from ai_report import generate_report_with_usage
from data.repository import SQLiteRepository
from pdf import create_pdf
from severity import calculate_severity


@dataclass
class InspectionRunResult:
    image_name: str
    detections: list[str]
    total_cracks: int
    high_severity: int
    report: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    approx_cost_inr: float
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
        self.usd_to_inr = float(os.getenv("USD_TO_INR_RATE", "83"))
        # Default rates align with GPT-4o-mini style pricing; override via env if needed.
        self.input_cost_per_1k_usd = float(os.getenv("LLM_INPUT_COST_PER_1K_USD", "0.00015"))
        self.output_cost_per_1k_usd = float(os.getenv("LLM_OUTPUT_COST_PER_1K_USD", "0.00060"))

    def estimate_cost_inr(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_usd = (max(prompt_tokens, 0) / 1000.0) * self.input_cost_per_1k_usd
        output_usd = (max(completion_tokens, 0) / 1000.0) * self.output_cost_per_1k_usd
        return round((input_usd + output_usd) * self.usd_to_inr, 6)

    def load_detection_model(self):
        try:
            # Import lazily so the app can boot even if cv2/ultralytics is unavailable.
            from model import load_model
        except Exception as exc:
            raise RuntimeError(
                "Model dependencies failed to import. Install compatible ultralytics/opencv packages."
            ) from exc

        try:
            return load_model(self.hf_token)
        except Exception as exc:
            raise RuntimeError(
                "Unable to load crack-detection model. Check runtime Python version and OpenCV wheel support."
            ) from exc

    def has_detection_stack(self) -> tuple[bool, str | None]:
        try:
            from model import load_model  # noqa: F401
            return True, None
        except Exception as exc:
            return False, str(exc)

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

    def generate_ai_report(self, detections: list[str]) -> tuple[str, int, int, int, float]:
        if not detections:
            detections = ["Minor surface anomaly detected"]

        try:
            client = OpenAI(api_key=self.openai_token, base_url="https://models.github.ai/inference")
            report, prompt_tokens, completion_tokens, total_tokens = generate_report_with_usage(
                client, self.model_name, detections
            )
            approx_cost_inr = self.estimate_cost_inr(prompt_tokens, completion_tokens)
            return report, prompt_tokens, completion_tokens, total_tokens, approx_cost_inr
        except Exception as exc:
            return f"AI report generation failed: {exc}", 0, 0, 0, 0.0

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
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        approx_cost_inr: float,
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
        self.repository.log_inspection(
            user_id,
            uploaded_file_name,
            image_path,
            final_pdf,
            total_cracks,
            high_severity,
            report,
            llm_prompt_tokens=prompt_tokens,
            llm_completion_tokens=completion_tokens,
            llm_total_tokens=total_tokens,
            llm_cost_inr=approx_cost_inr,
        )
        self.repository.log_llm_usage(user_id=user_id, llm_name=self.model_name, tokens_used=total_tokens)
        return image_path, final_pdf
