!define PRODUCT "ABC"
!define VERSION "3.0.1b"

!include "MUI.nsh"

;--------------------------------
;Configuration

;General
 Name "ABC [ Yet Another Bittorrent Client ] ${VERSION}"
 OutFile "${PRODUCT}-win32-v${VERSION}.exe"

;Folder selection page
 InstallDir "$PROGRAMFILES\${PRODUCT}"
 
;Remember install folder
 InstallDirRegKey HKCU "Software\${PRODUCT}" ""

 SetCompressor "lzma"

 CompletedText "Install Complete. Thank you for choosing ${PRODUCT}"

 BrandingText "ABC [ Yet Another Bittorrent Client ]"

;--------------------------------
;Modern UI Configuration

 !define MUI_ABORTWARNING
 !define MUI_HEADERIMAGE
 #!define MUI_HEADERIMAGE_BITMAP "${NSISDIR}\Contrib\Icons\modern-header.bmp"

;--------------------------------
;Pages

  !define MUI_LICENSEPAGE_RADIOBUTTONS
  !define MUI_LICENSEPAGE_RADIOBUTTONS_TEXT_ACCEPT "I accept"
  !define MUI_LICENSEPAGE_RADIOBUTTONS_TEXT_DECLINE "I decline"

  !insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
  
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
;Languages

 !insertmacro MUI_LANGUAGE "English"
 
;--------------------------------
;Language Strings

;Description
 LangString DESC_SecMain ${LANG_ENGLISH} "Install ABC"
 LangString DESC_SecDesk ${LANG_ENGLISH} "Create Desktop Shortcuts"
 LangString DESC_SecStart ${LANG_ENGLISH} "Create Start Menu Shortcuts"
 LangString DESC_SecDefault ${LANG_ENGLISH} "Associate .torrent files with ABC"

;--------------------------------
;Installer Sections

Section "!Main EXE" SecMain
 SectionIn RO
 SetOutPath "$INSTDIR"
 IfFileExists announce.lst announcelst 
 File announce.lst
 announcelst:
 File LICENSE.txt
 File *.ico
 File readme.txt
 File abc.exe.manifest
 File ABC.exe
 Delete "$INSTDIR\*.pyd"
 File *.pyd
 Delete "$INSTDIR\python*.dll"
 Delete "$INSTDIR\wx*.dll"
 File *.dll
 Delete "$INSTDIR\*.zip"
 File *.zip
 CreateDirectory "$INSTDIR\torrent"
 CreateDirectory "$INSTDIR\icons"
 SetOutPath "$INSTDIR\icons"
 File icons\*.*
 CreateDirectory "$INSTDIR\lang"
 SetOutPath "$INSTDIR\lang"
 IfFileExists user.lang userlang
 File lang\*.*
 userlang:
 File /x user.lang lang\*.*
 WriteRegStr HKEY_LOCAL_MACHINE "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayName" "${PRODUCT} (remove only)"
 WriteRegStr HKEY_LOCAL_MACHINE "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString" "$INSTDIR\Uninstall.exe"

; Now writing to KHEY_LOCAL_MACHINE only -- remove references to uninstall from current user
 DeleteRegKey HKEY_CURRENT_USER "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}"
; Remove old error log if present
 Delete "$INSTDIR\abc.exe.log"

 WriteUninstaller "$INSTDIR\Uninstall.exe"

SectionEnd

Section "Desktop Icons" SecDesk
   CreateShortCut "$DESKTOP\${PRODUCT}.lnk" "$INSTDIR\${PRODUCT}.exe" ""
SectionEnd

Section "Startmenu Icons" SecStart
   CreateDirectory "$SMPROGRAMS\${PRODUCT}"
   CreateShortCut "$SMPROGRAMS\${PRODUCT}\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
   CreateShortCut "$SMPROGRAMS\${PRODUCT}\${PRODUCT}.lnk" "$INSTDIR\${PRODUCT}.exe" "" "$INSTDIR\${PRODUCT}.exe" 0
SectionEnd

Section "Make Default" SecDefault
   WriteRegStr HKCR .torrent "" bittorrent
   WriteRegStr HKCR .torrent "Content Type" application/x-bittorrent
   WriteRegStr HKCR "MIME\Database\Content Type\application/x-bittorrent" Extension .torrent
   WriteRegStr HKCR bittorrent "" "TORRENT File"
   WriteRegBin HKCR bittorrent EditFlags 00000100
   WriteRegStr HKCR "bittorrent\shell" "" open
   WriteRegStr HKCR "bittorrent\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
   WriteRegStr HKCR "bittorrent" "DefaultIcon" "$INSTDIR\torrenticon.ico"
SectionEnd

;--------------------------------
;Descriptions

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
 !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
 !insertmacro MUI_DESCRIPTION_TEXT ${SecDesk} $(DESC_SecDesk)
 !insertmacro MUI_DESCRIPTION_TEXT ${SecStart} $(DESC_SecStart)
; !insertmacro MUI_DESCRIPTION_TEXT ${SecLang} $(DESC_SecLang)
 !insertmacro MUI_DESCRIPTION_TEXT ${SecDefault} $(DESC_SecDefault)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section

Section "Uninstall"

 Delete "$INSTDIR\torrent\*.*"
 RMDir "$INSTDIR\torrent"

 Delete "$INSTDIR\icons\*.*"
 RMDir "$INSTDIR\icons"

 Delete "$INSTDIR\lang\*.*"
 RMDir "$INSTDIR\lang"

 Delete "$INSTDIR\*.*"
 RMDir "$INSTDIR"

 Delete "$DESKTOP\${PRODUCT}.lnk"
 Delete "$SMPROGRAMS\${PRODUCT}\*.*"
 RmDir  "$SMPROGRAMS\${PRODUCT}"

 DeleteRegKey HKEY_LOCAL_MACHINE "SOFTWARE\${PRODUCT}"
 DeleteRegKey HKEY_LOCAL_MACHINE "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}"

SectionEnd

;--------------------------------
;Functions Section

Function .onInit
  System::Call 'kernel32::CreateMutexA(i 0, i 0, t "ABC") i .r1 ?e' 

  Pop $R0 

  StrCmp $R0 0 +3 

    MessageBox MB_OK "The installer is already running." 

    Abort 
FunctionEnd