-- =============================================================================
-- FILE 05: STORED PROCEDURES & GIAO TÁC (TRANSACTIONS) KHO: ĐẶT HÀNG, NHẬP, XUẤT
-- Server: LAPTOP-M19TS03A | Database: QLVT
-- Áp dụng đầy đủ 5 kỹ thuật Tối ưu hóa truy vấn trên 1 CSDL:
--   - [Tối ưu - Cách 1]: Dùng phép chọn/chiếu trước, phép kết sau.
--   - [Tối ưu - Cách 2]: Khử phép kết (truy vấn riêng vào biến khi cột dữ liệu không đổi).
--   - [Tối ưu - Cách 3]: Biến đổi tương đương P1 ^ (P2 v P3) để điều kiện xuất hiện 1 lần.
--   - [Tối ưu - Cách 4]: Trong AND đặt điều kiện xác suất sai cao ở đầu; OR thì ngược lại.
--   - [Tối ưu - Cách 5]: Sử dụng chỉ mục sắp thứ tự trước với WITH (INDEX=ten_index).
-- =============================================================================

USE QLVT;
GO

-- Xóa các SP trùng lặp từ phiên bản cũ (đã gộp vào các SP danh sách / chi tiết)
IF OBJECT_ID('dbo.SP_ChiTietMotDongCTDDH', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_ChiTietMotDongCTDDH;
IF OBJECT_ID('dbo.SP_ChiTietMotDongCTPN', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_ChiTietMotDongCTPN;
IF OBJECT_ID('dbo.SP_ChiTietMotDongCTPX', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_ChiTietMotDongCTPX;
IF OBJECT_ID('dbo.SP_KiemTraXoaDatHang', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_KiemTraXoaDatHang;
IF OBJECT_ID('dbo.SP_KiemTraXoaPhieuXuat', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_KiemTraXoaPhieuXuat;
IF OBJECT_ID('dbo.SP_DSDonHangConCanNhap', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_DSDonHangConCanNhap;
IF OBJECT_ID('dbo.SP_LayVatTuConCanNhapTheoDDH', 'P') IS NOT NULL
    DROP PROCEDURE dbo.SP_LayVatTuConCanNhapTheoDDH;
GO

-- =============================================================================
-- PHẦN A: ĐƠN ĐẶT HÀNG & CHI TIẾT ĐƠN ĐẶT HÀNG (DatHang - CTDDH)
-- Ba trạng thái của Đơn đặt hàng:
--   - N'Chưa nhập'    : Chưa có phiếu nhập kho nào hoặc tổng SL đã nhập = 0.
--   - N'Nhập một phần': Đã có phiếu nhập nhưng vẫn còn mặt hàng chưa nhập đủ (0 < SLDaNhap < SLDat).
--   - N'Đã nhập đủ'   : Có mặt hàng và toàn bộ mặt hàng trong đơn đều đã nhập đủ (SLDaNhap >= SLDat).
-- =============================================================================

-- 1. Lấy danh sách đơn đặt hàng (hỗ trợ tìm kiếm theo MasoDDH hoặc NhaCC)
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Lọc đơn đặt hàng theo `@Kw` trên bảng
--     `DatHang` trước rồi mới thực hiện phép kết `JOIN` với bảng `Nhanvien`.
--   - [Tối ưu - Cách 3 & Cách 4]: Đặt `@Kw = N''` (xác suất đúng cao nhất) ở đầu mệnh đề OR.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = IX_DatHang_NGAY)` và `WITH (INDEX = IX_PhieuNhap_MasoDDH)`.
CREATE OR ALTER PROCEDURE dbo.SP_DanhSachDonDatHang
    @TuKhoa NVARCHAR(100) = N''
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Kw NVARCHAR(100) = LTRIM(RTRIM(ISNULL(@TuKhoa, N'')));
    DECLARE @Pattern NVARCHAR(102) = N'%' + @Kw + N'%';

    SELECT
        RTRIM(dh.MasoDDH) AS MasoDDH,
        dh.NGAY,
        dh.NhaCC,
        dh.MANV,
        nv.HoTenNV,
        tk.SoMatHang,
        tk.TongSLDat,
        tk.TongSLDaNhap,
        tk.DaCoPhieuNhap,
        tk.TongTriGia,
        CASE
            WHEN tk.DaCoPhieuNhap = 0 OR tk.TongSLDaNhap = 0 THEN N'Chưa nhập'
            WHEN tk.SoMatHang > 0 AND tk.SoDongChuaDu = 0 THEN N'Đã nhập đủ'
            ELSE N'Nhập một phần'
        END AS TrangThaiNhap,
        CASE
            WHEN tk.SoMatHang > 0 AND tk.DaCoPhieuNhap = 1 AND tk.SoDongChuaDu = 0 THEN 1
            ELSE 0
        END AS DaNhapDu
    FROM (
        SELECT MasoDDH, NGAY, NhaCC, MANV
        FROM dbo.DatHang WITH (INDEX = IX_DatHang_NGAY)
        -- [Tối ưu - Cách 3 & Cách 4]: Đặt `@Kw = N''` ở đầu mệnh đề OR
        WHERE @Kw = N'' OR (MasoDDH LIKE @Pattern OR NhaCC LIKE @Pattern)
    ) dh
    JOIN (
        SELECT MANV, HO + N' ' + TEN AS HoTenNV
        FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
    ) nv ON dh.MANV = nv.MANV
    CROSS APPLY (
        SELECT
            COUNT(1) AS SoMatHang,
            ISNULL(SUM(ct.SOLUONG), 0) AS TongSLDat,
            ISNULL(SUM(ISNULL(nhap.SLNhap, 0)), 0) AS TongSLDaNhap,
            ISNULL(SUM(ct.SOLUONG * ct.DONGIA), 0) AS TongTriGia,
            SUM(CASE WHEN ISNULL(nhap.SLNhap, 0) < ct.SOLUONG THEN 1 ELSE 0 END) AS SoDongChuaDu,
            CASE WHEN EXISTS (
                SELECT 1 FROM dbo.PhieuNhap pn WITH (INDEX = IX_PhieuNhap_MasoDDH)
                WHERE pn.MasoDDH = dh.MasoDDH
            ) THEN 1 ELSE 0 END AS DaCoPhieuNhap
        FROM dbo.CTDDH ct WITH (INDEX = PK_CTDDH)
        LEFT JOIN (
            SELECT ctpn.MAVT, SUM(ctpn.SOLUONG) AS SLNhap
            FROM dbo.PhieuNhap pn WITH (INDEX = IX_PhieuNhap_MasoDDH)
            JOIN dbo.CTPN ctpn WITH (INDEX = PK_CTPN) ON pn.MAPN = ctpn.MAPN
            WHERE pn.MasoDDH = dh.MasoDDH
            GROUP BY ctpn.MAVT
        ) nhap ON ct.MAVT = nhap.MAVT
        WHERE ct.MasoDDH = dh.MasoDDH
    ) tk
    ORDER BY dh.NGAY DESC, dh.MasoDDH DESC;
END;
GO

-- 2. Lấy thông tin đầu đơn đặt hàng theo MasoDDH
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 2 (Khử phép kết)]: Truy vấn riêng họ tên nhân viên lập đơn vào biến `@HoTenNV`,
--     khử phép kết `JOIN Nhanvien`.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_DatHang)` và `WITH (INDEX = PK_Nhanvien)`.
CREATE OR ALTER PROCEDURE dbo.SP_ChiTietDonDatHang
    @MasoDDH NCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @MaNV INT;
    DECLARE @HoTenNV NVARCHAR(60);
    DECLARE @NgayNhapSomNhat DATE;

    SELECT @MaNV = MANV
    FROM dbo.DatHang WITH (INDEX = PK_DatHang)
    WHERE MasoDDH = @MasoDDH;

    IF @MaNV IS NULL RETURN;

    -- [Tối ưu - Cách 2 (Khử phép kết)]: Truy vấn riêng tên nhân viên và ngày nhập sớm nhất vào biến
    SELECT @HoTenNV = HO + N' ' + TEN
    FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
    WHERE MANV = @MaNV;

    SELECT @NgayNhapSomNhat = MIN(NGAY)
    FROM dbo.PhieuNhap WITH (INDEX = IX_PhieuNhap_MasoDDH)
    WHERE MasoDDH = @MasoDDH;

    SELECT
        RTRIM(dh.MasoDDH) AS MasoDDH,
        dh.NGAY,
        dh.NhaCC,
        dh.MANV,
        @HoTenNV AS HoTenNV,
        @NgayNhapSomNhat AS NgayNhapSomNhat,
        tk.SoMatHang,
        tk.TongSLDat,
        tk.TongSLDaNhap,
        tk.DaCoPhieuNhap,
        tk.TongTriGia,
        CASE
            WHEN tk.DaCoPhieuNhap = 0 OR tk.TongSLDaNhap = 0 THEN N'Chưa nhập'
            WHEN tk.SoMatHang > 0 AND tk.SoDongChuaDu = 0 THEN N'Đã nhập đủ'
            ELSE N'Nhập một phần'
        END AS TrangThaiNhap,
        CASE
            WHEN tk.SoMatHang > 0 AND tk.DaCoPhieuNhap = 1 AND tk.SoDongChuaDu = 0 THEN 1
            ELSE 0
        END AS DaNhapDu
    FROM dbo.DatHang dh WITH (INDEX = PK_DatHang)
    CROSS APPLY (
        SELECT
            COUNT(1) AS SoMatHang,
            ISNULL(SUM(ct.SOLUONG), 0) AS TongSLDat,
            ISNULL(SUM(ISNULL(nhap.SLNhap, 0)), 0) AS TongSLDaNhap,
            ISNULL(SUM(ct.SOLUONG * ct.DONGIA), 0) AS TongTriGia,
            SUM(CASE WHEN ISNULL(nhap.SLNhap, 0) < ct.SOLUONG THEN 1 ELSE 0 END) AS SoDongChuaDu,
            CASE WHEN @NgayNhapSomNhat IS NOT NULL THEN 1 ELSE 0 END AS DaCoPhieuNhap
        FROM dbo.CTDDH ct WITH (INDEX = PK_CTDDH)
        LEFT JOIN (
            SELECT ctpn.MAVT, SUM(ctpn.SOLUONG) AS SLNhap
            FROM dbo.PhieuNhap pn WITH (INDEX = IX_PhieuNhap_MasoDDH)
            JOIN dbo.CTPN ctpn WITH (INDEX = PK_CTPN) ON pn.MAPN = ctpn.MAPN
            WHERE pn.MasoDDH = @MasoDDH
            GROUP BY ctpn.MAVT
        ) nhap ON ct.MAVT = nhap.MAVT
        WHERE ct.MasoDDH = @MasoDDH
    ) tk
    WHERE dh.MasoDDH = @MasoDDH;
END;
GO

-- 3. Lấy danh sách chi tiết đơn đặt hàng (hoặc 1 dòng cụ thể nếu truyền @MAVT)
--    Kèm số lượng đã nhập (SLDaNhap) và trạng thái từng mặt hàng (Chưa nhập / Nhập một phần / Đã nhập đủ)
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Chọn trước các dòng `CTDDH` của đơn `@MasoDDH`
--     và các dòng đã nhập của đơn `@MasoDDH` rồi mới kết với bảng `Vattu`.
--   - [Tối ưu - Cách 3 & Cách 4]: Đặt `MasoDDH = @MasoDDH` ở đầu mệnh đề AND,
--     sau đó kiểm tra `(@MAVT IS NULL OR MAVT = @MAVT)`.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_CTDDH)`, `WITH (INDEX = IX_PhieuNhap_MasoDDH)` và `WITH (INDEX = PK_Vattu)`.
CREATE OR ALTER PROCEDURE dbo.SP_DSChiTietDDH
    @MasoDDH NCHAR(8),
    @MAVT NCHAR(4) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- [Tối ưu - Cách 1, 3, 4, 5]: Chọn/chiếu trước trên CTDDH và PhieuNhap theo @MasoDDH, kết Vattu sau
    SELECT
        RTRIM(ct.MasoDDH) AS MasoDDH,
        RTRIM(ct.MAVT) AS MAVT,
        vt.TENVT,
        vt.DVT,
        ct.SOLUONG,
        ct.DONGIA,
        (ct.SOLUONG * ct.DONGIA) AS ThanhTien,
        ISNULL(nhap.SLDaNhap, 0) AS SLDaNhap,
        (ct.SOLUONG - ISNULL(nhap.SLDaNhap, 0)) AS SLConLai,
        CASE
            WHEN ISNULL(nhap.SLDaNhap, 0) = 0 THEN N'Chưa nhập'
            WHEN ISNULL(nhap.SLDaNhap, 0) < ct.SOLUONG THEN N'Nhập một phần'
            ELSE N'Đã nhập đủ'
        END AS TrangThaiDong
    FROM (
        SELECT MasoDDH, MAVT, SOLUONG, DONGIA
        FROM dbo.CTDDH WITH (INDEX = PK_CTDDH)
        WHERE MasoDDH = @MasoDDH AND (@MAVT IS NULL OR MAVT = @MAVT)
    ) ct
    LEFT JOIN (
        SELECT ctpn.MAVT, SUM(ctpn.SOLUONG) AS SLDaNhap
        FROM (
            SELECT MAPN
            FROM dbo.PhieuNhap WITH (INDEX = IX_PhieuNhap_MasoDDH)
            WHERE MasoDDH = @MasoDDH
        ) pn
        JOIN (
            SELECT MAPN, MAVT, SOLUONG
            FROM dbo.CTPN WITH (INDEX = PK_CTPN)
        ) ctpn ON pn.MAPN = ctpn.MAPN
        GROUP BY ctpn.MAVT
    ) nhap ON ct.MAVT = nhap.MAVT
    JOIN (
        SELECT MAVT, TENVT, DVT
        FROM dbo.Vattu WITH (INDEX = PK_Vattu)
    ) vt ON ct.MAVT = vt.MAVT
    ORDER BY ct.MAVT ASC;
END;
GO

-- 4. Lập đầu đơn đặt hàng mới
CREATE OR ALTER PROCEDURE dbo.SP_ThemDonDatHang
    @MasoDDH NCHAR(8),
    @NGAY DATE,
    @NhaCC NVARCHAR(100),
    @MANV INT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.DatHang (MasoDDH, NGAY, NhaCC, MANV)
    VALUES (@MasoDDH, @NGAY, @NhaCC, @MANV);
END;
GO

-- 6. Cập nhật thông tin đầu đơn đặt hàng
CREATE OR ALTER PROCEDURE dbo.SP_SuaDonDatHang
    @MasoDDH NCHAR(8),
    @NGAY DATE,
    @NhaCC NVARCHAR(100),
    @MANV INT
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE dbo.DatHang
    SET NGAY = @NGAY,
        NhaCC = @NhaCC,
        MANV = @MANV
    WHERE MasoDDH = @MasoDDH;
END;
GO

-- 7. Xóa toàn bộ Đơn đặt hàng gồm cả chi tiết CTDDH và đầu đơn DatHang trong 1 Giao tác
CREATE OR ALTER PROCEDURE dbo.SP_XoaDonDatHang
    @MasoDDH NCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        DELETE FROM dbo.CTDDH WHERE MasoDDH = @MasoDDH;
        DELETE FROM dbo.DatHang WHERE MasoDDH = @MasoDDH;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- 8. Thêm mặt hàng vào chi tiết đơn đặt hàng CTDDH
CREATE OR ALTER PROCEDURE dbo.SP_ThemCTDDH
    @MasoDDH NCHAR(8),
    @MAVT NCHAR(4),
    @SOLUONG INT,
    @DONGIA FLOAT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.CTDDH (MasoDDH, MAVT, SOLUONG, DONGIA)
    VALUES (@MasoDDH, @MAVT, @SOLUONG, @DONGIA);
END;
GO

-- 9. Cập nhật dòng chi tiết đơn đặt hàng CTDDH
CREATE OR ALTER PROCEDURE dbo.SP_SuaCTDDH
    @MasoDDH NCHAR(8),
    @MAVT NCHAR(4),
    @SOLUONG INT,
    @DONGIA FLOAT
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE dbo.CTDDH
    SET SOLUONG = @SOLUONG,
        DONGIA = @DONGIA
    WHERE MasoDDH = @MasoDDH AND MAVT = @MAVT;
END;
GO

-- 10. Xóa 1 dòng mặt hàng khỏi chi tiết đơn đặt hàng CTDDH
CREATE OR ALTER PROCEDURE dbo.SP_XoaCTDDH
    @MasoDDH NCHAR(8),
    @MAVT NCHAR(4)
AS
BEGIN
    SET NOCOUNT ON;

    DELETE FROM dbo.CTDDH
    WHERE MasoDDH = @MasoDDH AND MAVT = @MAVT;
END;
GO

-- =============================================================================
-- PHẦN B: PHIẾU NHẬP KHO & CHI TIẾT PHIẾU NHẬP (PhieuNhap - CTPN)
-- =============================================================================

-- 1. Lấy danh sách phiếu nhập kho (hỗ trợ tìm kiếm theo MAPN, MasoDDH, NhaCC)
--    Kèm số mặt hàng trong phiếu (SoMatHang), tổng trị giá và trạng thái nhập của Đơn đặt hàng (TrangThaiDDH)
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Chiếu các cột cần thiết từ `PhieuNhap`,
--     `DatHang` và `Nhanvien` trước khi kết.
--   - [Tối ưu - Cách 3 & Cách 4]: Đặt `@Kw = N''` (xác suất đúng cao nhất) ở đầu mệnh đề OR.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_CTPN)` khi tính tổng trị giá từng phiếu.
CREATE OR ALTER PROCEDURE dbo.SP_DanhSachPhieuNhap
    @TuKhoa NVARCHAR(100) = N''
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Kw NVARCHAR(100) = LTRIM(RTRIM(ISNULL(@TuKhoa, N'')));
    DECLARE @Pattern NVARCHAR(102) = N'%' + @Kw + N'%';

    SELECT
        RTRIM(pn.MAPN) AS MAPN,
        pn.NGAY,
        RTRIM(pn.MasoDDH) AS MasoDDH,
        dh.NhaCC,
        pn.MANV,
        nv.HoTenNV,
        ct_pn.SoMatHang,
        ct_pn.TongTriGia,
        CASE
            WHEN ddh_tk.TongSLDaNhap = 0 THEN N'Chưa nhập'
            WHEN ddh_tk.SoDongChuaDu = 0 AND ddh_tk.SoMatHangDDH > 0 THEN N'Đã nhập đủ'
            ELSE N'Nhập một phần'
        END AS TrangThaiDDH
    FROM (
        SELECT MAPN, NGAY, MasoDDH, MANV
        FROM dbo.PhieuNhap WITH (INDEX = PK_PhieuNhap)
    ) pn
    JOIN (
        SELECT MasoDDH, NhaCC
        FROM dbo.DatHang WITH (INDEX = PK_DatHang)
    ) dh ON pn.MasoDDH = dh.MasoDDH
    JOIN (
        SELECT MANV, HO + N' ' + TEN AS HoTenNV
        FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
    ) nv ON pn.MANV = nv.MANV
    CROSS APPLY (
        SELECT
            COUNT(1) AS SoMatHang,
            ISNULL(SUM(ctpn.SOLUONG * ctpn.DONGIA), 0) AS TongTriGia
        FROM dbo.CTPN ctpn WITH (INDEX = PK_CTPN)
        WHERE ctpn.MAPN = pn.MAPN
    ) ct_pn
    CROSS APPLY (
        SELECT
            COUNT(1) AS SoMatHangDDH,
            ISNULL(SUM(ISNULL(nhap.SLNhap, 0)), 0) AS TongSLDaNhap,
            SUM(CASE WHEN ISNULL(nhap.SLNhap, 0) < ct.SOLUONG THEN 1 ELSE 0 END) AS SoDongChuaDu
        FROM dbo.CTDDH ct WITH (INDEX = PK_CTDDH)
        LEFT JOIN (
            SELECT c2.MAVT, SUM(c2.SOLUONG) AS SLNhap
            FROM dbo.PhieuNhap p2 WITH (INDEX = IX_PhieuNhap_MasoDDH)
            JOIN dbo.CTPN c2 WITH (INDEX = PK_CTPN) ON p2.MAPN = c2.MAPN
            WHERE p2.MasoDDH = pn.MasoDDH
            GROUP BY c2.MAVT
        ) nhap ON ct.MAVT = nhap.MAVT
        WHERE ct.MasoDDH = pn.MasoDDH
    ) ddh_tk
    WHERE @Kw = N''
       OR (pn.MAPN LIKE @Pattern OR pn.MasoDDH LIKE @Pattern OR dh.NhaCC LIKE @Pattern)
    ORDER BY pn.NGAY DESC, pn.MAPN DESC;
END;
GO

-- 2. Lấy thông tin đầu phiếu nhập kho theo MAPN kèm tiến độ nhập của đơn đặt hàng
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 2 (Khử phép kết)]: Truy vấn riêng thông tin đơn đặt hàng (`@NhaCC`, `@NgayDatHang`)
--     và tên nhân viên (`@HoTenNV`) vào biến cục bộ, khử phép kết 3 bảng (`PhieuNhap - DatHang - Nhanvien`).
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_PhieuNhap)`, `WITH (INDEX = PK_DatHang)`, `WITH (INDEX = PK_Nhanvien)`.
CREATE OR ALTER PROCEDURE dbo.SP_ChiTietPhieuNhap
    @MAPN NCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @MasoDDH NCHAR(8), @MaNV INT;
    DECLARE @NhaCC NVARCHAR(100), @NgayDatHang DATE, @HoTenNV NVARCHAR(60);
    DECLARE @TongSLDatDDH INT = 0, @TongSLDaNhapDDH INT = 0, @SoDongChuaDu INT = 0, @SoMatHangDDH INT = 0;
    DECLARE @MatHangDaXuat NVARCHAR(60) = NULL;

    SELECT @MasoDDH = MasoDDH, @MaNV = MANV
    FROM dbo.PhieuNhap WITH (INDEX = PK_PhieuNhap)
    WHERE MAPN = @MAPN;

    IF @MasoDDH IS NULL RETURN;

    -- [Tối ưu - Cách 2 (Khử phép kết)]: Truy vấn riêng bảng DatHang và Nhanvien vào biến
    SELECT @NhaCC = NhaCC, @NgayDatHang = NGAY
    FROM dbo.DatHang WITH (INDEX = PK_DatHang)
    WHERE MasoDDH = @MasoDDH;

    SELECT @HoTenNV = HO + N' ' + TEN
    FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
    WHERE MANV = @MaNV;

    SELECT TOP 1 @MatHangDaXuat = vt.TENVT + N' (' + RTRIM(ctpn.MAVT) + N')'
    FROM dbo.CTPN ctpn WITH (INDEX = PK_CTPN)
    JOIN dbo.Vattu vt WITH (INDEX = PK_Vattu) ON ctpn.MAVT = vt.MAVT
    WHERE ctpn.MAPN = @MAPN AND vt.Soluongton < ctpn.SOLUONG;

    SELECT
        @SoMatHangDDH = COUNT(1),
        @TongSLDatDDH = ISNULL(SUM(ct.SOLUONG), 0),
        @TongSLDaNhapDDH = ISNULL(SUM(ISNULL(nhap.SLNhap, 0)), 0),
        @SoDongChuaDu = SUM(CASE WHEN ISNULL(nhap.SLNhap, 0) < ct.SOLUONG THEN 1 ELSE 0 END)
    FROM dbo.CTDDH ct WITH (INDEX = PK_CTDDH)
    LEFT JOIN (
        SELECT c2.MAVT, SUM(c2.SOLUONG) AS SLNhap
        FROM dbo.PhieuNhap p2 WITH (INDEX = IX_PhieuNhap_MasoDDH)
        JOIN dbo.CTPN c2 WITH (INDEX = PK_CTPN) ON p2.MAPN = c2.MAPN
        WHERE p2.MasoDDH = @MasoDDH
        GROUP BY c2.MAVT
    ) nhap ON ct.MAVT = nhap.MAVT
    WHERE ct.MasoDDH = @MasoDDH;

    SELECT
        RTRIM(MAPN) AS MAPN,
        NGAY,
        RTRIM(MasoDDH) AS MasoDDH,
        @NhaCC AS NhaCC,
        @NgayDatHang AS NgayDatHang,
        MANV,
        @HoTenNV AS HoTenNV,
        @TongSLDatDDH AS TongSLDatDDH,
        @TongSLDaNhapDDH AS TongSLDaNhapDDH,
        CASE WHEN @MatHangDaXuat IS NULL THEN 1 ELSE 0 END AS CoTheXoaPhieu,
        @MatHangDaXuat AS MatHangDaXuat,
        CASE
            WHEN @TongSLDaNhapDDH = 0 THEN N'Chưa nhập'
            WHEN @SoMatHangDDH > 0 AND @SoDongChuaDu = 0 THEN N'Đã nhập đủ'
            ELSE N'Nhập một phần'
        END AS TrangThaiDDH
    FROM dbo.PhieuNhap WITH (INDEX = PK_PhieuNhap)
    WHERE MAPN = @MAPN;
END;
GO

-- 3. Lấy danh sách chi tiết phiếu nhập (hoặc 1 dòng cụ thể nếu truyền @MAVT)
--    Kèm SLDat, SLDaNhap toàn đơn, SLToiThieuPhieuNay, SLToiDaPhieuNay, CoTheXoaDong và trạng thái dòng mặt hàng
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Chọn trước các dòng `CTPN` của phiếu `@MAPN`
--     rồi mới kết với bảng `Vattu` và `CTDDH`.
--   - [Tối ưu - Cách 3 & Cách 4]: Đặt `MAPN = @MAPN` ở đầu mệnh đề AND trước `(@MAVT IS NULL OR MAVT = @MAVT)`.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_CTPN)` và `WITH (INDEX = PK_Vattu)`.
CREATE OR ALTER PROCEDURE dbo.SP_DSChiTietPN
    @MAPN NCHAR(8),
    @MAVT NCHAR(4) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @MasoDDH NCHAR(8);
    SELECT @MasoDDH = MasoDDH
    FROM dbo.PhieuNhap WITH (INDEX = PK_PhieuNhap)
    WHERE MAPN = @MAPN;

    -- [Tối ưu - Cách 1, 3, 4, 5]: Chọn/chiếu trước trên CTPN với WITH (INDEX=PK_CTPN), kết với Vattu & CTDDH sau
    SELECT
        RTRIM(ctpn.MAPN) AS MAPN,
        RTRIM(ctpn.MAVT) AS MAVT,
        vt.TENVT,
        vt.DVT,
        vt.Soluongton,
        ctpn.SOLUONG,
        ctpn.DONGIA,
        (ctpn.SOLUONG * ctpn.DONGIA) AS ThanhTien,
        ISNULL(ctddh.SOLUONG, ctpn.SOLUONG) AS SLDat,
        ISNULL(tongNhap.SLDaNhap, ctpn.SOLUONG) AS SLDaNhap,
        CASE
            WHEN ctpn.SOLUONG > vt.Soluongton THEN ctpn.SOLUONG - vt.Soluongton
            ELSE 1
        END AS SLToiThieuPhieuNay,
        ctpn.SOLUONG + ISNULL(ctddh.SOLUONG - ISNULL(tongNhap.SLDaNhap, 0), 0) AS SLToiDaPhieuNay,
        CASE
            WHEN vt.Soluongton >= ctpn.SOLUONG THEN 1
            ELSE 0
        END AS CoTheXoaDong,
        CASE
            WHEN ISNULL(tongNhap.SLDaNhap, 0) >= ISNULL(ctddh.SOLUONG, ctpn.SOLUONG) THEN N'Đã nhập đủ'
            ELSE N'Nhập một phần'
        END AS TrangThaiDong
    FROM (
        SELECT MAPN, MAVT, SOLUONG, DONGIA
        FROM dbo.CTPN WITH (INDEX = PK_CTPN)
        WHERE MAPN = @MAPN AND (@MAVT IS NULL OR MAVT = @MAVT)
    ) ctpn
    JOIN (
        SELECT MAVT, TENVT, DVT, Soluongton
        FROM dbo.Vattu WITH (INDEX = PK_Vattu)
    ) vt ON ctpn.MAVT = vt.MAVT
    LEFT JOIN (
        SELECT MAVT, SOLUONG
        FROM dbo.CTDDH WITH (INDEX = PK_CTDDH)
        WHERE MasoDDH = @MasoDDH
    ) ctddh ON ctpn.MAVT = ctddh.MAVT
    LEFT JOIN (
        SELECT c2.MAVT, SUM(c2.SOLUONG) AS SLDaNhap
        FROM dbo.PhieuNhap p2 WITH (INDEX = IX_PhieuNhap_MasoDDH)
        JOIN dbo.CTPN c2 WITH (INDEX = PK_CTPN) ON p2.MAPN = c2.MAPN
        WHERE p2.MasoDDH = @MasoDDH
        GROUP BY c2.MAVT
    ) tongNhap ON ctpn.MAVT = tongNhap.MAVT
    ORDER BY ctpn.MAVT ASC;
END;
GO

-- 4. Tính hạn mức số lượng còn được phép nhập của 1 mặt hàng trong đơn đặt hàng
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 2 (Khử phép kết)]: Truy vấn riêng `@TenVT` từ bảng `Vattu` và tính riêng
--     `@DaNhap` vào biến cục bộ, khử phép kết giữa `CTDDH` và `Vattu`.
--   - [Tối ưu - Cách 3 & Cách 4]: Đặt `MasoDDH = @MasoDDH` xuất hiện 1 lần ở đầu mệnh đề AND,
--     sau đó mới kiểm tra `(@LoaiTruMAPN IS NULL OR MAPN <> @LoaiTruMAPN)`.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_CTDDH)`, `WITH (INDEX = IX_PhieuNhap_MasoDDH)`.
CREATE OR ALTER PROCEDURE dbo.SP_HanMucNhapVatTu
    @MasoDDH NCHAR(8),
    @MAVT NCHAR(4),
    @LoaiTruMAPN NCHAR(8) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @TenVT NVARCHAR(30);
    DECLARE @DaNhap INT = 0;

    -- [Tối ưu - Cách 2 (Khử phép kết)]: Lấy riêng tên vật tư và tổng số đã nhập vào biến
    SELECT @TenVT = TENVT
    FROM dbo.Vattu WITH (INDEX = PK_Vattu)
    WHERE MAVT = @MAVT;

    -- [Tối ưu - Cách 1, 3, 4, 5]: Lọc PhieuNhap theo @MasoDDH trước khi kết với CTPN
    SELECT @DaNhap = ISNULL(SUM(ctpn.SOLUONG), 0)
    FROM (
        SELECT MAPN
        FROM dbo.PhieuNhap WITH (INDEX = IX_PhieuNhap_MasoDDH)
        WHERE MasoDDH = @MasoDDH
          AND (@LoaiTruMAPN IS NULL OR MAPN <> @LoaiTruMAPN)
    ) pn
    JOIN dbo.CTPN ctpn WITH (INDEX = PK_CTPN)
      ON pn.MAPN = ctpn.MAPN AND ctpn.MAVT = @MAVT;

    SELECT
        SOLUONG AS SLDat,
        DONGIA AS DonGiaDat,
        @TenVT AS TENVT,
        @DaNhap AS DaNhap
    FROM dbo.CTDDH WITH (INDEX = PK_CTDDH)
    WHERE MasoDDH = @MasoDDH AND MAVT = @MAVT;
END;
GO

-- 7. Lập đầu phiếu nhập kho mới
CREATE OR ALTER PROCEDURE dbo.SP_ThemPhieuNhap
    @MAPN NCHAR(8),
    @NGAY DATE,
    @MasoDDH NCHAR(8),
    @MANV INT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.PhieuNhap (MAPN, NGAY, MasoDDH, MANV)
    VALUES (@MAPN, @NGAY, @MasoDDH, @MANV);
END;
GO

-- 7b. Cập nhật ngày nhập kho của đầu phiếu nhập
CREATE OR ALTER PROCEDURE dbo.SP_SuaPhieuNhap
    @MAPN NCHAR(8),
    @NGAY DATE
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE dbo.PhieuNhap
    SET NGAY = @NGAY
    WHERE MAPN = @MAPN;
END;
GO

-- 8. Xóa phiếu nhập kho (Giao tác xóa CTPN để Trigger trừ lại tồn kho + xóa PhieuNhap)
CREATE OR ALTER PROCEDURE dbo.SP_XoaPhieuNhap
    @MAPN NCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        DELETE FROM dbo.CTPN WHERE MAPN = @MAPN;
        DELETE FROM dbo.PhieuNhap WHERE MAPN = @MAPN;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- 9. Thêm mặt hàng vào chi tiết phiếu nhập CTPN (Giao tác Nhập kho: Ghi CTPN + Cộng tồn kho)
CREATE OR ALTER PROCEDURE dbo.SP_ThemCTPN
    @MAPN NCHAR(8),
    @MAVT NCHAR(4),
    @SOLUONG INT,
    @DONGIA FLOAT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        INSERT INTO dbo.CTPN (MAPN, MAVT, SOLUONG, DONGIA)
        VALUES (@MAPN, @MAVT, @SOLUONG, @DONGIA);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- 10. Cập nhật dòng chi tiết phiếu nhập CTPN (Giao tác Sửa nhập kho + Điều chỉnh tồn kho)
CREATE OR ALTER PROCEDURE dbo.SP_SuaCTPN
    @MAPN NCHAR(8),
    @MAVT NCHAR(4),
    @SOLUONG INT,
    @DONGIA FLOAT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        UPDATE dbo.CTPN
        SET SOLUONG = @SOLUONG,
            DONGIA = @DONGIA
        WHERE MAPN = @MAPN AND MAVT = @MAVT;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- 11. Xóa 1 dòng chi tiết phiếu nhập CTPN (Giao tác Xóa dòng nhập + Trừ lại tồn kho)
CREATE OR ALTER PROCEDURE dbo.SP_XoaCTPN
    @MAPN NCHAR(8),
    @MAVT NCHAR(4)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        DELETE FROM dbo.CTPN
        WHERE MAPN = @MAPN AND MAVT = @MAVT;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- =============================================================================
-- PHẦN C: PHIẾU XUẤT KHO & CHI TIẾT PHIẾU XUẤT (PhieuXuat - CTPX)
-- =============================================================================

-- 1. Lấy danh sách phiếu xuất kho (hỗ trợ tìm kiếm theo MAPX hoặc HOTENKH)
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Chọn (lọc theo `@Kw`) trên bảng `PhieuXuat`
--     trước rồi mới kết `JOIN` với bảng `Nhanvien`.
--   - [Tối ưu - Cách 3 & Cách 4]: Đặt `@Kw = N''` (xác suất đúng cao nhất) ở đầu mệnh đề OR.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_CTPX)` khi đếm và tính tổng trị giá.
CREATE OR ALTER PROCEDURE dbo.SP_DanhSachPhieuXuat
    @TuKhoa NVARCHAR(100) = N''
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Kw NVARCHAR(100) = LTRIM(RTRIM(ISNULL(@TuKhoa, N'')));
    DECLARE @Pattern NVARCHAR(102) = N'%' + @Kw + N'%';

    SELECT
        RTRIM(px.MAPX) AS MAPX,
        px.NGAY,
        px.HOTENKH,
        px.MANV,
        nv.HoTenNV,
        (SELECT COUNT(1) FROM dbo.CTPX ctpx WITH (INDEX = PK_CTPX) WHERE ctpx.MAPX = px.MAPX) AS SoMatHang,
        ISNULL((
            SELECT SUM(ctpx.SOLUONG * ctpx.DONGIA)
            FROM dbo.CTPX ctpx WITH (INDEX = PK_CTPX)
            WHERE ctpx.MAPX = px.MAPX
        ), 0) AS TongTriGia
    FROM (
        SELECT MAPX, NGAY, HOTENKH, MANV
        FROM dbo.PhieuXuat WITH (INDEX = PK_PhieuXuat)
        WHERE @Kw = N'' OR (MAPX LIKE @Pattern OR HOTENKH LIKE @Pattern)
    ) px
    JOIN (
        SELECT MANV, HO + N' ' + TEN AS HoTenNV
        FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
    ) nv ON px.MANV = nv.MANV
    ORDER BY px.NGAY DESC, px.MAPX DESC;
