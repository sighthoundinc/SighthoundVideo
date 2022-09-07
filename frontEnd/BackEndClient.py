#!/usr/bin/env python

#*****************************************************************************
#
# BackEndClient.py
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
import cPickle
import os
import socket
import sys
import time
import xmlrpclib
from xml.parsers.expat import ExpatError

# Common 3rd-party imports...
import wx

# Toolbox imports...
from vitaToolbox.process.ProcessUtils import getProcessesWithName
from vitaToolbox.process.ProcessUtils import filteredProcessCommands
from vitaToolbox.process.ProcessUtils import killProcess
from vitaToolbox.strUtils import Obfuscate

# Local imports...
from appCommon.CommonStrings import kBackendExeName
from appCommon.CommonStrings import kWebcamExeName
from appCommon.CommonStrings import kPortFileName
from appCommon.CommonStrings import kMagicCommKey
from appCommon.CommonStrings import kBackendMarkerArg
from appCommon.CommonStrings import kMemStoreLicenseData
from appCommon.CommonStrings import kMemStoreLicenseLoginStatus
from appCommon.CommonStrings import kLoginStatusToken
from appCommon.XmlRpcClientIdWrappers import ServerProxyWithClientId
from frontEnd.FrontEndUtils import getUserLocalDataDir
from frontEnd.FrontEndUtils import getServiceStartsBackend
from launch.Launch import Launch



# Globals...



###########################################################
def getBackendProcesses():
    """ Returns a list of processes which have been identified to be the
    backend or former instances of such.

    @return List of process IDs (may be empty).
    """
    if sys.platform == "win32":
        res = getProcessesWithName(kBackendExeName)
    else:
        res = filteredProcessCommands(
            lambda _,cmdln: -1 != cmdln.find(kBackendMarkerArg))
    return res


