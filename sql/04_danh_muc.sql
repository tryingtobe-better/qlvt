-- =============================================================================
-- FILE 04: STORED PROCEDURES DANH MỤC NHÂN VIÊN & VẬT TƯ
-- Server: LAPTOP-M19TS03A | Database: QLVT
-- Áp dụng các kỹ thuật Tối ưu hóa truy vấn trên 1 CSDL:
--   - [Tối ưu - Cách 3]: Biến đổi tương đương P1 ^ (P2 v P3) để điều kiện xuất hiện 1 lần.
--   - [Tối ưu - Cách 4]: Trong AND đặt điều kiện xác suất sai cao ở đầu;
--                        trong OR đặt điều kiện xác suất đúng cao ở đầu.
--   - [Tối ưu - Cách 5]: Sử dụng chỉ mục sắp thứ tự trước với WITH (INDEX=ten_index).
-- =============================================================================

USE QLVT;
GO

-- Xóa các SP kiểm tra trùng lặp từ phiên bản cũ (đã tích hợp sẵn trong SP_ChiTietNhanVien & SP_ChiTietVatTu)
IF OBJECT_ID('dbo.SP_KiemTraNhanVienHoatDong', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_KiemTraNhanVienHoatDong;
IF OBJECT_ID('dbo.SP_KiemTraXoaNhanVien', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_KiemTraXoaNhanVien;
IF OBJECT_ID('dbo.SP_KiemTraXoaVatTu', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_KiemTraXoaVatTu;
GO

-- =============================================================================
-- PHẦN A: DANH MỤC NHÂN VIÊN (dbo.Nhanvien)
-- =============================================================================

-- 1. Lấy danh sách nhân viên (hỗ trợ tìm kiếm theo Mã NV, Họ tên, Địa chỉ)
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 3]: Gom điều kiện tìm kiếm với mẫu @Pattern tính 1 lần.
--   - [Tối ưu - Cách 4]: Trong mệnh đề OR, đặt `@Kw = N''` (xác suất đúng cao nhất) ở đầu.
--   - [Tối ưu - Cách 5]: Dùng `WITH (INDEX = IX_Nhanvien_TrangThaiXoa)` và các Index `IX_*_MANV`.
CREATE OR ALTER PROCEDURE dbo.SP_DanhSachNhanVien
    @TuKhoa NVARCHAR(100) = N''
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Kw NVARCHAR(100) = LTRIM(RTRIM(ISNULL(@TuKhoa, N'')));
    DECLARE @Pattern NVARCHAR(102) = N'%' + @Kw + N'%';

    SELECT
        nv.MANV,
        nv.HO,
        nv.TEN,
        nv.DIACHI,
        nv.NGAYSINH,
        nv.LUONG,
        nv.GHICHU,
        CAST(nv.TrangThaiXoa AS INT) AS TrangThaiXoa,
        tk.SoPhieuDaLap,
        tk.CoTaiKhoan,
        CASE WHEN tk.SoPhieuDaLap = 0 AND tk.CoTaiKhoan = 0 THEN 1 ELSE 0 END AS CoTheXoa
    FROM dbo.Nhanvien nv WITH (INDEX = IX_Nhanvien_TrangThaiXoa)
    CROSS APPLY (
        SELECT
            (
                (SELECT COUNT(1) FROM dbo.DatHang dh WITH (INDEX = IX_DatHang_MANV) WHERE dh.MANV = nv.MANV)
                + (SELECT COUNT(1) FROM dbo.PhieuNhap pn WITH (INDEX = IX_PhieuNhap_MANV) WHERE pn.MANV = nv.MANV)
                + (SELECT COUNT(1) FROM dbo.PhieuXuat px WITH (INDEX = IX_PhieuXuat_MANV) WHERE px.MANV = nv.MANV)
            ) AS SoPhieuDaLap,
            CASE WHEN EXISTS (
                -- [Tối ưu - Cách 4]: Đặt điều kiện `dp.name = ...` có xác suất sai cao ở đầu AND
                SELECT 1 FROM sys.database_principals dp
                WHERE dp.name = CAST(nv.MANV AS NVARCHAR(20)) AND dp.type = 'S'
            ) THEN 1 ELSE 0 END AS CoTaiKhoan
    ) tk
    -- [Tối ưu - Cách 3 & Cách 4]: Đặt `@Kw = N''` có xác suất đúng cao nhất ở đầu mệnh đề OR
    WHERE @Kw = N''
       OR (
           CAST(nv.MANV AS NVARCHAR(20)) LIKE @Pattern
           OR nv.HO LIKE @Pattern
           OR nv.TEN LIKE @Pattern
           OR (nv.HO + N' ' + nv.TEN) LIKE @Pattern
           OR ISNULL(nv.DIACHI, N'') LIKE @Pattern
       )
    ORDER BY nv.TrangThaiXoa ASC, nv.MANV ASC;
END;
GO

-- 2. Lấy thông tin chi tiết 1 nhân viên theo MANV
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_Nhanvien)` và các Index ngoại khóa `MANV`.
CREATE OR ALTER PROCEDURE dbo.SP_ChiTietNhanVien
    @MANV INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        nv.MANV,
        nv.HO,
        nv.TEN,
        nv.HO + N' ' + nv.TEN AS HoTen,
        nv.DIACHI,
        nv.NGAYSINH,
        nv.LUONG,
        nv.GHICHU,
        CAST(nv.TrangThaiXoa AS INT) AS TrangThaiXoa,
        tk.SoPhieuDaLap,
        tk.CoTaiKhoan,
        CASE WHEN tk.SoPhieuDaLap = 0 AND tk.CoTaiKhoan = 0 THEN 1 ELSE 0 END AS CoTheXoa
    FROM dbo.Nhanvien nv WITH (INDEX = PK_Nhanvien)
    CROSS APPLY (
        SELECT
            (
                (SELECT COUNT(1) FROM dbo.DatHang dh WITH (INDEX = IX_DatHang_MANV) WHERE dh.MANV = @MANV)
                + (SELECT COUNT(1) FROM dbo.PhieuNhap pn WITH (INDEX = IX_PhieuNhap_MANV) WHERE pn.MANV = @MANV)
                + (SELECT COUNT(1) FROM dbo.PhieuXuat px WITH (INDEX = IX_PhieuXuat_MANV) WHERE px.MANV = @MANV)
            ) AS SoPhieuDaLap,
            CASE WHEN EXISTS (
                SELECT 1 FROM sys.database_principals dp
                WHERE dp.name = CAST(@MANV AS NVARCHAR(20)) AND dp.type = 'S'
            ) THEN 1 ELSE 0 END AS CoTaiKhoan
    ) tk
    WHERE nv.MANV = @MANV;
END;
GO

-- 3. Thêm nhân viên mới
CREATE OR ALTER PROCEDURE dbo.SP_ThemNhanVien
    @MANV INT,
    @HO NVARCHAR(40),
    @TEN NVARCHAR(10),
    @DIACHI NVARCHAR(100),
    @NGAYSINH DATE,
    @LUONG FLOAT,
    @GHICHU NVARCHAR(MAX) = NULL,
    @TrangThaiXoa BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.Nhanvien (MANV, HO, TEN, DIACHI, NGAYSINH, LUONG, GHICHU, TrangThaiXoa)
    VALUES (@MANV, @HO, @TEN, @DIACHI, @NGAYSINH, @LUONG, @GHICHU, @TrangThaiXoa);
END;
GO

-- 5. Cập nhật hồ sơ nhân viên
CREATE OR ALTER PROCEDURE dbo.SP_SuaNhanVien
    @MANV INT,
    @HO NVARCHAR(40),
    @TEN NVARCHAR(10),
    @DIACHI NVARCHAR(100),
    @NGAYSINH DATE,
    @LUONG FLOAT,
    @GHICHU NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE dbo.Nhanvien
    SET HO = @HO,
        TEN = @TEN,
        DIACHI = @DIACHI,
        NGAYSINH = @NGAYSINH,
        LUONG = @LUONG,
        GHICHU = @GHICHU
    WHERE MANV = @MANV;
END;
GO

-- 6. Xóa nhân viên
CREATE OR ALTER PROCEDURE dbo.SP_XoaNhanVien
    @MANV INT
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM dbo.Nhanvien WHERE MANV = @MANV;
END;
GO

-- 7. Đổi trạng thái làm việc của nhân viên (0: Đang làm việc, 1: Nghỉ việc)
--    Nếu chuyển sang Nghỉ việc (@TrangThaiXoa = 1) thì tự động thu hồi tài khoản đăng nhập (nếu có)
CREATE OR ALTER PROCEDURE dbo.SP_DoiTrangThaiNhanVien
    @MANV INT,
    @TrangThaiXoa BIT
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE dbo.Nhanvien
    SET TrangThaiXoa = @TrangThaiXoa
    WHERE MANV = @MANV;

    IF @TrangThaiXoa = 1
    BEGIN
        DECLARE @UserName VARCHAR(50) = CAST(@MANV AS VARCHAR(50));
        DECLARE @LoginName VARCHAR(50);

        SELECT @LoginName = sp.name
        FROM sys.database_principals dp
        LEFT JOIN sys.server_principals sp ON dp.sid = sp.sid
        WHERE dp.name = @UserName AND dp.type = 'S';

        IF @LoginName IS NOT NULL OR EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @UserName AND type = 'S')
        BEGIN
            SET @LoginName = ISNULL(@LoginName, '');
            EXEC dbo.SP_XoaTaiKhoan @LoginName = @LoginName, @UserName = @UserName;
        END;
    END;
END;
GO

-- =============================================================================
-- PHẦN B: DANH MỤC VẬT TƯ (dbo.Vattu)
-- =============================================================================

-- 1. Lấy danh sách vật tư (hỗ trợ tìm kiếm theo Mã VT, Tên VT, ĐVT)
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 3 & Cách 4]: Đặt `@Kw = N''` (xác suất đúng cao nhất) ở đầu mệnh đề OR;
--     tính `DaCoGiaoDich` 1 lần trong `CROSS APPLY` rồi tái sử dụng cho `CoTheXoa`
--     (`vt.Soluongton = 0 AND gd.DaCoGiaoDich = 0`).
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_Vattu)` và các Index `IX_CT*_MAVT`.
CREATE OR ALTER PROCEDURE dbo.SP_DanhSachVatTu
    @TuKhoa NVARCHAR(100) = N''
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Kw NVARCHAR(100) = LTRIM(RTRIM(ISNULL(@TuKhoa, N'')));
    DECLARE @Pattern NVARCHAR(102) = N'%' + @Kw + N'%';

    SELECT
        RTRIM(vt.MAVT) AS MAVT,
        vt.TENVT,
        vt.DVT,
        vt.Soluongton,
        gd.DaCoGiaoDich,
        -- [Tối ưu - Cách 4]: Đặt `vt.Soluongton = 0` (xác suất sai cao) ở đầu AND
        CASE WHEN vt.Soluongton = 0 AND gd.DaCoGiaoDich = 0 THEN 1 ELSE 0 END AS CoTheXoa
    FROM dbo.Vattu vt WITH (INDEX = PK_Vattu)
    CROSS APPLY (
        SELECT CASE WHEN (
            EXISTS (SELECT 1 FROM dbo.CTDDH ct WITH (INDEX = IX_CTDDH_MAVT) WHERE ct.MAVT = vt.MAVT)
            OR EXISTS (SELECT 1 FROM dbo.CTPN pn WITH (INDEX = IX_CTPN_MAVT) WHERE pn.MAVT = vt.MAVT)
            OR EXISTS (SELECT 1 FROM dbo.CTPX px WITH (INDEX = IX_CTPX_MAVT) WHERE px.MAVT = vt.MAVT)
        ) THEN 1 ELSE 0 END AS DaCoGiaoDich
    ) gd
    -- [Tối ưu - Cách 3 & Cách 4]: Đặt `@Kw = N''` ở đầu mệnh đề OR
    WHERE @Kw = N''
       OR (vt.MAVT LIKE @Pattern OR vt.TENVT LIKE @Pattern OR vt.DVT LIKE @Pattern)
    ORDER BY vt.MAVT ASC;
END;
GO

-- 2. Lấy thông tin 1 vật tư theo MAVT
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_Vattu)` và các Index `IX_CT*_MAVT`.
CREATE OR ALTER PROCEDURE dbo.SP_ChiTietVatTu
    @MAVT NCHAR(4)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        RTRIM(vt.MAVT) AS MAVT,
        vt.TENVT,
        vt.DVT,
        vt.Soluongton,
        gd.DaCoGiaoDich,
        CASE WHEN vt.Soluongton = 0 AND gd.DaCoGiaoDich = 0 THEN 1 ELSE 0 END AS CoTheXoa
    FROM dbo.Vattu vt WITH (INDEX = PK_Vattu)
    CROSS APPLY (
        SELECT CASE WHEN (
            EXISTS (SELECT 1 FROM dbo.CTDDH ct WITH (INDEX = IX_CTDDH_MAVT) WHERE ct.MAVT = @MAVT)
            OR EXISTS (SELECT 1 FROM dbo.CTPN pn WITH (INDEX = IX_CTPN_MAVT) WHERE pn.MAVT = @MAVT)
            OR EXISTS (SELECT 1 FROM dbo.CTPX px WITH (INDEX = IX_CTPX_MAVT) WHERE px.MAVT = @MAVT)
        ) THEN 1 ELSE 0 END AS DaCoGiaoDich
    ) gd
    WHERE vt.MAVT = @MAVT;
END;
GO

-- 3. Kiểm tra trùng tên vật tư (TENVT)
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 3 (Biến đổi tương đương P1 ^ (P2 v P3))]:
--     Gộp điều kiện `TENVT = @TENVT` xuất hiện đúng 1 lần thay vì lặp lại ở 2 nhánh.
--   - [Tối ưu - Cách 4]: Đặt `TENVT = @TENVT` (xác suất sai cao nhất) ở đầu mệnh đề AND;
--     trong vế OR đặt `@LoaiTruMAVT IS NULL` lên trước.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = UQ_Vattu_TenVT)`.
CREATE OR ALTER PROCEDURE dbo.SP_KiemTraTrungTenVatTu
    @TENVT NVARCHAR(30),
    @LoaiTruMAVT NCHAR(4) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT RTRIM(MAVT) AS MAVT
    FROM dbo.Vattu WITH (INDEX = UQ_Vattu_TenVT)
    WHERE TENVT = @TENVT
      AND (@LoaiTruMAVT IS NULL OR MAVT <> @LoaiTruMAVT);
END;
GO

-- 4. Thêm vật tư mới
CREATE OR ALTER PROCEDURE dbo.SP_ThemVatTu
    @MAVT NCHAR(4),
    @TENVT NVARCHAR(30),
    @DVT NVARCHAR(15),
    @Soluongton INT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.Vattu (MAVT, TENVT, DVT, Soluongton)
    VALUES (@MAVT, @TENVT, @DVT, @Soluongton);
END;
GO

-- 6. Cập nhật vật tư
CREATE OR ALTER PROCEDURE dbo.SP_SuaVatTu
    @MAVT NCHAR(4),
    @TENVT NVARCHAR(30),
    @DVT NVARCHAR(15),
    @Soluongton INT
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE dbo.Vattu
    SET TENVT = @TENVT,
        DVT = @DVT,
        Soluongton = @Soluongton
    WHERE MAVT = @MAVT;
END;
GO

-- 7. Xóa vật tư
CREATE OR ALTER PROCEDURE dbo.SP_XoaVatTu
    @MAVT NCHAR(4)
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM dbo.Vattu WHERE MAVT = @MAVT;
END;
GO
