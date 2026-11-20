"""
Xử lý nghiệp vụ Phiếu Xuất Kho (`dbo.PhieuXuat`) và Chi Tiết Phiếu Xuất (`dbo.CTPX`):
Gọi các Stored Procedure có Giao tác (Transaction) trong `sql/05_giao_dich_kho.sql`:
- `dbo.SP_DanhSachPhieuXuat`, `dbo.SP_ChiTietPhieuXuat`, `dbo.SP_DSChiTietPX`
- `dbo.SP_ThemPhieuXuat`, `dbo.SP_SuaPhieuXuat`, `dbo.SP_XoaPhieuXuat`
- `dbo.SP_ThemCTPX`, `dbo.SP_SuaCTPX`, `dbo.SP_XoaCTPX`
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from qlvt.database import db
from qlvt.services.common import (
    UndoAction,
    UndoMixin,
    ensure_active_employee,
    normalize_spaces,
    parse_money,
    parse_positive_int,
    parse_voucher_date,
    validate_voucher_code,
)


class PhieuXuatService(UndoMixin):
    """Dịch vụ quản lý Phiếu xuất kho (`PhieuXuat` - `CTPX`) gọi Stored Procedures từ SQL Server."""

    def __init__(self) -> None:
        self._init_undo()

    def list_exports(self, keyword: str = "") -> List[Dict[str, Any]]:
        """Gọi `dbo.SP_DanhSachPhieuXuat` lấy danh sách phiếu xuất kho."""
        kw = normalize_spaces(keyword)
        return db.fetch_all("EXEC dbo.SP_DanhSachPhieuXuat @TuKhoa = ?", (kw,))

    def get_export(self, mapx: str) -> Optional[Dict[str, Any]]:
        """Gọi `dbo.SP_ChiTietPhieuXuat` lấy thông tin đầu phiếu xuất kho theo `MAPX`."""
        code = (mapx or "").strip().upper()
        return db.fetch_one("EXEC dbo.SP_ChiTietPhieuXuat @MAPX = ?", (code,))

    def list_details(self, mapx: str) -> List[Dict[str, Any]]:
        """Gọi `dbo.SP_DSChiTietPX` lấy danh sách các dòng mặt hàng chi tiết của một phiếu xuất."""
        code = (mapx or "").strip().upper()
        return db.fetch_all("EXEC dbo.SP_DSChiTietPX @MAPX = ?", (code,))

    def check_modify_permission(
        self,
        export_row: Dict[str, Any],
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """Kiểm tra phiếu xuất có được phép sửa/xóa hay không (chỉ người lập phiếu hoặc Quản trị viên)."""
        if (
            not is_admin
            and current_manv is not None
            and str(current_manv).strip() != ""
            and int(export_row["MANV"]) != int(str(current_manv).strip())
        ):
            return (
                False,
                f"Chỉ người lập ({export_row['HoTenNV']}) hoặc Quản trị viên mới được chỉnh sửa",
            )
        return True, None

    def ensure_modifiable(
        self,
        mapx: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Dict[str, Any]:
        """Ném ngoại lệ `ValueError` nếu người dùng không có quyền sửa/xóa phiếu xuất `mapx`."""
        code = (mapx or "").strip().upper()
        px = self.get_export(code)
        if px is None:
            raise ValueError(f"Phiếu xuất '{code}' không tồn tại!")

        can_modify, reason = self.check_modify_permission(
            px, current_manv=current_manv, is_admin=is_admin
        )
        if not can_modify:
            raise ValueError(f"Không thể chỉnh sửa/xóa phiếu xuất '{code}': {reason}!")
        return px

    def create_export(
        self,
        mapx: str,
        ngay: str | date,
        hotenkh: str,
        manv: int | str,
    ) -> None:
        """Gọi `dbo.SP_ThemPhieuXuat` tạo mới đầu phiếu xuất kho."""
        code = validate_voucher_code(mapx, "Mã phiếu xuất")
        kh_clean = normalize_spaces(hotenkh)
        if not kh_clean:
            raise ValueError("Họ tên khách hàng / đơn vị nhận không được để trống!")
        if len(kh_clean) > 100:
            raise ValueError("Họ tên khách hàng tối đa 100 ký tự!")
        if self.get_export(code) is not None:
            raise ValueError(f"Phiếu xuất '{code}' đã tồn tại!")

        export_date = parse_voucher_date(ngay, "Ngày xuất kho")
        if export_date > date.today():
            raise ValueError("Ngày xuất kho không được lớn hơn ngày hiện tại!")

        manv_int = ensure_active_employee(manv)

        db.execute(
            "EXEC dbo.SP_ThemPhieuXuat @MAPX = ?, @NGAY = ?, @HOTENKH = ?, @MANV = ?",
            (code, export_date.isoformat(), kh_clean, manv_int),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_XoaPhieuXuat @MAPX = ?",
                params=(code,),
                description=f"Hoàn tác lập phiếu xuất '{code}' ({kh_clean})",
                target_id=None,
            )
        )

    def update_export(
        self,
        mapx: str,
        ngay: str | date,
        hotenkh: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Gọi `dbo.SP_SuaPhieuXuat` cập nhật Ngày xuất kho và Họ tên khách hàng."""
        code = (mapx or "").strip().upper()
        old_px = self.ensure_modifiable(code, current_manv=current_manv, is_admin=is_admin)

        kh_clean = normalize_spaces(hotenkh)
        if not kh_clean:
            raise ValueError("Họ tên khách hàng / đơn vị nhận không được để trống!")
        if len(kh_clean) > 100:
            raise ValueError("Họ tên khách hàng tối đa 100 ký tự!")

        export_date = parse_voucher_date(ngay, "Ngày xuất kho")
        if export_date > date.today():
            raise ValueError("Ngày xuất kho không được lớn hơn ngày hiện tại!")

        db.execute(
            "EXEC dbo.SP_SuaPhieuXuat @MAPX = ?, @NGAY = ?, @HOTENKH = ?",
            (code, export_date.isoformat(), kh_clean),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_SuaPhieuXuat @MAPX = ?, @NGAY = ?, @HOTENKH = ?",
                params=(code, old_px["NGAY"], old_px["HOTENKH"]),
                description=f"Hoàn tác sửa thông tin phiếu xuất '{code}'",
                target_id=code,
            )
        )

    def delete_export(
        self,
        mapx: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Kiểm tra quyền qua `ensure_modifiable` và gọi `dbo.SP_XoaPhieuXuat` xóa phiếu xuất (hoàn trả tồn kho)."""
        code = (mapx or "").strip().upper()
        old_px = self.ensure_modifiable(code, current_manv=current_manv, is_admin=is_admin)
        old_details = self.list_details(code)

        db.execute("EXEC dbo.SP_XoaPhieuXuat @MAPX = ?", (code,))

        restore_steps: List[Tuple[str, Tuple[Any, ...]]] = [
            (
                "EXEC dbo.SP_ThemPhieuXuat @MAPX = ?, @NGAY = ?, @HOTENKH = ?, @MANV = ?",
                (code, old_px["NGAY"], old_px["HOTENKH"], int(old_px["MANV"])),
            )
        ]
        for ct in old_details:
            restore_steps.append(
                (
                    "EXEC dbo.SP_ThemCTPX @MAPX = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                    (code, ct["MAVT"], int(ct["SOLUONG"]), float(ct["DONGIA"])),
                )
            )

        self.undo_stack.append(
            UndoAction(
                description=f"Khôi phục phiếu xuất đã xóa '{code}' ({old_px['HOTENKH']})",
                steps=restore_steps,
                target_id=code,
            )
        )

    def add_detail(
        self,
        mapx: str,
        mavt: str,
        soluong: int | str,
        dongia: float | str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Tuple[bool, int]:
        """Gọi `dbo.SP_ThemCTPX` (hoặc cộng dồn qua `dbo.SP_SuaCTPX` nếu đã có trong phiếu) và tự động trừ tồn kho."""
        px_code = (mapx or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        self.ensure_modifiable(px_code, current_manv=current_manv, is_admin=is_admin)

        sl = parse_positive_int(soluong, "Số lượng xuất")
        dg = parse_money(dongia, "Đơn giá xuất")
        if sl <= 0:
            raise ValueError("Số lượng xuất phải > 0!")
        if dg <= 0:
            raise ValueError("Đơn giá xuất phải > 0!")

        vt = db.fetch_one("EXEC dbo.SP_ChiTietVatTu @MAVT = ?", (vt_code,))
        if vt is None:
            raise ValueError(f"Vật tư '{vt_code}' không tồn tại!")

        ton_hien_tai = int(vt["Soluongton"])
        if ton_hien_tai == 0 or sl > ton_hien_tai:
            raise ValueError(
                f"Số lượng tồn kho không đủ để xuất (Vật tư {vt_code} - {vt['TENVT']} hiện tồn: {ton_hien_tai})!"
            )

        dup = db.fetch_one(
            "EXEC dbo.SP_DSChiTietPX @MAPX = ?, @MAVT = ?",
            (px_code, vt_code),
        )
        if dup:
            old_sl = int(dup["SOLUONG"])
            old_dg = float(dup["DONGIA"])
            new_sl = old_sl + sl
            db.execute(
                "EXEC dbo.SP_SuaCTPX @MAPX = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                (px_code, vt_code, new_sl, dg),
            )
            self.undo_stack.append(
                UndoAction(
                    sql="EXEC dbo.SP_SuaCTPX @MAPX = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                    params=(px_code, vt_code, old_sl, old_dg),
                    description=f"Hoàn tác cộng dồn xuất mặt hàng '{vt['TENVT']}' ({vt_code}) trong phiếu '{px_code}' (về {old_sl})",
                    target_id=px_code,
                )
            )
            return True, new_sl

        db.execute(
            "EXEC dbo.SP_ThemCTPX @MAPX = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
            (px_code, vt_code, sl, dg),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_XoaCTPX @MAPX = ?, @MAVT = ?",
                params=(px_code, vt_code),
                description=f"Hoàn tác xuất mặt hàng '{vt['TENVT']}' ({vt_code}) trong phiếu '{px_code}'",
                target_id=px_code,
            )
        )
        return False, sl

    def update_detail(
        self,
        mapx: str,
        mavt: str,
        soluong: int | str,
        dongia: float | str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Gọi `dbo.SP_SuaCTPX` cập nhật dòng chi tiết phiếu xuất và điều chỉnh tồn kho trong giao tác."""
        px_code = (mapx or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        self.ensure_modifiable(px_code, current_manv=current_manv, is_admin=is_admin)

        sl = parse_positive_int(soluong, "Số lượng xuất")
        dg = parse_money(dongia, "Đơn giá xuất")
        if sl <= 0:
            raise ValueError("Số lượng xuất phải > 0!")
        if dg <= 0:
            raise ValueError("Đơn giá xuất phải > 0!")

        old_ct = db.fetch_one(
            "EXEC dbo.SP_DSChiTietPX @MAPX = ?, @MAVT = ?",
            (px_code, vt_code),
        )
        if old_ct is None:
            raise ValueError(f"Không tìm thấy vật tư '{vt_code}' trong phiếu xuất '{px_code}'!")

        max_allow = int(old_ct["Soluongton"]) + int(old_ct["SOLUONG"])
        if sl > max_allow:
            raise ValueError(
                f"Số lượng tồn kho không đủ để xuất (Tối đa có thể xuất: {max_allow})!"
            )

        db.execute(
            "EXEC dbo.SP_SuaCTPX @MAPX = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
            (px_code, vt_code, sl, dg),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_SuaCTPX @MAPX = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                params=(px_code, vt_code, int(old_ct["SOLUONG"]), float(old_ct["DONGIA"])),
                description=f"Hoàn tác sửa mặt hàng '{old_ct['TENVT']}' ({vt_code}) trong phiếu '{px_code}'",
                target_id=px_code,
            )
        )

    def delete_detail(
        self,
        mapx: str,
        mavt: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Gọi `dbo.SP_XoaCTPX` xóa 1 dòng mặt hàng khỏi phiếu xuất và hoàn trả tồn kho trong giao tác."""
        px_code = (mapx or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        self.ensure_modifiable(px_code, current_manv=current_manv, is_admin=is_admin)

        old_ct = db.fetch_one(
            "EXEC dbo.SP_DSChiTietPX @MAPX = ?, @MAVT = ?",
            (px_code, vt_code),
        )
        if old_ct is None:
            raise ValueError(f"Không tìm thấy mặt hàng '{vt_code}' trong phiếu xuất '{px_code}'!")

        db.execute(
            "EXEC dbo.SP_XoaCTPX @MAPX = ?, @MAVT = ?",
            (px_code, vt_code),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_ThemCTPX @MAPX = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                params=(px_code, vt_code, int(old_ct["SOLUONG"]), float(old_ct["DONGIA"])),
                description=f"Khôi phục dòng '{old_ct['TENVT']}' ({vt_code}) vào phiếu xuất '{px_code}'",
                target_id=px_code,
            )
        )


phieu_xuat_service = PhieuXuatService()