##############################################################################
class BackEndClient(object):
    """A class for communicating with the back end."""
    ###########################################################
    def __init__(self):
        """BackEndClient constructor."""
        super(BackEndClient, self).__init__()
        self._proxy = None


    ###########################################################
    def connect(self, portFileDir=None):
        """Connect to the back end server

        @param  portFileDir  The name of the user local data dir; if None, we'll
                             ask wx (must have wx app made w/ right name!)
        @return connected    True if the connection completed
        """
        if portFileDir is None:
            portFileDir = getUserLocalDataDir()

        portFilePath = os.path.join(portFileDir, kPortFileName)
        try:
            transport = _BackEndTransport(portFilePath)
            proxy =  ServerProxyWithClientId("http://0.0.0.0:0", transport,
                                             allow_none=True)
            proxy.ping() #PYCHECKER OK: Function exists on xmlrpc server
            self._proxy = proxy
            return True
        except Exception:
            self._proxy = None

        return False


    ###########################################################
    def isConnected(self, needSameVersion=False):
        """Verify that a connection to the back end exists.

        @param  needSameVersion  If True, we'll check to make sure that the
                                 backend version matches ours.
        @return connected        True if we can communicate with the back end.
        """
        try:
            magic = self._proxy.ping()
        except Exception:
            return False

        if magic == 'dead':
            return False

        if needSameVersion:
            return magic == kMagicCommKey
        else:
            return True


    ###########################################################
    def quit(self, waitForSeconds=0, progressPulseFn=None):
        """Request that the back end app terminate.

        @param  waitForSeconds  We'll wait for this many seconds to see if the
                                backend actually quits.  If the backend has
                                quit within this time, we'll return success;
                                else we'll return failure.
        @param  progressPulseFn A function to call periodically while we're
                                waiting.  We don't know how long we're going
                                to wait, so we call this function with no args.
        @return didQuit         If True, we believe that the back end quit.
                                If False, it hasn't quit yet.
        """
        assert (self._proxy is not None)

        try:
            self._proxy.quit()
        except ExpatError:
            # We seem to get an xml error sometimes when we send the quit.
            # I'll just assume that this is because the other side closed the
            # socket a little prematurely, and everything is still OK.
            pass

        # Loop till they quit or we timeout...
        startTime = time.time()
        while (time.time() - startTime) < waitForSeconds:
            if ((not self.isConnected()) and (not getBackendProcesses())):
                return True

            if progressPulseFn is not None:
                progressPulseFn()
            time.sleep(.5)

        return False


    ############################################################
    def forceQuit(self, waitForSeconds=0, progressPulseFn=None):
        """Force quit the backend.

        @param  waitForSeconds  We'll wait for this many seconds to see if the
                                backend actually quits.  If the backend has
                                quit within this time, we'll return success;
                                else we'll return failure.
        @param  progressPulseFn A function to call periodically while we're
                                waiting.  We don't know how long we're going
                                to wait, so we call this function with no args.
        @return didQuit         If True, we believe that the back end quit.
                                If False, it hasn't quit yet.
        """

        # When running as a service we tell the launcher to do the termination
        # of processes for us ...
        if getServiceStartsBackend():
            launch = Launch()
            if not launch.open():
                return False
            try:
                if launch.do(0, True) is None:
                    return False
            finally:
                launch.close()
        else:
            # Try a kill
            strayProcesses = getBackendProcesses()
            strayProcesses.extend(getProcessesWithName(kWebcamExeName))
            for strayProcess in strayProcesses:
                try:
                    killProcess(strayProcess)
                except Exception:
                    # Just in case process quits itself by the time we get here...
                    pass

        # Loop till they quit or we timeout...
        startTime = time.time()
        while (time.time() - startTime) < waitForSeconds:
            if not getBackendProcesses():
                return True

            if progressPulseFn is not None:
                progressPulseFn()
            time.sleep(.5)

        return False


    ###########################################################
    def editQuery(self, query, origName, postMessage=True):
        """Edit a query.

        @param  query     The edited SavedQueryDataModel.
        @param  origName  The original query name.
        @param  postMessage  True if the back end should be notified.
        """
        queryPickle = cPickle.dumps(query)
        self._proxy.editQuery(
            origName, xmlrpclib.Binary(queryPickle), postMessage
        )


    ###########################################################
    def getQuery(self, queryName):
        """Retrieve a saved query.

        @param  queryName  The name of the query to retrieve.
        @return query      A SavedQueryDataModel or None.
        """
        pickledQuery = self._proxy.getQuery(queryName).data

        try:
            query = cPickle.loads(pickledQuery)
            return query
        except Exception:
            pass

        return None


    ############################################################
    def addRule(self, query, enabled):
        """Add or replace a rule

        @param  query    The query to build the rule from.
        @param  enabled  True if the new rule should be enabled.
        @return success  True if hte rule was added successfully.
        """
        s = cPickle.dumps(query)
        return self._proxy.addRule(xmlrpclib.Binary(s), enabled)


    ###########################################################
    def deleteRule(self, ruleName):
        """Delete an existing rule

        @param  ruleName  The name of the rule to delete.
        """
        self._proxy.deleteRule(ruleName)


    ###########################################################
    def getRuleNames(self):
        """Get the names of all saved rules.

        @return ruleNames  The names of the rules.
        """
        return self._proxy.getRuleNames()


    ###########################################################
    def getRule(self, ruleName):
        """Retrieve a saved rule.

        @param  ruleName  The name of the rule to retrieve.
        @return rule      A RuleDataModel or None.
        """
        pickledRule = self._proxy.getRule(ruleName).data

        try:
            rule = cPickle.loads(pickledRule)
            return rule
        except Exception:
            pass

        return None


    ###########################################################
    def setRuleSchedule(self, ruleName, schedule):
        """Set a saved rule's schedule.

        @param  ruleName  The name of the rule to update.
        @param  schedule  The schedule dict to apply to the rule.
        """
        self._proxy.setRuleSchedule(ruleName, schedule)


    ###########################################################
    def enableRule(self, ruleName, enable=True):
        """Set whether a rule is enabled or not.

        @param  ruleName  The name of the rule to update.
        @param  enable    True if the rule should be enabled.
        """
        self._proxy.enableRule(ruleName, enable)


    ###########################################################
    def getRuleInfoForLocation(self, location):
        """Retrieve a list of information about rules for a given location.

        @param  location  The name of the location to retrieve information on.
        @return infoList  A list of (ruleName, queryName, scheduleString,
                          isEnabled, responseNames) for each rule at location.
        """
        return self._proxy.getRuleInfoForLocation(location)


    ###########################################################
    def getRuleInfo(self, ruleName):
        """Retrieve a list of information about a rule.

        @param  ruleName  The name of the rule to retrieve information on.
        @return info      (ruleName, queryName, scheduleString, isEnabled,
                          responseNames) for the given rule or None.
        """
        return self._proxy.getRuleInfo(ruleName)


    ###########################################################
    def getStorageLocation(self):
        """Retrieve the location specified to store database files.

        @return location  The path at which to store database files.
        """
        location = self._proxy.getStorageLocation()

        if type(location) == str:
            location = location.decode('utf-8')

        return location


    ###########################################################
    def getVideoLocation(self):
        """Retrieve the location specified to store recorded video.

        @return location  The path at which to store recorded video.
        """
        location = self._proxy.getVideoLocation()

        if type(location) == str:
            location = location.decode('utf-8')

        return location


    ###########################################################
    def setVideoLocation(self, path, preserveData, keepExisting=False):
        """Set the location specified to store recorded video.

        @param  path          The path at which to store recorded video.
        @param  preserveData  If True existing data should be moved to the new
                              location.
        @param  keepExisting  If True and preserveData is False, data at the
                              new location will not be removed and the
                              databases will not be reset.
        """
        self._proxy.setVideoLocation(path, preserveData, keepExisting)


    ###########################################################
    def getVideoLocationChangeStatus(self):
        """Get the status of a video location change operation.

        @return finished  True if the operation has completed.
        @return success   True if the operation succeeded, False if failed.
        """
        return self._proxy.getVideoLocationChangeStatus()


    ###########################################################
    def getCameraLocations(self):
        """Retrieve the locations of all configured cameras.

        @return  camLocs  A list of camera locations.
        """
        return self._proxy.getCameraLocations()


    ###########################################################
    def addCamera(self, camLocation, camType, camUri, extra={}):
        """Add a new camera

        @param  camLocation  The location of the camera
        @param  camType      The camera's type
        @param  camUri       The uri used to access the camera
        @param  extra        An optional extra dictionary of settings.
        """
        self._proxy.addCamera(camLocation, camType, camUri, extra)



    ###########################################################
    def getHardwareDevicesList(self):
        return self._proxy.getHardwareDevicesList()

    ###########################################################
    def getHardwareDevice(self):
        return self._proxy.getHardwareDevice()

    ###########################################################
    def setHardwareDevice(self, dev):
        return self._proxy.setHardwareDevice(dev)

    ###########################################################
    def editCamera(self, origLocation, camLocation, camType, camUri,
                   changeTime, extra={}):
        """Edit a camera.

        @param  origLocation  The original location of the camera.
        @param  camLocation   The location of the camera.
        @param  camType       The camera's type.
        @param  camUri        The uri used to access the camera.
        @param  changeTime    The time the camera changed, in seconds.
        @param  extra         An optional extra dictionary of settings.
        """
        self._proxy.editCamera(origLocation, camLocation, camType, camUri,
                               changeTime, extra)


    ###########################################################
    def enableCamera(self, camLocation, enable=True):
        """Enable or disable a camera.

        @param  camLocation  The location of the camera to edit.
        @param  enable       True if the camera should be enabled.
        """
        self._proxy.enableCamera(camLocation, enable)


    ###########################################################
    def removeCamera(self, camLocation, removeData=False):
        """Remove a camera.

        @param  camLocation  The location of the camera to remove.
        @param  removeData   If true all queries and saved video associated with
                             this camera will be deleted.
        """
        self._proxy.removeCamera(camLocation, removeData)


    ###########################################################
    def getCameraSettings(self, camLocation):
        """Retrieve the settings of a given camera

        @param  camLocation  The location of the desired camera
        @return camType      The camera's type
        @return camUri       The uri used to access the camera
        @return enabled      True if the camera is enabled
        @return extra        An optional extra string of settings.
        """
        return self._proxy.getCameraSettings(camLocation)


    ###########################################################
    def setMaxStorageSize(self, maxSize):
        """Specify the maximum disk space to be used for video storage

        @param  maxSize  The maximum size in bytes to use for video storage
        """
        self._proxy.setMaxStorageSize(maxSize)


    ###########################################################
    def getMaxStorageSize(self):
        """Get the maximum disk space to be used for video storage.

        @return maxSize  The maximum size in bytes to use for video storage.
        """
        return self._proxy.getMaxStorageSize()


    ###########################################################
    def setCacheDuration(self, cacheDuration):
        """Specify the number of hours of cache to store.

        @param  cacheDuration  The maximum hours of cache to store.
        """
        self._proxy.setCacheDuration(cacheDuration)


    ###########################################################
    def getCacheDuration(self):
        """Get the number of hours of cache to store.

        @return cacheDuration  The maximum hours of cache to store.
        """
        return self._proxy.getCacheDuration()

    ###########################################################
    def setRecordInMemory(self, value):
        """Specify whether the record clips in memory or in temp location
        """
        self._proxy.setRecordInMemory(value)


    ###########################################################
    def getRecordInMemory(self):
        """Return whether the record clips in memory or in temp location
        """
        return self._proxy.getRecordInMemory()

    ###########################################################
    def setClipMergeThreshold(self, value):
        """Specify how clips will be merged during search
        """
        self._proxy.setClipMergeThreshold(value)


    ###########################################################
    def getClipMergeThreshold(self):
        """Return threshold determining whether clips will be merged during search in seconds
        """
        return self._proxy.getClipMergeThreshold()

    ###########################################################
    def setEmailSettings(self, emailSettings):
        """Set settings related to email.

        @param  emailSettings  A dict describing email settings; see
                               BackEndPrefs for details.
        """
        self._proxy.setEmailSettings(emailSettings)


    ###########################################################
    def getEmailSettings(self):
        """Retrieve settings related to email.

        @return emailSettings  A dict describing email settings; see
                               BackEndPrefs for details.
        """
        return self._proxy.getEmailSettings()


    ###########################################################
    def setFtpSettings(self, ftpSettings):
        """Set settings related to ftp.

        @param  ftpSettings    A dict describing ftp settings; see
                               BackEndPrefs for details.
        """
        self._proxy.setFtpSettings(ftpSettings)


    ###########################################################
    def getFtpSettings(self):
        """Retrieve settings related to ftp.

        @return ftpSettings    A dict describing ftp settings; see
                               BackEndPrefs for details.
        """
        return self._proxy.getFtpSettings()


    ###########################################################
    def setArmSettings(self, armSettings):
        """Set settings related to arming a camera.

        @param  armSettings  A dict describing arm settings; see
                             BackEndPrefs for details.
        """
        self._proxy.setArmSettings(armSettings)


    ###########################################################
    def getArmSettings(self):
        """Retrieve settings related to arming a camera.

        @return armSettings  A dict describing arm settings; see
                             BackEndPrefs for details.
        """
        return self._proxy.getArmSettings()


    ###########################################################
    def getPendingClipInfo(self, protocol):
        """Retrieve info about pending clips.

        @param  protocol       The protocol to query about.
        @return queueLength    The length of the queue of pending clips.
        @return startTime      The start time of the last clip sent; or None.
        @return stopTime       The stop time of the last clip sent; or None.
        @return processAtTime  The time that the last clip was requested to
                               be processed at (currently the time the clip
                               was intended to be put in the queue); or None.
        @return sentAtTime     The time that the last clip was marked as sent;
                               or None.
        @return ruleName       The name of the rule that was used to send
                               the last clip; or None.
        """
        # Unpickle from xmlrpclib.Binary, since XMLRPC doesn't support long int.
        pickledResult = self._proxy.getPendingClipInfo(protocol).data
        return cPickle.loads(pickledResult)


    ###########################################################
    def purgePendingClips(self, protocol):
        """Purge all pending clips.

        @param  protocol       The protocol to purge.
        """
        self._proxy.purgePendingClips(protocol)


    ###########################################################
    def addVideosToImport(self, videoPaths):
        """Add the given video paths to the list of ones to import.

        @param  videoPaths  A list of videos to import.
        """
        self._proxy.addVideosToImport(videoPaths)


    ###########################################################
    def stopAllImports(self):
        """Stop all imports that are currently happening."""
        self._proxy.stopAllImports()


    ###########################################################
    def getImportStatusMessages(self):
        """Return all import status messages that have been posted.

        The front end calls this to get the messages that the back end posted.

        @return messageList  The list of messages that were posted.
        """
        return self._proxy.getImportStatusMessages()


    ###########################################################
    def getLocalCameraNames(self):
        """Get a list of the names of cameras on the local system.

        @return cameraNames  A list of names of the connected cameras
        """
        return self._proxy.getLocalCameraNames()


    ###########################################################
    def enableLiveView(self, cameraLocation, enable=True):
        """Enable or disable the live viewing of a camera

        @param  cameraLocation  The camera to enable or disable viewing for.
        @param  enable          True if viewing should be enabled.
        """
        return self._proxy.enableLiveView(cameraLocation, enable)


    ###########################################################
    def setLiveViewParams(self, cameraLocation, width, height, audioVolume,
                           fps):
        """Set the camera currently active in the monitor view.

        @param  cameraLocation  The camera active in the monitor view.
        @param  width           Requested width of large frames.
        @param  height          Requested height of large frames.
        @param  audioVolume     Volume to render audio at, or 0 to mute
        @param  fps             Frames per second, or 0 for unlimited
        """
        return self._proxy.setLiveViewParams(cameraLocation, width, height,
                                              audioVolume, fps)


    ###########################################################
    def flushVideo(self, cameraLocation):
        """Force a camera to formalize any temporary files.

        @param  cameraLocation  The camera to flush.
        @return lastProcessedMs  The last processed ms.
        @return lastTaggedMs     The last ms tagged for saving.
        """
        pSec, pMs, tSec, tMs = self._proxy.flushVideo(cameraLocation)
        return pSec*1000+pMs, tSec*1000+tMs


    ###########################################################
    def getCameraStatus(self, cameraLocation):
        """Get the status of a camera.

        @param  cameraLocation  The camera to update.
        @return status          The status of the camera.
        """
        return self._proxy.getCameraStatus(cameraLocation)


    ###########################################################
    def getCameraStatusAndEnabled(self, cameraLocation):
        """Get the status of a camera.

        @param  cameraLocation  The camera to update.
        @return status          The status of the camera.
        @return isEnabled       True if the camera is enabled.
        """
        return self._proxy.getCameraStatusAndEnabled(cameraLocation)


    ###########################################################
    def getCameraStatusAndReason(self, cameraLocation):
        """Get the status of a camera.

        @param  cameraLocation  The camera to update.
        @return status          The status of the camera and reason, if available.
        @return reason          Failure reason, if available, or None
        """
        return self._proxy.getCameraStatusAndReason(cameraLocation)


    ###########################################################
    def getCameraStatusEnabledAndReason(self, cameraLocation):
        """Get the status of a camera.

        @param  cameraLocation  The camera to update.
        @return status          The status of the camera.
        @return reason          Failure reason, if available, or None
        @return isEnabled       True if the camera is enabled.
        """
        return self._proxy.getCameraStatusEnabledAndReason(cameraLocation)


    ###########################################################
    def getActiveResponseTypes(self, ruleName):
        """Get the status of a camera.

        @param  ruleName        Name of the rule to fetch.
        @return activeReponses  A list of active response types.
        """
        return self._proxy.getActiveResponseTypes(ruleName)


    ###########################################################
    def startCameraTest(self, uri, forceTCP):
        """Begin streaming from a camera.

        @param  uri       The uri of the camera to stream
        @param  forceTCP  True to force TCP.
        """
        self._proxy.startCameraTest(uri, forceTCP)


    ###########################################################
    def stopCameraTest(self):
        """Stop any camera testing."""
        self._proxy.stopCameraTest()


    ###########################################################
    def testCameraFailed(self):
        """Retrieve whether the test camera failed connecting or not.

        @return failed  True if the test camera is marked as failed.
        """
        return self._proxy.testCameraFailed()


    ###########################################################
    def startPacketCapture(self, cameraLocation, delaySeconds, pcapDir):
        """

        @param  cameraLocation
        @param  delaySeconds
        """
        self._proxy.startPacketCapture(cameraLocation, delaySeconds, pcapDir)


    ###########################################################
    def stopPacketCapture(self):
        """Stop capturing packets from camera."""
        self._proxy.stopPacketCapture()


    ###########################################################
    def getPacketCaptureInfo(self):
        """Get the current status of the packet capture stream.

        @return info    A pickled empty dictionary, or a dictionary with two
                        keys, "pcapEnabled" and "pcapStatus", where their values
                        can be None or integers representing the current state
                        of the pcap process.
        """
        return cPickle.loads(self._proxy.getPacketCaptureInfo())


    ###########################################################
    def deleteVideo(self, cameraLocation, startSec, stopSec, quick):
        """Remove all stored data from a camera between two times.

        @param  cameraLocation  The camera location to delete from.
        @param  startSec        The start time in seconds to begin delting.
        @param  stopSec         The stop time in seconds to stop deleting.
        @param  quick           True if a quick delete should be performed.
        """
        self._proxy.deleteVideo(cameraLocation, startSec, stopSec, quick)


    ###########################################################
    def getUpnpDevices(self):
        """Get the UPNP devices.

        Return all of the UPNP devices found.  See _setUpnpDevices() for
        details.  One word of note from that function's comments: don't use
        'isExpired' on these devices--it may not be valid.

        @return pickedUpnpDeviceDict  A pickled dict of UpnpDevice objects.
                                      Keyed by usn.
        """
        return self._proxy.getUpnpDevices().data


    ###########################################################
    def getUpnpDictRevNum(self):
        """Get the revision number of the UPNP device dict.

        This can be useful so we don't have to transfer quite as much data
        while polling.

        @return upnpDictRevNum  The revision of the UPNP device dict.
        """
        return self._proxy.getUpnpDictRevNum()


    ###########################################################
    def getOnvifDevices(self):
        """Get the ONVIF devices.

        Return all of the ONVIF devices found.  See _setOnvifDevices() for
        details.

        @return pickedOnvifDeviceDict  A pickled dict of OnvifDevice objects.
                                       Keyed by uuid.
        """
        return self._proxy.getOnvifDevices().data


    ###########################################################
    def getOnvifDictRevNum(self):
        """Get the revision number of the ONVIF device dict.

        This can be useful so we don't have to transfer quite as much data
        while polling.

        @return onvifDictRevNum  The revision of the ONVIF device dict.
        """
        return self._proxy.getOnvifDictRevNum()


    ###########################################################
    def setOnvifSettings(self, uuid, selectedIp, username, password):
        """Sets the authentication information for an ONVIF device so we can
        retrieve its stream URI's and profiles.

        @param uuid        The unique identifier of the ONVIF device.
        @param selectedIp  The device's IP address that we want to communicate with.
        @param username    The username that has access to the stream URI's and
                           profiles that we want.
        @param password    Password to the username.
        """
        self._proxy.setOnvifSettings(uuid, selectedIp, username, password)


    ###########################################################
    def activeCameraSearch(self, isMajor=False):
        """Actively search for cameras.

        This will actively search the computer for more cameras.  After this is
        called, it's likely more UPNP and ONVIF cameras or local cameras
        will show up in other calls.

        @param  isMajor  If True, do a more major, heavyweight search. This is
                         done once when the "Edit Camera" dialog comes up. After
                         that, we'll do more minor searches once every 5 seconds
        """
        return self._proxy.activeCameraSearch(isMajor)


    ###########################################################
    def getMessage(self):
        """Get the next pending message.

        @return message  A list, the first entry of which is from MessageIds.
        """
        return self._proxy.getMessage()

    ###########################################################
    def submitClipToSighthound(self, camLocation, note, startTime, duration):
        """Submit clip to Sighthound for analysing."""
        endTime = startTime + duration
        return self._proxy.remoteSubmitClipToSighthound(camLocation,
                                    note,
                                    (startTime/1000, startTime%1000),
                                    (endTime/1000, endTime%1000))


    ###########################################################
    def sendCorruptDbMessage(self):
        """Notify the back end of a corrupt database."""
        return self._proxy.sendCorruptDbMessage()


    ###########################################################
    def enableNotifications(self):
        """Enable push notifications.

        @return success  True if enable was successful.
        """
        return self._proxy.enableNotifications(True, False)[0]


    ###########################################################
    def getWebUser(self):
        """ Get the currently configured user name for web server access.

        @return The user name for web server basic authentication.
        """
        return self._proxy.getWebUser()


    ###########################################################
    def setWebAuth(self, user, passw):
        """ Set the credentials for web server access. The server will be
        restarted if it has been running already.

        @param user The user name.
        @param passw The password."""
        self._proxy.setWebAuth(user, passw)


    ###########################################################
    def getWebPort(self):
        """ Get the currently configured port the web server will be listening
            on all interfaces/addresses.

        @return The web server port, or -1 if the server is turned off."""
        return self._proxy.getWebPort()


    ###########################################################
    def setWebPort(self, port):
        """ Sets the web server port, server will be restarted.

        @param port the new web server port. Use -1 to turn the server off.
        """
        self._proxy.setWebPort(port)

    ###########################################################
    def getVideoSetting(self, name):
        """Retrieve the remote access stream bitrates.

        @param  name         Name of the setting
        @return value        Value of the setting
        """
        return self._proxy.getVideoSetting(name)


    ###########################################################
    def setVideoSetting(self, name, value):
        """Set the remote access stream bitrates.

        @param  name         Name of the setting
        @param  value        Value of the setting
        """
        return self._proxy.setVideoSetting(name, value)


    ###########################################################
    def getStreamBitrates(self):
        """Retrieve the remote access stream bitrates.

        @return liveBitrate  The bit rate for live streams.
        @return clipBitrate  The bit rate for clip streams.
        """
        return self._proxy.getStreamBitrates()


    ###########################################################
    def setStreamBitrates(self, liveBitrate, clipBitrate):
        """Set the remote access stream bitrates.

        @param  liveBitrate  The bit rate for live streams.
        @param  clipBitrate  The bit rate for clip streams.
        """
        return self._proxy.setStreamBitrates(liveBitrate, clipBitrate)


    ###########################################################
    def getTimestampEnabledForClips(self):
        """Retrieve the remote access setting

        @return value        value of the setting
        """
        return self._proxy.getTimestampEnabledForClips()


    ###########################################################
    def setTimestampEnabledForClips(self, val):
        """Set the remote access setting.

        @param  val          Value of the setting
        """
        return self._proxy.setTimestampEnabledForClips(val)


    ###########################################################
    def getBoundingBoxesEnabledForClips(self):
        """Retrieve the remote access setting

        @return value        value of the setting
        """
        return self._proxy.getBoundingBoxesEnabledForClips()


    ###########################################################
    def setBoundingBoxesEnabledForClips(self, val):
        """Set the remote access setting.

        @param  val          Value of the setting
        """
        return self._proxy.setBoundingBoxesEnabledForClips(val)


    ###########################################################
    def enablePortOpener(self, enabled):
        """ Enables or disables the port opener (for the web server).

        @param enabled True to enable it, false to disable.
        """
        return self._proxy.enablePortOpener(enabled)


    ###########################################################
    def isPortOpenerEnabled(self):
        """ Checks whether the port opener is enabled.

        @return True if port opening attempts are happening, false if not.
        """
        return bool(self._proxy.isPortOpenerEnabled())


    ###########################################################
    def memstoreGet(self, key, timeout=0, oldVersion=-1):
        """ Gets data from the in-memory store.

        @param key Name (string) of the item to retrieve.
        @param timeout Number of seconds to wait for an item to appear/update.
        @param oldVersion Former version or -1 to get whatever is present.
        @return The requested item (data, version) or None if not found.
        """
        return self._proxy.memstoreGet(key, timeout, oldVersion)


    ###########################################################
    def memstorePut(self, key, data, ttl=-1):
        """ Puts data from into the in-memory store.

        @param key Name (string) of the item to create or update.
        @param data The data to store, must be able to persist via pickle
        @param ttl Expiration time in seconds, -1 for no expiration.
        @return The version number of the new data item.
        """
        return self._proxy.memstorePut(key, data, ttl)


    ###########################################################
    def memstoreRemove(self, key):
        """ Removes data from the in-memory store.

        @param key Name (string) of the item to remove.
        @return The removed data item (data, version) or None if not found.
        """
        return self._proxy.memstoreRemove(key)


    ###########################################################
    def userLogin(self, user, password):
        """ Initiate a new login attempt by user-provided credentials.

        @param user The user name.
        @param password The password.
        @return Operation identifier, under which in the memstore the result
                will then be available. Either as (True, short-token) or
                (False, error-message). Lifetime of the result is limited.
        """
        return self._proxy.userLogin(user, password)


    ###########################################################
    def userLogout(self):
        """Log out the current user."""
        return self._proxy.userLogout()


    ###########################################################
    def refreshLicenseList(self):
        """ Starts a request to refresh a list of all available licenses.

        @return Operation identifier, under which in the memstore the result
                will then be available. Either as (True, license-list) or
                (False, error-message). Lifetime of the result is limited.
        """
        return self._proxy.refreshLicenseList()


    ###########################################################
    def acquireLicense(self, serial):
        """ Initiates the acquisition of a license.

        @param serial The serial number of the license.
        @return Operation identifier, under which in the memstore the result
                will then be available. Either as (True, license-dict) or
                (False, error-message). Lifetime of the result is limited.
        """
        return self._proxy.acquireLicense(serial)


    ###########################################################
    def unlinkLicense(self):
        """ Unlinks the current license, goes back to starter.

        @return Operation identifier, under which in the memstore the result
                will then be available. Either as (True, info-text) or
                (False, error-message). Lifetime of the result is limited.
        """
        return self._proxy.unlinkLicense()


    ###########################################################
    def getLicenseData(self, timeout=0):
        """ Returns the current license data dictionary.

        @param timeout How long to wait for data to show up, in seconds.
        @return None if no data is available (which is a really serious issue
        and should normally never happen), otherwise the license dictionary.
        """
        item = self.memstoreGet(kMemStoreLicenseData, timeout)
        if item is not None:
            return item[0]
        return None


    ###########################################################
    def getLoginStatus(self):
        """ Returns the login status, unconditionally and immediately.

        @return statusDict  A dictionary containing the login status with keys
                            kLoginStatusAccountId, kLoginStatusFailed,
                            kLoginStatusLastUser, kLoginStatusMachineId and
                            kLoginStatusToken.
        """
        result = self.memstoreGet(kMemStoreLicenseLoginStatus)[0]
        if kLoginStatusToken in result:
            token = result[kLoginStatusToken]
            if token:
                result[kLoginStatusToken] = Obfuscate.load(token)
        return result


    ###########################################################
    def setTimePreferences(self, use12Hour, useUSDate):
        """Set settings related to time display.

        @param  use12Hour  True if 12 hour time should be used.
        @param  useUSDate  True if a US date format should be used.
        """
        self._proxy.setTimePreferences(use12Hour, useUSDate)


    ###########################################################
    def getTimePreferences(self):
        """Retrieve settings related to time display.

        @return use12Hour  True if 12 hour time should be used.
        @return useUSDate  True if a US date format should be used.
        """
        return self._proxy.getTimePreferences()


    ###########################################################
    def sendIftttMessage(self, camera, rule, triggerTime):
        """Queue an IFTTT message for sending.

        This is only used for testing from the front end.

        @param  camera       The camera name to use for the trigger.
        @param  rule         The rule name to use for the trigger.
        @param  triggerTime  The time in epoch seconds to use for the trigger.
        """
        return self._proxy.sendIftttMessage(camera, rule, triggerTime)


    ###########################################################
    def sendIftttRulesAndCameras(self, extraRules, extraCameras):
        """Retrieve and send rules and cameras configured for use with IFTTT.

        @param  extraRules    An extra list of rules to include.
        @param  extraCameras  An extra list of cameras to include.
        """
        return self._proxy.sendIftttRulesAndCameras(extraRules, extraCameras)


    ###########################################################
    def launchedByService(self):
        """ Checks whether the backend got launched by the service.

        @return  True if the service launched all of the backend processes.
        """
        return self._proxy.launchedByService()

    ###########################################################
    def setDebugConfiguration(self, config):
        """Set debug settings

        @param  config    Dictionary with configuration
        """
        self._proxy.setDebugConfiguration(config)



