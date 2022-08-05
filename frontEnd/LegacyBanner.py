#!/usr/bin/env python

#*****************************************************************************
#
# LegacyBanner.py
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

# Common 3rd-party imports...
import wx
import wx.adv

# Toolbox imports...
from vitaToolbox.wx.FontUtils import makeFontDefault

# Local imports...
from appCommon.CommonStrings import kAboutAccountsUrl
from appCommon.CommonStrings import kLoginStatusLastUser
from appCommon.LicenseUtils import kEditionField, kStarterEdition
from LoginDialog import LoginDialog
from TrialBanner import kBackgroundColor, styleBannerLink

_kWarningPaidText = ("""Link your license with a Sighthound Account """
        """to continue receiving updates.""")
_kWarningStarterText = ("""Sign in with a Sighthound Account to """
        """continue receiving updates.""")
_kLearnMoreText = "Learn More"
_kSignInText = "Sign In"
_kMyLicensesText = "My Licenses"

_SHOW_LOGIN_EVENT_TYPE = wx.NewEventType()
EVT_SHOW_LOGIN = wx.PyEventBinder(_SHOW_LOGIN_EVENT_TYPE, 1)


##############################################################################
class LegacyBanner(wx.Panel):
    """A banner for trial users with expiration and purchase information.

    @param  parent           The parent window.
    @param  backEndClient    An active BackEndClient instance.
    @param  licenseCallback  A function to call if the user clicks "licenses"
    """
    def __init__(self, parent, backEndClient, licenseCallback):
        # Call the base class initializer
        super(LegacyBanner, self).__init__(parent, -1)

        self._backEndClient = backEndClient

        # Create the controls.
        self._textCtrl = wx.StaticText(self, -1, _kWarningStarterText)
        self._textCtrl.SetForegroundColour(wx.WHITE)

        learnMoreLink = wx.adv.HyperlinkCtrl(self, -1, _kLearnMoreText, kAboutAccountsUrl)
        self._signinLink = wx.adv.HyperlinkCtrl(self, -1, _kSignInText, "")
        self._licensesLink = wx.adv.HyperlinkCtrl(self, -1, _kMyLicensesText, "")
        self._signinLink.Bind(wx.adv.EVT_HYPERLINK, self.OnSignIn)
        self._licensesLink.Bind(wx.adv.EVT_HYPERLINK, licenseCallback)

        makeFontDefault(self._textCtrl, learnMoreLink, self._signinLink,
                self._licensesLink)

        for link in (learnMoreLink, self._signinLink, self._licensesLink):
            styleBannerLink(link)

        # Layout the controls.
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddSpacer(8)
        sizer.Add(self._textCtrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.BOTTOM, 6)
        sizer.Add(learnMoreLink, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 16)
        sizer.Add(self._signinLink, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 16)
        sizer.Add(self._licensesLink, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 16)
        self.SetSizer(sizer)

        self.SetBackgroundColour(wx.Colour(*kBackgroundColor))


    ###########################################################
    def updateBanner(self, license):
        """Update the banner to reflect the current state.

        @param  license  The current license.
        """
        if license[kEditionField] == kStarterEdition:
            self._textCtrl.SetLabel(_kWarningStarterText)
        else:
            self._textCtrl.SetLabel(_kWarningPaidText)

        if self._backEndClient.getLoginStatus()[kLoginStatusLastUser]:
            self._signinLink.Hide()
            self._licensesLink.Show()
            if license[kEditionField] == kStarterEdition:
                # A legacy starter user who has signed in *should* have either
                # received a Trial license or a new style Starter license, and
                # this banner would be hidden. If we do wind up here in some
                # error case, go ahead and hide ourselves.
                self.Hide()
                self.GetParent().Layout()
        else:
            self._signinLink.Show()
            self._licensesLink.Hide()

        self.Layout()


    ###########################################################
    def OnSignIn(self, event):
        """Handle a click of the sign in link.

        @param  event  The hyperlink event. Ignored.
        """
        wx.PostEvent(self.GetEventHandler(),
                wx.PyCommandEvent(_SHOW_LOGIN_EVENT_TYPE, self.GetId()))

