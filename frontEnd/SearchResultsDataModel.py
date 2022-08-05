#!/usr/bin/env python

#*****************************************************************************
#
# SearchResultsDataModel.py
#
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
import bisect
import datetime
import math
import operator
import os
import sys
from threading import Lock
import time
import traceback

# Common 3rd-party imports...
import wx
from wx.lib import delayedresult

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.mvc.AbstractModel import AbstractModel
from vitaToolbox.profiling.MarkTime import TimerLogger

# Local imports...
from appCommon.CommonStrings import kFrontEndLogName
from appCommon.SearchUtils import getSearchResults, getSearchTimes
from appCommon.SearchUtils import MatchingClipInfo, SearchConfig
from backEnd.ClipManager import ClipManager
from backEnd.DataManager import DataManager

from FrontEndPrefs import getFrontEndPref
from FrontEndPrefs import setFrontEndPref


def OB_ASID(a): return a

# Constants...
_kMaxVideoLoadTimerRetries = 10
_kVideoLoadRetryPeriod = 2*60*1000 # only retry loading clips from the last two minutes

# We won't play into cache if < this many milliseconds...
_kMinCacheMs = 300

# We'll consider two ms values "close enough" if they're within this many ms.
_kSlopMs = 200

# We'll allow skipping over this much distance when skipping past a clip...
_kAllowableSkip = 1000 * 60 * 3

# For re-checking for available video...
_kVideoAvailInitRecheckMs = 500
_kVideoAvailSubsequentRecheckMs = 5000
_kVideoAvailNumRechecks = 3

# If we're within _kMsPrevEventTolerance of the previous event when skipping
# back, we'll instead look for the event before it.  This allows a user to
# jump back multiple times in a row rather than being stuck on one event.
_kMsPrevEventTolerance = 500


