#!/usr/bin/env python

#*****************************************************************************
#
# OptionsDialog.py
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
import os, time, pickle, sys, threading, socket, random
from SocketServer import TCPServer, BaseRequestHandler

# Common 3rd-party imports...
import wx

# Local imports...
from appCommon.CommonStrings import kVideoFolder
from appCommon.CommonStrings import kWebDirName
from appCommon.CommonStrings import kWebDirEnvVar
from appCommon.CommonStrings import kStatusFile
from appCommon.CommonStrings import kStatusKeyVerified
from appCommon.CommonStrings import kStatusKeyNumber
from appCommon.CommonStrings import kStatusKeyPort
from appCommon.CommonStrings import kStatusKeyPortOpenerState
from appCommon.CommonStrings import kStatusKeyRemotePort
from appCommon.CommonStrings import kStatusKeyRemoteAddress
from appCommon.CommonStrings import kStatusKeyCertificateId
from appCommon.CommonStrings import kStorageDetailUrl
from appCommon.CommonStrings import kRemoteAccessUrl
from appCommon.LicenseUtils import hasPaidEdition
from LocateVideoDialog import LocateVideoDialog
from MoveVideoDialog import MoveVideoDialog
from FrontEndUtils import setServiceStartsBackend
from FrontEndUtils import setServiceAutoStart, getServiceAutoStart
from FrontEndUtils import getUserLocalDataDir
from FrontEndUtils import promptUserIfAutoStartEvtHandler
from FrontEndUtils import determineGridViewCameras
from FrontEndPrefs import getFrontEndPref, setFrontEndPref
import backEnd.BackEndPrefs as Prefs

# vitaToolbox imports...
from vitaToolbox.path.GetDiskSpaceAvailable import getDiskSpaceAvailable
from vitaToolbox.path.VolumeUtils import getVolumeNameAndType
from vitaToolbox.path.VolumeUtils import getStorageSizeStr
from vitaToolbox.wx.TextCtrlUtils import setHyperlinkColors, CharValidator
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8, ensureUnicode


# Globals...
_kPaddingSize = 4
_kBorderSize = 20
_kSpaceSize1 = 12
_kSpaceSize2 = 16

if wx.Platform == '__WXMSW__':
    _kDialogTitle = "Options"
else:
    _kDialogTitle = "Preferences"


_kTimeLabel = "Time format:"
_kDateLabel = "Date format:"
_kTime12Hour = "12 Hour - 11:00:00 PM"
_kTime24Hour = "24 Hour - 23:00:00"
_kDateUS = "US - January 8, 2016"
_kDateInternatinal = "International - 8 January 2016"
_kSupportLabel = "Warn when my support and upgrade subscription is expiring"

_kVideoLocLabel = "Video is stored on %s (%s)"
_kDiskSpaceLabel = "Available disk space on %s (%s): %s"
_kStorageNote = (
"""Note: All video is saved for the duration specified above. Video\n"""
"""not matching "save" rules is then deleted and the resulting clips\n"""
"""are kept until the disk space quota is reached.\n\n"""
"""Temporary video is useful in the event something occurs that did\n"""
"""not match a rule but the video is still desired. Most users should\n"""
"""set the temporary storage as low as is acceptable and the disk \n"""
"""space allocation as high as possible."""
)

_kRemoteDescription = (
"""Remote access allows you to view clips and videos from the web \n"""
"""browser of any computer or mobile device. For access outside\n"""
"""your local network you will need to configure port forwarding on\n"""
"""your router."""
)

_kEnableRemoteLabel = "Enable remote access"
_kUsernameLabel = "Login user ID: "
_kPasswordLabel = "Login password: "
_kVerifyLabel = "Verify password: "
_kPortLabel = "Remote access port: "
_kPortOpenerEnabledLabel = "Open this port in my router"
_kFakePassword = "----------"
_kDefaultPort = 8848

_kMinPasswordLength = 6
_kMaxUserPassLength = 128
_kErrorTitle = "Error"
_kNonAsciiBody = "Username and password cannot contain international characters."
_kInvalidUsernameBody = "You must specify a username."
_kPasswordsMatchBody = "The password fields must match."
_kPasswordsLengthBody = "Your password must be at least %i characters." % \
        _kMinPasswordLength
_kPortErrorBody = "Port must be an integer between 1025 and 65535."
_kPortNABody = "Port %d is in use by a different application. Please choose another."

_kNotebookGeneral = "General";
_kNotebookStorage = "Storage";
_kNotebookRemoteAccess = "Remote Access";
_kNotebookGrid = "Grid";

_kStorageSizeGBMin = 1
_kStorageSizeGBMax = 999999
_kCacheSizeMinutesMin = 1
_kCacheSizeMinutesMax = 9999


_kGridRowsLabel = "Rows: "
_kGridColsLabel = "Columns: "
_kGridOrderLabel = "Order:"
_kGridFpsLabel = "Framerate: "
_kGridMoveUp = "Move up"
_kGridMoveDown = "Move Down"

kWebServerStatusLabel = "Server status: "
kWebServerStatusNA = "Unknown"
kWebServerStatusOff = "Off"
kWebServerStatusNotVerified = "Starting..."
kWebServerStatusOn = "Running"
kWebServerStatusUpdating = "Updating..."

kWebServerLocURL = "Local address: "
kWebServerIntURL = "Internal address: "
kWebServerExtURL = "External address: "
kWebServerExtStatusOff = "Unable to automatically verify"
kWebServerExtStatusNA = "Unable to automatically verify"
kWebServerCertificateId = "SSL Fingerprint: "

_kMbps = 1024*1024
_kBitrates =      [-1, .5*_kMbps, _kMbps,   2*_kMbps, 3*_kMbps, 4*_kMbps, 5*_kMbps]
_kBitrateLabels = ["No limit", ".5 Mbps", "1 Mbps", "2 Mbps", "3 Mbps", "4 Mbps", "5 Mbps"]
_kVideoQualityProfile = [ 0, 10, 20, 30 ]
_kVideoQualityProfileLabels = [ "Original", "High", "Medium", "Low" ]
_kVideoResolutions = [ -1, 1080, 720, 480, 240 ]
_kVideoResolutionLabels = [ "Original", "1080p", "720p", "480p", "240p" ]

# Interval for web server status polling, in milliseconds.
kWebServerStatusRefresh = 1000

_kLaunchOnStartupLabel = "Run Sighthound Video at system startup"
_kIsWin = wx.Platform == '__WXMSW__'

# To generate the remote access URLs
kHttpScheme = "https"
kHttpAddress = kHttpScheme + "://%s:%d"
kHttpLocalHost = "127.0.0.1"

_kGridShowInactiveCameras = "Show inactive cameras"
_kGridMoveInactiveCameras = "Move inactive cameras to the end of the list"


###############################################################
class GetInternalIPThread(threading.Thread):
    """ Tries to the determine the most likely internal/intranet address of the
    the machine. If we're connected directly to the Internet (no NAT) then this
    would be not very internal of course.
    """
    def __init__(self, logger):
        threading.Thread.__init__(self)
        self._logger = logger
        # the IPv4 address, or None if we haven't gotten anything (yet)
        self.result = None
    def run(self):
        attempts = 3   # retry, in case some UDP ports are problematic(?)
        while 0 < attempts:
            attempts -= 1
            port = 50000 + random.randrange(0,9999)
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setblocking(0)
                s.settimeout(0.5)
                # the target IP is the DNS server of Google, yet no traffic is
                # ever going to hit it since we won't send a single packet...
                s.connect(('8.8.8.8', port))
                self.result = s.getsockname()[0]
                return
            except:
                self._logger.warn("port %d failed (%s)" %
                                  (port, sys.exc_info()[1]))
                continue
            finally:
                if s is not None:
                    try: s.close()
                    except: pass

