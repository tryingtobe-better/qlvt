"""
Các Route thuộc phân hệ Báo Biểu & Thống Kê Kho (`/bao-cao`):
- Điều phối 7 mẫu báo cáo kho dựa trên tham số `type` (`nhan-vien`, `vat-tu`, `ddh-chua-nhap-het`,
  `bang-ke-nhap-xuat`, `thong-ke-nhap-nam`, `thong-ke-xuat-nam`, `tong-hop-nhap-xuat`).
- Hỗ trợ gom nhóm dữ liệu theo từng Đơn đặt hàng (`_group_ddh_rows`) và theo từng Tháng/Năm (`_group_bang_ke_by_month`).
"""

from datetime import date, datetime
from typing import Any, Dict, List

from flask import Flask, flash, render_template, request

from qlvt.services import bao_cao_service
from qlvt.web.helpers import login_required


def _format_vn_date(iso_date: str) -> str:
    """Chuyển chuỗi ngày chuẩn ISO (`YYYY-MM-DD`) sang định dạng Việt Nam (`DD/MM/YYYY`)."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def _group_ddh_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gom nhóm kết quả `usp_RPT_DonDatHangChuaNhapHet` theo từng mã đơn `MasoDDH` và tính tổng phụ từng đơn."""
    groups: List[Dict[str, Any]] = []
    index_by_ddh: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        maso_ddh = str(row.get("MasoDDH") or "").strip()
        if maso_ddh not in index_by_ddh:
            group = {
                "MasoDDH": maso_ddh,
                "NGAY": row.get("NGAY"),
                "NhaCC": row.get("NhaCC"),
                "NVLap": row.get("NVLap"),
                "items": [],
                "sub_dat": 0,
                "sub_da_nhap": 0,
                "sub_con_thieu": 0,
                "group_status": "Chưa nhập",
            }
            index_by_ddh[maso_ddh] = group
            groups.append(group)

        group = index_by_ddh[maso_ddh]
        group["items"].append(row)
        group["sub_dat"] += int(row.get("SLDat") or 0)
        group["sub_da_nhap"] += int(row.get("SLDaNhap") or 0)
        group["sub_con_thieu"] += int(row.get("SLConThieu") or 0)
        if group["sub_da_nhap"] > 0:
            group["group_status"] = "Nhập một phần"

    return groups


