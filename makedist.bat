REM @echo off
REM No LIBRARYNAME here as this is not distributed with Tribler as BaseLib

set PYTHONHOME=c:\Python271
REM Arno: Add . to find our core
set PYTHONPATH=.;%PYTHONHOME%
echo PYTHONPATH SET TO %PYTHONPATH%

set NSIS="\Program Files\NSIS\makensis.exe"

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

REM Arno, 2011-02-22: Python 2.7 requires Microsoft.VC90.CRT version 9.0.21022.8
REM   http://www.py2exe.org/index.cgi/Tutorial
REM This version is available in the vcredist_x86.exe for Visual Studio 2008 (NOT SP1)
REM  http://www.microsoft.com/downloads/en/details.aspx?FamilyID=9b2da534-3e03-4391-8a4d-074b9f2bc1bf&displaylang=en
REM Date published: 29-11-2007
REM Joyfully the paths for this CRT are different on XP and Win7 and the WinSxS
REM dir appears to be special when using wildcards....

IF EXIST C:\WINDOWS\WinSxS\x86_Microsoft.VC90.CRT_1fc8b3b9a1e18e3b_9.0.21022.8_x-ww_d08d0375 (
set CRTFULLNAME=x86_Microsoft.VC90.CRT_1fc8b3b9a1e18e3b_9.0.21022.8_x-ww_d08d0375
) ELSE (
set CRTFULLNAME=x86_microsoft.vc90.crt_1fc8b3b9a1e18e3b_9.0.21022.8_none_bcb86ed6ac711f91
) 

xcopy C:\WINDOWS\WinSxS\%CRTFULLNAME% dist\installdir\Microsoft.VC90.CRT /S /I
copy C:\WINDOWS\WinSxS\Manifests\%CRTFULLNAME%.manifest dist\installdir\Microsoft.VC90.CRT\Microsoft.VC90.CRT.manifest

REM Arno: py2exe for Python 2.7 needs msvcp90.dll to be in topdir
copy C:\WINDOWS\WinSxS\%CRTFULLNAME%\msvcp90.dll .


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

type Tribler\LICENSE.txt Tribler\binary-LICENSE-postfix.txt > Tribler\binary-LICENSE.txt
copy Tribler\binary-LICENSE.txt dist\installdir
mkdir dist\installdir\Tribler
copy Tribler\schema_sdb_v*.sql dist\installdir\Tribler
mkdir dist\installdir\Tribler\Core
copy Tribler\Core\superpeer.txt dist\installdir\Tribler\Core
mkdir dist\installdir\Tribler\Core\Statistics
copy Tribler\Core\Statistics\*.txt dist\installdir\Tribler\Core\Statistics
copy Tribler\Core\Statistics\*.sql dist\installdir\Tribler\Core\Statistics
mkdir dist\installdir\Tribler\Core\Tag
copy Tribler\Core\Tag\*.filter dist\installdir\Tribler\Core\Tag

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
copy vlc.py dist\installdir\vlc.py

copy reset*.bat dist\installdir

REM MainClient specific

mkdir dist\installdir\Tribler\Main
mkdir dist\installdir\Tribler\Main\vwxGUI
mkdir dist\installdir\Tribler\Main\vwxGUI\images
mkdir dist\installdir\Tribler\Main\webUI
mkdir dist\installdir\Tribler\Main\webUI\static
copy Tribler\Main\vwxGUI\*.xrc dist\installdir\Tribler\Main\vwxGUI
copy Tribler\Main\vwxGUI\images\*.* dist\installdir\Tribler\Main\vwxGUI\images
copy Tribler\Main\webUI\static\*.* dist\installdir\Tribler\Main\webUI\static
mkdir dist\installdir\Tribler\Category
copy Tribler\Category\category.conf dist\installdir\Tribler\Category
copy Tribler\Category\filter_terms.filter dist\installdir\Tribler\Category

cd dist\installdir

REM Arno: Sign .EXE so MS "Block / Unblock" dialog has publisher info.
"C:\Program Files\Microsoft Platform SDK for Windows Server 2003 R2\Bin\signtool.exe" sign /f c:\build\certs\swarmplayerprivatekey.pfx /p "" /d "Tribler" /du "http://www.pds.ewi.tudelft.nl/code.html" /t "http://timestamp.verisign.com/scripts/timestamp.dll" tribler.exe

:makeinstaller
%NSIS% tribler.nsi
move Tribler_*.exe ..
cd ..
REM Arno: Sign installer
"C:\Program Files\Microsoft Platform SDK for Windows Server 2003 R2\Bin\signtool.exe" sign /f c:\build\certs\swarmplayerprivatekey.pfx /p "" /d "Tribler" /du "http://www.pds.ewi.tudelft.nl/code.html" /t "http://timestamp.verisign.com/scripts/timestamp.dll" Tribler_*.exe
cd ..
