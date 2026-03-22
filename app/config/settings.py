from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class AppSettings:
    openai_token: str
    hf_token: str
    resend_api_key: str
    email_from: str
    admin_seed_email: str
    brevo_api_key: str
    brevo_from_email: str
    brevo_from_name: str
    db_path: str
    upload_dir: str
    report_dir: str
    project_root: str
    header_logo_path: str
    model_name: str
    code_exp_minutes: int
    session_hours: int
    request_cooldown_seconds: int
    demo_carousel_images: list[tuple[str, str]]



def _secret_or_env(name: str, default: str = "") -> str:
    env_value = os.getenv(name)
    if env_value:
        return env_value

    try:
        return st.secrets.get(name, default)
    except StreamlitSecretNotFoundError:
        return default



def load_settings() -> AppSettings:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(project_root)

    return AppSettings(
        openai_token=_secret_or_env("OPENAI_TOKEN"),
        hf_token=_secret_or_env("HF_TOKEN"),
        resend_api_key=_secret_or_env("RESEND_API_KEY"),
        email_from=_secret_or_env("EMAIL_FROM", "onboarding@resend.dev"),
        admin_seed_email=_secret_or_env("ADMIN_SEED_EMAIL").strip().lower(),
        brevo_api_key=_secret_or_env("BREVO_API_KEY"),
        brevo_from_email=_secret_or_env("BREVO_FROM_EMAIL", _secret_or_env("EMAIL_FROM", "onboarding@resend.dev")),
        brevo_from_name=_secret_or_env("BREVO_FROM_NAME", "Civil-AI-Agent"),
        db_path=os.path.join("app_data", "civil_ai.db"),
        upload_dir=os.path.join("app_data", "uploads"),
        report_dir=os.path.join("app_data", "reports"),
        project_root=project_root,
        header_logo_path=os.path.join(project_root, "images", "header_logo_Oxford.jpg"),
        model_name="openai/gpt-4o-mini",
        code_exp_minutes=10,
        session_hours=24,
        request_cooldown_seconds=30,
        demo_carousel_images=[
            ("Bridge inspection", os.path.join(project_root, "samples", "bridge1.jpg")),
            ("Road surface crack", os.path.join(project_root, "samples", "road1.jpg")),
            ("Concrete defect view", os.path.join(project_root, "samples", "v2-crack1.jpg")),
            ("Bridge structure crack", os.path.join(project_root, "samples", "bridge4.jpg")),
        ],
    )
