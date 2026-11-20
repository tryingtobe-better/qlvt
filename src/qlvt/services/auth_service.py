"""
Xử lý nghiệp vụ Hệ thống, Đăng nhập, Phân quyền và Sao lưu CSDL:
Gọi các Stored Procedure trong `sql/03_auth_and_system.sql`:
- `dbo.SP_DangNhap`
- `dbo.SP_DanhSachTaiKhoan`, `dbo.SP_TaoTaiKhoan`, `dbo.SP_XoaTaiKhoan`
- `dbo.SP_LayThuMucBackupMacDinh`, `dbo.SP_SaoLuuCSDL`
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qlvt.database import db


@dataclass
class SessionUser:
    """Thông tin phiên đăng nhập hiện tại của người dùng."""

    login_name: str
    manv: str
    ho_ten: str
    role: str

    @property
    def is_admin(self) -> bool:
        """Kiểm tra người dùng có thuộc nhóm quyền `Admin` hay không."""
        return self.role.strip().lower() == "admin"


class AuthService:
    """Dịch vụ xác thực, phân quyền người dùng và quản trị hệ thống."""

    def __init__(self) -> None:
        self.current_user: Optional[SessionUser] = None

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> SessionUser:
        """
        Đăng nhập vào SQL Server bằng `username`/`password` người dùng nhập,
        sau đó gọi `dbo.SP_DangNhap` để lấy Mã NV, Họ tên và Nhóm quyền (`Admin` / `NhanVien`).
        """
        if not username or not username.strip():
            raise ValueError("Vui lòng nhập tên đăng nhập!")
        if password is None or password == "":
            raise ValueError("Vui lòng nhập mật khẩu!")

        actual_login = username.strip()
        db.set_credentials(actual_login, password)

        try:
            with db.session(autocommit=True) as conn:
                cursor = conn.cursor()
                cursor.execute("EXEC dbo.SP_DangNhap @TenLogin = ?", (actual_login,))
                row = cursor.fetchone()
                if not row or not getattr(row, "TENNHOM", None):
                    raise PermissionError(
                        f"Tài khoản '{actual_login}' chưa được phân quyền trong CSDL QLVT!"
                    )
                if int(getattr(row, "TrangThaiXoa", 0) or 0) == 1:
                    raise PermissionError(
                        f"Nhân viên '{str(row.HOTEN).strip()}' đã nghỉ việc, tài khoản không còn hiệu lực đăng nhập!"
                    )

                session_user = SessionUser(
                    login_name=actual_login,
                    manv=str(row.MANV).strip(),
                    ho_ten=str(row.HOTEN).strip(),
                    role=str(row.TENNHOM).strip(),
                )
                self.current_user = session_user
                return session_user
        except Exception:
            db.set_credentials(None, None)
            self.current_user = None
            raise

    def logout(self) -> None:
        """Đăng xuất và xóa thông tin xác thực trên kết nối DB."""
        self.current_user = None
        db.set_credentials(None, None)

    def get_permissions(self) -> Dict[str, bool]:
        """Trả về cờ quyền hạn để hiển thị hoặc khóa các menu quản trị trên giao diện."""
        is_admin = bool(self.current_user and self.current_user.is_admin)
        return {
            "can_manage_login": is_admin,
            "can_backup_db": is_admin,
        }

    def list_accounts(self) -> List[Dict[str, Any]]:
        """Lấy danh sách nhân viên kèm trạng thái tài khoản Login và Role (`dbo.SP_DanhSachTaiKhoan`)."""
        return db.fetch_all("EXEC dbo.SP_DanhSachTaiKhoan")

    def create_account(
        self,
        login_name: str,
        password: str,
        manv: int | str,
        role: str,
    ) -> Tuple[int, str]:
        """Tạo SQL Login và Database User ánh xạ với Mã NV thông qua `dbo.SP_TaoTaiKhoan`."""
        if self.current_user and not self.current_user.is_admin:
            raise PermissionError("Chỉ nhóm quyền Admin mới được phép tạo tài khoản Login!")

        login_clean = login_name.strip()
        user_clean = str(manv).strip()
        role_clean = role.strip()

        if not login_clean:
            raise ValueError("Tên đăng nhập (LoginName) không được để trống!")
        if not password:
            raise ValueError("Mật khẩu không được để trống!")
        if role_clean not in ("Admin", "NhanVien"):
            raise ValueError("Nhóm quyền chỉ được chọn 'Admin' hoặc 'NhanVien'!")

        with db.session(autocommit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "EXEC dbo.SP_TaoTaiKhoan @LoginName = ?, @Password = ?, @UserName = ?, @Role = ?",
                (login_clean, password, user_clean, role_clean),
            )
            row = cursor.fetchone()
            if row:
                return int(row.RetCode), str(row.ThongBao)
            return 0, "Tạo tài khoản đăng nhập thành công!"

    def delete_account(self, login_name: str, manv: int | str) -> Tuple[int, str]:
        """Xóa tài khoản đăng nhập của nhân viên thông qua `dbo.SP_XoaTaiKhoan`."""
        if self.current_user and not self.current_user.is_admin:
            raise PermissionError("Chỉ nhóm quyền Admin mới được phép xóa tài khoản Login!")

        login_clean = login_name.strip()
        user_clean = str(manv).strip()

        if self.current_user and self.current_user.login_name.lower() == login_clean.lower():
            raise ValueError("Không thể xóa tài khoản đang đăng nhập hiện tại!")

        with db.session(autocommit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "EXEC dbo.SP_XoaTaiKhoan @LoginName = ?, @UserName = ?",
                (login_clean, user_clean),
            )
            row = cursor.fetchone()
            if row:
                return int(row.RetCode), str(row.ThongBao)
            return 0, "Đã xóa tài khoản đăng nhập thành công!"

    def change_password(self, login_name: str, new_password: str) -> Tuple[int, str]:
        """Đổi mật khẩu cho một tài khoản SQL Login thông qua `dbo.SP_DoiMatKhau` (chỉ dành cho `Admin`)."""
        if self.current_user and not self.current_user.is_admin:
            raise PermissionError("Chỉ nhóm quyền Admin mới được phép thay đổi mật khẩu tài khoản!")

        login_clean = (login_name or "").strip()
        if not login_clean:
            raise ValueError("Tên đăng nhập không được để trống!")
        if not new_password or len(new_password) < 3:
            raise ValueError("Mật khẩu mới phải từ 3 ký tự trở lên!")

        with db.session(autocommit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "EXEC dbo.SP_DoiMatKhau @LoginName = ?, @NewPassword = ?",
                (login_clean, new_password),
            )
            row = cursor.fetchone()
            ret_code = int(row.RetCode) if row else 0
            msg = str(row.ThongBao) if row else f"Đã đổi mật khẩu tài khoản '{login_clean}' thành công!"

        if (
            ret_code == 0
            and self.current_user
            and self.current_user.login_name.lower() == login_clean.lower()
        ):
            db.set_credentials(self.current_user.login_name, new_password)

        return ret_code, msg

    def get_default_backup_dir(self) -> Path:
        """Lấy đường dẫn thư mục Backup mặc định của SQL Server qua `dbo.SP_LayThuMucBackupMacDinh`."""
        try:
            row = db.fetch_one("EXEC dbo.SP_LayThuMucBackupMacDinh")
            if row and row.get("backup_dir"):
                return Path(str(row["backup_dir"]).strip())
        except Exception:
            pass
        return Path("C:/Backup")

    def backup_database(
        self, backup_file_path: Optional[str | Path] = None, overwrite: bool = True
    ) -> str:
        """Thực thi sao lưu CSDL qua Stored Procedure `dbo.SP_SaoLuuCSDL` (chỉ dành cho nhóm `Admin`)."""
        if self.current_user and not self.current_user.is_admin:
            raise PermissionError("Nhóm NhanVien không có quyền sao lưu cơ sở dữ liệu!")

        if backup_file_path is None:
            target_path = self.get_default_backup_dir() / "QLVT_Full.bak"
        else:
            target_path = Path(backup_file_path)

        path_str = str(target_path)
        ghi_de = 1 if overwrite else 0

        with db.session(autocommit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "EXEC dbo.SP_SaoLuuCSDL @DuongDan = ?, @GhiDe = ?",
                (path_str, ghi_de),
            )
            while cursor.nextset():
                pass

        return path_str


auth_service = AuthService()
