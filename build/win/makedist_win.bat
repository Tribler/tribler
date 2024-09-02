REM @echo off
REM No LIBRARYNAME here as this is not distributed with Tribler as BaseLib
setlocal

if not defined LOG_LEVEL set LOG_LEVEL="DEBUG"

REM Check that we are running from the expected directory
IF NOT EXIST build\win (
  ECHO .
  ECHO Please, execute this script from the repository root
  EXIT /b
)

REM ----- Check for NSIS installer
SET NSIS="C:\Program Files\NSIS\makensis.exe"

IF NOT EXIST %NSIS% SET NSIS="C:\Program Files (x86)\NSIS\makensis.exe"
IF NOT EXIST %NSIS% (
  ECHO .
  ECHO Could not locate the NSIS installer at %NSIS%.
  ECHO Please modify this script or install NSIS [nsis.sf.net]
  EXIT /b
)

REM ----- Build

REM Sandip 2024-03-22: Deprecated, we are not using PyInstaller anymore because of issue with False Malware detections.
REM %PYTHONHOME%\Scripts\pyinstaller.exe tribler.spec --log-level=%LOG_LEVEL% || exit /b
ECHO Building Tribler using Cx_Freeze
call python3 build/setup.py build

copy build\win\resources\tribler*.nsi dist\tribler

REM Martijn 2016-11-05: causing problems with PyInstaller
REM copy Tribler\Main\Build\Win\tribler.exe.manifest dist\tribler

mkdir dist\tribler\tools
copy build\win\tools\reset*.bat dist\tribler\tools

REM Copy various libraries required on runtime (libsodium and openssl)
move src\libsodium.dll dist\tribler\lib
REM Sandip, 2024-03-26: Some openssl dlls are missing so need to be copied manually.
copy C:\Program Files\OpenSSL\bin\*.dll dist\tribler\lib


REM Arno: Sign Tribler.exe so MS "Block / Unblock" dialog has publisher info.
REM --- Doing this in ugly way for now
if not defined SKIP_SIGNING_TRIBLER_BINARIES (
    openssl req  -nodes -new -x509 -config build\win\keygen_config.txt -keyout key.pem -out pub_key.pem
    openssl pkcs12 -export -in pub_key.pem -inkey key.pem -out ot_cert.pfx -passout pass:
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe" sign /f ot_cert.pfx /d "Tribler" /t "http://timestamp.digicert.com" dist\tribler\tribler.exe
)

@echo Running NSIS
cd dist\tribler

:makeinstaller
%NSIS% /DVERSION=%GITHUB_TAG% tribler.nsi || exit /b
move Tribler_*.exe ..
cd ..
REM Arno: Sign installer
if not defined SKIP_SIGNING_TRIBLER_BINARIES (
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe" sign /f ..\ot_cert.pfx /d "Tribler" /t "http://timestamp.digicert.com" Tribler_*.exe
)

endlocal
REM to neglect error code from the previous command we do exit 0
exit 0
