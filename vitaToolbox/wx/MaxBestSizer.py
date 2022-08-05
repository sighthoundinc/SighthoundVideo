#!/usr/bin/env python

#*****************************************************************************
#
# MaxBestSizer.py
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

# Local imports...

# Constants...


##############################################################################
class MaxBestSizer(wx.Sizer):
    """A sizer that doesn't let its child get bigger than its best size.

    This sizer should be given one child.  You can expand the sizeras big as you
    want, but it will never allow the child to get bigger than its best size.

    This is useful in some strange layout cases.  Specifically, it seems to be
    useful if you want to make an object it's best size _or smaller_.

    Note that this sizer ignores the child proportion.  However, it does pay
    attention to the following flags:
    - wx.ALIGN_TOP (0)
    - wx.ALIGN_BOTTOM
    - wx.ALIGN_CENTER_VERTICAL
    - wx.ALIGN_LEFT (0)
    - wx.ALIGN_RIGHT
    - wx.ALIGN_CENTER_HORIZONTAL

    Note that this sizer _does_ pay attention to the child's min size.
    """
    ###########################################################
    def __init__(self, childWin,
                 childFlag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL,
                 style=wx.HORIZONTAL | wx.VERTICAL):
        """MaxBestSizer constructor.

        @param  childWin   The child window to add to ourselves; should be a
                           Window, not a sizer.
        @param  childFlag  The flags to use when adding the child window.
        @param  style      Normally, we apply the "max best" rules both
                           vertically and horizontally.  If you only want one,
                           specify it.
        """
        super(MaxBestSizer, self).__init__()

        assert isinstance(childWin, wx.Window)
        assert style != 0

        self.__style = style

        self.Add(childWin, 0, childFlag)


    ###########################################################
    def CalcMin(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Calculate the minimum space that this sizer needs.

        This _must_ be called before RecalcSizes(), since we cache values here
        and assume they're up to date in RecalcSizes().

        @return size  The minimum size.
        """
        minWidth, minHeight = (-1, -1)

        # Get our child...
        children = self.GetChildren()
        assert len(children) == 1, "Must have exactly one child"
        child = children[0]

        # Pass our child's min through; else -1, -1
        if child.IsShown():
            return child.CalcMin()
        else:
            return (-1, -1)


    ###########################################################
    def RecalcSizes(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Size up all of our children.

        This is called whenever we need to size our children, and is the
        guts of the sizer.
        """
        # Get our full size...
        x, y = self.GetPosition()
        width, height = self.GetSize()

        # Get our child...
        children = self.GetChildren()
        assert len(children) == 1, "Must have exactly one child"
        child = children[0]
        assert child.IsWindow(), "Child must be a wx.Window"

        # If we're smaller than the child's min size, pretend we aren't...
        minWidth, minHeight = child.CalcMin()
        width = max(width, minWidth)
        height = max(height, minHeight)

        # Get child's flags and maxWidth / maxHeight...
        flag = child.GetFlag()
        maxWidth, maxHeight = child.GetWindow().GetBestSize()

        if (self.__style & wx.VERTICAL) and (height > maxHeight):
            extraHeight = height - maxHeight

            if flag & wx.ALIGN_BOTTOM:
                y += extraHeight
            elif flag & wx.ALIGN_CENTER_VERTICAL:
                y += extraHeight / 2

            height = maxHeight

        if (self.__style & wx.HORIZONTAL) and (width > maxWidth):
            extraWidth = width - maxWidth

            if flag & wx.ALIGN_RIGHT:
                x += extraWidth
            elif flag & wx.ALIGN_CENTER_HORIZONTAL:
                x += extraWidth / 2

            width = maxWidth

        child.SetDimension((x, y), (width, height))



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    frame = wx.Frame(None, size=(600, 400))
    panel = wx.Panel(frame)
    panel.SetBackgroundColour("yellow")

    choices = [
        "One",
        "Two",
        "Eleventeen",
        "Twenty twelve billion",
    ]

    label1 = wx.StaticText(panel, -1, "Normal case:")
    choice1 = wx.Choice(panel, -1, choices=choices)
    choice1.SetMinSize((1, -1))

    label2 = wx.StaticText(panel, -1, "Test\ncenter\nvertical:")
    choice2 = wx.Choice(panel, -1, choices=choices)
    choice1.SetMinSize((1, -1))

    label3 = wx.StaticText(panel, -1, "Normal two\nline case:")
    field3 = wx.TextCtrl(panel)

    label4 = wx.StaticText(panel, -1, "Center\ncenter:")
    field4 = wx.TextCtrl(panel)

    label5 = wx.StaticText(panel, -1, "Bottom\nright:")
    field5 = wx.TextCtrl(panel)

    label6 = wx.StaticText(panel, -1, "Top\nleft:")
    field6 = wx.TextCtrl(panel)

    label7 = wx.StaticText(panel, -1, "Vertical\nonly:")
    field7 = wx.TextCtrl(panel)

    label8 = wx.StaticText(panel, -1, "Horizontal\nonly:")
    field8 = wx.TextCtrl(panel)

    sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=6, hgap=6)
    sizer.AddGrowableCol(1)

    sizer.Add(label1, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(choice1, 1, wx.EXPAND)

    sizer.Add(label2, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(MaxBestSizer(choice2), 1, wx.EXPAND)

    sizer.Add(label3, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(field3, 1, wx.EXPAND)

    sizer.Add(label4, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(MaxBestSizer(field4, wx.ALIGN_CENTER_VERTICAL |
                           wx.ALIGN_CENTER_HORIZONTAL),
              1, wx.EXPAND)

    sizer.Add(label5, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(MaxBestSizer(field5, wx.ALIGN_BOTTOM |
                           wx.ALIGN_RIGHT),
              1, wx.EXPAND)

    sizer.Add(label6, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(MaxBestSizer(field6, wx.ALIGN_TOP |
                           wx.ALIGN_LEFT),
              1, wx.EXPAND)

    sizer.Add(label7, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(MaxBestSizer(field7, wx.ALIGN_CENTER_VERTICAL |
                           wx.ALIGN_CENTER_HORIZONTAL, wx.VERTICAL),
              1, wx.EXPAND)

    sizer.Add(label8, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(MaxBestSizer(field8, wx.ALIGN_CENTER_VERTICAL |
                           wx.ALIGN_CENTER_HORIZONTAL, wx.HORIZONTAL),
              1, wx.EXPAND)

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
