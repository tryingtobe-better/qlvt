-- =============================================================================
-- FILE 07: DỮ LIỆU MẪU ĐA DẠNG & TÀI KHOẢN MẪU (SEED DATA)
-- Server: LAPTOP-M19TS03A | Database: QLVT
-- Mục đích:
--   1. Làm sạch và khởi tạo bộ dữ liệu mẫu chuẩn, đa dạng cho 8 bảng:
--      - Nhanvien (17 nhân viên, có nhân viên đã nghỉ việc TrangThaiXoa = 1 và nhân viên mới chưa lập phiếu)
--      - Vattu (24 vật tư xây dựng - điện nước, có VT06 tồn = 0 để kiểm thử xóa vật tư)
--      - DatHang & CTDDH (15 đơn đặt hàng trải đều các tháng 01..11/2026 với đủ 3 trạng thái:
--          + 6 đơn [Đã nhập đủ] (trong đó DDH00005 nhập đủ qua 2 phiếu nhập nhiều đợt)
--          + 5 đơn [Nhập một phần] (DDH00002, DDH00007, DDH00010, DDH00013, DDH00014 - đa dạng tình huống)
--          + 4 đơn [Chưa nhập] (DDH00003, DDH00011, DDH00012, DDH00015 - chưa phát sinh phiếu nhập)
--      - PhieuNhap & CTPN (13 phiếu nhập kho từ tháng 01..11/2026)
--      - PhieuXuat & CTPX (13 phiếu xuất kho từ tháng 01..11/2026)
--   2. Khởi tạo 2 tài khoản đăng nhập mẫu:
--      - Quản trị viên: Login `admin`    / Pass `123456` (MANV = 1, Role = Admin)
--      - Nhân viên    : Login `nhanvien` / Pass `123456` (MANV = 2, Role = NhanVien)
-- =============================================================================

USE QLVT;
GO

SET NOCOUNT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    -- Tạm tắt trigger tồn kho khi làm sạch dữ liệu cũ để tránh vướng kiểm tra khi xóa CTPN
    DISABLE TRIGGER dbo.TRG_CTPN_CapNhatTonKho ON dbo.CTPN;
    DISABLE TRIGGER dbo.TRG_CTPX_CapNhatTonKho ON dbo.CTPX;

    DELETE FROM dbo.CTPX;
    DELETE FROM dbo.PhieuXuat;
    DELETE FROM dbo.CTPN;
    DELETE FROM dbo.PhieuNhap;
    DELETE FROM dbo.CTDDH;
    DELETE FROM dbo.DatHang;
    DELETE FROM dbo.Vattu;
    DELETE FROM dbo.Nhanvien;

    -- Bật lại trigger tồn kho để tự động cộng/trừ tồn kho chuẩn xác khi chèn CTPN & CTPX
    ENABLE TRIGGER dbo.TRG_CTPN_CapNhatTonKho ON dbo.CTPN;
    ENABLE TRIGGER dbo.TRG_CTPX_CapNhatTonKho ON dbo.CTPX;

    -- =========================================================================
    -- 1. Dữ liệu mẫu Nhân viên (17 nhân viên tại TP.HCM)
    -- =========================================================================
    INSERT INTO dbo.Nhanvien (MANV, HO, TEN, DIACHI, NGAYSINH, LUONG, GHICHU, TrangThaiXoa) VALUES
    (1,  N'Nguyễn Văn',    N'An',     N'12 Lê Lợi, Quận 1, TP.HCM',                  '1990-03-15', 15000000, N'Quản trị hệ thống / Quản lý kho',             0),
    (2,  N'Trần Thị',      N'Bình',   N'45 Nguyễn Huệ, Quận 1, TP.HCM',              '1994-07-22',  9000000, N'Nhân viên thủ kho chính',                      0),
    (3,  N'Lê Hoàng',      N'Cường',  N'88 Võ Văn Ngân, TP. Thủ Đức, TP.HCM',        '1996-11-05',  9000000, N'Nhân viên nhập xuất kho',                      0),
    (4,  N'Phạm Minh',     N'Dung',   N'23 Điện Biên Phủ, Bình Thạnh, TP.HCM',       '1998-01-19',  7500000, N'Nhân viên bán hàng (đã chuyển công tác)',      1),
    (5,  N'Hoàng Quốc',    N'Khánh',  N'102 Cộng Hòa, Tân Bình, TP.HCM',             '1999-09-02',  6500000, N'Nhân viên mới (chưa phát sinh phiếu)',         0),
    (6,  N'Đặng Quốc',     N'Hùng',   N'156 Nguyễn Thị Minh Khai, Quận 3, TP.HCM',   '1991-04-12', 14000000, N'Trưởng bộ phận thu mua vật tư',                0),
    (7,  N'Võ Thị Mỹ',     N'Linh',   N'72 Phan Xích Long, Phú Nhuận, TP.HCM',       '1995-08-25', 11000000, N'Kế toán kho vật tư',                           0),
    (8,  N'Bùi Thanh',     N'Tùng',   N'310 Quang Trung, Gò Vấp, TP.HCM',            '1993-12-10', 10500000, N'Giám sát điều phối kho',                       0),
    (9,  N'Ngô Phương',    N'Thảo',   N'19 Hoàng Diệu, Quận 4, TP.HCM',              '1997-02-14',  8800000, N'Nhân viên chứng từ mua hàng',                  0),
    (10, N'Đỗ Minh',       N'Quân',   N'405 Xa Lộ Hà Nội, TP. Thủ Đức, TP.HCM',      '1994-06-30',  9200000, N'Thủ kho vật liệu xây thô',                     0),
    (11, N'Lý Gia',        N'Bảo',    N'89 Hậu Giang, Quận 6, TP.HCM',               '1996-09-18',  8200000, N'Nhân viên giao nhận vật tư',                   0),
    (12, N'Trương Ngọc',   N'Ánh',    N'214 Lý Thường Kiệt, Quận 10, TP.HCM',        '1998-05-07',  7800000, N'Nhân viên bán hàng dự án',                     0),
    (13, N'Phan Văn',      N'Đức',    N'55 Nguyễn Văn Linh, Quận 7, TP.HCM',         '1992-10-21', 12000000, N'Chuyên viên kiểm kê định kỳ',                  0),
    (14, N'Dương Thị Thu', N'Hà',     N'128 Lạc Long Quân, Quận 11, TP.HCM',         '1999-03-09',  7200000, N'Nhân viên điều phối xuất kho',                 0),
    (15, N'Hồ Tấn',        N'Phát',   N'64 Trường Chinh, Tân Phú, TP.HCM',           '1995-01-28',  9000000, N'Nhân viên xuất nhập kho',                      0),
    (16, N'Mai Xuân',      N'Trường', N'91 Quốc lộ 13, Bình Thạnh, TP.HCM',          '2000-07-16',  6800000, N'Nhân viên phụ kho (chưa phát sinh phiếu)',     0),
    (17, N'Đinh Thị Cẩm',  N'Vân',    N'33 Nguyễn Ảnh Thủ, Quận 12, TP.HCM',         '2001-11-11',  6200000, N'Thực tập sinh kế toán kho',                    0);

    -- =========================================================================
    -- 2. Dữ liệu mẫu Vật tư (24 vật tư - khởi tạo tồn đầu kỳ trước khi chạy Trigger Nhập/Xuất)
    -- =========================================================================
    INSERT INTO dbo.Vattu (MAVT, TENVT, DVT, Soluongton) VALUES
    ('VT01', N'Xi măng Hà Tiên PCB40',         N'Bao',   50),
    ('VT02', N'Thép cuộn Hòa Phát Ф6',         N'Cuộn',  20),
    ('VT03', N'Gạch ống Tuynel Bình Dương',    N'Viên',  1000),
    ('VT04', N'Cát xây tô loại 1',             N'Khối',  15),
    ('VT05', N'Sơn nước Dulux Nội thất',       N'Thùng', 10),
    ('VT06', N'Ống nhựa Bình Minh Ф27',        N'Cây',   0),
    ('VT07', N'Đá dăm 1x2 Bình Hưng',          N'Khối',  45),
    ('VT08', N'Đá mi sàng Đồng Nai',           N'Khối',  30),
    ('VT09', N'Thép thanh Hòa Phát D12',       N'Cây',   120),
    ('VT10', N'Thép thanh Pomina D16',         N'Cây',   80),
    ('VT11', N'Tôn lạnh Hoa Sen 4.5 dem',      N'Tấm',   60),
    ('VT12', N'Lưới thép hàn B40 mạ kẽm',      N'Cuộn',  25),
    ('VT13', N'Bột trét tường Jotun 40kg',     N'Bao',   40),
    ('VT14', N'Sơn chống thấm Kova CT11A',     N'Thùng', 18),
    ('VT15', N'Keo dán gạch Weber Tai Vis',    N'Bao',   35),
    ('VT16', N'Gạch men Viglacera 60x60',      N'Hộp',   150),
    ('VT17', N'Ngói màu Đồng Tâm loại 1',      N'Viên',  800),
    ('VT18', N'Ống nhựa PPR Bình Minh Ф32',    N'Cây',   90),
    ('VT19', N'Dây cáp điện Cadivi 2.5mm',     N'Cuộn',  32),
    ('VT20', N'CB chống giật Panasonic 32A',   N'Cái',   28),
    ('VT21', N'Đèn pha LED Rạng Đông 50W',     N'Cái',   40),
    ('VT22', N'Ván ép phủ phim 18mm',          N'Tấm',   55),
    ('VT23', N'Bồn nước Inox Đại Thành 1000L', N'Cái',   8),
    ('VT24', N'Phụ gia chống thấm Sika Latex', N'Can',   15);

    -- =========================================================================
    -- 3. Dữ liệu mẫu Đơn đặt hàng (15 đơn: 6 Đã nhập đủ, 5 Nhập một phần, 4 Chưa nhập)
    -- =========================================================================
    INSERT INTO dbo.DatHang (MasoDDH, NGAY, NhaCC, MANV) VALUES
    -- [Đã nhập đủ] (6 đơn: DDH00001, DDH00004, DDH00005 [nhập 2 đợt], DDH00006, DDH00008, DDH00009)
    ('DDH00001', '2026-01-10', N'Công ty TNHH VLXD Miền Nam',                   1),
    ('DDH00004', '2026-03-15', N'Công ty Cổ phần Đá Hóa An',                    6),
    ('DDH00005', '2026-04-04', N'Nhà phân phối Thép Miền Nam',                  6),
    ('DDH00006', '2026-05-12', N'Tập đoàn Tôn Hoa Sen - CN Bình Dương',         8),
    ('DDH00008', '2026-07-19', N'Tổng công ty Viglacera - CN Miền Nam',        10),
    ('DDH00009', '2026-08-03', N'Công ty Cổ phần Nhựa Bình Minh',               8),

    -- [Nhập một phần] (5 đơn: DDH00002, DDH00007, DDH00010, DDH00013, DDH00014 [nhập 2 đợt])
    ('DDH00002', '2026-02-05', N'Tập đoàn Thép Hòa Phát',                       2),
    ('DDH00007', '2026-06-08', N'Công ty TNHH Sơn Jotun Việt Nam',              6),
    ('DDH00010', '2026-09-10', N'Công ty Dây cáp điện Việt Nam CADIVI',         6),
    ('DDH00013', '2026-10-22', N'Tập đoàn Tân Á Đại Thành',                     6),
    ('DDH00014', '2026-11-05', N'Công ty Cổ phần Chống thấm Sika Việt Nam',     9),

    -- [Chưa nhập] (4 đơn: DDH00003, DDH00011, DDH00012, DDH00015)
    ('DDH00003', '2026-03-01', N'Đại lý Sơn & Hóa chất Á Châu',                 3),
    ('DDH00011', '2026-09-25', N'Nhà phân phối Thiết bị điện Panasonic',        9),
    ('DDH00012', '2026-10-05', N'Công ty TNHH Ván ép Công nghiệp Nam Á',       10),
    ('DDH00015', '2026-11-12', N'Công ty TNHH Vật liệu Xây dựng Đông Á',        1);

    INSERT INTO dbo.CTDDH (MasoDDH, MAVT, SOLUONG, DONGIA) VALUES
    -- DDH00001 (Đã nhập đủ qua PN000001)
    ('DDH00001', 'VT01', 100,    85000),
    ('DDH00001', 'VT03', 2000,    1200),

    -- DDH00002 (Nhập một phần qua PN000002: VT02 đã nhập 15/30, VT04 chưa nhập 0/20)
    ('DDH00002', 'VT02', 30,   1150000),
    ('DDH00002', 'VT04', 20,    320000),

    -- DDH00003 (Chưa nhập: 0/85)
    ('DDH00003', 'VT05', 25,    950000),
    ('DDH00003', 'VT06', 60,     65000),

    -- DDH00004 (Đã nhập đủ qua PN000003)
    ('DDH00004', 'VT07', 80,    360000),
    ('DDH00004', 'VT08', 60,    290000),

    -- DDH00005 (Đã nhập đủ qua 2 đợt: PN000004 + PN000005)
    ('DDH00005', 'VT09', 200,   145000),
    ('DDH00005', 'VT10', 150,   240000),

    -- DDH00006 (Đã nhập đủ qua PN000006)
    ('DDH00006', 'VT11', 120,   165000),
    ('DDH00006', 'VT12', 40,    480000),

    -- DDH00007 (Nhập một phần qua PN000007: VT13 nhập 60/100, VT14 nhập 25/50, VT15 chưa nhập 0/80)
    ('DDH00007', 'VT13', 100,   285000),
    ('DDH00007', 'VT14', 50,    890000),
    ('DDH00007', 'VT15', 80,    195000),

    -- DDH00008 (Đã nhập đủ qua PN000008)
    ('DDH00008', 'VT16', 250,   210000),
    ('DDH00008', 'VT17', 1500,   14500),

    -- DDH00009 (Đã nhập đủ qua PN000009)
    ('DDH00009', 'VT18', 120,    92000),

    -- DDH00010 (Nhập một phần qua PN000010: VT19 nhập 35/60, VT21 đã nhập đủ 50/50)
    ('DDH00010', 'VT19', 60,    680000),
    ('DDH00010', 'VT21', 50,    310000),

    -- DDH00011 (Chưa nhập: 0/115)
    ('DDH00011', 'VT19', 30,    680000),
    ('DDH00011', 'VT20', 45,    420000),
    ('DDH00011', 'VT21', 40,    310000),

    -- DDH00012 (Chưa nhập: 0/75)
    ('DDH00012', 'VT12', 25,    480000),
    ('DDH00012', 'VT22', 50,    390000),

    -- DDH00013 (Nhập một phần qua PN000011: VT23 nhập 10/15, VT24 nhập 25/40)
    ('DDH00013', 'VT23', 15,   3100000),
    ('DDH00013', 'VT24', 40,    520000),

    -- DDH00014 (Nhập một phần qua 2 phiếu PN000012 & PN000013: VT09 đủ 50/50, VT15 20/40, VT24 0/30)
    ('DDH00014', 'VT09', 50,    145000),
    ('DDH00014', 'VT15', 40,    195000),
    ('DDH00014', 'VT24', 30,    520000),

    -- DDH00015 (Chưa nhập: 0/255)
    ('DDH00015', 'VT01', 150,    86000),
    ('DDH00015', 'VT02', 25,   1160000),
    ('DDH00015', 'VT06', 80,     65000);

    -- =========================================================================
    -- 4. Dữ liệu mẫu Phiếu nhập kho & Chi tiết phiếu nhập (13 phiếu)
    -- =========================================================================
    INSERT INTO dbo.PhieuNhap (MAPN, NGAY, MasoDDH, MANV) VALUES
    ('PN000001', '2026-01-12', 'DDH00001',  2),
    ('PN000002', '2026-02-08', 'DDH00002',  2),
    ('PN000003', '2026-03-18', 'DDH00004', 10),
    ('PN000004', '2026-04-07', 'DDH00005', 10),
    ('PN000005', '2026-04-16', 'DDH00005', 15),
    ('PN000006', '2026-05-15', 'DDH00006', 10),
    ('PN000007', '2026-06-12', 'DDH00007', 15),
    ('PN000008', '2026-07-22', 'DDH00008', 10),
    ('PN000009', '2026-08-06', 'DDH00009', 15),
    ('PN000010', '2026-09-14', 'DDH00010', 10),
    ('PN000011', '2026-10-25', 'DDH00013', 15),
    ('PN000012', '2026-11-07', 'DDH00014',  2),
    ('PN000013', '2026-11-10', 'DDH00014',  3);

    INSERT INTO dbo.CTPN (MAPN, MAVT, SOLUONG, DONGIA) VALUES
    -- PN000001 -> Nhập đủ DDH00001
    ('PN000001', 'VT01', 100,    85000),
    ('PN000001', 'VT03', 2000,    1200),
    -- PN000002 -> Nhập một phần DDH00002 (còn thiếu 15 VT02 và 20 VT04)
    ('PN000002', 'VT02', 15,   1150000),
    -- PN000003 -> Nhập đủ DDH00004
    ('PN000003', 'VT07', 80,    360000),
    ('PN000003', 'VT08', 60,    290000),
    -- PN000004 & PN000005 -> Nhập 2 đợt hoàn tất DDH00005
    ('PN000004', 'VT09', 120,   145000),
    ('PN000004', 'VT10', 100,   240000),
    ('PN000005', 'VT09', 80,    145000),
    ('PN000005', 'VT10', 50,    240000),
    -- PN000006 -> Nhập đủ DDH00006
    ('PN000006', 'VT11', 120,   165000),
    ('PN000006', 'VT12', 40,    480000),
    -- PN000007 -> Nhập một phần DDH00007 (còn thiếu 40 VT13, 25 VT14, 80 VT15)
    ('PN000007', 'VT13', 60,    285000),
    ('PN000007', 'VT14', 25,    890000),
    -- PN000008 -> Nhập đủ DDH00008
    ('PN000008', 'VT16', 250,   210000),
    ('PN000008', 'VT17', 1500,   14500),
    -- PN000009 -> Nhập đủ DDH00009
    ('PN000009', 'VT18', 120,    92000),
    -- PN000010 -> Nhập một phần DDH00010 (VT21 đủ 50/50, VT19 mới nhập 35/60)
    ('PN000010', 'VT19', 35,    680000),
    ('PN000010', 'VT21', 50,    310000),
    -- PN000011 -> Nhập một phần DDH00013 (VT23 nhập 10/15, VT24 nhập 25/40)
    ('PN000011', 'VT23', 10,   3100000),
    ('PN000011', 'VT24', 25,    520000),
    -- PN000012 & PN000013 -> Nhập 2 đợt cho DDH00014 (VT09 đủ 50/50, VT15 20/40, VT24 0/30)
    ('PN000012', 'VT09', 30,    145000),
    ('PN000012', 'VT15', 20,    195000),
    ('PN000013', 'VT09', 20,    145000);

    -- =========================================================================
    -- 5. Dữ liệu mẫu Phiếu xuất kho & Chi tiết phiếu xuất (13 phiếu)
    -- =========================================================================
    INSERT INTO dbo.PhieuXuat (MAPX, NGAY, HOTENKH, MANV) VALUES
    ('PX000001', '2026-01-20', N'Công ty Xây dựng Hòa Bình',                         3),
    ('PX000002', '2026-02-15', N'Nguyễn Minh Tuấn',                                  4),
    ('PX000003', '2026-03-25', N'Công ty Xây dựng Coteccons - Dự án Q9',            12),
    ('PX000004', '2026-04-18', N'Nhà thầu Xây dựng An Phong',                       12),
    ('PX000005', '2026-05-22', N'Công ty CP Đầu tư Xây dựng Ricons',                14),
    ('PX000006', '2026-06-19', N'Cửa hàng VLXD Đại Phát (TP. Thủ Đức)',             12),
    ('PX000007', '2026-07-28', N'Chủ đầu tư Biệt thự Thảo Điền - Anh Hải',          14),
    ('PX000008', '2026-08-14', N'Công ty Kỹ thuật Cơ điện REE M&E',                 12),
    ('PX000009', '2026-09-14', N'Đội thi công Điện nước Minh Khôi',                 15),
    ('PX000010', '2026-09-28', N'Công ty TNHH Nội thất Kiến Á',                     12),
    ('PX000011', '2026-10-08', N'Ban Quản lý Chung cư Opal Boulevard',              14),
    ('PX000012', '2026-10-28', N'Công trình Nhà xưởng KCN Tân Bình',                12),
    ('PX000013', '2026-11-12', N'Công ty Xây dựng Hòa Bình - Dự án Thủ Thiêm',      14);

    INSERT INTO dbo.CTPX (MAPX, MAVT, SOLUONG, DONGIA) VALUES
    ('PX000001', 'VT01',  40,   95000),
    ('PX000001', 'VT03', 500,    1500),
    ('PX000002', 'VT02',  10, 1280000),
    ('PX000002', 'VT05',   4, 1100000),
    ('PX000003', 'VT07',  50,  410000),
    ('PX000003', 'VT08',  35,  340000),
    ('PX000004', 'VT09',  90,  168000),
    ('PX000004', 'VT10',  70,  275000),
    ('PX000005', 'VT11',  65,  192000),
    ('PX000005', 'VT12',  20,  545000),
    ('PX000006', 'VT13',  45,  325000),
    ('PX000006', 'VT14',  18, 1020000),
    ('PX000007', 'VT16', 140,  245000),
    ('PX000007', 'VT17', 900,   17500),
    ('PX000008', 'VT18',  75,  112000),
    ('PX000009', 'VT19',  25,  765000),
    ('PX000009', 'VT20',  10,  485000),
    ('PX000010', 'VT15',  15,  230000),
    ('PX000011', 'VT21',  18,  365000),
    ('PX000011', 'VT23',   3, 3550000),
    ('PX000012', 'VT09',  60,  170000),
    ('PX000012', 'VT22',  25,  445000),
    ('PX000013', 'VT09',  40,  170000),
    ('PX000013', 'VT16',  30,  245000);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

-- =============================================================================
-- 6. Khởi tạo tài khoản đăng nhập cho các nhân viên đang làm việc có lập phiếu
--    (Nhân viên chưa lập phiếu #5, #7, #11, #13, #16, #17 để trống chưa cấp TK
--     để kiểm thử chức năng Cấp tài khoản mới và Xóa nhân viên;
--     Nhân viên #4 đã nghỉ việc nên tài khoản đã thu hồi)
-- =============================================================================
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'admin')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '1')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'admin',    @Password = '123456', @UserName = '1',  @Role = 'Admin';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nhanvien')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '2')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nhanvien', @Password = '123456', @UserName = '2',  @Role = 'NhanVien';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nv3')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '3')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nv3',      @Password = '123456', @UserName = '3',  @Role = 'NhanVien';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nv6')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '6')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nv6',      @Password = '123456', @UserName = '6',  @Role = 'NhanVien';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nv8')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '8')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nv8',      @Password = '123456', @UserName = '8',  @Role = 'NhanVien';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nv9')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '9')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nv9',      @Password = '123456', @UserName = '9',  @Role = 'NhanVien';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nv10')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '10')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nv10',     @Password = '123456', @UserName = '10', @Role = 'NhanVien';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nv12')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '12')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nv12',     @Password = '123456', @UserName = '12', @Role = 'NhanVien';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nv14')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '14')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nv14',     @Password = '123456', @UserName = '14', @Role = 'NhanVien';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'nv15')
   AND NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '15')
    EXEC dbo.SP_TaoTaiKhoan @LoginName = 'nv15',     @Password = '123456', @UserName = '15', @Role = 'NhanVien';
GO
