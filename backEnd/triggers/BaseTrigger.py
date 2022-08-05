#!/usr/bin/env python

#*****************************************************************************
#
# BaseTrigger.py
#     Base trigger class, common code for all triggers
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

###############################################################
class BaseTrigger(object):
    """
    Base class for creating alert triggers
    """
    ###########################################################
    def __init__(self):
        """Empty initializer for BaseTrigger class"""
        pass


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
        pass


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
        _ = timeStart
        _ = timeStop
        _ = type
        _ = procSizesMsRange
        return []


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
                                             (lastMs, lastFrame)), camLoc)
                                    ...
                                  ]
        """
        # This is a generic version that uses search().  It can be optimized
        # by child triggers as needed.

        # Get list sorted by objID, then frame number...
        # ...really, we just care about frame number, but I believe that search
        # will tend to naturally sort by objID first, so this should (?) be
        # faster...
        triggered = sorted(self.search(timeStart, timeStop, 'single', procSizesMsRange),
                           key=operator.itemgetter(0, 1))

        # The final results list.  Mostly, this will be filled in at the end
        # using resultsDict.items(), but we'll also fill some of it in early
        # if an item is discontiguous...
        resultList = []

        # A per-object ID map to the last frame number than an object triggered
        lastFramePerObj = {}

        # A per-object map to (minMs, maxMs) for the most recent sequence...
        resultDict = {}

        # Iterate through triggered, filling in resultList and resultDict...
        for objId, frameNum, ms in triggered:
            if objId not in lastFramePerObj:
                # First time we've seen this object.  It's the min and max...
                resultDict[objId] = ((ms, frameNum), (ms, frameNum))
            else:
                # Seen this object before; get old min and max...
                (oldMinMs, oldMinFrame), (oldMaxMs, oldMaxFrame) = \
                    resultDict[objId]

                # Check to see if this is contiguous to the last triggering
                # of this object id...
                if frameNum == lastFramePerObj[objId] + 1:
                    # It is!  ...just extend the range...
                    assert (oldMinMs < ms) and (ms > oldMaxMs), \
                           "List not sorted?"
                    resultDict[objId] = ((oldMinMs, oldMinFrame),
                                         (ms, frameNum))
                else:
                    # It's not!  ...add the old range straight to the dict, then
                    # start a new range...
                    resultList.append((objId, ((oldMinMs, oldMinFrame),
                                               (oldMaxMs, oldMaxFrame)), None))
                    resultDict[objId] = ((ms, frameNum), (ms, frameNum))

            # Need to keep track of the last time this object triggered...
            lastFramePerObj[objId] = frameNum

        # Extend with the end of each object's ranges...
        resultList.extend((item[0], item[1], None) for item in resultDict.iteritems())

        return resultList


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
        _ = objList
        _ = procSizesMsRange

        return []


    ###########################################################
    def reset(self):
        """Remove any continuation data from a trigger"""
        return


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataManager  The new data manager
        """
        return


    ###########################################################
    def getPlayTimeOffset(self):
        """Return the time in ms before trigger the video should start playing

        @return msOffset  The time in ms to 'rewind' before the first fire.
        @return preserve  True if clips should preserve msOffset if possible.
        """
        return 0, False


    ###########################################################
    def getClipLengthOffsets(self):
        """Return the times before and after the trigger to include in a clip

        @return  rewindMs  The time in ms to 'rewind' before the first fire
        @return  extendMs  The time in ms to 'extend' past the last fire
        """
        return 5000 + self.getPlayTimeOffset()[0], 10000


    ###########################################################
    def shouldCombineClips(self):
        """Determine whether overlapping clips should be combined.

        @return combine  True if overlaping clips should be combined.
        """
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
        return []


    ###########################################################
    def spatiallyAware(self):
        """Checks if this trigger uses spacial information for processing.

        @return  bool  True if this trigger uses, contains, or processes spacial
                       information needed for it to work properly. False
                       otherwise.
        """
        return False
