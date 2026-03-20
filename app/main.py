import os
import tempfile
import streamlit as st
import numpy as np
from PIL import Image
from dotenv import load_dotenv

from ultralytics import YOLO
from huggingface_hub import hf_hub_download
from openai import OpenAI

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet

# -------------------------------
# 🔐 LOAD ENV (uv + dotenv)
# -------------------------------
load_dotenv()

OPENAI_TOKEN = os.getenv("OPENAI_TOKEN") or st.secrets.get("OPENAI_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN") or st.secrets.get("HF_TOKEN", "")

# -------------------------------
# 🤖 OPENAI CLIENT
# -------------------------------
client = OpenAI(
    api_key=OPENAI_TOKEN,
    base_url="https://models.github.ai/inference"
)

MODEL_NAME = "openai/gpt-4o-mini"

# -------------------------------
# 🧠 MODEL LOADER (SAFE)
# -------------------------------
@st.cache_resource
def load_model():
    try:
        if HF_TOKEN:
            model_path = hf_hub_download(
                repo_id="cazzz307/yolov8-crack-detection",
                filename="best.pt",
                token=HF_TOKEN
            )
            return YOLO(model_path)
    except Exception:
        pass

    if os.path.exists("models/best.pt"):
        return YOLO("models/best.pt")

    return YOLO("yolov8n.pt")

model = load_model()

# -------------------------------
# 📊 SEVERITY CALCULATION
# -------------------------------
def calculate_severity(box, conf, img_shape):
    x1, y1, x2, y2 = box.xyxy[0]

    area = (x2 - x1) * (y2 - y1)
    total = img_shape[0] * img_shape[1]
    ratio = area / total

    if ratio > 0.15 or conf > 0.8:
        return "🔴 High"
    elif ratio > 0.05:
        return "🟡 Medium"
    else:
        return "🟢 Low"

# -------------------------------
# 🧾 AI REPORT GENERATION
# -------------------------------
def generate_ai_report(detections):
    if not detections:
        detections = ["Minor surface anomaly detected"]

    prompt = f"""
You are a civil engineering inspection expert.

Detected issues:
{detections}

Generate a professional report including:
1. Summary
2. Severity Assessment
3. Possible Causes
4. Repair Recommendations
5. Preventive Measures
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI report generation failed: {e}"

# -------------------------------
# 🎨 STYLED REPORT
# -------------------------------
def style_report(text):
    return f"""
    <div style="background:#0f172a;padding:20px;border-radius:10px;color:white">
        <h2 style="color:#38bdf8;">🏗️ AI Inspection Report</h2>
        <pre style="white-space:pre-wrap;font-size:14px;">{text}</pre>
    </div>
    """

# -------------------------------
# 📄 PDF GENERATOR
# -------------------------------
def create_pdf(report, image):
    file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(file.name)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("AI Infrastructure Inspection Report", styles["Title"]))
    content.append(Spacer(1, 12))

    img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
    image.save(img_path)

    content.append(RLImage(img_path, width=400, height=250))
    content.append(Spacer(1, 12))

    for line in report.split("\n"):
        content.append(Paragraph(line, styles["Normal"]))
        content.append(Spacer(1, 8))

    doc.build(content)
    return file.name

# -------------------------------
# 🖥️ UI CONFIG
# -------------------------------
st.set_page_config(page_title="Civil AI Agent", layout="wide")

st.title("🏗️ Civil AI Inspection Agent")

uploaded_files = st.file_uploader(
    "📤 Upload Infrastructure Images",
    type=["jpg", "png", "jpeg"],
    accept_multiple_files=True
)

# -------------------------------
# 🚀 MAIN LOGIC
# -------------------------------
if uploaded_files:
    for file in uploaded_files:
        image = Image.open(file).convert("RGB")
        img_np = np.array(image)

        col1, col2 = st.columns([1, 2])

        # Original image
        with col1:
            st.image(image, caption="Original Image", use_container_width=True)

        # Detection
        with col2:
            results = model(img_np)[0]
            annotated = results.plot()

            st.image(annotated, caption="Detected Cracks")

            st.subheader("📊 Crack Analysis")

            detections = []

            if len(results.boxes) == 0:
                st.warning("No cracks detected")
            else:
                for box in results.boxes:
                    conf = float(box.conf[0])
                    severity = calculate_severity(box, conf, img_np.shape)

                    text = f"Crack | Confidence: {conf:.2f} | Severity: {severity}"
                    detections.append(text)

                    st.write(text)

            # Metrics
            total = len(results.boxes)
            high = sum(
                1 for box in results.boxes
                if calculate_severity(box, float(box.conf[0]), img_np.shape).startswith("🔴")
            )

            colA, colB = st.columns(2)
            colA.metric("Total Cracks", total)
            colB.metric("High Severity", high)

            # AI Report
            st.subheader("📄 AI Generated Report")

            with st.spinner("Generating report..."):
                report = generate_ai_report(detections)

            st.markdown(style_report(report), unsafe_allow_html=True)

            # PDF Download
            pdf_file = create_pdf(report, image)

            with open(pdf_file, "rb") as f:
                st.download_button(
                    "📥 Download Report (PDF)",
                    f,
                    file_name="inspection_report.pdf"
                )

        st.divider()

else:
    st.info("Upload one or more images to begin inspection.")

# -------------------------------
# FOOTER
# -------------------------------
st.caption("🚀 YOLO + GenAI | Modern Civil AI Platform (uv-powered)")