#!/usr/bin/env python

#*****************************************************************************
#
# VideoMarkupModel.py
#     A data model that represents how to markup search results.
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

# Python imports...
import sys

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.mvc.AbstractModel import AbstractModel

# Local imports...

# Constants...


##############################################################################
class VideoMarkupModel(AbstractModel):
    """A data model that represents how to markup search results.

    This allows the user to decide how much extra data they want shown on their
    video.

    We'll send updates like:
    - 'showBoxesAroundObjects'
    - 'showDifferentColorBoxes'
    - 'showRegionZones'
    - 'showLabels'
    - 'showObjIds'
    """

    ###########################################################
    def __init__(self, showBoxesAroundObjects=True,
                 showDifferentColorBoxes=True,
                 showRegionZones=False, showLabels=False, showObjIds=False,
                 playAudio=True, overlayTimestamp=False, useUSDate=False,
                 use12HrTime=False, keyframeOnlyPlayback=False):
        """VideoMarkupModel constructor.

        IMPORTANT NOTE: Defaults to this constructor don't determine the
        defaults that the frontEnd uses.  Those are found in FrontEndPrefs.
        The defaults here DO however affect that the DataMgr will do if
        nobody ever gives it a model.

        @param  showBoxesAroundObjects   If True, we'll put boxes around objects
        @param  showDifferentColorBoxes  If True, boxes will be different colors
        @param  showRegionZones          If True, we'll draw the different
                                         regions on the video.  If this is True
                                         and we're showing boxes, we'll also
                                         show center info on the boxes.
        @param  showLabels               If True, we'll show labels.
        @param  showObjIds               If True, we'll show object database IDs
        @param  playAudio                If True, render audio for this clip
        @param  overlayTimestamp         If True, render timestamp for this clip
        @param  useUSDate                If True, use US date for the timestamp
        @param  use12HrTime              If True, use 12 hour time for the timestamp
        """
        super(VideoMarkupModel, self).__init__()

        self._showBoxesAroundObjects = bool(showBoxesAroundObjects)
        self._showDifferentColorBoxes = bool(showDifferentColorBoxes)
        self._showRegionZones = bool(showRegionZones)
        self._showLabels = bool(showLabels)
        self._showObjIds = bool(showObjIds)
        self._playAudio = bool(playAudio)
        self._overlayTimestamp = bool(overlayTimestamp)
        self._useUSDate = useUSDate
        self._use12HrTime = use12HrTime
        self._keyframeOnlyPlayback = bool(keyframeOnlyPlayback)

    ###########################################################
    def getOverlayTimestamp(self):
        return self._overlayTimestamp
    def setOverlayTimestamp(self, overlayTimestamp):
        overlayTimestamp = bool(overlayTimestamp)
        if overlayTimestamp != self._overlayTimestamp:
            self._overlayTimestamp = overlayTimestamp
            self.update('overlayTimestamp')

    def getPlayAudio(self):
        return self._playAudio
    def setPlayAudio(self, playAudio):
        playAudio = bool(playAudio)
        if playAudio != self._playAudio:
            self._playAudio = playAudio
            self.update('playAudio')

    def getShowBoxesAroundObjects(self):
        return self._showBoxesAroundObjects
    def setShowBoxesAroundObjects(self, showBoxesAroundObjects):
        showBoxesAroundObjects = bool(showBoxesAroundObjects)
        if showBoxesAroundObjects != self._showBoxesAroundObjects:
            self._showBoxesAroundObjects = showBoxesAroundObjects
            self.update('showBoxesAroundObjects')

    def getShowDifferentColorBoxes(self):
        return self._showDifferentColorBoxes
    def setShowDifferentColorBoxes(self, showDifferentColorBoxes):
        showDifferentColorBoxes = bool(showDifferentColorBoxes)
        if showDifferentColorBoxes != self._showDifferentColorBoxes:
            self._showDifferentColorBoxes = showDifferentColorBoxes
            self.update('showDifferentColorBoxes')

    def getShowRegionZones(self):
        return self._showRegionZones
    def setShowRegionZones(self, showRegionZones):
        showRegionZones = bool(showRegionZones)
        if showRegionZones != self._showRegionZones:
            self._showRegionZones = showRegionZones
            self.update('showRegionZones')

    def getShowLabels(self):
        return self._showLabels
    def setShowLabels(self, showLabels):
        showLabels = bool(showLabels)
        if showLabels != self._showLabels:
            self._showLabels = showLabels
            self.update('showLabels')

    def getShowObjIds(self):
        return self._showObjIds
    def setShowObjIds(self, showObjIds):
        showObjIds = bool(showObjIds)
        if showObjIds != self._showObjIds:
            self._showObjIds = showObjIds
            self.update('showObjIds')

    def getUSDate(self):
        return self._useUSDate
    def setUSDate(self, useUSDate):
        useUSDate=bool(useUSDate)
        if useUSDate != self._useUSDate:
            self._useUSDate = useUSDate
            self.update('useUSDate')

    def get12HrTime(self):
        return self._use12HrTime
    def set12HrTime(self, use12HrTime):
        use12HrTime=bool(use12HrTime)
        if use12HrTime != self._use12HrTime:
            self._use12HrTime = use12HrTime
            self.update('use12HrTime')

    def getKeyframeOnlyPlayback(self):
        return self._keyframeOnlyPlayback
    def setKeyframeOnlyPlayback(self, keyframeOnlyPlayback):
        keyframeOnlyPlayback = bool(keyframeOnlyPlayback)
        if keyframeOnlyPlayback != self._keyframeOnlyPlayback:
            self._keyframeOnlyPlayback = keyframeOnlyPlayback
            self.update('keyframeOnlyPlayback')


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "NO TEST CODE"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
