#! /usr/local/bin/python

#*****************************************************************************
#
# SearchUtils.py
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


"""
## @file
Contains search utilities for Arden AI.
"""

# Python imports...
import bisect
from collections import defaultdict
import datetime
import operator
import time
import sys

from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8
from vitaToolbox.sysUtils.TimeUtils import getDebugTime

def OB_ASID(a): return a

# Import numpy if it is available. It's here to support the
# 'parseSearchResultsLegacy' function. It should be used for testing purposes
# ONLY. It is also NOT an error if numpy cannot be loaded - this just means
# we are not on a machine that is testing / cares about legacy function.
try:
    import numpy
except:
    pass

# Constants...
_kSearchSlopMs  = 1000 * 60 * 5         # Search includes +/- this amount...

# For clips that should be combined the frame gap that is allowable between
# objects.  This is the number of blank frames between objects +1, allowing
# object A stopping at frame 10 to be combined with object B starting at frame
# 11 is tolerance 1, allowing one blank frame between them is tolerance 2...
kFrameTolerance = 3

# When we check frame tolerance, we also throw in a check to make sure that the
# millisecond times are close.  This is important because frame numbers reset
# themselves whenever the pipeline resets.  ...so if we're getting constant
# pipeline resets, we could get into trouble if we don't check the ms too.
_kMsTolerance = 3000


##############################################################################
class SearchConfig(object):
    def __init__(self):
        """
        The list of (updateTime, mergeThreshold) applicable to the duration of the current
        query.
        """
        self._mergeThresholdsForQuery = None

    def disableClipMerging(self):
        self._mergeThresholdsForQuery = [ (0, 0) ]

    def setMergeThresholdsForQuery(self, value, override=False):
        if self._mergeThresholdsForQuery is not None and not override:
            return
        self._mergeThresholdsForQuery = value

    def getMergeThresholdsForQuery(self):
        return self._mergeThresholdsForQuery

##############################################################################
def parseSearchResults(resultsList, shouldCombineClips):
    """Prepare search results to be sent to a

    @param  resultsList         The list of results.  Looks like a list of
                                (objId, objFrame, objTime) tuples.  MUST BE
                                SORTED, at least if shouldCombineClips!
    @param  shouldCombineClips  If True, we should combine adjacent results.
    @return rangeDict           Key = objId,
                                Value = list of (startFrame, startMs,
                                                 endFrame, endMs)
    """
    # Handle the non-combine case right away, which is really simple...
    if not shouldCombineClips:
        rangeDict = defaultdict(list)
        for objId, objFrame, objTime in resultsList:
            rangeDict[objId].append( ((objFrame, objTime),
                                      (objFrame, objTime)) )
        return rangeDict

    # Based on RecognitionObject's _getRangeStr()

    # Create a result dictionary for storing each object's results and a
    # range dict to store the return data
    resultDict = defaultdict(list)
    rangeDict = defaultdict(list)

    # Split the results by object id
    for (objId, frame, time) in resultsList:
        resultDict[objId].append((frame, time))

    for objId in resultDict:
        # This is a list of 2-tuples:
        #   [(frame1, time1), (frame2, time2), ..., (frameN, timeN)]
        resultList = resultDict[objId]

        # What we want is a list of just the frame numbers:
        # [frame1, frame2, ..., frameN]
        frameList, _ = zip(*resultList)

        # Get a "group ID" for each element.  This will magically assign an
        # ID that will be the same for elements that are consecutive.
        # ...so, for  [0,  1,  2,  5,  7,  8,  9, 20, 21, 30]
        # ...subtract [0,  1,  2,  3,  4,  5,  6,  7,  8,  9]
        # ...you get  [0,  0,  0,  2,  3,  3,  3, 13, 13, 21]

        zeroThruLength = range(len(frameList))
        groupIdArr = [u - v for (u, v) in zip(frameList, zeroThruLength)]

        # This will be the indicies of the end of sequences...
        # ...probably overly clever, but really quick.  By subtracting the
        # group IDs from 1-offset from themselves, you'll quickly identify
        # any places where the ID changes because those spots will be
        # non-zero. ...so above, the subtraction gets:
        # [ 0,  0,  2,  1,  0,  0, 10,  0,  8]
        # ...and then the non-zero gets the indices of the non-zero points
        # and gets us:
        # [ 0,  0,  2,  3,  0,  0,  6,  0,  8]
        # ...finally, keep the non-zero indices only:
        # [ 2,  3,  6,  8]
        # ... this final list is our 'sequenceEnds' list.
        sequenceEnds = [
            idx
            for (u, v, idx) in zip(
                groupIdArr[1:], groupIdArr[:-1], zeroThruLength[:-1]
            )
            if u - v != 0
        ]

        # Append the size of the list minus one to return to our original size.
        sequenceEnds.append(len(frameList)-1)

        # Parse the end points and add entries to the rangeDict
        ranges = []
        sequenceBegin = 0
        for sequenceEnd in sequenceEnds:
            ranges.append((resultList[sequenceBegin], resultList[sequenceEnd]))
            sequenceBegin = sequenceEnd + 1

        rangeDict[objId] = ranges

    return rangeDict


