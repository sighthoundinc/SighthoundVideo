#!/usr/bin/env python

#*****************************************************************************
#
# LicenseDialog.py
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
import urllib
import webbrowser
import sys, traceback

# Common 3rd-party imports...
import wx

# Local imports...
from appCommon.CommonStrings import kBuyNewUrl
from appCommon.CommonStrings import kBuyUpgradeUrl
from appCommon.CommonStrings import kSupportEmail
from appCommon.CommonStrings import kMajorVersionFirstReleaseDate, kMajorVersionFirstReleaseDateDisplay
from appCommon.CommonStrings import kMajorVersionString
from appCommon.LicenseUtils import isLegacyLicense
from appCommon.LicenseUtils import kExpiresField
from appCommon.LicenseUtils import kBasicEdition
from appCommon.LicenseUtils import kEditionField
from appCommon.LicenseUtils import kNameField
from appCommon.LicenseUtils import kSupportField
from appCommon.LicenseUtils import kCamerasField
from appCommon.LicenseUtils import kSerialField
from appCommon.LicenseUtils import kStarterEdition
from appCommon.LicenseUtils import kTrialEdition
from appCommon.LicenseUtils import kAvailableInfo
from appCommon.LicenseUtils import kNoValueToken
from appCommon.LicenseUtils import kDefaultUser
from appCommon.LicenseUtils import kDefaultSerial
from appCommon.LicenseUtils import licenseValidForAppVersion
from BackEndClient import LicenseBackEndClient
from LoginDialog import getLicenseMoreInfoSizer
from vitaToolbox.wx.DelayedProgressDialog import DelayedProgressDialog
from vitaToolbox.wx.FontUtils import adjustPointSize
from vitaToolbox.wx.FontUtils import makeFontBold
from vitaToolbox.wx.ListBoxWithIcons import kThemeBrushAlternatePrimaryHighlightColor
from vitaToolbox.wx.ListBoxWithIcons import kThemeBrushSecondaryHighlightColor
from vitaToolbox.wx.TruncateText import truncateText
from vitaToolbox.sysUtils.TimeUtils import formatTime

# License list draw variables
_kHeaderHeight = 30
_kItemHeight = 30
_kItemXOffset = 5
_kItemYOffset = 6
_kSerialOffset = _kItemXOffset
_kSerialWidth = 180
_kEditionOffset = _kSerialWidth+_kSerialOffset+_kItemXOffset
_kEditionWidth = 140
_kCamsOffset = _kEditionOffset+_kEditionWidth+_kItemXOffset
_kCamsWidth = 80
_kSupportOffset = _kCamsOffset+_kCamsWidth+_kItemXOffset
_kSupportWidth = 100
_kExpiresOffset = _kSupportOffset+_kSupportWidth+_kItemXOffset
_kExpiresWidth = 100
_kAvailableOffset = _kExpiresOffset+_kExpiresWidth+_kItemXOffset
_kAvailableWidth = 100
_kActivePaddingY = 3
_kActiveRadius = (_kItemHeight-2*_kActivePaddingY)/2
_kActivePaddingX = _kActiveRadius

if wx.Platform == '__WXMSW__':
    _kItemFontSize = 10
    _kHeaderFontSize = 10
    _kStatusFontSize = 13
else:
    _kItemFontSize = 13
    _kHeaderFontSize = 13
    _kStatusFontSize = 16

_kHeaderBackgroundA = (236, 236, 236)
_kHeaderBackgroundB = (255, 255, 255)
_kSelectionBackground = (60, 119, 212)

_kLicenseListMinSize = (_kAvailableOffset+_kAvailableWidth+20, _kItemHeight*7.5)

# Main dialog strings
_kTitle = "License Information"

_kPurchaseLabel =      "Purchase New License"
_kBuyUpgradeLabel =    "Upgrade"
_kUnlinkLicenseLabel = "Unlink"
_kUseLicenseLabel =    "Activate"

