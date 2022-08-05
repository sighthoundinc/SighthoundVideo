#!/usr/bin/env python

#*****************************************************************************
#
# RuleScheduleDialog.py
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

# Common 3rd-party imports...
import wx

# Local imports...
from backEnd.RealTimeRule import RealTimeRule
from vitaToolbox.dictUtils.OrderedDict import OrderedDict
from vitaToolbox.wx.FixedTimeCtrl import FixedTimeCtrl, EVT_TIMEUPDATE
from vitaToolbox.wx.FixedTimeCtrl import DoesThisLocalRequire24HrFmt

# Globals...
_kPaddingSize = 8


###############################################################
class RuleScheduleDialog(wx.Dialog):
    """A dialog for editing real time rule schedules."""
    ###########################################################
    def __init__(self, parent, ruleName, backEndClient, use24Hour):
        """Initializer for RuleScheduleDialog.

        @param  parent         The parent window.
        @param  ruleName       The identifier for the rule.
        @param  backEndClient  An object for communicating with the back end.
        @param  use24Hour      True if 24 hour time should be used.
        """
        wx.Dialog.__init__(self, parent, -1, "Schedule for Rules")

        try:
            self._use24Hour = use24Hour
            self._doInit(ruleName, backEndClient)
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _doInit(self, ruleName, backEndClient):
        """Actual init code; see __init__() for details.

        This function exists so we can put a "try" around it easily...
        """
        self._backEndClient = backEndClient
        self._ruleName = ruleName

        # Use an ordered dict for tracking enabled dates as we'll use the keys
        # to generate a text string
        self._customDateDict = OrderedDict()
        self._customDateDict["Sun"] = False
        self._customDateDict["Mon"] = False
        self._customDateDict["Tue"] = False
        self._customDateDict["Wed"] = False
        self._customDateDict["Thu"] = False
        self._customDateDict["Fri"] = False
        self._customDateDict["Sat"] = False

        # Create sizers
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        flexSizer = wx.FlexGridSizer(3, 2, _kPaddingSize, _kPaddingSize)
        daysSizer = wx.BoxSizer(wx.HORIZONTAL)
        timeSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        timeSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(mainSizer)

        # Create the summary text
        self._summaryText = wx.StaticText(self, -1, "")

        # Create the days controls
        daysLabel = wx.StaticText(self, -1, "Days:")
        daysChoices = ["Every day", "Weekdays", "Weekends", "Custom..."]
        self._daysChoice = wx.Choice(self, -1, choices=daysChoices)
        self._daysChoice.SetSelection(0)
        self._daysChoice.Bind(wx.EVT_CHOICE, self.OnDaysChoice)
        self._daysText = wx.StaticText(self, -1,
                                       "Sun, Mon, Tue, Wed, Thu, Fri, Sat")
        daysSizer.Add(self._daysChoice, 0, wx.EXPAND | wx.RIGHT, _kPaddingSize)
        daysSizer.Add(self._daysText, 1, wx.EXPAND)

        # Create the time range controls
        timeLabel = wx.StaticText(self, -1, "Time:")
        self._24Radio = wx.RadioButton(self, -1, style=wx.RB_GROUP)
        self._24Radio.Bind(wx.EVT_RADIOBUTTON, self.On24HourRadio)
        self._24Radio.SetValue(True)
        allHourText = wx.StaticText(self, -1, "24 hours per day")
        allHourText.Bind(wx.EVT_LEFT_DOWN, self.On24HourRadio)
        self._customHourRadio = wx.RadioButton(self, -1)
        self._customHourRadio.Bind(wx.EVT_RADIOBUTTON, self.OnCustomHourRadio)

        if (not self._use24Hour) and (not DoesThisLocalRequire24HrFmt()):
            fmt = 'HHMM'
        else:
            fmt = '24HHMM'

        self._startTimeCtrl = FixedTimeCtrl(self, -1, value='08:00:00',
                                            size=wx.DefaultSize, format=fmt)
        _, timeHeight = self._startTimeCtrl.GetSize()
        self._startTimeSpin = wx.SpinButton(self, -1, size=(-1, timeHeight),
                                            style=wx.SP_VERTICAL | wx.SP_WRAP)
        self._startTimeCtrl.BindSpinButton(self._startTimeSpin)
        self._startTimeCtrl.Bind(EVT_TIMEUPDATE, self.OnCustomHourRadio)
        self._stopTimeCtrl = FixedTimeCtrl(self, -1, value='18:00:00',
                                           size = wx.DefaultSize, format=fmt)
        self._stopTimeSpin = wx.SpinButton(self, -1, size=(-1, timeHeight),
                                           style=wx.SP_VERTICAL | wx.SP_WRAP)
        self._stopTimeCtrl.BindSpinButton(self._stopTimeSpin)
        self._stopTimeCtrl.Bind(EVT_TIMEUPDATE, self.OnCustomHourRadio)
        timeSizer1.Add(self._24Radio, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                       _kPaddingSize)
        timeSizer1.Add(allHourText, 0, wx.ALIGN_CENTER_VERTICAL)
        timeSizer2.Add(self._customHourRadio, 0, wx.ALIGN_CENTER_VERTICAL |
                       wx.RIGHT, _kPaddingSize)
        timeSizer2.Add(self._startTimeCtrl, 0, wx.ALIGN_CENTER_VERTICAL)
        timeSizer2.Add(self._startTimeSpin, 0, wx.ALIGN_CENTER_VERTICAL)
        timeSizer2.Add(wx.StaticText(self, -1, "to"), 0, wx.RIGHT | wx.LEFT |
                       wx.ALIGN_CENTER_VERTICAL, _kPaddingSize)
        timeSizer2.Add(self._stopTimeCtrl, 0, wx.ALIGN_CENTER_VERTICAL)
        timeSizer2.Add(self._stopTimeSpin, 0, wx.ALIGN_CENTER_VERTICAL)
        self.On24HourRadio()

        # Create ok and cancel buttons
        buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOK)
        self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)

        # Add everything to the main sizer
        flexSizer.Add(daysLabel, 0, wx.EXPAND)
        flexSizer.Add(daysSizer, 1, wx.EXPAND)
        flexSizer.Add(timeLabel, 0, wx.EXPAND)
        flexSizer.Add(timeSizer1, 1, wx.EXPAND)
        flexSizer.AddSpacer(0)
        flexSizer.Add(timeSizer2, 1, wx.EXPAND)
        mainSizer.Add(flexSizer, 0, wx.EXPAND | wx.TOP | wx.RIGHT | wx.LEFT, _kPaddingSize*2)
        mainSizer.Add(self._summaryText, 1, wx.EXPAND | wx.ALL, _kPaddingSize*2)
        mainSizer.Add(buttonSizer, 0, wx.EXPAND | wx.ALL, _kPaddingSize)

        self._summaryText.SetLabel("\n\n")

        self.Fit()
        self.CenterOnParent()
        self._daysText.SetLabel("")

        rule = self._backEndClient.getRule(self._ruleName)

        # Get rule schedule information and populate
        self._curSchedule = rule.getSchedule()
        self._daysChoice.SetStringSelection(self._curSchedule['dayType'])
        if self._curSchedule['dayType'] == 'Custom...':
            for day in self._curSchedule['customDays']:
                self._customDateDict[day] = True
        if not self._curSchedule['is24Hours']:
            startHour = str(self._curSchedule['startHour'])
            startMin = str(self._curSchedule['startMin'])
            stopHour = str(self._curSchedule['stopHour'])
            stopMin = str(self._curSchedule['stopMin'])
            self._startTimeCtrl.SetValue(startHour + ':' + startMin + ':00')
            self._stopTimeCtrl.SetValue(stopHour + ':' + stopMin + ':00')
            self.OnCustomHourRadio()

        self._updateActiveDaysText()
        self._updateSummary()


    ###########################################################
    def On24HourRadio(self, event=None):
        """Handle the user radio selection.

        @param  event  The radio button event (ignored).
        """
        self._24Radio.SetValue(True)
        self._updateSummary()


    ###########################################################
    def OnCustomHourRadio(self, event=None):
        """Handle the user radio selection.

        @param  event  The radio button event (ignored).
        """
        self._customHourRadio.SetValue(True)
        self._updateSummary()


    ###########################################################
    def OnDaysChoice(self, event=None):
        """Handle a day range selection

        @param  event  The choice event (ignored).
        """
        if self._daysChoice.GetStringSelection() == "Custom...":
            dlg = _CustomDaysDialog(self, self._customDateDict)
            try:
                dlg.ShowModal()
            finally:
                dlg.Destroy()

        self._updateActiveDaysText()
        self._updateSummary()


    ###########################################################
    def _updateActiveDaysText(self):
        """Update the active days text string."""
        if self._daysChoice.GetStringSelection() == "Custom...":
            # Retrieve a list of the selected days
            activeDays = []
            for day in self._customDateDict:
                if self._customDateDict[day]:
                    activeDays.append(day)
            if not activeDays:
                # If there are no days clear the string and set the choice
                # control to "Every day".
                self._daysChoice.SetSelection(0)
                self._daysText.SetLabel('')
            else:
                # Build and set the days string
                self._daysText.SetLabel(', '.join(activeDays))
        else:
            self._daysText.SetLabel('')


    ###########################################################
    def OnOK(self, event=None):
        """Respond to the OK selection.

        @param  event  The button event (ignored).
        """
        # Update the rule schedule
        self._curSchedule['dayType'] = self._daysChoice.GetStringSelection()
        if self._curSchedule['dayType'] == 'Custom...':
            self._curSchedule['customDays'] = []
            for day in self._customDateDict:
                if self._customDateDict[day]:
                    self._curSchedule['customDays'].append(day)

        self._curSchedule['is24Hours'] = self._24Radio.GetValue()
        if not self._curSchedule['is24Hours']:
            startStrList = self._startTimeCtrl.GetValue().split(':')
            startAm = startStrList[1].endswith('AM')
            stopStrList = self._stopTimeCtrl.GetValue().split(':')
            stopAm = stopStrList[1].endswith('AM')
            self._curSchedule['startHour'] = int(startStrList[0])
            self._curSchedule['startMin'] = int(startStrList[1][:2])
            self._curSchedule['stopHour'] = int(stopStrList[0])
            self._curSchedule['stopMin'] = int(stopStrList[1][:2])

            if not self._use24Hour:
                # We want the times to be represented in 24 hour time. If they
                # are in 12 hour, adjust.
                if (not startAm and self._curSchedule['startHour'] != 12) or \
                   (startAm and self._curSchedule['startHour'] == 12):
                    self._curSchedule['startHour'] += 12
                    self._curSchedule['startHour'] %= 24
                if (not stopAm and self._curSchedule['stopHour'] != 12) or \
                   (stopAm and self._curSchedule['stopHour'] == 12):
                    self._curSchedule['stopHour'] += 12
                    self._curSchedule['stopHour'] %= 24

        self._backEndClient.setRuleSchedule(self._ruleName, self._curSchedule)

        self.EndModal(wx.OK)


    ###########################################################
    def OnCancel(self, event=None):
        """Respond to canceling the dialog.

        @param  event  The button event (ignored).
        """
        self.EndModal(wx.CANCEL)


    ###########################################################
    def _updateSummary(self, event=None):
        """Update the summary text.

        @param event  Ignored.  Allows this function to be bound to events.
        """
        summaryStr = ''

        # Add the days wording
        if self._daysChoice.GetStringSelection() == "Custom...":
            dayStrs = []
            if self._customDateDict['Sun']:
                dayStrs.append('Sundays')
            if self._customDateDict['Mon']:
                dayStrs.append('Mondays')
            if self._customDateDict['Tue']:
                dayStrs.append('Tuesdays')
            if self._customDateDict['Wed']:
                dayStrs.append('Wednesdays')
            if self._customDateDict['Thu']:
                dayStrs.append('Thursdays')
            if self._customDateDict['Fri']:
                dayStrs.append('Fridays')
            if self._customDateDict['Sat']:
                dayStrs.append('Saturdays')
            summaryStr = ', '.join(dayStrs)
        else:
            summaryStr = self._daysChoice.GetStringSelection()
        summaryStr += ' - '

        # Add the hour wording
        if self._24Radio.GetValue():
            summaryStr += "24 hours."
        else:
            startStr = self._startTimeCtrl.GetValue().lower()
            stopStr = self._stopTimeCtrl.GetValue().lower()
            if not self._use24Hour:
                if startStr.startswith('0'):
                    startStr = startStr[1:]
                if stopStr.startswith('0'):
                    stopStr = stopStr[1:]
            summaryStr += startStr + " to " + stopStr
            if self._stopTimeCtrl.GetValue(True) <= \
               self._startTimeCtrl.GetValue(True):
                summaryStr += " the next day"

        self._summaryText.SetLabel(summaryStr)
        self._summaryText.Wrap(self.Size[0]-_kPaddingSize*4)


