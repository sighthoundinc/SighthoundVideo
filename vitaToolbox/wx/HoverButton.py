#!/usr/bin/env python

#*****************************************************************************
#
# HoverButton.py
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
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from TruncateText import truncateText

# Local imports...

# Constants...

# The first delay when you are generating repeat events, then a function
# to define subsequent ones.  Wish I could find a way to get what the OS does
# for things like spin controls, but this will have to do.  Note that we very
# quickly get to repeating as fast as we possibly can.
_kInitRepeatDelay = 600.0
_repeatDelayFn = (lambda oldDelay: .60 * oldDelay)

# All colors are tuples:               text color,           background color,     borderColor
kHoverButtonNormalColor_Hyperlink   = ((  0, 102, 204, 255), (  0,   0,   0,   0), (  0,   0,   0,   0))
kHoverButtonDisabledColor_Hyperlink = ((191, 191, 191, 255), (  0,   0,   0,   0), (  0,   0,   0,   0))   # TODO: Not very good...
kHoverButtonPressedColor_Hyperlink  = (( 85,  26, 139, 255), (  0,   0,   0,   0), (  0,   0,   0,   0))
kHoverButtonHoverColor_Hyperlink    = ((  5, 153, 255, 255), (  0,   0,   0,   0), (  0,   0,   0,   0))

# ...TODO: these all stink, but are placeholders
kHoverButtonNormalColor_Button      = ((  0,   0,   0, 255), (255, 255, 255, 255), (  0,   0,   0, 255))
kHoverButtonDisabledColor_Button    = ((128, 128, 128, 255), (255, 255, 255, 255), (  0,   0,   0, 255))
kHoverButtonPressedColor_Button     = ((255, 255, 255, 255), ( 31,  31, 191, 255), (  0,   0,   0, 255))
kHoverButtonHoverColor_Button       = ((  0,   0,   0, 255), ( 63,  63, 255, 255), (  0,   0,   0, 255))

# Make it look like platebutton...
kHoverButtonNormalColor_Plate      = ((  0,   0,   0, 255), (  0,   0,   0,   0), (   0,   0,   0,   0))
kHoverButtonDisabledColor_Plate    = ((128, 128, 128, 255), (  0,   0,   0,   0), (   0,   0,   0,   0))
kHoverButtonPressedColor_Plate     = ((255, 255, 255, 255), ( 56,  81, 121, 255), (   0,   0,   0,   0))
kHoverButtonHoverColor_Plate       = ((  0,   0,   0, 255), (193, 203, 221, 255), (   0,   0,   0,   0))

# Space used to give a border when getting the best size...
_kBorderSpace = 4



