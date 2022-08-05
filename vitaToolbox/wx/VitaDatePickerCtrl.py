#!/usr/bin/env python

#*****************************************************************************
#
# VitaDatePickerCtrl.py
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

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.BackgroundStyleUtils import kBackgroundStyle
from vitaToolbox.sysUtils.TimeUtils import formatTime

# Local imports...
from HoverBitmapButton import HoverBitmapButton
from HoverButton import HoverButton
from TextSizeUtils import makeFontDefault

# Constants...

# ...the spacing between the next/previous day controls and the text...
_kSpacing = 3

_kDateUS = "%a %m/%d/%y"
_kDateInternational = "%a %d.%m.%Y"

_kTodayString = "Today"
_kYesterdayString = "Yesterday"


##############################################################################
class VitaDatePickerCtrl(wx.Panel):
    """An alternate to DatePickerCtrl that looks like Rob wants it to.

    A few notes about "today":
    - If we're showing today's date, we'll show the special string "Today".
    - If we're showing yesterday's date, we'll show "Yesterday".
    - We listen for idle events; and at idle check to see if "today" changed.
      That way, we can handle cases where today changes while this control is
      up.
    - If you used the "earliestDate" or "latestDate" limits and used the special
      string "today", then today changes, this _could_ cause a date change.
      This is especially common when the earliestDate is today.  In that case,
      if the user currently has today picked and midnight rolls around, that
      will cause an automatic switch (including sending out an event) to keep
      the date in range.
    """

    ###########################################################
    def __init__(self, parent, initialDate=None,
                 earliestDate=None, latestDate=None, isBoldFn=None):
        """VitaDatePickerCtrl constructor.

        @param  parent        Our parent UI element.
        @param  initialDate   The initial date (in datetime.date format), or
                              None to use today.
        @param  earliestDate  We don't allow the user to pick a date earlier
                              than this date; None means no limit.  Special
                              value of "today" means that "today" is the
                              earliest date they can pick.
        @param  latestDate    We don't allow the user to pick a date later
                              than this date; None means no limit.  Special
                              value of "today" means that "today" is the latest
                              date they can pick.
        @param  isBoldFn      A function that will be called when we show a
                              calendar that should return whether to make the
                              date bold.  Takes a datetime.date object.
        """
        # Call our super
        super(VitaDatePickerCtrl, self).__init__(
            parent, -1, style=wx.BORDER_NONE | wx.TRANSPARENT_WINDOW
        )

        # Tell the window that we have a custom background style.  This keeps
        # wx from erasing our background for us and avoids flicker.
        self.SetBackgroundStyle(kBackgroundStyle)

        # Adjust parameters...
        if initialDate is None:
            initialDate = datetime.date.today()

        # Save parameters...
        self._date = initialDate
        self._earliestDate = earliestDate
        self._latestDate = latestDate
        self._isBoldFn = isBoldFn

        self._dateFormat = _kDateUS

        # Initialize this; it will be set in self._getDateString()
        self._lastKnownToday = None

        # Open our bitmaps...
        self._prevDayButton = HoverBitmapButton(
            self, wx.ID_ANY,
            "vitaToolbox/wx/bmps/Date_Arrow_Left_Enabled.png",
            wx.EmptyString,
            "vitaToolbox/wx/bmps/Date_Arrow_Left_Pressed.png",
            "vitaToolbox/wx/bmps/Date_Arrow_Left_Disabled.png",
            "vitaToolbox/wx/bmps/Date_Arrow_Left_Hover.png",
            True
        )

        self._dateButton = HoverButton(self, "")
        #makeFontDefault(self._dateButton)

        # Figure out maximum date size by iterating through 7 days in a long
        # month.  Kinda hacky, but best I could come up with...
        #
        # NOTE: Assumes that "Today" and "Yesterday" are smaller, but could
        # add that if needed...
        maxWidth = 0
        for i in xrange(7):
            for dateFormat in (_kDateUS, _kDateInternational):
                s = formatTime(dateFormat, datetime.date(2099, 12, 20 + i))

                self._dateButton.SetLabel(s)
                labelWidth, _ = self._dateButton.GetBestSize()
                maxWidth = max(maxWidth, labelWidth)
        self._dateButton.SetMinSize((maxWidth, -1))

        self._nextDayButton = HoverBitmapButton(
            self, wx.ID_ANY,
            "vitaToolbox/wx/bmps/Date_Arrow_Right_Enabled.png",
            wx.EmptyString,
            "vitaToolbox/wx/bmps/Date_Arrow_Right_Pressed.png",
            "vitaToolbox/wx/bmps/Date_Arrow_Right_Disabled.png",
            "vitaToolbox/wx/bmps/Date_Arrow_Right_Hover.png",
            True
        )

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self._prevDayButton, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                  _kSpacing)
        sizer.Add(self._dateButton, 0, wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, 1)
        sizer.Add(self._nextDayButton, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
                  _kSpacing)

        self.SetSizer(sizer)

        # Bind...
        self._prevDayButton.Bind(wx.EVT_BUTTON, self.OnPrevDay)
        self._nextDayButton.Bind(wx.EVT_BUTTON, self.OnNextDay)
        self._dateButton.Bind(wx.EVT_BUTTON, self.OnDateButton)
        self._dateButton.Bind(wx.EVT_CONTEXT_MENU, self.OnShowPopup)
        self.Bind(wx.EVT_IDLE, self.OnIdle)

        # Make sure label and prev/next is right...
        self._updateUi()


    ###########################################################
    def useUSDateFormat(self, useUS):
        """Toggle the date format from US to international.

        @param  useUS  If True use a US date format.
        """
        if useUS:
            self._dateFormat = _kDateUS
        else:
            self._dateFormat = _kDateInternational

        self._updateUi()


    ###########################################################
    def _replaceToday(self, date):
        """Return a real datetime object, or None (AKA replace "today")

        @param  date  Either a date object, None, or the special string "today".
        @return date  Either a date object or None.
        """
        if date == "today":
            return datetime.date.today()
        else:
            return date


    ###########################################################
    def _updatePrevNext(self):
        """Update the enabled state of the prev and next controls."""
        earliestDate = self._replaceToday(self._earliestDate)
        latestDate = self._replaceToday(self._latestDate)

        if latestDate is not None:
            self._nextDayButton.Enable(self._date < latestDate)
        if earliestDate is not None:
            self._prevDayButton.Enable(self._date > earliestDate)


    ###########################################################
    def _makeDateInRange(self, date):
        """Crop the given date to our range.

        @param  date          The original date.
        @return date          A date that's in range.
        """
        earliestDate = self._replaceToday(self._earliestDate)
        latestDate = self._replaceToday(self._latestDate)

        if (latestDate is not None) and (date > latestDate):
            date = latestDate
        if (earliestDate is not None) and (date < earliestDate):
            date = earliestDate

        return date


    ###########################################################
    def GetValue(self):
        """Return the date.

        Note that we return a python datetime object, not a wx.DateTime.

        @return curDate  The currently selected date.
        """
        return self._date


    ###########################################################
    def SetValue(self, newDate):
        """Set the date.

        Note that this doesn't sent an event.  Also note that we take a
        python datetime object, not a wx.DateTime.

        @param  newDate  The new date.
        """
        newInRangeDate = self._makeDateInRange(newDate)
        assert newInRangeDate == newDate, "Shouldn't set out of range date"

        self._date = newInRangeDate
        self._updateUi()


    ###########################################################
    def OnIdle(self, event):
        """Handle idle events; we use this to tell if the day changed.

        We may need to update ourselves if the day changed, since the text
        "Today" or "Yesterday" may be outdated.

        @param  event  The event.
        """
        if datetime.date.today() != self._lastKnownToday:
            # Make need to update day if no longer in range, which might happen
            # if "today" was specified...
            newDate = self._makeDateInRange(self._date)
            if newDate != self._date:
                self._date = newDate
                self._sendEvent()

            self._updateUi()

        event.Skip()


    ###########################################################
    def OnPrevDay(self, event=None):
        """Handle a press on the 'previous' button.

        @param  event  The event (ignored).
        """
        self._date -= datetime.timedelta(1)
        self._updateUi()
        self._sendEvent()


    ###########################################################
    def OnNextDay(self, event=None):
        """Handle a press on the 'previous' button.

        @param  event  The event (ignored).
        """
        self._date += datetime.timedelta(1)
        self._updateUi()
        self._sendEvent()


    ###########################################################
    def OnDateButton(self, event=None):
        """Handle a press on the actual date.

        @param  event  The event (ignored).
        """
        dlg = _CalendarPopup(self.GetTopLevelParent(), self._date,
                             self._replaceToday(self._earliestDate),
                             self._replaceToday(self._latestDate),
                             self._isBoldFn)
        try:
            # Put the dialog at the right place...
            dlgWidth, _ = dlg.GetSize()
            myWidth, myHeight = self.GetSize()
            topCenterX, topCenterY = self.ClientToScreen((myWidth/2, 0))
            dlg.SetPosition((topCenterX - dlgWidth/2, topCenterY))

            # Show it...
            dlg.ShowModal()

            # Get the results...
            newDate = dlg.GetValue()
            newDate = self._makeDateInRange(newDate)
            if newDate != self._date:
                self._date = newDate
                self._updateUi()
                self._sendEvent()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnShowPopup(self, event):
        """Handle the context menu event.

        @param  event  The event to handle
        """
        # Create our menu.
        menu = wx.Menu()

        enterManuallyMenuItem = menu.Append(-1, "Go to Date...")
        self.Bind(wx.EVT_MENU, self.OnManualEnterDate, enterManuallyMenuItem)

        # Popup the menu
        pos = event.GetPosition()
        pos = self.ScreenToClient(pos)
        self.PopupMenu(menu, pos)

        # Unbind.  Not sure if this is necessary, but seems like a good idea.
        self.Unbind(wx.EVT_MENU, enterManuallyMenuItem)

        # Kill the menu
        menu.Destroy()


    ###########################################################
    def OnManualEnterDate(self, event=None):
        """Allow the user to manually enter a date.

        TODO: We may take this out?

        @param  event  The event (ignored).
        """
        dlg = wx.TextEntryDialog(self.GetTopLevelParent(),
                                 "Type in a date, like 1999-12-31:",
                                 "Go to Date",
                                 str(self._date))
        try:
            dlg.CenterOnParent()
            dlgResult = dlg.ShowModal()
            if dlgResult != wx.ID_OK:
                return

            result = dlg.GetValue()

            try:
                newDate = datetime.datetime.strptime(result, "%Y-%m-%d").date()
            except ValueError:
                wx.MessageBox("Date must be in the format \"YYYY-MM-DD\".",
                              "Error", wx.OK | wx.ICON_ERROR,
                              self.GetTopLevelParent())
            else:
                newDateInRange = self._makeDateInRange(newDate)
                if newDateInRange != newDate:
                    wx.MessageBox("Date out of range.",
                                  "Error", wx.OK | wx.ICON_ERROR,
                                  self.GetTopLevelParent())
                elif newDate != self._date:
                    self._date = newDate
                    self._updateUi()
                    self._sendEvent()
        finally:
            dlg.Destroy()


    ###########################################################
    def _getDateString(self):
        """Return the current date, as a string.

        @return dateStr  The date, as a string.
        """
        today = datetime.date.today()
        self._lastKnownToday = today

        if self._date == today:
            return _kTodayString
        elif self._date == (today - datetime.timedelta(1)):
            return _kYesterdayString
        else:
            return formatTime(self._dateFormat, self._date)


    ###########################################################
    def _updateUi(self):
        """Update prev/next and the date string.
        """
        self._dateButton.SetLabel(self._getDateString())
        self._updatePrevNext()


    ###########################################################
    def _sendEvent(self):
        """Send an event saying that we were clicked on."""

        event = VitaDatePickerEvent(wx.adv.wxEVT_DATE_CHANGED, self.GetId())
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)


