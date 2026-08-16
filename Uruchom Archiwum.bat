@echo off
chcp 65001 >nul
title AWA Archiwum - serwer lokalny - NIE ZAMYKAJ podczas przegladania strony
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Nie znaleziono Pythona w tym systemie.
    echo.
    echo Pobierz i zainstaluj Pythona ze strony: https://www.python.org/downloads/
    echo Podczas instalacji zaznacz opcje "Add python.exe to PATH".
    echo Po instalacji uruchom ten plik ponownie.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient).Connect('127.0.0.1', 8000); exit 0 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
    echo Serwer juz dziala na porcie 8000 - nie uruchamiam drugiej kopii.
    echo Otwieram Archiwum w przegladarce...
    start "" http://localhost:8000 <nul
    timeout /t 2 /nobreak >nul
    exit /b 0
)

echo Uruchamiam lokalny serwer i otwieram Archiwum w przegladarce...
start "" /B powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:8000'" <nul

echo.
echo To okno to lokalny serwer Archiwum Wielkiej Apostazji - strona
echo potrzebuje go, zeby wczytac dane (artykuly, ksiazki, playlisty).
echo Mozesz to okno zminimalizowac, ale NIE ZAMYKAJ go, dopoki przegladasz strone.
echo Zamkniecie tego okna wylaczy strone w przegladarce.
echo.

python -m http.server 8000
