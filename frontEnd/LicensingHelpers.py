#!/usr/bin/env python

#*****************************************************************************
#
# LicensingHelpers.py
#
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Arden.ai, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Arden.ai, Inc.
# by emailing opensource@ardenai.com
#
# This file is part of the Arden AI project which can be found at
# https://github.com/ardenaiinc/ArdenAI
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

# Common 3rd-party imports...
import wx

# Local imports...
from appCommon.LicenseUtils import kCamerasField, kStarterEdition
from appCommon.CommonStrings import kAppName
from appCommon.CommonStrings import kVersionString
from appCommon.CommonStrings import kMajorVersionString
from LicenseDialog import doShowLicenseDialog


# Constants...
_kMessageWrapWidth = 480
_kActivateLicenseId = wx.NewId()

# When you add a wx.StdDialogButtonSizer, you need different borders
# on Mac vs. PC.
if wx.Platform == '__WXMAC__':
    _kButtonSizerBorders = (wx.LEFT | wx.TOP | wx.BOTTOM)
else:
    _kButtonSizerBorders = wx.ALL

_kActivateLicense = "Buy or activate license..."

_kBuyUpgradePling2 = (
"""\n\n"""
"""To add more cameras you will need to upgrade or activate an existing """
"""license or purchase a new license."""
)

_kAtMaxCamerasLabel = (
"""You are using the maximum number of cameras allowed by your license.%s"""
) % (_kBuyUpgradePling2)

_kBuyUpgradePling3 = (
"""\n\nTo save at higher resolutions you will need to upgrade or activate """
"""an existing license or purchase a new license."""
)

_kMaxResLabel = (
"""Your license supports saving at a maximum resolution of %s.%s"""
)

_kLicenseInformationTitle = "License Information"

_kCamerasFrozenTitle = "Maximum Cameras Exceeded"
_kCamerasFrozenText = (
"""You have more configured cameras than your license allows so some have """
"""disabled. To restore these cameras purchase, activate, or upgrade a """
"""license or delete one of the currently enabled cameras.""")



##############################################################################
def getLicense(backEndClient, uiParent=None, timeout=0):
    """Get a dictionary describing a valid license to run the app.

    @param  backEndClient  A client for accessing the back end; may be None,
                           in which case we won't check # of cameras.
    @param  uiParent       The parent for any UI we show; or None (for
                           top-level parent) (Unused)
    @param  timeout        Time to wait in seconds for license data to show up.
    @return licDict        A dictionary describing the license.  The
                           "Signature" element is the signature; other elements
                           are things like "Expires", "Name", "Email", ...
                           MAY BE None if user doesn't pick a valid license.
    """
    return backEndClient.getLicenseData(timeout)


##############################################################################
def checkForMaxCameras(backEndClient, uiParent, numPendingCameras=0):
    """Show the "at maximum cameras" dialog if needed.

    IMPORTANT NOTE: This may change the license.

    @param  backEndClient      A client for accessing the back end.
    @param  uiParent           The parent for any UI we show; or None.
    @param  numPendingCameras  This many cameras are pending, so should be
                               considered as configured cameras.
    @return isAtMax            True if we're still at max after any UI finished.
    """
    # Loop, since "activate license" may change license, and we want to re-load
    # and re-show...
    while True:
        # This will get a license that is currently valid for configured cams
        # (not including pending cameras), or None...
        lic = getLicense(backEndClient)

        # If we're under, no need for any UI...
        numCamsAllowed = int(lic[kCamerasField])
        numCamsConfigured = len(backEndClient.getCameraLocations()) + \
                            numPendingCameras
        if (numCamsAllowed == -1) or (numCamsConfigured < numCamsAllowed):
            return False

        # We're over or at max, so show UI...
        dlg = _GenericLicenseMessageDialog(uiParent, -1,
                                           _kLicenseInformationTitle,
                                           _kAtMaxCamerasLabel)
        try:
            result = dlg.ShowModal()
        finally:
            dlg.Destroy()

        # If OK, we're done; if "activate", the user wants to choose one.
        if (result == wx.ID_OK) or (result == wx.ID_CANCEL):
            # If user hit "OK", they're just accepting that they're at max...
            return True
        else:
            assert result == _kActivateLicenseId
            doShowLicenseDialog(uiParent, backEndClient)