##############################################################################
class HoverButton(wx.Control):
    """A generically implemented bitmap button that has a hover state.

    This button is implemented all in python and supports a few features:
    - Has a hover state (and is named for this).  We draw this state when the
      mouse is over the button.
    - Has normal, pressed, and disabled states.
    - Supports translucency.
    - Supports notifying the user if the user presses and holds on the button
      for a while.

    By default, this will look like a Hyperlink without an underline (no
    border, hyperlink-type colors), but the goal is to have some alternate color
    sets available too.
    """

    ###########################################################
    def __init__(self, parent, label, #PYCHECKER OK: Lots of args OK in this case...
                 normalColor=kHoverButtonNormalColor_Hyperlink,
                 disabledColor=kHoverButtonDisabledColor_Hyperlink,
                 pressedColor=kHoverButtonPressedColor_Hyperlink,
                 hoverColor=kHoverButtonHoverColor_Hyperlink,
                 cornerRadius=4,
                 wantRepeats=False,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=wx.ALIGN_CENTER, name="HoverButton",
                 ignoreExtraSpace=False):
        """HoverButton constructor.

        @param  parent             Our parent UI element.
        @param  label              Our label.
        @param  normalColor        A tuple: (textColor, bgColor, borderColor)
                                   for the normal state.
        @param  disabledColor      A tuple for the disabled state.
        @param  pressedColor       A tuple for the pressed state; this is the
                                   mouse down state.
        @param  hoverColor         A tuple for the hover state.
        @param  cornerRadius       The radius of our corners; 0 means we're a
                                   square box.
        @param  wantRepeats        If True, we'll continue to send button
                                   pressed events as long as the user keeps
                                   the mouse down on the button.
        @param  pos                UI pos.
        @param  size               UI size; if not (-1, -1) (the default), sets
                                   initial size and best size.
        @param  style              UI style.  This will be "ORed" with
                                   wx.BORDER_NONE and wx.TRANSPARENT_WINDOW.
                                   You can do wx.ALIGN_RIGHT or ALIGN_LEFT too.
        @param  name               UI name.
        @param  ignoreExtraSpace   If True the control will only be as wide as it
                                   needs to be regardless of the size available.
        """
        # Make sure that they don't pass an int for the label; a common mistake
        # since most wx things have ID as the 2nd parameter...
        assert (not isinstance(label, int)), "Hover button doesn't take ID"


        # Force style...
        style |= wx.BORDER_NONE | wx.TRANSPARENT_WINDOW

        # Call our super
        super(HoverButton, self).__init__(parent, -1, pos, size, style,
                                          name=name)

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)


        # Keep track of parameters...
        self._label = label
        self._normalColor = normalColor
        self._disabledColor = disabledColor
        self._pressedColor = pressedColor
        self._hoverColor = hoverColor
        self._cornerRadius = cornerRadius
        self._ignoreExtraSpace = ignoreExtraSpace

        # No menu by default...
        self._menu = None

        # Don't allow popping up too often...
        self._lastPopup = time.time()

        # Save our initial size as the best size...
        self._bestSize = size

        # Initial state...
        self._isPressed = False
        self._isHovered = False

        # State for repeating button presses if user holds it down...
        self._wantRepeats = wantRepeats
        self._nextDelay = -1
        self._repeatTimer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnRepeatTimer, self._repeatTimer)

        # We need to paint ourselves...
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # We need to handle all the mouse stuff...
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnMouseUp)

        # Bind to right down, which will only work if we have a menu...
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    ###########################################################
    def OnDestroy(self, event=None):
        """ Explicitly release mouse capture, if needed
        """
        if self.HasCapture():
            self.ReleaseMouse()


    ###########################################################
    def SetLabel(self, newLabel): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Sets a new label and refreshes.

        @param  newLabel  The new label.
        """
        self._label = newLabel
        self.Refresh()


    ###########################################################
    def SetColors(self, normalColor=None, disabledColor=None,
                  pressedColor=None, hoverColor=None):
        """Set the colors associated with the button.

        @param  normalColor    If non-None, sets the normal color.
        @param  disabledColor  If non-None, sets the disabled color.
        @param  pressedColor   If non-None, sets the pressed color.
        @param  hoverColor     If non-None, sets the hover color.
        """
        if normalColor is not None:
            self._normalColor = normalColor
        if disabledColor is not None:
            self._disabledColor = disabledColor
        if pressedColor is not None:
            self._pressedColor = pressedColor
        if hoverColor is not None:
            self._hoverColor = hoverColor

        self.Refresh()


    ###########################################################
    def SetMenu(self, newMenu):
        """Sets a menu.

        This means that we'll now show a drop arrow and that pressing on us
        will popup a menu.

        @param  newLabel  The new label.
        """
        self._menu = newMenu
        self.Refresh()


    ###########################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Tell wx what our best size should be.

        @return  bestSize  Our best size.
        """
        # If a size was specified, use that; else use the text size.
        bestWidth, bestHeight = self._bestSize

        if self._label:
            textWidth, textHeight = self.GetTextExtent(self._label)
        else:
            textWidth = 0
            _, textHeight = self.GetTextExtent("X")

        if bestHeight == -1:
            bestHeight = textHeight + _kBorderSpace

        # Add corner radius into width...
        if bestWidth == -1:
            # Figure out corner radius...
            if self._cornerRadius == -1:
                cornerRadius = bestHeight // 2
            else:
                cornerRadius = self._cornerRadius

            # Start out with text width + corner radius...
            bestWidth = textWidth + (2 * cornerRadius)

            # Give space for menu equivalent to our height...
            if self._menu:
                bestWidth += bestHeight

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
            menuStyle = wx.CONTROL_CURRENT | wx.CONTROL_DISABLED
        elif self._isPressed:
            color = self._pressedColor
            menuStyle = wx.CONTROL_PRESSED
        elif self._isHovered:
            color = self._hoverColor
            menuStyle = wx.CONTROL_CURRENT
        else:
            color = self._normalColor
            menuStyle = wx.CONTROL_CURRENT

        (textColor, bgColor, borderColor) = color

        width, height, offset = self._getSizeAndOffset()

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

        if self._cornerRadius == -1:
            cornerRadius = height // 2
        else:
            cornerRadius = self._cornerRadius
        dc.DrawRoundedRectangle(offset, 0, width, height, cornerRadius)

        _, arrowSize = self.DoGetBestSize()

        if self._menu:
            widthForText = max(0, width - arrowSize - 2*cornerRadius)
        else:
            widthForText = max(0, width - 2*cornerRadius)

        label = self._label
        if self.GetTextExtent(label)[0] > widthForText:
            label = truncateText(dc, self._label, widthForText)
        textWidth, textHeight = dc.GetTextExtent(label)

        style = self.GetWindowStyle()
        x = cornerRadius + offset
        if style & wx.ALIGN_CENTER:
            x += (widthForText - textWidth) / 2
        elif style & wx.ALIGN_RIGHT:
            x += widthForText - textWidth

        dc.DrawText(label, x, (height - textHeight) / 2)

        if self._menu:
            renderer = wx.RendererNative.Get()
            renderer.DrawDropArrow(self, dc, (x + textWidth, 0, arrowSize,
                                              height), menuStyle)


    ###########################################################
    def OnRepeatTimer(self, event=None):
        """Handle repeat timer events.

        To start the timer, set self._nextDelay to _kInitRepeatDelay and
        then call self._repeatTimer.Start(1, True).

        To stop the timer, just set self._nextDelay to -1 and it will stop
        itself.

        @param  event  The timer event.
        """
        if (self._nextDelay > 0) and self.IsEnabled():
            # Check for LeftIsDown(), since otherwise we can get into a state
            # where we don't get the MouseUp() event for a long time since we're
            # so backlogged with timer events...
            if self._isPressed and wx.GetMouseState().LeftIsDown():
                self._sendEvent()
                self._nextDelay = _repeatDelayFn(self._nextDelay)
                if int(self._nextDelay) == 0:
                    self._nextDelay = 1
                self._repeatTimer.Start(self._nextDelay, True)


    ###########################################################
    def OnMouseDown(self, event):
        """Handle mouse down on ourselves.

        @param  event  The event; may be a mouse down or a double-click event.
        """
        # Always take focus...
        self.SetFocus()

        x, y = (event.GetX(), event.GetY())

        if self._isPointOnButton(x, y):
            self._isHovered = False
            self._isPressed = True

            self.Refresh()

            if self._menu:
                # Only allow popping up every 1/10th of a second.  This
                # makes it so that if you click off of the popup to dismiss
                # the menu and your click is on the button itself, the popup
                # doesn't come back (not sure a better way to do this)...
                if (time.time() - self._lastPopup) > .1:
                    self.Update()

                    # Arbitrary code to make the popup show in a good place...
                    width, height, offset = self._getSizeAndOffset()
                    if wx.Platform == '__WXMAC__':
                        height += 3

                    # It's possible that the popup menu can have code that destroys
                    # this HoverButton on the call stack. So we will do a
                    # wx.callafter on the popup menu so that if the this control is
                    # destroyed, we won't crash.
                    wx.CallAfter(self.PopupMenu, self._menu, (offset+height/2, height))
                    self._lastPopup = time.time()

                self.OnMouseUp(event)
            else:
                self.CaptureMouse()

                if self._wantRepeats:
                    self._sendEvent()
                    self._nextDelay = _repeatDelayFn(_kInitRepeatDelay)
                    self._repeatTimer.Start(_kInitRepeatDelay, True)
        else:
            event.Skip()


    ###########################################################
    def OnMouseMove(self, event):
        """Handle mouse move on the window.

        @param  event  The event; may be a move event, a mouse up event, or
                       even a double-click event.
        """
        x, y = event.GetX(), event.GetY()

        isPointOnButton = self._isPointOnButton(x, y)

        if self.HasCapture():
            if self._isPressed != isPointOnButton:
                self._isPressed = isPointOnButton
                self.Refresh()

                if self._isPressed and self._wantRepeats:
                    # If we already have a timer running we don't want to
                    # force another event now.  If we do so a slight mouse
                    # movement when clicking will seem to generate two
                    # events, for example.
                    if not self._repeatTimer.IsRunning() or \
                       self._nextDelay == -1:
                        self._nextDelay = _kInitRepeatDelay
                        self._repeatTimer.Start(1, True)
                else:
                    self._nextDelay = -1
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

            # If we want repeats, we sent the event on mouse down; we don't
            # need to keep sending.
            if (not self._wantRepeats) and (not self._menu):
                self._sendEvent()

            self.Refresh()

        self._nextDelay = -1


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
    def OnRightDown(self, event):
        """Handle right down, but only if we have a menu.

        @param  event  The popup event.
        """
        if self._menu:
            self.OnMouseDown(event)
        else:
            event.Skip()


    ###########################################################
    def Enable(self, enable=True): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Wrap enable to do a refresh.

        @param  enable  If True, we'll enable; if False, we'll disable.
        """
        wasEnabled = self.IsEnabled()
        super(HoverButton, self).Enable(enable)
        if bool(enable) != wasEnabled:
            self.Refresh()


    ###########################################################
    def Disable(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Wrap disable to do a refresh."""
        wasEnabled = self.IsEnabled()
        super(HoverButton, self).Disable()
        if wasEnabled:
            self.Refresh()


    ###########################################################
    def SetUnderlined(self, wantUnderlined):
        """Shorthand for getting our font, setting underlined, and setting it.

        @param  wantUnderlined  True to underline; False to not.
        """
        font = self.GetFont()
        if (bool(font.GetUnderlined()) != bool(wantUnderlined)):
            font.SetUnderlined(wantUnderlined)
            self.SetFont(font)
            self.Refresh()


    ###########################################################
    def SetBold(self, wantBold=True):
        """Shorthand for getting our font, setting bold, and setting it.

        @param  wantBold  True to bold; False to not.
        """
        font = self.GetFont()
        wasBold = (font.GetWeight() == wx.FONTWEIGHT_BOLD)
        if wasBold != bool(wantBold):
            if wantBold:
                font.SetWeight(wx.FONTWEIGHT_BOLD)
            else:
                font.SetWeight(wx.FONTWEIGHT_NORMAL)

            self.SetFont(font)
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
        width, height, offset = self._getSizeAndOffset()
        return (x >= offset) and (y >= 0) and (x < offset+width) and (y < height)


    ###########################################################
    def _sendEvent(self):
        """Send an event saying that we were clicked on."""

        event = HoverButtonEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED,
                                       self.GetId())
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)


    ###########################################################
    def _getSizeAndOffset(self):
        """Retrieve our width, height, and offset.

        @return  width   The width we should use for drawing/events.
        @return  height  The height we should use for drawing/events.
        @return  offset  An offset that should be applied beginning the width.
        """
        width, height = self.GetClientSize()
        offset = 0
        if self._ignoreExtraSpace:
            bestWidth, bestHeight = self.BestSize
            offset = width-bestWidth
            width = min(width, bestWidth)
            height = min(height, bestHeight)

            style = self.GetWindowStyle()
            if style & wx.ALIGN_CENTER:
                offset = offset/2
            elif not (style & wx.ALIGN_RIGHT):
                offset = 0

        return width, height, offset


