#!/usr/bin/env python

#*****************************************************************************
#
# DoorTrigger.py
#     Trigger: entering through door threshold
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



from BaseTrigger import BaseTrigger
from RegionTrigger import RegionTrigger

#import time


###############################################################
class DoorTrigger(BaseTrigger):
    ###########################################################
    def __init__(self, dataMgr, region, trackPoint='center',
                 fromDir='any'):
        """Initializer for the RegionTrigger class

        @param  dataMgr       An interface to the stored motion data
        @param  regionPoints  A list of points defining the perimeter verticies
                              of the region cw in the order they are connected
        @param  trackPoint    The point in the bounding box to use for location
                              detection. Must be 'center', 'top', 'bottom',
                              'left' or 'right'.
        @param  fromDir       The direction from which to trigger events.  Must
                              be 'any', 'entering' or 'exiting'
        """
        BaseTrigger.__init__(self)

        assert fromDir in ['any', 'entering', 'exiting']

        self._regionTrigger = RegionTrigger(dataMgr, region,
                                            trackPoint, 'outside')

        self._dir = fromDir
        self._seenObjects = set()

        # These are objects that were first seen within the bounds of the
        # door, but haven't been seen exiting the bounds of the door yet.
        # We need this for both entering _and_ exiting.  Entering because
        # we trigger entering when objects that appeared in the door
        # leave the bounds of the door.  Exiting because we don't want to
        # trigger on objects that appear within the bounds of the door, then
        # disappear (without leaving the door's bounds)--this is the "person
        # walking by a transparent door without coming through" case.
        self._doorOriginSet = set()

        self._dataMgr = dataMgr
        self._trackPoint = trackPoint
        self._regionPoints = region.getPoints()


    ###########################################################
    def __str__(self):
        """Create a string representation of the trigger

        @return strDesc  A string description of the trigger
        """
        return 'DoorTrigger - direction: %s, objectPt: %s, points %s' % \
               (self._dir, self._trackPoint, self._regionPoints)


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
        self._regionTrigger.setProcessingCoordSpace(coordSpace)


    ###########################################################
    def getCoordinates(self):
        """Return coordinates defining the door

        @return  regionCoords  a list of x,y pairs
        """
        return self._regionTrigger.getCoordinates()


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
        assert type in ['single', 'realtime']

        isEnteringTrigger = (self._dir == 'any' or self._dir == 'entering')

        triggered = []
        uniqueProcSize = True
        timeToChangeCoordSpace = 0

        if procSizesMsRange:
            if len(procSizesMsRange) == 1:
                [(procWidth, procHeight, _, _)] = procSizesMsRange
                self._regionTrigger.setProcessingCoordSpace((procWidth, procHeight))
            else:
                uniqueProcSize = False
                (procWidth, procHeight, _, lastMs) = procSizesMsRange[0]
                self._regionTrigger.setProcessingCoordSpace((procWidth, procHeight))
                timeToChangeCoordSpace = lastMs

        # Track the most recent search stop time
        self._timeStop = timeStop

        if type == 'single':
            # Reset the state dict
            self.reset()

        # Track the id of any objects that originate in the door region during
        # this search period.
        activeObjects = self._dataMgr.getObjectsBetweenTimes(timeStart,
                                                             timeStop)

        # Finalize any objects that aren't around anymore.  TODO: Handle objects that disappear and reappear?
        oldObjs = self._seenObjects.difference(activeObjects)
        triggered = self.finalize(oldObjs, procSizesMsRange)

        # Add new objects that showed up within the bounds of the door.
        for objId in activeObjects:
            if objId not in self._seenObjects:
                self._seenObjects.add(objId)

                bbox, frame, objTime = \
                    self._dataMgr.getFirstObjectBbox(objId)
                if objTime == -1 or objTime < timeStart:
                    continue

                if (not uniqueProcSize) and (objTime > timeToChangeCoordSpace):
                    for procWidth, procHeight, firstMs, lastMs in procSizesMsRange:
                        if objTime >= firstMs and objTime <= lastMs:
                            self._regionTrigger.setProcessingCoordSpace((procWidth, procHeight))
                            timeToChangeCoordSpace = lastMs

                if self._regionTrigger.optimizedIsPointInside(*bbox):
                    self._doorOriginSet.add(objId)

        # Perform a region search on the door boundary to see what objects
        # may have left the boundary of the door...
        if self._doorOriginSet:
            results = self._regionTrigger.search(timeStart, timeStop, 'single',
                                                 procSizesMsRange, self._doorOriginSet)

            # Technically, we should sort the results here, which would make
            # things more predictable.  ...but I don't bother, since I know that
            # the region trigger "outside" search will give us things in order.
            # results.sort()

            # For each object that left the boundary of the door, remove
            # from the door orgin set.  Also trigger if this is an entering
            # trigger.  SIDE NOTE: A given objId can be in the results more than
            # once, which is why we need the 'if' below...
            for result in results:
                objId = result[0]

                if objId in self._doorOriginSet:
                    if isEnteringTrigger:
                        # If an object moved into the scene from the region
                        # trigger an 'enter' alert
                        triggered.append((objId, result[1], result[2]))
                    self._doorOriginSet.remove(objId)

        # If this is a stand-alone search, finalize
        if type == 'single':
            triggered.extend(self.finalize(activeObjects, procSizesMsRange))

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
        triggered = []
        uniqueProcSize = True
        timeToChangeCoordSpace = 0

        if procSizesMsRange:
            if len(procSizesMsRange) == 1:
                [(procWidth, procHeight, _, _)] = procSizesMsRange
                self._regionTrigger.setProcessingCoordSpace((procWidth, procHeight))
            else:
                uniqueProcSize = False
                (procWidth, procHeight, _, lastMs) = procSizesMsRange[0]
                self._regionTrigger.setProcessingCoordSpace((procWidth, procHeight))
                timeToChangeCoordSpace = lastMs

        if self._dir == 'any' or self._dir == 'exiting':
            # Remove all 'finalized' objects from our tracking list...
            self._seenObjects.difference_update(objList)

            # For objects that were in the room at any time, if their
            # final location is in the door region count it as an exit.
            for objId in objList:
                # We only want to trigger on objects that actually left the
                # doorway at some point in time.  This handles the "transparent
                # door and someone walking by without coming through" case.
                if objId not in self._doorOriginSet:
                    # Get objects final time and location
                    frame, objEndTime = self._dataMgr.getObjectFinalTime(objId)
                    bbox = self._dataMgr.getBboxAtFrame(objId, frame)
                    if not bbox:
                        continue

                    if (not uniqueProcSize) and (objEndTime > timeToChangeCoordSpace):
                        for procWidth, procHeight, firstMs, lastMs in procSizesMsRange:
                            if objEndTime >= firstMs and objEndTime <= lastMs:
                                self._regionTrigger.setProcessingCoordSpace((procWidth, procHeight))
                                timeToChangeCoordSpace = lastMs

                    # Check if it was inside the region and time constraints
                    if self._regionTrigger.optimizedIsPointInside(*bbox) and \
                       (self._timeStop == None or objEndTime <= self._timeStop):
                        triggered.append((objId, frame, objEndTime))
                else:
                    # Don't need to keep track of this anymore.  It's gone.
                    self._doorOriginSet.remove(objId)

        return triggered


    ###########################################################
    def reset(self):
        """Remove any continuation data from a trigger"""
        self._seenObjects = set()
        self._doorOriginSet = set()

        self._regionTrigger.reset()


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataManager  The new data manager
        """
        self._dataMgr = dataManager
        self._regionTrigger.setDataManager(dataManager)


    ###########################################################
    def getPlayTimeOffset(self):
        """Return the time in ms before trigger the video should start playing

        @return msOffset  The time in ms to 'rewind' before the first fire.
        @return preserve  True if clips should preserve msOffset if possible.
        """
        return 3000, False


    ###########################################################
    def getVideoDebugLines(self):
        """Retrieve lines to be displayed for debugging video.

        @param  triggerLines  A list of TriggerLineSegment or TriggerRegion
                              objects, which can be used to retrieve a list of
                              (x1,y1,x2,y2) tuples defining lines to display on
                              the screen by calling their getPoints(coordSpace)
                              instance method.
        """
        return self._regionTrigger.getVideoDebugLines()


    ###########################################################
    def spatiallyAware(self):
        """Checks if this trigger uses spacial information for processing.

        @return  bool  True if this trigger uses, contains, or processes spacial
                       information needed for it to work properly. False
                       otherwise.
        """
        return True
