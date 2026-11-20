# 📦 QLVT — Hệ Thống Quản Lý Vật Tư

Ứng dụng Web Quản lý Vật tư kết nối trực tiếp với **Microsoft SQL Server (`QLVT`)**, xây dựng bằng **Python (`Flask` + `pyodbc`)**.
Toàn bộ câu lệnh truy vấn, ràng buộc toàn vẹn, Trigger cập nhật tồn kho và Giao tác (`BEGIN TRAN ... COMMIT TRAN / ROLLBACK TRAN`) đều được đóng gói hoàn toàn trong thư mục **`sql/`**; tầng Python chỉ kiểm tra dữ liệu đầu vào và gọi `EXEC dbo.SP_*`.

---

## 🚀 Hướng dẫn tải về & chạy ngay (Dành cho máy mới)

### Yêu cầu môi trường trên máy:
1. **Python 3.10+** (đã tích chọn *"Add Python to PATH"* khi cài).
2. **Microsoft SQL Server** (đã bật chế độ đăng nhập **SQL Server and Windows Authentication mode / Mixed Mode**) + **ODBC Driver 17 for SQL Server** (có sẵn khi cài SQL Server / SSMS).

### Cách 1: Chạy tự động 1-Click bằng `run.bat` (Khuyên dùng)
1. Tải mã nguồn về máy (`git clone <link-github>` hoặc bấm **Code → Download ZIP** và giải nén).
2. Nhấp đúp chuột chạy file **`run.bat`** (hoặc gõ `.\run.bat` trong Terminal).
3. Script `run.bat` sẽ **tự động hoàn toàn**:
   - Tự dò tên SQL Server trên máy (`localhost` / tên máy / `SQLEXPRESS`) và tạo file `.env`.
   - Tự động khởi tạo Database `QLVT`, 8 bảng, 2 Trigger, 54 Stored Procedures, dữ liệu mẫu và các tài khoản đăng nhập mẫu từ 7 file trong `sql/`.
   - Tự tạo môi trường ảo `.venv`, cài đặt thư viện trong `requirements.txt` và mở trình duyệt tại **http://127.0.0.1:5000**.

### Tài khoản đăng nhập mẫu (Mật khẩu chung: `123456`):
| Vai trò | Tên đăng nhập | Mật khẩu | Nhân viên ánh xạ | Quyền hạn |
| :--- | :--- | :--- | :--- | :--- |
| **Quản trị viên (`Admin`)** | `admin` | `123456` | `#1` Nguyễn Văn An | Toàn quyền hệ thống, Danh mục, Kho, Báo cáo, Quản lý tài khoản & Sao lưu CSDL |
| **Nhân viên (`NhanVien`)** | `nhanvien` *(hoặc `nv3`, `nv6`, `nv8`, `nv9`, `nv10`, `nv12`, `nv14`, `nv15`)* | `123456` | `#2` Trần Thị Bình *(và các NV tương ứng)* | Xem danh mục, lập chứng từ kho, chỉ sửa/xóa phiếu do chính mình lập, xem & in 7 báo cáo (khóa Quản lý nhân sự, Tài khoản & Sao lưu CSDL) |

---

## 🎯 1. Các phân hệ chức năng chính

1. **Hệ thống & Phân quyền (`sql/03_auth_and_system.sql`)**:
   - Đăng nhập trực tiếp bằng tài khoản **SQL Server Login** (`UID`/`PWD`), ánh xạ sang `UserName = MANV` và phân quyền theo 2 Role: `Admin` (Quản trị viên) và `NhanVien` (Nhân viên).
   - Cấp mới, đổi mật khẩu (`SP_DoiMatKhau`), thu hồi tài khoản đăng nhập cho nhân viên và sao lưu cơ sở dữ liệu (`SP_SaoLuuCSDL`) dành riêng cho `Admin`.
2. **Danh mục Nhân viên & Vật tư (`sql/04_danh_muc.sql`)**:
   - Quản lý nhân viên (chỉ `Admin` được Thêm, Sửa, Xóa, chuyển **Nghỉ việc** `TrangThaiXoa = 1` kèm tự động thu hồi tài khoản; `NhanVien` chỉ tra cứu) và Quản lý vật tư kèm **Hoàn tác (Undo) nhiều bước**.
