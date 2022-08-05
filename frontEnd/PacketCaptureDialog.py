#!/usr/bin/env python

#*****************************************************************************
#
# PacketCaptureDialog.py
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
import time
import os
import shutil
import zipfile

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.wx.FontUtils import adjustPointSize
from vitaToolbox.wx.TextCtrlUtils import setHyperlinkColors
from vitaToolbox.wx.TextSizeUtils import makeFontUnderlined
from vitaToolbox.sysUtils.TimeUtils import getTimeAsString, getDateAsString, formatTime

# Local imports...
from appCommon.CommonStrings import kSupportEmail
from frontEnd.FrontEndUtils import getUserLocalDataDir

# Constants...
_kPcapTitle = "Camera Diagnostics"
_kPcapTimeCaption = "Capturing will stop in:"
_kPcapExplanationCaption = \
    "Please allow one full minute to capture as much data as possible.\n\n" \
    "WARNING: The information collected may contain sensitive data, \n" \
    "including the camera's URL, username and password. If this is a concern \n" \
    "please first change your camera's password both on device and in \n" \
    "Sighthound Video.\n\n" \
    "Please press 'Start' below to begin.\n" \
    "This process can be cancelled at any time."
_kErrorSavingTitle = "Error Saving Report"
_kErrorSavingText = (
    """There was a problem saving the diagnostics report: %s"""
)
_kAllDoneTitle = "Thanks!"
_kAllDoneSavingStr = (
    """Your diagnostics report has been saved.  \nPlease send it to %s."""
) % kSupportEmail

_kIsWin = "win32" == sys.platform

# Min / max on time spinner...
_kMinSeconds = 1
_kMaxSeconds = 2 * 60

# We'll run the timer once a second...
_kDelayTimerMs = 1000

# The width of the delay text...
_kDelayWidth = 350

# Small amount of seconds to give the pcap process enough time to finish...
_kDelaySecondsBuffer = 2

# Pcap status result codes.
_kPcapComplete = 0
_kPcapStreamOpen = 1
_kPcapStreamFailure = -1
_kPcapGeneralFailure = -2

# Pcap enabled result codes.
_kPcapInitSuccess = 0
_kPcapInsufficientPrivileges = -1
_kPcapDriverNotInstalledOrInactive = -2
_kPcapCaptureIsAlreadyEnabled = -3

# Error messages displayed to the user.
_kPcapErrGeneralFailure = "An unknown error has occured!"
_kPcapErrInsufficientPrivileges = "Admin rights are needed to capture packets!"
_kPcapErrNeedWinpcap = "WinPCAP is not installed or inactive, and is needed \n" \
                       "to capture packets on Windows."
_kWinPcapReboot = "A reboot is required after WinPCAP installation."
_kPcapErrNeedPcap = "Packet capture capabilities could \n" \
                    "not be found on this system!"
_kPcapErrCaptureInProgress = "Packet capture is already enabled or in progress!"

# Internet address for winpcap.
_kWinpcapUrl = "http://www.winpcap.org/install/default.htm"


