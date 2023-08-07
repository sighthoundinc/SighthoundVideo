#!/usr/bin/env python

#*****************************************************************************
#
# LookForList.py
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
import sys

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.ListBoxWithIcons import ListBoxWithIcons

# Local imports...
from appCommon.CommonStrings import kEmailResponse, kRecordResponse
from appCommon.CommonStrings import kSoundResponse, kCommandResponse
from appCommon.CommonStrings import kFtpResponse
from appCommon.CommonStrings import kLocalExportResponse, kPushResponse
from appCommon.CommonStrings import kIftttResponse, kWebhookResponse

# Constants...
_kNumRowsToShow = 6


##############################################################################
class LookForList(ListBoxWithIcons):
    """Implements the list box for letting the user choose a query."""

    ###########################################################
    def __init__(self, parent, uid=wx.ID_ANY):
        """The initializer for LookForList

        @param  parent       The parent window
        @param  uid          Our UI ID.
        """
        # Call the base class initializer
        super(LookForList, self).__init__(parent, uid, style=0)

        # Adjust number of rows...
        self.setMinNumRows(_kNumRowsToShow)

        # Organize bitmaps so we can index by [responseName][enabled]
        self._bitmaps = {
            kCommandResponse: {
                True:  wx.Bitmap("frontEnd/bmps/Response_Command_Enabled.png"),
                False: wx.Bitmap("frontEnd/bmps/Response_Command_Disabled.png"),
            },
            kRecordResponse: {
                True:  wx.Bitmap("frontEnd/bmps/Response_Save_Enabled.png"),
                False: wx.Bitmap("frontEnd/bmps/Response_Save_Disabled.png"),
            },
            kEmailResponse: {
                True:  wx.Bitmap("frontEnd/bmps/Response_Email_Enabled.png"),
                False: wx.Bitmap("frontEnd/bmps/Response_Email_Disabled.png"),
            },
            kSoundResponse: {
                True:  wx.Bitmap("frontEnd/bmps/Response_Sound_Enabled.png"),
                False: wx.Bitmap("frontEnd/bmps/Response_Sound_Disabled.png"),
            },
            kFtpResponse: {
                True:  wx.Bitmap("frontEnd/bmps/Response_SendClip_Enabled.png"),
                False: wx.Bitmap("frontEnd/bmps/Response_SendClip_Disabled.png"),
            }
        }

        # Add cases of identical bitmaps; want these to be the exact same bitmap
        # object...
        self._bitmaps[kLocalExportResponse] = self._bitmaps[kFtpResponse]
        self._bitmaps[kPushResponse] = self._bitmaps[kEmailResponse]
        self._bitmaps[kIftttResponse] = self._bitmaps[kEmailResponse]
        self._bitmaps[kWebhookResponse] = self._bitmaps[kEmailResponse]


    ###########################################################
    def setRuleInfo(self, defaultRules, ruleInfoList):
        """Sets text/icons based on the given rule info.

        @param  defaultRules  A list of default rules; these have no responses.
        @param  ruleInfoList  A list of rule info tuples as returned by the
                              backend's getRuleInfoForLocation().  This looks
                              like: (ruleName, queryName, scheduleString,
                              isEnabled, responseNames)
        """
        # Init items to the defaults, which have no responses...
        items = [ (itemName, []) for itemName in defaultRules ]

        # Walk through rules and build the rest of our items...
        for (ruleName, _, _, isEnabled, responseNames) in ruleInfoList:
            icons = []
            for responseName in responseNames:
                if responseName in self._bitmaps:
                    bmp = self._bitmaps[responseName][bool(isEnabled)]

                    # Only add a given bitmap once...
                    if bmp not in icons:
                        icons.append(bmp)
                else:
                    assert False, "Missing bitmaps for %s" % (responseName)

            items.append((ruleName, icons))

        # Save the selection; set the list, then re-set the selection...
        selection = self.GetStringSelection()

        self.Clear()
        self.AppendItems(items)

        if selection in self.GetStrings():
            self.SetStringSelection(selection)
        elif items:
            self.SetSelection(0)



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "No test code"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