END;
GO

-- 2. Lấy thông tin đầu phiếu xuất kho theo MAPX
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 2 (Khử phép kết)]: Truy vấn riêng họ tên nhân viên vào biến `@HoTenNV`,
--     khử phép kết giữa `PhieuXuat` và `Nhanvien`.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_PhieuXuat)` và `WITH (INDEX = PK_Nhanvien)`.
CREATE OR ALTER PROCEDURE dbo.SP_ChiTietPhieuXuat
    @MAPX NCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @MaNV INT;
    DECLARE @HoTenNV NVARCHAR(60);

    SELECT @MaNV = MANV
    FROM dbo.PhieuXuat WITH (INDEX = PK_PhieuXuat)
    WHERE MAPX = @MAPX;

    IF @MaNV IS NULL RETURN;

    -- [Tối ưu - Cách 2 (Khử phép kết)]: Truy vấn riêng tên nhân viên vào biến @HoTenNV
    SELECT @HoTenNV = HO + N' ' + TEN
    FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
    WHERE MANV = @MaNV;

    SELECT
        RTRIM(MAPX) AS MAPX,
        NGAY,
        HOTENKH,
        MANV,
        @HoTenNV AS HoTenNV
    FROM dbo.PhieuXuat WITH (INDEX = PK_PhieuXuat)
    WHERE MAPX = @MAPX;
END;
GO

-- 3. Lấy danh sách chi tiết phiếu xuất (hoặc 1 dòng cụ thể nếu truyền @MAVT)
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Chọn trước các dòng `CTPX` của phiếu `@MAPX`
--     rồi mới kết với bảng `Vattu`.
--   - [Tối ưu - Cách 3 & Cách 4]: Đặt `MAPX = @MAPX` ở đầu mệnh đề AND trước `(@MAVT IS NULL OR MAVT = @MAVT)`.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_CTPX)` và `WITH (INDEX = PK_Vattu)`.
CREATE OR ALTER PROCEDURE dbo.SP_DSChiTietPX
    @MAPX NCHAR(8),
    @MAVT NCHAR(4) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        RTRIM(ctpx.MAPX) AS MAPX,
        RTRIM(ctpx.MAVT) AS MAVT,
        vt.TENVT,
        vt.DVT,
        vt.Soluongton,
        ctpx.SOLUONG,
        (ctpx.SOLUONG + vt.Soluongton) AS SLToiDaPhieuNay,
        ctpx.DONGIA,
        (ctpx.SOLUONG * ctpx.DONGIA) AS ThanhTien
    FROM (
        SELECT MAPX, MAVT, SOLUONG, DONGIA
        FROM dbo.CTPX WITH (INDEX = PK_CTPX)
        WHERE MAPX = @MAPX AND (@MAVT IS NULL OR MAVT = @MAVT)
    ) ctpx
    JOIN (
        SELECT MAVT, TENVT, DVT, Soluongton
        FROM dbo.Vattu WITH (INDEX = PK_Vattu)
    ) vt ON ctpx.MAVT = vt.MAVT
    ORDER BY ctpx.MAVT ASC;
