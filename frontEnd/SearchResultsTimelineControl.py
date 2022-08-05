#!/usr/bin/env python

#*****************************************************************************
#
# SearchResultsTimelineControl.py
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
import datetime
import sys
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle

# Local imports...


# Constants...
_kMinDivisionsPerHour = 10
_kMaxHoursPerDay   = 25   # Daylight savings changeover...

_kMinTimebarWidth = _kMaxHoursPerDay * _kMinDivisionsPerHour + 2 # 2px for border
_kTimebarHeight = 17

_kSecIn1H       = 60 * 60
_kMsIn1H        = 1000 * _kSecIn1H

# The spacing above and below the time...
_kSpacing = 4

# The labels at the bottom...
# TODO: Handle 24H time?  ...locale-specific AM/PM?
_kLabels12 = ["12a", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
              "12p", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
              "12a"]
_kLabels24 = ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
              "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21",
              "22", "23", "24"]


if wx.Platform == "__WXMSW__":
    _kLabelFontSize = 8
else:
    _kLabelFontSize = 9


# Various color settings...
_kLabelColor            = "black"
_kClipColor             = ( 27,  87, 174)
_kVideoAvailBottomColor = (152, 202,  87)
_kVideoAvailTopColor    = (171, 213, 118)
_kBorderColor           = (163, 175, 192)
_kBlueLineColor         = (189, 212, 234)
_kCursorColor           = (255, 102,   0)