###############################################################

# Custom event mechanism to transport the web server status from the gathering
# thread to the options dialog ...
myEVT_WEBSERVERSTATUS = wx.NewEventType()
EVT_WEBSERVERSTATUS = wx.PyEventBinder(myEVT_WEBSERVERSTATUS, 1)
class WebServerStatusEvent(wx.PyCommandEvent):
    def __init__(self, status):
        wx.PyCommandEvent.__init__(self, myEVT_WEBSERVERSTATUS, -1)
        self._status = status
    def GetStatus(self):
        """ Returns the web server status, or None if the status file could not
        be opened (or does not exist yet). """
        return self._status

# TODO: could be done via wx workers instead, given that they have the same
#       possibilities for early termination/interruption ...

class WebServerStatusThread(threading.Thread):
    """ Background thread trying to read the web server status with a certain
    delay of in between each attempt.
    @param dialog The associated dialog or parent frame respectively.
    @param pollSecs The interval delay in seconds.
    """
    def __init__(self, dialog, pollIntvl=1):
        threading.Thread.__init__(self)
        self._dialog = dialog
        self._pollIntvl = pollIntvl
        self._evt = threading.Event()

    def stop(self):
        """ Signals the thread to stop and wait for such to happen. """
        self._evt.set()
        self.join()

    def run(self):
        """ Runs the main thread loop, getting the status now and then. """
        while not self._evt.isSet():
            if not self.runSync():
                break
            self._evt.wait(self._pollIntvl)

    def runSync(self):
        """ Runs the blocking portion of the thread. And also the part where we
        send events to the parent. This is useful e.g. for some initial
        determination of the status.
        @return False if a thread stop got detected. """
        s = self._readWebServerStatusFile()
        if self._evt.isSet():
            return False
        wx.PostEvent(self._dialog, WebServerStatusEvent(s))
        return True

    def _readWebServerStatusFile(self, timeout=.5):
        """ To read the web server status from the file it emits on start and
        every time here is a change. Since it might be written/renamed at the
        same time we do our readout there might be multiple attempts needed to
        be successful.
        @param timeout Number of seconds to wait until giving up.
        @return The web server status information as a dictionary or None if
        the status file didn't appear, or its information couldn't be parsed
        or if we the thread is going down.
        """
        webDir = os.environ.get(kWebDirEnvVar)
        if not webDir:
            userLocalDataDir = getUserLocalDataDir()
            webDir = os.path.join(userLocalDataDir, kWebDirName)
        statusFile = os.path.join(webDir, kStatusFile)
        end = time.time() + timeout
        while not self._evt.isSet():
            h = None
            try:
                h = open(statusFile, "rb")
                return pickle.load(h)
            except:
                if time.time() > end or self._evt.isSet():
                    return None
                time.sleep(.1)
            finally:
                if h is not None:
                    try: h.close()
                    except: pass
        return None

