-- =============================================================================
-- FILE 03: PHÂN QUYỀN HỆ THỐNG, ĐĂNG NHẬP, TÀI KHOẢN, TỔNG QUAN & SAO LƯU CSDL
-- Server: LAPTOP-M19TS03A | Database: QLVT
-- Áp dụng các kỹ thuật Tối ưu hóa truy vấn trên 1 CSDL:
--   - [Tối ưu - Cách 1]: Dùng phép chọn/chiếu trước, phép kết sau.
--   - [Tối ưu - Cách 2]: Khử phép kết bằng cách truy vấn riêng vào biến cục bộ.
--   - [Tối ưu - Cách 4]: Đặt điều kiện xác suất sai cao ở đầu mệnh đề AND.
--   - [Tối ưu - Cách 5]: Sử dụng chỉ mục với WITH (INDEX=ten_index).
-- =============================================================================

USE QLVT;
GO

-- =============================================================================
-- 0. KHỞI TẠO 2 ROLE (Admin & NhanVien) VÀ CẤP QUYỀN TRONG DATABASE QLVT
-- =============================================================================
IF DATABASE_PRINCIPAL_ID('Admin') IS NULL
    CREATE ROLE Admin;

IF DATABASE_PRINCIPAL_ID('NhanVien') IS NULL
    CREATE ROLE NhanVien;
GO

ALTER ROLE db_datareader ADD MEMBER NhanVien;
ALTER ROLE db_datawriter ADD MEMBER NhanVien;
GRANT EXECUTE TO NhanVien;

ALTER ROLE db_owner ADD MEMBER Admin;
ALTER ROLE db_backupoperator ADD MEMBER Admin;
GO

-- =============================================================================
-- 1. SP_DangNhap
-- Mục đích : Lấy thông tin nhân viên và nhóm quyền sau khi kết nối SQL Server thành công.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 2 (Khử phép kết)]: Thay vì JOIN 3 bảng (sys.sysusers, sys.sysmembers,
--     dbo.Nhanvien), ta truy vấn riêng thông tin nhân viên (@HoTen, @TrangThaiXoa) và
--     tên nhóm quyền (@TenNhom) vào các biến vô hướng rồi trả về kết quả.
--   - [Tối ưu - Cách 4 (Thứ tự điều kiện AND)]: Đặt `sid = SUSER_SID(@TenLogin)` (chỉ đúng
--     với 1 dòng duy nhất, xác suất sai cao nhất) lên trước `uid > 4`.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.SP_DangNhap
    @TenLogin NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @TenUser NVARCHAR(50);
    DECLARE @Uid INT;

    -- [Tối ưu - Cách 4]: Đặt điều kiện `sid = SUSER_SID(@TenLogin)` có xác suất sai cao ở đầu AND
    SELECT @Uid = uid, @TenUser = NAME
    FROM sys.sysusers
    WHERE sid = SUSER_SID(@TenLogin) AND uid > 4;

    IF @Uid IS NOT NULL
    BEGIN
        -- [Tối ưu - Cách 2 (Khử phép kết)]: Truy vấn riêng bảng Nhanvien và Role vào biến
        DECLARE @HoTen NVARCHAR(60) = @TenLogin;
        DECLARE @TrangThaiXoa INT = 0;
        DECLARE @TenNhom NVARCHAR(50);

        SELECT
            @HoTen = HO + N' ' + TEN,
            @TrangThaiXoa = CAST(TrangThaiXoa AS INT)
        FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
        WHERE MANV = TRY_CAST(@TenUser AS INT);

        SELECT TOP 1 @TenNhom = NAME
        FROM sys.sysusers
        WHERE uid = (
            SELECT TOP 1 groupuid
            FROM sys.sysmembers
            WHERE memberuid = @Uid
              AND groupuid IN (DATABASE_PRINCIPAL_ID('Admin'), DATABASE_PRINCIPAL_ID('NhanVien'))
        );

        IF @TenNhom IS NOT NULL
        BEGIN
            SELECT
                MANV = @TenUser,
                HOTEN = @HoTen,
                TENNHOM = @TenNhom,
                TrangThaiXoa = @TrangThaiXoa;
        END;
        RETURN 0;
    END;
