#!/usr/bin/env python

#*****************************************************************************
#
# UnitTests.py
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


# Python imports...
import cPickle as pickle
import datetime
import gzip
import os
import shutil
import sys
import time

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.loggingUtils import LoggingUtils

# Local imports...
from appCommon.SearchUtils import extendPendingRanges
from appCommon.SearchUtils import getSearchResults
from appCommon.SearchUtils import getSearchTimes
from appCommon.SearchUtils import makeResultsFromRanges
from appCommon.SearchUtils import parseSearchResults
from appCommon.SearchUtils import pullOutDoneClips
from appCommon.SearchUtils import SearchConfig
from backEnd.DataManager import DataManager
from backEnd.SavedQueryDataModel import SavedQueryDataModel


# Constants...
_kZippedObjDb = u"smallTestObjDb2.gz"
_kUnzippedObjDb = u"smallTestObjDb2"

_kTestDataDir = u"testData"
_kTmpDir = u"unitTestTmp"

_kZippedDbPath = os.path.join(_kTestDataDir, _kZippedObjDb)
_kTmpDbPath = os.path.join(_kTmpDir, _kUnzippedObjDb)


##############################################################################
def _doPiecemealRealtimeSearch(usableQuery, camLoc, searchDate, dataMgr,
                               incrementMs=10*1000):
    """Does a full search for the given date, but does it piecemeal.

    This is to help validate realtime search.  NOTE: In some cases we know that
    realtime search will be different than the 'single' search.  Specifically:
    * Most triggers that implement searchForRanges(), like the TargetTrigger,
      actually do it in a slightly less accurate (but much faster) manner.
      The target trigger, for instance, will always return one range per
      object ID, even if that object "blinks" out of the scene a few times
      (which it can do with out current tracker).  The normal search() will
      return separate ranges for these "blinks".
    * For some triggers, the 'realTime' search needs to give up on an object
      after a while.  If the object does vanish and then re-appear quite a few
      frames later, it can cause problems for us.  Hopefully this shouldn't
      ever be a problem.

    @param  usableQuery  The usable query object (a trigger object, maybe
                         with subtriggers).
    @param  camLoc       The name of the camera to search on.
    @param  searchDate   The date to search.
    @param  dataMgr      The data manager.
    @param  incrementMs  The number of ms to increment each time.
    """
    dataMgr.setCameraFilter([camLoc])

    startTime, endTime, midnightMs, nextMidnightMs = getSearchTimes(searchDate)
    shouldCombineClips = usableQuery.shouldCombineClips()

    rangeItems = []

    usableQuery.reset()
    for ms in range(startTime, endTime+1, incrementMs):
        endMs = min(ms+incrementMs-1, endTime)

        results = usableQuery.search(ms, endMs, 'realtime')
        results.sort()
        rangeDict = parseSearchResults(results, shouldCombineClips)

        # TODO: Actually yank more code out of the SendClipResponse to try
        # to pull things out early...

        extendPendingRanges(rangeItems, rangeDict, shouldCombineClips)
    usableQuery.reset()

    # TODO: Need to finalize()?

    playOffset, preservePlayOffset = usableQuery.getPlayTimeOffset()
    startOffset, stopOffset = usableQuery.getClipLengthOffsets()

    rangeItems = (
        item for item in rangeItems if
        (item[1][0][0] < nextMidnightMs and item[1][1][0] >= midnightMs)
    )

    # Preserve unit test behavior -- there used to be no maxClipMergeDistance
    searchConfig = SearchConfig()
    searchConfig.disableClipMerging()

    results = makeResultsFromRanges(rangeItems, playOffset, startOffset,
                                    stopOffset, shouldCombineClips,
                                    preservePlayOffset, searchConfig, None)

    return results


