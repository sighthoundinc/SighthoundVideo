#!/usr/bin/env python

#*****************************************************************************
#
# SavedQueryDataModel.py
#     A data model representing a saved query.
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
import copy
import sys
import cPickle
import os

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.math.LineSegment import LineSegment
from vitaToolbox.mvc.AbstractModel import AbstractModel

# Local imports...
from appCommon.CommonStrings import kAnyCameraStr
from appCommon.CommonStrings import kCommandResponse, kEmailResponse
from appCommon.CommonStrings import kImportSuffix
from appCommon.CommonStrings import kRecordResponse, kSoundResponse
from appCommon.CommonStrings import kFtpResponse
from appCommon.CommonStrings import kPushResponse
from appCommon.CommonStrings import kIftttResponse
from appCommon.CommonStrings import kWebhookResponse
from appCommon.CommonStrings import kLocalExportResponse
from appCommon.CommonStrings import kDefaultPreRecord
from appCommon.CommonStrings import kTargetSettingToLabel

from triggers.BinaryTrigger import BinaryTrigger
from triggers.DoorTrigger import DoorTrigger
from triggers.DurationTrigger import DurationTrigger
from triggers.LineTrigger import LineTrigger
from triggers.MinSizeTrigger import MinSizeTrigger
from triggers.RegionTrigger import RegionTrigger
from triggers.TargetTrigger import TargetTrigger

from triggers.TriggerRegion import TriggerRegion
from triggers.TriggerLineSegment import TriggerLineSegment




# Constants...

#_kAnyCameraAutoNamePart = "any camera"
_kAnyCameraAutoNamePart = ""

# NOTE: New responses MUST be added to the end of this list for old queries
#       to be properly updated.
kDefaultResponseList = [
    (kRecordResponse, {
        'isEnabled':  False,
        'preRecord':  kDefaultPreRecord,
        'postRecord': 10,
    }),
    (kEmailResponse, {
        'isEnabled':    False,
        'toAddrs':      "",
        'wantLimit':    False,
        'limitSeconds': 60,
        'maxRes' :      320,
        'imageInline':  True
    }),
    (kSoundResponse, {
        'isEnabled':  False,
        'soundPath':  u"",        # Must be of type unicode
    }),
    (kCommandResponse, {
        'isEnabled':  False,
        'command':    u"",        # Must be of type unicode
    }),
    (kFtpResponse, {
        'isEnabled':  False,
        # All other settings are app-global; see BackEndPrefs.
    }),
    (kLocalExportResponse, {
        'isEnabled':  False,
        'exportPath': u"",
    }),
    (kPushResponse, {
        'isEnabled':  False,
    }),
    (kIftttResponse, {
        'isEnabled':  False,
    }),
    (kWebhookResponse, {
        'isEnabled':  False,
        'webhookUri': '',
        'webhookContentType': 'text/plain',
        'webhookContent': '',
    }),
]



_kDefaultCoordSpace = (320, 240)