# List header text
_kHeaderSerial =  "Serial Number"
_kHeaderEdition = "Edition"
_kHeaderCameras = "Cameras"
_kHeaderSupport = "Support Exp."
_kHeaderExpires = "License Exp."
_kHeaderCanUse =  "Can Activate"

# String substitutions
_kNoExpirationText = "Never"
_kNAText = "-"
_kUnlimitedText = "Unlimited"
_kAvailableText = "Yes"
_kUnavailableText = "No"
_kActiveText = "Active"


_kStatusEditionText = "Sighthound Video %s"
_kStatusUserText = "Licensed To: %s"
_kStatusSerialText = "Serial Number: %s"
_kLicenseErrorText = "Current license could not be loaded."
_kLoadingText = "Loading..."

_kAcquiringProgTitle = "Acquiring License"
_kAcquiringContent = "Contacting server, just a moment..."
_kUnlinkingProgTitle = "Unlinking License"
_kUnlinkingContent = "Contacting server, just a moment..."


# Information text
_kLegacyWarning = (
"""Note: You are currently using a legacy license. You must create a """
"""Sighthound Account and activate a license below to continue """
"""receiving updates. Paid licenses should be linked and activated """
"""automatically after signing in but can also be manually linked in your """
"""account page at https://www.sighthound.com.""")

_kCantActivate = (
"""This license cannot be automatically transferred to this machine. """
"""Please contact %s for more information.""" % kSupportEmail)

_kVersionMismatch = (
"""The Support and Upgrades subscription for this license expired before """
"""the release of %s on %s. Please renew or download an earlier version of """
"""the application to use this license. For more information contact %s."""
% (kMajorVersionString, kMajorVersionFirstReleaseDateDisplay, kSupportEmail))

_kConfirmActivateTitle = "Confirm License Activation"
_kConfirmActivate = (
"""Activating this license will remove it from the machine it is currently """
"""installed on (if any) and revert that instance to Starter Edition. """
"""Activate?""")

_kActivateErrorTitle = "License Error"
_kActivateError = (
"""The selected license could not be activated, please try again. If trouble """
"""persists contact %s for assistance.""" % kSupportEmail)

_kUnlinkErrorTitle = "License Error"
_kUnlinkError = (
"""The current license could not be unlinked, please try again. If trouble """
"""persists contact %s for assistance.""" % kSupportEmail)

_kConfirmUnlinkTitle = "Confirm License Unlink"
_kConfirmUnlink = (
"""Unlinking this license will allow it to be activated on a different """
"""computer and this instance will be downgraded to the Starter Edition. """
"""Unlink?""")

_kConfirmLogoutTitle = "Account Disconnect"
_kConfirmLogout = (
"""Disconnecting your Sighthound account will unlink any activated license """
"""and prevent you from using the application until you have signed in """
"""again. Are you sure you would like to disconnect your current account?""")


_kPadding = 8
_kSecsPerDay = 60*60*24

_kRefreshPendingInterval = 333
_kRefreshRetryInterval = 30*1000
_kMaxRefreshCount = 15*60*1000/_kRefreshRetryInterval
_kAcquirePendingIntervalSec = .1
_kMaxAcquireRetries = 60/_kAcquirePendingIntervalSec
_kUnlinkPendingIntervalSec = .1
_kMaxUnlinkRetries = 60/_kUnlinkPendingIntervalSec



##############################################################################
def doShowLicenseDialog(parent, backEndClient):
    """Show the License Dialog.

    @param  parent         The UI parent for the dialog.
    @param  backEndClient  A BackEndClient instance.
    """
    dlg = LicenseDialog(parent, backEndClient)
    try:
        _ = dlg.ShowModal()
    finally:
        dlg.Destroy()


