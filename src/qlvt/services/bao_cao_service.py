"""
Xử lý nghiệp vụ cho Hệ thống 7 Báo biểu & Thống kê Kho (Phần 2):
Gọi 6 Stored Procedures `dbo.usp_RPT_*` trong SQL Server và kiểm tra tính hợp lệ của tham số lọc.
"""

from datetime import date
from typing import Any, Dict, List, Tuple

from qlvt.database import db
from qlvt.services.common import parse_required_date

# Danh mục 7 mẫu báo biểu hiển thị trên thanh chọn báo cáo
REPORT_CATALOG: List[Dict[str, Any]] = [
    {
        "slug": "nhan-vien",
        "title": "DANH SÁCH NHÂN VIÊN",
        "subtitle": "Sắp xếp tăng dần theo Tên + Họ nhân viên",
        "params": [],
    },
    {
        "slug": "vat-tu",
        "title": "DANH MỤC VẬT TƯ",
        "subtitle": "Sắp xếp tăng dần theo Tên vật tư kèm số lượng tồn kho hiện tại",
        "params": [],
    },
    {
        "slug": "ddh-chua-nhap-het",
        "title": "ĐƠN ĐẶT HÀNG CHƯA CÓ PHIẾU NHẬP HOẶC NHẬP MỘT PHẦN",
        "subtitle": "Nhóm theo từng Đơn đặt hàng kèm trạng thái Chưa nhập / Nhập một phần",
        "params": [],
    },
    {
        "slug": "bang-ke-nhap-xuat",
        "title": "BẢNG KÊ CHI TIẾT SỐ LƯỢNG – TRỊ GIÁ HÀNG NHẬP / XUẤT",
        "subtitle": "Nhóm theo từng tháng (Năm, Tháng) kèm tổng phụ cuối mỗi tháng",
        "params": ["tu_ngay", "den_ngay", "loai"],
    },
    {
        "slug": "thong-ke-nhap-nam",
        "title": "THỐNG KÊ PHIẾU NHẬP THEO TỪNG THÁNG TRONG NĂM",
        "subtitle": "Số lượng phiếu nhập, tổng số lượng vật tư và tổng trị giá đủ 12 tháng",
        "params": ["nam"],
    },
    {
        "slug": "thong-ke-xuat-nam",
        "title": "THỐNG KÊ PHIẾU XUẤT THEO TỪNG THÁNG TRONG NĂM",
        "subtitle": "Số lượng phiếu xuất, tổng số lượng vật tư và tổng trị giá đủ 12 tháng",
        "params": ["nam"],
    },
    {
        "slug": "tong-hop-nhap-xuat",
        "title": "BẢNG TỔNG HỢP NHẬP XUẤT",
        "subtitle": "Tổng hợp tiền Nhập – Xuất mỗi ngày một dòng kèm tỷ trọng phần trăm toàn kỳ",
        "params": ["tu_ngay", "den_ngay"],
    },
]


class BaoCaoService:
    """Dịch vụ truy xuất dữ liệu báo cáo kho từ các Stored Procedure `dbo.usp_RPT_*`."""

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Trả về danh sách cấu hình của 7 mẫu báo cáo."""
        return REPORT_CATALOG

    @staticmethod
    def parse_date_range(tu_ngay_raw: str, den_ngay_raw: str) -> Tuple[date, date]:
        """Kiểm tra hợp lệ khoảng thời gian `Từ ngày` <= `Đến ngày`."""
        tu_ngay = parse_required_date(tu_ngay_raw, "Từ ngày")
        den_ngay = parse_required_date(den_ngay_raw, "Đến ngày")
        if tu_ngay > den_ngay:
            raise ValueError("Từ ngày phải nhỏ hơn hoặc bằng Đến ngày!")
        return tu_ngay, den_ngay

    @staticmethod
    def parse_year(nam_raw: Any) -> int:
        """Kiểm tra năm thống kê hợp lệ (1900..9998)."""
        try:
            nam = int(str(nam_raw).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("Năm thống kê phải là số nguyên hợp lệ!") from exc

        if nam < 1900 or nam > 9998:
            raise ValueError("Năm thống kê không hợp lệ!")
        return nam

    def get_ds_nhan_vien(self) -> List[Dict[str, Any]]:
        """Báo cáo Danh sách Nhân viên (`dbo.usp_RPT_DSNhanVien`)."""
        return db.fetch_all("EXEC dbo.usp_RPT_DSNhanVien")

    def get_dm_vat_tu(self) -> List[Dict[str, Any]]:
        """Báo cáo Danh mục Vật tư (`dbo.usp_RPT_DMVatTu`)."""
        return db.fetch_all("EXEC dbo.usp_RPT_DMVatTu")

    def get_ddh_chua_nhap_het(self) -> List[Dict[str, Any]]:
        """Báo cáo Đơn đặt hàng chưa có Phiếu nhập hoặc nhập chưa hết (`dbo.usp_RPT_DonDatHangChuaNhapHet`)."""
        return db.fetch_all("EXEC dbo.usp_RPT_DonDatHangChuaNhapHet")

    def get_bang_ke_nhap_xuat(
        self, tu_ngay_raw: str, den_ngay_raw: str, loai_raw: str = "T"
    ) -> List[Dict[str, Any]]:
        """Bảng kê chi tiết Số lượng – Trị giá hàng Nhập / Xuất (`dbo.usp_RPT_BangKeNhapXuat`)."""
        tu_ngay, den_ngay = self.parse_date_range(tu_ngay_raw, den_ngay_raw)
        loai = (loai_raw or "T").strip().upper()
        if loai not in ("N", "X", "T"):
            raise ValueError("Loại phải là N (nhập), X (xuất) hoặc T (cả hai).")

        return db.fetch_all(
            "EXEC dbo.usp_RPT_BangKeNhapXuat @TuNgay = ?, @DenNgay = ?, @Loai = ?",
            (tu_ngay, den_ngay, loai),
        )

    def get_thong_ke_theo_thang(self, nam_raw: Any, loai_raw: str) -> List[Dict[str, Any]]:
        """Thống kê Phiếu Nhập (`'N'`) hoặc Phiếu Xuất (`'X'`) theo 12 tháng (`dbo.usp_RPT_ThongKeTheoThang`)."""
        nam = self.parse_year(nam_raw)
        loai = (loai_raw or "N").strip().upper()
        if loai not in ("N", "X"):
            raise ValueError("Loại phải là N (nhập) hoặc X (xuất).")

        return db.fetch_all(
            "EXEC dbo.usp_RPT_ThongKeTheoThang @Nam = ?, @Loai = ?",
            (nam, loai),
        )

    def get_tong_hop_nhap_xuat(
        self, tu_ngay_raw: str, den_ngay_raw: str
    ) -> List[Dict[str, Any]]:
        """Bảng Tổng hợp Nhập Xuất theo từng ngày kèm tỷ trọng % (`dbo.usp_RPT_TongHopNhapXuat`)."""
        tu_ngay, den_ngay = self.parse_date_range(tu_ngay_raw, den_ngay_raw)
        return db.fetch_all(
            "EXEC dbo.usp_RPT_TongHopNhapXuat @TuNgay = ?, @DenNgay = ?",
            (tu_ngay, den_ngay),
        )


bao_cao_service = BaoCaoService()
