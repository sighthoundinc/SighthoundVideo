#!/usr/bin/env python

#*****************************************************************************
#
# ListBoxWithIcons.py
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
from vitaToolbox.wx.TruncateText import truncateText

# Local imports...

# Special imports...


# Constants...
_kIconSpacing = 2

# Horizontal and vertical margins; seems to be different on Mac and Win...
# ...also need an extra few pixels on Mac when settings our default size...
if wx.Platform == '__WXMAC__':
    _kMargins = (5, 1)
    _kExtraHeight = 2
else:
    _kMargins = (2, 1)
    _kExtraHeight = 0


# This is supposed to be in Carbon.Appearance, but appears missing...
kThemeBrushAlternatePrimaryHighlightColor = -5

# ...this is in Carbon.Appearance, but since we're hardcoding the above anyway
# we might as well hardcode this (so we don't have to deal with obfuscator
# weirdness of this not being on Windows)
kThemeBrushSecondaryHighlightColor = -4


##############################################################################
class ListBoxWithIcons(wx.VListBox):
    """Implements a list box with icons on the right.

    API should be as close to wx.ListBox as possible.
    """

    ###########################################################
    def __init__(self, parent, id=wx.ID_ANY, style=wx.BORDER_THEME):
        """The initializer for ListBoxWithIcons

        @param  parent       The parent window
        @param  id           Our UI ID.
        """
        # Call the base class initializer
        super(ListBoxWithIcons, self).__init__(parent, id, style=style)

        # Set the margins to something reasonable...
        self.SetMargins(_kMargins)

        # A list of our items.  See AppendItems()
        self._items = []

        # We draw slightly different depending on whether our window is
        # active, at least on Mac...
        if wx.Platform == '__WXMAC__':
            self._isActive = True
            self.GetTopLevelParent().Bind(wx.EVT_ACTIVATE, self.OnActivate)


    ###########################################################
    def setMinNumRows(self, numRows):
        """Set the minimum size based on number of rows.

        This assumes that you've already set our font right.  It also assumes
        that the text is the tallest thing in the row, not the icons.

        @param  numRows  The number of rows to show.
        """
        # Measure the rows...
        height = 0
        for i in range(numRows):
            height += self.OnMeasureItem(i)
        height += _kExtraHeight

        # Set the client size, which takes into account borders...
        self.SetClientSize((0, height))

        # Set the minimum size by the current size...
        self.SetMinSize(self.GetSize())


    ###########################################################
    def AppendItems(self, items):
        """Append the given items to the list.

        @param  items  A list of items.  Should be tuples:
                           (itemText, iconBmpList)
                       ...iconBmpList is list of wx.Bitmaps for icons to show
                       with this item.
        """
        self._items += items
        self.SetItemCount(len(self._items))
        self.Refresh()


    ###########################################################
    def Clear(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Clear the items in the list."""
        self._items = []
        self.SetItemCount(0)
        self.SetSelection(-1)
        self.Refresh()

        # I don't know if this is needed, but seems like maybe a good idea?
        super(ListBoxWithIcons, self).Clear()


    ###########################################################
    def SetStringSelection(self, itemText):
        """Sets selection based on text.

        @param  itemText  The text of the item to select.
        """
        for i, (thisItemText, _) in enumerate(self._items):
            if thisItemText == itemText:
                self.SetSelection(i)
                return

        assert False, "%s not in list" % itemText
        self.SetSelection(-1)


    ###########################################################
    def GetStringSelection(self):
        """Returns the itemText for the current selection.

        @return itemText  The itemText for the current selection.
        """
        selection = self.GetSelection()
        if selection == -1:
            return ""
        else:
            itemText, _ = self._items[selection]
            return itemText


    ###########################################################
    def GetStrings(self):
        """Return a list of all of our itemText elements.

        @return itemTextList  A list of our itemText.
        """
        return [itemText for (itemText, _) in self._items]


    ###########################################################
    def OnActivate(self, event):
        """Handle activate events on our top level parent.

        We just refresh, and cache active state.  Mac ONLY.

        @param  event  The activate event.
        """
        # Cache whether we're active, since calling IsActive() on the top
        # level window always seems to return true...
        self._isActive = event.GetActive()

        self.Refresh()
        event.Skip()


    ###########################################################
    def OnDrawItem(self, dc, rect, n):
        """Draw the item with the given index

        @param  dc    The drawing context in which to draw
        @param  rect  The rectangle in which to draw
        @param  n     The index of the item to draw
        """
        # Make a copy of the rect so we can mess with it (TODO: needed?)
        rect = wx.Rect(*rect.Get())

        # Get the item we're drawing...
        itemText, iconBmpList = self._items[n]

        if n == self.GetSelection():
            # Mac seems to have very special rules for selection colors...
            if wx.Platform == '__WXMAC__':
                if self._isActive:
                    fgColor = "white"
                else:
                    fgColor = "black"
            else:
                fgColor = wx.SystemSettings.GetColour(
                    wx.SYS_COLOUR_HIGHLIGHTTEXT
                )
        else:
            fgColor = self.GetForegroundColour()

        # First, do the bitmaps, right to left...
        for iconBmp in reversed(iconBmpList):
            iconWidth = iconBmp.GetWidth()
            iconHeight = iconBmp.GetHeight()
            x = rect.right - _kIconSpacing - iconWidth
            y = rect.top + ((rect.height - iconHeight) // 2)
            dc.DrawBitmap(iconBmp, x, y, True)

            rect.SetWidth(rect.width - (iconWidth + _kIconSpacing))

        # Next, the text...
        dc.SetFont(self.GetFont())
        dc.SetTextForeground(fgColor)
        itemText = truncateText(dc, itemText, rect.width - (2 * _kIconSpacing))
        dc.DrawLabel(itemText, rect, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)


    ###########################################################
    def OnDrawBackground(self, dc, rect, n): #PYCHECKER signature mismatch OK
        """Draw the background and border for the given item

        @param  dc    The drawing context in which to draw
        @param  rect  The rectangle in which to draw
        @param  n     The index of the item to draw
        """
        if n == self.GetSelection():
            # Mac seems to have very special rules for selection colors...
            if wx.Platform == '__WXMAC__':
                brush = wx.Brush(wx.BLACK)
                if self._isActive:
                    brush = wx.Brush(wx.MacThemeColour(kThemeBrushAlternatePrimaryHighlightColor))
                else:
                    brush = wx.Brush(wx.MacThemeColour(kThemeBrushSecondaryHighlightColor))
            else:
                brush = wx.Brush(
                    wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
                )
        else:
            brush = wx.Brush(self.GetBackgroundColour())

        dc.SetBackground(brush)
        dc.Clear()


    ###########################################################
    def OnMeasureItem(self, n):
        """Return the height of an item in the list box

        @param  n     The index of the item to retrieve the height of
        """
        if n >= len(self._items):
            # If we're asked to measure something we don't have, just use "X"
            _, height = self.GetTextExtent("X")
        else:
            # Get the item we're measuring...
            itemText, iconBmpList = self._items[n]

            # Start out with the text...
            _, height = self.GetTextExtent(itemText)

            # Now go through the icons...
            for iconBmp in reversed(iconBmpList):
                height = max(height, iconBmp.GetHeight())

        return height


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    from vitaToolbox.wx.GradientPanel import GradientPanel
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = GradientPanel(frame, startColor=(172, 0, 0))
    #panel = wx.Panel(frame)
    panel.SetDoubleBuffered(True)

    recordEnabledBmp = wx.Bitmap("frontEnd/bmps/Response_Save_Enabled.png")
    recordDisabledBmp = wx.Bitmap("frontEnd/bmps/Response_Save_Disabled.png")
    #emailEnabledBmp = wx.Bitmap("frontEnd/bmps/Response_Email_Enabled.png")
    emailDisabledBmp = wx.Bitmap("frontEnd/bmps/Response_Email_Disabled.png")

    items = [
        ("All Objects", []),
        ("People", []),
        ("Unknown objects", []),
        ("All Objects in Front Camera", [recordEnabledBmp]),
        ("All Objects in Back Camera", [emailDisabledBmp, recordDisabledBmp]),
        ("Really, really, really, really, really, really, really, really "
         "really, really, really, really long rule", [recordEnabledBmp]),
    ]

    lookForList = ListBoxWithIcons(panel)
    lookForList.setMinNumRows(4)
    lookForList.SetMinSize((300, lookForList.GetMinSize()[1]))
    lookForList.AppendItems(items)
    lookForList.SetStringSelection("People")

    clearButton = wx.Button(panel, -1, "Clear")
    appendButton = wx.Button(panel, -1, "Append")

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    yellowWin = wx.Window(panel, -1, size=(64, 64))
    yellowWin.SetBackgroundColour("yellow")
    sizer.Add(yellowWin, 0, wx.EXPAND)

    vertSizer = wx.BoxSizer(wx.VERTICAL)
    vertSizer.AddStretchSpacer(1)
    vertSizer.Add(lookForList, 0, wx.ALIGN_CENTER_HORIZONTAL)
    vertSizer.Add(clearButton, 0, wx.ALIGN_CENTER_HORIZONTAL)
    vertSizer.Add(appendButton, 0, wx.ALIGN_CENTER_HORIZONTAL)
    vertSizer.AddStretchSpacer(1)
    sizer.Add(vertSizer, 1, wx.EXPAND)

    yellowWin = wx.Window(panel, -1, size=(64, 64))
    yellowWin.SetBackgroundColour("yellow")
    sizer.Add(yellowWin, 0, wx.EXPAND)

    panel.SetSizer(sizer)

    frameSizer = wx.BoxSizer()
    frameSizer.Add(panel, 1, wx.EXPAND)
    frame.SetSizer(frameSizer)
    frame.Fit()

    def onClear(event):
        lookForList.Clear()
    def onAppend(event):
        lookForList.AppendItems(items)
    clearButton.Bind(wx.EVT_BUTTON, onClear)
    appendButton.Bind(wx.EVT_BUTTON, onAppend)

    frame.CenterOnParent()
    frame.Show()

    # Run the main loop, which will close when the frame does.
    app.MainLoop()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
