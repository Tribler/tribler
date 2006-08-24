call clean.bat

set PYTHONPATH="C:\Python24"
set NSIS="C:\Program Files\NSIS\makensis.exe"
set IMGCFG="C:\Program Files\Imagecfg\imagecfg.exe"

%PYTHONPATH%\python.exe -O setuptribler.py py2exe
REM copy %PYTHONPATH%\msvcr71.dll dist\tribler
REM copy %PYTHONPATH%\msvcp71.dll dist\tribler
copy %PYTHONPATH%\msvcp60.dll dist\tribler
copy SSLEAY32.dll dist\tribler
copy LIBEAY32.dll dist\tribler
copy heading.bmp dist\tribler
mkdir dist\tribler\Lang
copy superpeer.txt dist
copy cities.txt dist
copy binary-LICENSE.txt dist
mkdir dist\tribler\icons
copy icons\*.bmp dist\tribler\icons
mkdir dist\tribler\icons\mugshots
copy icons\mugshots\*.bmp dist\tribler\icons\mugshots
copy icons\*.jpg dist\tribler\icons
copy Lang\*.lang dist\tribler\Lang
cd dist
move abc.exe tribler.exe
move *.* tribler
cd tribler

rem if exist %IMGCFG% goto imageconfig
rem goto makeinstaller
rem :imageconfig
rem %IMGCFG% -u tribler.exe
rem %IMGCFG% -a 0x1 tribler.exe

:makeinstaller
%NSIS% tribler.nsi
move Tribler_*.exe ..
cd ..
cd ..