##############################################################################
def _doSendClipSearch(usableQuery, camLoc, searchDate, dataMgr,
                      incrementMs=10*1000):
    """This is like _doPiecemealRealtimeSearch(), but takes things 1 step more.

    Here, we actually "send" clips our when they're done, like the
    "SendClipResponse" does.  Once a clip is sent, there's no going back.

    This has the possibility of being different than
    _doPiecemealRealtimeSearch() in one important way: if the same object trips
    the trigger more than once, but at times that are far apart.  In
    _doPiecemealRealtimeSearch(), we will make one clip out of the whole time
    that object was in the scene.  However, in _doSendClipSearch() we will
    eventually give up and decide that the object isn't coming back.  We'll
    just send the clip out, and won't be able to combine it with the previous
    clip.

    @param  usableQuery  The usable query object (a trigger object, maybe
                         with subtriggers).
    @param  camLoc       The name of the camera to search on.
    @param  searchDate   The date to search.
    @param  dataMgr      The data manager.
    @param  incrementMs  The number of ms to increment each time.
    @return allClipInfos All the clip infos that we found.
    """
    dataMgr.setCameraFilter([camLoc])

    startTime, endTime, midnightMs, nextMidnightMs = getSearchTimes(searchDate)
    shouldCombineClips = usableQuery.shouldCombineClips()
    playOffset, preservePlayOffset = usableQuery.getPlayTimeOffset()
    startOffset, stopOffset = usableQuery.getClipLengthOffsets()

    rangeItems = []
    prevStopTime = 0
    allClipInfos = []

    # Preserve unit test behavior -- there used to be no maxClipMergeDistance
    searchConfig = SearchConfig()
    searchConfig.disableClipMerging()

    usableQuery.reset()
    for ms in range(startTime, endTime+1, incrementMs) + [None]:
        if ms is not None:
            endMs = min(ms+incrementMs-1, endTime)
            results = usableQuery.search(ms, endMs, 'realtime')
            results.sort()
            rangeDict = parseSearchResults(results, shouldCombineClips)
            extendPendingRanges(rangeItems, rangeDict, shouldCombineClips)
        else:
            endMs = None

        # Try to make results, just like we do in search view...  This will
        # keep track of which 'source item indices' (indices into
        # self._pendingRanges) were used to make each result.
        curResults = makeResultsFromRanges(
            rangeItems, playOffset, startOffset,
            stopOffset, shouldCombineClips, preservePlayOffset,
            searchConfig, None )

        # Pull out done clips, deleting things from rangeItems...
        prevStopTime, doneClips = pullOutDoneClips(
            curResults, rangeItems, endMs, startOffset, stopOffset,
            shouldCombineClips, prevStopTime
        )

        for clipInfo in doneClips:
            if (clipInfo._realStartTime < nextMidnightMs) and \
               (clipInfo._realStopTime >= midnightMs):
                allClipInfos.append(clipInfo)
    usableQuery.reset()

    return allClipInfos


##############################################################################
def _doSingleSearch(usableQuery, camLoc, searchDate, dataMgr):
    """Wrap getSearchResults() to have the same API as other search methods.

    @param  usableQuery  The usable query object (a trigger object, maybe
                         with subtriggers).
    @param  camLoc       The name of the camera to search on.
    @param  searchDate   The date to search.
    @param  dataMgr      The data manager.
    @return allClipInfos All the clip infos that we found.
    """
    # preserve old behavior - for now
    searchConfig = SearchConfig()
    searchConfig.disableClipMerging()

    _, matchingClips = \
        getSearchResults(usableQuery, [camLoc],
                         searchDate, dataMgr, None, lambda x:None)
    return matchingClips


##############################################################################
def testAgainstOldResults():
    """Test triggers against old results of the triggers.

    These tests are against real data and real queries created in the GUI.
    They don't actually test the correctness of existing code, but the hope
    is that they would tend to fire if anything ever changed.  If they fire,
    we'd have to manually go through and see whether the old code or the new
    code was correct.

    These shouldn't replace targetted tests cases, but right no are all we have.
    """
    # Tuples look like:
    # (queryName, searchDate, isRealTimeDifferent)
    queriesToTest = [
        # Query                        date                       sendClipSuffix realTimeSuffix
        # -------------------------------------------------------------------------------------

        # Real time is different because when I was capturing this, I had
        # 'stuck box fixer' in, which would cause an object to vanish and then
        # reappear later (with the same ID)...  ...and, in fact, it depends
        # on the 'increment' we do the search on, so I just commented this one
        # out.
        #("entering the street in acti",datetime.date(2010, 5, 3), True),

        ("not in over there in acti",  datetime.date(2010, 5, 3), ".results", ".results"),
        ("10s in acti",                datetime.date(2010, 5, 3), ".results", ".results"),

        # Real time is different here because we're using the optimized
        # searchForRanges() in the 'single' search, which is less accurate.
        ("non-people in acti",         datetime.date(2010, 5, 3), ".rtresults", ".rtresults"),
        ("big things in acti",         datetime.date(2010, 5, 3), ".rtresults", ".rtresults"),
        ("big people in acti",         datetime.date(2010, 5, 3), ".rtresults", ".rtresults"),

        ("from mex mkt in acti",       datetime.date(2010, 5, 3), ".results",   ".results"),
        ("to mex mkt in acti",         datetime.date(2010, 5, 3), ".results",   ".results"),
        ("parking in my spot in acti", datetime.date(2010, 5, 3), ".results",   ".results"),
        ("loitering in acti",          datetime.date(2010, 5, 3), ".results", ".results"),


        ("entering the street in acti",datetime.date(2010, 5, 4), ".results",   ".results"),  # entering a region
        ("not in over there in acti",  datetime.date(2010, 5, 4), ".results",   ".results"),  # outside a region
        ("10s in acti",                datetime.date(2010, 5, 4), ".results",   ".results"),  # duration

        # Real time is different here because we're using the optimized
        # searchForRanges() in the 'single' search, which is less accurate.
        ("non-people in acti",         datetime.date(2010, 5, 4), ".rtresults", ".rtresults"),   # target
        ("big things in acti",         datetime.date(2010, 5, 4), ".rtresults", ".rtresults"),   # min size
        ("big people in acti",         datetime.date(2010, 5, 4), ".rtresults", ".rtresults"),   # target + min size

        ("from mex mkt in acti",       datetime.date(2010, 5, 4), ".results",   ".results"),  # coming in through a door
        ("to mex mkt in acti",         datetime.date(2010, 5, 4), ".results",   ".results"),  # exiting through a door
        ("parking in my spot in acti", datetime.date(2010, 5, 4), ".results",   ".results"),  # single direction line trigger
        ("loitering in acti",          datetime.date(2010, 5, 4), ".results",   ".results"),  # on top of region + duration
    ]

    # Make a logger
    logger = LoggingUtils.getLogger("UnitTests")

    if not os.path.isdir(_kTmpDir):
        os.makedirs(_kTmpDir)

    # Uncompress the database into a temp directory...
    shutil.copyfileobj(gzip.GzipFile(_kZippedDbPath, "rb"),
                       open(_kTmpDbPath, 'wb'))

    # Open up the data manager...
    dataMgr = DataManager(logger)
    dataMgr.open(_kTmpDbPath)

    formatFn = _formatClipDataTuple

    for (queryName, searchDate, sendClipSuffix, realTimeSuffix) in queriesToTest:
        resultsDir = os.path.join(_kTestDataDir, str(searchDate))
        if not os.path.isdir(resultsDir):
            os.makedirs(resultsDir)

        searchMechanisms = [
            ("Single",   _doSingleSearch,            ".results"),
            ("SendClip", _doSendClipSearch,          sendClipSuffix),
            ("Realtime", _doPiecemealRealtimeSearch, realTimeSuffix),
        ]

        queryFile = open(os.path.join(_kTestDataDir, queryName + ".query"), 'r')
        query = pickle.load(queryFile)
        camLoc = query.getVideoSource().getLocationName()

        for (mechName, searchFn, resultsSuffix) in searchMechanisms:
            print ("%16s %s % 32s..." % (mechName, str(searchDate), queryName)),
            sys.stdout.flush()

            usableQuery = query.getUsableQuery(dataMgr)

            time1 = time.time()
            matchingClips = searchFn(usableQuery, camLoc, searchDate, dataMgr)
            time2 = time.time()

            print "...% 4d results, took %.3f seconds" % (len(matchingClips),
                                                          time2-time1)

            clipData = [_getClipDataTuple(clip) for clip in matchingClips]
            resultsPath = os.path.join(resultsDir, queryName + resultsSuffix)
            if not os.path.exists(resultsPath):
                print "WARNING: Creating new results for %s" % queryName
                pickle.dump(clipData, open(resultsPath, 'wb'),
                            pickle.HIGHEST_PROTOCOL)
            oldClipData = pickle.load(open(resultsPath, 'rb'))
            if _compareLists(oldClipData, clipData, 'old', 'new', formatFn):
                raise Exception("%s mismatch for %s" % (mechName, queryName))


