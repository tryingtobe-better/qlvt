"""
Quản lý cấu hình môi trường và tạo chuỗi kết nối ODBC (Connection String) tới SQL Server.
Đọc thông số từ file `.env` (hoặc dùng giá trị mặc định cho Server `LAPTOP-M19TS03A`, Database `QLVT`).
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME = os.getenv("DB_NAME", "QLVT")
DB_ENCRYPT = os.getenv("DB_ENCRYPT", "yes")
DB_TRUST_CERT = os.getenv("DB_TRUST_CERT", "yes")


def build_connection_string(
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Xây dựng chuỗi kết nối pyodbc tới SQL Server:
    - Nếu có `username`: Kết nối bằng tài khoản SQL Server Authentication (UID/PWD) của người dùng đăng nhập.
    - Nếu không có `username`: Kết nối bằng Windows Authentication (Trusted_Connection=yes).
    """
    parts = [
        f"DRIVER={{{DB_DRIVER}}}",
        f"SERVER={DB_SERVER}",
        f"DATABASE={DB_NAME}",
        f"Encrypt={DB_ENCRYPT}",
        f"TrustServerCertificate={DB_TRUST_CERT}",
    ]

    if username:
        parts.append(f"UID={username}")
        parts.append(f"PWD={password or ''}")
    else:
        parts.append("Trusted_Connection=yes")

    return ";".join(parts) + ";"
