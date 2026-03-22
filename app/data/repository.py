from __future__ import annotations

import csv
import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone


class SQLiteRepository:
    def __init__(self, db_path: str, upload_dir: str, report_dir: str, admin_seed_email: str) -> None:
        self.db_path = db_path
        self.upload_dir = upload_dir
        self.report_dir = report_dir
        self.admin_seed_email = admin_seed_email

    def utc_now_str(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def ensure_dirs(self) -> None:
        os.makedirs("app_data", exist_ok=True)
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.report_dir, exist_ok=True)

    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _table_columns(cur: sqlite3.Cursor, table_name: str) -> set[str]:
        cur.execute(f"PRAGMA table_info({table_name})")
        return {str(row[1]) for row in cur.fetchall()}

    def _ensure_column(self, cur: sqlite3.Cursor, table_name: str, column_name: str, definition: str) -> None:
        if column_name in self._table_columns(cur, table_name):
            return
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def init_db(self) -> None:
        self.ensure_dirs()
        conn = self.get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT,
                last_name TEXT,
                full_name TEXT NOT NULL DEFAULT '',
                email TEXT UNIQUE NOT NULL,
                mobile TEXT,
                college TEXT,
                profession TEXT,
                python_knowledge TEXT,
                ai_tool_usage TEXT,
                ai_awareness TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                is_verified INTEGER NOT NULL DEFAULT 0,
                registration_completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                image_name TEXT,
                image_path TEXT,
                pdf_path TEXT,
                total_cracks INTEGER NOT NULL DEFAULT 0,
                high_severity INTEGER NOT NULL DEFAULT 0,
                llm_prompt_tokens INTEGER NOT NULL DEFAULT 0,
                llm_completion_tokens INTEGER NOT NULL DEFAULT 0,
                llm_total_tokens INTEGER NOT NULL DEFAULT 0,
                llm_cost_inr REAL NOT NULL DEFAULT 0,
                report_text TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                llm_name TEXT NOT NULL,
                usage_count INTEGER NOT NULL DEFAULT 1,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                last_used TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, llm_name)
            )
            """
        )

        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_college ON users(college)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_codes_user ON verification_codes(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inspections_user ON inspections(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_user ON llm_usage(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_name ON llm_usage(llm_name)")

        self._ensure_column(cur, "users", "first_name", "TEXT")
        self._ensure_column(cur, "users", "last_name", "TEXT")
        self._ensure_column(cur, "users", "profession", "TEXT")
        self._ensure_column(cur, "users", "python_knowledge", "TEXT")
        self._ensure_column(cur, "users", "ai_tool_usage", "TEXT")
        self._ensure_column(cur, "users", "ai_awareness", "TEXT")
        self._ensure_column(cur, "users", "registration_completed", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(cur, "inspections", "llm_prompt_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(cur, "inspections", "llm_completion_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(cur, "inspections", "llm_total_tokens", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(cur, "inspections", "llm_cost_inr", "REAL NOT NULL DEFAULT 0")

        cur.execute(
            """
            UPDATE users
            SET full_name = TRIM(COALESCE(full_name, '')),
                college = CASE
                    WHEN college IS NULL OR TRIM(college) = '' THEN ''
                    ELSE UPPER(TRIM(college))
                END,
                registration_completed = CASE
                    WHEN registration_completed = 1 THEN 1
                    WHEN TRIM(COALESCE(full_name, '')) <> '' THEN 1
                    ELSE 0
                END
            """
        )

        if self.admin_seed_email:
            cur.execute("SELECT id FROM users WHERE email = ?", (self.admin_seed_email,))
            admin_row = cur.fetchone()
            if admin_row:
                cur.execute(
                    "UPDATE users SET role = 'admin', is_verified = 1, updated_at = ? WHERE id = ?",
                    (self.utc_now_str(), admin_row["id"]),
                )

        self._seed_demo_data(cur)

        conn.commit()
        conn.close()

    def _seed_demo_data(self, cur: sqlite3.Cursor) -> None:
        """Seed demo records for admin dashboard charts (idempotent)."""
        now_dt = datetime.now(timezone.utc)
        now = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        samples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "samples"))
        users_csv = os.path.join(samples_dir, "demo_users.csv")
        llm_csv = os.path.join(samples_dir, "demo_llm_usage.csv")
        inspections_csv = os.path.join(samples_dir, "demo_inspections.csv")

        if not (os.path.exists(users_csv) and os.path.exists(llm_csv) and os.path.exists(inspections_csv)):
            return

        with open(users_csv, "r", encoding="utf-8", newline="") as f:
            demo_users = [row for row in csv.DictReader(f) if (row.get("email") or "").strip()]

        with open(llm_csv, "r", encoding="utf-8", newline="") as f:
            llm_rows = [row for row in csv.DictReader(f) if (row.get("email") or "").strip()]

        with open(inspections_csv, "r", encoding="utf-8", newline="") as f:
            inspection_rows = [row for row in csv.DictReader(f) if (row.get("email") or "").strip()]

        llm_by_email: dict[str, list[dict[str, str]]] = {}
        for row in llm_rows:
            email = self.normalize_email(row.get("email", ""))
            llm_by_email.setdefault(email, []).append(row)

        inspections_by_email: dict[str, list[dict[str, str]]] = {}
        for row in inspection_rows:
            email = self.normalize_email(row.get("email", ""))
            inspections_by_email.setdefault(email, []).append(row)

        for idx, row in enumerate(demo_users):
            first_name = (row.get("first_name") or "").strip()
            last_name = (row.get("last_name") or "").strip()
            full_name = (row.get("full_name") or f"{first_name} {last_name}").strip()
            email = self.normalize_email(row.get("email", ""))
            if not email:
                continue

            mobile = (row.get("mobile") or f"90000{idx:05d}").strip()
            college = self.normalize_college(row.get("college", ""))
            profession = (row.get("profession") or "").strip()
            python_knowledge = (row.get("python_knowledge") or "").strip()
            ai_tool_usage = (row.get("ai_tool_usage") or "").strip()
            ai_awareness = (row.get("ai_awareness") or "").strip()

            created_days_ago_raw = (row.get("created_days_ago") or "").strip()
            created_days_ago = int(created_days_ago_raw) if created_days_ago_raw.isdigit() else (idx * 9 + 10)
            created_at = (now_dt - timedelta(days=created_days_ago)).strftime("%Y-%m-%d %H:%M:%S")

            cur.execute(
                """
                INSERT INTO users (
                    first_name, last_name, full_name, email, mobile, college,
                    profession, python_knowledge, ai_tool_usage, ai_awareness,
                    role, is_verified, registration_completed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', 1, 1, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    first_name=excluded.first_name,
                    last_name=excluded.last_name,
                    full_name=excluded.full_name,
                    mobile=excluded.mobile,
                    college=excluded.college,
                    profession=excluded.profession,
                    python_knowledge=excluded.python_knowledge,
                    ai_tool_usage=excluded.ai_tool_usage,
                    ai_awareness=excluded.ai_awareness,
                    is_verified=1,
                    registration_completed=1,
                    updated_at=excluded.updated_at
                """,
                (
                    first_name,
                    last_name,
                    full_name,
                    email,
                    mobile,
                    college,
                    profession,
                    python_knowledge,
                    ai_tool_usage,
                    ai_awareness,
                    created_at,
                    now,
                ),
            )

            cur.execute("SELECT id FROM users WHERE email = ?", (email,))
            row = cur.fetchone()
            if not row:
                continue
            user_id = int(row["id"])

            cur.execute("DELETE FROM llm_usage WHERE user_id = ?", (user_id,))
            for llm_row in llm_by_email.get(email, []):
                llm_name = (llm_row.get("llm_name") or "").strip()
                if not llm_name:
                    continue
                usage_count = int((llm_row.get("usage_count") or "0").strip() or "0")
                tokens_used = int((llm_row.get("tokens_used") or "0").strip() or "0")
                cur.execute(
                    """
                    INSERT INTO llm_usage (user_id, llm_name, usage_count, tokens_used, last_used, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        llm_name,
                        int(usage_count),
                        int(tokens_used),
                        now,
                        created_at,
                        now,
                    ),
                )

            cur.execute("DELETE FROM inspections WHERE user_id = ? AND image_name LIKE 'DEMO_%'", (user_id,))
            for inspection_row in inspections_by_email.get(email, []):
                image_name = (inspection_row.get("image_name") or "").strip()
                if not image_name:
                    continue

                created_days_ago_raw = (inspection_row.get("created_days_ago") or "").strip()
                created_days_ago = int(created_days_ago_raw) if created_days_ago_raw.isdigit() else (idx * 7 + 2)
                created_at_insp = (now_dt - timedelta(days=created_days_ago)).strftime("%Y-%m-%d %H:%M:%S")

                total_cracks = int((inspection_row.get("total_cracks") or "0").strip() or "0")
                high_severity = int((inspection_row.get("high_severity") or "0").strip() or "0")
                prompt_tokens = int((inspection_row.get("llm_prompt_tokens") or "0").strip() or "0")
                completion_tokens = int((inspection_row.get("llm_completion_tokens") or "0").strip() or "0")
                total_tokens_raw = (inspection_row.get("llm_total_tokens") or "").strip()
                total_tokens = int(total_tokens_raw) if total_tokens_raw.isdigit() else prompt_tokens + completion_tokens

                cost_inr_raw = (inspection_row.get("llm_cost_inr") or "").strip()
                if cost_inr_raw:
                    cost_inr = float(cost_inr_raw)
                else:
                    cost_inr = round((prompt_tokens / 1000 * 0.00015 + completion_tokens / 1000 * 0.00060) * 83, 6)

                report_text = (inspection_row.get("report_text") or "Demo AI inspection report").strip()
                cur.execute(
                    """
                    INSERT INTO inspections (
                        user_id, image_name, image_path, pdf_path,
                        total_cracks, high_severity,
                        llm_prompt_tokens, llm_completion_tokens, llm_total_tokens, llm_cost_inr,
                        report_text, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        image_name,
                        f"app_data/uploads/{user_id}/{image_name}",
                        f"app_data/reports/{user_id}/{os.path.splitext(image_name)[0]}.pdf",
                        total_cracks,
                        high_severity,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        cost_inr,
                        report_text,
                        created_at_insp,
                    ),
                )

    @staticmethod
    def normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def normalize_college(college: str) -> str:
        return (college or "").strip().upper()

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_or_update_user(self, full_name: str, email: str, mobile: str, college: str) -> int:
        email = self.normalize_email(email)
        college = self.normalize_college(college)
        now = self.utc_now_str()
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()

        if row:
            cur.execute(
                """
                UPDATE users
                SET full_name = COALESCE(NULLIF(?, ''), full_name),
                    mobile = COALESCE(NULLIF(?, ''), mobile),
                    college = COALESCE(NULLIF(?, ''), college),
                    registration_completed = CASE
                        WHEN COALESCE(NULLIF(?, ''), full_name) <> '' THEN 1
                        ELSE registration_completed
                    END,
                    updated_at = ?
                WHERE id = ?
                """,
                (full_name, mobile, college, full_name, now, row["id"]),
            )
            user_id = row["id"]
        else:
            role = "admin" if self.admin_seed_email and email == self.admin_seed_email else "user"
            cur.execute(
                """
                INSERT INTO users (
                    full_name,
                    email,
                    mobile,
                    college,
                    role,
                    is_verified,
                    registration_completed,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (full_name, email, mobile, college, role, 1 if full_name.strip() else 0, now, now),
            )
            user_id = cur.lastrowid

        conn.commit()
        conn.close()
        return int(user_id)

    def replace_verification_code(self, user_id: int, code: str, purpose: str, expires_at: str) -> None:
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM verification_codes WHERE user_id = ?", (user_id,))
        cur.execute(
            "INSERT INTO verification_codes (user_id, code, purpose, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, code, purpose, expires_at, self.utc_now_str()),
        )
        conn.commit()
        conn.close()

    def find_user_by_email(self, email: str):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (self.normalize_email(email),))
        row = cur.fetchone()
        conn.close()
        return row

    def ensure_user(self, email: str) -> int:
        email = self.normalize_email(email)
        existing = self.find_user_by_email(email)
        if existing:
            return int(existing["id"])

        now = self.utc_now_str()
        role = "admin" if self.admin_seed_email and email == self.admin_seed_email else "user"
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (
                full_name,
                email,
                mobile,
                college,
                role,
                is_verified,
                registration_completed,
                created_at,
                updated_at
            )
            VALUES ('', ?, '', '', ?, 0, 0, ?, ?)
            """,
            (email, role, now, now),
        )
        user_id = cur.lastrowid
        conn.commit()
        conn.close()
        return int(user_id)

    def update_user_registration(
        self,
        user_id: int,
        first_name: str,
        last_name: str,
        mobile: str,
        college: str,
        profession: str,
        python_knowledge: str,
        ai_tool_usage: str,
        ai_awareness: str,
    ) -> None:
        now = self.utc_now_str()
        college = self.normalize_college(college)
        full_name = " ".join(part for part in [first_name.strip(), last_name.strip()] if part).strip()

        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE users
            SET first_name = ?,
                last_name = ?,
                full_name = ?,
                mobile = ?,
                college = ?,
                profession = ?,
                python_knowledge = ?,
                ai_tool_usage = ?,
                ai_awareness = ?,
                registration_completed = 1,
                updated_at = ?
            WHERE id = ?
            """,
            (
                first_name.strip(),
                last_name.strip(),
                full_name,
                mobile.strip(),
                college,
                profession.strip(),
                python_knowledge.strip(),
                ai_tool_usage.strip(),
                ai_awareness.strip(),
                now,
                user_id,
            ),
        )
        conn.commit()
        conn.close()

    def get_latest_code(self, user_id: int, code: str):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM verification_codes
            WHERE user_id = ? AND code = ?
            ORDER BY id DESC LIMIT 1
            """,
            (user_id, code.strip()),
        )
        row = cur.fetchone()
        conn.close()
        return row

    def complete_login(self, user_id: int, token_hash: str, expires_at: str) -> None:
        now = self.utc_now_str()
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_verified = 1, updated_at = ? WHERE id = ?", (now, user_id))
        cur.execute("DELETE FROM verification_codes WHERE user_id = ?", (user_id,))
        cur.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user_id, token_hash, expires_at, now),
        )
        cur.execute(
            "INSERT INTO audit_log (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (user_id, "login_success", "Email verification login", now),
        )
        conn.commit()
        conn.close()

    def get_user_from_session(self, session_token: str):
        if not session_token:
            return None

        token_hash = self.hash_token(session_token)
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.*
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
            ORDER BY s.id DESC
            LIMIT 1
            """,
            (token_hash,),
        )
        user = cur.fetchone()
        if not user:
            conn.close()
            return None

        cur.execute(
            "SELECT expires_at FROM sessions WHERE token_hash = ? ORDER BY id DESC LIMIT 1",
            (token_hash,),
        )
        sess = cur.fetchone()
        conn.close()

        if not sess:
            return None

        exp_dt = datetime.strptime(sess["expires_at"], "%Y-%m-%d %H:%M:%S")
        if exp_dt < datetime.now(timezone.utc).replace(tzinfo=None):
            return None
        return user

    def log_inspection(
        self,
        user_id: int,
        image_name: str,
        image_path: str,
        pdf_path: str,
        total: int,
        high: int,
        report_text: str,
        llm_prompt_tokens: int = 0,
        llm_completion_tokens: int = 0,
        llm_total_tokens: int = 0,
        llm_cost_inr: float = 0.0,
    ) -> None:
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO inspections (
                user_id,
                image_name,
                image_path,
                pdf_path,
                total_cracks,
                high_severity,
                llm_prompt_tokens,
                llm_completion_tokens,
                llm_total_tokens,
                llm_cost_inr,
                report_text,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                image_name,
                image_path,
                pdf_path,
                total,
                high,
                int(llm_prompt_tokens),
                int(llm_completion_tokens),
                int(llm_total_tokens),
                float(llm_cost_inr),
                report_text,
                self.utc_now_str(),
            ),
        )
        conn.commit()
        conn.close()

    def recent_inspections(self, user_id: int, limit: int = 5):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT image_name, total_cracks, high_severity, llm_total_tokens, llm_cost_inr, created_at FROM inspections WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    def inspection_history(self, user_id: int, image_query: str = "", min_high: int = 0, start_date=None, end_date=None):
        where_clauses = ["user_id = ?"]
        params = [user_id]

        if image_query:
            where_clauses.append("LOWER(image_name) LIKE ?")
            params.append(f"%{image_query.lower()}%")

        where_clauses.append("high_severity >= ?")
        params.append(int(min_high))

        if start_date:
            where_clauses.append("created_at >= ?")
            params.append(f"{start_date.strftime('%Y-%m-%d')} 00:00:00")
        if end_date:
            where_clauses.append("created_at <= ?")
            params.append(f"{end_date.strftime('%Y-%m-%d')} 23:59:59")

        where_sql = " AND ".join(where_clauses)

        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, image_name, total_cracks, high_severity, llm_total_tokens, llm_cost_inr, created_at, pdf_path
            FROM inspections
            WHERE {where_sql}
            ORDER BY id DESC
            """,
            tuple(params),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    def list_users_for_admin(self):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, full_name, email, role, is_verified, created_at FROM users ORDER BY id DESC")
        rows = cur.fetchall()
        conn.close()
        return rows

    def log_llm_usage(self, user_id: int, llm_name: str, tokens_used: int = 0) -> None:
        """Log LLM usage for a user (ChatGPT, Claude, Gemini, etc.)"""
        now = self.utc_now_str()
        conn = self.get_conn()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT id, usage_count, tokens_used FROM llm_usage WHERE user_id = ? AND llm_name = ?",
            (user_id, llm_name)
        )
        row = cur.fetchone()
        
        if row:
            new_count = row["usage_count"] + 1
            new_tokens = row["tokens_used"] + tokens_used
            cur.execute(
                """
                UPDATE llm_usage 
                SET usage_count = ?, tokens_used = ?, last_used = ?, updated_at = ?
                WHERE user_id = ? AND llm_name = ?
                """,
                (new_count, new_tokens, now, now, user_id, llm_name)
            )
        else:
            cur.execute(
                """
                INSERT INTO llm_usage (user_id, llm_name, usage_count, tokens_used, last_used, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, ?, ?)
                """,
                (user_id, llm_name, tokens_used, now, now, now)
            )
        conn.commit()
        conn.close()

    def get_user_llm_stats(self, user_id: int) -> list:
        """Get LLM usage statistics for a user"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT llm_name, usage_count, tokens_used, last_used, created_at
            FROM llm_usage
            WHERE user_id = ?
            ORDER BY usage_count DESC
            """,
            (user_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    def get_users_by_college_with_llm_stats(self, college: str = None):
        """Get all users (optionally filtered by college) with their LLM usage stats"""
        conn = self.get_conn()
        cur = conn.cursor()
        
        if college:
            cur.execute(
                """
                SELECT 
                    u.*,
                    COALESCE(l.total_llm_calls, 0) as total_llm_calls,
                    COALESCE(l.total_tokens, 0) as total_tokens,
                    COALESCE(l.distinct_llms, 0) as distinct_llms,
                    COALESCE(l.llm_breakdown, '') as llm_breakdown,
                    COALESCE(i.total_prompt_tokens, 0) as total_prompt_tokens,
                    COALESCE(i.total_completion_tokens, 0) as total_completion_tokens,
                    COALESCE(i.inspection_total_tokens, 0) as inspection_total_tokens,
                    COALESCE(i.inspection_total_cost_inr, 0) as inspection_total_cost_inr
                FROM users u
                LEFT JOIN (
                    SELECT
                        user_id,
                        SUM(usage_count) as total_llm_calls,
                        SUM(tokens_used) as total_tokens,
                        COUNT(DISTINCT llm_name) as distinct_llms,
                        GROUP_CONCAT(llm_name || ':' || usage_count, '; ') as llm_breakdown
                    FROM llm_usage
                    GROUP BY user_id
                ) l ON u.id = l.user_id
                LEFT JOIN (
                    SELECT
                        user_id,
                        SUM(llm_prompt_tokens) as total_prompt_tokens,
                        SUM(llm_completion_tokens) as total_completion_tokens,
                        SUM(llm_total_tokens) as inspection_total_tokens,
                        SUM(llm_cost_inr) as inspection_total_cost_inr
                    FROM inspections
                    GROUP BY user_id
                ) i ON u.id = i.user_id
                WHERE u.college = ?
                ORDER BY u.full_name
                """,
                (college,)
            )
        else:
            cur.execute(
                """
                SELECT 
                    u.*,
                    COALESCE(l.total_llm_calls, 0) as total_llm_calls,
                    COALESCE(l.total_tokens, 0) as total_tokens,
                    COALESCE(l.distinct_llms, 0) as distinct_llms,
                    COALESCE(l.llm_breakdown, '') as llm_breakdown,
                    COALESCE(i.total_prompt_tokens, 0) as total_prompt_tokens,
                    COALESCE(i.total_completion_tokens, 0) as total_completion_tokens,
                    COALESCE(i.inspection_total_tokens, 0) as inspection_total_tokens,
                    COALESCE(i.inspection_total_cost_inr, 0) as inspection_total_cost_inr
                FROM users u
                LEFT JOIN (
                    SELECT
                        user_id,
                        SUM(usage_count) as total_llm_calls,
                        SUM(tokens_used) as total_tokens,
                        COUNT(DISTINCT llm_name) as distinct_llms,
                        GROUP_CONCAT(llm_name || ':' || usage_count, '; ') as llm_breakdown
                    FROM llm_usage
                    GROUP BY user_id
                ) l ON u.id = l.user_id
                LEFT JOIN (
                    SELECT
                        user_id,
                        SUM(llm_prompt_tokens) as total_prompt_tokens,
                        SUM(llm_completion_tokens) as total_completion_tokens,
                        SUM(llm_total_tokens) as inspection_total_tokens,
                        SUM(llm_cost_inr) as inspection_total_cost_inr
                    FROM inspections
                    GROUP BY user_id
                ) i ON u.id = i.user_id
                ORDER BY u.college, u.full_name
                """
            )
        rows = cur.fetchall()
        conn.close()
        return rows

    def get_all_colleges(self):
        """Get list of unique colleges"""
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT college FROM users 
            WHERE college IS NOT NULL AND college <> ''
            ORDER BY college
            """
        )
        rows = cur.fetchall()
        conn.close()
        return [row["college"] for row in rows]

    def get_llm_usage_summary(self):
        """Get overall LLM usage statistics across all users"""
        conn = self.get_conn()
        cur = conn.cursor()
        
        cur.execute(
            """
            SELECT 
                llm_name,
                COUNT(DISTINCT user_id) as num_users,
                SUM(usage_count) as total_calls,
                SUM(tokens_used) as total_tokens,
                AVG(usage_count) as avg_calls_per_user
            FROM llm_usage
            GROUP BY llm_name
            ORDER BY total_calls DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    def export_users_to_list(self, college: str = None) -> list[dict]:
        """Export users data to list of dictionaries for CSV/Excel export"""
        rows = self.get_users_by_college_with_llm_stats(college)
        result = []
        for row in rows:
            result.append({
                'ID': row['id'],
                'First Name': row['first_name'],
                'Last Name': row['last_name'],
                'Full Name': row['full_name'],
                'Email': row['email'],
                'Mobile': row['mobile'],
                'College': row['college'],
                'Profession': row['profession'],
                'Python Knowledge': row['python_knowledge'],
                'AI Tool Usage': row['ai_tool_usage'],
                'AI Awareness': row['ai_awareness'],
                'Role': row['role'],
                'Verified': 'Yes' if row['is_verified'] else 'No',
                'Registration Completed': 'Yes' if row['registration_completed'] else 'No',
                'Registration Date': row['created_at'],
                'Last Updated': row['updated_at'],
                'Total LLM Calls': row['total_llm_calls'],
                'Total Tokens': row['total_tokens'],
                'Distinct LLMs Used': row['distinct_llms'],
                'LLM Breakdown': row['llm_breakdown'] or 'None',
                'Inspection Prompt Tokens': row['total_prompt_tokens'],
                'Inspection Completion Tokens': row['total_completion_tokens'],
                'Inspection Total Tokens': row['inspection_total_tokens'],
                'Inspection Total Cost (INR)': float(row['inspection_total_cost_inr'] or 0),
            })
        return result