##############################################################################
def HandlePacketCaptureRequest(parent, logger, backEndClient, cameraLocation, delaySeconds):
    """Show the packet capture box.

    @param  parent          The parent window.
    @param  logger          logger instance to use.
    @param  backEndClient   A proxy to the back end.
    @param  cameraLocation  The name of the camera to run and log packet
                            capturing.
    @param  delaySeconds    The time alloted to packet capturing for the IP
                            camera.
    """
    userLocalDataDir = getUserLocalDataDir()

    pcapDirName = 'pcap_' + formatTime("%Y%m%d%H%M%S")
    pcapDirPath = os.path.join(userLocalDataDir, pcapDirName)

    packetCaptureInfo = {}

    dlg = _PacketCaptureBox(parent, logger, backEndClient, cameraLocation, delaySeconds, pcapDirPath)
    try:
        result = dlg.ShowModal()
        if result != wx.ID_OK:
            cleanupPcapFiles(logger, pcapDirPath)
            return
        packetCaptureInfo = dlg.packetCaptureInfo
    except:
        logger.error("Dialog exception!", exc_info=True)
    finally:
        dlg.Destroy()

    logger.info("packetCaptureInfo=%s" % packetCaptureInfo)

    pcapEnabled = packetCaptureInfo.get("pcapEnabled")

    if pcapEnabled == _kPcapInitSuccess:
        # Pcap was initialized successfully. Ask the user where they want their
        # diagnostics report saved to, and then acquire the relevant files and
        # zip them up at that location.
        errStr = ""
        didSave = False

        # Allow the user to save the zip file wherever they want...
        dlg = wx.FileDialog(parent, "Save",
                            wx.StandardPaths.Get().GetDocumentsDir(),
                            "%s.zip" % pcapDirName, style=wx.FD_SAVE |
                            wx.FD_OVERWRITE_PROMPT)
        try:
            result = dlg.ShowModal()
            if result == wx.ID_OK:
                savePath = dlg.GetPath()
                numFiles = 0
                with zipfile.ZipFile(savePath, 'w') as zipFp:
                    for root, dirs, files in os.walk(pcapDirPath):
                        for f in files:
                            zipFp.write(
                                os.path.join(root, f),
                                os.path.join(root.split(userLocalDataDir)[-1], f)
                            )
                            numFiles += 1
                didSave = True
                logger.info("Num files zipped: %s" % numFiles)
        except:
            logger.error("Could not save the zip file!", exc_info=True)
        finally:
            dlg.Destroy()

        if didSave:
            wx.MessageBox(_kAllDoneSavingStr, _kAllDoneTitle,
                          wx.OK | wx.ICON_INFORMATION, parent)
        elif errStr:
            wx.MessageBox(_kErrorSavingText % errStr, _kErrorSavingTitle,
                          wx.OK | wx.ICON_ERROR, parent)

    elif _kIsWin and (pcapEnabled == _kPcapDriverNotInstalledOrInactive):
        # For Windows only: If the winpcap driver is not installed or inactive,
        # provide a link to the user where they can find the installer for
        # winpcap.
        dlg = _NeedWinPcapBox(parent)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()

    else:
        # An error occurred while initializing packet capture; inform the user...
        msg = _kPcapErrGeneralFailure
        if pcapEnabled == _kPcapInsufficientPrivileges:
            msg = _kPcapErrInsufficientPrivileges
        elif pcapEnabled == _kPcapCaptureIsAlreadyEnabled:
            msg = _kPcapErrCaptureInProgress
        elif pcapEnabled == _kPcapDriverNotInstalledOrInactive:
            msg = _kPcapErrNeedPcap

        dlg = wx.MessageDialog(
            parent,
            msg,
            _kPcapTitle,
            wx.ICON_ERROR,
        )
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()

    # Cleanup after ourselves...
    cleanupPcapFiles(logger, pcapDirPath)


##############################################################################
def cleanupPcapFiles(logger, pcapDir):
    """Deletes the packet capture directory.

    @param  logger      Logger instance.
    @param  pcapDir     Directory where pcap-associated files are stored.
    """
    try:
        if os.path.exists(pcapDir) and os.path.isdir(pcapDir):
            shutil.rmtree(pcapDir)
    except:
        logger.error(
            "The pcap files could not be deleted, or they don't exist!!",
            exc_info=True
        )