def _group_bang_ke_by_month(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gom nhóm kết quả `usp_RPT_BangKeNhapXuat` theo từng cặp `(Tháng, Năm)` kèm tổng phụ mỗi tháng."""
    groups: List[Dict[str, Any]] = []
    index_by_month: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        nam = int(row.get("Nam") or 0)
        thang = int(row.get("Thang") or 0)
        key = f"{thang:02d}/{nam}"

        if key not in index_by_month:
            group = {
                "ThangNam": key,
                "Nam": nam,
                "Thang": thang,
                "items": [],
                "sub_qty": 0,
                "sub_amount": 0.0,
            }
            index_by_month[key] = group
            groups.append(group)

        group = index_by_month[key]
        group["items"].append(row)
        group["sub_qty"] += int(row.get("SOLUONG") or 0)
        group["sub_amount"] += float(row.get("TriGia") or 0)

    return groups


def register_bao_cao_routes(app: Flask) -> None:
    """Đăng ký đường dẫn `/bao-cao` hiển thị và in ấn 7 biểu mẫu báo cáo kho."""

    @app.route("/bao-cao", methods=["GET"])
    @login_required
    def bao_cao_page() -> Any:
        catalog = bao_cao_service.get_catalog()
        slug_map = {item["slug"]: item for item in catalog}

        selected_slug = request.args.get("type", "nhan-vien").strip()
        if selected_slug not in slug_map:
            selected_slug = "nhan-vien"
        report_meta = slug_map[selected_slug]

        today = date.today()
        default_from = date(today.year, 1, 1).isoformat()
        default_to = today.isoformat()

        loai = request.args.get("loai", "T").strip().upper()
        if loai not in ("T", "N", "X"):
            loai = "T"

        tu_ngay = request.args.get("tu_ngay", default_from).strip() or default_from
        den_ngay = request.args.get("den_ngay", default_to).strip() or default_to
        nam_raw = request.args.get("nam", str(today.year)).strip() or str(today.year)

        rows: List[Dict[str, Any]] = []
        grouped_rows: List[Dict[str, Any]] = []
        summary: Dict[str, Any] = {}

        try:
            if selected_slug == "nhan-vien":
                rows = bao_cao_service.get_ds_nhan_vien()
                active_count = sum(1 for r in rows if int(r.get("TrangThaiXoa") or 0) == 0)
                summary = {
                    "total_rows": len(rows),
                    "active_count": active_count,
                    "inactive_count": len(rows) - active_count,
                    "total_salary": sum(float(r.get("LUONG") or 0) for r in rows),
                }

            elif selected_slug == "vat-tu":
                rows = bao_cao_service.get_dm_vat_tu()
                summary = {
                    "total_rows": len(rows),
                    "total_stock": sum(int(r.get("Soluongton") or 0) for r in rows),
                }

            elif selected_slug == "ddh-chua-nhap-het":
                rows = bao_cao_service.get_ddh_chua_nhap_het()
                grouped_rows = _group_ddh_rows(rows)
                summary = {
                    "total_orders": len(grouped_rows),
                    "total_rows": len(rows),
                    "total_dat": sum(int(r.get("SLDat") or 0) for r in rows),
                    "total_da_nhap": sum(int(r.get("SLDaNhap") or 0) for r in rows),
                    "total_con_thieu": sum(int(r.get("SLConThieu") or 0) for r in rows),
                }

            elif selected_slug == "bang-ke-nhap-xuat":
                rows = bao_cao_service.get_bang_ke_nhap_xuat(
                    tu_ngay_raw=tu_ngay,
                    den_ngay_raw=den_ngay,
                    loai_raw=loai,
                )
                grouped_rows = _group_bang_ke_by_month(rows)
                summary = {
                    "total_months": len(grouped_rows),
                    "total_rows": len(rows),
                    "total_qty": sum(int(r.get("SOLUONG") or 0) for r in rows),
                    "total_amount": sum(float(r.get("TriGia") or 0) for r in rows),
                }

            elif selected_slug in ("thong-ke-nhap-nam", "thong-ke-xuat-nam"):
                loai_tk = "N" if selected_slug == "thong-ke-nhap-nam" else "X"
                rows = bao_cao_service.get_thong_ke_theo_thang(nam_raw, loai_tk)
                summary = {
                    "total_vouchers": sum(int(r.get("SoPhieu") or 0) for r in rows),
                    "total_qty": sum(int(r.get("TongSoLuong") or 0) for r in rows),
                    "total_amount": sum(float(r.get("TongTriGia") or 0) for r in rows),
                }

            elif selected_slug == "tong-hop-nhap-xuat":
                rows = bao_cao_service.get_tong_hop_nhap_xuat(
                    tu_ngay_raw=tu_ngay,
                    den_ngay_raw=den_ngay,
                )
                summary = {
                    "total_days": len(rows),
                    "total_nhap": sum(float(r.get("Nhap") or 0) for r in rows),
                    "total_xuat": sum(float(r.get("Xuat") or 0) for r in rows),
                }

        except ValueError as exc:
            flash(str(exc), "error")
        except Exception as exc:
            flash(f"Lỗi khi truy xuất báo cáo: {exc}", "error")

        return render_template(
            "bao_cao.html",
            active_page="bao_cao",
            catalog=catalog,
            selected_slug=selected_slug,
            report_meta=report_meta,
            loai=loai,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
            tu_ngay_vn=_format_vn_date(tu_ngay),
            den_ngay_vn=_format_vn_date(den_ngay),
            nam=nam_raw,
            today_day=f"{today.day:02d}",
            today_month=f"{today.month:02d}",
            today_year=str(today.year),
            rows=rows,
            grouped_rows=grouped_rows,
            summary=summary,
        )
