#! /usr/local/bin/python

#*****************************************************************************
#
# GradientPanel.py
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
#from vitaToolbox.profiling.MarkTime import resetMarkedTime, markTime, summarizeMarkedTime


# Constants

if wx.Platform == '__WXMAC__':
    _kDefaultStartColor = (173, 173, 173)
    _kDefaultEndColor = (220, 220, 220)
else:
    _kDefaultStartColor = (172, 214, 251)
    _kDefaultEndColor = (235, 249, 253)



##############################################################################
# GradientPanel introduces unnecessary complexities on Windows, causing
# GLCanvas to not function properly. Using regular wx.Panel instead resolves
# those problems, without a major impact to the UI
class GradientPanelWin(wx.Panel):
    def __init__(self, parent, id=wx.ID_ANY, #PYCHECKER Too many args OK--wx function
                 direction=wx.NORTH,
                 startColor=None, endColor=None,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=wx.TAB_TRAVERSAL | wx.BORDER_NONE,
                 name="panel"):
        # Call the base class initializer
        super(GradientPanelWin, self).__init__(parent, id, pos, size, style, name)

##############################################################################
class GradientPanelMac(wx.Panel):
    """A panel with a linear gradient background."""

    ###########################################################
    def __init__(self, parent, id=wx.ID_ANY, #PYCHECKER Too many args OK--wx function
                 direction=wx.NORTH,
                 startColor=None, endColor=None,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=wx.TAB_TRAVERSAL | wx.BORDER_NONE,
                 name="panel"):
        """The initializer for GradientPanel.

        @param  parent       The parent Window.
        @param  id           The ID
        @param  direction    The direction of the gradient.  NOTE: We have
                             special logic in this class to allow the extra:
                               (wx.NORTH | wx.EAST), (wx.NORTH | wx.WEST),
                               (wx.SOUTH | wx.EAST), (wx.SOUTH | wx.WEST)
        @param  startColor   The start color; if None, will be auto-assigned.
        @param  endColor     The end color; if None, will be auto-assigned.
        @param  pos          UI pos.
        @param  size         UI size.
        @param  style        UI style.
        """
        # Force some bits into the style.  wx.FULL_REPAINT_ON_RESIZE is
        # equivalent to catching the OnSize event and calling self.Refresh
        # within it. This can work for/against flickering depending on how
        # are widgets are drawn.  Because we are double-buffered, we won't see
        # flickering.  But, without this style, we will see children drawing
        # white or black backgrounds because this window is not being told
        # to redraw itself and all of its children during (and right after)
        # sizing events.
        style |= wx.FULL_REPAINT_ON_RESIZE

        # Call the base class initializer
        super(GradientPanelMac, self).__init__(parent, id, pos, size, style, name)

        # Tell the window that we do not want to receive EVT_ERASE_BACKGROUND
        # events.  This keeps wx from erasing our background for us and avoids
        # flicker.  Do *NOT* use wx.BG_STYLE_CUSTOM -- it is not currently
        # documented in wxWidgets and wxPython, and will be deprecated in the
        # future.  Use wx.BG_STYLE_PAINT instead.
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # --- IMPORTANT (MSW only) ---
        # According to:
        #
        # <https://msdn.microsoft.com/en-us/library/windows/desktop/ff700543(v=vs.90).aspx>
        #
        #   Window Extended Style Flag: WS_EX_COMPOSITED = 0x02000000L:
        #       "Paints all descendants of a window in bottom-to-top painting
        #       order using double-buffering. For more information, see Remarks.
        #       This cannot be used if the window has a class style of either
        #       CS_OWNDC or CS_CLASSDC."
        #
        #   Window Extended Style Flag: WS_EX_TRANSPARENT = 0x00000020L:
        #       "The window should not be painted until siblings beneath the
        #       window (that were created by the same thread) have been painted.
        #       The window appears transparent because the bits of underlying
        #       sibling windows have already been painted."
        #
        # <https://msdn.microsoft.com/en-us/library/windows/desktop/ms632680(v=vs.90).aspx>
        #
        #   Under 'Remarks':
        #       "With WS_EX_COMPOSITED set, all descendants of a window get
        #       bottom-to-top painting order using double-buffering.
        #       Bottom-to-top painting order allows a descendent window to have
        #       translucency (alpha) and transparency (color-key) effects, but
        #       only if the descendent window also has the WS_EX_TRANSPARENT bit
        #       set. Double-buffering allows the window and its descendents to
        #       be painted without flicker."
        #
        # <https://msdn.microsoft.com/en-us/library/windows/desktop/dd374250(v=vs.90).aspx>
        #
        #   Under 'The generic (software) implementation (of OpenGL) has the
        #   following limitations':
        #
        #       " - OpenGL and GDI graphics cannot be mixed in a double-buffered
        #           window.
        #               Note:   An application can directly draw both OpenGL
        #                       graphics and GDI graphics into a single-buffered
        #                       window, but not into a double-buffered window."
        #
        # Avoid flicker when translucent children are drawn...
        self.SetDoubleBuffered(True)

        # Adjust params...
        if startColor is None: startColor = _kDefaultStartColor
        if endColor is None: endColor = _kDefaultEndColor

        # Save params...
        self._direction = direction
        self._startColor = wx.Colour(*startColor)
        self._endColor = wx.Colour(*endColor)

        # Keep a copy of our current background image as a wx.Bitmap...
        self._backgroundBmp = None

        # Bind to paint events
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        # Get the initial background ready.
        self._updateBackground()


    ###########################################################
    def OnSize(self, event):
        """Handle size events to re-create our background.

        Do this OnSize() instead of just checking cache in OnPaint() for
        best speed possible...

        @param  event  The size event.
        """
        # We never eat the event...
        if event is not None:
            event.Skip()

        self._updateBackground()


    ###########################################################
    def _updateBackground(self):
        """ Creates (or refreshes) the background image.
        """

        width, height = self.GetClientSize()

        # If zero-sized, just return...
        if (width == 0) or (height == 0):
            self._backgroundBmp = None
            return

        # If no size change, just return...
        if self._backgroundBmp is not None:
            oldWidth, oldHeight = self._backgroundBmp.GetSize()
            if (oldWidth, oldHeight) == (width, height):
                return


        self._backgroundBmp = wx.Bitmap.FromRGBA(width, height)
        memDC = wx.MemoryDC(self._backgroundBmp)
        gc = wx.GraphicsContext.Create(memDC)

        # Get start and end points, adjusting negative ones (since that means
        # they are specified from the opposite end of the screen)...
        if self._direction & wx.SOUTH:
            (y1, y2) = (0, height)
        elif self._direction & wx.NORTH:
            (y1, y2) = (height, 0)
        else:
            y1 = y2 = 0
        if self._direction & wx.EAST:
            (x1, x2) = (0, width)
        elif self._direction & wx.WEST:
            (x1, x2) = (width, 0)
        else:
            x1 = x2 = 0

        # Draw the rectangle with the gradient...
        gradientBrush = gc.CreateLinearGradientBrush(
            x1, y1, x2, y2, self._startColor, self._endColor
        )
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(gradientBrush)
        gc.DrawRectangle(0, 0, width, height)

        memDC.SelectObject(wx.NullBitmap)


    ###########################################################
    def OnPaint(self, event):
        """Draw ourselves...

        @param  event  The paint event.
        """
        dc = wx.BufferedPaintDC(self, self._backgroundBmp)


if wx.Platform == '__WXMAC__':
    GradientPanel = GradientPanelMac
else:
    GradientPanel = GradientPanelWin

##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = GradientPanel(frame, direction=(wx.NORTH | wx.WEST), startColor=(0, 0, 0))
    _ = panel

    frame.Show()

    #if True:
    #    countList = [0]
    #    timer = wx.Timer(panel, -1)
    #    def OnTimer(event):
    #        if countList[0] == 0:
    #            resetMarkedTime()
    #        elif countList[0] >= 1000:
    #            summarizeMarkedTime()
    #            timer.Stop()
    #        countList[0] += 1
    #        panel.Refresh()
    #    panel.Bind(wx.EVT_TIMER, OnTimer, timer)
    #    timer.Start(1, False)

    # Run the main loop, which will close when the frame does.
    app.MainLoop()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