##############################################################################
class _PacketCaptureBox(wx.Dialog):
    """The packet capture dialog."""

    ###########################################################
    def __init__(self, parent, logger, backEndClient, cameraLocation, delaySeconds, pcapDir):
        """AboutBox constructor.

        @param  parent          The parent window.
        @param  logger          logger instance to use.
        @param  backEndClient   A proxy to the back end.
        @param  cameraLocation  The name of the camera to run and log packet
                                capturing.
        @param  delaySeconds    The time alloted to packet capturing for the IP
                                camera.
        @param  pcapDir         The directory where packet capture information
                                will be saved.
        """
        # Call our super
        super(_PacketCaptureBox, self).__init__(
            parent, title=_kPcapTitle
        )

        self._backEndClient = backEndClient
        self._cameraLocation = cameraLocation
        self._logger = logger
        self._delaySeconds = delaySeconds
        self._pcapDir = pcapDir
        self._timeLeft = int(round(self._delaySeconds))
        self._doCountDown = False
        self._delayEndsAt = 0

        # Exposed properties...
        self.packetCaptureInfo = {}

        try:
            self._initUiWidgets()
            self.Fit()
            self.CenterOnParent()
        except:
            # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        self._explanationLabel = wx.StaticText(self, -1, _kPcapExplanationCaption,
                                           style=wx.ST_NO_AUTORESIZE)

        self._timeLeftCaption = wx.StaticText(self, -1, _kPcapTimeCaption,
                                           style=wx.ST_NO_AUTORESIZE)
        self._timeLeftCaption.Hide()

        self._timeLeftLabel = wx.StaticText(self, -1, "",
                                            style=wx.ST_NO_AUTORESIZE |
                                            wx.ALIGN_CENTER)
        self._timeLeftLabel.Hide()
        adjustPointSize(self._timeLeftLabel, 2)
        self._timeLeftLabel.SetMinSize((_kDelayWidth, -1))

        # We use the StdDialogButtonSizer() in case we later want to add more
        # weird buttons...
        buttonSizer = wx.StdDialogButtonSizer()

        self._startButton = wx.Button(self, wx.ID_ANY, "Start")
        self._cancelButton = wx.Button(self, wx.ID_CANCEL)

        buttonSizer.AddButton(self._startButton)
        buttonSizer.SetAffirmativeButton(self._startButton)
        buttonSizer.AddButton(self._cancelButton)

        self._cancelButton.SetDefault()
        self._cancelButton.SetFocus()
        buttonSizer.Realize()

        # Throw things in sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        mainSizer.Add(self._explanationLabel, 0, wx.EXPAND | wx.BOTTOM)
        mainSizer.Add(self._timeLeftCaption, 0, wx.EXPAND | wx.BOTTOM, 10)
        mainSizer.Add(self._timeLeftLabel, 0, wx.EXPAND | wx.BOTTOM, 20)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
        borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

        self.SetSizer(borderSizer)

        # Bind to UI stuff...
        self.Bind(wx.EVT_BUTTON, self.OnStart, self._startButton)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self._cancelButton)

        # Make timer and bind to it...
        self._timer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self._timer)

        # Update the text...
        self.OnTimer()


    ###########################################################
    def _toggleShowHideUIWidgets(self):
        """Hides the explanation, and shows the timer info and timer.
        """
        isShown = self._explanationLabel.IsShown()

        for w in [self._explanationLabel]:
            w.Show(not isShown)

        for w in [self._timeLeftLabel, self._timeLeftCaption]:
            w.Show(isShown)

        self.Fit()
        self.CenterOnParent()


    ###########################################################
    def OnStart(self, event):

        # Disable the start button to prevent the user from running all of this
        # again...
        self._startButton.Disable()
        self._toggleShowHideUIWidgets()

        # Stop the camera first, then enable it with the appropriate arguments
        # for packet capturing...
        self._backEndClient.enableCamera(self._cameraLocation, False)
        self._backEndClient.stopPacketCapture()
        self._backEndClient.startPacketCapture(
                self._cameraLocation, self._delaySeconds, self._pcapDir
        )

        # Start the timer, but not the countdown. We have to wait till the user
        # successfully authenticates AND pcap initializes successfully before
        # we can start counting down.
        self._timer.Start(_kDelayTimerMs)


    ###########################################################
    def OnTimer(self, event=None):
        """Update the time left label, and dismiss the dialog if needed.

        @param  event  The event; Will be None when this box is being initialized.
        """
        if event is None:
            # Initialize the time amount for count down...
            self._timeLeft = int(round(self._delaySeconds))
        elif self._doCountDown:
            # Calculate the timeleft...
            self._timeLeft = max(self._delayEndsAt - time.time(), 0)
            self._timeLeft = int(round(self._timeLeft))

        # Update the UI...
        minutesLeft, secondsLeft = divmod(self._timeLeft, 60)
        self._timeLeftLabel.SetLabel("%02d:%02d" % (minutesLeft, secondsLeft))

        # Grab the pcap progress from the backend...
        self.packetCaptureInfo = \
            self._backEndClient.getPacketCaptureInfo()

        pcapEnabled = self.packetCaptureInfo.get('pcapEnabled', None)
        pcapStatus = self.packetCaptureInfo.get('pcapStatus', None)

        # Start the countdown if packet capturing was initialized successfully...
        if not self._doCountDown and pcapEnabled == _kPcapInitSuccess:
            self._delayEndsAt = time.time() + self._delaySeconds
            self._doCountDown = True

        # We cleanup and end modal if the count down reaches 0:00, if there is
        # an error during pcap initialization, or if pcap completes before the
        # countdown does. Check if event is None so we _don't_ cleanup and end
        # modal, because it means this box is being initialized.
        if (((event is not None) and (self._timeLeft == 0))                 or
            ((pcapEnabled is not None) and (pcapEnabled != _kPcapInitSuccess))  or
            ((pcapStatus is not None) and (pcapStatus == _kPcapComplete))   ):
            self._cleanupAndEndModal(wx.ID_OK)


    ###########################################################
    def OnCancel(self, event):
        """Respond to the user pressing Cancel

        @param  event  The button event
        """
        self._cleanupAndEndModal(wx.ID_CANCEL)


    ###########################################################
    def _cleanupAndEndModal(self, wxID):
        """Cleanup and end modal.

        @param  wxID    A valid wx ID for ending the modal (examples: wx.ID_OK,
                        wx.ID_CANCEL, etc).
        """
        try:
            if self._timer.IsRunning():
                self._timer.Stop()
            self._backEndClient.stopPacketCapture()

        except:
            # We want to catch *everything* here so that the "EndModal" call
            # is successful.
            self._logger.error("Exception on cleanup: ", exc_info=True)

        finally:
            self.EndModal(wxID)


