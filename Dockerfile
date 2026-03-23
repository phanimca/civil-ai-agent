FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app
ARG REQUIREMENTS_FILE=requirements.txt

# Minimal system libs often required by Pillow/OpenCV headless wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-gcloud.txt ./
RUN pip install --upgrade pip \
    && pip install -r ${REQUIREMENTS_FILE}

COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "app/main.py", "--server.port=8080", "--server.address=0.0.0.0"]
