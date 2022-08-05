#!/usr/bin/env python

#*****************************************************************************
#
# CameraSetupWizard.py
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
import cPickle
import mmap
import operator
import os
import sys
import re
import time
import urllib
import urlparse

# Common 3rd-party imports...
import wx
import wx.adv as wxWizard

# Toolbox imports...
from vitaToolbox.mvc.AbstractModel import AbstractModel
from vitaToolbox.networking.Upnp import constructUpnpUrl
from vitaToolbox.networking.Upnp import isUpnpUrl
from vitaToolbox.networking.Upnp import extractUsnFromUpnpUrl
from vitaToolbox.networking.Upnp import realizeUpnpUrl
from vitaToolbox.networking.Onvif import kFaultSubcodeNotAuthorized
from vitaToolbox.networking.Onvif import kHttpRequestError
from vitaToolbox.networking.Onvif import kAllFaultCodes
from vitaToolbox.networking.Onvif import constructOnvifUrl
from vitaToolbox.networking.Onvif import isOnvifUrl
from vitaToolbox.networking.Onvif import extractUuidFromOnvifUrl
from vitaToolbox.networking.Onvif import realizeOnvifUrl
from vitaToolbox.path.PathUtils import kInvalidPathChars
from vitaToolbox.path.PathUtils import kInvalidPathCharsDesc
from vitaToolbox.path.PathUtils import normalizePath
from vitaToolbox.strUtils.EnsureUnicode import ensureUnicode
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8
from vitaToolbox.wx.BitmapWindow import BitmapWindow
from vitaToolbox.wx.FixedStaticBitmap import FixedStaticBitmap
from vitaToolbox.wx.OverlapSizer import OverlapSizer
from vitaToolbox.wx.TextCtrlUtils import setHyperlinkColors
from vitaToolbox.wx.TextSizeUtils import makeFontBold, makeFontUnderlined
from vitaToolbox.wx.TextSizeUtils import makeFontDefault
from vitaToolbox.wx.TruncateText import truncateStaticText

# Local imports...
from appCommon.CommonStrings import kDefaultRecordSize, kMaxRecordSize
from appCommon.CommonStrings import kMatchSourceSize, kDefaultRecordAudio
from appCommon.CommonStrings import kRecordResponse
from appCommon.CommonStrings import kTestLiveFileName, kTestLiveHeaderSize
from appCommon.CommonStrings import kObjDbFile
from appCommon.LicenseUtils import hasPaidEdition
from backEnd.SavedQueryDataModel import SavedQueryDataModel
from backEnd.SavedQueryDataModel import WhereBlockDataModel
from backEnd.SavedQueryDataModel import DurationBlockDataModel
from backEnd.SavedQueryDataModel import kDefaultResponseList
from CameraTable import kOtherIpCamType
from CameraTable import kWebcamCamType
from CameraTable import kOtherCameraManufacturer
from CameraTable import kResMaps
from CameraTable import kDeprecatedSettings
from CameraTable import kOldCameraNameMap
from CameraTable import kGenericIndicator
from CameraTable import kUpnpModelMap
from CameraTable import kUpnpGenericList
from CameraTable import kCameraDescriptions
from CameraTable import kCameraGenericDescriptions
from CameraTable import kTypeToStreamPath
from CameraTable import kTypeToManufacturer
from CameraTable import kIpCameraTypes
from CameraTable import kCameraTypes
from CameraTable import kCameraManufacturers
from CameraTable import kUpnpManufactrers
from appCommon.CommonStrings import kAppName, kCameraConfigUrl
import FrontEndEvents
from frontEnd.FrontEndUtils import getUserLocalDataDir

from LicensingHelpers import checkForMaxCameras
from LicensingHelpers import showResolutionWarning


# Globals...

# Constants...

# If there is only one camera manufacturer (implies that an OEM patch modified
# the camera table), then we must be a bundled version of the software.  We
# do things a little differently in that case...
_isOemVersion = (len(kCameraManufacturers) == 1)

_kMinorActiveSearchPeriod = 7  # Every 7 seconds, we'll search for USB cams...

_kPaddingSize = 8
_kTextWrap = 448
_kTestVideoSize = (160, 120)

_kLargestPageType = kOtherIpCamType


# Fake link when no device is found; normally the user will never see this
# unless they try to copy the URL by right-clicking.
_kBadLink = "about:no.device.found"


_kCameraStyleNetwork = "Network (IP) camera"
_kCameraStyleLocal   = "USB, built-in, or other webcam"


# Record size settings.
# NOTE: Some cameras (like Panasonics) allow setting the stream resolution
#       in the URL. Maybe worth investigating A) expanding support for that to
#       more cameras and B) use those settings to limit the options presented.
# NOTE: "Match source" must be removed for local cameras as a specific
#       needs to be requested.
_kRecordSizes = [
    ("QVGA (320x240)", (320, 240)),
    ("VGA (640x480)", (640, 480)),
    ("XGA (1024x768)", (1024, 768)),
    ("HD 720 (1280x720)", (1280, 720)),
    ("SXGA (1280x1024)", (1280, 1024)),
    ("UXGA (1600x1200)", (1600, 1200)),
    ("HD 1080 (1920x1080)", (1920, 1080)),
    ("WXGA (1920x1200)", (1920, 1200)),
    ("Match source", kMatchSourceSize),
]
_kRecordSizeStrs = map(operator.itemgetter(0), _kRecordSizes)
_kRecordSizeStrToNums = dict(map(operator.itemgetter(0, 1), _kRecordSizes))
_kRecordSizeNumsToStr = dict(map(operator.itemgetter(1, 0), _kRecordSizes))

_kDefaultRecordSizeStr = _kRecordSizeNumsToStr[kDefaultRecordSize]
_kMaxRecordSizeStr = _kRecordSizeNumsToStr[kMaxRecordSize]


# Public global for maximum camera name length.
kMaxCameraNameLen = 50

# Different flows of the wizard.
_kFlowTypeDefault = 0
_kFlowTypeWebcam = 1
_kFlowTypeUpnp = 2
_kFlowTypeBadUpnp = 3
_kFlowTypeUpnpManualConfig = 4
_kFlowTypeUpnpManualConfigAfterHelp = 5
_kFlowTypeManualNetcam = 6
_kFlowTypeOnvif = 7

# Invalid camera name suffixes.
kInvalidCameraNameSuffixes = [' (inactive)']

_kPasswordsMustMatchStr = "The two password fields must match."

_kResolutionHelpText = "Confirm that your camera supports the selected " \
                       "resolution.  Also, if you are using a network camera," \
                       " go to the configuration website of your camera to " \
                       "verify that it is configured to stream that " \
                       "resolution, or choose \"Match source\" to " \
                       "automatically save at the incoming resolution.\n\n" \
                       "Note that higher resolutions can " \
                       "increase processing and disk space requirements " \
                       "considerably.\n\nThe aspect ratio of the source will " \
                       "always be maintained. Selecting 640x480 for an " \
                       "incoming 1280x720 feed will produce 640x360 clips."

# For local cameras, new-style (relative) device IDs start here...
_kNewDeviceIdOffset = 1000

# Users will select this if they want to customize the stream uri associated
# with their currently selected ONVIF profile in the settings screen.
_kOnvifCustomUri = "Custom"

_kSpinnerDelay = 50

_kAdvancedLabel = "Advanced:"
_kForceTCPLabel = "Force TCP connection"
_kAudioCtrlLabel = "Record audio if compatible stream is available"