##############################################################################
class SavedQueryDataModel(AbstractModel):
    """A data model representing a saved query.

    This is more centered around the UI--we'll have to write something to
    convert between this and the other view.

    Note: use 'getPropertyName()' and 'setPropertyName()' to get and set
    properties.  Look at the code for a list of properties, for now.
    """

    ###########################################################
    def __init__(self, name="", wantRecord=False):
        """SavedQueryDataModel constructor.

        TODO: Actually construct from something real rather than hardcoding.

        @param  name        A name for the query; if "" we will auto-name.
        @param  wantRecord  If True, we should start out with recording enabled.
        """
        # Call our super
        super(SavedQueryDataModel, self).__init__()

        # TODO: Just not sure how this design will morph into something that
        # can handle connectors w/ "and", "or".  Also: I'm not sure how
        # queries will evolve.
        #
        # Should video sources / targets really be special cased?  The video
        # source certainly needs to be special cased, to some extent
        # ...that's how we can show a camera view on the right.  What about
        # the targets?  ...should those really just be a trigger?
        #
        # ...also, should responses be in here?  Is our "SavedQuery" now a rule?

        # The hardcoding seems awfully wrong...

        self._name = name

        self._videoSource = VideoSourceBlockDataModel(kAnyCameraStr)

        self._targets = [
            TargetBlockDataModel('anything'),
        ]

        width, height = _kDefaultCoordSpace

        self._triggers = [
            WhereBlockDataModel('blankTrigger', 'inside', "my region",
                                'entering',
                                TriggerRegion([
                                    (int(width/4),       int(height/4)),
                                    (int((3 * width)/4), int(height/4)),
                                    (int((3 * width)/4), int((3 * height)/4)),
                                    (int(width/4),       int((3 * height)/4)),
                                ],
                                    (width, height)
                                ),
                                TriggerLineSegment(
                                    LineSegment(int(width/2), int(height/4),
                                                int(width/2), int((3 * height)/4)),
                                    'left',
                                    (width, height)
                                )),
            DurationBlockDataModel(False, 0, 'seconds', False, 0, 'seconds')
        ]

        # A list of (responseType, configDict) tuples.  Only one entry for
        # each responseType is allowed.
        # NOTE: This is not symmetric with all of the other response blocks,
        # but it probably doesn't matter since we'd like to redesign all of
        # this once we have a more flexible QueryConstructionView.
        self._responses = copy.deepcopy(kDefaultResponseList)
        if wantRecord:
            for responseName, responseDetails in self._responses:
                if responseName == kRecordResponse:
                    responseDetails['isEnabled'] = True
                    break
            else:
                assert False, "No record response found"

        # Keep track of what we last edited.  Start with the camera block...
        # ...this is a tuple that looks like: (sourceBlock, blockNum)
        # Can be 'videoSource', 'target', 'trigger', 'ifSeen', ...
        self._lastEdited = ('videoSource', None)

        # Listen for updates from our submodels...
        self._addListeners()

        # Keep track of visible name so we know when to do updates
        self._visibleName = self._calcVisibleName()


    ###########################################################
    def _addListeners(self):
        """Register as a listener for sub models"""
        for subModel in (self._targets + self._triggers + [self._videoSource]):
            subModel.addListener(self._handleSubModelUpdate)


    ###########################################################
    def _calcVisibleName(self):
        """Return the user-apparent name.

        If our current name is blank, it means we're using an auto-generated
        name, which to the user looks like our name.  This will return the
        name that the user sees.

        @return visibleName  Our visible name.
        """
        if self.isAutoNamed():
            return self.getAutoName()
        else:
            return self._name


    ###########################################################
    def isOk(self):
        """Verifies the current state of this query.

        Note:   Currently, the only thing we verify here is if the local paths
                exist and are reachable.

        @return isOk        True if the state of this data model is valid, and
                            False otherwise.
        """
        return self._fixIfInvalid(True)


    ###########################################################
    def fixIfInvalid(self):
        """Fixes the current state of this query if it is invalid

        Note:   Currently, the only thing we verify here is if the local paths
                exist and are reachable.

        @return isFixed     True if the state was already valid, or if all of
                            the fixes were successful if the state was invalid.
                            False if any fixes were unsuccessful.
        """
        return self._fixIfInvalid(False)


    ###########################################################
    def _fixIfInvalid(self, dryrun=False):
        """Verifies the current state of this query and attempts to fix it if
        it is invalid.

        Note:   Currently, the only thing we verify here is if the local paths
                exist and are reachable.

        @param  dryrun      When set to True, do not fix. Return False early
                            upon discovery of invalid state.
        @return isOk        True if the state is valid. This will also return
                            True if all fixes were successful for an invalid
                            state. False if dryrun is True and we found an
                            invalid setting. Also False if the fixes were
                            unsuccessful.
        """

        # Return early if we find a violation...
        for name, config in self.getResponses():

            if not config.get('isEnabled', False):
                continue

            if name == kSoundResponse:
                soundPath = config.get('soundPath', '')
                if soundPath and not os.path.isdir(soundPath):
                    if dryrun:
                        return False
                    config['isEnabled'] = False

            elif name == kLocalExportResponse:
                exportPath = config.get('exportPath', '')
                if exportPath and not os.path.isdir(exportPath):
                    if dryrun:
                        return False
                    config['isEnabled'] = False

        return True


    ###########################################################
    def isAutoNamed(self):
        """Return true if we're using auto-naming.

        @return isAutoNamed
        """
        # A blank value for self._name indicates auto-naming...
        return not self._name


    ###########################################################
    def getAutoName(self):
        """Return what the auto-generated name would be.

        This is even if we currently aren't using auto-naming.

        @return autoName  The automatically generated name.
        """
        targetPart = self._targets[0]._getAutoNamePart()
        wherePart = self._triggers[0]._getAutoNamePart()
        videoPart = self._videoSource._getAutoNamePart()

        # If target and where are both non-blank, need a space between them.
        if targetPart and wherePart:
            autoName = '%s %s' % (targetPart, wherePart)
        elif wherePart:
            autoName = wherePart[:1].upper() + wherePart[1:]
        else:
            autoName = targetPart

        if videoPart:
            autoName = '%s in %s' % (autoName, videoPart)
        return autoName


    ###########################################################
    def setCoordSpace(self, coordSpace):
        """Convenience function that sets the coordinate space for the trigger
        regions and trigger linesegments in the WhereBlockDataModel object.

        @param coordSpace: coordinate space represented as a two-tuple
                           (width, height).
        """
        if self._triggers and self._triggers[0]:
            whereBlockDataModel = self._triggers[0]
            whereBlockDataModel.setCoordSpace(coordSpace)


    ###########################################################
    def getName(self):
        return self._visibleName
    def setName(self, name):
        if self._name != name:
            self._name = name
            self._visibleName = self._calcVisibleName()
            self.update('name')
    def getVideoSource(self):
        return self._videoSource
    def setVideoSource(self, videoSource):
        if self._videoSource != videoSource:
            self._videoSource = videoSource
            self.update('videoSource')
    def getTargets(self):
        return self._targets
    def setTargets(self, targets):
        if self._targets != targets:
            self._targets = targets
            self.update('targets')
    def getTriggers(self):
        return self._triggers
    def setTriggers(self, triggers):
        if self._triggers != triggers:
            self._triggers = triggers
            self.update('triggers')
    def getLastEdited(self):
        return self._lastEdited
    def setLastEdited(self, componentStr, i):
        if self._lastEdited != (componentStr, i):
            self._lastEdited = (componentStr, i)
            self.update('lastEdited')
    def getResponses(self):
        # Return a deep copy to force caller to do a setResponses() when they
        # change the dicts.
        return copy.deepcopy(self._responses)
    def setResponses(self, responses):
        if self._responses != responses:
            self._responses = responses
            self.update('responses')


    ###########################################################
    def _handleSubModelUpdate(self, subModel):
        """Handle an update from one of our submodel.

        We'll pass this on to any of our listeners.

        @param  subModel  The submodel that was updated.  We'll use this as the
                          key to our update.
        """
        # First, handle any updates on our name...
        visibleName = self._calcVisibleName()
        if visibleName != self._visibleName:
            self._visibleName = visibleName
            self.update('name')

        # Now, update regarding the subModel...
        self.update(subModel)


    ###########################################################
    def __setstate__(self, state):
        """Restore an object from from the pickled state

        @param  state  The information previously returned from __getstate__
        """
        self.__dict__ = state
        self._visibleName = self._calcVisibleName()

        # Update old queries to have the current set of responses.
        numResponses = len(self._responses)
        numDefaultResponses = len(kDefaultResponseList)
        if numResponses != numDefaultResponses:
            self._responses = self._responses[:numDefaultResponses] + \
                              kDefaultResponseList[numResponses:]

        self._addListeners()


    ###########################################################
    def copy(self):
        """Return a copy

        @return modelCopy  A copy of this model
        """
        return copy.deepcopy(self)


    ###########################################################
    def getUsableQuery(self, dataManager):
        """Return a query built from the current settings

        NOTE: This is very specific for the demo.  Will need a later rewrite.

        @param  dataManager  The database to give the created query
        @return query        The query
        """
        moreThanTrigger = None
        lessThanTrigger = None
        whereModel = None
        durationModel = None

        for model in self.getTriggers():
            if isinstance(model, WhereBlockDataModel):
                whereModel = model
            else:
                durationModel = model

        # Create the where trigger
        if whereModel.getTriggerType() == 'regionTrigger':
            # Region Trigger
            regionType = whereModel.getRegionType()
            region = whereModel.getRegion()
            trackPt = 'center'
            if regionType == 'ground':
                regionType = 'inside'
                trackPt = 'bottom'

            # Get points in the same coordinate space as our processing size.
            whereTrigger = RegionTrigger(dataManager, region, trackPt,
                                         regionType)
        elif whereModel.getTriggerType() == 'doorTrigger':
            # Door Trigger
            doorType = whereModel.getDoorType()
            region = whereModel.getRegion()
            # Get points in the same coordinate space as our processing size.
            whereTrigger = DoorTrigger(dataManager, region, 'center', doorType)
        elif whereModel.getTriggerType() == 'lineTrigger':
            segment = whereModel.getLineSegment()
            # Get points in the same coordinate space as our processing size.
            whereTrigger = LineTrigger(dataManager, segment, 'center')
        else:
            assert whereModel.getTriggerType() == 'blankTrigger'
            whereTrigger = RegionTrigger(dataManager,
                                         TriggerRegion(
                                             [(0,0),(319,0),(319,239),(0,239)],
                                             _kDefaultCoordSpace
                                         ),
                                         'center', 'inside')

        # Create the duration trigger(s)
        if durationModel.getWantMoreThan():
            msecs = self._unitsValuesToMsecs(durationModel.getMoreThanUnits(),
                                             durationModel.getMoreThanValue())
            if msecs > 0:
                moreThanTrigger = DurationTrigger(whereTrigger, msecs, True)

        if durationModel.getWantLessThan():
            msecs = self._unitsValuesToMsecs(durationModel.getLessThanUnits(),
                                             durationModel.getLessThanValue())
            lessThanTrigger = DurationTrigger(whereTrigger, msecs, False)

        # Prepare the trigger to be fed into the target trigger
        if moreThanTrigger and lessThanTrigger:
            preTargetTrigger = BinaryTrigger('and', [moreThanTrigger,
                                                    lessThanTrigger], True)
        elif moreThanTrigger:
            preTargetTrigger = moreThanTrigger
        elif lessThanTrigger:
            preTargetTrigger = lessThanTrigger
        else:
            # Go back to "None" rather than a bogus region trigger if we
            # aren't using durations...
            if whereModel.getTriggerType() == 'blankTrigger':
                preTargetTrigger = None
            else:
                preTargetTrigger = whereTrigger

        # Deal with size...
        assert len(self.getTargets()) == 1, "Should be exactly one target"
        target = self.getTargets()[0]
        if target.getWantMinSize():
            preTargetTrigger = MinSizeTrigger(dataManager, target.getMinSize(),
                                              preTargetTrigger)

        # Return the final trigger
        targetTypes = [(target.getTargetName(), target.getActionName())
                       for target in self.getTargets()]
        if targetTypes[0][0] != 'anything':
            # Add a target trigger...
            return TargetTrigger(dataManager, targetTypes, preTargetTrigger)
        else:
            # No target trigger needed; though do make sure that there's only
            # on target...
            assert len(targetTypes) == 1, \
                   "Don't know what to do about multiple targets w/ anything."

        if preTargetTrigger is None:
            # Add in a target trigger if nothing else (since that's fast!)
            return TargetTrigger(dataManager, [])
        else:
            return preTargetTrigger


    ###########################################################
    def _unitsValuesToMsecs(self, units, value):
        """Convert a value and unit type to a value in milliseconds

        @param  units  'minutes' or 'seconds'
        @param  value  The duration value in units
        @return msecs  The duration value in milliseconds
        """
        assert units in ['minutes', 'seconds']
        if units == 'minutes':
            return value*60*1000
        else:
            return value*1000


