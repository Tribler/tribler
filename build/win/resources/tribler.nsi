!define PRODUCT "Tribler"
!define BITVERSION "x86"

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "nsProcess.nsh"

; Laurens, 2016-04-06: We are going to possibly touch the C:/ drive (by default we do) and it's restricted areas,
; so we need admin permission to do so (for most devices).
RequestExecutionLevel admin

;--------------------------------
;Configuration

;General
Name "${PRODUCT} ${VERSION}"
OutFile "${PRODUCT}_${VERSION}_${BITVERSION}.exe"

;Folder selection page. 
; Laurens, 2016-03-14: Note that $PROGRAMFILES will be replaced by $PROGRAMFILES64
; if the 64 bit argument is passed to update_version_from_git.py.
InstallDir "$PROGRAMFILES\${PRODUCT}"

; Laurens, 2016-03-15: No silent mode for the installer and uninstaller because 
; this will disbale the init functions being called.
SilentInstall normal
SilentUnInstall normal

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

CompletedText "Installation completed. Thank you for choosing ${PRODUCT}."

BrandingText "${PRODUCT}"

; ----------------------------
; Tribler running check - shared function
!macro RUNMACRO un
  Function ${un}checkrunning
     DetailPrint "Checking if Tribler is not running..."
     checkRunning:
          ${nsProcess::FindProcess} "tribler.exe" $r0
                StrCmp $r0 0 0 notRunning
                MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "${PRODUCT} is running, please close it so the (un)installation can proceed." /SD IDCANCEL IDRETRY checkRunning
                Abort

        notRunning:
  FunctionEnd
!macroend
 
; Insert function as an installer and uninstaller function.
!insertmacro RUNMACRO ""
!insertmacro RUNMACRO "un."

;--------------------------------
;Modern UI Configuration

!define MUI_ICON "..\..\build\win\resources\tribler.ico"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_ABORTWARNING

;--------------------------------
;Pages
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

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
LangString DESC_SecDefaultMagnet ${LANG_ENGLISH} "Associate magnet links with ${PRODUCT}"

;--------------------------------
;Installer Sections

Section "!Main EXE" SecMain
    SectionIn RO
    ; Check if tribler is not running when trying to install because files will be in use when cleaning the isntall dir.
    Call checkrunning

    ; Boudewijn, need to remove stuff from previously installed version
    RMDir /r "$INSTDIR"

    ; Install Tribler stuff
    SetOutPath "$INSTDIR"
    File /r *

    ; Install MSVCR 2008, 2012 and 2015
    SetOutPath "$INSTDIR"

    ; Libraries dependant on 2015 are: Python, Qt5
    File "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Redist\MSVC\v143\vc_redist.${BITVERSION}.exe"
    ExecWait "$INSTDIR\vc_redist.${BITVERSION}.exe /q /norestart"

    FileOpen $9 "$INSTDIR\tribler.exe.log" w
    FileWrite $9 ""
    FileClose $9
    Exec 'icacls "$INSTDIR\tribler.exe.log" /grant *BU:F'
    #AccessControl::GrantOnFile "$INSTDIR\tribler.exe.log" "(BU)" "FullAccess"
    Exec 'icacls "$INSTDIR\tribler.exe.log" /grant *S-1-5-32-545:F'
    #AccessControl::GrantOnFile "$INSTDIR\tribler.exe.log" "(S-1-5-32-545)" "FullAccess"

    ; End
    SetOutPath "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayName" "${PRODUCT}"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "NoRepair" 1
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Tribler" "" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayVersion" '${VERSION}'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "DisplayIcon" "$INSTDIR\${PRODUCT}.exe,0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "Publisher" "The Tribler Team"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "HelpLink" 'https://forum.tribler.org'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "URLInfoAbout" 'https://www.tribler.org'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "URLUpdateInfo" 'https://github.com/tribler/tribler/releases'
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "EstimatedSize" "$0"

    ; Now writing to KHEY_LOCAL_MACHINE only -- remove references to uninstall from current user
    DeleteRegKey HKEY_CURRENT_USER "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}"

    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Add an application to the firewall exception list - All Networks - All IP Version - Enabled
    SimpleFC::AddApplication "Tribler" "$INSTDIR\${PRODUCT}.exe" 0 2 "" 1
SectionEnd


Section "Desktop Icons" SecDesk
    CreateShortCut "$DESKTOP\${PRODUCT}.lnk" "$INSTDIR\${PRODUCT}.exe" ""
SectionEnd


Section "Startmenu Icons" SecStart
    CreateShortCut "$SMPROGRAMS\${PRODUCT}.lnk" "$INSTDIR\${PRODUCT}.exe"
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
    WriteRegStr HKCR "bittorrent\DefaultIcon" "" "$INSTDIR\tribler_source\resources\torrenticon.ico"
SectionEnd


Section "Make Default For magnet://" SecDefaultMagnet
    WriteRegStr HKCR "magnet" "" "URL: Magnet Link Protocol"
    WriteRegStr HKCR "magnet" "URL Protocol" ""
    WriteRegStr HKCR "magnet\DefaultIcon" "" "$INSTDIR\tribler_source\resources\torrenticon.ico"
    WriteRegStr HKCR "magnet\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
    WriteRegStr HKLM "SOFTWARE\Classes\magnet\shell\open\command" "" '"$INSTDIR\${PRODUCT}.exe" "%1"'
SectionEnd

;--------------------------------
;Descriptions

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDesk} $(DESC_SecDesk)
!insertmacro MUI_DESCRIPTION_TEXT ${SecStart} $(DESC_SecStart)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultTorrent} $(DESC_SecDefaultTorrent)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultMagnet} $(DESC_SecDefaultMagnet)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section

Section "Uninstall"
    ; Check if tribler is not running when trying to uninstall because files will be in use then.
    Call un.checkrunning
    RMDir /r "$INSTDIR"

    Delete "$DESKTOP\${PRODUCT}.lnk"

    SetShellVarContext all
    Delete "$SMPROGRAMS\${PRODUCT}.lnk"

    DeleteRegKey HKEY_LOCAL_MACHINE "SOFTWARE\${PRODUCT}"
    DeleteRegKey HKEY_LOCAL_MACHINE "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}"

    ; Remove an application from the firewall exception list
    SimpleFC::RemoveApplication "$INSTDIR\${PRODUCT}.exe"
SectionEnd

;--------------------------------
;Macros and Functions Section

Function .onInit
    System::Call 'kernel32::CreateMutexA(i 0, i 0, t "Tribler") i .r1 ?e'

    Pop $R0
    StrCmp $R0 0 checkinst

    MessageBox MB_OK "The installer is already running."
    Abort

    checkinst:
        ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString"
        StrCmp $R0 "" done
        IfFileExists $R0 showuninstdialog done

    showuninstdialog:
        MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "${PRODUCT} is already installed. $\n$\nClick `OK` to remove the previous version or `Cancel` to cancel this upgrade." /SD IDCANCEL IDOK uninst
        Abort

    uninst:
        ClearErrors
        ; Laurens (2016-03-29): Retrieve the uninstallString stored in the register. 
		; Do NOT use $INSTDIR as this points to the current $INSTDIR var of the INSTALLER, 
        ; which is the default location at this point.
        ReadRegStr $R0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString"
        ReadRegStr $R1 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "InstallLocation"
        ExecWait '"$R0" _?=$R1' ; This prevents the installer from being ran in a tmp directory, causing execwait not to wait.
        RMDir /r "$R1"  ; Remove the previous install directory
        ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString"
        StrCmp $R0 "" done
        Abort
    done:

FunctionEnd

