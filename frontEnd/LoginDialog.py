#!/usr/bin/env python

#*****************************************************************************
#
# LoginDialog.py
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
import time
import webbrowser
import re

# Common 3rd-party imports...
import wx

# Local imports...
from appCommon.LicenseUtils import kNoValueToken
from appCommon.LicenseUtils import kSerialField
from appCommon.LicenseUtils import isLegacyLicense
from appCommon.LicenseUtils import kStarterEdition
from appCommon.LicenseUtils import kEditionField
from appCommon.LicenseUtils import legacyEndOfLife
from appCommon.CommonStrings import kAboutAccountsUrl
from appCommon.CommonStrings import kCreateAccountUrl
from appCommon.CommonStrings import kForgotPassUrl
from appCommon.CommonStrings import kLoginStatusLastUser
from BackEndClient import LicenseBackEndClient
from vitaToolbox.wx.DelayedProgressDialog import DelayedProgressDialog
from vitaToolbox.wx.FontUtils import makeFontNotUnderlined
from vitaToolbox.wx.TextCtrlUtils import setHyperlinkColors


_kTitle = "Sign In"

_kErrorText = (
"""There was a problem authenticating your Sighthound account. """
"""Please enter your email address and password to sign in again."""
)


_kLegacyPaidAction = "."
_kLegacyStarterAction = " and claim your free Pro trial."

_kWelcomeTextLegacy = (
"""Sighthound Video now requires a Sighthound Account. This system allows """
"""for easier license storage, activation, upgrades, and will enable the """
"""addtion of many new features going forward. You must create an account """
"""to continue receiving application updates"""
)


_kEmptyFieldErrorTitle = "Error"
_kEmptyFieldError = (
"""You must fill out both the email address and password fields before """
"""signing in.""")
_kInvalidEmailError = (
"""Please enter a valid e-mail address.""")

_kConnectingTitle = "Signing In"
_kConnectingContent = "Connecting to the server..."

_kSignInErrorTitle = "Error"
_kSignInError = (
"""There was an error signing you in. Please verify your email address and """
"""password and try again.""")

_kAboutAccountsTextA = "For more information about accounts click "
_kAboutAccountsTextB = "here"
_kAboutAccountsTextC = "."
_kForgotPasswordText = "Forgot Password?"
_kCreateAccountText = "Create Account"
_kErrorSkipText = "Remind Me Later"
_kLogInText = "Sign In"

_kMessageWrap = 500
_kTextFieldWidth = 300

_kEmailLabel = "Email address:"
_kPasswordLabel = "Password:"

_kPadding = 16

_kConnectCheckIntervalSec = .1
_kMaxConnectRetries = 30/_kConnectCheckIntervalSec

_kEMailRegex = re.compile('^[0-9a-zA-Z._%+-]+@[0-9a-zA-Z.-]+\.[a-zA-Z]{2,63}$')

##############################################################################
def getLicenseMoreInfoSizer(parent):
    """Return a box sizer containing 'more info' text and hyperlink.

    @param  parent The parent control.
    """
    aboutLink = wx.adv.HyperlinkCtrl(parent, -1, _kAboutAccountsTextB, kAboutAccountsUrl)
    setHyperlinkColors(aboutLink)
    makeFontNotUnderlined(aboutLink)

    aboutSizer = wx.BoxSizer(wx.HORIZONTAL)
    aboutSizer.Add(wx.StaticText(parent, -1, _kAboutAccountsTextA))
    aboutSizer.Add(aboutLink)
    aboutSizer.Add(wx.StaticText(parent, -1, _kAboutAccountsTextC))

    return aboutSizer