##############################################################################
class SearchResultsDataModel(wx.EvtHandler, AbstractModel):
    """A data model that represents search results and our current loc in them.

    Putting this into a data model allows everyone to listen for changes
    and allows multiple controllers to make changes.

    Keys for updates are:
    - 'results'      - Called whenever search results change.  Implies
                       'videoAvail', 'videoSegment', 'ms', and 'play' (though
                       we won't actually send those updates out).
    - 'videoAvail'   - Called if the amount of video available changes after
                       the inital results.
    - 'videoSegment' - Called whenever we've changed which video segment we're
                       looking at.  Note that many things won't be ready until
                       the video is actually loaded.
    - 'videoLoaded'  - Called after we've changed video segments and have
                       finished loading the video (OR WE'VE GIVEN UP).
                       ...may also be sent if there's a delay loading, then
                       again after the loading finishes...
                       Note that after getting 'results' or 'videoSegment'
                       notification, many functions will return bogus values
                       until the videoLoaded is sent out.  Implies 'ms' and
                       'play', since we always start at the first play frame,
                       and may have set play or pause when we jumped there.
    - 'ms'           - Called whenever we've changed the location we're looking
                       at within a video segment.
    - 'play'         - Called whenever the play value has changed.
    - 'changingRapidly' - We are changing rapidly when the mouse is down on
                          a slider or the time bar.
    - 'searching'    - Called before we perform a search.
    - 'multipleSelected' - Called when the number of selected clips changes.
    - 'sortResults'  - Called when the sort order of the results changes.
    """

    ###########################################################
    def __init__(self, dataMgr, clipMgr):
        """SearchResultsDataModel constructor.

        @param  clipMgr      A reference to the clip manager.
        @param  dataMgr      A reference to the data manager.
        """
        # We multiply inherit.  The wx.EvtHandler is really only there so that
        # we can use a wx.Timer class easily.
        wx.EvtHandler.__init__(self)
        AbstractModel.__init__(self)

        # Init state that doesn't change w/ a search...
        self._dataMgr = dataMgr
        self._clipMgr = clipMgr

        # Keeps track of whether the user intentionally paused the video;
        # affects whether we start playing automatically in some instances
        self._userPaused = False

        # Keeps track of whether things are changing rapidly (like if the mouse
        # is down on a slider).  Certain thigns won't happen until the rapid
        # change calms down...
        self._changingRapidly = False

        self._videoLoadTimer = wx.Timer(self, -1)
        self._videoLoadTimerRetries = 0
        self.Bind(wx.EVT_TIMER, self.OnVideoLoadTimer, self._videoLoadTimer)

        # A timer to try to look for new video that's available...
        self._videoAvailTimer = wx.Timer(self, -1)
        self._videoAvailTimerRechecks = 0
        self.Bind(wx.EVT_TIMER, self.OnVideoAvailTimer, self._videoAvailTimer)

        # Init transitory state; use the resetXXX functions so that we are
        # consistent.
        self.resetSearch(False)

        # Sort order for the clip results in the SearchResultsList. When "True"
        # the values are _ascending_ downward with least recent detection at the
        # top of the list.  When "False" the values are _descending_ downward
        # with the most recent detection at the top of the list.
        self._isAscending = getFrontEndPref('isSortAscending')

        # Key = camera name, value = (highestProcessedMs, highestTaggedMs)
        self._processedDict = {}

        # True when multiple clips are selected in the results list.
        self._multipleSelected = False
        self._selectedIds = []

        # The size to open video and return frames at.
        self._desiredVideoSize = (0, 0)

        # Searches are performed in background threads. This lock protects the
        # search id var for everyone and underscore vars for the search thread.
        # underscore and id vars.
        self._lock = Lock()
        self._searchId = -1
        self._searchAbortEvent = None
        self._pendingFlush = False
        self._oldTime = None
        self._oldStartTime = None
        self._oldCamName = None


    ###########################################################
    def abortProcessing(self):
        """Abort any processing, regardless of current state."""
        self._videoAvailTimer.Stop()
        self._videoLoadTimer.Stop()


    ###########################################################
    def toggleSortAscending(self):
        self.setSortAscending(not self._isAscending)


    ###########################################################
    def setSortAscending(self, shouldAscend):
        if self._isAscending != shouldAscend:
            self._isAscending = shouldAscend
            setFrontEndPref('isSortAscending', shouldAscend)
            self.update('sortResults')


    ###########################################################
    def isSortAscending(self):
        return self._isAscending


    ###########################################################
    def hasAudio(self):
        if self._dataMgr:
            return self._dataMgr.hasAudio()
        return False


    ###########################################################
    def resetSearch(self, doUpdate=True):
        """Reset search so that we have no results.

        NOTE: This is called at __init__ time, so don't do anything too
        sketchy...

        @param  doUpdate  If true, we'll send out an update; should only be
                          called with False by internal clients.
        """
        # Stop checking for available video changes...
        self._videoAvailTimer.Stop()

        # We haven't done a search yet...
        self._didSearch = False

        # A list of clips, each of which is a MatchingClipInfo object
        self._matchingClips = []

        # A list of time ranges:
        #   [(startMs, stopMs), (startMs2, stopMs2), ..., ... ]
        self._videoAvailTimes = []
        self._cacheCamera = None

        # Reset our location; start out as -1
        self._currentClipNum = -1

        # We won't start with a multiple selection
        self._multipleSelected = False
        self._selectedIds = []

        # This is where we entered the current clip at...
        self._enterClipAt = None

        # We store the "midnightMs" for the search here.  That's used for
        # drawing the timeline control...
        self._midnightMs = None

        # We'll keep track of start and end of current search...
        self._searchStartTime = None
        self._searchEndTime = None

        # Clear out anything related to loading video...
        self._resetVideoVariables(False, False)

        # Reset the current camera variable.
        self._currentSearchCamera = ""

        # Send the update if needed...
        if doUpdate:
            self.update('results')


    ###########################################################
    def _resetVideoVariables(self, wantPlay, doUpdate=True):
        """Reset anything associated with loaded video.

        This is an internal function used when we change video segments.  It's
        called by resetSearch() (self._disSearch will be False) and also by
        setCurrentClipNum().

        NOTE: This is called at __init__ time, so don't do anything too
        sketchy...

        @param  wantPlay  If True, we'll set play; else we'll unset play.
        @param  doUpdate  If true, we'll send out an update on 'videoSegment'.
        """
        # Stop any loading of video...
        self._videoLoadTimer.Stop()

        # This will be set to true when (if) the video load timer succeeds.
        self._isVideoLoaded = False

        # The current (relative) milliseconds in the clip, plus an image from
        # that time..
        self._currentMs = None
        self._img = None

        # The absolute ms of the start of the file containing self._img.
        self._fileStartMs = None

        # Whether or not we're currently in "play" mode.
        self._play = bool(wantPlay)

        # Info about the current clip.
        self._cameraName = None    # Name of camera it came from.
        self._startTime = -1       # Absolute start time of clip.
        self._stopTime = -1        # Absolute stop time of clip.
        self._playTime = -1        # Absolute time to start playing at in clip.

        # Keep track of what the request was; used for skipping to next clip.
        self._requestedFirstMs = -1
        self._requestedLastMs = -1

        if doUpdate:
            self.update('videoSegment')

        # Start loading if we actually have done a search; we do this even
        # if there are no clips so that we will eventually send a 'videoLoaded'
        # notification when we give up trying to load.
        if self._didSearch:
            self._videoLoadTimerRetries = 0
            self._videoLoadTimer.Start(1, True)


    ###########################################################
    def resetLocationInSegment(self):
        """Reset to the play location within the current video segment.

        This will send the 'ms' update, plus potentially the 'play' update.

        This function is a no-op if we haven't finished loading the video yet,
        since we'll automatically start at this location when we finish loading.
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        # Set the ms using our helper function...
        self.setCurrentAbsoluteMs(self._playTime)

        # Play if the user hasn't paused; this will send out a 'play' update...
        if not self._userPaused:
            self.setPlay(True, False)


    ###########################################################
    def setPlay(self, play, userReq=True, doUpdate=True):
        """Set the value of play.

        This will send the 'play' update if the value changes.

        @param  play      If true, we're playing; false is for paused.
        @param  userReq   If true, this is a user-requested pause (instead of
                          an implicit one).  That affects future auto-playing.
        @param  doUpdate  If true, we'll send out an update; should only be
                          called with False by internal clients.
                          NOTE: If False, won't set self._userPaused
        """
        # Make play into a real boolean (always exactly True or False)
        play = bool(play)

        # If we're being called by an external client, then it must have been
        # due to a user-requested pause.  Keep track of that.
        if userReq:
            self._userPaused = not play

        if play != self._play:
            self._play = play
            if doUpdate:
                self.update('play')


    ###########################################################
    def isPlaying(self):
        """Return the value of play.

        @return play  The value of play.
        """
        return self._play


    ###########################################################
    def getMatchingClips(self):
        """Get a list of matching clips.

        Each is a MatchingClipInfo object.

        @return matchingClips  A list of matching clips; see above.
        """
        return self._matchingClips


    ###########################################################
    def getNumMatchingClips(self):
        """Get the number of matching clips.

        This is shorthand for len(dataModel.getMatchingClips())

        @return numMatchingClips  The number of matching clips.
        """
        return len(self._matchingClips)


    ###########################################################
    def getCurrentClipNum(self):
        """Return an index into getMatchingClips().

        This is the clip number that we're currently looking at.

        @return currentClipNum  The current clip number.
        """
        return self._currentClipNum


    ###########################################################
    def setCurrentClipNum(self, clipNum, enterClipAt=None, allowWantPlay=True):
        """Go to the given clipNum; may be used for entering cache.

        This will update our listeners on 'videoSegment'; assuming you actually
        changed the clip.

        @param  clipNum         The clip number to go to; if not an int, means
                                that we're going into cache (so enterClipAt
                                should be non-None)
        @param  enterClipAt     The 'ms' that we want to enter the clip at; if
                                None, we'll enter at "playTime"
        @param  allowWantPlay   True if you wish to allow results model to
                                decide if video will be playing or not if the
                                video variables are reset. False if you wish to
                                force no playing.
        """
        if clipNum != self._currentClipNum:
            # Change the clip...
            self._currentClipNum = clipNum
            self._enterClipAt = enterClipAt

            # Do this after setting self._currentClipNum, so that the
            # SearchResultsList can properly figure out which clip was
            # selected when responding to the 'multipleSelected' update.
            self.setMultipleSelected(False, [clipNum])

            # Reset things associated with loaded video, since we haven't
            # loaded yet.  This will also start the video load thread running.
            self._resetVideoVariables(allowWantPlay and (not self._userPaused))
        elif enterClipAt is not None:
            self.setMultipleSelected(False, [clipNum])

            if not self._isVideoLoaded:
                self._enterClipAt = enterClipAt
            else:
                if (enterClipAt < self._requestedFirstMs) or \
                   (enterClipAt > self._requestedLastMs):
                    # Same clip number, but different part; this can happen
                    # if we're in a different slice of cache...
                    self._enterClipAt = enterClipAt

                    # Reset things associated with loaded video, since we haven't
                    # loaded yet.  This will also start the video load thread running.
                    self._resetVideoVariables(not self._userPaused)
                else:
                    self.setCurrentAbsoluteMs(enterClipAt)
        else:
            self.setMultipleSelected(False, [clipNum])



    ###########################################################
    def goToNextClip(self):
        """Switch to the next clip, chronologically."""

        assert self._currentClipNum < len(self._matchingClips)

        # If we're already at the end, this is a no-op...
        if self._currentClipNum >= (len(self._matchingClips) - 1):
            return

        self.setCurrentClipNum(int(math.floor(self._currentClipNum)) + 1)


    ###########################################################
    def goToPrevClip(self):
        """Switch to the next clip, chronologically."""

        assert self._currentClipNum < len(self._matchingClips)

        # If we're already at the beginning, this is a no-op...
        if self._currentClipNum <= 0:
            return

        self.setCurrentClipNum(int(math.ceil(self._currentClipNum)) - 1)


    ###########################################################
    def isCurrentClipMatching(self):
        """Return True if the current clip matched the search.

        @return didMatch  True if the current clip matched the search.
        """
        return self._currentClipNum == int(self._currentClipNum)


    ###########################################################
    def canPassClipBeginning(self):
        """Return True if we have video for going past the begin of this clip.

        @return canPassClipEnd  True if we can move past the begin of the clip.
        """
        return self.passClipBeginning(True)


    ###########################################################
    def canPassClipEnd(self, limitDistance=True):
        """Return True if we have video for going past the end of this clip.

        @param  limitDistance   If True only check for cache and clips within
                                _kAllowableSkip ms of the current video.
        @return canPassClipEnd  True if we can move past the end of the clip.
        """
        return self.passClipEnd(True, limitDistance)


    ###########################################################
    def passClipBeginning(self, dryRun=False):
        """Try to pass the beginning of the clip.

        This may move us into cache, or may move us into an adjacent clip.

        @param  dryRun          Don't actually move; just report whether it
                                would have worked.
        @return canPassClipEnd  True if we moved past the beginning of the clip.
        """
        # Shorthand...
        matchingClips = self._matchingClips
        clipNum = self._currentClipNum

        # Search clips first for adjacent ones...
        adjacentClipDistance = _kAllowableSkip + 1

        prevClipNum = int(math.ceil(clipNum)) - 1
        while prevClipNum >= 0:
            prevClip = matchingClips[prevClipNum]

            # When we find the next one for this camera, get the distance
            # and get out...
            if prevClip.camLoc == self._cameraName:
                adjacentClipDistance = (self._requestedFirstMs -
                                        prevClip.stopTime)
                break

            prevClipNum -= 1

        # If we have no cache, just see if the clip is close enough...
        if not self._videoAvailTimes:
            if -_kSlopMs <= adjacentClipDistance <= _kAllowableSkip:
                if not dryRun:
                    self.setCurrentClipNum(prevClipNum,
                                           self._requestedFirstMs -
                                           adjacentClipDistance)
                return True
            return False

        # See what video we can continue into...
        # ...note that if the clip we found above is the next video,
        # this will just be another way to find it...
        rangeNum = _findPlaceInRangeList(self._videoAvailTimes,
                                         self._requestedFirstMs - _kMinCacheMs)
        if rangeNum == int(rangeNum):
            # There is video right next to us...
            _, videoStopMs = self._videoAvailTimes[rangeNum]
            videoStopMs = min(self._requestedLastMs, videoStopMs)
            adjacentVideoDistance = (self._requestedLastMs - videoStopMs)
        else:
            # No video adjacent; find the prev section of video, bailing if
            # there isn't one...
            rangeNum = int(math.ceil(rangeNum)) - 1
            if rangeNum < 0:
                assert not (-_kSlopMs <= adjacentClipDistance <= _kAllowableSkip)
                return False
            _, videoStopMs = self._videoAvailTimes[rangeNum]
            adjacentVideoDistance = (self._requestedFirstMs - videoStopMs)

        if adjacentVideoDistance > _kAllowableSkip:
            # It's too far to be allowable...  # TODO: This actually happened when refreshing.  Why???
            assert not (-_kSlopMs <= adjacentClipDistance <= _kAllowableSkip)
            return False
        if -_kSlopMs <= adjacentClipDistance <= (adjacentVideoDistance + _kMinCacheMs):
            # We found the clip again, so go into the clip...
            if not dryRun:
                self.setCurrentClipNum(prevClipNum,
                                       self._requestedFirstMs -
                                       adjacentClipDistance)
            return True

        enteredCacheAt = self._requestedFirstMs - adjacentVideoDistance

        # We got it; do the move if we're not a dry run...
        if not dryRun:
            # Change to a floating point clip number to indicate that we're
            # between clips...
            self.setCurrentClipNum(math.ceil(clipNum) - .5, enteredCacheAt)

        # Return success...
        return True


    ###########################################################
    def passClipEnd(self, dryRun=False, limitDistance=True):
        """Try to pass the end of the clip.

        This may move us into cache, or may move us into an adjacent clip.

        @param  dryRun          Don't actually move; just report whether it
                                would have worked.
        @param  limitDistance   If True only move ahead _kAllowableSkip at max.
        @return canPassClipEnd  True if we moved past the end of the clip.
        """
        # Force limitDistance if we are doing an unbounded search (import mode)
        # ...this is because clips can be out of time order, and logic below
        # doesn't handle that.
        if self._midnightMs is None:
            limitDistance = True

        # Shorthand...
        matchingClips = self._matchingClips
        clipNum = self._currentClipNum
        numMatchingClips = len(matchingClips)

        # Search clips for first adjacent one in the same camera...
        nextClipNum = int(math.floor(clipNum)) + 1
        while nextClipNum < numMatchingClips:
            nextClip = matchingClips[nextClipNum]

            # When we find the next one for this camera, get the distance
            # and get out...
            if nextClip.camLoc == self._cameraName:
                adjacentClipDistance = (nextClip.startTime -
                                        self._requestedLastMs)
                break

            nextClipNum += 1
        else:
            # Put in a bogus value; no more clips for this camera found...
            adjacentClipDistance = _kAllowableSkip + 1
            if not limitDistance:
                adjacentClipDistance = None

        # If we have no cache, just see if the clip is close enough...
        if not self._videoAvailTimes:
            if adjacentClipDistance is None:
                return False
            if (not limitDistance) or \
               (-_kSlopMs <= adjacentClipDistance <= _kAllowableSkip):
                if not dryRun:
                    self.setCurrentClipNum(nextClipNum,
                                           self._requestedLastMs +
                                           adjacentClipDistance)
                return True
            return False

        # See what video we can continue into...
        # ...note that if the clip we found above is the next video,
        # this will just be another way to find it...
        rangeNum = _findPlaceInRangeList(self._videoAvailTimes,
                                         self._requestedLastMs + _kMinCacheMs)
        if rangeNum == int(rangeNum):
            # There is video right next to us...
            videoStartMs, _ = self._videoAvailTimes[rangeNum]
            videoStartMs = max(self._requestedLastMs, videoStartMs)
            adjacentVideoDistance = (videoStartMs - self._requestedLastMs)
        else:
            # No video adjacent; find the next section of video, bailing if
            # there isn't one...
            rangeNum = int(math.floor(rangeNum)) + 1
            if rangeNum >= len(self._videoAvailTimes):
                if limitDistance:
                    assert not (-_kSlopMs <= adjacentClipDistance <= _kAllowableSkip)
                return False
            videoStartMs, _ = self._videoAvailTimes[rangeNum]
            adjacentVideoDistance = (videoStartMs - self._requestedLastMs)

        if limitDistance and adjacentVideoDistance > _kAllowableSkip:
            # It's too far to be allowable...
            return False
        if (adjacentClipDistance is not None) and \
           (-_kSlopMs <= adjacentClipDistance <= (adjacentVideoDistance+_kMinCacheMs)):
            # We found the clip again, so go into the clip...
            if not dryRun:
                self.setCurrentClipNum(nextClipNum,
                                       self._requestedLastMs +
                                       adjacentClipDistance)
            return True

        enteredCacheAt = self._requestedLastMs + adjacentVideoDistance

        # We got it; do the move if we're not a dry run...
        if not dryRun:
            # Change to a floating point clip number to indicate that we're
            # between clips...
            self.setCurrentClipNum(math.floor(clipNum) + .5, enteredCacheAt)

        # Return success...
        return True


    ###########################################################
    def setCurrentRelativeMs(self, ms, doUpdate=True):
        """Set the current ms, relative to the start of the current clip.

        Will send an update to listeners with 'ms' assuming ms changed.

        ...note that the ms that's actually set might not be exactly what's
        passed in--it will be adjusted to the ms of a valid frame.

        @param  ms  The new ms value (in relative ms).
        @param  doUpdate  If true, we'll send out an update; should only be
                          called with False by internal clients.
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        if ms != self._currentMs:
            # Cache the image...
            self._img = self._dataMgr.getFrameAt(self._startTime + ms)
            self._fileStartMs = self._dataMgr.getFileStartMs()

            # Get the official ms from the data manager...
            ms = self._dataMgr.getCurFrameOffset()

            # Re-check the ms; what the client asked for may be the same as
            # we had before if there was just rounding errors...
            if ms != self._currentMs:
                self._currentMs = ms
                if doUpdate:
                    self.update('ms')

                # Restart playing if we need to...
                if not self._userPaused:
                    duration = self.getCurrentClipDuration()
                    if ms != duration-1:
                        self.setPlay(True, False)


    ###########################################################
    def reloadCurrentFrame(self):
        """Reload the current frame.

        This is called when we change between debug mode and non-debug mode,
        since we want to re-generate the image. This is also called by the
        OnSize function in SearchResultsPlaybackPanel if the video is paused.
        """
        # Nothing if no video loaded...
        if not self._isVideoLoaded:
            return

        # Re-get the image; that shouldn't change our location...
        self._img = self._dataMgr.getFrameAt(self._startTime + self._currentMs)
        assert self._dataMgr.getCurFrameOffset() == self._currentMs
        assert self._dataMgr.getFileStartMs() == self._fileStartMs

        # Let people know that the video changed...
        self.update('ms')


    ###########################################################
    def getCurrentRelativeMs(self):
        """Return the current ms, relative to the start of the current clip.

        @return currentMs  The current ms (in relative ms).
        """
        return self._currentMs


    ###########################################################
    def getNextRelativeMs(self):
        """Return the ms of the next frame, relative to the start of the clip.

        @return nextMs  The next frame ms (in relative ms).
        """
        assert self._currentMs == self._dataMgr.getCurFrameOffset()
        return self._dataMgr.getNextFrameOffset()


    ###########################################################
    def goToNextFrame(self):
        """Go to the next frame of the video.

        Will send out the 'ms' notificatoin, assuming ms changed.  May also
        send out the 'play' notification if we hit the end of the video.
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        duration = self.getCurrentClipDuration()

        img = self._dataMgr.getNextFrame()
        if img is None:
            nextFrameOffset = -1
        else:
            self._img = img
            self._fileStartMs = self._dataMgr.getFileStartMs()
            nextFrameOffset = self._dataMgr.getNextFrameOffset()

        if nextFrameOffset == -1:
            # Force ms to be exactly the duration if we're at the end; this
            # avoids any rounding errors...
            ms = duration - 1
        else:
            ms = self._dataMgr.getCurFrameOffset()
            assert ms < duration

        # Check the ms; what the client asked for may be the same as
        # we had before if there was just rounding errors...
        if ms != self._currentMs:
            self._currentMs = ms
            self.update('ms')

        # If we've hit the end, ensure we're paused...
        if ms >= (duration - 1):
            assert ms == (duration - 1)
            self.setPlay(False, False)


    ###########################################################
    def goToPrevFrame(self):
        """Go to the previous frame of the video.

        Will send out the 'ms' notification, assuming ms changed.  May also
        send out the 'play' notification if we hit the end of the video.
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        img = self._dataMgr.getPrevFrame()
        if img is None:
            ms = 0
        else:
            self._img = img
            self._fileStartMs = self._dataMgr.getFileStartMs()
            ms = self._dataMgr.getCurFrameOffset()

            # TODO: Will ms be exactly 0 at beginning?  Do we need to do
            # extra work like in goToNextFrame()?

        # Check the ms; what the client asked for may be the same as
        # we had before if there was just rounding errors...
        if ms != self._currentMs:
            self._currentMs = ms
            self.update('ms')

        # If the user never paused, start playing (this is a little
        # weird, but is consistant with elsewhere).
        if not self._userPaused:
            self.setPlay(True, False)


    ###########################################################
    def goForwardXMs(self, x):
        """Skip forward x milliseconds.

        This will send out the 'ms' notification, assuming ms changed.  May
        also send out the 'play' notification if we hit the end.

        @param  x  The number of milliseconds to move forward.
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        duration = self.getCurrentClipDuration()

        # Figure out old and new ms...
        oldMs = self._currentMs
        newMs = oldMs + x

        # Try to set the new ms, but don't sent an update yet...
        self.setCurrentRelativeMs(min(newMs, duration-1), False)

        # Check if our desired target time was actually past this clip.
        if newMs > duration-1 and self.passClipEnd():
            # If we moved clips return.  We don't need to send an 'ms' update,
            # as we will be recieving a video loaded update instead.
            return

        # Check to see where we ended up.  If we didn't move, just do a
        # goToNextFrame(), which will send an update.  If we did move,
        # send the update ourselves and potentially pause if we've reached
        # the end...
        if self._currentMs == oldMs:
            self.goToNextFrame()
        else:
            self.update('ms')
            if self._currentMs == duration-1:
                self.setPlay(False, False)


    ###########################################################
    def goBackwardXMs(self, x):
        """Skip backward x milliseconds.

        This will send out the 'ms' notification, assuming ms changed.

        @param  x  The number of milliseconds to move backward.
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        # Figure out old and new ms...
        oldMs = self._currentMs
        newMs = oldMs - x

        # Try to set the new ms, but don't sent an update yet...
        self.setCurrentRelativeMs(max(newMs, 0), False)

        # If our target time was before this clip, try to move back.
        if newMs < 0 and self.passClipBeginning():
            # If we moved clips return.  We don't need to send an 'ms' update,
            # as we will be recieving a video loaded update instead.
            return

        # Check to see where we ended up.  If we didn't move, just do a
        # goToPrevFrame(), which will send an update.  If we did move,
        # send the update ourselves...
        if self._currentMs == oldMs:
            self.goToPrevFrame()
        else:
            self.update('ms')


    ###########################################################
    def goToPrevStartTime(self):
        """Go to the prev start time, or beginning of the clip if none.

        This will send out the 'ms' notification, assuming ms changed.
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        # Get relative start times; empty list if in cache...
        startTimes = sorted(self.getStartTimes())

        # Find the new index to go to based on bisecting the start times...
        newIndex = bisect.bisect_left(startTimes, self._currentMs) - 1

        # Keep track of old ms so we can be sure we moved...
        oldMs = self._currentMs

        # We'll try to move to the startTime specified by newIndex until
        # we actually move...
        while newIndex >= 0:
            # Move, but don't send the update yet...
            self.setCurrentRelativeMs(startTimes[newIndex], False)

            # If we moved, then send out an update.  We're done.
            if self._currentMs < oldMs-_kMsPrevEventTolerance:
                self.update('ms')
                return

            # We didn't move; try to go one index back...
            newIndex -= 1

        # Got to the beginning.  Set relative ms to 0.
        assert newIndex == -1
        self.setCurrentRelativeMs(0)


    ###########################################################
    def goToNextStartTime(self):
        """Go to the next start time, or end of the clip if none.

        This will send out the 'ms' notification, assuming ms changed.  May
        also send out the 'play' notification if we hit the end.
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        # Get relative start times...
        startTimes = sorted(self.getStartTimes())
        numStartTimes = len(startTimes)

        # Find the new index to go to based on bisecting the start times...
        newIndex = bisect.bisect_right(startTimes, self._currentMs)

        # Keep track of old ms so we can be sure we moved...
        oldMs = self._currentMs

        # We'll try to move to the startTime specified by newIndex until
        # we actually move...
        while newIndex < numStartTimes:
            # Move, but don't send the update yet...
            self.setCurrentRelativeMs(startTimes[newIndex], False)

            # If we moved, then send out an update.  We're done.
            if self._currentMs != oldMs:
                self.update('ms')
                return

            # We didn't move; try to go one index forward...
            newIndex += 1

        # Got to the beginning.  Set relative ms to 0.
        assert newIndex == numStartTimes
        self.setCurrentRelativeMs(self.getCurrentClipDuration() - 1)
        self.setPlay(False, False)


    ###########################################################
    def setCurrentAbsoluteMs(self, ms):
        """Set the current ms, in absolute ms.

        Will send an update to listeners with 'ms' assuming ms changed.

        @param  ms  The new ms value (in absolute ms).
        """
        # This doesn't do anything if we're not yet loaded...
        if not self._isVideoLoaded:
            return

        if (self._startTime == -1):
            assert False, "Can't set absolute ms if no start time"
            return
        self.setCurrentRelativeMs(ms - self._startTime)


    ###########################################################
    def getCurrentAbsoluteMs(self):
        """Return the current ms.

        @return currentMs  The current ms (in absolute ms).
        """
        if (self._currentMs is None) or (self._startTime == -1):
            return None
        return self._currentMs + self._startTime


    ###########################################################
    def getCurrentImg(self):
        """Return the current image.

        @return currentImg  The current image.
        """
        return self._img


    ###########################################################
    def getCurrentFileRelativeMs(self):
        """Get the current ms relative to the current file.

        @return fileRelativeMs  The ms relative to the current file.
        """
        absMs = self.getCurrentAbsoluteMs()
        if (self._fileStartMs == -1) or (absMs is None):
            # Don't expect this, but be paranoid...
            assert False, "Bad state in getCurrentFileRelativeMs"
            return 0
        else:
            return absMs - self._fileStartMs


    ###########################################################
    def didSearch(self):
        """Return True if a search was performed since the last reset.

        @return  didSearch  True if a search was performed.
        """
        return self._didSearch


    ###########################################################
    def isVideoLoaded(self):
        """Return True if video has been loaded.

        @return  isLoaded  True if video is currently loaded.
        """
        return self._isVideoLoaded


    ###########################################################
    def getCurrentClipDuration(self):
        """Get the duration of the current clip, in ms.

        @return clipDurationMs  The clip duration, in ms; 0 if no clip now.
        """
        return (self._stopTime - self._startTime) + 1


    ###########################################################
    def getCurrentClipStart(self):
        """Get the start ms of the current clip.

        @return clipStartMs  The start ms of the current clip; -1 if no clip.
        """
        return self._startTime


    ###########################################################
    def getCurrentClipStop(self):
        """Get the stop ms of the current clip.

        @return clipStopMs  The stop ms of the current clip; -1 if no clip.
        """
        return self._stopTime


    ###########################################################
    def getCurrentClipPlayTime(self):
        """Get the playTime (in ms) of the current clip.

        @return playTimeMs  The playTime of the current clip; -1 if no clip.
        """
        return self._playTime


    ###########################################################
    def getCurrentCameraName(self):
        """Get the camera name associated with the current clip.

        @return clipCameraName  The camera name associated with the clip.
        """
        return self._cameraName


    ###########################################################
    def getAvailableVideoRanges(self):
        """Returns ranges of video that are available.

        Note: if we have done a search over multiple cameras, this will be
        empty.

        @return ranges     A list of ranges that looks like:
                             [(firstAvailMs, lastAvailMs), ..., ..., ...]
        """
        return self._videoAvailTimes


    ###########################################################
    def getMidnightMs(self):
        """Return midnight for whatever day the search happened on.

        @return midnightMs  The milliseconds of midnight.
        """
        return self._midnightMs


    ###########################################################
    def getStartTimes(self):
        """Return the start times for the current clip.

        @return startTimes  A list of start times, relative to the start of
                            the clip.
        """
        # Only start times if we're in a matching clip...
        if (self._currentClipNum == int(self._currentClipNum)) and \
           (self._currentClipNum != -1):

            absStartTimes = self._matchingClips[self._currentClipNum].startList

            clipAbsStartTime = self._startTime
            clipDuration = self.getCurrentClipDuration()

            relStartTimes = [max(0, min(clipDuration-1, t-clipAbsStartTime))
                             for t in absStartTimes]
            return relStartTimes

        # Non-matching clip, just return empty list...
        return []


    ###########################################################
    def setChangingRapidly(self, changingRapidly):
        """Set whether or not we're changing rapidly.

        We use this to keep the play timer from running while the mouse is down
        in the slider or the time bar.

        This will send an update on 'changingRapidly' if this call changes
        the current value.

        @param  changingRapidly  The new value for changingRapidly.
        """
        self.setPlay(False, True)
        if changingRapidly != self._changingRapidly:
            self._changingRapidly = changingRapidly
            self.update('changingRapidly')


    ###########################################################
    def isChangingRapidly(self):
        """Get the current value of changingRapidly.

        @return changingRapidly  See setChangingRapidly().
        """
        return self._changingRapidly


    ###########################################################
    def doSearch(self, query, cameraList, searchDate, flushFunc):
        """Do a search.

        Note: you don't need to call resetSearch() first; this implicitly
        resets the search (though listeners will only get one update for the
        whole process).

        @param  query       The query to search with.
        @param  cameraList  A list of cameras to search on.
        @param  searchDate  A datetime object of the day to search on; may be
                            None if no date is being used in search.
        @param  flushFunc   A function that takes a camera name, to be used
                            for flushing the cameras if necessary.
        """
        self._lock.acquire()

        try:
            # If there is an existing search tell it to abort.
            if self._searchAbortEvent is not None:
                self._searchAbortEvent.set()

            # Keep track of previous camera location / time to try to get back
            # there...
            # Only do this if searchId == -1, otherwise we're on a search
            # interrupting a previous search and these would be junk values.
            if self._searchId == -1:
                self._oldTime = self.getCurrentAbsoluteMs()
                self._oldStartTime = self._searchStartTime
                self._oldCamName = self.getCurrentCameraName()

            self._searchAbortEvent = delayedresult.AbortEvent()
            self._searchId = time.time()
            self._pendingFlush = False

            self.update('searching')

            # Reset, but don't send an update yet; this gets us into a nice
            # and predictable state...
            self.resetSearch(False)

            self._dataMgr.setVideoDebugLines(query.getVideoDebugLines())

            self._searchStartTime, self._searchEndTime, self._midnightMs = \
                getSearchTimes(searchDate)[:3]

            delayedresult.startWorker(self._delayedSearchDone,
                    self._delayedSearch, jobID=self._searchId,
                    wargs=(query, cameraList, searchDate, flushFunc,
                        self._searchId, self._searchAbortEvent))
        finally:
            self._lock.release()


    ###########################################################
    def _delayedSearch(self, query, cameraList, searchDate, flushFunc,
            searchId, abortEvent):
        """Do a search.

        @param  query       The query to search with.
        @param  cameraList  A list of cameras to search on.
        @param  searchDate  A datetime object of the day to search on; may be
                            None if no date is being used in search.
        @param  flushFunc   A function that takes a camera name, to be used
                            for flushing the cameras if necessary.
        @param  searchId    A uid for this search.
        @param  abortEvent  An event that will be set if search should abort.
        """
        timeLogger = TimerLogger("searching")
        resultsCount = 0

        try:
            dataMgrPath, clipMgrPath, videoDir = self._dataMgr.getPaths()
            logger = getLogger(kFrontEndLogName)
            clipMgr = ClipManager(logger)
            clipMgr.open(clipMgrPath)
            dataMgr = DataManager(logger, clipMgr, videoDir)
            dataMgr.open(dataMgrPath)

            # key off config to determine how far the clips can be apart and still be merged
            searchConfig = SearchConfig()

            # Perform the search and retrieve the matching clips.
            processedDict, matchingClips = getSearchResults(query, cameraList,
                    searchDate, dataMgr, clipMgr, searchConfig, flushFunc,
                    self._updateSearchProgress, abortEvent)

            # Get available video too, if one camera...
            videoAvailTimes = []
            if len(cameraList) == 1:
                # With one camera, we show the real info...
                videoAvailTimes = clipMgr.getTimesFromLocation(cameraList[0],
                        self._searchStartTime, self._searchEndTime)

            currentClipNum = self._currentClipNum
            enterClipAt = self._enterClipAt
            if matchingClips:
                if searchDate is not None:
                    # Normal clips; sort the result list by file start time
                    matchingClips.sort(
                        key=operator.attrgetter(OB_ASID("startTime"))
                    )
                else:
                    # The searchDate is None, which only happens for imported clips.
                    # Fill in filename, then sort by that...  TODO: Optimize?
                    # We'll delete anything that doesn't have a clip yet.  User can
                    # refresh to get them...
                    for i in xrange(len(matchingClips)-1, -1, -1):
                        matchingClip = matchingClips[i]

                        # We'll assume that the startList[0] is the best
                        # representative time to use for the file name...
                        pathName = clipMgr.getFileAt(
                            matchingClip.camLoc, matchingClip.startList[0]
                        )
                        if pathName is None:
                            del matchingClips[i]
                        else:
                            matchingClip.filename = os.path.basename(pathName)
                            matchingClip.fileStartMs, _ = \
                                clipMgr.getFileTimeInformation(pathName)
                    matchingClips.sort(
                        key=operator.attrgetter(OB_ASID('filename'))
                    )

                # Set the current clip number; default is last clip, but we'll
                # be better if we can find our old selection (if still same day)...
                # TODO: do we need to use binary search to be faster?
                currentClipNum = 0
                if (searchDate is not None)                and \
                   (self._oldStartTime == self._searchStartTime) and \
                   (self._oldTime is not None):

                    bestClipNum = None

                    # Something really big!
                    bestDistance = (self._searchEndTime-self._searchStartTime) + 1

                    # Selection rule is like this: If we have a perfect match on
                    # same camera, choose it; else pick the closest one across any
                    # camera.
                    for i, clipInfo in enumerate(matchingClips):
                        cam = clipInfo.camLoc
                        start = clipInfo.startTime
                        stop = clipInfo.stopTime
                        play = clipInfo.playStart

                        if (cam == self._oldCamName) and (start <= self._oldTime <= stop):
                            currentClipNum = i
                            break
                        else:
                            distance = abs(play - self._oldTime)
                            if distance < bestDistance:
                                bestClipNum = i
                                bestDistance = distance
                    else:
                        if bestClipNum is not None:
                            currentClipNum = bestClipNum
            elif videoAvailTimes:
                # No clips, but cache!
                currentClipNum = -0.5
                enterClipAt = videoAvailTimes[0][0]

            self._lock.acquire()
            try:
                abortEvent()
                if self._searchId == searchId:
                    self._matchingClips = matchingClips
                    self._processedDict = processedDict
                    self._videoAvailTimes = videoAvailTimes

                    self._currentClipNum = currentClipNum
                    self._enterClipAt = enterClipAt

                    if len(cameraList) == 1:
                        self._cacheCamera = cameraList[0]

                        # If we have a flush pending, we'll need to retry
                        # loading the info about available video. We'll do it in
                        # _delayedSearchDone if we're still the active search.
                        if searchDate == datetime.date.today():
                            self._pendingFlush = True

                    resultsCount = len(self._matchingClips)
            finally:
                self._lock.release()

        except delayedresult.AbortedException:
            pass
        except Exception, e:
            logger.warning("Search failed: " + traceback.format_exc())

        finally:
            logger.debug(timeLogger.status() + ": " +
                            str(resultsCount) + " results loaded");
            dataMgr.close()
            clipMgr.close()


    ###########################################################
    def _updateSearchProgress(self, currentCamera):
        """Send search progress updates if necessary.

        @param  currentCamera  The camera being searched.
        """
        self._currentSearchCamera = currentCamera


    ###########################################################
    def getCurrentSearchCamera(self):
        """Return the name of the camera being searched on.

        @return  currentCamera  The camera being searched or an empty string.
        """
        return self._currentSearchCamera


    ###########################################################
    def _delayedSearchDone(self, delayedResultObj):
        """Called when a background search is complete.

        @param  delayedResultObj  The delayedresult object the search was
                                  executed in.
        """
        self._lock.acquire()
        try:
            if self._searchId == delayedResultObj.getJobID():
                if self._pendingFlush:
                    self._videoAvailTimerRechecks = 0
                    self._videoAvailTimer.Start(_kVideoAvailInitRecheckMs, True)

                self._searchId = -1
                self._searchAbortEvent = None
                self._didSearch = True
                self._pendingFlush = False

                # Indicate that our results are ready...
                self.update('results')
                self._currentSearchCamera = ""

                # Start the load of video going...
                self._videoLoadTimerRetries = 0
                self._videoLoadTimer.Start(1, True)
        finally:
            self._lock.release()


    ###########################################################
    def OnVideoAvailTimer(self, event):
        """Look for changes in what video is available.

        @param  event  The timer event (ignored).
        """
        videoAvailTimes = \
            self._clipMgr.getTimesFromLocation(self._cacheCamera,
                                               self._searchStartTime,
                                               self._searchEndTime)

        if videoAvailTimes != self._videoAvailTimes:
            self._videoAvailTimes = videoAvailTimes
            self.update('videoAvail')

        self._videoAvailTimerRechecks += 1
        if (self._videoAvailTimerRechecks < _kVideoAvailNumRechecks):
            self._videoAvailTimer.Start(_kVideoAvailSubsequentRecheckMs, True)


    ###########################################################
    def getCurrentFilename(self):
        """Return the filename associated with the current clip, or None.

        This will only be non-None for imported cameras.

        @return filename  The current filename, or "" if unknown.
        """
        clipInfo, _ = self._getMatchingClipOrCache()
        if clipInfo is None:
            return ""
        else:
            return clipInfo.filename

    ###########################################################
    def reloadCurrentClip(self):
        """ Reload the clip at current position.
            Useful, for example, when our markup model has changed

        """
        if not self._isVideoLoaded:
            return
        currentTime = self._startTime + self._currentMs
        if self._loadClip(currentTime):
            self.update('ms')


    ###########################################################
    def OnVideoLoadTimer(self, event):
        """Attempt to load a video.

        @param  event  The timer event (ignored).
        """
        if self._loadClip(None):
            self.update('videoLoaded')


    ###########################################################
    def _loadClip(self, offset):
        """ Load current clip at optionally specified offset

        @param offset   Playback position to load the clip at.
        """
        clipInfo, matchingClipNum = self._getMatchingClipOrCache()
        if (clipInfo is None) or \
           (self._videoLoadTimerRetries > _kMaxVideoLoadTimerRetries):

            # Give up and call it loaded, even though it isn't...
            # ...note that isVideoLoaded() still returns False...
            return True

        class _FailedToLoadException(Exception): pass
        res = False;
        try:
            camLoc = clipInfo.camLoc
            firstMs = clipInfo.startTime
            lastMs = clipInfo.stopTime
            playMs = clipInfo.playStart if offset is None else offset
            objList = clipInfo.objList

            self._startTime, self._stopTime = self._dataMgr.openMarkedVideo(
                                    camLoc, firstMs, lastMs, playMs, objList,
                                    self._desiredVideoSize, True, True)

            if self._startTime == -1:
                raise _FailedToLoadException()

            # Keep track of real play ms...
            self._playTime = min(self._stopTime, max(self._startTime, playMs))

            # Adjust to enterClipAt if needed
            if self._enterClipAt is not None:
                playMs = min(self._stopTime, max(self._startTime,
                                                 self._enterClipAt))

            # Obtain information about the clip
            self._cameraName = camLoc
            self._img = self._dataMgr.getFrameAt(playMs)

            if self._img is None:
                # Try to handle case where getFrameAt failed (untested).
                # TODO: Do we need to log this?
                raise _FailedToLoadException()

            self._currentMs = self._dataMgr.getCurFrameOffset()
            self._fileStartMs = self._dataMgr.getFileStartMs()

            if (matchingClipNum is not None):
                # If it's a matching clip, update the entry in our table to
                # be exact times.  This fixes up problems that can come up when
                # there is not continuous video behind one of our matching
                # clips--once you visit it once, we'll shorten it and you can
                # get to the non-continuous data in cache.
                self._matchingClips[matchingClipNum].startTime = self._startTime
                self._matchingClips[matchingClipNum].stopTime  = self._stopTime
                self._matchingClips[matchingClipNum].playTime = self._playTime

                # Make requested times the adjusted times.  TODO: Do we even
                # need requested times at all, or can we always use start/stop?
                self._requestedFirstMs = self._startTime
                self._requestedLastMs = self._stopTime
            else:
                self._requestedFirstMs, self._requestedLastMs = firstMs, lastMs

            self._isVideoLoaded = True

            res = True
        except _FailedToLoadException:
            # Send a bogus 'videoLoaded' on the first retry; we'll send another
            # when we actually succeed.
            if self._videoLoadTimerRetries == 0:
                res = True

            # Retries only make sense if we're trying to load a recent clip,
            # which may still be flushing to disk
            if clipInfo.stopTime + _kVideoLoadRetryPeriod > int(time.time()*1000):
                self._videoLoadTimerRetries += 1
                self._videoLoadTimer.Start(500, True)
        return res


    ###########################################################
    def _getMatchingClipOrCache(self):
        """Returns info for the given clipNum, which might be in cache.

        @return clipInfo  A tuple like what is stored in matchingClips.
        @return clipNum   If this was a matching clip, we'll return the clip
                          number; else returns None.
        """
        clipNum = self._currentClipNum
        matchingClips = self._matchingClips
        numMatchingClips = len(matchingClips)

        # Catch negative clip numbers that are integers so we don't get a bogus
        # index of matchingClips.
        if clipNum <= -1:
            return None, None

        try:
            # Try to index with the clip number; this will fail if the
            # current clip number is non-integral.
            clipInfo = matchingClips[clipNum]
        except TypeError:
            # If we got an index error above and we didn't enter the cache,
            # return failure.  This could happen if the clip number is too big.
            if self._enterClipAt is None:
                return None, None

            # We failed; self._currentClipNum must be a float, which means we're
            # in cache...
            rangeNum = _findPlaceInRangeList(self._videoAvailTimes,
                                             self._enterClipAt)
            if rangeNum != int(rangeNum):
                return None, None

            startTime, stopTime = self._videoAvailTimes[rangeNum]

            # Trim with the nearest clips...
            prevClipNum = int(math.floor(clipNum))
            nextClipNum = int(math.ceil(clipNum))
            if prevClipNum >= 0:
                prevClip = matchingClips[prevClipNum]
                prevStartTime = prevClip.startTime
                prevStopTime = prevClip.stopTime
                prevFilename = prevClip.filename
                prevFileStartMs = prevClip.fileStartMs

                # If this is True, the entry point is part of (or close to) the
                # previous clip...
                isPartOfPrev = (prevStartTime-_kSlopMs) <= \
                               self._enterClipAt        <= \
                               (prevStopTime+_kSlopMs)
            else:
                prevStartTime, prevStopTime = None, None
                isPartOfPrev = False
            if nextClipNum < numMatchingClips:
                nextClip = matchingClips[nextClipNum]

                nextStartTime = nextClip.startTime
                nextStopTime = nextClip.stopTime
                nextFilename = nextClip.filename
                nextFileStartMs = nextClip.fileStartMs

                # If this is True, the entry point is part of (or close to) the
                # next clip...
                isPartOfNext = (nextStartTime-_kSlopMs) <= \
                                self._enterClipAt <= \
                               (nextStopTime+_kSlopMs)
            else:
                nextStartTime, nextStopTime = None, None
                isPartOfNext = False

            # Look for out of order clips; this happens in 'import' mode because
            # we sort by filename.  If we see out of order clips, we'll ignore
            # the one that's not relevant...
            if (prevStopTime is not None) and (nextStartTime is not None) and \
               (nextStartTime < prevStopTime):

                if isPartOfPrev:
                    # Where we are is part of previous; don't chop by next...
                    nextStartTime = None
                elif isPartOfNext:
                    # Were we are is part of next; don't chop by previous...
                    prevStopTime = None
                else:
                    # Where we are is part of neither.  Don't chop...
                    nextStartTime = None
                    prevStopTime = None

            if prevStopTime is not None:
                startTime = max(startTime, prevStopTime)
            if nextStartTime is not None:
                stopTime = min(stopTime, nextStartTime)

            # Try to get filename and fileStartMs, which is only used for
            # imported clips.  Note that in imported clips, there are always
            # large gaps between files, so it's impossible that "isPartOfPrev"
            # and "isPartOfNext" will both be true if the filename is different.
            filename = ""
            fileStartMs = None
            if isPartOfPrev:
                filename = prevFilename
                fileStartMs = prevFileStartMs
            if isPartOfNext:
                assert (not filename) or (filename == nextFilename), \
                       "If prev and next both provide filename, it must match!"
                filename = nextFilename
                fileStartMs = nextFileStartMs

            previewMs = startTime + ((stopTime - startTime) / 2)
            clipInfo = MatchingClipInfo(self._cacheCamera, startTime, stopTime,
                                        startTime, previewMs, [], [], False,
                                        filename, fileStartMs)

            # Set clipNum to None to indicate that this wasn't a matching clip.
            clipNum = None

        return clipInfo, clipNum


    ###########################################################
    def getProcessedInfoForLocation(self, cameraLocation):
        """Return what has been processed for the given location.

        @param  cameraLocation      The location to look at.
        @return highestProcessedMs  The highest processed ms, or 0.
        @return highestTaggedMs     The highest tagged ms, or 0.
        """
        return self._processedDict.get(cameraLocation, (0,0))


    ###########################################################
    def setMultipleSelected(self, multipleSelected, selectedIds):
        """Return what has been processed for the given location.

        @param  multipleSelected  True if multiple clips are selected.
        @param  selectedIds       A list of the selected ids.
        """
        self._selectedIds = selectedIds
        if self._multipleSelected != multipleSelected:
            self._multipleSelected = multipleSelected
            self.update('multipleSelected')


    ###########################################################
    def getMultipleSelected(self):
        """Return what has been processed for the given location.

        @return multipleSelected  True if multiple clips are selected.
        """
        return self._multipleSelected


    ###########################################################
    def getSelectedIds(self):
        """Retrieve the currently selected clip ids.

        @return clipIds  The currently selected clip ids.  Returns the empty
                         list if there is no current selection.
        """
        if self._multipleSelected:
            return self._selectedIds
        elif self._currentClipNum == -1:
            return []
        return [self._currentClipNum]


    ###########################################################
    def getClipInformation(self, clipNum):
        """Retrieve information about a specific clip.

        Note: This does not work for cache clips.

        @param  clipNum         The clip number.
        @return cameraLocation  The location at which the clip was recorded.
        @return startMs         The absolute ms of the clip start.
        @return stopMs          The absolute ms of the clip stop.
        """
        if (clipNum != int(clipNum)) or \
           not (-1 < clipNum < len(self._matchingClips)):
            return None, -1, -1

        clipInfo = self._matchingClips[clipNum]
        return clipInfo.camLoc, clipInfo.startTime, clipInfo.stopTime


    ###########################################################
    def setVideoSize( self, videoSize ):
        """Set the size frames should be returned in.

        @param  videoSize  The requested video size.
        """
        self._desiredVideoSize  = videoSize
        self._dataMgr.updateVideoSize( videoSize )



