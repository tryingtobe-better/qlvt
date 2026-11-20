-- =============================================================================
-- FILE 06: STORED PROCEDURES BÁO CÁO & THỐNG KÊ KHO (PHẦN 2)
-- Server: LAPTOP-M19TS03A | Database: QLVT
-- Áp dụng các kỹ thuật Tối ưu hóa truy vấn trên 1 CSDL:
--   - [Tối ưu - Cách 1]: Dùng phép chọn/chiếu trước, phép kết sau.
--   - [Tối ưu - Cách 3]: Biến đổi tương đương P1 ^ (P2 v P3) để điều kiện xuất hiện 1 lần.
--   - [Tối ưu - Cách 4]: Trong AND đặt điều kiện xác suất sai cao ở đầu;
--                        trong OR đặt điều kiện xác suất đúng cao ở đầu.
--   - [Tối ưu - Cách 5]: Sử dụng chỉ mục sắp thứ tự trước với WITH (INDEX=ten_index).
-- =============================================================================

USE QLVT;
GO

-- =============================================================================
-- SP 1: dbo.usp_RPT_DSNhanVien
-- Mục đích : In danh sách toàn bộ nhân viên sắp xếp tăng dần theo Tên, Họ.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = IX_Nhanvien_TenHo)` vì chỉ mục này
--     đã sắp xếp sẵn theo đúng thứ tự `(TEN, HO, MANV)` giúp không tốn chi phí Sort.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_RPT_DSNhanVien
AS
BEGIN
    SET NOCOUNT ON;

    -- [Tối ưu - Cách 5]: Đọc theo thứ tự Index IX_Nhanvien_TenHo đã sắp sẵn (TEN, HO, MANV)
    SELECT
        MANV,
        HO,
        TEN,
        HO + N' ' + TEN AS HOTEN,
        DIACHI,
        NGAYSINH,
        LUONG,
        GHICHU,
        CAST(TrangThaiXoa AS INT) AS TrangThaiXoa
    FROM dbo.Nhanvien WITH (INDEX = IX_Nhanvien_TenHo)
    ORDER BY TEN, HO, MANV;
END;
GO

-- =============================================================================
-- SP 2: dbo.usp_RPT_DMVatTu
-- Mục đích : In danh mục vật tư kèm đơn vị tính và số lượng tồn kho hiện tại.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = UQ_Vattu_TenVT)` vì chỉ mục Unique trên
--     cột `TENVT` đã sắp xếp sẵn theo Tên vật tư tăng dần.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_RPT_DMVatTu
AS
BEGIN
    SET NOCOUNT ON;

    -- [Tối ưu - Cách 5]: Đọc theo thứ tự Index UQ_Vattu_TenVT đã sắp sẵn theo TENVT
    SELECT
        RTRIM(MAVT) AS MAVT,
        TENVT,
        DVT,
        Soluongton
    FROM dbo.Vattu WITH (INDEX = UQ_Vattu_TenVT)
    ORDER BY TENVT, MAVT;
END;
GO