##############################################################################
class LoginDialog(wx.Dialog):
    """A dialog allowing the user to associate a user account.

    Returns wx.OK if an account is successfully added, a legacy user cancels,
    or a user in need of re-authentication cancels.

    All other return values indicate that the app should exit.
    """

    ###########################################################
    def __init__(self, parent, backEndClient, isReauth=False):
        """LoginDialog constructor.

        @param  parent         Our UI parent.
        @param  backEndClient  A communication channel to the back end.
        @param  isReauth       True if this is a re-authentication. Will present
                               error text rather than welcome UI, and the dialog
                               will be canceleable.
        """
        super(LoginDialog, self).__init__(parent, -1, _kTitle)

        try:
            self._backEndClient = backEndClient
            self._licenseClient = LicenseBackEndClient(backEndClient)
            self._license = backEndClient.getLicenseData()
            self._isLegacy = isLegacyLicense(self._license)
            self._isReauth = isReauth

            self.Bind(wx.EVT_CLOSE, self.OnClose)

            if not self._isReauth:
                welcomeBmp = wx.Bitmap("frontEnd/bmps/Login_welcome.png")
                welcome = wx.StaticBitmap(self, -1, welcomeBmp)

            label = None
            if self._isReauth:
                label = wx.StaticText(self, -1, _kErrorText)
            elif self._isLegacy:
                action = _kLegacyPaidAction
                if self._license[kEditionField] == kStarterEdition:
                    action = _kLegacyStarterAction
                label = wx.StaticText(self, -1, _kWelcomeTextLegacy + action)

            if label:
                label.Wrap(_kMessageWrap)
                label.SetMinSize((_kMessageWrap, -1))

            userLabel = wx.StaticText(self, -1, _kEmailLabel)
            self._userField = wx.TextCtrl(self, -1, size=(_kTextFieldWidth, -1))
            user = backEndClient.getLoginStatus()[kLoginStatusLastUser]
            if user:
                self._userField.SetValue(user)
            passLabel = wx.StaticText(self, -1, _kPasswordLabel)
            self._passField = wx.TextCtrl(self, -1, style=wx.TE_PASSWORD,
                size=(_kTextFieldWidth, -1))
            self._userField.Bind(wx.EVT_TEXT, self.OnText)
            self._passField.Bind(wx.EVT_TEXT, self.OnText)

            forgotPassLink = wx.adv.HyperlinkCtrl(self, -1, _kForgotPasswordText, kForgotPassUrl)
            setHyperlinkColors(forgotPassLink)
            makeFontNotUnderlined(forgotPassLink)

            createAccountButton = wx.Button(self, -1, _kCreateAccountText)
            createAccountButton.Bind(wx.EVT_BUTTON, self.OnCreateAccount)
            self._logInButton = wx.Button(self, -1, _kLogInText)
            self._logInButton.Bind(wx.EVT_BUTTON, self.OnLogIn)
            self._logInButton.SetDefault()
            self._logInButton.Disable()

            # Fill the field sizer
            fieldSizer = wx.BoxSizer(wx.VERTICAL)
            gridSizer = wx.FlexGridSizer(rows=0, cols=2, vgap=_kPadding/2,
                    hgap=4)
            gridSizer.Add(userLabel, 0, wx.ALIGN_CENTER_VERTICAL)
            gridSizer.Add(self._userField)
            gridSizer.Add(passLabel, 0, wx.ALIGN_CENTER_VERTICAL)
            gridSizer.Add(self._passField)
            fieldSizer.Add(gridSizer)
            fieldSizer.AddSpacer(4)
            fieldSizer.Add(forgotPassLink, 0, wx.ALIGN_RIGHT)

            # Fill the button sizer.
            buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
            buttonSizer.Add(createAccountButton, 0, wx.ALIGN_CENTER)
            if self._isReauth:
                createAccountButton.Hide()
            buttonSizer.AddStretchSpacer(1)
            if self._isLegacy:
                self.SetEscapeId(wx.ID_NONE)
            if self._isReauth:
                skipButton = wx.Button(self, wx.ID_CANCEL, _kErrorSkipText)
                buttonSizer.Add(skipButton, 0, wx.ALIGN_CENTER | wx.RIGHT,
                        _kPadding)
                skipButton.Bind(wx.EVT_BUTTON, self.OnClose)
            buttonSizer.Add(self._logInButton, 0, wx.ALIGN_CENTER)

            # Add everything to the main sizer.
            mainSizer = wx.BoxSizer(wx.VERTICAL)
            if not self._isReauth:
                mainSizer.Add(welcome, 0, wx.ALIGN_CENTER)
            if label:
                mainSizer.Add(label, 0,
                    wx.ALIGN_CENTER | wx.TOP | wx.RIGHT | wx.LEFT, 2*_kPadding)
            if self._isLegacy:
                # Add an about link for legacy users to explain licenses.
                aboutSizer = getLicenseMoreInfoSizer(self)
                mainSizer.AddSpacer(_kPadding)
                mainSizer.Add(aboutSizer, 0, wx.ALIGN_LEFT | wx.LEFT, 2*_kPadding)

            mainSizer.Add(fieldSizer, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 2*_kPadding)
            mainSizer.Add(buttonSizer, 0,wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, _kPadding)

            self.SetSizer(mainSizer)
            self.Fit()
            self.CenterOnParent()

        except:
            self.Destroy()
            raise


    ###########################################################
    def OnCreateAccount(self, event):
        """Handle a click of the create account button.

        @param  event The button event.
        """
        webbrowser.open(kCreateAccountUrl)


    ###########################################################
    def OnText(self, event=None):
        """Enable or disable the log in button in response to a text event

        @param  event  The EVT_TEXT event, ignored.
        """
        self._logInButton.Enable(len(self._userField.GetValue()) and
                len(self._passField.GetValue()))


    ###########################################################
    def OnLogIn(self, event):
        """Handle a log in request.

        @param  event The log in button click
        """
        email = self._userField.GetValue().strip()
        password = self._passField.GetValue()

        # Ensure the user entered an email and password.
        if not email or not len(email) or not password or not len(password):
            wx.MessageBox(_kEmptyFieldError, _kEmptyFieldErrorTitle,
                wx.OK | wx.ICON_ERROR, self)
            return

        # Check if the e-mail address looks valid.
        if not _kEMailRegex.match(email):
            wx.MessageBox(_kInvalidEmailError, _kEmptyFieldErrorTitle,
                wx.OK | wx.ICON_ERROR, self)
            return

        # Attempt to log in.
        result = None
        dlg = DelayedProgressDialog(1, _kConnectingTitle, _kConnectingContent,
                parent=self, style=wx.PD_APP_MODAL)
        try:
            self._licenseClient.login(email, password)

            for _ in xrange(0, int(_kMaxConnectRetries)):
                result = self._licenseClient.loginComplete(
                        _kConnectCheckIntervalSec)
                if result is not None:
                    break
        finally:
            dlg.Destroy()

        if result and result[0]:
            # On success close the dialog.
            self.EndModal(wx.OK)
            return

        # Display an error dialog and ask the user to verify their info.
        wx.MessageBox(_kSignInError, _kSignInErrorTitle,
                wx.OK | wx.ICON_ERROR, self)


    ###########################################################
    def OnClose(self, event):
        """Handle a close event.

        @param  event The close event.
        """
        if self._isLegacy or self._isReauth:
            # If we're legacy, the app can continue running without a log in.
            self.EndModal(wx.OK)
            return

        self.EndModal(wx.CANCEL)

