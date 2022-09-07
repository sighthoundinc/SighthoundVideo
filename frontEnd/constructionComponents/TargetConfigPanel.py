#!/usr/bin/env python

#*****************************************************************************
#
# TargetConfigPanel.py
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
import operator
import sys

# Common 3rd-party imports...
from PIL import Image, ImageDraw
import wx

# Local imports...
from ConfigPanel import ConfigPanel
from appCommon.CommonStrings import kTargetSettingToLabel, kTargetLabelToSetting, kTargetLabels

# Constants...

_kTargetLabelStr = "Look for:"


_kWantMinSizeStr = "Ignore objects smaller than:"
_kMinSizeValues = [ 30, 40, 50, 60, 70 ]
_kMinSizeStrs = [
    "%d pixels" % (val) for val in _kMinSizeValues
]

_kShowMinSizeLabelStr = "Show how tall this is in the image above"

_kOverlayImageWidth = 25
_kOverlayBackgroundColor = (255, 255, 255, 127)
_kOverlayLineColor = (0, 204, 0, 127)
_kOverlayLineWidth = 3


##############################################################################
class TargetConfigPanel(ConfigPanel):
    """The block configuration panel for a camera."""

    ###########################################################
    def __init__(self, parent, videoWindow, targetBlockDataModel):
        """TargetConfigPanel constructor.

        @param  parent                Our parent UI element.
        @param  videoWindow           The videoWindow.
        @param  targetBlockDataModel  The data model for this target block.
        """
        # Call our super
        super(TargetConfigPanel, self).__init__(parent)

        # Keep track of params...
        self._videoWindow = videoWindow
        self._targetBlockDataModel = targetBlockDataModel

        # Create our UI elements...

        # Create the target choice.  Curr select will be set from model later.
        targetLabel = wx.StaticText(self, -1, _kTargetLabelStr)
        self._targetChoice = wx.Choice(self, -1, choices=kTargetLabels)
        self._targetChoice.Bind(wx.EVT_CHOICE, self.OnTargetChoice)

        self._wantMinSizeCheckbox = wx.CheckBox(self, -1, _kWantMinSizeStr)
        self._wantMinSizeCheckbox.Bind(wx.EVT_CHECKBOX,
                                       self.OnWantMinSizeCheckbox)
        self._minSizeChoice = wx.Choice(self, -1, choices=_kMinSizeStrs)
        self._minSizeChoice.Bind(wx.EVT_CHOICE, self.OnMinSizeChoice)

        self._showMinSizeCheckbox = wx.CheckBox(self, -1, _kShowMinSizeLabelStr)
        self._showMinSizeCheckbox.Bind(wx.EVT_CHECKBOX, self.OnShowMinSizeCheckbox)

        # Throw our stuff into our sizer...
        targetSizer = wx.BoxSizer(wx.HORIZONTAL)
        targetSizer.Add(targetLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        targetSizer.Add(self._targetChoice, 1, wx.ALIGN_CENTER_VERTICAL)

        minSizeSizer = wx.BoxSizer(wx.HORIZONTAL)
        minSizeSizer.Add(self._wantMinSizeCheckbox, 0,
                         wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        minSizeSizer.Add(self._minSizeChoice, 1, wx.ALIGN_CENTER_VERTICAL)

        showMinSizeSizer = wx.BoxSizer()
        showMinSizeSizer.Add(self._showMinSizeCheckbox, 0, wx.LEFT, 15)

        # Use a border sizer to give a little space
        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(targetSizer, 0, wx.EXPAND | wx.TOP, 15)
        borderSizer.Add(minSizeSizer, 0, wx.EXPAND | wx.TOP, 10)
        borderSizer.Add(showMinSizeSizer, 0, wx.EXPAND | wx.TOP, 5)
        self.SetSizer(borderSizer)

        # Listen for changes.
        self._targetBlockDataModel.addListener(self._updateFromModels)

        # Update everything...
        self._updateFromModels()


    ###########################################################
    def getIcon(self):
        """Return the path to the bitmap associated with this panel.

        @return bmpPath  The path to the bitmap.
        """
        return "frontEnd/bmps/Block_Icon_Look_For.png"


    ###########################################################
    def getTitle(self):
        """Return the title associated with this panel.

        @return title  The title
        """
        return "Look for"


    ###########################################################
    def activate(self):
        """Set this panel as the active one."""
        self._updateFromModels(None)


    ###########################################################
    def deactivate(self):
        """Called before another panel gets activate."""
        self._videoWindow.setOverlayImage(None)


    ###########################################################
    def _updateFromModels(self, modelThatChanged=None):
        """Update all of our settings based on our data models.

        @param  modelThatChanged  The model that changed (ignored).
        """
        _ = modelThatChanged

        target = self._targetBlockDataModel.getTargetName()
        target = kTargetSettingToLabel[target]
        self._targetChoice.SetStringSelection(target)

        minSize = self._targetBlockDataModel.getMinSize()
        try:
            minSizeSelection = _kMinSizeValues.index(minSize)
            self._minSizeChoice.SetSelection(minSizeSelection)
        except ValueError:
            pass

        wantMinSize = self._targetBlockDataModel.getWantMinSize()
        if not wantMinSize:
            self._wantMinSizeCheckbox.SetValue(0)
            self._minSizeChoice.Enable(False)
            self._showMinSizeCheckbox.SetValue(0)
            self._showMinSizeCheckbox.Enable(False)
            self._videoWindow.setOverlayImage(None)
        else:
            self._wantMinSizeCheckbox.SetValue(1)
            self._minSizeChoice.Enable(True)

            self._showMinSizeCheckbox.Enable(True)
            showMinSize = self._targetBlockDataModel.getShowMinSize()
            self._showMinSizeCheckbox.SetValue(int(showMinSize))
            if showMinSize:
                overlayImage = self._makeOverlayImage(minSize)
                self._videoWindow.setOverlayImage(overlayImage)
            else:
                self._videoWindow.setOverlayImage(None)


    ###########################################################
    def _makeOverlayImage(self, height):
        """Make an image showing how tall the "height" is.

        @param  height  The height to show.
        @return img     A PIL Image.
        """
        img = Image.new('RGBA', (_kOverlayImageWidth, height), 0)
        imgDraw = ImageDraw.Draw(img)

        imgDraw.rectangle((_kOverlayLineWidth, _kOverlayLineWidth,
                           _kOverlayImageWidth - _kOverlayLineWidth,
                           height - _kOverlayLineWidth),
                          fill=_kOverlayBackgroundColor)
        for i in xrange(_kOverlayLineWidth):
            imgDraw.rectangle((i, i, _kOverlayImageWidth-i-1, height-i-1),
                              outline=_kOverlayLineColor)

        label = str(height)
        labelWidth, labelHeight = imgDraw.textsize(label)
        imgDraw.text(((_kOverlayImageWidth-labelWidth)/2,
                      (height-labelHeight)/2), label, fill="black")

        return img


    ###########################################################
    def OnTargetChoice(self, event=None):
        """Handle when the user changes targets.

        @param  event  The choice event (ignored)
        """
        target = self._targetChoice.GetStringSelection()
        target = kTargetLabelToSetting[target]
        self._targetBlockDataModel.setTargetName(target)


    ###########################################################
    def OnWantMinSizeCheckbox(self, event=None):
        """Handle when the user changes "want min size" checkbox.

        @param  event  The choice event (ignored)
        """
        wantMinSize = self._wantMinSizeCheckbox.GetValue()
        self._targetBlockDataModel.setWantMinSize(bool(wantMinSize))


    ###########################################################
    def OnMinSizeChoice(self, event=None):
        """Handle when the user changes min size.

        @param  event  The choice event (ignored)
        """
        minSizeIndex = self._minSizeChoice.GetSelection()
        if minSizeIndex != -1:
            self._targetBlockDataModel.setMinSize(_kMinSizeValues[minSizeIndex])
        else:
            assert False, "Bad min size choice"


    ###########################################################
    def OnShowMinSizeCheckbox(self, event=None):
        """Handle when the user changes "show min size" checkbox.

        @param  event  The choice event (ignored)
        """
        showMinSize = self._showMinSizeCheckbox.GetValue()
        self._targetBlockDataModel.setShowMinSize(bool(showMinSize))


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