##############################################################################
class LicenseDialog(wx.Dialog):
    """A dialog allowing the user to associate a user account."""

    ###########################################################
    def __init__(self, parent, backEndClient):
        """LicenseDialog constructor.

        @param  parent         Our UI parent.
        @param  backEndClient  A BackEndClient instance.
        """
        super(LicenseDialog, self).__init__(parent, -1, _kTitle)

        try:
            self._backEndClient = backEndClient
            self._licenseClient = LicenseBackEndClient(backEndClient)

            self._license = None

            self._refreshCount = 0
            self._refreshPending = False
            self._refreshTimer = wx.Timer(self, -1)

            self.Bind(wx.EVT_TIMER, self.OnRefreshTimer, self._refreshTimer)
            self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

            # Icon and user information/messages/blah
            badgeBmp = wx.Bitmap("frontEnd/bmps/Sighthound_Badge.png")
            badge = wx.StaticBitmap(self, -1, badgeBmp)
            badge.Bind(wx.EVT_CONTEXT_MENU, self.OnBadgeMenu)
            self._statusEditionLabel = wx.StaticText(self, -1, " ")
            self._statusUserLabel = wx.StaticText(self, -1, " ")
            self._statusSerialLabel = wx.StaticText(self, -1, " ")
            adjustPointSize(self._statusEditionLabel, 1.6)
            adjustPointSize(self._statusUserLabel, 1.2)
            adjustPointSize(self._statusSerialLabel, 1.2)
            makeFontBold(self._statusEditionLabel)
            topSizer = wx.BoxSizer(wx.HORIZONTAL)
            statusSizer = wx.BoxSizer(wx.VERTICAL)
            statusSizer.Add(self._statusEditionLabel, 0, wx.EXPAND)
            statusSizer.Add(self._statusUserLabel, 0, wx.EXPAND | wx.TOP,
                    _kPadding)
            statusSizer.Add(self._statusSerialLabel, 0, wx.EXPAND | wx.TOP,
                    _kPadding)
            topSizer.Add(badge, 0, wx.RIGHT, 2*_kPadding)
            topSizer.Add(statusSizer, 0, wx.ALIGN_CENTER_VERTICAL)

            # Notifications for legacy users
            # FIXME: Remove after legacy expiration date
            self._legacyWarning = wx.StaticText(self, -1, _kLegacyWarning)
            self._legacyWarning.Wrap(_kLicenseListMinSize[0])
            self._legacyLink = getLicenseMoreInfoSizer(self)
            self._legacySizer = wx.BoxSizer(wx.VERTICAL)
            self._legacySizer.Add(self._legacyWarning, 0, wx.EXPAND)
            self._legacySizer.Add(self._legacyLink, 0, wx.EXPAND | wx.TOP,
                    _kPadding)
            textSizer = wx.BoxSizer(wx.VERTICAL)
            textSizer.Add(topSizer, 0, wx.EXPAND | wx.TOP, 2*_kPadding)
            textSizer.Add(self._legacySizer, 0, wx.EXPAND | wx.TOP, 2*_kPadding)

            # The license list view
            licenseListBorder = wx.Panel(self, style=wx.SIMPLE_BORDER)
            licenseHeader = _LicenseListHeader(licenseListBorder)
            self._licenseList = _LicenseList(licenseListBorder)
            self._licenseList.SetMinSize(_kLicenseListMinSize)
            self._licenseList.Bind(wx.EVT_LISTBOX, self.OnResult)


            # Room for error text
            self._errorTextSizer = wx.BoxSizer()
            self._errorText = wx.StaticText(self, -1, "")
            self._errorTextSizer.Add(self._errorText, 0, wx.EXPAND | wx.TOP,
                    _kPadding)
            self._errorTextSizer.ShowItems(False)

            # License buttons
            self._upgradeButton = wx.Button(self, -1, _kBuyUpgradeLabel)
            self._unlinkButton = wx.Button(self, -1, _kUnlinkLicenseLabel)
            self._activateButton = wx.Button(self, -1, _kUseLicenseLabel)
            self._upgradeButton.Bind(wx.EVT_BUTTON, self.OnUpgrade)
            self._unlinkButton.Bind(wx.EVT_BUTTON, self.OnUnlink)
            self._activateButton.Bind(wx.EVT_BUTTON, self.OnActivate)
            self._upgradeButton.Disable()
            self._unlinkButton.Disable()
            self._activateButton.Disable()
            buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
            if wx.Platform != '__WXMAC__':
                purchaseButton = wx.Button(self, -1, _kPurchaseLabel)
                purchaseButton.Bind(wx.EVT_BUTTON, self.OnPurchase)
                buttonSizer.Add(purchaseButton, 0, wx.RIGHT, _kPadding)
            buttonSizer.Add(self._upgradeButton, 0, wx.RIGHT, _kPadding)
            buttonSizer.Add(self._unlinkButton, 0, wx.RIGHT, _kPadding)
            buttonSizer.Add(self._activateButton)

            # OK Button
            okButton = wx.Button(self, wx.ID_OK)
            okButton.SetDefault()

            # Main dialog layout
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(textSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 3*_kPadding)
            listSizer = wx.BoxSizer(wx.VERTICAL)
            listSizer.Add(licenseHeader, 0, wx.EXPAND)
            listSizer.Add(self._licenseList, 1, wx.EXPAND)
            licenseListBorder.SetSizer(listSizer)
            sizer.Add(licenseListBorder, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                    3*_kPadding)
            sizer.Add(self._errorTextSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT,
                    3*_kPadding)
            sizer.AddSpacer(2*_kPadding)
            sizer.Add(buttonSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 3*_kPadding)
            sizer.Add(okButton, 0, wx.ALIGN_RIGHT | wx.BOTTOM | wx.RIGHT ,
                    2*_kPadding)
            self.SetSizer(sizer)

            # Prime the controls
            self._refreshActiveLicense()

            self.Fit()
            self.CenterOnParent()

            wx.CallAfter(self._startListRefresh)

        except:
            self.Destroy()
            raise


    ###########################################################
    def _startListRefresh(self):
        """Start a refresh of the license list."""
        if self._refreshPending or self._refreshCount >= _kMaxRefreshCount:
            return

        self._refreshCount += 1
        self._licenseClient.refreshList()
        self._refreshPending = True
        self._refreshTimer.Start(_kRefreshPendingInterval, True)


    ###########################################################
    def OnRefreshTimer(self, event):
        """Start a new refresh or check for results of a pending refresh.

        @param  event  The EVT_TIMER event, ignored.
        """
        if not self._refreshPending:
            # Kick off a new refresh
            self._startListRefresh()
        else:
            # Check if our current refresh has completed.
            result = self._licenseClient.refreshListComplete(0)

            if result is None:
                # Result still pending, start timer to check again
                self._refreshTimer.Start(_kRefreshPendingInterval, True)
                return

            self._refreshPending = False
            if result[0]:
                self._licenseList.setLicenses(result[1])
            else:
                # Need to set empty list to clear loading placeholder.
                self._licenseList.setLicenses([])

            # TODO: What errors can this get? What do we need to do?

            # Now we may get a license update from the server on a list call
            # so we need to refresh our idea of what our active license is
            # each time as well.
            self._refreshActiveLicense()

            # Schedule the kickoff of a new refresh to catch changes while
            # this dialog is up (user buys a license, etc...
            self._refreshTimer.Start(_kRefreshRetryInterval, True)


    ###########################################################
    def OnDestroy(self, event):
        """Handle an EVT_WINDOW_DESTROY event.

        @param  event  The EVT_WINDOW_DESTROY event.
        """
        try:
            # Ensure we kill any timer we may have when we're destroyed.
            self._refreshTimer.Stop()
        except:
            pass

        event.Skip()


    ###########################################################
    def OnBadgeMenu(self, event):
        """Handle a right click on the sighthound logo.

        @param  event  The EVT_CONTEXT_MENU event.
        """
        menu = wx.Menu()
        item = menu.Append(-1, "Disconnect my account")
        self.Bind(wx.EVT_MENU, self.OnRemoveAccount, item)
        self.PopupMenu(menu, self.ScreenToClient(event.GetPosition()))
        menu.Destroy()


    ###########################################################
    def OnRemoveAccount(self, event):
        """Respond to a remove account menu request.

        @param  event  The generating EVT_MENU event.
        """
        wx.CallAfter(self._doRemoveAccount)


    ###########################################################
    def _doRemoveAccount(self):
        """Confirm and remove the current user account."""
        if wx.YES == wx.MessageBox(_kConfirmLogout, _kConfirmLogoutTitle,
                                   wx.YES_NO, self):
            self._backEndClient.userLogout()


    ###########################################################
    def _refreshActiveLicense(self):
        """Update  the UI to reflect the currently activated license."""
        self._license = self._backEndClient.getLicenseData()
        if self._license:
            self._licenseList.setActiveSerial(
                    self._license.get(kSerialField, ""))
        else:
            self._licenseList.setActiveSerial("")

        if not self._license:
            self._statusEditionLabel.SetLabel(_kStatusEditionText % "")
            self._statusUserLabel.SetLabel(_kLicenseErrorText)
            self._statusSerialLabel.SetLabel("")
            return

        isLegacy = isLegacyLicense(self._license)


        self._statusEditionLabel.SetLabel(_kStatusEditionText %
                self._license.get(kEditionField, ""))
        self._statusUserLabel.SetLabel(_kStatusUserText %
                _getUserStringFromLicense(self._license))
        self._statusSerialLabel.SetLabel(_kStatusSerialText %
                _getSerialStringFromLicense(self._license))

        self._legacySizer.ShowItems(isLegacy)
        self.Layout()

        # The selected license may have changed state, 'reselect' to ensure
        # our buttons are correct.
        if self._licenseList.GetSelection() != wx.NOT_FOUND:
            self.OnResult(None)


    ###########################################################
    def OnResult(self, event):
        """Respond to a list item selection or change.

        @param  event  The selection event
        """
        canUpgrade, canUnlink, canLink, versionError = \
                self._licenseList.getSelectionActions()
        self._upgradeButton.Enable(canUpgrade)
        self._unlinkButton.Enable(canUnlink)
        self._activateButton.Enable(canLink)

        if canLink or canUnlink:
            self._errorTextSizer.ShowItems(False)
        else:
            if versionError:
                self._errorText.SetLabel(_kVersionMismatch)
            else:
                self._errorText.SetLabel(_kCantActivate)
            self._errorText.Wrap(_kLicenseListMinSize[0])
            self._errorTextSizer.ShowItems(True)
        self.Layout()
        self.Fit()


    ###########################################################
    def OnPurchase(self, event):
        """Handle a click of the purchase button.

        @param  event The button event.
        """
        webbrowser.open(kBuyNewUrl)


    ###########################################################
    def OnUpgrade(self, event):
        """Handle a click of the purchase button.

        @param  event The button event.
        """
        serialNum = self._licenseList.getSelectedSerial()
        if serialNum:
            serialNum = urllib.quote(serialNum)
        webbrowser.open(kBuyUpgradeUrl % serialNum)


    ###########################################################
    def OnActivate(self, event):
        """Handle a click of the activate button.

        @param  event The button event.
        """
        serialNum = self._licenseList.getSelectedSerial()
        result = None
        if not serialNum:
            return

        if wx.YES == wx.MessageBox(_kConfirmActivate, _kConfirmActivateTitle,
                wx.YES_NO, self):
            dlg = DelayedProgressDialog(.5, _kAcquiringProgTitle,
                    _kAcquiringContent, parent=self, style=wx.PD_APP_MODAL)
            try:
                self._licenseClient.acquire(serialNum)

                for _ in xrange(0, int(_kMaxAcquireRetries)):
                    dlg.Pulse()
                    result = self._licenseClient.acquireComplete(
                                _kAcquirePendingIntervalSec)
                    if result is not None:
                        break
            finally:
                dlg.Destroy()

            # Update the active license UI view, which will also trigger an
            # update of the license list (drawing of only, not a re-list). We do
            # this regardless of success or failure to ensure we reflect the
            # current state of things.
            self._refreshActiveLicense()

            if not result or not result[0]:
                # Display a generic error dialog if we failed.
                wx.MessageBox(_kActivateError, _kActivateErrorTitle,
                    wx.OK | wx.ICON_ERROR, self)


    ###########################################################
    def OnUnlink(self, event):
        """Handle a click of the unlink button.

        @param  event The button event.
        """
        if wx.YES == wx.MessageBox(_kConfirmUnlink, _kConfirmUnlinkTitle,
                wx.YES_NO, self):
            dlg = DelayedProgressDialog(.5, _kUnlinkingProgTitle,
                    _kUnlinkingContent, parent=self, style=wx.PD_APP_MODAL)
            try:
                self._licenseClient.unlink()

                for _ in xrange(0, int(_kMaxUnlinkRetries)):
                    dlg.Pulse()
                    result = self._licenseClient.unlinkComplete(
                                _kUnlinkPendingIntervalSec)
                    if result is not None:
                        break
            finally:
                dlg.Destroy()

            self._refreshActiveLicense()

            if not result or not result[0]:
                # Display a generic error dialog if we failed.
                wx.MessageBox(_kUnlinkError, _kUnlinkErrorTitle,
                    wx.OK | wx.ICON_ERROR, self)



##############################################################################
class _LicenseListHeader(wx.Control):
    """A custom list view for displaying license information."""
    ###########################################################
    def __init__(self, parent):
        """The initializer for _LicenseListHeader

        @param  parent  The parent window
        """
        super(_LicenseListHeader, self).__init__(parent, style=wx.BORDER_NONE)

        self._gradientA = wx.Colour(*_kHeaderBackgroundA)
        self._gradientB = wx.Colour(*_kHeaderBackgroundB)
        self.Bind(wx.EVT_PAINT, self.OnPaint)


    ###########################################################
    def OnPaint(self, event):
        """Draw the header.

        @param  event The EVT_PAINT event.
        """
        dc = wx.BufferedPaintDC(self)
        dc.GradientFillLinear(self.GetClientRect(), self._gradientA,
                self._gradientB, wx.NORTH)

        font = dc.GetFont()
        font.SetWeight(wx.FONTWEIGHT_NORMAL)
        font.SetPointSize(_kHeaderFontSize)
        dc.SetFont(font)
        dc.SetTextForeground(wx.BLACK)

        dc.DrawText(truncateText(dc, _kHeaderSerial, _kSerialWidth),
                _kSerialOffset, _kItemYOffset)
        dc.DrawText(truncateText(dc, _kHeaderEdition, _kEditionWidth),
                _kEditionOffset, _kItemYOffset)
        dc.DrawText(truncateText(dc, _kHeaderCameras, _kCamsWidth),
                _kCamsOffset, _kItemYOffset)
        dc.DrawText(truncateText(dc, _kHeaderSupport, _kSupportWidth),
                _kSupportOffset, _kItemYOffset)
        dc.DrawText(truncateText(dc, _kHeaderExpires, _kExpiresWidth),
                _kExpiresOffset, _kItemYOffset)
        dc.DrawText(truncateText(dc, _kHeaderCanUse, _kAvailableWidth),
                _kAvailableOffset, _kItemYOffset)


    ###########################################################
    def DoGetBestSize(self):
        """Return the best size for the header.

        @return bestSize  The best size for the header.
        """
        return (_kLicenseListMinSize[0], _kHeaderHeight)


##############################################################################
class _LicenseList(wx.VListBox):
    """A custom list view for displaying license information."""
    ###########################################################
    def __init__(self, parent):
        """The initializer for _LicenseList

        @param  parent  The parent window
        """
        super(_LicenseList, self).__init__(parent)

        selectionBg = wx.Colour(*_kSelectionBackground)
        self._selectedBgPen = wx.Pen(selectionBg)
        self._selectedBgBrush = wx.Brush(selectionBg)

        # None is a flag to indicate "Loading..." text should be displayed.
        # A license result should replace this with [] rather than None if no
        # licenses are available.
        self._licenses = None
        self._curSerial = None

        self.SetItemCount(1)

        # We draw slightly different depending on whether our window is
        # active, at least on Mac...
        if wx.Platform == '__WXMAC__':
            self._isActive = True
            self.GetTopLevelParent().Bind(wx.EVT_ACTIVATE, self.OnActivate)


    ###########################################################
    def OnActivate(self, event):
        """Handle activate events on our top level parent.

        We just refresh, and cache active state.  Mac ONLY.

        @param  event  The activate event.
        """
        # Cache whether we're active, since calling IsActive() on the top
        # level window always seems to return true...
        self._isActive = event.GetActive()

        self.Refresh()
        event.Skip()


    ###########################################################
    def getSelectionActions(self):
        """Retrieve the available options for the selected license.

        @return canUpgrade    True if the license can be upgraded.
        @return canUnlink     True if the license can be unlinked.
        @return canLink       True if the license can be linked.
        @return versionError  True if license requires earlier verison.
        """
        selection = self.GetSelection()

        if selection == wx.NOT_FOUND or not self._licenses:
            return False, False, False, False

        lic = self._licenses[selection]

        canUpgrade = lic[kEditionField] == kBasicEdition
        canUnlink = (lic[kSerialField] == self._curSerial)
        if not self._curSerial:
            canUnlink = False
        canLink = lic[kAvailableInfo] and not canUnlink

        versionError = not licenseValidForAppVersion(lic)

        return canUpgrade, canUnlink, canLink, versionError


    ###########################################################
    def getSelectedSerial(self):
        """Return the serial number of the current selection.

        @return serial  The serial number or empty string.
        """
        if self.GetSelection() == wx.NOT_FOUND:
            return ""
        return self._licenses[self.GetSelection()][kSerialField]


    ###########################################################
    def setActiveSerial(self, serial):
        """Set the active license serial number.

        @param  serial  The active serial number or None.
        """
        self._curSerial = serial
        self.Refresh()


    ###########################################################
    def _setLicenses(self, licenses):
        """Set the licenses to display.

        @param  licenses  A list of license info dictionaries to display.
        """

        # Parse out licenses we don't want to display (starter and trial)
        licenses = [x for x in licenses if x[kEditionField] not in
                [kStarterEdition, kTrialEdition]]
        if licenses == self._licenses:
            return

        # Save the current selection if we have one.
        curSerial = None
        selection = self.GetSelection()
        if selection != wx.NOT_FOUND and self._licenses:
            curSerial = self._licenses[selection][kSerialField]

        self._licenses = licenses

        self.Clear()
        self.SetItemCount(len(self._licenses))

        # Attempt to restore the previous selection
        if curSerial:
            for i in xrange(0, len(self._licenses)):
                if licenses[i][kSerialField] == curSerial:
                    self.SetSelection(i)
                    if not self.IsVisible(i):
                        self.ScrollToLine(i)
                    break

        self.Refresh()


    ###########################################################
    def setLicenses(self, licenses):
        """ Exception catcher, since we encountered unexplained problems where
        the license list might have None fields or is None itself.
        """
        try:
            self._setLicenses(licenses)
        except:
            report = "setLicenses() failed (%s)\nlicenses: %s\n%s" % \
                (str(sys.exc_info()[1]), str(licenses), traceback.format_exc())
            raise Exception(report)


    ###########################################################
    def OnDrawBackground(self, dc, rect, n): #PYCHECKER signature mismatch OK
        """Draw the background and border for the given item.

        @param  dc    The drawing context in which to draw
        @param  rect  The rectangle in which to draw
        @param  n     The index of the item to draw
        """
        # Stolen from vitaToolbox/wx/ListBoxWithIcons
        if n == self.GetSelection():
            # Mac seems to have very special rules for selection colors...
            if wx.Platform == '__WXMAC__':
                brush = wx.Brush(wx.BLACK)
                if self._isActive:
                    brush = wx.Brush(wx.MacThemeColour(kThemeBrushAlternatePrimaryHighlightColor))
                else:
                    brush = wx.Brush(wx.MacThemeColour(kThemeBrushSecondaryHighlightColor))
            else:
                brush = wx.Brush(
                    wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
                )
        else:
            brush = wx.Brush(self.GetBackgroundColour())

        dc.SetBackground(brush)
        dc.Clear()


    ###########################################################
    def OnDrawSeparator(self, dc, rect, n): #PYCHECKER signature mismatch OK
        """Draw a seperator for the given item.

        @param  dc    The drawing context in which to draw
        @param  rect  The rectangle in which to draw
        @param  n     The index of the item to draw
        """
        if self._licenses is None:
            return

        dc.SetPen(wx.GREY_PEN)
        dc.DrawLine(rect.X, rect.Y+rect.Height-1, rect.X+rect.Width-1,
                    rect.Y+rect.Height-1)


    ###########################################################
    def OnDrawItem(self, dc, rect, n):
        """Draw the item with the given index.

        @param  dc    The drawing context in which to draw
        @param  rect  The rectangle in which to draw
        @param  n     The index of the item to draw
        """
        font = dc.GetFont()
        font.SetWeight(wx.FONTWEIGHT_NORMAL)
        font.SetPointSize(_kItemFontSize)
        dc.SetFont(font)

        # Check for special loading UI case
        if self._licenses is None:
            dc.SetTextForeground(wx.BLACK)
            dc.DrawText(_kLoadingText, rect.X+_kSerialOffset,
                    rect.Y+_kItemYOffset)
            return

        if self.IsSelected(n):
            textForeground = wx.WHITE
        else:
            textForeground = wx.BLACK
        dc.SetTextForeground(textForeground)

        lic = self._licenses[n]

        serialText = _getSerialStringFromLicense(lic)
        dc.DrawText(truncateText(dc, serialText, _kSerialWidth),
                rect.X+_kSerialOffset, rect.Y+_kItemYOffset)
        dc.DrawText(truncateText(dc, lic[kEditionField], _kEditionWidth),
                rect.X+_kEditionOffset, rect.Y+_kItemYOffset)

        camsText = str(lic[kCamerasField])
        if lic[kCamerasField] == -1:
            camsText = _kUnlimitedText
        dc.DrawText(truncateText(dc, camsText, _kCamsWidth),
                rect.X+_kCamsOffset, rect.Y+_kItemYOffset)

        expiresText = _kNAText
        if lic[kExpiresField]:
            expiresText = formatTime("%x", time.localtime(lic[kExpiresField]))
        dc.DrawText(truncateText(dc, expiresText, _kExpiresWidth),
                rect.X+_kExpiresOffset, rect.Y+_kItemYOffset)

        availText = _kUnavailableText
        if lic[kSerialField] and lic[kSerialField] == self._curSerial:
            availText = _kActiveText
        elif lic[kAvailableInfo]:
            availText = _kAvailableText
        dc.DrawText(truncateText(dc, availText, _kAvailableWidth),
                rect.X+_kAvailableOffset, rect.Y+_kItemYOffset)

        supportText = _kNoExpirationText
        if lic[kSupportField]:
            if time.time() > lic[kSupportField]-30*_kSecsPerDay:
                dc.SetTextForeground(wx.RED)
            supportText = formatTime("%x", time.localtime(lic[kSupportField]))
        dc.DrawText(truncateText(dc, supportText, _kSupportWidth),
                rect.X+_kSupportOffset, rect.Y+_kItemYOffset)
        # If anything ever comes after this, ensure we set the foreground
        # color again as it might have changed above.
        #dc.SetTextForeground(textForeground)


    ###########################################################
    def OnMeasureItem(self, n):
        """Return the height of an item in the list box

        @param  n     The index of the item to retrieve the height of
        """
        return _kItemHeight


###########################################################
def _getUserStringFromLicense(lic):
    """Retrieve a username for display from the given license.

    @param  lic  The license to use.
    """
    user = lic.get(kNameField, kNoValueToken)
    if not user or user == kNoValueToken:
        user = kDefaultUser

    return user.replace('&', '&&') # TODO: case 10422


###########################################################
def _getSerialStringFromLicense(lic):
    """Retrieve a serial for display from the given license.

    @param  lic  The license to use.
    """
    serial = lic.get(kSerialField, kNoValueToken)
    if not serial or serial == kNoValueToken:
        serial = kDefaultSerial

    return serial