##############################################################################
_kCalBorder = 5
_kCalHgap = 4
_kCalVgap = 1
_kHeaderVgap = 3

_kNumDaysInWeek = 7
_kNumWeeksInCal = 6
_kNumDaysInCal = (_kNumDaysInWeek * _kNumWeeksInCal)

_kFirstDayOfWeek = 6  # Sunday = 6, Monday = 0

# All colors are tuples:               text color,           background color,     borderColor
_kNormalColorForInitial         = ((236, 243, 252, 255), ( 27,  87, 174, 255), (  0,   0,   0,   0))
_kPressedColorForInitial        = (( 85,  26, 139, 255), (222, 238, 253, 255), (  0,   0,   0,   0))
_kHoverColorForInitial          = ((  0, 102, 204, 255), (222, 238, 253, 255), (  0,   0,   0,   0))

_kNormalColorForDayInMonth      = ((  0, 102, 204, 255), (  0,   0,   0,   0), (  0,   0,   0,   0))
_kPressedColorForDayInMonth     = (( 85,  26, 139, 255), (222, 238, 253, 255), (  0,   0,   0,   0))
_kHoverColorForDayInMonth       = ((  0, 102, 204, 255), (222, 238, 253, 255), (  0,   0,   0,   0))
_kDisabledColorForDayInMonth    = ((127, 127, 127, 255), (  0,   0,   0,   0), (  0,   0,   0,   0))

