#!/usr/bin/env python

#*****************************************************************************
#
# MovieSlider.py
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
from vitaToolbox.image.BorderImage import loadBorderImage
from BitmapFromFile import bitmapFromFile

# Local imports...

# Constants...

# These are default images / settings...
kDefaultSliderEnabledImg = \
    "vitaToolbox/wx/bmps/PB_Slider_Background_Enabled.png"
kDefaultSliderDisabledImg = \
    "vitaToolbox/wx/bmps/PB_Slider_Background_Disabled.png"
kDefaultSliderSpecialImg = \
    "vitaToolbox/wx/bmps/PB_Slider_Background_Special.png"
kDefaultSliderBorderWidth = 4

kDefaultElevatorEnabled = "vitaToolbox/wx/bmps/PB_Elevator_Enabled.png"
kDefaultElevatorDisabled = "vitaToolbox/wx/bmps/PB_Elevator_Disabled.png"
kDefaultElevatorPressed = None
kDefaultElevatorHover = None




##############################################################################
class MovieSlider(wx.Control):
    """A slider appropriate for choosing a position in a movie.

    This button is implemented all in python and supports a few features:
    - All UI elements are implemented with bitmaps or border bitmaps (see
      vitaToolbox.image.BorderImage).
    - You can mark parts of the slider background to use a "special" border
      bitmap to show special parts of the video.
    - The elevator has hover state.
    - We support translucency.

    Note: this control is intended to be used with a parent who has
    SetDoubleBuffered(True).
    """

    ###########################################################
    def __init__(self, parent, id, value, minValue, maxValue, #PYCHECKER OK: Lots of args OK in this case...
                 sliderEnabledBorderImg=kDefaultSliderEnabledImg,
                 sliderDisabledBorderImg=kDefaultSliderDisabledImg,
                 sliderSpecialBorderImg=kDefaultSliderSpecialImg,
                 sliderBorderWidth=kDefaultSliderBorderWidth,
                 elevatorEnabledImg=kDefaultElevatorEnabled,
                 elevatorDisabledImg=kDefaultElevatorDisabled,
                 elevatorPressedImg=kDefaultElevatorPressed,
                 elevatorHoveredImg=kDefaultElevatorHover,
                 pos=wx.DefaultPosition, size=wx.DefaultSize,
                 style=0):
        """MovieSlider constructor.

        @param  parent                   Our parent UI element.
        @param  id                       Our UI ID.
        @param  value                    Initial value for the slider.
        @param  minValue                 Min value for the slider.
        @param  maxValue                 Max value for the slider.
        @param  sliderEnabledBorderImg   Border image for slider background.
                                         Used as a src for loadBorderImage().
        @param  sliderDisabledBorderImg  Border image for ... (disabled).
                                         Passing None will just use enabled.
        @param  sliderSpecialBorderImg   Border image for ... (special).
                                         Passing None will just use enabled.
        @param  sliderBorderWidth        Border image width border width.
        @param  elevatorEnabledImg       Image for the elevator; should be a
                                         path or a file-like object.
        @param  elevatorDisabledImg      Image for the elevator (disabled).
                                         Passing None will just use enabled.
        @param  elevatorPressedImg       Image for the elevator (pressed).
                                         Passing None will just use enabled.
        @param  elevatorHoveredImg       Image for the elevator (hover).
                                         Passing None will just use enabled.
        @param  pos                      UI pos.
        @param  size                     UI size; if not (-1, -1) (the
                                         default), sets initial size and best
                                         size.
        @param  style                    UI style.  This will be "ORed" with
                                         wx.BORDER_NONE, wx.TRANSPARENT_WINDOW
                                         and wx.FULL_REPAINT_ON_RESIZE
        """
        # Force some bits into style...
        style |= (wx.BORDER_NONE | wx.TRANSPARENT_WINDOW |
                  wx.FULL_REPAINT_ON_RESIZE)

        # Call our super
        super(MovieSlider, self).__init__(parent, id, pos, size, style)

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Keep track of parameters, asjusting as needed...
        self._value = value
        self._minValue = minValue
        self._maxValue = maxValue

        # Make a copy of these so when the update runs, the file isn't locked

        self._sliderEnabledBorderPilImg = Image.open(sliderEnabledBorderImg).copy()
        if sliderDisabledBorderImg is None:
            self._sliderDisabledBorderPilImg = self._sliderEnabledBorderPilImg
        else:
            self._sliderDisabledBorderPilImg = \
                Image.open(sliderDisabledBorderImg).copy()
        if sliderSpecialBorderImg is None:
            self._sliderSpecialBorderPilImg = self._sliderEnabledBorderPilImg
        else:
            self._sliderSpecialBorderPilImg = Image.open(sliderSpecialBorderImg).copy()

        self._sliderWidth, self._sliderHeight = \
            self._sliderEnabledBorderPilImg.size

        self._sliderBorderWidth = sliderBorderWidth

        self._elevatorEnabledBmp = bitmapFromFile(elevatorEnabledImg)
        if elevatorDisabledImg is None:
            self._elevatorDisabledBmp = self._elevatorEnabledBmp
        else:
            self._elevatorDisabledBmp = bitmapFromFile(elevatorDisabledImg)
        if elevatorPressedImg is None:
            self._elevatorPressedBmp = self._elevatorEnabledBmp
        else:
            self._elevatorPressedBmp = bitmapFromFile(elevatorPressedImg)
        if elevatorHoveredImg is None:
            self._elevatorHoveredBmp = self._elevatorEnabledBmp
        else:
            self._elevatorHoveredBmp = bitmapFromFile(elevatorHoveredImg)

        self._elevatorWidth  = self._elevatorEnabledBmp.GetWidth()
        self._elevatorHeight = self._elevatorEnabledBmp.GetHeight()

        # Start out with no special ranges...
        self._specialRanges = []

        # Cache current copies of the slider, as wx.Bitmaps...
        self._sliderDisabledBmp = None
        self._sliderEnabledBmp = None
        self._cachedSize = None          # Tuple: (width, height)

        # Same type bitmaps should be the same size...
        for bmp in (self._elevatorDisabledBmp, self._elevatorPressedBmp,
                    self._elevatorHoveredBmp):
            assert bmp.GetWidth() == self._elevatorWidth
            assert bmp.GetHeight() == self._elevatorHeight
        for pilImg in (self._sliderDisabledBorderPilImg,
                       self._sliderSpecialBorderPilImg):
            assert self._sliderWidth, self._sliderHeight == pilImg.size

        # The cached x position of the elevator.  We won't redraw if this
        # doesn't change; None means we haven't drawn...
        self._elevatorCX = None

        # Save our initial size as the best size...
        self._bestSize = size

        # Initial state...
        self._isPressed = False
        self._isHovered = False
        self._needPaint = False

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
        """Returns our value.

        @return value  Our value.
        """
        return self._value


    ###########################################################
    def SetValue(self, value):
        """Sets our value.  Refreshes if needed...

        Doesn't send an event...

        @param  value  Our new value; will be cropped according to min and max.
        """
        value = max(self._minValue, min(self._maxValue, value))

        if value != self._value:
            self._value = value

            elevatorCX = self._valueToX(value)
            if self._elevatorCX != elevatorCX:
                self.Refresh()


    ###########################################################
    def SetRange(self, minValue, maxValue):
        """Set the minimum and maximum slider values.

        ...will force value to be in this range...

        @param  minValue  The new minimum slider value.
        @param  maxValue  The new maximim slider value.
        """
        assert minValue <= maxValue

        if (self._minValue != minValue) or (self._maxValue != maxValue):
            self._minValue = minValue
            self._maxValue = maxValue

            # Force value to be in range...
            self._value = max(minValue, min(maxValue, self._value))

            # If we've changed the ranges, we need to re-cache the background
            # (only if we have special stuff)...
            if self._specialRanges:
                self._cacheBackgrounds()

            self.Refresh()


    ###########################################################
    def SetSpecialRanges(self, specialRanges):
        """Set some ranges to draw using the "special" slider background.

        This is a semi-expensive operation, since it re-creates our background
        images.

        Note that if you pass a negative value for the 2nd item in the range,
        it specifies that you want the the special range to last negative that
        many pixels.

        @param  specialRanges  Python-style ranges to have the special
                               background.  So if you wanted the first 1/4
                               and the last 1/4, you'd pass: [
                                 (minVal, minVal + (maxVal-minVal+1) // 4),
                                 (minVal + (3*(maxVal-minVal+1)) // 4, maxVal+1)
                               ]
        """
        if self._specialRanges != specialRanges:
            self._specialRanges = specialRanges
            self._cacheBackgrounds()
            self.Refresh()


    ###########################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Tell wx what our best size should be.

        @return  bestSize  Our best size.
        """
        # Return what was passed to constructor if not -1; else do our best...
        bestWidth, bestHeight = self._bestSize

        if bestWidth == -1:
            bestWidth = max(self._sliderWidth, self._elevatorWidth)
        if bestHeight == -1:
            bestHeight = max(self._sliderHeight, self._elevatorHeight)

        return (bestWidth, bestHeight)


    ###########################################################
    def OnPaint(self, event):
        """Paint ourselves.

        @param  event  The paint event.
        """
        dc = wx.PaintDC(self)
        self._needPaint = False
        width, height = self.GetClientSize()

        if (width, height) != self._cachedSize:
            self._cacheBackgrounds()

        self._elevatorCX = self._valueToX(self._value)

        if not self.IsEnabled():
            backgroundBmp = self._sliderDisabledBmp
            elevatorBmp = self._elevatorDisabledBmp
        else:
            backgroundBmp = self._sliderEnabledBmp
            if self._isPressed:
                elevatorBmp = self._elevatorPressedBmp
            elif self._isHovered:
                elevatorBmp = self._elevatorHoveredBmp
            else:
                elevatorBmp = self._elevatorEnabledBmp

        if backgroundBmp is not None:
            dc.DrawBitmap(backgroundBmp, self._elevatorWidth // 2,
                          (height - self._sliderHeight) // 2, True)
            dc.DrawBitmap(elevatorBmp,
                          self._elevatorCX - (self._elevatorWidth // 2),
                          (height - self._elevatorHeight) // 2, True)


    ###########################################################
    def OnMouseDown(self, event):
        """Handle mouse down on ourselves.

        @param  event  The event; may be a mouse down or a double-click event.
        """
        # Always take focus...
        self.SetFocus()

        # All mouse downs capture the mouse, since we want to elevator to
        # jump to the cursor.
        self._isHovered = False
        self._isPressed = True
        self.CaptureMouse()
        self.Refresh()

        self.OnMouseMove(event)


    ###########################################################
    def OnMouseMove(self, event):
        """Handle mouse move on the window.

        @param  event  The event; may be a move event, a mouse up event, or
                       even a double-click event.
        """
        if self.HasCapture():
            newValue = self._xToValue(event.X)

            if newValue != self._value:
                self.SetValue(newValue)
                if not self._needPaint:
                    # do not flood us with a chain of updates,
                    # if we didn't even have a time to repaint the control yet
                    self._needPaint = True
                    self._sendEvent()
        else:
            # If we think we're selected but we don't have capture, we somehow
            # lost capture; force mouse up processing...
            if self._isPressed:
                self.OnMouseUp(event)

            if not self._isHovered:
                self._isHovered = True
                self.Refresh()

        event.Skip()


    ###########################################################
    def OnMouseUp(self, event):
        """Handle mouse up on the window.

        @param  event  The event
        """
        # On mouse up, just release capture...
        if self.HasCapture():
            self.ReleaseMouse()

        x, y = self.ScreenToClient(wx.GetMousePosition())
        width, height = self.GetClientSize()

        if self._isPressed:
            self._isPressed = False

            # Send one last event; this will have isPressed as False.
            self._sendEvent()

        self._isHovered = (x >= 0) and (y >= 0) and (x < width) and (y < height)

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
        """Handle mouse leaving the window.

        @param  event  The event.
        """
        if self._isHovered:
            self._isHovered = False

            # If we think we're selected but we don't have capture, we somehow
            # lost capture; force mouse up processing...
            if self._isPressed:
                self.OnMouseUp(event)

            self.Refresh()


    ###########################################################
    def Enable(self, enable=True): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Wrap enable to do a refresh.

        @param  enable  If True, we'll enable; if False, we'll disable.
        """
        wasEnabled = self.IsEnabled()
        super(MovieSlider, self).Enable(enable)
        if bool(enable) != wasEnabled:
            self.Refresh()


    ###########################################################
    def Disable(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Wrap disable to do a refresh."""
        wasEnabled = self.IsEnabled()
        super(MovieSlider, self).Disable()
        if wasEnabled:
            self.Refresh()


    ###########################################################
    def _getSliderWidth(self):
        """Return the current width of the slider.

        This is simply the width of the control minus the width of the
        elevator (since we want to leave room for half of the elevator on
        the left and half on the right).

        Note that we subtract 1 from the width of the elevator in the case of
        an odd-width elevator.  This makes it so that the center of the elevator
        will always be on top of the ends of the slider for min and max.
        """
        width, _ = self.GetClientSize()
        return width - 2 * (self._elevatorWidth // 2)


    ###########################################################
    def _xToValue(self, x):
        """Convert from a value to the x coord associated with that value.

        @param  x      The x coord, in client coordinates.
        @return value  The value associated with that x coordinate.
        """
        # Want to map pixel 0 on the slider to self._minValue
        # Want to map pixel (width-1) to self._maxValue
        # ...everything in between will just work out...

        sliderWidth = self._getSliderWidth()
        adjMaxValue = self._maxValue - self._minValue

        # Adjust x for where the slider starts: at elevatorWidth/2
        adjX = x - (self._elevatorWidth // 2)

        # Find the floating point translation...
        if (sliderWidth-1) == 0:
            adjVal = 0
        else:
            adjVal = (float(adjX) * adjMaxValue) / (sliderWidth-1)

        # Round and convert to int...
        return int(round(adjVal)) + self._minValue


    ###########################################################
    def _valueToX(self, value):
        """Calculate where the x position of the elevator should be.

        Uses our current self.GetClientSize().

        @param  value  The value to calc for.
        @return x      The x value to put the elevator at.
        """
        # Want to map pixel 0 on the slider to self._minValue
        # Want to map pixel (width-1) to self._maxValue
        # ...everything in between will just work out...

        sliderWidth = self._getSliderWidth()
        adjMaxValue = self._maxValue - self._minValue

        # Adjust value for minValue
        adjVal = value - self._minValue

        # Find floating point translation...
        if adjMaxValue == 0:
            adjX = 0
        else:
            adjX = (float(adjVal) * (sliderWidth-1)) / adjMaxValue

        # Round and convert to int...
        return int(round(adjX)) + (self._elevatorWidth // 2)


    ###########################################################
    def _cacheBackgrounds(self):
        """Cache backgrounds in _sliderDisabledBmp and _sliderEnabledBmp.

        ...updates self._cachedSize to be (width, height) of the current client
        size when this is called.

        Uses our current self.GetClientSize().
        """
        clientWidth, clientHeight = self.GetClientSize()
        width = self._getSliderWidth()

        if width <= 0:
            self._sliderEnabledBmp = None
            self._sliderDisabledBmp = None
            return

        img = loadBorderImage(self._sliderEnabledBorderPilImg,
                              (width, self._sliderHeight),
                              self._sliderBorderWidth, self._sliderHeight // 2)
        img = img.convert("RGBA")
        if self._specialRanges:
            specialImg = loadBorderImage(self._sliderSpecialBorderPilImg,
                                         (width, self._sliderHeight),
                                         self._sliderBorderWidth,
                                         self._sliderHeight // 2)
            for (start, end) in self._specialRanges:
                startPix = self._valueToX(start) - (self._elevatorWidth // 2)
                if end < 0:
                    # Special is in # of pixels...
                    endPix = min(startPix - end, width)
                else:
                    endPix = self._valueToX(end) - (self._elevatorWidth // 2)
                bbox = (startPix, 0, endPix, self._sliderHeight)
                specialCropped = specialImg.crop(bbox)
                img.paste(specialCropped, (startPix, 0))

        self._sliderEnabledBmp = \
            wx.Bitmap.FromBufferRGBA(width, self._sliderHeight, img.tobytes())

        img = loadBorderImage(self._sliderDisabledBorderPilImg,
                              (width, self._sliderHeight),
                              self._sliderBorderWidth, self._sliderHeight // 2)
        img = img.convert("RGBA")
        self._sliderDisabledBmp = \
            wx.Bitmap.FromBufferRGBA(width, self._sliderHeight, img.tobytes())

        self._cachedSize = (clientWidth, clientHeight)


    ###########################################################
    def _sendEvent(self):
        """Send an event saying that our value changed."""

        event = MovieSliderEvent(wx.wxEVT_COMMAND_SLIDER_UPDATED,
                                 self.GetId(), self._isPressed)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)


##############################################################################
class MovieSliderEvent(wx.PyCommandEvent):
    """The event we fire off."""

    ###########################################################
    def __init__(self, eventType, id, isPressed):
        """MovieSliderEvent constructor; only used internally.

        @param  eventType  The type of the event, like
                           wx.wxEVT_COMMAND_RADIOBUTTON_SELECTED
        @param  id         The ID.
        @param  isPressed  True if the mouse is currently pressed down on the
                           slider (so we'll definitely get another event).
        """
        super(MovieSliderEvent, self).__init__(eventType, id)
        self._isPressed = isPressed


    ###########################################################
    def isPressed(self):
        """Return whether the mouse was pressed on the slider for this event.

        On any mouse action on the slider, we'll always send one last event
        on the slider where isPressed is False.

        @return isPressed  True if the mouse was pressed down for this action.
        """
        return self._isPressed



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    from GradientPanel import GradientPanel
    app = wx.App(False)

    frame = wx.Frame(None)
    frame.CreateStatusBar(4)
    panel = GradientPanel(frame, startColor=(172, 0, 0))
    panel.SetDoubleBuffered(True)

    minVal = 40
    maxVal = 140

    slider1 = MovieSlider(panel, -1, 90, minVal, maxVal)
    slider1.SetSpecialRanges([
        (minVal, minVal + (maxVal-minVal+1) // 4),
        (minVal + (3 * (maxVal-minVal+1)) // 4, maxVal+1)
    ])

    slider2 = MovieSlider(panel, -1, 40, minVal, maxVal)
    slider2.SetSpecialRanges([
        (minVal, -5),
        (minVal + (3 * (maxVal-minVal+1)) // 4, -10)
    ])

    slider3 = MovieSlider(panel, -1, 140, minVal, maxVal)
    slider3.SetSpecialRanges([
        (0, minVal + (maxVal-minVal+1) // 2)
    ])

    slider4 = MovieSlider(panel, -1, 1, -2, 2)

    slider5 = MovieSlider(panel, -1, -1, -2, 2)
    slider5.Disable()

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    yellowWin = wx.Window(panel, -1, size=(64, 64))
    yellowWin.SetBackgroundColour("yellow")
    sizer.Add(yellowWin, 0, wx.EXPAND)

    vertSizer = wx.BoxSizer(wx.VERTICAL)
    vertSizer.Add(slider1, 1, wx.EXPAND)
    vertSizer.Add(slider2, 0, wx.ALIGN_CENTER_HORIZONTAL)
    vertSizer.Add(slider3, 1, wx.EXPAND)
    vertSizer.Add(slider4, 1, wx.EXPAND)
    vertSizer.Add(slider5, 1, wx.EXPAND)
    sizer.Add(vertSizer, 1, wx.EXPAND)

    yellowWin = wx.Window(panel, -1, size=(64, 64))
    yellowWin.SetBackgroundColour("yellow")
    sizer.Add(yellowWin, 0, wx.EXPAND)

    panel.SetSizer(sizer)

    def onSlider1(event):
        frame.SetStatusText("%d" % slider1.GetValue(), 0)
    slider1.Bind(wx.EVT_SLIDER, onSlider1)
    def onSlider2(event):
        frame.SetStatusText("%d" % slider2.GetValue(), 1)
    slider2.Bind(wx.EVT_SLIDER, onSlider2)
    def onSlider3(event):
        frame.SetStatusText("%d" % slider3.GetValue(), 2)
    slider3.Bind(wx.EVT_SLIDER, onSlider3)
    def onSlider4(event):
        frame.SetStatusText("%d" % slider4.GetValue(), 3)
    slider4.Bind(wx.EVT_SLIDER, onSlider4)

    frameSizer = wx.BoxSizer()
    frameSizer.Add(panel, 1, wx.EXPAND)
    frame.SetSizer(frameSizer)
    frame.Fit()

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