##############################################################################
class _BackEndTransport(xmlrpclib.Transport):
    """A subclass of Transport that connects to the right place.

    Effectively, we ignore the "host" that is passed into the XMLRPC stuff.
    We'll always connect to localhost and will connect to the port specified
    in the port file.  If the connection ever fails, we'll double-check the
    port file and redo the request (once).
    """

    ###########################################################
    def __init__(self, portFilePath, use_datetime=0):
        """_BackEndTransport constructor.

        This will raise an exception if the port file doesn't exist or can't
        be read.

        @param  portFilePath  The path to the file where the port is stored.
        @param  use_datetime  Passed to our superclass; see xmlrpclib.
        """
        self.__portFilePath = portFilePath
        self.__host = None
        xmlrpclib.Transport.__init__(self, use_datetime)

        # Call this right now so we throw an exception if there's a problem...
        self.__host = self.__figureOutHost()


    ###########################################################
    def request(self, host, *args, **kwargs): #PYCHECKER OK: Using args and kwargs
        """Issue an XMLRPC request.

        If we get a socket error, we'll re-read the port file and retry once.
        Any other exceptions (including an exception re-reading the port file)
        will be passed up to the caller.

        @param  host          Ignored; expect to be 0.0.0.0:0
        @param  args          Passed to superclass.
        @param  kwargs        Passed to superclass.
        @return result        From superclass.
        """
        assert host == '0.0.0.0:0', "Expected bogus host, not '%s'" % str(host)

        try:
            return xmlrpclib.Transport.request(self, self.__host,
                                               *args, **kwargs)
        except socket.error:
            self.__host = self.__figureOutHost()
            return xmlrpclib.Transport.request(self, self.__host,
                                               *args, **kwargs)


    ###########################################################
    def __figureOutHost(self):
        """Read the port from our port file and combine with 127.0.0.1.

        This will raise an exception if the file can't be read...

        @return host          The host to connect to.
        """
        try:
            portFile = open(self.__portFilePath, 'r')
        except IOError:
            # Give a little nicer error...
            raise RuntimeError("Missing port file opening " + self.__portFilePath)

        try:
            port = cPickle.load(portFile)
        except Exception:
            raise RuntimeError("Bad port file contents")

        portFile.close()

        return "127.0.0.1:%s" % str(port)