_kNormalColorForDayNotInMonth   = ((  0,   0,   0, 255), (  0,   0,   0,   0), (  0,   0,   0,   0))
_kPressedColorForDayNotInMonth  = (( 85,  26, 139, 255), (222, 238, 253, 255), (  0,   0,   0,   0))
_kHoverColorForDayNotInMonth    = ((  0,   0,   0, 255), (222, 238, 253, 255), (  0,   0,   0,   0))
_kDisabledColorForDayNotInMonth = ((127, 127, 127, 255), (  0,   0,   0,   0), (  0,   0,   0,   0))


##############################################################################
class _CalendarPopup(wx.Dialog):
    """A dialog that we can show with ShowModal to show a calendar.

    TODO: If this is useful, we could abstract it out?  ...but there are already
    do many other calendar widgets out there...
    """

    ###########################################################
    def __init__(self, parent, initialDate, earliestDate=None, latestDate=None,
                 isBoldFn=None):
        """_CalendarPopup constructor.

        @param  parent        Our parent UI element.
        @param  initialDate   A datetime object for the initial date.
        @param  earliestDate  We don't allow the user to pick a date earlier
                              than this date; None means no limit.
        @param  latestDate    We don't allow the user to pick a date later
                              than this date; None means no limit.
        @param  isBoldFn      A function that will be called when we show a
                              calendar that should return whether to make the
                              date bold.
        """
        super(_CalendarPopup, self).__init__(
            parent, style=0
        )

        try:
            self._doInit(initialDate, earliestDate, latestDate, isBoldFn)
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _doInit(self, initialDate, earliestDate, latestDate, isBoldFn):
        """Actual init code; see __init__() for details.

        This function exists so we can put a "try" around it easily...
        """
        assert ((earliestDate is None) or (initialDate >= earliestDate) and
                (latestDate is None)   or (initialDate <= latestDate)      ), \
               "Initial date must be in range"

        # Save params...
        self._chosenDate = initialDate
        self._earliestDate = earliestDate
        self._latestDate = latestDate
        self._isBoldFn = isBoldFn

        # This is the first of the month we're currently looking at...
        self._firstOfMonth = initialDate.replace(day=1)

        # This first of the earliest and latest months; both inclusive...
        # ...for comparison with self._firstOfMonth...
        if earliestDate is not None:
            self._earliestMonth = earliestDate.replace(day=1)
        else:
            self._earliestMonth = None
        if latestDate is not None:
            self._latestMonth = latestDate.replace(day=1)
        else:
            self._latestMonth = None

        # This is the first shown date--calculated in _updateMonth
        self._firstShownDate = None


        # Extra UI init...
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour("white")

        # Init the return code to -1 so that we can tell if EndModal was
        # called (we don't want to call it twice--that crashes on Windows)
        self.SetReturnCode(-1)

        # Make a zero-sized Cancel button so that Escape works on Windows.
        self.SetEscapeId(wx.ID_CANCEL)
        cancelButton = wx.Button(self, wx.ID_CANCEL, "", size=(0, 0),
                                 style=wx.NO_BORDER)
        _ = cancelButton

        # Make UI...
        self._prevMonthButton = HoverButton(self, "<<", wantRepeats=True)
        self._monthText = wx.StaticText(self, -1, "",
                                        style=wx.ST_NO_AUTORESIZE |
                                        wx.ALIGN_CENTER)
        self._nextMonthButton = HoverButton(self, ">>", wantRepeats=True)
        makeFontDefault(self._prevMonthButton, self._monthText,
                        self._nextMonthButton)

        # Make the heading text with automatic localization.  We'll pick a
        # known Monday and then use strftime().
        day1 = datetime.date(2006, 4, 3) + datetime.timedelta(_kFirstDayOfWeek)
        self._dowLabels = []
        for i in xrange(_kNumDaysInWeek):
            s = formatTime("%a", day1 + datetime.timedelta(i))[0]
            self._dowLabels.append(
                wx.StaticText(self, -1, s,
                              style=wx.ST_NO_AUTORESIZE | wx.ALIGN_CENTER)
            )
        makeFontDefault(*self._dowLabels)

        staticLine = wx.StaticLine(self)

        self._dayButtons = []
        for i in xrange(_kNumDaysInCal):
            hoverButton = HoverButton(self, "99", style=wx.ALIGN_RIGHT)
            hoverButton.SetId(i)
            makeFontDefault(hoverButton)
            hoverButton.SetBold(True)
            hoverButton.SetMinSize(hoverButton.GetBestSize())
            hoverButton.SetBold(False)
            self._dayButtons.append(hoverButton)

        self._todayButton = HoverButton(self, _kTodayString)
        firstOfTodaysMonth = datetime.date.today().replace(day=1)
        self._todayButton.Enable(
            ((self._earliestMonth is None)               or
             (firstOfTodaysMonth >= self._earliestMonth)   ) and
            ((self._latestMonth is None)               or
             (firstOfTodaysMonth <= self._latestMonth)   )
        )
        makeFontDefault(self._todayButton)

        # Add to sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        headerSizer = wx.BoxSizer(wx.HORIZONTAL)
        headerSizer.Add(self._prevMonthButton, 0, wx.ALIGN_CENTER_VERTICAL)
        headerSizer.Add(self._monthText, 1, wx.ALIGN_CENTER_VERTICAL)
        headerSizer.Add(self._nextMonthButton, 0, wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(headerSizer, 0, wx.EXPAND | wx.BOTTOM, _kHeaderVgap)

        dowSizer = wx.GridSizer(rows=1, cols=_kNumDaysInWeek, vgap=0, hgap=_kCalHgap)
        for i in xrange(_kNumDaysInWeek):
            dowSizer.Add(self._dowLabels[i], 1, wx.EXPAND)
        mainSizer.Add(dowSizer, 0, wx.EXPAND)

        mainSizer.Add(staticLine, 0, wx.EXPAND)

        daySizer = wx.GridSizer(rows=_kNumWeeksInCal, cols=_kNumDaysInWeek,
                                hgap=_kCalHgap, vgap=_kCalVgap)
        for i in xrange(_kNumDaysInCal):
            daySizer.Add(self._dayButtons[i], 1, wx.EXPAND)
        mainSizer.Add(daySizer, 0, wx.EXPAND)

        mainSizer.Add(self._todayButton, 0, wx.EXPAND)

        borderSizer = wx.BoxSizer()
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, _kCalBorder)

        self.SetSizer(borderSizer)

        # Bind
        self._prevMonthButton.Bind(wx.EVT_BUTTON, self.OnPrevMonth)
        self._nextMonthButton.Bind(wx.EVT_BUTTON, self.OnNextMonth)
        self._todayButton.Bind(wx.EVT_BUTTON, self.OnTodayButton)
        for i in xrange(_kNumDaysInCal):
            self._dayButtons[i].Bind(wx.EVT_BUTTON, self.OnDateButton)

        self.Bind(wx.EVT_IDLE, self.OnIdle)

        # Update everything...
        self._updateMonth(True)

        self.Fit()
        wx.CallLater(1, self._updateMonth)


    ###########################################################
    def GetValue(self):
        """Return the date.

        @return curDate  The currently selected date.
        """
        return self._chosenDate


    ###########################################################
    def _updateMonth(self, disableAll=False):
        """Update all the buttons to match self._firstOfMonth"""
        # Show a wait cursor as this can sometimes be slow.
        # Only do this on windows as the mac wait cursor looks terrible
        # and winds up being replaced by the beachball after a second or
        # two anyway.
        if not disableAll and sys.platform != 'darwin':
            self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
            for child in self.GetChildren():
                child.SetCursor(wx.Cursor(wx.CURSOR_WAIT))

        self._monthText.SetLabel(formatTime("%B %Y", self._firstOfMonth))

        # Find the first day to show in the calendar...
        curDate = self._firstOfMonth
        while curDate.weekday() != _kFirstDayOfWeek:
            curDate -= datetime.timedelta(1)

        self._firstShownDate = curDate

        # Go through and set all of the labels...
        for i in xrange(_kNumDaysInCal):
            self._dayButtons[i].SetLabel(str(curDate.day))

            if curDate == self._chosenDate and not disableAll:
                # Init date
                self._dayButtons[i].SetColors(
                    _kNormalColorForInitial, None,
                    _kPressedColorForInitial, _kHoverColorForInitial
                )
            elif curDate.month == self._firstOfMonth.month and not disableAll:
                # This month
                self._dayButtons[i].SetColors(
                    _kNormalColorForDayInMonth, _kDisabledColorForDayInMonth,
                    _kPressedColorForDayInMonth, _kHoverColorForDayInMonth
                )
            else:
                # Not this month
                self._dayButtons[i].SetColors(
                    _kNormalColorForDayNotInMonth,
                    _kDisabledColorForDayNotInMonth,
                    _kPressedColorForDayNotInMonth, _kHoverColorForDayNotInMonth
                )

            wantEnabled = True
            if disableAll:
                wantEnabled = False
            elif ((self._earliestDate is not None) and
                  (curDate < self._earliestDate)      ):
                wantEnabled = False
            elif ((self._latestDate is not None) and
                  (curDate > self._latestDate)      ):
                wantEnabled = False

            if self._isBoldFn is not None:
                self._dayButtons[i].SetBold(wantEnabled and
                                            self._isBoldFn(curDate))

            self._dayButtons[i].Enable(wantEnabled)

            curDate += datetime.timedelta(1)

        self._prevMonthButton.Enable(self._firstOfMonth != self._earliestMonth
                                     and not disableAll)
        self._nextMonthButton.Enable(self._firstOfMonth != self._latestMonth
                                     and not disableAll)

        if not disableAll and sys.platform != 'darwin':
            # Restore the default cursor.
            self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            for child in self.GetChildren():
                child.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))


    ###########################################################
    def OnIdle(self, event=None):
        """Called on idle events.

        Try to check for mouse clicks that are outside our window to
        dismiss ourselves.  TODO: a better way to do this?
        """
        # Always set event for skipping...
        event.Skip()

        # If we've already called EndModal, we're a no-op
        if self.GetReturnCode() != -1:
            return

        mouseState = wx.GetMouseState()
        if mouseState.LeftIsDown():
            mouseX, mouseY = mouseState.GetX(), mouseState.GetY()
            ourWidth, ourHeight = self.GetSize()
            relativeX, relativeY = self.ScreenToClient((mouseX, mouseY))

            if (relativeX < 0) or (relativeX > ourWidth) or \
               (relativeY < 0) or (relativeY > ourHeight):
                self.EndModal(wx.ID_CANCEL)


    ###########################################################
    def OnPrevMonth(self, event=None):
        """Handle going to the previous month.

        @param  event  The event (ignored).
        """
        if self._firstOfMonth.month == 1:
            self._firstOfMonth = \
                self._firstOfMonth.replace(year=self._firstOfMonth.year-1,
                                           month=12)
        else:
            self._firstOfMonth = \
                self._firstOfMonth.replace(month=self._firstOfMonth.month-1)
        self._updateMonth()


    ###########################################################
    def OnNextMonth(self, event=None):
        """Handle going to the next month.

        @param  event  The event (ignored).
        """
        if self._firstOfMonth.month == 12:
            self._firstOfMonth = \
                self._firstOfMonth.replace(year=self._firstOfMonth.year+1,
                                           month=1)
        else:
            self._firstOfMonth = \
                self._firstOfMonth.replace(month=self._firstOfMonth.month+1)
        self._updateMonth()


    ###########################################################
    def OnTodayButton(self, event=None):
        """Handle a press on the actual date.

        @param  event  The event (ignored).
        """
        self._chosenDate = datetime.date.today()
        self.EndModal(wx.ID_OK)


    ###########################################################
    def OnDateButton(self, event):
        """Handle a press on one of the days.

        @param  event  The event
        """
        buttonId = event.GetEventObject().GetId()
        self._chosenDate = self._firstShownDate + datetime.timedelta(buttonId)
        self.EndModal(wx.ID_OK)