-- =============================================================================
-- SP 3: dbo.usp_RPT_DonDatHangChuaNhapHet
-- Mục đích : Liệt kê các Đơn đặt hàng chưa có Phiếu nhập hoặc mới nhập một phần.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]:
--     + Bước 1: Chiếu chỉ các cột cần dùng trên `CTDDH`, `PhieuNhap`, `CTPN` và lọc
--       ngay những dòng còn thiếu (`ct.SOLUONG > ISNULL(nhap.SLDaNhap, 0)`).
--     + Bước 2: Sau khi đã thu hẹp tập dòng còn thiếu, mới thực hiện phép kết (`JOIN`)
--       với `DatHang`, `Vattu` và `Nhanvien` để lấy thông tin hiển thị.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = PK_CTDDH)`, `WITH (INDEX = PK_DatHang)`,
--     `WITH (INDEX = PK_Vattu)`, `WITH (INDEX = PK_Nhanvien)`.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_RPT_DonDatHangChuaNhapHet
AS
BEGIN
    SET NOCOUNT ON;

    -- [Tối ưu - Cách 1]: Lọc các dòng chi tiết còn thiếu trước, kết lấy tên ĐĐH/Vật tư/Nhân viên sau
    SELECT
        RTRIM(dh.MasoDDH) AS MasoDDH,
        dh.NGAY,
        dh.NhaCC,
        nv.NVLap,
        RTRIM(thieu.MAVT) AS MAVT,
        vt.TENVT,
        vt.DVT,
        thieu.SLDat,
        thieu.SLDaNhap,
        thieu.SLConThieu,
        thieu.TrangThai
    FROM (
        SELECT
            ct.MasoDDH,
            ct.MAVT,
            ct.SOLUONG AS SLDat,
            ISNULL(nhap.SLDaNhap, 0) AS SLDaNhap,
            ct.SOLUONG - ISNULL(nhap.SLDaNhap, 0) AS SLConThieu,
            CASE
                WHEN nhap.SLDaNhap IS NULL OR nhap.SLDaNhap = 0 THEN N'Chưa nhập'
                ELSE N'Nhập một phần'
            END AS TrangThai
        FROM (
            SELECT MasoDDH, MAVT, SOLUONG
            FROM dbo.CTDDH WITH (INDEX = PK_CTDDH)
        ) ct
        LEFT JOIN (
            SELECT pn.MasoDDH, ctpn.MAVT, SUM(ctpn.SOLUONG) AS SLDaNhap
            FROM (SELECT MAPN, MasoDDH FROM dbo.PhieuNhap) pn
            JOIN (SELECT MAPN, MAVT, SOLUONG FROM dbo.CTPN) ctpn ON pn.MAPN = ctpn.MAPN
            GROUP BY pn.MasoDDH, ctpn.MAVT
        ) nhap ON ct.MasoDDH = nhap.MasoDDH AND ct.MAVT = nhap.MAVT
        WHERE ct.SOLUONG > ISNULL(nhap.SLDaNhap, 0)
    ) thieu
    JOIN (
        SELECT MasoDDH, NGAY, NhaCC, MANV
        FROM dbo.DatHang WITH (INDEX = PK_DatHang)
    ) dh ON thieu.MasoDDH = dh.MasoDDH
    JOIN (
        SELECT MAVT, TENVT, DVT
        FROM dbo.Vattu WITH (INDEX = PK_Vattu)
    ) vt ON thieu.MAVT = vt.MAVT
    JOIN (
        SELECT MANV, HO + N' ' + TEN AS NVLap
        FROM dbo.Nhanvien WITH (INDEX = PK_Nhanvien)
    ) nv ON dh.MANV = nv.MANV
    ORDER BY dh.NGAY, dh.MasoDDH, vt.TENVT;
END;
GO

-- =============================================================================
-- SP 4: dbo.usp_RPT_BangKeNhapXuat
-- Mục đích : Bảng kê chi tiết từng dòng vật tư đã Nhập ('N'), Xuất ('X') hoặc cả hai ('T')
--            trong khoảng [@TuNgay, @DenNgay], phục vụ gom nhóm theo từng Tháng/Năm.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Lọc các phiếu theo khoảng ngày
--     `NGAY BETWEEN @TuNgay AND @DenNgay` trên bảng `PhieuNhap` / `PhieuXuat` trước,
--     rồi mới kết với `CTPN` / `CTPX`, và cuối cùng mới kết với `Vattu`.
--   - [Tối ưu - Cách 3 (Biến đổi tương đương P1 ^ (P2 v P3))]:
--     Gộp điều kiện ngày xuất hiện 1 lần: `(@Loai = 'T' OR @Loai = 'N') AND NGAY BETWEEN @TuNgay AND @DenNgay`.
--   - [Tối ưu - Cách 4 (Thứ tự điều kiện AND / OR)]:
--     + Trong OR: `@Loai = 'T'` là mặc định (xác suất đúng cao nhất) nên đặt trước `@Loai = 'N'` / `'X'`.
--     + Trong AND: Đặt `(@Loai = 'T' OR @Loai = 'N')` ở đầu mệnh đề AND để nếu người dùng chọn
--       chỉ Xuất (`@Loai = 'X'`) thì điều kiện sai ngay lập tức mà không cần đọc bảng `PhieuNhap`.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = IX_PhieuNhap_NGAY)` và `WITH (INDEX = IX_PhieuXuat_NGAY)`.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_RPT_BangKeNhapXuat
    @TuNgay DATE,
    @DenNgay DATE,
    @Loai CHAR(1) = 'T'
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        YEAR(bc.Ngay) AS Nam,
        MONTH(bc.Ngay) AS Thang,
        bc.Loai,
        bc.Ngay,
        RTRIM(bc.MaPhieu) AS MaPhieu,
        RTRIM(bc.MAVT) AS MAVT,
        vt.TENVT,
        vt.DVT,
        bc.SOLUONG,
        bc.DONGIA,
        bc.SOLUONG * bc.DONGIA AS TriGia
    FROM (
        -- Nhánh Nhập kho: [Tối ưu - Cách 1, 3, 4, 5]
        SELECT 'N' AS Loai, p.NGAY AS Ngay, p.MAPN AS MaPhieu, c.MAVT, c.SOLUONG, c.DONGIA
        FROM (
            SELECT MAPN, NGAY
            FROM dbo.PhieuNhap WITH (INDEX = IX_PhieuNhap_NGAY)
            WHERE (@Loai = 'T' OR @Loai = 'N') AND NGAY BETWEEN @TuNgay AND @DenNgay
        ) p
        JOIN (
            SELECT MAPN, MAVT, SOLUONG, DONGIA
            FROM dbo.CTPN WITH (INDEX = PK_CTPN)
        ) c ON p.MAPN = c.MAPN

        UNION ALL

        -- Nhánh Xuất kho: [Tối ưu - Cách 1, 3, 4, 5]
        SELECT 'X' AS Loai, p.NGAY AS Ngay, p.MAPX AS MaPhieu, c.MAVT, c.SOLUONG, c.DONGIA
        FROM (
            SELECT MAPX, NGAY
            FROM dbo.PhieuXuat WITH (INDEX = IX_PhieuXuat_NGAY)
            WHERE (@Loai = 'T' OR @Loai = 'X') AND NGAY BETWEEN @TuNgay AND @DenNgay
        ) p
        JOIN (
            SELECT MAPX, MAVT, SOLUONG, DONGIA
            FROM dbo.CTPX WITH (INDEX = PK_CTPX)
        ) c ON p.MAPX = c.MAPX
    ) bc
    JOIN (
        SELECT MAVT, TENVT, DVT
        FROM dbo.Vattu WITH (INDEX = PK_Vattu)
    ) vt ON bc.MAVT = vt.MAVT
    ORDER BY Nam, Thang, bc.Ngay, bc.MaPhieu, vt.TENVT;