##############################################################################
class VideoSourceBlockDataModel(AbstractModel):
    """The data model keeping track of where we get video from."""

    ###########################################################
    def __init__(self, locationName):
        """VideoSourceBlockDataModel constructor.

        This model will hold information about where we'll find video.

        @param  locationName  The name of the location we'll get video from.
                              In the current UI, this is the name of the camera.
        """
        # Call our super
        super(VideoSourceBlockDataModel, self).__init__()

        self._locationName = locationName


    ###########################################################
    def getLocationName(self):
        return self._locationName
    def setLocationName(self, locationName):
        self._locationName = locationName
        self.update('locationName')


    ###########################################################
    def _getAutoNamePart(self):
        """Used by SavedQueryDataModel for auto-naming.

        @return autoNamePart  The part to contribute to the auto name.  May be
                              blank.
        """
        if self._locationName == kAnyCameraStr:
            return _kAnyCameraAutoNamePart
        else:
            locationName = self._locationName

            # Take out the 'imported' suffix.  Note: if we add more suffixes,
            # we could just kill everything after '<'...
            if locationName.endswith(kImportSuffix):
                locationName = locationName[:-len(kImportSuffix)]

            return locationName


##############################################################################
class TargetBlockDataModel(AbstractModel):
    """The data model keeping track of a target."""

    ###########################################################
    def __init__(self, targetName, actionNameDict={}, wantMinSize=False,
                 minSize=30, showMinSize=True):
        """TargetBlockDataModel constructor.

        This model will hold information about a target we're looking for.

        @param  targetName      The name of a target, like "person" or "pet".
        @param  actionNameDict  A dictionary to look up the action name based
                                on the target.  If a target is not in the
                                dict, we'll assume that the action is 'any'.
        @param  wantMinSize     If True, we want to use the minSize.
        @param  minSize         The minimum size that this object needs to be.
        @param  showMinSize     Boolean of whether the user wants to see the min
                                size displayed on the screen.
        """
        # Call our super
        super(TargetBlockDataModel, self).__init__()

        self._targetName = targetName
        self._actionNameDict = actionNameDict
        self._wantMinSize = wantMinSize
        self._minSize = minSize
        self._showMinSize = showMinSize


    ###########################################################
    def __setstate__(self, state):
        """Restore an object from from the pickled state

        @param  state  The information previously returned from __getstate__
        """
        # Upgrade old queries (build 4901 and earlier)
        if '_minSize' not in state:
            state['_wantMinSize'] = False
            state['_minSize'] = 30
            state['_showMinSize'] = True

        self.__dict__ = state


    ###########################################################
    def getTargetName(self):
        return self._targetName
    def setTargetName(self, targetName):
        self._targetName = targetName
        self.update()  # Action and target change; just give a general update.
    def getActionName(self):
        return self._actionNameDict.get(self._targetName, 'any')
    def setActionName(self, actionName):
        self._actionNameDict[self._targetName] = actionName
        self.update('actionName')
    def getWantMinSize(self):
        return self._wantMinSize
    def setWantMinSize(self, wantMinSize):
        self._wantMinSize = wantMinSize
        self.update('wantMinSize')
    def getMinSize(self):
        return self._minSize
    def setMinSize(self, minSize):
        self._minSize = minSize
        self.update('minSize')
    def getShowMinSize(self):
        return self._showMinSize
    def setShowMinSize(self, showMinSize):
        self._showMinSize = showMinSize
        self.update('showMinSize')


    ###########################################################
    def _getAutoNamePart(self):
        """Used by SavedQueryDataModel for auto-naming.

        @return autoNamePart  The part to contribute to the auto name.  May be
                              blank.
        """
        return kTargetSettingToLabel[self._targetName]


