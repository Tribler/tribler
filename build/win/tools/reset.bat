
ver | find "Version 6." > nul
if %ERRORLEVEL% == 0 goto IFDEFVISTA
REM No quotes around this, otherwise we have double in the *DIR vars
set APPDIR=Application Data
goto general

:IFDEFVISTA
set APPDIR=AppData\Roaming
goto general

:general
set TDIR="%USERPROFILE%\%APPDIR%\.Tribler"
set DDIR="%USERPROFILE%\Downloads\TriblerDownloads"
rmdir %TDIR% /S /Q
rmdir %DDIR% /S /Q
