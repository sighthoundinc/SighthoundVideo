#!/usr/bin/env python

#*****************************************************************************
#
# EmailSetupDialog.py
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
import operator
import smtplib
import socket
import sys

# Common 3rd-party imports...
from PIL import Image
import wx

# Toolbox imports...
from vitaToolbox.wx.FontUtils import makeFontDefault
from vitaToolbox.networking.SimpleEmail import kEncryptionNone
from vitaToolbox.networking.SimpleEmail import kEncryptionSsl
from vitaToolbox.networking.SimpleEmail import kEncryptionTls
from vitaToolbox.networking.SimpleEmail import kEncryptionList
from vitaToolbox.networking.SimpleEmail import kStandardPortList
from vitaToolbox.networking.SimpleEmail import kNumProgressSteps
from vitaToolbox.networking.SimpleEmail import kProgressInitialSpacing
from vitaToolbox.networking.SimpleEmail import sendSimpleEmail
from vitaToolbox.wx.TextCtrlUtils import fixSelection

# Local imports...
from appCommon.CommonStrings import kAppName
from appCommon.CommonStrings import kDefaultNotificationSubject


# Constants...
_kDialogTitle = "Set up Email Notification"

_kFromAddrLabelStr = "Send email from:"
_kHostLabelStr = "Outgoing SMTP server:"
_kUserLabelStr = "Login user ID:"
_kPasswordLabelStr = "Login password:"
_kVerifyPasswordLabelStr = "Verify password:"
_kPortLabelStr = "SMTP port number:"
_kEncryptionLabelStr = "Security:"

_kGetTestAddrTitle = "Send Test Message"
_kGetTestAddrPrompt = "Send a test message to the following email address:"

_kFromAddrDescStr = "from address"
_kToAddrDescStr = "to address"
_kHostDescStr = "SMTP Server"
_kUserDescStr = "user ID"
_kPasswordDescStr = "password"
_kBadCharErrorTitleStr = "Illegal Value"
_kBadCharErrorStr = "The '%s' field cannot contain the '%s' character."

_kPasswordsMustMatchStr = "The two password fields must match."
_kPasswordsMustMatchTitleStr = "Error"

_kBadPortErrorTitleStr = "Illegal Port Number"
_kBadPortErrorStr = "Invalid SMTP port number: \"%s\"."
_kNoPortErrorStr = "You must specify an SMTP port number."


_kHelpLabelStr = (
    "These settings can be found at the website of your email provider."
)

_kBadSettingsErrorTitleStr = "Invalid Settings"
_kBadSettingsErrorStr = (
    """You must at least specify a "from" address and a server."""
)
_kEmailSettingsNotCompleteStr = (
    """You must configure an email account to send email responses."""
)

_kLimitMustBeIntegerStr = "The rate limit period must be an integer"


_kNeedToAddrTitleStr = "Please Enter an Address"
_kNeedToAddrStr = "You must enter an address to send a test message to."

_kSendTestMessageStr = "Send Test Message..."

_kEncryptionSettingToLabelMap = {
    kEncryptionNone: "None",
    kEncryptionSsl: "SSL",
    kEncryptionTls: "TLS",
}
_kEncryptionLabelToSettingMap = dict(map(operator.itemgetter(1, 0),
                                         _kEncryptionSettingToLabelMap.items()))
_kEncryptionLabelList = [_kEncryptionSettingToLabelMap[setting]
                         for setting in kEncryptionList]


_kTestProgressTitle = "Sending Test Message"
_kTestErrorTitleStr = "Error Sending"
_kTestErrorStr = "%s"


_kUnknownHostErrorTitleStr = "Problem finding your SMTP server"
_kUnknownHostErrorStr = "SMTP server not found: %s"

_kTestEmailSubject = (
    "%s test message" % (kAppName)
)
_kTestEmailBody = (
    """Congratulations, you have confirmed that you can send messages from """
    """the %s application.\n\n""" % (kAppName)
)
_kTestEmailImageName = "Congratulations.jpg"

_kToAddrLabelStr = "Send email notifications to:"
_kMultipleHelpStr = "You can separate multiple email addresses by commas"
_kRateLimitStr = "Send at most one alert every"
_kInlineImagesStr = "Send images inline, rather than as an attachment"
_kInlineImagesHelp = "Depending on your client this may improve how images are displayed"
_kEmailSubjectLine = "Email subject line"
_kSecondsStr = "seconds"
_kRateLimitHelpStr = "Additional events in this time period will not generate notifications"
_kResolutionLabel = "Maximum dimensions of image attachment:"
_kResolutionHelp = "Warning: Full resolution images may be large in file size"

