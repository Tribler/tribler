!define PRODUCT "SwarmPlayer"
!define VERSION "2.0.0"
!define BG "bgprocess"


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
;   !define MUI_FINISHPAGE_RUN "$INSTDIR\swarmplayer.exe"

!insertmacro MUI_PAGE_INSTFILES

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
LangString DESC_SecStart ${LANG_ENGLISH} "Create Start Menu Shortcuts"

;--------------------------------
;Installer Sections

Section "!Main EXE" SecMain
 SectionIn RO
 SetOutPath "$INSTDIR"
 File *.txt
  ; TODO : add checkbox for IE and Fx
 File activex\axvlc.dll
 File activex\axvlc.dll.manifest
 File *.dll
 File *.dll.manifest
 
 File /r bgprocess

 File /r plugins
 File /r locale
 ; Arno, 2010-08-10: Appears to work without.
 ;File /r osdmenu
 ;File /r http

 WriteRegStr HKLM "Software\${PRODUCT}" "BGProcessPath" "$INSTDIR\bgprocess\SwarmEngine.exe"
 WriteRegStr HKLM "Software\${PRODUCT}" "InstallDir" "$INSTDIR"
 
 ; Register IE Plug-in
 RegDLL "$INSTDIR\axvlc.dll"

; Vista Registration
  ; Vista detection
  ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows NT\CurrentVersion" CurrentVersion
  StrCpy $R1 $R0 3
  StrCmp $R1 '6.0' lbl_vista lbl_done

  ; TODO : look at that
  lbl_vista:
  WriteRegStr HKLM "Software\RegisteredApplications" "${PRODUCT}" "Software\Clients\Media\${PRODUCT}\Capabilities"
  WriteRegStr HKLM "Software\Clients\Media\${PRODUCT}\Capabilities" "ApplicationName" "${PRODUCT} media player"
  WriteRegStr HKLM "Software\Clients\Media\${PRODUCT}\Capabilities" "ApplicationDescription" "${PRODUCT} - Torrent videostreaming browser plugin"

  lbl_done:

 WriteRegStr HKEY_LOCAL_MACHINE "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayName" "${PRODUCT} (remove only)"
 WriteRegStr HKEY_LOCAL_MACHINE "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString" "$INSTDIR\Uninstall.exe"

; Now writing to KHEY_LOCAL_MACHINE only -- remove references to uninstall from current user
 DeleteRegKey HKEY_CURRENT_USER "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}"
; Remove old error log if present
 Delete "$INSTDIR\swarmplayer.exe.log"

 WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Add an application to the firewall exception list - All Networks - All IP Version - Enabled
  SimpleFC::AddApplication "SwarmEngine" "$INSTDIR\bgprocess\SwarmEngine.exe" 0 2 "" 1

  ; Pop $0 ; return error(1)/success(0)


SectionEnd

Section "Startmenu Icons" SecStart
   CreateDirectory "$SMPROGRAMS\${PRODUCT}"
   CreateShortCut "$SMPROGRAMS\${PRODUCT}\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
SectionEnd


;--------------------------------
;Descriptions

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
!insertmacro MUI_DESCRIPTION_TEXT ${SecStart} $(DESC_SecStart)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section

Section "Uninstall"

 UnRegDLL "$INSTDIR\axvlc.dll"
 RMDir /r "$INSTDIR"

 DeleteRegKey HKEY_LOCAL_MACHINE "Software\Clients\Media\${PRODUCT}"
 DeleteRegKey HKEY_LOCAL_MACHINE "SOFTWARE\${PRODUCT}"
 DeleteRegKey HKEY_LOCAL_MACHINE "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}"

 ; Remove an application from the firewall exception list
 SimpleFC::RemoveApplication "$INSTDIR\bgprocess\SwarmEngine.exe"

 ; Pop $0 ; return error(1)/success(0)

SectionEnd


;--------------------------------
;Functions Section

Function .onInit
  System::Call 'kernel32::CreateMutexA(i 0, i 0, t "SwarmPlayer") i .r1 ?e' 

  Pop $R0 

  StrCmp $R0 0 +3 

  MessageBox MB_OK "The installer is already running."

  Abort 
FunctionEnd
