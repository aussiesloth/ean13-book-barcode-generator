@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 ean13_book_barcode.py
) else (
    python ean13_book_barcode.py
)
if errorlevel 1 pause
