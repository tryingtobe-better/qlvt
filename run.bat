@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================================
echo   QLVT - HE THONG QUAN LY VAT TU (AUTO SETUP ^& RUN)
echo ============================================================================

:: 1. Tu dong phat hien SQL Server tren may va tao file .env neu chua co
if not exist ".env" (
    set "DETECTED_SERVER=localhost"
    sqlcmd -S localhost -E -C -Q "SELECT 1" >nul 2>&1
    if errorlevel 1 (
        sqlcmd -S "%COMPUTERNAME%" -E -C -Q "SELECT 1" >nul 2>&1
        if not errorlevel 1 (
            set "DETECTED_SERVER=%COMPUTERNAME%"
        ) else (
            sqlcmd -S "localhost\SQLEXPRESS" -E -C -Q "SELECT 1" >nul 2>&1
            if not errorlevel 1 set "DETECTED_SERVER=localhost\SQLEXPRESS"
        )
    )
    echo [1/4] Tao file cau hinh .env voi SQL Server: !DETECTED_SERVER!
    (
        echo DEBUG=false
        echo DB_DRIVER=ODBC Driver 17 for SQL Server
        echo DB_SERVER=!DETECTED_SERVER!
        echo DB_NAME=QLVT
        echo DB_ENCRYPT=yes
        echo DB_TRUST_CERT=yes
    ) > ".env"
)

:: Doc DB_SERVER tu file .env
set "SQL_SERVER=localhost"
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="DB_SERVER" set "SQL_SERVER=%%B"
)

:: 2. Kiem tra va tu dong khoi tao CSDL QLVT + 7 file SQL neu chua co
echo [2/4] Kiem tra co so du lieu QLVT tren SQL Server (!SQL_SERVER!)...
sqlcmd -S "!SQL_SERVER!" -d QLVT -E -C -Q "IF OBJECT_ID('dbo.SP_DangNhap', 'P') IS NULL RAISERROR('MISSING', 16, 1)" >nul 2>&1
if errorlevel 1 (
    echo       Dang khoi tao Database QLVT, Bang, Trigger, Stored Procedures va Du lieu mau...
    sqlcmd -S "!SQL_SERVER!" -E -C -f 65001 -b -i sql\01_tables_and_constraints.sql -i sql\02_triggers.sql -i sql\03_auth_and_system.sql -i sql\04_danh_muc.sql -i sql\05_giao_dich_kho.sql -i sql\06_bao_cao.sql -i sql\07_seed_data.sql
    if errorlevel 1 (
        echo [LOI] Khong the khoi tao CSDL QLVT. Vui long kiem tra SQL Server da bat va cho phep SQL Server Authentication ^(Mixed Mode^).
        pause
        exit /b 1
    )
    echo       Da khoi tao CSDL QLVT va tai khoan mau thanh cong!
) else (
    echo       CSDL QLVT da san sang.
)

:: 3. Tao moi truong ao Python (.venv) va cai dat thu vien neu chua co
if not exist ".venv\Scripts\python.exe" (
    echo [3/4] Dang tao moi truong ao Python ^(.venv^) va cai dat thu vien...
    python -m venv .venv
    if errorlevel 1 (
        echo [LOI] Khong tim thay Python. Vui long cai dat Python 3.10+ va tich chon "Add Python to PATH".
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
    ".venv\Scripts\pip.exe" install -r requirements.txt
) else (
    echo [3/4] Moi truong Python ^(.venv^) da san sang.
)

:: 4. Khoi chay ung dung Web
echo [4/4] Dang khoi chay QLVT Web tai http://127.0.0.1:5000 ...
echo       Tai khoan Admin    : admin    / 123456
echo       Tai khoan NhanVien : nhanvien / 123456
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" -B main.py
pause