_kUnlimitedResolution = "Unlimited"
_kResolutionChoices =  [  "320", "640", "960", "1280", _kUnlimitedResolution ]
_kResSettingToIndex = {320 : 0, 640 : 1, 960: 2, 1280:3, 0 : 4}


##############################################################################
class EmailSetupDialog(wx.Dialog):
    """A dialog for setting up email notification."""

    ###########################################################
    def __init__(self, parent, emailConfig, responseConfig):
        """EmailSetupDialog constructor.

        @param  parent             Our parent UI element.
        @param  emailConfig        See BackEndPrefs for details.
        @param  responseConfig     Local settings for this email response.
        """
        # Call our super
        super(EmailSetupDialog, self).__init__(
            parent, title=_kDialogTitle
        )

        try:
            self._responseConfig = responseConfig
            self._oldEmailConfig = emailConfig

            # Create the UI elements
            self._initDialogUiWidgets()
            self._initLocalUiWidgets()
            self._initGlobalUiWidgets()

            self.Fit()
            self.CenterOnParent()

            # Windows will screw up if we set insertion points before the
            # control has been sized - text can be halfway off screen even if
            # there is enough room in the text control.
            self._putEmailConfigToUi(emailConfig)
            self._putLocalSettingsToUi()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _initDialogUiWidgets(self):
        """Init / bind all of the main UI widgets..."""
        # We use the StdDialogButtonSizer(), but yet add some normal buttons
        # too.  I'm not sure if this is intended by wxpython, or if it's
        # kosher UI, but it seems to work and does about what I'd expect.
        buttonSizer = wx.StdDialogButtonSizer()

        self._testMessageButton = wx.Button(self, -1, _kSendTestMessageStr)
        buttonSizer.Add(self._testMessageButton, 0, wx.LEFT | wx.RIGHT, 12)

        self._okButton = wx.Button(self, wx.ID_OK)
        buttonSizer.AddButton(self._okButton)

        self._cancelButton = wx.Button(self, wx.ID_CANCEL)
        buttonSizer.AddButton(self._cancelButton)

        self._okButton.SetDefault()
        buttonSizer.Realize()

        self._notebook = wx.Notebook(self, -1)

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(self._notebook, 1, wx.EXPAND | wx.ALL, 16)
        mainSizer.Add(buttonSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)
        mainSizer.AddSpacer(16)
        self.SetSizer(mainSizer)

        self.Bind(wx.EVT_BUTTON, self.OnTestMessage, self._testMessageButton)
        self.Bind(wx.EVT_BUTTON, self.OnOK, self._okButton)


    ###########################################################
    def _initLocalUiWidgets(self):
        """Init / bind all of the UI widgets controlling local settings..."""
        localPanel = wx.Panel(self._notebook, -1)
        localSizer = wx.BoxSizer(wx.VERTICAL)

        toAddrLabel = wx.StaticText(localPanel, -1, _kToAddrLabelStr,
                style=wx.ST_NO_AUTORESIZE)
        self._toAddrField = wx.TextCtrl(localPanel, -1)
        toHelpLabel = wx.StaticText(localPanel, -1, _kMultipleHelpStr,
                style=wx.ST_NO_AUTORESIZE)
        makeFontDefault(toHelpLabel)

        # Make our top label line up with top label on next tab
        localSizer.AddSpacer(
            max((self._toAddrField.GetSize()[1]-toAddrLabel.GetSize()[1])/2, 0))
        localSizer.Add(toAddrLabel, 0, wx.BOTTOM, 8)
        localSizer.Add(self._toAddrField, 0, wx.EXPAND | wx.BOTTOM, 4)
        localSizer.Add(toHelpLabel, 0, wx.BOTTOM, 12)
        localSizer.AddSpacer(1)

        subjectLabel = wx.StaticText(localPanel, -1, _kEmailSubjectLine,
                style=wx.ST_NO_AUTORESIZE)
        self._subjectField = wx.TextCtrl(localPanel, -1)

        # Make our top label line up with top label on next tab
        localSizer.AddSpacer(
            max((self._subjectField.GetSize()[1]-subjectLabel.GetSize()[1])/2, 0))
        localSizer.Add(subjectLabel, 0, wx.BOTTOM, 8)
        localSizer.Add(self._subjectField, 0, wx.EXPAND | wx.BOTTOM, 4)


        self._rateLimitCheck = wx.CheckBox(localPanel, -1, _kRateLimitStr)
        self._rateLimitSpinner = wx.SpinCtrl(localPanel, -1, "", size=(80, -1))
        self._rateLimitSpinner.SetRange(1, 3600)
        secondsLabel = wx.StaticText(localPanel, -1, _kSecondsStr,
                style=wx.ST_NO_AUTORESIZE)
        rateLimitHelp = wx.StaticText(localPanel, -1, _kRateLimitHelpStr,
                style=wx.ST_NO_AUTORESIZE)
        makeFontDefault(rateLimitHelp)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self._rateLimitCheck, 0, wx.EXPAND )
        hSizer.Add(self._rateLimitSpinner, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 2)
        hSizer.Add(secondsLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        localSizer.Add(hSizer, 0, wx.BOTTOM, 4)
        localSizer.Add(rateLimitHelp, 0, wx.BOTTOM, 12)

        self._sizeChoice = wx.Choice(localPanel, -1, choices=_kResolutionChoices)
        resolutionLabel = wx.StaticText(localPanel, -1, _kResolutionLabel,
                style=wx.ST_NO_AUTORESIZE)
        resolutionHelp = wx.StaticText(localPanel, -1, _kResolutionHelp,
                style=wx.ST_NO_AUTORESIZE)
        makeFontDefault(resolutionHelp)


        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(resolutionLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._sizeChoice, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        localSizer.Add(hSizer, 0, wx.BOTTOM | wx.EXPAND, 4)
        localSizer.Add(resolutionHelp, 0, wx.BOTTOM | wx.EXPAND, 12)

        self._inlineImagesCheck = wx.CheckBox(localPanel, -1, _kInlineImagesStr)
        inlineImagesHelp = wx.StaticText(localPanel, -1, _kInlineImagesHelp,
                style=wx.ST_NO_AUTORESIZE)
        makeFontDefault(inlineImagesHelp)

        localSizer.Add(self._inlineImagesCheck, 0, wx.BOTTOM | wx.EXPAND, 4)
        localSizer.Add(inlineImagesHelp, 0, wx.BOTTOM, 12)


        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(localSizer, 1, wx.EXPAND | wx.ALL, 12)
        localPanel.SetSizer(borderSizer)
        self._notebook.AddPage(localPanel, "Rule Settings")


    ###########################################################
    def _initGlobalUiWidgets(self):
        """Init / bind all of the UI widgets controlling global settings..."""
        globalPanel = wx.Panel(self._notebook, -1)

        fromAddrLabel = wx.StaticText(globalPanel, -1, _kFromAddrLabelStr,
                                      style=wx.ST_NO_AUTORESIZE)
        self._fromAddrField = wx.TextCtrl(globalPanel, -1)
        hostLabel = wx.StaticText(globalPanel, -1, _kHostLabelStr,
                                  style=wx.ST_NO_AUTORESIZE)
        self._hostField = wx.TextCtrl(globalPanel, -1)
        userLabel = wx.StaticText(globalPanel, -1, _kUserLabelStr,
                                  style=wx.ST_NO_AUTORESIZE)
        self._userField = wx.TextCtrl(globalPanel, -1)
        passwordLabel = wx.StaticText(globalPanel, -1, _kPasswordLabelStr,
                                      style=wx.ST_NO_AUTORESIZE)
        self._passwordField = wx.TextCtrl(globalPanel, -1, style=wx.TE_PASSWORD)
        verifyPasswordLabel = wx.StaticText(globalPanel, -1, _kVerifyPasswordLabelStr,
                                            style=wx.ST_NO_AUTORESIZE)
        self._verifyPasswordField = wx.TextCtrl(globalPanel, -1, style=wx.TE_PASSWORD)
        portLabel = wx.StaticText(globalPanel, -1, _kPortLabelStr,
                                  style=wx.ST_NO_AUTORESIZE)

        self._portCtrl = wx.ComboBox(globalPanel, -1, style=wx.CB_DROPDOWN,
                                     choices=kStandardPortList + ['99999'])
        self._portCtrl.SetMinSize(self._portCtrl.GetBestSize())
        self._portCtrl.SetItems(kStandardPortList)

        encryptionLabel = wx.StaticText(globalPanel, -1, _kEncryptionLabelStr,
                                        style=wx.ST_NO_AUTORESIZE)
        self._encryptionChoice = wx.Choice(globalPanel, -1,
                                           choices=_kEncryptionLabelList)

        helpLabel = wx.StaticText(globalPanel, -1, _kHelpLabelStr,
                                  style=wx.ST_NO_AUTORESIZE)

        # Throw things in sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        gridSizer = wx.FlexGridSizer(rows=0, cols=2, vgap=8, hgap=8)
        gridSizer.AddGrowableCol(1)
        gridSizer.Add(fromAddrLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._fromAddrField, 0, wx.EXPAND)
        gridSizer.Add(hostLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._hostField, 0, wx.EXPAND)
        gridSizer.Add(userLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._userField, 0, wx.EXPAND)
        gridSizer.Add(passwordLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._passwordField, 0, wx.EXPAND)
        gridSizer.Add(verifyPasswordLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._verifyPasswordField, 0, wx.EXPAND)
        gridSizer.Add(portLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._portCtrl)
        gridSizer.Add(encryptionLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._encryptionChoice)

        mainSizer.Add(gridSizer, 0, wx.EXPAND)
        mainSizer.Add(helpLabel, 0, wx.TOP, 12)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)

        globalPanel.SetSizer(borderSizer)
        self._notebook.AddPage(globalPanel, "Global Settings")



    ###########################################################
    def getToAddrs(self):
        """Return the "to" addresses.

        @return toAddrs  The "to" addresses alerts should be sent to.
        """
        try:
            return self._toAddrField.GetValue().encode('ascii', 'strict').strip()
        except UnicodeEncodeError, e:
            self._notebook.ChangeSelection(0)
            self._toAddrField.SetFocus()
            self._toAddrField.SetSelection(-1, -1)
            wx.MessageBox(_kBadCharErrorStr % (_kToAddrDescStr,
                                               e.object[e.start:e.start+1]),
                          _kBadCharErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self)
        return None


    ###########################################################
    def getEmailConfig(self, isBlankOk=True):
        """Read out an email configuration dict from our UI.

        @param  isBlankOk    If True, it's OK for settings to be "blank"
        @return emailConfig  See BackEndPrefs for details; may be None if an
                             error was found (and reported to the user).
        """
        # Init email config with the old one.  That way we keep the "To"
        # address if the user used to have one (that's needed for any rules
        # that haven't been updated yet).
        emailConfig = dict(self._oldEmailConfig)

        # Convert to unicode; on failure, give an error and return None.
        try:
            desc = _kFromAddrDescStr
            field = self._fromAddrField
            emailConfig['fromAddr'] = \
                field.GetValue().encode('ascii', 'strict').strip()
            desc = _kHostDescStr
            field = self._hostField
            emailConfig['host'] = \
                field.GetValue().encode('ascii', 'strict').strip()
            desc = _kUserDescStr
            field = self._userField
            emailConfig['user'] = \
                field.GetValue().encode('ascii', 'strict').strip()
            desc = _kPasswordDescStr
            field = self._passwordField
            emailConfig['password'] = \
                field.GetValue().encode('ascii', 'strict').strip()
            desc = _kPasswordDescStr
            field = self._verifyPasswordField
            verifyPassword = field.GetValue().encode('ascii', 'strict').strip()
            emailConfig['imageInline'] = self._inlineImagesCheck.GetValue()
        except UnicodeEncodeError, e:
            assert desc is not None
            self._notebook.ChangeSelection(1)
            field.SetFocus()
            field.SetSelection(-1, -1)
            wx.MessageBox(_kBadCharErrorStr % (desc,
                                               e.object[e.start:e.start+1]),
                          _kBadCharErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self)
            return None

        desc = None

        if emailConfig['password'] != verifyPassword:
            self._verifyPasswordField.SetFocus()
            self._verifyPasswordField.SetValue("")
            wx.MessageBox(_kPasswordsMustMatchStr, _kPasswordsMustMatchTitleStr,
                          wx.OK | wx.ICON_ERROR, self)
            return None

        # Convert the port--it must be an int and within range...
        try:
            emailConfig['port'] = int(self._portCtrl.GetValue().strip())
            if (emailConfig['port'] < 1) or (emailConfig['port'] > 65535):
                raise ValueError()
        except ValueError:
            if self._portCtrl.GetValue():
                wx.MessageBox(_kBadPortErrorStr % (self._portCtrl.GetValue()),
                              _kBadPortErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, self)
            else:
                wx.MessageBox(_kNoPortErrorStr,
                              _kBadPortErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, self)
            return None

        emailConfig['encryption'] = _kEncryptionLabelToSettingMap[
                               self._encryptionChoice.GetStringSelection()]

        # If they've specified something, they must specify fromAddr, toAddr,
        # and host.
        fromAddr = emailConfig['fromAddr']
        host = emailConfig['host']
        user = emailConfig['user']
        password = emailConfig['password']
        if (not isBlankOk) or fromAddr or host or user or password:
            if not (fromAddr and host):
                wx.MessageBox(_kBadSettingsErrorStr, _kBadSettingsErrorTitleStr,
                              wx.OK | wx.ICON_ERROR, self)
                return None

        # If we're here, we're OK...
        return emailConfig


    ###########################################################
    def _putEmailConfigToUi(self, emailConfig):
        """The opposite of _getEmailConfigFromUi.

        @param  emailConfig  See BackEndPrefs for details.
        """
        self._fromAddrField.SetValue(emailConfig.get('fromAddr', ""))
        self._hostField.SetValue(emailConfig.get('host', ""))
        self._userField.SetValue(emailConfig.get('user', ""))
        self._passwordField.SetValue(emailConfig.get('password', ""))
        self._verifyPasswordField.SetValue(emailConfig.get('password', ""))
        self._portCtrl.SetValue(str(emailConfig.get('port', "")))
        self._portCtrl.SetStringSelection(str(emailConfig.get('port', "")))
        self._encryptionChoice.SetStringSelection(
            _kEncryptionSettingToLabelMap[emailConfig.get('encryption', "")]
        )

        # Fix Mac text fields...
        fixSelection(self._fromAddrField, self._hostField, self._userField,
                     self._passwordField, self._verifyPasswordField,
                     self._portCtrl)


    ###########################################################
    def _putLocalSettingsToUi(self):
        """Fill the local settings with the current values."""
        toEmail = self._responseConfig.get('toAddrs', "")
        if not toEmail:
            # We may have an old style rule
            toEmail = self._oldEmailConfig.get('toAddrs', "")
        self._toAddrField.SetValue(toEmail)
        self._toAddrField.SetFocus()
        self._toAddrField.SetInsertionPointEnd()

        self._subjectField.SetValue(
            self._responseConfig.get('subject', kDefaultNotificationSubject))
        self._rateLimitCheck.SetValue(
            self._responseConfig.get('wantLimit', False))
        self._rateLimitSpinner.SetValue(
            int(self._responseConfig.get('limitSeconds', 60)))
        self._rateLimitSpinner.SetSelection(8,8)
        self._inlineImagesCheck.SetValue(
            self._responseConfig.get('imageInline', True))

        res = self._responseConfig.get('maxRes', 320)
        self._sizeChoice.SetSelection(_kResSettingToIndex.get(res, 0))


    ###########################################################
    def OnOK(self, event):
        """Respond to the user pressing OK

        @param  event  The button event
        """
        # Get the email config; if it's completely invalid, we'll get back
        # None (and the user will already have been shown an error message).
        emailConfig = self.getEmailConfig()
        if emailConfig is None:
            return

        to = self.getToAddrs()
        if to is None:
            return

        # We do full validation elsewhere, but if a user has filled out a 'to'
        # address but not even a 'from' or 'host', they probably just skipped
        # the global email config.
        if not emailConfig.get('fromAddr', "") \
                    or not emailConfig.get('host', ""):
            wx.MessageBox(_kEmailSettingsNotCompleteStr,
                _kBadSettingsErrorTitleStr, wx.OK | wx.ICON_ERROR, self)
            self._notebook.ChangeSelection(1)
            return

        limitSeconds = 60
        if self._rateLimitCheck.GetValue():
            try:
                limitSeconds = int(self._rateLimitSpinner.GetValue())
            except:
                wx.MessageBox(_kLimitMustBeIntegerStr,
                    _kBadSettingsErrorTitleStr, wx.OK | wx.ICON_ERROR, self)
                self._notebook.ChangeSelection(0)
                self._rateLimitSpinner.SetFocus()
                return

        self._responseConfig['toAddrs'] = to
        self._responseConfig['subject'] = self._subjectField.GetValue()
        self._responseConfig['wantLimit'] = self._rateLimitCheck.GetValue()
        if self._responseConfig['wantLimit']:
            self._responseConfig['limitSeconds'] = limitSeconds
        maxResStr = self._sizeChoice.GetStringSelection()
        self._responseConfig['maxRes'] = 0 if maxResStr == _kUnlimitedResolution else int(maxResStr)
        self._responseConfig['imageInline'] = self._inlineImagesCheck.GetValue()

        self.EndModal(wx.ID_OK)


    ###########################################################
    def OnTestMessage(self, event):
        """Respond to the user pressing the "Send test message" button.

        @param  event  The button event
        """
        # Get the email config; if it's completely invalid, we'll get back
        # None (and the user will already have been shown an error message).
        emailConfig = self.getEmailConfig(False)
        if emailConfig is None:
            return

        # Get the "to" addresses...
        to = self._toAddrField.GetValue()
        dlg = wx.TextEntryDialog(self, _kGetTestAddrPrompt, _kGetTestAddrTitle,
                                 to)
        try:
            while True:
                result = dlg.ShowModal()

                # If they cancel, bail...
                if result != wx.ID_OK:
                    return

                # Get the TO address out, and make sure it's ASCII.  If not,
                # show an error message and loop...
                try:
                    to = dlg.GetValue().encode('ascii', 'strict')
                except UnicodeEncodeError, e:
                    wx.MessageBox(_kBadCharErrorStr % (
                                  _kToAddrDescStr, e.object[e.start:e.start+1]),
                                  _kBadCharErrorTitleStr,
                                  wx.OK | wx.ICON_ERROR, self)
                    continue

                # If no TO address, show a message and loop...
                if not to:
                    wx.MessageBox(_kNeedToAddrStr, _kNeedToAddrTitleStr,
                                  wx.OK | wx.ICON_ERROR, self)
                    continue

                # All good, break...
                break
        finally:
            dlg.Destroy()

        progressDlg = \
            wx.ProgressDialog(_kTestProgressTitle, kProgressInitialSpacing,
                              kNumProgressSteps, self, wx.PD_APP_MODAL |
                              wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT)

        testImg = Image.open("frontEnd/bmps/Notification_Test.jpg")
        try:
            # Just return the "continue" part of the progress dialog update...
            progressFn = lambda value, msg: progressDlg.Update(value, msg)[0]

            sendSimpleEmail(_kTestEmailBody, emailConfig['fromAddr'],
                            to, _kTestEmailSubject,
                            emailConfig['host'], emailConfig['user'],
                            emailConfig['password'], emailConfig['port'],
                            emailConfig['encryption'],
                            [(_kTestEmailImageName, testImg)], [],
                            progressFn,
                            False,
                            None,
                            emailConfig.get('textInline', False),
                            emailConfig.get('imageInline', True) )
            progressDlg.Destroy()
        except socket.gaierror:
            progressDlg.Destroy()
            wx.MessageBox(_kUnknownHostErrorStr % emailConfig['host'],
                          _kUnknownHostErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self)
        except Exception, e:
            progressDlg.Destroy()

            # Default: just use string version of error...
            msg = str(e)

            # Some nicer error messages for certain types of errors...
            if isinstance(e, socket.error):
                try:   msg = e.args[1] #PYCHECKER OK: OK, checked type
                except Exception: pass
            elif isinstance(e, smtplib.SMTPAuthenticationError):
                msg = e.smtp_error #PYCHECKER OK: OK, checked type

            wx.MessageBox(_kTestErrorStr % msg, _kTestErrorTitleStr,
                          wx.OK | wx.ICON_ERROR, self)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    # Ugly test code...
    from BackEndClient import BackEndClient

    app = wx.PySimpleApp(redirect=False)
    app.SetAppName(kAppName)

    backEndClient = BackEndClient()
    didConnect = backEndClient.connect()
    assert didConnect

    emailSettings = backEndClient.getEmailSettings()
    dlg = EmailSetupDialog(None, emailSettings, {})
    try:
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            backEndClient.setEmailSettings(dlg.getEmailConfig())
    finally:
        dlg.Destroy()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
