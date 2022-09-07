#!/usr/bin/env python

#*****************************************************************************
#
# HoverBitmapButton.py
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
import os
import sys

# Common 3rd-party imports...
from PIL import Image
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from vitaToolbox.wx.BitmapFromFile import bitmapFromFile

from vitaToolbox.wx.TruncateText import truncateText


# Local imports...

# Constants...

# The first delay when you are generating repeat events, then a function
# to define subsequent ones.  Wish I could find a way to get what the OS does
# for things like spin controls, but this will have to do.  Note that we very
# quickly get to repeating as fast as we possibly can.
_kInitRepeatDelay = 600.0
_repeatDelayFn = (lambda oldDelay: .60 * oldDelay)

_kTextColor = (0, 0, 0, 255)
_kBgColor = wx.TransparentColour
_kBorderColor = wx.TransparentColour

_kNormalTextColor = (_kTextColor, _kBgColor, _kBorderColor)
_kDisabledTextColor = (_kTextColor, _kBgColor, _kBorderColor)
_kPressedTextColor = (_kTextColor, _kBgColor, _kBorderColor)
_kHoverTextColor = (_kTextColor, _kBgColor, _kBorderColor)


##############################################################################
class HoverBitmapButton(wx.Control):
    """A generically implemented bitmap button that has a hover state.

    This button is implemented all in python and supports a few features:
    - Has a hover state (and is named for this).  We draw this state when the
      mouse is over the button.
    - Has normal, pressed, and disabled states.
    - Supports translucency.
    - Supports notifying the user if the user presses and holds on the button
      for a while.
    - Can automatically look for platform specific bitmaps by appending
      _Mac or _Win to provided bitmaps.

    The API for this attempts to most closely match GenBitmapButton.
    """

    ###########################################################
    def __init__(self, parent, id=wx.ID_ANY, bmpNormal=None, #PYCHECKER OK: Lots of args OK in this case...
                 label=wx.EmptyString, bmpPressed=None, bmpDisabled=None,
                 bmpHovered=None, wantRepeats=False, platformBmps=True,
                 pos=wx.DefaultPosition, size=wx.DefaultSize, useMask=True,
                 normalTextColor=_kNormalTextColor,
                 disabledTextColor=_kDisabledTextColor,
                 pressedTextColor=_kPressedTextColor,
                 hoverTextColor=_kHoverTextColor,
                 name="HoverBitmapButton", ignoreExtraSpace=False,):
        """HoverBitmapButton constructor.

        @param  parent              Our parent UI element.
        @param  bmpNormal           Our normal bitmap (a path to a file or a wx.Bitmap)
        @param  label               Text that will appear on top of the button.
        @param  bmpPressed          The bitmap to show when we're pressed down.
                                    If None, bmpNormal will be used.
        @param  bmpDisabled         The bitmap to show when we're disabled.  If None,
                                    bmpNormal will be used.
        @param  bmpHovered          The bitmap to show when we're hovered over.
                                    If None, bmpNormal will be used.
        @param  wantRepeats         If True, we'll continue to send button pressed
                                    events as long as the user keeps the mouse down
                                    on the button.
        @param  platformBmps        If True and bitmaps were specified as paths to
                                    bitmap files, we'll look for platform specific
                                    bitmap files.  If they exist, they will be used.
                                    See the main class docstring.
        @param  pos                 UI pos.
        @param  size                UI size; if not (-1, -1) (the default), sets
                                    initial size and best size.
        @param  style               UI style.  This will be "ORed" with
                                    wx.BORDER_NONE and wx.TRANSPARENT_WINDOW.
                                    You can do wx.ALIGN_RIGHT or ALIGN_LEFT too.
        @param  useMask             If True the button will only show hover state/be
                                    clickable if the mouse is over a non-transparent
                                    section of the bitmap.
        @param  normalTextColor     A tuple: (textColor, bgColor, borderColor)
                                    for the normal state.
        @param  disabledTextColor   A tuple for the disabled state.
        @param  pressedTextColor    A tuple for the pressed state; this is the
                                    mouse down state.
        @param  hoverTextColor      A tuple for the hover state.
        @param  name                UI name.
        """
        # Force style...
        style = wx.BORDER_NONE | wx.TRANSPARENT_WINDOW

        # Call our super
        super(HoverBitmapButton, self).__init__(parent, id, pos, size, style,
                                                wx.DefaultValidator, name)

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        self._label = label
        self._normalTextColor = normalTextColor
        self._disabledTextColor = disabledTextColor
        self._pressedTextColor = pressedTextColor
        self._hoverTextColor = hoverTextColor

        # Keep track of bitmaps, loading if needed.
        if isinstance(bmpNormal, basestring):
            self._bmpNormal = bitmapFromFile(bmpNormal, platformBmps)
        else:
            self._bmpNormal = bmpNormal
        if bmpPressed is None:
            self._bmpPressed = self._bmpNormal
        elif isinstance(bmpPressed, basestring):
            self._bmpPressed = bitmapFromFile(bmpPressed, platformBmps)
        else:
            self._bmpPressed = bmpPressed
        if bmpDisabled is None:
            self._bmpDisabled = self._bmpNormal
        elif isinstance(bmpDisabled, basestring):
            self._bmpDisabled = bitmapFromFile(bmpDisabled, platformBmps)
        else:
            self._bmpDisabled = bmpDisabled
        if bmpHovered is None:
            self._bmpHovered = self._bmpNormal
        elif isinstance(bmpHovered, basestring):
            self._bmpHovered = bitmapFromFile(bmpHovered, platformBmps)
        else:
            self._bmpHovered = bmpHovered

        self._bmpWidth  = self._bmpNormal.GetWidth()
        self._bmpHeight = self._bmpNormal.GetHeight()

        # Use the hovered bitmap to figure out a region...
        if useMask:
            self._maskRegion = wx.Region(self._bmpHovered, (0, 0, 0, 0))
        else:
            self._maskRegion = wx.Region(0, 0, self._bmpWidth, self._bmpHeight)

        # Save our initial size as the best size...
        self._bestSize = size

        # Check bitmap sizes--they must all be the same...
        for i, bmp in enumerate((self._bmpPressed, self._bmpDisabled,
                                 self._bmpHovered)):
            assert bmp.GetWidth() == self._bmpWidth
            assert bmp.GetHeight() == self._bmpHeight

        # If they didn't specify a size, default to the bitmap one.  This
        # shouldn't affect best size...
        if (size[0] == -1) and (size[1] == -1):
            self.SetSize((self._bmpWidth, self._bmpHeight))

        # Initial state...
        self._isPressed = False
        self._isHovered = False

        self._ignoreExtraSpace = ignoreExtraSpace

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

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    ###########################################################
    def OnDestroy(self, event=None):
        """ Explicitly release mouse capture, if needed
        """
        if self.HasCapture():
            self.ReleaseMouse()

    ###########################################################
    def SetLabel(self, newLabel):  # PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Sets a new label and refreshes.

        @param  newLabel  The new label.
        """
        self._label = newLabel
        self.Refresh()


    ###########################################################
    def SetBitmap(self, bmp):
        if self._isValidSize(bmp):
            self._bmpNormal = bmp
            self.Refresh()


    ###########################################################
    def SetBitmapCurrent(self, bmp):
        if self._isValidSize(bmp):
            self._bmpHovered = bmp
            self.Refresh()


    ###########################################################
    def SetBitmapPressed(self, bmp):
        if self._isValidSize(bmp):
            self._bmpPressed = bmp
            self.Refresh()


    ###########################################################
    def SetBitmapDisabled(self, bmp):
        if self._isValidSize(bmp):
            self._bmpDisabled = bmp
            self.Refresh()


    ###########################################################
    def _isValidSize(self, bmp):
        return (
            (self._bmpWidth  == bmp.GetWidth()) and
            (self._bmpHeight == bmp.GetHeight())
        )


    ###########################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Tell wx what our best size should be.

        @return  bestSize  Our best size.
        """
        # If a size was specified, use that; else use the text size.
        bestWidth, bestHeight = self._bestSize
        if bestWidth == -1:
            bestWidth = self._bmpWidth
        if bestHeight == -1:
            bestHeight = self._bmpHeight

        return (bestWidth, bestHeight)


    ###########################################################
    def OnPaint(self, event):
        """Paint ourselves.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self)

        if not self.IsEnabled():
            bmp = self._bmpDisabled
        elif self._isPressed:
            bmp = self._bmpPressed
        elif self._isHovered:
            bmp = self._bmpHovered
        else:
            bmp = self._bmpNormal

        if bmp is not None:
            dc.DrawBitmap(bmp, 0, 0, True)

        if self._label == wx.EmptyString:
            return

        dc.SetFont(self.GetFont())

        if not self.IsEnabled():
            color = self._disabledTextColor
        elif self._isPressed:
            color = self._pressedTextColor
        elif self._isHovered:
            color = self._hoverTextColor
        else:
            color = self._normalTextColor

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

        dc.DrawRectangle(offset, 0, width, height)

        _, arrowSize = self.DoGetBestSize()

        widthForText = max(0, width)

        label = self._label
        if self.GetTextExtent(label)[0] > widthForText:
            label = truncateText(dc, self._label, widthForText)
        textWidth, textHeight = dc.GetTextExtent(label)

        style = self.GetWindowStyle()
        x = offset
        if style & wx.ALIGN_CENTER:
            x += (widthForText - textWidth) / 2
        elif style & wx.ALIGN_RIGHT:
            x += widthForText - textWidth

        dc.DrawText(label, x, (height - textHeight) / 2)


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

            self.CaptureMouse()

            if self._wantRepeats:
                self._sendEvent()
                self._nextDelay = _repeatDelayFn(_kInitRepeatDelay)
                self._repeatTimer.Start(_kInitRepeatDelay, True)

            self.Refresh()
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
            # If we think we're pressed but we don't have capture, we somehow
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

        # If we get a mouse up while pressed, that's a click!
        if self._isPressed:
            pt = self.ScreenToClient(wx.GetMousePosition())
            self._isPressed = False
            self._isHovered = self._isPointOnButton(*pt)

            # If we want repeats, we sent the event on mouse down; we don't
            # need to keep sending.
            if not self._wantRepeats:
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
    def Enable(self, enable=True): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Wrap enable to do a refresh.

        @param  enable  If True, we'll enable; if False, we'll disable.
        """
        wasEnabled = self.IsEnabled()
        super(HoverBitmapButton, self).Enable(enable)
        if bool(enable) != wasEnabled:
            self.Refresh()


    ###########################################################
    def Disable(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Wrap disable to do a refresh."""
        wasEnabled = self.IsEnabled()
        super(HoverBitmapButton, self).Disable()
        if wasEnabled:
            self.Refresh()


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
            offset = width - bestWidth
            width = min(width, bestWidth)
            height = min(height, bestHeight)

            style = self.GetWindowStyle()
            if style & wx.ALIGN_CENTER:
                offset /= 2
            elif not (style & wx.ALIGN_RIGHT):
                offset = 0

        return width, height, offset


    ###########################################################
    def _isPointOnButton(self, x, y):
        """Return true if the given point is on the button.

        @param  x           The x coord, in local coords.
        @param  y           The y coord, in local coords.
        @return isOnButton  True if (x, y) is on the active part of the button.
        """
        return self._maskRegion.Contains(x, y)


    ###########################################################
    def _sendEvent(self):
        """Send an event saying that we were clicked on.

        Note:  Calling this method will do nothing if this control is disabled.
        """

        # Only send an event if we are enabled...
        # We need this here, because for some reason in wxPython 3.0.2.0,
        # setting ourselves to Disabled through the normal wx.Pycontrol methods
        # doesn't seem to apply anymore when dealing with our own events and
        # manually catching the mouse events.
        if not self.IsEnabled():
            return

        event = HoverBitmapButtonEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED,
                                       self.GetId())
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)


##############################################################################
class HoverBitmapButtonEvent(wx.PyCommandEvent):
    """The event we fire off."""

    ###########################################################
    def __init__(self, eventType, id):
        """HoverBitmapButtonEvent constructor; only used internally.

        @param  eventType  The type of the event, like
                           wx.wxEVT_COMMAND_BUTTON_CLICKED
        @param  id         The ID.
        """
        super(HoverBitmapButtonEvent, self).__init__(eventType, id)



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    from ImagePanel import ImagePanel
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    panel.SetBackgroundColour("yellow")
    panel.SetDoubleBuffered(True)

    #ip = ImagePanel(panel, -1, "frontEnd/bmps/PB_button_bar_w_buttons.png")
    #button = HoverBitmapButton(ip,
    #                           'frontEnd/bmps/PB_frame_back_enabled.png',
    #                           'frontEnd/bmps/PB_frame_back_pressed.png',
    #                           'frontEnd/bmps/PB_frame_back_disabled.png',
    #                           'frontEnd/bmps/PB_frame_back_hover.png',
    #                           (137, 28))
    ip = ImagePanel(panel, -1, "frontEnd/bmps/PB_button_bar.png")
    buttons = []
    buttons.append(
        HoverBitmapButton(ip,
                          'frontEnd/bmps/PB_prev_clip_enabled.png',
                          'frontEnd/bmps/PB_prev_clip_pressed.png',
                          None,
                          'frontEnd/bmps/PB_prev_clip_hover.png')
    )
    buttons.append(
        HoverBitmapButton(ip,
                          'frontEnd/bmps/PB_minus2_enabled.png',
                          'frontEnd/bmps/PB_minus2_pressed.png',
                          'frontEnd/bmps/PB_minus2_disabled.png',
                          'frontEnd/bmps/PB_minus2_hover.png')
    )
    buttons.append(
        HoverBitmapButton(ip,
                          'frontEnd/bmps/PB_frame_back_enabled.png',
                          'frontEnd/bmps/PB_frame_back_pressed.png',
                          'frontEnd/bmps/PB_frame_back_disabled.png',
                          'frontEnd/bmps/PB_frame_back_hover.png',
                          True)
    )
    buttons.append(
        HoverBitmapButton(ip,
                          'frontEnd/bmps/PB_play_enabled.png',
                          'frontEnd/bmps/PB_play_pressed.png',
                          None,
                          'frontEnd/bmps/PB_play_hover.png')
    )
    buttons.append(
        HoverBitmapButton(ip,
                          'frontEnd/bmps/PB_frame_fwd_enabled.png',
                          'frontEnd/bmps/PB_frame_fwd_pressed.png',
                          'frontEnd/bmps/PB_frame_fwd_disabled.png',
                          'frontEnd/bmps/PB_frame_fwd_hover.png',
                          True)
    )
    buttons.append(
        HoverBitmapButton(ip,
                          'frontEnd/bmps/PB_plus2_enabled.png',
                          'frontEnd/bmps/PB_plus2_pressed.png',
                          'frontEnd/bmps/PB_plus2_disabled.png',
                          'frontEnd/bmps/PB_plus2_hover.png')
    )
    buttons.append(
        HoverBitmapButton(ip,
                          'frontEnd/bmps/PB_next_clip_enabled.png',
                          'frontEnd/bmps/PB_next_clip_pressed.png',
                          None,
                          'frontEnd/bmps/PB_next_clip_hover.png')
    )

    def OnButtonClick(event):
        print "Click", event

    for button in buttons:
        button.Bind(wx.EVT_BUTTON, OnButtonClick)

    ipSizer = wx.BoxSizer(wx.HORIZONTAL)
    ipSizer.Add(buttons[0], 0, wx.ALIGN_CENTER_VERTICAL)
    for button in buttons[1:]:
        ipSizer.AddStretchSpacer(1)
        ipSizer.Add(button, 0, wx.ALIGN_CENTER_VERTICAL)
    ip.SetSizer(ipSizer)

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    sizer.AddStretchSpacer(1)
    sizer.Add(ip, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.AddStretchSpacer(1)

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
