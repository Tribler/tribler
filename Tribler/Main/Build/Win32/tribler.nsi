!define PRODUCT "Tribler"
!define VERSION "__GIT__"

!include "MUI.nsh"
!include "UAC.nsh"
!include "FileFunc.nsh"

; In order to use the UAC plugin we are required to set RequestExecutionLevel to user.
RequestExecutionLevel user

;--------------------------------
;Configuration

;General
Name "${PRODUCT} ${VERSION}"
OutFile "${PRODUCT}_${VERSION}.exe"

;Folder selection page
InstallDir "$PROGRAMFILES\${PRODUCT}"

;Remember install folder
InstallDirRegKey HKCU "Software\${PRODUCT}" ""

;
; Uncomment for smaller file size
;
SetCompressor "lzma"
;
; Uncomment for quick built time
;
;SetCompress "off"

CompletedText "Installation completed. Thank you for choosing ${PRODUCT}"

BrandingText "${PRODUCT}"

;--------------------------------
;Modern UI Configuration

!define MUI_ICON "Tribler\Main\vwxGUI\images\tribler.ico"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_ABORTWARNING

;--------------------------------
;Pages

!define MUI_LICENSEPAGE_RADIOBUTTONS
!define MUI_LICENSEPAGE_RADIOBUTTONS_TEXT_ACCEPT "I accept"
!define MUI_LICENSEPAGE_RADIOBUTTONS_TEXT_DECLINE "I decline"