###########################################################
def _findPlaceInRangeList(rangeList, x):
    """Find the range that x lives in in a list of ranges.

    Note that ranges are _inclusive_ (not like normal python ranges).  This
    will do a binary search (though in python code), so it should be lg(n)
    speed.

    # Basic positive tests..
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 1000)
    0
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 1100)
    0
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 2000)
    0
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 2100)
    1
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 2400)
    1

    # Basic negative tests...
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 999)
    -0.5
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 2001)
    0.5
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 2050)
    0.5
    >>> print _findPlaceInRangeList([(1000, 2000), (2100, 2400)], 2500)
    1.5

    # Stress test a bit...
    >>> [_findPlaceInRangeList([(1,2), (4,5), (7,8), (10,11)], i) for i in xrange(13)]
    [-0.5, 0, 0, 0.5, 1, 1, 1.5, 2, 2, 2.5, 3, 3, 3.5]
    >>> [_findPlaceInRangeList([(1,2), (4,5), (7,8)], i) for i in xrange(10)]
    [-0.5, 0, 0, 0.5, 1, 1, 1.5, 2, 2, 2.5]

    # Special case of empty list: returns 0.5
    >>> print _findPlaceInRangeList([], 100)
    0.5

    @param  x  The number to look for in the range list.
    @return i  The index into rangeList where x would live, or None.
    """
    i = 0
    rangeLen = len(rangeList)

    approx = .5

    while rangeLen > 0:
        halfway = i + rangeLen // 2
        start, end = rangeList[halfway]
        if x < start:
            rangeLen = rangeLen // 2
            approx = halfway - .5
        elif x > end:
            newI = halfway+1
            rangeLen -= (newI - i)
            i = newI
            approx = halfway + .5
        else:
            return halfway

    return approx


##############################################################################
def test_main():
    """Contains various self-test code."""
    import doctest
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
