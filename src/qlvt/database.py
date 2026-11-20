"""
Tầng truy xuất cơ sở dữ liệu (Data Access Layer) qua thư viện `pyodbc`.
Cung cấp lớp `DatabaseManager` quản lý kết nối động theo tài khoản đăng nhập
và các hàm tiện ích gọi Stored Procedures (`fetch_all`, `fetch_one`, `execute`, `session`).
"""

from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Sequence

import pyodbc

from qlvt import config


class DatabaseManager:
    """Quản lý kết nối và thực thi các Stored Procedure trên Microsoft SQL Server."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.username = username
        self.password = password

    @property
    def connection_string(self) -> str:
        """Lấy chuỗi kết nối ODBC ứng với tài khoản đang đăng nhập hiện tại."""
        return config.build_connection_string(
            username=self.username,
            password=self.password,
        )

    def set_credentials(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Cập nhật thông tin tài khoản SQL Login khi người dùng đăng nhập hoặc đăng xuất."""
        self.username = username
        self.password = password

    def connect(self, autocommit: bool = False, timeout: int = 5) -> pyodbc.Connection:
        """Mở một kết nối mới tới SQL Server."""
        return pyodbc.connect(
            self.connection_string,
            autocommit=autocommit,
            timeout=timeout,
        )

    @contextmanager
    def session(self, autocommit: bool = False) -> Generator[pyodbc.Connection, None, None]:
        """
        Context manager quản lý phiên kết nối và giao dịch (Transaction):
        - Tự động `commit()` khi khối lệnh hoàn tất thành công.
        - Tự động `rollback()` nếu xảy ra lỗi và đóng kết nối an toàn.
        """
        conn = self.connect(autocommit=autocommit)
        try:
            yield conn
            if not autocommit:
                conn.commit()
        except Exception:
            if not autocommit:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            conn.close()

    def fetch_all(
        self, query: str, params: Optional[Sequence[Any]] = None
    ) -> List[Dict[str, Any]]:
        """Thực thi Stored Procedure truy vấn và trả về danh sách các dòng dạng `dict`."""
        with self.session(autocommit=True) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if cursor.description is None:
                return []
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def fetch_one(
        self, query: str, params: Optional[Sequence[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Thực thi Stored Procedure và trả về dòng đầu tiên dạng `dict` (hoặc `None`)."""
        with self.session(autocommit=True) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if cursor.description is None:
                return None
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()
            return dict(zip(columns, row)) if row else None

    def execute(
        self, query: str, params: Optional[Sequence[Any]] = None
    ) -> int:
        """Thực thi Stored Procedure cập nhật dữ liệu và trả về số dòng bị ảnh hưởng."""
        with self.session(autocommit=False) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.rowcount


db = DatabaseManager()
