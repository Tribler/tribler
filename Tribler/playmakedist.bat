@echo off

set PYTHONPATH="C:\Python243wx2801"
set NSIS="C:\Program Files\NSIS\makensis.exe"
set IMGCFG="C:\Program Files\Imagecfg\imagecfg.exe"

REM ----- Check for Python and essential site-packages

IF NOT EXIST %PYTHONPATH%\python.exe (
  echo .
  echo Could not locate Python in %PYTHONPATH%.
  echo Please modify this script or install python [www.python.org]
  exit /b
)

IF NOT EXIST %PYTHONPATH%\Lib\site-packages\wx-*-unicode (
  echo .
  echo Could not locate wxPython in %PYTHONPATH%\Lib\site-packages.
  echo Please modify this script or install wxPython [www.wxpython.org]
  exit /b
)

IF NOT EXIST %PYTHONPATH%\Lib\site-packages\py2exe (
  echo .
  echo Could not locate py2exe in %PYTHONPATH%\Lib\site-packages.
  echo Please modify this script or install wxPython [www.py2exe.org]
  exit /b
)

REM ----- Check for NSIS installer

IF NOT EXIST %NSIS% (
  echo .
  echo Could not locate the NSIS installer at %NSIS%.
  echo Please modify this script or install NSIS [nsis.sf.net]
  exit /b
)

REM ----- Clean up

call clean.bat

REM ----- Build

REM Arno: When adding files here, make sure tribler.nsi actually
REM packs them in the installer .EXE

%PYTHONPATH%\python.exe -O setuptriblerplay.py py2exe

REM copy %PYTHONPATH%\msvcr71.dll dist\tribler
REM For Vista. This works only when building on XP
REM as Vista doesn't have this DLL by default.
REM JD: My XP SP2 doesn't have it. It /is/ shipped with wxPython though
copy %PYTHONPATH%\Lib\site-packages\wx-2.8-msw-unicode\wx\msvcp71.dll dist\tribler
copy %SystemRoot%\msvcp71.dll dist\tribler
copy %PYTHONPATH%\msvcp60.dll dist\tribler
copy SSLEAY32.dll dist\tribler
copy LIBEAY32.dll dist\tribler
copy heading.bmp dist\tribler
mkdir dist\tribler\Lang
copy superpeer.txt dist
copy cities.txt dist
copy FAQ.txt dist
copy category.conf dist
copy binary-LICENSE.txt dist
mkdir dist\tribler\icons
copy icons\*.* dist\tribler\icons
mkdir dist\tribler\icons\mugshots
copy icons\mugshots\*.* dist\tribler\icons\mugshots
copy Lang\*.lang dist\tribler\Lang
copy ffmpeg.exe dist\tribler
copy tor.exe dist\tribler
xcopy vlc dist\tribler\vlc /E /I

mkdir dist\tribler\Tribler
mkdir dist\tribler\Tribler\vwxGUI
mkdir dist\tribler\Tribler\vwxGUI\images
copy Tribler\vwxGUI\*.xrc dist\tribler\Tribler\vwxGUI
copy Tribler\vwxGUI\images\*.* dist\tribler\Tribler\vwxGUI\images

cd dist
move *.* tribler
cd tribler

rem if exist %IMGCFG% goto imageconfig
rem goto makeinstaller
rem :imageconfig
rem %IMGCFG% -u tribler.exe
rem %IMGCFG% -a 0x1 tribler.exe

:makeinstaller
%NSIS% triblerplay.nsi
move p2player_*.exe ..
cd ..
cd ..
