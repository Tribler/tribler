REM @echo off
REM No LIBRARYNAME here as this is not distributed with Tribler as BaseLib

REM Check that we are running from the expected directory
IF NOT EXIST Tribler\Main (
  ECHO .
  ECHO Please, execute this script from the repository root
  EXIT /b
)

REM locate Python directory and set up Python environment
SET BUILDER_PYTHON_VERSION="2"
IF [%1] NEQ [] (
  SET BUILDER_PYTHON_VERSION="%~1"
)

ECHO Builder Python version: %BUILDER_PYTHON_VERSION%
IF %BUILDER_PYTHON_VERSION% == "2" (
  python win\locate-python.py > tmp_pythonhome.txt
)
IF %BUILDER_PYTHON_VERSION% == "3" (
  python3 win\locate-python.py > tmp_pythonhome.txt
)

SET /p PYTHONHOME= < tmp_pythonhome.txt
DEL /f /q tmp_pythonhome.txt
REM Arno: Add . to find our core
SET PYTHONPATH=.;%PYTHONHOME%
ECHO PYTHONPATH SET TO %PYTHONPATH%

REM ----- Check for PyInstaller

IF NOT EXIST %PYTHONHOME%\Scripts\pyinstaller.exe (
  ECHO .
  ECHO Could not locate pyinstaller in %PYTHONHOME%\Scripts.
  ECHO Please modify this script or install PyInstaller [www.pyinstaller.org]
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

REM ----- Clean up

call win\clean.bat

REM ----- Build

REM Arno: When adding files here, make sure tribler.nsi actually
REM packs them in the installer .EXE

%PYTHONHOME%\Scripts\pyinstaller.exe tribler.spec

copy Tribler\Main\Build\Win\tribler*.nsi dist\tribler

REM Martijn 2016-11-05: causing problems with PyInstaller
REM copy Tribler\Main\Build\Win\tribler.exe.manifest dist\tribler

type Tribler\LICENSE Tribler\binary-LICENSE-postfix.txt > Tribler\binary-LICENSE.txt
copy Tribler\binary-LICENSE.txt dist\tribler

mkdir dist\tribler\tools
copy win\tools\reset*.bat dist\tribler\tools

REM Laurens, 2016-04-20: Copy the redistributables of 2008, 2012 and 2015 and the VLC installer to the install dir
REM Sandip, 2019-10-24: redistributables 2008, 2012 are not necessary anymore
REM copy C:\build\vc_redist_110.exe dist\tribler
copy C:\build\vc_redist_140.exe dist\tribler

REM Copy various libraries required on runtime (libsodium and openssl)
copy C:\build\libsodium.dll dist\tribler
REM Sandip, 2019-10-24: No need to copy openssl dlls separately
REM copy C:\build\openssl\*.dll dist\tribler

REM Copy missing dll files
copy C:\build\missing_dlls\*.dll dist\tribler

REM Copy VLC, different files based on 32-bit or 64-bit
mkdir dist\tribler\VLC
xcopy C:\build\vlc dist\tribler\VLC /s /e
REM Make sure that there are no conflicting VLC DLLs in the Tribler root directory
IF EXIST dist\tribler\libvlc.dll DEL /F dist\tribler\libvlc.dll
IF EXIST dist\tribler\libvlccore.dll DEL /F dist\tribler\libvlccore.dll


@echo Running NSIS
cd dist\tribler

REM get password for swarmplayerprivatekey.pfx
set /p PASSWORD="Enter the PFX password:"

REM Arno: Sign Tribler.exe so MS "Block / Unblock" dialog has publisher info.
REM --- Doing this in ugly way for now

signtool.exe sign /f C:\build\certs\certificate.pfx /p "%PASSWORD%" /d "Tribler" /t "http://timestamp.digicert.com" tribler.exe

:makeinstaller
%NSIS% tribler.nsi
move Tribler_*.exe ..
cd ..
REM Arno: Sign installer
signtool.exe sign /f c:\build\certs\certificate.pfx /p "%PASSWORD%" /d "Tribler" /t "http://timestamp.digicert.com" Tribler_*.exe
cd ..