##############################################################################
def parseSearchResultsLegacy(resultsList, shouldCombineClips):
    """Prepare search results to be sent to a

    @param  resultsList         The list of results.  Looks like a list of
                                (objId, objFrame, objTime) tuples.  MUST BE
                                SORTED, at least if shouldCombineClips!
    @param  shouldCombineClips  If True, we should combine adjacent results.
    @return rangeDict           Key = objId,
                                Value = list of (startFrame, startMs,
                                                 endFrame, endMs)
    """
    # Handle the non-combine case right away, which is really simple...
    if not shouldCombineClips:
        rangeDict = defaultdict(list)
        for objId, objFrame, objTime in resultsList:
            rangeDict[objId].append(((objFrame, objTime),
                                     (objFrame, objTime)))
        return rangeDict

    # Based on RecognitionObject's _getRangeStr()

    # Create a result dictionary for storing each object's results and a
    # range dict to store the return data
    resultDict = defaultdict(list)
    rangeDict = defaultdict(list)

    # Split the results by object id
    for (objId, frame, time) in resultsList:
        resultDict[objId].append((frame, time))

    for objId in resultDict:
        # This is a list of 2-tuples:
        #   [(frame1, time1), (frame2, time2), ..., (frameN, timeN)]
        resultList = resultDict[objId]

        # What we want is a list of just the frame numbers:
        # [frame1, frame2, ..., frameN]

        # Get a "group ID" for each element.  This will magically assign an
        # ID that will be the same for elements that are consecutive.
        # ...so, for  [0,  1,  2,  5,  7,  8,  9, 20, 21, 30]
        # ...subtract [0,  1,  2,  3,  4,  5,  6,  7,  8,  9]
        # ...you get  [0,  0,  0,  2,  3,  3,  3, 13, 13, 21]

        numpyArr = numpy.array(resultList)[:, 0]
        groupIdArr = numpyArr - xrange(len(numpyArr))

        # This will be the indicies of the end of sequences...
        # ...probably overly clever, but really quick.  By subtracting the
        # group IDs from 1-offset from themselves, you'll quickly identify
        # any places where the ID changes because those spots will be
        # non-zero. ...so above, the subtraction gets:
        # [ 0,  0,  2,  1,  0,  0, 10,  0,  8]
        # ...and then the non-zero gets the indices of the non-zero points
        # and gets us:
        # [ 0,  0,  2,  3,  0,  0,  6,  0,  8]
        # ...finally, keep the non-zero indices only:
        # [ 2,  3,  6,  8]
        # ... this final list is our 'sequenceEnds' list.
        # Append the size of the list minus one to return to our original size.
        sequenceEnds = (groupIdArr[1:] - groupIdArr[:-1]).nonzero()[0]
        sequenceEnds = numpy.append(sequenceEnds, len(numpyArr) - 1)

        # Parse the end points and add entries to the rangeDict
        ranges = []
        sequenceBegin = 0
        for sequenceEnd in sequenceEnds:
            ranges.append((resultList[sequenceBegin], resultList[sequenceEnd]))
            sequenceBegin = sequenceEnd + 1

        rangeDict[objId] = ranges

    return rangeDict


##############################################################################
def extendPendingRanges(pendingRanges, rangeDict, shouldCombineRanges):
    """Extend pendingRanges with the given rangeDict.

    Adjacent ranges (within 1 frame) will be combined.

    @param  pendingRanges  A list of pending ranges...  [
                              (objId, ((firstMs, firstFrame),
                                       (lastMs, lastFrame))),
                              ...,
                              ...
                            ]
                           Will be sorted.
    @param  rangeDict      A dictionary of response ranges.  Key = objId,
                           value = list of ((firstFrame, firstTime),
                                            (lastFrame, lastTime))
    @param  shouldCombineRanges  If True, we'll combine adjacent ranges.
    """
    for objId, rangeList in rangeDict.iteritems():
        assert rangeDict[objId], "Shouldn't add empty ranges"

        for ((firstFrame, firstTime), (lastFrame, lastTime)) in rangeList:
            pendingRanges.append((
                objId, ((firstTime, firstFrame), (lastTime, lastFrame)), None
            ))
    pendingRanges.sort()

    # Bail out of the combining code if we're not supposed to run it...
    if not shouldCombineRanges:
        return

    # We'll merge adjacent ranges (ones that are 1 frame apart and refer
    # to the same object).  Merging is easy, since we already sorted by
    # objectId and startTime, and an object can only exist once at any given
    # time.  Work backwards so it's easy to delete...
    for i in xrange(len(pendingRanges)-1, 0, -1):
        # Get previous (p) and this (t) range...
        pId, ((pFirstTime, pFirstFrame), (pLastTime, pLastFrame)), _ = \
            pendingRanges[i-1]
        tId, ((tFirstTime, tFirstFrame), (tLastTime, tLastFrame)), _ = \
            pendingRanges[i]

        # If they are adjacent, combine...
        if (pId == tId) and (tFirstFrame == (pLastFrame+1)):
            pendingRanges[i-1] = (
                pId, ((pFirstTime, pFirstFrame), (tLastTime, tLastFrame)), None
            )
            del pendingRanges[i]