##############################################################################
def _getClipDataTuple(clip):
    """Takes in a MatchingClip object and returns data for comparison.

    @param  clip       A MatchingClip object.
    @return clipTuple  A tuple of the relevent information for comparing.
    """
    return (clip.camLoc, clip.startTime, clip.stopTime, clip.playStart,
            clip.previewMs, clip.objList, clip.startList, clip.isSaved)


##############################################################################
def _formatClipDataTuple(tup):
    """Format the tuple retuned by _getClipDataTuple().

    @param  tup  A tuple returned by _getClipDataTuple
    @return s    A formatted version.
    """
    return ("""%s: %s - %s (pl %s, pv %s), %s %s %s""" % (
        tup[0],
        _formatTime(tup[1]), _formatTime(tup[2]),
        _formatTime(tup[3]), _formatTime(tup[4]),
        str(tup[5]),
        str([_formatTime(startMs) for startMs in tup[6]]),
        str(tup[7])
    ))


##############################################################################
def _formatTime(ms):
    """Format the given millisecond to be nicely readable.

    @param  ms       The millisecond value (something like time.time() * 1000).
    @return timeStr  A nicely formatted version; won't include the date, tho.
    """
    sec, ms = divmod(ms, 1000)
    timeStruct = time.localtime(sec)
    timeStr = time.strftime('%H:%M:%S', timeStruct).swapcase()
    if timeStr[0] == '0':
        timeStr = timeStr[1:]

    timeStr += (".%03d" % ms)
    return timeStr


##############################################################################
def _compareLists(oldList, newList, oldListName="old", newListName="new",
                  formatFn=str):
    """Compare two lists, printing out differences.

    @param  oldList      The old list.
    @param  newList      The new list.
    @param  oldListName  The name of the old list.
    @param  newListName  The name of the new list.
    @param  formatFn     The function to use to format the lists.
    @return wereDiff     If True, there were differences.
    """
    if oldList != newList:
        for i, oldItem in enumerate(oldList):
            if oldItem not in newList:
                print "ERROR: Item %d not in %s: %s" % (i, newListName, formatFn(oldItem))
        for i, newItem in enumerate(newList):
            if newItem not in oldList:
                print "ERROR: Item %d not in %s: %s" % (i, oldListName, formatFn(newItem))

        return True
    return False


##############################################################################
def test_main():
    """Contains various self-test code."""

    testAgainstOldResults()


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."