##############################################################################
def _simpleProgressPulse():
    """A simple progress function that just prints a period and flushes it."""
    sys.stdout.write(".")
    sys.stdout.flush()


##############################################################################
def sendCommand(command='status', portFileDir=None):
    """Main program, allowing a few commands to be run from command line.

    @param  command      Either 'status' or 'quit'.
    @param  portFileDir  The name of the user local data dir; if None, we'll
                         make a wx app and ask wx.
    """
    # Need to create a front end app, including giving it a name.  This
    # makes "FrontEndUtils.getUserLocalDataDir()" work properly...
    from FrontEndApp import kAppName

    if portFileDir is None:
        app = wx.App(False)
        app.SetAppName(kAppName)

    client = BackEndClient()
    didConnect = client.connect(portFileDir)

    if command == 'status':
        if didConnect:
            print "Back end is running."
        else:
            print "Back end is not running."
    elif command == 'quit':
        didQuit = False

        if didConnect:
            sys.stdout.write("Quitting back end...")
            sys.stdout.flush()
            didQuit = client.quit(15, _simpleProgressPulse)

        if didQuit:
            print "\n...OK, backend was quit."
        else:
            if didConnect:
                print "\n...WARNING: Backend didn't quit gracefully..."

            if didConnect or getBackendProcesses():
                sys.stdout.write("Forcing stray back end processes to quit...")
                sys.stdout.flush()
                didQuit = client.forceQuit(10, _simpleProgressPulse)
                if didQuit:
                    print "\n...OK, backend was forced to quit."
                else:
                    print "\n...ERROR: backend failed to quit."
            else:
                print "Back end wasn't running."


