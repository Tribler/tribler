
ver | find "Version 6." > nul
if %ERRORLEVEL% == 0 goto IFDEFVISTA
set APPDIR="Application Data"
goto general

:IFDEFVISTA
set APPDIR=AppData\Roaming
goto general

:general
set TDIR="%USERPROFILE%\%APPDIR%\.Tribler"
set DDIR="%USERPROFILE%\Desktop\TriblerDownloads"
rmdir %TDIR% /S /Q
rmdir %DDIR% /S /Q

REM SwarmPlayer
set TDIR="%USERPROFILE%\%APPDIR%\.SwarmPlayer"
rmdir %TDIR% /S /Q

REM SwarmPlugin
set TDIR="%USERPROFILE%\%APPDIR%\.SwarmPlugin"
rmdir %TDIR% /S /Q
