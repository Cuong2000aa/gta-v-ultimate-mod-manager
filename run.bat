@echo off
rem Launch GTA V Ultimate Mod Manager (no console window)
cd /d "%~dp0"

set "PYTHONW=%LocalAppData%\Programs\Python\Python311\pythonw.exe"
if not exist "%PYTHONW%" set "PYTHONW=%LocalAppData%\Programs\Python\Python310\pythonw.exe"
if not exist "%PYTHONW%" set "PYTHONW=pythonw.exe"

rem The data location is selected in Settings and resolved from a machine-local
rem bootstrap file. --data-dir remains available for explicit/portable launches.
start "" "%PYTHONW%" -m gta_mod_manager