; Arno, 2010-02-09: On Vista+Win7 the default value for RequestExecutionLevel
; is auto, so this installer will be run as Administrator. Hence also the
; Tribler.exe that is launched by FINISHPAGE_RUN will be launched as that user.
; This is not what we want. We do want an admin-level install, in particular
; for configuring the Windows firewall automatically. Alternative is the
; UAC plugin (http://nsis.sourceforge.net/UAC_plug-in) but that's still beta.
; Bouman, 2012-04-13: Now using the UAC plugin.
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION PageFinishRun

!insertmacro MUI_PAGE_LICENSE "binary-LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

;!insertmacro MUI_DEFAULT UMUI_HEADERIMAGE_BMP heading.bmp"

;--------------------------------
;Languages

!insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Language Strings

;Description
LangString DESC_SecMain ${LANG_ENGLISH} "Install ${PRODUCT}"
LangString DESC_SecDesk ${LANG_ENGLISH} "Create Desktop Shortcuts"
LangString DESC_SecStart ${LANG_ENGLISH} "Create Start Menu Shortcuts"
LangString DESC_SecDefaultTorrent ${LANG_ENGLISH} "Associate .torrent files with ${PRODUCT}"
LangString DESC_SecDefaultTStream ${LANG_ENGLISH} "Associate .tstream files with ${PRODUCT}"
LangString DESC_SecDefaultMagnet ${LANG_ENGLISH} "Associate magnet links with ${PRODUCT}"
LangString DESC_SecDefaultPpsp ${LANG_ENGLISH} "Associate ppsp links with ${PRODUCT}"

;--------------------------------
;Installer Sections

Section "!Main EXE" SecMain
 SectionIn RO

 ; Boudewijn, need to remove stuff from previously installed version
 RMDir /r "$INSTDIR"

 ; Install Tribler stuff
 SetOutPath "$INSTDIR"
 File /r Microsoft.VC90.CRT
 File /r *
 File *.txt
 ; Arno: Appears to be for CRT v6?
 ; File tribler.exe.manifest
 File logger.conf
 File tribler.exe
 File ffmpeg.exe
 File /r vlc
 File tools\*.bat
 Delete "$INSTDIR\*.pyd"
 File *.pyd
 Delete "$INSTDIR\python*.dll"
 Delete "$INSTDIR\wx*.dll"
 File *.dll
 File anon_test.torrent
 CreateDirectory "$INSTDIR\Tribler"
 SetOutPath "$INSTDIR\Tribler"
 File Tribler\*.sql
 CreateDirectory "$INSTDIR\Tribler\Core"

  ; Main client specific
 CreateDirectory "$INSTDIR\Tribler"
 CreateDirectory "$INSTDIR\Tribler\Main\vwxGUI"
 CreateDirectory "$INSTDIR\Tribler\Main\vwxGUI\images"
 CreateDirectory "$INSTDIR\Tribler\Main\vwxGUI\images\default"
 CreateDirectory "$INSTDIR\Tribler\Main\vwxGUI\images\flags"
 SetOutPath "$INSTDIR\Tribler\Main\vwxGUI\images"
 File Tribler\Main\vwxGUI\images\*
 SetOutPath "$INSTDIR\Tribler\Main\vwxGUI\images\default"
 File Tribler\Main\vwxGUI\images\default\*
 SetOutPath "$INSTDIR\Tribler\Main\vwxGUI\images\flags"
 File Tribler\Main\vwxGUI\images\flags\*

 CreateDirectory "$INSTDIR\Tribler\Main\webUI"
 CreateDirectory "$INSTDIR\Tribler\Main\webUI\static"
 CreateDirectory "$INSTDIR\Tribler\Main\webUI\static\images"
 CreateDirectory "$INSTDIR\Tribler\Main\webUI\static\lang"
 SetOutPath "$INSTDIR\Tribler\Main\webUI\static"
 File Tribler\Main\webUI\static\*.*
 SetOutPath "$INSTDIR\Tribler\Main\webUI\static\images"
 File Tribler\Main\webUI\static\images\*.*
 SetOutPath "$INSTDIR\Tribler\Main\webUI\static\lang"
 File Tribler\Main\webUI\static\lang\*.*

 ; Categories
 CreateDirectory "$INSTDIR\Tribler\Category"
 SetOutPath "$INSTDIR\Tribler\Category"
 File Tribler\Category\*.conf
 File Tribler\Category\*.filter

 ; Arno, 2012-05-25: data files for pymdht
 CreateDirectory "$INSTDIR\Tribler\Core\DecentralizedTracking"
 CreateDirectory "$INSTDIR\Tribler\Core\DecentralizedTracking\pymdht"
 CreateDirectory "$INSTDIR\Tribler\Core\DecentralizedTracking\pymdht\core"
 SetOutPath "$INSTDIR\Tribler\Core\DecentralizedTracking\pymdht\core"
 File Tribler\Core\DecentralizedTracking\pymdht\core\bootstrap_stable
 File Tribler\Core\DecentralizedTracking\pymdht\core\bootstrap_unstable

 ; For python-cryptography
 CreateDirectory "$INSTDIR\cryptography\hazmat\primitives\src"
 SetOutPath "$INSTDIR\cryptography\hazmat\primitives\src"
 File C:\Python27\x86\Lib\site-packages\cryptography-0.7.2-py2.7-win32.egg\cryptography\hazmat\primitives\src\constant_time.c
 File C:\Python27\x86\Lib\site-packages\cryptography-0.7.2-py2.7-win32.egg\cryptography\hazmat\primitives\src\constant_time.h

 ; End
 SetOutPath "$INSTDIR"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayName" "${PRODUCT}"
 WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "NoModify" 1
 WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "NoRepair" 1
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString" "$INSTDIR\Uninstall.exe"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "InstallLocation" "$INSTDIR"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayVersion" '${VERSION}'
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayIcon" "$INSTDIR\${PRODUCT}.exe,0"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "Publisher" "The Tribler Team"
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "HelpLink" 'http://forum.tribler.org'
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "URLInfoAbout" 'http://www.tribler.org'
 WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "URLUpdateInfo" 'http://www.tribler.org/trac/wiki/Download'
 ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
 IntFmt $0 "0x%08X" $0
 WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "EstimatedSize" "$0"

 ; Now writing to KHEY_LOCAL_MACHINE only -- remove references to uninstall from current user
 DeleteRegKey HKEY_CURRENT_USER "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}"
 ; Remove old error log if present
 Delete "$INSTDIR\tribler.exe.log"

 WriteUninstaller "$INSTDIR\Uninstall.exe"

 ; Add an application to the firewall exception list - All Networks - All IP Version - Enabled
 SimpleFC::AddApplication "Tribler" "$INSTDIR\${PRODUCT}.exe" 0 2 "" 1
 ; Pop $0 ; return error(1)/success(0)

SectionEnd


Section "Desktop Icons" SecDesk
   CreateShortCut "$DESKTOP\${PRODUCT}.lnk" "$INSTDIR\${PRODUCT}.exe" ""
SectionEnd


Section "Startmenu Icons" SecStart
   CreateDirectory "$SMPROGRAMS\${PRODUCT}"
   CreateShortCut "$SMPROGRAMS\${PRODUCT}\Uninstall ${PRODUCT}.lnk" "$INSTDIR\Uninstall.exe"
   CreateShortCut "$SMPROGRAMS\${PRODUCT}\${PRODUCT}.lnk" "$INSTDIR\${PRODUCT}.exe"
SectionEnd


Section "Make Default For .torrent" SecDefaultTorrent
   ; Delete ddeexec key if it exists
   DeleteRegKey HKCR "bittorrent\shell\open\ddeexec"
   WriteRegStr HKCR .torrent "" bittorrent
   WriteRegStr HKCR .torrent "Content Type" application/x-bittorrent
   WriteRegStr HKCR "MIME\Database\Content Type\application/x-bittorrent" Extension .torrent
   WriteRegStr HKCR bittorrent "" "TORRENT File"
   WriteRegBin HKCR bittorrent EditFlags 00000100
   WriteRegStr HKCR "bittorrent\shell" "" open
   WriteRegStr HKCR "bittorrent\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
   WriteRegStr HKCR "bittorrent\DefaultIcon" "" "$INSTDIR\Tribler\Main\vwxGUI\images\torrenticon.ico"
SectionEnd


Section "Make Default For .tstream" SecDefaultTStream
   ; Arno: Poor man's attempt to check if already registered
   ReadRegStr $0 HKCR .tstream ""
   ReadRegStr $1 HKCR "tstream\shell\open\command" ""
   StrCpy $2 $1 -4
   StrCmp $0 "" 0 +2
      return
   MessageBox MB_YESNO ".tstream already registered to $2. Overwrite?" IDYES +2 IDNO 0
      Return
   DetailPrint "Arno registering .tstream: $0 $1 $2"

   ; Register
   WriteRegStr HKCR .tstream "" tstream
   WriteRegStr HKCR .tstream "Content Type" application/x-tribler-stream
   WriteRegStr HKCR "MIME\Database\Content Type\application/x-tribler-stream" Extension .tstream
   WriteRegStr HKCR tstream "" "TSTREAM File"
   WriteRegBin HKCR tstream EditFlags 00000100
   WriteRegStr HKCR "tstream\shell" "" open
   WriteRegStr HKCR "tstream\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
   WriteRegStr HKCR "tstream\DefaultIcon" "" "$INSTDIR\Tribler\Main\vwxGUI\images\torrenticon.ico"
SectionEnd

Section "Make Default For magnet://" SecDefaultMagnet
   WriteRegStr HKCR "magnet" "" "URL: Magnet Link Protocol"
   WriteRegStr HKCR "magnet" "URL Protocol" ""
   WriteRegStr HKCR "magnet\DefaultIcon" "" "$INSTDIR\Tribler\Main\vwxGUI\images\torrenticon.ico"
   WriteRegStr HKCR "magnet\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
   WriteRegStr HKLM "SOFTWARE\Classes\magnet\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
SectionEnd

Section "Make Default For ppsp://" SecDefaultPpsp
   WriteRegStr HKCR "ppsp" "" "URL: Ppsp Link Protocol"
   WriteRegStr HKCR "ppsp" "URL Protocol" ""
   WriteRegStr HKCR "ppsp\DefaultIcon" "" "$INSTDIR\Tribler\Main\vwxGUI\images\torrenticon.ico"
   WriteRegStr HKCR "ppsp\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
   WriteRegStr HKLM "SOFTWARE\Classes\ppsp\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
SectionEnd

;--------------------------------
;Descriptions

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDesk} $(DESC_SecDesk)
!insertmacro MUI_DESCRIPTION_TEXT ${SecStart} $(DESC_SecStart)
;!insertmacro MUI_DESCRIPTION_TEXT ${SecLang} $(DESC_SecLang)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultTorrent} $(DESC_SecDefaultTorrent)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultTStream} $(DESC_SecDefaultTStream)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultMagnet} $(DESC_SecDefaultMagnet)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultPpsp} $(DESC_SecDefaultPpsp)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section

