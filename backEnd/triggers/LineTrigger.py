#!/usr/bin/env python

#*****************************************************************************
#
# LineTrigger.py
#    Trigger: crossing a line
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


from BaseTrigger import BaseTrigger
from TriggerUtils import getBboxTrackingPoint, optimizedDidObjCrossLine, BBOX
from TriggerUtils import kTrackPointStrToInt, kDirectionStrToInt

# If an object disappears for > this long, we assume it's gone...
_kStaleObjMs = 5000


###############################################################
class LineTrigger(BaseTrigger):
    ###########################################################
    def __init__(self, dataMgr, segment, point='center'):
        """Initializer for the LineTrigger class

        @param  dataMgr  An interface to the stored motion data
        @param  segment  A TriggerLineSegment object.
        @param  point    The point in the bounding box to use for location
                         detection. Must be 'center', 'top', 'bottom', 'left'
                         or 'right'.
        """
        BaseTrigger.__init__(self)

        self._trigLineSegment = segment

        # Save the tracking location preference
        assert point in kTrackPointStrToInt.keys()
        self._point = point

        # Save the data manager
        self._dataMgr = dataMgr

        # For real-time, keep track of previous bboxes for various objects...
        # Key = objId
        # Value = (x1, y1, x2, y2, frame, time, objId)
        self._prevBboxMap = {}

        self._objBboxes = None

        [(x1, y1), (x2, y2)] = self._trigLineSegment.getPoints()
        self._cLine = BBOX(int(x1), int(y1), int(x2), int(y2))
        self._cDirection = kDirectionStrToInt[segment.getDirection()]
        self._cLocation = kTrackPointStrToInt[point]


    ###########################################################
    def __str__(self):
        """Create a string representation of the trigger

        @return strDesc  A string description of the trigger
        """
        return 'LineTrigger - from: %s, objectPt: %s, %s' % \
                (self._trigLineSegment.getDirection(), self._point, self._trigLineSegment.getLineSegment())


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
        [(x1, y1), (x2, y2)] = self._trigLineSegment.getPoints(coordSpace)
        self._cLine = BBOX(int(x1), int(y1), int(x2), int(y2))


    ###########################################################
    def getCoordinates(self):
        """Return coordinates defining the line segment

        @return  x1, y1, x2, y2  The coordinates defining the line segment
        """
        return self._trigLineSegment.getPoints()


    ###########################################################
    def setSearchData(self, objBboxes):
        """Set the data to be used during the next search.

        @param  objBboxes  The list returned by DataManager's
                           getObjectBboxesBetweenTimes function.
        """
        self._objBboxes = objBboxes


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
        triggered = []
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

        if not self._objBboxes:
            # Get a list of objects moving between the specified times
            objIds = self._dataMgr.getObjectsBetweenTimes(timeStart, timeStop)

            # Get a list of bounding boxes for the objects
            self._objBboxes = self._dataMgr.getObjectBboxesBetweenTimes(
                                                    objIds, timeStart, timeStop)

        # For realtime, we need to look at old state; for 'single', we just
        # start from scratch...
        if type == 'realtime':
            prevBoxMap = self._prevBboxMap

            # Delete stale objects from the prevBoxMap
            for (_, _, _, _, _, frameTime, objId) in prevBoxMap.values():
                if timeStart - frameTime > _kStaleObjMs:
                    del prevBoxMap[objId]
        else:
            prevBoxMap = {}

        # Walk through all boxes...
        for box in self._objBboxes:
            # Break this box out into its pieces, and get any previous box...
            (x1, y1, x2, y2, frame, frameTime, objId) = box
            prevBox = prevBoxMap.get(objId, None)
            prevBoxMap[objId] = box

            # Translate the bounding boxes to the desired coordinate points
            if prevBox is not None:
                prevBBOX = BBOX(prevBox[0], prevBox[1], prevBox[2], prevBox[3])
                curBBOX = BBOX(box[0], box[1], box[2], box[3])

                if (not uniqueProcSize) and (frameTime > timeToChangeCoordSpace):
                    for procWidth, procHeight, firstMs, lastMs in procSizesMsRange:
                        if frameTime >= firstMs and frameTime <= lastMs:
                            self.setProcessingCoordSpace((procWidth, procHeight))
                            timeToChangeCoordSpace = lastMs

                if optimizedDidObjCrossLine(prevBBOX, curBBOX, self._cLine,
                                            self._cLocation, self._cDirection):
                    triggered.append((objId, frame, frameTime))

        self._objBboxes = None

        return triggered


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataMgr  The new data manager
        """
        self._dataMgr = dataManager


    ###########################################################
    def getVideoDebugLines(self):
        """Retrieve lines to be displayed for debugging video.

        @param  triggerLines  A list of TriggerLineSegment or TriggerRegion
                              objects, which can be used to retrieve a list of
                              (x1,y1,x2,y2) tuples defining lines to display on
                              the screen by calling their getPoints(coordSpace)
                              instance method.
        """
        return [self._trigLineSegment]


    ###########################################################
    def spatiallyAware(self):
        """Checks if this trigger uses spacial information for processing.

        @return  bool  True if this trigger uses, contains, or processes spacial
                       information needed for it to work properly. False
                       otherwise.
        """
        return True


###############################################################
class _fakeLineSegment(object):
    """A class for findIntersection with lower overhead than LineSegment"""
    ###########################################################
    def __init__(self, x1, y1, x2, y2):
        """Initializer for _fakeLineSegment

        @param  x1, y1, x2, y2  Points defining the line segment
        """
        self._x1 = x1
        self._y1 = y1
        self._x2 = x2
        self._y2 = y2