##############################################################################
def pullOutDoneClips(curResults, pendingRanges, ms, startOffset, stopOffset,
                     shouldCombineClips, prevStopTime=0):
    """Pull out clips that are done.

    The idea here is that we want to pull things out of the 'pendingRanges'
    that we are totally done with and make clips out of them.  These clips
    are ready to send off and won't be extended more.

    @param  curResults          The result of makeResultsFromRanges().  This
                                will not be modified.
    @param  pendingRanges       The pendingRanges that were passed to
                                makeResultsFromRanges().  We'll delete things
                                from here.
    @param  ms                  The ms which indicates the latest ms which
                                has been accounted for in pendingRanges.  May
                                be None to pull out everything.
    @param  startOffset         The startOffset of the current query.
    @param  stopOffset          The stopOffset of the current query.
    @param  shouldCombineClips  The shouldCombineClips of the current query.
    @param  prevStopTime        The value of stopTime from last call; start at 0
    @return stopTime            Pass as prevStopTime next call.
    @return doneClips           A list of clips that are all done.
    """
    doneClips = []

    # NOTE: When running in "shouldCombineClips" mode, the way that this
    # function works is that it generally assumes that it won't be given data
    # about time points _before_ the ms passed to the previous call.  Said
    # another way, we assume that nothing else will later be added to the
    # pending ranges that is before the passed in "ms".
    #
    # There is one case that is definitely not true: door triggers.  Those
    # triggers fire with a pretty big delay.  Luckily, door triggers are
    # instant triggers, and never set "shouldCombineClips" to true.

    # Figure out what ms should be considered 'finished'.  In other words,
    # anything that happened before this ms cannot be changed...
    if (ms is not None) and shouldCombineClips:
        # We will say that we're "finished" with all clips whose REAL stop
        # time was more than "startOffset + stopOffset" ms ago.
        # Those clips can't overlap with us anymore.
        #
        # We also need to worry about overlapping clips getting combined
        # (that happens if two clips are within 3 frames of each other
        # regardless of object ID), but I figure that should be handled
        # because it's always much smaller than startOffset.
        finishedMs = (ms - startOffset - stopOffset - 1)
    else:
        # No combining is done.  When we have enough video, we're finished.
        finishedMs = ms

    # Sort by startTime.  This means we upload earlier clips first.  It is
    # also important in the case of "combine clips" in keeping track of
    # self._prevStopTime properly...
    curResults.sort(key=operator.attrgetter(OB_ASID('startTime'),
                                            OB_ASID('stopTime')))

    rangesToKill = []
    for clipInfo in curResults:
        realStopTime = clipInfo._realStopTime

        if (finishedMs is not None) and (realStopTime > finishedMs):
            continue

        rangesToKill.extend(clipInfo.sourceItemIndices)

        # Make sure that we don't ever include stuff that we previously sent
        # out if we're combining clips...
        if shouldCombineClips:
            clipInfo.startTime = max(clipInfo.startTime, prevStopTime+1)
            clipInfo.playStart = max(clipInfo.startTime, clipInfo.playStart)

            assert clipInfo.stopTime >= clipInfo.startTime
            assert clipInfo.stopTime >= prevStopTime

            prevStopTime = clipInfo.stopTime

        doneClips.append(clipInfo)

    # Delete any ranges that were used up...
    rangesToKill.sort(reverse=True)
    assert len(rangesToKill) == len(set(rangesToKill)), \
           "Should be no duplication in rangesToKill"

    for i in rangesToKill:
        del pendingRanges[i]

    return prevStopTime, doneClips


##############################################################################
def getSearchTimes(searchDate):
    """Translate a date into a set of times used to perform a search.

    @param  searchDate  A datetime object of the day to find times for.
    @return startTime   The start time of the search.
    @return endTime     The end time of the search.
    @return midnightMs  The time value of midnight for what to show in
                        the timeline control.  This is fairly close to
                        startTime, but doesn't have slop.
    @return nextMidnightMs  The ms of the next midnight.  Clips that start after
                            this should be ignored.
    """
    # If searchDate is None, search throughout all time.  This is signified
    # by returning None for everything...
    if searchDate is None:
        return None, None, None, None

    if searchDate <= datetime.date.fromtimestamp(0):
        # Force time to be 0 or more; next date will be midnight of the day
        # after, which is probably less than 24 hours unless you're GMT.
        midnightTime = 0
        searchDate = datetime.date.fromtimestamp(0)
    else:
        midnightTime = int(time.mktime(searchDate.timetuple()) * 1000)

    # Next midnight time is constructed using datetime objects and a
    # timedelta object.  This is good, since it handles daylight savings
    # time properly.  That is, next midnight can be 23, 24, or 25 hours
    # away from the current midnight (24 is normal, 23 and 25 happen during
    # daylight savings time).
    nextMidnightTime = int(time.mktime((searchDate +
                                        datetime.timedelta(1)).timetuple()) *
                           1000)

    # Make start and end time.  A few notes:
    # - we put a bit of slop in so that we can detect events that happen
    #   across midnight.  They will show up on both days.
    # - we don't want to search for anything newer than the current time,
    #   since we won't have video.  We find the current time _before_
    #   flushing to try to make sure we really have the video.
    startTime = max(midnightTime - _kSearchSlopMs, 0)
    fullDay = nextMidnightTime + _kSearchSlopMs - 1
    nowTime = int(time.time()*1000)
    endTime = min(fullDay, nowTime)
    #stopSlop = min(max(nowTime-(fullDay-_kSearchSlopMs), 0), _kSearchSlopMs)
    return startTime, endTime, midnightTime, nextMidnightTime


