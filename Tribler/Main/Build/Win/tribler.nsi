!define PRODUCT "Tribler"
; Laurens, 2016-03-14: The __GIT__ string will be replaced by update_version_from_git.py
; with the current version of the build.
!define VERSION "__GIT__"
; Laurens, 2016-03-14: The _x86 will be replaced by _x64 if needed in update_version_from_git.py
!define BITVERSION "x86"
!define VLCBITVERSION "32"

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

!define MUI_ICON "tribler_source\Tribler\Main\Build\Win\tribler.ico"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_ABORTWARNING

;--------------------------------
;Pages

!define MUI_LICENSEPAGE_RADIOBUTTONS
!define MUI_LICENSEPAGE_RADIOBUTTONS_TEXT_ACCEPT "I accept"
!define MUI_LICENSEPAGE_RADIOBUTTONS_TEXT_DECLINE "I decline"

!insertmacro MUI_PAGE_LICENSE "binary-LICENSE.txt"
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
LangString DESC_SecDefaultTStream ${LANG_ENGLISH} "Associate .tstream files with ${PRODUCT}"
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

    ; Install MSVCR 2008 and 2012
    SetOutPath "$INSTDIR"

    ; Libraries dependant on 2008 are: Python, APSW
    File vc_redist_90.exe
    ExecWait "$INSTDIR\vc_redist_90.exe /q /norestart"

    ; Libraries dependant on 2012 are: LevelDB, LibTorrent
    File vc_redist_110.exe
    ExecWait "$INSTDIR\vc_redist_110.exe /q /norestart"

    ; Install VLC
    File "vlc-2.2.4-win${VLCBITVERSION}.exe"
    ExecWait "$INSTDIR\vlc-2.2.4-win${VLCBITVERSION}.exe /language=en_GB /S"

    FileOpen $9 "$INSTDIR\tribler.exe.log" w
    FileWrite $9 ""
    FileClose $9
    AccessControl::GrantOnFile "$INSTDIR\tribler.exe.log" "(BU)" "FullAccess"
    AccessControl::GrantOnFile "$INSTDIR\tribler.exe.log" "(S-1-5-32-545)" "FullAccess"

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

;--------------------------------
;Descriptions

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDesk} $(DESC_SecDesk)
!insertmacro MUI_DESCRIPTION_TEXT ${SecStart} $(DESC_SecStart)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultTorrent} $(DESC_SecDefaultTorrent)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultTStream} $(DESC_SecDefaultTStream)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultMagnet} $(DESC_SecDefaultMagnet)
!insertmacro MUI_DESCRIPTION_TEXT ${SecDefaultPpsp} $(DESC_SecDefaultPpsp)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section

Section "Uninstall"
    ; Check if tribler is not running when trying to uninstall because files will be in use then.
    Call un.checkrunning
    RMDir /r "$INSTDIR"

    Delete "$DESKTOP\${PRODUCT}.lnk"

    SetShellVarContext all
    RMDir "$SMPROGRAMS\${PRODUCT}"
    RMDir /r "$SMPROGRAMS\${PRODUCT}"

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
        ExecWait '"$R0" _?=$INSTDIR' ; This prevents the installer from being ran in a tmp directory, causing execwait not to wait.
        ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT}" "UninstallString"
        StrCmp $R0 "" done
        Abort
    done:

FunctionEnd