##############################################################################
class WhereBlockDataModel(AbstractModel):
    """The data model keeping track the data in a "where" block."""

    ###########################################################
    def __init__(self, triggerType, regionType, regionName,
                 doorType, region, lineSegment):
        """WhereBlockDataModel constructor.

        This model holds information that belongs in a "where" block.

        NOTE: We currently _don't_ pass on updates from our contained
        region / lineSegment.  We might in the future, though.

        @param  triggerType  Tells whether this is a region-based trigger
                             or a line based trigger.
        @param  regionType   If this is a region-based trigger, this will
                             be the type of region-based trigger.  In the UI,
                             some of these are grouped together.
        @param  regionName   The name of the region.
        @param  doorType     If this is a doorTrigger, this will be the type
                             of the door trigger.
        @param  region       A TriggerRegion; used for region and door triggers.
        @param  lineSegment  A TriggerLineSegment.
        """
        # Call our super
        super(WhereBlockDataModel, self).__init__()

        assert triggerType in ('blankTrigger', 'regionTrigger', 'doorTrigger',
                               'lineTrigger')
        assert regionType in (
            'inside', 'outside', 'entering', 'exiting', 'crosses', 'ground',
        )
        assert doorType in (
            'entering', 'exiting', 'any',
        )

        self._triggerType = triggerType
        self._regionType = regionType
        self._regionName = regionName
        self._doorType = doorType
        self._region = region
        self._lineSegment = lineSegment


    ###########################################################
    def __getstate__(self):
        """Prepare our state to be pickled.

        Need to do this so that obfuscation works properly!

        @return  state  The state to be pickled.
        """
        state = super(WhereBlockDataModel, self).__getstate__()
        region = state.pop('_region')
        lineSegment = state.pop('_lineSegment')

        state['_regionPoints'] = region.getPoints()
        state['_regionCoordSpace'] = region.getCoordSpace()
        state['_lineSegmentPoints'] = lineSegment.getLineSegment().getPoints()
        state['_lineSegmentCoordSpace'] = lineSegment.getCoordSpace()
        state['_lineSegmentDirection'] = lineSegment.getDirection()

        return state


    ###########################################################
    def __setstate__(self, state):
        """Restore an object from from the pickled state

        @param  state  The information previously returned from __getstate__
        """
        lineSegmentDirection = state.pop('_lineSegmentDirection')
        lineSegmentPoints = state.pop('_lineSegmentPoints')

        # Before SV 3.0, we didn't save the coordinate space of our regions
        # and linsegments. If the coordinate space variable is not in 'state',
        # then we're looking at an old version of the SavedQueryDataModel.
        # 'None' is a valid value for the coordinate space. It just means it
        # doesn't exist.

        if '_lineSegmentCoordSpace' in state:
            lineSegmentCoordSpace = state.pop('_lineSegmentCoordSpace')
        else:
            lineSegmentCoordSpace = None

        regionPoints = state.pop('_regionPoints')

        if '_regionCoordSpace' in state:
            regionCoordSpace = state.pop('_regionCoordSpace')
        else:
            regionCoordSpace = None

        state['_lineSegment'] = TriggerLineSegment(
            LineSegment(*lineSegmentPoints), lineSegmentDirection,
            lineSegmentCoordSpace
        )
        state['_region'] = TriggerRegion(regionPoints, regionCoordSpace)

        self.__dict__ = state


    ###########################################################
    def setCoordSpace(self, coordSpace):
        if self._region:
            self._region.setCoordSpace(coordSpace)
        if self._lineSegment:
            self._lineSegment.setCoordSpace(coordSpace)


    ###########################################################
    def getTriggerType(self):
        return self._triggerType
    def setTriggerType(self, triggerType):
        self._triggerType = triggerType
        self.update('triggerType')
    def getRegionType(self):
        return self._regionType
    def setRegionType(self, regionType):
        self._regionType = regionType
        self.update('regionType')
    def getRegionName(self):
        return self._regionName
    def setRegionName(self, regionName):
        self._regionName = regionName
        self.update('regionName')
    def getDoorType(self):
        return self._doorType
    def setDoorType(self, doorType):
        self._doorType = doorType
        self.update('doorType')
    def getRegion(self):
        return self._region
    def setRegion(self, region):
        self._region = region
        self.update('region')
    def getLineSegment(self):
        return self._lineSegment
    def setLineSegment(self, lineSegment):
        self._lineSegment = lineSegment
        self.update('lineSegment')


    ###########################################################
    def _getAutoNamePart(self):
        """Used by SavedQueryDataModel for auto-naming.

        @return autoNamePart  The part to contribute to the auto name.  May be
                              blank.
        """
        triggerType = self._triggerType

        if triggerType == 'blankTrigger':
            label = ""
        elif triggerType == 'lineTrigger':
            label = "crossing a boundary"
        elif triggerType == 'doorTrigger':
            doorType = self._doorType
            if doorType == 'entering':
                label = "entering through a door"
            elif doorType == 'exiting':
                label = "leaving through a door"
            elif doorType == 'any':
                label = "entering or leaving through a door"
            else:
                assert False, "Unknown door type: %s" % doorType
        else:
            assert triggerType == 'regionTrigger'

            regionType  = self._regionType
            regionName  = self._regionName
            if not regionName.strip():
                regionName = 'my region'

            if regionType == 'inside':
                label = "inside " + regionName
            elif regionType == 'outside':
                label = "outside " + regionName
            elif regionType == 'entering':
                label = "entering " + regionName
            elif regionType == 'exiting':
                label = "exiting " + regionName
            elif regionType == 'crosses':
                label = "entering or exiting " + regionName
            elif regionType == 'ground':
                label = "on top of " + regionName
            else:
                assert False, "Unknown region type: %s" % regionType

        return label