##############################################################################
class HoverButtonEvent(wx.PyCommandEvent):
    """The event we fire off."""

    ###########################################################
    def __init__(self, eventType, id):
        """HoverButtonEvent constructor; only used internally.

        @param  eventType  The type of the event, like
                           wx.wxEVT_COMMAND_BUTTON_CLICKED
        @param  id         The ID.
        """
        super(HoverButtonEvent, self).__init__(eventType, id)



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    from TextSizeUtils import makeFontDefault

    app = wx.App(False)

    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    panel.SetBackgroundColour("yellow")
    panel.SetDoubleBuffered(True)

    bList = []
    bList.append(HoverButton(panel, "Hover 1", wantRepeats=True))
    bList.append(HoverButton(panel, "Hover 2 - disabled"))
    bList.append(HoverButton(panel, "Hover 3",
                             kHoverButtonNormalColor_Button,
                             kHoverButtonDisabledColor_Button,
                             kHoverButtonPressedColor_Button,
                             kHoverButtonHoverColor_Button,
                             -1
                             ))
    bList.append(HoverButton(panel, "Hover 4 - disabled",
                             kHoverButtonNormalColor_Button,
                             kHoverButtonDisabledColor_Button,
                             kHoverButtonPressedColor_Button,
                             kHoverButtonHoverColor_Button,
                             -1
                             ))
    bList.append(HoverButton(panel, "Plate With menu",
                             kHoverButtonNormalColor_Plate,
                             kHoverButtonDisabledColor_Plate,
                             kHoverButtonPressedColor_Plate,
                             kHoverButtonHoverColor_Plate,
                             -1
                             ))

    bList[1].Disable()
    bList[3].Disable()

    menu = wx.Menu()
    menu.Append(-1, "Item 1")
    menu.Append(-1, "Item 2")
    bList[4].SetMenu(menu)

    makeFontDefault(*bList)

    def OnButtonClick(event):
        print "Click", event

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    sizer.AddSpacer(64)
    for button in bList:
        button.Bind(wx.EVT_BUTTON, OnButtonClick)
        sizer.Add(button, 0, wx.ALL, 2)
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
