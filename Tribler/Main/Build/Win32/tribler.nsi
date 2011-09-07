!define PRODUCT "Tribler"
!define VERSION "5.4.3"

!include "MUI.nsh"

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

!define MUI_ABORTWARNING
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "heading.bmp"

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
;    !define MUI_FINISHPAGE_RUN "$INSTDIR\tribler.exe"

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

;--------------------------------
;Installer Sections

Section "!Main EXE" SecMain
 SectionIn RO

 ; Boudewijn, need to remove stuff from previously installed version
 RMDir /r "$INSTDIR"

 ; Install Tribler stuff
 SetOutPath "$INSTDIR"
 File /r Microsoft.VC90.CRT
 File *.txt
 ; Arno: Appears to be for CRT v6?
 ; File tribler.exe.manifest
 File tribler.exe
 File ffmpeg.exe
 File /r vlc
 File *.bat
 Delete "$INSTDIR\*.pyd"
 File *.pyd
 Delete "$INSTDIR\python*.dll"
 Delete "$INSTDIR\wx*.dll"
 File *.dll
 Delete "$INSTDIR\*.zip"
 File *.zip
 CreateDirectory "$INSTDIR\Tribler"
 SetOutPath "$INSTDIR\Tribler"
 File Tribler\*.sql
 CreateDirectory "$INSTDIR\Tribler\Core"
 SetOutPath "$INSTDIR\Tribler\Core"
 File Tribler\Core\*.txt
 CreateDirectory "$INSTDIR\Tribler\Core\Statistics"
 SetOutPath "$INSTDIR\Tribler\Core\Statistics"
 File Tribler\Core\Statistics\*.txt
 File Tribler\Core\Statistics\*.sql
 CreateDirectory "$INSTDIR\Tribler\Core\Tag"
 SetOutPath "$INSTDIR\Tribler\Core\Tag"
 File Tribler\Core\Tag\*.filter
 CreateDirectory "$INSTDIR\Tribler\Images"
 SetOutPath "$INSTDIR\Tribler\Images"
 File Tribler\Images\*.*
 CreateDirectory "$INSTDIR\Tribler\Video"
 CreateDirectory "$INSTDIR\Tribler\Video\Images"
 SetOutPath "$INSTDIR\Tribler\Video\Images"
 File Tribler\Video\Images\*.*
 CreateDirectory "$INSTDIR\Tribler\Lang"
 SetOutPath "$INSTDIR\Tribler\Lang"
 IfFileExists user.lang userlang
 File Tribler\Lang\*.*
 userlang:
 File /x user.lang Tribler\Lang\*.*
  ; Main client specific
 CreateDirectory "$INSTDIR\Tribler"
 CreateDirectory "$INSTDIR\Tribler\Main\vwxGUI"
 CreateDirectory "$INSTDIR\Tribler\Main\vwxGUI\images"
 SetOutPath "$INSTDIR\Tribler\Main\vwxGUI"
 File Tribler\Main\vwxGUI\*.*
 SetOutPath "$INSTDIR\Tribler\Main\vwxGUI\images"
 File Tribler\Main\vwxGUI\images\*.*
 ; Categories
 CreateDirectory "$INSTDIR\Tribler\Category"
 SetOutPath "$INSTDIR\Tribler\Category"
 File Tribler\Category\*.conf
 File Tribler\Category\*.filter
 ; End
 SetOutPath "$INSTDIR"
 WriteRegStr HKEY_LOCAL_MACHINE "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayName" "${PRODUCT} (remove only)"
 WriteRegStr HKEY_LOCAL_MACHINE "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString" "$INSTDIR\Uninstall.exe"

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
   CreateShortCut "$SMPROGRAMS\${PRODUCT}\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
   CreateShortCut "$SMPROGRAMS\${PRODUCT}\${PRODUCT}.lnk" "$INSTDIR\${PRODUCT}.exe" "" "$INSTDIR\${PRODUCT}.exe" 0
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
   WriteRegStr HKCR "bittorrent\DefaultIcon" "" "$INSTDIR\Tribler\Images\torrenticon.ico"
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
   WriteRegStr HKCR "tstream\DefaultIcon" "" "$INSTDIR\Tribler\Images\SwarmPlayerIcon.ico"
SectionEnd

Section "Make Default For magnet://" SecDefaultMagnet
   WriteRegStr HKCR "magnet" "" "URL: Magnet Link Protocol"
   WriteRegStr HKCR "magnet" "URL Protocol" ""
   WriteRegStr HKCR "magnet\DefaultIcon" "" "$INSTDIR\Tribler\Images\torrenticon.ico"
   WriteRegStr HKCR "magnet\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
   WriteRegStr HKLM "SOFTWARE\Classes\magnet\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
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
;Functions Section

Function .onInit
  System::Call 'kernel32::CreateMutexA(i 0, i 0, t "Tribler") i .r1 ?e' 

  Pop $R0 

  StrCmp $R0 0 +3 

  MessageBox MB_OK "The installer is already running."

  Abort 
FunctionEnd
