#!/usr/bin/env python

#*****************************************************************************
#
# ViewToolbarControl.py
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
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle

# Local imports...


# Events...
myEVT_VIEW_CHANGED = wx.NewEventType()
EVT_VIEW_CHANGED = wx.PyEventBinder(myEVT_VIEW_CHANGED, 1)


# Public Constants...

# The order of bitmaps...
kUnselectedUp      = 0
kUnselectedPressed = 1
kSelectedUp        = 2
kSelectedDown      = 3


# Private Constants...

# On windows there is no break between toolbar items so we want to make sure we
# don't draw all the way to the edge.
if (wx.Platform == "__WXMAC__"):
    _kSidePadding = 0
else:
    _kSidePadding = 4


##############################################################################
class ViewToolbarControl(wx.Control):
    """A control for letting the user switch between views in the toolbar.

    These look roughly like the Mac's "segmented controls".  Unfortunately, wx
    doesn't have anything like this--especially something that would look good
    in the toolbar.

    This class is a bit fragile--it tries to "fit in" with other toolbar items,
    but it makes a lot of assumptions about how they will look.  Hopefully it
    won't require too much tweaking.
    """

    ###########################################################
    def __init__(self, parent, bitmapList):
        """ViewToolbarControl constructor.

        @param  parent      Our parent UI element, which should be the toolbar.
        @param  bitmapList  A list of lists of wx.Bitmap objects to place in
                            the control.  It should look like:
                            [
                                [ unselUp, unselPressed, selUp, selPressed ],
                                [ unselUp, unselPressed, selUp, selPressed ],
                                ...
                            ]
                            See the constants like kUnselectedUp above.
        """
        # Call our super
        super(ViewToolbarControl, self).__init__(
            parent, -1, style=wx.BORDER_NONE | wx.TRANSPARENT_WINDOW
        )

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Keep track of parameters...
        self._bitmapList = bitmapList

        # Set the font; do this early so we can use it in calculations...
        toolbarAttrs = parent.GetClassDefaultAttributes()
        self.SetFont(toolbarAttrs.font)

        # Figure out location / dimensions for the buttons...
        self._buttonsWidth, self._buttonsHeight = self._getButtonsSize()

        # Set our initial size.
        initialWidth, initialHeight = self._getInitialSize()
        self.SetSize((initialWidth, initialHeight))

        self._buttonsX, self._buttonsY = self._getButtonsPos()

        # We start out with item 0 selected...
        self._selection = 0

        # We'll put the index of the bitmap the mouse was clicked on...
        self._mouseDownOn = None

        # If the mouse is still over self._mouseDownOn, this will equal it;
        # else it will be None.
        self._showPressedDown = None


        # We need to paint ourselves...
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # We'll set this while we're tracking the mouse.  This helps keep
        # our state right without relying on HasCapture(), which is sometimes
        # wrong (especially with our capture workaround)
        self._trackingMouse = False

        # Bind to other mouse events...
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    ###########################################################
    def OnDestroy(self, event=None):
        """ Explicitly release mouse capture, if needed
        """
        if self.HasCapture():
            self.ReleaseMouse()

    ############################################################
    def OnSize(self, event=None):
        """Update as necessary in response to a size change.

        @param  event  The EVT_SIZE event, ignored.
        """
        self._buttonsX, self._buttonsY = self._getButtonsPos()
        self.Refresh()


    ############################################################
    def setSelection(self, selection):
        """Set the selection.

        @param  selection  The index (0 thru numBitmaps-1) to select.
        """
        self._selection = selection
        self.Refresh()


    ############################################################
    def getSelection(self):
        """Get the selection.

        @return selection  The index (0 thru numBitmaps-1) selected.
        """
        return self._selection


    ############################################################
    def OnMouseDown(self, event):
        """Handle mouse down events.

        @param  event  The event; may be a mouse down or even a double-click.
        """
        x, y = (event.X, event.Y)

        assert self._mouseDownOn is None

        self._mouseDownOn = self._findButtonNumForPoint(x, y)
        self._showPressedDown = self._mouseDownOn

        self._trackingMouse = True
        self.CaptureMouse()

        self.Refresh()


    ############################################################
    def OnMouseMove(self, event):
        """Handle mouse move events.

        We'll get these whenever the mouse moves over us.  The only time we
        really care is when we're tracking the pen, in which case we may need
        to update ourselves.

        @param  event  The event; may be a move event, a mouse up event, or
                       even a double-click event.
        """
        # If we think we're tracking the mouse but we don't have catpure,
        # we somehow lost it (which appears to be a wxMac bug?).  I've seen
        # this when you right click while holding the left button.  Treat
        # that as a mouse up.
        if (not self.HasCapture()) and (self._trackingMouse):
            self.OnMouseUp(event)


        if self._trackingMouse:
            x, y = (event.X, event.Y)

            mouseOverButtonNum = self._findButtonNumForPoint(x, y)
            if mouseOverButtonNum != self._mouseDownOn:
                mouseOverButtonNum = None

            if self._showPressedDown != mouseOverButtonNum:
                self._showPressedDown = mouseOverButtonNum
                self.Refresh()

        # Most other code I have always skips mouse moves.  Do that just to
        # be consistent (not sure it's needed).
        event.Skip()


    ############################################################
    def OnMouseUp(self, event):
        """Handle mouse up on the window.

        @param  event  The event; may be a mouse up or a double-click event.
        """
        if self._trackingMouse:
            # Do one last "mouse move".  Only do if we have capture to avoid
            # circular recursion...
            if self.HasCapture():
                self.OnMouseMove(event)

            # OK, we're not tracking any more...
            self._trackingMouse = False
            while self.HasCapture():
                self.ReleaseMouse()

            # Send an event if needed...
            if self._showPressedDown is not None:
                if self._selection != self._showPressedDown:
                    self._selection = self._showPressedDown
                    self._sendEvent()

            self._mouseDownOn = None
            self._showPressedDown = None

            self.Refresh()


    ###########################################################
    def OnDoubleClick(self, event):
        """Handle a double click.

        We just treat this as a mouse down and mouse up.  Why?  This way if
        a user just sits there clicking on the arrow, it will keep cycling
        directions.

        @param  event  The double-click event.
        """
        self.OnMouseDown(event)
        self.OnMouseUp(event)


    ###########################################################
    def OnPaint(self, event):
        """Paint ourselves.

        @param  event  The paint event.
        """
        # Get a device context.  We don't do buffered, since then we'd have to
        # worry about drawing our background...
        dc = wx.PaintDC(self)

        width, height = self.GetClientSize()

        x = self._buttonsX
        for i, bmpsForView in enumerate(self._bitmapList):
            if (i == self._showPressedDown) and (i == self._selection):
                bmp = bmpsForView[kSelectedDown]
            elif (i == self._selection):
                bmp = bmpsForView[kSelectedUp]
            elif (i == self._showPressedDown):
                bmp = bmpsForView[kUnselectedPressed]
            else:
                bmp = bmpsForView[kUnselectedUp]

            dc.DrawBitmap(bmp, x, self._buttonsY, True)
            bmpWidth, _ = bmp.GetWidth(), bmp.GetHeight()

            x += bmpWidth


    ############################################################
    def _getButtonsSize(self):
        """Return the size needed for all the buttons jammed together.

        @return size  The size for all the buttons.
        """
        height = 0
        width = 0
        for bmpsForView in self._bitmapList:
            bmp = bmpsForView[0]

            width += bmp.GetWidth()
            height = max(height, bmp.GetHeight())

        return (width+2*_kSidePadding, height)


    ############################################################
    def _getButtonsPos(self):
        """Returns the top-left coordinates for the buttons.

        Assumes that self._buttonsHeight is already set.

        @return pos  The top-left coordinate for the buttons.
        """
        _, h = self.GetSize()

        # The buttons should be centered, according to the toolbar's size.
        return _kSidePadding, (h - self._buttonsHeight+1) / 2


    ############################################################
    def _getInitialSize(self):
        """Figure out what size we should start out as.

        This is pretty ugly, since we need to deal with the MacOS weirdness.

        Assumes that:
        - Our parent is the toolbar...
        - self._buttonsWidth is already set.

        @return  initSize  Our initial size.
        """
        # Our width is based on the buttons
        width = self._buttonsWidth

        # Our height is based on the standard toolbar bitmap size...
        toolbar = self.GetParent()
        _, height = toolbar.GetToolBitmapSize()

        return (width, height)


    ############################################################
    def _findButtonNumForPoint(self, x, y):
        """Given an x and y, find which button number we're on.

        @param  x          The x value of the point.
        @param  y          The y value of the point.
        @return buttonNum  The button number, or None if we're not over a button
        """
        currX = self._buttonsX

        # Walk through bitmaps...
        for i, bmpsForView in enumerate(self._bitmapList):
            # Pick the first bitmap & get size (assumes all bitmaps in a group
            # are the same size).
            bmp = bmpsForView[0]
            width = bmp.GetWidth()
            height = bmp.GetHeight()

            # If we're within range of this button, we're done.  Break out...
            if (currX <= x < (currX + width)) and \
               (self._buttonsY <= y < self._buttonsY + height):
                break

            # Weren't in range of this one; move X.
            currX += width
        else:
            # If we get here, nothing was found.  Return None.
            return None

        return i


    ###########################################################
    def _sendEvent(self):
        """Send an event saying that our selection changed."""

        event = ViewToolbarControlEvent(myEVT_VIEW_CHANGED, self.GetId(),
                                        self._selection)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)