##############################################################################
class VitaDatePickerEvent(wx.PyCommandEvent):
    """The event we fire off."""

    ###########################################################
    def __init__(self, eventType, id):
        """VitaDatePickerEvent constructor; only used internally.

        @param  eventType  The type of the event, like
                           wx.wxEVT_COMMAND_BUTTON_CLICKED
        @param  id         The ID.
        """
        super(VitaDatePickerEvent, self).__init__(eventType, id)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    from GradientPanel import GradientPanel
    app = wx.App(False)

    frame = wx.Frame(None)
    panel = GradientPanel(frame, startColor=(172, 0, 0))
    panel.SetDoubleBuffered(True)

    datePicker1 = VitaDatePickerCtrl(panel)
    datePicker2 = VitaDatePickerCtrl(panel, None, None, "today")
    datePicker3 = VitaDatePickerCtrl(panel, None, "today", None)
    datePicker4 = VitaDatePickerCtrl(panel, datetime.date(1997, 4, 3),
                                     datetime.date(1976, 4, 3),
                                     datetime.date(2006, 4, 3))

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(datePicker1, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 20)
    sizer.Add(datePicker2, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 20)
    sizer.Add(datePicker3, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 20)
    sizer.Add(datePicker4, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 20)

    panel.SetSizer(sizer)

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
