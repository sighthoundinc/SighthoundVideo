#! /usr/local/bin/python

#*****************************************************************************
#
# GradientEndedLine.py
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



# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from DoubleBufferCompatGc import createDoubleBufferCompatGc



class GradientEndedLine(wx.Window):
    """A line with gradient edges."""
    ###########################################################
    def __init__(self, parent, lineColor, endColor, lineHeight=2,
                 maxEndWidth=-1, style=wx.LI_HORIZONTAL):
        """The initializer for GradientEndedLine.

        @param  parent       The parent Window.
        @param  lineColor    An (r,g,b) tuple representing the main line color.
        @param  endColor     An (r,g,b) tuple representing the line end color.
        @param  lineHeight   The height of the line.
        @param  maxEndWidth  The maximum size of the gradient portion, or -1.
        @param  style        Like wx.StaticLine, can be either wx.LI_HORIZONTAL
                             or wx.LI_VERTICAL.
        """
        # Force style...
        style |= wx.TRANSPARENT_WINDOW

        # Figure out size depending on horizontal or vertical...
        if (style & wx.LI_HORIZONTAL):
            size = (-1, lineHeight)
        else:
            size = (lineHeight, -1)

        # Call the base class initializer
        super(GradientEndedLine, self).__init__(parent, -1, size=size,
                                                style=style)

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Save the max width
        self._maxEndWidth = maxEndWidth

        # Set the background and save our colors
        self._mainColor = wx.Colour(*lineColor)
        self._endColor = wx.Colour(*endColor)

        # Bind to paint events
        self.Bind(wx.EVT_PAINT, self.OnPaint)


    ###########################################################
    def OnPaint(self, event):
        """Draw the gradient line.

        @param  event  The paint event.
        """
        # Get a dc and our width
        dc = wx.PaintDC(self)
        gc, finishFn = createDoubleBufferCompatGc(dc)
        w, h = self.Size
        style = self.GetWindowStyle()

        if (style & wx.LI_HORIZONTAL):
            gradientWidth = w/2
        else:
            gradientWidth = h/2

        if self._maxEndWidth != -1:
            # If we have a max gradient size ensure we're within bounds
            gradientWidth = min(gradientWidth, self._maxEndWidth)

        # Always use transparent pen...
        gc.SetPen(wx.TRANSPARENT_PEN)

        if (style & wx.LI_HORIZONTAL):
            gc.SetBrush(gc.CreateLinearGradientBrush(
                0, 0, gradientWidth, 0, self._endColor, self._mainColor
            ))
            gc.DrawRectangle(0, 0, gradientWidth, h)

            gc.SetBrush(wx.Brush(self._mainColor))
            gc.DrawRectangle(gradientWidth, 0, w-2*gradientWidth, h)

            gc.SetBrush(gc.CreateLinearGradientBrush(
                w-gradientWidth, 0, w, 0, self._mainColor, self._endColor
            ))
            gc.DrawRectangle(w-gradientWidth, 0, gradientWidth, h)
        else:
            gc.SetBrush(gc.CreateLinearGradientBrush(
                0, 0, 0, gradientWidth, self._endColor, self._mainColor
            ))
            gc.DrawRectangle(0, 0, w, gradientWidth)

            gc.SetBrush(wx.Brush(self._mainColor))
            gc.DrawRectangle(0, gradientWidth, w, h-2*gradientWidth)

            gc.SetBrush(gc.CreateLinearGradientBrush(
                0, h-gradientWidth, 0, h, self._mainColor, self._endColor
            ))
            gc.DrawRectangle(0, h-gradientWidth, w, gradientWidth)

        finishFn()


##############################################################################
if __name__ == '__main__':
    app = wx.App(redirect=bool("__WXMAC__" not in wx.PlatformInfo))
    frame = wx.Frame(None, -1, "GradientLineTest", size=(400,400))

    frame.SetDoubleBuffered(True)

    lineA = GradientEndedLine(frame, (255,128,128), (255,255,255))
    lineB = GradientEndedLine(frame, (255,128,128), (255,255,255),
                              maxEndWidth=50)

    lineC = GradientEndedLine(frame, (255,128,128), (255,128,128,0))

    lineD = GradientEndedLine(frame, (255,128,128), (255,255,255),
                              style=wx.LI_VERTICAL)
    lineE = GradientEndedLine(frame, (255,128,128), (255,255,255),
                              maxEndWidth=50, style=wx.LI_VERTICAL)
    lineF = GradientEndedLine(frame, (255,128,128), (255,128,128,0),
                              style=wx.LI_VERTICAL)

    frame.SetBackgroundColour("yellow")
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.AddStretchSpacer(1)
    sizer.Add(wx.StaticText(frame, -1, "Below line is gradient all the way"))
    sizer.Add(lineA, 0, wx.EXPAND)
    sizer.AddSpacer(20)
    sizer.Add(wx.StaticText(frame, -1,
                            "Below line is gradient for a max of 50 pixels"))
    sizer.Add(lineB, 0, wx.EXPAND)
    sizer.AddSpacer(20)
    sizer.Add(wx.StaticText(frame, -1,
                            "Below lines uses alpha blend in its gradient"))
    sizer.Add(lineC, 0, wx.EXPAND)

    hSizer = wx.BoxSizer(wx.HORIZONTAL)
    hSizer.Add(wx.StaticText(frame, -1,
                             "Here are vertical versions of the same 3 lines:"))
    hSizer.AddStretchSpacer(1)
    hSizer.Add(lineD, 0, wx.EXPAND | wx.LEFT, 20)
    hSizer.Add(lineE, 0, wx.EXPAND | wx.LEFT, 20)
    hSizer.Add(lineF, 0, wx.EXPAND | wx.LEFT, 20)
    hSizer.AddStretchSpacer(1)
    sizer.Add(hSizer, 3, wx.EXPAND | wx.TOP, 20)
    frame.SetSizer(sizer)

    frame.Show(1)
    app.MainLoop()