##############################################################################
def _makeResultsFromRangesStage1(rangeItems, playOffset, startOffset,
                                 stopOffset, shouldCombineClips):
    """Make a preliminary set of results given rangeItems.

    Processing that happens here:
    - If we're not combining clips and two objects on the same camera trigger
      at the same time, we'll still combine them into one result (with both
      objects)
    - If we are combining clips and the same object triggers twice in close
      proximity (the object's two padded ranges overlap), we'll combine the
      two ranges.

    Note: we DON'T do the generic combining of overlapping clips here.  That
    happens even between objects of different IDs, but works on _actual_
    start and stop times, not padded ones.

    NOTES:
    - Results should all be from the same camera.

    @param  rangeItems          A sorted iterable of tuples, like this: [
                                  (objId, ((firstMs, firstFrame),
                                           (lastMs, lastFrame))),
                                  ...,
                                  ...
                                ]
    @param  playOffset          Value from the query indicating how far back
                                from the start of the action we should start
                                playing.
    @param  startOffset         Value from the query indicating how far back
                                from the start of the action we should start
                                clips (AKA: how much padding should we add
                                to the beginning of the clip).
    @param  stopOffset          Value from the query indicating how much
                                padding we should add to the end of the clip.
    @param  shouldCombineClips  If True, this is not an "instant" query and we
                                should try to combine clips.
    @return curResults          Results.  These will be MatchingClipInfo objects
                                with the camLoc and isSaved as None.  Note that
                                the sourceItemIndices of the objects will be
                                valid.  Will be sorted by stopTime.
    """
    curResults = []

    if not shouldCombineClips:
        instClips = {}

        enumedItems = enumerate(rangeItems)
        for i, (objId, ((start, startFrame), (stop, stopFrame)), camLoc) in enumedItems:

            if (start, startFrame) in instClips:
                # We want to combine any instantaneous occurances. If we
                # don't do this and boxes had merged together door queries
                # and the like will give us multiple identical clips in the
                # results list.
                clipInfo = instClips[(start, startFrame)]
                clipInfo.camLoc = camLoc
                clipInfo.sourceItemIndices.append(i)
                if objId not in clipInfo.objList:
                    clipInfo.objList.append(objId)
            else:
                clipInfo = MatchingClipInfo._privateMake(
                    start-startOffset, stop+stopOffset, start-playOffset,
                    (stop+start)/2, [objId], [start], start, stop,
                    startFrame, stopFrame, [i]
                )
                clipInfo.camLoc = camLoc
                curResults.append(clipInfo)

                # Keep track of 'instant' clips so we can add to them...
                if start == stop:
                    instClips[(start, startFrame)] = clipInfo
    else:
        prevObjId = None

        enumedItems = enumerate(rangeItems)
        for i, (objId, ((start, startFrame), (stop, stopFrame)), camLoc) in enumedItems:
            # Create list of clips.
            #
            # ...note that if we're combining clips and the same object
            # ID triggered in close proximity (look at overlap in padded
            # ranges, not actual ones), we'll combine...
            if objId == prevObjId:
                prevClipInfo = curResults[-1]

                if (start-startOffset) <= prevClipInfo.stopTime:
                    prevClipInfo.stopTime = stop+stopOffset
                    prevClipInfo.startList.append(start)
                    prevClipInfo._realStopTime = stop
                    prevClipInfo._stopFrame = stopFrame
                    prevClipInfo.sourceItemIndices.append(i)
                    continue

            clipInfo = MatchingClipInfo._privateMake(
                start-startOffset, stop+stopOffset, start-playOffset,
                (stop+start)/2, [objId], [start], start, stop,
                startFrame, stopFrame, [i]
            )
            clipInfo.camLoc = camLoc
            curResults.append(clipInfo)

            prevObjId = objId

    # Sort by stopTime...
    curResults.sort(key=operator.attrgetter(OB_ASID('stopTime')))

    return curResults

##############################################################################
def _getMinMergeThreshold(mergeThresholds, startTime, endTime):
    """ Determine the minimum merge threshold in effect between two times
        This value will determine how much excess video will be spared between the two events,
        and thus, our ability to merge the two clips.
    @param mergeThresholds      A list of (updateTime, mergeThreshold) tuples
    """
    result = None
    for (updateTime,value) in mergeThresholds:
        if updateTime < startTime and updateTime <= endTime:
            result = value
        elif updateTime >= startTime and updateTime <= endTime:
            result = value if result is None else min(result, value)
        else:
            assert updateTime > endTime
            break
    result = 0 if result is None else result
    # print "Using " + str(result) + " for clip merge threshold during " + str((startTime,endTime))
    return result


