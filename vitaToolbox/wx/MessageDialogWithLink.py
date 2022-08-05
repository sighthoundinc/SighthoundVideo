#!/usr/bin/env python

#*****************************************************************************
#
# MessageDialogWithLink.py
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
import sys

# Common 3rd-party imports...
import wx

# Toolbox imports...
from TextSizeUtils import makeFontDefault

# Local imports...

# Constants
_kMessageWidth = 400
_kNormalHyperlink = (0, 102, 204)
_kHoverHyperlink  = (5, 153, 255)


##############################################################################
class MessageDialogWithLink(wx.Dialog):
    """Shows a message dialog with a link at the bottom."""

    ###########################################################
    def __init__(self, parent, title, message, linkText, linkUrl,
                 artId=wx.ART_WARNING):
        """MessageDialogWithLink constructor.

        @param  parent    UI parent.
        @param  title     The title for the dialog.
        @param  message   The message to show in the dialog.
        @param  linkText  The text of the link.
        @param  linkUrl   The URL to have the link go to.
        @param  artId     The ID of something to get from the art provider.
                          We'll use the client wx.ART_MESSAGE_BOX.
        """
        super(MessageDialogWithLink, self).__init__(parent, -1, title)


        bmp = wx.ArtProvider.GetBitmap(artId, wx.ART_MESSAGE_BOX, (32,32))

        staticBitmap = wx.StaticBitmap(self, -1, bmp)
        messageLabel = wx.StaticText(self, -1, message)
        messageLabel.Wrap(_kMessageWidth)
        urlObj = wx.adv.HyperlinkCtrl(self, -1, linkText, linkUrl, style=wx.adv.HL_ALIGN_LEFT | wx.NO_BORDER)
        urlObj.SetNormalColour(wx.Colour(*_kNormalHyperlink))
        urlObj.SetVisitedColour(wx.Colour(*_kNormalHyperlink))
        urlObj.SetHoverColour(wx.Colour(*_kHoverHyperlink))

        buttonSizer = self.CreateStdDialogButtonSizer(wx.OK)

        makeFontDefault(messageLabel, urlObj)

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        horizSizer = wx.BoxSizer(wx.HORIZONTAL)
        horizSizer.Add(staticBitmap, 0, wx.ALL, 12)
        messageAndLinkSizer = wx.BoxSizer(wx.VERTICAL)
        messageAndLinkSizer.Add(messageLabel, 0, wx.EXPAND | wx.BOTTOM, 12)
        messageAndLinkSizer.Add(urlObj, 0, wx.EXPAND)
        horizSizer.Add(messageAndLinkSizer, 0, wx.TOP | wx.RIGHT, 12)

        mainSizer.Add(horizSizer)
        mainSizer.Add(buttonSizer, 0, wx.EXPAND | wx.ALL, 12)

        self.SetSizer(mainSizer)
        self.Fit()

        self.CenterOnParent()


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)
    _ = app

    testWarning = (
        """I have a message for you.  It might be pretty long.  Hopefully, """
        """it will wrap properly.  Will it?  It'd better.  OK, now that """
        """we've determined that, let's make some points:\n"""
        """\n"""
        """- Point one\n"""
        """- Point two\n"""
        """- Point three\n"""
        """- Point four"""
    )
    dlg = MessageDialogWithLink(None, "Test dialog", testWarning,
                                "Here's a link.",
                                "http://www.vitamindinc.com/")
    dlg.ShowModal()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