END;
GO

-- =============================================================================
-- SP 5: dbo.usp_RPT_ThongKeTheoThang
-- Mục đích : Thống kê số lượng phiếu, tổng SL vật tư và tổng trị giá đủ 12 tháng
--            trong năm `@Nam` cho Phiếu Nhập (`@Loai = 'N'`) hoặc Phiếu Xuất (`@Loai = 'X'`).
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Chọn trước các phiếu thuộc năm `@Nam`
--     (`NGAY BETWEEN @DauNam AND @CuoiNam`) trên `PhieuNhap`/`PhieuXuat` rồi mới kết với `CTPN`/`CTPX`.
--   - [Tối ưu - Cách 4]: Đặt `@Loai = 'N'` / `@Loai = 'X'` ở đầu mệnh đề AND để nhánh không khớp
--     có xác suất sai 100% và dừng ngay lập tức.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = IX_PhieuNhap_NGAY)` và `WITH (INDEX = IX_PhieuXuat_NGAY)`.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_RPT_ThongKeTheoThang
    @Nam INT,
    @Loai CHAR(1)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @DauNam DATE = DATEFROMPARTS(@Nam, 1, 1);
    DECLARE @CuoiNam DATE = DATEFROMPARTS(@Nam, 12, 31);

    SELECT
        m.Thang,
        COUNT(DISTINCT ph.MaPhieu) AS SoPhieu,
        ISNULL(SUM(ph.SOLUONG), 0) AS TongSoLuong,
        ISNULL(SUM(ph.SOLUONG * ph.DONGIA), 0) AS TongTriGia
    FROM (VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11),(12)) AS m(Thang)
    LEFT JOIN (
        -- [Tối ưu - Cách 1, 4, 5]: Chọn PhieuNhap trong năm trước với WITH (INDEX), kết CTPN sau
        SELECT p.MAPN AS MaPhieu, p.Thang, c.SOLUONG, c.DONGIA
        FROM (
            SELECT MAPN, MONTH(NGAY) AS Thang
            FROM dbo.PhieuNhap WITH (INDEX = IX_PhieuNhap_NGAY)
            WHERE @Loai = 'N' AND NGAY BETWEEN @DauNam AND @CuoiNam
        ) p
        LEFT JOIN (
            SELECT MAPN, SOLUONG, DONGIA
            FROM dbo.CTPN WITH (INDEX = PK_CTPN)
        ) c ON p.MAPN = c.MAPN

        UNION ALL

        -- [Tối ưu - Cách 1, 4, 5]: Chọn PhieuXuat trong năm trước với WITH (INDEX), kết CTPX sau
        SELECT p.MAPX AS MaPhieu, p.Thang, c.SOLUONG, c.DONGIA
        FROM (
            SELECT MAPX, MONTH(NGAY) AS Thang
            FROM dbo.PhieuXuat WITH (INDEX = IX_PhieuXuat_NGAY)
            WHERE @Loai = 'X' AND NGAY BETWEEN @DauNam AND @CuoiNam
        ) p
        LEFT JOIN (
            SELECT MAPX, SOLUONG, DONGIA
            FROM dbo.CTPX WITH (INDEX = PK_CTPX)
        ) c ON p.MAPX = c.MAPX
    ) ph ON m.Thang = ph.Thang
    GROUP BY m.Thang
    ORDER BY m.Thang;
END;
GO

-- =============================================================================
-- SP 6: dbo.usp_RPT_TongHopNhapXuat
-- Mục đích : Tổng hợp tiền Nhập và tiền Xuất theo từng ngày kèm tỷ lệ % toàn kỳ.
-- Kỹ thuật tối ưu áp dụng:
--   - [Tối ưu - Cách 1 (Chọn/chiếu trước, kết sau)]: Chọn trước các phiếu thỏa điều kiện
--     `NGAY BETWEEN @TuNgay AND @DenNgay` trên bảng `PhieuNhap` và `PhieuXuat` rồi mới
--     thực hiện phép kết `JOIN` với bảng chi tiết `CTPN` và `CTPX`.
--   - [Tối ưu - Cách 5]: Sử dụng `WITH (INDEX = IX_PhieuNhap_NGAY)` và `WITH (INDEX = IX_PhieuXuat_NGAY)`.
-- =============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_RPT_TongHopNhapXuat
    @TuNgay DATE,
    @DenNgay DATE
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        Ngay,
        Nhap,
        ISNULL(Nhap / NULLIF(SUM(Nhap) OVER (), 0), 0) AS TyLeNhap,
        Xuat,
        ISNULL(Xuat / NULLIF(SUM(Xuat) OVER (), 0), 0) AS TyLeXuat
    FROM (
        SELECT
            NGAY AS Ngay,
            SUM(TienNhap) AS Nhap,
            SUM(TienXuat) AS Xuat
        FROM (
            -- [Tối ưu - Cách 1 & Cách 5]: Chọn PhieuNhap theo ngày với WITH (INDEX) trước khi kết CTPN
            SELECT p.NGAY, c.SOLUONG * c.DONGIA AS TienNhap, CAST(0 AS FLOAT) AS TienXuat
            FROM (
                SELECT MAPN, NGAY
                FROM dbo.PhieuNhap WITH (INDEX = IX_PhieuNhap_NGAY)
                WHERE NGAY BETWEEN @TuNgay AND @DenNgay
            ) p
            JOIN (
                SELECT MAPN, SOLUONG, DONGIA
                FROM dbo.CTPN WITH (INDEX = PK_CTPN)
            ) c ON p.MAPN = c.MAPN

            UNION ALL

            -- [Tối ưu - Cách 1 & Cách 5]: Chọn PhieuXuat theo ngày với WITH (INDEX) trước khi kết CTPX
            SELECT p.NGAY, CAST(0 AS FLOAT) AS TienNhap, c.SOLUONG * c.DONGIA AS TienXuat
            FROM (
                SELECT MAPX, NGAY
                FROM dbo.PhieuXuat WITH (INDEX = IX_PhieuXuat_NGAY)
                WHERE NGAY BETWEEN @TuNgay AND @DenNgay
            ) p
            JOIN (
                SELECT MAPX, SOLUONG, DONGIA
                FROM dbo.CTPX WITH (INDEX = PK_CTPX)
            ) c ON p.MAPX = c.MAPX
        ) ct
        GROUP BY NGAY
    ) th
    ORDER BY Ngay;
END;
GO
