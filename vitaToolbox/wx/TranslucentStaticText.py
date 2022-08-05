#! /usr/local/bin/python

#*****************************************************************************
#
# TranslucentStaticText.py
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
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from TruncateText import truncateText




##############################################################################
class TranslucentStaticText(wx.StaticText):
    """A static text object that works on background images.

    This is not yet a complete drop-in replacement for static text.
    Specifically, it doesn't at the moment support wrapping or multi-line text.
    """

    ###########################################################
    def __init__(self, parent, id, label,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=0, name="staticText"):
        """The initializer for TranslucentStaticText.

        @param  parent       The parent Window.
        @param  id           The ID
        @param  label        The text label.
        @param  pos          UI pos.
        @param  size         UI size.
        @param  style        UI style.  Note that you can pass in
                             wx.ST_ELLIPSIZE_END, which will indicate that we
                             should truncate text nicely.
        @param  name         UI name.
        """
        # Make sure it's transparent, even if client doesn't set it...
        style |= wx.TRANSPARENT_WINDOW

        # Call the base class initializer
        super(TranslucentStaticText, self).__init__(parent, id, label, pos, size,
                                                    style, name)

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Set default attributes
        visAttributes = wx.StaticText.GetClassDefaultAttributes()
        self.SetForegroundColour(visAttributes.colFg)

        # Bind to paint events
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)


    ###########################################################
    def OnPaint(self, event):
        """Draw the gradient line.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self)

        dc.SetFont(self.GetFont())

        width, _ = self.GetClientSize()
        style = self.GetWindowStyle()
        label = self.GetLabel()

        # If client passed wx.ST_ELLIPSIZE_END, we'll use that as a key that
        # we should truncate text nicely.
        if style & wx.ST_ELLIPSIZE_END:
            label = truncateText(dc, label, width)

        textWidth, _ = dc.GetTextExtent(label)
        if style & wx.ALIGN_CENTER:
            x = (width - textWidth) / 2
        elif style & wx.ALIGN_RIGHT:
            x = width - textWidth
        else:
            x = 0

        dc.SetTextForeground(self.GetForegroundColour())
        dc.SetBackgroundMode(wx.TRANSPARENT)

        dc.DrawText(label, x, 0)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    panel.SetBackgroundStyle(kBackgroundStyle)

    st1 = TranslucentStaticText(panel, -1, "Left-1")
    st2 = TranslucentStaticText(panel, -1, "Left-2", style=wx.ALIGN_LEFT)
    st3 = TranslucentStaticText(panel, -1, "Right", style=wx.ALIGN_RIGHT)
    st4 = TranslucentStaticText(panel, -1, "Center", style=wx.ALIGN_CENTER)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(st1, 0, wx.EXPAND | wx.ALL, 10)
    sizer.Add(st2, 0, wx.EXPAND | wx.ALL, 10)
    sizer.Add(st3, 0, wx.EXPAND | wx.ALL, 10)
    sizer.Add(st4, 0, wx.EXPAND | wx.ALL, 10)

    panel.SetSizer(sizer)

    frame.Show()

    # Run the main loop, which will close when the frame does.
    app.MainLoop()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