##############################################################################
def _combineOverlappingClips(curResults, preservePlayOffset, searchConfig, clipMgr):
    """Combine clips that overlap.

    This tries to combine clips in curResults whose _actual_ range (not the
    padded ones) overlap, or are within a few frames of each other.

    It also has a second purpose of making sure that the padding for
    non-overlapping clips don't overlap each other.

    @param  curResults          The current results, which will be modified.
                                Should be sorted by stopTime.
    @param  preservePlayOffset  If True attempt to treat playOffset as part of
                                the clip, not as padding.
    @param  searchConfig        Search configuration attributes
    @param  clipMgr             Clip manager
    """


    i = len(curResults)-1

    mergeThresholds = None
    if searchConfig is not None:
        mergeThresholds = searchConfig.getMergeThresholdsForQuery()
    if mergeThresholds is None:
        timeMin = curResults[0].startTime
        timeMax = curResults[i].stopTime
        mergeThresholds = clipMgr.getClipMergeThresholds(timeMin, timeMax)
    assert mergeThresholds is not None

    while i>0:
        clipInfo = curResults[i]
        prevClipInfo = curResults[i-1]

        start = clipInfo.startTime
        playStart = clipInfo.playStart
        realStart = clipInfo._realStartTime
        startFrame = clipInfo._startFrame
        prevStop = prevClipInfo.stopTime
        prevRealStop = prevClipInfo._realStopTime
        prevStopFrame = prevClipInfo._stopFrame

        # Get min merge threshold for the relevant time period, and convert from sec to ms
        mergeThreshold = _getMinMergeThreshold(mergeThresholds, prevStop, start)*1000

        # Three possible scenarios:
        # 1. within max distance
        # 2. actual overlap
        # 3. within hardcoded distance with very few frames in between
        if ( mergeThreshold > 0 and \
            realStart - prevRealStop <= mergeThreshold ) or \
            realStart < prevRealStop or \
           ((0 <= startFrame-prevStopFrame <= kFrameTolerance) and
            (realStart-prevRealStop <= _kMsTolerance)              ):

            # Combine overlapping clips
            clipInfo.startTime = min(start, prevClipInfo.startTime)
            clipInfo.playStart = min(clipInfo.playStart, prevClipInfo.playStart)
            clipInfo.previewMs = min(clipInfo.previewMs, prevClipInfo.previewMs)
            clipInfo.objList = list(set(clipInfo.objList+prevClipInfo.objList))
            clipInfo.startList.extend(prevClipInfo.startList)
            clipInfo._realStartTime = min(realStart, prevClipInfo._realStartTime)
            clipInfo._startFrame = min(startFrame, prevClipInfo._startFrame)
            clipInfo.sourceItemIndices.extend(prevClipInfo.sourceItemIndices)
            # if one of the clip is saved because of the rule, so is combined clip
            clipInfo.isSaved = clipInfo.isSaved or prevClipInfo.isSaved

            curResults.pop(i-1)

        elif start <= prevStop:
            # Ensure that lead in and out buffers don't overlap
            if preservePlayOffset:
                assert playStart >= start
                # For some queries we don't want to allow the playOffset to
                # be treated as padding.
                if playStart <= prevRealStop:
                    diff = 0
                else:
                    diff = playStart-prevRealStop
            else:
                diff = realStart-prevRealStop

            newPrevStopTime = prevRealStop + diff//2
            if (newPrevStopTime+1) < clipInfo.startTime:
                prevClipInfo.stopTime = clipInfo.startTime-1
            elif newPrevStopTime >= prevClipInfo.stopTime:
                clipInfo.startTime = prevClipInfo.stopTime+1
            else:
                prevClipInfo.stopTime = newPrevStopTime
                clipInfo.startTime = newPrevStopTime + 1
            clipInfo.playStart = max(clipInfo.startTime, clipInfo.playStart)

            if not hasattr(sys, 'frozen'):
                if prevClipInfo.stopTime < prevClipInfo._realStopTime or \
                    clipInfo.startTime > clipInfo._realStartTime or \
                    prevClipInfo.stopTime >= clipInfo.startTime:
                    print "Assertion inbound: prev=" + str(prevClipInfo) + " cur=" + str(clipInfo)
                    assert False


        i -= 1


##############################################################################
def makeResultsFromRanges(rangeItems, playOffset, startOffset,
                          stopOffset, shouldCombineClips, preservePlayOffset,
                          searchConfig, clipMgr):
    """Make a results given rangeItems.

    NOTES:
    - Results should all be from the same camera.

    @param  rangeItems          A sorted iterable of tuples, like this: [
                                  (objId, ((firstMs, firstFrame),
                                           (lastMs, lastFrame))),
                                  ...,
                                  ...
                                ]
    @param  playOffset          Value from the query indicating how far back
                                from the start of the action we should start
                                playing.
    @param  startOffset         Value from the query indicating how far back
                                from the start of the action we should start
                                clips (AKA: how much padding should we add
                                to the beginning of the clip).
    @param  stopOffset          Value from the query indicating how much
                                padding we should add to the end of the clip.
    @param  shouldCombineClips  If True, this is not an "instant" query and we
                                should try to combine clips.
    @param  preservePlayOffset  If True attempt to treat playOffset as part of
                                the clip, not as padding.
    @param  searchConfig        Search configuration attributes
    @param  clipMgr             Clip manager
    @return curResults          Results.  These will be MatchingClipInfo objects
                                with the camLoc and isSaved as None.  Note that
                                the sourceItemIndices of the objects will be
                                valid.
    """
    curResults = _makeResultsFromRangesStage1(
        rangeItems, playOffset, startOffset, stopOffset, shouldCombineClips
    )

    # Combine overlapping clips if the query is a simple in/out/on
    # region trigger
    if shouldCombineClips:
        _combineOverlappingClips(curResults, preservePlayOffset, searchConfig, clipMgr)

    return curResults


