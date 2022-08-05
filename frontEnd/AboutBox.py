#!/usr/bin/env python
# -*- coding: utf8 -*-

#*****************************************************************************
#
# AboutBox.py
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
import os
import re
import sys


# Common 3rd-party imports...
import wx



# Toolbox imports...
from vitaToolbox.wx.BindChildren import bindChildren
from vitaToolbox.wx.FixedStaticBitmap import FixedStaticBitmap
from vitaToolbox.wx.TextSizeUtils import makeFontDefault
from vitaToolbox.wx.TextCtrlUtils import setHyperlinkColors


# Local imports...
from appCommon.LicenseUtils import kEditionField
from appCommon.LicenseUtils import kStarterEdition
from appCommon.CommonStrings import kAppName
from appCommon.CommonStrings import kCopyrightStr
from appCommon.CommonStrings import kCopyrightMoreInfoStr
from appCommon.CommonStrings import kCopyrightMoreInfoUrl
from appCommon.CommonStrings import kVersionString, kVersionStringModifier
from LicensingHelpers import getLicense


# Constants
_kAppInfoStr          = "%(edition)s version %(version)s build %(buildStr)s"
_kTitleStr            = "About %s" % kAppName

##############################################################################
def ShowAboutBox(parent, backEndClient):
    """Show the about box.

    @param  parent         The parent window.
    @param  backEndClient  A proxy to the back end.
    """
    dlg = _AboutBox(parent, backEndClient)
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()


##############################################################################
class _AboutBox(wx.Dialog):
    """The about box dialog."""

    ###########################################################
    def __init__(self, parent, backEndClient):
        """AboutBox constructor.

        @param  parent         The parent window.
        @param  backEndClient  A proxy to the back end.
        """
        # Call the superclass constructor.
        super(_AboutBox, self).__init__(parent, -1, _kTitleStr)
        try:
            self._doInit(backEndClient)
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _doInit(self, backEndClient):
        """Actual init code; see __init__() for details.

        This function exists so we can put a "try" around it easily...
        """

        mainBitmap = wx.Bitmap("frontEnd/bmps/About_Image.png")

        mainStaticBitmap = FixedStaticBitmap(self, -1, mainBitmap)

        intMatch = re.search('[0-9]+', wx.GetApp().getAppBuildStr())
        buildStr = 'unknown'
        if intMatch:
            buildStr = intMatch.group()

        lic = getLicense(backEndClient, self.GetTopLevelParent())
        edition = kStarterEdition
        if lic:
            edition = lic[kEditionField]
        appInfoLabel = wx.StaticText(self, -1, _kAppInfoStr % {
            'edition': edition,
            'version': kVersionString + kVersionStringModifier,
            'buildStr': buildStr
        })

        # Make copyright label; set min size so it wraps properly...
        copyrightLabel = wx.StaticText(self, -1, kCopyrightStr)

        copyrightMoreInfoCtrl = wx.adv.HyperlinkCtrl(self, -1, kCopyrightMoreInfoStr, kCopyrightMoreInfoUrl)
        setHyperlinkColors(copyrightMoreInfoCtrl)

        okButton = wx.Button(self, wx.ID_OK)
        okButton.SetFocus()
        okButton.SetDefault()

        makeFontDefault(appInfoLabel, copyrightLabel, copyrightMoreInfoCtrl,
                        okButton)
        copyrightLabel.Wrap(mainBitmap.Size[0]-24)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(mainStaticBitmap,  0, wx.ALIGN_RIGHT | wx.BOTTOM, 5)
        sizer.Add(appInfoLabel, 0, wx.LEFT, 12)
        sizer.Add(copyrightLabel, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 12)
        sizer.Add(copyrightMoreInfoCtrl, 0, wx.LEFT | wx.RIGHT, 12)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.AddStretchSpacer(1)
        buttonSizer.Add(okButton)
        sizer.Add(buttonSizer, 0, wx.EXPAND | wx.ALL, 12)

        if wx.Platform == '__WXMAC__':
            bindChildren(self, wx.EVT_CHAR, self.OnChar)

        self.SetSizer(sizer)
        self.Fit()
        self.CenterOnParent()


    ############################################################
    def OnChar(self, event):
        """Handle key character events.

        @param  event  The key event, from the system
        """
        # Close the window if Cmd+W is pressed.
        if ord('w') == event.GetKeyCode() and \
           wx.MOD_CMD == event.GetModifiers():
            self.Close()
            return

        event.Skip()



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "No tests"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
