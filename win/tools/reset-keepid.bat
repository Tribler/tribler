
ver | find "Version 6." > nul
if %ERRORLEVEL% == 0 goto IFDEFVISTA
REM No quotes around this, otherwise we have double in the *DIR vars.
set APPDIR=%APPDIR%
goto general

:IFDEFVISTA
set APPDIR=AppData\Roaming
goto general

:general


set TDIR="%USERPROFILE%\%APPDIR%\.Tribler"
set DDIR="%USERPROFILE%\Downloads\TriblerDownloads"
rmdir %TDIR%\sqlite /S /Q
rmdir %TDIR%\dlcheckpoints /S /Q
rmdir %TDIR%\channels /S /Q
rmdir %TDIR%\logs /S /Q
del %TDIR%\triblerd.conf
REM Remove downloads
rmdir %DDIR% /S /Q