##############################################################################
def _addCamAndSaveInfo(curResults, camera, flushDict, savedRanges):
    """Make the final results from the interrim results.

    @param  curResults   The interrim results.
    @param  camera       The camera related to the interrim results.
    @param  flushDict    A dictionary, keyed by camera.  Values are tuples:
                            (lastProcssedMs, lastTaggedForSavingMs)
    @param  savedRanges  The results of:
                            clipMgr.getTimesFromLocation(camera, startTime,
                                                         endTime, True)
    """
    assert curResults, "Shouldn't call if no interrim results."

    # There's a flush pending if there's anything in the flush dictionary...
    flushPending = bool(flushDict)

    startBisectIdx = 0
    _, realMaxTaggedMs = flushDict.get(camera, (0,0))

    numRanges = len(savedRanges)
    curMaxTaggedMs = 0
    if numRanges:
        curMaxTaggedMs = savedRanges[numRanges-1][1]

    for clipInfo in curResults:
        start, stop = clipInfo._realStartTime, clipInfo._realStopTime
        isSaved = False

        # If this file hasn't been fully flushed yet, put it in an
        # 'unknown' state that just happens to be the real stop time.
        # We'll use this as a check in the SearchResultsList to know
        # if we need further validation for this element.
        if flushPending and stop > curMaxTaggedMs and \
           stop <= realMaxTaggedMs:
            isSaved = stop

        elif numRanges:
            idx = bisect.bisect_left(savedRanges, (start, 0),
                                     startBisectIdx)
            if idx < numRanges and \
               start == savedRanges[idx][0] and \
               stop <= savedRanges[idx][1]:
                isSaved = True
            elif idx != 0 and stop <= savedRanges[idx-1][1]:
                # We know start is greater than the previous index,
                # so we only need to check that the clip stop is
                # less than the previous stop.
                isSaved = True

            startBisectIdx = max(0, idx-1)

        clipInfo.camLoc = camera
        clipInfo.isSaved = isSaved


##############################################################################
def getSearchResults(query, cameraList, searchDate, dataMgr, clipMgr,
        searchConfig, flushFunc, updateFunc=None, abortEvent=None):
    """Perform a search and return matching clips.

    @param  query          The query to search with.
    @param  cameraList     A list of cameras to search on.
    @param  searchDate     A datetime object of the day to search on.
    @param  dataMgr        A DataManager instance.
    @param  clipMgr        A ClipManager instance.
    @param  searchConfig   Search configuration attributes
    @param  flushFunc      A function that takes a camera name, to be used
                           for flushing the cameras if necessary.  Returns
                              (lastProcssedMs, lastTaggedForSavingMs)
    @param  updateFunc     An update function that will be occasionally called
                           during search and processing. Must take a single
                           string parameter, the camera being searched.
    @param  abortEvent     An event that will be set if search should abort.
    @return processedDict  Key = camera name, value = (highestProcessedMs,
                                                       highestTaggedMs)
                           This will be empty if searchDate != today.
    @return matchingClips  A list of MatchingClipInfo objects for each
                           clip that matched the search.
    """
    matchingClips = []

    startTime, endTime, midnightMs, nextMidnightMs = getSearchTimes(searchDate)

    flushDict = {}
    if searchDate == datetime.date.today():
        for camera in cameraList:
            # Ensure that video for everything we search will be available
            # for playback.
            flushDict[camera] = flushFunc(camera)

    return _realGetSearchResults(query, cameraList, startTime, endTime,
            midnightMs, nextMidnightMs, dataMgr, clipMgr, flushDict, searchConfig,
            updateFunc, abortEvent)


##############################################################################
def getSearchResultsBetweenTimes(query, cameraList, startTime, endTime, slop,
        dataMgr, clipMgr, searchConfig, flushFunc, updateFunc=None, abortEvent=None):
    """Perform a search and return matching clips.

    @param  query          The query to search with.
    @param  cameraList     A list of cameras to search on.
    @param  startTime      The ms to begin the search on.
    @param  endTime        The ms to end the search on.
    @param  slop           The amount of time to search before or after for
                           clips that may be ongoing or extend past the
                           startTime and endTime.
    @param  dataMgr        A DataManager instance.
    @param  clipMgr        A ClipManager instance.
    @param  searchConfig   Search configuration attributes
    @param  flushFunc      A function that takes a camera name, to be used
                           for flushing the cameras if necessary.  Returns
                              (lastProcssedMs, lastTaggedForSavingMs)
    @return processedDict  Key = camera name, value = (highestProcessedMs,
                                                       highestTaggedMs)
                           This will be empty if searchDate != today.
    @return matchingClips  A list of MatchingClipInfo objects for each
                           clip that matched the search.
    """
    # If within 30 mintues of end, flush
    flushDict = {}
    if endTime > (time.time()*1000-30*60*1000):
        for camera in cameraList:
            # Ensure that video for everything we search will be available
            # for playback.
            flushDict[camera] = flushFunc(camera)

    return _realGetSearchResults(query, cameraList, startTime-slop,
            endTime+slop, startTime, endTime, dataMgr, clipMgr, flushDict,
            searchConfig, updateFunc, abortEvent)

