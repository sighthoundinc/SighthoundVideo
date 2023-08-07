#!/usr/bin/env python

#*****************************************************************************
#
# RadioPushButton.py
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
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle

# Local imports...

# Constants...

if wx.Platform == '__WXMAC__':
    # All colors are tuples:       text color,           background color,     borderColor
    _kDefaultNormalColor        = ((96, 96, 96, 255), (  0,   0,   0,   0), (0, 0, 0,   0))
    _kDefaultDisabledColor      = ((96, 96, 96, 255), (  0,   0,   0,   0), (0, 0, 0,   0))
    _kDefaultSelectedColor      = ((244, 244, 244, 255), (122, 122, 122, 255), (0, 0, 0,   0))
    _kDefaultPressedColor       = ((244, 244, 244, 255), (100, 100, 100, 255), (0, 0, 0,   0))
    _kDefaultHoverColor         = ((96, 96, 96, 255), (244, 244, 244, 255), (0, 0, 0,   0))
    _kDefaultHoverSelectedColor = ((244, 244, 244, 255), (122, 122, 122, 255), (0, 0, 0,   0))
else:
    _kDefaultNormalColor        = (( 45,  80, 138, 255), (  0,   0,   0,   0), (0, 0, 0,   0))
    _kDefaultDisabledColor      = ((160, 179, 198, 255), (  0,   0,   0,   0), (0, 0, 0,   0))
    _kDefaultSelectedColor      = ((255, 255, 255, 255), (149, 169, 204, 255), (0, 0, 0,   0))
    _kDefaultPressedColor       = ((255, 255, 255, 255), ( 56,  81, 121, 255), (0, 0, 0,   0))
    _kDefaultHoverColor         = (( 45,  80, 138, 255), (193, 203, 221, 255), (0, 0, 0,   0))
    _kDefaultHoverSelectedColor = ((255, 255, 255, 255), (149, 169, 204, 255), (0, 0, 0,   0))

# Space used to give a border when getting the best size...
_kBorderSpace = 4

