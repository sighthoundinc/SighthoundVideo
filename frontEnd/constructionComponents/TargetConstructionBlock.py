#!/usr/bin/env python

#*****************************************************************************
#
# TargetConstructionBlock.py
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
import sys

# Common 3rd-party imports...
import wx

# Local imports...
from ConstructionBlock import ConstructionBlock, kDefaultConstructionBlockSize
from appCommon.CommonStrings import kTargetSettingToLabel

# Constants...
_kColor = ( 95,  73, 180)    # Purple


##############################################################################
class TargetConstructionBlock(ConstructionBlock):
    """The construction block for a camera."""

    ###########################################################
    def __init__(self, parent, targetBlockDataModel,
                 pos=wx.DefaultPosition, size=kDefaultConstructionBlockSize):
        """TargetConstructionBlock constructor.

        @param  parent                Our parent UI element.
        @param  targetBlockDataModel  The data model for this target block.
        @param  pos                   Our UI position.
        @param  size                  Our UI size.
        """
        # Store parameters first, so we can call _figureOutLabel
        self._targetBlockDataModel = targetBlockDataModel

        # Things we need to get out to pass to our super...
        icon = self._figureOutBitmap()
        label = self._figureOutLabel()

        # Call our super
        super(TargetConstructionBlock, self).__init__(
            parent, icon, label, _kColor, pos, size
        )

        # Listen for changes so we can update our label...
        self._targetBlockDataModel.addListener(self._handleModelChange)


    ###########################################################
    def _figureOutLabel(self):
        """Figure out our label, based on our data model.

        @return label  Our label.
        """
        target = self._targetBlockDataModel.getTargetName()
        # any long labels need to be broken into multiple lines
        return kTargetSettingToLabel[target].replace(' ', '\n')


    ###########################################################
    def _figureOutBitmap(self):
        """Figure out our bitmap, based on our data model.

        @return bitmap  Our bitmap.
        """
        targetName = self._targetBlockDataModel.getTargetName()
        #action = self._targetBlockDataModel.getActionName()
        if targetName == 'person':
            #if action == 'climbing':
            #    bmpPath = "frontEnd/bmps/Block_Icon_Person_Climbing.png"
            #elif action == 'crawling':
            #    bmpPath = "frontEnd/bmps/Block_Icon_Person_Crawling.png"
            #elif action == 'falling':
            #    bmpPath = "frontEnd/bmps/Block_Icon_Person_Falling.png"
            #elif action == 'running':
            #    bmpPath = "frontEnd/bmps/Block_Icon_Person_Running.png"
            #elif action == 'walking':
            #    bmpPath = "frontEnd/bmps/Block_Icon_Person_Walking.png"
            #else:
                bmpPath = "frontEnd/bmps/Block_Icon_Person.png"
        elif targetName == 'animal':
            bmpPath = "frontEnd/bmps/Block_Icon_Pet.png"
        elif targetName == 'vehicle':
            bmpPath = "frontEnd/bmps/Block_Icon_Vehicle.png"
        elif targetName == 'object':
            bmpPath = "frontEnd/bmps/Block_Icon_Object.png"
        elif targetName == 'anything':
            bmpPath = "frontEnd/bmps/Block_Icon_All.png"
        else:
            bmpPath = "frontEnd/bmps/questionMark.png"

        return wx.Bitmap(bmpPath)


    ###########################################################
    def _handleModelChange(self, model):
        """Handle changes to our model.

        @param  model        Our data model.
        """
        assert model == self._targetBlockDataModel

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
