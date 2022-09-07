#!/usr/bin/env python

#*****************************************************************************
#
# WinInstaller.py
#   Part of build process.
#   Used for creating Windows installer based on the specified template.
#
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Sighthound, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Sighthound, Inc.
# by emailing opensource@sighthound.com
#
# This file is part of the Sighthound Video project which can be found at
# https://github.com/sighthoundinc/SighthoundVideo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; using version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02111, USA.
#
#
#*****************************************************************************


"""
## @file
Contains the InnoInstaller class, for creating an InnoSetup installer
"""

import sys
import os, subprocess
from string import Template

from appCommon.CommonStrings import kAppName, kOemName, kExeName
from appCommon.CommonStrings import kVersionString
from appCommon.CommonStrings import kDocumentationIconUrl
from appCommon.CommonStrings import kDocumentationDescription
from appCommon.CommonStrings import kDocumentationUrl, kOemUrl
from appCommon.CommonStrings import kSoftwareLicenseAgreementRtf

_kInstallScriptTemplate = r"""
; WARNING: This script has been auto-generated! Changes to this script
;          will be overwritten the next time a build is made!

[Setup]
ArchitecturesInstallIn64BitMode=x64
OutputDir=$OUTPUT_DIR
OutputBaseFilename=$APP_NAME Setup
AppName=$APP_NAME
AppVerName=$APP_NAME $VERSION_STRING
AppId=$APP_NAME
DefaultDirName={pf}\$APP_NAME
DefaultGroupName=$APP_NAME
SetupIconFile=$INSTALLER_ICON
LicenseFile=$LICENSE_FILE
ChangesAssociations=no
AppPublisher=$OEM_NAME
AppPublisherURL=$OEM_URL
DisableProgramGroupPage=yes
WizardImageFile=$IMG_WELCOME
WizardSmallImageFile=$IMG_PILL
UninstallDisplayIcon={app}\$EXE_NAME.exe
AllowCancelDuringInstall=no

[Files]
Source: "$APP_OUT_DIR/redist/vc_redist.x64.exe"; DestDir: {tmp}; Flags: deleteafterinstall; AfterInstall: InstallCRT; Check: CRTIsNotInstalled
Source: "$APP_OUT_DIR/redist/w_dpcpp_cpp_runtime_p_2022.0.0.3663.exe"; DestDir: {tmp}; Flags: deleteafterinstall; AfterInstall: InstallIntel; Check: IntelIsNotInstalled
Source: "$APP_OUT_DIR$SERVICE_EXE"; DestDir: "{tmp}\"; AfterInstall: SV_Shutdown()
Source: "$APP_OUT_DIR$EXE_NAME.exe"; DestDir: "{app}\"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "$APP_OUT_DIR*.*"; DestDir: "{app}\"; Flags: ignoreversion recursesubdirs createallsubdirs; AfterInstall: SV_InstallService()

[InstallDelete]
Type: files; Name: "{app}\numpy.core._dotblas.pyd"

[UninstallDelete]
Type: files; Name: "{app}\data_dir_ptr"

[Icons]
Name: "{group}\$APP_NAME"; Filename: "{app}\$EXE_NAME.exe"; WorkingDir: {app}
Name: "{group}\$DOCUMENTATION_NAME"; Filename: "$DOCUMENTATION_URL"; IconFilename: "$DOCUMENTATION_ICON"; IconIndex: 1
Name: "{group}\Uninstall $APP_NAME"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\$EXE_NAME.exe"; Description: "{cm:LaunchProgram,$APP_NAME}"; Flags: postinstall nowait
Filename: "{app}\$APP_NAME $DOCUMENTATION_NAME.url"; Description: "$DOCUMENTATION_DESCRIPTION"; Flags: postinstall shellexec skipifsilent skipifdoesntexist unchecked nowait

[Code]

procedure ExitProcess(ExitCode : Integer);
  external 'ExitProcess@kernel32.dll stdcall';

(******************************************************************************
 *
 *  Inno Setup docs state that the installer adds registry entries for various
 *  paths and other values related to the app. "AppId" is a setup setting of
 *  Inno Setup that we can use to acquire the registry entry for the app. We use
 *  AppName as the AppId because we did not previously have any value set for
 *  AppId, and the default value for it is the AppName when not defined in the
 *  setup settings. This gaurantees we will be able to find all previous
 *  installs of the app.
 *
 *  The uninstall parameters chosen here gaurantee a silent removal of the app
 *  such that the user never sees any indication that the previous version is
 *  being removed, no pop-ups, and no auto-restart after app removal process is
 *  completed.
 *)


(******************************************************************************)
const
  _RegLegacyUnInstPath = 'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\' + '$APP_NAME' + '_is1';
  _RegUnInstPath = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';
  _UnInstParams = '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES';


(******************************************************************************)
var
  _MustRestart : Boolean;
  _ServiceExe : String;


(******************************************************************************)
function CRTIsNotInstalled: Boolean;
begin
  Result := True;
end;

(******************************************************************************)
procedure InstallCRT;
var
  ResultCode: Integer;
begin
  if not Exec(ExpandConstant('{tmp}/vc_redist.x64.exe'), '/install /passive /norestart', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
  begin
    { you can interact with the user that the installation failed }
    MsgBox('CRT installation failed with code: ' + IntToStr(ResultCode) + '.', mbError, MB_OK);
    WizardForm.Close;
  end;
end;

(******************************************************************************)
function IntelIsNotInstalled: Boolean;
begin
  Result := True;
end;

(******************************************************************************)
procedure InstallIntel;
var
  ResultCode: Integer;
begin
  if not Exec(ExpandConstant('{tmp}/vc_redist.x64.exe'), '/install /passive /norestart', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
  if not Exec( 'msiexec.exe', '/i ' + ExpandConstant('{tmp}\w_dpcpp_cpp_runtime_p_2022.0.0.3663.exe') + ' --silent  --remove-extracted-files yes --a /passive /norestart /qn /quiet', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
  begin
    { you can interact with the user that the installation failed }
    MsgBox('Intel runtime installation failed with code: ' + IntToStr(ResultCode) + '.', mbError, MB_OK);
    WizardForm.Close;
  end;
end;

(******************************************************************************)
procedure SV_Log(msg : String);
begin
  Log('[SVLOG] - ' + msg);
end;


(******************************************************************************
 *
 *  Helper function that expands any Inno Setup constants in the string
 *  containing the registry key to the path of the app's uninstaller.
 *)
function SV_GetRegUnInstPath() : String;
begin
  Result := ExpandConstant(_RegUnInstPath);
end;

(******************************************************************************
 *
 *  Acquires the path to the uninstaller as a string and returns it. The string
 *  returned will be the empty string if no path is found.
 *)
function SV_GetUninstallString() : string;
var
  sUnInstPath: string;
  sUnInstallString: String;
begin
  sUnInstPath := SV_GetRegUnInstPath();
  sUnInstallString := '';
  if RegQueryStringValue(HKLM, _RegLegacyUnInstPath, 'UninstallString', sUnInstallString) then
    SV_Log('Install - $APP_NAME was found.in HKLM/' + _RegLegacyUnInstPath)
  else if RegQueryStringValue(HKCU, _RegLegacyUnInstPath, 'UninstallString', sUnInstallString) then
    SV_Log('Install - $APP_NAME was found.in HKCU/' + _RegLegacyUnInstPath)
  else if RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    SV_Log('Install - $APP_NAME was found.in HKLM/' + sUnInstPath)
  else if RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString) then
    SV_Log('Install - $APP_NAME was found.in HKCU/' + sUnInstPath)
  else
    SV_Log('Install - $APP_NAME: previous install was not found');
  Result := sUnInstallString;
end;


(******************************************************************************)
procedure SV_UninstallPreviousVersion();
var
  iResultCode: Integer;
  sUnInstallString: string;
begin
  (* Get the uninstaller path if it exists in the registry... *)
  sUnInstallString := SV_GetUninstallString();
  if sUnInstallString <> '' then begin
    SV_Log('Install - A previous installation of $APP_NAME was detected; ' + \
           'running "' + sUnInstallString + ' ' + _UnInstParams + '" now.');
    sUnInstallString := RemoveQuotes(sUnInstallString);
    (* Run the uninstaller completely invisible to the user, and wait
       for it to finish before we return... *)
    Exec(ExpandConstant(sUnInstallString), _UnInstParams, '', SW_HIDE, ewWaitUntilTerminated, iResultCode);
    if iResultCode = 0 then
      SV_Log(Format('Install - $APP_NAME was successfully removed. (%d).', [iResultCode]))
    else
      SV_Log(Format('Install - Error during auto-uninstall process. (%d).', [iResultCode]));
  end;
end;


(******************************************************************************
 *
 *  Acquires the path to the pointer of existing data_dir_ptr
 *  Returned value will be the empty string if no path is found.
 *)
function SV_GetExistingDataDirPtr() : string;
var
  sUnInstallString: String;
  dirPtr: String;
  dirName: String;
begin
  sUnInstallString := SV_GetUninstallString();
  dirPtr := '';

  if sUnInstallString <> '' then begin
    sUnInstallString := RemoveQuotes(sUnInstallString)
    dirName := ExtractFileDir(sUnInstallString)
    dirPtr := dirName + '\data_dir_ptr'
    if not FileExists(dirPtr) then begin
      SV_Log('Install - ' + dirPtr + ' does not exist')
      dirPtr := ''
    end
    else begin
      SV_Log('Install - found existing ' + dirPtr)
    end;
  end;

  Result := dirPtr;
end;

(******************************************************************************)
function SV_CloseFrontend() : Boolean;
var
  OldWindow : HWND;
  QuitCount : Integer;
  ResultCode : Integer;
begin
  (* we used to call the FindWindowA/Win32 function directly, also passing in the window
     class name 'wxWindowClassNR' for better identification; that however has stopped
     working, maybe some new Windows 8 protection or so? INSPECT.EXE of the Windows 8 SDK
     still shows our front-end window with the correct title and class name though ... *)
  OldWindow := FindWindowByWindowName('$APP_NAME');
  if (OldWindow <> 0) then begin
    ResultCode := SendMessage(OldWindow, $$0010, 0, 0);   (* send WM_CLOSE *)
    QuitCount := 0
    while (OldWindow <> 0) and (QuitCount < 120) do begin
      Sleep(500);
      OldWindow := FindWindowByWindowName('$APP_NAME');
      QuitCount := QuitCount + 1;
      SV_Log(Format('Trying to quit the frontend, count is %d', [QuitCount]));
    end;
  end;
  Result := OldWindow = 0;
  if not Result then
    MsgBox('$APP_NAME is still running. Please quit before continuing.', mbError, MB_OK);
end;


(******************************************************************************)
procedure SV_Shutdown;
var
  ResultCode : Integer;
begin
  SV_Log('Shutting down...');
  Exec(ExpandConstant('{tmp}') + '\$SERVICE_EXE', 'shutdown', '', $SHOW_EXEC, ewWaitUntilTerminated, ResultCode);
  if ResultCode <> 0 then
    MsgBox(Format('$APP_NAME could not be shut down (%d).', [ResultCode]), mbError, MB_OK);
end;


(******************************************************************************)
procedure SV_InstallService;
var
  ResultCode : Integer;
  ServiceExe : String;
begin
  ServiceExe := ExpandConstant(CurrentFileName);
  if ExtractFileName(ServiceExe) <> '$SERVICE_EXE' then
    Exit;
  SV_Log('Installing service...');
  Exec(ServiceExe, 'install', '', $SHOW_EXEC, ewWaitUntilTerminated, ResultCode);
  if ResultCode = 0 then
    _ServiceExe := ServiceExe
  else begin
    MsgBox(Format('The $APP_NAME service could not be installed (%d).' + #13#10 + \
                  'Please restart your computer first.', [ResultCode]), mbError, MB_OK);
    (* there's no(?) other way to quickly get out and also leave nothing behind *)
    DelTree(ExpandConstant('{app}'), True, True, True);
    ExitProcess(0);
  end;
end;


(******************************************************************************)
procedure InitializeWizard;
begin
  _MustRestart := false;
  _ServiceExe := '';
end;

function InitializeSetup : Boolean;
begin
  if IsWin64 then begin
    Result := SV_CloseFrontend
  end
  else begin
    MsgBox('The $APP_NAME $VERSION_STRING is a 64-bit application and can not be installed on 32-bit OS.' , mbError, MB_OK);
    Result := false
  end;
end;

(******************************************************************************)
function UninstallNeedRestart : Boolean;
begin
  Result := _MustRestart;
end;


(******************************************************************************)
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode : Integer;
  DataDirPtr : String;
  DataDirPtrBk : String;
begin
  if CurStep = ssInstall then
  begin
    (* We _MUST_ backup the data directory file pointer _BEFORE_ we run the
     * uninstaller of the previous version. If the user decides to install SV
     * over a previously installed version from a different Windows user
     * account, SV-service will use this user's local app data directory for
     * storage instead of the directory that was used previously. It is safe
     * to rename this file in the SV installation directory, because the
     * uninstaller will only delete files that its accompanying installer
     * created, or files that the uninstaller is explicitly told to delete.
     *)
    DataDirPtr := SV_GetExistingDataDirPtr()
    if DataDirPtr =  '' then
      DataDirPtr := ExpandConstant('{app}\data_dir_ptr');
    DataDirPtrBk := ExpandConstant('{tmp}\data_dir_ptr');
    if FileExists(DataDirPtr) then
    begin
      FileCopy(DataDirPtr, DataDirPtrBk, false);
    end;
    (* Uninstall the previous version of this app and wait for it to finish
     * BEFORE we start installing this version of the app...
     *)
    SV_UninstallPreviousVersion();
    (* Whether uninstallation succeeded or failed, we must now restore the
     * data directory file pointer backup to its original name.
     *)
    if FileExists(DataDirPtrBk) then
    begin
      FileCopy(DataDirPtrBk, DataDirPtr, false);
      if FileExists(DataDirPtr) then
        DeleteFile(DataDirPtrBk);
    end;
    Exit;
  end;
  if (CurStep <> ssPostInstall) or ('' = _ServiceExe) then
    Exit;
  Exec(_ServiceExe, 'start', '', $SHOW_EXEC, ewWaitUntilTerminated, ResultCode);
  if ResultCode <> 0 then
    MsgBox(Format('The $APP_NAME service could not be started (%d).', [ResultCode]), mbError, MB_OK);
end;


(******************************************************************************)
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode : Integer;
  ServiceExe : String;
begin
  if (CurUninstallStep <> usUninstall) then
    Exit;
  ServiceExe := ExpandConstant('{app}') + '\$SERVICE_EXE';
  SV_Log('Uninstall - shutting down...');
  Exec(ServiceExe, 'shutdown', '', $SHOW_EXEC, ewWaitUntilTerminated, ResultCode);
  SV_Log(Format('Uninstall - shutdown result is %d', [ResultCode]));
  SV_Log('Uninstall - removing...');
  Exec(ServiceExe, 'remove', '', $SHOW_EXEC, ewWaitUntilTerminated, ResultCode);
  SV_Log(Format('Uninstall - removal result is %d', [ResultCode]));
  if ResultCode = 4 then
    _MustRestart := true
end;

procedure DeinitializeSetup;
var
  TempServiceExe : String;
begin
  TempServiceExe := ExpandConstant('{tmp}') + '\$SERVICE_EXE';
  DelayDeleteFile(TempServiceExe, 10);
end;


(******************************************************************************)
function InitializeUninstall: Boolean;
begin
  SV_CloseFrontend;
  Result := true;
end;

"""