3. **Giao dịch kho Master – Detail (`sql/05_giao_dich_kho.sql`)**:
   - **Đơn đặt hàng (`DatHang` – `CTDDH`)**: Hỗ trợ 3 trạng thái `Chưa nhập`, `Nhập một phần`, `Đã nhập đủ`; tự động khóa xóa khi đơn đã có phiếu nhập và khóa sửa khi đơn đã nhập đủ.
   - **Phiếu nhập kho (`PhieuNhap` – `CTPN`)**: Nhập hàng theo đơn đặt hàng còn thiếu vật tư, kiểm tra số lượng nhập không vượt số lượng đặt, thực thi trong **Giao tác (`BEGIN TRAN ... COMMIT TRAN`)** kết hợp Trigger tự động cộng tồn kho; khóa xóa/sửa giảm dưới lượng hàng đã xuất kho.
   - **Phiếu xuất kho (`PhieuXuat` – `CTPX`)**: Xuất vật tư cho khách hàng, kiểm tra tồn kho thực tế (`SOLUONG <= Soluongton`), thực thi trong **Giao tác (`BEGIN TRAN ... COMMIT TRAN`)** kết hợp Trigger tự động trừ tồn kho.
4. **Hệ thống Báo biểu & Thống kê kho (`sql/06_bao_cao.sql`)**:
   - 7 mẫu báo cáo kho gọi trực tiếp từ 6 Stored Procedure `dbo.usp_RPT_*`, thiết kế đơn sắc chuẩn in ấn / xuất PDF khổ A4.

---

## 📁 2. Cấu trúc thư mục dự án

```text
qlvt/
├── run.bat                              # Script 1-Click tự động cài đặt CSDL, môi trường & chạy Web
├── main.py                              # Điểm khởi chạy ứng dụng (Entry Point)
├── requirements.txt                     # Danh sách thư viện Python (Flask, pyodbc, python-dotenv)
├── .env.example                         # Mẫu cấu hình kết nối SQL Server
├── sql/                                 # Toàn bộ mã nguồn SQL chia thành 7 file theo chức năng
│   ├── 01_tables_and_constraints.sql    # Tự tạo DB QLVT, 8 Bảng dữ liệu, Ràng buộc & 12 Index
│   ├── 02_triggers.sql                  # 2 Trigger tự động cập nhật tồn kho (CTPN, CTPX)
│   ├── 03_auth_and_system.sql           # Role, SP Đăng nhập, Tài khoản, Đổi mật khẩu & Backup (8 SP)
│   ├── 04_danh_muc.sql                  # SP Danh mục Nhân viên & Vật tư (12 SP)
│   ├── 05_giao_dich_kho.sql             # SP & Giao tác (BEGIN TRAN) Đặt hàng, Nhập, Xuất kho (28 SP)
│   ├── 06_bao_cao.sql                   # 6 SP Báo biểu & Thống kê kho (usp_RPT_*)
│   └── 07_seed_data.sql                 # Dữ liệu mẫu đa dạng & khởi tạo tài khoản đăng nhập mẫu
└── src/qlvt/                            # Mã nguồn ứng dụng Python
    ├── config.py
    ├── database.py
    ├── services/                        # Tầng xử lý nghiệp vụ (gọi EXEC dbo.SP_*)
    │   ├── common.py
    │   ├── auth_service.py
    │   ├── nhan_vien_service.py
    │   ├── vat_tu_service.py
    │   ├── dat_hang_service.py
    │   ├── phieu_nhap_service.py
    │   ├── phieu_xuat_service.py
    │   └── bao_cao_service.py
    └── web/                             # Tầng giao diện & điều hướng Web (Flask Routes + HTML)
        ├── app.py
        ├── helpers.py
        ├── routes_he_thong.py
        ├── routes_danh_muc.py
        ├── routes_kho.py
        ├── routes_bao_cao.py
        └── templates/
            ├── base.html
            ├── login.html
            ├── dashboard.html
            ├── accounts.html
            ├── backup.html
            ├── nhan_vien.html
            ├── vat_tu.html
            ├── dat_hang.html
            ├── phieu_nhap.html
            ├── phieu_xuat.html
            └── bao_cao.html
```