##############################################################################
class RadioPushButton(wx.Control):
    """A generically implemented button that supports radio-like behavior.

    This button is implemented all in python and supports a few features:
    - Implements radio-button type behavior.  Only one button in a given
      radio group can be "pressed" at once.
    - Has a hover state.  We draw this state when the mouse is over the button.
    - Supports translucency.
    """

    ###########################################################
    def __init__(self, parent, label, #PYCHECKER OK: Lots of args OK in this case...
                 normalColor=_kDefaultNormalColor,
                 disabledColor=_kDefaultDisabledColor,
                 selectedColor=_kDefaultSelectedColor,
                 pressedColor=_kDefaultPressedColor,
                 hoverColor=_kDefaultHoverColor,
                 hoverSelectedColor=_kDefaultHoverSelectedColor,
                 cornerRadius=2,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=0):
        """RadioPushButton constructor.

        @param  parent             Our parent UI element.
        @param  label              Our label.
        @param  normalColor        A tuple: (textColor, bgColor, borderColor)
                                   for the normal state.
        @param  disabledColor      A tuple for the disabled state.
        @param  selectedColor      A tuple for the selected state; this is when
                                   we are the active radio button.
        @param  pressedColor       A tuple for the pressed state; this is the
                                   mouse down state.
        @param  hoverColor         A tuple for the hover state.
        @param  hoverSelectedColor A tuple for the hover state when we're
                                   selected.
        @param  cornerRadius       The radius of our corners; 0 means we're a
                                   square box.
        @param  pos                UI pos.
        @param  size               UI size; if not (-1, -1) (the default), sets
                                   initial size and best size.
        @param  style              UI style.  This will be "ORed" with
                                   wx.BORDER_NONE and wx.TRANSPARENT_WINDOW.
                                   Use wx.RB_GROUP to start a new radio button
                                   group.
        """
        # Force style...
        style |= (wx.BORDER_NONE | wx.TRANSPARENT_WINDOW)

        # Call our super
        super(RadioPushButton, self).__init__(parent, -1, pos, size, style)

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Keep track of parameters...
        self._label = label
        self._normalColor = normalColor
        self._disabledColor = disabledColor
        self._selectedColor = selectedColor
        self._pressedColor = pressedColor
        self._hoverColor = hoverColor
        self._hoverSelectedColor = hoverSelectedColor
        self._cornerRadius = cornerRadius

        # Save our initial size as the best size...
        self._bestSize = size

        # Initial state...
        self._isSelected = False
        self._isPressed = False
        self._isHovered = False

        # Set default attributes...
        # ...arbitrarily use StaticText's default font...
        visAttributes = wx.StaticText.GetClassDefaultAttributes()
        self.SetFont(visAttributes.font)

        # We need to paint ourselves...
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # We need to handle all the mouse stuff...
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnMouseUp)

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    ###########################################################
    def OnDestroy(self, event=None):
        """ Explicitly release mouse capture, if needed
        """
        if self.HasCapture():
            self.ReleaseMouse()

    ###########################################################
    def GetValue(self):
        """Returns our value: 0 if not selected, 1 if selected.

        @return value  Our value.
        """
        if self._isSelected:
            return 1
        return 0


    ###########################################################
    def SetValue(self, value):
        """Sets our value.  Non-zero means selected and zero means not.

        Doesn't send an event...

        @param  value  Our new value.
        """
        if value:
            self._takeSelection()
        else:
            # Kinda bogus to set to 0, since it leaves the group with nothing
            # selected, but I guess we'll allow it.
            self._isSelected = False
            self.Refresh()


    ###########################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Tell wx what our best size should be.

        @return  bestSize  Our best size.
        """
        # If a size was specified, use that; else use the text size.
        bestWidth, bestHeight = self._bestSize
        textWidth, textHeight = self.GetTextExtent(self._label)
        if bestWidth == -1:
            bestWidth = textWidth + _kBorderSpace
        if bestHeight == -1:
            bestHeight = textHeight + _kBorderSpace

        return (bestWidth, bestHeight)


    ###########################################################
    def OnPaint(self, event):
        """Paint ourselves.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self)

        dc.SetFont(self.GetFont())

        if not self.IsEnabled():
            color = self._disabledColor
        elif self._isPressed:
            color = self._pressedColor
        elif self._isSelected:
            if self._isHovered:
                color = self._hoverSelectedColor
            else:
                color = self._selectedColor
        elif self._isHovered:
            color = self._hoverColor
        else:
            color = self._normalColor

        (textColor, bgColor, borderColor) = color

        width, height = self.GetClientSize()
        textWidth, textHeight = dc.GetTextExtent(self._label)

        # Hacky: use the transparent pen / brush if we have a zero alpha
        # channel.  This is needed on Windows.  TODO: If we need partial
        # translucency, maybe we need to use a GraphicsContext?
        if bgColor[3] == 0:
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
        else:
            dc.SetBrush(wx.Brush(bgColor))
        if borderColor[3] == 0:
            dc.SetPen(wx.TRANSPARENT_PEN)
        else:
            dc.SetPen(wx.Pen(borderColor))
        dc.SetTextForeground(textColor)
        dc.SetBackgroundMode(wx.TRANSPARENT)

        dc.DrawRoundedRectangle(0, 0, width, height, self._cornerRadius)
        dc.DrawText(self._label,
                    (width - textWidth) / 2, (height - textHeight) / 2)


    ###########################################################
    def OnMouseDown(self, event):
        """Handle mouse down on ourselves.

        @param  event  The event; may be a mouse down or a double-click event.
        """
        # Always take focus...
        self.SetFocus()

        x, y = (event.X, event.Y)

        if self._isPointOnButton(x, y):
            self._isHovered = False
            self._isPressed = True

            self.CaptureMouse()

            self.Refresh()
        else:
            event.Skip()


    ###########################################################
    def OnMouseMove(self, event):
        """Handle mouse move on the window.

        @param  event  The event; may be a move event, a mouse up event, or
                       even a double-click event.
        """
        x, y = event.X, event.Y

        isPointOnButton = self._isPointOnButton(x, y)

        if self.HasCapture():
            if self._isPressed != isPointOnButton:
                self._isPressed = isPointOnButton
                self.Refresh()
        else:
            # If we think we're selected but we don't have capture, we somehow
            # lost capture; force mouse up processing...
            if self._isPressed:
                self.OnMouseUp(event)

            if self._isHovered != isPointOnButton:
                self._isHovered = isPointOnButton
                self.Refresh()

        event.Skip()


    ###########################################################
    def OnMouseUp(self, event):
        """Handle mouse up on the window.

        @param  event  The event; may be a mouse up or a double-click event.
        """
        # Do one more move, then release if we really still have capture.
        # ...note that it seems possible to lose capture in some weird ways,
        # like right clicking on Mac while dragging (?).
        if self.HasCapture():
            self.OnMouseMove(event)
            self.ReleaseMouse()

        # If we get a mouse up while selected, that's a click!
        if self._isPressed:
            pt = self.ScreenToClient(wx.GetMousePosition())
            self._isPressed = False
            self._isHovered = self._isPointOnButton(*pt)

            self._takeSelection()
            self._sendEvent()

            self.Refresh()


    ###########################################################
    def OnDoubleClick(self, event):
        """Handle a double click.

        We just treat this as a mouse down.  Why?  This way if a user just sits
        there clicking we'll handle it.

        @param  event  The double-click event.
        """
        self.OnMouseDown(event)


    ###########################################################
    def OnLeaveWindow(self, event):
        """Handle mouse leaving the window, so we can delete phantom point.

        @param  event  The event.
        """
        if self._isHovered:
            self._isHovered = False
            self._isPressed = False
            self.Refresh()


    ###########################################################
    def Enable(self, enable=True): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Wrap enable to do a refresh.

        @param  enable  If True, we'll enable; if False, we'll disable.
        """
        wasEnabled = self.IsEnabled()
        super(RadioPushButton, self).Enable(enable)
        if bool(enable) != wasEnabled:
            self.Refresh()


    ###########################################################
    def Disable(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Wrap disable to do a refresh."""
        wasEnabled = self.IsEnabled()
        super(RadioPushButton, self).Disable()
        if wasEnabled:
            self.Refresh()


    ###########################################################
    def _isPointOnButton(self, x, y):
        """Return true if the given point is on the button.

        @param  x           The x coord, in local coords.
        @param  y           The y coord, in local coords.
        @return isOnButton  True if (x, y) is on the active part of the button.
        """
        # For now, just use a rectangle (would be slightly better to take out
        # the corners of the rounded rectangle, but I don't think that's
        # really necessary)...
        width, height = self.GetClientSize()
        return (x >= 0) and (y >= 0) and (x < width) and (y < height)


    ###########################################################
    def _takeSelection(self):
        """Take the selection.

        This will take selection away from our siblings.
        """
        # Take the selection and mark ourselves for redraw...
        self._isSelected = True
        self.Refresh()

        # Find ourself in our parent...
        parent = self.GetParent()
        siblings = list(parent.GetChildren())
        ourIndex = siblings.index(self)

        # Search for siblings to the right to take selection away from; stop
        # if we hit a new group or hit something other than a RadioPushButton.
        for sibling in siblings[ourIndex+1:]:
            if not isinstance(sibling, RadioPushButton):
                break
            if sibling.GetWindowStyle() & wx.RB_GROUP:
                break
            if sibling._isSelected:
                sibling._isSelected = False
                sibling.Refresh()
                return

        # Search for siblings to the left to take selection away from; stop
        # if we hit a new group or hit something other than a RadioPushButton.
        # Note that we have to look at "self" for RB_GROUP, since if we
        # are the first in the group we don't want to look left...
        for sibling in reversed(siblings[:ourIndex+1]):
            if not isinstance(sibling, RadioPushButton):
                break
            if (sibling != self) and (sibling._isSelected):
                sibling._isSelected = False
                sibling.Refresh()
                return
            if sibling.GetWindowStyle() & wx.RB_GROUP:
                break


    ###########################################################
    def _sendEvent(self):
        """Send an event saying that we were clicked on."""

        event = RadioPushButtonEvent(wx.wxEVT_COMMAND_RADIOBUTTON_SELECTED,
                                     self.GetId())
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)


##############################################################################
class RadioPushButtonEvent(wx.PyCommandEvent):
    """The event we fire off."""

    ###########################################################
    def __init__(self, eventType, id):
        """RadioPushButtonEvent constructor; only used internally.

        @param  eventType  The type of the event, like
                           wx.wxEVT_COMMAND_RADIOBUTTON_SELECTED
        @param  id         The ID.
        """
        super(RadioPushButtonEvent, self).__init__(eventType, id)



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    panel.SetBackgroundColour("yellow")
    panel.SetDoubleBuffered(True)

    bList = []
    bList.append(RadioPushButton(panel, "1x"))
    bList.append(RadioPushButton(panel, "2x"))
    bList.append(RadioPushButton(panel, "3x"))
    bList.append(RadioPushButton(panel, "4x"))
    bList.append(RadioPushButton(panel, "5x", style=wx.RB_GROUP))
    bList.append(RadioPushButton(panel, "6x"))
    bList[2].Disable()

    def OnButtonClick(event):
        print "Click", event

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    sizer.AddSpacer(64)
    for button in bList:
        button.Bind(wx.EVT_RADIOBUTTON, OnButtonClick)
        sizer.Add(button)
    sizer.AddSpacer(64)

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
