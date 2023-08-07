#! /usr/local/bin/python

#*****************************************************************************
#
# ImagePanel.py
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
from PIL import Image
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle


##############################################################################
class ImagePanel(wx.Panel):
    """A panel that has a (possibly translucent) background image.

    NOTES:
    - May be important (at least for Windows) that at least one of our
      parents has SetDoubleBuffered(True).  ...otherwise, we may get drawing
      problems or blinkiness.
    """

    ###########################################################
    def __init__(self, parent, id, backgroundBmp,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=wx.TAB_TRAVERSAL | wx.BORDER_NONE |
                 wx.TRANSPARENT_WINDOW, name="panel"):
        """The initializer for ImagePanel.

        @param  parent         The parent Window.
        @param  id             The ID
        @param  backgroundBmp  The background bitmap to use.  Can be a
                               wx.Bitmap or a string with a path to a file.
                               If it has alpha, we will use it when drawing.
        @param  pos            UI pos.
        @param  size           UI size; if not (-1, -1) (the default), sets
                               initial size and best size.
        @param  style          UI style; if you want partial translucenty,
                               make sure you include wx.TRANSPARENT_WINDOW.
        """
        # Call the base class initializer
        super(ImagePanel, self).__init__(parent, id, pos, size, style, name)

        # Save our best size as the one passed in, with is (-1, -1) by default
        self._bestSize = size

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Save params...
        if isinstance(backgroundBmp, basestring):
            backgroundBmp = wx.Bitmap(backgroundBmp)
        self._backgroundBmp = backgroundBmp

        # Bind to paint events
        self.Bind(wx.EVT_PAINT, self.OnPaint)


    ###########################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Tell wx what our best size should be.

        @return  bestSize  Our best size.
        """
        # If a size was specified, use that; else use the text size.
        bestWidth, bestHeight = self._bestSize
        bitmapWidth = self._backgroundBmp.GetWidth()
        bitmapHeight = self._backgroundBmp.GetHeight()
        if bestWidth == -1:
            bestWidth = bitmapWidth
        if bestHeight == -1:
            bestHeight = bitmapHeight

        return (bestWidth, bestHeight)


    ###########################################################
    def OnPaint(self, event):
        """Draw ourselves...

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self)
        dc.DrawBitmap(self._backgroundBmp, 0, 0, True)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    panel.SetBackgroundColour("yellow")

    # Pass path to bitmap in sys.argv[2]
    ip1 = ImagePanel(panel, -1, sys.argv[2])
    ip2 = ImagePanel(panel, -1, sys.argv[2])

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(ip1, 1, wx.EXPAND | wx.ALL, 0)
    sizer.Add(ip2, 1, wx.EXPAND | wx.ALL, 0)

    panel.SetSizer(sizer)

    frameSizer = wx.BoxSizer()
    frameSizer.Add(panel, 1, wx.EXPAND)
    frame.SetSizer(frameSizer)

    frame.Fit()
    frame.Show()

    # Run the main loop, which will close when the frame does.
    app.MainLoop()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
