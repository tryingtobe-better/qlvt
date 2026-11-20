"""
Xử lý nghiệp vụ Danh mục Nhân viên (`dbo.Nhanvien`):
Gọi các Stored Procedure trong `sql/04_danh_muc.sql`:
- `dbo.SP_DanhSachNhanVien`, `dbo.SP_ChiTietNhanVien`
- `dbo.SP_ThemNhanVien`, `dbo.SP_SuaNhanVien`, `dbo.SP_XoaNhanVien`, `dbo.SP_DoiTrangThaiNhanVien`
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from qlvt.database import db
from qlvt.services.common import (
    UndoAction,
    UndoMixin,
    normalize_spaces,
    parse_money,
    parse_required_date,
    title_case_vn,
)


class NhanVienService(UndoMixin):
    """Dịch vụ quản lý Danh mục Nhân viên gọi Stored Procedures từ SQL Server."""

    def __init__(self) -> None:
        self._init_undo()

    def list_all(self, keyword: str = "") -> List[Dict[str, Any]]:
        """Gọi `dbo.SP_DanhSachNhanVien` lấy danh sách toàn bộ nhân viên theo từ khóa."""
        kw = normalize_spaces(keyword)
        return db.fetch_all("EXEC dbo.SP_DanhSachNhanVien @TuKhoa = ?", (kw,))

    def get_by_id(self, manv: int | str) -> Optional[Dict[str, Any]]:
        """Gọi `dbo.SP_ChiTietNhanVien` lấy thông tin 1 nhân viên theo `MANV`."""
        return db.fetch_one("EXEC dbo.SP_ChiTietNhanVien @MANV = ?", (int(manv),))

    def _validate_fields(
        self,
        manv: int | str,
        ho: str,
        ten: str,
        ngaysinh: Optional[str | date],
        luong: float | str,
    ) -> Tuple[int, str, str, str, float]:
        """Kiểm tra tính hợp lệ của Mã NV, Họ, Tên, Ngày sinh (18..65 tuổi) và Lương (>= 5,000,000)."""
        try:
            manv_int = int(str(manv).strip())
        except ValueError as exc:
            raise ValueError("Mã nhân viên phải là số nguyên!") from exc
        if manv_int <= 0:
            raise ValueError("Mã nhân viên phải lớn hơn 0!")

        ho_clean = title_case_vn(ho)
        if not ho_clean:
            raise ValueError("Họ và tên đệm nhân viên không được để trống!")
        if len(ho_clean) > 40:
            raise ValueError("Họ và tên đệm tối đa 40 ký tự!")
        if not all(word.isalpha() for word in ho_clean.split(" ")):
            raise ValueError("Họ và tên đệm chỉ được chứa chữ cái, không chứa số hoặc ký tự đặc biệt!")

        ten_clean = title_case_vn(ten)
        if not ten_clean:
            raise ValueError("Tên nhân viên không được để trống!")
        if " " in ten_clean:
            raise ValueError("Ô 'Tên' chỉ nhập 1 từ tên chính (tên đệm vui lòng nhập ở ô Họ và tên đệm)!")
        if len(ten_clean) > 10:
            raise ValueError("Tên nhân viên tối đa 10 ký tự!")
        if not ten_clean.isalpha():
            raise ValueError("Tên nhân viên chỉ được chứa chữ cái, không chứa số hoặc ký tự đặc biệt!")

        dob = parse_required_date(ngaysinh, "Ngày sinh")
        today = date.today()
        if dob > today:
            raise ValueError("Ngày sinh không được lớn hơn ngày hiện tại!")
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            raise ValueError(
                f"Nhân viên chưa đủ độ tuổi lao động (phải từ 18 tuổi trở lên, hiện tại mới {age} tuổi)!"
            )
        if age > 65:
            raise ValueError(
                f"Ngày sinh không hợp lệ (độ tuổi lao động tối đa 65 tuổi, hiện tại {age} tuổi)!"
            )

        luong_val = parse_money(luong, "Mức lương")
        if luong_val < 5000000:
            raise ValueError("Lương nhân viên phải từ 5.000.000 đ trở lên!")

        return manv_int, ho_clean, ten_clean, dob.isoformat(), luong_val

    @staticmethod
    def _validate_address(diachi: Optional[str]) -> str:
        """Kiểm tra và chuẩn hóa chuỗi địa chỉ nhân viên."""
        clean = normalize_spaces(diachi)
        if not clean:
            raise ValueError("Địa chỉ nhân viên không được để trống!")
        if len(clean) > 100:
            raise ValueError("Địa chỉ nhân viên tối đa 100 ký tự!")
        allowed_punct = set(",./-() ")
        if not all(ch.isalnum() or ch in allowed_punct for ch in clean):
            raise ValueError(
                "Địa chỉ chỉ được chứa chữ cái, chữ số và các dấu (, . / -), không chứa ký tự đặc biệt!"
            )
        if not any(ch.isalpha() for ch in clean):
            raise ValueError(
                "Địa chỉ phải có tên đường hoặc khu vực (không được chỉ nhập số hoặc dấu câu)!"
            )
        return clean

    def create(
        self,
        manv: int | str,
        ho: str,
        ten: str,
        diachi: Optional[str] = None,
        ngaysinh: Optional[str | date] = None,
        luong: float | str = 5000000,
        ghichu: Optional[str] = None,
    ) -> None:
        """Gọi `dbo.SP_ThemNhanVien` thêm mới nhân viên và lưu `SP_XoaNhanVien` vào `undo_stack`."""
        manv_int, ho_clean, ten_clean, dob_str, luong_val = self._validate_fields(
            manv, ho, ten, ngaysinh, luong
        )
        if self.get_by_id(manv_int) is not None:
            raise ValueError(f"Mã nhân viên {manv_int} đã tồn tại!")

        diachi_val = self._validate_address(diachi)
        ghichu_val = normalize_spaces(ghichu) or None

        db.execute(
            "EXEC dbo.SP_ThemNhanVien @MANV = ?, @HO = ?, @TEN = ?, @DIACHI = ?, @NGAYSINH = ?, @LUONG = ?, @GHICHU = ?, @TrangThaiXoa = 0",
            (manv_int, ho_clean, ten_clean, diachi_val, dob_str, luong_val, ghichu_val),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_XoaNhanVien @MANV = ?",
                params=(manv_int,),
                description=f"Hoàn tác thêm nhân viên mã {manv_int} ({ho_clean} {ten_clean})",
                target_id=str(manv_int),
            )
        )

    def update(
        self,
        manv: int | str,
        ho: str,
        ten: str,
        diachi: Optional[str] = None,
        ngaysinh: Optional[str | date] = None,
        luong: float | str = 5000000,
        ghichu: Optional[str] = None,
    ) -> None:
        """Gọi `dbo.SP_SuaNhanVien` cập nhật hồ sơ nhân viên và lưu bản ghi cũ vào `undo_stack`."""
        manv_int, ho_clean, ten_clean, dob_str, luong_val = self._validate_fields(
            manv, ho, ten, ngaysinh, luong
        )
        old_row = self.get_by_id(manv_int)
        if old_row is None:
            raise ValueError(f"Không tìm thấy nhân viên mã {manv_int} để cập nhật!")

        diachi_val = self._validate_address(diachi)
        ghichu_val = normalize_spaces(ghichu) or None

        db.execute(
            "EXEC dbo.SP_SuaNhanVien @MANV = ?, @HO = ?, @TEN = ?, @DIACHI = ?, @NGAYSINH = ?, @LUONG = ?, @GHICHU = ?",
            (manv_int, ho_clean, ten_clean, diachi_val, dob_str, luong_val, ghichu_val),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_SuaNhanVien @MANV = ?, @HO = ?, @TEN = ?, @DIACHI = ?, @NGAYSINH = ?, @LUONG = ?, @GHICHU = ?",
                params=(
                    manv_int,
                    old_row["HO"],
                    old_row["TEN"],
                    old_row["DIACHI"],
                    old_row["NGAYSINH"],
                    old_row["LUONG"],
                    old_row["GHICHU"],
                ),
                description=f"Hoàn tác sửa nhân viên mã {manv_int} ({old_row['HO']} {old_row['TEN']})",
            )
        )

    def delete(self, manv: int | str, current_manv: Optional[int | str] = None) -> None:
        """Kiểm tra điều kiện xóa từ `dbo.SP_ChiTietNhanVien` và gọi `dbo.SP_XoaNhanVien` xóa nhân viên."""
        manv_int = int(str(manv).strip())
        if current_manv is not None and str(current_manv).strip() != "":
            if int(str(current_manv).strip()) == manv_int:
                raise ValueError("Không thể xóa hồ sơ của chính nhân viên đang đăng nhập!")

        old_row = self.get_by_id(manv_int)
        if old_row is None:
            raise ValueError(f"Không tìm thấy nhân viên mã {manv_int} để xóa!")

        if int(old_row.get("CoTheXoa") or 0) == 0:
            reason = (
                "nhân viên đã lập chứng từ kho"
                if int(old_row.get("SoPhieuDaLap") or 0) > 0
                else "nhân viên đang có tài khoản đăng nhập"
            )
            raise ValueError(
                f"Không thể xóa vì {reason}. Vui lòng dùng chức năng 'Nghỉ việc' để giữ nguyên lịch sử chứng từ."
            )

        db.execute("EXEC dbo.SP_XoaNhanVien @MANV = ?", (manv_int,))

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_ThemNhanVien @MANV = ?, @HO = ?, @TEN = ?, @DIACHI = ?, @NGAYSINH = ?, @LUONG = ?, @GHICHU = ?, @TrangThaiXoa = ?",
                params=(
                    old_row["MANV"],
                    old_row["HO"],
                    old_row["TEN"],
                    old_row["DIACHI"],
                    old_row["NGAYSINH"],
                    old_row["LUONG"],
                    old_row["GHICHU"],
                    int(old_row["TrangThaiXoa"]),
                ),
                description=f"Khôi phục nhân viên đã xóa mã {manv_int} ({old_row['HO']} {old_row['TEN']})",
            )
        )

    def set_work_status(
        self,
        manv: int | str,
        resigned: bool,
        current_manv: Optional[int | str] = None,
    ) -> None:
        """Gọi `dbo.SP_DoiTrangThaiNhanVien` chuyển trạng thái làm việc của nhân viên."""
        manv_int = int(str(manv).strip())
        if resigned and current_manv is not None and str(current_manv).strip() != "":
            if int(str(current_manv).strip()) == manv_int:
                raise ValueError("Không thể chuyển trạng thái nghỉ việc cho chính tài khoản đang đăng nhập!")

        old_row = self.get_by_id(manv_int)
        if old_row is None:
            raise ValueError(f"Không tìm thấy nhân viên mã {manv_int}!")

        new_val = 1 if resigned else 0
        old_val = int(old_row["TrangThaiXoa"])
        if old_val == new_val:
            return

        db.execute(
            "EXEC dbo.SP_DoiTrangThaiNhanVien @MANV = ?, @TrangThaiXoa = ?",
            (manv_int, new_val),
        )

        action_label = "nghỉ việc" if resigned else "đi làm lại"
        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_DoiTrangThaiNhanVien @MANV = ?, @TrangThaiXoa = ?",
                params=(manv_int, old_val),
                description=f"Hoàn tác chuyển {action_label} nhân viên mã {manv_int} ({old_row['HO']} {old_row['TEN']})",
            )
        )

    def undo_with_target(self) -> Tuple[str, Optional[str]]:
        """Kiểm tra an toàn trước khi hoàn tác thao tác thêm nhân viên."""
        if not self.undo_stack:
            raise ValueError("Hiện không có thao tác nào để hoàn tác!")
        action = self.undo_stack[-1]
        if "SP_XOANHANVIEN" in action.sql.upper() and action.params:
            manv_target = int(action.params[0])
            row = self.get_by_id(manv_target)
            if row and int(row.get("CoTheXoa") or 0) == 0:
                self.undo_stack.pop()
                raise ValueError(
                    f"Không thể hoàn tác thao tác thêm nhân viên mã {manv_target} vì nhân viên đã phát sinh chứng từ hoặc tài khoản!"
                )
        return super().undo_with_target()


nhan_vien_service = NhanVienService()
