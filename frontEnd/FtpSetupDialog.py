#!/usr/bin/env python

#*****************************************************************************
#
# FtpSetupDialog.py
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
# https://github.url/thing
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

# Python imports...
import ftplib
import socket
import StringIO
import sys
import time

# Common 3rd-party imports...
#from PIL import Image
import wx

# Toolbox imports...
from vitaToolbox.wx.TextCtrlUtils import fixSelection

# Local imports...
from appCommon.CommonStrings import kAppName


# Constants...
_kDialogTitle = "Set up FTP"

_kHostLabelStr = "Host:"
_kDirectoryLabelStr = "Directory:"
_kUserLabelStr = "Login user ID:"
_kPasswordLabelStr = "Login password:"
_kVerifyPasswordLabelStr = "Verify password:"
_kPortLabelStr = "FTP port number:"
_kPassiveModeLabelStr = "Use passive (pasv) mode"

_kHostDescStr = "FTP Server"
#_kDirectoryDescStr = "directory"
#_kUserDescStr = "user ID"
#_kPasswordDescStr = "password"
_kBadCharErrorTitleStr = "FTP settings"
_kBadCharErrorStr = "The '%s' field cannot contain the '%s' character."

_kPasswordsMustMatchStr = "The two password fields must match."
_kPasswordsMustMatchTitleStr = "FTP settings"

_kBadPortErrorTitleStr = "FTP settings"
_kBadPortErrorStr = "Invalid FTP port number: \"%s\"."
_kNoPortErrorStr = "You must specify an FTP port number."


_kBadSettingsErrorTitleStr = "FTP settings"
_kBadSettingsErrorStr = (
    """You must at least specify a server and a directory."""
)

_kTestUploadStr = "Test"

_kTestProgressTitle = "Uploading test file"

_kTestErrorTitleStr = "FTP settings"
_kTestErrorStr = "There was a problem while %s:\n\n%s"

_kLoginErrorTitleStr = "FTP settings"
_kLoginErrorStr = \
    "Login to server failed. Please check your user ID and password.\n\n%s"


_kUnknownHostErrorTitleStr = "FTP settings"
_kUnknownHostErrorStr = "FTP server not found: %s"

_kSuccessTitleStr = "FTP settings"
_kSuccessStr = "Success! A test file has been uploaded to your FTP server."

_kTestFtpFileContents = (
    "%s uploaded this test file to your FTP server at %%(timeNow)s."
) % (kAppName)

_kTestFtpFileName = kAppName + " Test.txt"

_kStandardPortList = [
    str(ftplib.FTP_PORT),
]

# Limit timeout to 30 seconds, 10 wasn't always enough on Windows.
_kSocketTimeout = 30.0


_kOpeningConnection   = (0, "opening connection to %s:%s...")
_kLoggingIn           = (1, "logging in...")
_kChangingDirectories = (2, "changing directories...")
_kUploadingFile       = (3, "uploading...")
_kDone                = (4, "done uploading")
_kNumProgressSteps    =  4
_kProgressInitialSpacing = (
    "                                                                          "
)

# Minimum width for our fields...
_kMinFieldWidth = 400