END;
GO

-- 4. Lập đầu phiếu xuất kho mới
CREATE OR ALTER PROCEDURE dbo.SP_ThemPhieuXuat
    @MAPX NCHAR(8),
    @NGAY DATE,
    @HOTENKH NVARCHAR(100),
    @MANV INT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.PhieuXuat (MAPX, NGAY, HOTENKH, MANV)
    VALUES (@MAPX, @NGAY, @HOTENKH, @MANV);
END;
GO

-- 5b. Cập nhật thông tin đầu phiếu xuất kho
CREATE OR ALTER PROCEDURE dbo.SP_SuaPhieuXuat
    @MAPX NCHAR(8),
    @NGAY DATE,
    @HOTENKH NVARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE dbo.PhieuXuat
    SET NGAY = @NGAY,
        HOTENKH = @HOTENKH
    WHERE MAPX = @MAPX;
END;
GO

-- 6. Xóa phiếu xuất kho (Giao tác xóa CTPX + PhieuXuat)
CREATE OR ALTER PROCEDURE dbo.SP_XoaPhieuXuat
    @MAPX NCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        DELETE FROM dbo.CTPX WHERE MAPX = @MAPX;
        DELETE FROM dbo.PhieuXuat WHERE MAPX = @MAPX;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- 7. Thêm mặt hàng vào chi tiết phiếu xuất CTPX (Giao tác Xuất kho: Ghi CTPX + Trừ tồn kho)