##############################################################################
class SearchResultsTimelineControl(wx.Control):
    """The timeline control for the search results."""

    ###########################################################
    def __init__(self, parent, resultsModel):
        """SearchResultsTimelineControl constructor.

        @param  parent       Our parent UI element.
        @param  resultsModel The SearchResultDataModel to listen to.
        """
        # Call our super
        super(SearchResultsTimelineControl, self).__init__(
            parent, -1, style=wx.BORDER_NONE | wx.TRANSPARENT_WINDOW
        )

        self._is12 = True

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Set our color and font...
        self.SetForegroundColour(_kLabelColor)
        font = self.GetFont()
        font.SetPointSize(_kLabelFontSize)
        self.SetFont(font)

        # Get the size of the first/last label for calculations below...
        assert _kLabels12[0] == _kLabels12[-1], "Math assumes first and last are ="
        self._width12a, self._height12a = self.GetTextExtent(_kLabels12[0])

        # Figure out our size...
        minWidth = _kMinTimebarWidth + self._width12a
        maxHeight = _kTimebarHeight + self._height12a + 2 * _kSpacing
        self.SetMinSize((minWidth, maxHeight))

        # Cache coordinates...
        self._timebarX = 0

        # Things that change based on the day; set in _handleResultsChange()
        self._labels = None

        # Keep track of the cursor position, from 0 to (self._numDivisions-1)...
        self._cursorPosition = None

        # Save the results model and listen for updates...
        self._resultsModel = resultsModel
        self._resultsModel.addListener(self._handleResultsChange,
                                       False, 'results')
        self._resultsModel.addListener(self._handleVideoAvailChange,
                                       False, 'videoAvail')
        self._resultsModel.addListener(self._handleMsChange,
                                       False, 'ms')
        self._resultsModel.addListener(self._handleVideoLoaded,
                                       False, 'videoLoaded')

        # Setup midnight ms values and timebar
        self._handleResultsChange(self._resultsModel)

        # Initial state...
        self._isPressed = False

        # We need to paint ourselves...
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # We need to handle all the mouse stuff...
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnMouseUp)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    ###########################################################
    def OnDestroy(self, event=None):
        """ Explicitly release mouse capture, if needed
        """
        if self.HasCapture():
            self.ReleaseMouse()

    ###########################################################
    def _getNumDivisions(self):
        """Return the number of divisions in the toolbar.

        @return numDivisions  The number of divisions, min 1.
        """
        return max(1, self.GetSize()[0]-2-self._width12a)


    ###########################################################
    def _getMsPerDivision(self):
        """Return the number of ms covered by each division.

        @return msPerDivision  The number of ms covered by each division.
        """
        return self._getNumDivisions()/float(self._numMsToday)


    ###########################################################
    def _adjustConstantsByMidnight(self):
        """Adjust our internal constants based on the current midnight.

        This handles things like daylight savings time.
        """
        if self._curMidnightMs is None:
            # We'll do things based on today's mightnight by default...
            midnightSecs = int(time.mktime(datetime.date.today().timetuple()))
        else:
            midnightSecs = self._curMidnightMs/1000

        midnightDate = datetime.date.fromtimestamp(midnightSecs)
        nextMidnightDate = midnightDate + datetime.timedelta(1)  # Handles DST!
        nextMidnightSec = int(time.mktime(nextMidnightDate.timetuple()))

        hoursInThisDay = (nextMidnightSec - midnightSecs) / _kSecIn1H
        self._numMsToday = hoursInThisDay*_kMsIn1H

        # Adjust labels...
        self._labels = []
        for i in xrange(hoursInThisDay + 1):
            dt = datetime.datetime.fromtimestamp(midnightSecs + i * _kSecIn1H)
            if self._is12:
                self._labels.append(_kLabels12[dt.hour])
            else:
                self._labels.append(_kLabels24[dt.hour])



    ###########################################################
    def OnMouseDown(self, event):
        """Handle mouse down on ourselves.

        @param  event  The event; may be a mouse down or a double-click event.
        """
        if self._curMidnightMs is None:
            event.Skip()
            return

        x, y = (event.X, event.Y)

        if self._isPointOnTimeline(x, y):
            self._isPressed = True

            # We're going through a process of rapid change (until mouse up)
            self._resultsModel.setChangingRapidly(True)

            # Start capturing the mouse...
            self.CaptureMouse()

            # Treat the down as a move...
            self.OnMouseMove(event)
        else:
            event.Skip()


    ###########################################################
    def OnMouseMove(self, event):
        """Handle mouse move on the window.

        @param  event  The event; may be a move event, a mouse up event, or
                       even a double-click event.
        """
        x, _ = event.X, event.Y

        if self.HasCapture():
            # Find divNum from 0 to (self._numDivisions-1).  Remember to account
            # for the 1 pixel border around the timebar...
            #
            # Note: we continue tracking the pen even if it actually moves
            # off from on top of the timebar...
            #divNum = min(self._numDivisions-1, max(0, x - (self._timebarX+1)))
            divNum = min(self._getNumDivisions()-1, max(0, x - (self._timebarX+1)))

            # Find the division numbers to the "left" of the current division
            # and to the "right" where we have a non-None value in the map.
            # Note that if the current division is non-None, left and right
            # will both be the current division.
            # Also look for the clip num to the right so we can figure out
            # our ".5" value (we'll be rightClip - .5)
            leftAnything = None
            rightAnything = None
            rightClip = None

            for i in xrange(divNum, -1, -1):
                if self._divisionMap[i] is not None:
                    if leftAnything is None:
                        leftAnything = i
                        break

            for i in xrange(divNum, self._getNumDivisions()):
                if self._divisionMap[i] is not None:
                    if rightAnything is None:
                        rightAnything = i
                    if isinstance(self._divisionMap[i], int):
                        rightClip = i
                        break

            # Find which divNum we're actually going to go to.  Right now,
            # it's always the closest thing...
            if leftAnything is not None:
                if rightAnything is not None:
                    if (divNum - leftAnything) <= (rightAnything - divNum):
                        divNum = leftAnything
                    else:
                        divNum = rightAnything
                else:
                    divNum = leftAnything
            else:
                if rightAnything is not None:
                    divNum = rightAnything
                else:
                    divNum = None

            if divNum is not None:
                ms = (divNum * self._numMsToday / self._getNumDivisions()) + \
                        self._curMidnightMs

                if isinstance(self._divisionMap[divNum], int):
                    # We're on a clip.  Go there.
                    clipNum = self._divisionMap[divNum]
                    self._resultsModel.setCurrentClipNum(clipNum, ms)
                else:
                    # We're on cache; figure out the closest clip by using
                    # the clipNum that we found to the right, then move into
                    # cache...
                    if rightClip is None:
                        clipNum = self._resultsModel.getNumMatchingClips() - .5
                    else:
                        clipNum = self._divisionMap[rightClip] - .5

                    startMs, stopMs = self._divisionMap[divNum]
                    ms = max(startMs, min(stopMs, ms))

                    self._resultsModel.setCurrentClipNum(clipNum, ms)
        else:
            # If we think we're selected but we don't have capture, we somehow
            # lost capture; force mouse up processing...
            if self._isPressed:
                self.OnMouseUp(event)

        event.Skip()


    ###########################################################
    def OnMouseUp(self, event):
        """Handle mouse up on the window.

        @param  event  The event; may be a mouse up or a double-click event.
        """
        # On mouse up, just release capture...
        if self.HasCapture():
            self.ReleaseMouse()

        if self._isPressed:
            self._isPressed = False

            # We're no longer changing rapidly...
            self._resultsModel.setChangingRapidly(False)


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
        # If we think we're selected but we don't have capture, we somehow
        # lost capture; force mouse up processing...
        if self._isPressed:
            self.OnMouseUp(event)


    ###########################################################
    def _isPointOnTimeline(self, x, y):
        """Return true if the given point is on the timeline.

        @param  x             The x coord, in local coords.
        @param  y             The y coord, in local coords.
        @return isOnTimeline  True if (x, y) is on the timeline.
        """
        x -= self._timebarX
        return (x >= 0) and (y >= 0) and \
               (x < self._getNumDivisions()+2) and (y < _kTimebarHeight)


    ###########################################################
    def _handleResultsChange(self, resultsModel):
        """Handle a change in search results.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        if self._resultsModel.didSearch():
            self._curMidnightMs = self._resultsModel.getMidnightMs()
        else:
            self._curMidnightMs = None

        self._adjustConstantsByMidnight()

        self._cursorPosition = None

        if not self.IsShown():
            return

        self._makeDivisionMap()
        self._makeTimebarBitmap()
        self.Refresh()


    ###########################################################
    def _handleVideoAvailChange(self, resultsModel):
        """Handle a change in available video (though nothing else).

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        if not self.IsShown():
            return

        # Ignore this if no search range...
        if self._curMidnightMs is None:
            return

        # All we gotta do is to re-do the division map, then the bitmap.
        self._makeDivisionMap()
        self._makeTimebarBitmap()

        # Refresh, since we changed our bitmap...
        self.Refresh()


    ###########################################################
    def _handleMsChange(self, resultsModel):
        """Handle a change in search millisecond.

        In this case, we want to redraw since the cursor needs to be updated.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        if not self.IsShown():
            return

        # Ignore this if no search range...
        if self._curMidnightMs is None:
            return

        ms = self._resultsModel.getCurrentAbsoluteMs()
        cursorPosition = self._calcDivisionFor(ms)
        if cursorPosition != self._cursorPosition:
            self._cursorPosition = cursorPosition
            self.Refresh()


    ###########################################################
    def _handleVideoLoaded(self, resultsModel):
        """Handle when a video is loaded.

        We also refresh, since this implies a ms change.

        @param  resultsModel  Should be self._resultsModel
        """
        assert resultsModel == self._resultsModel

        if not self.IsShown():
            return

        # Ignore this if no search range...
        if self._curMidnightMs is None:
            return

        ms = self._resultsModel.getCurrentAbsoluteMs()
        cursorPosition = self._calcDivisionFor(ms)
        if cursorPosition != self._cursorPosition:
            self._cursorPosition = cursorPosition
            self.Refresh()


    ###########################################################
    def _makeDivisionMap(self):
        """Make a map from division number to clip or cache.

        This will be stored in self._divisionMap.
        """
        # The divisionMap will look like this:
        # - None if nothing at that spot
        # - An integer if a clip is at that spot, indicating the clip number.
        #   in the list of matching clips.
        # - A tuple of (startMs, stopMs) if cache is at that spot.
        self._divisionMap = [None] * self._getNumDivisions()

        # Walk through current search results...
        # ...if this ends up being too slow, we'll have to use numpy or somesuch
        # to do this (might be pretty fast with numpy.bincount?)
        if self._resultsModel.didSearch() and (self._curMidnightMs is not None):
            matchingClips = self._resultsModel.getMatchingClips()
            availVideo = self._resultsModel.getAvailableVideoRanges()

            # Do avail video first, and in reversed order.  This will mean
            # that matching clips (and earlier starting available video) will
            # take priority in the map...
            for (startMs, stopMs) in reversed(availVideo):
                startDiv = self._calcDivisionFor(startMs)
                stopDiv = self._calcDivisionFor(stopMs)
                self._divisionMap[startDiv:stopDiv+1] = \
                    [(startMs, stopMs)] * (stopDiv-startDiv + 1)

            # Next, do matching clips, again in reversed order so that
            # earlier clips take priority.
            for i in xrange(len(matchingClips)-1, -1, -1):
                startMs = matchingClips[i].startTime
                stopMs = matchingClips[i].stopTime

                startDiv = self._calcDivisionFor(startMs)
                stopDiv = self._calcDivisionFor(stopMs)
                self._divisionMap[startDiv:stopDiv+1] = \
                    [i] * (stopDiv-startDiv + 1)


    ###########################################################
    def _makeTimebarBitmap(self):
        """Make a bitmap for the timebar using the current pens.

        Requires that self._divisionMap is already made.
        This will be stored in self._timeBarBitmap.
        """
        w = self.GetSize()[0] - self._width12a
        if w < 1:
            return

        self._timebarWidth = w
        self._timebarX = self._width12a/2

        bitmap = wx.Bitmap.FromRGBA(w, _kTimebarHeight)
        dc = wx.MemoryDC()
        dc.SelectObject(bitmap)

        # Important to do a GC here, since DC has trouble drawing on a bitmap
        # with alpha (it just leaves the alpha channel alone, which is a
        # problem)...
        gc = wx.GraphicsContext.Create(dc)

        # Draw the border...
        # ...don't understand why width and height are -1 here?  ...because we
        # are using the pen, not the brush???
        gc.SetPen(wx.Pen(_kBorderColor))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRectangle(0, 0, w-1, _kTimebarHeight-1)

        # Draw the "lines"...
        if self._resultsModel.didSearch() and (self._curMidnightMs is not None):
            seqStartDivision = None
            seqType = type(None)

            gc.SetPen(wx.TRANSPARENT_PEN)

            availBrush = gc.CreateLinearGradientBrush(
                0, _kTimebarHeight-2, 0, 0,
                _kVideoAvailBottomColor, _kVideoAvailTopColor
            )
            clipBrush = wx.Brush(_kClipColor)

            for i in xrange(len(self._divisionMap) + 1):
                if i == self._getNumDivisions():
                    divisionData = None
                else:
                    divisionData = self._divisionMap[i]

                if type(divisionData) != seqType:
                    if seqType == int:
                        gc.SetBrush(clipBrush)
                        gc.DrawRectangle(seqStartDivision + 1, 1,
                                         i - seqStartDivision,
                                         _kTimebarHeight-2)
                    elif seqType == tuple:
                        gc.SetBrush(availBrush)
                        gc.DrawRectangle(seqStartDivision + 1, 1,
                                         i - seqStartDivision,
                                         _kTimebarHeight-2)

                    seqStartDivision = i
                    seqType = type(divisionData)


        # Get the result...
        dc.SelectObject(wx.NullBitmap)
        self._timeBarBitmap = bitmap


    ###########################################################
    def _calcDivisionFor(self, ms):
        """Calculate what division the given ms belongs in.

        The timeline is separated into a bunch of discrete divisions--this
        figures out which one the given ms belongs in.  If the ms is before
        the start, it will be cropped to the start.  If the ms is after the end,
        it will be cropped to the end.

        @param  ms           A millisecond value (absolute time).
        @return divisionNum  The division number.
        """
        if ms is None:
            return None

        divisionNum = int((ms - self._curMidnightMs) * self._getNumDivisions() / self._numMsToday)
        return min(max(0, divisionNum), self._getNumDivisions()-1)


    ###########################################################
    def OnPaint(self, event):
        """Paint ourselves.

        @param  event  The paint event.
        """
        width, height = self.GetClientSize()

        dc = wx.PaintDC(self)

        # If we have no midnight, just hide ourselves.  IMPORTANT to do this
        # after creating the wx.PaintDC, since wx gets upset if you don't do
        # that.
        if self._curMidnightMs is None:
            return

        dc.SetFont(self.GetFont())

        dc.SetTextForeground(self.GetForegroundColour())
        dc.SetBackgroundMode(wx.TRANSPARENT)

        # Draw the time bar...
        dc.DrawBitmap(self._timeBarBitmap, self._timebarX, 0, True)

        # Draw the labels...
        timebarWidth = self._getNumDivisions()+2 # num divisions + border
        spacePerLabel = timebarWidth / float(len(self._labels) - 1)
        for i, label in enumerate(self._labels):
            cx = int(round((self._timebarX) + (i * spacePerLabel)))
            labelWidth, _ = dc.GetTextExtent(label)
            dc.DrawText(label, cx - labelWidth/2, _kTimebarHeight + _kSpacing)

        # Draw the blue line at the bottom
        dc.SetPen(wx.Pen(_kBlueLineColor))
        dc.DrawLine(self._timebarX, height-1, self._timebarX + timebarWidth,
                height-1)

        # Draw the cursor if it's available...
        if self._cursorPosition is not None:
            dc.SetPen(wx.Pen(_kCursorColor))
            dc.DrawLine(self._timebarX + 1 + self._cursorPosition, 0,
                        self._timebarX + 1 + self._cursorPosition, height)


    ###########################################################
    def OnSize(self, event=None):
        """Recreate the timeline control to match the new width.

        @param event  The wx.EVT_SIZE event.
        """
        self.recreateTimeline()


    ###########################################################
    def recreateTimeline(self):
        """Update the timeline bitmap and cursor position."""
        if not self.IsShown():
            return

        self._makeDivisionMap()
        self._makeTimebarBitmap()

        if self._resultsModel:
            # Ensure the cursor is in the correct position
            self._handleMsChange(self._resultsModel)

        self.Refresh()


    ###########################################################
    def enable12HourTime(self, enable):
        """Toggle 12 and 24 hour time displays.

        @param  enable  True to use 12 hour time.
        """
        needRedraw = enable != self._is12
        self._is12 = enable

        if needRedraw:
            self._handleResultsChange(self._resultsModel)


##############################################################################
def _figureMidnightForMs(ms):
    """Figure out midnight for the given ms value.

    @return midnightMs  The midnight ms.
    """
    midnightDateTime = datetime.date.fromtimestamp(float(ms) / 1000)
    midnightTime = time.mktime(midnightDateTime.timetuple())
    midnightMs = int(midnightTime * 1000)

    return midnightMs


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    from vitaToolbox.mvc.AbstractModel import AbstractModel
    from vitaToolbox.wx.GradientPanel import GradientPanel

    # Fake up something with some reasonable results.  Current absolute ms
    # will be now, and we'll bogus up some time for the day...
    class FakeResultsModel(AbstractModel):
        def __init__(self):
            AbstractModel.__init__(self)

            nowTime = time.time()
            self._ms = int(round(nowTime * 1000))
            self._midnightMs = _figureMidnightForMs(self._ms)
        def getCurrentAbsoluteMs(self):
            return self._ms
        def getAvailableVideoRanges(self):
            msIn1H = _kMsIn1H
            return [
                (self._midnightMs + (0 * msIn1H),
                 self._midnightMs + (1 * msIn1H) - 1),
                (self._midnightMs + (8 * msIn1H),
                 self._midnightMs + (24 * msIn1H) - 1),
            ]
        def getMatchingClips(self):
            msIn1H = _kMsIn1H
            return [
                (None,
                 self._midnightMs + (2 * msIn1H),
                 self._midnightMs + (2 * msIn1H) + 1,
                 None, None, None, None),
                (None,
                 self._midnightMs + (2 * msIn1H) + 1000 * 60 * 10,
                 self._midnightMs + (2 * msIn1H) + 1000 * 60 * 30,
                 None, None, None, None),
                (None,
                 self._midnightMs + (9 * msIn1H),
                 self._midnightMs + (10 * msIn1H),
                 None, None, None, None),
            ]
        def didSearch(self):
            return True
        def getMidnightMs(self):
            return self._midnightMs
    fakeResults = FakeResultsModel()

    app = wx.App(False)

    frame = wx.Frame(None)
    panel = GradientPanel(frame)

    ctrl = SearchResultsTimelineControl(panel, fakeResults)
    fakeResults.update('results')

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    sizer.AddSpacer(64)
    sizer.Add(ctrl, 0, wx.ALIGN_CENTER_VERTICAL)
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



