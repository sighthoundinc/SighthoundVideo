#!/usr/bin/env python

#*****************************************************************************
#
# WhereConfigPanel.py
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
import operator
import sys

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.path.PathUtils import normalizePath
from vitaToolbox.wx.FontUtils import makeFontDefault

# Local imports...
from ConfigPanel import ConfigPanel

###############################################################
# Where constants

# Help strings...
_kHelpTextAnywhere = \
""""""
_kHelpTextStandardRegion = \
"""Click and drag the white circles to select a region."""
_kHelpTextGroundRegion = \
"""Drag the circles to outline a surface on which an object is walking or moving."""
_kHelpTextDoorRegion = \
"""Click and drag the white circles to outline a door."""
_kHelpTextDirection = \
"""Click and drag the white circles to select the endpoints of a boundary. Click arrow to reverse direction."""

_kHelpTextColor = "grey"

# The top label...
_kLookForMovementLabelString = "Moving objects that are:"

# The "anywhere" string
_kAnywhereRadioString = "Anywhere"

# Mapping choice labels to settings in the model...
_kStandardRegionMapping = [
    ("Inside", 'inside'),
    ("Outside", 'outside'),
    ("Entering", 'entering'),
    ("Exiting", 'exiting'),
    ("Entering or Exiting", 'crosses'),
    ("On top of", 'ground'),
]
_kStandardRegionLabels = map(operator.itemgetter(0), _kStandardRegionMapping)
_kStandardRegionLabelToSetting = dict(_kStandardRegionMapping)
_kStandardRegionSettingToLabel = dict(map(operator.itemgetter(1, 0),
                                          _kStandardRegionMapping))

# Mapping choice labels to settings in the model...
_kDoorRegionMapping = [
    ("Entering scene", 'entering'),
    ("Leaving scene", 'exiting'),
    ("Entering or leaving", 'any'),
]
_kDoorRegionLabels = map(operator.itemgetter(0), _kDoorRegionMapping)
_kDoorRegionLabelToSetting = dict(_kDoorRegionMapping)
_kDoorRegionSettingToLabel = dict(map(operator.itemgetter(1, 0),
                                      _kDoorRegionMapping))

# We'll put this after the choice...
_kDoorRegionLabelEndString = "through a door"

# Strings associated with line triggers...
_kDirectionRadioString  = "Crossing a boundary"

# Maximum length of the region field.  This number should be small
# enough to not give user "rule name too long" errors when auto-generated
# names are being used.
_kMaxRegionNameLen = 25

###############################################################
# Duration constants

# Force spinners to stop at 60 seconds / minutes...
_kMaxDuration = 60

# The top label...
_kLookForMotionVisibleLabelString = "Include objects visible longer than:"

# Mapping choice labels to settings in the model...
_kTimeUnitMapping = [
    ("seconds", 'seconds'),
    ("minutes", 'minutes'),
]
#_kTimeUnitLabels = map(operator.itemgetter(0), _kTimeUnitMapping)
_kTimeUnitLabelToSetting = dict(_kTimeUnitMapping)
_kTimeUnitSettingToLabel = dict(map(operator.itemgetter(1, 0),
                                    _kTimeUnitMapping))



