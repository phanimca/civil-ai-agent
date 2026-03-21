from __future__ import annotations

import base64
import csv
import io
import os
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components

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

    @staticmethod
    def _image_mime_type(file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if ext == ".png":
            return "image/png"
        if ext == ".avif":
            return "image/avif"
        return "application/octet-stream"

    @st.cache_data
    def _build_demo_carousel_html(_self, demo_images: list[tuple[str, str]]) -> str:
        slides = []
        for index, (title, file_path) in enumerate(demo_images):
            if not os.path.exists(file_path):
                continue

            with open(file_path, "rb") as img_file:
                encoded = base64.b64encode(img_file.read()).decode("utf-8")

            mime_type = _self._image_mime_type(file_path)
            slides.append(
                f"""
                <div class=\"carousel-slide slide-{index}\">
                    <img src=\"data:{mime_type};base64,{encoded}\" alt=\"{title}\" />
                    <div class=\"carousel-caption\">{title}</div>
                </div>
                """
            )

        if not slides:
            return "<div style='padding:16px;border:1px solid #cbd5e1;border-radius:16px;'>No demo images found.</div>"

        total_duration = max(12, len(slides) * 4)
        slide_duration = total_duration / len(slides)
        animation_css = "\n".join(
            f".slide-{index} {{ animation-delay: {index * slide_duration}s; }}"
            for index in range(len(slides))
        )

        return f"""
        <style>
            .carousel-shell {{
                position: relative;
                width: 100%;
                height: 360px;
                overflow: hidden;
                border-radius: 22px;
                border: 1px solid #cbd5e1;
                background: linear-gradient(135deg, #dbeafe, #f8fafc 55%, #dcfce7);
                box-shadow: 0 24px 60px rgba(15, 23, 42, 0.10);
            }}
            .carousel-slide {{
                position: absolute;
                inset: 0;
                opacity: 0;
                animation: fadeSlides {total_duration}s infinite;
            }}
            .carousel-slide img {{
                width: 100%;
                height: 100%;
                object-fit: cover;
                display: block;
            }}
            .carousel-caption {{
                position: absolute;
                left: 20px;
                top: 20px;
                padding: 12px 16px;
                border-radius: 14px;
                background: rgba(15, 23, 42, 0.72);
                color: #fff;
                font: 700 16px/1.2 \"Segoe UI\", sans-serif;
                letter-spacing: 0.02em;
            }}
            .carousel-dots {{
                position: absolute;
                left: 50%;
                bottom: 18px;
                transform: translateX(-50%);
                display: flex;
                gap: 8px;
                z-index: 5;
            }}
            .carousel-dots span {{
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.65);
                border: 1px solid rgba(15, 23, 42, 0.18);
            }}
            {animation_css}
            @keyframes fadeSlides {{
                0% {{ opacity: 0; }}
                6% {{ opacity: 1; }}
                24% {{ opacity: 1; }}
                30% {{ opacity: 0; }}
                100% {{ opacity: 0; }}
            }}
        </style>
        <div class=\"carousel-shell\">
            {''.join(slides)}
            <div class=\"carousel-dots\">{''.join('<span></span>' for _ in slides)}</div>
        </div>
        """

    @st.cache_resource
    def _get_model(_self, hf_token: str):
        return _self.inspection_service.load_detection_model()

    @staticmethod
    def _style_report(text: str) -> str:
        return f"""
        <div style=\"background:#f8fafc;padding:20px 22px;border-radius:12px;border:1px solid #e2e8f0;color:#0f172a;line-height:1.6;\">
            <h2 style=\"margin:0 0 10px 0;color:#0369a1;font-size:22px;\">AI Inspection Report</h2>
            <p style=\"margin:0 0 10px 0;color:#64748b;font-size:12px;\">For more details: <a href=\"https://github.com/phanimca/civil-ai-agent/blob/initial-version/README.md\" target=\"_blank\" style=\"font-size:12px;\">GitHub Repository</a></p>
            <div style=\"font-size:14px;white-space:pre-wrap;font-family:Segoe UI, sans-serif;\">{text}</div>
        </div>
        """

    @staticmethod
    def _bootstrap_session() -> None:
        st.session_state.setdefault("page", "home")
        st.session_state.setdefault("session_token", None)
        st.session_state.setdefault("pending_email", "")
        st.session_state.setdefault("pending_code_expires_at", None)
        st.session_state.setdefault("next_code_request_at", None)
        st.session_state.setdefault("pending_code", "")

    def _render_header(self) -> None:
        logo_col, title_col = st.columns([1.6, 5.4])
        with logo_col:
            if os.path.exists(self.settings.header_logo_path):
                st.image(self.settings.header_logo_path, width=190)
        with title_col:
            st.title("Civil Inspection AI Agent")
            st.markdown(
                '<p style="font-size:12px;color:#64748b;margin-top:-6px;margin-bottom:8px;">'
                "Demo for B.Tech Civil students | Designed by Phani"
                "</p>",
                unsafe_allow_html=True,
            )
        st.divider()

    @staticmethod
    def _render_footer() -> None:
        st.divider()
        st.caption("Civil-AI-Agent Demo | Built with GenAI")

    def _render_home(self) -> None:
        left_col, right_col = st.columns([1.05, 1.35], vertical_alignment="center")

        with left_col:
            st.markdown("## Welcome")
            st.markdown(
                "This demo helps civil engineering students detect cracks, assess severity, and generate structured inspection reports from infrastructure images."
            )
            st.markdown("### Highlights")
            st.markdown("- AI crack detection\n- Severity scoring\n- AI narrative report\n- Export-ready documentation")

        with right_col:
            if st.button("Try for Free", type="primary", use_container_width=True):
                st.session_state["page"] = "auth"
                st.rerun()
            components.html(self._build_demo_carousel_html(self.settings.demo_carousel_images), height=300)

    def _render_auth(self) -> None:
        st.subheader("Sign in / Register")

        cooldown_left = self.auth_service.seconds_until(st.session_state.get("next_code_request_at"))
        expiry_left = self.auth_service.seconds_until(st.session_state.get("pending_code_expires_at"))

        if expiry_left > 0:
            mins = expiry_left // 60
            secs = expiry_left % 60
            st.info(f"Current verification code expires in {mins}m {secs}s.")

        if cooldown_left > 0:
            st.caption(f"You can request a new code in {cooldown_left}s.")

        with st.form("request_code_form"):
            st.markdown("Request Verification Code")
            full_name = st.text_input("Name")
            email = st.text_input("Email")
            mobile = st.text_input("Mobile")
            college = st.text_input("College")
            request = st.form_submit_button(
                "Send Verification Code",
                type="primary",
                disabled=cooldown_left > 0,
            )

        if request:
            if cooldown_left > 0:
                st.warning(f"Please wait {cooldown_left}s before requesting another code.")
                return

            email_norm = self.auth_service.normalize_email(email)
            validation_errors = self.auth_service.validate_profile(full_name, email_norm, mobile, college)
            if validation_errors:
                for err in validation_errors:
                    st.error(err)
            else:
                user_id = self.repository.create_or_update_user(full_name, email_norm, mobile, college)
                code = self.auth_service.issue_verification_code(user_id, "login")
                ok, msg = self.email_service.send_verification_email(email_norm, full_name or "Student", code)
                if ok:
                    st.success(msg)
                    now = datetime.now(timezone.utc)
                    st.session_state["next_code_request_at"] = (
                        now + timedelta(seconds=self.settings.request_cooldown_seconds)
                    ).isoformat()
                    st.session_state["pending_code_expires_at"] = (
                        now + timedelta(minutes=self.settings.code_exp_minutes)
                    ).isoformat()
                    st.session_state["pending_code"] = ""
                else:
                    st.warning(msg)
                    fallback_code = self.email_service.extract_demo_code(msg)
                    if fallback_code:
                        st.info("Demo fallback active: use this verification code to continue.")
                        st.code(fallback_code)
                        st.session_state["pending_code"] = fallback_code
                        now = datetime.now(timezone.utc)
                        st.session_state["pending_code_expires_at"] = (
                            now + timedelta(minutes=self.settings.code_exp_minutes)
                        ).isoformat()
                st.session_state["pending_email"] = email_norm

        with st.form("verify_code_form"):
            st.markdown("Verify Code")
            code_email = st.text_input("Email for verification", value=st.session_state.get("pending_email", ""))
            code = st.text_input("Verification Code", value=st.session_state.get("pending_code", ""))
            verify = st.form_submit_button("Verify and Login")

        if verify:
            ok, msg, token = self.auth_service.verify_code_and_create_session(code_email, code)
            if ok:
                st.session_state["session_token"] = token
                st.session_state["page"] = "landing"
                st.session_state["pending_code_expires_at"] = None
                st.session_state["next_code_request_at"] = None
                st.session_state["pending_code"] = ""
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    def _render_landing(self, user) -> None:
        st.subheader(f"Welcome, {user['full_name']}")
        st.write("Explore the core capabilities of Phani's Civil Inspection AI Agent.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Role", user["role"].title())
        c2.metric("Verified", "Yes" if user["is_verified"] else "No")
        c3.metric("Demo", "Active")

        st.markdown("### Features")
        st.markdown("- AI crack detection from images\n- Severity analytics\n- AI narrative report\n- PDF download")

        st.markdown("### Recent Inspections")
        rows = self.repository.recent_inspections(user["id"], limit=5)
        if not rows:
            st.info("No inspections yet. Open the Inspect page from the tabs above.")
        else:
            for row in rows:
                st.write(
                    f"{row['created_at']} | {row['image_name']} | Total: {row['total_cracks']} | High: {row['high_severity']}"
                )

    def _render_inspect(self, user) -> None:
        model = self._get_model(self.settings.hf_token)
        st.subheader("Inspect Infrastructure Images")
        uploaded_files = st.file_uploader(
            "Upload images",
            type=["jpg", "png", "jpeg"],
            accept_multiple_files=True,
        )

        if not uploaded_files:
            st.info("Upload one or more images to begin inspection.")
            return

        for up_file in uploaded_files:
            image = Image.open(up_file).convert("RGB")
            img_np = np.array(image)
            col1, col2 = st.columns([1, 2])

            with col1:
                st.image(image, caption="Original Image", use_container_width=True)

            with col2:
                results = self.inspection_service.run_detection(model, img_np)
                annotated = results.plot()
                st.image(annotated, caption="Detected Cracks")
                st.subheader("Crack Analysis")

                if len(results.boxes) == 0:
                    st.warning("No cracks detected")
                    detections = []
                else:
                    detections = self.inspection_service.build_detection_lines(results.boxes, img_np.shape)
                    for line in detections:
                        st.write(line)

                total, high = self.inspection_service.summarize_counts(results.boxes, img_np.shape)
                m1, m2 = st.columns(2)
                m1.metric("Total Cracks", total)
                m2.metric("High Severity", high)

                st.subheader("AI Generated Report")
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
                    )

            st.divider()

    def _render_history(self, user) -> None:
        st.subheader("Inspection History")

        f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
        image_query = f1.text_input("Search by image name", value="")
        min_high = f2.number_input("Min High Severity", min_value=0, value=0, step=1)
        start_date = f3.date_input("From")
        end_date = f4.date_input("To")

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
        )

        for row in rows:
            h1, h2, h3, h4 = st.columns([3, 1, 1, 2])
            h1.write(f"{row['image_name']}")
            h2.metric("Total", row["total_cracks"])
            h3.metric("High", row["high_severity"])
            h4.write(row["created_at"])

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
            st.divider()

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
        options = ["home", "auth"]
        labels = {
            "home": "Home",
            "auth": "Sign In",
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

        nav_col_count = len(options) + (1 if user else 0)
        nav_cols = st.columns(nav_col_count)

        for index, option in enumerate(options):
            is_active = st.session_state["page"] == option
            if nav_cols[index].button(
                labels[option],
                key=f"nav_{option}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["page"] = option
                st.rerun()

        if user:
            if nav_cols[-1].button("Logout", key="nav_logout", use_container_width=True):
                st.session_state["session_token"] = None
                st.session_state["page"] = "home"
                st.rerun()
            st.caption(f"Logged in as: {user['email']}")

        st.divider()

    def run(self) -> None:
        st.set_page_config(page_title="Civil Inspection AI Demo", layout="wide")
        self.repository.init_db()
        self._bootstrap_session()

        user = self.repository.get_user_from_session(st.session_state.get("session_token"))

        self._render_header()
        self._render_nav(user)

        page = st.session_state["page"]
        if page == "home":
            self._render_home()
        elif page == "auth":
            self._render_auth()
        elif page == "landing":
            if not user:
                st.warning("Please sign in first.")
                st.session_state["page"] = "auth"
                st.rerun()
            self._render_landing(user)
        elif page == "inspect":
            if not user:
                st.warning("Please sign in first.")
                st.session_state["page"] = "auth"
                st.rerun()
            self._render_inspect(user)
        elif page == "history":
            if not user:
                st.warning("Please sign in first.")
                st.session_state["page"] = "auth"
                st.rerun()
            self._render_history(user)
        elif page == "admin":
            if not user:
                st.warning("Please sign in first.")
                st.session_state["page"] = "auth"
                st.rerun()
            self._render_admin(user)

        self._render_footer()
