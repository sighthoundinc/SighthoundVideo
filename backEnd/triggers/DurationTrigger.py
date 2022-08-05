#!/usr/bin/env python

#*****************************************************************************
#
# DurationTrigger.py
#     Trigger: duration-based (exclude objects if visible for less than specified time)
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



import operator

from BaseTrigger import BaseTrigger


###############################################################
class DurationTrigger(BaseTrigger):
    """A trigger that fires when another trigger remains active over time"""
    ###########################################################
    def __init__(self, childTrigger, msecs, moreThan=True):
        """Initializer for the DurationTrigger class

        @param  childTrigger  The trigger to monitor
        @param  msecs         The duration boundary in msecs
        @param  moreThan      If True will alert when childTrigger has been
                              active longer duration.  If False, will fire while
                              childTrigger has been active less than duration.
        """
        BaseTrigger.__init__(self)

        self._childTrigger = childTrigger
        self._msecs = msecs
        self._moreThan = moreThan

        self._playOffset = 0
        if self._moreThan:
            self._playOffset = msecs

        # A dictionary of objectId to (first seen time, last frame seen)
        self._activeObjects = {}


    ###########################################################
    def __str__(self):
        """Create a string representation of the trigger

        @return strDesc  A string description of the trigger
        """
        strDesc = 'Duration Trigger - Fires when [%s] is active for ' % str(
                                                            self._childTrigger)
        if self._moreThan:
            strDesc += 'more than'
        else:
            strDesc += 'less than'
        strDesc += ' %.3f seconds.' % (self._msecs/1000.)

        return strDesc


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
        self._childTrigger.setProcessingCoordSpace(coordSpace)


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
        if type == 'single':
            # Reset the state dict
            self.reset()

        return self._doSearch(self._childTrigger.search(timeStart, timeStop,
                                                        type, procSizesMsRange))

        # TODO: Need to call finalize()?  It shouldn't be needed for duration
        # triggers, since we can't ever trigger unless we actually got more
        # data...


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
        # TODO: Since we finalize ourselves in search(), isn't child in charge
        # of finalizing itself?
        return self._doSearch(
            self._childTrigger.finalize(objList, procSizesMsRange),
            True
        )


    ###########################################################
    def reset(self):
        """Remove any continuation data from a trigger"""
        self._activeObjects = {}

        # TODO: Since we reset ourselves in search(), isn't child in charge of
        # resetting itself?
        self._childTrigger.reset()


    ###########################################################
    def _doSearch(self, triggerResults, isFinalize=False):
        """Update the active objects and trigger if conditions are met

        @param  triggerResults  The results of a search on the child trigger
        @param  isFinalize      True if this is being called from finalize()
        @return triggered       A list of dbId, frame, time tuples for objects
                                that set off the trigger
        """
        triggered = []

        # We need the results to be sorted by time which they likely won't be
        triggerResults.sort(key=operator.itemgetter(2))

        prevActive = set(self._activeObjects.iterkeys())
        curActive = set()

        for result in triggerResults:
            # Add this objId to the currently active list
            curActive.add(result[0])

            if result[0] in self._activeObjects:
                # Ensure we don't count skipped frames
                firstTime, lastFrame = self._activeObjects[result[0]]
                if lastFrame < result[1]-1:
                    firstTime = result[2]
                self._activeObjects[result[0]] = (firstTime, result[1])

                # Calc the duration of this trigger
                diff = result[2] - firstTime

                if self._moreThan:
                    if diff > self._msecs:
                        triggered.append(result)
                elif diff < self._msecs:
                    triggered.append(result)
            else:
                # New object, add it to the dictionary
                self._activeObjects[result[0]] = (result[2], result[1])

                if not self._moreThan:
                    # If this is the first time we've seen this object trigger
                    # it's been happening for less than any possible duration
                    triggered.append(result)

        # Remove objects no longer triggering from our active list
        if not isFinalize:
            expired = prevActive.difference(curActive)
            for objId in expired:
                del self._activeObjects[objId]

        return triggered


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataManager  The new data manager
        """
        self._childTrigger.setDataManager(dataManager)


    ###########################################################
    def getPlayTimeOffset(self):
        """Return the time in ms before trigger the video should start playing

        @return msOffset  The time in ms to 'rewind' before the first fire.
        @return preserve  True if clips should preserve msOffset if possible.
        """
        return self._playOffset, True


    ###########################################################
    def shouldCombineClips(self):
        """Determine whether overlapping clips should be combined.

        @return combine  True if overlaping clips should be combined.
        """
        return self._childTrigger.shouldCombineClips()


    ###########################################################
    def getVideoDebugLines(self):
        """Retrieve lines to be displayed for debugging video.

        @param  triggerLines  A list of TriggerLineSegment or TriggerRegion
                              objects, which can be used to retrieve a list of
                              (x1,y1,x2,y2) tuples defining lines to display on
                              the screen by calling their getPoints(coordSpace)
                              instance method.
        """
        return self._childTrigger.getVideoDebugLines()


    ###########################################################
    def spatiallyAware(self):
        """Checks if this trigger uses spacial information for processing.

        @return  bool  True if this trigger uses, contains, or processes spacial
                       information needed for it to work properly. False
                       otherwise.
        """
        return self._childTrigger.spatiallyAware()
