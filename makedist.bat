call clean.bat

set PYTHONPATH="C:\Python24"
set NSIS="C:\Program Files\NSIS\makensis.exe"
set IMGCFG="C:\Program Files\Imagecfg\imagecfg.exe"

%PYTHONPATH%\python.exe -OO setupabc.py py2exe
copy %PYTHONPATH%\msvcp71.dll dist\abc
copy %PYTHONPATH%\msvcr71.dll dist\abc
mkdir dist\abc\torrent
mkdir dist\abc\icons
copy icons\*.bmp dist\abc\icons
mkdir dist\abc\lang
copy lang\*.lang dist\abc\lang
cd dist
move *.* abc
cd abc

rem if exist %IMGCFG% goto imageconfig
rem goto makeinstaller
rem :imageconfig
rem %IMGCFG% -u abc.exe
rem %IMGCFG% -a 0x1 abc.exe

:makeinstaller
%NSIS% abc.nsi
move ABC-win32-v*.exe ..
cd ..
cd ..