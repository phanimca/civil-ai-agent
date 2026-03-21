from __future__ import annotations

import re

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import resend


class EmailService:
    def __init__(
        self,
        brevo_api_key: str,
        brevo_from_email: str,
        brevo_from_name: str,
        resend_api_key: str,
        email_from: str,
        code_exp_minutes: int,
    ) -> None:
        self.brevo_api_key = brevo_api_key
        self.brevo_from_email = brevo_from_email
        self.brevo_from_name = brevo_from_name
        self.resend_api_key = resend_api_key
        self.email_from = email_from
        self.code_exp_minutes = code_exp_minutes

    def send_verification_email(self, email: str, full_name: str, code: str) -> tuple[bool, str]:
        brevo_error_message = None

        if self.brevo_api_key and self.brevo_from_email:
            try:
                configuration = sib_api_v3_sdk.Configuration()
                configuration.api_key["api-key"] = self.brevo_api_key

                api_client = sib_api_v3_sdk.ApiClient(configuration)
                api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    sender={"email": self.brevo_from_email, "name": self.brevo_from_name},
                    to=[{"email": email, "name": full_name}],
                    subject="Civil-AI-Agent verification code",
                    text_content=(
                        f"Hi {full_name},\n\n"
                        f"Your verification code is: {code}\n"
                        f"This code expires in {self.code_exp_minutes} minutes.\n"
                    ),
                    html_content=(
                        f"<p>Hi {full_name},</p>"
                        f"<p>Your verification code is <strong>{code}</strong>.</p>"
                        f"<p>This code expires in {self.code_exp_minutes} minutes.</p>"
                    ),
                )
                api_instance.send_transac_email(send_smtp_email)

                return True, "Verification code sent via Brevo."
            except ApiException as exc:
                brevo_error_message = f"Brevo send failed (status {getattr(exc, 'status', 'unknown')}): {exc}. Attempting Resend fallback."
            except Exception as exc:
                brevo_error_message = f"Brevo send failed: {exc}. Attempting Resend fallback."

        if not self.resend_api_key:
            if brevo_error_message:
                return False, f"{brevo_error_message} No Resend key configured. Demo verification code: {code}"
            return (
                False,
                f"No email provider configured. Set BREVO_API_KEY/BREVO_FROM_EMAIL or RESEND_API_KEY. Demo code: {code}",
            )

        resend.api_key = self.resend_api_key
        payload: resend.Emails.SendParams = {
            "from": self.email_from,
            "to": [email],
            "subject": "Civil-AI-Agent verification code",
            "html": (
                f"<p>Hi {full_name},</p>"
                f"<p>Your verification code is <strong>{code}</strong>.</p>"
                f"<p>This code expires in {self.code_exp_minutes} minutes.</p>"
            ),
        }
        try:
            resend.Emails.send(payload)
            if brevo_error_message:
                return True, f"{brevo_error_message} Verification code sent via Resend fallback."
            return True, "Verification code sent."
        except Exception as exc:
            err = str(exc)
            if "You can only send testing emails to your own email address" in err:
                return (
                    False,
                    "Resend testing mode only allows emails to your own address. "
                    f"Demo verification code: {code}. To send to other users, verify a domain in Resend and use EMAIL_FROM from that domain.",
                )
            if "403" in err:
                return (
                    False,
                    "Email send failed (403). Verify EMAIL_FROM in Resend (domain/sender) or use onboarding@resend.dev for testing.",
                )
            return False, f"Email send failed: {exc}"

    @staticmethod
    def extract_demo_code(message: str) -> str:
        if not message:
            return ""
        match = re.search(r"(?:demo\s+verification\s+code|demo\s+code)\s*[:=]\s*(\d{6})", message, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""
