"""
Các Route thuộc phân hệ Danh Mục:
- `/vat-tu`, `/vat-tu/save`, `/vat-tu/delete/<mavt>`, `/vat-tu/undo`: Quản lý Danh mục Vật tư.
- `/nhan-vien`, `/nhan-vien/save`, `/nhan-vien/delete/<manv>`, `/nhan-vien/status/<manv>`, `/nhan-vien/undo`: Quản lý Danh mục Nhân viên.
"""

from datetime import date
from typing import Any

from flask import Flask, flash, redirect, render_template, request, url_for

from qlvt.services import auth_service, nhan_vien_service, vat_tu_service
from qlvt.web.helpers import admin_required, login_required, next_code, next_manv


def register_danh_muc_routes(app: Flask) -> None:
    """Đăng ký các đường dẫn thuộc nhóm chức năng Danh mục (Vật tư & Nhân viên)."""

    @app.route("/vat-tu")
    @login_required
    def vat_tu_page() -> Any:
        """Hiển thị trang Danh mục Vật tư kèm thanh tìm kiếm và trạng thái hoàn tác."""
        keyword = request.args.get("q", "").strip()
        all_rows = vat_tu_service.list_all()
        rows = vat_tu_service.list_all(keyword) if keyword else all_rows
        return render_template(
            "vat_tu.html",
            active_page="vat_tu",
            rows=rows,
            existing_items={
                str(r["MAVT"]).strip().upper(): str(r["TENVT"]).strip()
                for r in all_rows
            },
            keyword=keyword,
            suggested_mavt=next_code(all_rows, "MAVT", "VT", 2),
            can_undo=vat_tu_service.can_undo,
            undo_count=vat_tu_service.undo_count,
            next_undo=vat_tu_service.next_undo_description,
        )

    @app.route("/vat-tu/save", methods=["POST"])
    @login_required
    def vat_tu_save() -> Any:
        """Thêm mới (`mode=create`) hoặc cập nhật (`mode=update`) một vật tư."""
        mode = request.form.get("mode", "create")
        mavt = request.form.get("mavt", "").strip()
        tenvt = request.form.get("tenvt", "").strip()
        dvt = request.form.get("dvt", "").strip()
        soluongton = request.form.get("soluongton", "0").strip() or "0"

        try:
            if mode == "update":
                vat_tu_service.update(mavt, tenvt, dvt, soluongton)
                flash(f"Đã cập nhật vật tư '{mavt.upper()}' thành công!", "success")
            else:
                vat_tu_service.create(mavt, tenvt, dvt, soluongton)
                flash(f"Đã thêm vật tư '{mavt.upper()}' thành công!", "success")
        except Exception as exc:
            flash(f"Lỗi khi lưu vật tư: {exc}", "error")

        return redirect(url_for("vat_tu_page"))

    @app.route("/vat-tu/delete/<mavt>", methods=["POST"])
    @login_required
    def vat_tu_delete(mavt: str) -> Any:
        """Xóa vật tư nếu chưa phát sinh giao dịch và tồn kho bằng 0."""
        try:
            vat_tu_service.delete(mavt)
            flash(f"Đã xóa vật tư '{mavt}'.", "success")
        except Exception as exc:
            flash(f"Không thể xóa vật tư: {exc}", "error")
        return redirect(url_for("vat_tu_page"))

    @app.route("/vat-tu/undo", methods=["POST"])
    @login_required
    def vat_tu_undo() -> Any:
        """Hoàn tác thao tác Thêm / Sửa / Xóa gần nhất trên bảng Vật tư."""
        try:
            desc = vat_tu_service.undo()
            flash(f"Đã hoàn tác: {desc}", "undo_done")
        except Exception as exc:
            flash(f"Không thể hoàn tác: {exc}", "error")
        return redirect(url_for("vat_tu_page"))

    @app.route("/nhan-vien")
    @login_required
    def nhan_vien_page() -> Any:
        """Hiển thị trang Danh mục Nhân viên kèm tìm kiếm và trạng thái hoàn tác."""
        keyword = request.args.get("q", "").strip()
        all_rows = nhan_vien_service.list_all()
        rows = nhan_vien_service.list_all(keyword) if keyword else all_rows
        today = date.today()
        max_dob = date(today.year - 18, today.month, today.day).isoformat()
        min_dob = date(today.year - 65, today.month, today.day).isoformat()
        return render_template(
            "nhan_vien.html",
            active_page="nhan_vien",
            rows=rows,
            existing_manvs=[int(r["MANV"]) for r in all_rows],
            keyword=keyword,
            suggested_manv=next_manv(all_rows),
            max_dob=max_dob,
            min_dob=min_dob,
            can_undo=nhan_vien_service.can_undo,
            undo_count=nhan_vien_service.undo_count,
            next_undo=nhan_vien_service.next_undo_description,
        )

    @app.route("/nhan-vien/save", methods=["POST"])
    @admin_required
    def nhan_vien_save() -> Any:
        """Thêm mới (`mode=create`) hoặc cập nhật (`mode=update`) hồ sơ nhân viên (chỉ `Admin`)."""
        mode = request.form.get("mode", "create")
        manv = request.form.get("manv", "").strip()
        ho = request.form.get("ho", "").strip()
        ten = request.form.get("ten", "").strip()
        diachi = request.form.get("diachi", "").strip()
        ngaysinh = request.form.get("ngaysinh", "").strip()
        luong = request.form.get("luong", "0").strip()
        ghichu = request.form.get("ghichu", "").strip()

        try:
            if mode == "update":
                nhan_vien_service.update(manv, ho, ten, diachi, ngaysinh, luong, ghichu)
                flash(f"Đã cập nhật hồ sơ nhân viên mã {manv} thành công!", "success")
            else:
                nhan_vien_service.create(manv, ho, ten, diachi, ngaysinh, luong, ghichu)
                flash(f"Đã thêm nhân viên mã {manv} thành công!", "success")
        except Exception as exc:
            flash(f"Lỗi khi lưu nhân viên: {exc}", "error")

        return redirect(url_for("nhan_vien_page"))

    @app.route("/nhan-vien/delete/<int:manv>", methods=["POST"])
    @admin_required
    def nhan_vien_delete(manv: int) -> Any:
        """Xóa vật lý nhân viên chưa phát sinh chứng từ và chưa có tài khoản Login (chỉ `Admin`)."""
        try:
            nhan_vien_service.delete(manv, current_manv=auth_service.current_user.manv)
            flash(f"Đã xóa nhân viên mã {manv}.", "success")
        except Exception as exc:
            flash(f"Không thể xóa nhân viên: {exc}", "error")
        return redirect(url_for("nhan_vien_page"))

    @app.route("/nhan-vien/status/<int:manv>", methods=["POST"])
    @admin_required
    def nhan_vien_status(manv: int) -> Any:
        """Đổi trạng thái làm việc của nhân viên (Đang làm việc <-> Nghỉ việc, chỉ `Admin`)."""
        resigned = request.form.get("resigned") == "1"
        try:
            nhan_vien_service.set_work_status(
                manv,
                resigned=resigned,
                current_manv=auth_service.current_user.manv,
            )
            if resigned:
                flash(
                    f"Đã chuyển nhân viên mã {manv} sang trạng thái Nghỉ việc (và tự động thu hồi tài khoản nếu có).",
                    "success",
                )
            else:
                flash(f"Đã khôi phục trạng thái Đang làm việc cho nhân viên mã {manv}.", "success")
        except Exception as exc:
            flash(f"Không thể đổi trạng thái làm việc: {exc}", "error")
        return redirect(url_for("nhan_vien_page"))

    @app.route("/nhan-vien/undo", methods=["POST"])
    @admin_required
    def nhan_vien_undo() -> Any:
        """Hoàn tác thao tác gần nhất trên bảng Nhân viên (chỉ `Admin`)."""
        try:
            desc = nhan_vien_service.undo()
            flash(f"Đã hoàn tác: {desc}", "undo_done")
        except Exception as exc:
            flash(f"Không thể hoàn tác: {exc}", "error")
        return redirect(url_for("nhan_vien_page"))
