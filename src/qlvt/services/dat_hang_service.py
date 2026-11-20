"""
Xử lý nghiệp vụ Đơn Đặt Hàng (`dbo.DatHang`) và Chi Tiết Đơn Đặt Hàng (`dbo.CTDDH`):
Hỗ trợ 3 trạng thái nghiệp vụ của Đơn đặt hàng:
- `Chưa nhập`    : Được phép sửa/xóa toàn bộ đơn và chi tiết mặt hàng.
- `Nhập một phần`: Không được xóa cả đơn hoặc xóa mặt hàng đã nhập, nhưng được phép thêm mặt hàng mới,
                   sửa/xóa mặt hàng chưa nhập (`SLDaNhap = 0`), và sửa tăng số lượng đặt (`SOLUONG >= SLDaNhap`).
- `Đã nhập đủ`   : Đơn hàng đã hoàn tất nhập kho, khóa chỉnh sửa và xóa.
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


class DatHangService(UndoMixin):
    """Dịch vụ quản lý Đơn đặt hàng (`DatHang` - `CTDDH`) gọi Stored Procedures từ SQL Server."""

    def __init__(self) -> None:
        self._init_undo()

    def list_orders(self, keyword: str = "") -> List[Dict[str, Any]]:
        """Gọi `dbo.SP_DanhSachDonDatHang` lấy danh sách các đơn đặt hàng kèm trạng thái nhập."""
        kw = normalize_spaces(keyword)
        return db.fetch_all("EXEC dbo.SP_DanhSachDonDatHang @TuKhoa = ?", (kw,))

    def get_order(self, maso_ddh: str) -> Optional[Dict[str, Any]]:
        """Gọi `dbo.SP_ChiTietDonDatHang` lấy thông tin đầu đơn đặt hàng theo `MasoDDH`."""
        code = (maso_ddh or "").strip().upper()
        return db.fetch_one("EXEC dbo.SP_ChiTietDonDatHang @MasoDDH = ?", (code,))

    def list_details(self, maso_ddh: str) -> List[Dict[str, Any]]:
        """Gọi `dbo.SP_DSChiTietDDH` lấy danh sách mặt hàng chi tiết của một đơn đặt hàng."""
        code = (maso_ddh or "").strip().upper()
        return db.fetch_all("EXEC dbo.SP_DSChiTietDDH @MasoDDH = ?", (code,))

    def check_modify_permission(
        self,
        order_row: Dict[str, Any],
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """Kiểm tra đơn đặt hàng có được phép chỉnh sửa hay không (người lập/Admin và chưa nhập đủ)."""
        if (
            not is_admin
            and current_manv is not None
            and str(current_manv).strip() != ""
            and int(order_row["MANV"]) != int(str(current_manv).strip())
        ):
            return (
                False,
                f"Chỉ người lập ({order_row['HoTenNV']}) hoặc Quản trị viên mới được chỉnh sửa",
            )
        if int(order_row.get("DaNhapDu") or 0) == 1:
            return (
                False,
                "Đơn hàng đã nhập đủ toàn bộ mặt hàng nên đã khóa chỉnh sửa",
            )
        return True, None

    def ensure_editable(
        self,
        maso_ddh: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Dict[str, Any]:
        """Kiểm tra đơn đặt hàng ở trạng thái `Chưa nhập` hoặc `Nhập một phần` và đúng quyền người lập/Admin."""
        code = (maso_ddh or "").strip().upper()
        order = self.get_order(code)
        if order is None:
            raise ValueError(f"Không tìm thấy đơn đặt hàng '{code}'!")
        can_mod, reason = self.check_modify_permission(
            order, current_manv=current_manv, is_admin=is_admin
        )
        if not can_mod:
            raise ValueError(f"Không thể chỉnh sửa đơn đặt hàng '{code}': {reason}!")
        return order

    def create_order(
        self,
        maso_ddh: str,
        ngay: str | date,
        nhacc: str,
        manv: int | str,
    ) -> None:
        """Gọi `dbo.SP_ThemDonDatHang` tạo đầu đơn đặt hàng mới."""
        code = validate_voucher_code(maso_ddh, "Mã đơn đặt hàng")
        nhacc_clean = normalize_spaces(nhacc)
        if not nhacc_clean:
            raise ValueError("Tên nhà cung cấp không được để trống!")
        if len(nhacc_clean) > 100:
            raise ValueError("Tên nhà cung cấp tối đa 100 ký tự!")
        if self.get_order(code) is not None:
            raise ValueError(f"Đơn đặt hàng '{code}' đã tồn tại!")

        order_date = parse_voucher_date(ngay, "Ngày đặt hàng")
        if order_date > date.today():
            raise ValueError("Ngày đặt hàng không được lớn hơn ngày hiện tại!")

        manv_int = ensure_active_employee(manv)

        db.execute(
            "EXEC dbo.SP_ThemDonDatHang @MasoDDH = ?, @NGAY = ?, @NhaCC = ?, @MANV = ?",
            (code, order_date.isoformat(), nhacc_clean, manv_int),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_XoaDonDatHang @MasoDDH = ?",
                params=(code,),
                description=f"Hoàn tác lập đơn đặt hàng '{code}' ({nhacc_clean})",
                target_id=None,
            )
        )

    def update_order(
        self,
        maso_ddh: str,
        ngay: str | date,
        nhacc: str,
        manv: Optional[int | str] = None,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Cập nhật Ngày đặt / Nhà cung cấp của đơn đặt hàng (`Chưa nhập` hoặc `Nhập một phần`)."""
        code = (maso_ddh or "").strip().upper()
        old_order = self.ensure_editable(code, current_manv=current_manv, is_admin=is_admin)

        nhacc_clean = normalize_spaces(nhacc)
        if not nhacc_clean:
            raise ValueError("Tên nhà cung cấp không được để trống!")
        if len(nhacc_clean) > 100:
            raise ValueError("Tên nhà cung cấp tối đa 100 ký tự!")

        order_date = parse_voucher_date(ngay, "Ngày đặt hàng")
        if order_date > date.today():
            raise ValueError("Ngày đặt hàng không được lớn hơn ngày hiện tại!")

        if old_order.get("NgayNhapSomNhat"):
            earliest_import = parse_voucher_date(old_order["NgayNhapSomNhat"], "Ngày nhập kho")
            if order_date > earliest_import:
                raise ValueError(
                    f"Đơn hàng đã nhập một phần ngày {earliest_import}, ngày đặt hàng không được lớn hơn ngày nhập kho!"
                )

        manv_int = (
            ensure_active_employee(manv)
            if manv is not None and str(manv).strip() != ""
            else int(old_order["MANV"])
        )

        db.execute(
            "EXEC dbo.SP_SuaDonDatHang @MasoDDH = ?, @NGAY = ?, @NhaCC = ?, @MANV = ?",
            (code, order_date.isoformat(), nhacc_clean, manv_int),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_SuaDonDatHang @MasoDDH = ?, @NGAY = ?, @NhaCC = ?, @MANV = ?",
                params=(code, old_order["NGAY"], old_order["NhaCC"], int(old_order["MANV"])),
                description=f"Hoàn tác sửa thông tin đơn đặt hàng '{code}'",
                target_id=code,
            )
        )

    def delete_order(
        self,
        maso_ddh: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Gọi `dbo.SP_XoaDonDatHang` xóa toàn bộ đơn đặt hàng (chỉ khi đơn ở trạng thái `Chưa nhập`)."""
        code = (maso_ddh or "").strip().upper()
        old_order = self.ensure_editable(code, current_manv=current_manv, is_admin=is_admin)
        if int(old_order.get("DaCoPhieuNhap") or 0) == 1:
            raise ValueError("Không thể xóa vì Đơn đặt hàng này đã phát sinh Phiếu nhập kho.")
        old_details = self.list_details(code)

        db.execute("EXEC dbo.SP_XoaDonDatHang @MasoDDH = ?", (code,))

        restore_steps: List[Tuple[str, Tuple[Any, ...]]] = [
            (
                "EXEC dbo.SP_ThemDonDatHang @MasoDDH = ?, @NGAY = ?, @NhaCC = ?, @MANV = ?",
                (code, old_order["NGAY"], old_order["NhaCC"], int(old_order["MANV"])),
            )
        ]
        for ct in old_details:
            restore_steps.append(
                (
                    "EXEC dbo.SP_ThemCTDDH @MasoDDH = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                    (code, ct["MAVT"], int(ct["SOLUONG"]), float(ct["DONGIA"])),
                )
            )

        self.undo_stack.append(
            UndoAction(
                description=f"Khôi phục đơn đặt hàng đã xóa '{code}' ({old_order['NhaCC']})",
                steps=restore_steps,
                target_id=code,
            )
        )

    def add_detail(
        self,
        maso_ddh: str,
        mavt: str,
        soluong: int | str,
        dongia: float | str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Tuple[bool, int]:
        """Gọi `dbo.SP_ThemCTDDH` (hoặc `dbo.SP_SuaCTDDH` nếu cộng dồn) để thêm mặt hàng vào đơn."""
        code = (maso_ddh or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        self.ensure_editable(code, current_manv=current_manv, is_admin=is_admin)

        vt_info = db.fetch_one("EXEC dbo.SP_ChiTietVatTu @MAVT = ?", (vt_code,))
        if vt_info is None:
            raise ValueError(f"Vật tư '{vt_code}' không tồn tại trong danh mục!")

        sl = parse_positive_int(soluong, "Số lượng đặt")
        dg = parse_money(dongia, "Đơn giá đặt")
        if sl <= 0:
            raise ValueError("Số lượng đặt phải > 0!")
        if dg <= 0:
            raise ValueError("Đơn giá đặt phải > 0!")

        existing = db.fetch_one(
            "EXEC dbo.SP_DSChiTietDDH @MasoDDH = ?, @MAVT = ?",
            (code, vt_code),
        )
        if existing:
            old_sl = int(existing["SOLUONG"])
            old_dg = float(existing["DONGIA"])
            new_sl = old_sl + sl
            db.execute(
                "EXEC dbo.SP_SuaCTDDH @MasoDDH = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                (code, vt_code, new_sl, dg),
            )
            self.undo_stack.append(
                UndoAction(
                    sql="EXEC dbo.SP_SuaCTDDH @MasoDDH = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                    params=(code, vt_code, old_sl, old_dg),
                    description=(
                        f"Hoàn tác cộng dồn mặt hàng '{vt_info['TENVT']}' ({vt_code}) "
                        f"trong đơn '{code}' (về {old_sl})"
                    ),
                    target_id=code,
                )
            )
            return True, new_sl

        db.execute(
            "EXEC dbo.SP_ThemCTDDH @MasoDDH = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
            (code, vt_code, sl, dg),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_XoaCTDDH @MasoDDH = ?, @MAVT = ?",
                params=(code, vt_code),
                description=f"Hoàn tác thêm mặt hàng '{vt_info['TENVT']}' ({vt_code}) vào đơn '{code}'",
                target_id=code,
            )
        )
        return False, sl

    def update_detail(
        self,
        maso_ddh: str,
        mavt: str,
        soluong: int | str,
        dongia: float | str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """
        Gọi `dbo.SP_SuaCTDDH` cập nhật Số lượng / Đơn giá của một dòng chi tiết đơn đặt hàng.
        Nếu mặt hàng đã nhập một phần (`SLDaNhap > 0`), số lượng đặt mới phải `>= SLDaNhap`.
        """
        code = (maso_ddh or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        self.ensure_editable(code, current_manv=current_manv, is_admin=is_admin)

        old_ct = db.fetch_one(
            "EXEC dbo.SP_DSChiTietDDH @MasoDDH = ?, @MAVT = ?",
            (code, vt_code),
        )
        if old_ct is None:
            raise ValueError(f"Không tìm thấy vật tư '{vt_code}' trong đơn đặt hàng '{code}'!")

        sl = parse_positive_int(soluong, "Số lượng đặt")
        dg = parse_money(dongia, "Đơn giá đặt")
        if sl <= 0:
            raise ValueError("Số lượng đặt phải > 0!")
        if dg <= 0:
            raise ValueError("Đơn giá đặt phải > 0!")

        sl_da_nhap = int(old_ct.get("SLDaNhap") or 0)
        if sl < sl_da_nhap:
            raise ValueError(
                f"Mặt hàng '{old_ct['TENVT']}' ({vt_code}) đã nhập kho {sl_da_nhap}, "
                f"số lượng đặt mới không được nhỏ hơn {sl_da_nhap}!"
            )

        db.execute(
            "EXEC dbo.SP_SuaCTDDH @MasoDDH = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
            (code, vt_code, sl, dg),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_SuaCTDDH @MasoDDH = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                params=(code, vt_code, int(old_ct["SOLUONG"]), float(old_ct["DONGIA"])),
                description=f"Hoàn tác sửa mặt hàng '{vt_code}' trong đơn '{code}'",
                target_id=code,
            )
        )

    def delete_detail(
        self,
        maso_ddh: str,
        mavt: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """
        Gọi `dbo.SP_XoaCTDDH` xóa một dòng mặt hàng khỏi chi tiết đơn đặt hàng.
        Chỉ cho phép xóa dòng mặt hàng chưa nhập kho (`SLDaNhap == 0`).
        """
        code = (maso_ddh or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        self.ensure_editable(code, current_manv=current_manv, is_admin=is_admin)

        old_ct = db.fetch_one(
            "EXEC dbo.SP_DSChiTietDDH @MasoDDH = ?, @MAVT = ?",
            (code, vt_code),
        )
        if old_ct is None:
            raise ValueError(f"Không tìm thấy mặt hàng '{vt_code}' trong đơn '{code}' để xóa!")

        sl_da_nhap = int(old_ct.get("SLDaNhap") or 0)
        if sl_da_nhap > 0:
            raise ValueError(
                f"Không thể xóa mặt hàng '{old_ct['TENVT']}' ({vt_code}) khỏi đơn '{code}' "
                f"vì mặt hàng này đã được nhập kho ({sl_da_nhap})!"
            )

        db.execute(
            "EXEC dbo.SP_XoaCTDDH @MasoDDH = ?, @MAVT = ?",
            (code, vt_code),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_ThemCTDDH @MasoDDH = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                params=(code, vt_code, int(old_ct["SOLUONG"]), float(old_ct["DONGIA"])),
                description=f"Khôi phục mặt hàng '{old_ct['TENVT']}' ({vt_code}) vào đơn '{code}'",
                target_id=code,
            )
        )


dat_hang_service = DatHangService()
