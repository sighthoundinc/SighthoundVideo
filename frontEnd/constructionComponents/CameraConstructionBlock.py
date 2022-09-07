#!/usr/bin/env python

#*****************************************************************************
#
# CameraConstructionBlock.py
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
_kColor = (181,  66,  66)    # Red-ish


##############################################################################
class CameraConstructionBlock(ConstructionBlock):
    """The construction block for a camera."""

    ###########################################################
    def __init__(self, parent, cameraBlockDataModel,
                 pos=wx.DefaultPosition, size=kDefaultConstructionBlockSize):
        """CameraConstructionBlock constructor.

        @param  parent                Our parent UI element.
        @param  cameraBlockDataModel  The data model for the camera block.
        @param  pos                   Our UI position.
        @param  size                  Our UI size.
        """
        # Store parameters first, so we can call _figureOutLabel
        self._cameraBlockDataModel = cameraBlockDataModel

        # Things we need to get out to pass to our super...
        icon = wx.Bitmap("frontEnd/bmps/Block_Icon_Camera.png")
        label = self._figureOutLabel()

        # Call our super
        super(CameraConstructionBlock, self).__init__(
            parent, icon, label, _kColor, pos, size
        )

        # Listen for changes so we can update our label...
        self._cameraBlockDataModel.addListener(self._handleModelChange,
                                               True)


    ###########################################################
    def _figureOutLabel(self):
        """Figure out our label, based on our data model.

        @return label  Our label.
        """
        return self._cameraBlockDataModel.getLocationName()


    ###########################################################
    def _handleModelChange(self, model, whatChanged):
        """Handle changes to our model.

        @param  model        Our data model.
        @param  whatChanged  What changed: 'locationName' or 'resolution'.
        """
        assert model == self._cameraBlockDataModel

        if whatChanged == 'locationName':
            self.SetLabel(self._figureOutLabel())


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
