"""
Xử lý nghiệp vụ Danh mục Vật tư (`dbo.Vattu`):
Gọi các Stored Procedure trong `sql/04_danh_muc.sql`:
- `dbo.SP_DanhSachVatTu`, `dbo.SP_ChiTietVatTu`
- `dbo.SP_KiemTraTrungTenVatTu`
- `dbo.SP_ThemVatTu`, `dbo.SP_SuaVatTu`, `dbo.SP_XoaVatTu`
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from qlvt.database import db
from qlvt.services.common import UndoAction, UndoMixin, capitalize_first, normalize_spaces


class VatTuService(UndoMixin):
    """Dịch vụ quản lý Danh mục Vật tư gọi Stored Procedures từ SQL Server."""

    def __init__(self) -> None:
        self._init_undo()

    def list_all(self, keyword: str = "") -> List[Dict[str, Any]]:
        """Gọi `dbo.SP_DanhSachVatTu` lấy danh sách vật tư theo từ khóa."""
        kw = normalize_spaces(keyword)
        return db.fetch_all("EXEC dbo.SP_DanhSachVatTu @TuKhoa = ?", (kw,))

    def get_by_id(self, mavt: str) -> Optional[Dict[str, Any]]:
        """Gọi `dbo.SP_ChiTietVatTu` lấy thông tin 1 vật tư theo `MAVT`."""
        return db.fetch_one(
            "EXEC dbo.SP_ChiTietVatTu @MAVT = ?",
            ((mavt or "").strip().upper(),),
        )

    def _validate_fields(
        self,
        mavt: str,
        tenvt: str,
        dvt: str,
        soluongton: int | str = 0,
    ) -> Tuple[str, str, str, int]:
        """Kiểm tra hợp lệ các trường dữ liệu của Vật tư."""
        mavt_clean = (mavt or "").strip().upper()
        if not mavt_clean or len(mavt_clean) > 4:
            raise ValueError("Mã vật tư không được rỗng và tối đa 4 ký tự!")
        if not re.match(r"^[A-Z0-9]{1,4}$", mavt_clean):
            raise ValueError(
                "Mã vật tư chỉ được chứa chữ cái không dấu (A-Z) và chữ số (0-9), không có khoảng trắng hoặc ký tự đặc biệt!"
            )

        tenvt_clean = capitalize_first(tenvt)
        if not tenvt_clean:
            raise ValueError("Tên vật tư không được để trống!")
        if len(tenvt_clean) > 30:
            raise ValueError("Tên vật tư tối đa 30 ký tự!")

        dvt_clean = capitalize_first(dvt)
        if not dvt_clean:
            raise ValueError("Đơn vị tính không được để trống!")
        if len(dvt_clean) > 15:
            raise ValueError("Đơn vị tính tối đa 15 ký tự!")

        try:
            slt_int = int(str(soluongton).strip())
        except ValueError as exc:
            raise ValueError("Số lượng tồn phải là số nguyên!") from exc
        if slt_int < 0:
            raise ValueError("Số lượng tồn phải >= 0!")

        return mavt_clean, tenvt_clean, dvt_clean, slt_int

    def create(
        self,
        mavt: str,
        tenvt: str,
        dvt: str,
        soluongton: int | str = 0,
    ) -> None:
        """Gọi `dbo.SP_ThemVatTu` thêm mới vật tư và lưu `SP_XoaVatTu` vào `undo_stack`."""
        mavt_clean, tenvt_clean, dvt_clean, slt_int = self._validate_fields(
            mavt, tenvt, dvt, soluongton
        )
        if self.get_by_id(mavt_clean) is not None:
            raise ValueError(f"Mã vật tư '{mavt_clean}' đã tồn tại!")

        dup_name = db.fetch_one(
            "EXEC dbo.SP_KiemTraTrungTenVatTu @TENVT = ?, @LoaiTruMAVT = NULL",
            (tenvt_clean,),
        )
        if dup_name is not None:
            raise ValueError(f"Tên vật tư '{tenvt_clean}' đã tồn tại trong danh mục!")

        db.execute(
            "EXEC dbo.SP_ThemVatTu @MAVT = ?, @TENVT = ?, @DVT = ?, @Soluongton = ?",
            (mavt_clean, tenvt_clean, dvt_clean, slt_int),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_XoaVatTu @MAVT = ?",
                params=(mavt_clean,),
                description=f"Hoàn tác thêm vật tư '{mavt_clean}' ({tenvt_clean})",
            )
        )

    def update(
        self,
        mavt: str,
        tenvt: str,
        dvt: str,
        soluongton: Optional[int | str] = None,
    ) -> None:
        """Gọi `dbo.SP_SuaVatTu` cập nhật thông tin vật tư và lưu trạng thái cũ vào `undo_stack`."""
        old_row = self.get_by_id(mavt)
        if old_row is None:
            raise ValueError(f"Không tìm thấy vật tư '{(mavt or '').strip().upper()}' để cập nhật!")

        current_stock = int(old_row["Soluongton"])
        has_tx = int(old_row["DaCoGiaoDich"]) == 1
        target_slt = current_stock if soluongton is None or str(soluongton).strip() == "" else soluongton

        mavt_clean, tenvt_clean, dvt_clean, slt_int = self._validate_fields(
            mavt, tenvt, dvt, target_slt
        )

        if has_tx and slt_int != current_stock:
            raise ValueError(
                f"Vật tư '{mavt_clean}' đã phát sinh giao dịch kho nên số lượng tồn chỉ tự động cập nhật qua Phiếu nhập/xuất!"
            )

        old_dvt = str(old_row["DVT"]).strip()
        if has_tx and dvt_clean.lower() != old_dvt.lower():
            raise ValueError(
                f"Không thể thay đổi Đơn vị tính của vật tư '{mavt_clean}' vì vật tư đã phát sinh chứng từ!"
            )

        dup_name = db.fetch_one(
            "EXEC dbo.SP_KiemTraTrungTenVatTu @TENVT = ?, @LoaiTruMAVT = ?",
            (tenvt_clean, mavt_clean),
        )
        if dup_name is not None:
            raise ValueError(f"Tên vật tư '{tenvt_clean}' đã bị trùng với vật tư khác!")

        db.execute(
            "EXEC dbo.SP_SuaVatTu @MAVT = ?, @TENVT = ?, @DVT = ?, @Soluongton = ?",
            (mavt_clean, tenvt_clean, dvt_clean, slt_int),
        )

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_SuaVatTu @MAVT = ?, @TENVT = ?, @DVT = ?, @Soluongton = ?",
                params=(mavt_clean, old_row["TENVT"], old_row["DVT"], current_stock),
                description=f"Hoàn tác sửa vật tư '{mavt_clean}' ({old_row['TENVT']})",
            )
        )

    def delete(self, mavt: str) -> None:
        """Kiểm tra điều kiện xóa từ `dbo.SP_ChiTietVatTu` và gọi `dbo.SP_XoaVatTu` xóa vật tư."""
        mavt_clean = (mavt or "").strip().upper()
        old_row = self.get_by_id(mavt_clean)
        if old_row is None:
            raise ValueError(f"Không tìm thấy vật tư '{mavt_clean}' để xóa!")

        if int(old_row.get("CoTheXoa") or 0) == 0:
            if int(old_row.get("Soluongton") or 0) > 0:
                raise ValueError("Không thể xóa vì vật tư đang có số lượng tồn kho > 0.")
            raise ValueError("Không thể xóa vì vật tư đã phát sinh trong chứng từ Đặt hàng / Nhập / Xuất kho.")

        db.execute("EXEC dbo.SP_XoaVatTu @MAVT = ?", (mavt_clean,))

        self.undo_stack.append(
            UndoAction(
                sql="EXEC dbo.SP_ThemVatTu @MAVT = ?, @TENVT = ?, @DVT = ?, @Soluongton = ?",
                params=(
                    old_row["MAVT"],
                    old_row["TENVT"],
                    old_row["DVT"],
                    old_row["Soluongton"],
                ),
                description=f"Khôi phục vật tư đã xóa '{mavt_clean}' ({old_row['TENVT']})",
            )
        )


vat_tu_service = VatTuService()
