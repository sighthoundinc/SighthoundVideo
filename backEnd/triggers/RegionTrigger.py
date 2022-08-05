#!/usr/bin/env python

#*****************************************************************************
#
# RegionTrigger.py
#    Trigger: region containment
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
from LineTrigger import LineTrigger
from TriggerLineSegment import TriggerLineSegment
from TriggerUtils import kTrackPointStrToInt, optimizedIsPointInside, BBOX
from vitaToolbox.math.LineSegment import LineSegment


_kInfinity = 10000


###############################################################
class RegionTrigger(BaseTrigger):
    ###########################################################
    def __init__(self, dataMgr, region, trackPoint='center',
                 alertType='crosses'):
        """Initializer for the LineTrigger class

        @param  dataMgr       An interface to the stored motion data
        @param  region        A list of points defining the perimeter verticies
                              of the region cw in the order they are connected
        @param  trackPoint    The point in the bounding box to use for location
                              detection. Must be 'center', 'top', 'bottom',
                              'left' or 'right'.
        @param  alertType     The condition to monitor for.
                              'entering'- fires when an object enters the region
                              'exiting'- fires when an object exits a region
                              'crosses'- includes both 'entering' and 'exiting'
                              'inside'- fires when an object is in the region
                              'outside'- fires when an obj is outside the region
        """
        BaseTrigger.__init__(self)

        # TODO: Do we need to check that points were given in cw order?
        #       For now just trusting the caller.
        self._region = region
        self._dataMgr = dataMgr
        self._lastTime = -1

        # Save the tracking location preference
        assert trackPoint in kTrackPointStrToInt
        self._trackPoint = trackPoint

        # Save the tracking direction
        assert alertType in ['entering', 'exiting', 'crosses', 'inside',
                             'outside']
        self._type = alertType

        segDir = 'any'
        if alertType == 'entering':
            segDir = 'right'
        if alertType == 'exiting':
            segDir = 'left'

        # Create line triggers and segments from points
        self._triggerLineSegments = []
        self._lineTriggerList = []
        self._regionSegments = []

        regionPoints = self._region.getPoints()

        coordSpace = region.getCoordSpace()
        numPts = len(regionPoints)
        for i in range(0, numPts):
            x1, y1 = regionPoints[i]
            x2, y2 = regionPoints[(i+1)%numPts]

            triggerLineSegment = TriggerLineSegment(
                LineSegment(x1, y1, x2, y2), segDir, coordSpace
            )

            self._triggerLineSegments.append(triggerLineSegment)

            self._lineTriggerList.append(
                LineTrigger(dataMgr, triggerLineSegment, trackPoint)
            )

            self._regionSegments.append(LineSegment(x1, y1, x2, y2))

        # Create a list of the segments suitable for giving to C.
        boxList = []
        numSegments = len(self._regionSegments)
        for i in range(0, numSegments):
            x1, y1= regionPoints[i]
            x2, y2 = regionPoints[(i+1) % numSegments]
            boxList.append((x1, y1, x2, y2))

        self._cSegments = (BBOX * numSegments)(*boxList)
        self._cTrackLocation = kTrackPointStrToInt[trackPoint]


    ###########################################################
    def __str__(self):
        """Create a string representation of the trigger

        @return strDesc  A string description of the trigger
        """
        return 'RegionTrigger - type: %s, objectPt: %s, points %s' % \
               (self._type, self._trackPoint, self._region.getPoints())


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
        self._regionSegments = [
            tLineSeg.getLineSegment(coordSpace)
            for tLineSeg in self._triggerLineSegments
        ]

        # Create a list of the segments suitable for giving to C.
        boxList = []
        numSegments = len(self._regionSegments)
        regionPoints = self._region.getPoints(coordSpace)
        for i in range(0, numSegments):
            x1, y1= regionPoints[i]
            x2, y2 = regionPoints[(i+1) % numSegments]
            boxList.append((x1, y1, x2, y2))

        self._cSegments = (BBOX * numSegments)(*boxList)
        self._cTrackLocation = kTrackPointStrToInt[self._trackPoint]


    ###########################################################
    def getCoordinates(self):
        """Return coordinates defining the region

        @return  regionCoords  a list of x,y pairs
        """
        return self._region.getPoints()


    ###########################################################
    def optimizedIsPointInside(self, x1, y1, x2, y2):
        """Does the work of getBboxTrackingPoint and isPoint inside in C.

        @param  x1, y1, x2, y2  The bounding box defining the object.
        @return isInside        True if the point is inside the region.
        """
        objBbox = BBOX(x1, y1, x2, y2)
        return optimizedIsPointInside(objBbox, self._cTrackLocation,
                                      self._cSegments,
                                      len(self._regionSegments))



    ###########################################################
    def search(self, timeStart=None, timeStop=None, type='single', procSizesMsRange=None,
               objIdFilter=None):
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
        triggered = []

        if self._type in ['entering', 'exiting', 'crosses']:
            # If we're looking for boundary crossings, we can simply return the
            # combined results of searches on our child triggers
            objs = self._dataMgr.getObjectsBetweenTimes(timeStart, timeStop)
            if objIdFilter is not None:
                objs = objIdFilter.intersection(objs)
            bboxes = self._dataMgr.getObjectBboxesBetweenTimes(objs, timeStart,
                                                               timeStop)

            for trigger in self._lineTriggerList:
                trigger.setSearchData(bboxes)
                results = trigger.search(timeStart, timeStop, type, procSizesMsRange)
                triggered.extend(results)

            # NOTES:
            # - Because of the way that the above works, we can actually get
            #   duplicate entries if something crosses right at the border of
            #   two lines.  We could fix this by transforming to a set and then
            #   back to a list, but it doesn't seem super important
            # - The above won't produce sorted results, since we process each
            #   trigger one at a time.
            # ...if we wanted to "fix" the above two things, we could do this:
            #triggered = sorted(set(triggered))

        else:
            maxTime = -1
            uniqueProcSize = True
            timeToChangeCoordSpace = 0

            if procSizesMsRange:
                if len(procSizesMsRange) == 1:
                    [(procWidth, procHeight, _, _)] = procSizesMsRange
                    self.setProcessingCoordSpace((procWidth, procHeight))
                else:
                    uniqueProcSize = False
                    (procWidth, procHeight, _, lastMs) = procSizesMsRange[0]
                    self.setProcessingCoordSpace((procWidth, procHeight))
                    timeToChangeCoordSpace = lastMs

            objIds = self._dataMgr.getObjectsBetweenTimes(timeStart, timeStop)
            if objIdFilter is not None:
                objIds = objIdFilter.intersection(objIds)

            # Get a list of bounding boxes for the current object
            bboxes = self._dataMgr.getObjectBboxesBetweenTimes(objIds,
                                                               timeStart,
                                                               timeStop)

            for x1, y1, x2, y2, frame, time, objId in bboxes:

                if (not uniqueProcSize) and (time > timeToChangeCoordSpace):
                    for procWidth, procHeight, firstMs, lastMs in procSizesMsRange:
                        if time >= firstMs and time <= lastMs:
                            self.setProcessingCoordSpace((procWidth, procHeight))
                            timeToChangeCoordSpace = lastMs

                if type == 'realtime':
                    # Since this mode of the trigger only requires a single
                    # frame we want to ensure that we don't return an alert
                    # for anything we did in the previous call
                    maxTime = max(maxTime, time)
                    if time <= self._lastTime:
                        continue

                # For each bounding box, determine whether the object was
                # inside or outside the region, alerting as necessary
                isInside = self.optimizedIsPointInside(x1, y1, x2, y2)

                if (isInside and self._type == 'inside') or \
                   (not isInside and self._type == 'outside'):
                    triggered.append((objId, frame, time))

            self._lastTime = maxTime

        return triggered


    ################################################
    def reset(self):
        """Remove any continuation data from a trigger"""
        self._lastTime = -1

        for trigger in self._lineTriggerList:
            trigger.reset()


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataManager  The new data manager
        """
        self._dataMgr = dataManager
        for trigger in self._lineTriggerList:
            trigger.setDataManager(dataManager)


    ###########################################################
    def shouldCombineClips(self):
        """Determine whether overlapping clips should be combined.

        @return combine  True if overlaping clips should be combined.
        """
        if self._type in ['inside', 'outside']:
            return True

        return False


    ###########################################################
    def getVideoDebugLines(self):
        """Retrieve lines to be displayed for debugging video.

        @param  triggerLines  A list of TriggerLineSegment or TriggerRegion
                              objects, which can be used to retrieve a list of
                              (x1,y1,x2,y2) tuples defining lines to display on
                              the screen by calling their getPoints(coordSpace)
                              instance method.
        """
        return [self._region]


    ###########################################################
    def spatiallyAware(self):
        """Checks if this trigger uses spacial information for processing.

        @return  bool  True if this trigger uses, contains, or processes spacial
                       information needed for it to work properly. False
                       otherwise.
        """
        return True
