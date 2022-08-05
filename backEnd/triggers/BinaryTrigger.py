#!/usr/bin/env python

#*****************************************************************************
#
# BinaryTrigger.py
#      Trigger: logical AND or OR on multiple triggers
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



from copy import deepcopy

from BaseTrigger import BaseTrigger


###############################################################
class BinaryTrigger(BaseTrigger):
    """A trigger that fires on a binary operation of it's children triggers"""
    ###########################################################
    def __init__(self, type='and', childTriggers=None,
                 sameObject=False, diffObject=False):
        """Initializer for the BinaryTrigger class

        @param  type           The type of binary operation to perform on the
                               child triggers.  Must be either 'and' or 'or'
        @param  childTriggers  A list of child triggers to monitor
        """
        BaseTrigger.__init__(self)

        assert type in ['and', 'or']
        self._type = type

        # Can't find cases where the objects are the same but also different...
        assert not (sameObject and diffObject)
        self._sameObject = sameObject
        self._diffObject = diffObject

        self._childTriggers = []
        if childTriggers:
            self._childTriggers.extend(childTriggers)

        self._msOffset = 0
        self._preservePlayOffset = False
        for trigger in childTriggers:
            msOffset, preserve = trigger.getPlayTimeOffset()
            self._msOffset = max(self._msOffset, msOffset)
            self._preservePlayOffset = self._preservePlayOffset or preserve


    ###########################################################
    def __str__(self):
        """Create a string representation of the trigger

        @return strDesc  A string description of the trigger
        """
        if self._type == 'and':
            strDesc = 'AND Trigger - '
            if self._sameObject:
                strDesc += 'Same object required\n['
            elif self._diffObject:
                strDesc += 'Different objects required\n['
            else:
                strDesc += 'Any object combination\n['
        else:
            strDesc = 'OR Trigger - \n['

        for trigger in self._childTriggers:
            strDesc += '\n%s' % str(trigger)

        strDesc += '\n]'

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
        for trigger in self._childTriggers:
            trigger.setProcessingCoordSpace(coordSpace)


    ###########################################################
    def addChildTrigger(self, child):
        """Add another child trigger to the AND operation

        @param  child  The trigger to add
        """
        self._childTriggers.append(child)


    ###########################################################
    def clearChildTriggers(self):
        """Remove all current child triggers"""
        self._childTriggers = []


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
        if not self._childTriggers:
            return []

        # Collect the results for each of the child triggers
        triggerResults = []
        for trigger in self._childTriggers:
            triggerResults.append(trigger.search(timeStart, timeStop, type, procSizesMsRange))

        # Search for 'AND' joins on each child triggers
        if self._type == 'and':
            return self._doAndSearch(triggerResults)

        # Search for 'OR' joins of each child trigger
        elif self._type == 'or':
            return self._doOrSearch(triggerResults)


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
        triggerResults = []

        # Get the finalize results for each of the child triggers
        for trigger in self._childTriggers:
            triggerResults.append(trigger.finalize(objList, procSizesMsRange))

        if self._type == 'and':
            return self._doAndSearch(triggerResults)
        elif self._type == 'or':
            return self._doOrSearch(triggerResults)


    ###########################################################
    def reset(self):
        """Remove any continuation data from a trigger"""
        for trigger in self._childTriggers:
            trigger.reset()


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataManager  The new data manager
        """
        for child in self._childTriggers:
            child.setDataManager(dataManager)


    ###########################################################
    def _doAndSearch(self, triggerResults):
        """Perform an 'AND' operation on the given trigger results

        @param  triggerResults  A list of lists of trigger search outputs,
                                one result list for each trigger
        @return triggered       A list of dbId, frame, time tuples for objects
                                that set off the trigger
        """
        triggered = set()

        if self._sameObject:
            # If we're looking for the same object in each alert, we can
            # simply do an intersection
            triggered = set(triggerResults[0])
            for i in range(1, len(triggerResults)):
                triggered = triggered.intersection(set(triggerResults[i]))
            return list(triggered)

        else:
            # Build a list of time points shared between the alert lists
            frames = set([result[1] for result in triggerResults[0]])
            for i in range(1, len(triggerResults)):
                frames = frames.intersection(set(
                        [result[1] for result in triggerResults[i]]))

            # Different objects required for each trigger
            if self._diffObject:
                # For each alert list, create a list of objects active at
                # given timepoints.  Then add each of these to a set
                # tracking possibilities for active objects at each alert.
                # In the end sets that have the length of the number of
                # triggers are valid combinations of trigger AND trigger
                # AND trigger ... where the object in each was different.
                setDict = {}
                blankDict = {}
                for frame in frames:
                    setDict[frame] = [set()]
                    blankDict[frame] = []

                for resultList in triggerResults:
                    resultDict = deepcopy(blankDict)
                    for result in resultList:
                        if result[1] in resultDict:
                            resultDict[result[1]].append(result)

                    for frame, values in resultDict.iteritems():
                        existingSets = setDict[frame]
                        setDict[frame] = []
                        for alert in values:
                            for alertSet in existingSets:
                                newSet = alertSet.copy()
                                newSet.add(alert)
                                setDict[frame].append(newSet)

                for setList in setDict.itervalues():
                    for frameSet in setList:
                        if len(frameSet) == len(triggerResults):
                            triggered = triggered.union(frameSet)

            # Don't care if same or different objects
            else:
                # Iterate through each alert, saving objects that match the
                # given frames
                for resultList in triggerResults:
                    for result in resultList:
                        if result[1] in frames:
                            triggered.add(result)

        return list(triggered)


    ###########################################################
    def _doOrSearch(self, triggerResults):
        """Perform an 'OR' operation on the given trigger results

        @param  triggerResults  A list of lists of trigger search outputs,
                                one result list for each trigger
        @return triggered       A list of dbId, frame, time tuples for objects
                                that set off the trigger
        """
        triggered = set()

        for i in range(0, len(triggerResults)):
            triggered = triggered.union(set(triggerResults[i]))

        return list(triggered)


    ###########################################################
    def getPlayTimeOffset(self):
        """Return the time in ms before trigger the video should start playing

        @return msOffset  The time in ms to 'rewind' before the first fire.
        @return preserve  True if clips should preserve msOffset if possible.
        """
        return self._msOffset, self._preservePlayOffset


    ###########################################################
    def getVideoDebugLines(self):
        """Retrieve lines to be displayed for debugging video.

        @param  triggerLines  A list of TriggerLineSegment or TriggerRegion
                              objects, which can be used to retrieve a list of
                              (x1,y1,x2,y2) tuples defining lines to display on
                              the screen by calling their getPoints(coordSpace)
                              instance method.
        """
        lines = []
        for trigger in self._childTriggers:
            lines.extend(trigger.getVideoDebugLines())
        return lines


    ###########################################################
    def spatiallyAware(self):
        """Checks if this trigger uses spacial information for processing.

        @return  bool  True if this trigger uses, contains, or processes spacial
                       information needed for it to work properly. False
                       otherwise.
        """
        for trigger in self._childTriggers:
            if trigger.spatiallyAware():
                return True

        return False