##############################################################################
class _NeedWinPcapBox(wx.Dialog):
    """The packet capture dialog."""

    ###########################################################
    def __init__(self, parent):
        """AboutBox constructor.

        @param  parent  The parent window.
        """
        # Call our super
        super(_NeedWinPcapBox, self).__init__(
            parent, wx.ID_ANY, _kPcapTitle
        )

        try:
            self._initUiWidgets()
            self.Fit()
            self.CenterOnParent()
        except:
            # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise


    ###########################################################
    def _initUiWidgets(self):
        """Init / bind all of the UI widgets that go in our sizer..."""

        mainMessage = wx.StaticText(
            self, wx.ID_ANY, _kPcapErrNeedWinpcap, style=wx.ST_NO_AUTORESIZE
        )
        captionLeft = wx.StaticText(
            self, wx.ID_ANY, "Please click ", style=wx.ST_NO_AUTORESIZE
        )
        referenceLink = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, "here", _kWinpcapUrl)
        setHyperlinkColors(referenceLink)
        makeFontUnderlined(referenceLink)
        captionRight = wx.StaticText(
            self, wx.ID_ANY, " to download WinPCAP.", style=wx.ST_NO_AUTORESIZE
        )
        rebootRequiredText = wx.StaticText(
            self, wx.ID_ANY, _kWinPcapReboot, style=wx.ST_NO_AUTORESIZE
        )

        # We use the StdDialogButtonSizer() in case we later want to add more
        # weird buttons...
        buttonSizer = wx.StdDialogButtonSizer()
        buttonSizer.AddButton(
                wx.Button(self, wx.ID_OK)
        )
        buttonSizer.Realize()

        # Throw things in sizers...
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(mainMessage, 0, wx.EXPAND)
        mainSizer.Add(hsizer, 1, wx.EXPAND | wx.BOTTOM, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(captionLeft, 0, wx.EXPAND)
        hsizer.Add(referenceLink, 0, wx.EXPAND)
        hsizer.Add(captionRight, 0, wx.EXPAND)
        mainSizer.Add(hsizer, 1, wx.EXPAND | wx.BOTTOM, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(rebootRequiredText, 0, wx.EXPAND)
        mainSizer.Add(hsizer, 1, wx.EXPAND)

        borderSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer.Add(mainSizer, 1, wx.EXPAND | wx.ALL, 12)
        borderSizer.Add(buttonSizer, 0, wx.EXPAND | wx.BOTTOM, 12)

        self.SetSizer(borderSizer)


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    print "No tests"


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
