#!/usr/bin/env python

#*****************************************************************************
#
# FtpStatusDialog.py
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
import time

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.sysUtils.TimeUtils import formatTime

# Local imports...
from appCommon.CommonStrings import kFtpProtocol


# Constants...
_kDialogTitle = "FTP status"


_kAreYouSureTitle = "FTP uploads"
_kAreYouSureText = (
    """Are you sure you want to cancel the upload of pending video clips? """
    """Video stored on your computer will not be affected."""
)

_kClearQueueButtonText = "Cancel pending uploads"

_kDialogTemplate = (
'''Last clip uploaded to FTP site: %%(lastRecordedStr)s.

Clips waiting to be uploaded: %%(queueLength)d

To skip clips waiting for upload, click "%s."'''
) % (_kClearQueueButtonText)

_kNoClipsUploadedText = "No clips have been uploaded"
_kRecordedAtTemplate = "recorded at %(timeStr)s on %(dateStr)s"
_kTimeTemplate = "%I:%M %p"  # Will swap case on this, and strip leading 0.
_kDateTempalte = "%x"        # Will strip off leading 0 on this.


##############################################################################
class FtpStatusDialog(wx.Dialog):
    """A dialog for setting up ftp upload."""

    ###########################################################
    def __init__(self, parent, backEndClient):
        """FtpStatusDialog constructor.

        @param  parent             Our parent UI element.
        @param  backEndClient      A client to talk to the back end.
        """
        # Call our super
        super(FtpStatusDialog, self).__init__(
            parent, title=_kDialogTitle
        )

        try:
            self._backEndClient = backEndClient

            self._initUiWidgets()
            self.Fit()
            self.CenterOnParent()
        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _makeMainText(self):
        """Make the main text of the dialog.

        @return mainStr       The main label of the dialog.
        @return isQueueEmpty  True if the queue is empty.
        """
        queueLength, startTime, stopTime, processAt, sentAt, ruleName = \
            self._backEndClient.getPendingClipInfo(kFtpProtocol)

        if startTime is None:
            lastRecordedStr = _kNoClipsUploadedText
        else:
            startTimeSecs = startTime/1000
            startTimeStruct = time.localtime(startTimeSecs)

            timeStr = formatTime(_kTimeTemplate, startTimeStruct).swapcase().lstrip('0')
            dateStr = formatTime(_kDateTempalte, startTimeStruct).lstrip('0')

            lastRecordedStr = _kRecordedAtTemplate % {
                'timeStr': timeStr,
                'dateStr': dateStr,
            }

        mainStr = _kDialogTemplate % {
            'lastRecordedStr': lastRecordedStr,
            'queueLength': queueLength,
        }
        return mainStr, (queueLength == 0)


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        # Do the work to make the main string of the dialog...
        mainStr, isQueueEmpty = self._makeMainText()
        self._mainLabel = wx.StaticText(self, -1, mainStr,
                                        style=wx.ST_NO_AUTORESIZE)

        # We use the StdDialogButtonSizer(), but yet add some normal buttons
        # too.  I'm not sure if this is intended by wxpython, or if it's
        # kosher UI, but it seems to work and does about what I'd expect.
        buttonSizer = wx.StdDialogButtonSizer()

        self._clearQueueButton = wx.Button(self, -1, _kClearQueueButtonText)
        self._clearQueueButton.Enable(not isQueueEmpty)
        buttonSizer.Add(self._clearQueueButton, 0, wx.LEFT | wx.RIGHT, 12)

        self._okButton = wx.Button(self, wx.ID_OK)
        buttonSizer.AddButton(self._okButton)

        self._okButton.SetDefault()
        buttonSizer.Realize()


        # Throw things in sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        mainSizer.Add(self._mainLabel, 0, wx.EXPAND | wx.BOTTOM, 20)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
        borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

        self.SetSizer(borderSizer)

        self.Bind(wx.EVT_BUTTON, self.OnClearQueue, self._clearQueueButton)
        self.Bind(wx.EVT_BUTTON, self.OnOK, self._okButton)


    ###########################################################
    def OnOK(self, event):
        """Respond to the user pressing OK

        @param  event  The button event
        """
        self.EndModal(wx.ID_OK)


    ###########################################################
    def OnClearQueue(self, event):
        """Respond to the user pressing the "Cancel Pending Uploads" button.

        @param  event  The button event
        """
        choice = wx.MessageBox(_kAreYouSureText, _kAreYouSureTitle,
                               wx.YES_NO | wx.NO_DEFAULT, self)
        if choice == wx.YES:
            self._backEndClient.purgePendingClips(kFtpProtocol)

            mainStr, isQueueEmpty = self._makeMainText()
            self._clearQueueButton.Enable(not isQueueEmpty)
            self._mainLabel.SetLabel(mainStr)

            self.Fit()


