"""
Điểm khởi chạy chính (Entry Point) của ứng dụng Web Quản Lý Vật Tư (QLVT).
Chạy lệnh `python main.py` để khởi động máy chủ Flask tại http://127.0.0.1:5000.
"""

import sys
from pathlib import Path

# Thêm thư mục `src/` vào sys.path để import gói `qlvt`
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from qlvt.web import run_app  # noqa: E402


def main() -> None:
    """Cấu hình chuẩn mã hóa UTF-8 cho console trên Windows và khởi chạy Flask server."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    run_app()


if __name__ == "__main__":
    main()
