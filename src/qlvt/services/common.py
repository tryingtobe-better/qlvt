"""
Các hàm tiện ích dùng chung cho tầng nghiệp vụ (Services):
- Chuẩn hóa chuỗi tiếng Việt (`normalize_spaces`, `capitalize_first`, `title_case_vn`).
- Kiểm tra định dạng ngày tháng, số tiền và mã chứng từ (`parse_required_date`, `parse_voucher_date`, `parse_money`, `parse_positive_int`, `validate_voucher_code`).
- Kiểm tra nhân viên lập chứng từ còn đang làm việc và đã có tài khoản qua `dbo.SP_ChiTietNhanVien`.
- Cơ chế hoàn tác nhiều bước (`UndoAction`, `UndoMixin`) gọi lại các Stored Procedure hoàn tác.
"""

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any, List, Optional, Tuple

from qlvt.database import db


def normalize_spaces(text: Optional[str]) -> str:
    """Loại bỏ khoảng trắng thừa ở 2 đầu và giữa các từ."""
    return " ".join((text or "").strip().split())


def capitalize_first(text: Optional[str]) -> str:
    """Chuẩn hóa khoảng trắng và viết hoa chữ cái đầu tiên của chuỗi (dùng cho Tên vật tư, ĐVT)."""
    clean = normalize_spaces(text)
    if not clean:
        return ""
    return clean[0].upper() + clean[1:]


def title_case_vn(text: Optional[str]) -> str:
    """Viết hoa chữ cái đầu mỗi từ (dùng cho Họ và Tên nhân viên)."""
    words = normalize_spaces(text).split(" ")
    return " ".join((w[0].upper() + w[1:].lower()) if w else "" for w in words if w)


def parse_required_date(val: str | date | None, field_label: str) -> date:
    """Chuyển đổi và kiểm tra trường ngày bắt buộc theo định dạng YYYY-MM-DD."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    raw = (str(val) if val is not None else "").strip()
    if not raw:
        raise ValueError(f"{field_label} không được để trống!")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise ValueError(f"{field_label} không đúng định dạng YYYY-MM-DD!") from exc


def parse_voucher_date(val: str | date | None, field_label: str) -> date:
    """Phân tích ngày chứng từ; nếu bỏ trống thì mặc định lấy ngày hiện tại."""
    if val is None or str(val).strip() == "":
        return date.today()
    return parse_required_date(val, field_label)


def validate_voucher_code(raw_code: Optional[str], field_label: str) -> str:
    """Kiểm tra mã chứng từ (MasoDDH, MAPN, MAPX): tối đa 8 ký tự chữ/số không dấu."""
    code = (raw_code or "").strip().upper()
    if not code or len(code) > 8:
        raise ValueError(f"{field_label} không được để trống và tối đa 8 ký tự!")
    if not re.match(r"^[A-Z0-9]{1,8}$", code):
        raise ValueError(
            f"{field_label} chỉ được chứa chữ cái không dấu (A-Z) và chữ số (0-9), không có khoảng trắng!"
        )
    return code


def parse_money(val: Any, field_label: str = "Đơn giá") -> float:
    """Chuyển đổi chuỗi số tiền có dấu chấm/phẩy phân cách hàng nghìn (VD: '1.150.000') sang float."""
    if isinstance(val, (int, float)):
        return float(val)
    raw = str(val or "").strip().replace(" ", "").replace(".", "").replace(",", "")
    if not raw:
        raise ValueError(f"{field_label} không được để trống!")
    try:
        num = float(raw)
    except ValueError as exc:
        raise ValueError(f"{field_label} phải là số tiền hợp lệ!") from exc
    return num


def parse_positive_int(val: Any, field_label: str = "Số lượng") -> int:
    """Chuyển đổi chuỗi số lượng (có thể kèm dấu chấm phân cách) sang số nguyên dương."""
    if isinstance(val, int):
        return val
    raw = str(val or "").strip().replace(" ", "").replace(".", "").replace(",", "")
    if not raw:
        raise ValueError(f"{field_label} không được để trống!")
    try:
        num = int(raw)
    except ValueError as exc:
        raise ValueError(f"{field_label} phải là số nguyên hợp lệ!") from exc
    return num


def ensure_active_employee(manv: int | str) -> int:
    """Gọi `dbo.SP_ChiTietNhanVien` để đảm bảo nhân viên lập phiếu đang làm việc (`TrangThaiXoa = 0`) và đã có tài khoản (`CoTaiKhoan = 1`)."""
    try:
        manv_int = int(str(manv).strip())
    except ValueError as exc:
        raise ValueError("Mã nhân viên lập phiếu không hợp lệ!") from exc

    emp = db.fetch_one("EXEC dbo.SP_ChiTietNhanVien @MANV = ?", (manv_int,))
    if emp is None:
        raise ValueError(f"Không tìm thấy nhân viên mã {manv_int}!")
    if int(emp["TrangThaiXoa"]) == 1:
        raise ValueError(
            f"Nhân viên '{emp['HoTen']}' (Mã {manv_int}) đã nghỉ việc, không được phép lập chứng từ mới!"
        )
    if int(emp.get("CoTaiKhoan", 1)) == 0:
        raise ValueError(
            f"Nhân viên '{emp['HoTen']}' (Mã {manv_int}) chưa được cấp tài khoản đăng nhập nên không thể lập chứng từ!"
        )
    return manv_int


@dataclass
class UndoAction:
    """Lưu trữ một hành động hoàn tác (gọi 1 hoặc nhiều Stored Procedure trong 1 giao tác)."""

    sql: str = ""
    params: Tuple[Any, ...] = ()
    description: str = ""
    steps: Optional[List[Tuple[str, Tuple[Any, ...]]]] = None
    target_id: Optional[str] = None

    def get_steps(self) -> List[Tuple[str, Tuple[Any, ...]]]:
        if self.steps is not None:
            return self.steps
        if self.sql:
            return [(self.sql, self.params)]
        return []


class UndoMixin:
    """
    Mixin cung cấp chức năng Phục hồi (Undo) nhiều bước cho các Service danh mục & chứng từ.
    Mỗi khi Thêm / Xóa / Sửa thành công, lời gọi Stored Procedure ngược lại được đẩy vào `undo_stack`.
    """

    undo_stack: List[UndoAction]

    def _init_undo(self) -> None:
        self.undo_stack = []

    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    @property
    def undo_count(self) -> int:
        return len(self.undo_stack)

    @property
    def next_undo_description(self) -> Optional[str]:
        return self.undo_stack[-1].description if self.undo_stack else None

    def undo_with_target(self) -> Tuple[str, Optional[str]]:
        """Thực thi hành động hoàn tác mới nhất trên đỉnh `undo_stack` và trả về `(mô_tả, mã_phiếu_đích)`."""
        if not self.undo_stack:
            raise ValueError("Hiện không có thao tác nào để hoàn tác!")
        action = self.undo_stack[-1]
        steps = action.get_steps()
        with db.session(autocommit=False) as conn:
            cur = conn.cursor()
            for stmt, stmt_params in steps:
                cur.execute(stmt, stmt_params)
        self.undo_stack.pop()
        return action.description, action.target_id

    def undo(self) -> str:
        """Thực thi hoàn tác và chỉ trả về chuỗi mô tả."""
        desc, _ = self.undo_with_target()
        return desc