##############################################################################
class WhereConfigPanel(ConfigPanel):
    """The block configuration panel for region and direction triggers."""

    ###########################################################
    def __init__(self, parent, videoWindow, whereBlockDataModel, durationBlockDataModel):
        """WhereConfigPanel constructor.

        @param  parent                  Our parent UI element.
        @param  videoWindow             The videoWindow.
        @param  whereBlockDataModel     The data model for 'where' updates.
        @param  durationBlockDataModel  The data model for 'duration' updates.
        """
        # Call our super
        super(WhereConfigPanel, self).__init__(parent)

        # Keep track of params...
        self._videoWindow = videoWindow
        self._whereBlockDataModel = whereBlockDataModel
        self._durationBlockDataModel = durationBlockDataModel

        # Put this space before the normal radio buttons to make it look good
        # with all of the choice controls.
        kRadioSpace = "  "

        # Create our UI elements.  Note that common stuff was already created
        # by our superclass...  Some of the UI elements will be refined by
        # self._updateFromModels

        # We don't want the help label to affect the width of the first column,
        # but we need it to be sized for 2 lines (even if we don't use 2 lines).
        self._helpLabel = wx.StaticText(self, -1, " \n ")
        makeFontDefault(self._helpLabel)
        self._helpLabel.SetForegroundColour(_kHelpTextColor)
        self._helpLabelMinSize = (1, self._helpLabel.GetBestSize()[1])
        self._helpLabel.SetMinSize(self._helpLabelMinSize)

        lookForMovementLabel = \
            wx.StaticText(self, -1, _kLookForMovementLabelString)
        lookForMovementLabel.SetMinSize((1, -1))

        self._anywhereRadio = \
            wx.RadioButton(self, -1, kRadioSpace + _kAnywhereRadioString,
                           style=wx.RB_GROUP)
        self._anywhereRadio.SetMinSize((1, -1))

        self._standardRegionRadio = \
            wx.RadioButton(self, -1, "")
        self._standardRegionChoice = \
            wx.Choice(self, -1, choices=_kStandardRegionLabels)
        self._standardRegionField = \
            wx.TextCtrl(self, -1)
        self._standardRegionField.SetMaxLength(_kMaxRegionNameLen)

        self._doorRegionRadio = \
            wx.RadioButton(self, -1, "")
        self._doorRegionChoice = \
            wx.Choice(self, -1, choices=_kDoorRegionLabels)
        doorRegionEndLabel = \
            wx.StaticText(self, -1, _kDoorRegionLabelEndString)

        self._directionRadio = \
            wx.RadioButton(self, -1, kRadioSpace + _kDirectionRadioString)
        self._directionRadio.SetMinSize((1, -1))

        lookForMotionLabel = \
            wx.StaticText(self, -1, _kLookForMotionVisibleLabelString)

        self._moreThanSpinner = wx.SpinCtrl(self, -1)
        self._moreThanUnits = wx.StaticText(self, -1)

        # Throw our stuff into our sizer...
        #
        # We use a grid bag sizer.  ...some of the magic here around setting
        # min sizers makes the grid bag sizer assign the right size the the
        # various rows / cols.  Specifically, we want the first column to be
        # the size of a blank radio button, not based on the size of any of
        # the full radio buttons...
        self._whereSettingsSizer = wx.GridBagSizer(vgap=6, hgap=5)
        whereSettingsSizer = self._whereSettingsSizer
        whereSettingsSizer.Add(self._helpLabel,
                               pos=(0, 0), span=(1, 3), flag=wx.EXPAND)
        whereSettingsSizer.Add(lookForMovementLabel,
                               pos=(1, 0), span=(1, 3), flag=wx.EXPAND)
        whereSettingsSizer.Add(self._anywhereRadio,
                               pos=(2, 0), span=(1, 3), flag=wx.EXPAND)
        whereSettingsSizer.Add(self._standardRegionRadio,
                               pos=(3, 0))
        whereSettingsSizer.Add(self._standardRegionChoice,
                               pos=(3, 1), flag=wx.EXPAND)
        fieldSizer = wx.BoxSizer(wx.HORIZONTAL)
        fieldSizer.Add(self._standardRegionField, 1)
        whereSettingsSizer.Add(fieldSizer,
                               pos=(3, 2), flag=wx.EXPAND)
        whereSettingsSizer.Add(self._doorRegionRadio,
                               pos=(4, 0))
        whereSettingsSizer.Add(self._doorRegionChoice,
                               pos=(4, 1), flag=wx.EXPAND)
        whereSettingsSizer.Add(doorRegionEndLabel,
                               pos=(4, 2), flag=wx.EXPAND)
        whereSettingsSizer.Add(self._directionRadio,
                               pos=(5, 0), span=(1, 3), flag=wx.EXPAND)

        whereSettingsSizer.AddGrowableCol(2)

        durationSettingsSizer = wx.BoxSizer(wx.HORIZONTAL)
        durationSettingsSizer.Add(self._moreThanSpinner, 0,
                                  wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        durationSettingsSizer.Add(self._moreThanUnits, 1,
                                  wx.ALIGN_CENTER_VERTICAL)

        # Stick our sizer into the place provided by our superclass...
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(whereSettingsSizer, 0, wx.EXPAND)
        mainSizer.AddSpacer(15)
        mainSizer.Add(lookForMotionLabel, 0)
        mainSizer.Add(durationSettingsSizer, 0, wx.EXPAND |
                      wx.TOP | wx.BOTTOM, 10)
        self.SetSizer(mainSizer)

        # Update everything...
        self._updateFromModels()

        # Listen for changes from the model...
        self._whereBlockDataModel.addListener(self._updateFromModels)
        self._durationBlockDataModel.addListener(self._updateFromModels)

        # Bind to the UI elements to get their changes...
        self._anywhereRadio.Bind(wx.EVT_RADIOBUTTON, self.OnAnywhere)

        self._standardRegionRadio.Bind(wx.EVT_RADIOBUTTON, self.OnStdRegion)
        self._standardRegionChoice.Bind(wx.EVT_CHOICE, self.OnStdRegion)
        self._standardRegionField.Bind(wx.EVT_TEXT, self.OnStdRegion)

        self._doorRegionRadio.Bind(wx.EVT_RADIOBUTTON, self.OnDoorRegion)
        self._doorRegionChoice.Bind(wx.EVT_CHOICE, self.OnDoorRegion)

        self._directionRadio.Bind(wx.EVT_RADIOBUTTON, self.OnDirection)

        self._moreThanSpinner.Bind(wx.EVT_SPINCTRL, self.OnUiChange)


    ###########################################################
    def getIcon(self):
        """Return the path to the bitmap associated with this panel.

        @return bmpPath  The path to the bitmap.
        """
        return "frontEnd/bmps/Block_Icon_Region_Big.png"


    ###########################################################
    def getTitle(self):
        """Return the title associated with this panel.

        @return title  The title
        """
        return "That are"


    ###########################################################
    def activate(self):
        """Set this panel as the active one."""
        self._updateFromModels(None)


    ###########################################################
    def deactivate(self):
        """Called before another panel gets activate."""
        self._videoWindow.setTriggerRegions([])
        self._videoWindow.setTriggerLineSegments([])


    ###########################################################
    def OnUiChange(self, event=None):
        """Handle any UI change for duration controls.

        To simplify things, we just have one function that updates the model
        from the UI.

        @param  event  One of a number of event types.  Ignored
        """
        moreThanValue = self._moreThanSpinner.GetValue()
        moreThanUnits = self._moreThanUnits.GetLabel()
        moreThanUnits = _kTimeUnitLabelToSetting[moreThanUnits]

        if self._moreThanSpinner.IsEnabled():
            self._durationBlockDataModel.setMoreThanValue(moreThanValue)
        self._durationBlockDataModel.setMoreThanUnits(moreThanUnits)


    ###########################################################
    def OnAnywhere(self, event=None):
        """Handle changes to any UI elements for the "anywhere" region.

        @param  event  One of a number of event types.  Ignored
        """
        self._whereBlockDataModel.setTriggerType('blankTrigger')


    ###########################################################
    def OnStdRegion(self, event=None):
        """Handle changes to any UI elements for the "standard" type region.

        @param  event  One of a number of event types.  Ignored
        """
        label = self._standardRegionChoice.GetStringSelection()
        regionName = self._standardRegionField.GetValue()
        regionName = normalizePath(regionName)

        setting = _kStandardRegionLabelToSetting[label]

        self._whereBlockDataModel.setRegionName(regionName)
        self._whereBlockDataModel.setTriggerType('regionTrigger')
        self._whereBlockDataModel.setRegionType(setting)


    ###########################################################
    def OnDoorRegion(self, event=None):
        """Handle changes to any UI elements for the door-type region.

        @param  event  One of a number of event types.  Ignored
        """
        label = self._doorRegionChoice.GetStringSelection()

        setting = _kDoorRegionLabelToSetting[label]

        self._whereBlockDataModel.setTriggerType('doorTrigger')
        self._whereBlockDataModel.setDoorType(setting)


    ###########################################################
    def OnDirection(self, event=None):
        """Handle the user selecting the "direction" radio button.

        @param  event  One of a number of event types.  Ignored
        """
        self._whereBlockDataModel.setTriggerType('lineTrigger')


    ###########################################################
    def OnChangeDirection(self, event=None):
        """Handle the "change direction" button.

        @param  event  One of a number of event types.  Ignored
        """
        # Have the VideoWindow do it, so that "Undo" works right...
        triggerLineSegment = self._whereBlockDataModel.getLineSegment()
        self._videoWindow.changeLineTriggerDirection(triggerLineSegment)


    ###########################################################
    def _setHelpText(self, newHelpText):
        """Update the help text label, including wrapping.

        @param  newHelpText  The new help text to set.
        """
        # Due to weirdnesses of wx, we need to re-create the control to get
        # wrapping to work.  Ick.  We still set the min size to make sure it
        # takes up the right amount of space.
        newHelpLabel = wx.StaticText(self, -1, newHelpText)
        makeFontDefault(newHelpLabel)
        newHelpLabel.SetForegroundColour(_kHelpTextColor)
        newHelpLabel.SetMinSize(self._helpLabelMinSize)

        self._whereSettingsSizer.Replace(self._helpLabel, newHelpLabel)
        self._helpLabel.Destroy()
        self._helpLabel = newHelpLabel
        self._whereSettingsSizer.Layout()


    ###########################################################
    def _updateFromModels(self, modelThatChanged=None):
        """Update settings based on the changed data model.

        @param  modelThatChanged  The model that changed.
        """
        # Update where controls.
        if not modelThatChanged or \
               modelThatChanged == self._whereBlockDataModel:
            disablableComponents = set([
                self._standardRegionField,
            ])
            toEnable = set()

            newHelpText = ""

            # TODO: Show in video window.

            # Always set the region name, even if the field will be disabled.
            # I'm not sure if this is right, but it seems like a good idea...
            regionName  = self._whereBlockDataModel.getRegionName()
            if regionName != self._standardRegionField.GetValue():
                self._standardRegionField.SetValue(regionName)
                self._standardRegionField.SetInsertionPointEnd()

            # Always set door type / region type too, so that the user doesn't
            # see it change (even if that type isn't selected).
            doorType = self._whereBlockDataModel.getDoorType()
            label = _kDoorRegionSettingToLabel[doorType]
            self._doorRegionChoice.SetStringSelection(label)

            regionType  = self._whereBlockDataModel.getRegionType()
            label = _kStandardRegionSettingToLabel[regionType]
            self._standardRegionChoice.SetStringSelection(label)

            triggerType = self._whereBlockDataModel.getTriggerType()
            if triggerType == 'blankTrigger':
                self._anywhereRadio.SetValue(1)
                newHelpText = _kHelpTextAnywhere
                self._videoWindow.setTriggerRegions([])
                self._videoWindow.setTriggerLineSegments([])

                self._durationBlockDataModel.setWantMoreThan(True)
            elif triggerType == 'lineTrigger':
                self._directionRadio.SetValue(1)
                newHelpText = _kHelpTextDirection

                self._videoWindow.setTriggerRegions([])
                self._videoWindow.setTriggerLineSegments([
                    self._whereBlockDataModel.getLineSegment()
                ])

                self._durationBlockDataModel.setWantMoreThan(False)
            elif triggerType == 'doorTrigger':
                self._doorRegionRadio.SetValue(1)
                newHelpText = _kHelpTextDoorRegion

                self._videoWindow.setTriggerLineSegments([])
                self._videoWindow.setTriggerRegions([
                    self._whereBlockDataModel.getRegion()
                ])

                self._durationBlockDataModel.setWantMoreThan(False)
            else:
                assert triggerType == 'regionTrigger'

                self._standardRegionRadio.SetValue(1)
                toEnable.add(self._standardRegionField)
                if regionType == 'ground':
                    newHelpText = _kHelpTextGroundRegion
                else:
                    newHelpText = _kHelpTextStandardRegion

                self._videoWindow.setTriggerLineSegments([])
                self._videoWindow.setTriggerRegions([
                    self._whereBlockDataModel.getRegion()
                ])

                self._durationBlockDataModel.setWantMoreThan(
                    regionType not in ['entering', 'exiting', 'crosses'])

            for component in toEnable:
                component.Enable(True)
            for component in disablableComponents - toEnable:
                component.Enable(False)

            self._setHelpText(newHelpText)

        # Update duration controls.
        if not modelThatChanged or \
               modelThatChanged == self._durationBlockDataModel:
            # TODO: constrain min / max of spinners?

            wantMoreThan  = self._durationBlockDataModel.getWantMoreThan()
            if wantMoreThan:
                moreThanValue = self._durationBlockDataModel.getMoreThanValue()
            else:
                moreThanValue = 0
            moreThanUnits = self._durationBlockDataModel.getMoreThanUnits()
            moreThanUnits = _kTimeUnitSettingToLabel[moreThanUnits]

            assert not self._durationBlockDataModel.getWantLessThan(), \
                   "Less than UI has been removed."

            self._moreThanSpinner.SetValue(moreThanValue)
            self._moreThanSpinner.Enable(wantMoreThan)
            self._moreThanSpinner.SetRange(0, _kMaxDuration)
            self._moreThanUnits.SetLabel(moreThanUnits)



##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "NO TESTS"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
