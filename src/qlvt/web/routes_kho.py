"""
Các Route thuộc phân hệ Giao Dịch Kho (Master-Detail):
- `/dat-hang` và các route con: Lập, sửa, xóa Đơn đặt hàng (`DatHang`) & Chi tiết đơn đặt hàng (`CTDDH`).
- `/phieu-nhap` và các route con: Lập, sửa, xóa Phiếu nhập kho (`PhieuNhap`) & Chi tiết phiếu nhập (`CTPN`).
- `/phieu-xuat` và các route con: Lập, sửa, xóa Phiếu xuất kho (`PhieuXuat`) & Chi tiết phiếu xuất (`CTPX`).
"""

from datetime import date
from typing import Any

from flask import Flask, flash, redirect, render_template, request, url_for

from qlvt.services import (
    auth_service,
    dat_hang_service,
    phieu_nhap_service,
    phieu_xuat_service,
    vat_tu_service,
)
from qlvt.web.helpers import login_required, next_code


def register_kho_routes(app: Flask) -> None:
    """Đăng ký các đường dẫn thuộc nhóm chức năng Giao dịch kho (Đặt hàng, Nhập kho, Xuất kho)."""

    # =========================================================================
    # 1. ĐƠN ĐẶT HÀNG (DatHang - CTDDH)
    # =========================================================================
    @app.route("/dat-hang")
    @login_required
    def dat_hang_page() -> Any:
        """Hiển thị giao diện Master-Detail quản lý Đơn đặt hàng và Chi tiết đơn đặt hàng."""
        keyword = request.args.get("q", "").strip()
        all_orders = dat_hang_service.list_orders()
        orders = dat_hang_service.list_orders(keyword) if keyword else all_orders
        select_id = request.args.get("select", "").strip()
        if not select_id and orders:
            select_id = orders[0]["MasoDDH"]

        selected_order = dat_hang_service.get_order(select_id) if select_id else None
        details = dat_hang_service.list_details(select_id) if selected_order else []

        can_modify, lock_reason = (
            dat_hang_service.check_modify_permission(
                selected_order,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            if selected_order
            else (False, None)
        )

        all_materials = vat_tu_service.list_all()
        existing_map = {ct["MAVT"]: ct for ct in details}
        unadded_materials = [vt for vt in all_materials if vt["MAVT"] not in existing_map]
        added_materials = [
            {**vt, "SoLuongDaDat": existing_map[vt["MAVT"]]["SOLUONG"]}
            for vt in all_materials
            if vt["MAVT"] in existing_map
        ]

        return render_template(
            "dat_hang.html",
            active_page="dat_hang",
            orders=orders,
            existing_ddhs=[str(r["MasoDDH"]).strip().upper() for r in all_orders],
            selected_order=selected_order,
            details=details,
            can_modify=can_modify,
            lock_reason=lock_reason,
            suggested_ddh=next_code(all_orders, "MasoDDH", "DDH", 5),
            unadded_materials=unadded_materials,
            added_materials=added_materials,
            keyword=keyword,
            today=str(date.today()),
            can_undo=dat_hang_service.can_undo,
            undo_count=dat_hang_service.undo_count,
            next_undo=dat_hang_service.next_undo_description,
        )

    @app.route("/dat-hang/create", methods=["POST"])
    @login_required
    def dat_hang_create() -> Any:
        """Lập đầu đơn đặt hàng mới."""
        maso_ddh = request.form.get("maso_ddh", "").strip().upper()
        ngay = request.form.get("ngay", "").strip()
        nhacc = request.form.get("nhacc", "").strip()
        manv = auth_service.current_user.manv

        try:
            dat_hang_service.create_order(maso_ddh, ngay, nhacc, manv)
            flash(
                f"Đã lập Đơn đặt hàng '{maso_ddh}'! Mời bạn thêm mặt hàng ở khung bên phải.",
                "success",
            )
            return redirect(url_for("dat_hang_page", select=maso_ddh))
        except Exception as exc:
            flash(f"Không thể tạo đơn đặt hàng: {exc}", "error")
            return redirect(url_for("dat_hang_page"))

    @app.route("/dat-hang/update/<maso_ddh>", methods=["POST"])
    @login_required
    def dat_hang_update(maso_ddh: str) -> Any:
        """Cập nhật thông tin đầu đơn đặt hàng (khi chưa nhập đủ)."""
        ngay = request.form.get("ngay", "").strip()
        nhacc = request.form.get("nhacc", "").strip()
        try:
            dat_hang_service.update_order(
                maso_ddh,
                ngay,
                nhacc,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã cập nhật thông tin Đơn đặt hàng '{maso_ddh}'.", "success")
        except Exception as exc:
            flash(f"Không thể cập nhật đơn đặt hàng: {exc}", "error")
        return redirect(url_for("dat_hang_page", select=maso_ddh))

    @app.route("/dat-hang/delete/<maso_ddh>", methods=["POST"])
    @login_required
    def dat_hang_delete(maso_ddh: str) -> Any:
        """Xóa đơn đặt hàng (khi chưa có phiếu nhập)."""
        try:
            dat_hang_service.delete_order(
                maso_ddh,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã xóa Đơn đặt hàng '{maso_ddh}'.", "success")
        except Exception as exc:
            flash(f"Không thể xóa đơn đặt hàng: {exc}", "error")
        return redirect(url_for("dat_hang_page"))

    @app.route("/dat-hang/<maso_ddh>/add-detail", methods=["POST"])
    @login_required
    def dat_hang_add_detail(maso_ddh: str) -> Any:
        """Thêm hoặc cộng dồn mặt hàng vào chi tiết đơn đặt hàng (`CTDDH`)."""
        mavt = request.form.get("mavt", "").strip()
        soluong = request.form.get("soluong", "0").strip()
        dongia = request.form.get("dongia", "0").strip()
        try:
            merged, total_sl = dat_hang_service.add_detail(
                maso_ddh,
                mavt,
                soluong,
                dongia,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            if merged:
                flash(
                    f"Mặt hàng '{mavt}' đã có trong đơn '{maso_ddh}', hệ thống đã tự động cộng dồn thêm {soluong} (tổng SL đặt: {total_sl}).",
                    "success",
                )
            else:
                flash(f"Đã thêm mặt hàng '{mavt}' (SL: {total_sl}) vào đơn '{maso_ddh}'.", "success")
        except Exception as exc:
            flash(f"Không thể thêm mặt hàng vào đơn: {exc}", "error")
        return redirect(url_for("dat_hang_page", select=maso_ddh))

    @app.route("/dat-hang/<maso_ddh>/update-detail/<mavt>", methods=["POST"])
    @login_required
    def dat_hang_update_detail(maso_ddh: str, mavt: str) -> Any:
        """Cập nhật số lượng / đơn giá của một dòng chi tiết đơn đặt hàng."""
        soluong = request.form.get("soluong", "0").strip()
        dongia = request.form.get("dongia", "0").strip()
        try:
            dat_hang_service.update_detail(
                maso_ddh,
                mavt,
                soluong,
                dongia,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã cập nhật số lượng/đơn giá mặt hàng '{mavt}' trong đơn '{maso_ddh}'.", "success")
        except Exception as exc:
            flash(f"Không thể cập nhật mặt hàng: {exc}", "error")
        return redirect(url_for("dat_hang_page", select=maso_ddh))

    @app.route("/dat-hang/<maso_ddh>/delete-detail/<mavt>", methods=["POST"])
    @login_required
    def dat_hang_delete_detail(maso_ddh: str, mavt: str) -> Any:
        """Xóa một dòng mặt hàng khỏi chi tiết đơn đặt hàng."""
        try:
            dat_hang_service.delete_detail(
                maso_ddh,
                mavt,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã xóa mặt hàng '{mavt}' khỏi đơn '{maso_ddh}'.", "success")
        except Exception as exc:
            flash(f"Không thể xóa mặt hàng khỏi đơn: {exc}", "error")
        return redirect(url_for("dat_hang_page", select=maso_ddh))

    @app.route("/dat-hang/undo", methods=["POST"])
    @login_required
    def dat_hang_undo() -> Any:
        """Hoàn tác thao tác gần nhất trên Đơn đặt hàng / Chi tiết ĐĐH."""
        try:
            desc, target_id = dat_hang_service.undo_with_target()
            flash(f"Đã hoàn tác: {desc}", "undo_done")
            if target_id:
                return redirect(url_for("dat_hang_page", select=target_id))
        except Exception as exc:
            flash(f"Không thể hoàn tác: {exc}", "error")
        return redirect(url_for("dat_hang_page"))

    # =========================================================================
    # 2. PHIẾU NHẬP KHO (PhieuNhap - CTPN)
    # =========================================================================
    @app.route("/phieu-nhap")
    @login_required
    def phieu_nhap_page() -> Any:
        """Hiển thị giao diện Master-Detail quản lý Phiếu nhập kho và Chi tiết phiếu nhập."""
        keyword = request.args.get("q", "").strip()
        all_receipts = phieu_nhap_service.list_receipts()
        receipts = phieu_nhap_service.list_receipts(keyword) if keyword else all_receipts
        select_id = request.args.get("select", "").strip()
        if not select_id and receipts:
            select_id = receipts[0]["MAPN"]

        selected_receipt = phieu_nhap_service.get_receipt(select_id) if select_id else None
        details = phieu_nhap_service.list_details(select_id) if selected_receipt else []
        available_items = (
            phieu_nhap_service.list_available_items_for_order(selected_receipt["MasoDDH"])
            if selected_receipt
            else []
        )

        can_modify, lock_reason = (
            phieu_nhap_service.check_modify_permission(
                selected_receipt,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            if selected_receipt
            else (False, None)
        )
        can_delete_receipt, delete_lock_reason = (
            phieu_nhap_service.check_delete_permission(
                selected_receipt,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            if selected_receipt
            else (False, None)
        )

        return render_template(
            "phieu_nhap.html",
            active_page="phieu_nhap",
            receipts=receipts,
            existing_mapns=[str(r["MAPN"]).strip().upper() for r in all_receipts],
            selected_receipt=selected_receipt,
            details=details,
            can_modify=can_modify,
            lock_reason=lock_reason,
            can_delete_receipt=can_delete_receipt,
            delete_lock_reason=delete_lock_reason,
            suggested_mapn=next_code(all_receipts, "MAPN", "PN", 6),
            available_orders=phieu_nhap_service.list_orders_available_for_import(),
            available_items=available_items,
            keyword=keyword,
            today=str(date.today()),
            can_undo=phieu_nhap_service.can_undo,
            undo_count=phieu_nhap_service.undo_count,
            next_undo=phieu_nhap_service.next_undo_description,
        )

    @app.route("/phieu-nhap/create", methods=["POST"])
    @login_required
    def phieu_nhap_create() -> Any:
        """Lập đầu phiếu nhập kho mới theo một Đơn đặt hàng còn thiếu hàng."""
        mapn = request.form.get("mapn", "").strip().upper()
        maso_ddh = request.form.get("maso_ddh", "").strip().upper()
        ngay = request.form.get("ngay", "").strip()
        manv = auth_service.current_user.manv

        try:
            phieu_nhap_service.create_receipt(mapn, ngay, maso_ddh, manv)
            flash(
                f"Đã tạo Phiếu nhập '{mapn}' cho đơn '{maso_ddh}'! Mời bạn chọn mặt hàng nhập kho ở khung bên phải.",
                "success",
            )
            return redirect(url_for("phieu_nhap_page", select=mapn))
        except Exception as exc:
            flash(f"Không thể tạo phiếu nhập: {exc}", "error")
            return redirect(url_for("phieu_nhap_page"))

    @app.route("/phieu-nhap/update/<mapn>", methods=["POST"])
    @login_required
    def phieu_nhap_update(mapn: str) -> Any:
        """Cập nhật Ngày nhập kho của phiếu nhập."""
        ngay = request.form.get("ngay", "").strip()
        try:
            phieu_nhap_service.update_receipt(
                mapn,
                ngay,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã cập nhật ngày nhập của Phiếu nhập '{mapn}'.", "success")
        except Exception as exc:
            flash(f"Không thể cập nhật phiếu nhập: {exc}", "error")
        return redirect(url_for("phieu_nhap_page", select=mapn))

    @app.route("/phieu-nhap/delete/<mapn>", methods=["POST"])
    @login_required
    def phieu_nhap_delete(mapn: str) -> Any:
        """Xóa phiếu nhập kho (nếu đủ tồn kho để trừ ngược lại)."""
        try:
            phieu_nhap_service.delete_receipt(
                mapn,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã xóa Phiếu nhập '{mapn}'.", "success")
        except Exception as exc:
            flash(f"Không thể xóa phiếu nhập: {exc}", "error")
            return redirect(url_for("phieu_nhap_page", select=mapn))
        return redirect(url_for("phieu_nhap_page"))

    @app.route("/phieu-nhap/<mapn>/add-detail", methods=["POST"])
    @login_required
    def phieu_nhap_add_detail(mapn: str) -> Any:
        """Thêm mặt hàng vào phiếu nhập (`CTPN`) và tự động tăng tồn kho qua Trigger."""
        mavt = request.form.get("mavt", "").strip()
        soluong = request.form.get("soluong", "0").strip()
        dongia = request.form.get("dongia", "0").strip()
        try:
            merged, total_sl = phieu_nhap_service.add_detail(
                mapn,
                mavt,
                soluong,
                dongia,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            if merged:
                flash(
                    f"Đã nhập bổ sung {soluong} '{mavt}' vào phiếu '{mapn}' (tổng trong phiếu: {total_sl}, tồn kho đã tự động cộng thêm).",
                    "success",
                )
            else:
                flash(
                    f"Đã nhập {total_sl} '{mavt}' vào phiếu '{mapn}' (Tồn kho đã tự động cộng thêm).",
                    "success",
                )
        except Exception as exc:
            flash(f"Không thể ghi mặt hàng vào phiếu nhập: {exc}", "error")
        return redirect(url_for("phieu_nhap_page", select=mapn))

    @app.route("/phieu-nhap/<mapn>/update-detail/<mavt>", methods=["POST"])
    @login_required
    def phieu_nhap_update_detail(mapn: str, mavt: str) -> Any:
        """Cập nhật số lượng / đơn giá mặt hàng trong phiếu nhập."""
        soluong = request.form.get("soluong", "0").strip()
        dongia = request.form.get("dongia", "0").strip()
        try:
            phieu_nhap_service.update_detail(
                mapn,
                mavt,
                soluong,
                dongia,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(
                f"Đã cập nhật mặt hàng '{mavt}' trong phiếu '{mapn}' (Tồn kho đã tự động điều chỉnh).",
                "success",
            )
        except Exception as exc:
            flash(f"Không thể cập nhật mặt hàng: {exc}", "error")
        return redirect(url_for("phieu_nhap_page", select=mapn))

    @app.route("/phieu-nhap/<mapn>/delete-detail/<mavt>", methods=["POST"])
    @login_required
    def phieu_nhap_delete_detail(mapn: str, mavt: str) -> Any:
        """Xóa một dòng mặt hàng khỏi phiếu nhập."""
        try:
            phieu_nhap_service.delete_detail(
                mapn,
                mavt,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã xóa mặt hàng '{mavt}' khỏi phiếu nhập '{mapn}'.", "success")
        except Exception as exc:
            flash(f"Không thể xóa mặt hàng khỏi phiếu nhập: {exc}", "error")
        return redirect(url_for("phieu_nhap_page", select=mapn))

    @app.route("/phieu-nhap/undo", methods=["POST"])
    @login_required
    def phieu_nhap_undo() -> Any:
        """Hoàn tác thao tác gần nhất trên Phiếu nhập / Chi tiết phiếu nhập."""
        try:
            desc, target_id = phieu_nhap_service.undo_with_target()
            flash(f"Đã hoàn tác: {desc}", "undo_done")
            if target_id:
                return redirect(url_for("phieu_nhap_page", select=target_id))
        except Exception as exc:
            flash(f"Không thể hoàn tác: {exc}", "error")
        return redirect(url_for("phieu_nhap_page"))

    # =========================================================================
    # 3. PHIẾU XUẤT KHO (PhieuXuat - CTPX)
    # =========================================================================
    @app.route("/phieu-xuat")
    @login_required
    def phieu_xuat_page() -> Any:
        """Hiển thị giao diện Master-Detail quản lý Phiếu xuất kho và Chi tiết phiếu xuất."""
        keyword = request.args.get("q", "").strip()
        all_exports = phieu_xuat_service.list_exports()
        exports = phieu_xuat_service.list_exports(keyword) if keyword else all_exports
        select_id = request.args.get("select", "").strip()
        if not select_id and exports:
            select_id = exports[0]["MAPX"]

        selected_export = phieu_xuat_service.get_export(select_id) if select_id else None
        details = phieu_xuat_service.list_details(select_id) if selected_export else []
        can_modify, lock_reason = (
            phieu_xuat_service.check_modify_permission(
                selected_export,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            if selected_export
            else (False, None)
        )

        all_materials = vat_tu_service.list_all()
        existing_map = {ct["MAVT"]: ct for ct in details}
        unadded_materials = [vt for vt in all_materials if vt["MAVT"] not in existing_map]
        added_materials = [
            {**vt, "SoLuongDaXuat": existing_map[vt["MAVT"]]["SOLUONG"]}
            for vt in all_materials
            if vt["MAVT"] in existing_map
        ]

        return render_template(
            "phieu_xuat.html",
            active_page="phieu_xuat",
            exports=exports,
            existing_mapxs=[str(r["MAPX"]).strip().upper() for r in all_exports],
            selected_export=selected_export,
            details=details,
            can_modify=can_modify,
            lock_reason=lock_reason,
            suggested_mapx=next_code(all_exports, "MAPX", "PX", 6),
            unadded_materials=unadded_materials,
            added_materials=added_materials,
            keyword=keyword,
            today=str(date.today()),
            can_undo=phieu_xuat_service.can_undo,
            undo_count=phieu_xuat_service.undo_count,
            next_undo=phieu_xuat_service.next_undo_description,
        )

    @app.route("/phieu-xuat/create", methods=["POST"])
    @login_required
    def phieu_xuat_create() -> Any:
        """Lập đầu phiếu xuất kho mới."""
        mapx = request.form.get("mapx", "").strip().upper()
        ngay = request.form.get("ngay", "").strip()
        hotenkh = request.form.get("hotenkh", "").strip()
        manv = auth_service.current_user.manv

        try:
            phieu_xuat_service.create_export(mapx, ngay, hotenkh, manv)
            flash(
                f"Đã tạo Phiếu xuất '{mapx}'! Mời bạn chọn mặt hàng xuất kho ở khung bên phải.",
                "success",
            )
            return redirect(url_for("phieu_xuat_page", select=mapx))
        except Exception as exc:
            flash(f"Không thể tạo phiếu xuất: {exc}", "error")
            return redirect(url_for("phieu_xuat_page"))

    @app.route("/phieu-xuat/update/<mapx>", methods=["POST"])
    @login_required
    def phieu_xuat_update(mapx: str) -> Any:
        """Cập nhật thông tin đầu phiếu xuất kho (Ngày xuất, Họ tên khách hàng)."""
        ngay = request.form.get("ngay", "").strip()
        hotenkh = request.form.get("hotenkh", "").strip()
        try:
            phieu_xuat_service.update_export(
                mapx,
                ngay,
                hotenkh,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã cập nhật thông tin Phiếu xuất '{mapx}'.", "success")
        except Exception as exc:
            flash(f"Không thể cập nhật phiếu xuất: {exc}", "error")
        return redirect(url_for("phieu_xuat_page", select=mapx))

    @app.route("/phieu-xuat/delete/<mapx>", methods=["POST"])
    @login_required
    def phieu_xuat_delete(mapx: str) -> Any:
        """Xóa phiếu xuất kho (hoàn trả tồn kho qua Trigger)."""
        try:
            phieu_xuat_service.delete_export(
                mapx,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã xóa Phiếu xuất '{mapx}' (tồn kho các mặt hàng trong phiếu đã được hoàn trả).", "success")
        except Exception as exc:
            flash(f"Không thể xóa phiếu xuất: {exc}", "error")
            return redirect(url_for("phieu_xuat_page", select=mapx))
        return redirect(url_for("phieu_xuat_page"))

    @app.route("/phieu-xuat/<mapx>/add-detail", methods=["POST"])
    @login_required
    def phieu_xuat_add_detail(mapx: str) -> Any:
        """Thêm hoặc cộng dồn mặt hàng vào phiếu xuất (`CTPX`) và tự động trừ tồn kho qua Trigger."""
        mavt = request.form.get("mavt", "").strip()
        soluong = request.form.get("soluong", "0").strip()
        dongia = request.form.get("dongia", "0").strip()
        try:
            merged, total_sl = phieu_xuat_service.add_detail(
                mapx,
                mavt,
                soluong,
                dongia,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            if merged:
                flash(
                    f"Đã xuất bổ sung {soluong} '{mavt}' trong phiếu '{mapx}' (tổng SL xuất: {total_sl}, tồn kho đã tự động trừ).",
                    "success",
                )
            else:
                flash(
                    f"Đã xuất {total_sl} '{mavt}' trong phiếu '{mapx}' (Tồn kho đã tự động trừ).",
                    "success",
                )
        except Exception as exc:
            flash(f"Không thể ghi mặt hàng vào phiếu xuất: {exc}", "error")
        return redirect(url_for("phieu_xuat_page", select=mapx))

    @app.route("/phieu-xuat/<mapx>/update-detail/<mavt>", methods=["POST"])
    @login_required
    def phieu_xuat_update_detail(mapx: str, mavt: str) -> Any:
        """Cập nhật số lượng / đơn giá mặt hàng trong phiếu xuất."""
        soluong = request.form.get("soluong", "0").strip()
        dongia = request.form.get("dongia", "0").strip()
        try:
            phieu_xuat_service.update_detail(
                mapx,
                mavt,
                soluong,
                dongia,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã cập nhật mặt hàng '{mavt}' trong phiếu xuất '{mapx}'.", "success")
        except Exception as exc:
            flash(f"Không thể cập nhật mặt hàng: {exc}", "error")
        return redirect(url_for("phieu_xuat_page", select=mapx))

    @app.route("/phieu-xuat/<mapx>/delete-detail/<mavt>", methods=["POST"])
    @login_required
    def phieu_xuat_delete_detail(mapx: str, mavt: str) -> Any:
        """Xóa một dòng mặt hàng khỏi phiếu xuất (hoàn trả tồn kho qua Trigger)."""
        try:
            phieu_xuat_service.delete_detail(
                mapx,
                mavt,
                current_manv=auth_service.current_user.manv,
                is_admin=auth_service.current_user.is_admin,
            )
            flash(f"Đã xóa mặt hàng '{mavt}' khỏi phiếu xuất '{mapx}'.", "success")
        except Exception as exc:
            flash(f"Không thể xóa mặt hàng khỏi phiếu xuất: {exc}", "error")
        return redirect(url_for("phieu_xuat_page", select=mapx))

    @app.route("/phieu-xuat/undo", methods=["POST"])
    @login_required
    def phieu_xuat_undo() -> Any:
        """Hoàn tác thao tác gần nhất trên Phiếu xuất / Chi tiết phiếu xuất."""
        try:
            desc, target_id = phieu_xuat_service.undo_with_target()
            flash(f"Đã hoàn tác: {desc}", "undo_done")
            if target_id:
                return redirect(url_for("phieu_xuat_page", select=target_id))
        except Exception as exc:
            flash(f"Không thể hoàn tác: {exc}", "error")
        return redirect(url_for("phieu_xuat_page"))