###############################################################
class OptionsDialog(wx.Dialog):
    """A dialog for configuring app settings."""
    ###########################################################
    def __init__(self, parent, backEndClient, dataManager, logger,
            uiPrefsModel):
        """Initializer for OptionsDialog.

        @param  parent         The parent window.
        @param  backEndClient  An object for communicating with the back end.
        @param  dataManager    An interface to the database and video files.
        @param  logger         The caller's log instance to share.
        @param  uiPrefsModel   The caller's log instance to share.
        """
        wx.Dialog.__init__(self, parent, -1, _kDialogTitle, size=(400, -1))

        try:
            self._backEndClient = backEndClient
            self._dataMgr = dataManager
            self._logger = logger
            self._uiPrefsModel = uiPrefsModel

            self._hwDevices = self._backEndClient.getHardwareDevicesList()
            self._hwDevice = self._backEndClient.getHardwareDevice()

            try:
                self._hasPaid = hasPaidEdition(backEndClient.getLicenseData())
            except Exception, e:
                self._logger.error(str(e))
                self._hasPaid = False

            # try to get the internal IP address as quickly as possible...
            self._internalIP = GetInternalIPThread(self._logger)
            self._internalIP.start()

            self._origStorageSize = \
                self._backEndClient.getMaxStorageSize()
            self._origCacheSize = self._backEndClient.getCacheDuration()
            self._origRecordInMemory = self._backEndClient.getRecordInMemory()

            # Create the top sizer.
            mainSizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(mainSizer)
            self._notebook = wx.Notebook(self, -1)

            defaultPanel = wx.Panel(self._notebook, -1)

            sizer = wx.BoxSizer(wx.VERTICAL)

            # Create the options controls.
            s = wx.FlexGridSizer(0, 2, _kPaddingSize, _kPaddingSize)

            storageLabel = wx.StaticText(
                defaultPanel, -1, "For clips and temporary video, use up to:"
            )
            self._storageSizeCtrl = wx.TextCtrl(defaultPanel, -1, "", size=(80,-1), validator=CharValidator(CharValidator.kAllowDigits))
            self._storageSizeCtrl.SetMaxLength(len(str(_kStorageSizeGBMax)))
            self._storageSizeCtrl.SetValue(str(self._origStorageSize))
            storageSizer = wx.BoxSizer(wx.HORIZONTAL)
            storageSizer.Add(self._storageSizeCtrl, 0, wx.EXPAND)
            storageSizer.Add(wx.StaticText(defaultPanel, -1, "GB"), 0, wx.EXPAND | wx.ALL, _kPaddingSize)

            cacheLabel = wx.StaticText(defaultPanel, -1,
                                       "Temporarily keep all video for up to:")
            self._cacheSizeCtrl= wx.TextCtrl(defaultPanel, -1, "", size=(64,-1), validator=CharValidator(CharValidator.kAllowDigits))
            self._cacheSizeCtrl.SetValue(str(self._origCacheSize))
            self._cacheSizeCtrl.SetMaxLength(len(str(_kCacheSizeMinutesMax)))
            cacheSizer= wx.BoxSizer(wx.HORIZONTAL)
            cacheSizer.Add(self._cacheSizeCtrl, 0, wx.ALIGN_CENTER_VERTICAL)
            cacheSizer.Add(wx.StaticText(defaultPanel, -1, "Hours"), 0,
                           wx.ALL | wx.ALIGN_CENTER_VERTICAL, _kPaddingSize)

            tempVideoLabel = wx.StaticText(defaultPanel, -1, "Buffer newly received video")
            self._tempVideoSystemDriveRadio = wx.RadioButton(defaultPanel, -1, "on system drive",
                    style=wx.RB_GROUP)
            self._tempVideoMemoryRadio = wx.RadioButton(defaultPanel, -1, "in memory")
            self._tempVideoSystemDriveRadio.SetValue(not self._origRecordInMemory)
            self._tempVideoMemoryRadio.SetValue(self._origRecordInMemory)

            tempVideoSizer = wx.BoxSizer(wx.HORIZONTAL)
            tempVideoSizer.AddMany([(tempVideoLabel, 0, wx.LEFT),
                        (self._tempVideoSystemDriveRadio, 0, wx.LEFT),
                        (self._tempVideoMemoryRadio)])


            videoLocation = self._backEndClient.getVideoLocation()
            volumeName = "Unknown"
            volumeType = "Unknown"
            bytesFree = -1
            try:
                volumeName, volumeType = getVolumeNameAndType(videoLocation)
                bytesFree = getDiskSpaceAvailable(videoLocation)
            except Exception:
                import traceback
                self._logger.warning("Except: " + traceback.format_exc())
                pass

            self._locLabel = wx.StaticText(defaultPanel, -1,
                                            ensureUnicode(_kVideoLocLabel
                                                        % (volumeType, volumeName)))
            locButton = wx.Button(defaultPanel, -1, "Move video...")
            locButton.Bind(wx.EVT_BUTTON, self.OnMoveVideo)

            sizeStr = getStorageSizeStr(bytesFree)
            self._spaceFree = wx.StaticText(defaultPanel, -1,
                                            ensureUnicode(_kDiskSpaceLabel %
                                                    (volumeType, volumeName, sizeStr)))

            storageNotice = wx.StaticText(defaultPanel, -1, _kStorageNote)
            storageNotice2 = wx.StaticText(defaultPanel, -1, "For further details click ")
            storageLink = wx.adv.HyperlinkCtrl(defaultPanel, wx.ID_ANY, "here", kStorageDetailUrl)
            setHyperlinkColors(storageLink)
            storageNotice3 = wx.StaticText(defaultPanel, -1, ".")

            s.AddMany([(storageLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                        _kPaddingSize),
                       (storageSizer, 1, wx.EXPAND),
                       (cacheLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                        _kPaddingSize),
                       (cacheSizer, 1, wx.EXPAND),
                       (self._locLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT |
                        wx.RIGHT, _kPaddingSize),
                       (locButton, 0, wx.LEFT | _kPaddingSize),
                       ])

            sizer.AddSpacer(_kSpaceSize1)
            sizer.Add(s, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)
            sizer.AddSpacer(_kSpaceSize1)
            sizer.Add(self._spaceFree, 0, wx.LEFT | wx.RIGHT, _kBorderSize)

            sizer.AddSpacer(_kSpaceSize1)
            sizer.Add(tempVideoSizer, 1, wx.LEFT | wx.RIGHT, _kBorderSize )

            sizer.AddSpacer(_kSpaceSize1)
            sizer.AddStretchSpacer(1)
            sizer.Add(storageNotice, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddStretchSpacer(1)
            sizer.AddSpacer(_kSpaceSize1)

            helpSizer = wx.BoxSizer(wx.HORIZONTAL)
            helpSizer.Add(storageNotice2)
            helpSizer.Add(storageLink)
            helpSizer.Add(storageNotice3)
            sizer.Add(helpSizer, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kSpaceSize2)

            defaultPanel.SetSizer(sizer)

            generalPanel = self._createGeneralPanel()
            gridPanel = self._createGridPanel()
            self._notebook.AddPage(generalPanel, _kNotebookGeneral)
            self._notebook.AddPage(defaultPanel, _kNotebookStorage)
            self._notebook.AddPage(gridPanel, _kNotebookGrid)
            if self._hasPaid:
                remotePanel = self._createRemoteAccessPanel()
                self._notebook.AddPage(remotePanel, _kNotebookRemoteAccess)

            mainSizer.Add(self._notebook, 1,
                    wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _kSpaceSize2)

            # Add the ok button.
            self._okButton = wx.Button(self, -1, "OK")
            self._okButton.Bind(wx.EVT_BUTTON, self.OnOk)
            okSizer = wx.BoxSizer(wx.HORIZONTAL)
            okSizer.AddStretchSpacer(1)
            okSizer.Add(self._okButton, 0, wx.EXPAND)
            mainSizer.Add(okSizer, 0, wx.EXPAND | wx.ALL, _kSpaceSize2)

            self.SetEscapeId(wx.ID_CANCEL)
            wx.Button(self, wx.ID_CANCEL, "", size=(0, 0), style=wx.NO_BORDER)

            self.Fit()
            self.CenterOnParent()


        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise

    ###########################################################
    def _createGeneralPanel(self):
        """ Create the general panel (time settings etc).

        @return  New panel instance.
        """

        panel = wx.Panel(self._notebook, -1)
        sizer = wx.BoxSizer(wx.VERTICAL)

        was12Time, wasUSDate = self._uiPrefsModel.getTimePreferences()
        warnSupport = self._uiPrefsModel.shouldShowSupportWarning()
        self._clipMergeLimit = self._backEndClient.getClipMergeThreshold()

        self._wasAutoStart = getServiceAutoStart()

        hasHwControls = len(self._hwDevices)>0
        hasHwChoice = len(self._hwDevices)>1
        hwEnabled = self._hwDevice != "none"

        if hasHwControls:
            self._enableHardwareAcceleration = wx.CheckBox(panel, -1, "Enable hardware-accelerated decoder")
            self._enableHardwareAcceleration.SetValue(hwEnabled)
        else:
            self._enableHardwareAcceleration = None

        if hasHwChoice:
            devList = ["auto"] + self._hwDevices
            self._hwDevicesChoice = wx.Choice(panel, -1, choices=devList)
            if self._hwDevice in self._hwDevices:
                self._hwDevicesChoice.SetSelection(self._hwDevicesChoice.FindString(self._hwDevice))
            else:
                self._hwDevicesChoice.SetSelection(0)
            self._hwDevicesChoice.Enable(hwEnabled)
        else:
            self._hwDevicesChoice = None

        self._launchOnStartup = wx.CheckBox(panel, -1, _kLaunchOnStartupLabel)
        self._launchOnStartup.SetValue(self._wasAutoStart)

        timeLabel = wx.StaticText(panel, -1, _kTimeLabel)
        dateLabel = wx.StaticText(panel, -1, _kDateLabel)
        self._time12Radio = wx.RadioButton(panel, -1, _kTime12Hour,
                style=wx.RB_GROUP)
        self._time24Radio = wx.RadioButton(panel, -1, _kTime24Hour)
        self._dateUSRadio = wx.RadioButton(panel, -1, _kDateUS,
                style=wx.RB_GROUP)
        self._dateInternationalRadio = wx.RadioButton(panel, -1,
                _kDateInternatinal)
        self._combineCheckbox = wx.CheckBox(panel, -1, label="Join clips that are within ")
        self._combineCheckbox.SetValue( self._clipMergeLimit > 0 )
        kMaxClipPaddingSec = 15 # we allow maximum of 15s distance for clips to be bridged
        self._combineTimeLimit = wx.Choice(panel, -1, choices=[str(x) for x in range(0,kMaxClipPaddingSec+1)])
        self._combineTimeLimit.SetSelection(self._clipMergeLimit)
        self._combineTimeLimit.Enable( self._clipMergeLimit > 0 )
        unit = wx.StaticText(panel, -1, " seconds of each other")


        if was12Time:
            self._time12Radio.SetValue(True)
        else:
            self._time24Radio.SetValue(True)

        if wasUSDate:
            self._dateUSRadio.SetValue(True)
        else:
            self._dateInternationalRadio.SetValue(True)

        sizer.AddSpacer(_kSpaceSize1)
        gridSizer = wx.FlexGridSizer(0, 2, 2*_kPaddingSize, 2*_kPaddingSize)
        gridSizer.Add(timeLabel)
        gridSizer.AddSpacer(1)
        gridSizer.AddMany([(self._time12Radio, 0, wx.LEFT, 2*_kPaddingSize), (self._time24Radio)])
        gridSizer.Add(dateLabel)
        gridSizer.AddSpacer(1)
        gridSizer.AddMany([(self._dateUSRadio, 0, wx.LEFT, 2*_kPaddingSize), (self._dateInternationalRadio)])
        sizer.Add(gridSizer, 0, wx.LEFT | wx.RIGHT, _kBorderSize)

        sizer.AddStretchSpacer(1)

        combineClipsSizer = wx.BoxSizer(wx.HORIZONTAL)
        combineClipsSizer.Add(self._combineCheckbox, 0, wx.LEFT)
        combineClipsSizer.Add(self._combineTimeLimit, 0, wx.LEFT)
        combineClipsSizer.Add(unit, 0, wx.LEFT)
        sizer.AddSpacer(_kSpaceSize1)
        sizer.Add(combineClipsSizer, 0, wx.LEFT | wx.RIGHT, _kBorderSize)


        if hasHwControls:
            hwControlSizer = wx.BoxSizer(wx.HORIZONTAL)
            hwControlSizer.Add(self._enableHardwareAcceleration, 0, wx.LEFT)
            if hasHwChoice:
                hwControlSizer.Add(self._hwDevicesChoice, 0, wx.LEFT)
            sizer.AddSpacer(_kSpaceSize1)
            sizer.Add(hwControlSizer, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
            sizer.AddSpacer(_kSpaceSize1)


        sizer.Add(self._launchOnStartup, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
        sizer.AddSpacer(_kSpaceSize1)

        self._supportCheck = wx.CheckBox(panel, -1, _kSupportLabel)
        self._supportCheck.SetValue(warnSupport)
        sizer.Add(self._supportCheck, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
        sizer.AddSpacer(_kSpaceSize1)

        panel.SetSizer(sizer)

        self.Bind(wx.EVT_CHECKBOX, promptUserIfAutoStartEvtHandler, self._launchOnStartup)
        self._combineCheckbox.Bind(wx.EVT_CHECKBOX, self.OnCombineClips)
        if hasHwChoice:
            self._enableHardwareAcceleration.Bind(wx.EVT_CHECKBOX, self.OnHwAccelerationChange)


        return panel

    ##########################################################
    def _createGridPanel(self):
        """ Create the panel where the grid view can be configured.

        @return  New panel instance.
        """

        panel = wx.Panel(self._notebook, -1)

        # The main sizer to contain it all.
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.AddSpacer(_kSpaceSize1)

        # Grid sizer for most of the layout stuff here.
        flexGridSizer = wx.FlexGridSizer(0, 2, _kPaddingSize, _kPaddingSize)

        # Add the dimension (rows/columns) controls.
        rowsLabel = wx.StaticText(panel, -1, _kGridRowsLabel)
        colsLabel = wx.StaticText(panel, -1, _kGridColsLabel)
        orderLabel = wx.StaticText(panel, -1, _kGridOrderLabel)
        choices = list(map(lambda i: str(i), xrange(1, 10)))
        style = wx.CB_DROPDOWN + wx.CB_READONLY
        cols = str(getFrontEndPref("gridViewCols"))
        rows = str(getFrontEndPref("gridViewRows"))
        self._gridColsComboBox = wx.ComboBox(panel, value=cols, choices=choices, style=style)
        self._gridRowsComboBox = wx.ComboBox(panel, value=rows, choices=choices, style=style)
        flexGridSizer.AddMany([
            (colsLabel, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, _kPaddingSize),
            (self._gridColsComboBox, 1),
            (rowsLabel, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, _kPaddingSize),
            (self._gridRowsComboBox, 1)])

        # Get the camera names and overlay them with former order preferences.
        cameras = self._backEndClient.getCameraLocations()
        order = getFrontEndPref("gridViewOrder")
        choices = determineGridViewCameras(cameras, order)

        # Create a list box to show these camera names.
        self._gridOrder = wx.ListBox(panel, choices=choices)
        # Need to spy on all mouse events because we don't get an EVT_LISTBOX
        # when an item gets deselected.
        self._gridOrder.Bind(wx.EVT_MOUSE_EVENTS, self.OnGridOrderChanged)
        self._gridOrder.Bind(wx.EVT_LISTBOX, self.OnGridOrderChanged)
        # TODO: need to make it expand in a cooperative way, somehow ...
        self._gridOrder.SetMinSize((320, -1))

        # Add buttons to move camera names up or down.
        self._gridMoveUpButton = wx.Button(panel, -1, _kGridMoveUp)
        self._gridMoveUpButton.Bind(wx.EVT_BUTTON, self.OnGridMoveUp)
        self._gridMoveDownButton = wx.Button(panel, -1, _kGridMoveDown)
        self._gridMoveDownButton.Bind(wx.EVT_BUTTON, self.OnGridMoveDown)
        moveSizer = wx.BoxSizer(wx.HORIZONTAL)
        moveSizer.Add(self._gridMoveUpButton)
        moveSizer.AddSpacer(_kPaddingSize)
        moveSizer.Add(self._gridMoveDownButton)

        # Put both the camera list and the move buttons into a separate sizer.
        gridOrderSizer = wx.BoxSizer(wx.VERTICAL)
        gridOrderSizer.Add(self._gridOrder)
        gridOrderSizer.AddSpacer(_kPaddingSize)
        gridOrderSizer.Add(moveSizer)

        # Add all things camera ordering to the grid.
        flexGridSizer.AddSpacer(_kPaddingSize)
        flexGridSizer.AddSpacer(_kPaddingSize)
        flexGridSizer.AddMany([
            (orderLabel, 0, wx.LEFT | wx.EXPAND, _kPaddingSize),
            (gridOrderSizer, 1)])
        flexGridSizer.AddSpacer(_kPaddingSize)
        flexGridSizer.AddSpacer(_kPaddingSize)

        # Create the framerate controls and add it to the grid.
        fpsValue = getFrontEndPref("gridViewFps")
        fpsLabel = wx.StaticText(panel, -1, _kGridFpsLabel)
        choices = list(map(lambda i: str(i), (2, 5, 10, 30)))
        self._gridFpsComboBox = wx.ComboBox(panel, value=str(fpsValue), choices=choices, style=style)
        flexGridSizer.AddMany([
            (fpsLabel, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, _kPaddingSize),
            (self._gridFpsComboBox, 1)])

        # Add the grid to the main sizer.
        mainSizer.Add(flexGridSizer, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, _kSpaceSize2)
        panel.SetSizer(mainSizer)

        # Add the bitmap flag on the bottom, since it won't fit the grid style.
        showInactiveMode = getFrontEndPref("gridViewShowInactive")
        self._gridShowInactiveCheckbox = wx.CheckBox(panel, label=_kGridShowInactiveCameras)
        self._gridShowInactiveCheckbox.SetValue(showInactiveMode>0)
        self._gridShowInactiveCheckbox.Bind(wx.EVT_CHECKBOX, self.OnShowInactiveCameras)
        self._gridMoveInactiveCheckbox = wx.CheckBox(panel, label=_kGridMoveInactiveCameras)
        self._gridMoveInactiveCheckbox.SetValue(showInactiveMode>1)
        self._gridMoveInactiveCheckbox.Enable(showInactiveMode>0)
        mainSizer.AddStretchSpacer()
        mainSizer.Add(self._gridShowInactiveCheckbox, 0, wx.LEFT, _kSpaceSize2)
        mainSizer.Add(self._gridMoveInactiveCheckbox, 0, wx.LEFT, _kSpaceSize2)
        mainSizer.AddSpacer(_kSpaceSize1)

        # Make sure that the move buttons for ordering cameras not enabled yet.
        self.OnGridOrderChanged()

        return panel

    ###########################################################
    def OnShowInactiveCameras(self, event=None):
        self._gridMoveInactiveCheckbox.Enable(self._gridShowInactiveCheckbox.GetValue()>0)

    ###########################################################
    def _createRemoteAccessPanel(self):
        """ Create the remote access panel. Has its own [Apply] button where
        things can be activated without the options panel being closed.

        @return  New panel instance.
        """

        self._origWebUser = self._backEndClient.getWebUser()
        self._origPassword = _kFakePassword
        origWebPort = self._backEndClient.getWebPort()
        self._origWebEnabled = origWebPort > 0
        self._origPortOpenerEnabled = self._backEndClient.isPortOpenerEnabled()

        remotePanel = wx.Panel(self._notebook, -1)
        remoteSizer = wx.BoxSizer(wx.VERTICAL)

        remoteDescriptionLabel = wx.StaticText(remotePanel, -1,
                _kRemoteDescription)
        self._webEnableCheckbox = wx.CheckBox(remotePanel, -1,
                _kEnableRemoteLabel)
        self._webEnableCheckbox.SetValue(self._origWebEnabled)

        advancedButton = wx.Button(remotePanel, -1, "Advanced")
        advancedButton.Bind(wx.EVT_BUTTON, self.OnAdvanced)

        remoteSizer.AddSpacer(_kSpaceSize1)
        remoteSizer.Add(remoteDescriptionLabel, 0, wx.LEFT | wx.RIGHT, _kBorderSize)
        remoteSizer.AddSpacer(_kSpaceSize1)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self._webEnableCheckbox, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.AddStretchSpacer(1)
        hSizer.Add(advancedButton, 0, wx.ALIGN_CENTER_VERTICAL)
        remoteSizer.Add(hSizer, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, _kBorderSize)

        usernameLabel = wx.StaticText(remotePanel, -1, _kUsernameLabel)
        self._userField = wx.TextCtrl(remotePanel, -1)
        self._userField.SetMaxLength(_kMaxUserPassLength)
        passwordLabel = wx.StaticText(remotePanel, -1, _kPasswordLabel)
        self._passField = wx.TextCtrl(remotePanel, -1, style=wx.TE_PASSWORD)
        self._passField.SetMaxLength(_kMaxUserPassLength)
        verifyLabel = wx.StaticText(remotePanel, -1, _kVerifyLabel)
        self._verifyField = wx.TextCtrl(remotePanel, -1,
                style=wx.TE_PASSWORD)
        self._verifyField.SetMaxLength(_kMaxUserPassLength)
        portLabel = wx.StaticText(remotePanel, -1, _kPortLabel)
        self._portCtrl = wx.TextCtrl(remotePanel, -1)
        if self._origWebEnabled:
            self._portCtrl.SetValue(str(origWebPort))
            self._userField.SetValue(self._origWebUser)
            if self._origWebUser:
                self._passField.SetValue(_kFakePassword)
                self._verifyField.SetValue(_kFakePassword)
        else:
            self._portCtrl.SetValue(str(_kDefaultPort))
        self._portOpenerEnabled = wx.CheckBox(remotePanel, -1,
                _kPortOpenerEnabledLabel)
        self._portOpenerEnabled.SetValue(self._origPortOpenerEnabled)

        portSizer = wx.BoxSizer(wx.HORIZONTAL)
        height = self._passField.GetSize()[1]
        width = self._portCtrl.GetTextExtent("00000")[0] + height
        self._portCtrl.SetMinSize((width, height))
        self._portCtrl.SetMaxSize((width, height))
        portSizer.Add(self._portCtrl)
        portSizer.Add(self._portOpenerEnabled, 0,  wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        webServerStatusLabel = wx.StaticText(remotePanel, -1, kWebServerStatusLabel)
        self._webServerStatusNotice = wx.StaticText(remotePanel, -1, "")
        webServerLocalNotice = wx.StaticText(remotePanel, -1, kWebServerLocURL)
        self._webServerLocalLink = wx.adv.HyperlinkCtrl(remotePanel, wx.ID_ANY, ".", ".")
        webServerInternalNotice = wx.StaticText(remotePanel, -1, kWebServerIntURL)
        self._webServerInternalLink = wx.adv.HyperlinkCtrl(remotePanel, wx.ID_ANY, ".", ".")
        webServerExternalNotice = wx.StaticText(remotePanel, -1, kWebServerExtURL)
        self._webServerExternalLink = wx.adv.HyperlinkCtrl(remotePanel, wx.ID_ANY, ".", ".")
        webServerCertificateId = wx.StaticText(remotePanel, -1, kWebServerCertificateId)
        self._webServerCertificateId = wx.StaticText(remotePanel, -1, "", )
        setHyperlinkColors(self._webServerLocalLink)
        setHyperlinkColors(self._webServerInternalLink)
        setHyperlinkColors(self._webServerExternalLink)

        # The hyperlink left align flag also adds a depth border on win so
        # we must unfortunately add an extra set of sizers and spacers, and
        # update the layout periodically ourselves.
        self._localSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._localSizer.Add(self._webServerLocalLink)
        self._localSizer.AddStretchSpacer(1)
        self._internalSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._internalSizer.Add(self._webServerInternalLink)
        self._internalSizer.AddStretchSpacer(1)
        self._externalSizer = wx.BoxSizer(wx.HORIZONTAL)
        self._externalSizer.Add(self._webServerExternalLink)
        self._externalSizer.AddStretchSpacer(1)

        self._applyButton = wx.Button(remotePanel, -1, "Apply")
        self._applyButton.Bind(wx.EVT_BUTTON, self.OnApply)

        accountSizer = wx.FlexGridSizer(0, 2, _kPaddingSize, _kPaddingSize)
        accountSizer.AddGrowableCol(1, 1)
        accountSizer.AddMany([
                (usernameLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (self._userField, 0, wx.EXPAND),
                (passwordLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (self._passField, 0, wx.EXPAND),
                (verifyLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (self._verifyField, 0, wx.EXPAND),
                (portLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (portSizer, 0, 0),
            ])
        accountSizer.AddSpacer(8)
        accountSizer.AddSpacer(8)
        accountSizer.AddMany([
                (webServerStatusLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (self._webServerStatusNotice, 0, wx.EXPAND),
                (webServerLocalNotice, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (self._localSizer, 0, wx.EXPAND),
                (webServerInternalNotice, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (self._internalSizer, 0, wx.EXPAND),
                (webServerExternalNotice, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (self._externalSizer, 0, wx.EXPAND),
                (webServerCertificateId, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
                    _kPaddingSize), (self._webServerCertificateId, 0, wx.EXPAND),
                ])
        accountSizer.AddSpacer(1)
        accountSizer.Add(self._applyButton, 0, wx.RIGHT | wx.ALIGN_RIGHT)

        remoteSizer.AddSpacer(_kSpaceSize1)
        remoteSizer.Add(accountSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)
        remoteSizer.AddSpacer(_kSpaceSize1)
        remotePanel.SetSizer(remoteSizer)

        self._userField.Bind(wx.EVT_TEXT, self.OnRemoteUserChange)
        self._passField.Bind(wx.EVT_TEXT, self.OnRemoteItemChange)
        self._verifyField.Bind(wx.EVT_TEXT, self.OnRemoteItemChange)
        self._portCtrl.Bind(wx.EVT_TEXT, self.OnRemoteItemChange)
        self._userField.SetInsertionPointEnd()
        self._passField.SetInsertionPointEnd()
        self._verifyField.SetInsertionPointEnd()
        self._portCtrl.SetInsertionPointEnd()

        self._currentPort = None
        self._lastStatusNumber = None
        self.Bind(EVT_WEBSERVERSTATUS, self.OnWebServerStatus)
        self._webServerStatusThread = WebServerStatusThread(self)
        self._webServerStatusThread.runSync()  # get initial status
        self._webServerStatusThread.start()

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        return remotePanel


    ###########################################################
    def OnDestroy(self, event):
        """ Make sure that the web server status thread goes down with us. """
        if self._hasPaid:
            self._webServerStatusThread.stop()

    ###########################################################
    def OnAdvanced(self, event=None):
        """Display the advanced remote settings dialog.

        @param  event  Ignored.
        """
        dlg = AdvancedDialog(self, self._backEndClient, self._logger)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnApply(self, event=None):
        self._validateAndSetRemoteSettings(False)


    ###########################################################
    def OnOk(self, event=None):
        """Close the dialog applying any changes.

        @param  event  The button event.
        """
        curStorageSize = int(self._storageSizeCtrl.GetValue())
        if curStorageSize < _kStorageSizeGBMin or curStorageSize > _kStorageSizeGBMax:
            wx.MessageBox("Invalid value %d for storage size, please enter values between %d and %d" % \
                    (curStorageSize, _kStorageSizeGBMin, _kStorageSizeGBMax),
                    _kErrorTitle, wx.OK | wx.ICON_ERROR, self)
            return

        if self._origStorageSize != curStorageSize:
            self._backEndClient.setMaxStorageSize(curStorageSize)

        curCacheSize = int(self._cacheSizeCtrl.GetValue())
        if curCacheSize < _kCacheSizeMinutesMin or curCacheSize > _kCacheSizeMinutesMax:
            wx.MessageBox("Invalid value %d for cache size, please enter values between %d and %d" % \
                    (curCacheSize, _kCacheSizeMinutesMin, _kCacheSizeMinutesMax),
                    _kErrorTitle, wx.OK | wx.ICON_ERROR, self)
            return
        if self._origCacheSize != curCacheSize:
            self._backEndClient.setCacheDuration(curCacheSize)

        curRecordInMemory = self._tempVideoMemoryRadio.GetValue()
        if curRecordInMemory != self._origRecordInMemory:
            self._backEndClient.setRecordInMemory(curRecordInMemory)

        # Check if the autostart checkbox value changed...
        if self._wasAutoStart != self._launchOnStartup.GetValue():

            # If autostart checkbox value changed, save this configuration, and
            # log any errors...
            if not setServiceAutoStart(not self._wasAutoStart):
                self._logger.error(
                    "Unable to store service launch config: autostart=%s"
                    % (not self._wasAutoStart)
                )

            # If the user enabled autostart, make sure the service launches the
            # backend, and log any errors...
            if self._launchOnStartup.GetValue():
                if not setServiceStartsBackend(True):
                    self._logger.error(
                        "Unable to store service launch config: "
                        "serviceStartBackend=True"
                    )

        # TODO: Update remote values if different
        if not self._validateAndSetRemoteSettings():
            return

        is12Hour = self._time12Radio.GetValue()
        isUSDate = self._dateUSRadio.GetValue()
        was12, wasUS = self._uiPrefsModel.getTimePreferences()
        if is12Hour != was12 or isUSDate != wasUS:
            self._backEndClient.setTimePreferences(is12Hour, isUSDate)
            self._uiPrefsModel.setTimePreferences(is12Hour, isUSDate)

        warnSupport = self._supportCheck.GetValue()
        if warnSupport != self._uiPrefsModel.shouldShowSupportWarning():
            self._uiPrefsModel.enableSupportWarnings(warnSupport)

        self._setGridPrefs()


        value = self._combineTimeLimit.GetSelection() if self._combineCheckbox.GetValue() else 0
        if value != self._clipMergeLimit:
            self._backEndClient.setClipMergeThreshold(value)

        if self._enableHardwareAcceleration:
            device = "none"
            if self._enableHardwareAcceleration.GetValue():
                device = "auto"
                if self._hwDevicesChoice:
                    device = self._hwDevicesChoice.GetString(self._hwDevicesChoice.GetSelection())
            if device != self._hwDevice:
                self._backEndClient.setHardwareDevice("" if device == "auto" else device)


        self.EndModal(wx.OK)


    ###########################################################
    def OnRemoteItemChange(self, event=None):
        """Ensure the 'enable' box is checked when other settings change.

        @param  event  The change event.
        """
        self._webEnableCheckbox.SetValue(True)


    ###########################################################
    def OnCombineClips(self, event=None):
        self._combineTimeLimit.Enable(self._combineCheckbox.GetValue())

    ###########################################################
    def OnHwAccelerationChange(self, event=None):
        self._hwDevicesChoice.Enable(self._enableHardwareAcceleration.GetValue())

    ###########################################################
    def OnRemoteUserChange(self, event=None):
        """Respond to a username change.

        If the username is updated we need to force the user to enter a new
        password as we don't store their old, so clear the password fields
        if they haven't already been updated.

        @param  event  The change event.
        """
        if (self._passField.GetValue() == _kFakePassword):
            self._passField.SetValue("")
            self._verifyField.SetValue("")
        self.OnRemoteItemChange(event)


    ###########################################################
    def OnGridOrderChanged(self, event=None):
        """ Ensures proper controls' state when the grid order view potentially
        changed. At this moment it's about enabling and disabling the move
        buttons.

        @param  event  The event causing the invocation, if any.
        """
        selection = self._gridOrder.GetSelection()
        if selection == wx.NOT_FOUND:
            self._gridMoveDownButton.Enable(False)
            self._gridMoveUpButton.Enable(False)
        else:
            count = self._gridOrder.GetCount()
            self._gridMoveDownButton.Enable(selection < count - 1)
            self._gridMoveUpButton.Enable(selection > 0)
        if not event is None:
            event.Skip()


    ###########################################################
    def OnGridMove(self, inc):
        """ Moves a selected item in the grid order list up or down. Does
        nothing if no item is selected or moving it would be out of bounds.

        @param  inc  The direction to move, either -1 or +1.
        """
        selection = self._gridOrder.GetSelection()
        if selection == wx.NOT_FOUND:
            return
        selection += inc
        if selection < 0:
            return
        a = self._gridOrder.GetString(selection)
        b = self._gridOrder.GetString(selection - inc)
        self._gridOrder.SetString(selection, b)
        self._gridOrder.SetString(selection - inc, a)
        self._gridOrder.SetSelection(selection)
        self.OnGridOrderChanged()


    ###########################################################
    def OnGridMoveUp(self, event=None):
        """ Move a selected grid order item up one level. """
        self.OnGridMove(-1)


    ###########################################################
    def OnGridMoveDown(self, event=None):
        """ Move a selected grid order item down one level. """
        self.OnGridMove(1)


    ###########################################################
    def _setGridPrefs(self):
        """ Store the current grid view settings.
        """
        rows = self._gridRowsComboBox.GetValue()
        cols = self._gridColsComboBox.GetValue()
        fps = self._gridFpsComboBox.GetValue()
        order = self._gridOrder.GetStrings()
        showInactiveMode = 0 if not self._gridShowInactiveCheckbox.GetValue() else \
                           1 if not self._gridMoveInactiveCheckbox.GetValue() else \
                           2

        setFrontEndPref("gridViewShowInactive", showInactiveMode)
        setFrontEndPref("gridViewRows", int(rows))
        setFrontEndPref("gridViewCols", int(cols))
        setFrontEndPref("gridViewOrder", order)
        setFrontEndPref("gridViewFps", int(fps))
        self._logger.info(
            "saved grid settings: %sx%s, fps=%s, order=(%s)" %
            (rows, cols, fps, ",".join(order)))
        self._uiPrefsModel.updateGridViewSettings(
            rows, cols, order, fps, showInactiveMode)


    ###########################################################
    def _validateAndSetRemoteSettings(self, closing=True):
        """Ensure the remote settings are valid, will display error UI if not.

        @return valid  True if valid, else false.
        """
        if not self._hasPaid:
            return True

        # If web is not enabled, no real validation needed.
        if not self._webEnableCheckbox.GetValue():
            if self._origWebEnabled:
                self._backEndClient.setWebPort(-1)
                self._origWebEnabled = False
                self._userField.SetValue("")
                self._passField.SetValue("")
                self._verifyField.SetValue("")
                self._origWebUser = ""
                self._origPassword = ""
                self._webEnableCheckbox.SetValue(False)
            return True

        updateUser = False
        updatePort = False

        newUser = self._userField.GetValue()
        newPass = self._passField.GetValue()

        if 0 == len(newUser):
            wx.MessageBox(_kInvalidUsernameBody, _kErrorTitle,
                    wx.OK | wx.ICON_ERROR, self)
            return False
        if 0 == len(newPass):
            wx.MessageBox(_kPasswordsLengthBody, _kErrorTitle,
                    wx.OK | wx.ICON_ERROR, self)
            return False

        if not all(ord(c) < 128 for c in newUser) or \
           not all(ord(c) < 128 for c in newPass):
            wx.MessageBox(_kNonAsciiBody, _kErrorTitle,
                    wx.OK | wx.ICON_ERROR, self)
            return False

        if (self._origWebUser != newUser) or (self._origPassword != newPass):
            if not len(newUser):
                wx.MessageBox(_kInvalidUsernameBody, _kErrorTitle,
                        wx.OK | wx.ICON_ERROR, self)
                return False
            if len(newPass) < _kMinPasswordLength:
                wx.MessageBox(_kPasswordsLengthBody, _kErrorTitle,
                        wx.OK | wx.ICON_ERROR, self)
                return False
            if newPass != self._verifyField.GetValue():
                wx.MessageBox(_kPasswordsMatchBody, _kErrorTitle,
                        wx.OK | wx.ICON_ERROR, self)
                return False
            updateUser = True

        newPort = 0
        try:
            newPort = int(self._portCtrl.GetValue())
            if (newPort <= 1024) or (newPort > 65535):
                raise Exception()
            if newPort != self._currentPort:
                if not self._portCheck(newPort):
                    wx.MessageBox(_kPortNABody % newPort, _kErrorTitle,
                                  wx.OK | wx.ICON_ERROR, self)
                    return False
                updatePort = True
        except Exception:
            wx.MessageBox(_kPortErrorBody, _kErrorTitle, wx.OK | wx.ICON_ERROR,
                    self)
            return False

        if updateUser or updatePort:
            self._updateStatus(kWebServerStatusUpdating)
            self._applyButton.Enable(False)
        if updateUser:
            self._backEndClient.setWebAuth(newUser, newPass)
        if updatePort:
            self._backEndClient.setWebPort(newPort)

        self._backEndClient.enablePortOpener(
            self._portOpenerEnabled.GetValue())

        self._origWebEnabled = True
        self._origPassword = newPass
        self._origWebUser = newUser

        return True

    ###########################################################
    def OnMoveVideo(self, event=None):
        """Display the move video dialog.

        @param  event  The button event.
        """
        if not os.path.isdir(os.path.join(
                    self._backEndClient.getVideoLocation(), kVideoFolder)):
            # If the current video folder can't be found show the locate dialog.
            dlg = LocateVideoDialog(self, self._backEndClient, self._dataMgr)
        else:
            # If the current video folder does exist show the move dialog.
            dlg = MoveVideoDialog(self, self._backEndClient, self._dataMgr,
                                  self._logger)
        try:
            result = dlg.ShowModal()
            if result == wx.OK:
                volumeName = "Unknown"
                volumeType = "Unknown"
                bytesFree = -1
                try:
                    videoLocation = self._backEndClient.getVideoLocation()
                    volumeName, volumeType = getVolumeNameAndType(videoLocation)
                    bytesFree = getDiskSpaceAvailable(videoLocation)
                except Exception:
                    pass
                self._locLabel.SetLabel(ensureUnicode(_kVideoLocLabel %
                                        (volumeType, volumeName)))
                sizeStr = getStorageSizeStr(bytesFree)
                self._spaceFree.SetLabel(ensureUnicode(_kDiskSpaceLabel %
                                         (volumeType, volumeName, sizeStr)))
                self.Fit()
        finally:
            dlg.Destroy()


    ###########################################################
    def OnWebServerStatus(self, event=None):
        if self._hasPaid:
            self.showWebServerStatus(event.GetStatus())


    ###########################################################
    def _updateStatus(self, status, localURL="", internalURL="",
            externalLabel="", externalURL="", certificateId = ""):
        """Update the web server status.

        @param  status        Text describing the web server status.
        @param  localURL      A URL to use for machine local access.
        @param  internal      A URL to use for local network access.
        @param  externalLabel A url or status message for external access.
        @param  externalURL   A URL to use for external access.
        @param  certificateId SHA-1 of the SSL certificate, in hex.
        """
        if not self._hasPaid:
            return

        certificateIdShort = ''
        certificateIdLong = ''
        if certificateId:
            certificateId = certificateId.upper()
            for i in xrange(0,len(certificateId)/2):
                certificateIdLong += \
                    '\n' if i == len(certificateId)/4 else ':' if i else ''
                certificateIdLong += certificateId[i*2:i*2+2]
            certificateIdShort = certificateIdLong[0:23]

        self._webServerStatusNotice.SetLabel(status)
        self._webServerLocalLink.SetLabel(localURL)
        self._webServerLocalLink.SetURL(localURL)
        self._webServerInternalLink.SetLabel(internalURL)
        self._webServerInternalLink.SetURL(internalURL)
        self._webServerExternalLink.SetLabel(externalLabel)
        self._webServerExternalLink.SetURL(externalURL)
        self._webServerCertificateId.SetLabel(certificateIdShort)
        self._webServerCertificateId.SetToolTip(wx.ToolTip(certificateIdLong))
        self._localSizer.Layout()
        self._internalSizer.Layout()
        self._externalSizer.Layout()
        self._applyButton.Enable()


    ###########################################################
    def showWebServerStatus(self, wss):
        """ Processes the web server status and displays it. Checks the status
        number and compares it to the last one to avoid unnecessary updates.
        @param wss The web server status.
        """
        if not self._hasPaid:
            return

        status, locu, intu,  = "", "", ""
        externalLabel, externalURL = "", ""
        certificateId = ""
        while True:
            if wss is None:
                status = kWebServerStatusNA
                break
            snum = wss[kStatusKeyNumber]
            if self._lastStatusNumber == snum:
                return
            self._lastStatusNumber = snum;
            self._currentPort = wss[kStatusKeyPort]
            if -1 == self._currentPort:
                status = kWebServerStatusOff
                break
            if not wss[kStatusKeyVerified]:
                status = kWebServerStatusNotVerified
                break
            status = kWebServerStatusOn
            locu = kHttpAddress % (kHttpLocalHost, self._currentPort)
            intIP = self._internalIP.result
            if intIP is None:
                intu = locu # better than showing nothing, no?
            else:
                intu = kHttpAddress % (intIP, self._currentPort)
            pos = wss.get(kStatusKeyPortOpenerState, None)
            if pos is None:
                externalLabel = kWebServerExtStatusOff
                externalURL = kRemoteAccessUrl
            else:
                rport = wss[kStatusKeyRemotePort]
                raddr = wss[kStatusKeyRemoteAddress]
                if -1 == rport:
                    externalLabel = kWebServerExtStatusNA
                    externalURL = kRemoteAccessUrl
                else:
                    externalLabel = externalURL = kHttpAddress % (raddr, rport)
            certificateId = wss[kStatusKeyCertificateId]
            break

        self._updateStatus(status, locu, intu, externalLabel, externalURL,
                           certificateId)


    ###########################################################
    def _portCheck(self, port):
        """ Checks if a server port can be opened by just opening it ourselves
        and then immediately releasing it.
        @param port The port to check.
        @return True if the port can be used or not (False).
        """
        if not self._hasPaid:
            return

        tm = time.time()
        try:
            TCPServer(('0.0.0.0', port), BaseRequestHandler).server_close()
            return True
        except:
            self._logger.warn("check for port %d failed (%s)" %
                              (port, sys.exc_info()[1]))
            return False
        finally:
            self._logger.info("check for port %d took %.3f seconds" %
                              (port, time.time() - tm))


###############################################################
class AdvancedDialog(wx.Dialog):
    """A dialog for advanced remote access settings."""

    ###########################################################
    def __init__(self, parent, backEndClient, logger):
        """Initializer for AdvancedDialog.

        @param  parent         The parent window.
        @param  backEndClient  An object for communicating with the back end.
        """
        wx.Dialog.__init__(self, parent, -1, "Advanced")

        try:
            self._backEndClient = backEndClient
            self._logger = logger

            # Create the main sizer.
            sizer = wx.BoxSizer(wx.VERTICAL)
            self.SetSizer(sizer)
            sizer.AddSpacer(_kSpaceSize2)

            # Create the controls.

            clipLabel = wx.StaticText(self, -1, "Clip Video Quality:")
            self._clipChoices = wx.Choice(self, -1, choices=_kVideoQualityProfileLabels)
            self._clipChoices.Bind( wx.EVT_CHOICE, self.OnClipChoiceSelection )

            liveResLabel = wx.StaticText(self, -1, "Maximum Live Video Resolution:")
            self._liveResChoices = wx.Choice(self, -1, choices=_kVideoResolutionLabels)

            clipResLabel = wx.StaticText(self, -1, "Maximum Clip Video Resolution:")
            self._clipResChoices = wx.Choice(self, -1, choices=_kVideoResolutionLabels)

            self._origLiveTimestampEnabled = self._backEndClient.getVideoSetting(Prefs.kLiveEnableTimestamp)
            self._timestampEnabledForLiveViewCheckbox = wx.CheckBox(self, -1,
                                        "Overlay timestamp on live view")
            self._timestampEnabledForLiveViewCheckbox.SetValue(self._origLiveTimestampEnabled)

            self._origEnableLiveFastStart = self._backEndClient.getVideoSetting(Prefs.kLiveEnableFastStart)
            self._fastStartEnabledCheckbox = wx.CheckBox(self, -1,
                                        "Enable live stream fast start (may consume more memory)")
            self._fastStartEnabledCheckbox.SetValue(self._origEnableLiveFastStart)

            self._origClipsTimestampEnabled = self._backEndClient.getTimestampEnabledForClips()
            self._timestampEnabledForClipsCheckbox = wx.CheckBox(self, -1,
                                        "Overlay timestamp on clips")
            self._timestampEnabledForClipsCheckbox.SetValue(self._origClipsTimestampEnabled)
            self._origBoundingBoxesEnabled = self._backEndClient.getBoundingBoxesEnabledForClips()
            self._boundingBoxesEnabledCheckbox = wx.CheckBox(self, -1,
                                        "Overlay bounding boxes on clips")
            self._boundingBoxesEnabledCheckbox.SetValue(self._origBoundingBoxesEnabled)

            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(liveResLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
                    _kPaddingSize)
            hSizer.Add(self._liveResChoices, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.Add(hSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)
            sizer.AddSpacer(_kPaddingSize*2)
            sizer.Add(self._timestampEnabledForLiveViewCheckbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)
            sizer.AddSpacer(_kPaddingSize*2)
            sizer.Add(self._fastStartEnabledCheckbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)

            sizer.AddSpacer(_kPaddingSize*8)

            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(clipLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
                    _kPaddingSize)
            hSizer.Add(self._clipChoices, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.Add(hSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)
            sizer.AddSpacer(_kPaddingSize*2)

            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(clipResLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
                    _kPaddingSize)
            hSizer.Add(self._clipResChoices, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.Add(hSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)
            sizer.AddSpacer(_kPaddingSize*2)

            sizer.Add(self._boundingBoxesEnabledCheckbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)
            sizer.AddSpacer(_kPaddingSize*2)

            sizer.Add(self._timestampEnabledForClipsCheckbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, _kSpaceSize2)
            sizer.AddSpacer(_kPaddingSize*2)

            buttonSizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
            sizer.Add(buttonSizer, 0, wx.BOTTOM | wx.EXPAND, _kSpaceSize1)

            self.FindWindowById(wx.ID_OK, self).Bind(wx.EVT_BUTTON, self.OnOk)
            self.FindWindowById(wx.ID_CANCEL, self).SetDefault()

            self.Fit()
            self.CenterOnParent()

            self._videoSettings = {
                #                            orig default                               control                 values
                Prefs.kClipQualityProfile: ( -1,  Prefs.kClipQualityProfileDefault,     self._clipChoices,      _kVideoQualityProfile ),
                Prefs.kLiveMaxResolution : ( -1,  Prefs.kLiveMaxResolutionDefault,      self._liveResChoices,   _kVideoResolutions    ),
                Prefs.kClipResolution    : ( -1,  Prefs.kClipResolutionDefault,         self._clipResChoices,   _kVideoResolutions    )
            }

            # Fetch current prefs and set controls
            for key in self._videoSettings:
                self._initVideoQualitySetting(key)
            self.OnClipChoiceSelection(None)

        except: # All exceptions, not just Exception subclasses
            # Make absolutely sure that we are destroyed, even if we crash
            # in the above...
            self.Destroy()
            raise

    ###########################################################
    def _initVideoQualitySetting(self, name):
        current = self._backEndClient.getVideoSetting(name)
        original, default, ctrl, options = self._videoSettings[name]
        if current not in options:
            current = default
        ctrl.SetSelection(options.index(current))
        self._videoSettings[name] = ( current, default, ctrl, options )

    ###########################################################
    def _saveVideoQualitySetting(self, name):
        original, default, ctrl, options = self._videoSettings[name]
        current = ctrl.GetSelection()
        if current != original:
            self._backEndClient.setVideoSetting(name, options[current])

    ###########################################################
    def OnClipChoiceSelection(self, event=None):
        current = self._clipChoices.GetSelection()
        enableFilters = (_kVideoQualityProfile[current] != 0)
        self._boundingBoxesEnabledCheckbox.Enable( enableFilters )
        self._timestampEnabledForClipsCheckbox.Enable( enableFilters )
        self._clipResChoices.Enable( enableFilters )

    ###########################################################
    def OnOk(self, event=None):
        """Close the dialog applying any changes.

        @param  event  The button event.
        """
        # If any changes, propagate to back end.
        for key in self._videoSettings:
            self._saveVideoQualitySetting(key)

        val = self._boundingBoxesEnabledCheckbox.GetValue()
        if val != self._origBoundingBoxesEnabled:
            self._backEndClient.setBoundingBoxesEnabledForClips(val)

        val = self._timestampEnabledForClipsCheckbox.GetValue()
        if val != self._origClipsTimestampEnabled:
            self._backEndClient.setTimestampEnabledForClips(val)

        val = self._timestampEnabledForLiveViewCheckbox.GetValue()
        if val != self._origLiveTimestampEnabled:
            self._backEndClient.setVideoSetting(Prefs.kLiveEnableTimestamp, val)

        val = self._fastStartEnabledCheckbox.GetValue()
        if val != self._origEnableLiveFastStart:
            self._backEndClient.setVideoSetting(Prefs.kLiveEnableFastStart, val)

        self.EndModal(wx.OK)


