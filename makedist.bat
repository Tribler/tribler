REM @echo off
REM No LIBRARYNAME here as this is not distributed with Tribler as BaseLib

set PYTHONHOME=C:\Python252
REM Arno: Add .. to make it find khashmir. Add . to find our core (py 2.5)
set PYTHONPATH=.;%PYTHONHOME%;..

echo PYTHONPATH SET TO %PYTHONPATH%

set NSIS="C:\Program Files\NSIS\makensis.exe"
set IMGCFG="C:\Program Files\Imagecfg\imagecfg.exe"

REM ----- Check for Python and essential site-packages

IF NOT EXIST %PYTHONHOME%\python.exe (
  echo .
  echo Could not locate Python in %PYTHONHOME%.
  echo Please modify this script or install python [www.python.org]
  exit /b
)

IF NOT EXIST %PYTHONHOME%\Lib\site-packages\wx-*-unicode (
  echo .
  echo Could not locate wxPython in %PYTHONHOME%\Lib\site-packages.
  echo Please modify this script or install wxPython [www.wxpython.org]
  exit /b
)

IF NOT EXIST %PYTHONHOME%\Lib\site-packages\py2exe (
  echo .
  echo Could not locate py2exe in %PYTHONHOME%\Lib\site-packages.
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

mkdir dist\installdir

%PYTHONHOME%\python.exe -O Tribler\Main\Build\Win32\setuptribler.py py2exe

REM Arno: Move py2exe results to installdir
move dist\*.* dist\installdir

copy Tribler\Main\Build\Win32\tribler.nsi dist\installdir
copy Tribler\Main\Build\Win32\tribler.exe.manifest dist\installdir
REM copy %PYTHONHOME%\msvcr71.dll dist\installdir
REM For Vista. This works only when building on XP
REM as Vista doesn't have this DLL by default.
REM JD: My XP SP2 doesn't have it. It /is/ shipped with wxPython though
copy %PYTHONHOME%\Lib\site-packages\wx-2.8-msw-unicode\wx\msvcp71.dll dist\installdir
copy %SystemRoot%\msvcp71.dll dist\installdir
copy %PYTHONHOME%\msvcp60.dll dist\installdir
REM py2exe does this: copy SSLEAY32.dll dist\installdir
REM copy LIBEAY32.dll dist\installdir

copy Tribler\binary-LICENSE.txt dist\installdir
mkdir dist\installdir\Tribler
copy Tribler\tribler_sdb_v*.sql dist\installdir\Tribler
mkdir dist\installdir\Tribler\Core
copy Tribler\Core\superpeer.txt dist\installdir\Tribler\Core
mkdir dist\installdir\Tribler\Core\Statistics
copy Tribler\Core\Statistics\*.txt dist\installdir\Tribler\Core\Statistics
copy Tribler\Core\Statistics\*.sql dist\installdir\Tribler\Core\Statistics
mkdir dist\installdir\Tribler\Images
copy Tribler\Images\*.* dist\installdir\Tribler\Images
copy Tribler\Main\Build\Win32\heading.bmp dist\installdir
mkdir dist\installdir\Tribler\Video
mkdir dist\installdir\Tribler\Video\Images
copy Tribler\Video\Images\*.* dist\installdir\Tribler\Video\Images
mkdir dist\installdir\Tribler\Lang
copy Tribler\Lang\*.lang dist\installdir\Tribler\Lang

copy ffmpeg.exe dist\installdir
xcopy vlc dist\installdir\vlc /E /I

copy reset*.bat dist\installdir

REM MainClient specific

mkdir dist\installdir\Tribler\Main
mkdir dist\installdir\Tribler\Main\vwxGUI
mkdir dist\installdir\Tribler\Main\vwxGUI\images
mkdir dist\installdir\Tribler\Main\vwxGUI\images\5.0
copy Tribler\Main\vwxGUI\*.xrc dist\installdir\Tribler\Main\vwxGUI
copy Tribler\Main\vwxGUI\images\*.* dist\installdir\Tribler\Main\vwxGUI\images
copy Tribler\Main\vwxGUI\images\5.0\*.* dist\installdir\Tribler\Main\vwxGUI\images\5.0
mkdir dist\installdir\Tribler\Category
copy Tribler\Category\category.conf dist\installdir\Tribler\Category
copy Tribler\Category\filter_terms.filter dist\installdir\Tribler\Category

cd dist\installdir

:makeinstaller
%NSIS% tribler.nsi
move Tribler_*.exe ..
cd ..
cd ..