##############################################################################
class LicenseBackEndClient():
    """ Helper class to deal with license calls and result retrieval. Does not
    do much more than keeping operation IDs, so start and complete methods are
    in one context. If you want to run requests of the same kind in parallel
    simply use multiple instances of this class.
    """

    ###########################################################
    def __init__(self, backEndClient):
        """ Constructor.

        @param backEndClient The backend client instance to use.
        """
        self._backEndClient = backEndClient
        self._opidLogin = None
        self._opidRefreshList = None
        self._opidAcquire = None
        self._opidUnlink = None


    ###########################################################
    def _complete(self, opid, timeout):
        """ Try to completes an operation.

        @param opid The operation ID.
        @param opid Timeout in seconds.
        @return None if no result is available yet, otherwise the result value.
        """
        item = self._backEndClient.memstoreGet(opid, timeout)
        if item is None:
            return None
        return item[0]


    ###########################################################
    def login(self, user, password):
        """ Starts the login to the license server, so we can then talk to it
        regarding license acquisition and license listing.

        @param user The user name (e-mail).
        @param password The password.
        """
        self._opidLogin = self._backEndClient.userLogin(user, password)


    ###########################################################
    def loginComplete(self, timeout):
        """ Returns the login status as a result of a login attempt.

        @param timeout Number of seconds willing to wait for the new status to
                       show up. Zero for polling.
        @return        None if the last login operation has not completed yet.
                       (True, short-token) if the login succeeded. (False,
                       error-text) if the attempt failed.
        """
        return self._complete(self._opidLogin, timeout)


    ###########################################################
    def refreshList(self):
        """ Starts a request to refresh a list of all available licenses.
        """
        self._opidRefreshList = self._backEndClient.refreshLicenseList()


    ###########################################################
    def refreshListComplete(self, timeout):
        """ Returns a license list updated after the last list refresh call.

        @param  timeout  Number of seconds to wait for the refresh.
        @return complete None if no updated data is available. (False, error) if
                         an error happened. (True, list-of-dicts) if a new
                         license list got received.
        """
        return self._complete(self._opidRefreshList, timeout)


    ###########################################################
    def acquire(self, serialNumber):
        """ Starts a license acquisition request.

        @param serialNumber The serial number of the license to acquire.
        """
        self._opidAcquire = self._backEndClient.acquireLicense(serialNumber)


    ###########################################################
    def acquireComplete(self, timeout):
        """ Returns license data updated after the last acquisition call.

        @param  timeout  Number of seconds to wait for the refresh.
        @return complete None if no updated data is available. (False, error) if
                         an error got detected. (True, license-dict) if new
                         license data got received.
        """
        return self._complete(self._opidAcquire, timeout)


    ###########################################################
    def unlink(self):
        """ Starts a license unlink request.
        """
        self._opidUnlink = self._backEndClient.unlinkLicense()


    ###########################################################
    def unlinkComplete(self, timeout):
        """ Returns after an unlink operation finished.

        @param  timeout  Number of seconds to wait for the refresh.
        @return complete None if no updated data is available. (False, error) if
                         an error got detected. (True, info-text) if the unlink
                         operation succeeded.
        """
        return self._complete(self._opidUnlink, timeout)



##############################################################################
if __name__ == '__main__':
    sendCommand(*(sys.argv[1:]))