##############################################################################
class FtpSetupDialog(wx.Dialog):
    """A dialog for setting up ftp upload."""

    ###########################################################
    def __init__(self, parent, ftpConfig):
        """FtpSetupDialog constructor.

        @param  parent             Our parent UI element.
        @param  ftpConfig          See BackEndPrefs for details.
        """
        # Call our super
        super(FtpSetupDialog, self).__init__(
            parent, title=_kDialogTitle
        )

        try:
            self._oldFtpConfig = ftpConfig
            self._initUiWidgets()
            self._putFtpConfigToUi(ftpConfig)

            self.Fit()
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        hostLabel = wx.StaticText(self, -1, _kHostLabelStr,
                                  style=wx.ST_NO_AUTORESIZE)
        self._hostField = wx.TextCtrl(self, -1)
        directoryLabel = wx.StaticText(self, -1, _kDirectoryLabelStr,
                                       style=wx.ST_NO_AUTORESIZE)
        self._directoryField = wx.TextCtrl(self, -1)
        userLabel = wx.StaticText(self, -1, _kUserLabelStr,
                                  style=wx.ST_NO_AUTORESIZE)
        self._userField = wx.TextCtrl(self, -1)
        passwordLabel = wx.StaticText(self, -1, _kPasswordLabelStr,
                                      style=wx.ST_NO_AUTORESIZE)
        self._passwordField = wx.TextCtrl(self, -1, style=wx.TE_PASSWORD)
        verifyPasswordLabel = wx.StaticText(self, -1, _kVerifyPasswordLabelStr,
                                            style=wx.ST_NO_AUTORESIZE)
        self._verifyPasswordField = wx.TextCtrl(self, -1, style=wx.TE_PASSWORD)
        portLabel = wx.StaticText(self, -1, _kPortLabelStr,
                                  style=wx.ST_NO_AUTORESIZE)

        for field in (self._hostField, self._directoryField, self._userField,
                      self._passwordField, self._verifyPasswordField):
            field.SetMinSize((_kMinFieldWidth, -1))


        self._portCtrl = wx.ComboBox(self, -1, style=wx.CB_DROPDOWN,
                                     choices=_kStandardPortList + ['99999'])
        self._portCtrl.SetMinSize(self._portCtrl.GetBestSize())
        self._portCtrl.SetItems(_kStandardPortList)

        self._passiveCheckbox = wx.CheckBox(self, -1, _kPassiveModeLabelStr)


        # We use the StdDialogButtonSizer(), but yet add some normal buttons
        # too.  I'm not sure if this is intended by wxpython, or if it's
        # kosher UI, but it seems to work and does about what I'd expect.
        buttonSizer = wx.StdDialogButtonSizer()

        self._testMessageButton = wx.Button(self, -1, _kTestUploadStr)
        buttonSizer.Add(self._testMessageButton, 0, wx.LEFT | wx.RIGHT, 12)

        self._okButton = wx.Button(self, wx.ID_OK)
        buttonSizer.AddButton(self._okButton)

        self._cancelButton = wx.Button(self, wx.ID_CANCEL)
        buttonSizer.AddButton(self._cancelButton)

        self._okButton.SetDefault()
        buttonSizer.Realize()


        # Throw things in sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        gridSizer = wx.FlexGridSizer(rows=0, cols=2, vgap=7, hgap=5)
        gridSizer.AddGrowableCol(1)
        gridSizer.Add(hostLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._hostField, 0, wx.EXPAND)
        gridSizer.Add(directoryLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._directoryField, 0, wx.EXPAND)
        gridSizer.Add(userLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._userField, 0, wx.EXPAND)
        gridSizer.Add(passwordLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._passwordField, 0, wx.EXPAND)
        gridSizer.Add(verifyPasswordLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._verifyPasswordField, 0, wx.EXPAND)
        gridSizer.Add(portLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._portCtrl)
        gridSizer.AddSpacer(1)
        gridSizer.Add(self._passiveCheckbox)

        mainSizer.Add(gridSizer, 0, wx.EXPAND | wx.BOTTOM, 7)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
        borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

        self.SetSizer(borderSizer)

        self.Bind(wx.EVT_BUTTON, self.OnTestUpload, self._testMessageButton)
        self.Bind(wx.EVT_BUTTON, self.OnOK, self._okButton)


    ###########################################################
    def getFtpConfig(self, isBlankOk=True):
        """Read out an ftp configuration dict from our UI.

        @param  isBlankOk  If True, it's OK for settings to be "blank"
        @return ftpConfig  See BackEndPrefs for details; may be None if an
                           error was found (and reported to the user).
        """
        # Init config with the old one.  This allows us to save settings that
        # are in the default, but that we can't (currently) configure via the
        # UI...
        ftpConfig = dict(self._oldFtpConfig)

        # Convert to unicode; on failure, give an error and return None.
        try:
            desc = _kHostDescStr
            field = self._hostField
            ftpConfig['host'] = \
                field.GetValue().encode('ascii', 'strict').strip()
        except UnicodeEncodeError, e:
            assert desc is not None
            field.SetFocus()
            field.SetSelection(-1, -1)
            wx.MessageBox(_kBadCharErrorStr % (desc,
                                               e.object[e.start:e.start+1]),
                          _kBadCharErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self)
            return None
        desc = None

        # Get fields that are OK to be unicode.
        ftpConfig['directory'] = self._directoryField.GetValue().strip()
        ftpConfig['user'] = self._userField.GetValue().strip()
        ftpConfig['password'] = self._passwordField.GetValue().strip()
        verifyPassword = self._verifyPasswordField.GetValue().strip()

        if ftpConfig['password'] != verifyPassword:
            self._verifyPasswordField.SetFocus()
            self._verifyPasswordField.SetValue("")
            wx.MessageBox(_kPasswordsMustMatchStr, _kPasswordsMustMatchTitleStr,
                          wx.OK | wx.ICON_ERROR, self)
            return None

        # Convert the port--it must be an int and within range...
        try:
            ftpConfig['port'] = int(self._portCtrl.GetValue().strip())
            if (ftpConfig['port'] < 1) or (ftpConfig['port'] > 65535):
                raise ValueError()
        except ValueError:
            if self._portCtrl.GetValue():
                wx.MessageBox(_kBadPortErrorStr % (self._portCtrl.GetValue()),
                              _kBadPortErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, self)
            else:
                wx.MessageBox(_kNoPortErrorStr, _kBadPortErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, self)
            return None

        ftpConfig['isPassive'] = bool(self._passiveCheckbox.GetValue())

        # If they've specified something, they must specify host / directory.
        host = ftpConfig['host']
        directory = ftpConfig['directory']
        user = ftpConfig['user']
        password = ftpConfig['password']
        if (not isBlankOk) or host or directory or user or password:
            if not (host and directory):
                wx.MessageBox(_kBadSettingsErrorStr, _kBadSettingsErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, self)
                return None

        # If we're here, we're OK...
        return ftpConfig


    ###########################################################
    def _putFtpConfigToUi(self, ftpConfig):
        """The opposite of getFtpConfig().

        @param  ftpConfig  See BackEndPrefs for details.
        """
        self._hostField.SetValue(ftpConfig.get('host', ""))
        self._directoryField.SetValue(ftpConfig.get('directory', ""))
        self._userField.SetValue(ftpConfig.get('user', ""))
        self._passwordField.SetValue(ftpConfig.get('password', ""))
        self._verifyPasswordField.SetValue(ftpConfig.get('password', ""))
        self._portCtrl.SetValue(str(ftpConfig.get('port', "")))
        self._portCtrl.SetStringSelection(str(ftpConfig.get('port', "")))
        self._passiveCheckbox.SetValue(ftpConfig.get('isPassive', True))

        # Fix Mac text fields...
        fixSelection(self._hostField, self._directoryField, self._userField,
                     self._passwordField, self._verifyPasswordField,
                     self._portCtrl)


    ###########################################################
    def OnOK(self, event):
        """Respond to the user pressing OK

        @param  event  The button event
        """
        # Get the ftp config; if it's completely invalid, we'll get back
        # None (and the user will already have been shown an error message).
        ftpConfig = self.getFtpConfig()
        if ftpConfig is None:
            return

        self.EndModal(wx.ID_OK)


    ###########################################################
    def OnTestUpload(self, event):
        """Respond to the user pressing the "Send test message" button.

        @param  event  The button event
        """
        # Get the ftp config; if it's completely invalid, we'll get back
        # None (and the user will already have been shown an error message).
        ftpConfig = self.getFtpConfig(False)
        if ftpConfig is None:
            return

        loggedIn = False

        progressDlg = \
            wx.ProgressDialog(_kTestProgressTitle, _kProgressInitialSpacing,
                              _kNumProgressSteps, self, wx.PD_APP_MODAL |
                              wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT)

        ftpObj = ftplib.FTP(timeout=_kSocketTimeout)
        #ftpObj.set_debuglevel(2)
        try:
            stage, msg = _kOpeningConnection
            msg = msg % (ftpConfig['host'], ftpConfig['port'])
            wantContinue, _ = progressDlg.Update(stage, msg.capitalize())
            if not wantContinue:
                return
            ftpObj.connect(ftpConfig['host'], int(ftpConfig['port']))

            stage, msg = _kLoggingIn
            wantContinue, _ = progressDlg.Update(stage, msg.capitalize())
            if not wantContinue:
                return
            ftpObj.login(ftpConfig['user'], ftpConfig['password'])
            loggedIn = True

            # Set to passive mode if user wants it...
            ftpObj.set_pasv(ftpConfig['isPassive'])

            stage, msg = _kChangingDirectories
            wantContinue, _ = progressDlg.Update(stage, msg.capitalize())
            if not wantContinue:
                return
            ftpObj.cwd(ftpConfig['directory'])

            stage, msg = _kUploadingFile
            wantContinue, _ = progressDlg.Update(stage, msg.capitalize())
            if not wantContinue:
                return
            fileToSend = StringIO.StringIO(_kTestFtpFileContents % {
                                             'timeNow': time.asctime(),
                                           })
            ftpObj.storlines('STOR %s' % _kTestFtpFileName, fileToSend)

            stage, msg = _kDone
            progressDlg.Update(stage, msg.capitalize())
        except socket.gaierror:
            progressDlg.Destroy()
            progressDlg = None
            wx.MessageBox(_kUnknownHostErrorStr % ftpConfig['host'],
                          _kUnknownHostErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self)
            return
        except ftplib.error_perm, e:
            progressDlg.Destroy()
            progressDlg = None
            if not loggedIn:
                wx.MessageBox(_kLoginErrorStr % str(e), _kLoginErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, self)
            else:
                wx.MessageBox(_kTestErrorStr % (msg.rstrip('.'), str(e)),
                              _kTestErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, self)
            return
        except Exception, e:
            progressDlg.Destroy()
            progressDlg = None
            wx.MessageBox(_kTestErrorStr % (msg.rstrip('.'), str(e)),
                          _kTestErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self)
            return
        finally:
            try:
                ftpObj.quit()
            except Exception:
                # Ignore errors to quit, just in case...
                pass

            if progressDlg is not None:
                progressDlg.Destroy()

        wx.MessageBox(_kSuccessStr, _kSuccessTitleStr,
                      wx.OK | wx.ICON_INFORMATION, self)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    # Ugly test code...
    from BackEndClient import BackEndClient

    app = wx.App(False)
    app.SetAppName(kAppName)

    backEndClient = BackEndClient()
    didConnect = backEndClient.connect()
    assert didConnect

    ftpSettings = backEndClient.getFtpSettings()
    dlg = FtpSetupDialog(None, ftpSettings)
    try:
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            backEndClient.setFtpSettings(dlg.getFtpConfig())
    finally:
        dlg.Destroy()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
