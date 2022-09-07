#!/usr/bin/env python

#*****************************************************************************
#
# ConstructionBlock.py
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

# Local imports...

# Constants...

# We'll brighten our border color by this much to get the start gradient...
# ...should be a percentage: 1.0 would be white; 0.0 would make it start at
# the border color
_kGradientBrightenPct = .75

# This is how wide of a border we'll have; the second one is used when focused.
_kBorderWidth = 2
_kSelectBorderWidth = 4

# The color of the focus border...
_kSelectBorderColor = (232, 39, 72)

# This is the margin from the outer border of our control that we'll use when
# placing the bitmap and text.  Must include space for the borders...
_kMarginWidth = max(_kBorderWidth, _kSelectBorderWidth) + 1

# This is the default construction block size, grokked from the PowerPoint.
kDefaultConstructionBlockSize = (106, 68)


##############################################################################
class ConstructionBlock(wx.Control):
    """A UI element used in the "flow chart" part of the QueryConstructionView.

    This acts roughly like a button and has a bitmap, a label, and a color.
    """

    ###########################################################
    def __init__(self, parent, bitmap, label, color=(255, 0, 0),
                 pos=wx.DefaultPosition, size=kDefaultConstructionBlockSize):
        """ConstructionBlock constructor.

        @param  parent  Our parent UI element.
        @param  bitmap  The bitmap to use in the button.
        @param  label   The label to use in the button.  May be multiline--each
                        line will be truncated separately.  Note: it's your
                        responsibility to make sure there's enough vertical
                        space for all of the lines.
        @param  color   The color.  This will be used directly for the normal
                        border of the object.  A lightened version of this
                        will be used for the gradient.
        @param  pos     The position to put us at.
        @param  size    The size of the button.
        """
        # Call our super
        super(ConstructionBlock, self).__init__(
            parent, -1, pos, size, style=wx.BORDER_NONE |
            wx.FULL_REPAINT_ON_RESIZE
        )

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)


        # Keep track of parameters...
        self._bitmap = bitmap
        self._label = label
        self._color = color
        self._size = size

        # We can store some data for the client...
        self._clientData = None

        # Pre-calculate our gradient color based on the passed color.  This
        # formula effectively makes us "closer" to white.
        self._gradientColor = \
            tuple(c + ((255-c) * _kGradientBrightenPct) for c in color)

        # Set our default font to be 2 less than the default font for a button,
        # but not less than 10 point...
        font = self.GetFont()
        font.SetPointSize(max(font.GetPointSize()-2, 10))
        self.SetFont(font)

        # We start out not being selected...
        self._isSelected = False

        # We need to paint ourselves...
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # We act on mouse down only--we don't track the pen (for now).
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)


    ###########################################################
    def DoGetBestSize(self): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Tell wx what our best size should be.

        We'll return the size that was passed to the constructor.  This doesn't
        seem to be needed on Mac, but seems to be on Windows (dunno why).

        @return  bestSize  Our best size.
        """
        return self._size


    ###########################################################
    def OnPaint(self, event):
        """Paint ourselves.

        @param  event  The paint event.
        """
        # Get a device context.  Use AutoBuffered, since it's best in terms
        # of being flicker-free on Windows and fast on Mac.
        dc = wx.AutoBufferedPaintDC(self)

        if self._isSelected:
            self._drawOnDc(_kSelectBorderWidth, _kSelectBorderColor, dc)
        else:
            self._drawOnDc(_kBorderWidth, self._color, dc)


    ###########################################################
    def OnLeftDown(self, event):
        """Handle mouse down to take selection

        @param  event  The mouse down event.
        """
        if not self._isSelected:
            self.takeHighlight()


    ###########################################################
    def takeHighlight(self):
        """Make this the highlighted block.

        Note: unlike much of wx, this _does_ still send out an event.
        """
        # Only one construction block can be selected--take away everyone
        # else's...
        self._takeAwaySiblingHighlight()

        # Raise ourselves so that we draw properly even if our border
        # overlaps with someone else's...
        self.Raise()

        # We're now selected...
        self._isSelected = True

        # Take question.  Question: is that right?  Do construction blocks
        # really get focus?
        self.SetFocus()

        # Refresh ourselves to show the selected state...
        self.Refresh()

        # Send out an event telling clients we were clicked on...
        self._sendEvent()


    ###########################################################
    def getClientData(self):
        """Return client data set with setClientData.

        @return data  The client's data.
        """
        return self._clientData


    ###########################################################
    def setClientData(self, data):
        """Set client data set associated with this object.

        @param  data  The client's data.
        """
        self._clientData = data


    ###########################################################
    def SetLabel(self, label): #PYCHECKER signature mismatch OK; wx has *args and **kwargs
        """Allow setting of the label.

        This will also refresh the control.
        Named to conform to standard wx function.

        @param  label  The new label.
        """
        self._label = label
        self.Refresh()


    ###########################################################
    def SetBitmap(self, bitmap):
        """Allow setting of the bitmap.

        This will also refresh the control.
        Named to conform to standard wx function.

        @param  bitmap  The new bitmap.
        """
        self._bitmap = bitmap
        self.Refresh()


    ###########################################################
    def _takeAwaySiblingHighlight(self):
        """Walk through any siblings and make sure they're deselected.

        This is done on mouse down to make sure we don't have the
        selection border around more than one box.

        Note: redrawing of siblings happens right away...
        """
        parent = self.GetParent()
        siblings = list(parent.GetChildren())

        # Walk through all siblings, refreshing them right away if
        # we change their highlight...
        otherBlocks = [win
                       for win in siblings
                       if (win != self) and isinstance(win, ConstructionBlock)]
        for otherBlock in otherBlocks:
            if otherBlock._isSelected:
                otherBlock._isSelected = False
                otherBlock.Refresh()
                otherBlock.Update()


    ###########################################################
    def _sendEvent(self):
        """Send an event saying that we were clicked on."""

        event = ConstructionBlockEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED,
                                       self.GetId())
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)


    ###########################################################
    def _drawOnDc(self, borderWidth, borderColor, dc):
        """Draw ourselves on the given DC.

        We have a normal state and a "selected" state.  They have a different
        border and border color, but are otherwise the same.

        @param  borderWidth  The width of the border.
        @param  borderColor  The color of the border.
        """
        drawConstructionBlock(dc, self.GetClientSize(),
                              self._bitmap, self._label, self.GetFont(),
                              self.GetForegroundColour(), borderColor,
                              borderWidth, self._gradientColor)


##############################################################################
def drawConstructionBlock(dc, size, bitmap, label, font, txtColor,
                          borderColor, borderWidth=_kBorderWidth,
                          gradientColor=None):
    """Draw a construction block on the given dc.

    This is called from outside this file in some cases.

    @param  dc             The wx.DC to draw on.  If this is a MemoryDC, it
                           should be backed by a wx.Bitmap, not a
                           wx.Bitmap.FromRGBA.
    @param  size           The size to draw.
    @param  bitmap         The bitmap to use in the button; may be None.
    @param  label          The label to use in the button.  May be multiline--
                           each line will be truncated separately.  Note: it's
                           your responsibility to make sure there's enough
                           vertical space for all of the lines.
    @param  font           The font to use.
    @param  txtColor       The color to use for the text.
    @param  borderColor    The color of the border.
    @param  borderWidth    The width of the border.
    @param  gradientColor  The color to use for the gradient.  If None, we'll
                           figure something out from the border color.
    """
    (fullWidth, fullHeight) = size

    # Compute gradientColor if not passed in...
    if gradientColor is None:
        gradientColor = \
            tuple(c + ((255-c) * _kGradientBrightenPct) for c in borderColor)

    # Give us a pretty gradient as a background...
    # ...always offset by the _smaller_ border width so the gradient
    # is consistent between focused and non-focused.  ...the offset is
    # important, though, so that if we have a slightly-rounded border the
    # corners don't get filled in...
    dc.GradientFillLinear((_kBorderWidth, _kBorderWidth,
                           fullWidth - (2*_kBorderWidth),
                           fullHeight - (2*_kBorderWidth)),
                          "white", gradientColor, wx.SOUTH)

    # Draw the bitmap...
    y = _kMarginWidth
    if bitmap is not None:
        dc.DrawBitmap(bitmap, (fullWidth - bitmap.GetWidth()) / 2, y, True)
        y += bitmap.GetHeight()

    # Add the text, centering and trimming each line...
    dc.SetFont(font)

    # TODO: If we need to support disabled text, we could use:
    #       wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
    dc.SetTextForeground(txtColor)

    _, allTextHeight = dc.GetMultiLineTextExtent(label)
    spaceLeft = (fullHeight - _kMarginWidth) - y
    y += (spaceLeft - allTextHeight) / 2

    availTextWidth = fullWidth - (2 * _kMarginWidth)
    dotdotWidth, _ = dc.GetTextExtent("...")
    for line in label.splitlines():
        lineWidth, lineHeight = dc.GetTextExtent(line)
        if lineWidth > availTextWidth:
            partialLineWidths = dc.GetPartialTextExtents(line)
            for i, partialLineWidth in enumerate(partialLineWidths):
                if partialLineWidth > (availTextWidth - dotdotWidth):
                    i = max(0, i - 1)
                    break
            line = line[:i] + "..."
            lineWidth, lineHeight = dc.GetTextExtent(line)

        dc.DrawText(line, (fullWidth - lineWidth) / 2, y)
        y += lineHeight

    # Draw the border...
    dc.SetPen(wx.Pen(borderColor, borderWidth))
    dc.SetBrush(wx.TRANSPARENT_BRUSH)
    if wx.Platform == "__WXMSW__":
        # Windows seems to have an off-by-one error on the width when you've
        # got a pen width > 1.  It makes the rectangle one pixel too small.
        dc.DrawRectangle(borderWidth/2, borderWidth/2,
                         fullWidth - borderWidth+1,
                         fullHeight - borderWidth+1)
    else:
        dc.DrawRectangle(borderWidth/2, borderWidth/2,
                         fullWidth - borderWidth,
                         fullHeight - borderWidth)


##############################################################################
class ConstructionBlockEvent(wx.PyCommandEvent):
    """The event we fire off for constructoin blocks."""

    ###########################################################
    def __init__(self, eventType, id):
        """ConstructionBlockEvent constructor; only used internally.

        @param  eventType  The type of the event, like
                           wx.wxEVT_COMMAND_BUTTON_CLICKED
        @param  id         The ID.
        """
        super(ConstructionBlockEvent, self).__init__(eventType, id)



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    panel.SetDoubleBuffered(True)
    webcamBitmap = wx.Bitmap("frontEnd/bmps/questionMark.png")

    # Colors that we will use.  Grokked from the powerpoint slide.
    videoSourceColor = (181,  66,  66)
    lookForColor     = ( 95,  73, 180)
    thatAreColor     = (105, 154, 205)

    # These are designed to look like the powerpoint slide...
    cb1 = ConstructionBlock(panel, webcamBitmap, "Side camera",
                            size=(107, 68), color=videoSourceColor)
    cb2 = ConstructionBlock(panel, webcamBitmap, "People",
                            size=(107, 68), color=lookForColor)
    cb3 = ConstructionBlock(panel, webcamBitmap, "Inside\nThe garden",
                            size=(107, 68), color=thatAreColor)
    cb4 = ConstructionBlock(panel, webcamBitmap, "Crossing\na boundary",
                            size=(107, 68), color=thatAreColor)

    # These are intended to test resizing / cropping / boundary conditions...
    cb5 = ConstructionBlock(panel, webcamBitmap,
                            "If two witches were watching two watches,\n"
                            "which witch would watch which watch?",
                            size=(107, 68), color=(255, 255, 0))
    cb6 = ConstructionBlock(panel, webcamBitmap,
                            "The quick\n"
                            "black fox jumps\n"
                            "over the lazy dog",
                            size=(107, 68), color=(0, 255, 0))
    cb7 = ConstructionBlock(panel, webcamBitmap,
                            "ABC",
                            size=(107, 68), color=(0, 0, 255))

    # Throw everything into sizers...
    panelSizer = wx.BoxSizer(wx.VERTICAL)
    nonStretchSizer = wx.BoxSizer(wx.HORIZONTAL)
    nonStretchSizer.Add(cb1, 0, wx.ALL, 2)
    nonStretchSizer.Add(cb2, 0, wx.ALL, 2)
    nonStretchSizer.Add(cb3, 0, wx.ALL, 2)
    nonStretchSizer.Add(cb4, 0, wx.ALL, 2)
    panelSizer.Add(nonStretchSizer)
    panelSizer.Add(cb5, 1, wx.EXPAND | wx.ALL, 2)
    panelSizer.Add(cb6, 1, wx.ALL, 2)
    panelSizer.Add(cb7, 0, wx.EXPAND | wx.ALL, 2)
    panel.SetSizer(panelSizer)

    # Create a frame sizer, which appears to be needed if we use Fit()
    frameSizer = wx.BoxSizer()
    frameSizer.Add(panel, 1, wx.EXPAND)
    frame.SetSizer(frameSizer)

    # Fit and show...
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
