#!/usr/bin/env python

#*****************************************************************************
#
# StarterBanner.py
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
import webbrowser

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.FixedGenBitmapButton import FixedGenBitmapButton
from vitaToolbox.wx.FontUtils import makeFontDefault

# Local imports...
from appCommon.CommonStrings import kDirectBuyBasic
from appCommon.CommonStrings import kDirectBuyPro
from TrialBanner import DIRECT_PURCHASE_EVENT_TYPE
from TrialBanner import kBackgroundColor, kBasicLabel, kProLabel
from TrialBanner import getAccountAndToken

_kPurchaseText = ("""Purchase a license to unlock multiple cameras, """
                  """HD video, remote access, and more.""")

# TODO: Merge me with TrialBanner?

##############################################################################
class StarterBanner(wx.Panel):
    """A banner for starter edition users with purchase links."""
    def __init__(self, parent, backEndClient):
        # Call the base class initializer
        super(StarterBanner, self).__init__(parent, -1)

        self._backEndClient = backEndClient

        # Create the controls.
        purchaseText = wx.StaticText(self, -1, _kPurchaseText)
        purchaseText.SetForegroundColour(wx.WHITE)

        bmp = wx.Bitmap(
                os.path.join("frontEnd/bmps", "Purchase_MouseUp_Small.png"))
        bmpSel = wx.Bitmap(
                os.path.join("frontEnd/bmps", "Purchase_MouseDown_Small.png"))
        basicButton = FixedGenBitmapButton(self, bmp, bmpSel)
        proButton = FixedGenBitmapButton(self, bmp, bmpSel)

        basicLabel = wx.StaticText(self, -1, kBasicLabel)
        proLabel = wx.StaticText(self, -1, kProLabel)
        basicLabel.SetForegroundColour(wx.WHITE)
        proLabel.SetForegroundColour(wx.WHITE)

        makeFontDefault(purchaseText, basicLabel, proLabel)

        basicButton.Bind(wx.EVT_BUTTON, self.OnBasicPurchase)
        proButton.Bind(wx.EVT_BUTTON, self.OnProPurchase)

        # Layout the controls.
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(purchaseText, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        sizer.AddStretchSpacer(1)

        sizer.Add(basicLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        sizer.Add(basicButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        sizer.Add(proLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        sizer.Add(proButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.BOTTOM, 6)

        sizer.AddSpacer(8)
        self.SetSizer(sizer)

        self.SetBackgroundColour(wx.Colour(*kBackgroundColor))


    ###########################################################
    def OnBasicPurchase(self, event):
        """Handle a click of the Purcahse button.

        @param  event  The EVT_BUTTON event.
        """
        webbrowser.open(kDirectBuyBasic %
                getAccountAndToken(self._backEndClient))

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

