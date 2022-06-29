REM @echo off
REM No LIBRARYNAME here as this is not distributed with Tribler as BaseLib

if not defined LOG_LEVEL set LOG_LEVEL="DEBUG"

REM Check that we are running from the expected directory
IF NOT EXIST build\win (
  ECHO .
  ECHO Please, execute this script from the repository root
  EXIT /b
)

REM locate Python directory and set up Python environment
python3 build\win\locate-python.py > tmp_pythonhome.txt
SET /p PYTHONHOME= < tmp_pythonhome.txt
DEL /f /q tmp_pythonhome.txt
REM Arno: Add . to find our core
SET PYTHONPATH=.;%PYTHONHOME%
ECHO PYTHONPATH SET TO %PYTHONPATH%

REM ----- Check for NSIS installer
SET NSIS="C:\Program Files\NSIS\makensis.exe"

IF NOT EXIST %NSIS% SET NSIS="C:\Program Files (x86)\NSIS\makensis.exe"
IF NOT EXIST %NSIS% (
  ECHO .
  ECHO Could not locate the NSIS installer at %NSIS%.
  ECHO Please modify this script or install NSIS [nsis.sf.net]
  EXIT /b
)

REM ----- Clean up

call build\win\clean.bat

REM ----- Prepare venv & install dependencies before the build

python3 -m venv build-env
./build-env/Scripts/activate.bat
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade -r requirements-build.txt

REM ----- Build

REM Arno: When adding files here, make sure tribler.nsi actually
REM packs them in the installer .EXE

ECHO Install pip dependencies for correct py-installer's work
python3 -m pip install --upgrade -r build\win\requirements.txt

%PYTHONHOME%\Scripts\pyinstaller.exe tribler.spec --log-level=%LOG_LEVEL% || exit /b

copy build\win\resources\tribler*.nsi dist\tribler

REM Martijn 2016-11-05: causing problems with PyInstaller
REM copy Tribler\Main\Build\Win\tribler.exe.manifest dist\tribler

type LICENSE binary-LICENSE-postfix.txt > binary-LICENSE.txt
copy binary-LICENSE.txt dist\tribler

mkdir dist\tribler\tools
copy build\win\tools\reset*.bat dist\tribler\tools

REM Laurens, 2016-04-20: Copy the redistributables of 2008, 2012 and 2015 to the install dir
REM Sandip, 2019-10-24: redistributables 2008, 2012 are not necessary anymore
REM copy C:\build\vc_redist_110.exe dist\tribler
copy C:\build\vc_redist_140.exe dist\tribler

REM Copy various libraries required on runtime (libsodium and openssl)
copy C:\build\libsodium.dll dist\tribler
REM Sandip, 2019-10-24: No need to copy openssl dlls separately
REM copy C:\build\openssl\*.dll dist\tribler


@echo Running NSIS
cd dist\tribler

REM get password for swarmplayerprivatekey.pfx
set /p PASSWORD="Enter the PFX password:"

REM Arno: Sign Tribler.exe so MS "Block / Unblock" dialog has publisher info.
REM --- Doing this in ugly way for now
if not defined SKIP_SIGNING_TRIBLER_BINARIES (
    signtool.exe sign /f C:\build\certs\certificate.pfx /p "%PASSWORD%" /d "Tribler" /t "http://timestamp.digicert.com" tribler.exe
)
:makeinstaller
%NSIS% tribler.nsi || exit /b
move Tribler_*.exe ..
cd ..
REM Arno: Sign installer
if not defined SKIP_SIGNING_TRIBLER_BINARIES (
    signtool.exe sign /f c:\build\certs\certificate.pfx /p "%PASSWORD%" /d "Tribler" /t "http://timestamp.digicert.com" Tribler_*.exe
)

REM to neglect error code from the previous command we do exit 0
exit 0
