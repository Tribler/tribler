REM @echo off
set LIBRARYNAME=Tribler

set PYTHONHOME=\Python254
REM Arno: Add . to find our core (py 2.5)
set PYTHONPATH=.;%PYTHONHOME%
echo PYTHONPATH SET TO %PYTHONPATH%

set XULRUNNER=..\xulrunner-sdk
set ZIP7CMD="\Program Files\7-Zip\7z.exe"

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
  echo Please modify this script or install py2exe [www.py2exe.org]
  exit /b
)

REM ----- Check for XULRUNNER

IF NOT EXIST %XULRUNNER% (
  echo .
  echo Could not locate the XULRUNNER SDK at %XULRUNNER%.
  echo Please modify this script or install from https://developer.mozilla.org/en/XULRunner
  exit /b
)

REM ----- Check for ZIP7CMD

IF NOT EXIST %ZIP7CMD% (
  echo .
  echo Could not locate the 7-Zip at %ZIP7CMD%.
  echo Please modify this script or install from ww.7-zip.org
  exit /b
)


REM ----- Clean up

call clean.bat

REM ----- Build

REM Arno: When adding files here, make sure tribler.nsi actually
REM packs them in the installer .EXE

REM Diego: building the deepest dir we get all of them.
mkdir dist\installdir\bgprocess\%LIBRARYNAME%\Images

%PYTHONHOME%\python.exe -O %LIBRARYNAME%\Transport\Build\Win32\setupBGexe.py py2exe

REM Arno: Move py2exe results to installdir
move dist\*.* dist\installdir\bgprocess
copy %LIBRARYNAME%\Images\SwarmPlayerIcon.ico dist\installdir\bgprocess\%LIBRARYNAME%\Images

REM Riccardo:  move the files needed for the WebUI
xcopy %LIBRARYNAME%\WebUI dist\installdir\bgprocess\%LIBRARYNAME%\WebUI /S /I
del dist\installdir\bgprocess\%LIBRARYNAME%\WebUI\*.py

REM Diego: replace vlc *.txt with P2P-Next License.txt
del dist\installdir\*.txt
type %LIBRARYNAME%\ns-LICENSE.txt %LIBRARYNAME%\binary-LICENSE-postfix.txt > %LIBRARYNAME%\binary-LICENSE.txt
copy %LIBRARYNAME%\binary-LICENSE.txt dist\installdir

copy %PYTHONHOME%\Lib\site-packages\wx-2.8-msw-unicode\wx\msvcp71.dll dist\installdir\bgprocess

copy reset.bat dist\installdir

REM Arno: Move swift binary to installdir
copy swift.exe dist\installdir\bgprocess


REM ----- Build XPI of SwarmTransport
mkdir dist\installdir\components
copy %LIBRARYNAME%\Transport\icon.png dist\installdir
copy %LIBRARYNAME%\Transport\install.rdf dist\installdir
copy %LIBRARYNAME%\Transport\chrome.manifest dist\installdir
xcopy %LIBRARYNAME%\Transport\components dist\installdir\components /S /I
xcopy %LIBRARYNAME%\Transport\chrome dist\installdir\chrome /S /I
xcopy %LIBRARYNAME%\Transport\skin dist\installdir\skin /S /I

REM ----- Turn .idl into .xpt
%XULRUNNER%\bin\xpidl -m typelib -w -v -I %XULRUNNER%\idl -e dist\installdir\components\tribeIChannel.xpt %LIBRARYNAME%\Transport\tribeIChannel.idl
%XULRUNNER%\bin\xpidl -m typelib -w -v -I %XULRUNNER%\idl -e dist\installdir\components\tribeISwarmTransport.xpt %LIBRARYNAME%\Transport\tribeISwarmTransport.idl

cd dist\installdir

REM Arno: Win7 gives popup if SwarmEngine is not signed
"C:\Program Files\Microsoft Platform SDK for Windows Server 2003 R2\Bin\signtool.exe" sign /f c:\build\certs\swarmplayerprivatekey.pfx /p "" /d "SwarmEngine" /du "http://www.pds.ewi.tudelft.nl/code.html" /t "http://timestamp.verisign.com/scripts/timestamp.dll" bgprocess\SwarmEngine.exe

REM ----- Turn installdir into .xpi
%ZIP7CMD% a -tzip "SwarmPlayer.xpi" * -r -mx=9 
move SwarmPlayer.xpi ..
cd ..\..
 