##############################################################################
class ViewToolbarControlEvent(wx.PyCommandEvent):
    """The event we fire off when our selection changes."""

    ###########################################################
    def __init__(self, eventType, id, newSelection):
        """ViewToolbarControlEvent constructor.

        @param  eventType     The type of the event, like
                              myEVT_VIEW_CHANGED
        @param  id            The ID.
        @param  newSelection  The new selection.
        """
        super(ViewToolbarControlEvent, self).__init__(eventType, id)
        self.newSelection = newSelection





##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    frame = wx.Frame(None, size=(600, 400))

    (normalBmpWidth, normalBmpHeight) = (24, 24)

    # Create the toolbar using the frame, which makes it pretty.
    toolbar = frame.CreateToolBar()

    toolbar.SetWindowStyle(wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT)
    toolbar.SetToolBitmapSize((normalBmpWidth, normalBmpHeight))

    def _emptyBitmap(width, height, color):
        # We'll use this bitmap as a placeholder...
        img = wx.EmptyImage(width, height)
        img.SetRGBRect(wx.Rect(0, 0, width, height), *color)
        return img.ConvertToBitmap()

    bmps = [
        [
            _emptyBitmap(16, 16, (255, 0, 0)), _emptyBitmap(16, 16, (191, 0, 0)),
            _emptyBitmap(16, 16, (127, 0, 0)), _emptyBitmap(16, 16, (63, 0, 0))
        ],
        [
            _emptyBitmap(16, 16, (0, 255, 0)), _emptyBitmap(16, 16, (0, 191, 0)),
            _emptyBitmap(16, 16, (0, 127, 0)), _emptyBitmap(16, 16, (0, 63, 0))
        ],
    ]

    viewControl = ViewToolbarControl(toolbar, bmps)
    _ = toolbar.AddControl(viewControl)

    #bmp = _emptyBitmap(normalBmpWidth, normalBmpHeight, (0, 0, 255))
    #toolbar.AddLabelTool(wx.ID_ANY, MenuIds._kViewMenu, bmp, bmp)

    if wx.Platform == '__WXMSW__' :
        # Stop the toolbar from flickering by setting to double buffered.
        # This happens in Windows only.
        toolbar.SetDoubleBuffered(True)
        # Setting the toolbar to doube buffered makes its background solid
        # black. To fix that, we just hijack its paint event, and clear the
        # paint DC. Technically, we can do whatever we want with it now; we
        # can draw our own themes and colours if we wanted to.
        def OnPaint(event):
            dc = wx.AutoBufferedPaintDCFactory(toolbar)
            dc.Clear()
        toolbar.Bind(wx.EVT_PAINT, OnPaint)

    toolbar.Realize()

    # Show...
    frame.Show()

    # Run the main loop, which will close when the frame does.
    app.MainLoop()



##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