##############################################################################
class CameraSetupWizard(wxWizard.Wizard):
    """A wizard for adding and editing cameras."""

    ###########################################################
    def __init__(self, parent, backEndClient, dataManager, cameraName='',
                 testing=False):
        """Initializer for the CameraSetupWizard class.

        @param  parent         The parent window.
        @param  backEndClient  An interface to the back end app.
        @param  cameraName     The name of the camera to edit, or None for new.
        @param  dataManager    An interface to the object database.
        @param  testing        If True jump directly to the test screen.
        """
        wxWizard.Wizard.__init__(self, parent, title='Camera Setup')

        self.SetDoubleBuffered(True)

        self.backEndClient = backEndClient
        self.dataManager = dataManager
        self._testing = testing

        # Kick off a major active camera search...
        self.backEndClient.activeCameraSearch(True)

        # Wx insists on a 5 pixel border, which we really don't want...
        self.SetBorder(-5)

        # Retrieve and store the camera settings.
        self.origName = cameraName
        self.cameraName = cameraName
        self.cameraType = ''
        self.cameraUri = ''
        self.origCameraUri = ''
        self.camExtras = {}

        self.upnpDataModel = _UpnpDataModel()
        self.onvifDataModel = _OnvifDataModel()
        self.localCamModel = _LocalCamDataModel()

        if cameraName:
            self.cameraType, self.cameraUri, _, self.camExtras = \
                    self.backEndClient.getCameraSettings(self.cameraName)

            # Keep track of original camera URI...
            self.origCameraUri = self.cameraUri

            # Parse out any old tcp force flags and update to use settings.
            forceTCP, self.cameraUri = _stripLegacyTcpOverride(self.cameraUri)
            if forceTCP:
                self.camExtras['forceTCP'] = True

            # If we've got a camera type/URL that matches one of the
            # deprecated patterns then move the camera type
            for (deprecatedTypeRe, deprecatedUriRe, cameraType) in \
                kDeprecatedSettings:

                if (re.match(deprecatedTypeRe, self.cameraType) and
                    re.match(deprecatedUriRe, self.cameraUri)):

                    self.cameraType = cameraType

            # Update old camera types...
            self.cameraType = kOldCameraNameMap.get(self.cameraType,
                                                     self.cameraType)

            if self.cameraType not in kCameraTypes:
                self.cameraType = kOtherIpCamType

        self.cameraManufacturer = \
            kTypeToManufacturer.get(self.cameraType, kOtherCameraManufacturer)

        # Flow information...
        self._basicFlowType = _kFlowTypeDefault
        self._wantExtraHelp = False
        self._wantWifiHelp = True

        # Create the wizard components.
        self._welcomeScreen = _WelcomeScreen(self)
        self._offerHelpScreen = _OfferHelpScreen(self)
        self._ethernetHelpScreen = _EthernetHelpScreen(self)
        self._powerHelpScreen = _PowerHelpScreen(self)
        self._detectedCamerasScreen = _DetectedCamerasScreen(self)
        self._upnpSettingsScreen = _UpnpSettingsScreen(self)
        self._badUpnpSettingsScreen = _BadUpnpScreen(self)
        self._onvifCredentialsScreen = _OnvifCredentialsScreen(self)
        self._OnvifSettingsScreen = _OnvifSettingsScreen(self)
        self._manualSettingsScreen = _ManualSettingsScreen(self)
        self._discoverHelpScreen = _DiscoverHelpScreen(self)
        self._logIntoCameraHelpScreen = _LogIntoCameraHelpScreen(self)
        self._offerWifiHelpScreen = _OfferWifiHelpScreen(self)
        self._wifiSsidHelpScreen = _WifiSsidHelpScreen(self)
        self._wifiUnplugEthernetHelpScreen = _WifiUnplugEthernetHelpScreen(self)
        self._wifiUnplugPowerHelpScreen = _WifiUnplugPowerHelpScreen(self)
        self._wifiConfirmHelpScreen = _WifiConfirmHelpScreen(self)
        self._testScreen = _TestScreen(self)
        self._locationScreen = _LocationScreen(self)

        firstScreen = self._welcomeScreen

        self._finishScreen = _FinishScreen(self, firstScreen)

        # Link the pages w/ default linkage and fit...
        self._reflow()
        self.FitToPage(firstScreen)

        # Now, update the flow to be somewhat correct.  This is important if
        # we're jumping straight to the testing screen...
        if self.cameraType == kWebcamCamType:
            assert self.cameraUri.startswith('device:')
            self.updateBasicFlow(_kFlowTypeWebcam)
        elif isUpnpUrl(self.cameraUri):
            self.updateBasicFlow(_kFlowTypeUpnp)
        elif isOnvifUrl(self.cameraUri):
            self.updateBasicFlow(_kFlowTypeOnvif)
        elif self.cameraManufacturer in kUpnpManufactrers:
            if self.origName:
                self.updateBasicFlow(_kFlowTypeUpnpManualConfig)
            else:
                self.updateBasicFlow(_kFlowTypeUpnp)
        else:
            self.updateBasicFlow(_kFlowTypeManualNetcam)

        self.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)
        self.Bind(wxWizard.EVT_WIZARD_CANCEL, self.OnWizardCancel)
        self.Bind(wxWizard.EVT_WIZARD_FINISHED, self.OnWizardFinished)

        # We use a timer to poll the backend for camera changes...
        self._refreshLoopCount = 0
        self._refreshTimer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnRefreshTimer, self._refreshTimer)
        self.OnRefreshTimer()


    ###########################################################
    def setHelpFlow(self, wantExtraHelp):
        """Update whether we'll include extra help in the flow.

        @param  wantExtraHelp  If True, we'll give extra help.
        """
        self._wantExtraHelp = wantExtraHelp
        self._reflow()


    ###########################################################
    def getHelpFlow(self):
        """Return whether we are showing the help flow.

        @return wantExtraHelp  If True, we'll give extra help.
        """
        return self._wantExtraHelp


    ###########################################################
    def setWifiHelpFlow(self, wantWifiHelp):
        """Update whether we'll include wifi help in the flow.

        @param  wantWifiHelp  If True, we give help with WiFi setup.
        """
        self._wantWifiHelp = wantWifiHelp
        self._reflow()


    ###########################################################
    def getWifiHelpFlow(self):
        """Return whether we are showing the WiFi help flow.

        @return wantWifiHelp  If True, we'll give help with Wifi setup.
        """
        return self._wantWifiHelp


    ###########################################################
    def updateBasicFlow(self, basicFlowType):
        """Update the flow of the wizard.

        @param  basicFlowType  One of the _kFlowTypeXXX constants.
        """
        self._basicFlowType = basicFlowType
        self._reflow()


    ###########################################################
    def getBasicFlow(self):
        """Get the basic flow.

        @return  basicFlowType  One of the _kFlowTypeXXX constants.
        """
        return self._basicFlowType


    ###########################################################
    def _reflow(self):
        """Update our flow based on self._wantExtraHelp and self._basicFlowType.

        This is called by the "public" functions that change the above.
        Note that the flow is also affected by whether or not we have a camera
        name.  If we don't, we'll add a few extra pages.
        """
        flowType = self._basicFlowType

        pageList = [
            { 'page':    self._welcomeScreen, },
        ]

        if flowType == _kFlowTypeDefault:
            # Bogus flowtype that just links all pages in for fitting purposes.
            pageList.extend([
                { 'page':    self._offerHelpScreen, },
                { 'page':    self._ethernetHelpScreen, },
                { 'page':    self._powerHelpScreen, },
                { 'page':    self._detectedCamerasScreen, },
                { 'page':    self._upnpSettingsScreen, },
                { 'page':    self._badUpnpSettingsScreen, },
                { 'page':    self._onvifCredentialsScreen, },
                { 'page':    self._OnvifSettingsScreen, },
                { 'page':    self._manualSettingsScreen, },
                { 'page':    self._discoverHelpScreen, },
                { 'page':    self._logIntoCameraHelpScreen, },
                { 'page':    self._offerWifiHelpScreen, },
                { 'page':    self._wifiSsidHelpScreen, },
                { 'page':    self._wifiUnplugEthernetHelpScreen, },
                { 'page':    self._wifiUnplugPowerHelpScreen, },
                { 'page':    self._wifiConfirmHelpScreen, },
                { 'page':    self._testScreen, },
                { 'page':    self._locationScreen, },
                { 'page':    self._finishScreen, },
            ])
        elif flowType == _kFlowTypeWebcam:
            pageList.extend([
                { 'page':    self._testScreen, },
                { 'page':    self._locationScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._finishScreen,
                  'isShown': not bool(self.origName), },
            ])
        elif flowType == _kFlowTypeUpnp:
            pageList.extend([
                { 'page':    self._offerHelpScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._ethernetHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._powerHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._detectedCamerasScreen, },
                { 'page':    self._logIntoCameraHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._offerWifiHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._wifiSsidHelpScreen,
                  'isShown': self._wantExtraHelp and self._wantWifiHelp, },
                { 'page':    self._wifiUnplugEthernetHelpScreen,
                  'isShown': self._wantExtraHelp and self._wantWifiHelp, },
                { 'page':    self._wifiUnplugPowerHelpScreen,
                  'isShown': self._wantExtraHelp and self._wantWifiHelp, },
                { 'page':    self._wifiConfirmHelpScreen,
                  'isShown': self._wantExtraHelp and self._wantWifiHelp, },
                { 'page':    self._upnpSettingsScreen, },
                { 'page':    self._testScreen, },
                { 'page':    self._locationScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._finishScreen,
                  'isShown': not bool(self.origName), },
            ])
        elif flowType == _kFlowTypeOnvif:
            pageList.extend([
                { 'page':    self._offerHelpScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._ethernetHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._powerHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._detectedCamerasScreen, },
                { 'page':    self._logIntoCameraHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._offerWifiHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._wifiSsidHelpScreen,
                  'isShown': self._wantExtraHelp and self._wantWifiHelp, },
                { 'page':    self._wifiUnplugEthernetHelpScreen,
                  'isShown': self._wantExtraHelp and self._wantWifiHelp, },
                { 'page':    self._wifiUnplugPowerHelpScreen,
                  'isShown': self._wantExtraHelp and self._wantWifiHelp, },
                { 'page':    self._wifiConfirmHelpScreen,
                  'isShown': self._wantExtraHelp and self._wantWifiHelp, },
                { 'page':    self._onvifCredentialsScreen, },
                { 'page':    self._OnvifSettingsScreen, },
                { 'page':    self._testScreen, },
                { 'page':    self._locationScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._finishScreen,
                  'isShown': not bool(self.origName), },
            ])
        elif flowType == _kFlowTypeBadUpnp:
            pageList.extend([
                { 'page':    self._offerHelpScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._ethernetHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._powerHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._detectedCamerasScreen, },
                { 'page':    self._badUpnpSettingsScreen,
                  'next':    self._detectedCamerasScreen, },
            ])
        elif flowType == _kFlowTypeUpnpManualConfig:
            pageList.extend([
                { 'page':    self._offerHelpScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._ethernetHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._powerHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._detectedCamerasScreen, },
                { 'page':    self._manualSettingsScreen, },
                { 'page':    self._testScreen, },
                { 'page':    self._locationScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._finishScreen,
                  'isShown': not bool(self.origName), },
            ])
        elif flowType == _kFlowTypeUpnpManualConfigAfterHelp:  # The "discover" help screen, specifically...
            pageList.extend([
                { 'page':    self._offerHelpScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._ethernetHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._powerHelpScreen,
                  'isShown': self._wantExtraHelp, },
                { 'page':    self._detectedCamerasScreen, },
                { 'page':    self._discoverHelpScreen, },
                { 'page':    self._manualSettingsScreen, },
                { 'page':    self._testScreen, },
                { 'page':    self._locationScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._finishScreen,
                  'isShown': not bool(self.origName), },
            ])
        elif flowType == _kFlowTypeManualNetcam:
            pageList.extend([
                { 'page':    self._manualSettingsScreen, },
                { 'page':    self._testScreen, },
                { 'page':    self._locationScreen,
                  'isShown': not bool(self.origName), },
                { 'page':    self._finishScreen,
                  'isShown': not bool(self.origName), },
            ])
        else:
            assert False, "Unknown flow type: %d" % (flowType)

        # Only keep pages that are shown (note: they are shown by default)...
        pageList = [ page for page in pageList if page.get('isShown', True) ]

        # Do the linking...
        numPages = len(pageList)
        _linkPages(None, pageList[0]['page'])
        for i, thisPageDict in enumerate(pageList):
            # Get this page out...
            thisPage = thisPageDict['page']

            # Get the next page...
            if 'next' in thisPageDict:
                # If this happens, we do a non-symmetric link...
                nextPage = thisPageDict['next']
                _linkPages(thisPage, nextPage, True, False)
            elif i != (numPages-1):
                nextPage = pageList[i+1]['page']
                _linkPages(thisPage, nextPage)
            else:
                _linkPages(thisPage, None)


    ###########################################################
    def run(self):
        """Run the create network wizard"""
        if self._testing:
            return self.RunWizard(self._testScreen)

        return self.RunWizard(self._welcomeScreen)


    ###########################################################
    def OnRefreshTimer(self, event=None):
        """Handle the refresh timer.

        This will update the list of cameras.  This is temp until we get
        notification from the back end.

        @param  event  Normally, the timer event; None when called first.
        """
        backEndClient = self.backEndClient

        # Kick off a minor active camera search periodically...
        self._refreshLoopCount += 1
        if (self._refreshLoopCount % _kMinorActiveSearchPeriod) == 0:
            backEndClient.activeCameraSearch(False)

        # Set the UPNP info if needed...
        revNum = backEndClient.getUpnpDictRevNum()
        oldRevNum = self.upnpDataModel.getUpnpRevNum()
        if revNum != oldRevNum:
            try:
                upnpDeviceDict = cPickle.loads(backEndClient.getUpnpDevices())
            except:
                upnpDeviceDict = {}
            self.upnpDataModel.setUpnpDeviceDict(revNum, upnpDeviceDict)

        # Set the ONVIF info if needed...
        revNum = backEndClient.getOnvifDictRevNum()
        oldRevNum = self.onvifDataModel.getOnvifRevNum()
        if revNum != oldRevNum:
            onvifDeviceDict = cPickle.loads(backEndClient.getOnvifDevices())
            self.onvifDataModel.setOnvifDeviceDict(revNum, onvifDeviceDict)

        # Set the local cams; this will send an update if they are different...
        camNames = backEndClient.getLocalCameraNames()
        self.localCamModel.setLocalCams(camNames)

        # Refresh again in a second...
        self._refreshTimer.Start(1000, True)

    ###########################################################
    def OnWizardCancel(self, event):
        self.CleanupTimers()

    ###########################################################
    def OnWizardFinished(self, event):
        self.CleanupTimers()

    ###########################################################
    def CleanupTimers(self):
        self._refreshTimer.Stop()
        self._refreshTimer = None
        self._onvifCredentialsScreen.CleanupTimers()
        self._testScreen.CleanupTimers()

    ###########################################################
    def OnChanging(self, event):
        """Respond to a page changing event.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        # We only care about things if we were on the last page and we're
        # moving forward; if not, return.
        # ...detect last page by seeing the "finish" page, or any page that
        # has no "next"...  (finish page might have next if adding another cam)
        thisPage = event.GetPage()
        hasNextPage = self.HasNextPage(thisPage)
        wasOnLastPage = (thisPage == self._finishScreen) or (not hasNextPage)
        if (not wasOnLastPage) or not event.GetDirection():
            event.Skip()
            return

        topLevelParent = self.GetParent()

        # Prevent adding cameras in a way that would violate the license.  This
        # is a litle weird, since we're trying to prevent two things here:
        # 1. Don't let them add another camera if this one fills up the max.
        # 2. If the user downgraded the license from the error dialog (or
        #    somehow got into the wizard by hacking stuff), don't even let
        #    them add this camera.
        pendingCams = 0
        if hasNextPage:
            # Adding _another_ camera case, so need to check one more...
            pendingCams += 1
        # If the user isn't editing a camera, enforce max cams number.
        if not self.origName and checkForMaxCameras(self.backEndClient, self, pendingCams):
            event.Veto()
            return

        if self.origName:
            # If we're editing a camera perform the edit.
            self.backEndClient.editCamera(self.origName, self.cameraName,
                                          self.cameraType, self.cameraUri,
                                          -1, self.camExtras)

            evt = FrontEndEvents.CameraEditedEvent(self.origName,
                                                   self.cameraName)
            if topLevelParent:
                topLevelParent.GetEventHandler().ProcessEvent(evt)

        else:
            # Add a new camera
            self.backEndClient.addCamera(self.cameraName, self.cameraType,
                                         self.cameraUri, self.camExtras)
            addDefaultRule(self.backEndClient, self.cameraName)

            # Post an event so interested controls can update.
            evt = FrontEndEvents.CameraAddedEvent(self.cameraName)
            if topLevelParent:
                topLevelParent.GetEventHandler().ProcessEvent(evt)


        # Reset variables to be in a new camera state
        self.origName = ''
        self.cameraName = ''
        self.cameraType = ''
        self.cameraUri = ''
        self.origCameraUri = ''
        self.camExtras = {}


###########################################################
def addDefaultRule(backEndClient, cameraName):
    """Ensure a camera has the default rule.

    @param  backEndClient  An interface to the back end.
    @param  cameraName     The camera to add the default rule to.
    """
    hasDefaultRule = False
    existingRules = backEndClient.getRuleInfoForLocation( cameraName)
    for name, _, _, _, _ in existingRules:
        # Look through any rules that already exist for a camera with
        # this name.  If one has the default target and trigger setup
        # we'll re-enable it and skip making a default rule.
        query = backEndClient.getQuery(name)
        targets = query.getTargets()
        triggers = query.getTriggers()

        if len(targets) != 1 or len(triggers) != 2:
            continue

        if targets[0].getTargetName() != 'anything':
            continue

        where = None
        duration = None
        if isinstance(triggers[0], WhereBlockDataModel):
            where = triggers[0]
        elif isinstance(triggers[1], WhereBlockDataModel):
            where = triggers[1]
        else:
            continue

        if isinstance(triggers[0], DurationBlockDataModel):
            duration = triggers[0]
        elif isinstance(triggers[1], DurationBlockDataModel):
            duration = triggers[1]
        else:
            continue

        if where.getTriggerType() != 'blankTrigger':
            continue

        if not duration.getMoreThanValue() == 0 or \
           not duration.getWantLessThan() == 0:
            continue

        hasDefaultRule = True
        backEndClient.enableRule(name)

        # Ensure it has only recording enabled...
        responses = kDefaultResponseList
        for name, config in responses:
            if name == kRecordResponse:
                config['isEnabled'] = True
        query.setResponses(responses)

        # Don't notify the backend about the edit we're doing. The "editQuery"
        # function issues a deleteRule() and addRule() to make sure that legacy
        # rules are in the correct format. However, the backend is notified of
        # the call to deleteRule() which causes it to stop the stream associated
        # with that rule; this is immediately followed by addRule() which turns
        # that stream back on.  This can cause a USB cameras to show as "not
        # connected" for more than 20 seconds. Please refer to Case 15964 in
        # FogBugz for more details.
        backEndClient.editQuery(query, query.getName(), False)

        break

    if not hasDefaultRule:
        # Create a default rule for the camera.
        newQuery = SavedQueryDataModel("", True)
        newQuery.getVideoSource().setLocationName(cameraName)
        baseQueryName = newQuery.getName()
        counter = 0
        existingQueryNames = [s.lower() for s in
                                 backEndClient.getRuleNames()]
        while newQuery.getName().lower() in existingQueryNames:
            counter += 1
            newQuery.setName(baseQueryName + "(%i)" % counter)
        backEndClient.addRule(newQuery, True)


##############################################################################
def _linkPages(pageA, pageB, linkForward=True, linkBack=True):
    """Link wizard pages together

    @param  pageA  The first page.
    @param  pageB  The page that follows pageA.
    """
    if pageA and linkForward:
        pageA.SetNext(pageB)
    if pageB and linkBack:
        pageB.SetPrev(pageA)


##############################################################################
class _BasePage(wxWizard.WizardPageSimple):
    """The base class for pages in the CameraSetupWizard."""

    ###########################################################
    def __init__(self, wizard, title, prev=None, next=None):
        """The initializer for _BasePage.

        Subclasses will note that they can expect a vertical box sizer (with
        the header already added) in self.sizer.  They can find the wizard
        in self.wizard.

        @param  wizard  The CameraSetupWizard.
        @param  title   A title for this page.
        @param  prev    The previous page.
        @param  next    The next page.
        """
        wxWizard.WizardPageSimple.__init__(self, wizard, prev, next)

        # For our subclasses...
        self.wizard = wizard
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        # Add title and descriptor text in a header if present
        headerPanel = wx.Panel(self)
        headerPanel.SetBackgroundColour(wx.WHITE)

        # Create the title text.
        headerTitle = wx.StaticText(headerPanel, -1, title)
        makeFontDefault(headerTitle)
        makeFontBold(headerTitle)

        # Create the help text...
        helpTextA = wx.StaticText(
            self, -1, "Need help?  For detailed online instructions, click ",
            style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(helpTextA)
        referenceLink = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, "here", kCameraConfigUrl)
        setHyperlinkColors(referenceLink)
        makeFontDefault(referenceLink)
        makeFontUnderlined(referenceLink)
        helpTextC = wx.StaticText(
            self, -1, ".", style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(helpTextC)

        # Size everything.
        headerSizer = wx.BoxSizer(wx.VERTICAL)
        headerSizer.Add(headerTitle, 1, wx.EXPAND | wx.LEFT | wx.TOP |
                        wx.BOTTOM, 2*_kPaddingSize)
        headerSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND)
        headerPanel.SetSizer(headerSizer)

        footerSizer = wx.BoxSizer(wx.HORIZONTAL)
        footerSizer.Add(helpTextA)
        footerSizer.Add(referenceLink)
        footerSizer.Add(helpTextC)

        # Add the header sizer, the footer sizer, and the child sizer...
        baseSizer = wx.BoxSizer(wx.VERTICAL)
        baseSizer.Add(headerPanel, 0, wx.EXPAND)
        baseSizer.Add(self.sizer, 1, wx.EXPAND | wx.BOTTOM, _kPaddingSize)
        baseSizer.Add(footerSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT,
                      3*_kPaddingSize)

        self.SetSizer(baseSizer)


##############################################################################
class _WelcomeScreen(_BasePage):
    """The welcome screen for the CameraSetupWizard."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _WelcomeScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_WelcomeScreen, self).__init__(
            wizard, ("Welcome.  This assistant will help you set up your "
            "camera with %s.") % (kAppName)
        )

        # This will be a tuple (idx, localCameraName) of whatever local camera
        # the user has picked.  Initted when we change to this page...
        self._camBeingEditedDeviceId = None
        self._resolutionOfCamBeingEdited = None
        self._selectedDeviceId = None
        self._selectedCam = None

        # If we're editing, get the camera's device ID and resolution.
        camUri = self.wizard.cameraUri
        camType = self.wizard.cameraType
        if camType == kWebcamCamType:
            reResult = re.match("(device):(\d+):(.*)", camUri)
            if reResult:
                _, deviceIdx, deviceName = reResult.groups()
                deviceIdx = int(deviceIdx)
                self._camBeingEditedDeviceId = (deviceIdx, deviceName)
                # Get the resolution of the camera being edited.
                if self.wizard.camExtras:
                    self._resolutionOfCamBeingEdited = \
                        tuple(self.wizard.camExtras.get('recordSize', None))

        caption = wx.StaticText(
            self, -1, u"Select which kind of camera you would like to set up:",
            style=wx.ST_NO_AUTORESIZE
        )

        cameraStyleLabel = wx.StaticText(self, -1, "Camera type:",
                                        style=wx.ST_NO_AUTORESIZE)
        self._cameraStyleChoice = wx.Choice(
            self, -1, choices=[_kCameraStyleNetwork, _kCameraStyleLocal]
        )

        self._manufacturerLabel = wx.StaticText(self, -1, "Manufacturer:",
                                                style=wx.ST_NO_AUTORESIZE)
        self._manufacturerChoice = wx.Choice(
            self, -1, choices=kCameraManufacturers
        )

        # A list of local cameras; note that we always want some min size here,
        # since cameras might show up later...
        self._localCamLabel = wx.StaticText(self, -1, "Camera:",
                                      style=wx.ST_NO_AUTORESIZE)
        self._localCamChoice = wx.Choice(self, -1)
        self._localCamChoice.SetMinSize((210, -1))

        # Need to show resolution for local cameras...
        self._resLabel = wx.StaticText(self, -1, "Record video at: ")
        self._resCtrl = wx.Choice(self, -1, choices=self.wizard.localCamModel.getDefaultResolutionsStr())
        self._resCtrl.SetSelection(0)
        self._resHelp = _getResHelpLink(self)

        # A warning shown for local cameras; we'll let this expand vertically,
        # so no need to wrap, but we do need to set the min size so it doesn't
        # grow the wizard...
        self._localCamWarning = wx.StaticText(self, -1,
            "IMPORTANT: Your webcam cannot be accessed if it is being used by "
            "other software.  Make sure to quit or disable webcam applications "
            "such as video chat.", style=wx.ST_NO_AUTORESIZE
        )
        self._localCamWarning.SetMinSize((1, -1))

        # Get all the fonts right...
        makeFontDefault(
            caption, cameraStyleLabel, self._cameraStyleChoice,
            self._manufacturerLabel, self._manufacturerChoice,
            self._localCamLabel, self._localCamChoice,
            self._resLabel, self._resCtrl,
            self._localCamWarning
        )


        # Add to sizers...
        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(caption, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)

        gridSizer = wx.FlexGridSizer(cols=2,
                                     vgap=_kPaddingSize, hgap=_kPaddingSize)
        gridSizer.Add(cameraStyleLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._cameraStyleChoice, 1,
                      wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        labelOverlapSizer = OverlapSizer(True)
        labelOverlapSizer.Add(self._manufacturerLabel)
        labelOverlapSizer.Add(self._localCamLabel)
        choiceOverlapSizer = OverlapSizer(True)
        choiceOverlapSizer.Add(self._manufacturerChoice)
        choiceOverlapSizer.Add(self._localCamChoice)
        gridSizer.Add(labelOverlapSizer, 0, wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(choiceOverlapSizer, 1,
                      wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self._resLabel, 0, wx.ALIGN_CENTER_VERTICAL |
                      wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        resCtrlSizer = wx.BoxSizer(wx.HORIZONTAL)
        resCtrlSizer.Add(self._resCtrl, 0, wx.ALIGN_CENTER_VERTICAL |
                         wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.RIGHT,
                         _kPaddingSize)
        resCtrlSizer.Add(self._resHelp, 0, wx.ALIGN_CENTER_VERTICAL |
                         wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.RIGHT,
                         _kPaddingSize)
        gridSizer.Add(resCtrlSizer, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL |
                      wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        innerSizer.Add(gridSizer, 0, wx.EXPAND | wx.TOP, 3*_kPaddingSize)

        innerSizer.Add(self._localCamWarning, 1, wx.EXPAND | wx.TOP |
                       wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 3*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)


        # Listen for model updates...
        self.wizard.localCamModel.addListener(self._handleLocalCamChange)


        # Bind...
        self._cameraStyleChoice.Bind(wx.EVT_CHOICE, self.OnCameraStyle)
        self._manufacturerChoice.Bind(wx.EVT_CHOICE, self.OnManufacturer)
        self._localCamChoice.Bind(wx.EVT_CHOICE, self.OnLocalCam)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)


    ###########################################################
    def _handleLocalCamChange(self, localCamModel):
        """Handle a change in the available local cameras.

        This just updates our UI to match...

        @param  localCamModel  The local camera data model.
        """
        assert localCamModel == self.wizard.localCamModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        # Freeze, just so user doesn't see UI changing...  TODO: Needed?
        self._localCamChoice.Freeze()
        try:
            # Start out with a blank choice...
            self._localCamChoice.Clear()

            # We'll look to see which should be selected by comparing to
            # self._localCamChoice; that way we keep selection good even if
            # user unplugs and re-plugs camera...
            selectedCam = localCamModel.getCamData(self._selectedDeviceId)

            for camName, deviceId in sorted(localCamModel.getLocalCamNamesWithDeviceIDs()):
                self._localCamChoice.Append(camName, deviceId)

            if selectedCam != None:
                # Found the camera that should be selected; select it...
                self._localCamChoice.SetStringSelection(selectedCam.getCamName())
                if self._resCtrl.GetItems() != selectedCam.getResolutionsStr():
                    self._resCtrl.Clear()
                    self._resCtrl.AppendItems(selectedCam.getResolutionsStr())
                    self._resCtrl.SetSelection(0)
                self._selectedCam = selectedCam

                # If this camera is being edited, we need to update the
                # resolution selection to the correct index.
                if self._camBeingEditedDeviceId == self._selectedDeviceId:
                    # The camera that has been selected is the one we are
                    # currently editing. Try to choose the correct
                    # resolution index.
                    if self._resolutionOfCamBeingEdited:
                        resolutionStr = self._selectedCam.resolutionNum2Str(
                                                self._resolutionOfCamBeingEdited
                                                )
                        if resolutionStr != None:
                            self._resCtrl.SetStringSelection(resolutionStr)
                        self._resolutionOfCamBeingEdited = None
            else:
                # Didn't find a camera that should be selected...
                if self._selectedDeviceId is not None:
                    # ...but something _should_ be selected; try to select
                    # by camera name.  Note that we don't actually re-set
                    # self._selectedDeviceId in this case, in case user later
                    # re-plugs in...
                    # If the camName isn't in the list, this will just be a
                    # no-op...
                    _, camName = self._selectedDeviceId
                    self._localCamChoice.SetStringSelection(camName)
                else:
                    # ...and the user hasn't made a selection yet, so pick
                    # the first one...
                    if self._localCamChoice.GetCount() != 0:
                        self._localCamChoice.SetSelection(0)

                        # Special case: update the device ID so we don't flip
                        # flop around...
                        self._selectedDeviceId = \
                            self._localCamChoice.GetClientData(0)
                        selectedCam = localCamModel.getCamData(self._selectedDeviceId)
                        self._resCtrl.Clear()
                        self._resCtrl.AppendItems(selectedCam.getResolutionsStr())
                        self._resCtrl.SetSelection(0)
                        self._selectedCam = selectedCam


        finally:
            self._localCamChoice.Thaw()


    ###########################################################
    def OnLocalCam(self, event):
        """Handle a change in the local camera choice.

        @param  event  The event.
        """
        # We just keep track of what was selected to handle unplug / replug...
        selection = self._localCamChoice.GetSelection()
        deviceId = self._localCamChoice.GetClientData(selection)

        self._selectedDeviceId = deviceId
        selectedCam = self.wizard.localCamModel.getCamData(self._selectedDeviceId)
        if self._resCtrl.GetItems() != selectedCam.getResolutionsStr():
            self._resCtrl.Clear()
            self._resCtrl.AppendItems(selectedCam.getResolutionsStr())
            self._resCtrl.SetSelection(0)
        self._selectedCam = selectedCam


    ###########################################################
    def OnCameraStyle(self, event):
        """Handle changes of the choice for switching between IP and webcam.

        @param  event  The event.
        """
        self._showUiByCameraStyle()
        self._adjustFlow()


    ###########################################################
    def OnManufacturer(self, event):
        """Handle changes of the manufacturer choice.

        @param  event  The event.
        """
        self._adjustFlow()


    ###########################################################
    def _showUiByCameraStyle(self):
        """Show/hide our UI based on the camera style selected in UI."""

        isLocal = (self._cameraStyleChoice.GetStringSelection() ==
                   _kCameraStyleLocal                             )

        self._manufacturerLabel.Show(not isLocal)
        self._manufacturerChoice.Show(not isLocal)

        self._localCamLabel.Show(isLocal)
        self._localCamChoice.Show(isLocal)
        self._resLabel.Show(isLocal)
        self._resCtrl.Show(isLocal)
        self._resHelp.Show(isLocal)

        self._localCamWarning.Show(isLocal)


    ###########################################################
    def _adjustFlow(self):
        """Adjust wizard flow based on current UI selections."""

        cameraStyle = self._cameraStyleChoice.GetStringSelection()
        if cameraStyle == _kCameraStyleLocal:
            self.wizard.updateBasicFlow(_kFlowTypeWebcam)
        else:
            manufacturer = self._manufacturerChoice.GetStringSelection()
            if manufacturer in kUpnpManufactrers:
                self.wizard.updateBasicFlow(_kFlowTypeUpnp)
            else:
                # Special-case: if someone happened to configure a camera as
                # UPnP even though the manufacturer isn't a UPnP manufacturer,
                # and they edit the camera, take them through the UPnP flow.
                # ...this should only happen with ACTi cameras, where we have
                # enabled their UPnP, but not listed them as a UPnP manufacturer
                try:
                    origUsn = extractUsnFromUpnpUrl(self.wizard.origCameraUri)
                    newUsn = extractUsnFromUpnpUrl(self.wizard.cameraUri)

                    if origUsn == newUsn:
                        self.wizard.updateBasicFlow(_kFlowTypeUpnp)
                        return
                except ValueError:
                    pass

                self.wizard.updateBasicFlow(_kFlowTypeManualNetcam)


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        This happens when we switch _to_ this page...  This is the place where
        we READ from the wizard and populate our UI.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        camUri = self.wizard.cameraUri
        camType = self.wizard.cameraType

        # By default, no webcam is selected...
        self._selectedDeviceId = None

        # Select the right style; default is network (so it's the else case)...
        if camType == kWebcamCamType:
            self._cameraStyleChoice.SetStringSelection(_kCameraStyleLocal)

            # Initialize self._selectedDeviceId based on the URI...
            reResult = re.match("(device):(\d+):(.*)", camUri)
            if reResult:
                _, deviceIdx, deviceName = reResult.groups()
                deviceIdx = int(deviceIdx)
                self._selectedDeviceId = (deviceIdx, deviceName)
        else:
            self._cameraStyleChoice.SetStringSelection(_kCameraStyleNetwork)

        # Always init the manufacturer by the wizard setting, even if we're
        # using 'webcam' mode.  This makes sure that things are initted in
        # any case...
        self._manufacturerChoice.SetStringSelection(
            self.wizard.cameraManufacturer
        )

        # Fake up a local camera change...
        # ...this will make sure that the webcam choice is initted and has the
        # right selection...
        self._handleLocalCamChange(self.wizard.localCamModel)

        # Make sure the right things are shown / hidden...
        self._showUiByCameraStyle()

        # Set focus on camera type...
        self._cameraStyleChoice.SetFocus()

        # Make sure that the flow is good...
        self._adjustFlow()


    ###########################################################
    def OnChanging(self, event):
        """Respond to a page changing event.

        We use this to handle switches from our page.  This is where we WRITE
        to the wizard...  Note that it's too late to edit flows now, so we did
        all that earlier...

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        isForward = event.GetDirection()
        if event.GetPage() != self:
            # Only care if we're leaving ourselves...
            event.Skip()
            return

        cameraStyle = self._cameraStyleChoice.GetStringSelection()

        if cameraStyle == _kCameraStyleNetwork:
            self.wizard.cameraManufacturer = \
                self._manufacturerChoice.GetStringSelection()

            if (self.wizard.cameraType == kWebcamCamType) or \
               (self.wizard.cameraUri.startswith("device:")):
                # If we were on a webcam camera type but now aren't, clear a
                # few things out; otherwise we'll leave things alone...
                assert (self.wizard.cameraType == kWebcamCamType) and \
                       (self.wizard.cameraUri.startswith("device:")), \
                       "Expected webcam type and URI to match."
                self.wizard.cameraType = ''
                self.wizard.cameraUri = ''

            # If we're not going to the UPnP flow, make sure we resolve any
            # UPnP URLs here.  This happens if the user selects a UPnP cam, then
            # goes back, then selects a non-UPnP manufacturer.
            if self.wizard.getBasicFlow() != _kFlowTypeUpnp:
                try:
                    self.wizard.cameraUri = realizeUpnpUrl(
                        self.wizard.upnpDataModel.getUpnpDeviceDict(),
                        self.wizard.cameraUri
                    )
                except ValueError:
                    pass
        else:
            if _vetoIfResolutionLocked(event, self.wizard,
                    self._resCtrl.GetStringSelection()):
                return

            selection = self._localCamChoice.GetSelection()
            if selection == -1:
                # Check isForward, even though we're the first page, just in
                # case we end up adding an earlier page in a redesign later...
                if isForward:
                    if self._localCamChoice.GetCount():
                        wx.MessageBox("You must select a camera", "Error",
                                      wx.OK | wx.ICON_ERROR,
                                      self.GetTopLevelParent())
                    else:
                        wx.MessageBox("No USB or built-in cameras were "
                                      "detected", "Error",
                                      wx.OK | wx.ICON_ERROR,
                                      self.GetTopLevelParent())
                    event.Veto()
                    return
            else:
                # Update self._selectedDeviceId from self._localCamChoice
                # ...this can be important if we had a name that matched,
                # but not the index...
                self._selectedDeviceId = \
                    self._localCamChoice.GetClientData(selection)

            try:
                (deviceIdx, deviceName) = self._selectedDeviceId
            except Exception:
                # If we have a bad device ID (which I think can only happen
                # if we're going backwards, which can't happen at the moment),
                # we'll just forget updating the cameraType...
                pass
            else:
                # This was only true of old-style device URLs...
                #localCamNames = self.wizard.localCamModel.getLocalCams()
                #assert localCamNames[deviceIdx] == deviceName

                self.wizard.cameraType = kWebcamCamType
                self.wizard.cameraUri = "device:%d:%s" % (deviceIdx, deviceName)

            # NOTE: We don't bother updating the manufacturer.  If the user
            # somehow gets back here, it's fine to leave it how it was...

            # Update the record size...
            self.wizard.camExtras['recordSize'] = \
                self._selectedCam.resolutionStr2Num(self._resCtrl.GetStringSelection())


##############################################################################
class _LocationScreen(_BasePage):
    """A screen for naming cameras."""
    def __init__(self, wizard):
        """The initializer for _LocationScreen.

        @param  wizard  The CameraSetupWizard.
        """
        super(_LocationScreen, self).__init__(wizard, "Location name")

        # Create persistent controls.
        locationLabel = wx.StaticText(self, -1, "Camera location:")
        makeFontDefault(locationLabel)
        self._locationCtrl = wx.TextCtrl(self, -1, size=(200, -1))
        self._locationCtrl.SetMaxLength(kMaxCameraNameLen)

        # Create controls shown when making a new camera.
        helpText = wx.StaticText(self, -1, "If you set up multiple cameras, a "
                   'descriptive name (e.g. "Backyard") can be helpful when '
                   'using features where you need to tell your cameras apart.'
                   '\n\nTo change this name in the future, select '
                   'Tools > Edit Location Name')
        makeFontDefault(helpText)
        helpText.Wrap(_kTextWrap)

        # Throw everything in sizers.
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(locationLabel, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._locationCtrl, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
                   _kPaddingSize)
        self.sizer.Add(hSizer, 0, wx.LEFT | wx.TOP, 3*_kPaddingSize)
        self.sizer.Add(helpText, 0, wx.ALL, 3*_kPaddingSize)

        # Bind to events
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)

        self.Layout()


    ###########################################################
    def OnChanging(self, event): #PYCHECKER OK: Function (OnChanging) has too many returns
        """Handle a page changing event.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        if (event.GetPage() != self) or not event.GetDirection():
            # If we're not going forward we don't care about this event.
            event.Skip()
            return

        # Normalize the location name so it can be safely saved as a file name
        newLocation = normalizePath(self._locationCtrl.GetValue())
        newLocationLower = newLocation.lower()

        if len(newLocation) > kMaxCameraNameLen:
            wx.MessageBox("Location names cannot be more than %d characters." \
                          % kMaxCameraNameLen,
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            event.Veto()
            self._locationCtrl.SetFocus()
            return

        if not len(newLocation):
            wx.MessageBox("You must enter a location.", "Error",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            event.Veto()
            self._locationCtrl.SetFocus()
            return

        if newLocation.startswith(' ') or newLocation.endswith(' '):
            wx.MessageBox("Location names cannot begin or end with a space.",
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            event.Veto()
            self._locationCtrl.SetFocus()
            return

        if newLocation.endswith('.'):
            wx.MessageBox("Location names cannot end with a period.",
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            event.Veto()
            self._locationCtrl.SetFocus()
            return

        for suffix in kInvalidCameraNameSuffixes:
            if newLocation.endswith(suffix):
                wx.MessageBox('The camera name cannot end with "%s".' % suffix,
                              "Error", wx.OK | wx.ICON_ERROR,
                              self.GetTopLevelParent())
                event.Veto()
                self._locationCtrl.SetFocus()
                return

        # Prevent invalid location names
        if re.search("[%s]" % kInvalidPathChars, newLocation) is not None:
            wx.MessageBox("The camera name cannot contain any of the following "
                          "characters: %s. Please choose a different name." % \
                          kInvalidPathCharsDesc, "Error",
                          wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            event.Veto()
            self._locationCtrl.SetFocus()
            return

        # Prevent non-UTF8 characters in location names
        try:
            newLocation.encode('utf-8', 'strict')
        except UnicodeEncodeError, e:
            wx.MessageBox(("The camera name cannot contain the "
                          "character \"%s\". "
                          "Please choose a different name.") %
                           e.object[e.start:e.start+1],
                          "Error",
                           wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
            event.Veto()
            self._locationCtrl.SetFocus()
            return

        # Prevent duplicate camera locations
        locations = [s.lower() for s in
                        self.wizard.backEndClient.getCameraLocations()]
        if newLocationLower != self.wizard.origName.lower():
            if newLocationLower in locations:
                # Check if another camera is configured with a name differing
                # only by caps.
                wx.MessageBox("Another camera is configured as location \"%s\". "
                              "Please choose another name." \
                              % newLocation, "Error",
                              wx.OK | wx.ICON_ERROR, self.GetTopLevelParent())
                event.Veto()
                self._locationCtrl.SetFocus()
                return

            rules = \
                self.wizard.backEndClient.getRuleInfoForLocation(newLocationLower)
            dmNames = [s.lower() for s in
                       self.wizard.dataManager.getCameraLocations()]
            if len(rules) > 0 or newLocationLower in dmNames:
                # Check if there are any old rules or video that will be
                # associated with this name, and warn the user.
                res = wx.MessageBox("The name of this camera location already "
                    "exists. Video recorded at that location will be added to "
                    "the video recorded by this camera location.  If this is "
                    "not what you intended, enter a different name.",
                    "Warning", wx.OK | wx.CANCEL | wx.ICON_WARNING,
                    self.GetTopLevelParent())

                if res != wx.OK:
                    event.Veto()
                    self._locationCtrl.SetFocus()
                    return

        # Set the current camera name
        self.wizard.cameraName = newLocation



    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        self._locationCtrl.SetValue(self.wizard.cameraName)
        self._locationCtrl.SetFocus()


##############################################################################
class _OfferHelpScreen(_BasePage):
    """A screen asking the user if they want extra help setting their cam up."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _OfferHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_OfferHelpScreen, self).__init__(
            wizard, "Choose setup options"
        )

        textA = wx.StaticText(
            self, -1, u"I would like to:", style=wx.ST_NO_AUTORESIZE
        )

        self._alreadyRadio = wx.RadioButton(self, -1,
            "Set up %s with a network camera that is already working" %
            (kAppName), style=wx.RB_GROUP
        )
        self._helpRadio = wx.RadioButton(self, -1,
            "Use %s to help me get my network camera working" %
            (kAppName)
        )
        rb1 = self._alreadyRadio
        rb2 = self._helpRadio

        makeFontDefault(textA, self._alreadyRadio, self._helpRadio)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)
        innerSizer.Add(rb1, 0, wx.TOP, 3*_kPaddingSize)
        innerSizer.Add(rb2, 0, wx.TOP, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        self._alreadyRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self._helpRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self._alreadyRadio.Bind(wx.EVT_LEFT_DCLICK, self.OnRadioDoubleClick)
        self._helpRadio.Bind(wx.EVT_LEFT_DCLICK, self.OnRadioDoubleClick)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)


    ###########################################################
    def OnRadioButton(self, event):
        """Handle either of the radio buttons being pressed.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        self.wizard.setHelpFlow(self._helpRadio.GetValue())


    ###########################################################
    def OnRadioDoubleClick(self, event):
        """Handle double-clicks to radio buttons.

        This should automatically go to next.
        """
        radioButton = event.GetEventObject()

        # Don't know if all of this is needed, but could imagine getting a
        # double-click when radio button wasn't selected...
        if not radioButton.GetValue():
            radioButton.SetValue(1)
            radioButton.Refresh()
            radioButton.Update()
            self.wizard.setHelpFlow(self._helpRadio.GetValue())

        self.wizard.ShowPage(self.GetNext())


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        We use this to handle switches to our page.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Init to the wizard default for wantHelp...
        wantHelp = self.wizard.getHelpFlow()
        self._alreadyRadio.SetValue(not wantHelp)
        self._helpRadio.SetValue(wantHelp)


##############################################################################
class _EthernetHelpScreen(_BasePage):
    """A screen telling the user to plug into Ethernet."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _EthernetHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_EthernetHelpScreen, self).__init__(
            wizard, "Prepare your camera"
        )

        textA = wx.StaticText(self, -1,
            "Connect one end of an Ethernet cable into your camera, and the "
            "other into your router.  This step is necessary even if you plan "
            "to use your camera wirelessly.\n"
            "\n"
            "IMPORTANT: Make sure your camera is NOT plugged into a power "
            "source yet.",
            style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textA)
        textA.Wrap(_kTextWrap)

        ethernetBmp = wx.Bitmap("frontEnd/bmps/Connect_Ethernet_Help.jpg")
        ethernetStaticBmp = FixedStaticBitmap(self, -1, ethernetBmp)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)
        innerSizer.Add(ethernetStaticBmp, 0, wx.TOP, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)


##############################################################################
class _PowerHelpScreen(_BasePage):
    """A screen telling the user to plug into power."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _PowerHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_PowerHelpScreen, self).__init__(
            wizard, "Prepare your camera - plug it into power"
        )

        textA = wx.StaticText(self, -1,
            "Now plug your camera into a power source.",
            style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textA)

        powerBmp = wx.Bitmap("frontEnd/bmps/Plug_In_Power_Help.jpg")
        powerStaticBmp = FixedStaticBitmap(self, -1, powerBmp)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)
        innerSizer.Add(powerStaticBmp, 0, wx.TOP, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)


##############################################################################
class _DetectedCamerasScreen(_BasePage):
    """A screen for choosing auto-detected cameras."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _DetectedCamerasScreen.

        @param  wizard  The CameraSetupWizard.
        """
        super(_DetectedCamerasScreen, self).__init__(wizard,
            "Select your camera from the devices connected to your network"
        )

        self._hideConfiguredCheck = wx.CheckBox(self, -1,
                                                "Hide configured cameras")
        self._hideConfiguredCheck.SetValue(True);

        # This will be the UPNP string of what the user has picked.  Initted
        # when we change to this page...
        self._selectedDeviceId = None

        # Create the controls.
        self._automaticRadio = wx.RadioButton(
            self, -1, "My camera is in the list below (it may take a "
            "minute before it appears):",
            style=wx.RB_GROUP
        )
        self._listBox = wx.ListBox(self, -1)
        self._listBox.SetMinSize((-1, 120))
        self._upnpList = []
        self._onvifList = []

        self._upnpPanel = wx.Panel(self, -1)
        self._modelNameTitle = wx.StaticText(self._upnpPanel, -1,
                                             "Model name:")
        self._modelNameLabel = wx.StaticText(self._upnpPanel, -1, "")
        self._addressTitle = wx.StaticText(self._upnpPanel, -1,
                                           "Device address:")
        self._addressLink = wx.adv.HyperlinkCtrl(self._upnpPanel, -1, "", " ", style=wx.NO_BORDER | wx.adv.HL_CONTEXTMENU | wx.adv.HL_ALIGN_LEFT)
        setHyperlinkColors(self._addressLink)

        self._helpMeRadio = wx.RadioButton(self, -1,
            "My camera does not appear in the list.  Tell me my options."
        )

        self._manualRadio = wx.RadioButton(
            self, -1, "Manually specify the address of a network camera"
        )

        makeFontDefault(self._automaticRadio, self._listBox,
                        self._modelNameTitle, self._modelNameLabel,
                        self._addressTitle, self._addressLink,
                        self._helpMeRadio, self._manualRadio,
                        self._hideConfiguredCheck)
        makeFontUnderlined(self._addressLink)

        innerSizer = wx.BoxSizer(wx.VERTICAL)


        innerSizer.Add(self._automaticRadio, 0, wx.TOP, 2*_kPaddingSize)

        autoStuffSizer = wx.BoxSizer(wx.VERTICAL)

        autoStuffSizer.Add(self._hideConfiguredCheck, 0, wx.TOP, _kPaddingSize)

        autoStuffSizer.Add(self._listBox, 0, wx.EXPAND | wx.TOP, _kPaddingSize)

        upnpSizer = wx.BoxSizer(wx.VERTICAL)
        modelNameSizer = wx.BoxSizer(wx.HORIZONTAL)
        modelNameSizer.Add(self._modelNameTitle, 0,
                           wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        modelNameSizer.Add(self._modelNameLabel, 1,
                           wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.LEFT,
                           _kPaddingSize/2)
        upnpSizer.Add(modelNameSizer, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                      wx.EXPAND)
        deviceAddrSizer = wx.BoxSizer(wx.HORIZONTAL)
        deviceAddrSizer.Add(self._addressTitle, 0,
                            wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        deviceAddrSizer.Add(self._addressLink, 1,
                            wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.LEFT,
                            _kPaddingSize/2)
        upnpSizer.Add(deviceAddrSizer, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                      wx.EXPAND | wx.TOP, _kPaddingSize/2)
        self._upnpPanel.SetSizer(upnpSizer)
        self._upnpPanel.Show(False)

        autoStuffSizer.Add(self._upnpPanel, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                           wx.EXPAND | wx.TOP, _kPaddingSize)

        innerSizer.Add(autoStuffSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        innerSizer.Add(self._helpMeRadio, 0, wx.TOP, _kPaddingSize)

        innerSizer.Add(self._manualRadio, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN |
                       wx.TOP | wx.BOTTOM, _kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        self.wizard.upnpDataModel.addListener(self._handleUpnpChange)
        self.wizard.onvifDataModel.addListener(self._handleOnvifChange)

        # Bind...
        self._hideConfiguredCheck.Bind(wx.EVT_CHECKBOX, self.OnCheckBox);
        self._listBox.Bind(wx.EVT_LISTBOX, self.OnListBox)
        self._listBox.Bind(wx.EVT_LISTBOX_DCLICK, self.OnListBoxSelect)
        self._automaticRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self._helpMeRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self._manualRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)

        self._listBox.Bind(wx.EVT_RIGHT_DOWN, self.OnRightClick)


    ###########################################################
    def _isManufacturerMatch(self, model):
        """Tell whether the given model matches the needed manufacturer.

        @param  model  The model to check against.
        """
        neededManufacturer = self.wizard.cameraManufacturer

        # If 'needed' is other, we have no filter; allow everything...
        if neededManufacturer == kOtherCameraManufacturer:
            return True

        # Always allow 'Unknown' to show up...
        if model == 'Unknown':
            return True

        if model in kTypeToManufacturer:
            return (kTypeToManufacturer[model] == neededManufacturer)
        else:
            genericModels = _findGenericCamTypes(model)
            for genericModel in genericModels:
                assert genericModel in kTypeToManufacturer
                if kTypeToManufacturer[genericModel] == neededManufacturer:
                    return True

            return False


    ###########################################################
    def OnCheckBox(self, event):
        """Handle a request to hide or show configured cameras.

        @param  event  The event.  Ignored.
        """
        self._handleUpnpChange(self.wizard.upnpDataModel)
        self._handleOnvifChange(self.wizard.onvifDataModel)


    ###########################################################
    def OnRightClick(self, event):
        """Handle a request to dump UPNP and ONVIF info to the log.

        @param  event  The event.  Ignored.
        """
        if wx.GetKeyState(wx.WXK_SHIFT) and wx.GetKeyState(wx.WXK_ALT):
            upnpDeviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()
            onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()

            for _, dev in upnpDeviceDict.iteritems():
                print str(dev)
            for _, dev in onvifDeviceDict.iteritems():
                print str(dev)

            wx.MessageBox("UPNP and ONVIF data has been dumped to the log.",
                          kAppName, wx.OK | wx.ICON_INFORMATION,
                          self.GetTopLevelParent())


    ###########################################################
    def _handleUpnpChange(self, upnpDataModel):
        """Handle a change in the UPNP dictionary.

        We don't change much, but we might need to update our link.

        @param  upnpDataModel  The UPNP data model.
        """
        assert upnpDataModel == self.wizard.upnpDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        self._handleDataModelChange(upnpDataModel)
        self._updateUiFromSelection()


    ###########################################################
    def _handleOnvifChange(self, onvifDataModel):
        """Handle a change in the ONVIF dictionary.

        We don't change much, but we might need to update our link.

        @param  onvifDataModel  The ONVIF data model.
        """
        assert onvifDataModel == self.wizard.onvifDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        self._handleDataModelChange(onvifDataModel)
        self._updateUiFromSelection()


    ###########################################################
    def _handleDataModelChange(self, dataModel):
        """Handle a change in the UPNP dictionary.

        We don't change much, but we might need to update our link.

        @param  upnpDataModel  The UPNP data model.
        """
        assert ((dataModel == self.wizard.upnpDataModel) ^
                (dataModel == self.wizard.onvifDataModel))

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        isUpnp = (dataModel == self.wizard.upnpDataModel)

        # We want to hide already configured UPnP cameras, except for the edit
        # case when we need to show the camera we're editing.
        configuredDevIds = []

        if self._hideConfiguredCheck.GetValue():
            editedDevId = ""
            if isUpnpUrl(self.wizard.cameraUri):
                editedDevId = extractUsnFromUpnpUrl(self.wizard.cameraUri)
            elif isOnvifUrl(self.wizard.cameraUri):
                editedDevId = extractUuidFromOnvifUrl(self.wizard.cameraUri)
            editedDevId = editedDevId.encode('utf-8')

            locations = self.wizard.backEndClient.getCameraLocations()
            for location in locations:
                _, uri, _, _ = self.wizard.backEndClient.getCameraSettings(location)

                devId = ''
                if isUpnp and isUpnpUrl(uri):
                    devId = extractUsnFromUpnpUrl(uri)
                elif not isUpnp and isOnvifUrl(uri):
                    devId = extractUuidFromOnvifUrl(uri)
                if devId:
                    devId = devId.encode('utf-8')
                    if devId != editedDevId:
                        configuredDevIds.append(devId)

        if isUpnp:
            upnpDeviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()
            # Make a sorted list of tuples: (name, identifier)
            # ...where identifier is a USN...
            # We strip out all routers, non-presentable UPNP devices, and wrong-
            # manufacturer devices...
            deviceList = [(dev.getFriendlyName(True)+" [UPnP]", devUsn)
                          for (devUsn, dev) in upnpDeviceDict.iteritems()
                          if (not dev.isRouter()) and
                             dev.isPresentable(True) and
                             self._isManufacturerMatch(dev.getModelName()) and
                             (devUsn not in configuredDevIds) ]
        else:
            onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()
            # Make a sorted list of tuples: (name, identifier)
            # ...where identifier is a UUID...
            deviceList = [(dev.getFriendlyName(True)+" [ONVIF]", devUuid)
                          for (devUuid, dev) in onvifDeviceDict.iteritems()
                          if ((devUuid not in configuredDevIds) and
                              (len(dev.validOnvifIpAddrs) > 0))
                          ]
        deviceList.sort(key=lambda x: (x[0].lower(), x[1]))

        # Freeze, just so user doesn't see UI changing...  TODO: Needed?
        self._listBox.Freeze()
        try:
            # Start out with a blank choice...
            self._listBox.Clear()
            if isUpnp:
                self._upnpList = deviceList
            else:
                self._onvifList = deviceList

            # We'll look to see which should be selected by comparing to
            # self._localCamChoice; that way we keep selection good even if
            # user unplugs and re-plugs camera...
            selectedCam = -1

            # All all things in the list...
            for (friendlyName, deviceId) in self._onvifList + self._upnpList:
                if deviceId == self._selectedDeviceId:
                    selectedCam = self._listBox.GetCount()
                self._listBox.Append(friendlyName, deviceId)

            if selectedCam != -1:
                # Found the camera that should be selected; select it...
                self._listBox.SetSelection(selectedCam)
            else:
                self._listBox.EnsureVisible(0)

        finally:
            self._listBox.Thaw()


    ###########################################################
    def OnRadioButton(self, event=None):
        """Handles a press on one of the radio buttons.

        @param  event  The event; or None in some cases.
        """
        self._updateUiFromSelection()
        event.Skip()


    ###########################################################
    def OnListBoxSelect(self, event=None):
        """Handle listbox events.

        This event happens on double-click...

        @param  event  The event.
        """
        self._automaticRadio.SetValue(True)
        self._updateUiFromSelection()
        self.wizard.ShowPage(self.GetNext())


    ###########################################################
    def OnListBox(self, event):
        """Handle listbox events.

        @param  event  The event.
        """
        # Make sure we're in automatic mode whenever they choose something
        # from the listbox...
        self._automaticRadio.SetValue(1)
        self._updateUiFromSelection()

        # Keep track of selected device, so that if a device disappears and
        # reappears we can get it back...
        selection = self._listBox.GetSelection()
        if selection == -1:
            self._selectedDeviceId = None
        else:
            self._selectedDeviceId = self._listBox.GetClientData(selection)
        event.Skip()


    ###########################################################
    def _updateUiFromSelection(self):
        """Updates the flow type based on the state of the UI."""

        showUpnp = False

        selection = self._listBox.GetSelection()
        upnpDeviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()
        onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()

        # Update UI elements...
        if selection != -1:
            deviceId = self._listBox.GetClientData(selection)

            if deviceId in upnpDeviceDict or deviceId in onvifDeviceDict:
                showUpnp = True

                if deviceId in upnpDeviceDict:
                    device = upnpDeviceDict[deviceId]
                    modelName = device.getModelName()
                    presentationUrl, isGuess = device.getPresentationUrl()
                else:
                    device = onvifDeviceDict[deviceId]
                    modelName = device.getFriendlyName()
                    presentationUrl = device.validOnvifIpAddrs[-1][0]
                    isGuess = False

                self._modelNameLabel.SetLabel(modelName)
                self._addressLink.SetURL(presentationUrl)
                if isGuess:
                    # Show the label "Unknown", but make it link to the guess?
                    self._addressLink.SetLabel("Unknown")
                else:
                    self._addressLink.SetLabel(presentationUrl)

                # Refreshing after setting label seems necessary on Win.
                self._addressLink.Refresh()

            else:
                assert False, "%s missing from deviceDict" % deviceId

        self._upnpPanel.Show(showUpnp)

        # Update flow...
        if self._automaticRadio.GetValue():
            if selection != -1:
                deviceId = self._listBox.GetClientData(selection)
                if deviceId not in upnpDeviceDict and \
                   deviceId not in onvifDeviceDict:
                    self.wizard.updateBasicFlow(_kFlowTypeWebcam)
                    return

                device = upnpDeviceDict.get(deviceId)
                onvifDev = onvifDeviceDict.get(deviceId)
                if device:
                    _, isGuess = device.getPresentationUrl()
                    if isGuess:
                        self.wizard.updateBasicFlow(_kFlowTypeBadUpnp)
                    else:
                        self.wizard.updateBasicFlow(_kFlowTypeUpnp)

                elif onvifDev:
                    self.wizard.updateBasicFlow(_kFlowTypeOnvif)

                else:
                    self.wizard.updateBasicFlow(_kFlowTypeBadUpnp)

            else:
                # We won't let them hit next anyway, so flow doesn't matter...
                pass
        elif self._helpMeRadio.GetValue():
            self.wizard.updateBasicFlow(_kFlowTypeUpnpManualConfigAfterHelp)
        else:
            self.wizard.updateBasicFlow(_kFlowTypeUpnpManualConfig)


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        We use this to handle switches to our page.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Ensure the proper controls are displayed and populated.
        camUri = self.wizard.cameraUri
        isHelpFlow = self.wizard.getHelpFlow()
        basicFlowType = self.wizard.getBasicFlow()

        # By default, no camera is selected...
        self._selectedDeviceId = None

        # Check for UPNP/ONVIF, which has special URL types...
        if isUpnpUrl(camUri):
            self._selectedDeviceId = extractUsnFromUpnpUrl(camUri)

            self._automaticRadio.SetValue(1)
            self._listBox.SetFocus()
        elif isOnvifUrl(camUri):
            self._selectedDeviceId = extractUuidFromOnvifUrl(camUri)

            self._automaticRadio.SetValue(1)
            self._listBox.SetFocus()
        elif not camUri:
            # No URI, so assume user wants UPNP...
            self._automaticRadio.SetValue(1)
            self._listBox.SetFocus()
        else:
            # Non-upnp.  Select one of the manual ones...
            if (basicFlowType == _kFlowTypeUpnpManualConfigAfterHelp) or \
               isHelpFlow:

                # Select "help me" radio, since we're either in the help flow
                # (no 'manual' choice) or the user is coming back from the
                # 'manualWithHelp' screen...
                self._helpMeRadio.SetValue(1)
                self._helpMeRadio.SetFocus()
            else:
                self._manualRadio.SetValue(1)
                self._manualRadio.SetFocus()

        # Only show "manual" option if we're not in the "help" flow...
        self._manualRadio.Show(not isHelpFlow)

        # Fake up a UPNP and ONVIF change...
        self._handleDataModelChange(self.wizard.upnpDataModel)
        self._handleDataModelChange(self.wizard.onvifDataModel)

        self._updateUiFromSelection()

        # Bizarre that scrolling is weird on Mac (with > 6 items in the list)
        # if we don't do this...  Still not great if item 7 is selected...
        if wx.Platform == '__WXMAC__':
            selection = self._listBox.GetSelection()
            if selection != -1:
                wx.CallAfter(self._listBox.EnsureVisible, 0)
                wx.CallAfter(self._listBox.EnsureVisible, selection)


    ###########################################################
    def OnChanging(self, event):
        """Handle a page changing event.

        We use this to handle switches from our page.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        isForward = event.GetDirection()
        if event.GetPage() != self:
            # Only care if we're leaving ourselves...
            event.Skip()
            return

        upnpDeviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()
        onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()
        camManuf = self.wizard.cameraManufacturer

        # If manual, we just try to convert if we're currently using a UPNP/ONVIF URL.
        if self._manualRadio.GetValue() or self._helpMeRadio.GetValue():
            if isUpnpUrl(self.wizard.cameraUri):
                self.wizard.cameraUri = realizeUpnpUrl(upnpDeviceDict,
                                                       self.wizard.cameraUri)
            elif isOnvifUrl(self.wizard.cameraUri):
                self.wizard.cameraUri = realizeOnvifUrl(onvifDeviceDict,
                                                        self.wizard.cameraUri)
            return

        selection = self._listBox.GetSelection()
        if selection == -1:
            if isForward:
                if self._listBox.GetCount() == 0:
                    if camManuf and (camManuf != kOtherCameraManufacturer):
                        manufString = " %s" % camManuf
                    else:
                        manufString = ""

                    wx.MessageBox("No%s devices were found." % manufString,
                                  "Error", wx.OK | wx.ICON_ERROR,
                                  self.GetTopLevelParent())
                else:
                    wx.MessageBox("You must select a device from the list.",
                                  "Error", wx.OK | wx.ICON_ERROR,
                                  self.GetTopLevelParent())
                event.Veto()
            return

        deviceId = self._listBox.GetClientData(selection)
        assert deviceId in upnpDeviceDict or deviceId in onvifDeviceDict, \
               "Unknown UPNP/ONVIF device selected"


        try:
            prevUsn = extractUsnFromUpnpUrl(self.wizard.cameraUri)
        except ValueError:
            prevUsn = ""

        try:
            prevUuid = extractUuidFromOnvifUrl(self.wizard.cameraUri)
        except ValueError:
            prevUuid = ""

        if prevUsn != deviceId and prevUuid != deviceId:
            # Clear camera type; UPNP screen will pick one...
            # ...put a bogus cameraUri in, just so we can keep track of
            # which camera was selected.  The UPNP screen should reset this
            # with a real path...  Note: we also put a username/password in
            # so that if the user typed it in, it gets kept.
            self.wizard.cameraType = ""
            splitResult = urlparse.urlsplit(self.wizard.cameraUri)

            # Unquote before passing in to constructUpnpUrl, which requires
            # unquoted username and password...
            username = splitResult.username
            if username:
                username = urllib.unquote(username)
            else:
                username = ''
            password = splitResult.password
            if password:
                password = urllib.unquote(password)
            else:
                password = ''

            if deviceId in upnpDeviceDict:
                self.wizard.cameraUri = \
                    constructUpnpUrl(deviceId, username, password)
            elif deviceId in onvifDeviceDict:
                self.wizard.cameraUri = \
                    constructOnvifUrl(deviceId, username, password)
        else:
            # No need to do anything...
            pass


##############################################################################
class _UpnpSettingsScreen(_BasePage):
    """A screen for setting up supported UPNP cameras."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _UpnpSettingsScreen.

        @param  wizard  The CameraSetupWizard.
        """
        super(_UpnpSettingsScreen, self).__init__(
            wizard,
            "Enter settings to allow %s to access your camera" % kAppName
        )

        # Create the controls.
        self._cameraTypeLabel = wx.StaticText(self, -1, "Camera type:")
        self._cameraTypeCtrl = wx.Choice(self, -1)

        # This should create this so that it doesn't affect the needed width
        # given by the grid bag sizer; we'll tell the grid bag sizer to expand
        # it, though, so it will always have the full width of the grid bag
        # sizer...
        self._typeDescLabel = wx.StaticText(self, -1, " ")
        self._typeDescLabel.SetMinSize((_kTextWrap, -1))

        self._schemeLabel = wx.StaticText(self, -1, "Protocol:")
        self._schemeCtrl = wx.Choice(self, -1, choices=["http", "rtsp"])
        self._schemeCtrl.SetSelection(1)

        self._otherPortLabel = wx.StaticText(self, -1, "Port (optional):")
        self._otherPortCtrl = wx.TextCtrl(self, -1, size=(40, -1))
        self._otherPortCtrl.SetMaxLength(5)

        self._streamPathLabel = wx.StaticText(self, -1, "Stream path:")
        self._streamPathCtrl = wx.TextCtrl(self, -1, size=(200, -1))

        self._fullUrlLabel = wx.StaticText(self, -1, " ",
                                           style=wx.ST_NO_AUTORESIZE)

        self._userLabel = wx.StaticText(self, -1, "User name:")
        self._userCtrl = wx.TextCtrl(self, -1, size=(200, -1))
        self._passLabel = wx.StaticText(self, -1, "Password:")
        self._passCtrl = wx.TextCtrl(self, -1, size=(200, -1),
                                     style=wx.TE_PASSWORD)
        self._passVerifyLabel = wx.StaticText(self, -1, "Verify password:")
        self._passVerifyCtrl = wx.TextCtrl(self, -1, size=(200, -1),
                                           style=wx.TE_PASSWORD)

        self._rtspPortLabel = wx.StaticText(self, -1, "RTSP port (optional):")
        self._rtspPortCtrl = wx.TextCtrl(self, -1, size=(40, -1))
        self._rtspPortCtrl.SetMaxLength(5)
        self._rtspPortLabel.Show(False)    # Init to hidden for default sizing...
        self._rtspPortCtrl.Show(False)     # Init to hidden for default sizing...

        self._httpPortLabel = wx.StaticText(self, -1, "HTTP port (optional):")
        self._httpPortCtrl = wx.TextCtrl(self, -1, size=(40, -1))
        self._httpPortCtrl.SetMaxLength(5)
        self._httpPortLabel.Show(False)    # Init to hidden for default sizing...
        self._httpPortCtrl.Show(False)     # Init to hidden for default sizing...

        self._audioCtrl = wx.CheckBox(self, -1, _kAudioCtrlLabel)

        self._advancedLabel = wx.StaticText(self, -1, _kAdvancedLabel,
                style=wx.ST_NO_AUTORESIZE)
        self._forceTcpCtrl = wx.CheckBox(self, -1, _kForceTCPLabel)

        makeFontDefault(self._cameraTypeLabel, self._cameraTypeCtrl,
                        self._typeDescLabel,
                        self._schemeLabel, self._schemeCtrl,
                        self._otherPortLabel, self._otherPortCtrl,
                        self._streamPathLabel, self._streamPathCtrl,
                        self._fullUrlLabel,
                        self._userLabel, self._userCtrl,
                        self._passLabel, self._passCtrl,
                        self._passVerifyLabel, self._passVerifyCtrl,
                        self._rtspPortLabel, self._rtspPortCtrl,
                        self._httpPortLabel, self._httpPortCtrl,
                        self._advancedLabel, self._audioCtrl,
                        self._forceTcpCtrl)

        innerSizer = wx.BoxSizer(wx.VERTICAL)

        controlSizer = wx.GridBagSizer(vgap=_kPaddingSize, hgap=2*_kPaddingSize)
        controlSizer.SetEmptyCellSize((0,0))
        self._controlSizer = controlSizer
        controlSizer.Add(self._cameraTypeLabel, pos=(0, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._cameraTypeCtrl, pos=(0, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)

        controlSizer.Add(self._typeDescLabel, pos=(1, 0), span=(1, 2),
                         flag=wx.EXPAND)

        controlSizer.Add(self._schemeLabel, pos=(2, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        protoPortSizer = wx.BoxSizer(wx.HORIZONTAL)
        protoPortSizer.Add(self._schemeCtrl, 0, wx.ALIGN_CENTER_VERTICAL |
                           wx.RIGHT, _kPaddingSize)
        protoPortSizer.AddStretchSpacer(1)
        protoPortSizer.Add(self._otherPortLabel, 0, wx.ALIGN_CENTER_VERTICAL |
                           wx.LEFT | wx.RIGHT, _kPaddingSize)
        protoPortSizer.Add(self._otherPortCtrl, 0, wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(protoPortSizer, pos=(2, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        controlSizer.AddGrowableCol(1)

        controlSizer.Add(self._streamPathLabel, pos=(3, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._streamPathCtrl, pos=(3, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        controlSizer.Add(self._fullUrlLabel, pos=(4, 1),
                         flag=wx.EXPAND | wx.BOTTOM, border=2*_kPaddingSize)

        controlSizer.Add(self._userLabel, pos=(5, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._userCtrl, pos=(5, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._passLabel, pos=(6, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._passCtrl, pos=(6, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._passVerifyLabel, pos=(7, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._passVerifyCtrl, pos=(7, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)

        controlSizer.Add(self._rtspPortLabel, pos=(8, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._rtspPortCtrl, pos=(8, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._httpPortLabel, pos=(9, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._httpPortCtrl, pos=(9, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)

        controlSizer.Add(self._advancedLabel, pos=(10,0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._audioCtrl, pos=(10,1),
                         flag=wx.ALIGN_CENTER_VERTICAL)

        controlSizer.Add(self._forceTcpCtrl, pos=(11,1),
                         flag=wx.ALIGN_CENTER_VERTICAL |
                         wx.RESERVE_SPACE_EVEN_IF_HIDDEN)


        innerSizer.Add(controlSizer, 1, wx.EXPAND | wx.TOP | wx.BOTTOM,
                       2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        self._cameraTypeCtrl.Bind(wx.EVT_CHOICE, self.OnCameraType)

        self._schemeCtrl.Bind(wx.EVT_CHOICE, self.OnUrlRelatedUiChange)
        self._streamPathCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)
        self._otherPortCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)
        self._rtspPortCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)
        self._httpPortCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)

        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)

        self.wizard.upnpDataModel.addListener(self._handleUpnpChange)


    ###########################################################
    def OnUrlRelatedUiChange(self, event):
        """Handle generic UI changes that could change the URL we show.

        @param  event  The event.
        """
        isRTSP = self._shouldShowForceTCPControl()
        self._forceTcpCtrl.Show(isRTSP)

        self._updateUrl()
        event.Skip()


    ###########################################################
    def OnCameraType(self, event):
        """Handle changes in the camera type.

        @param  event  The type event (or None).
        """
        self._adjustUiByCameraType()
        self._updateUrl()
        event.Skip()


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        This happens when we switch _to_ this page...

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Get the device; if no device, we skip.  Should only happen if we
        # are coming backwards from the test screen.  In that case, our UI
        # will be as good as it gets...
        device = None
        if isUpnpUrl(self.wizard.cameraUri):
            devId = extractUsnFromUpnpUrl(self.wizard.cameraUri)
            device = self.wizard.upnpDataModel.getUpnpDeviceDict().get(devId)

        if device is None:
            event.Skip()
            return

        # Split the URI...
        splitResult = urlparse.urlsplit(self.wizard.cameraUri)

        # Parse out any current username and password, and pathPart...
        username = splitResult.username
        if not username:
            username = ""
        else:
            username = urllib.unquote(username)
        password = splitResult.password
        if not password:
            password = ""
        else:
            password = urllib.unquote(password)

        port = ""
        try:
            if splitResult.port is not None:
                port = str(splitResult.port)
        except Exception:
            # Could happen if the URL somehow has a non-integral port...
            pass

        scheme = splitResult.scheme

        # Get the resolution...
        resolution = tuple(self.wizard.camExtras.get('recordSize',
                                                     kDefaultRecordSize))

        # Get the choices...
        modelName = device.getModelName()

        listChoices, selection = self._getCameraChoices(modelName)

        if self.wizard.cameraType in kTypeToStreamPath:
            defaultScheme, defaultPathPart, defaultPort = \
                _getStreamPath(self.wizard.cameraType, resolution)
            defaultScheme = defaultScheme.split(':')[0]
            if defaultPort:
                defaultPort = str(defaultPort)
            else:
                defaultPort = ""
        else:
            defaultScheme, defaultPathPart, defaultPort = ("http", "", "")

        # Pre-select if our current type is in the choices; else choose the
        # default type...
        if self.wizard.cameraType in listChoices:
            selection = listChoices.index(self.wizard.cameraType)
            pathPart = _getUrlPathPart(splitResult)

            # Never show the default port, except in "other"...
            otherPort = port
            if port == defaultPort:
                port = ""
        else:
            # Should happen if we purposely cleared cameraType from prev.
            # wizard screen.  In that case, we want to init everything from
            # the camera table--only username/password/USN were valid...
            assert self.wizard.cameraType == "", \
                   "Expected blank camType, not: %s" % self.wizard.cameraType
            assert not port, "Expected no port was set by previous screen"

            self.wizard.cameraType = listChoices[selection]

            scheme = defaultScheme
            pathPart = defaultPathPart

            # Never show the default port, except in "other"...
            otherPort = defaultPort
            port = ""


        # Expect pathPart to have a '/' at the start, but don't want to show
        # that to user (unless that's the whole path)...
        if pathPart.startswith('/') and (pathPart != '/'):
            pathPart = pathPart[len('/'):]

        # Put in controls...
        self._cameraTypeCtrl.SetItems(listChoices)
        self._cameraTypeCtrl.SetSelection(selection)

        self._schemeCtrl.SetStringSelection(scheme)
        self._otherPortCtrl.SetValue(otherPort)
        self._streamPathCtrl.SetValue(ensureUnicode(pathPart))
        self._userCtrl.SetValue(ensureUnicode(username))
        self._passCtrl.SetValue(ensureUnicode(password))
        self._passVerifyCtrl.SetValue(ensureUnicode(password))

        # Only set the port control if it's RTSP.
        if scheme == 'rtsp':
            self._rtspPortCtrl.SetValue(port)
            self._httpPortCtrl.SetValue("")
        else:
            self._rtspPortCtrl.SetValue("")
            self._httpPortCtrl.SetValue(port)

        self._audioCtrl.SetValue(
                self.wizard.camExtras.get('recordAudio', kDefaultRecordAudio))

        self._forceTcpCtrl.SetValue(
                self.wizard.camExtras.get('forceTCP', True))

        self._adjustUiByCameraType()
        self._updateUrl()

        self._userCtrl.SetFocus()


    ###########################################################
    def _getSettingsFromUi(self, ignoreErrors):
        """Get the current settings out of the UI.

        @param  ignoreErrors  Can be 'all', 'none', 'most'.  For 'all', no
                              errors will be ignored.  For 'none', none will.
                              For 'most', we'll ignore all but the most dire of
                              errors.
        @return errorMessage  If non-None, contains the error message.
                              If None, there were no errors, or the errors were
                              ignored.
        @return cameraUri     The camera URI.  None if we couldn't figure out.
                              Will always be utf-8.
        """
        assert ignoreErrors in ('all', 'none', 'most')

        # Get simple things out of UI...
        cameraType = self._cameraTypeCtrl.GetStringSelection()

        # Init camera URI...
        cameraUri = None

        # Init device...
        device = None

        # Get the device; will fail if the device disappared...
        try:
            devId = extractUsnFromUpnpUrl(self.wizard.cameraUri)
            device = self.wizard.upnpDataModel.getUpnpDeviceDict().get(devId)
        except:
            # Expecting this if it's not UPNP.
            pass

        if device is None:
            if ignoreErrors == 'none':
                return ("This device can no longer be found on the "
                        "network.  It may be rebooting.", None, None)
            return (None, cameraType, cameraUri)

        # Get settings out of UI...
        username = self._userCtrl.GetValue().strip()
        password = self._passCtrl.GetValue().strip()

        if (ignoreErrors != 'all')                       and \
           (password != self._passVerifyCtrl.GetValue())    :
            self._passVerifyCtrl.SetValue('')
            self._passVerifyCtrl.SetFocus()
            return (_kPasswordsMustMatchStr, None, None)

        if (ignoreErrors == 'none') and (password) and (not (username)):
            return ("A username is required if a password is used.",
                    None, None, None)

        if cameraType in kTypeToStreamPath:
            scheme, pathPart, defaultPort = \
                _getStreamPath(
                    cameraType, _getHighestResolutionByLicense(self.wizard)
                )

            portStr = ""
            if self._shouldShowRtspPort(cameraType):
                portStr = self._rtspPortCtrl.GetValue().strip()
            elif self._shouldShowHttpPort(cameraType):
                portStr = self._httpPortCtrl.GetValue().strip()
        else:
            assert (cameraType == "") or (cameraType == kOtherIpCamType)
            pathPart = self._streamPathCtrl.GetValue().strip()

            scheme = "%s://" % (self._schemeCtrl.GetStringSelection())

            # Don't allow them to just keep clicking "Next" without thinking.
            # We don't know of any good reason to have a blank path part with
            # 'http', so we'll prevent it.  If a user really wants it, they can
            # enter '/'...
            if (not pathPart) and (scheme == 'http://') and \
               (ignoreErrors == 'none'):
                return ("You must enter the path to the video stream.",
                        None, None)

            # Add a '/' to the start if the user didn't put one (we don't
            # expect them to, but don't add an extra one if they did)...
            if pathPart and (not pathPart.startswith('/')):
                pathPart = '/' + pathPart

            defaultPort = None
            portStr = self._otherPortCtrl.GetValue().strip()

        try:
            port = int(portStr)
        except ValueError:
            # Any non-integer string other than the blank string is an error
            if portStr and (ignoreErrors == 'none'):
                return("Please enter a valid port number.",
                       None, None)
            port = defaultPort

        cameraUri = constructUpnpUrl(device.getUsn(), username, password,
                                     pathPart, scheme, port)

        return (None, cameraType, cameraUri)


    ###########################################################
    def OnChanging(self, event):
        """Handle a page changing event.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        isForward = event.GetDirection()
        if event.GetPage() != self:
            # Only care if we're leaving ourselves...
            event.Skip()
            return

        if isForward:
            ignoreErrors = 'none'
        else:
            # Want to ignore most errors when going backward...
            ignoreErrors = 'most'

        errorMessage, cameraType, cameraUri = \
            self._getSettingsFromUi(ignoreErrors)

        if errorMessage:
            wx.MessageBox(errorMessage, "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            event.Veto()
        else:
            # Only update if we have something good...
            if (cameraType and cameraUri):
                self.wizard.cameraType = cameraType
                self.wizard.cameraUri = cameraUri
                self.wizard.camExtras['recordSize'] = \
                    _getHighestResolutionByLicense(self.wizard)
                self.wizard.camExtras['recordAudio'] = self._audioCtrl.GetValue()
                self.wizard.camExtras['forceTCP'] = self._forceTcpCtrl.GetValue()


    ###########################################################
    def _handleUpnpChange(self, upnpDataModel):
        """Handle a change in the UPNP dictionary.

        We don't change much, but we might need to update our link.

        @param  upnpDataModel  The UPNP data model.
        """
        assert upnpDataModel == self.wizard.upnpDataModel

        # Update the UI, which should adjust spacing (I hope)...
        self._adjustUiByCameraType()

        self._updateUrl()


    ###########################################################
    def _updateUrl(self):
        """Update the URL link.

        This is called whenever the UPNP dicts change.
        """
        _, _, url = self._getSettingsFromUi('all')

        if url is not None:

            if isUpnpUrl(url):
                deviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()

                try:
                    url = realizeUpnpUrl(deviceDict, url)
                except ValueError:
                    # Don't expect this, since we've already checked that the
                    # url is UPnP.
                    url = None

        if url:
            # Strip out username and password from the URL...
            scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
            netloc = netloc.split('@', 1)[-1]
            url = urlparse.urlunsplit((scheme, netloc, path, query, fragment))

            # It seems important to escape out the ampersand.  Weird.
            url = url.replace('&', '&&')

            self._fullUrlLabel.SetLabel(ensureUnicode(url))
            truncateStaticText(self._fullUrlLabel)
        else:
            # The only reason we should fail when ignoring all errors is if
            # the device isn't available...
            self._fullUrlLabel.SetLabel("<device not available>")


    ###########################################################
    def _shouldShowRtspPort(self, camType):
        """Return True if we should show the port controls for the given cam.

        @param  camType         The camera type in question.
        @return shouldShowPort  True if we should show the port.
        """
        if camType in kTypeToStreamPath:
            return kTypeToStreamPath[camType][0] == 'rtsp://'
        else:
            return False


    ###########################################################
    def _shouldShowHttpPort(self, camType):
        """Return True if we should show the port controls for the given cam.

        @param  camType         The camera type in question.
        @return shouldShowPort  True if we should show the port.
        """
        if camType in kTypeToStreamPath:
            return kTypeToStreamPath[camType][0] == 'http://'
        else:
            return False


    ###########################################################
    def _shouldShowForceTCPControl(self):
        """Return True if we should show the Force TCP control according to the
        current URL scheme.

        @return: shouldShowCtrl  True if we should show the control.
        """
        return 'rtsp' == self._schemeCtrl.GetStringSelection()


    ###########################################################
    def _adjustUiByCameraType(self):
        """Adjust our UI based on the currently selected camera tye."""

        camType = self._cameraTypeCtrl.GetStringSelection()
        if camType == kOtherIpCamType:
            showUrlControls = True
            description = ""
            showRtspPortControls = False  # We show the "other" port controls...
            showHttpPortControls = False
        else:
            showUrlControls = False

            description = _getCameraDescription(camType)

            if description:
                description += "\n\n"
            description += \
                "Enter the information you used to set up your camera:"
            showRtspPortControls = self._shouldShowRtspPort(camType)
            showHttpPortControls = self._shouldShowHttpPort(camType)

        for urlControl in (self._schemeLabel, self._schemeCtrl,
                           self._streamPathLabel, self._streamPathCtrl,
                           self._otherPortLabel, self._otherPortCtrl,
                           self._fullUrlLabel):
            urlControl.Show(showUrlControls)
        for portControl in (self._rtspPortLabel, self._rtspPortCtrl):
            portControl.Show(showRtspPortControls)
        for portControl in (self._httpPortLabel, self._httpPortCtrl):
            portControl.Show(showHttpPortControls)

        self._forceTcpCtrl.Show(
            showRtspPortControls or
            (showUrlControls and self._shouldShowForceTCPControl())
        )

        if description:
            # Show the label...
            self._typeDescLabel.Show(True)

            # Now, set the label and wrap...
            self._typeDescLabel.SetLabel(description)
            self._typeDescLabel.Wrap(_kTextWrap)
        else:
            # Hide the label...
            self._typeDescLabel.Show(False)

        # Ack, a Layout() call.  ...needed since we're shuffling around UI
        # stuff massively...  Sketchy: calling twice seems to make it work
        # correctly...
        self.Layout()
        self.Layout()

        # Shouldn't be needed, but is on Mac (the fields don't get redrawn if
        # not)...
        if wx.Platform == '__WXMAC__':
            self.Refresh()


    ###########################################################
    def _getCameraChoices(self, modelName):
        """Get the list of camera choices given a model name.

        @param  modelName         The UPNP model name.
        @return listChoices       A list of choices.
        @return defaultSelection  The default selection for listChoices.
        """
        genericTypes = _findGenericCamTypes(modelName)
        if modelName in kUpnpModelMap:
            listChoices = kUpnpModelMap[modelName] + genericTypes
            listChoices.append(kOtherIpCamType)
            defaultSelection = 0
        else:
            if not genericTypes:
                # We didn't find any generics for the given model name; show
                # all generics in the UPnP list.  TODO: Filter by the
                # manufacturer that the user chose (?)
                listChoices = [camType for (_, camType) in kUpnpGenericList
                               if kGenericIndicator in camType             ]
            else:
                listChoices = genericTypes

            listChoices.append(kOtherIpCamType)

            if genericTypes:
                # If we had some generics, select first...
                defaultSelection = 0
            else:
                # If we didn't, select "other" by default...
                defaultSelection = len(listChoices)-1

        return listChoices, defaultSelection


##############################################################################
class _OnvifCredentialsScreen(_BasePage):
    """A screen for entering credentials for a supported ONVIF camera."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _OnvifCredentialsScreen.

        @param  wizard  The CameraSetupWizard.
        """
        super(_OnvifCredentialsScreen, self).__init__(
            wizard,
            "Enter credentials to allow %s to access your camera" % kAppName
        )

        # We use this flag to allow only one event the ability to kill
        # credentials verification.
        self._verifyingCredentials = False

        # This flag is set when authentication is successful; however, this
        # alone is not enough to continue the flow. If authentication is False,
        # self._reasonForAuthFailure will hold a string value that tells us why.
        self._authenticationSuccessful = False

        # This holds the reason for authentication failure. It will hold a
        # string value that is an ONVIF fault code if the camera returns some
        # kind of error message; if no fault code is returned, it can be a
        # http request error string message; if neither of these two, then
        # it will be an empty string, which means authentication was successful,
        # or it's inited.
        self._reasonForAuthFailure = ''

        # This flag is set when stream uri's are received from the camera
        # AFTER authentication was successful.  This is the flag that controls
        # moving on to the next page in the wizard.
        self._streamUrisRetrieved = False

        # We keep track of the chosen device object's generation number so we
        # know when our device has updated. They start at 0, and continue
        # incrementing by '1' every time an active search is performed.
        self._deviceGenerationNum = -1

        # We set a timeout while we wait for credentials to verify. If the
        # timer times out before verification is complete, we all enable all
        # controls, and try progress to the next page. If the wizard fails to
        # advance, then this could indicate that the camera is unreachable,
        # or it's off.
        self._timer = wx.Timer(self, -1)

        # A timer for updating the progress spinner.
        self._spinnerTimer = wx.Timer(self, -1)

        # This is the spinner we'll be showing while the user waits for the
        # app to authenticate their credentials.
        progBmps = [wx.Bitmap("frontEnd/bmps/prog%d.png" % i) for i in xrange(8)]
        self._spinnerBmps = [FixedStaticBitmap(self, -1, progBmps[i])
                                 for i in xrange(8)]
        self._curSpinnerId = 0

        self._userLabel = wx.StaticText(self, -1, "User name:")
        self._userCtrl = wx.TextCtrl(self, -1, size=(200, -1))
        self._passLabel = wx.StaticText(self, -1, "Password:")
        self._passCtrl = wx.TextCtrl(self, -1, size=(200, -1),
                                     style=wx.TE_PASSWORD)
        self._passVerifyLabel = wx.StaticText(self, -1, "Verify password:")
        self._passVerifyCtrl = wx.TextCtrl(self, -1, size=(200, -1),
                                           style=wx.TE_PASSWORD)

        self._authMessage = wx.StaticText(self, -1, "Please wait while we "
                                                    "connect to your camera...",
                                                    style=wx.ST_NO_AUTORESIZE)

        self._description = wx.StaticText(self, -1, "",
                                          style=wx.ST_NO_AUTORESIZE)
        self._description.SetMinSize((1, 1))

        makeFontDefault(self._userLabel, self._userCtrl,
                        self._passLabel, self._passCtrl,
                        self._passVerifyLabel, self._passVerifyCtrl,
                        self._authMessage, self._description)

        innerSizer = wx.BoxSizer(wx.VERTICAL)

        controlSizer = wx.GridBagSizer(vgap=_kPaddingSize, hgap=2*_kPaddingSize)
        controlSizer.SetEmptyCellSize((0,0))

        overlapSizer = OverlapSizer(True)
        for bmp in self._spinnerBmps:
            overlapSizer.Add(bmp, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
            bmp.Hide()

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self._authMessage, 0, wx.ALIGN_CENTER_VERTICAL |
                   wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        hsizer.Add(overlapSizer, 0, wx.ALIGN_CENTER_VERTICAL |
                   wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(hsizer, 0, wx.EXPAND)

        overlapSizer = OverlapSizer(True)
        overlapSizer.Add(vsizer, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        overlapSizer.Add(self._description, 1, wx.EXPAND |
                         wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        controlSizer.Add(self._userLabel, pos=(1, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._userCtrl, pos=(1, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._passLabel, pos=(2, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._passCtrl, pos=(2, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._passVerifyLabel, pos=(3, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._passVerifyCtrl, pos=(3, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.AddGrowableCol(1)

        innerSizer.Add(controlSizer, 0, wx.EXPAND | wx.TOP | wx.BOTTOM,
                       2*_kPaddingSize)
        innerSizer.Add(overlapSizer, 1, wx.EXPAND | wx.BOTTOM, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        # Bind to things...
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)

        self.Bind(wx.EVT_TIMER, self.OnTimer, self._timer)
        self.Bind(wx.EVT_TIMER, self.OnSpinnerTimer, self._spinnerTimer)

        # Listen to ONVIF changes...
        self.wizard.onvifDataModel.addListener(self._handleOnvifChange)


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        This happens when we switch _to_ this page...

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Assume we need verification whenever we get to this page.
        self._authenticationSuccessful = False
        self._streamUrisRetrieved = False

        # Split the URI...
        splitResult = urlparse.urlsplit(self.wizard.cameraUri)

        # Parse out any current username and password, and pathPart...
        username = splitResult.username
        if not username:
            username = ""
        else:
            username = urllib.unquote(username)
        password = splitResult.password
        if not password:
            password = ""
        else:
            password = urllib.unquote(password)

        self._userCtrl.SetValue(ensureUnicode(username))
        self._passCtrl.SetValue(ensureUnicode(password))
        self._passVerifyCtrl.SetValue(ensureUnicode(password))

        # Hide the messages.
        self._authMessage.Hide()
        self._description.Hide()

        self.Refresh()

        self._userCtrl.SetFocus()


    ###########################################################
    def OnChanging(self, event):
        """Handle a page changing event.

        This happens when we switch _from_ this page...

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        isForward = event.GetDirection()
        if event.GetPage() != self:
            # Only care if we're leaving ourselves...
            event.Skip()
            return

        if isForward:

            if self._verifyingCredentials:
                event.Veto()
                return

            ignoreErrors = 'none'
        else:
            # Want to ignore all errors when going backward...
            ignoreErrors = 'all'

        errorMessage, usernameUI, passwordUI = self._getSettingsFromUi(ignoreErrors)

        if errorMessage:
            self._updateDescription(errorMessage)
            event.Veto()

        elif isForward:

            devUuid, device, selectedIp = None, None, None

            # Try to get the device. If we can't, veto and return. This means
            # the camera is not reachable for some reason.
            if isOnvifUrl(self.wizard.cameraUri):
                devUuid = extractUuidFromOnvifUrl(self.wizard.cameraUri)
                device = self.wizard.onvifDataModel.getOnvifDeviceDict().get(devUuid)

                if device and device.validOnvifIpAddrs:
                    selectedIp = device.validOnvifIpAddrs[-1]

            if not device or not selectedIp:
                self._updateDescription("The camera disconnected from the "
                                        "network.")
                event.Veto()
                return

            creds = device.getCredentials()
            isAuth = device.isAuthenticated()
            generationNum = device.generation

            if creds == (usernameUI, passwordUI):
                self._authenticationSuccessful = isAuth
                self._streamUrisRetrieved = len(device.streamUris) > 0
            else:
                self._authenticationSuccessful = False
                self._streamUrisRetrieved = False

            # Veto and start verifying credentials if we don't have our
            # stream uri's for the selected camera yet.
            if (not self._authenticationSuccessful) or \
                    (not self._streamUrisRetrieved):
                self._startVerifyingCredentials(devUuid, generationNum,
                                                selectedIp, usernameUI,
                                                passwordUI)
                event.Veto()

            # All is clear, save relevant information, and continue.
            else:
                self.wizard.cameraUri = \
                    constructOnvifUrl(devUuid, usernameUI, passwordUI,
                                      self.wizard.cameraUri)


        elif not isForward:

            self._stopVerifyingCredentials('backwards')


    ###########################################################
    def OnTimer(self, event):
        """This kills credentials verification on timeout. This should only
        be called during verification, and if the timer times out.

        @param  event  The Timer event.
        """
        # If we timeout, kill verification.
        self._stopVerifyingCredentials('timeout')


    ###########################################################
    def OnSpinnerTimer(self, event):
        """This animates the spinner.

        @param  event  The Timer event.
        """
        self._spinnerBmps[self._curSpinnerId].Hide()
        self._curSpinnerId = (self._curSpinnerId+1) % len(self._spinnerBmps)
        self._spinnerBmps[self._curSpinnerId].Show()


    ###########################################################
    def _getSettingsFromUi(self, ignoreErrors):
        """Checks if the passwords match, and if there is a username and password.

        @param  ignoreErrors  Can be 'all', 'none', 'most'.  For 'all', all
                              errors will be ignored.  For 'none', none will.
                              For 'most', we'll ignore all but the most dire of
                              errors.
        @return errorMessage  If non-None, contains the error message.
                              If None, there were no errors, or the errors were
                              ignored.
        @return username      The username to the desired ONVIF profile.
                              None if an error occured.
        @return password      The password to the given username.
                              None if an error occured.
        """
        username = self._userCtrl.GetValue().strip()
        password = self._passCtrl.GetValue().strip()

        if (ignoreErrors != 'all')                       and \
           (password != self._passVerifyCtrl.GetValue())    :
            self._passVerifyCtrl.SetValue('')
            self._passVerifyCtrl.SetFocus()
            return (_kPasswordsMustMatchStr, None, None)

        if (ignoreErrors == 'none') and (password) and (not (username)):
            return ("A username is required if a password is used.",
                    None, None)

        return (None, username, password)


    ###########################################################
    def _startVerifyingCredentials(self, devUuid, generationNum, selectedIp,
                                   username, password):
        """Displays a spinner and some text that tells the user to wait while
        verification is in progress; sets a timeout if the camera is
        unreachable or off.

        @param devUuid  The UUID of the device we wish to verify our credentials
                        with.
        @param generationNum  The generation number of the device.
        @param selectedIp  The selected IP address of the device.
        @param username  The username.
        @param password  The password.
        """
        if not self._verifyingCredentials:

            # Prevent ourselves from being called again during verification.
            self._verifyingCredentials = True

            # Save the generation number
            self._deviceGenerationNum = generationNum

            self.wizard.backEndClient.setOnvifSettings(devUuid, selectedIp,
                                                       username, password)

            # Disable controls so that the user can't change anything, while
            # we're verifying credentials.
            self._userCtrl.Disable()
            self._passCtrl.Disable()
            self._passVerifyCtrl.Disable()

            # Start timeout timer.
            timeout = 30000
            self._timer.Start(timeout, wx.TIMER_ONE_SHOT)

            # Show spinner and Start the spinner timer.
            self._spinnerBmps[self._curSpinnerId].Show()
            self._spinnerTimer.Start(_kSpinnerDelay, wx.TIMER_CONTINUOUS)

            # Hide the description, and show the authentication message.
            self._description.Hide()
            self._authMessage.Show()

    ###########################################################
    def CleanupTimers(self):
        self._spinnerTimer.Stop()
        self._spinnerTimer = None
        self._timer.Stop()
        self._timer = None



    ###########################################################
    def _stopVerifyingCredentials(self, reason):
        """Stops spinner and attempts to move to the next page.

        @param  reason  A string that tells us who is stopping verification.
        """
        if self._verifyingCredentials:
            # prevent ourselves from being called while no verification is
            # in progress.
            self._verifyingCredentials = False

            # Enable controls.
            self._userCtrl.Enable()
            self._passCtrl.Enable()
            self._passVerifyCtrl.Enable()

            # Hide the messages.
            self._authMessage.Hide()
            self._description.Hide()

            # Stop the timers.
            if self._timer.IsRunning():
                self._timer.Stop()
            if self._spinnerTimer.IsRunning():
                self._spinnerTimer.Stop()

            # Hide the spinner.
            for bmp in self._spinnerBmps:
                bmp.Hide()

            # Only check for authentication if we timed out, or if onvif
            # says we're done.
            if reason in ('onvif', 'timeout'):
                wx.CallAfter(self._checkForOnvifAuthentication)

    ###########################################################
    def _log(self, strmsg):
        print >> sys.stderr, strmsg

    ###########################################################
    def _checkForOnvifAuthentication(self):
        """Show error messages if we couldn't get verification from the camera.
        If no errors, we try to go to the next page.
        """

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        if ((not self._authenticationSuccessful) or
            (not self._streamUrisRetrieved)):
            # If we didn't retrieve any stream uri's, we can't go to the next
            # screen in the wizard. Find out what went wrong, and tell the user.

            errorMsg = ''

            if ((not self._authenticationSuccessful) and
                (self._reasonForAuthFailure == kFaultSubcodeNotAuthorized)):

                # We're here because authentication was NOT successful.
                errorMsg = "Authentication failed. Please verify your " \
                           "username and password and try again."

            elif ((not self._reasonForAuthFailure) or
                (self._reasonForAuthFailure == kFaultSubcodeNotAuthorized)):
                # We're here because authentication was successful, but for
                # some reason, we were not able to retrieve the stream
                # uri's. If the reason is an empty string (or None), then
                # the camera returned an empty list of profiles. This
                # technically should never happen, but we put this catch
                # here in case a camera is not completely ONVIF compliant,
                # or if the camera is not configured proplerly.
                # If the reason is an Authentication Failure Fault Code,
                # then it's possible the user is able to view the list of
                # stream profile names, but not have the access rights to
                # retrieve the actual stream URI's for those profiles. This
                # technically shouldn't happen, but just in case, we'll
                # catch it here...
                errorMsg = "Could not retrieve camera configuration. " \
                           "Please ensure your user account has the " \
                           "correct permissions and try again."

            elif self._reasonForAuthFailure == kHttpRequestError:
                # We expect this to happen if the connection with the camera
                # went wrong for some reason.
                errorMsg = "The camera could not be reached. Please " \
                           "ensure it is still powered on and connected " \
                           "to the network and try again."

            elif ((self._reasonForAuthFailure) and
                  (self._reasonForAuthFailure in kAllFaultCodes)):
                # Under normal circumstances, we should never get here.
                # We expect this to happen if we're talking to a camera
                # with a different ONVIF version, or it's not fully
                # compliant, or something else. Luckily, we've got a fault
                # code, and we can use this to find out what happened
                # to the camera internally.
                errorMsg = "The camera has experienced an internal error " \
                           "with fault code: %s." % \
                           self._reasonForAuthFailure

            else:
                # We should never, ever, get here; however, we expect this
                # if we (or the camera) experienced an unknown error,
                # (crash, maybe?) or we received a fault code from it that
                # we don't have documented for some reason.
                if self._reasonForAuthFailure is None:
                    self._reasonForAuthFailure = "unknown error"
                errorMsg = "An error has occurred :" + str(self._reasonForAuthFailure) + \
                            ". Please wait a moment and try again."

            self._updateDescription(errorMsg)
            return

        self.wizard.ShowPage(self.GetNext())


    ###########################################################
    def _updateDescription(self, message):
        """Updates and displays the description under the user/pass controls.

        @param  message  The message to display as a string.
        """
        self._description.SetLabel(message)
        self.Layout()
        self._description.Show()


    ###########################################################
    def _handleOnvifChange(self, onvifDataModel):
        """Handle a change in the ONVIF dictionary.

        We check to see if the device we're trying to connect to has profiles
        or streamUris yet.  If it does, we stop verifying credentials.

        @param  onvifDataModel  The ONVIF data model.
        """
        assert onvifDataModel == self.wizard.onvifDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        devUuid, device = None, None
        if isOnvifUrl(self.wizard.cameraUri):
            devUuid = extractUuidFromOnvifUrl(self.wizard.cameraUri)
            device = self.wizard.onvifDataModel.getOnvifDeviceDict().get(devUuid)

        if device and (device.generation > self._deviceGenerationNum):

            creds = device.getCredentials()
            isAuth = device.isAuthenticated()
            reason = device.getFailureReason()

            _, usernameUI, passwordUI = self._getSettingsFromUi('all')

            if creds == (usernameUI, passwordUI):
                self._authenticationSuccessful = isAuth
                self._reasonForAuthFailure = reason
                self._streamUrisRetrieved = len(device.streamUris) > 0
                self._stopVerifyingCredentials('onvif')



##############################################################################
class _OnvifSettingsScreen(_BasePage):
    """A screen for editing onvif camera settings."""
    def __init__(self, wizard):
        """The initializer for _OnvifSettingsScreen.

        @param  wizard  The CameraSetupWizard.
        """
        super(_OnvifSettingsScreen, self).__init__(
            wizard, "Enter settings to allow the %s application to access your "
            "camera" % kAppName
        )

        # Will be inited on Changed...
        self._selectedStreamUri = ''

        # Create the controls.
        self._onvifUriLabel = wx.StaticText(self, -1, "Video Profile:")
        self._onvifUriCtrl = wx.Choice(self, -1, size=(320, -1))

        self._schemeLabel = wx.StaticText(self, -1, "Protocol:")
        self._schemeCtrl = wx.Choice(self, -1, choices=["http", "rtsp"])
        self._schemeCtrl.SetSelection(1)

        self._otherPortLabel = wx.StaticText(self, -1, "Port (optional):")
        self._otherPortCtrl = wx.TextCtrl(self, -1, size=(40, -1))
        self._otherPortCtrl.SetMaxLength(5)

        self._streamPathLabel = wx.StaticText(self, -1, "Stream path:")
        self._streamPathCtrl = wx.TextCtrl(self, -1, size=(200, -1))

        self._fullUrlLabel = wx.StaticText(self, -1, " ",
                                           style=wx.ST_NO_AUTORESIZE)

        self._advancedLabel = wx.StaticText(self, -1, _kAdvancedLabel,
                style=wx.ST_NO_AUTORESIZE)
        self._audioCtrl = wx.CheckBox(self, -1, _kAudioCtrlLabel)
        self._forceTcpCtrl = wx.CheckBox(self, -1, _kForceTCPLabel)

        makeFontDefault(self._onvifUriLabel, self._onvifUriCtrl,
                        self._schemeLabel, self._schemeCtrl,
                        self._otherPortLabel, self._otherPortCtrl,
                        self._streamPathLabel, self._streamPathCtrl,
                        self._fullUrlLabel,
                        self._advancedLabel, self._audioCtrl,
                        self._forceTcpCtrl)

        # Throw stuff into sizers...
        innerSizer = wx.BoxSizer(wx.VERTICAL)

        controlSizer = wx.GridBagSizer(vgap=_kPaddingSize, hgap=2*_kPaddingSize)
        self._controlSizer = controlSizer

        innerSizer.Add(controlSizer, 1, wx.EXPAND | wx.TOP | wx.BOTTOM,
                       2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        # Bind to events.
        self._schemeCtrl.Bind(wx.EVT_CHOICE, self.OnUrlRelatedUiChange)
        self._streamPathCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)
        self._otherPortCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)

        self._onvifUriCtrl.Bind(wx.EVT_CHOICE, self.OnOnvifProfileChange)

        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)



        self.wizard.onvifDataModel.addListener(self._handleOnvifChange)

        # Add default "Custom" choice into the profiles list.
        self._onvifUriCtrl.Append(_kOnvifCustomUri, _kOnvifCustomUri)
        self._onvifUriCtrl.SetSelection(0)


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        This happens when we switch _to_ this page...

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Fake-up an ONVIF update to update our profile choices.
        self._handleOnvifChange(self.wizard.onvifDataModel)

        # Set the default selection.
        self._onvifUriCtrl.SetSelection(0)

        # Set the audio control.
        self._audioCtrl.SetValue(
            self.wizard.camExtras.get('recordAudio', kDefaultRecordAudio))

        # The idea here is that we want to check if our currently saved
        # cameraUri is in the list of available stream uri's. If it's there,
        # then we set our selection to that position. If it's not there,
        # then our cameraUri is either custom-made, or the device is not
        # reachable. Unfortunately, because IP address can change, our
        # comparisons are made based off of the scheme and paths of the
        # URI's; so it's a tad messy.
        cameraUri = self.wizard.cameraUri
        if cameraUri and isOnvifUrl(cameraUri):

            result = urlparse.urlsplit(cameraUri)
            pathPart = "%s%s%s" % (result.path.strip('/'), result.query,
                                   result.fragment)
            self._selectedStreamUri = cameraUri

            if pathPart:
                # We have a path part, which means the cameraUri is custom-made
                # or it's a streamUri from the camera's list. Set the selection
                # to "Custom", unless we can find a better match from the list.
                self._onvifUriCtrl.SetSelection(self._onvifUriCtrl.GetCount()-1)

                for selection in xrange(0, self._onvifUriCtrl.GetCount()):

                    streamUri = self._onvifUriCtrl.GetClientData(selection)

                    if _compareUris(cameraUri, streamUri):
                        # We found a match in the list, set this selection.
                        self._onvifUriCtrl.SetSelection(selection)
                        self._selectedStreamUri = streamUri
                        break

        self._forceTcpCtrl.SetValue(
                self.wizard.camExtras.get('forceTCP', True))

        # Fake-up a profile selection change to initialize controls.
        self.OnOnvifProfileChange()

        self._onvifUriCtrl.SetFocus()


    ###########################################################
    def OnChanging(self, event):
        """Handle a page changing event.

        This is when we change _from_ this page.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        isForward = event.GetDirection()
        if event.GetPage() != self:
            # Only care if we're leaving ourselves...
            event.Skip()
            return

        if isForward:
            ignoreErrors = 'none'
        else:
            # Want to ignore most errors when going backward...
            ignoreErrors = 'most'

        errorMessage, cameraUri = \
            self._getSettingsFromUi(ignoreErrors)

        if errorMessage:
            wx.MessageBox(errorMessage, "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            event.Veto()
        else:
            # Only update if we have something good...
            if cameraUri:
                self.wizard.cameraUri = cameraUri
                self.wizard.camExtras['recordSize'] = \
                    _getHighestResolutionByLicense(self.wizard)
                self.wizard.camExtras['recordAudio'] = self._audioCtrl.GetValue()
                self.wizard.camExtras['forceTCP'] = self._forceTcpCtrl.GetValue()


    ###########################################################
    def OnUrlRelatedUiChange(self, event):
        """Handle generic UI changes that could change the URL we show.

        @param  event  The event.
        """
        isRTSP = 'rtsp' == self._schemeCtrl.GetStringSelection()
        self._forceTcpCtrl.Show(isRTSP)

        self._updateUrl()
        event.Skip()


    ###########################################################
    def OnOnvifProfileChange(self, event=None):
        """This gets called whenever the user selects a different profile name,
        or "Custom" from the profiles list. We just update the UI, and possibly
        change the UI if "Custom" is selected.

        :param event: The event.
        """
        selection = self._onvifUriCtrl.GetSelection()

        if selection is wx.NOT_FOUND:
            return

        # If the user has selected the "Custom" option, show all controls,
        # and populate the UI based off of the currently selected profile.
        # Else, we hide all of the URL controls, and keep track of the new
        # profile name choice (we keep track of the stream uri, though, not
        # the profile name).
        profileName = self._onvifUriCtrl.GetStringSelection()
        if profileName == _kOnvifCustomUri:
            showUrlControls = True
            otherOptionsRow = 5
            streamUri = self._selectedStreamUri
        else:
            showUrlControls = False
            otherOptionsRow = 2
            streamUri = self._onvifUriCtrl.GetClientData(selection)
            self._selectedStreamUri = streamUri

        # Throw stuff into sizers...
        controlSizer = self._controlSizer

        controlSizer.Clear()

        controlSizer.SetEmptyCellSize((0,0))

        controlSizer.Add(self._onvifUriLabel, pos=(1, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        controlSizer.Add(self._onvifUriCtrl, pos=(1, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL)
        #controlSizer.AddGrowableCol(1)

        if showUrlControls:

            controlSizer.Add(self._schemeLabel, pos=(2, 0),
                             flag=wx.ALIGN_CENTER_VERTICAL)
            protoPortSizer = wx.BoxSizer(wx.HORIZONTAL)
            protoPortSizer.Add(self._schemeCtrl, 0, wx.ALIGN_CENTER_VERTICAL |
                               wx.RIGHT, _kPaddingSize)
            protoPortSizer.AddStretchSpacer(1)
            protoPortSizer.Add(self._otherPortLabel, 0, wx.ALIGN_CENTER_VERTICAL |
                               wx.LEFT | wx.RIGHT, _kPaddingSize)
            protoPortSizer.Add(self._otherPortCtrl, 0, wx.ALIGN_CENTER_VERTICAL)
            controlSizer.Add(protoPortSizer, pos=(2, 1),
                             flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

            controlSizer.Add(self._streamPathLabel, pos=(3, 0),
                             flag=wx.ALIGN_CENTER_VERTICAL)
            controlSizer.Add(self._streamPathCtrl, pos=(3, 1),
                             flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

            controlSizer.Add(self._fullUrlLabel, pos=(4, 1),
                             flag=wx.EXPAND)

        controlSizer.Add(self._advancedLabel, pos=(otherOptionsRow, 0),
                         flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP,
                         border=2*_kPaddingSize)
        controlSizer.Add(self._audioCtrl, pos=(otherOptionsRow, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP,
                         border=2*_kPaddingSize)
        otherOptionsRow += 1

        controlSizer.Add(self._forceTcpCtrl, pos=(otherOptionsRow, 1),
                         flag=wx.ALIGN_CENTER_VERTICAL |
                         wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        for urlControl in (self._schemeLabel, self._schemeCtrl,
                           self._streamPathLabel, self._streamPathCtrl,
                           self._otherPortLabel, self._otherPortCtrl,
                           self._fullUrlLabel):
            urlControl.Show(showUrlControls)

        # Split the URI...
        splitResult = urlparse.urlsplit(streamUri)

        port = ""
        try:
            if splitResult.port is not None:
                port = str(splitResult.port)
        except ValueError:
            # Could happen if the URL somehow has a non-integral port...
            pass

        scheme = splitResult.scheme

        pathPart = _getUrlPathPart(splitResult)

        # Expect pathPart to have a '/' at the start, but don't want to show
        # that to user (unless that's the whole path)...
        if pathPart.startswith('/') and (pathPart != '/'):
            pathPart = pathPart[len('/'):]

        self._schemeCtrl.SetStringSelection(scheme)
        self._otherPortCtrl.SetValue(port)
        self._streamPathCtrl.SetValue(ensureUnicode(pathPart))

        # We have to call Layout here so that the controls will be properly
        # re-arranged. We must also call refresh so that the text in the
        # controls will show their correct values if they've been changed
        # just now.
        self.Layout()
        self.Refresh()

        # Updating the URL *MUST* come after the Layout and Refresh methods
        # because it truncates its text based off of its client size. If you
        # update the URL BEFORE the Layout and Refresh methods, the text box
        # will think it has a size that is much too small, and it will only
        # display "..." to the user.
        self._updateUrl()


    ###########################################################
    def OnRightClick(self, event):
        """Handle a request to dump UPNP and ONVIF info to the log.

        @param  event  The event.  Ignored.
        """
        if wx.GetKeyState(wx.WXK_SHIFT) and wx.GetKeyState(wx.WXK_ALT):
            onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()

            devId = self.wizard.onvifSettings.get('uuid')
            device = onvifDeviceDict.get(devId)
            print str(device)

            wx.MessageBox("ONVIF device data has been dumped to the log.",
                          kAppName, wx.OK | wx.ICON_INFORMATION,
                          self.GetTopLevelParent())


    ###########################################################
    def _getSettingsFromUi(self, ignoreErrors):
        """Get the current settings out of the UI.

        @param  ignoreErrors  Can be 'all', 'none', 'most'.  For 'all', all
                              errors will be ignored.  For 'none', none will.
                              For 'most', we'll ignore all but the most dire of
                              errors.
        @return errorMessage  If non-None, contains the error message.
                              If None, there were no errors, or the errors were
                              ignored.
        @return cameraUri     The camera URI.  None if we couldn't figure out.
                              Will always be utf-8.
        """
        assert ignoreErrors in ('all', 'none', 'most')

        # Get simple things out of UI...
        streamUriIndex = self._onvifUriCtrl.GetSelection()

        if (streamUriIndex == wx.NOT_FOUND) and (ignoreErrors == 'none'):
            return ("You must make a selection.", None)

        # Init camera URI...
        cameraUri = None

        # Init device...
        device = None

        # Get the device; will fail if the device disappared...
        try:
            devId = extractUuidFromOnvifUrl(self.wizard.cameraUri)
            device = self.wizard.onvifDataModel.getOnvifDeviceDict().get(devId)
        except:
            # Expecting this if it's not ONVIF.
            pass

        if device is None:
            if ignoreErrors == 'none':
                return ("This device can no longer be found on the "
                        "network.  It may be rebooting.", None)
            return (None, cameraUri)

        # Split the URI...
        splitResult = urlparse.urlsplit(self.wizard.cameraUri)

        # Get the hostname...
        hostname = splitResult.hostname
        if not hostname:
            hostname = ""

        # Parse out any current username and password...
        username = splitResult.username
        if not username:
            username = ""
        else:
            username = urllib.unquote(username)
        password = splitResult.password
        if not password:
            password = ""
        else:
            password = urllib.unquote(password)

        portStr = self._otherPortCtrl.GetValue().strip()
        try:
            portStr = int(portStr)
            portStr = str(portStr)
        except ValueError:
            # Any non-integer string other than the blank string is an error
            if portStr and (ignoreErrors == 'none'):
                return("Please enter a valid port number.",
                       None)
            portStr = ""

        if portStr:
            portStr = ":" + portStr

        pathPart = self._streamPathCtrl.GetValue().strip()

        scheme = "%s://" % (self._schemeCtrl.GetStringSelection())

        # Don't allow them to just keep clicking "Next" without thinking.
        # We don't know of any good reason to have a blank path part with
        # 'http', so we'll prevent it.  If a user really wants it, they can
        # enter '/'...
        isSchemeChosen = (scheme == 'http://') or (scheme == 'https://') or \
                         (scheme == 'rtsp://')
        if (not pathPart) and (isSchemeChosen) and (ignoreErrors == 'none'):
            return ("You must enter the path to the video stream.",
                    None)

        # Add a '/' to the start if the user didn't put one (we don't
        # expect them to, but don't add an extra one if they did)...
        if pathPart and (not pathPart.startswith('/')):
            pathPart = '/' + pathPart

        # String everything together...
        streamUri = "%s%s%s%s" % (scheme, hostname, portStr, pathPart)

        cameraUri = constructOnvifUrl(device.uuid, username, password, streamUri)

        return (None, cameraUri)


    ###########################################################
    def _updateUrl(self):
        """Update the URL link.

        This is called whenever the ONVIF dicts change.
        """
        _, url = self._getSettingsFromUi('all')

        if url is not None:

            if isOnvifUrl(url):
                deviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()
                url = realizeOnvifUrl(deviceDict, url)

        if url:
            url = self._stripUsernameAndPassword(url)

            # It seems important to escape out the ampersand.  Weird.
            url = url.replace('&', '&&')

            self._fullUrlLabel.SetLabel(ensureUnicode(url))
            truncateStaticText(self._fullUrlLabel)
        else:
            # The only reason we should fail when ignoring all errors is if
            # the device isn't available...
            self._fullUrlLabel.SetLabel("<device not available>")


    ###########################################################
    def _handleOnvifChange(self, onvifDataModel):
        """Handle a change in the ONVIF dictionary.

        We don't change much, just need to update the profile selection list.

        @param  onvifDataModel  The ONVIF data model.
        """
        assert onvifDataModel == self.wizard.onvifDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        devUuid, device = None, None
        if isOnvifUrl(self.wizard.cameraUri):
            devUuid = extractUuidFromOnvifUrl(self.wizard.cameraUri)
            device = self.wizard.onvifDataModel.getOnvifDeviceDict().get(devUuid)

        # If the device doesn't exist, clear the profiles list control, but
        # add the "Custom" option.
        if device is None:
            self._onvifUriCtrl.Freeze()
            try:
                self._onvifUriCtrl.Clear()
                self._onvifUriCtrl.Append(_kOnvifCustomUri, _kOnvifCustomUri)
            finally:
                self._onvifUriCtrl.Thaw()
            return

        # Make a sorted list of tuples:
        # (profile0: h264, 800x600 (rtsp://blah/foo.bar), rtsp://blah/foo.bar)
        # from ((profileName, profileToken, encoding, resolution),
        #       (streamUri, transportType))
        streamUris = [("%s: %s, %sx%s (%s)" %
                       (profileName, encoding, resolution[0], resolution[1],
                        self._stripUsernameAndPassword(streamUri)),
                       streamUri)
                      for ((profileName, profileToken, encoding, resolution),
                           (streamUri, transportType))
                      in device.streamUris.iteritems()
        ]
        streamUris.sort()
        # Make sure we add the "Custom" option. We add "Custom" as client data
        # so that if we ever use GetClientData, we don't get a surprise
        # exception. If the client data is None, it can raise an exception.
        streamUris.append((_kOnvifCustomUri, _kOnvifCustomUri))

        # Freeze, just so user doesn't see UI changing...  TODO: Needed?
        self._onvifUriCtrl.Freeze()
        try:
            # First get current selection...
            currSelection = self._onvifUriCtrl.GetSelection()
            if (currSelection is wx.NOT_FOUND):
                currClientData = _kOnvifCustomUri
            else:
                currClientData = self._onvifUriCtrl.GetClientData(currSelection)

            # Then, start out with a blank choice...
            self._onvifUriCtrl.Clear()

            # Now fill the control. We'll look to see which should be selected
            # by comparing to selection; that way we keep selection good even if
            # user unplugs and re-plugs camera...
            selection = wx.NOT_FOUND
            for (profileName, streamUri) in streamUris:
                if currClientData == streamUri:
                    selection = self._onvifUriCtrl.GetCount()
                self._onvifUriCtrl.Append(profileName, streamUri)

            # Only set the selection if it's valid.
            if selection is not wx.NOT_FOUND:
                self._onvifUriCtrl.SetSelection(selection)

        finally:
            self._onvifUriCtrl.Thaw()


    ###########################################################
    def _stripUsernameAndPassword(self, url):
        """Strips username and password from the given url.

        @param   url     URL that needs username and password stripped.
        @return  result  URL after username and password have been stripped.
        """
        if url:
            # Strip out username and password from the URL...
            scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
            netloc = netloc.split('@', 1)[-1]
            url = urlparse.urlunsplit((scheme, netloc, path, query, fragment))
        return url


##############################################################################
def _findGenericCamTypes(modelName):
    """Find the generic camera types for the given UPNP model name.

    @param  modelName       The model name
    @return genericDrivers  The names of the generic camera type (a list)
    """
    genericDrivers = []
    for thisModelRe, thisModelName in kUpnpGenericList:
        mo = re.match(thisModelRe, modelName)
        if mo:
            genericDrivers.append(thisModelName)

    return genericDrivers


##############################################################################
class _BadUpnpScreen(_BasePage):
    """We get here if we detect a misconfigured or broken UPNP device."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _BadUpnpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_BadUpnpScreen, self).__init__(
            wizard, "Unable to communicate with device"
        )

        textA = wx.StaticText(
            self, -1, u"We detected this device on the network, but were "
            u"unable to communicate with it.  This could be for a number of "
            u"reasons, including:\n"
            u"\n"
            u"\u2022 The device may be on a different IP subnet than your "
                    u"computer.  You may need to temporarily change the IP "
                    u"address of your computer to talk to the device and "
                    u"reconfigure it.\n"
            u"\n"
            u"\u2022 The device may be in a bad state.  Try unplugging the "
                    u"device and plugging it back in.\n"
            u"\n"
            u"\n"
            u"Once this device is communicating properly, return to the "
            u"previous page and select it again.",
            style=wx.ST_NO_AUTORESIZE
        )
        textA.SetMinSize((_kTextWrap, -1))

        makeFontDefault(textA)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 1, wx.EXPAND | wx.TOP, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)


##############################################################################
class _ManualSettingsScreen(_BasePage):
    """A screen for editing camera settings."""
    def __init__(self, wizard):
        """The initializer for _ManualSettingsScreen.

        @param  wizard  The CameraSetupWizard.
        """
        super(_ManualSettingsScreen, self).__init__(
            wizard, "Enter settings to allow the %s application to find your "
            "camera." % kAppName
        )

        # Create the controls.
        self._typeLabel = wx.StaticText(self, -1, "Camera type:")
        self._typeCtrl = wx.Choice(self, -1, size=(214, -1))
        makeFontDefault(self._typeLabel, self._typeCtrl)
        self._ipHelpA = wx.StaticText(self, -1, " \n ",
                                      style=wx.ST_NO_AUTORESIZE)
        self._ipHelpA.SetMinSize((_kTextWrap, -1))

        self._schemeLabel = wx.StaticText(self, -1, "Protocol:")
        self._schemeCtrl = wx.Choice(self, -1, choices=["http", "rtsp"])
        self._schemeCtrl.SetSelection(1)

        self._ipLabel = wx.StaticText(self, -1, "IP address:")
        self._ipCtrl = wx.TextCtrl(self, -1, size=(150, -1))

        self._httpPortLabel = wx.StaticText(self, -1, "HTTP port (optional):")
        self._httpPortCtrl = wx.TextCtrl(self, -1, size=(40, -1))
        self._httpPortCtrl.SetMaxLength(5)

        self._rtspPortLabel = wx.StaticText(self, -1, "RTSP port (optional):")
        self._rtspPortCtrl = wx.TextCtrl(self, -1, size=(40, -1))
        self._rtspPortCtrl.SetMaxLength(5)

        self._streamPathLabel = wx.StaticText(self, -1, "Stream path:")
        self._streamPathCtrl = wx.TextCtrl(self, -1, size=(320, -1))

        self._fullUrlLabel = wx.StaticText(self, -1, " ",
                                           style=wx.ST_NO_AUTORESIZE)

        self._userLabel = wx.StaticText(self, -1, "User name:")
        self._userCtrl = wx.TextCtrl(self, -1, size=(200, -1))

        self._passLabel = wx.StaticText(self, -1, "Password:")
        self._passCtrl = wx.TextCtrl(self, -1, size=(200, -1),
                                     style=wx.TE_PASSWORD)
        self._passVerifyLabel = wx.StaticText(self, -1, "Verify password:")
        self._passVerifyCtrl = wx.TextCtrl(self, -1, size=(200, -1),
                                           style=wx.TE_PASSWORD)

        self._advancedLabel = wx.StaticText(self, -1, _kAdvancedLabel,
                style=wx.ST_NO_AUTORESIZE)
        self._audioCtrl = wx.CheckBox(self, -1, _kAudioCtrlLabel)
        self._forceTcpCtrl = wx.CheckBox(self, -1, _kForceTCPLabel)

        self._nonStaticControls = [self._schemeLabel, self._schemeCtrl,
                                   self._ipLabel, self._ipCtrl,
                                   self._httpPortLabel, self._httpPortCtrl,
                                   self._rtspPortLabel, self._rtspPortCtrl,
                                   self._userLabel, self._userCtrl,
                                   self._passLabel, self._passCtrl,
                                   self._passVerifyLabel, self._passVerifyCtrl,
                                   self._streamPathLabel, self._streamPathCtrl,
                                   self._fullUrlLabel,
                                   self._ipHelpA,
                                   self._advancedLabel, self._audioCtrl,
                                   self._forceTcpCtrl]
        self._genericControls = [self._ipLabel, self._ipCtrl,
                                 self._httpPortLabel, self._httpPortCtrl,
                                 self._rtspPortLabel, self._rtspPortCtrl,
                                 self._schemeLabel, self._schemeCtrl,
                                 self._streamPathLabel, self._streamPathCtrl,
                                 self._fullUrlLabel,
                                 self._userLabel, self._userCtrl,
                                 self._passLabel, self._passCtrl,
                                 self._passVerifyLabel, self._passVerifyCtrl,
                                 self._advancedLabel, self._audioCtrl,
                                 self._forceTcpCtrl]
        self._ipCamControls = [self._ipLabel, self._ipCtrl,
                               self._httpPortLabel, self._httpPortCtrl,
                               self._rtspPortLabel, self._rtspPortCtrl,
                               self._userLabel, self._userCtrl,
                               self._passLabel, self._passCtrl,
                               self._passVerifyLabel, self._passVerifyCtrl,
                               self._ipHelpA,
                               self._advancedLabel, self._audioCtrl,
                               self._forceTcpCtrl]

        for ctrl in self._nonStaticControls:
            makeFontDefault(ctrl)

        # Add everything to sizers.
        self._gridBagSizer = wx.GridBagSizer(_kPaddingSize, 3*_kPaddingSize)
        self._gridBagSizer.SetEmptyCellSize((0,0))

        self.sizer.AddSpacer(2*_kPaddingSize)
        self.sizer.Add(self._gridBagSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)
        self.sizer.AddSpacer(_kPaddingSize)

        self._typeCtrl.SetStringSelection(_kLargestPageType)
        self.OnCameraTypeChange()

        # Bind to events.
        self._typeCtrl.Bind(wx.EVT_CHOICE, self.OnCameraTypeChange)

        self._schemeCtrl.Bind(wx.EVT_CHOICE, self.OnSchemeChange)

        self._ipCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)
        self._streamPathCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)
        self._httpPortCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)
        self._rtspPortCtrl.Bind(wx.EVT_TEXT, self.OnUrlRelatedUiChange)

        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)



    ###########################################################
    def OnUrlRelatedUiChange(self, event):
        """Handle generic UI changes that could change the URL we show.

        @param  event  The event.
        """
        self._updateUrl()
        event.Skip()


    ###########################################################
    def OnSchemeChange(self, event):
        """Handle a change in the scheme.

        Can only happen when we're using the "other" IP camera.
        """
        self._showProperPortCtrls()
        self._updateUrl()
        event.Skip()


    ###########################################################
    def OnCameraTypeChange(self, event=None):
        """Update the displayed controls after a type selection.

        @param  event  The choice event (ignored).
        """
        for ctrl in self._nonStaticControls:
            ctrl.Hide()

        showList = []
        typeStr = self._typeCtrl.GetStringSelection()

        self._gridBagSizer.Clear()
        self._gridBagSizer.Add(self._typeLabel, (0,0), (1,1),
                         wx.ALIGN_CENTER_VERTICAL)
        self._gridBagSizer.Add(self._typeCtrl, (0,1), (1,1),
                         wx.ALIGN_CENTER_VERTICAL)
        #self._gridBagSizer.AddGrowableCol(1)

        portLabelSizer = OverlapSizer(True)
        portLabelSizer.Add(self._httpPortLabel)
        portLabelSizer.Add(self._rtspPortLabel)
        portCtrlSizer = OverlapSizer(True)
        portCtrlSizer.Add(self._httpPortCtrl)
        portCtrlSizer.Add(self._rtspPortCtrl)

        ipAndPortSizer = wx.BoxSizer(wx.HORIZONTAL)
        ipAndPortSizer.Add(self._ipCtrl, 1, wx.ALIGN_CENTER_VERTICAL)
        ipAndPortSizer.Add(portLabelSizer, 0, wx.ALIGN_CENTER_VERTICAL |
                           wx.LEFT, _kPaddingSize)
        ipAndPortSizer.Add(portCtrlSizer, 0, wx.ALIGN_CENTER_VERTICAL |
                           wx.LEFT, _kPaddingSize)

        if typeStr == "Other IP camera":
            showList = self._genericControls

            self._gridBagSizer.Add(self._schemeLabel, (1,0), (1,1),
                                   wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._schemeCtrl, (1,1), (1,1),
                                   wx.ALIGN_CENTER_VERTICAL)

            self._gridBagSizer.Add(self._ipLabel, (2,0), (1,1),
                         wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(ipAndPortSizer, (2,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

            self._gridBagSizer.Add(self._streamPathLabel, (3,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._streamPathCtrl, (3,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

            self._gridBagSizer.Add(self._fullUrlLabel, (4,1), (1,1),
                                  wx.EXPAND | wx.BOTTOM, border=2*_kPaddingSize)

            self._gridBagSizer.Add(self._userLabel, (5,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._userCtrl, (5,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._passLabel, (6,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._passCtrl, (6,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._passVerifyLabel, (7,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._passVerifyCtrl, (7,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)

            self._gridBagSizer.Add(self._advancedLabel, (8,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.TOP,
                             border=2*_kPaddingSize)
            self._gridBagSizer.Add(self._audioCtrl, (8,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.TOP,
                             border=2*_kPaddingSize)

            self._gridBagSizer.Add(self._forceTcpCtrl, (9,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND |
                             wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        else:
            # Reset "IP Help A" with a description...
            ipHelpALabel = "Enter the information you used to setup " \
                           "your IP camera:"

            ipHelpALabel = _getCameraDescription(typeStr) + "\n\n\n" + \
                           ipHelpALabel
            self._ipHelpA.SetLabel(ipHelpALabel)
            self._ipHelpA.Wrap(_kTextWrap)

            showList = self._ipCamControls

            self._gridBagSizer.Add(self._ipHelpA, (1,0), (1,2),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

            self._gridBagSizer.Add(self._ipLabel, (2,0), (1,1),
                         wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(ipAndPortSizer, (2,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

            self._gridBagSizer.Add(self._userLabel, (3,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._userCtrl, (3,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._passLabel, (4,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._passCtrl, (4,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._passVerifyLabel, (5,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)
            self._gridBagSizer.Add(self._passVerifyCtrl, (5,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL)

            self._gridBagSizer.Add(self._advancedLabel, (6,0), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.TOP,
                             border=2*_kPaddingSize)
            self._gridBagSizer.Add(self._audioCtrl, (6,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.TOP,
                             border=2*_kPaddingSize)

            self._gridBagSizer.Add(self._forceTcpCtrl, (7,1), (1,1),
                             wx.ALIGN_CENTER_VERTICAL | wx.EXPAND |
                             wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        for ctrl in showList:
            ctrl.Show()

        # Show the right set of port controls
        self._showProperPortCtrls()

        # I hate layout.  ...but for some reason I have to do it twice (ick!)
        # here in order to make things work right in this particular case:
        # - Choose UPNP camera
        # - In UPNP screen, choose other
        # - Go back
        # - Choose manual
        # - Choose a non-other type
        self.Layout()
        self.Layout()
        self.Refresh()

        # Do this last, after the layout.  If we don't, we won't truncate to
        # the right size...
        self._updateUrl()


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        This is when we change _to_ this page.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Clear out everything by default, just in case we forget something...
        for ctrl in [self._httpPortCtrl, self._rtspPortCtrl,
                     self._userCtrl, self._passCtrl, self._passVerifyCtrl,
                     self._streamPathCtrl, self._ipCtrl]:
            ctrl.SetValue('')

        # Split the URI...  (TODO: don't think the 'http' is really needed)
        splitResult = urlparse.urlsplit(self.wizard.cameraUri, 'rtsp')

        # Parse out any current username and password, and pathPart...
        username = splitResult.username
        if not username:
            username = ""
        else:
            username = urllib.unquote(username)
        password = splitResult.password
        if not password:
            password = ""
        else:
            password = urllib.unquote(password)

        port = ""
        try:
            if splitResult.port is not None:
                port = str(splitResult.port)
        except ValueError:
            # Could happen if the URL somehow has a non-integral port...
            pass

        scheme = splitResult.scheme

        # Get the resolution...
        resolution = tuple(self.wizard.camExtras.get('recordSize',
                                                     kDefaultRecordSize))

        # Get the record audio setting.
        self._audioCtrl.SetValue(
            self.wizard.camExtras.get('recordAudio', kDefaultRecordAudio))

        # Get the tcp override...
        forceTCP = self.wizard.camExtras.get('forceTCP', True)

        # Get the choices...
        camManuf = self.wizard.cameraManufacturer
        listChoices, selection = self._getCameraChoicesForManuf(camManuf)

        # Pre-select if our current type is in the choices...
        if self.wizard.cameraType in listChoices:
            selection = listChoices.index(self.wizard.cameraType)

        if splitResult.hostname:
            self._ipCtrl.SetValue(ensureUnicode(splitResult.hostname))

        pathPart = _getUrlPathPart(splitResult)

        # Expect pathPart to have a '/' at the start, but don't want to show
        # that to user (unless that's the whole path)...
        if pathPart.startswith('/') and (pathPart != '/'):
            pathPart = pathPart[len('/'):]

        # Put in controls...
        self._typeCtrl.SetItems(listChoices)
        self._typeCtrl.SetSelection(selection)

        self._schemeCtrl.SetStringSelection(scheme)
        if scheme == 'rtsp':
            self._rtspPortCtrl.SetValue(str(port))
        else:
            assert scheme == 'http'
            self._httpPortCtrl.SetValue(str(port))
        self._streamPathCtrl.SetValue(ensureUnicode(pathPart))
        self._userCtrl.SetValue(ensureUnicode(username))
        self._passCtrl.SetValue(ensureUnicode(password))
        self._passVerifyCtrl.SetValue(ensureUnicode(password))

        self._forceTcpCtrl.SetValue(forceTCP)

        self.OnCameraTypeChange()

        # Set focus on camera type...
        self._typeCtrl.SetFocus()


    ###########################################################
    def _getSettingsFromUi(self, ignoreErrors):
        """Get the current settings out of the UI.

        @param  ignoreErrors  Can be 'all', 'none', 'most'.  For 'all', no
                              errors will be ignored.  For 'none', none will.
                              For 'most', we'll ignore all but the most dire of
                              errors.
        @return errorMessage  If non-None, contains the error message.
                              If None, there were no errors, or the errors were
                              ignored.
        @return cameraType    The camera type.  None if we couldn't figure out.
        @return cameraUri     The camera URI.  None if we couldn't figure out.
                              Will always be utf-8.
        """
        assert ignoreErrors in ('all', 'none', 'most')

        # Get simple things out of UI...
        cameraType = self._typeCtrl.GetStringSelection()

        # Get settings out of UI...
        username = ensureUtf8(self._userCtrl.GetValue().strip())
        username = urllib.quote(username, "")
        password = ensureUtf8(self._passCtrl.GetValue().strip())
        password = urllib.quote(password, "")
        scheme   = "%s://" % ensureUtf8(self._getStreamType())
        hostname = ensureUtf8(self._ipCtrl.GetValue().strip())
        pathPart = ensureUtf8(self._streamPathCtrl.GetValue().strip())
        if scheme == 'rtsp://':
            portStr = self._rtspPortCtrl.GetValue()
        else:
            assert scheme == 'http://'
            portStr = self._httpPortCtrl.GetValue()

        if (ignoreErrors != 'all')                                       and \
           (self._passCtrl.GetValue() != self._passVerifyCtrl.GetValue())   :
            self._passVerifyCtrl.SetValue('')
            self._passVerifyCtrl.SetFocus()
            return (_kPasswordsMustMatchStr, None, None)

        if ignoreErrors == 'none':
            if not hostname:
                self._ipCtrl.SetFocus()
                return ("The IP address field cannot be blank.",
                        None, None)
            elif hostname.lower().startswith('http://'):
                self._ipCtrl.SetFocus()
                return ("The IP address field must not start with \"http://\".",
                        None, None)
            elif hostname.lower().startswith('rtsp://'):
                self._ipCtrl.SetFocus()
                return ("The IP address field must not start with \"rtsp://\".",
                        None, None)
            elif re.search("[^A-Za-z0-9\.\-]", hostname):
                self._ipCtrl.SetFocus()
                return ("The IP address field must contain a valid IP address "
                        "or host name.",
                        None, None)
        elif re.search("[^A-Za-z0-9\.\-]", hostname) and \
             (ignoreErrors == 'most'):
            # Handles hitting 'back' and not having junk in the hostname.
            hostname = ""

        if (ignoreErrors != 'none') or (username and password):
            userPassStr = username + ':' + password + '@'
        elif username:
            userPassStr = username + '@'
        elif password and (ignoreErrors == 'none'):
            return ("A username is required if a password is used.",
                    None, None)
        else:
            userPassStr = ''

        try:
            port = int(portStr)
        except ValueError:
            if portStr and (ignoreErrors == 'none'):
                return ("The port must be numeric characters only.",
                        None, None)
            portStr = ""
        else:
            portStr = ":%d" % port

        if cameraType and (cameraType != "Other IP camera"):
            driverScheme, driverPathPart, driverDefaultPort = _getStreamPath(
                cameraType, _getHighestResolutionByLicense(self.wizard)
            )
            assert scheme == driverScheme, \
                   "Probably bug in _getStreamType()"

            if (not portStr) and (driverDefaultPort is not None):
                portStr = ":%d" % driverDefaultPort

            pathPart = driverPathPart

        # Don't allow them to just keep clicking "Next" without thinking.
        # We don't know of any good reason to have a blank path part with
        # 'http', so we'll prevent it.  If a user really wants it, they can
        # enter '/'...
        if (not pathPart) and (scheme == 'http://') and \
           (ignoreErrors == 'none'):
            return ("You must enter the path to the video stream.",
                    None, None)

        # Add a '/' to the start if the user didn't put one (we don't
        # expect them to, but don't add an extra one if they did)...
        if pathPart and (not pathPart.startswith('/')):
            pathPart = '/' + pathPart

        # Make a URI by just concatenating all of the pices...
        cameraUri = "%s%s%s%s%s" % (scheme, userPassStr, hostname,
                                    portStr, pathPart)

        return None, cameraType, cameraUri


    ###########################################################
    def OnChanging(self, event):
        """Handle a page changing event.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        isForward = event.GetDirection()
        if event.GetPage() != self:
            # Only care if we're leaving ourselves...
            event.Skip()
            return

        if isForward:
            ignoreErrors = 'none'
        else:
            # Want to ignore most errors when going backward...
            ignoreErrors = 'most'

        errorMessage, cameraType, cameraUri = \
            self._getSettingsFromUi(ignoreErrors)

        if errorMessage:
            wx.MessageBox(errorMessage, "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
            event.Veto()
        else:
            # Only update if we have something good...
            if (cameraType and cameraUri):
                self.wizard.cameraType = cameraType
                self.wizard.cameraUri = cameraUri
                self.wizard.camExtras['recordSize'] = \
                    _getHighestResolutionByLicense(self.wizard)
                self.wizard.camExtras['recordAudio'] = self._audioCtrl.GetValue()
                self.wizard.camExtras['forceTCP'] = self._forceTcpCtrl.GetValue()


    ###########################################################
    def _updateUrl(self):
        """Update the URL link.

        This is called whenever the UPNP dict changes.
        """
        _, _, url = self._getSettingsFromUi('all')

        assert url, "Should always get a valid URL when ignoring all errors."
        if url:
            # Strip out username and password from the URL...
            scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
            netloc = netloc.split('@', 1)[-1]
            url = urlparse.urlunsplit((scheme, netloc, path, query, fragment))

            # It seems important to escape out the ampersand.  Weird.
            url = url.replace('&', '&&')

            self._fullUrlLabel.SetLabel(ensureUnicode(url))
            truncateStaticText(self._fullUrlLabel)
        else:
            # Don't expect to ever get here, but if we do, we'll put a blank
            # label in...
            self._fullUrlLabel.SetLabel(" ")


    ###########################################################
    def _getStreamType(self):
        """Return the type of stream selected in the UI.

        @return streamType  Either "http" or "rtsp".
        """
        camType = self._typeCtrl.GetStringSelection()
        if camType in kTypeToStreamPath:
            return kTypeToStreamPath[camType][0].split(':')[0]
        else:
            assert (camType == "") or (camType == kOtherIpCamType), \
                   "Unexpected camType: %s" % camType
            return self._schemeCtrl.GetStringSelection()


    ###########################################################
    def _showProperPortCtrls(self):
        """Show the proper port controls depending on other UI.

        If other UI indicates that the user wants RTSP, show the RTSP port
        controls.  Otherwise, show the HTTP port controls.
        """
        streamType = self._getStreamType()

        showHttpControls = (streamType == 'http')
        showRtspControls = (streamType == 'rtsp')
        assert showHttpControls ^ showRtspControls, \
               "Unexpected stream type: %s" % streamType

        for ctrl in (self._rtspPortLabel, self._rtspPortCtrl,
                     self._forceTcpCtrl):
            ctrl.Show(showRtspControls)
        for ctrl in (self._httpPortLabel, self._httpPortCtrl):
            ctrl.Show(showHttpControls)


    ###########################################################
    def _getCameraChoicesForManuf(self, camManuf):
        """Get the list of camera choices for the given manufacturer.

        @param  camManuf          A manufacturer to limit to.
        @return listChoices       A list of choices.
        @return defaultSelection  The default selection for listChoices.
        """
        if camManuf == kOtherCameraManufacturer:
            # Other / unknown means to show all...
            availTypes = kIpCameraTypes
        else:
            # Just show ones from this manufacturer, plus other...
            availTypes = [thisCamType for thisCamType in kIpCameraTypes if
                          kTypeToManufacturer.get(thisCamType) == camManuf]
            availTypes.append(kOtherIpCamType)

        # If other manufacturer was chosen, choose other camera; else
        # pick the first one (arbitrarily)...
        if camManuf == kOtherCameraManufacturer:
            defaultSelection = len(availTypes) - 1
            assert availTypes[defaultSelection] == kOtherIpCamType, \
                   "Assumed other IP camera type was last"
        else:
            defaultSelection = 0

        return availTypes, defaultSelection


##############################################################################
class _DiscoverHelpScreen(_BasePage):
    """A screen telling the user to tips for finding their camera."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _DiscoverHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_DiscoverHelpScreen, self).__init__(
            wizard, "%s could not find your camera" % kAppName
        )

        if _isOemVersion:
            textA = wx.StaticText(self, -1,
                u"\u2022 Try unplugging and plugging in your camera, or "
                u"disconnecting and reconnecting your computer from your "
                u"network, then click Back.\n"
                u"\n"
                u"\u2022 Check that your camera's \"UPnP\" feature is enabled. "
                u"This is necessary for it to be seen in the list.\n"
                u"\n"
                u"\u2022 Check if your network setup is preventing your PC "
                u"from seeing your camera.\n"
                u"\n"
                u"\u2022 Use your router to find the IP address.  Then click "
                u"Next to enter this information in the next screen.",
                style=wx.ST_NO_AUTORESIZE
            )
        else:
            textA = wx.StaticText(self, -1,
                u"\u2022 Try unplugging and plugging in your camera, or "
                u"disconnecting and reconnecting your computer from your "
                u"network, then click Back.\n"
                u"\n"
                u"\u2022 Check if your camera supports \"UPnP\" and has the "
                u"feature enabled.  This is necessary for it to be seen in the "
                u"list.\n"
                u"\n"
                u"\u2022 Check if your network setup is preventing your PC "
                u"from seeing your camera.\n"
                u"\n"
                u"\u2022 Use the software that came with your camera, or your "
                u"router software, to find the IP address.  Then click Next to "
                u"enter this information in the next screen.",
                style=wx.ST_NO_AUTORESIZE
            )
        textA.SetMinSize((1, -1))
        makeFontDefault(textA)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 1, wx.EXPAND | wx.TOP, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)


##############################################################################
class _LogIntoCameraHelpScreen(_BasePage):
    """A screen telling the user to log in."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _LogIntoCameraHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_LogIntoCameraHelpScreen, self).__init__(
            wizard, "Set up your username and password"
        )

        textA = wx.StaticText(self, -1,
            "You now should log in to the configuration website of your "
            "camera to verify your username and password.  You may be asked to "
            "enter the default username and password listed in your camera's "
            "documentation (which you can change on the website), or to set a "
            "new password the first time you log in.\n"
            "\n"
            "IMPORTANT: write down the username and password, as you will need "
            "to enter it later in this process.\n"
            " ",
            style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textA)
        textA.Wrap(_kTextWrap)

        # Create the help text...
        textB = wx.StaticText(
            self, -1, "To go to the configuration web page, click ",
            style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textB)
        self._addressLink = wx.adv.HyperlinkCtrl(self, -1, "here", " ", style=wx.NO_BORDER | wx.adv.HL_CONTEXTMENU | wx.adv.HL_ALIGN_LEFT)
        makeFontDefault(self._addressLink)
        makeFontUnderlined(self._addressLink)
        setHyperlinkColors(self._addressLink)
        textC = wx.StaticText(
            self, -1, ".", style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textC)

        textD = wx.StaticText(self, -1,
            " \n"
            "Once you have logged in and have your username and password, "
            "click Next.",
            style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textD)
        textD.Wrap(_kTextWrap)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)

        linkSizer = wx.BoxSizer(wx.HORIZONTAL)
        linkSizer.Add(textB, 0, wx.ALIGN_CENTER_VERTICAL)
        linkSizer.Add(self._addressLink, 0, wx.ALIGN_CENTER_VERTICAL)
        linkSizer.Add(textC, 0, wx.ALIGN_CENTER_VERTICAL)
        innerSizer.Add(linkSizer, 0, wx.EXPAND)

        innerSizer.Add(textD, 0, wx.EXPAND)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        self.wizard.upnpDataModel.addListener(self._handleUpnpChange)
        self.wizard.onvifDataModel.addListener(self._handleOnvifChange)

        self._addressLink.Bind(wx.adv.EVT_HYPERLINK, self.OnAddressLink)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)


    ###########################################################
    def OnAddressLink(self, event):
        """Handle a click on the address link

        @param  event  The hyperlink event.
        """
        if self._addressLink.GetURL() == _kBadLink:
            wx.MessageBox("This device can no longer be found on the "
                          "network.  It may be rebooting.",
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
        else:
            event.Skip()


    ###########################################################
    def _handleUpnpChange(self, upnpDataModel):
        """Handle a change in the UPNP dictionary.

        We don't change much, but we might need to update our link.

        @param  upnpDataModel  The UPNP data model.
        """
        assert upnpDataModel == self.wizard.upnpDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        # Ignore changes if the stored device is a ONVIF URL.
        if isOnvifUrl(self.wizard.cameraUri):
            return

        # Get the USN for the device we stashed away...
        try:
            usn = extractUsnFromUpnpUrl(self.wizard.cameraUri)
        except ValueError:
            usn = None

        # Get the device...
        upnpDeviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()
        device = upnpDeviceDict.get(usn)

        if device is not None:
            # Get the presentation URL.
            presentationUrl, _ = device.getPresentationUrl()
            self._addressLink.SetURL(presentationUrl)
        else:
            self._addressLink.SetURL(_kBadLink)


    ###########################################################
    def _handleOnvifChange(self, onvifDataModel):
        """Handle a change in the ONVIF dictionary.

        We don't change much, but we might need to update our link.

        @param  onvifDataModel  The ONVIF data model.
        """
        assert onvifDataModel == self.wizard.onvifDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        # Ignore changes if the stored device is a UPnP URL.
        if isUpnpUrl(self.wizard.cameraUri):
            return

        # Get the UUID for the device we stashed away...
        try:
            uuid = extractUuidFromOnvifUrl(self.wizard.cameraUri)
        except ValueError:
            uuid = None

        # Get the device...
        onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()
        device = onvifDeviceDict.get(uuid)

        if device is not None:
            # Get the base URL.
            baseUrl = device.validOnvifIpAddrs[-1]
            self._addressLink.SetURL(baseUrl)
        else:
            self._addressLink.SetURL(_kBadLink)


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        This happens when we switch _to_ this page...  This is the place where
        we READ from the wizard and populate our UI.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Fake up a UPNP message, since we were ignoring while we weren't
        # active...
        self._handleUpnpChange(self.wizard.upnpDataModel)
        self._handleOnvifChange(self.wizard.onvifDataModel)


##############################################################################
class _OfferWifiHelpScreen(_BasePage):
    """A screen asking the user if they are using WiFi."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _OfferWifiHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_OfferWifiHelpScreen, self).__init__(
            wizard, "Wired or wireless camera connection?"
        )

        textA = wx.StaticText(
            self, -1, "Select how you plan to use this camera:",
            style=wx.ST_NO_AUTORESIZE
        )
        self._wifiRadio = wx.RadioButton(self, -1,
            "Wirelessly, connected to my network using Wi-Fi.",
            style=wx.RB_GROUP
        )
        self._wiredRadio = wx.RadioButton(self, -1,
            "Wired, plugged in where it is, or into another Ethernet port "
            "on this network."
        )
        makeFontDefault(textA, self._wifiRadio, self._wiredRadio)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)
        innerSizer.Add(self._wifiRadio, 0, wx.TOP, 3*_kPaddingSize)
        innerSizer.Add(self._wiredRadio, 0, wx.TOP, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        self._wifiRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self._wiredRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
        self._wifiRadio.Bind(wx.EVT_LEFT_DCLICK, self.OnRadioDoubleClick)
        self._wiredRadio.Bind(wx.EVT_LEFT_DCLICK, self.OnRadioDoubleClick)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)


    ###########################################################
    def OnRadioButton(self, event):
        """Handle either of the radio buttons being pressed.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        self.wizard.setWifiHelpFlow(self._wifiRadio.GetValue())


    ###########################################################
    def OnRadioDoubleClick(self, event):
        """Handle double-clicks to radio buttons.

        This should automatically go to next.
        """
        radioButton = event.GetEventObject()

        # Don't know if all of this is needed, but could imagine getting a
        # double-click when radio button wasn't selected...
        if not radioButton.GetValue():
            radioButton.SetValue(1)
            radioButton.Refresh()
            radioButton.Update()
            self.wizard.setWifiHelpFlow(self._wifiRadio.GetValue())

        self.wizard.ShowPage(self.GetNext())


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        We use this to handle switches to our page.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Init to the wizard default for wantHelp...
        wantWifiHelp = self.wizard.getWifiHelpFlow()
        self._wifiRadio.SetValue(wantWifiHelp)
        self._wiredRadio.SetValue(not wantWifiHelp)


##############################################################################
class _WifiSsidHelpScreen(_BasePage):
    """A screen telling the user to setup WiFi on their camera."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _WifiSsidHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_WifiSsidHelpScreen, self).__init__(
            wizard, "Enter wireless network settings on your camera's website"
        )

        if not _isOemVersion:
            textA = wx.StaticText(self, -1,
                u"On your camera's configuration website, look for a screen where "
                u"you can enter settings for your camera to connect to your "
                u"network (often labeled \"Wireless\" or \"Network\"):\n"
                u"\n"
                u"\u2022 Network name (\"SSID\")\n"
                u"\u2022 Type of security (e.g., WEP, WPA or none)\n"
                u"\u2022 Password (or \"key\")\n"
                u"\n"
                u"Click the button on your website to save these settings for your "
                u"camera (usually labeled \"Save\" or \"Apply\").  But don't close "
                u"your browser yet.",
                style=wx.ST_NO_AUTORESIZE
            )
            makeFontDefault(textA)
            textA.SetMinSize((1, -1))

            innerSizer = wx.BoxSizer(wx.VERTICAL)
            innerSizer.Add(textA, 1, wx.EXPAND | wx.TOP, 2*_kPaddingSize)

        else:
            # Create the wireless settings link.
            textB = wx.StaticText(
                self, -1, 'To go to the "Wireless Settings" page, click ',
                style=wx.ST_NO_AUTORESIZE
            )
            makeFontDefault(textB)
            self._addressLink = wx.adv.HyperlinkCtrl(self, -1, "here", " ", style=wx.NO_BORDER | wx.adv.HL_CONTEXTMENU | wx.adv.HL_ALIGN_LEFT)
            makeFontDefault(self._addressLink)
            makeFontUnderlined(self._addressLink)
            setHyperlinkColors(self._addressLink)
            textC = wx.StaticText(
                self, -1, ".", style=wx.ST_NO_AUTORESIZE
            )
            makeFontDefault(textC)

            # TODO-asante: Asante should provide/approve this text.
            textA = wx.StaticText(self, -1,
                'On the "Wireless Settings" page of your camera\'s configuration '
                'website, press the "Scan" button and select your network from '
                'the list.  Press the "Show All" if present to reveal all '
                'available settings.  Ensure that "Enabled" is set to "On" and '
                'your authentication information is correct.\n'
                '\n'
                'You should also verify that the "Wireless IP Assignment" '
                'settings are correct. For most users this will simply be '
                'ensuring that DHCP is set to "On".\n'
                '\n'
                'When you are finished click the "Connect" button at the '
                'bottom of the page.  After a few moments the "Status" field '
                'should update to say "Connected".  If not, please recheck '
                'your settings.\n'
                '\n'
                'Once you have completed these steps click Next.',
                style=wx.ST_NO_AUTORESIZE
            )
            makeFontDefault(textA)
            textA.SetMinSize((1, -1))
            textA.Wrap(_kTextWrap)

            innerSizer = wx.BoxSizer(wx.VERTICAL)
            innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)
            linkSizer = wx.BoxSizer(wx.HORIZONTAL)
            linkSizer.Add(textB, 0, wx.ALIGN_CENTER_VERTICAL)
            linkSizer.Add(self._addressLink, 0, wx.ALIGN_CENTER_VERTICAL)
            linkSizer.Add(textC, 0, wx.ALIGN_CENTER_VERTICAL)
            innerSizer.Add(linkSizer, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)

            self.wizard.upnpDataModel.addListener(self._handleUpnpChange)
            self.wizard.onvifDataModel.addListener(self._handleOnvifChange)
            self._addressLink.Bind(wx.adv.EVT_HYPERLINK, self.OnAddressLink)
            self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)


    ###########################################################
    def OnAddressLink(self, event):
        """Handle a click on the address link

        @param  event  The hyperlink event.
        """
        if self._addressLink.GetURL() == _kBadLink:
            wx.MessageBox("This device can no longer be found on the "
                          "network.  It may be rebooting.",
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
        else:
            event.Skip()


    ###########################################################
    def _handleUpnpChange(self, upnpDataModel):
        """Handle a change in the UPNP dictionary.

        We don't change much, but we might need to update our link.

        @param  upnpDataModel  The UPNP data model.
        """
        assert upnpDataModel == self.wizard.upnpDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        # Ignore changes if the stored device is a ONVIF URL.
        if isOnvifUrl(self.wizard.cameraUri):
            return

        # Get the USN for the device we stashed away...
        try:
            usn = extractUsnFromUpnpUrl(self.wizard.cameraUri)
        except ValueError:
            usn = None

        # Get the device...
        upnpDeviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()
        device = upnpDeviceDict.get(usn)

        if device is not None:
            # Get the presentation URL.
            presentationUrl, _ = device.getPresentationUrl()
            url = urlparse.urljoin(presentationUrl, "/asante/wireless.asp")
            self._addressLink.SetURL(url)
        else:
            self._addressLink.SetURL(_kBadLink)


    ###########################################################
    def _handleOnvifChange(self, onvifDataModel):
        """Handle a change in the ONVIF dictionary.

        We don't change much, but we might need to update our link.

        @param  onvifDataModel  The ONVIF data model.
        """
        assert onvifDataModel == self.wizard.onvifDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        # Ignore changes if the stored device is a UPnP URL.
        if isUpnpUrl(self.wizard.cameraUri):
            return

        # Get the UUID for the device we stashed away...
        try:
            uuid = extractUuidFromOnvifUrl(self.wizard.cameraUri)
        except ValueError:
            uuid = None

        # Get the device...
        onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()
        device = onvifDeviceDict.get(uuid)

        if device is not None:
            # Get the base URL.
            baseUrl, _ = device.validOnvifIpAddrs[-1]
            url = urlparse.urljoin(baseUrl, "/asante/wireless.asp")
            self._addressLink.SetURL(url)
        else:
            self._addressLink.SetURL(_kBadLink)


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        This happens when we switch _to_ this page...  This is the place where
        we READ from the wizard and populate our UI.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Fake up a UPNP message, since we were ignoring while we weren't
        # active...
        self._handleUpnpChange(self.wizard.upnpDataModel)
        self._handleOnvifChange(self.wizard.onvifDataModel)


##############################################################################
class _WifiUnplugEthernetHelpScreen(_BasePage):
    """A screen telling the user to unplug ethernet."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _WifiUnplugEthernetHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_WifiUnplugEthernetHelpScreen, self).__init__(
            wizard, "Disconnect the Ethernet cable from your camera"
        )

        helpText = \
            "When you unplug your Ethernet cable, the video feed on your " \
            "camera's configuration website may freeze, but that is normal.\n"
        if not _isOemVersion:
            helpText += \
            "\n" \
            "IMPORTANT: If your camera has a wired/wireless switch, such as " \
            "Panasonic network cameras, flip the switch to the \"wireless\" " \
            "position now."

        textA = wx.StaticText(self, -1, helpText, style=wx.ST_NO_AUTORESIZE)
        makeFontDefault(textA)
        textA.Wrap(_kTextWrap)

        ethernetBmp = wx.Bitmap("frontEnd/bmps/Connect_Ethernet_Help.jpg")
        ethernetStaticBmp = FixedStaticBitmap(self, -1, ethernetBmp)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)
        innerSizer.Add(ethernetStaticBmp, 0, wx.TOP, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)


##############################################################################
class _WifiUnplugPowerHelpScreen(_BasePage):
    """A screen telling the user to unplug power."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _WifiUnplugPowerHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_WifiUnplugPowerHelpScreen, self).__init__(
            wizard, "Reboot your camera"
        )

        if not _isOemVersion:
            textA = wx.StaticText(self, -1,
                "Unplug the power cable, wait five seconds, and plug it in again.  "
                "Your camera will reboot, which may take up to a minute or more.  "
                "The LED light usually indicates when this is complete (see your "
                "camera's documentation).",
                style=wx.ST_NO_AUTORESIZE
            )
        else:
            # TODO-asante: Asante should provide/approve this text.
            textA = wx.StaticText(self, -1,
                "Unplug the power cable, wait five seconds, and plug it in again.  "
                "Your camera will reboot, which may take up to a minute or more.  "
                "When the LED light on the front of the camera changes from "
                "yellow to off, the boot has completed and the caemera is "
                "connected.", style=wx.ST_NO_AUTORESIZE
            )
        makeFontDefault(textA)
        textA.Wrap(_kTextWrap)

        powerBmp = wx.Bitmap("frontEnd/bmps/Plug_In_Power_Help.jpg")
        powerStaticBmp = FixedStaticBitmap(self, -1, powerBmp)

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)
        innerSizer.Add(powerStaticBmp, 0, wx.TOP, 2*_kPaddingSize)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)


##############################################################################
class _WifiConfirmHelpScreen(_BasePage):
    """A screen telling the user to confirm their WiFi."""

    ###########################################################
    def __init__(self, wizard):
        """The initializer for _WifiConfirmHelpScreen.

        @param  wizard  The CameraSetupWizard..
        """
        super(_WifiConfirmHelpScreen, self).__init__(
            wizard, "Confirm your camera works wirelessly"
        )

        textA = wx.StaticText(self, -1,
            "Return to the website of your camera to "
            "verify that your configuration worked.\n ",
            style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textA)

        # Create the help text...
        textB = wx.StaticText(
            self, -1, "To go to the configuration web page, click ",
            style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textB)
        self._addressLink = wx.adv.HyperlinkCtrl(self, -1, "here", " ", style=wx.NO_BORDER | wx.adv.HL_CONTEXTMENU | wx.adv.HL_ALIGN_LEFT)
        makeFontDefault(self._addressLink)
        makeFontUnderlined(self._addressLink)
        setHyperlinkColors(self._addressLink)
        textC = wx.StaticText(
            self, -1, ". ", style=wx.ST_NO_AUTORESIZE
        )
        makeFontDefault(textC)

        if not _isOemVersion:
            textD = wx.StaticText(self, -1,
                " \nIf you can see a live image from your camera, click Next "
                "to continue. You may need to find a screen called something "
                "like \"Live View\" or \"View Video.\""
                "\n"
                "Note that your computer needs to be on the same network "
                "as your camera.",
                style=wx.ST_NO_AUTORESIZE
            )
        else:
            # TODO-asante: Asante should provide/approve this text.
            textD = wx.StaticText(self, -1,
                " \nIf you can see a live image from your camera, click Next "
                "to continue.\n"
                "\n"
                "Note that your computer needs to be on the same network "
                "as your camera.",
                style=wx.ST_NO_AUTORESIZE
            )
        makeFontDefault(textD)
        textD.SetMinSize((1, -1))

        innerSizer = wx.BoxSizer(wx.VERTICAL)
        innerSizer.Add(textA, 0, wx.EXPAND | wx.TOP, 2*_kPaddingSize)

        linkSizer = wx.BoxSizer(wx.HORIZONTAL)
        linkSizer.Add(textB, 0, wx.ALIGN_CENTER_VERTICAL)
        linkSizer.Add(self._addressLink, 0, wx.ALIGN_CENTER_VERTICAL)
        linkSizer.Add(textC, 0, wx.ALIGN_CENTER_VERTICAL)
        innerSizer.Add(linkSizer, 0, wx.EXPAND)

        innerSizer.Add(textD, 0, wx.EXPAND)

        self.sizer.Add(innerSizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        self.wizard.upnpDataModel.addListener(self._handleUpnpChange)
        self.wizard.onvifDataModel.addListener(self._handleOnvifChange)

        self._addressLink.Bind(wx.adv.EVT_HYPERLINK, self.OnAddressLink)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)


    ###########################################################
    def OnAddressLink(self, event):
        """Handle a click on the address link

        @param  event  The hyperlink event.
        """
        if self._addressLink.GetURL() == _kBadLink:
            wx.MessageBox("This device can no longer be found on the "
                          "network.  It may be rebooting.",
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
        else:
            event.Skip()


    ###########################################################
    def _handleUpnpChange(self, upnpDataModel):
        """Handle a change in the UPNP dictionary.

        We don't change much, but we might need to update our link.

        @param  upnpDataModel  The UPNP data model.
        """
        assert upnpDataModel == self.wizard.upnpDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        # Ignore changes if the stored device is a ONVIF URL.
        if isOnvifUrl(self.wizard.cameraUri):
            return

        # Get the USN for the device we stashed away...
        try:
            usn = extractUsnFromUpnpUrl(self.wizard.cameraUri)
        except ValueError:
            usn = None

        # Get the device...
        upnpDeviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()
        device = upnpDeviceDict.get(usn)

        if device is not None:
            # Get the presentation URL.
            presentationUrl, _ = device.getPresentationUrl()
            self._addressLink.SetURL(presentationUrl)
        else:
            self._addressLink.SetURL(_kBadLink)


    ###########################################################
    def _handleOnvifChange(self, onvifDataModel):
        """Handle a change in the ONVIF dictionary.

        We don't change much, but we might need to update our link.

        @param  onvifDataModel  The ONVIF data model.
        """
        assert onvifDataModel == self.wizard.onvifDataModel

        # Ignore changes while we're not the current page...
        if self.wizard.GetCurrentPage() != self:
            return

        # Ignore changes if the stored device is a UPnP URL.
        if isUpnpUrl(self.wizard.cameraUri):
            return

        # Get the UUID for the device we stashed away...
        try:
            uuid = extractUuidFromOnvifUrl(self.wizard.cameraUri)
        except ValueError:
            uuid = None

        # Get the device...
        onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()
        device = onvifDeviceDict.get(uuid)

        if device is not None:
            # Get the base URL.
            baseUrl = device.validOnvifIpAddrs[-1]
            self._addressLink.SetURL(baseUrl)
        else:
            self._addressLink.SetURL(_kBadLink)


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        This happens when we switch _to_ this page...  This is the place where
        we READ from the wizard and populate our UI.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Fake up a UPNP message, since we were ignoring while we weren't
        # active...
        self._handleUpnpChange(self.wizard.upnpDataModel)
        self._handleOnvifChange(self.wizard.onvifDataModel)


##############################################################################
class _TestScreen(_BasePage):
    """A screen for testing cameras."""
    def __init__(self, wizard):
        """The initializer for _TestScreen.

        @param  wizard  The CameraSetupWizard.
        """
        super(_TestScreen, self).__init__(wizard, "Test your camera connection")

        self._mmap = None
        self._lastFrame = -1
        self._timer = wx.Timer(self)
        self._lastStatusUpdate = time.time()

        # Create the controls
        nextText = wx.StaticText(self, -1, "If you see your camera's image in "
                                 "the window below, click Next.")
        viewText = wx.StaticText(self, -1, "If not, try to ")
        self._viewLink = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, "view your camera from your browser.", "")
        setHyperlinkColors(self._viewLink)

        bmpFont = self.GetFont()
        bmpFont.SetPointSize(12)
        if wx.Platform == '__WXMSW__':
            bmpFont.SetPointSize(10)

        # Import here to avoid circular dependencies...
        from MonitorView import makeVideoStatusBitmap
        self._connectingBmp = makeVideoStatusBitmap("Connecting...", bmpFont,
                                                    False,
                                                    width=_kTestVideoSize[0],
                                                    height=_kTestVideoSize[1])
        self._failedBmp = makeVideoStatusBitmap("Could not connect", bmpFont,
                                                False,
                                                width=_kTestVideoSize[0],
                                                height=_kTestVideoSize[1])
        self._videoWindow = BitmapWindow(self, self._connectingBmp,
                                         _kTestVideoSize, scale=True)

        knownHelpText = wx.StaticText(self, -1, "If you can see it in your "
                            "browser, then click the Back button below and "
                            "check your user name and password.\n\n"
                            "If you can't see your camera in your browser, "
                            "there may be a problem with the camera, the "
                            "settings in the last screen, or your network.")

        otherHelpText = wx.StaticText(self, -1, "If you can see it in your "
                            "browser, then click the Back button below and "
                            "check your user name, password and URL.  If you "
                            "entered your user name, password and URL "
                            "correctly, your camera may not be compatible with "
                            "this software.\n\n"
                            "If you can't see your camera in your browser, "
                            "there may be a problem with the camera, the "
                            "settings in the last screen, or your network. ")
        webcamHelpText = wx.StaticText(self, -1, "If not, make sure that no "
                            "other applications are running that use "
                            "your webcam.  You can also try one of "
                            "those applications to verify that your "
                            "webcam is working.")

        makeFontDefault(nextText, viewText, self._viewLink, knownHelpText,
                        otherHelpText, webcamHelpText)
        makeFontUnderlined(self._viewLink)

        for control in [nextText, knownHelpText, otherHelpText, webcamHelpText]:
            control.Wrap(_kTextWrap)

        self._ipControls = [viewText, self._viewLink, knownHelpText]
        self._otherControls = [viewText, self._viewLink, otherHelpText]
        self._webcamControls = [webcamHelpText]

        # Add to the sizer
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(nextText, 0, wx.TOP, 2*_kPaddingSize)
        vSizer.Add(self._videoWindow, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM,
                   1.5*_kPaddingSize)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(viewText, 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self._viewLink, 0, wx.ALIGN_CENTER_VERTICAL)
        vSizer.Add(hSizer, 0, wx.BOTTOM, _kPaddingSize)
        vSizer.Add(knownHelpText, 0, wx.BOTTOM, _kPaddingSize)
        vSizer.Add(otherHelpText, 0, wx.BOTTOM, _kPaddingSize)
        vSizer.Add(webcamHelpText, 0, wx.BOTTOM, _kPaddingSize)
        self.sizer.Add(vSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT,
                       3*_kPaddingSize)

        # When we're created ensure we're at our maximum size
        knownHelpText.Hide()
        webcamHelpText.Hide()

        self._viewLink.Bind(wx.adv.EVT_HYPERLINK, self.OnViewLink)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)

        self.wizard.upnpDataModel.addListener(self._handleUpnpChange)
        self.wizard.onvifDataModel.addListener(self._handleOnvifChange)


    ###########################################################
    def __del__(self):
        """The destructor for _TestScreen."""
        # We want to ensure that any open streams were closed.
        self._stopTestStream()


    ###########################################################
    def CleanupTimers(self):
        self._timer.Stop()
        self._timer = None

    ###########################################################
    def OnViewLink(self, event):
        """Handle a click on the view link

        @param  event  The hyperlink event.
        """
        if self._viewLink.GetURL() == _kBadLink:
            wx.MessageBox("This device can no longer be found on the "
                          "network.  It may be rebooting.",
                          "Error", wx.OK | wx.ICON_ERROR,
                          self.GetTopLevelParent())
        else:
            event.Skip()


    ###########################################################
    def OnChanging(self, event):
        """Handle a page changing event.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        if event.GetPage() != self:
            # If we're not the source page we don't care about this event.
            event.Skip()
            return

        # Stop the live view
        self._stopTestStream()


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        # Update the URL right away when we're changed to...
        self._updateUrl()

        # Ensure the proper controls are displaying based on the current
        # camera configuration.
        allControls = self._ipControls+self._otherControls+self._webcamControls
        for control in allControls:
            control.Hide()

        if self.wizard.cameraType == 'Webcam':
            for control in self._webcamControls:
                control.Show()
        elif self.wizard.cameraType == 'Other IP camera':
            for control in self._otherControls:
                control.Show()
        else:
            for control in self._ipControls:
                control.Show()
        self.Layout()

        # Start the live view.
        self._startTestStream()


    ###########################################################
    def _handleUpnpChange(self, upnpDataModel):
        """Handle a change in the UPNP dictionary.

        We don't change much, but we might need to update our link.

        @param  upnpDataModel  The UPNP data model.
        """
        assert upnpDataModel == self.wizard.upnpDataModel
        self._updateUrl()


    ###########################################################
    def _handleOnvifChange(self, onvifDataModel):
        """Handle a change in the ONVIF dictionary.

        We don't change much, but we might need to update our link.

        @param  onvifDataModel  The ONVIF data model.
        """
        assert onvifDataModel == self.wizard.onvifDataModel
        self._updateUrl()


    ###########################################################
    def _updateUrl(self):
        """Update the URL in our viewLink.

        You want to do this periodically, at least for UPNP URLs.  That's
        because UPNP devices could theoretically change IP addresses...
        """
        upnpDeviceDict = self.wizard.upnpDataModel.getUpnpDeviceDict()
        onvifDeviceDict = self.wizard.onvifDataModel.getOnvifDeviceDict()

        # Default to a bad link...
        linkStr = _kBadLink

        # Set the browse hyperlink to the url/port of the camera.
        if self.wizard.cameraType != 'Webcam':
            # Get the URL, then realize it if it's a UPNP URL...
            # TODO: Use the full device dict...
            url = self.wizard.cameraUri
            if isUpnpUrl(url):
                url = realizeUpnpUrl(upnpDeviceDict, url)
            elif isOnvifUrl(url):
                url = realizeOnvifUrl(onvifDeviceDict, url)

            if url:
                # Make a new URL with just the hostname and port...
                # ...we'll also force to http port 80 (as a guess) if the URL
                # is non-http...
                splitResult = urlparse.urlsplit(url)
                scheme = splitResult.scheme
                netloc = splitResult.hostname

                try:
                    port = splitResult.port
                except ValueError:
                    assert False, "Non-numeric port"
                    port = None

                if not netloc:
                    netloc = ''
                if scheme != 'http':
                    # Non-http.  Guess that we can do http default port...
                    scheme = 'http'
                elif port:
                    # Http, and there's a port.  Add it in...
                    netloc += ':%d' % port

                linkStr = urlparse.urlunsplit((scheme, netloc, "/", "", ""))

        self._viewLink.SetURL(linkStr)


    ###########################################################
    def _startTestStream(self):
        """Attempt to stream from the camera."""
        self._failed = False

        # Tell the back end to start the stream
        self.wizard.backEndClient.startCameraTest(self.wizard.cameraUri,
                self.wizard.camExtras.get('forceTCP', True))

        # Start the update timer.
        self._timer.Start(50, False)


    ###########################################################
    def _stopTestStream(self):
        """Stop the test stream."""
        # Tell the back end to close the stream.
        self.wizard.backEndClient.stopCameraTest()

        # Stop the timer.
        self._timer.Stop()

        # Blank the test image.
        self._videoWindow.updateBitmap(self._connectingBmp)

        # Close the memory map.
        if self._mmap is not None:
            self._mmap.close()

        self._mmap = None
        self._lastFrame = -1


    ###########################################################
    def OnTimer(self, event=None):
        """Update the preview image.

        @param  event  The timer event (ignored).
        """
        try:
            if self._mmap is None:
                if not self._failed and time.time() > self._lastStatusUpdate+1:
                    # Show the failed screen if necessary
                    self._lastStatusUpdate = time.time()
                    if self.wizard.backEndClient.testCameraFailed():
                        self._failed = True
                        self._videoWindow.updateBitmap(self._failedBmp)

                dataDir = getUserLocalDataDir()
                fLoc = os.path.join(dataDir, 'live', kTestLiveFileName)
                f = open(fLoc, 'r+b')
                self._mmap = mmap.mmap(f.fileno(), 0)

            if self._mmap is not None:
                # In case old files are stuck around we wait until we actually
                # witness the frame number change before displaying any images.
                header = str(self._mmap[:kTestLiveHeaderSize])
                headerNum = int(header[0])
                if self._lastFrame == -1:
                    self._lastFrame = headerNum
                    return
                if self._lastFrame == headerNum:
                    return
                self._lastFrame = headerNum

                try:
                    # Find the size of the image we are looking for, grab
                    # the image data and update the video window.
                    width = int(header[1:5])
                    height = int(header[5:9])
                    if width > 0 and height > 0:
                        bmpData = self._mmap[kTestLiveHeaderSize:]
                        bmp = wx.Bitmap.FromBuffer(width, height, bmpData)
                        self._videoWindow.updateBitmap(bmp)
                except ValueError:
                    pass

        except Exception:
            self._mmap = None


##############################################################################
class _FinishScreen(_BasePage):
    """The closing screen for CameraSetupWizard."""
    def __init__(self, wizard, firstScreen):
        """The initializer for _FinishScreen.

        @param  wizard       The CameraSetupWizard.
        @param  firstScreen  The screen to progress to when creating another
                             camera.
        """
        super(_FinishScreen, self).__init__(wizard, "Camera setup complete")

        self._firstScreen = firstScreen
        self._emptyPage = _BasePage(wizard, "Camera setup complete")

        self._finishRadio = wx.RadioButton(self, -1,
                                           "Click Finish to close this wizard "
                                           "and view your camera in the Monitor"
                                           " view", style=wx.RB_GROUP)
        self._finishRadio.SetValue(True)
        self._continueRadio = wx.RadioButton(self, -1, "Set up another camera ("
                                             "click Next to return to the first"
                                             " setup screen).")
        makeFontDefault(self._finishRadio, self._continueRadio)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self._finishRadio)
        vSizer.AddSpacer(3*_kPaddingSize)
        vSizer.Add(self._continueRadio)
        self.sizer.Add(vSizer, 0, wx.ALL, 3*_kPaddingSize)

        self._finishRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadio)
        self._continueRadio.Bind(wx.EVT_RADIOBUTTON, self.OnRadio)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGED, self.OnChanged)
        self.wizard.Bind(wxWizard.EVT_WIZARD_PAGE_CHANGING, self.OnChanging)


    ###########################################################
    def OnChanging(self, event):
        """Handle a page changing event.

        @param  event  The EVT_WIZARD_PAGE_CHANGING event.
        """
        if (event.GetPage() != self) or not event.GetDirection():
            # If we're not the source page we don't care about this event.
            event.Skip()
            return

        assert False, "This is never called--wizard overrides"


    ###########################################################
    def OnChanged(self, event):
        """Handle a page changed event.

        @param  event  The EVT_WIZARD_PAGE_CHANGED event.
        """
        if event.GetPage() != self:
            event.Skip()
            return

        self._updateNext()


    ###########################################################
    def _updateNext(self):
        """Update the next page based on the radio buttons."""

        # Figure out what should be next...
        if self._finishRadio.GetValue():
            wantNext = None
        else:
            wantNext = self._firstScreen

        # Only update if needed; this is important since we are called from
        # OnChanged(), and the last step in here will end up causing OnChanged()
        # to be called.  ...we need to avoid the infinite recursion.
        if self.GetNext() != wantNext:
            # We want to update the button to properly display Next or Finish.
            # Unfortunately if we do this while we're the active page the button
            # seems to get stuck on 'Finish', even when we go to different
            # pages!  To prevent this we temporarily switch to an empty page,
            # update our link, and then switch back to ourself.  This makes the
            # buttons display properly.
            self.wizard.ShowPage(self._emptyPage, False)
            self.SetNext(wantNext)
            self.wizard.ShowPage(self, False)


    ###########################################################
    def OnRadio(self, event=None):
        """Ensure that the proper buttons are active.

        @param  event  The EVT_RADIOBUTTON event, ignored.
        """
        self._updateNext()


##############################################################################
class _LocalCamDataModel(AbstractModel):
    """A model for holding info about webcams.

    This allows subscription to change notification.  Right now, there is just
    the generic change notification--no subtypes.
    """

    ###########################################################
    def __init__(self):
        """_LocalCamDataModel constructor."""
        super(_LocalCamDataModel, self).__init__()

        self._localCamNames = []
        self._localCamData = {}
        self._localCamDeviceIdStyleOldToNew = {}

        self._defaultResolutionsNum = [(320, 240),
                                       (640, 480),
                                       (1024, 768),
                                       (1280, 720),
                                       (1280, 1024),
                                       (1600, 1200),
                                       (1920, 1080),
                                       (1920, 1200)
                                             ]
        self._defaultResolutionsStr = ['%dx%d' % (w, h) for (w, h) in self._defaultResolutionsNum]
        self._defaultResolutionsStr2Num = dict(zip(self._defaultResolutionsStr, self._defaultResolutionsNum))
        self._defaultResolutionsNum2Str = dict(zip(self._defaultResolutionsNum, self._defaultResolutionsStr))

    ###########################################################
    def setLocalCams(self, localCamNames):
        """Set the local cameras.

        Sends an update if these are new names.

        @param  localCamNames  The new localCamNames.
        """
        if localCamNames != self._localCamNames:
            self._localCamNames = localCamNames

            # Sort the names to make new-style device IDs easy, but keep
            # track of index for old-style device IDs...
            localCams = sorted((data, i) for (i, data) in enumerate(self._localCamNames))

            # Add all non VFW cameras (which are kinda broken); keep deviceId
            # in the client data...
            # Note that we want to match against old style device IDs (where
            # index was global across all local cameras) and new style device
            # IDs (where index is local across cameras of the same name)...
            prevName = None
            sameNameCount = 0
            for ((camName, camResIntList), i) in localCams:
                if not camName.endswith('(VFW)'):
                    if camName == prevName:
                        sameNameCount += 1
                    else:
                        prevName = camName
                        sameNameCount = 0

                    oldStyleDeviceId = (i, camName)
                    deviceId = (_kNewDeviceIdOffset + sameNameCount, camName)

                    if camResIntList:
                        camResIntList = [(w,h) for [w,h] in camResIntList]
                        camResIntList.append( kDefaultRecordSize )
                        camResIntList.append( kMaxRecordSize )
                        camResIntList = sorted(list(set(camResIntList)))
                    else:
                        camResIntList = self._defaultResolutionsNum

                    camModel = _CamData(camName, deviceId, oldStyleDeviceId, camResIntList)

                    self._localCamData[deviceId] = camModel
                    self._localCamDeviceIdStyleOldToNew[oldStyleDeviceId] = deviceId

            self.update()


    ###########################################################
    def getLocalCamNamesWithDeviceIDs(self):
        """
        """
        return [(camData.getCamName(), deviceId) for (deviceId, camData) in self._localCamData.items()]


    ###########################################################
    def getCamData(self, deviceId):
        """
        """
        camData = self._localCamData.get(deviceId)
        if camData is None:
            newStyleId = self._localCamDeviceIdStyleOldToNew.get(deviceId)
            camData = self._localCamData.get(newStyleId)
        return camData


    ###########################################################
    def getLocalCams(self):
        """Get the local cameras.

        @return localCameras  The local cameras.
        """
        return self._localCamData.values()

    ###########################################################
    def getDefaultResolutionsStr(self):
        return self._defaultResolutionsStr

    ###########################################################
    def defaultResolutionStr2Num(self, val):
        return self._defaultResolutionsStr2Num.get(val)

    ###########################################################
    def defaultResolutionNum2Str(self, num):
        return self._defaultResolutionsNum2Str.get(num)


##############################################################################
class _CamData(object):
    """
    """
    ###########################################################
    def __init__(self, camName, deviceId, oldStyleDeviceId, resNums):
        """
        """
        self._camName = camName
        self._deviceId = deviceId
        self._oldStyleDeviceId = oldStyleDeviceId
        self._resolutionsNum = resNums
        self._resolutionsStr = ['%dx%d' % (w, h) for (w, h) in resNums]
        self._resolutionsStr2Num = dict(zip(self._resolutionsStr, resNums))
        self._resolutionsNum2Str = dict(zip(resNums, self._resolutionsStr))

    ###########################################################
    def getCamName(self):
        return self._camName

    ###########################################################
    def getDeviceId(self):
        return self._deviceId

    ###########################################################
    def getOldStyleDeviceId(self):
        return self._oldStyleDeviceId

    ###########################################################
    def getResolutionsStr(self):
        return self._resolutionsStr

    ###########################################################
    def resolutionStr2Num(self, val):
        return self._resolutionsStr2Num.get(val)

    ###########################################################
    def resolutionNum2Str(self, num):
        return self._resolutionsNum2Str.get(num)



##############################################################################
class _UpnpDataModel(AbstractModel):
    """A model for holding UPNP data.

    This allows subscription to change notification.  Right now, there is just
    the generic change notification--no subtypes.
    """

    ###########################################################
    def __init__(self):
        """_UpnpDataModel constructor."""
        super(_UpnpDataModel, self).__init__()

        self._upnpRevNum = None
        self._upnpDeviceDict = {}


    ###########################################################
    def getUpnpRevNum(self):
        """Return the UPNP rev number.

        Whenever the UPNP dict changes, it will have a new revnum.

        @return upnpRevNum  The UPNP rev num.
        """
        return self._upnpRevNum


    ###########################################################
    def getUpnpDeviceDict(self):
        """Return the UPNP device dict.

        @return upnpDeviceDict  The UPNP device dict.
        """
        return self._upnpDeviceDict


    ###########################################################
    def setUpnpDeviceDict(self, upnpRevNum, upnpDeviceDict):
        """Set the upnp device dict (and thus, the rev num).

        This will send an update.

        @param  upnpRevNum      The UPNP revision number; must be newer than
                                the previous one.
        @param  upnpDeviceDict  The UPNP device dict.
        """
        assert upnpRevNum != self._upnpRevNum
        self._upnpRevNum = upnpRevNum
        self._upnpDeviceDict = upnpDeviceDict

        self.update()


##############################################################################
class _OnvifDataModel(AbstractModel):
    """A model for holding ONVIF data.

    This allows subscription to change notification.  Right now, there is just
    the generic change notification--no subtypes.
    """

    ###########################################################
    def __init__(self):
        """_OnvifDataModel constructor."""
        super(_OnvifDataModel, self).__init__()

        self._onvifRevNum = None
        self._onvifDeviceDict = {}


    ###########################################################
    def getOnvifRevNum(self):
        """Return the ONVIF rev number.

        Whenever the ONVIF dict changes, it will have a new revnum.

        @return onvifRevNum  The ONVIF rev num.
        """
        return self._onvifRevNum


    ###########################################################
    def getOnvifDeviceDict(self):
        """Return the ONVIF device dict.

        @return onvifDeviceDict  The ONVIF device dict.
        """
        return self._onvifDeviceDict


    ###########################################################
    def setOnvifDeviceDict(self, onvifRevNum, onvifDeviceDict):
        """Set the onvif device dict (and thus, the rev num).

        This will send an update.

        @param  onvifRevNum      The ONVIF revision number; must be newer than
                                 the previous one.
        @param  onvifDeviceDict  The ONVIF device dict.
        """
        assert onvifRevNum != self._onvifRevNum
        self._onvifRevNum = onvifRevNum
        self._onvifDeviceDict = onvifDeviceDict

        self.update()


###########################################################
def _compareUris(uri1, uri2):
    """Compares two URI's for equality.

    This will NOT compare host names nor IP addresses. It checks if the
    scheme and paths are the same. Trailing slashes are removed for
    comparisons.

    @param   uri1  The first URI, as a string.
    @param   uri1  The second URI to compare with the first, as a string.
    @return  result  True if they match, False otherwise.
    """

    if not uri1:
        uri1 = ''
    if not uri2:
        uri2 = ''

    uri1Result = urlparse.urlsplit(str(uri1))
    uri2Result = urlparse.urlsplit(str(uri2))

    scheme1, _, path1, query1, fragment1 = uri1Result
    port1 = uri1Result.port

    scheme2, _, path2, query2, fragment2 = uri2Result
    port2 = uri2Result.port

    return ((scheme1.lower() == scheme2.lower())                     and
            (_getPort(port1, scheme1) == _getPort(port2, scheme2))   and
            (path1.strip('/') == path2.strip('/'))                   and
            (query1.strip('/') == query2.strip('/'))                 and
            (fragment1.strip('/') == fragment2.strip('/')))


###########################################################
def _getDefaultPortForScheme(scheme):
    """Returns the default port for a given scheme as a string value.

    @param   scheme  The protocol. Can be http, https or rtsp.
    @return  result  Returns 80 for http, 554 for rtsp, 443 for https,
                     and -1 otherwise.  The result will be an integer.
    """
    if scheme:

        schemeStripped ,_ ,_ = scheme.lower().partition(':')

        if schemeStripped == 'http':
            return 80
        elif schemeStripped == 'rtsp':
            return 554
        elif schemeStripped == 'https':
            return 443

    return -1


###########################################################
def _getPort(port, scheme):
    """If the given port is valid, port is returned. Otherwise the default port
    is returned determined by the given scheme.

    @param   port    Port number as a string or integer.
    @param   scheme  The protocol. Can be http, https or rtsp.
    @return  result  Returns the port as an integer. If the port number is
                     non-numeric, None, or the empty string, then the default
                     port is returned, as determined by the given scheme. If the
                     port is invalid and the scheme not a valid protocol string,
                     then -1 is returned.
    """
    if port:
        try:
            port = int(port)
        except ValueError:
            # We expect this if port is non-numeric for some reason.
            pass
        return port

    # _getDefaultPortForScheme() returns -1 when the scheme is invalid.
    return _getDefaultPortForScheme(scheme)


##############################################################################
def _getStreamPath(cameraType, resolution):
    """Get the stream path given a camera type and resolution.

    This mostly uses kTypeToStreamPath to do the lookup, but handles the
    resolution too (which sometimes affects the stream path).

    @param  cameraType  The camera type.
    @param  resolution  The resolution, as a tuple of (width, height)
    @return scheme      The scheme, like "http://"
    @return pathPart    The path part, always starting with "/"
    @return defaultPort The default port to use, or None.
    """
    assert cameraType in kTypeToStreamPath

    scheme, pathPart, defaultPort = kTypeToStreamPath[cameraType]

    mapping = {}

    # Figure out if it referrs to a resolution map...
    resSplit = pathPart.split('%(Res_', 2)
    if len(resSplit) == 2:
        # It does!  Get the map out...
        mapName = resSplit[-1].split(')', 2)[0]

        if mapName in kResMaps:
            # We have the map, so get it...
            resMap = kResMaps.get(mapName)

            # If the resolution is in the map, then we'll put in a mapping.
            # If not, we'll use the default from the map (and if no default,
            # we'll use the empty string).
            if resolution in resMap:
                resStr = resMap[resolution]
            else:
                resStr = resMap.get(None, "")

            mapping['Res_' + mapName] = resStr
        else:
            assert False, "Unknown resolution map: %s" % mapName
            mapping['Res_' + mapName] = ""

    pathPart = pathPart % mapping

    return scheme, pathPart, defaultPort


##############################################################################
def _getCameraDescription(camType):
    """Return the description for the given camera type.

    @param  camType  The camera type.
    @return camDesc  A description string for the type.
    """
    if camType in kCameraDescriptions:
        return kCameraDescriptions[camType]
    else:
        for thisCamRe, thisCamDesc in kCameraGenericDescriptions:
            mo = re.match(thisCamRe, camType)
            if mo:
                return thisCamDesc

    return ""




##############################################################################
def _getUrlPathPart(urlSplitResult):
    """Join the "path", "query", and "fragment" parts of urlsplit result.

    @param  urlSplitResult  The result of calling urlparse.urlsplit() on a URL.
    @return pathPart        The path part.
    """
    pathPart = urlSplitResult.path
    if urlSplitResult.query:
        pathPart += "?" + urlSplitResult.query
    if urlSplitResult.fragment:
        pathPart += "#" + urlSplitResult.fragment

    return pathPart


##############################################################################
def _getResHelpLink(parent):
    """Create a help hyperlink to display near resolution controls.

    @param  parent     The parent window for the hyperlink.
    @return hyperlink  The hyperlink control.
    """
    hyperlink = wx.adv.HyperlinkCtrl(parent, -1, "(more information)", "")
    setHyperlinkColors(hyperlink)
    makeFontDefault(hyperlink)
    makeFontUnderlined(hyperlink)
    hyperlink.Bind(wx.adv.EVT_HYPERLINK, OnResHelpLink)

    return hyperlink


##############################################################################
def OnResHelpLink(event):
    """Handle a click of the resolution help hyperlink.

    @param  event  The hyperlink event.
    """
    wx.MessageBox(_kResolutionHelpText,
                  "Video Resolution", wx.OK | wx.ICON_INFORMATION,
                  event.GetEventObject().GetTopLevelParent())


##############################################################################
def _getHighestResolutionByLicense(wizard):
    """Return the highest resolution possible allowed by the current license.

    @param  wizard      The wizard.
    @return resolution  The resolution as a two-tuple of ints.
    """
    if hasPaidEdition(wizard.backEndClient.getLicenseData()):
        return kMatchSourceSize
    else:
        return kMaxRecordSize


##############################################################################
def _vetoIfResolutionLocked(event, wizard, selectedResStr):
    """Veto the given event if an invalid resolution is selected.

    @param  event           The page changing event.
    @param  wizard          The wizard.
    @param  selectedResStr  The selected resolution string.
    @return vetoed          True if vetoed.
    """
    if hasPaidEdition(wizard.backEndClient.getLicenseData()):
        return False

    # We can't use wizard.cameraType to see if it's a webcam or ip camera that
    # we're checking when the user is starting fresh from the welcome screen.
    # So just try to get the resolutions from the ip camera default resolution
    # dictionary first.  If there's nothing there, go through the webcams
    # and check their dictionaries for the right resolution we want. Finally,
    # if it's not found there, just get the resolution from the default webcam
    # resolution list.  All of this checking should still be just as fast, or
    # nearly just as fast as the way it was done before. Since the list of
    # usb cameras will always be very tiny, there won't be any performance hit
    # here.
    resolution = _kRecordSizeStrToNums.get(selectedResStr)

    if resolution is None:
        for camData in wizard.localCamModel.getLocalCams():
            resolution = camData.resolutionStr2Num(selectedResStr)
            if resolution is not None:
                break
        else:
            resolution = wizard.localCamModel.defaultResolutionStr2Num(selectedResStr)

    if resolution is not None and resolution != kMatchSourceSize:
        if resolution[0] <= kMaxRecordSize[0] and resolution[1] <= kMaxRecordSize[1]:
            return False

    event.Veto()
    try:
        showResolutionWarning(wizard.GetTopLevelParent(), _kMaxRecordSizeStr,
                wizard.backEndClient)
    except Exception, e:
        print e

    return True


_kLegacyTcpFlag = 'svforcetcp'
###########################################################
def _stripLegacyTcpOverride(url):
    """Check for a legacy tcp force flag in the url.

    @param  url         The url to examine.
    @return hadTcpFlag  True if there was a tcp flag present.
    @return newUrl      The new URL, stripped of tcp flags.
    """
    hadTcpFlag = False

    try:
        if not url or _kLegacyTcpFlag not in url:
            return hadTcpFlag, url

        hadTcpFlag = True

        if url.endswith(_kLegacyTcpFlag):
            # If at the end of the url remove the flag and the leading ? or &
            url = url[:-len(_kLegacyTcpFlag)-1]
        else:
            # If not at the end there is a following param, so strip the flag
            # and the following &. Leave the lead char, it may be either ? or &
            index = url.index(_kLegacyTcpFlag)
            url = url[:index]+url[index+len(_kLegacyTcpFlag)+1:]
    except Exception, e:
        print e

    return hadTcpFlag, url


###########################################################
def _testStripLegacyTcp():

    testVals = [
        # Positive
        ('rtsp://blah:123/somePath?someflag&anotherflag&svforcetcp',
         'rtsp://blah:123/somePath?someflag&anotherflag', True),
        ('rtsp://blah:123/somePath?someflag&svforcetcp&trailingflag',
         'rtsp://blah:123/somePath?someflag&trailingflag', True),
        ('rtsp://blah:123/somePath?svforcetcp',
         'rtsp://blah:123/somePath', True),
        ('rtsp://blah:123/somePath?svforcetcp&alskdjfaksldfj',
         'rtsp://blah:123/somePath?alskdjfaksldfj', True),

        # Negative
        ('rtsp://blah:123/somePath?someflag&svforctcp&trailingflag',
         'rtsp://blah:123/somePath?someflag&svforctcp&trailingflag',
         False),
    ]

    for (url, good, stripped) in testVals:
        print "Checking " + url
        strip, new = _stripLegacyTcpOverride(url)
        assert good == new and strip == stripped, \
                "TCP strip failed %s -> %s (%s)" % (url, new, good)


##############################################################################
def test_main(testType="full"):
    """OB_REDACT
       Contains various self-test code.
    """
    from BackEndClient import BackEndClient
    from backEnd.DataManager import DataManager

    # A list of 3-tuples used for testing the _compareUris().
    # The 3-tuple stores:
    # (url1, url2, hardTruth)  where,
    # url1 is a url as a string value.
    # url2 is a url as a string value.
    # hardTruth must be set to True if url1==url2, False otherwise. A match
    # is defined as a string match between the schemes, ports, and paths, but
    # not the hostnames, of the two url's.
    # TODO:  ADD MORE TEST CASES
    linkComparisons = [('rtsp://192.168.0.1:554/0',
                        'rtsp://ovzg4otvovuwiorq.gaygeobsgqzc2ndd.'
                        'ge4s2ndbmrtc2obx.gazc2mbqgbrdqmru.gi2ggmjz.'
                        'sighthoundonvif/0', True),
                       ]

    for (uri1, uri2, hardTruth) in linkComparisons:
        assert hardTruth == _compareUris(uri1, uri2)

    app = wx.App(False)
    _ = app
    app.SetAppName(kAppName)

    dm = DataManager(None)
    dm.open(os.path.join(getUserLocalDataDir(), 'videos', 'objdb2'))

    backEndClient = BackEndClient()
    didConnect = backEndClient.connect()
    assert didConnect, "BACK END NEED TO BE RUNNING TO RUN TEST CODE"

    assert testType in ("full", "partial")
    if testType == "full":
        wiz = CameraSetupWizard(None, backEndClient, dm)
    else:
        wiz = CameraSetupWizard(None, backEndClient, dm,
                               backEndClient.getCameraLocations()[0])
    wiz.run()


##############################################################################
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main(*sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "tcp":
        _testStripLegacyTcp()
    else:
        print "Try calling with 'test' as the argument."
