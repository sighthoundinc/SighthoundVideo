#! /usr/local/bin/python

#*****************************************************************************
#
# RealTimeRule.py
#    Encapsulation of query class combined with the scheduling information applying to it.
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
import datetime
import time

# Common 3rd-party imports...

# Local imports...



# Globals...
_kDefaultRuleSchedule = {'dayType' : 'Every day',
                         'customDays' : [],
                         'is24Hours' : True,
                         'startHour' : 8,
                         'stopHour' : 18,
                         'startMin' : 0,
                         'stopMin' : 0}

_kEveryday = [0, 1, 2, 3, 4, 5, 6]
_kWeekdays = [0, 1, 2, 3, 4]
_kWeekend = [5, 6]
_kDayStrToInt = {'Mon':0, 'Tue':1, 'Wed':2, 'Thu':3, 'Fri':4, 'Sat':5, 'Sun':6}


##############################################################################
class RealTimeRule(object):
    """A class containing information about real time rules."""
    ###########################################################
    def __init__(self, queryName, cameraLocation):
        """RealTimeRule constructor.

        @param queryName       The name of the query this rule uses to search.
        @param cameraLocation  The location where the rule is active.
        """
        super(RealTimeRule, self).__init__()

        self._queryName = queryName
        self._cameraLocation = cameraLocation
        self._isEnabled = True
        self._schedule = _kDefaultRuleSchedule


    ###########################################################
    def getQueryName(self):
        """Get the name of the rule's query.

        @return name  The name of the rule's query.
        """
        return self._queryName


    ###########################################################
    def setQueryName(self, queryName):
        """Set the name of the rule's query.

        @param  name  The name of the rule's query.
        """
        self._queryName = queryName


    ###########################################################
    def getSchedule(self):
        """Get the rule's schedule.

        @return schedule  The rule's schedule.
        """
        return self._schedule


    ###########################################################
    def setSchedule(self, schedule):
        """Set the rule's schedule.

        @param  schedule  The rule's schedule.
        """
        self._schedule = schedule


    ###########################################################
    def getCameraLocation(self):
        """Get the rule's camera location.

        @return cameraLocation  The rule's cameraLocation.
        """
        return self._cameraLocation


    ###########################################################
    def setCameraLocation(self, cameraLocation):
        """Set the rule's camera location.

        @param  cameraLocation  The rule's camera location.
        """
        self._cameraLocation = cameraLocation


    ###########################################################
    def isEnabled(self):
        """Return whether the rule is enabled.

        @param  enabled  True if the rule is enabled.
        """
        return self._isEnabled


    ###########################################################
    def setEnabled(self, enabled=True):
        """Set whether the rule is enabled or not.

        @param  enabled  True if the rule should be enabled.
        """
        self._isEnabled = enabled


    ###########################################################
    def getScheduleInfo(self):
        """Determine if the rule is currently scheduled and the next change.

        @param  isScheduled  True if the rule is currently scheduled to run.
        @param  nextChange   The time in seconds when the rule should change
                             state, or None if it will never change.
        """
        isScheduled = True
        nextChange = None

        now = datetime.datetime.today()
        nowDayInt = now.weekday()

        dayType = self._schedule['dayType']
        is24 = self._schedule['is24Hours']
        startHour = self._schedule['startHour']
        startMin = self._schedule['startMin']
        stopHour = self._schedule['stopHour']
        stopMin = self._schedule['stopMin']
        dateWraps = (stopHour < startHour) or \
                    (stopHour == startHour and stopMin < startMin)

        if dayType == "Every day":
            dayList = _kEveryday
        elif dayType == "Weekdays":
            dayList = _kWeekdays
        elif dayType == "Weekends":
            dayList = _kWeekend
        else:
            dayList = [_kDayStrToInt[dayStr] for
                       dayStr in self._schedule['customDays']]

        # 24 hours a day
        if is24:
            # Determine the next start or stop time, 12:00am
            nextChange = now.replace(hour=0, minute=0, second=0, microsecond=0)
            dayDelta = 1

            if len(dayList) == 7:
                # If we're active every day we never have a change.
                isScheduled, nextChange = True, None

            elif nowDayInt in dayList:
                # If we're active today find the next day we aren't.
                while (nowDayInt+dayDelta) % 7 in dayList:
                    dayDelta += 1
                isScheduled, nextChange = True, _datetimeToSeconds(nextChange +
                                                datetime.timedelta(dayDelta))
            else:
                # If we're not active find the next day we are.
                while (nowDayInt+dayDelta) % 7 not in dayList:
                    dayDelta += 1
                isScheduled, nextChange = False, _datetimeToSeconds(nextChange +
                                                 datetime.timedelta(dayDelta))

        # Specified times without wrapping.
        elif not dateWraps:
            # Determine if for any given day we would be before, in or after
            # the specified time range.
            beforeTimeRange = now.hour < startHour or \
                              (now.hour == startHour and now.minute < startMin)
            inTimeRange = not beforeTimeRange and ((now.hour < stopHour) or \
                          (now.hour == stopHour and now.minute < stopMin))
            afterTimeRange = (not beforeTimeRange and not inTimeRange)

            # Calculate the times we would start or stop if we were active or
            # inactive.
            activeNextChange = now.replace(hour=stopHour, minute=stopMin)
            inactiveNextChange = now.replace(hour=startHour, minute=startMin)

            if nowDayInt not in dayList or afterTimeRange:
                # After the scheduled time, return the next scheduled day
                # at the start time.
                dayDelta = 1
                while (nowDayInt+dayDelta) % 7 not in dayList:
                    dayDelta += 1
                isScheduled = False
                nextChange = _datetimeToSeconds(inactiveNextChange +
                                                datetime.timedelta(dayDelta))
            elif inTimeRange:
                # If we're in the time range, return the current day at the
                # stop time.
                isScheduled = True
                nextChange = _datetimeToSeconds(activeNextChange)
            else:
                # Else we're beforeTimeRange, return the current day at the
                # start time.
                isScheduled = False
                nextChange = _datetimeToSeconds(inactiveNextChange)

        # Specified times that continue into the following day.
        else:
            # Determine if our hour/minute falls inside the next day schedule,
            # the current day schedule, or always unscheduled.
            nextDayTimeRange = now.hour < stopHour or \
                               (now.hour == stopHour and now.minute < stopMin)
            notInTimeRange = not nextDayTimeRange and ((now.hour < startHour) \
                             or (now.hour == startHour and \
                                 now.minute < startMin))
            curDayTimeRange = not nextDayTimeRange and not notInTimeRange

            # Calculate the times we would start or stop if we were active or
            # inactive.
            activeNextChange = now.replace(hour=stopHour, minute=stopMin)
            inactiveNextChange = now.replace(hour=startHour, minute=startMin)

            if nowDayInt in dayList and curDayTimeRange:
                # If we're on a scheduled day and in the starting time range...
                isScheduled = True
                nextChange = _datetimeToSeconds(activeNextChange +
                                                datetime.timedelta(1))
            elif (nowDayInt-1)%7 in dayList and nextDayTimeRange:
                # We're on the day after a scheduled day and in the next day
                # time range...
                isScheduled = True
                nextChange = _datetimeToSeconds(activeNextChange)
            elif nowDayInt in dayList:
                # We're on a scheduled day in a non-scheduled time...
                isScheduled = False
                nextChange = _datetimeToSeconds(inactiveNextChange)
            else:
                # We're on a non scheduled day in a non-scheduled time...
                dayDelta = 1
                while (nowDayInt+dayDelta) % 7 not in dayList:
                    dayDelta += 1
                isScheduled = False
                nextChange = _datetimeToSeconds(inactiveNextChange +
                                                datetime.timedelta(dayDelta))

        return isScheduled, nextChange


    ###########################################################
    def getScheduleSummary(self, use12HourTime=True):
        """Retrieve a text string describing the rule schedule."""
        summaryStr = ''

        if not self.isEnabled():
            return "Disabled"

        # Add the days wording
        if self._schedule['dayType'] == "Custom...":
            summaryStr = ', '.join(self._schedule['customDays'])
        else:
            summaryStr = self._schedule['dayType']
        summaryStr += ' - '

        # Add the hour wording
        if self._schedule['is24Hours']:
            summaryStr += "24 hours"
        else:
            startHour = self._schedule['startHour']
            if use12HourTime:
                if startHour > 12:
                    startHour -= 12
                if startHour == 0:
                    startHour = 12
                summaryStr += str(startHour)
            else:
                summaryStr += ("%02d" % startHour)

            if self._schedule['startMin'] or not use12HourTime:
                summaryStr += ":%02i" % self._schedule['startMin']
            if use12HourTime:
                if self._schedule['startHour'] < 12:
                    summaryStr += ' am'
                else:
                    summaryStr += ' pm'
            summaryStr += ' to '

            stopHour = self._schedule['stopHour']
            if use12HourTime:
                if stopHour > 12:
                    stopHour -= 12
                if stopHour == 0:
                    stopHour = 12
                summaryStr += str(stopHour)
            else:
                summaryStr += ("%02d" % stopHour)

            if self._schedule['stopMin'] or not use12HourTime:
                summaryStr += ":%02i" % self._schedule['stopMin']

            if use12HourTime:
                if self._schedule['stopHour'] < 12:
                    summaryStr += ' am'
                else:
                    summaryStr += ' pm'


        if (self._schedule['startHour'] > self._schedule['stopHour']) or \
               ((self._schedule['startHour'] == self._schedule['stopHour']) \
               and (self._schedule['startMin'] >= self._schedule['stopMin'])):
            summaryStr += ' the next day'

        return summaryStr


#####################################################################
def _datetimeToSeconds(datetimeObj):
    # Convert a datetime object to seconds since epoch
    return time.mktime(datetimeObj.timetuple())
