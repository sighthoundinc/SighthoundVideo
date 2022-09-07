#!/usr/bin/env python

#*****************************************************************************
#
# WhereConstructionBlock.py
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

# Python imports...
import sys

# Common 3rd-party imports...
import wx

# Local imports...
from ConstructionBlock import ConstructionBlock, kDefaultConstructionBlockSize

# Constants...
_kColor = (105, 154, 205)    # Light blue


##############################################################################
class WhereConstructionBlock(ConstructionBlock):
    """The construction block for region and direction triggers."""

    ###########################################################
    def __init__(self, parent,
                 whereBlockDataModel, durationBlockDataModel,
                 pos=wx.DefaultPosition, size=kDefaultConstructionBlockSize):
        """WhereConstructionBlock constructor.

        @param  parent                  Our parent UI element.
        @param  dataMgr                 The data manager for the app.
        @param  cameraBlockDataModel    The data model for the camera block.
                                        Needed so we can figure out what to
                                        show in the video box.
        @param  whereBlockDataModel     The data model for this block.
        @param  durationBlockDataModel  The data model for 'duration' updates.
        @param  pos                     Our UI position.
        @param  size                    Our UI size.
        """
        # Store parameters first, so we can call _figureOutLabel
        self._whereBlockDataModel = whereBlockDataModel
        self._durationBlockDataModel = durationBlockDataModel

        # Things we need to get out to pass to our super...
        icon = self._figureOutBitmap()
        label = self._figureOutLabel()

        # Call our super
        super(WhereConstructionBlock, self).__init__(
            parent, icon, label, _kColor, pos, size
        )

        # Listen for changes so we can update our label...
        self._whereBlockDataModel.addListener(self._handleModelChange, True)


    ###########################################################
    def _figureOutLabel(self):
        """Figure out our label, based on our data model.

        @return label  Our label.
        """
        triggerType = self._whereBlockDataModel.getTriggerType()
        if triggerType == 'blankTrigger':
            label = "Anywhere"
        elif triggerType == 'lineTrigger':
            label = "Crossing\na boundary"
        elif triggerType == 'doorTrigger':
            doorType    = self._whereBlockDataModel.getDoorType()
            if doorType == 'entering':
                label = "Entering\nthrough a door"
            elif doorType == 'exiting':
                label = "Leaving\nthrough a door"
            elif doorType == 'any':
                label = "Entering/Leaving\nthrough a door"
            else:
                assert False, "Unknown door type: %s" % doorType
        else:
            assert triggerType == 'regionTrigger'

            regionType  = self._whereBlockDataModel.getRegionType()
            regionName  = self._whereBlockDataModel.getRegionName()
            if not regionName.strip():
                regionName = 'my region'

            if regionType == 'inside':
                label = "Inside\n" + regionName
            elif regionType == 'outside':
                label = "Outside\n" + regionName
            elif regionType == 'entering':
                label = "Entering\n" + regionName
            elif regionType == 'exiting':
                label = "Exiting\n" + regionName
            elif regionType == 'crosses':
                label = "Entering/Exiting\n" + regionName
            elif regionType == 'ground':
                label = "On top of\n" + regionName
            else:
                assert False, "Unknown region type: %s" % regionType

        return label


    ###########################################################
    def _figureOutBitmap(self):
        """Figure out our bitmap, based on our data model.

        @return bitmap  Our bitmap.
        """
        triggerType = self._whereBlockDataModel.getTriggerType()
        if triggerType == 'blankTrigger':
            bmpPath =  "frontEnd/bmps/Block_Icon_Anywhere.png"
        elif triggerType == 'lineTrigger':
            bmpPath =  "frontEnd/bmps/Block_Icon_Direction.png"
        elif triggerType == 'doorTrigger':
            doorType  = self._whereBlockDataModel.getDoorType()
            if doorType == 'entering':
                bmpPath =  "frontEnd/bmps/Block_Icon_Coming_Through.png"
            elif doorType == 'exiting':
                bmpPath =  "frontEnd/bmps/Block_Icon_Going_Out.png"
            elif doorType == 'any':
                bmpPath =  "frontEnd/bmps/Block_Icon_Coming_Or_Going.png"
            else:
                assert False, "Unknown door type: %s" % doorType
        else:
            assert triggerType == 'regionTrigger'

            regionType  = self._whereBlockDataModel.getRegionType()

            if regionType == 'inside':
                bmpPath =  "frontEnd/bmps/Block_Icon_Inside_Region.png"
            elif regionType == 'outside':
                bmpPath =  "frontEnd/bmps/Block_Icon_Outside_Region.png"
            elif regionType == 'entering':
                bmpPath =  "frontEnd/bmps/Block_Icon_Entering_Region.png"
            elif regionType == 'exiting':
                bmpPath =  "frontEnd/bmps/Block_Icon_Exiting_Region.png"
            elif regionType == 'crosses':
                bmpPath =  "frontEnd/bmps/Block_Icon_Exiting_Or_Exiting_Region.png"
            elif regionType == 'ground':
                bmpPath =  "frontEnd/bmps/Block_Icon_On_Top_Of_Region.png"
            else:
                assert False, "Unknown region type: %s" % regionType

        bmp = wx.Bitmap(bmpPath)
        assert bmp.IsOk(), bmpPath
        return bmp


    ###########################################################
    def _handleModelChange(self, model, whatChanged):
        """Handle changes to our model.

        @param  model        Our data model.
        @param  whatChanged  What changed: 'locationName' or 'resolution'.
        """
        _ = whatChanged
        assert model == self._whereBlockDataModel

        self.SetLabel(self._figureOutLabel())
        self.SetBitmap(self._figureOutBitmap())


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
