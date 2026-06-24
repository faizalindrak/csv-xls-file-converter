; Inno Setup Script for CSV-XLS-Converter
; Build with: iscc installer.iss

#define MyAppName "CSV-XLS Converter"
#define MyAppVersion "0.4.23"
#define MyAppPublisher "CSV-XLS Converter"
#define MyAppURL "https://github.com/faizalindrak/csv-xls-file-converter"
#define MyAppExeName "CSV-XLS-Converter.exe"
#define MyCliExeName "CSV-XLS-Converter-CLI.exe"
#define MyAppDescription "Convert CSV and XLS files to XLSX format"

[Setup]
; Basic app info
AppId={{8A3E5D2F-1B4C-4E6A-9D8F-2C7B3A9E5D1F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation paths
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output settings
OutputDir=dist
OutputBaseFilename=CSV-XLS-Converter-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Windows version requirements
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; Appearance
WizardStyle=modern
; SetupIconFile=assets\icon.ico  ; Uncomment when icon.ico is available
UninstallDisplayIcon={app}\{#MyAppExeName}

; Close running applications before install/update
CloseApplications=force
CloseApplicationsFilter=*.exe
RestartApplications=yes

; Privileges (install for current user by default, no admin required)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Uninstall info
Uninstallable=yes
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "contextmenu"; Description: "Add ""Convert to XLSX"" to right-click context menu"; GroupDescription: "Windows Explorer Integration:"; Flags: checkedonce

[Files]
; Main GUI executable from Cargo release output
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Command-line executable for automation
Source: "dist\{#MyCliExeName}"; DestDir: "{app}"; Flags: ignoreversion

; If you have additional files (config, assets, etc.), add them here:
; Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"

; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{#MyAppDescription}"

; Quick Launch shortcut (legacy)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Registry]
; Context menu entries for CSV files (Windows 10 classic style)
Root: HKCU; Subkey: "Software\Classes\.csv\shell\ConvertToXLSX"; ValueType: string; ValueName: ""; ValueData: "Convert to XLSX"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\.csv\shell\ConvertToXLSX"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\.csv\shell\ConvertToXLSX"; ValueType: string; ValueName: "Position"; ValueData: "Top"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\.csv\shell\ConvertToXLSX\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --silent ""%1"""; Tasks: contextmenu

; Context menu entries for XLS files (Windows 10 classic style)
Root: HKCU; Subkey: "Software\Classes\.xls\shell\ConvertToXLSX"; ValueType: string; ValueName: ""; ValueData: "Convert to XLSX"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\.xls\shell\ConvertToXLSX"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\.xls\shell\ConvertToXLSX"; ValueType: string; ValueName: "Position"; ValueData: "Top"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\.xls\shell\ConvertToXLSX\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --silent ""%1"""; Tasks: contextmenu

; Context menu entries for CSV files (Windows 11 modern style)
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.csv\shell\ConvertToXLSX"; ValueType: string; ValueName: ""; ValueData: "Convert to XLSX"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.csv\shell\ConvertToXLSX"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.csv\shell\ConvertToXLSX"; ValueType: string; ValueName: "Position"; ValueData: "Top"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.csv\shell\ConvertToXLSX\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --silent ""%1"""; Tasks: contextmenu

; Context menu entries for XLS files (Windows 11 modern style)
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xls\shell\ConvertToXLSX"; ValueType: string; ValueName: ""; ValueData: "Convert to XLSX"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xls\shell\ConvertToXLSX"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xls\shell\ConvertToXLSX"; ValueType: string; ValueName: "Position"; ValueData: "Top"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xls\shell\ConvertToXLSX\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --silent ""%1"""; Tasks: contextmenu

[Run]
; Option to launch app after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Check if application is running and prompt user to close it
function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  // Use tasklist to check if the process is running
  Exec('cmd.exe', '/c tasklist /FI "IMAGENAME eq {#MyAppExeName}" 2>NUL | find /I "{#MyAppExeName}" >NUL', 
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := (ResultCode = 0);
end;

function InitializeSetup(): Boolean;
var
  RetryCount: Integer;
  ResultCode: Integer;
begin
  Result := True;
  RetryCount := 0;
  
  while IsAppRunning() and (RetryCount < 3) do
  begin
    if MsgBox('{#MyAppName} is currently running.' + #13#10 + #13#10 +
              'Please close the application before continuing.' + #13#10 + #13#10 +
              'Click OK after closing the application, or Cancel to abort installation.',
              mbError, MB_OKCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
    RetryCount := RetryCount + 1;
    Sleep(500);
  end;
  
  // If still running after 3 retries, offer to force close
  if IsAppRunning() then
  begin
    if MsgBox('{#MyAppName} is still running.' + #13#10 + #13#10 +
              'Would you like to force close it? (Unsaved data may be lost)' + #13#10 + #13#10 +
              'Click Yes to force close, or No to abort installation.',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('taskkill.exe', '/F /IM "{#MyAppExeName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(1000);  // Wait for process to terminate
      Result := not IsAppRunning();
      if not Result then
        MsgBox('Failed to close {#MyAppName}. Please close it manually and try again.', mbError, MB_OK);
    end
    else
      Result := False;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  NeedsRestart := False;
  
  // Final check before installation begins
  if IsAppRunning() then
  begin
    // Try to gracefully close the application
    Exec('taskkill.exe', '/IM "{#MyAppExeName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(2000);  // Wait for graceful shutdown
    
    // If still running, force close
    if IsAppRunning() then
    begin
      Exec('taskkill.exe', '/F /IM "{#MyAppExeName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(1000);
    end;
    
    // Final check
    if IsAppRunning() then
      Result := '{#MyAppName} could not be closed. Please close it manually and run setup again.';
  end;
end;
