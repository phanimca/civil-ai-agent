from __future__ import annotations

import csv
import io
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image
import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards  # pyright: ignore[reportMissingImports]
from streamlit_extras.stylable_container import stylable_container  # pyright: ignore[reportMissingImports]

from config.settings import AppSettings
from data.repository import SQLiteRepository
from services.auth_service import AuthService
from services.email_service import EmailService
from services.inspection_service import InspectionService


class CivilAIStreamlitApp:
    def __init__(
        self,
        settings: AppSettings,
        repository: SQLiteRepository,
        auth_service: AuthService,
        email_service: EmailService,
        inspection_service: InspectionService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.auth_service = auth_service
        self.email_service = email_service
        self.inspection_service = inspection_service

    def _render_demo_carousel(self, demo_images: list[tuple[str, str]]) -> None:
        slides = [(title, file_path) for title, file_path in demo_images if os.path.exists(file_path)]
        if not slides:
            st.info("No demo images found.")
            return

        carousel_key = "demo_carousel_index"
        current_index = int(st.session_state.get(carousel_key, 0))
        total = len(slides)
        if current_index < 0 or current_index >= total:
            current_index = 0
            st.session_state[carousel_key] = 0

        title, file_path = slides[current_index]

        # Render a shorter, wider visual by center-cropping to a panoramic ratio.
        frame = Image.open(file_path).convert("RGB")
        width, height = frame.size
        target_ratio = 2.35
        current_ratio = width / max(1, height)
        if current_ratio < target_ratio:
            crop_h = int(width / target_ratio)
            top = max(0, (height - crop_h) // 2)
            frame = frame.crop((0, top, width, top + crop_h))
        else:
            crop_w = int(height * target_ratio)
            left = max(0, (width - crop_w) // 2)
            frame = frame.crop((left, 0, left + crop_w, height))

        st.image(frame, width="stretch")
        st.markdown(f"**{title}**")
        st.caption(f"Sample inspection scene: {title}.")

        if total > 1 and not st.session_state.get("show_auth_dialog", False):
            now = time.time()
            last_advance_at = float(st.session_state.get("demo_carousel_last_advance_at", now))
            interval_seconds = float(st.session_state.get("demo_carousel_interval_seconds", 3.0))
            if now - last_advance_at >= interval_seconds:
                st.session_state[carousel_key] = (current_index + 1) % total
                st.session_state["demo_carousel_last_advance_at"] = now
                st.rerun()

    @st.cache_resource
    def _get_model(_self, hf_token: str):
        return _self.inspection_service.load_detection_model()

    @staticmethod
    def _style_report(text: str) -> str:
        return f"""
        <div style=\"background:#f8fafc;padding:20px 22px;border-radius:12px;border:1px solid #e2e8f0;color:#0f172a;line-height:1.6;\">
            <h2 style=\"margin:0 0 10px 0;color:#0369a1;font-size:22px;\">AI Inspection Report</h2>
            <div style=\"font-size:14px;white-space:pre-wrap;font-family:Segoe UI, sans-serif;\">{text}</div>
        </div>
        """

    @staticmethod
    def _bootstrap_session() -> None:
        st.session_state.setdefault("page", "home")
        st.session_state.setdefault("session_token", None)
        st.session_state.setdefault("show_auth_dialog", False)
        st.session_state.setdefault("auth_step", "email")
        st.session_state.setdefault("pending_email", "")
        st.session_state.setdefault("pending_code_expires_at", None)
        st.session_state.setdefault("next_code_request_at", None)
        st.session_state.setdefault("pending_code", "")
        st.session_state.setdefault("verified_user_id", None)
        st.session_state.setdefault("auth_flash_message", None)
        st.session_state.setdefault("auth_flash_target_step", None)
        st.session_state.setdefault("demo_carousel_index", 0)
        st.session_state.setdefault("demo_carousel_last_advance_at", time.time())
        st.session_state.setdefault("demo_carousel_interval_seconds", 3.0)

    @staticmethod
    def _split_name(full_name: str) -> tuple[str, str]:
        parts = (full_name or "").strip().split(None, 1)
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[1]

    def _dismiss_auth_dialog(self) -> None:
        st.session_state["show_auth_dialog"] = False

    def _reset_auth_flow(self, preserve_email: bool = False) -> None:
        st.session_state["auth_step"] = "email"
        st.session_state["pending_code_expires_at"] = None
        st.session_state["next_code_request_at"] = None
        st.session_state["pending_code"] = ""
        st.session_state["verified_user_id"] = None
        st.session_state["auth_flash_message"] = None
        st.session_state["auth_flash_target_step"] = None
        if not preserve_email:
            st.session_state["pending_email"] = ""

    def _open_auth_dialog(self, step: str = "email") -> None:
        st.session_state["show_auth_dialog"] = True
        st.session_state["auth_step"] = step

    def _send_otp(self, email: str) -> bool:
        email_norm = self.auth_service.normalize_email(email)
        validation_errors = self.auth_service.validate_email(email_norm)
        if validation_errors:
            for err in validation_errors:
                st.error(err)
            return False

        existing_user = self.repository.find_user_by_email(email_norm)
        user_id = int(existing_user["id"]) if existing_user else self.repository.ensure_user(email_norm)

        recipient_name = "Student"
        if existing_user:
            recipient_name = (
                (existing_user["first_name"] or "").strip()
                or (existing_user["full_name"] or "").strip()
                or recipient_name
            )

        code = self.auth_service.issue_verification_code(user_id, "login")
        ok, msg = self.email_service.send_verification_email(email_norm, recipient_name, code)
        fallback_code = None

        if ok:
            st.success(msg)
        else:
            st.warning(msg)
            fallback_code = self.email_service.extract_demo_code(msg)
            if fallback_code:
                st.info("Demo fallback active: use this OTP to continue.")
                st.code(fallback_code)
            else:
                return False

        now = datetime.now(timezone.utc)
        st.session_state["pending_email"] = email_norm
        st.session_state["pending_code"] = fallback_code or ""
        st.session_state["pending_code_expires_at"] = (
            now + timedelta(minutes=self.settings.code_exp_minutes)
        ).isoformat()
        st.session_state["next_code_request_at"] = (
            now + timedelta(seconds=self.settings.request_cooldown_seconds)
        ).isoformat()
        st.session_state["auth_step"] = "otp"
        return True

    def _start_auth_transition(self, message: str, next_step: str) -> None:
        st.session_state["auth_flash_message"] = message
        st.session_state["auth_flash_target_step"] = next_step
        st.session_state["auth_step"] = "success"

    def _consume_auth_transition(self) -> None:
        message = st.session_state.get("auth_flash_message")
        next_step = st.session_state.get("auth_flash_target_step")
        if not message or not next_step:
            return

        st.markdown(
            '<div style="text-align:center;padding:30px;border-radius:20px;background:linear-gradient(135deg,#ecfeff,#ffffff);border:1px solid #bae6fd;">'
            '<h2 style="color:#0284c7;">&#x2705; Verified Successfully</h2>'
            f'<p style="color:#0f172a;font-weight:600;">{message}</p>'
            '<p style="color:#475569;">Redirecting to next step...</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.9)
        st.session_state["auth_flash_message"] = None
        st.session_state["auth_flash_target_step"] = None
        st.session_state["auth_step"] = next_step
        st.rerun()

    def _require_authentication(self, user) -> bool:
        if not user:
            st.warning("Please sign in first.")
            st.session_state["page"] = "home"
            self._open_auth_dialog("email")
            st.rerun()

        if not user["registration_completed"]:
            st.warning("Please complete your registration to continue.")
            st.session_state["pending_email"] = user["email"]
            st.session_state["verified_user_id"] = int(user["id"])
            st.session_state["page"] = "home"
            self._open_auth_dialog("register")
            st.rerun()

        return True

    @staticmethod
    def _auth_step_index(step: str) -> int:
        return {"email": 1, "otp": 2, "success": 2, "register": 3}.get(step, 1)

    def _render_auth_stepper(self, step: str) -> None:
        current = {"email": 1, "otp": 2, "success": 2, "register": 3}.get(step, 1)

        steps = [("Email", 1), ("Verify OTP", 2), ("Profile", 3)]

        step_html = ""
        for label, index in steps:
            cls = "step done" if index < current else ("step active" if index == current else "step")
            step_html += f'<div class="{cls}"><div class="circle">{index}</div><div class="label">{label}</div></div>'

        # CSS — keep other auth component classes so _render_auth_note, success card, etc. still work
        css = (
            '<style>'
            '.auth-container{border-radius:20px;padding:24px;background:rgba(255,255,255,0.75);backdrop-filter:blur(14px);border:1px solid #e2e8f0;box-shadow:0 20px 60px rgba(0,0,0,0.08);margin-bottom:20px;}'
            '.auth-title{font-size:26px;font-weight:800;margin-bottom:8px;}'
            '.auth-sub{color:#64748b;font-size:14px;margin-bottom:18px;}'
            '.steps{display:flex;justify-content:space-between;margin-top:10px;}'
            '.step{text-align:center;flex:1;}'
            '.circle{width:36px;height:36px;border-radius:50%;background:#e2e8f0;color:#0f172a;display:flex;align-items:center;justify-content:center;margin:auto;font-weight:700;transition:0.3s;}'
            '.step.active .circle{background:#0ea5e9;color:white;transform:scale(1.1);}'
            '.step.done .circle{background:#22c55e;color:white;}'
            '.label{margin-top:6px;font-size:12px;color:#475569;font-weight:600;}'
            '.auth-side-note{padding:12px 14px;border-radius:16px;border:1px solid #e2e8f0;background:#ffffff;color:#334155;font-size:13px;line-height:1.5;margin-bottom:14px;}'
            '.auth-success-card{text-align:center;border:1px solid #bfdbfe;border-radius:22px;padding:34px 20px;background:linear-gradient(180deg,#f0f9ff 0%,#ffffff 100%);}'
            '.auth-success-badge{display:inline-block;padding:6px 12px;border-radius:999px;background:#0ea5e9;color:#ffffff;font-size:12px;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;}'
            '.auth-success-title{margin:14px 0 8px 0;color:#0f172a;font-size:28px;line-height:1.15;font-weight:800;}'
            '.auth-success-copy{margin:0;color:#475569;font-size:14px;}'
            '</style>'
        )
        html = (
            css
            + '<div class="auth-container">'
            + '<div class="auth-title">&#x1F510; Secure Login</div>'
            + '<div class="auth-sub">Fast OTP-based access for students &amp; engineers</div>'
            + f'<div class="steps">{step_html}</div>'
            + '</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    @staticmethod
    def _render_auth_note(message: str) -> None:
        st.markdown(
            f"<div class=\"auth-side-note\">{message}</div>",
            unsafe_allow_html=True,
        )

    @staticmethod
    def _render_visual_system_styles() -> None:
        st.markdown(
            """
            <style>
                .surface-hero {
                    border: 1px solid #dbe4f0;
                    border-radius: 28px;
                    padding: 30px 28px;
                    background:
                        radial-gradient(circle at top left, rgba(14, 165, 233, 0.16), transparent 34%),
                        radial-gradient(circle at bottom right, rgba(34, 197, 94, 0.12), transparent 32%),
                        linear-gradient(165deg, #ffffff 0%, #f8fbff 56%, #f0fdf4 100%);
                    box-shadow: 0 22px 60px rgba(15, 23, 42, 0.08);
                    margin-bottom: 18px;
                }
                .surface-kicker {
                    display: inline-block;
                    padding: 7px 12px;
                    border-radius: 999px;
                    background: #0f172a;
                    color: #f8fafc;
                    font-size: 12px;
                    font-weight: 700;
                    letter-spacing: 0.05em;
                    text-transform: uppercase;
                }
                .surface-title {
                    margin: 16px 0 8px 0;
                    color: #0f172a;
                    font-size: 38px;
                    line-height: 1.06;
                    font-weight: 800;
                }
                .surface-copy {
                    margin: 0 0 18px 0;
                    color: #334155;
                    font-size: 15px;
                    line-height: 1.7;
                }
                .surface-chip-grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 10px;
                }
                .surface-chip {
                    padding: 12px 14px;
                    border-radius: 18px;
                    border: 1px solid #dbe4f0;
                    background: rgba(255, 255, 255, 0.84);
                    color: #0f172a;
                    font-size: 14px;
                    font-weight: 600;
                }
                .panel-title {
                    margin: 0 0 12px 0;
                    color: #0f172a;
                    font-size: 24px;
                    font-weight: 800;
                }
                .panel-note {
                    color: #64748b;
                    font-size: 13px;
                    margin-top: -6px;
                    margin-bottom: 10px;
                }
                .result-row {
                    display: grid;
                    grid-template-columns: minmax(0, 2.2fr) repeat(3, minmax(0, 1fr));
                    gap: 12px;
                    padding: 14px 16px;
                    border: 1px solid #dbe4f0;
                    border-radius: 18px;
                    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
                    margin-bottom: 12px;
                    align-items: center;
                }
                .result-name {
                    color: #0f172a;
                    font-size: 14px;
                    font-weight: 700;
                    margin-bottom: 4px;
                }
                .result-date {
                    color: #64748b;
                    font-size: 12px;
                }
                .result-label {
                    color: #64748b;
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: 0.04em;
                    margin-bottom: 4px;
                }
                .result-metric {
                    color: #0f172a;
                    font-size: 13px;
                    font-weight: 700;
                }
                .detection-grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 10px;
                    margin-bottom: 14px;
                }
                .detection-card {
                    padding: 12px 14px;
                    border-radius: 18px;
                    border: 1px solid #dbe4f0;
                    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
                    color: #0f172a;
                    font-size: 13px;
                    line-height: 1.55;
                }
                .nav-title {
                    color: #0f172a;
                    font-size: 13px;
                    font-weight: 800;
                    letter-spacing: 0.05em;
                    text-transform: uppercase;
                    margin-bottom: 10px;
                }
                .nav-user {
                    color: #475569;
                    font-size: 13px;
                    margin-top: 10px;
                }
                @media (max-width: 900px) {
                    .surface-title {
                        font-size: 32px;
                    }
                    .surface-chip-grid,
                    .detection-grid {
                        grid-template-columns: 1fr;
                    }
                    .result-row {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def _surface_container(key: str):
        return stylable_container(
            key=key,
            css_styles="""
            {
                border: 1px solid #dbe4f0;
                border-radius: 22px;
                padding: calc(1rem - 1px);
                background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
                box-shadow: 0 14px 36px rgba(15, 23, 42, 0.05);
            }
            """,
        )

    def _render_detection_cards(self, detections: list[str]) -> None:
        self._render_visual_system_styles()
        detection_markup = "".join(f'<div class="detection-card">{line}</div>' for line in detections)
        st.markdown(f'<div class="detection-grid">{detection_markup}</div>', unsafe_allow_html=True)

    def _render_auth_dialog(self) -> None:
        profession_options = ["", "Student", "Faculty Member"]
        python_options = ["", "No", "Beginner", "Advanced", "Expert"]
        ai_tool_options = ["", "No", "EveryDay", "Once In a While"]

        cooldown_left = self.auth_service.seconds_until(st.session_state.get("next_code_request_at"))
        expiry_left = self.auth_service.seconds_until(st.session_state.get("pending_code_expires_at"))

        @st.dialog("Try Civil AI for Free", width="large", dismissible=False, on_dismiss="ignore")
        def auth_dialog() -> None:
            close_col, _ = st.columns([1, 5])
            if close_col.button("Close", key="auth_dialog_close", width="stretch"):
                self._dismiss_auth_dialog()
                self._reset_auth_flow()
                st.rerun()

            st.markdown(
                '<style>'
                '.auth-card{padding:20px;border-radius:18px;background:linear-gradient(135deg,#f0f9ff,#ffffff);border:1px solid #e2e8f0;margin-bottom:16px;}'
                '.auth-highlight{font-size:14px;color:#0369a1;font-weight:600;}'
                '</style>'
                '<div class="auth-card"><div class="auth-highlight">&#x1F680; AI-powered civil inspection demo</div></div>',
                unsafe_allow_html=True,
            )

            step = st.session_state.get("auth_step", "email")
            pending_email = st.session_state.get("pending_email", "")
            self._render_auth_stepper(step)

            if step == "success":
                self._consume_auth_transition()
                return

            if step == "email":
                self._render_auth_note(
                    "We use OTP-based sign-in so you do not need to remember a password for the demo."
                )
                st.markdown("### Get your OTP")
                st.caption("Enter your college or personal email address to continue.")
                if cooldown_left > 0:
                    st.caption(f"You can request a new OTP in {cooldown_left}s.")

                with st.form("send_otp_form"):
                    email = st.text_input(
                        "📧 Email Address",
                        value=pending_email,
                        placeholder="Enter your email",
                        help="We will send a one-time password to this email.",
                    )
                    send_otp = st.form_submit_button(
                        "🚀 Send OTP",
                        type="primary",
                        width="stretch",
                        disabled=cooldown_left > 0,
                    )

                if send_otp and self._send_otp(email):
                    st.rerun()
                return

            if step == "otp":
                self._render_auth_note(
                    "Check your inbox for the latest six-digit OTP. Use Send OTP Again if the previous code expired."
                )
                st.markdown("### Verify your email")
                st.caption(f"OTP sent to {pending_email}")
                if expiry_left > 0:
                    mins = expiry_left // 60
                    secs = expiry_left % 60
                    st.info(f"Current OTP expires in {mins}m {secs}s.")
                if cooldown_left > 0:
                    st.caption(f"You can request a new OTP in {cooldown_left}s.")

                with st.form("verify_otp_form"):
                    st.text_input("Email", value=pending_email, disabled=True)
                    code = st.text_input(
                        "🔢 Enter OTP",
                        value=st.session_state.get("pending_code", ""),
                        placeholder="6-digit code",
                    )
                    verify = st.form_submit_button("✅ Verify OTP", type="primary", width="stretch")

                action_col1, action_col2 = st.columns(2)
                if action_col1.button("Change Email", width="stretch"):
                    self._reset_auth_flow()
                    self._open_auth_dialog("email")
                    st.rerun()

                if action_col2.button(
                    "Send OTP Again",
                    width="stretch",
                    disabled=cooldown_left > 0,
                ):
                    if self._send_otp(pending_email):
                        st.rerun()

                if verify:
                    ok, msg, verified_user = self.auth_service.verify_code(pending_email, code)
                    if not ok:
                        st.error(msg)
                        return

                    if verified_user["registration_completed"]:
                        self._dismiss_auth_dialog()
                        self._reset_auth_flow(preserve_email=True)
                        st.session_state["session_token"] = self.auth_service.create_session_for_user(int(verified_user["id"]))
                        st.session_state["page"] = "landing"
                        st.rerun()

                    st.session_state["verified_user_id"] = int(verified_user["id"])
                    self._start_auth_transition("Email verified. Let us complete your profile.", "register")
                    st.rerun()
                return

            user = self.repository.find_user_by_email(pending_email)
            if not user:
                st.error("We could not find your registration record. Please request a new OTP.")
                self._reset_auth_flow()
                self._open_auth_dialog("email")
                st.rerun()

            first_name, last_name = self._split_name(user["full_name"])
            profession_index = profession_options.index(user["profession"]) if user["profession"] in profession_options else 0
            python_index = python_options.index(user["python_knowledge"]) if user["python_knowledge"] in python_options else 0
            ai_tool_index = ai_tool_options.index(user["ai_tool_usage"]) if user["ai_tool_usage"] in ai_tool_options else 0

            self._render_auth_note(
                "This short profile helps tailor the demo to civil engineering learners and faculty members."
            )
            st.markdown("### Complete your profile")
            st.caption("First-time users only. After this step, you will land on the dashboard.")
            st.caption(f"Verified email: {pending_email}")

            with st.form("registration_form"):
                col1, col2 = st.columns(2)
                first_name_value = col1.text_input("First Name", value=(user["first_name"] or first_name or ""))
                last_name_value = col2.text_input("Last Name", value=(user["last_name"] or last_name or ""))

                mobile = st.text_input("Mobile", value=user["mobile"] or "", placeholder="10 to 15 digits")
                college = st.text_input("College Name", value=user["college"] or "")
                profession = st.selectbox("Profession", options=profession_options, index=profession_index)
                python_knowledge = st.selectbox(
                    "Your knowledge on Python programming",
                    options=python_options,
                    index=python_index,
                )
                ai_tool_usage = st.selectbox(
                    "How often do you use AI tools (e.g ChatGPT, Gemini)",
                    options=ai_tool_options,
                    index=ai_tool_index,
                )
                ai_awareness = st.text_area(
                    "What do you know about AI",
                    value=user["ai_awareness"] or "",
                    placeholder="Share what you know, use, or want to learn about AI in civil engineering.",
                    height=120,
                )
                register = st.form_submit_button("Finish Setup and Open Dashboard", type="primary", width="stretch")

            if register:
                validation_errors = self.auth_service.validate_registration_profile(
                    first_name=first_name_value,
                    last_name=last_name_value,
                    mobile=mobile,
                    college=college,
                    profession=profession,
                    python_knowledge=python_knowledge,
                    ai_tool_usage=ai_tool_usage,
                    ai_awareness=ai_awareness,
                )
                if validation_errors:
                    for err in validation_errors:
                        st.error(err)
                    return

                self.repository.update_user_registration(
                    user_id=int(user["id"]),
                    first_name=first_name_value,
                    last_name=last_name_value,
                    mobile=mobile,
                    college=college,
                    profession=profession,
                    python_knowledge=python_knowledge,
                    ai_tool_usage=ai_tool_usage,
                    ai_awareness=ai_awareness,
                )
                token = self.auth_service.create_session_for_user(int(user["id"]))
                self._dismiss_auth_dialog()
                self._reset_auth_flow(preserve_email=True)
                st.session_state["session_token"] = token
                st.session_state["page"] = "landing"
                st.rerun()

        auth_dialog()

    def _render_header(self) -> None:
        title_col, right_col = st.columns([1.55, 1.0], vertical_alignment="center")

        with title_col:
            if os.path.exists(self.settings.header_logo_path):
                st.image(self.settings.header_logo_path, width=190)
            st.title("Phani's Civil Inspection AI Agent")
            st.markdown(
                '<p style="font-size:12px;color:#64748b;margin-top:-6px;margin-bottom:8px;">'
                "Demo for B.Tech Civil students | Designed by Phani"
                "</p>",
                unsafe_allow_html=True,
            )

        with right_col:
            ai_img_path = os.path.join(self.settings.project_root, "images", "AI_in_Civil_Engineering.png")
            if os.path.exists(ai_img_path):
                st.image(ai_img_path, width="stretch")

        st.divider()

    @staticmethod
    def _render_footer() -> None:
        st.divider()
        st.caption("Civil-AI-Agent Demo | Built with GenAI")

    def _render_home(self) -> None:
        left_col, right_col = st.columns([1.05, 1.35], vertical_alignment="center")

        with left_col:
            self._render_page_intro(
                kicker="Civil Inspection Demo",
                title="Upload a crack image. Get a structured AI inspection report.",
                copy="Built for civil engineering students and faculty, this demo detects cracks, estimates severity, and prepares report-ready output from infrastructure images.",
                chips=[
                    "AI crack detection",
                    "Severity scoring",
                    "Narrative inspection summary",
                    "Export-ready documentation",
                ],
            )
            st.markdown("### Start the demo")
            st.caption("Use the free trial flow to access the dashboard, inspect images, and download reports.")

        with right_col:
            if st.button("Try for Free", type="primary", width="stretch"):
                self._reset_auth_flow()
                self._open_auth_dialog("email")
                st.rerun()
            with self._surface_container("home_carousel_panel"):
                self._render_demo_carousel(self.settings.demo_carousel_images)

    def _render_auth(self) -> None:
        st.info("Use the Try for Free button on the home page to sign in.")
        self._reset_auth_flow()
        self._open_auth_dialog("email")

    def _render_landing(self, user) -> None:
        rows = self.repository.recent_inspections(user["id"], limit=5)
        total_recent_cracks = sum(row["total_cracks"] for row in rows)
        total_recent_high = sum(row["high_severity"] for row in rows)
        first_name = (user["first_name"] or "").strip() if "first_name" in user.keys() else ""
        display_name = first_name or user["full_name"] or "Engineer"

        self._render_page_intro(
            kicker="Dashboard",
            title=f"Welcome back, {display_name}.",
            copy="Your inspection workspace is ready. Review recent activity, track crack severity, and jump back into image analysis from here.",
            chips=[
                "AI crack detection from uploaded site images",
                "Severity analytics for quick triage",
                "Narrative inspection reports for documentation",
                "PDF exports for submission and review",
            ],
        )

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        metric_col1.metric("Role", user["role"].title())
        metric_col2.metric("Verified", "Yes" if user["is_verified"] else "No")
        metric_col3.metric("Recent Inspections", len(rows))
        metric_col4.metric("High Severity Flags", total_recent_high)
        style_metric_cards(border_left_color="#0ea5e9", border_color="#dbe4f0", border_radius_px=16)

        insight_col, activity_col = st.columns([1.05, 1.45], vertical_alignment="top")

        with insight_col:
            with self._surface_container("dashboard_snapshot"):
                st.markdown('<div class="panel-title">Workspace Snapshot</div>', unsafe_allow_html=True)
                st.write("Use the navigation tabs to inspect new images, review report history, and download PDFs.")
                st.markdown(
                    f"- Recent crack detections analysed: {total_recent_cracks}\n"
                    f"- High severity detections in recent reports: {total_recent_high}\n"
                    f"- Account email: {user['email']}"
                )
                if user["role"] == "admin":
                    st.info("Admin mode is available from the Admin tab.")
                else:
                    st.caption("Open Inspect to upload new infrastructure images.")

        with activity_col:
            st.markdown('<div class="panel-title">Recent Inspections</div>', unsafe_allow_html=True)
            if not rows:
                st.info("No inspections yet. Open the Inspect page from the tabs above.")
            else:
                for row in rows:
                    st.markdown(
                        f"""
                        <div class="result-row">
                            <div>
                                <div class="result-name">{row['image_name']}</div>
                                <div class="result-date">{row['created_at']}</div>
                            </div>
                            <div>
                                <div class="result-label">Total Cracks</div>
                                <div class="result-metric">{row['total_cracks']}</div>
                            </div>
                            <div>
                                <div class="result-label">High Severity</div>
                                <div class="result-metric">{row['high_severity']}</div>
                            </div>
                            <div>
                                <div class="result-label">Status</div>
                                <div class="result-metric">{"Attention Needed" if row['high_severity'] else "Stable"}</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    def _render_page_intro(self, kicker: str, title: str, copy: str, chips: list[str]) -> None:
        self._render_visual_system_styles()
        chip_markup = "".join(f'<div class="surface-chip">{chip}</div>' for chip in chips)
        st.markdown(
            f"""
            <div class="surface-hero">
                <div class="surface-kicker">{kicker}</div>
                <h2 class="surface-title">{title}</h2>
                <p class="surface-copy">{copy}</p>
                <div class="surface-chip-grid">{chip_markup}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _render_inspect(self, user) -> None:
        model = self._get_model(self.settings.hf_token)
        self._render_page_intro(
            kicker="Inspect",
            title="Analyse new infrastructure images.",
            copy="Upload one or more photos to detect cracks, review severity, and generate an AI-assisted inspection report.",
            chips=[
                "Batch image upload",
                "Detection overlays",
                "Severity metrics",
                "PDF report export",
            ],
        )

        with self._surface_container("inspect_upload_panel"):
            st.markdown('<div class="panel-title">Upload Inspection Images</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="panel-note">Supported formats: JPG, JPEG, PNG. Each uploaded image is analysed independently.</div>',
                unsafe_allow_html=True,
            )
            uploaded_files = st.file_uploader(
                "Upload images",
                type=["jpg", "png", "jpeg"],
                accept_multiple_files=True,
                label_visibility="collapsed",
            )

        if not uploaded_files:
            st.info("Upload one or more images to begin inspection.")
            return

        for up_file in uploaded_files:
            image = Image.open(up_file).convert("RGB")
            img_np = np.array(image)
            with self._surface_container(f"inspect_result_{user['id']}_{up_file.name}"):
                st.markdown(f'<div class="panel-title">{up_file.name}</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="panel-note">Review the original image, AI detections, severity summary, and generated report below.</div>',
                    unsafe_allow_html=True,
                )

                col1, col2 = st.columns([1, 2])

                with col1:
                    st.image(image, caption="Original Image", width="stretch")

                with col2:
                    results = self.inspection_service.run_detection(model, img_np)
                    annotated = results.plot()
                    st.image(annotated, caption="Detected Cracks")
                    st.markdown('<div class="panel-title">Crack Analysis</div>', unsafe_allow_html=True)

                    if len(results.boxes) == 0:
                        st.warning("No cracks detected")
                        detections = []
                    else:
                        detections = self.inspection_service.build_detection_lines(results.boxes, img_np.shape)
                        self._render_detection_cards(detections)

                    total, high = self.inspection_service.summarize_counts(results.boxes, img_np.shape)
                    m1, m2 = st.columns(2)
                    m1.metric("Total Cracks", total)
                    m2.metric("High Severity", high)
                    style_metric_cards(border_left_color="#16a34a", border_color="#dbe4f0", border_radius_px=16)

                    st.markdown('<div class="panel-title">AI Generated Report</div>', unsafe_allow_html=True)
                    with st.spinner("Generating report..."):
                        report = self.inspection_service.generate_ai_report(detections)
                    st.markdown(self._style_report(report), unsafe_allow_html=True)

                    _, final_pdf = self.inspection_service.create_and_persist_report(
                        user_id=user["id"],
                        uploaded_file_name=up_file.name,
                        image=image,
                        total_cracks=total,
                        high_severity=high,
                        report=report,
                    )

                    with open(final_pdf, "rb") as f:
                        st.download_button(
                            "Download Report (PDF)",
                            f,
                            file_name=os.path.basename(final_pdf),
                            key=f"download_current_{user['id']}_{up_file.name}_{total}_{high}",
                            width="stretch",
                        )

    def _render_history(self, user) -> None:
        self._render_page_intro(
            kicker="History",
            title="Search previous inspections.",
            copy="Filter your report history by image name, severity, and date range, then export the result set as CSV.",
            chips=[
                "Search by image name",
                "Severity filters",
                "Optional date range",
                "CSV and PDF export",
            ],
        )

        with st.container(border=True):
            st.markdown('<div class="panel-title">Filter History</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="panel-note">Leave the date fields empty if you want to search across all available inspection records.</div>',
                unsafe_allow_html=True,
            )
            f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
            image_query = f1.text_input("Search by image name", value="")
            min_high = f2.number_input("Min High Severity", min_value=0, value=0, step=1)
            start_date = f3.date_input("From", value=None)
            end_date = f4.date_input("To", value=None)

        if start_date and end_date and start_date > end_date:
            st.error("'From' date cannot be after 'To' date.")
            return

        rows = self.repository.inspection_history(
            user["id"],
            image_query=image_query,
            min_high=min_high,
            start_date=start_date,
            end_date=end_date,
        )
        if not rows:
            st.info("No matching inspection records found.")
            return

        s1, s2, s3 = st.columns(3)
        s1.metric("Filtered Records", len(rows))
        s2.metric("Total Cracks", sum(r["total_cracks"] for r in rows))
        s3.metric("Total High Severity", sum(r["high_severity"] for r in rows))
        style_metric_cards(border_left_color="#0f172a", border_color="#dbe4f0", border_radius_px=16)

        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(["id", "image_name", "total_cracks", "high_severity", "created_at", "pdf_path"])
        for row in rows:
            csv_writer.writerow(
                [
                    row["id"],
                    row["image_name"],
                    row["total_cracks"],
                    row["high_severity"],
                    row["created_at"],
                    row["pdf_path"],
                ]
            )

        st.download_button(
            "Export Filtered History (CSV)",
            csv_buffer.getvalue().encode("utf-8"),
            file_name=f"inspection_history_{user['id']}.csv",
            mime="text/csv",
            key=f"history_csv_{user['id']}",
            width="stretch",
        )

        with self._surface_container("history_results_table"):
            st.markdown('<div class="panel-title">Results Table</div>', unsafe_allow_html=True)
            st.dataframe(
                [
                    {
                        "Image": row["image_name"],
                        "Total Cracks": row["total_cracks"],
                        "High Severity": row["high_severity"],
                        "Created At": row["created_at"],
                    }
                    for row in rows
                ],
                width="stretch",
                hide_index=True,
            )

        st.markdown('<div class="panel-title">Inspection Cards</div>', unsafe_allow_html=True)

        for row in rows:
            st.markdown(
                f"""
                <div class="result-row">
                    <div>
                        <div class="result-name">{row['image_name']}</div>
                        <div class="result-date">{row['created_at']}</div>
                    </div>
                    <div>
                        <div class="result-label">Total Cracks</div>
                        <div class="result-metric">{row['total_cracks']}</div>
                    </div>
                    <div>
                        <div class="result-label">High Severity</div>
                        <div class="result-metric">{row['high_severity']}</div>
                    </div>
                    <div>
                        <div class="result-label">Status</div>
                        <div class="result-metric">{"Attention Needed" if row['high_severity'] else "Stable"}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if row["pdf_path"] and os.path.exists(row["pdf_path"]):
                with open(row["pdf_path"], "rb") as pdf_f:
                    st.download_button(
                        "Download PDF",
                        pdf_f,
                        file_name=os.path.basename(row["pdf_path"]),
                        key=f"download_history_{row['id']}",
                    )
            else:
                st.caption("Report file not found on disk.")

    def _render_admin(self, user) -> None:
        if user["role"] != "admin":
            st.warning("Admin access required.")
            return

        st.subheader("Admin Console")
        rows = self.repository.list_users_for_admin()
        if not rows:
            st.info("No users found.")
            return

        for row in rows:
            st.write(
                f"#{row['id']} | {row['full_name']} | {row['email']} | role={row['role']} | verified={row['is_verified']} | {row['created_at']}"
            )

    def _render_nav(self, user) -> None:
        options = ["home"]
        labels = {
            "home": "Home",
            "landing": "Dashboard",
            "inspect": "Inspect",
            "history": "History",
            "admin": "Admin",
        }

        if user:
            options = ["landing", "inspect", "history", "home"]
            if user["role"] == "admin":
                options.append("admin")

        if st.session_state["page"] not in options:
            st.session_state["page"] = options[0]

        self._render_visual_system_styles()

        with self._surface_container("top_navigation"):
            left_col, right_col = st.columns([5, 1.2], vertical_alignment="center")
            with left_col:
                st.markdown('<div class="nav-title">Navigate</div>', unsafe_allow_html=True)
                selected_page = st.segmented_control(
                    "Navigation",
                    options=options,
                    default=st.session_state["page"],
                    format_func=lambda option: labels[option],
                    selection_mode="single",
                    label_visibility="collapsed",
                )
                if selected_page and selected_page != st.session_state["page"]:
                    st.session_state["page"] = selected_page
                    st.rerun()

                if user:
                    st.markdown(f'<div class="nav-user">Logged in as: {user["email"]}</div>', unsafe_allow_html=True)

            with right_col:
                if user:
                    st.markdown('<div class="nav-title">Session</div>', unsafe_allow_html=True)
                    if st.button("Logout", key="nav_logout", width="stretch"):
                        st.session_state["session_token"] = None
                        st.session_state["page"] = "home"
                        st.rerun()

        st.divider()

    def run(self) -> None:
        st.set_page_config(page_title="Civil Inspection AI Demo", layout="wide")
        self.repository.init_db()
        self._bootstrap_session()

        user = self.repository.get_user_from_session(st.session_state.get("session_token"))
        if user and not user["registration_completed"]:
            st.session_state["pending_email"] = user["email"]
            st.session_state["verified_user_id"] = int(user["id"])
            self._open_auth_dialog("register")

        self._render_header()
        self._render_nav(user)

        page = st.session_state["page"]
        if page == "home":
            self._render_home()
        elif page == "auth":
            st.session_state["page"] = "home"
            self._render_auth()
        elif page == "landing":
            self._require_authentication(user)
            self._render_landing(user)
        elif page == "inspect":
            self._require_authentication(user)
            self._render_inspect(user)
        elif page == "history":
            self._require_authentication(user)
            self._render_history(user)
        elif page == "admin":
            self._require_authentication(user)
            self._render_admin(user)

        if st.session_state.get("show_auth_dialog"):
            self._render_auth_dialog()

        self._render_footer()
