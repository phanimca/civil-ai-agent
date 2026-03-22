from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone


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

        cur.execute(
            """
            UPDATE users
            SET full_name = TRIM(COALESCE(full_name, '')),
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

        conn.commit()
        conn.close()

    @staticmethod
    def normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_or_update_user(self, full_name: str, email: str, mobile: str, college: str) -> int:
        email = self.normalize_email(email)
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
                college.strip(),
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

    def log_inspection(self, user_id: int, image_name: str, image_path: str, pdf_path: str, total: int, high: int, report_text: str) -> None:
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO inspections (user_id, image_name, image_path, pdf_path, total_cracks, high_severity, report_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, image_name, image_path, pdf_path, total, high, report_text, self.utc_now_str()),
        )
        conn.commit()
        conn.close()

    def recent_inspections(self, user_id: int, limit: int = 5):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT image_name, total_cracks, high_severity, created_at FROM inspections WHERE user_id = ? ORDER BY id DESC LIMIT ?",
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
            SELECT id, image_name, total_cracks, high_severity, created_at, pdf_path
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
                    u.id, u.full_name, u.email, u.college, u.profession, 
                    u.ai_tool_usage, u.is_verified, u.created_at,
                    COALESCE(SUM(l.usage_count), 0) as total_llm_calls,
                    COALESCE(SUM(l.tokens_used), 0) as total_tokens,
                    COUNT(DISTINCT l.llm_name) as distinct_llms,
                    GROUP_CONCAT(l.llm_name || ':' || l.usage_count, '; ') as llm_breakdown
                FROM users u
                LEFT JOIN llm_usage l ON u.id = l.user_id
                WHERE u.college = ?
                GROUP BY u.id
                ORDER BY u.full_name
                """,
                (college,)
            )
        else:
            cur.execute(
                """
                SELECT 
                    u.id, u.full_name, u.email, u.college, u.profession, 
                    u.ai_tool_usage, u.is_verified, u.created_at,
                    COALESCE(SUM(l.usage_count), 0) as total_llm_calls,
                    COALESCE(SUM(l.tokens_used), 0) as total_tokens,
                    COUNT(DISTINCT l.llm_name) as distinct_llms,
                    GROUP_CONCAT(l.llm_name || ':' || l.usage_count, '; ') as llm_breakdown
                FROM users u
                LEFT JOIN llm_usage l ON u.id = l.user_id
                GROUP BY u.id
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
                'Full Name': row['full_name'],
                'Email': row['email'],
                'College': row['college'],
                'Profession': row['profession'],
                'AI Tool Usage': row['ai_tool_usage'],
                'Verified': 'Yes' if row['is_verified'] else 'No',
                'Registration Date': row['created_at'],
                'Total LLM Calls': row['total_llm_calls'],
                'Total Tokens': row['total_tokens'],
                'Distinct LLMs Used': row['distinct_llms'],
                'LLM Breakdown': row['llm_breakdown'] or 'None'
            })
        return result
