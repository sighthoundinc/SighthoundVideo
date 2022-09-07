#! /usr/local/bin/python

#*****************************************************************************
#
# BorderImagePanel.py
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
# https://github.com/sighthoundinc/SighthoundVideo
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
from vitaToolbox.image.BorderImage import loadBorderImage


##############################################################################
class BorderImagePanel(wx.Panel):
    """A panel that has a (possibly translucent) background border image."""

    ###########################################################
    def __init__(self, parent, id, borderImage, borderWidth,
                 borderHeight=None,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=wx.TAB_TRAVERSAL | wx.BORDER_NONE |
                 wx.TRANSPARENT_WINDOW,
                 name="panel"):
        """The initializer for BorderImagePanel.

        @param  parent       The parent Window.
        @param  id           The ID
        @param  borderImage  The border image to use.  This will be used as the
                             src to loadBorderImage()
        @param  borderWidth  The width of the border in the image.
        @param  borderHeight The height of the border in the image, or None to
                             use the width.
        @param  pos          UI pos.
        @param  size         UI size.
        @param  style        UI style.
        """
        # Call the base class initializer
        super(BorderImagePanel, self).__init__(parent, id, pos, size, style, name)

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Save params...
        self._borderImage = borderImage
        self._borderWidth = borderWidth
        self._borderHeight = borderHeight

        # Find our border image...

        #12-18-2009 There is a problem running the auto installer on windows
        # where is this files is kept in a locked state if passed to Image.open
        # There is a 2.6 call which forces these file handles to not be inherited
        # by the sub process but that doesn't seem to work on 2.4
        srcImage = Image.open(self._borderImage)

        self._borderPilImg = srcImage.copy()

        # Keep a copy of our current background image as a wx.Bitmap...
        self._backgroundBmp = None

        # Bind to paint events
        self.Bind(wx.EVT_PAINT, self.OnPaint)


    ###########################################################
    def OnPaint(self, event):
        """Draw the gradient line.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self)
        width, height = self.GetClientSize()

        # Invalidate any existing background bitmap if it's not the right size.
        if self._backgroundBmp is not None:
            oldWidth, oldHeight = self._backgroundBmp.GetSize()
            if (oldWidth, oldHeight) != (width, height):
                self._backgroundBmp = None

        # If we need to make a background bitmap, make it!
        if self._backgroundBmp is None:
            img = loadBorderImage(self._borderPilImg, (width, height),
                                  self._borderWidth, self._borderHeight)
            img = img.convert("RGBA")
            if img.size[0] > 0 and img.size[1] > 0:
                self._backgroundBmp = \
                    wx.Bitmap.FromBufferRGBA(width, height, img.tobytes())

        # Finally, draw...
        if self._backgroundBmp is not None:
            dc.DrawBitmap(self._backgroundBmp, 0, 0, True)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    from GradientPanel import GradientPanel
    app = wx.App(False)

    borderImg = 'frontEnd/bmps/RaisedPanelBorder.png'
    borderWidth = 8

    frame = wx.Frame(None)
    panel = GradientPanel(frame)

    rp1 = BorderImagePanel(panel, -1, borderImg, borderWidth)
    rp2 = BorderImagePanel(panel, -1, borderImg, borderWidth)

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    sizer.Add(rp1, 1, wx.EXPAND | wx.ALL, 30)
    sizer.Add(rp2, 1, wx.EXPAND | wx.ALL, 30)

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