Section "Uninstall"

 RMDir /r "$INSTDIR"

 Delete "$DESKTOP\${PRODUCT}.lnk"

 SetShellVarContext all
 RMDir "$SMPROGRAMS\${PRODUCT}"
 RMDir /r "$SMPROGRAMS\${PRODUCT}"

 DeleteRegKey HKEY_LOCAL_MACHINE "SOFTWARE\${PRODUCT}"
 DeleteRegKey HKEY_LOCAL_MACHINE "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}"

 ; Remove an application from the firewall exception list
 SimpleFC::RemoveApplication "$INSTDIR\${PRODUCT}.exe"
 ; Pop $0 ; return error(1)/success(0)

SectionEnd

;--------------------------------
;Macros and Functions Section


!macro Init thing
uac_tryagain:
!insertmacro UAC_RunElevated
${Switch} $0
${Case} 0
	${IfThen} $1 = 1 ${|} Quit ${|} ;we are the outer process, the inner process has done its work, we are done
	${IfThen} $3 <> 0 ${|} ${Break} ${|} ;we are admin, let the show go on
	${If} $1 = 3 ;RunAs completed successfully, but with a non-admin user
		MessageBox mb_YesNo|mb_IconExclamation|mb_TopMost|mb_SetForeground "This ${thing} requires admin privileges, try again" /SD IDNO IDYES uac_tryagain IDNO 0
	${EndIf}
	;fall-through and die
