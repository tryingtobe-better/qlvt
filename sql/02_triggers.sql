-- =============================================================================
-- FILE 02: TRIGGERS TỰ ĐỘNG CẬP NHẬT SỐ LƯỢNG TỒN KHO
-- Server: LAPTOP-M19TS03A | Database: QLVT
-- Mục đích:
--   Đảm bảo tồn kho (`dbo.Vattu.Soluongton`) luôn chính xác tuyệt đối khi có bất kỳ
--   thao tác INSERT / UPDATE / DELETE nào trên bảng chi tiết nhập (`CTPN`) và xuất (`CTPX`):
--     1. TRG_CTPN_CapNhatTonKho: Kiểm tra vật tư thuộc ĐĐH, SL nhập <= SL đặt, cộng tồn kho.
--     2. TRG_CTPX_CapNhatTonKho: Kiểm tra SL xuất <= Soluongton hiện có, trừ tồn kho.
-- =============================================================================

USE QLVT;
GO

-- =============================================================================
-- 1. Trigger trên bảng CTPN (Nhập hàng -> Kiểm tra SL đặt & Tăng tồn kho)
-- =============================================================================
CREATE OR ALTER TRIGGER dbo.TRG_CTPN_CapNhatTonKho
ON dbo.CTPN
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    -- Bước 1: Kiểm tra vật tư nhập phải tồn tại trong CTDDH của đơn đặt hàng tương ứng
    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN dbo.PhieuNhap pn ON i.MAPN = pn.MAPN
        LEFT JOIN dbo.CTDDH ctddh ON pn.MasoDDH = ctddh.MasoDDH AND i.MAVT = ctddh.MAVT
        WHERE ctddh.MAVT IS NULL
    )
    BEGIN
        RAISERROR(N'Lỗi: Vật tư nhập không nằm trong chi tiết đơn đặt hàng của phiếu nhập này!', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END;

    -- Bước 2: Kiểm tra tổng số lượng nhập qua các phiếu không vượt quá số lượng đặt trong CTDDH
    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN dbo.PhieuNhap pn ON i.MAPN = pn.MAPN
        JOIN dbo.CTDDH ctddh ON pn.MasoDDH = ctddh.MasoDDH AND i.MAVT = ctddh.MAVT
        OUTER APPLY (
            SELECT SUM(ctpn.SOLUONG) AS TongDaNhap
            FROM dbo.CTPN ctpn
            JOIN dbo.PhieuNhap pn2 ON ctpn.MAPN = pn2.MAPN
            WHERE pn2.MasoDDH = pn.MasoDDH AND ctpn.MAVT = i.MAVT
        ) daNhap
        WHERE daNhap.TongDaNhap > ctddh.SOLUONG
    )
    BEGIN
        RAISERROR(N'Lỗi: Số lượng nhập vượt quá số lượng đã đặt trong đơn hàng!', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END;

    -- Bước 3: Cập nhật số lượng tồn (Cộng thêm số mới trong inserted, trừ đi số cũ trong deleted)
    UPDATE vt
    SET vt.Soluongton = vt.Soluongton
                        + ISNULL((SELECT SUM(SOLUONG) FROM inserted WHERE MAVT = vt.MAVT), 0)
                        - ISNULL((SELECT SUM(SOLUONG) FROM deleted WHERE MAVT = vt.MAVT), 0)
    FROM dbo.Vattu vt
    WHERE vt.MAVT IN (SELECT MAVT FROM inserted UNION SELECT MAVT FROM deleted);

    -- Bước 4: Đảm bảo tồn kho không bị âm khi xóa/sửa giảm phiếu nhập
    IF EXISTS (SELECT 1 FROM dbo.Vattu WHERE Soluongton < 0)
    BEGIN
        RAISERROR(N'Lỗi: Không thể giảm hoặc xóa chi tiết phiếu nhập vì sẽ làm âm số lượng tồn kho!', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END;
END;
GO

-- =============================================================================
-- 2. Trigger trên bảng CTPX (Xuất hàng -> Kiểm tra đủ tồn kho & Giảm tồn kho)
-- =============================================================================
CREATE OR ALTER TRIGGER dbo.TRG_CTPX_CapNhatTonKho
ON dbo.CTPX
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    -- Bước 1: Kiểm tra tồn kho trước khi trừ để không bị âm kho
    IF EXISTS (
        SELECT 1
        FROM dbo.Vattu vt
        WHERE vt.MAVT IN (SELECT MAVT FROM inserted UNION SELECT MAVT FROM deleted)
          AND (
              vt.Soluongton
              + ISNULL((SELECT SUM(SOLUONG) FROM deleted WHERE MAVT = vt.MAVT), 0)
              - ISNULL((SELECT SUM(SOLUONG) FROM inserted WHERE MAVT = vt.MAVT), 0)
          ) < 0
    )
    BEGIN
        RAISERROR(N'Lỗi: Số lượng xuất vượt quá số lượng tồn kho hiện có!', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END;

    -- Bước 2: Cập nhật số lượng tồn (Cộng trả lại số cũ trong deleted, trừ đi số mới trong inserted)
    UPDATE vt
    SET vt.Soluongton = vt.Soluongton
                        + ISNULL((SELECT SUM(SOLUONG) FROM deleted WHERE MAVT = vt.MAVT), 0)
                        - ISNULL((SELECT SUM(SOLUONG) FROM inserted WHERE MAVT = vt.MAVT), 0)
    FROM dbo.Vattu vt
    WHERE vt.MAVT IN (SELECT MAVT FROM inserted UNION SELECT MAVT FROM deleted);
END;
GO
