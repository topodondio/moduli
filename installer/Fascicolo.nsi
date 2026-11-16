; Programma di installazione di Fascicolo (NSIS).
; Si crea con:  python installer/crea_installer.py   (funziona anche da Linux, non serve Windows)

Unicode true
!ifndef VERSIONE
  !define VERSIONE "0.0.0"
!endif
!ifndef ORIGINE
  !define ORIGINE "..\build\Fascicolo"
!endif
!ifndef USCITA
  !define USCITA "..\dist"
!endif
!ifndef ICONA
  !define ICONA "..\assets\fascicolo.ico"
!endif
!define NOME "Fascicolo"
!define CHIAVE "Software\Microsoft\Windows\CurrentVersion\Uninstall\Fascicolo"

Name "${NOME} ${VERSIONE}"
OutFile "${USCITA}\Fascicolo-Setup-${VERSIONE}.exe"
InstallDir "$LOCALAPPDATA\Programs\${NOME}"
; se è già installato altrove, aggiorno quella cartella
InstallDirRegKey HKCU "${CHIAVE}" "InstallLocation"
; per l'utente: niente permessi di amministratore, aggiornamenti silenziosi
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${NOME} ${VERSIONE}"
VIProductVersion "${VERSIONE}.0"
VIAddVersionKey /LANG=1040 "ProductName" "${NOME}"
VIAddVersionKey /LANG=1040 "FileDescription" "Installazione di ${NOME}"
VIAddVersionKey /LANG=1040 "FileVersion" "${VERSIONE}"
VIAddVersionKey /LANG=1040 "ProductVersion" "${VERSIONE}"
VIAddVersionKey /LANG=1040 "CompanyName" "topodondio"
VIAddVersionKey /LANG=1040 "LegalCopyright" "topodondio"

!include "MUI2.nsh"
!define MUI_ICON "${ICONA}"
!define MUI_UNICON "${ICONA}"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION AvviaFascicolo
!define MUI_FINISHPAGE_RUN_TEXT "Avvia ${NOME}"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Italian"

Function AvviaFascicolo
  Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\Fascicolo.pyw"'
FunctionEnd

Section "Fascicolo" SecMain
  SetOutPath "$INSTDIR"
  ; via i file della versione precedente (le pratiche stanno nell'archivio, non qui)
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\fascicolo"
  RMDir /r "$INSTDIR\mappature"
  RMDir /r "$INSTDIR\moduli"
  File /r "${ORIGINE}\*.*"
  WriteUninstaller "$INSTDIR\Disinstalla.exe"

  CreateDirectory "$SMPROGRAMS\${NOME}"
  CreateShortcut "$SMPROGRAMS\${NOME}\${NOME}.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\Fascicolo.pyw"' "$INSTDIR\assets\fascicolo.ico"
  CreateShortcut "$SMPROGRAMS\${NOME}\Disinstalla ${NOME}.lnk" "$INSTDIR\Disinstalla.exe"
  CreateShortcut "$DESKTOP\${NOME}.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\Fascicolo.pyw"' "$INSTDIR\assets\fascicolo.ico"

  WriteRegStr HKCU "${CHIAVE}" "DisplayName" "${NOME}"
  WriteRegStr HKCU "${CHIAVE}" "DisplayVersion" "${VERSIONE}"
  WriteRegStr HKCU "${CHIAVE}" "Publisher" "topodondio"
  WriteRegStr HKCU "${CHIAVE}" "DisplayIcon" "$INSTDIR\assets\fascicolo.ico"
  WriteRegStr HKCU "${CHIAVE}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${CHIAVE}" "UninstallString" '"$INSTDIR\Disinstalla.exe"'
  WriteRegStr HKCU "${CHIAVE}" "URLInfoAbout" "https://github.com/topodondio/moduli"
  WriteRegDWORD HKCU "${CHIAVE}" "NoModify" 1
  WriteRegDWORD HKCU "${CHIAVE}" "NoRepair" 1

  ; aggiornamento lanciato dal programma (/S): a fine installazione lo riapro
  IfSilent 0 +2
    Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\Fascicolo.pyw"'
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\${NOME}.lnk"
  RMDir /r "$SMPROGRAMS\${NOME}"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${CHIAVE}"
SectionEnd