################################################################
class InnoScript:
    """Class to create and compile InnoSetup scripts.

    @param pathName  Path of the script file to create. Can be relative.
    """
    def __init__(self, pathName, buildDir="build"):
        self._pathName = pathName

        self._distDir = os.path.join(buildDir, "app-out", "frontEnd-Win")
        self._outputDir = os.path.join(buildDir, "installer-out", "frontEnd-Win")
        self._stage2Dir = os.path.join(buildDir, "package-out", "frontEndPrep-stage2", "smartvideo", "frontEnd")

        if not self._distDir[-1] in "\\/":
            self._distDir += "\\"
        self.documentation_name = "%s Documentation" % kAppName


    ################################################################
    def create(self):
        """Create the InnoSetup script file.
        """

        installScript = Template(_kInstallScriptTemplate).substitute(
            OUTPUT_DIR = self._outputDir,
            APP_NAME = kAppName,
            VERSION_STRING = kVersionString,
            LICENSE_FILE = os.path.join(self._stage2Dir, "docs", kSoftwareLicenseAgreementRtf),
            OEM_NAME = kOemName,
            OEM_URL = kOemUrl,
            INSTALLER_ICON = os.path.join(self._distDir, "icons", "InstallerIcon-win.ico"),
            IMG_WELCOME = os.path.join(self._stage2Dir, "bmps", "Installer_welcome.bmp"),
            IMG_PILL = os.path.join(self._stage2Dir, "bmps", "Installer_pill.bmp"),
            APP_OUT_DIR = self._distDir,
            DOCUMENTATION_NAME = self.documentation_name,
            DOCUMENTATION_URL = kDocumentationUrl,
            DOCUMENTATION_ICON = kDocumentationIconUrl,
            DOCUMENTATION_DESCRIPTION = kDocumentationDescription,
            SHOW_EXEC = "SW_HIDE",  # SW_SHOW to see console output of shlaunch.exe
            SERVICE_EXE = "shlaunch.exe",
            EXE_NAME = kExeName)

        ofi = self.file = open(self._pathName, "w")
        ofi.write(installScript)
        ofi.close()


    ################################################################
    def compile(self):
        """Execute InnoSetup to compile the script"""
        compilerOptions = [
            "C:\Program Files\Inno Setup 5\ISCC.exe",
            "C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        ]
        for compiler in compilerOptions:
            if os.path.exists(compiler):
                break
        else:
            assert False, "Missing %s. Please install Inno Setup." % compiler

        print compiler, self._pathName
        subprocess.call([compiler, self._pathName])


################################################################
# Create the installer script
if __name__ == '__main__':

    if len(sys.argv) > 1:
        script = InnoScript("%s Setup.iss" % kAppName, *sys.argv[1:])
    else:
        script = InnoScript("%s Setup.iss" % kAppName)

    print "*** creating the InnoSetup script***"
    script.create()

    print "*** compiling the InnoSetup script***"
    script.compile()

    print "*** InnoSetup installer creation complete***"