---

## 🗄️ 3. Chi tiết 7 file SQL trong thư mục `sql/`

1. **[sql/01_tables_and_constraints.sql](sql/01_tables_and_constraints.sql)**: Tự động tạo Database `QLVT` (nếu chưa có), 8 bảng (`Nhanvien`, `Vattu`, `DatHang`, `CTDDH`, `PhieuNhap`, `CTPN`, `PhieuXuat`, `CTPX`), các ràng buộc `PK`, `FK`, `CHECK`, `UNIQUE` và 12 Index tối ưu truy vấn.
2. **[sql/02_triggers.sql](sql/02_triggers.sql)**: 2 Trigger `TRG_CTPN_CapNhatTonKho` và `TRG_CTPX_CapNhatTonKho` tự động cộng/trừ `Vattu.Soluongton` và kiểm tra âm kho / vượt số lượng đặt.
3. **[sql/03_auth_and_system.sql](sql/03_auth_and_system.sql)** *(8 SP)*: `SP_DangNhap`, `SP_TaoTaiKhoan`, `SP_XoaTaiKhoan`, `SP_DoiMatKhau`, `SP_DanhSachTaiKhoan`, `SP_ThongKeTongQuan`, `SP_LayThuMucBackupMacDinh`, `SP_SaoLuuCSDL`.
4. **[sql/04_danh_muc.sql](sql/04_danh_muc.sql)** *(12 SP)*:
   - Nhân viên (6 SP): `SP_DanhSachNhanVien`, `SP_ChiTietNhanVien`, `SP_ThemNhanVien`, `SP_SuaNhanVien`, `SP_XoaNhanVien`, `SP_DoiTrangThaiNhanVien`.
   - Vật tư (6 SP): `SP_DanhSachVatTu`, `SP_ChiTietVatTu`, `SP_KiemTraTrungTenVatTu`, `SP_ThemVatTu`, `SP_SuaVatTu`, `SP_XoaVatTu`.
5. **[sql/05_giao_dich_kho.sql](sql/05_giao_dich_kho.sql)** *(28 SP)*:
   - Đơn đặt hàng (9 SP): `SP_DanhSachDonDatHang`, `SP_ChiTietDonDatHang`, `SP_DSChiTietDDH`, `SP_ThemDonDatHang`, `SP_SuaDonDatHang`, `SP_XoaDonDatHang`, `SP_ThemCTDDH`, `SP_SuaCTDDH`, `SP_XoaCTDDH`.
   - Phiếu nhập kho (10 SP): `SP_DanhSachPhieuNhap`, `SP_ChiTietPhieuNhap`, `SP_DSChiTietPN`, `SP_HanMucNhapVatTu`, `SP_ThemPhieuNhap`, `SP_SuaPhieuNhap`, `SP_XoaPhieuNhap`, `SP_ThemCTPN`, `SP_SuaCTPN`, `SP_XoaCTPN`.
   - Phiếu xuất kho (9 SP): `SP_DanhSachPhieuXuat`, `SP_ChiTietPhieuXuat`, `SP_DSChiTietPX`, `SP_ThemPhieuXuat`, `SP_SuaPhieuXuat`, `SP_XoaPhieuXuat`, `SP_ThemCTPX`, `SP_SuaCTPX`, `SP_XoaCTPX`.
6. **[sql/06_bao_cao.sql](sql/06_bao_cao.sql)** *(6 SP)*: `usp_RPT_DSNhanVien`, `usp_RPT_DMVatTu`, `usp_RPT_DonDatHangChuaNhapHet`, `usp_RPT_BangKeNhapXuat`, `usp_RPT_ThongKeTheoThang`, `usp_RPT_TongHopNhapXuat`.
7. **[sql/07_seed_data.sql](sql/07_seed_data.sql)**: Dữ liệu mẫu đa dạng (`17` nhân viên, `24` vật tư, `15` đơn đặt hàng đủ 3 trạng thái `Chưa nhập` / `Nhập một phần` / `Đã nhập đủ`, `13` phiếu nhập, `13` phiếu xuất) và khởi tạo tài khoản đăng nhập mẫu.

---

