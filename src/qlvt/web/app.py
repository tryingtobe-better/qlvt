"""
Khởi tạo ứng dụng Flask (`create_app`) và đăng ký toàn bộ các phân hệ định tuyến (Routes):
- Hệ thống & Đăng nhập (`routes_he_thong`)
- Danh mục Nhân viên & Vật tư (`routes_danh_muc`)
- Giao dịch kho: Đơn đặt hàng, Phiếu nhập, Phiếu xuất (`routes_kho`)
- Báo biểu & Thống kê kho (`routes_bao_cao`)
"""

from pathlib import Path
from typing import Any

from flask import Flask

from qlvt import config
from qlvt.services import auth_service
from qlvt.web.routes_bao_cao import register_bao_cao_routes
from qlvt.web.routes_danh_muc import register_danh_muc_routes
from qlvt.web.routes_he_thong import register_he_thong_routes
from qlvt.web.routes_kho import register_kho_routes


def create_app() -> Flask:
    """Tạo đối tượng Flask, cấu hình thư mục giao diện (`templates`) và gắn các biến dùng chung."""
    template_dir = Path(__file__).resolve().parent / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    app.secret_key = "qlvt-local-web-secret-key"
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        """Tự động truyền `current_user` và `permissions` vào mọi template Jinja2."""
        return {
            "current_user": auth_service.current_user,
            "permissions": auth_service.get_permissions(),
        }

    register_he_thong_routes(app)
    register_danh_muc_routes(app)
    register_kho_routes(app)
    register_bao_cao_routes(app)

    return app


def run_app(host: str = "127.0.0.1", port: int = 5000) -> None:
    """Khởi chạy máy chủ web Flask tại địa chỉ `http://127.0.0.1:5000`."""
    app = create_app()
    print(f"=== QLVT Web Local đang chạy tại: http://{host}:{port} ===")
    app.run(host=host, port=port, debug=config.DEBUG)
