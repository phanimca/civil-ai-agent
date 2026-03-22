from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from data.repository import SQLiteRepository


class AuthService:
    def __init__(self, repository: SQLiteRepository, code_exp_minutes: int, session_hours: int) -> None:
        self.repository = repository
        self.code_exp_minutes = code_exp_minutes
        self.session_hours = session_hours

    @staticmethod
    def normalize_email(email: str) -> str:
        return SQLiteRepository.normalize_email(email)

    def validate_email(self, email: str) -> list[str]:
        errors = []

        email_norm = self.normalize_email(email)
        if not email_norm:
            errors.append("Email is required.")
        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_norm):
            errors.append("Email format looks invalid.")

        return errors

    def validate_registration_profile(
        self,
        first_name: str,
        last_name: str,
        mobile: str,
        college: str,
        profession: str,
        python_knowledge: str,
        ai_tool_usage: str,
        ai_awareness: str,
    ) -> list[str]:
        errors = []
        if not (first_name or "").strip():
            errors.append("First name is required.")

        if not (last_name or "").strip():
            errors.append("Last name is required.")

        digits = "".join(ch for ch in (mobile or "") if ch.isdigit())
        if len(digits) < 10 or len(digits) > 15:
            errors.append("Mobile must contain 10-15 digits.")

        if not (college or "").strip():
            errors.append("College name is required.")

        if profession not in {"Student", "Faculty Member"}:
            errors.append("Profession is required.")

        if python_knowledge not in {"No", "Beginner", "Advanced", "Expert"}:
            errors.append("Python knowledge selection is required.")

        if ai_tool_usage not in {"No", "EveryDay", "Once In a While"}:
            errors.append("AI tool usage selection is required.")

        if not (ai_awareness or "").strip():
            errors.append("Please tell us what you know about AI.")

        return errors

    def issue_verification_code(self, user_id: int, purpose: str) -> str:
        code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=self.code_exp_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        self.repository.replace_verification_code(user_id, code, purpose, expires_at)
        return code

    @staticmethod
    def seconds_until(iso_ts: str | None) -> int:
        if not iso_ts:
            return 0
        try:
            dt = datetime.fromisoformat(iso_ts)
        except Exception:
            return 0
        remaining = int((dt - datetime.now(timezone.utc)).total_seconds())
        return max(0, remaining)

    def verify_code(self, email: str, code: str):
        email_norm = self.normalize_email(email)
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)

        user = self.repository.find_user_by_email(email_norm)
        if not user:
            return False, "User not found.", None

        code_row = self.repository.get_latest_code(user["id"], code)
        if not code_row:
            return False, "Invalid verification code.", None

        exp_dt = datetime.strptime(code_row["expires_at"], "%Y-%m-%d %H:%M:%S")
        if exp_dt < now_dt:
            return False, "Verification code expired.", None

        return True, "Verification successful.", user

    def create_session_for_user(self, user_id: int) -> str:
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)

        session_token = secrets.token_urlsafe(32)
        token_hash = SQLiteRepository.hash_token(session_token)
        expires_at = (now_dt + timedelta(hours=self.session_hours)).strftime("%Y-%m-%d %H:%M:%S")
        self.repository.complete_login(user_id, token_hash, expires_at)

        return session_token

    def verify_code_and_create_session(self, email: str, code: str) -> tuple[bool, str, str | None]:
        ok, msg, user = self.verify_code(email, code)
        if not ok or not user:
            return ok, msg, None

        return True, "Login successful.", self.create_session_for_user(int(user["id"]))
