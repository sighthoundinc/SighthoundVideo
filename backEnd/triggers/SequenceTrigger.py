#!/usr/bin/env python

#*****************************************************************************
#
# SequenceTrigger.py
#     Trigger: daisy-chaining two triggers
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


from BaseTrigger import BaseTrigger


###############################################################
class SequenceTrigger(BaseTrigger):
    """A trigger that fires when one trigger follows another within some time"""
    ###########################################################
    def __init__(self, trigger1, trigger2, msecs, sameObject=True):
        """Initializer for the SequenceTrigger class

        @param  trigger1    Trigger that should fire first
        @param  trigger2    Trigger to follow the first within a certain time
        @param  msecs       The time trigger 2 should fire before or after
        @param  sameObject  If True the alert object must be the same for each
                            trigger
        """
        BaseTrigger.__init__(self)

        self._t1 = trigger1
        self._t2 = trigger2
        self._msecs = msecs
        self._sameObject = sameObject

        # In the case of same object alerts, this is a dict of objIds to alarm
        # times, otherwise it is a set of alert times from any object.
        if sameObject:
            self._t1AlertTimes = {}
        else:
            self._t1AlertTimes = set()

        self._latestTime = 0


    ###########################################################
    def __str__(self):
        """Create a string representation of the trigger

        @return strDesc  A string description of the trigger
        """
        return 'Sequence Trigger - Fires when ' \
               '[%s] occurs within %.3f seconds of [%s]' % \
               (str(self._t2), self._msecs/1000., str(self._t1))


    ###########################################################
    def setProcessingCoordSpace(self, coordSpace):
        """Sets the processing coordinate space for searches.

        Note 1: Should call 'spatiallyAware()' first to see if it is worth
                calling this function, since only spatially aware triggers will
                implement it.
        Note 2: There is no need to overload this method if designing a new
                subclass that will not be spatially aware, unless it will
                contain and expose functionality of other triggers that are
                spatially aware.

        @param  coordSpace  The coordinate space as a 2-tuple, (width, height).
        """
        self._t1.setProcessingCoordSpace(coordSpace)
        self._t2.setProcessingCoordSpace(coordSpace)



    ###########################################################
    def search(self, timeStart=None, timeStop=None, type='single', procSizesMsRange=None):
        """Search the database for objects tripping the trigger

        @param  timeStart        The time to start searching from, None for beginning
        @param  timeStop         The time to stop searching at, None for present
        @param  type             The type of search to be performed
                                   'single'   - The database is presumed complete
                                   'realtime' - Maintain state between searches
        @param  procSizesMsRange A list of sizes the camera was processed at for
                                 certain ranges of time. Contains a list of 4-tuples
                                 of (procWidth, procHeight, firstMs, lastMs).
                                 Note: if the list contains only one 4-tuple, then
                                 procWidth and procHeight is unique, and firstMs and
                                 lastMs should be ignored; they may hold None values.
                                 If the list contains more than one 4-tuple, then
                                 procWidth and procHeight are not unique, and you must
                                 use the firstMs and lastMs to determine which
                                 procSize was used for a specified period of time.
        @return triggered        A list of dbId, frame, time tuples for objects that
                                 set off the trigger
        """
        self._latestTime = timeStop

        t1Results = self._t1.search(timeStart, timeStop, type, procSizesMsRange)
        t2Results = self._t2.search(timeStart, timeStop, type, procSizesMsRange)

        triggered = self._doSearch(t1Results, t2Results)

        if type == 'single':
            self.reset()

        return triggered


    ###########################################################
    def finalize(self, objList, procSizesMsRange=None):
        """Do a final search on some objects assuming all data has been received

        @param  objList          A list or set of dbIds of objects to search
        @param  procSizesMsRange A list of sizes the camera was processed at for
                                 certain ranges of time. Contains a list of 4-tuples
                                 of (procWidth, procHeight, firstMs, lastMs).
                                 Note: if the list contains only one 4-tuple, then
                                 procWidth and procHeight is unique, and firstMs and
                                 lastMs should be ignored; they may hold None values.
                                 If the list contains more than one 4-tuple, then
                                 procWidth and procHeight are not unique, and you must
                                 use the firstMs and lastMs to determine which
                                 procSize was used for a specified period of time.
        @return triggered        A list of dbId, frame, time tuples for objects that
                                 set off the trigger presuming no more data will come
        """
        triggered = self._doSearch(self._t1.finalize(objList, procSizesMsRange),
                                   self._t2.finalize(objList, procSizesMsRange))

        # We also take this opportunity to purge old timepoints we're tracking
        minTime = None

        if self._latestTime:
            minTime = self._latestTime - self._msecs

        if self._sameObject:
            for obj in objList:
                if not minTime and len(self._t1AlertTimes[obj]):
                    minTime = max(self._t1AlertTimes[obj])
                    minTime = minTime-self._msecs
                del self._t1AlertTimes[obj]

            for obj in self._t1AlertTimes:
                self._t1AlertTimes[obj] = \
                    [time for time in self._t1AlertTimes[obj] if time > minTime]
        else:
            if not minTime and len(self._t1AlertTimes):
                minTime = max(self._t1AlertTimes)
                minTime = minTime-self._msecs
            self._t1AlertTimes = \
                [time for time in self._t1AlertTimes if time > minTime]

        return triggered


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataManager  The new data manager
        """
        self._t1.setDataManager(dataManager)
        self._t2.setDataManager(dataManager)


    ###########################################################
    def reset(self):
        """Remove any continuation data from a trigger"""
        if self._sameObject:
            self._t1AlertTimes = {}
        else:
            self._t1AlertTimes = set()

        self._t1.reset()
        self._t2.reset()


    ###########################################################
    def _doSearch(self, t1Results, t2Results):
        """Update the active objects and trigger if conditions are met

        @param  t1Results  The results from a search on trigger1
        @param  t2Results  The results from a search on trigger2
        @return triggered  A list of dbId, frame, time tuples for objects
                           that set off the trigger
        """
        triggered = []

        for result in t1Results:
            if self._sameObject:
                if result[0] not in self._t1AlertTimes:
                    self._t1AlertTimes[result[0]] = []
                self._t1AlertTimes[result[0]].append(result[2])
            else:
                self._t1AlertTimes.add(result[2])

        for result in t2Results:
            if self._sameObject:
                timeList = []
                if result[0] in self._t1AlertTimes:
                    timeList = self._t1AlertTimes[result[0]]
            else:
                timeList = self._t1AlertTimes

            minTime = result[2]-self._msecs
            for time in timeList:
                if time >= minTime and time < result[2]:
                    triggered.append(result)
                    break

        return list(set(triggered))


    ###########################################################
    def getVideoDebugLines(self):
        """Retrieve lines to be displayed for debugging video.

        @param  triggerLines  A list of TriggerLineSegment or TriggerRegion
                              objects, which can be used to retrieve a list of
                              (x1,y1,x2,y2) tuples defining lines to display on
                              the screen by calling their getPoints(coordSpace)
                              instance method.
        """
        return self._t1.getVideoDebugLines() + self._t2.getVideoDebugLines()


    ###########################################################
    def spatiallyAware(self):
        """Checks if this trigger uses spacial information for processing.

        @return  bool  True if this trigger uses, contains, or processes spacial
                       information needed for it to work properly. False
                       otherwise.
        """
        return self._t1.spatiallyAware() or self._t2.spatiallyAware()