END;
GO

-- =============================================================================
-- 2. SP_TaoTaiKhoan
-- Mục đích : Tạo SQL Server Login + Database User (tên trùng MANV) và gán vào Role.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 4]: Trong điều kiện kiểm tra nhân viên nghỉ việc, đặt
--     `MANV = TRY_CAST(@UserName AS INT)` (xác suất sai cao nhất) ở đầu mệnh đề AND.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_Nhanvien)` khi kiểm tra nhân viên.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.SP_TaoTaiKhoan
    @LoginName VARCHAR(50),
    @Password VARCHAR(50),
    @UserName VARCHAR(50),
    @Role VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;

    IF @Role NOT IN ('Admin', 'NhanVien')
    BEGIN
        RAISERROR(N'Lỗi: Nhóm quyền (Role) chỉ được phép là Admin hoặc NhanVien!', 16, 1);
        RETURN -1;
    END;

    -- 1. Kiểm tra trùng LoginName ở mức Server
    IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name = @LoginName)
    BEGIN
        SELECT 1 AS RetCode, N'Tên đăng nhập (LoginName) đã tồn tại trên hệ thống!' AS ThongBao;
        RETURN 1;
    END;

    -- 2. Kiểm tra nhân viên (MANV) đã có User trong Database chưa
    IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @UserName)
    BEGIN
        SELECT 2 AS RetCode, N'Nhân viên này đã được cấp tài khoản rồi!' AS ThongBao;
        RETURN 2;
    END;

    -- 3. [Tối ưu - Cách 4 & Cách 5]: Đặt điều kiện khóa chính ở đầu AND + dùng WITH (INDEX)
    IF EXISTS (
        SELECT 1
        FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
        WHERE MANV = TRY_CAST(@UserName AS INT) AND TrangThaiXoa = 1
    )
    BEGIN
        RAISERROR(N'Không thể cấp tài khoản đăng nhập cho nhân viên đã nghỉ việc!', 16, 1);
        RETURN -1;
    END;

    -- 4. Tạo Login trên SQL Server
    DECLARE @SqlCreateLogin NVARCHAR(MAX);
    SET @SqlCreateLogin = N'CREATE LOGIN ' + QUOTENAME(@LoginName)
        + N' WITH PASSWORD = ' + QUOTENAME(@Password, '''')
        + N', DEFAULT_DATABASE = [QLVT], CHECK_EXPIRATION = OFF, CHECK_POLICY = OFF;';
    EXEC (@SqlCreateLogin);

    -- 5. Tạo User trong Database QLVT ánh xạ với MANV
    DECLARE @SqlCreateUser NVARCHAR(MAX);
    SET @SqlCreateUser = N'CREATE USER ' + QUOTENAME(@UserName)
        + N' FOR LOGIN ' + QUOTENAME(@LoginName) + N';';
    BEGIN TRY
        EXEC (@SqlCreateUser);
    END TRY
    BEGIN CATCH
        DECLARE @SqlDropLogin NVARCHAR(MAX) = N'DROP LOGIN ' + QUOTENAME(@LoginName) + N';';
        EXEC (@SqlDropLogin);
        SELECT 2 AS RetCode, N'Nhân viên này đã được cấp tài khoản rồi!' AS ThongBao;
        RETURN 2;
    END CATCH;

    -- 6. Gán vào Role tương ứng trong Database
    EXEC sp_addrolemember @Role, @UserName;

    IF (@Role = 'Admin')
    BEGIN
        EXEC sp_addsrvrolemember @LoginName, 'securityadmin';
        EXEC sp_addsrvrolemember @LoginName, 'processadmin';
    END;

    SELECT 0 AS RetCode, N'Tạo tài khoản đăng nhập thành công!' AS ThongBao;
    RETURN 0;
END;
GO

-- =============================================================================
-- 3. SP_XoaTaiKhoan
-- Mục đích : Ngắt kết nối đang mở và xóa Database User + SQL Server Login của nhân viên.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 4]: Đặt `login_name = @LoginName` và `name = @UserName` (điều kiện
--     có xác suất sai cao nhất) lên đầu mệnh đề AND.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.SP_XoaTaiKhoan
    @LoginName VARCHAR(50),
    @UserName VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Spid INT;
    DECLARE cur_sess CURSOR LOCAL FAST_FORWARD FOR
        SELECT session_id
        FROM sys.dm_exec_sessions
        WHERE login_name = @LoginName AND session_id <> @@SPID;

    OPEN cur_sess;
    FETCH NEXT FROM cur_sess INTO @Spid;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        DECLARE @KillCmd NVARCHAR(50) = N'KILL ' + CAST(@Spid AS NVARCHAR(10));
        BEGIN TRY
            EXEC (@KillCmd);
        END TRY
        BEGIN CATCH
        END CATCH;
        FETCH NEXT FROM cur_sess INTO @Spid;
    END;
    CLOSE cur_sess;
    DEALLOCATE cur_sess;

    IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @UserName AND type = 'S')
    BEGIN
        DECLARE @SqlDropUser NVARCHAR(MAX) = N'DROP USER ' + QUOTENAME(@UserName) + N';';
        EXEC (@SqlDropUser);
    END;

    IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name = @LoginName AND type = 'S')
    BEGIN
        DECLARE @SqlDropLogin NVARCHAR(MAX) = N'DROP LOGIN ' + QUOTENAME(@LoginName) + N';';
        EXEC (@SqlDropLogin);
    END;

    SELECT 0 AS RetCode, N'Đã xóa tài khoản đăng nhập thành công!' AS ThongBao;
    RETURN 0;
END;
GO

-- =============================================================================
-- 3b. SP_DoiMatKhau
-- Mục đích : Đổi hoặc đặt lại mật khẩu cho một SQL Server Login (chỉ dành cho Admin).
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 4]: Đặt điều kiện `name = @LoginName` (xác suất sai cao nhất) ở đầu AND.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.SP_DoiMatKhau
    @LoginName VARCHAR(50),
    @NewPassword VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = @LoginName AND type = 'S')
    BEGIN
        SELECT 1 AS RetCode, N'Không tìm thấy tài khoản đăng nhập trên SQL Server!' AS ThongBao;
        RETURN 1;
    END;

    DECLARE @SqlAlterLogin NVARCHAR(MAX);
    SET @SqlAlterLogin = N'ALTER LOGIN ' + QUOTENAME(@LoginName)
        + N' WITH PASSWORD = ' + QUOTENAME(@NewPassword, '''') + N';';
    EXEC (@SqlAlterLogin);

    SELECT 0 AS RetCode, N'Đã thay đổi mật khẩu cho tài khoản ''' + @LoginName + N''' thành công!' AS ThongBao;
    RETURN 0;
END;
GO

-- =============================================================================
-- 4. SP_DanhSachTaiKhoan
-- Mục đích : Liệt kê toàn bộ nhân viên kèm trạng thái tài khoản Login và Role.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Lọc và chiếu trước các bảng hệ thống
--     `sys.database_principals` (`WHERE type = 'S'` và `WHERE name IN ('Admin', 'NhanVien')`)
--     trước khi thực hiện phép kết `LEFT JOIN` với bảng `Nhanvien`.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.SP_DanhSachTaiKhoan
AS
BEGIN
    SET NOCOUNT ON;

    -- [Tối ưu - Cách 1]: Chiếu và chọn trước các cột cần dùng ở từng bảng trước khi kết
    SELECT
        nv.MANV,
        nv.HOTEN,
        nv.TrangThaiXoa,
        dp.name AS UserName,
        sp.name AS LoginName,
        r.name AS RoleName,
        CASE WHEN sp.name IS NOT NULL THEN 1 ELSE 0 END AS DaCoTaiKhoan
    FROM (
        SELECT MANV, HO + N' ' + TEN AS HOTEN, CAST(TrangThaiXoa AS INT) AS TrangThaiXoa
        FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
    ) nv
    LEFT JOIN (
        SELECT principal_id, name, sid
        FROM sys.database_principals
        WHERE type = 'S'
    ) dp ON dp.name = CAST(nv.MANV AS NVARCHAR(50))
    LEFT JOIN (
        SELECT sid, name FROM sys.server_principals
    ) sp ON dp.sid = sp.sid
    LEFT JOIN sys.database_role_members drm ON drm.member_principal_id = dp.principal_id
    LEFT JOIN (
        SELECT principal_id, name
        FROM sys.database_principals
        WHERE name IN ('Admin', 'NhanVien')
    ) r ON r.principal_id = drm.role_principal_id
    ORDER BY nv.MANV ASC;
END;
GO

-- =============================================================================
-- 5. SP_ThongKeTongQuan
-- Mục đích : Lấy số liệu thống kê nhanh cho trang Tổng quan (Dashboard).
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = ...)` trên các cột `TrangThaiXoa` và `NGAY`
--     để SQL Server đếm trực tiếp trên Index (Index Seek / Index Scan) thay vì Table Scan.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.SP_ThongKeTongQuan
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @HomNay DATE = CAST(GETDATE() AS DATE);

    -- [Tối ưu - Cách 5]: Sử dụng WITH (INDEX=...) cho các truy vấn đếm theo điều kiện
    SELECT
        (SELECT COUNT(1) FROM dbo.Nhanvien WITH (INDEX = IX_Nhanvien_TrangThaiXoa) WHERE TrangThaiXoa = 0) AS nv_count,
        (SELECT COUNT(1) FROM dbo.Vattu) AS vt_count,
        (SELECT COUNT(1) FROM dbo.DatHang) AS ddh_count,
        (SELECT COUNT(1) FROM dbo.PhieuNhap) AS pn_count,
        (SELECT COUNT(1) FROM dbo.PhieuXuat) AS px_count,
        (SELECT COUNT(1) FROM dbo.PhieuNhap WITH (INDEX = IX_PhieuNhap_NGAY) WHERE NGAY = @HomNay) AS pn_today,
        (SELECT COUNT(1) FROM dbo.PhieuXuat WITH (INDEX = IX_PhieuXuat_NGAY) WHERE NGAY = @HomNay) AS px_today,
        (SELECT COUNT(1) FROM dbo.DatHang WITH (INDEX = IX_DatHang_NGAY) WHERE NGAY = @HomNay) AS ddh_today;
END;
GO

-- =============================================================================
-- 6. SP_LayThuMucBackupMacDinh
-- Mục đích : Trả về đường dẫn thư mục Backup mặc định của SQL Server Instance.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.SP_LayThuMucBackupMacDinh
AS
BEGIN
    SET NOCOUNT ON;

    SELECT CAST(SERVERPROPERTY('InstanceDefaultBackupPath') AS NVARCHAR(4000)) AS backup_dir;
END;
GO

-- =============================================================================
-- 7. SP_SaoLuuCSDL
-- Mục đích : Sao lưu toàn bộ cơ sở dữ liệu QLVT ra file .bak trên ổ cứng.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.SP_SaoLuuCSDL
    @DuongDan NVARCHAR(500),
    @GhiDe BIT = 1
AS
BEGIN
    SET NOCOUNT ON;

    IF @GhiDe = 1
    BEGIN
        BACKUP DATABASE [QLVT]
        TO DISK = @DuongDan
        WITH INIT, FORMAT, NAME = N'QLVT-Full Database Backup';
    END
    ELSE
    BEGIN
        BACKUP DATABASE [QLVT]
        TO DISK = @DuongDan
        WITH NOINIT, NAME = N'QLVT-Full Database Backup';
    END;
END;
GO