${Case} 1223
	Quit
${Case} 1062
	MessageBox mb_IconStop|mb_TopMost|mb_SetForeground "Logon service not running."
	Quit
${Default}
	MessageBox mb_IconStop|mb_TopMost|mb_SetForeground "Unable to elevate , error $0"
	Quit
${EndSwitch}

SetShellVarContext all
!macroend


Function .onInit
  !insertmacro Init "installer"

  System::Call 'kernel32::CreateMutexA(i 0, i 0, t "Tribler") i .r1 ?e'

  Pop $R0

  StrCmp $R0 0 +3

  MessageBox MB_OK "The installer is already running."

  Abort

  ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString"
  StrCmp $R0 "" done
  IfFileExists $R0 +1 done

  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "${PRODUCT} is already installed. $\n$\nClick `OK` to remove the previous version or `Cancel` to cancel this upgrade." /SD IDOK IDOK uninst
  Abort

  uninst:
    ClearErrors
    ExecWait '$R0 _?=$INSTDIR' ;Do not copy the uninstaller to a temp file
    ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString"
    StrCmp $R0 "" done
    Abort
  done:

FunctionEnd


Function un.onInit
  !insertmacro Init "uninstaller"
FunctionEnd


Function PageFinishRun
  !insertmacro UAC_AsUser_ExecShell "" "$INSTDIR\tribler.exe" "" "" ""
FunctionEnd
