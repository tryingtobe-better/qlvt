-- =============================================================================
-- FILE 01: TẠO BẢNG, RÀNG BUỘC TOÀN VẸN & INDEX TỐI ƯU TRUY VẤN
-- Server: LAPTOP-M19TS03A | Database: QLVT
-- Mục đích:
--   1. Khởi tạo 8 bảng dữ liệu cốt lõi cùng đầy đủ Khóa chính (PK), Khóa ngoại (FK),
--      Ràng buộc kiểm tra (CHECK) và Duy nhất (UNIQUE).
--   2. Tạo các Index sắp thứ tự trước trên các cột thường xuyên tham gia điều kiện
--      WHERE / JOIN / ORDER BY để phục vụ [Tối ưu - Cách 5] (`WITH (INDEX=ten_index)`).
-- =============================================================================

IF DB_ID('QLVT') IS NULL
    CREATE DATABASE QLVT;
GO

USE QLVT;
GO

-- 1. Bảng Nhân viên
IF OBJECT_ID('dbo.Nhanvien', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Nhanvien (
        MANV INT NOT NULL,
        HO NVARCHAR(40) NOT NULL,
        TEN NVARCHAR(10) NOT NULL,
        DIACHI NVARCHAR(100) NULL,
        NGAYSINH DATE NULL,
        LUONG FLOAT NOT NULL,
        GHICHU NVARCHAR(MAX) NULL,
        TrangThaiXoa BIT NOT NULL CONSTRAINT DF_Nhanvien_TrangThaiXoa DEFAULT (0),
        CONSTRAINT PK_Nhanvien PRIMARY KEY (MANV),
        CONSTRAINT CK_Nhanvien_Luong CHECK (LUONG >= 5000000)
    );
END;
GO

IF COL_LENGTH('dbo.Nhanvien', 'TrangThaiXoa') IS NULL
BEGIN
    ALTER TABLE dbo.Nhanvien
    ADD TrangThaiXoa BIT NOT NULL CONSTRAINT DF_Nhanvien_TrangThaiXoa DEFAULT (0);
END;
GO

-- 2. Bảng Vật tư
IF OBJECT_ID('dbo.Vattu', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Vattu (
        MAVT NCHAR(4) NOT NULL,
        TENVT NVARCHAR(30) NOT NULL,
        DVT NVARCHAR(15) NOT NULL,
        Soluongton INT NOT NULL,
        CONSTRAINT PK_Vattu PRIMARY KEY (MAVT),
        CONSTRAINT UQ_Vattu_TenVT UNIQUE (TENVT),
        CONSTRAINT CK_Vattu_Soluongton CHECK (Soluongton >= 0)
    );
END;
GO

-- 3. Bảng Đơn đặt hàng (Master)
IF OBJECT_ID('dbo.DatHang', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DatHang (
        MasoDDH NCHAR(8) NOT NULL,
        NGAY DATE NOT NULL,
        NhaCC NVARCHAR(100) NOT NULL,
        MANV INT NOT NULL,
        CONSTRAINT PK_DatHang PRIMARY KEY (MasoDDH),
        CONSTRAINT FK_DatHang_Nhanvien FOREIGN KEY (MANV) REFERENCES dbo.Nhanvien (MANV)
    );
END;
GO

-- 4. Bảng Chi tiết đơn đặt hàng (Detail)
IF OBJECT_ID('dbo.CTDDH', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CTDDH (
        MasoDDH NCHAR(8) NOT NULL,
        MAVT NCHAR(4) NOT NULL,
        SOLUONG INT NOT NULL,
        DONGIA FLOAT NOT NULL,
        CONSTRAINT PK_CTDDH PRIMARY KEY (MasoDDH, MAVT),
        CONSTRAINT FK_CTDDH_DatHang FOREIGN KEY (MasoDDH) REFERENCES dbo.DatHang (MasoDDH),
        CONSTRAINT FK_CTDDH_Vattu FOREIGN KEY (MAVT) REFERENCES dbo.Vattu (MAVT),
        CONSTRAINT CK_CTDDH_Soluong CHECK (SOLUONG > 0),
        CONSTRAINT CK_CTDDH_Dongia CHECK (DONGIA > 0)
    );
END;
GO

-- 5. Bảng Phiếu nhập kho (Master)
IF OBJECT_ID('dbo.PhieuNhap', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PhieuNhap (
        MAPN NCHAR(8) NOT NULL,
        NGAY DATE NOT NULL,
        MasoDDH NCHAR(8) NOT NULL,
        MANV INT NOT NULL,
        CONSTRAINT PK_PhieuNhap PRIMARY KEY (MAPN),
        CONSTRAINT FK_PhieuNhap_DatHang FOREIGN KEY (MasoDDH) REFERENCES dbo.DatHang (MasoDDH),
        CONSTRAINT FK_PhieuNhap_Nhanvien FOREIGN KEY (MANV) REFERENCES dbo.Nhanvien (MANV)
    );
END;
GO

-- 6. Bảng Chi tiết phiếu nhập kho (Detail)
IF OBJECT_ID('dbo.CTPN', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CTPN (
        MAPN NCHAR(8) NOT NULL,
        MAVT NCHAR(4) NOT NULL,
        SOLUONG INT NOT NULL,
        DONGIA FLOAT NOT NULL,
        CONSTRAINT PK_CTPN PRIMARY KEY (MAPN, MAVT),
        CONSTRAINT FK_CTPN_PhieuNhap FOREIGN KEY (MAPN) REFERENCES dbo.PhieuNhap (MAPN),
        CONSTRAINT FK_CTPN_Vattu FOREIGN KEY (MAVT) REFERENCES dbo.Vattu (MAVT),
        CONSTRAINT CK_CTPN_Soluong CHECK (SOLUONG > 0),
        CONSTRAINT CK_CTPN_Dongia CHECK (DONGIA > 0)
    );
END;
GO

-- 7. Bảng Phiếu xuất kho (Master)
IF OBJECT_ID('dbo.PhieuXuat', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.PhieuXuat (
        MAPX NCHAR(8) NOT NULL,
        NGAY DATE NOT NULL,
        HOTENKH NVARCHAR(100) NOT NULL,
        MANV INT NOT NULL,
        CONSTRAINT PK_PhieuXuat PRIMARY KEY (MAPX),
        CONSTRAINT FK_PhieuXuat_Nhanvien FOREIGN KEY (MANV) REFERENCES dbo.Nhanvien (MANV)
    );
END;
GO

-- 8. Bảng Chi tiết phiếu xuất kho (Detail)
IF OBJECT_ID('dbo.CTPX', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CTPX (
        MAPX NCHAR(8) NOT NULL,
        MAVT NCHAR(4) NOT NULL,
        SOLUONG INT NOT NULL,
        DONGIA FLOAT NOT NULL,
        CONSTRAINT PK_CTPX PRIMARY KEY (MAPX, MAVT),
        CONSTRAINT FK_CTPX_PhieuXuat FOREIGN KEY (MAPX) REFERENCES dbo.PhieuXuat (MAPX),
        CONSTRAINT FK_CTPX_Vattu FOREIGN KEY (MAVT) REFERENCES dbo.Vattu (MAVT),
        CONSTRAINT CK_CTPX_Soluong CHECK (SOLUONG > 0),
        CONSTRAINT CK_CTPX_Dongia CHECK (DONGIA > 0)
    );
END;
GO

-- =============================================================================
-- 9. HỆ THỐNG INDEX PHỤC VỤ [TỐI ƯU HÓA TRUY VẤN - CÁCH 5]
--    "Field tham gia trong điều kiện truy vấn nên được sắp thứ tự trước, và thứ tự
--     này phải được sử dụng trong mệnh đề truy vấn với WITH (INDEX=ten_index)"
-- =============================================================================

-- Index trên bảng Nhanvien: lọc theo TrangThaiXoa và sắp xếp theo TEN, HO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Nhanvien_TrangThaiXoa' AND object_id = OBJECT_ID(N'dbo.Nhanvien'))
    CREATE INDEX IX_Nhanvien_TrangThaiXoa ON dbo.Nhanvien(TrangThaiXoa, MANV);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Nhanvien_TenHo' AND object_id = OBJECT_ID(N'dbo.Nhanvien'))
    CREATE INDEX IX_Nhanvien_TenHo ON dbo.Nhanvien(TEN, HO, MANV);

-- Index trên bảng DatHang: lọc theo MANV và theo NGAY
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_DatHang_MANV' AND object_id = OBJECT_ID(N'dbo.DatHang'))
    CREATE INDEX IX_DatHang_MANV ON dbo.DatHang(MANV);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_DatHang_NGAY' AND object_id = OBJECT_ID(N'dbo.DatHang'))
    CREATE INDEX IX_DatHang_NGAY ON dbo.DatHang(NGAY DESC, MasoDDH DESC);

-- Index trên bảng CTDDH: kiểm tra vật tư theo MAVT
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_CTDDH_MAVT' AND object_id = OBJECT_ID(N'dbo.CTDDH'))
    CREATE INDEX IX_CTDDH_MAVT ON dbo.CTDDH(MAVT);

-- Index trên bảng PhieuNhap: lọc theo MasoDDH, MANV và NGAY
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_PhieuNhap_MasoDDH' AND object_id = OBJECT_ID(N'dbo.PhieuNhap'))
    CREATE INDEX IX_PhieuNhap_MasoDDH ON dbo.PhieuNhap(MasoDDH);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_PhieuNhap_MANV' AND object_id = OBJECT_ID(N'dbo.PhieuNhap'))
    CREATE INDEX IX_PhieuNhap_MANV ON dbo.PhieuNhap(MANV);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_PhieuNhap_NGAY' AND object_id = OBJECT_ID(N'dbo.PhieuNhap'))
    CREATE INDEX IX_PhieuNhap_NGAY ON dbo.PhieuNhap(NGAY) INCLUDE (MasoDDH);

-- Index trên bảng CTPN: kiểm tra vật tư theo MAVT
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_CTPN_MAVT' AND object_id = OBJECT_ID(N'dbo.CTPN'))
    CREATE INDEX IX_CTPN_MAVT ON dbo.CTPN(MAVT);

-- Index trên bảng PhieuXuat: lọc theo MANV và NGAY
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_PhieuXuat_MANV' AND object_id = OBJECT_ID(N'dbo.PhieuXuat'))
    CREATE INDEX IX_PhieuXuat_MANV ON dbo.PhieuXuat(MANV);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_PhieuXuat_NGAY' AND object_id = OBJECT_ID(N'dbo.PhieuXuat'))
    CREATE INDEX IX_PhieuXuat_NGAY ON dbo.PhieuXuat(NGAY);

-- Index trên bảng CTPX: kiểm tra vật tư theo MAVT
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_CTPX_MAVT' AND object_id = OBJECT_ID(N'dbo.CTPX'))
    CREATE INDEX IX_CTPX_MAVT ON dbo.CTPX(MAVT);
GO
