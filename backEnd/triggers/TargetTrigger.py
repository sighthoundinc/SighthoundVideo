#!/usr/bin/env python

#*****************************************************************************
#
# TargetTrigger.py
#    Trigger: based on object type
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
import operator

# Common 3rd-party imports...

# Toolbox imports...

# Local imports...
from BaseTrigger import BaseTrigger
from appCommon.CommonStrings import kSearchViewDefaultRules

###############################################################
class TargetTrigger(BaseTrigger):
    ###########################################################
    def __init__(self, dataMgr, typeList, childTrigger=None):
        """Initializer for the TargetTrigger class.

        @param  dataMgr       The DataManager instance.
        @param  typeList      A list of types/actions.  We will trigger on
                              any of these.  Looks like: [
                                ('person', 'walking'),
                                ('person', 'running'),
                                ('vehicle', 'any'),
                                ...
                              ]
        @param  childTrigger  The child trigger that we're modifying.
        """
        BaseTrigger.__init__(self)

        self._dataMgr = dataMgr
        self._typeList = typeList
        self._childTrigger = childTrigger


    ###########################################################
    def __str__(self):
        """Create a string representation of the trigger

        @return strDesc  A string description of the trigger
        """
        # Combine the target names with actions...
        targetsWithActions = []
        for targetName, action in self._typeList:
            if action == 'any':
                targetsWithActions.append(targetName)
            else:
                targetsWithActions.append("%s %s" % (targetName, action))

        strDesc = 'TargetTrigger - ' + ' or '.join(targetsWithActions)
        if self._childTrigger:
            strDesc += ' doing ' + str(self._childTrigger)
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
        if self._childTrigger:
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
        _ = type
        triggered = []

        # Set the database filter for the desired target types...
        self._dataMgr.setTargetFilter(self._typeList, timeStart, timeStop)

        # If we have a child trigger return the result of it's search on the
        # filtered database
        if self._childTrigger:
            triggered = self._childTrigger.search(timeStart, timeStop, type, procSizesMsRange)

        else:
            objIds = self._dataMgr.getObjectsBetweenTimes(timeStart, timeStop)
            bboxes = self._dataMgr.getObjectBboxesBetweenTimes(
                                                    objIds, timeStart, timeStop)
            triggered = map(operator.itemgetter(6, 4, 5), bboxes)

        # Remove the database filter
        self._dataMgr.setTargetFilter(None)

        return triggered


    ###########################################################
    def searchForRanges(self, timeStart=None, timeStop=None, procSizesMsRange=None):
        """Search the database for objects tripping the trigger

        @param  timeStart         The time to start searching from, None for all time
        @param  timeStop          The time to stop searching at, None for present
        @param  procSizesMsRange  A list of sizes the camera was processed at for
                                  certain ranges of time. Contains a list of 4-tuples
                                  of (procWidth, procHeight, firstMs, lastMs).
                                  Note: if the list contains only one 4-tuple, then
                                  procWidth and procHeight is unique, and firstMs and
                                  lastMs should be ignored; they may hold None values.
                                  If the list contains more than one 4-tuple, then
                                  procWidth and procHeight are not unique, and you must
                                  use the firstMs and lastMs to determine which
                                  procSize was used for a specified period of time.
        @return resultItems       A iterable of tuples, like this: [
                                    (objId, ((firstMs, firstFrame),
                                             (lastMs, lastFrame)))
                                    ...
                                  ]
        """
        # Set the database filter for the desired target types...
        self._dataMgr.setTargetFilter(self._typeList, timeStart, timeStop)

        # If we have a child trigger return the result of it's search on the
        # filtered database
        if self._childTrigger:
            resultItems = self._childTrigger.searchForRanges(timeStart, timeStop, procSizesMsRange)
        else:
            resultItems = self._dataMgr.getObjectRangesBetweenTimes(
                timeStart, timeStop
            )

        # Remove the database filter
        self._dataMgr.setTargetFilter(None)

        # Uncomment to test against generic version...
        # ...note that this might actually fail if an object disappears for
        # a few frames.  In that case, the generic trigger will make two ranges
        # for the object and we'll do just one.  I think that's fine, since
        # objects would only ever disappear for a small number of frames and we
        # can just pretend that doesn't happen...
        #assert super(TargetTrigger, self).searchForRanges(timeStart, timeStop) == resultDict

        return resultItems


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
        if self._childTrigger:
            return self._childTrigger.finalize(objList, procSizesMsRange)

        return []


    ###########################################################
    def reset(self):
        """Remove any continuation data from a trigger"""
        if self._childTrigger:
            self._childTrigger.reset()


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataMgr  The new data manager
        """
        self._dataMgr = dataManager
        if self._childTrigger:
            self._childTrigger.setDataManager(dataManager)


    ###########################################################
    def getPlayTimeOffset(self):
        """Return the time in ms before trigger the video should start playing

        @return msOffset  The time in ms to 'rewind' before the first fire.
        @return preserve  True if clips should preserve msOffset if possible.
        """
        if self._childTrigger:
            return self._childTrigger.getPlayTimeOffset()
        return 0, False


    ###########################################################
    def shouldCombineClips(self):
        """Determine whether overlapping clips should be combined.

        @return combine  True if overlaping clips should be combined.
        """
        if self._childTrigger:
            return self._childTrigger.shouldCombineClips()
        return True


    ###########################################################
    def getVideoDebugLines(self):
        """Retrieve lines to be displayed for debugging video.

        @param  triggerLines  A list of TriggerLineSegment or TriggerRegion
                              objects, which can be used to retrieve a list of
                              (x1,y1,x2,y2) tuples defining lines to display on
                              the screen by calling their getPoints(coordSpace)
                              instance method.
        """
        if self._childTrigger:
            return self._childTrigger.getVideoDebugLines()
        return []


    ###########################################################
    def spatiallyAware(self):
        """Checks if this trigger uses spacial information for processing.

        @return  bool  True if this trigger uses, contains, or processes spacial
                       information needed for it to work properly. False
                       otherwise.
        """
        if self._childTrigger:
            return self._childTrigger.spatiallyAware()

        return False

################################################################################
def getQueryForDefaultRule(dataMgr, ruleName):
    """ Returns a standard query for a predefined rule name, or None otherwise
    """
    result = None
    isDefaultRule = ruleName in kSearchViewDefaultRules
    if isDefaultRule:
        objectType = []
        if ruleName == 'People':
            objectType = [('person', 'any')]
        elif ruleName == 'Vehicles':
            objectType = [('vehicle', 'any')]
        elif ruleName == 'Animals':
            objectType = [('animal', 'any')]
        elif ruleName == 'Unknown objects':
            objectType = [('object', 'any')]
        result = TargetTrigger(dataMgr, objectType)
    return result
