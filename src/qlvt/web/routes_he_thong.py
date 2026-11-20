"""
Các Route thuộc phân hệ Hệ Thống:
- `/login`, `/logout`: Đăng nhập và đăng xuất tài khoản SQL Server.
- `/`: Trang Tổng quan (Dashboard) gọi `dbo.SP_ThongKeTongQuan`.
- `/accounts`, `/accounts/create`, `/accounts/delete`: Quản lý tài khoản đăng nhập (chỉ `Admin`).
- `/backup`: Sao lưu cơ sở dữ liệu `QLVT` ra file `.bak` (chỉ `Admin`).
"""

from typing import Any

from flask import Flask, flash, redirect, render_template, request, url_for

from qlvt.database import db
from qlvt.services import (
    auth_service,
    dat_hang_service,
    nhan_vien_service,
    phieu_nhap_service,
    phieu_xuat_service,
    vat_tu_service,
)
from qlvt.web.helpers import admin_required, login_required


def _clear_all_undo_stacks() -> None:
    """Xóa toàn bộ ngăn xếp hoàn tác (Undo) khi đổi phiên đăng nhập hoặc đăng xuất."""
    for svc in (
        nhan_vien_service,
        vat_tu_service,
        dat_hang_service,
        phieu_nhap_service,
        phieu_xuat_service,
    ):
        svc.undo_stack.clear()


def register_he_thong_routes(app: Flask) -> None:
    """Đăng ký các đường dẫn thuộc nhóm chức năng Hệ thống & Quản trị."""

    @app.route("/login", methods=["GET", "POST"])
    def login() -> Any:
        """Trang đăng nhập hệ thống bằng tài khoản SQL Server Login."""
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            try:
                user = auth_service.login(username=username, password=password)
                _clear_all_undo_stacks()
                role_label = "Quản trị viên" if user.is_admin else "Nhân viên"
                flash(f"Xin chào {user.ho_ten} (Mã NV: {user.manv} — {role_label}).", "info")
                return redirect(url_for("dashboard"))
            except Exception as exc:
                flash(f"Đăng nhập thất bại: {exc}", "error")

        return render_template("login.html", active_page="login")

    @app.route("/logout")
    def logout() -> Any:
        """Đăng xuất khỏi phiên làm việc hiện tại."""
        _clear_all_undo_stacks()
        auth_service.logout()
        flash("Đã đăng xuất khỏi hệ thống.", "info")
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard() -> Any:
        """Trang Tổng quan (Dashboard) lấy số liệu thống kê qua `dbo.SP_ThongKeTongQuan`."""
        stats = db.fetch_one("EXEC dbo.SP_ThongKeTongQuan")
        return render_template(
            "dashboard.html",
            active_page="dashboard",
            stats=stats,
        )

    @app.route("/accounts")
    @admin_required
    def accounts_page() -> Any:
        """Trang Quản lý tài khoản đăng nhập (liệt kê nhân viên và trạng thái Login/Role)."""
        accounts = auth_service.list_accounts()
        available_employees = [
            r
            for r in accounts
            if not r["DaCoTaiKhoan"] and not int(r.get("TrangThaiXoa") or 0)
        ]
        return render_template(
            "accounts.html",
            active_page="accounts",
            accounts=accounts,
            available_employees=available_employees,
        )

    @app.route("/accounts/create", methods=["POST"])
    @admin_required
    def create_account_route() -> Any:
        """Xử lý form cấp tài khoản đăng nhập mới cho nhân viên."""
        manv = request.form.get("manv", "").strip()
        login_name = request.form.get("login_name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "NhanVien").strip()

        try:
            code, msg = auth_service.create_account(
                login_name=login_name,
                password=password,
                manv=manv,
                role=role,
            )
            flash(msg, "success" if code == 0 else "error")
        except Exception as exc:
            flash(f"Lỗi khi tạo tài khoản: {exc}", "error")

        return redirect(url_for("accounts_page"))

    @app.route("/accounts/delete", methods=["POST"])
    @admin_required
    def delete_account_route() -> Any:
        """Xử lý thu hồi (xóa) tài khoản đăng nhập của nhân viên."""
        login_name = request.form.get("login_name", "").strip()
        manv = request.form.get("manv", "").strip()

        try:
            code, msg = auth_service.delete_account(login_name=login_name, manv=manv)
            flash(msg, "success" if code == 0 else "error")
        except Exception as exc:
            flash(f"Lỗi khi xóa tài khoản: {exc}", "error")

        return redirect(url_for("accounts_page"))

    @app.route("/accounts/change-password", methods=["POST"])
    @admin_required
    def change_password_route() -> Any:
        """Xử lý đổi mật khẩu tài khoản đăng nhập (chỉ `Admin`)."""
        login_name = request.form.get("login_name", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password != confirm_password:
            flash("Mật khẩu xác nhận không khớp với mật khẩu mới!", "error")
            return redirect(url_for("accounts_page"))

        try:
            code, msg = auth_service.change_password(
                login_name=login_name,
                new_password=new_password,
            )
            flash(msg, "success" if code == 0 else "error")
        except Exception as exc:
            flash(f"Lỗi khi đổi mật khẩu: {exc}", "error")

        return redirect(url_for("accounts_page"))

    @app.route("/backup", methods=["GET", "POST"])
    @admin_required
    def backup_page() -> Any:
        """Trang Sao lưu cơ sở dữ liệu `QLVT` ra file `.bak`."""
        default_backup_path = str(auth_service.get_default_backup_dir() / "QLVT_Full.bak")
        if request.method == "POST":
            backup_path = request.form.get("backup_path", "").strip() or default_backup_path
            overwrite = request.form.get("overwrite") == "1"
            try:
                saved = auth_service.backup_database(
                    backup_file_path=backup_path,
                    overwrite=overwrite,
                )
                flash(f"Sao lưu CSDL QLVT thành công tại: {saved}", "success")
            except Exception as exc:
                flash(f"Không thể sao lưu CSDL: {exc}", "error")

        return render_template(
            "backup.html",
            active_page="backup",
            default_backup_path=default_backup_path,
        )
