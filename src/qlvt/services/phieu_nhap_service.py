"""
Xử lý nghiệp vụ Phiếu Nhập Kho (`dbo.PhieuNhap`) và Chi Tiết Phiếu Nhập (`dbo.CTPN`):
Gọi các Stored Procedure có Giao tác (Transaction) trong `sql/05_giao_dich_kho.sql`:
- `dbo.SP_DanhSachPhieuNhap`, `dbo.SP_ChiTietPhieuNhap`, `dbo.SP_DSChiTietPN`, `dbo.SP_HanMucNhapVatTu`
- `dbo.SP_DanhSachDonDatHang`, `dbo.SP_DSChiTietDDH`
- `dbo.SP_ThemPhieuNhap`, `dbo.SP_SuaPhieuNhap`, `dbo.SP_XoaPhieuNhap`
- `dbo.SP_ThemCTPN`, `dbo.SP_SuaCTPN`, `dbo.SP_XoaCTPN`
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


class PhieuNhapService(UndoMixin):
    """Dịch vụ quản lý Phiếu nhập kho (`PhieuNhap` - `CTPN`) gọi Stored Procedures từ SQL Server."""

    def __init__(self) -> None:
        self._init_undo()

    def list_receipts(self, keyword: str = "") -> List[Dict[str, Any]]:
        """Gọi `dbo.SP_DanhSachPhieuNhap` lấy danh sách phiếu nhập kho."""
        kw = normalize_spaces(keyword)
        return db.fetch_all("EXEC dbo.SP_DanhSachPhieuNhap @TuKhoa = ?", (kw,))

    def get_receipt(self, mapn: str) -> Optional[Dict[str, Any]]:
        """Gọi `dbo.SP_ChiTietPhieuNhap` lấy thông tin đầu phiếu nhập kho theo `MAPN`."""
        code = (mapn or "").strip().upper()
        return db.fetch_one("EXEC dbo.SP_ChiTietPhieuNhap @MAPN = ?", (code,))

    def list_details(self, mapn: str) -> List[Dict[str, Any]]:
        """Gọi `dbo.SP_DSChiTietPN` lấy danh sách các dòng mặt hàng chi tiết của một phiếu nhập."""
        code = (mapn or "").strip().upper()
        return db.fetch_all("EXEC dbo.SP_DSChiTietPN @MAPN = ?", (code,))

    def check_modify_permission(
        self,
        receipt_row: Dict[str, Any],
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """Kiểm tra người dùng có quyền chỉnh sửa phiếu nhập (người lập phiếu hoặc Quản trị viên)."""
        if (
            not is_admin
            and current_manv is not None
            and str(current_manv).strip() != ""
            and int(receipt_row["MANV"]) != int(str(current_manv).strip())
        ):
            return (
                False,
                f"Chỉ người lập ({receipt_row['HoTenNV']}) hoặc Quản trị viên mới được chỉnh sửa",
            )
        return True, None

    def check_delete_permission(
        self,
        receipt_row: Dict[str, Any],
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """Kiểm tra phiếu nhập có thể xóa được không (đúng quyền người lập/Admin và hàng trong phiếu chưa bị xuất kho lẹm tồn)."""
        can_mod, reason = self.check_modify_permission(
            receipt_row, current_manv=current_manv, is_admin=is_admin
        )
        if not can_mod:
            return False, reason
        if int(receipt_row.get("CoTheXoaPhieu", 1)) == 0:
            mat_hang = receipt_row.get("MatHangDaXuat") or "trong phiếu"
            return (
                False,
                f"Không thể xóa phiếu vì mặt hàng {mat_hang} đã được xuất kho (tồn hiện tại không đủ để trừ lại)",
            )
        return True, None

    def ensure_modifiable(
        self,
        mapn: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Dict[str, Any]:
        """Ném `ValueError` nếu người dùng không có quyền chỉnh sửa phiếu nhập `mapn`."""
        code = (mapn or "").strip().upper()
        pn = self.get_receipt(code)
        if pn is None:
            raise ValueError(f"Phiếu nhập '{code}' không tồn tại!")
        can_mod, reason = self.check_modify_permission(
            pn, current_manv=current_manv, is_admin=is_admin
        )
        if not can_mod:
            raise ValueError(f"Không thể chỉnh sửa/xóa phiếu nhập '{code}': {reason}!")
        return pn

    def list_orders_available_for_import(self) -> List[Dict[str, Any]]:
        """Lấy danh sách Đơn đặt hàng đang còn mặt hàng chưa nhập đủ từ `dbo.SP_DanhSachDonDatHang`."""
        orders = db.fetch_all("EXEC dbo.SP_DanhSachDonDatHang @TuKhoa = N''")
        return [
            r
            for r in orders
            if int(r.get("SoMatHang") or 0) > 0 and int(r.get("DaNhapDu") or 0) == 0
        ]

    def list_available_items_for_order(self, maso_ddh: str) -> List[Dict[str, Any]]:
        """Lấy các vật tư còn thiếu (`SLConLai > 0`) của đơn đặt hàng từ `dbo.SP_DSChiTietDDH`."""
        code = (maso_ddh or "").strip().upper()
        items = db.fetch_all("EXEC dbo.SP_DSChiTietDDH @MasoDDH = ?", (code,))
        return [r for r in items if int(r.get("SLConLai") or 0) > 0]

    def get_import_quota(
        self,
        maso_ddh: str,
        mavt: str,
        exclude_mapn: Optional[str] = None,
    ) -> Tuple[int, int, int, str, float]:
        """Gọi `dbo.SP_HanMucNhapVatTu` tính hạn mức số lượng còn được phép nhập của vật tư trong đơn."""
        ddh_code = (maso_ddh or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        excl = exclude_mapn.strip().upper() if exclude_mapn else None

        row = db.fetch_one(
            "EXEC dbo.SP_HanMucNhapVatTu @MasoDDH = ?, @MAVT = ?, @LoaiTruMAPN = ?",
            (ddh_code, vt_code, excl),
        )
        if row is None:
            raise ValueError(
                f"Vật tư '{vt_code}' không tồn tại trong Đơn đặt hàng '{ddh_code}'!"
            )

        sl_dat = int(row["SLDat"])
        da_nhap = int(row["DaNhap"])
        con_lai = sl_dat - da_nhap
        return sl_dat, da_nhap, con_lai, str(row["TENVT"]), float(row["DonGiaDat"])

    def create_receipt(
        self,
        mapn: str,
        ngay: str | date,
        maso_ddh: str,
        manv: int | str,
    ) -> None:
        """Gọi `dbo.SP_ThemPhieuNhap` tạo đầu phiếu nhập kho gắn với một Đơn đặt hàng còn thiếu hàng."""
        code = validate_voucher_code(mapn, "Mã phiếu nhập")
        ddh_code = (maso_ddh or "").strip().upper()
        if not ddh_code:
            raise ValueError("Vui lòng chọn Mã số đơn đặt hàng!")
        if self.get_receipt(code) is not None:
            raise ValueError(f"Phiếu nhập '{code}' đã tồn tại!")

        ddh_row = db.fetch_one("EXEC dbo.SP_ChiTietDonDatHang @MasoDDH = ?", (ddh_code,))
        if ddh_row is None:
            raise ValueError(f"Đơn đặt hàng '{ddh_code}' không tồn tại!")

        remaining_items = self.list_available_items_for_order(ddh_code)
        if not remaining_items:
            raise ValueError(
                f"Đơn đặt hàng '{ddh_code}' đã được nhập đủ toàn bộ hàng hoặc chưa có chi tiết đặt hàng!"
            )

        receipt_date = parse_voucher_date(ngay, "Ngày nhập kho")
        if receipt_date > date.today():
            raise ValueError("Ngày nhập kho không được lớn hơn ngày hiện tại!")

        order_date = parse_voucher_date(ddh_row["NGAY"], "Ngày đặt hàng")
        if receipt_date < order_date:
            raise ValueError(
                f"Ngày nhập kho ({receipt_date}) không được nhỏ hơn ngày đặt hàng ({order_date}) của đơn '{ddh_code}'!"
            )

        manv_int = ensure_active_employee(manv)

        db.execute(
            "EXEC dbo.SP_ThemPhieuNhap @MAPN = ?, @NGAY = ?, @MasoDDH = ?, @MANV = ?",
            (code, receipt_date.isoformat(), ddh_code, manv_int),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_XoaPhieuNhap @MAPN = ?",
                params=(code,),
                description=f"Hoàn tác lập phiếu nhập '{code}'",
                target_id=None,
            )
        )

    def update_receipt(
        self,
        mapn: str,
        ngay: str | date,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Gọi `dbo.SP_SuaPhieuNhap` cập nhật Ngày nhập kho của phiếu nhập (`NgayDatHang <= NGAY <= hôm nay`)."""
        code = (mapn or "").strip().upper()
        old_pn = self.ensure_modifiable(code, current_manv=current_manv, is_admin=is_admin)

        receipt_date = parse_voucher_date(ngay, "Ngày nhập kho")
        if receipt_date > date.today():
            raise ValueError("Ngày nhập kho không được lớn hơn ngày hiện tại!")

        order_date = parse_voucher_date(old_pn["NgayDatHang"], "Ngày đặt hàng")
        if receipt_date < order_date:
            raise ValueError(
                f"Ngày nhập kho ({receipt_date}) không được nhỏ hơn ngày đặt hàng ({order_date}) của đơn '{old_pn['MasoDDH']}'!"
            )

        db.execute(
            "EXEC dbo.SP_SuaPhieuNhap @MAPN = ?, @NGAY = ?",
            (code, receipt_date.isoformat()),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_SuaPhieuNhap @MAPN = ?, @NGAY = ?",
                params=(code, old_pn["NGAY"]),
                description=f"Hoàn tác sửa ngày nhập của phiếu '{code}'",
                target_id=code,
            )
        )

    def delete_receipt(
        self,
        mapn: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Gọi `dbo.SP_XoaPhieuNhap` xóa phiếu nhập kho trong 1 Giao tác (sau khi kiểm tra quyền & tồn kho)."""
        code = (mapn or "").strip().upper()
        old_pn = self.ensure_modifiable(code, current_manv=current_manv, is_admin=is_admin)
        old_details = self.list_details(code)

        for ct in old_details:
            vt = db.fetch_one("EXEC dbo.SP_ChiTietVatTu @MAVT = ?", (ct["MAVT"],))
            if vt and int(vt["Soluongton"]) < int(ct["SOLUONG"]):
                raise ValueError(
                    f"Không thể xóa phiếu nhập '{code}' vì mặt hàng {ct['MAVT']} ({vt['TENVT']}) "
                    f"đã xuất kho (Tồn hiện tại: {vt['Soluongton']}, cần trừ lại: {ct['SOLUONG']})!"
                )

        db.execute("EXEC dbo.SP_XoaPhieuNhap @MAPN = ?", (code,))

        restore_steps: List[Tuple[str, Tuple[Any, ...]]] = [
            (
                "EXEC dbo.SP_ThemPhieuNhap @MAPN = ?, @NGAY = ?, @MasoDDH = ?, @MANV = ?",
                (code, old_pn["NGAY"], old_pn["MasoDDH"], int(old_pn["MANV"])),
            )
        ]
        for ct in old_details:
            restore_steps.append(
                (
                    "EXEC dbo.SP_ThemCTPN @MAPN = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                    (code, ct["MAVT"], int(ct["SOLUONG"]), float(ct["DONGIA"])),
                )
            )

        self.undo_stack.append(
            UndoAction(
                description=f"Khôi phục phiếu nhập đã xóa '{code}' (cộng trả lại tồn kho)",
                steps=restore_steps,
                target_id=code,
            )
        )

    def add_detail(
        self,
        mapn: str,
        mavt: str,
        soluong: int | str,
        dongia: float | str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> Tuple[bool, int]:
        """Gọi `dbo.SP_ThemCTPN` (hoặc cộng dồn qua `dbo.SP_SuaCTPN` nếu đã có trong phiếu) và tự động tăng tồn kho."""
        pn_code = (mapn or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        receipt = self.ensure_modifiable(pn_code, current_manv=current_manv, is_admin=is_admin)

        sl = parse_positive_int(soluong, "Số lượng nhập")
        dg = parse_money(dongia, "Đơn giá nhập")
        if sl <= 0:
            raise ValueError("Số lượng nhập phải > 0!")
        if dg <= 0:
            raise ValueError("Đơn giá nhập phải > 0!")

        sl_dat, da_nhap, con_lai, ten_vt, _dg_dat = self.get_import_quota(
            receipt["MasoDDH"], vt_code
        )
        if sl > con_lai:
            raise ValueError(
                f"Vật tư [{vt_code} - {ten_vt}] đặt [{sl_dat}], đã nhập [{da_nhap}], "
                f"chỉ còn được nhập tối đa [{con_lai}]!"
            )

        dup = db.fetch_one(
            "EXEC dbo.SP_DSChiTietPN @MAPN = ?, @MAVT = ?",
            (pn_code, vt_code),
        )
        if dup:
            old_sl = int(dup["SOLUONG"])
            old_dg = float(dup["DONGIA"])
            new_sl = old_sl + sl
            db.execute(
                "EXEC dbo.SP_SuaCTPN @MAPN = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                (pn_code, vt_code, new_sl, dg),
            )
            self.undo_stack.append(
                UndoAction(
                    sql="EXEC dbo.SP_SuaCTPN @MAPN = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                    params=(pn_code, vt_code, old_sl, old_dg),
                    description=f"Hoàn tác cộng dồn nhập mặt hàng '{ten_vt}' ({vt_code}) trong phiếu '{pn_code}' (về {old_sl})",
                    target_id=pn_code,
                )
            )
            return True, new_sl

        db.execute(
            "EXEC dbo.SP_ThemCTPN @MAPN = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
            (pn_code, vt_code, sl, dg),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_XoaCTPN @MAPN = ?, @MAVT = ?",
                params=(pn_code, vt_code),
                description=f"Hoàn tác nhập mặt hàng '{ten_vt}' ({vt_code}) trong phiếu '{pn_code}'",
                target_id=pn_code,
            )
        )
        return False, sl

    def update_detail(
        self,
        mapn: str,
        mavt: str,
        soluong: int | str,
        dongia: float | str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Gọi `dbo.SP_SuaCTPN` cập nhật dòng chi tiết phiếu nhập và điều chỉnh tồn kho trong giao tác."""
        pn_code = (mapn or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        receipt = self.ensure_modifiable(pn_code, current_manv=current_manv, is_admin=is_admin)

        old_ct = db.fetch_one(
            "EXEC dbo.SP_DSChiTietPN @MAPN = ?, @MAVT = ?",
            (pn_code, vt_code),
        )
        if old_ct is None:
            raise ValueError(f"Không tìm thấy vật tư '{vt_code}' trong phiếu nhập '{pn_code}'!")

        sl = parse_positive_int(soluong, "Số lượng nhập")
        dg = parse_money(dongia, "Đơn giá nhập")
        if sl <= 0:
            raise ValueError("Số lượng nhập phải > 0!")
        if dg <= 0:
            raise ValueError("Đơn giá nhập phải > 0!")

        sl_dat, da_nhap_khac, con_lai, ten_vt, _ = self.get_import_quota(
            receipt["MasoDDH"], vt_code, exclude_mapn=pn_code
        )
        if sl > con_lai:
            raise ValueError(
                f"Vật tư [{vt_code} - {ten_vt}] đặt [{sl_dat}], đã nhập [{da_nhap_khac}], "
                f"chỉ còn được nhập tối đa [{con_lai}]!"
            )

        old_sl = int(old_ct["SOLUONG"])
        if sl < old_sl:
            giam_di = old_sl - sl
            if int(old_ct["Soluongton"]) < giam_di:
                raise ValueError(
                    f"Không thể giảm số lượng nhập của '{ten_vt}' xuống {sl} vì hàng đã xuất kho "
                    f"(Tồn hiện tại: {old_ct['Soluongton']}, số lượng nhập tối thiểu phải >= {old_sl - int(old_ct['Soluongton'])})!"
                )

        db.execute(
            "EXEC dbo.SP_SuaCTPN @MAPN = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
            (pn_code, vt_code, sl, dg),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_SuaCTPN @MAPN = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                params=(pn_code, vt_code, old_sl, float(old_ct["DONGIA"])),
                description=f"Hoàn tác sửa mặt hàng '{ten_vt}' ({vt_code}) trong phiếu '{pn_code}'",
                target_id=pn_code,
            )
        )

    def delete_detail(
        self,
        mapn: str,
        mavt: str,
        current_manv: Optional[int | str] = None,
        is_admin: bool = True,
    ) -> None:
        """Gọi `dbo.SP_XoaCTPN` xóa 1 dòng mặt hàng khỏi phiếu nhập và trừ lại tồn kho trong giao tác."""
        pn_code = (mapn or "").strip().upper()
        vt_code = (mavt or "").strip().upper()
        self.ensure_modifiable(pn_code, current_manv=current_manv, is_admin=is_admin)

        old_ct = db.fetch_one(
            "EXEC dbo.SP_DSChiTietPN @MAPN = ?, @MAVT = ?",
            (pn_code, vt_code),
        )
        if old_ct is None:
            raise ValueError(f"Không tìm thấy mặt hàng '{vt_code}' trong phiếu nhập '{pn_code}'!")

        if int(old_ct["Soluongton"]) < int(old_ct["SOLUONG"]):
            raise ValueError(
                f"Không thể xóa dòng '{old_ct['TENVT']}' khỏi phiếu nhập '{pn_code}' vì hàng đã xuất kho "
                f"(Tồn hiện tại: {old_ct['Soluongton']}, cần trừ lại: {old_ct['SOLUONG']})!"
            )

        db.execute(
            "EXEC dbo.SP_XoaCTPN @MAPN = ?, @MAVT = ?",
            (pn_code, vt_code),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_ThemCTPN @MAPN = ?, @MAVT = ?, @SOLUONG = ?, @DONGIA = ?",
                params=(pn_code, vt_code, int(old_ct["SOLUONG"]), float(old_ct["DONGIA"])),
                description=f"Khôi phục dòng '{old_ct['TENVT']}' ({vt_code}) vào phiếu nhập '{pn_code}'",
                target_id=pn_code,
            )
        )


phieu_nhap_service = PhieuNhapService()
