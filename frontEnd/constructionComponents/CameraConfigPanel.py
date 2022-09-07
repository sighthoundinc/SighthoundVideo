#!/usr/bin/env python

#*****************************************************************************
#
# CameraConfigPanel.py
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

# Toolbox imports...
from vitaToolbox.wx.FudgedChoice import FudgedChoice
from vitaToolbox.wx.MaxBestSizer import MaxBestSizer


# Local imports...
from appCommon.CommonStrings import kAnyCameraStr
from appCommon.CommonStrings import kImportSuffix, kImportDisplaySuffix
from ConfigPanel import ConfigPanel

# Constants...


##############################################################################
class CameraConfigPanel(ConfigPanel):
    """The block configuration panel for a camera."""

    ###########################################################
    def __init__(self, parent, cameraBlockDataModel, cameraLocations):
        """CameraConfigPanel constructor.

        @param  parent                Our parent UI element.
        @param  cameraBlockDataModel  The data model for the camera block.
        @param  cameraLocations       A list of the camera locations.
        """
        # Call our super
        super(CameraConfigPanel, self).__init__(parent)

        # Cleanup params...
        if not cameraLocations:
            cameraLocations = [kAnyCameraStr]

        # Save params that we need...
        self._cameraBlockDataModel = cameraBlockDataModel


        # Create our UI elements...

        # Create the camera choice.  Curr select will be set from model later.
        cameraLabel = wx.StaticText(self, -1, "Camera:")
        self._cameraChoice = FudgedChoice(self, -1, choices=cameraLocations,
                                          fudgeList=[(kImportSuffix,
                                                      kImportDisplaySuffix)])
        self._cameraChoice.SetMinSize((1, -1))
        self._cameraChoice.Enable(len(cameraLocations) > 1)
        self._cameraChoice.Bind(wx.EVT_CHOICE, self.OnCameraChoice)

        # Throw our stuff into sizers...
        settingsSizer = wx.FlexGridSizer(rows=1, cols=2, vgap=5, hgap=5)
        settingsSizer.AddGrowableCol(1)
        settingsSizer.Add(cameraLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        settingsSizer.Add(MaxBestSizer(self._cameraChoice), 1, wx.EXPAND)

        # Use a border sizer to give a little space
        borderSizer = wx.BoxSizer()
        borderSizer.Add(settingsSizer, 1, wx.EXPAND | wx.TOP, 15)
        self.SetSizer(borderSizer)

        # Listen for changes...
        self._cameraBlockDataModel.addListener(self._updateFromModels)

        # Update everything...
        self._updateFromModels()


    ###########################################################
    def getIcon(self):
        """Return the path to the bitmap associated with this panel.

        @return bmpPath  The path to the bitmap.
        """
        return "frontEnd/bmps/Block_Icon_Camera.png"


    ###########################################################
    def getTitle(self):
        """Return the title associated with this panel.

        @return title  The title
        """
        return "Video Source"


    ###########################################################
    def _updateFromModels(self, modelThatChanged=None):
        """Update all of our settings based on our data models.

        @param  modelThatChanged  The model that changed (ignored).
        """
        _ = modelThatChanged

        camera = self._cameraBlockDataModel.getLocationName()

        self._cameraChoice.SetStringSelection(camera)


    ###########################################################
    def OnCameraChoice(self, event=None):
        """Handle when the user changes cameras.

        @param  event  The choice event (ignored)
        """
        chosenCamera = self._cameraChoice.GetStringSelection()
        self._cameraBlockDataModel.setLocationName(chosenCamera)



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