##############################################################################
class DurationBlockDataModel(AbstractModel):
    """The data model keeping track the data in a "duration" block."""

    ###########################################################
    def __init__(self, wantMoreThan, moreThanValue, moreThanUnits,
                 wantLessThan, lessThanValue, lessThanUnits):
        """DurationBlockDataModel constructor.

        This model holds information that belongs in a "duration" block.  A
        few notes about the design of this:
        * If the user chooses neither 'more than' nor 'less than', I'll assume
          that means we should trigger on any duration--essentially this block
          becomes a no-op.
        * I'm assuming that it's important to present the user the same UI
          next time he/she comes in.  In other words, if the user specifies
          "60 seconds", next time through it shouldn't say "1 minute".
          Similarly, if the user unchecks "more than" but the UI shows
          "60 seconds", the next time through the user should be shown this
          same state (in other words, we shouldn't lose the "60 seconds" part
          just because the user chose not to trigger on "more than" right now).

        NOTE: At the moment, we're not using the "less than" part, since UI
        has changed.  We may resurrect it later.

        @param  wantMoreThan   If True, the "more than" constraint is active.
        @param  moreThanValue  The number of units we need to be more than.
        @param  moreThanUnits  The units: 'seconds' or 'minutes'.
        @param  wantLessThan   Like 'more', but for 'less'.
        @param  lessThanValue  Like 'more', but for 'less'.
        @param  lessThanUnits  Like 'more', but for 'less'.
        """
        # Call our super
        super(DurationBlockDataModel, self).__init__()

        assert moreThanUnits in ('minutes', 'seconds')
        assert lessThanUnits in ('minutes', 'seconds')

        self._wantMoreThan = wantMoreThan
        self._moreThanValue = moreThanValue
        self._moreThanUnits = moreThanUnits
        self._wantLessThan = wantLessThan
        self._lessThanValue = lessThanValue
        self._lessThanUnits = lessThanUnits


    ###########################################################
    def getWantMoreThan(self):
        return self._wantMoreThan
    def setWantMoreThan(self, wantMoreThan):
        self._wantMoreThan = wantMoreThan
        self.update('wantMoreThan')
    def getMoreThanValue(self):
        return self._moreThanValue
    def setMoreThanValue(self, moreThanValue):
        self._moreThanValue = moreThanValue
        self.update('moreThanValue')
    def getMoreThanUnits(self):
        return self._moreThanUnits
    def setMoreThanUnits(self, moreThanUnits):
        self._moreThanUnits = moreThanUnits
        self.update('moreThanUnits')
    def getWantLessThan(self):
        return self._wantLessThan
    def setWantLessThan(self, wantLessThan):
        self._wantLessThan = wantLessThan
        self.update('wantLessThan')
    def getLessThanValue(self):
        return self._lessThanValue
    def setLessThanValue(self, lessThanValue):
        self._lessThanValue = lessThanValue
        self.update('lessThanValue')
    def getLessThanUnits(self):
        return self._lessThanUnits
    def setLessThanUnits(self, lessThanUnits):
        self._lessThanUnits = lessThanUnits
        self.update('lessThanUnits')


