"""
Các hàm tiện ích và Decorator bảo vệ route dùng chung cho tầng Web:
- `@login_required`: Yêu cầu người dùng đã đăng nhập mới được truy cập trang.
- `@admin_required`: Chỉ cho phép nhóm quyền `Admin` truy cập (Quản lý tài khoản, Sao lưu CSDL).
- `next_manv`, `next_code`: Gợi ý mã nhân viên / mã vật tư / mã chứng từ kế tiếp.
"""

from functools import wraps
import re
from typing import Any, Callable, Dict, List

from flask import flash, redirect, url_for

from qlvt.services import auth_service


def login_required(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator kiểm tra đăng nhập; nếu chưa đăng nhập sẽ chuyển hướng về `/login`."""
    @wraps(view_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if auth_service.current_user is None:
            flash("Vui lòng đăng nhập để sử dụng hệ thống!", "info")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator kiểm tra quyền Quản trị viên (`Admin`); trả về lỗi 403 nếu là `NhanVien`."""
    @wraps(view_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if auth_service.current_user is None:
            flash("Vui lòng đăng nhập để sử dụng hệ thống!", "info")
            return redirect(url_for("login"))
        if not auth_service.current_user.is_admin:
            flash("Chỉ Quản trị viên mới có quyền thực hiện chức năng này.", "error")
            return redirect(url_for("dashboard")), 403
        return view_func(*args, **kwargs)

    return wrapper


def next_manv(rows: List[Dict[str, Any]]) -> int:
    """Gợi ý mã nhân viên số nguyên kế tiếp (`max(MANV) + 1`)."""
    if not rows:
        return 1
    return max(int(r["MANV"]) for r in rows) + 1


def next_code(rows: List[Dict[str, Any]], key: str, prefix: str, width: int) -> str:
    """Gợi ý mã tự tăng có tiền tố (ví dụ: `VT01` -> `VT02`, `DDH00001` -> `DDH00002`)."""
    max_num = 0
    for r in rows:
        val = str(r.get(key, "")).strip().upper()
        match = re.match(rf"^{re.escape(prefix)}(\d+)$", val)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"{prefix}{max_num + 1:0{width}d}"