##############################################################################
def _getMatchingRanges(query, startTime, endTime, midnightMs,
        nextMidnightMs, dataMgr, procSizesMsRange):
    """Perform a search and return matching motion ranges.

    @param  query          The query to search with.
    @param  startTime      The start time of the search.
    @param  endTime        The end time of the search.
    @param  midnightMs     The time value of midnight for what to show in
                           the timeline control.  This is fairly close to
                           startTime, but doesn't have slop.
    @param  nextMidnightMs The ms of the next midnight.  Clips that start after
                           this should be ignored.
    @param  dataMgr        A DataManager instance.
    @return processedDict  Key = camera name, value = (highestProcessedMs,
                                                       highestTaggedMs)
                           This will be empty if searchDate != today.
    @return rangeItems     An iterable of tuples, like this: [
                                (objId, ((firstMs, firstFrame),
                                         (lastMs, lastFrame)), camLoc)
                                ...
                              ]
    """
    if query.shouldCombineClips():
        rangeItems = \
            dataMgr.getSearchResultsRanges(query, startTime, endTime, procSizesMsRange)
    else:
        results = dataMgr.getSearchResults(query, startTime, endTime, procSizesMsRange)
        rangeItems = []
        for objId, msList in results.iteritems():
            rangeList = zip(msList, msList)
            rangeItems.extend(zip([objId] * len(rangeList), rangeList))

    # At this point, rangeItems is an iterable of tuples, like this:
    #  [ (objId, ((firstMs, firstFrame), (lastMs, lastFrame))), camLoc, ..., ... ]

    # Make sure each of the items is in completely in bounds.  That is,
    # the item must start or end within today.
    if (startTime is not None):
        rangeItems = (
            item for item in rangeItems if
            (item[1][0][0] < nextMidnightMs and item[1][1][0] >= midnightMs)
        )
        # Convert generator to list, for consistent return value
        rangeItems = list(rangeItems)

    return rangeItems

##############################################################################
def _realGetSearchResults(query, cameraList, startTime, endTime, midnightMs,
        nextMidnightMs, dataMgr, clipMgr, flushDict, searchConfig, updateFunc=None,
        abortEvent=None):
    """Perform a search and return matching clips.

    @param  query          The query to search with.
    @param  cameraList     A list of cameras to search on.
    @param  startTime      The start time of the search.
    @param  endTime        The end time of the search.
    @param  midnightMs     The time value of midnight for what to show in
                           the timeline control.  This is fairly close to
                           startTime, but doesn't have slop.
    @param  nextMidnightMs The ms of the next midnight.  Clips that start after
                           this should be ignored.
    @param  dataMgr        A DataManager instance.
    @param  clipMgr        A ClipManager instance.
    @param  flushDict      A dictionary, key=camera name, value =
                           (lastProcessedMs, lastTaggedForSavingMs), or {}
    @param  searchConfig   Search configuration attributes
    @param  updateFunc     An update function that will be occasionally called
                           during search and processing. Must take a single
                           string parameter, the camera being searched.
    @param  abortEvent     An event that will be set if search should abort.
    @return processedDict  Key = camera name, value = (highestProcessedMs,
                                                       highestTaggedMs)
                           This will be empty if searchDate != today.
    @return matchingClips  A list of MatchingClipInfo objects for each
                           clip that matched the search.
    """
    matchingClips = []

    # Retrieve information about the query to perform.
    playOffset, preservePlayOffset = query.getPlayTimeOffset()
    startOffset, stopOffset = query.getClipLengthOffsets()
    shouldCombineClips = query.shouldCombineClips()

    query.setDataManager(dataMgr)

    # We can run a single search, as long as the query isn't spatially aware
    # (and thus isn't dependent on processing size ranges)
    individualSearch = query.spatiallyAware()
    if not individualSearch:
        # This will end up in dataMgr.getObjectRangesBetweenTimes ... we don't want
        # camera locations to be part of the query, if there's more than one camera
        dataMgr.setCameraFilter(None if len(cameraList)>1 else cameraList)
        rangeItems = _getMatchingRanges(query, startTime, endTime,
                    midnightMs, nextMidnightMs, dataMgr, [])
        dataMgr.setCameraFilter(None)


    # Get thresholds once, so we don't query database separately for each camera
    mergeThresholds = clipMgr.getClipMergeThresholds(startTime, endTime)
    if searchConfig is not None:
        searchConfig.setMergeThresholdsForQuery(mergeThresholds)

    for camera in cameraList:
        if updateFunc:
            updateFunc(camera)

        if abortEvent is not None:
            abortEvent()

        cameraSpecificRangeItems = []
        if individualSearch:
            # If the search is performed on each camera individually,
            # determine the processing ranges, and filter with camera name
            dataMgr.setCameraFilter([camera])
            procSizesMsRange = dataMgr.getUniqueProcSizesBetweenTimes(
                    camera, startTime, endTime)
            rangeItems = _getMatchingRanges(query, startTime, endTime,
                    midnightMs, nextMidnightMs, dataMgr, procSizesMsRange)
            dataMgr.setCameraFilter(None)

            # trigger query in BastTrigger.searchForRanges can't assign camera name as
            # DataManager.getObjectRangesBetweenTimes does
            # TODO: figure out a way to propagate camera info to BaseTrigger.searchForRanges
            for item in rangeItems:
                cameraSpecificRangeItems.append( (item[0], item[1], camera) )
        else:
            # If a global search, not filtered on camera names had been ran,
            # get only results for the current camera, and use those to
            # arrange the clips
            newRangeItems = []

            for item in rangeItems:
                if camera == item[2]:
                    cameraSpecificRangeItems.append(item)
                else:
                    newRangeItems.append(item)
            rangeItems = newRangeItems

        # Sort the ranges, so that all objects with the same ID are grouped
        # together, then the ranges are ordered by time...
        cameraSpecificRangeItems = sorted(cameraSpecificRangeItems)

        # Make curResults
        curResults = makeResultsFromRanges( cameraSpecificRangeItems, playOffset,
            startOffset, stopOffset, False, preservePlayOffset, searchConfig, clipMgr)

        # Add a flag signifying whether each file is fully marked as saved
        # or not.
        if curResults and clipMgr:
            savedRanges = clipMgr.getTimesFromLocation(camera, startTime,
                                                       endTime, True)
            _addCamAndSaveInfo(curResults, camera, flushDict, savedRanges)

        if curResults and query.shouldCombineClips():
            _combineOverlappingClips(curResults, preservePlayOffset, searchConfig, clipMgr)

        matchingClips.extend(curResults)

    return flushDict, matchingClips