##############################################################################
def showResolutionWarning(uiParent, maxResStr, backEndClient):
    """Show the "resolution invalid" dialog.

    @param  uiParent       The parent for the dialog.
    @param  maxResStr      The maximum resolution supported by the license.
    @param  backEndClient  A BackEndClient instance.
    """
    dialogText = _kMaxResLabel % (maxResStr, _kBuyUpgradePling3)
    dlg = _GenericLicenseMessageDialog(uiParent, -1, _kLicenseInformationTitle,
            dialogText);
    try:
        result = dlg.ShowModal()
    finally:
        dlg.Destroy()

    # If OK, we're done; if "activate", the user wants to choose one.
    if (result == wx.ID_OK) or (result == wx.ID_CANCEL):
        return
    else:
        assert result == _kActivateLicenseId
        doShowLicenseDialog(uiParent, backEndClient)


##############################################################################
def showHiddenCamsWarning(uiParent, backEndClient):
    dlg = _GenericLicenseMessageDialog(uiParent, -1, _kCamerasFrozenTitle,
            _kCamerasFrozenText);
    try:
        result = dlg.ShowModal()
    finally:
        dlg.Destroy()

    # If OK, we're done; if "activate", the user wants to choose one.
    if (result == wx.ID_OK) or (result == wx.ID_CANCEL):
        return
    else:
        assert result == _kActivateLicenseId
        doShowLicenseDialog(uiParent, backEndClient)



##############################################################################
class _GenericLicenseMessageDialog(wx.Dialog):
    """A dialog showing a message to the user with license-related buttons.

    Can return the following from ShowModal:
    - wx.ID_OK
    - _kActivateLicenseId

    The "Buy Upgrade..." button is handled internally in this dialog.
    """

    ###########################################################
    def __init__(self, parent, uid, title, label):
        """_GenericLicenseMessageDialog constructor.

        @param  parent  Our UI parent.
        @param  uid     Our UI id.
        @param  label   The label to show.  Will be wrapped.
        """
        super(_GenericLicenseMessageDialog, self).__init__(
            parent, uid, title
        )

        try:
            messageLabel = wx.StaticText(self, -1, label)
            messageLabel.Wrap(_kMessageWrapWidth)
            messageLabel.SetMinSize((_kMessageWrapWidth, -1))

            # We use the StdDialogButtonSizer(), but yet add some normal buttons
            # too.  I'm not sure if this is intended by wxpython, or if it's
            # kosher UI, but it seems to work and does about what I'd expect.
            buttonSizer = wx.StdDialogButtonSizer()

            activateLicenseButton = wx.Button(self, _kActivateLicenseId,
                                              _kActivateLicense)
            buttonSizer.Add(activateLicenseButton, 0, wx.ALIGN_CENTER_VERTICAL |
                            wx.RIGHT, 12)

            okButton = wx.Button(self, wx.ID_OK)
            buttonSizer.AddButton(okButton)

            okButton.SetDefault()
            okButton.SetFocus()
            buttonSizer.Realize()

            # Throw things in sizers...
            mainSizer = wx.BoxSizer(wx.VERTICAL)
            mainSizer.Add(messageLabel, 0, wx.ALL, 12)
            mainSizer.Add(buttonSizer, 0, wx.EXPAND | _kButtonSizerBorders, 12)

            self.SetSizer(mainSizer)

            activateLicenseButton.Bind(wx.EVT_BUTTON, self.OnEndModalButton)

            self.Fit()
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ##############################################################################
    def OnEndModalButton(self, event):
        """Handles all events by ending the modal dialog w/ event object's ID.

        @param  event  The event.
        """
        button = event.GetEventObject()
        dlg = button.GetParent()
        dlg.EndModal(button.GetId())