CREATE OR ALTER PROCEDURE dbo.SP_ThemCTPX
    @MAPX NCHAR(8),
    @MAVT NCHAR(4),
    @SOLUONG INT,
    @DONGIA FLOAT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        INSERT INTO dbo.CTPX (MAPX, MAVT, SOLUONG, DONGIA)
        VALUES (@MAPX, @MAVT, @SOLUONG, @DONGIA);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- 8. Cập nhật dòng chi tiết phiếu xuất CTPX (Giao tác Sửa xuất kho + Điều chỉnh tồn kho)
CREATE OR ALTER PROCEDURE dbo.SP_SuaCTPX
    @MAPX NCHAR(8),
    @MAVT NCHAR(4),
    @SOLUONG INT,
    @DONGIA FLOAT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        UPDATE dbo.CTPX
        SET SOLUONG = @SOLUONG,
            DONGIA = @DONGIA
        WHERE MAPX = @MAPX AND MAVT = @MAVT;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- 9. Xóa 1 dòng chi tiết phiếu xuất CTPX (Giao tác Xóa dòng xuất + Hoàn trả tồn kho)
CREATE OR ALTER PROCEDURE dbo.SP_XoaCTPX
    @MAPX NCHAR(8),
    @MAVT NCHAR(4)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        DELETE FROM dbo.CTPX
        WHERE MAPX = @MAPX AND MAVT = @MAVT;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO
