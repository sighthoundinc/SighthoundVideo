#!/usr/bin/env python

#*****************************************************************************
#
# TrialBanner.py
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
import os
import time
import urllib
import webbrowser

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.FixedGenBitmapButton import FixedGenBitmapButton
from vitaToolbox.wx.FontUtils import makeFontDefault

# Local imports...
from appCommon.CommonStrings import kDirectBuyBasic
from appCommon.CommonStrings import kDirectBuyPro
from appCommon.CommonStrings import kLoginStatusAccountId
from appCommon.CommonStrings import kLoginStatusMachineId
from appCommon.LicenseUtils import kProEdition


kBackgroundColor = (35, 37, 74)


_kEditionText = """Your %s trial will expire in """ % kProEdition
_kPurchaseText = ("""Purchase a license to continue enjoying multiple """
"""cameras, HD video, and remote access.""")
_kCountdownText = _kEditionText + "%s days. " + _kPurchaseText
_kCountdownOneText = _kEditionText + "%s day. " + _kPurchaseText
_kCountdownImmediateText = _kEditionText + """in less than 24 hours. """ + _kPurchaseText

kBasicLabel = "Basic - 2 Cameras"
kProLabel = "Pro - Unlimited Cameras"

if wx.Platform == "__WXMSW__":
    _kEditionPointSize = 13
else:
    _kEditionPointSize = 16

_kTimerInterval = 60*60*1000

DIRECT_PURCHASE_EVENT_TYPE = wx.NewEventType()
EVT_DIRECT_PURCHASE = wx.PyEventBinder(DIRECT_PURCHASE_EVENT_TYPE, 1)


##############################################################################
class TrialBanner(wx.Panel):
    """A banner for trial users with expiration and purchase information."""
    def __init__(self, parent, backEndClient):
        # Call the base class initializer
        super(TrialBanner, self).__init__(parent, -1)

        self._backEndClient = backEndClient
        self._expiration = time.time()

        # Create the controls.
        self._countdownText = wx.StaticText(self, -1, "")
        makeFontDefault(self._countdownText)
        self._countdownText.SetForegroundColour(wx.WHITE)

        bmp = wx.Bitmap(os.path.join("frontEnd/bmps", "Purchase_MouseUp.png"))
        bmpSel = wx.Bitmap(os.path.join("frontEnd/bmps",
                                        "Purchase_MouseDown.png"))
        basicButton = FixedGenBitmapButton(self, bmp, bmpSel)
        proButton = FixedGenBitmapButton(self, bmp, bmpSel)

        basicLabel = wx.StaticText(self, -1, kBasicLabel)
        proLabel = wx.StaticText(self, -1, kProLabel)
        basicLabel.SetForegroundColour(wx.WHITE)
        proLabel.SetForegroundColour(wx.WHITE)

        font = basicLabel.GetFont()
        font.SetPointSize(_kEditionPointSize)
        basicLabel.SetFont(font)
        proLabel.SetFont(font)

        basicButton.Bind(wx.EVT_BUTTON, self.OnBasicPurchase)
        proButton.Bind(wx.EVT_BUTTON, self.OnProPurchase)

        # Layout the controls.
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(6)
        sizer.Add(self._countdownText, 0, wx.LEFT, 8)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(basicLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        hSizer.Add(basicButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 40)
        hSizer.Add(proLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        hSizer.Add(proButton, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.AddSpacer(6)
        sizer.Add(hSizer, 0, wx.LEFT, 8)
        sizer.AddSpacer(6)
        self.SetSizer(sizer)

        self.SetBackgroundColour(wx.Colour(*kBackgroundColor))

        # A timer to update the expiration countdown.
        self._timer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self._timer)


    ###########################################################
    def setExpiration(self, expiration):
        """Set the trial expiration.

        Note: This will not update the UI. It is assumed this will be
        followed by a call to showBanner.

        @param  expiration  The UTC timestamp of the trial's expiration.
        """
        try:
            self._expiration = int(expiration)
        except:
            self._expiration = time.time()


    ###########################################################
    def showBanner(self, shouldShow):
        """Show or hide the trial banner.

        @param  shouldShow  True to show the banner.
        """
        if shouldShow:
            self.OnTimer(None)
            self.Show()
        else:
            self.Hide()
            self._timer.Stop()


    ###########################################################
    def OnTimer(self, event):
        """Handle a timer fire.

        @param  event  The EVT_TIMER event. Ignored.
        """
        # Update the countdown.
        now = time.time()
        days = max(0, int((self._expiration-now)/(60*60*24)))
        if days < 1:
            self._countdownText.SetLabel(_kCountdownImmediateText)
        elif days == 1:
            self._countdownText.SetLabel(_kCountdownOneText % str(days))
        else:
            self._countdownText.SetLabel(_kCountdownText % str(days))

        # Schedule the next firing.
        self._timer.Start(_kTimerInterval, True)


    ###########################################################
    def OnBasicPurchase(self, event):
        """Handle a click of the Purcahse button.

        @param  event  The EVT_BUTTON event.
        """
        webbrowser.open(kDirectBuyBasic % getAccountAndToken(self._backEndClient))

        wx.PostEvent(self.GetEventHandler(),
                wx.PyCommandEvent(DIRECT_PURCHASE_EVENT_TYPE, self.GetId()))


    ###########################################################
    def OnProPurchase(self, event):
        """Handle a click of the Purcahse button.

        @param  event  The EVT_BUTTON event.
        """
        webbrowser.open(kDirectBuyPro % getAccountAndToken(self._backEndClient))

        wx.PostEvent(self.GetEventHandler(),
                wx.PyCommandEvent(DIRECT_PURCHASE_EVENT_TYPE, self.GetId()))


##############################################################################
def styleBannerLink(hyperlink):
    """Style a link control to fit in with the banner.

    @param  hyperlink  the wx.adv.HyperlinkCtrl to style.
    """
    hyperlink.SetNormalColour(wx.Colour(224, 224, 224, 224))
    hyperlink.SetHoverColour(wx.WHITE)
    hyperlink.SetVisitedColour(hyperlink.GetNormalColour())
    font = hyperlink.GetFont()
    font.SetUnderlined(True)
    hyperlink.SetFont(font)


##############################################################################
def getAccountAndToken(backEndClient):
    """Retrieve a url escaped account and machine id tuple.

    @param  backEndClient  A valid BackEndClient instance.
    @return accountId      A url escaped account id.
    @return machineId      A url escaped machine id.
    """
    machineId = backEndClient.getLoginStatus()[kLoginStatusMachineId]
    accountId = backEndClient.getLoginStatus()[kLoginStatusAccountId]

    if not machineId or not accountId:
        return ("", "")

    return (urllib.quote(accountId), urllib.quote(machineId))

