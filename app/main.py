from __future__ import annotations

from config.settings import load_settings
from data.repository import SQLiteRepository
from services.auth_service import AuthService
from services.email_service import EmailService
from services.inspection_service import InspectionService
from ui.streamlit_app import CivilAIStreamlitApp


class AppContainer:
    def __init__(self) -> None:
        self.settings = load_settings()

        self.repository = SQLiteRepository(
            db_path=self.settings.db_path,
            upload_dir=self.settings.upload_dir,
            report_dir=self.settings.report_dir,
            admin_seed_email=self.settings.admin_seed_email,
        )

        self.auth_service = AuthService(
            repository=self.repository,
            code_exp_minutes=self.settings.code_exp_minutes,
            session_hours=self.settings.session_hours,
        )

        self.email_service = EmailService(
            brevo_api_key=self.settings.brevo_api_key,
            brevo_from_email=self.settings.brevo_from_email,
            brevo_from_name=self.settings.brevo_from_name,
            resend_api_key=self.settings.resend_api_key,
            email_from=self.settings.email_from,
            code_exp_minutes=self.settings.code_exp_minutes,
        )

        self.inspection_service = InspectionService(
            repository=self.repository,
            upload_dir=self.settings.upload_dir,
            report_dir=self.settings.report_dir,
            openai_token=self.settings.openai_token,
            model_name=self.settings.model_name,
            hf_token=self.settings.hf_token,
        )

    def build_app(self) -> CivilAIStreamlitApp:
        return CivilAIStreamlitApp(
            settings=self.settings,
            repository=self.repository,
            auth_service=self.auth_service,
            email_service=self.email_service,
            inspection_service=self.inspection_service,
        )


def main() -> None:
    container = AppContainer()
    app = container.build_app()
    app.run()


if __name__ == "__main__":
    main()