##############################################################################
class MatchingClipInfo(object):
    """Holds info about a matching clip.

    This is pretty much a structure, but is also a subclass of list for
    backward compatibility with old code.
    """

    ###########################################################
    def __init__(self, camLoc, startTime, stopTime, playStart, #PYCHECKER too many args OK.
                 previewMs, objList, startList, isSaved, filename="",
                 fileStartMs=None):
        """MatchingClipInfo constructor.

        @param  camLoc      The camera location of the clip.
        @param  startTime   The time the clip starts.
        @param  stopTime    The time the clip stops.
        @param  playStart   The time where we should start playing the clip.
        @param  previewMs   The time that the preview window should show.
        @param  objList     A list of object IDs in this clip.
        @param  startList   A list of 'start times' of the various events in the
                            clip.
        @param  isSaved     True if the clip is saved.
        @param  filename    The filename (not the full path, just the filename)
                            of the clip.  May be None, then filled in later.
        @param  fileStartMs The ms of the start of filename.  Only valid if
                            filename is.
        """
        # Old fields...
        self.camLoc = camLoc
        self.startTime = startTime
        self.stopTime = stopTime
        self.playStart = playStart
        self.previewMs = previewMs
        self.objList = objList
        self.startList = startList
        self.isSaved = isSaved

        # New fields...
        self.filename = filename
        self.fileStartMs = fileStartMs

        # New fields not passed to constructor

        # ...the rangeItem that originally made this clip.  Valid only in
        # items returned by makeResultsFromRanges.  Otherwise, this value
        # should be ignored.
        self.sourceItemIndices = None

    ###########################################################
    def __str__(self):
        result = ""
        if self.camLoc is not None:
            result = result + "camLoc=" + str(ensureUtf8(self.camLoc))
        result = result + " startTime=" + getDebugTime(self.startTime)
        result = result + " stopTime=" + getDebugTime(self.stopTime)
        result = result + " playStart=" + str(self.playStart)
        result = result + " realStartTime=" + getDebugTime(self._realStartTime)
        result = result + " realStopTime=" + getDebugTime(self._realStopTime)
        result = result + " objList=" + str(self.objList)
        return result

    __repr__ = __str__

    ###########################################################
    @classmethod #PYCHECKER too many args OK.
    def _privateMake(cls, startTime, stopTime, playStart, previewMs, objList,
                     startList, realStartTime, realStopTime,
                     startFrame, stopFrame, sourceItemIndices):
        """A private constructor, used internally.

        This sets variables that are only used by internal functions as they
        create, sort, and organize results.  It is not the general, "public"
        constructor for this object.

        @param  startTime          See normal constructor
        @param  stopTime           ...
        @param  playStart          ...
        @param  previewMs          ...
        @param  objList            ...
        @param  startList          ...
        @param  realStartTime      The real (unpadded) start time
        @param  realStopTime       The real (unpadded) stop time.
        @param  startFrame         The frame number of the start.  Remember that
                                   frame numbers reset every time a camera
                                   is turned on and off.
        @param  stopFrame          The frame number of the stop.
        @param  sourceItemIndices  The rangeItem that originally made this
                                   clip.  Valid only for items returned by
                                   makeResultsFromRanges()
        """
        self = cls(None, startTime, stopTime, playStart, previewMs,
                   objList, startList, None)

        self.sourceItemIndices = sourceItemIndices

        # These are private and used internally in this file.  They shouldn't
        # be relied upon to be correct in other places.  Specifically, other
        # places that create MatchingClipInfo() objects won't create them.
        self._realStartTime = realStartTime
        self._realStopTime = realStopTime
        self._startFrame = startFrame
        self._stopFrame = stopFrame

        return self