## ⚡ 4. Áp dụng 5 kỹ thuật Tối ưu hóa truy vấn trên 1 CSDL

| Cách tối ưu | Nội dung nguyên tắc | Vị trí áp dụng tiêu biểu trong `sql/` |
| :---: | :--- | :--- |
| **Cách 1** | **Dùng phép chọn/chiếu trước, phép kết sau**: Lọc dòng (`WHERE`) và chỉ lấy các cột cần thiết ở từng bảng con trước khi thực hiện phép kết `JOIN`. | • `SP_DSChiTietDDH`, `SP_DSChiTietPN`, `SP_DSChiTietPX`, `SP_DanhSachDonDatHang`, `SP_DanhSachPhieuNhap`, `SP_DanhSachPhieuXuat` ([sql/05_giao_dich_kho.sql](sql/05_giao_dich_kho.sql))<br>• `usp_RPT_DonDatHangChuaNhapHet`, `usp_RPT_BangKeNhapXuat`, `usp_RPT_ThongKeTheoThang`, `usp_RPT_TongHopNhapXuat` ([sql/06_bao_cao.sql](sql/06_bao_cao.sql)) |
| **Cách 2** | **Khử phép kết (nếu được)**: Khi truy vấn theo 1 mã cố định mà cột dữ liệu từ bảng liên kết không đổi, tách ra truy vấn riêng vào biến `@Bien` thay vì `JOIN`. | • `SP_DangNhap` ([sql/03_auth_and_system.sql](sql/03_auth_and_system.sql))<br>• `SP_ChiTietDonDatHang`, `SP_ChiTietPhieuNhap`, `SP_ChiTietPhieuXuat`, `SP_HanMucNhapVatTu` ([sql/05_giao_dich_kho.sql](sql/05_giao_dich_kho.sql)) |
| **Cách 3** | **Biến đổi tương đương cho điều kiện xuất hiện 1 lần**: Áp dụng $P_1 \land (P_2 \lor P_3) \equiv (P_1 \land P_2) \lor (P_1 \land P_3)$ để đặt nhân tử chung. | • `SP_KiemTraTrungTenVatTu`, `SP_DanhSachNhanVien`, `SP_DanhSachVatTu` ([sql/04_danh_muc.sql](sql/04_danh_muc.sql))<br>• `SP_DSChiTietDDH`, `SP_DSChiTietPN`, `SP_DSChiTietPX`, `SP_HanMucNhapVatTu` ([sql/05_giao_dich_kho.sql](sql/05_giao_dich_kho.sql))<br>• `usp_RPT_BangKeNhapXuat` ([sql/06_bao_cao.sql](sql/06_bao_cao.sql)) |
| **Cách 4** | **Thứ tự điều kiện trong `AND` / `OR`**: Trong `AND`, đặt điều kiện có xác suất sai cao ở đầu; trong `OR`, đặt điều kiện có xác suất đúng cao ở đầu (`@Kw = N''`, `@Loai = 'T'`). | • `SP_DangNhap`, `SP_TaoTaiKhoan`, `SP_DoiMatKhau` ([sql/03_auth_and_system.sql](sql/03_auth_and_system.sql))<br>• `SP_DanhSachNhanVien`, `SP_DanhSachVatTu` ([sql/04_danh_muc.sql](sql/04_danh_muc.sql))<br>• `usp_RPT_BangKeNhapXuat`, `usp_RPT_ThongKeTheoThang` ([sql/06_bao_cao.sql](sql/06_bao_cao.sql)) |
| **Cách 5** | **Tạo Index sắp thứ tự trước & dùng `WITH (INDEX=ten_index)`**: Đánh chỉ mục trên các trường tham gia điều kiện truy vấn / sắp xếp và chỉ định tường minh `WITH (INDEX = ...)`. | • Tạo 12 Index trong [sql/01_tables_and_constraints.sql](sql/01_tables_and_constraints.sql) (`IX_Nhanvien_TenHo`, `IX_PhieuNhap_NGAY`, `IX_PhieuXuat_NGAY`, `IX_PhieuNhap_MasoDDH`, `IX_CT*_MAVT`...) và sử dụng `WITH (INDEX = ...)` xuyên suốt các file `03`, `04`, `05`, `06`. |