###############################################################
class _CustomDaysDialog(wx.Dialog):
    """A dialog for selecting weekdays."""
    ###########################################################
    def __init__(self, parent, daysDict):
        """Initializer for _CustomDaysDialog.

        @param  parent    The parent window.
        @param  daysDict  A dict to update with the selected days.
        """
        wx.Dialog.__init__(self, parent, -1, "Custom Days")

        try:
            self._doInit(daysDict)
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _doInit(self, daysDict):
        """Actual init code; see __init__() for details.

        This function exists so we can put a "try" around it easily...
        """
        self._daysDict = daysDict

        # Create the day controls
        self._sun = wx.CheckBox(self, -1, "Sunday")
        self._sun.SetValue(daysDict["Sun"])
        self._mon = wx.CheckBox(self, -1, "Monday")
        self._mon.SetValue(daysDict["Mon"])
        self._tue = wx.CheckBox(self, -1, "Tuesday")
        self._tue.SetValue(daysDict["Tue"])
        self._wed = wx.CheckBox(self, -1, "Wednesday")
        self._wed.SetValue(daysDict["Wed"])
        self._thu = wx.CheckBox(self, -1, "Thursday")
        self._thu.SetValue(daysDict["Thu"])
        self._fri = wx.CheckBox(self, -1, "Friday")
        self._fri.SetValue(daysDict["Fri"])
        self._sat = wx.CheckBox(self, -1, "Saturday")
        self._sat.SetValue(daysDict["Sat"])

        # Create ok and cancel buttons
        buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOK)
        self.FindWindowById(wx.ID_CANCEL, self).Bind(wx.EVT_BUTTON, self.OnCancel)

        # Sizer fun
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)
        sizer.Add(self._sun, 0, wx.TOP | wx.LEFT | wx.RIGHT, _kPaddingSize*2)
        sizer.AddSpacer(_kPaddingSize/2)
        sizer.Add(self._mon, 0, wx.LEFT | wx.RIGHT, _kPaddingSize*2)
        sizer.AddSpacer(_kPaddingSize/2)
        sizer.Add(self._tue, 0, wx.LEFT | wx.RIGHT, _kPaddingSize*2)
        sizer.AddSpacer(_kPaddingSize/2)
        sizer.Add(self._wed, 0, wx.LEFT | wx.RIGHT, _kPaddingSize*2)
        sizer.AddSpacer(_kPaddingSize/2)
        sizer.Add(self._thu, 0, wx.LEFT | wx.RIGHT, _kPaddingSize*2)
        sizer.AddSpacer(_kPaddingSize/2)
        sizer.Add(self._fri, 0, wx.LEFT | wx.RIGHT, _kPaddingSize*2)
        sizer.AddSpacer(_kPaddingSize/2)
        sizer.Add(self._sat, 0, wx.LEFT | wx.RIGHT, _kPaddingSize*2)
        sizer.Add(buttonSizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.TOP,
                  _kPaddingSize*2)

        self.Fit()
        self.CenterOnParent()


    ###########################################################
    def OnOK(self, event=None):
        """Respond to the OK selection.

        @param  event  The button event (ignored).
        """
        if not self._sun.GetValue() and not self._mon.GetValue() and \
           not self._tue.GetValue() and not self._wed.GetValue() and \
           not self._thu.GetValue() and not self._fri.GetValue() and \
           not self._sat.GetValue():
            wx.MessageBox("You must select at least one day.", "Error",
                          wx.OK | wx.ICON_ERROR, self)
            return

        self._daysDict['Sun'] = self._sun.GetValue()
        self._daysDict['Mon'] = self._mon.GetValue()
        self._daysDict['Tue'] = self._tue.GetValue()
        self._daysDict['Wed'] = self._wed.GetValue()
        self._daysDict['Thu'] = self._thu.GetValue()
        self._daysDict['Fri'] = self._fri.GetValue()
        self._daysDict['Sat'] = self._sat.GetValue()
        self.EndModal(wx.OK)


    ###########################################################
    def OnCancel(self, event=None):
        """Respond to canceling the dialog.

        @param  event  The button event (ignored).
        """
        self.EndModal(wx.CANCEL)