##############################################################################
def canImport(backEndClient, uiParent, noUi=False):
    """Checks to see if we can import with the current license.

    @param  backEndClient       A client for the back end; may be None.
    @param  uiParent            A UI parent in case we need to prompt for a new
                                license; may be None.
    @param  noUi                If True, we'll never show UI; if problems
                                reading the license, we default to False.
    @return canImport           True if user can import
    """
    return False

##############################################################################

_kPaddingSize = 4
_kBorderSize = 16

_kHelpText = (
"""License "%s" is not valid for use with version %s of %s. Your support """
"""and upgrades subscription expired %d days before version %s was released."""
"""\n\nPlease select one of the following options to continue:"""
)

_kTargetWidth = 520


_kOptionRenew = "Renew your support and upgrades subscription"
_kOptionReset = "Run version %s using a %s license" % (kVersionString,
        kStarterEdition)
_kOptionQuit =  "Make no changes and exit %s" % kAppName


kSupportExpiredChoiceRenew = "renew"
kSupportExpiredChoiceQuit = "quit"
kSupportExpiredChoiceStarter = "starter"

###############################################################################
class SupportExpiredDialog(wx.Dialog):
    """A simple dialog for showing that the support of a license expired and
    the user has to decide how to continue."""

    ###########################################################
    def __init__(self, parent, serial, expiredSeconds):
        """Constructor.

        @param  parent          The parent window.
        @param  serial          Serial number of license.
        @param  expiredSeconds  Number of seconds since expiration.
        """
        wx.Dialog.__init__(self, parent, -1, kAppName,
                style=wx.DEFAULT_DIALOG_STYLE & ~wx.CLOSE_BOX, size=(400, -1))

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self._choice = kSupportExpiredChoiceQuit

        try:
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)

            expiredDays = max(1, int(expiredSeconds / (3600*24)))
            helpText = _kHelpText % (serial, kVersionString, kAppName,
                    expiredDays, kMajorVersionString)
            textHelp = wx.StaticText(self, -1, helpText)

            self._rbtnReset = wx.RadioButton(self, -1, _kOptionReset,
                                             style=wx.RB_GROUP)
            self._rbtnQuit = wx.RadioButton(self, -1, _kOptionQuit)
            self._rbtnRenew = wx.RadioButton(self, -1, _kOptionRenew)
            self._rbtnRenew.SetValue(True)

            textHelp.Wrap(max(_kTargetWidth,
                              self._rbtnReset.GetBestSize()[0],
                              self._rbtnQuit.GetBestSize()[0],
                              self._rbtnRenew.GetBestSize()[0]))

            sizer.Add(textHelp, 0, wx.ALL, _kBorderSize)
            sizer.Add(self._rbtnRenew, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._rbtnReset, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kPaddingSize)
            sizer.Add(self._rbtnQuit, 0, wx.LEFT | wx.RIGHT, _kBorderSize)

            sizerButtons = self.CreateStdDialogButtonSizer(wx.OK)
            sizer.Add(sizerButtons, 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 16)

            self.FindWindowById(wx.ID_OK, self).SetDefault()
            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOk)

            self.SetEscapeId(wx.ID_NONE)

            self.Fit()
            self.CenterOnParent()

        except:
            self.Destroy()
            raise


    ###########################################################
    def GetChoiceSelection(self):
        """ Get the choice made by the user.

        @return  choice  The choice made by the user; return value will be
                         'renew', 'quit', or 'starter'.
        """
        return self._choice


    ###########################################################
    def OnClose(self, event=None):
        """ Called if the dialog closes through another way than [OK].

        @param  event  The close event.
        """
        self.EndModal(wx.OK)


    ###########################################################
    def OnOk(self, event=None):
        """ Called if the [OK] button is clicked.

        @param  event  The button event.
        """
        if self._rbtnRenew.GetValue():
            self._choice = kSupportExpiredChoiceRenew
        elif self._rbtnQuit.GetValue():
            self._choice = kSupportExpiredChoiceQuit
        elif self._rbtnReset.GetValue():
            self._choice = kSupportExpiredChoiceStarter
        self.Close()