##############################################################################
def convertOld2NewSavedQueryDataModel(dataManager, queryModel):
    """Finds the processing resolution size of the given query model using the
    given data manager, and updates this query's coordinate space if it is
    invalid. Queries from older versions of the app do not have coordinate
    spaces, so they will show up as 'None' values. The newer data models will
    already contain coordinate space information. The coordinate space is
    necessary for editing, drawing and detecting objects using trigger regions
    and boundaries.

    Note: This conversion may fail (and behave as a no-op) for the following
          reasons:

            - if the data manager can't find the processing size of the camera
              location saved in the query. This can happen if video hasn't
              been stored yet, video has been deleted, corrupt database, or
              if the files are somehow in use.

    @param dataManager  A DataManager object assumed to be in a valid state.
    @param queryModel   An instance of SavedQueryDataModel
    """

    # If the object we unpickled is not a SavedQueryDataModel, return.
    if not isinstance(queryModel, SavedQueryDataModel):
        return

    # Get the processing size of the camera location in this query; this will
    # be used to calculate the old processing size.
    procSize = dataManager.getProcSize(
        queryModel.getVideoSource().getLocationName()
    )

    # Nothing we can do if we don't have a processing size to work with. Just
    # return.
    if procSize == (0, 0) or procSize is None:
        return

    procWidth, procHeight = procSize

    # The old processing size was 320x___. So we need to first divide by the
    # current processing size width, then multiply by 320. The old processing
    # size is the coordinate space for the old saved query settings.
    oldProcSize = (320, int(float(procHeight)/procWidth*320))

    # Retrieve the WhereBlockDataModel object so we can get the triggers.
    whereModel = None
    for model in queryModel.getTriggers():
        if isinstance(model, WhereBlockDataModel):
            whereModel = model
            break

    # This should never happen. But if it does, return.
    if whereModel is None:
        return

    # Get the triggers. Old queries have 'None' as their coordinate space. All
    # new queries either have the default (320x240) coordinate space, or their
    # processing size or equivalent aspect ratio of the processing size.
    triggerLineSegment = whereModel.getLineSegment()
    triggerRegion = whereModel.getRegion()

    # If the coordinate space is 'None', we found an old query. Set the
    # coordinate space as the old processing size, since that is what the
    # coordinate space really was for these queries.
    if triggerLineSegment.getCoordSpace() is None:
        triggerLineSegment.setCoordSpace(oldProcSize)
    if triggerRegion.getCoordSpace() is None:
        triggerRegion.setCoordSpace(oldProcSize)


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
