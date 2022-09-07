#!/usr/bin/env python

#*****************************************************************************
#
# ResponseConstructionBlock.py
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
from appCommon.CommonStrings import kCommandResponse
from appCommon.CommonStrings import kEmailResponse
from appCommon.CommonStrings import kIftttResponse
from appCommon.CommonStrings import kWebhookResponse
from appCommon.CommonStrings import kPushResponse
from appCommon.CommonStrings import kRecordResponse
from appCommon.CommonStrings import kSoundResponse
from appCommon.CommonStrings import kFtpResponse
from appCommon.CommonStrings import kLocalExportResponse

# Constants...
_kColor = (105, 205, 105)    # Green-ish


# Mapping from stored constants to user-visible strings...
_kResponseStrMap = {
    kCommandResponse:      "Run command",
    kEmailResponse:        "Send mail",
    kIftttResponse:        "Trigger IFTTT",
    kWebhookResponse:      "Trigger Webhook",
    kPushResponse:         "Send mobile alert",
    kRecordResponse:       "Save",
    kSoundResponse:        "Play sound",
    kFtpResponse:          "Save",
    kLocalExportResponse:  "Save",
}

_kResponseNone = "(Click here for\noptions)"
_kResponseStrMultiple = "Take action"
_kResponseStrMultipleSave = "%s and\ntake action" % \
                            _kResponseStrMap[kRecordResponse]

# Using bitflags, can make a map to bitmaps...
_kBitmapMap = {
    kCommandResponse:      "frontEnd/bmps/Block_Icon_Command.png",
    kEmailResponse:        "frontEnd/bmps/Block_Icon_Email.png",
    kIftttResponse:        "frontEnd/bmps/Block_Icon_Email.png",
    kWebhookResponse:      "frontEnd/bmps/Block_Icon_Email.png",
    kPushResponse:         "frontEnd/bmps/Block_Icon_Email.png",
    kRecordResponse:       "frontEnd/bmps/Block_Icon_Rec.png",
    kSoundResponse:        "frontEnd/bmps/Block_Icon_Sound.png",
    kFtpResponse:          "frontEnd/bmps/Block_Icon_Rec.png",
    kLocalExportResponse:  "frontEnd/bmps/Block_Icon_Rec.png",
}

_kBitmapPathMultiple = "frontEnd/bmps/Block_Icon_Mult.png"
_kBitmapPathMultipleSave = "frontEnd/bmps/Block_Icon_Mult_Rec.png"


##############################################################################
class ResponseConstructionBlock(ConstructionBlock):
    """The construction block for a camera."""

    ###########################################################
    def __init__(self, parent, dataModel,
                 pos=wx.DefaultPosition, size=kDefaultConstructionBlockSize):
        """ResponseConstructionBlock constructor.

        @param  parent     Our parent UI element.
        @param  dataModel  The SavedQueryDataModel.
        @param  pos        Our UI position.
        @param  size       Our UI size.
        """
        # Store parameters first, so we can call _figureOutLabel
        self._dataModel = dataModel

        # Things we need to get out to pass to our super...
        icon = self._figureOutBitmap()
        label = self._figureOutLabel()

        # Call our super
        super(ResponseConstructionBlock, self).__init__(
            parent, icon, label, _kColor, pos, size
        )

        # Listen for changes.
        self._dataModel.addListener(self._handleModelChange, False, 'responses')


    ###########################################################
    def _figureOutLabel(self):
        """Figure out our label, based on our data model.

        @return label  Our label.
        """
        enabledResponses = set()

        responseConfigList = self._dataModel.getResponses()
        for responseName, config in responseConfigList:
            if config.get('isEnabled'):
                responseStr = _kResponseStrMap.get(responseName, "")
                assert responseStr, \
                       "Need a response string for %s" % responseName
                enabledResponses.add(responseStr)

        if not enabledResponses:
            label = _kResponseNone
        elif len(enabledResponses) == 1:
            label = enabledResponses.pop()
        elif _kResponseStrMap[kRecordResponse] in enabledResponses:
            label = _kResponseStrMultipleSave
        else:
            label = _kResponseStrMultiple

        return label


    ###########################################################
    def _figureOutBitmap(self):
        """Figure out our bitmap, based on our data model.

        @return bitmap  Our bitmap.
        """
        enabledResponses = set()
        bmp = None
        bmpPath = None

        responseConfigList = self._dataModel.getResponses()
        for responseName, config in responseConfigList:
            if config.get('isEnabled'):
                bmpPath = _kBitmapMap.get(responseName)
                assert bmpPath, "Need a bitmap for %s" % responseName
                enabledResponses.add(bmpPath)

        if not enabledResponses:
            pass
        elif len(enabledResponses) == 1:
            bmpPath = enabledResponses.pop()
        elif _kBitmapMap[kRecordResponse] in enabledResponses:
            bmpPath = _kBitmapPathMultipleSave
        else:
            bmpPath = _kBitmapPathMultiple

        if bmpPath is not None:
            bmp = wx.Bitmap(bmpPath)
            assert bmp.IsOk(), bmpPath
        else:
            bmp = None

        return bmp


    ###########################################################
    def _handleModelChange(self, dataModel):
        """Handle changes to our model.

        @param  dataModel  Our data model.
        """
        assert dataModel == self._dataModel
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
