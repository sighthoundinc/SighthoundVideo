#! /usr/local/bin/python

#*****************************************************************************
#
# BackEndApp.py
#   Core orchestration process.
#   Responsible for spawning and communicating with all the other processes of the app.
#   Receives analytics data from camera processes, and persists it in the database,
#   as well as performs real-time searches and initiates responses.
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


"""
## @file
Contains the BackEndApp class.
"""

# Python imports...
import bisect
import cPickle
import errno
import logging
import operator
from Queue import Empty as QueueEmpty
from multiprocessing import Pipe, Queue
from Queue import PriorityQueue
import os
from signal import SIGTERM
from socket import timeout as sockettimeout
import shutil
from sqlite3 import DatabaseError
import sys
import time
import traceback
import xmlrpclib
import multiprocessing
import hashlib
import ssl

from collections import deque

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.networking.SanitizeUrl import sanitizeUrl
from vitaToolbox.networking.XmlRpcUtils import TimeoutTransport
from vitaToolbox.networking.Upnp import ControlPointManager
from vitaToolbox.networking.Upnp import extractUsnFromUpnpUrl
from vitaToolbox.networking.Upnp import isUpnpUrl
from vitaToolbox.networking.Upnp import realizeUpnpUrl
from vitaToolbox.networking.Onvif import OnvifDeviceManager
from vitaToolbox.networking.Onvif import extractUuidFromOnvifUrl
from vitaToolbox.networking.Onvif import isOnvifUrl
from vitaToolbox.networking.Onvif import realizeOnvifUrl
from vitaToolbox.path.PathUtils import normalizePath
from vitaToolbox.path.VolumeUtils import getVolumeNameAndType
from vitaToolbox.path.VolumeUtils import isRemotePath
from vitaToolbox.path.GetDiskSpaceAvailable import checkFreeSpace
from vitaToolbox.windows.winUtils import registerForForcedQuitEvents
from vitaToolbox.sysUtils.MachineId import machineId
from vitaToolbox.sysUtils.TimeUtils import getTimeAsMs
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8
from vitaToolbox.threading.ThreadPool import ThreadPool
from vitaToolbox.process.ProcessUtils import listChildProcessesOfPID
from vitaToolbox.profiling.QueueStats import QueueStats

# Local imports...
from appCommon.CommonStrings import kPortFileName, isLocalCamera
from appCommon.CommonStrings import kRuleDir, kRuleExt, kQueryExt
from appCommon.CommonStrings import kPrefsFile, kCamDbFile
from appCommon.CommonStrings import kAnyCameraStr
from appCommon.CommonStrings import kCameraUndefined, kCameraOn, kCameraOff
from appCommon.CommonStrings import kCameraConnecting, kCameraFailed
from appCommon.CommonStrings import kEmailResponse, kRecordResponse
from appCommon.CommonStrings import kSoundResponse, kCommandResponse
from appCommon.CommonStrings import kFtpResponse, kPushResponse
from appCommon.CommonStrings import kIftttResponse
from appCommon.CommonStrings import kWebhookResponse
from appCommon.CommonStrings import kFtpProtocol
from appCommon.CommonStrings import kLocalExportProtocol
from appCommon.CommonStrings import kLocalExportResponse
from appCommon.CommonStrings import kTestLiveFileName
from appCommon.CommonStrings import kCorruptDbErrorStrings
from appCommon.CommonStrings import kVideoFolder, kRemoteFolder
from appCommon.CommonStrings import kWebDirName
from appCommon.CommonStrings import kWebDirEnvVar
from appCommon.CommonStrings import kMemStoreBackendReady
from appCommon.CommonStrings import kMemStoreRulesLock
from appCommon.CommonStrings import kSupportEmail
from appCommon.CommonStrings import kClipDbFile
from appCommon.CommonStrings import kResponseDbFile
from appCommon.CommonStrings import kObjDbFile
from appCommon.CommonStrings import kDefaultRecordSize, kMaxRecordSize
from appCommon.CommonStrings import kMatchSourceSize
from appCommon.CommonStrings import kExecAlertThreshold
from appCommon.CommonStrings import kOpenSourceVersion
from appCommon.LicenseUtils import hasPaidEdition
from appCommon.LicenseUtils import kCamerasField
from appCommon.SearchUtils import parseSearchResults
from appCommon.XmlRpcClientIdWrappers import ServerProxyWithClientId
from appCommon.DbRecovery import setCorruptDatabaseStatus
from appCommon.DbRecovery import getCorruptDatabaseStatus
from appCommon.DbRecovery import runDatabaseRecovery
from appCommon.DbRecovery import kStatusRecover
from appCommon.DbRecovery import kStatusReset
from appCommon.DebugPrefs import getDebugPrefAsInt, getDebugPrefAsFloat
from BackEndPrefs import BackEndPrefs
from BackEndPrefs import kLiveMaxBitrate
from BackEndPrefs import kLiveEnableTimestamp
from BackEndPrefs import kLiveMaxResolution
from BackEndPrefs import kClipResolution
from BackEndPrefs import kLiveEnableFastStart
from BackEndPrefs import kGenThumbnailResolution
from BackEndPrefs import kFpsLimit
from BackEndPrefs import kRecordInMemory, kClipMergeThreshold, kHardwareAccelerationDevice
from BackEndProcessJumper import startCapture
from BackEndProcessJumper import startDiskCleaner
from BackEndProcessJumper import startNetworkMessageServer
from BackEndProcessJumper import startResponseRunner
from BackEndProcessJumper import startStream
from BackEndProcessJumper import startWebServer
from BackEndProcessJumper import startPacketCapture
from BackEndProcessJumper import startPlatformHTTPWrapper
from CameraManager import CameraManager
from ClipManager import ClipManager
from DataManager import DataManager
from DebugLogManager import DebugLogManager
if kOpenSourceVersion:
    from LicenseManagerOSS import LicenseManager
else:
    from LicenseManager import LicenseManager
from ClipUploader import ClipUploader
import MessageIds
from ResponseDbManager import ResponseDbManager
from responses.CommandResponse import CommandResponse
from responses.EmailResponse import EmailResponse
from responses.WebhookResponse import WebhookResponse
from responses.PushResponse import PushResponse
from responses.IftttResponse import IftttResponse
from responses.RecordResponse import RecordResponse
from responses.SoundResponse import SoundResponse
from responses.SendClipResponse import SendClipResponse
from videoLib2.python.ClipReader import ClipReader, getMsList
from videoLib2.python.StreamReader import getLocalCameraNames as strmGetLocalCameraNames
from videoLib2.python.StreamReader import getHardwareDevicesList as getHardwareDevicesList
from WebServer import killWebServerProcesses
from launch.Launch import Launch
from launch.Launch import serviceAvailable
from appCommon.hostedServices.IftttClient import IftttClient
from SavedQueryDataModel import convertOld2NewSavedQueryDataModel
from NetworkScanner import NetworkScanner, OnvifNetworkScanner



# We need to check for instances of WindowsError but it's not defined on osx.
try:
    WindowsError #PYCHECKER OK: Line does have effect in context of surrounding.
except NameError:
    WindowsError = None


# Constants...

_kTmpFolder = 'tmp'
_kCameraCheckInterval = 10
_kLogName = "BackEndApp.log"
_kLogSize = 1024*1024*5
_kOnvifLogName = "Onvif.log"
_kOnvifLogSize = 1024 * 1024 * 2
_kUpnpLogName = "Upnp.log"
_kUpnpLogSize = 1024 * 1024 * 2
_kPipeCleanupWait = 60*5
_kMinimumSearchDelayMs = 1000

# After stopping a camera, we'll tell responses to flush after this many secs.
_kResponseFlushTime = 60

_kMaxIdleDelay = 15

# If we've had a pending search for longer than this many seconds, we'll do it.
_kStaleRealtimeSearchSeconds = 5

# If a camera hasn't responded in longer than this many seconds we assume it
# has eternally stalled.
_kCameraTimeout = 240

# If a response runner hasn't responded in longer than this many seconds we
# assume it has eternally stalled.  Go a little on the long end here since
# the ResponseRunner has some long sleeps in it (TODO: needed?)
_kResponseRunnerTimeout = 300

# We'll ping the NMS every X seconds to let it know we're still around.
_kMessageServerPingTime = 120

# We'll delete rules associated with a camera this long after we remove the
# camera to give any pending information time to be processed.
_kRuleCleanupTimeout = 120

# If a temp video file could not be moved we'll try again for this many seconds
# before giving up and deleting it.
_kTmpFileLifetime = 20*60

# We won't give UPNP time more than every this many seconds...
_kFastestUpnpPoll = 2.0

# UPnP shouldn't take longer than this...
_kSlowUpupTime = _kFastestUpnpPoll / 2

# We won't give ONVIF time more than every this many seconds...
_kFastestOnvifPoll = 2.0

# ONVIF shouldn't take longer than this...
_kSlowOnvifTime = _kFastestOnvifPoll / 2

# Timeouts for waiting for quit during cleanup...
_kCamQuitTimeout = 5
_kDiskCleanerQuitTimeout = 22  # Just lower than front end's timeout
_kWebServerQuitTimeout = 5

# Number of worker threads for the (global) thread-pool.
_kThreadPoolSize = multiprocessing.cpu_count() * 4

# Timeout for communicating with the network message server. If we exceed this
# we assume it is hung and destroy the world.
_kNetworkMessageServerTimeout = 300

# Timeout to deliver the shutdown message to the NMS.
_kNmsShutdownTimeout = 2

# Current logging configuration
_kDebugConfig = None

# Globals...

# Keep a reference to the current instance, for the forced quit callback to use.
_app = None


_kFakeMessageIdDataManagerIdleProcessing = 90000
_kFakeMessageIdRealTimeSearch            = 90001
_kFakeMessageIPCUtility                  = 90002
_kFakeMessageIPCCamera                   = 90003

# Queue statistics constants
_kStatsDefaultInterval = 60*60 # by default, log stats every hour
_kStatsMaxQueue = 50        # consider queue size over 50 an error
_kStatsMaxExecTime = 0.2    # consider any event processing over 0.2s an error
_kStatsAlertInterval = 10   # log an alert every 10s at most

##############################################################################
class NetworkScannerCallback(object):
    def __init__(self, msgId, q):
        self._msgId = msgId
        self._queue = q

    def onUpdate(self, allDevices, changedDevices, goneDevices):
        self._queue.put([self._msgId, allDevices, changedDevices, goneDevices])

##############################################################################
class BackEndApp(object):
    """The main application class for the back end."""
    ###########################################################
    def __init__(self, userLocalDataDir):
        """Initialize BackEndApp.

        @param  userLocalDataDir  The directory in which to store app data.
        """
        # Call the superclass constructor.
        super(BackEndApp, self).__init__()

        self._cleanedUp = False
        self._upnpDevices = {}
        self._upnpScanner = None
        self._upnpLogger = None
        self._onvifDevices = {}
        self._onvifScanner = None
        self._onvifLogger = None


        self._netMsgServerProc = None
        self._diskCleanupProc = None
        self._diskCleanupQueue = None
        self._webServerProc = None
        self._webServerQueue = None
        self._platformHTTPWrapperProc = None
        self._responseRunnerProc = None
        self._responseRunnerQueue = None

        # Setup logging...  SHOULD BE FIRST!
        self._userLocalDataDir = userLocalDataDir
        self._logDir = os.path.join(self._userLocalDataDir, "logs")
        self._logger = getLogger(_kLogName, self._logDir, _kLogSize)
        self._logger.grabStdStreams()

        assert type(self._userLocalDataDir) == unicode

        self._threadPool = ThreadPool(_kThreadPoolSize)

        self._iftttStatePending = None  # state to be sent
        self._iftttStateSending = False # some state is currently being sent
        self._iftttStateCleared = None  # state got set to empty on the server
        self._iftttLastStateOut = None  # the last state sent (successfully)

        # Key = Camera Location
        # value = (process, cameraPipe, dataMgrPipeId, lastPingTime)
        self._captureStreams = {}
        # Key = id, value = data manager pipe
        self._dataMgrPipes = {}
        self._nextPipeId = 0
        self._analyticsPort = None

        self._disableDiskCleanup = os.path.exists(
                                        os.path.join(self._userLocalDataDir,
                                                     'nocleanup'))
        # Key = Camera Location
        # value = (uri, isEnabled, isBeingMonitored, extraDict)
        self._cameraInfo = {}

        # Key = Camera Location
        # value = (procWidth, procHeight)
        self._cameraProcSizes = {}

        # Key = Camera Location
        # value = {key=sessionUid, value=lastPing}
        self._cameraJpegList = {}

        # Key = camera location, value = ruleDict:
        #    key = ruleName, value = (rule, isScheduled, nextSchedChange, query,
        #                             responseList)
        self._ruleDicts = {}
        # Key = camera location, value = last time a search was run
        self._lastSearchTimes = {}

        # We don't want to remove data manager pipes until we're sure that they
        # are completely done.  This is a list of pipe ids that are potentially
        # dead, and the time that we feel safe removing them.
        self._deadPipes = {}

        self._clipManager = None
        self._dataManager = None
        self._childProcQueue = None
        self._childProcLocalQueue = deque()
        self._delayedMessagesQueue = PriorityQueue()
        interval = getDebugPrefAsInt("backEndQueueStats", _kStatsDefaultInterval, userLocalDataDir)
        maxQueueSize = getDebugPrefAsInt("backEndQueueMaxSize", _kStatsMaxQueue, userLocalDataDir)
        maxExecTime = getDebugPrefAsFloat("backEndQueueMaxExecTime", float(kExecAlertThreshold), userLocalDataDir)
        self._childProcQueueStats = QueueStats(self._logger, interval, _kStatsAlertInterval, maxQueueSize, maxExecTime)

        self._lastCameraCheck = 0

        # The time.time() of the last time we did a realtime search...
        # Note that we use to make sure that data doesn't get left unsearched
        # even if no new motion data is coming in.
        self._lastRealtimeSearch = 0

        # A list of pending "add frame" requests.
        # We buffer these up and add them at idle time (obviously before doing
        # any real time searches)
        self._pendingAddFrames = []

        # A dictionary of pending real-time searches.  When we receive the
        # msgIdStreamProcessedData message, we'll set:
        #  self._pendingRealTimeSearches[camName] = ms
        # ...then, when we're idle, we'll do searches.  This keeps searches
        # from backlogging and also lowers their priority.
        self._pendingRealTimeSearches = {}

        # A dictionary of the maximum processed time for all running cameras.
        # Key = camera name, value = maximum time processed in the pipeline.
        self._maxProcessedTime = {}

        # Here we keep track of when we'd like to call flush on responses
        # that we might have...
        # Key = camLoc
        # Value = (list of responses, timeCamTurnedOff)
        self._responsesToFlush = {}

        # A way to map temporary IDs used by the queued data manager to dbId.
        # Key: pipeId (can be used to index into self._dataMgrPipes)
        # Value: A list of (camObjId, dbId) tuples, oldest first.
        # ...things will be deleted from this list as soon as the queued
        # data manager stops using the temp Id.
        self._tempIdMap = {}

        # A process handle to the current test camera, or None; also keep URI...
        self._testCamProc = None
        self._testCamUri = None

        # A process handle to the current packet capture, or None. We also keep
        # track of the status of the pcap process using a dictionary with two
        # keys, 'pcapEnabled' and 'pcapStatus', both set to None when
        # initialized and when the process is dead.
        self._pcapCamProc = None
        self._pcapInfo = {"pcapEnabled":None, "pcapStatus":None}

        # Track the last time we sent a ping to the network message server.
        self._lastMessageServerPing = 0

        # Track the last time we got a ping from the response runner.
        self._lastResponseRunnerPing = 0

        # Key = camera name, value = target cleanup time
        self._pendingRuleCleanupDict = {}

        # A list for record responses to append messages to
        self._recordResponseMsgs = []

        # Key = camera name, value = highest tagged time for that location
        self._lastTaggedTimes = {}

        # Key = target file name, value = camLoc, time to delete the file.
        self._pendingFileMoves = {}

        # A tuple of (fail time, proc, msg) for a pending rename operation.
        self._pendingRenameMsg = None

        # A list of (process, time stopped) tuples for cameras that have
        # been told to quit.
        self._deadCameras = []

        # A list of camera locations that we should add saved times for no
        # matter what.  Used to avoid missed tagging when we know a camera
        # process will no longer receive messages but still appears alive.
        self._selfAddSavedTimes = []

        # Exit flag to indicate that the back-end must not be restarred.
        self.wantQuit = False

        # To avoid multiple cleanup attempts.
        self._cleanedUp = False

        # List of cameras and their status
        self._cameras = {}

        self._clipUploader = None

        # cached live view requests while the camera was connecting
        self._pendingLiveViewStatus = {}
        self._pendingLiveViewSettings = {}

        # set up debug logging, if needed
        self._debugLogManager = DebugLogManager("BackEnd", self._userLocalDataDir)



    ###########################################################
    def __del__(self):
        """Destructor for BackEndApp."""
        self._logger.info("Beginning back end shutdown, in dtor.")
        self.cleanup()
        self._logger.info("Finished back end shutdown, in dtor.")


    ###########################################################
    def _terminateCameraProcess(self, proc):
        """Terminate the process, and all of its children too, if any.

        @param proc process to kill.
        """
        childrenPIDs = listChildProcessesOfPID(proc.pid)

        for childPID in childrenPIDs:
            try:
                os.kill(childPID, SIGTERM)
            except OSError:
                # We expect this if the child was already stopped or killed...
                pass

        proc.terminate()


    ###########################################################
    def cleanup(self):
        """Free resources used by BackEndApp."""
        if self._cleanedUp:
            return
        self._cleanedUp = True

        self._logger.info("Beginning cleanup")

        # Bring down the thread pool. Don't wait though.
        self._threadPool.shutdown()

        if self._upnpScanner:
            self._upnpScanner.shutdown()
        if self._onvifScanner:
            self._onvifScanner.shutdown()

        # Bring down the web server first, since it depends on everything else.
        if self._webServerProc:
            webServerQuitTime = time.time()
            self._putMsgWS([MessageIds.msgIdQuit])

        # Stop the xmlrpc server
        self._logger.info("Stopping NMS...")
        if self._netMsgServerProc:
            portFilePath = os.path.join(self._userLocalDataDir, kPortFileName)
            tmout = time.time() + _kNmsShutdownTimeout
            try:
                nmsClient = self._getXMLRPCClient(_kNmsShutdownTimeout)
                if nmsClient is not None:
                    nmsClient.shutdown()
                while time.time() < tmout:
                    if not os.path.exists(portFilePath):
                        self._logger.info("NMS shutdown completed")
                        break
                    time.sleep(.1)
            except:
                self._logger.error("cannot send shutdown to NMS (%s)" %
                                   sys.exc_info()[1])
            self._netMsgServerProc.terminate()
            try:
                os.remove(portFilePath)
                self._logger.info("port file removed")
            except:
                self._logger.warn("removing port file failed (%s)" %
                                  sys.exc_info()[1])

        # Stop the disk cleanup process
        self._logger.info("Stopping disk monitor...")
        if self._diskCleanupProc:
            diskCleanQuitTime = time.time()
            self._putMsgDC([MessageIds.msgIdQuit])

        # Stop the response process
        self._logger.info("Stopping responses...")
        if self._responseRunnerProc:
            self._putMsgRR([MessageIds.msgIdQuit])

        # Signal the camera capture processes to cleanup
        cameraProcesses = []
        self._logger.info("Stopping cameras...")
        for camLoc in self._captureStreams:
            proc, camPipe, _, _ = self._captureStreams[camLoc]
            self._sendMsg(camPipe, [MessageIds.msgIdQuit], camLoc)
            cameraProcesses.append(proc)
        self._captureStreams = {}

        # Make sure that dead cameras get killed too...
        for (proc, _) in self._deadCameras:
            cameraProcesses.append(proc)
        self._deadCameras = []

        # If there was a test camera going, kill it
        self._logger.info("Stopping test cam...")
        self._stopTestCamera()

        startTime = time.time()
        anyAlive = True
        self._logger.info("Waiting for cameras...")
        while anyAlive and (time.time()-startTime < _kCamQuitTimeout):
            for proc in cameraProcesses:
                if proc.is_alive():
                    time.sleep(1)
                    break
            else:
                anyAlive = False

        # Ensure all camera streams are killed
        self._logger.info("Terminating cameras...")
        for proc in cameraProcesses:
            self._terminateCameraProcess(proc)

        # Handle any last minute messages
        self._logger.info("Handling last messages...")
        for n in xrange(1,1000):
            try:
                msg, _ = self._getQueueMessage(timeout=1)
                self._logger.info("last message #%d: %s" % (n, str(msg[0])))
                self._processQueueMessage(msg)
            except QueueEmpty:
                break
            except:
                self._logger.error(traceback.format_exc())
                break

        # Force flush any responses.  Note that the response runner is gone, but
        # that's OK.  The only thing that needs this is the SendClip response,
        # which writes to a database...
        self._logger.info("Flushing responses...")
        try:
            self._flushResponses(True)
        except:
            self._logger.error("failed (%s)" % sys.exc_info()[1])

        # Ensure any last minute additions are saved
        if self._dataManager:
            # Finish up any idle processing
            try:
                self._flushIdleQueue()
            except:
                self._logger.error("final idle queue flush failed (%s)" %
                                   sys.exc_info()[1])

        # Make sure that the disk cleaner is gone; give a longer timeout
        # than for cameras, since killing it can cause data loss...
        self._logger.info("Waiting for disk monitor...")
        if self._diskCleanupProc:
            while (self._diskCleanupProc.is_alive())                       and \
                  (time.time() - diskCleanQuitTime < _kDiskCleanerQuitTimeout):
                time.sleep(1)
            self._diskCleanupProc.terminate()
            self._diskCleanupProc = None

        if self._platformHTTPWrapperProc:
            self._platformHTTPWrapperProc.terminate()
            self._platformHTTPWrapperProc = None

        # And finally, in case it got stuck, remove the web server.
        self._logger.info("Waiting for web server...")
        if self._webServerProc:
            while (self._webServerProc.is_alive()) and \
                  (time.time() - webServerQuitTime < _kWebServerQuitTimeout):
                time.sleep(1)
            self._webServerProc.terminate()
            # Make sure all of the associated web server processes are gone too,
            # at this moment we do not trust the web server logic itself to
            # always take them down (and there's no harm in trying anyway) ...
            killWebServerProcesses(self._logger)
            self._webServerProc = None

        # Check if the thread pool is really down.
        if not self._threadPool.shutdown():
            self._logger.warning("Thread pool is still active.")

        if self._clipUploader is not None:
            self._logger.info("Shutting down clip uploader")
            self._clipUploader.shutdown()
            self._clipUploader = None

        self._logger.info("Back end cleanup complete")

        # In case the service is waiting for us, but we came here through a
        # different path this call will release the service from waiting ...
        self.checkForServiceShutdown()


    ###########################################################
    def checkForServiceShutdown(self):
        """ Opens the exchange to the service via shared memory and checks if.
        a shutdown request is pending. We copy the signal and clear it, so the
        service knows that there was a taker and it can continue.

        @return  True if shutdown got detected.
        """
        if serviceAvailable():
            try:
                launch = Launch()
                if launch.open():
                    return 1 == launch.shutdown()
            except:
                pass
            finally:
                try:
                    launch.close()
                except:
                    pass
        return False


    ###########################################################
    def forceQuit(self):
        """Mark the app as done."""
        self._logger.warn("Forced quit - Windows logout or similar event.")
        self.wantQuit = True
        # NOTE: we called cleanup() before, but this is not right because we
        #       might be in a different thread, hence we just setting the quit
        #       flag is enough to let the run() loop exit

    ###########################################################
    def _setCameraStatus(self, camLocation, camStatus, wsgiPort=None, reason=None):
        # Determine what is the value to use for wsgi port?
        if camStatus == kCameraOff:
            wsgiPortSet = None
        elif wsgiPort is not None:
            wsgiPortSet = wsgiPort
        elif camLocation in self._cameras:
            wsgiPortSet = self._cameras[camLocation][1]
        else:
            wsgiPortSet = None

        # Check if update is actually needed
        if camLocation in self._cameras and \
            self._cameras[camLocation][0] == camStatus and \
            self._cameras[camLocation][1] == wsgiPortSet and \
            self._cameras[camLocation][2] == reason:
            return

        # Update the internal state
        realCamStatus = self._cameras[camLocation][0] if camStatus is None else camStatus
        self._cameras[camLocation]=(realCamStatus, wsgiPortSet, reason)

        # Update the NMS
        self._netMsgServerClient.setCameraStatus(camLocation, camStatus, wsgiPort, reason)

        # Update the web server
        self._putMsgWS([MessageIds.msgIdWsgiPortChanged, camLocation, wsgiPortSet])

    ###########################################################
    def _enableDiskLogging(self, enable):
        if enable:
            self._logger.enableDiskLogging()
            if self._onvifLogger:
                self._onvifLogger.enableDiskLogging()
            if self._upnpLogger:
                self._upnpLogger.enableDiskLogging()
        else:
            self._logger.disableDiskLogging()
            if self._onvifLogger:
                self._onvifLogger.disableDiskLogging()
            if self._upnpLogger:
                self._upnpLogger.disableDiskLogging()

    ###########################################################
    def _updateAnalyticsPort(self, msg):
        """ Update camera processes with the new analytics port
        """
        self._analyticsPort = msg[1]
        self._broadcastMsg(msg)

    ###########################################################
    def _getQueueMessage(self, timeout):
        # Attempt to empty all of the shared queue first
        while True:
            try:
                msg = self._childProcQueue.get(False)
                msgEx = (msg, time.time())
                self._childProcLocalQueue.append(msgEx)
            except QueueEmpty:
                break

        while self._delayedMessagesQueue.qsize()>0:
            procTime, msg = self._delayedMessagesQueue.queue[0]
            if getTimeAsMs() >= procTime:
                # re-get the item, to remove it, and deposit for processing
                procTime, msg = self._delayedMessagesQueue.get()
                self._childProcLocalQueue.append((msg, procTime/1000.))
            else:
                # do not make delayed messages wait longer than necessary
                timeout = min(timeout, (procTime - getTimeAsMs())/1000.)
                # no point in processing the rest of them
                break

        # If we have at least one message in the local queue, get it
        if len(self._childProcLocalQueue) > 0:
            msg, depositTime = self._childProcLocalQueue.popleft()
            return (msg, time.time() - depositTime)

        # Time to wait for a message from the far end
        return ( self._childProcQueue.get(timeout=timeout), 0 )

    ###########################################################
    def _getQueueSize(self):
        return len(self._childProcLocalQueue)

    ###########################################################
    def run(self): #PYCHECKER too many lines OK
        """Run the back end application."""
        self._logger.info("Starting the back end, pid: %d" % os.getpid())
        self._logger.info("SSL version " + str(ssl.OPENSSL_VERSION))

        if self.alreadyRunning():
            self._logger.info("Back end already running.")
            self.wantQuit = True
            self._cleanedUp = True  # nothing to clean up
            return



        # Open a messaging queue for child processes to post to
        self._childProcQueue = Queue(0)

        # We load prefs and rules before we call _openIPC because once we
        # create the NetworkMessageServer it isn't guaranteed to be safe to
        # open these files.
        prefs = BackEndPrefs(os.path.join(self._userLocalDataDir, kPrefsFile))
        self._maxStorage = prefs.getPref("maxStorageSize")
        self._cacheDuration = prefs.getPref("cacheDuration")
        self._recordInMemory = prefs.getPref(kRecordInMemory)
        self._clipMergeThreshold = prefs.getPref(kClipMergeThreshold)
        self._hardwareDevice = prefs.getPref(kHardwareAccelerationDevice)
        self._dataStorageLocation = prefs.getPref('dataDir')
        self._timePrefs = ( prefs.getPref('timePref12'), prefs.getPref('datePrefUS') )
        if type(self._dataStorageLocation) == str:
            self._dataStorageLocation = self._dataStorageLocation.decode('utf-8')

        if self._dataStorageLocation is None:
            self._dataStorageLocation = os.path.join(self._userLocalDataDir,
                                                     "videos")
            prefs.setPref("dataDir", self._dataStorageLocation)
        try:
            os.makedirs(self._dataStorageLocation)
        except Exception:
            pass

        self._webPort = prefs.getPref("webPort")
        self.videoSettings = {
            kLiveMaxBitrate:        prefs.getPref(kLiveMaxBitrate),
            kLiveEnableTimestamp:   prefs.getPref(kLiveEnableTimestamp),
            kLiveEnableFastStart:   prefs.getPref(kLiveEnableFastStart),
            kLiveMaxResolution:     prefs.getPref(kLiveMaxResolution),
            kClipResolution:        prefs.getPref(kClipResolution),
            kGenThumbnailResolution:prefs.getPref(kGenThumbnailResolution),
        }

        videoStorageLocation = prefs.getPref('videoDir')
        if type(videoStorageLocation) == str:
            videoStorageLocation = videoStorageLocation.decode('utf-8')
        if videoStorageLocation is None:
            videoStorageLocation = os.path.join(self._userLocalDataDir,
                                                "videos")
            prefs.setPref("videoDir", videoStorageLocation)
        try:
            os.makedirs(videoStorageLocation)
        except Exception:
            pass

        self._emailSettings = prefs.getPref('emailSettings')
        self._ftpSettings = prefs.getPref('ftpSettings')
        self._notificationSettings = prefs.getPref('notificationSettings')
        self._localExportSettings = {}

        self._clipDbPath = os.path.join(self._dataStorageLocation, kClipDbFile)
        self._objDbPath = os.path.join(self._dataStorageLocation, kObjDbFile)
        self._responseDbPath = os.path.join(self._dataStorageLocation,
                                            kResponseDbFile)
        self._videoDir = os.path.join(videoStorageLocation, kVideoFolder)
        self._tmpDir = os.path.join(self._dataStorageLocation, _kTmpFolder)
        self._remoteDir = os.path.join(self._userLocalDataDir, kRemoteFolder)

        # Clean up data that shouldn't be around anymore
        self._removeTmpFiles()

        self._removeEmptyDirs(self._tmpDir)
        self._removeEmptyDirs(self._remoteDir)

        try:
            os.makedirs(self._remoteDir)
        except Exception:
            pass

        # Run the database recovery, but only if it has been confirmed.
        dbCorruptStatus = getCorruptDatabaseStatus(self._userLocalDataDir)
        if dbCorruptStatus:
            self._logger.info("DB corruption status %s" % str(dbCorruptStatus))
            if kStatusRecover == dbCorruptStatus[0]:
                runDatabaseRecovery(self._userLocalDataDir,
                                    self._dataStorageLocation,
                                    self._logger,
                                    False)
            elif kStatusReset == dbCorruptStatus[0]:
                runDatabaseRecovery(self._userLocalDataDir,
                                    self._dataStorageLocation,
                                    self._logger,
                                    True)
        else:
            # TODO: run (quick)check right here
            self._logger.info("DB not found to be corrupted.")

        # Get the databases ready.
        self._responseDb = ResponseDbManager(self._logger)
        self._responseDb.open(self._responseDbPath)

        try:
            self._openDatabases()
        except DatabaseError, e:
            self._logger.error("Couldn't open databases.", exc_info=True)
            if e.message in kCorruptDbErrorStrings:
                self._handleCorruptDatabase()
            else:
                raise

        # Make response runner queue.  Must be done before loading rules...
        self._responseRunnerQueue = Queue(0)

        # Get the camera configuration. We just need the state right here, the
        # actual read/write manager instance lives in the NMS.
        camDb = os.path.join(self._userLocalDataDir, kCamDbFile)
        cm = CameraManager(self._logger, camDb)

        # Start the licensing manager.
        licenseSettings = prefs.getPref('licenseSettings')
        self._licenseManager = self._openLicenseManager(licenseSettings)

        # Make sure the cameras comply with the license.
        self._syncCamerasWithLicense(cm)

        # Open IPC.  Must be done before response runner, since the RR might
        # stick something in our queue (and so can Platform wrapper)...
        self._logger.info("Opening IPC")
        ipcOK, ipcPorts = self._openIPC()
        if not ipcOK:
            return
        # Start the analytics
        self._initPlatformHTTPWrapper()

        # Now we link the NMS to the license manager, so it gets told about
        # what happened during license setup...
        self._licenseManager.setNmsClient(self._netMsgServerClient)

        # Now we have enough things together to load the rules.
        self._loadRules(cm)

        # Startup the response runner.
        self._initResponseRunner()

        # Declare ourselves to be ready for the frontend.
        self._netMsgServerClient.memstorePut(kMemStoreBackendReady, True, -1)

        # Initialize the video streams and disk cleanup
        self._initVideoStreams(cm)
        self._initDiskCleanup(self._maxStorage)

        # Initialize the web server. Uses the low priority port because we need
        # to shield ourselves from overzealous external participants.
        webPort = prefs.getPref('webPort')
        lic = self._licenseManager.licenseData()
        if not hasPaidEdition(lic):
            self._logger.info("web server disabled due to starter license")
            webPort = -1

        self._initWebServer(webPort, ipcPorts[1],
                            prefs.getPref('webAuth'),
                            prefs.getPref('portOpenerEnabled'))

        # No idles are pending...
        idlePendingSince = None

        # Debugging info for slow loops...
        loopCount = 0
        curTime = time.time()

        if not os.path.isfile(os.path.join(self._userLocalDataDir, "disableOnvif")):
            self._onvifLogger = getLogger(_kOnvifLogName, self._logDir, _kOnvifLogSize)
            self._onvifScanner = OnvifNetworkScanner(self._onvifLogger,
                                    NetworkScannerCallback(MessageIds.msgIdUpdateOnvif, self._childProcQueue),
                                    _kFastestOnvifPoll,
                                    OnvifDeviceManager(self._onvifLogger, self._threadPool),
                                    "ONVIF")
            self._logger.info("ONVIF scanner had been created")
        else:
            self._logger.info("ONVIF scanner is disabled")

        if not os.path.isfile(os.path.join(self._userLocalDataDir, "disableUpnp")):
            self._upnpLogger = getLogger(_kUpnpLogName, self._logDir, _kUpnpLogSize)
            self._upnpScanner = NetworkScanner(self._upnpLogger,
                                    NetworkScannerCallback(MessageIds.msgIdUpdateUpnp, self._childProcQueue),
                                    _kFastestUpnpPoll,
                                    ControlPointManager(self._upnpLogger),
                                    "UPNP")
            self._logger.info("UPNP scanner had been created")
        else:
            self._logger.info("UPNP scanner is disabled")


        while not self.wantQuit:
            loopCount += 1
            try:
                queueMsg = None

                if self.checkForServiceShutdown():
                    self._logger.info("Shutdown flag found set in the service.")
                    self.wantQuit = True
                    continue

                isIdleNeeded = self._isIdleTimeNeeded()
                isIdle = False

                if isIdleNeeded:
                    timeout = 0
                else:
                    timeout = 2

                msgId = -1
                try:
                    queueMsg, timeInQueue = self._getQueueMessage(timeout=timeout)
                    qsize = self._getQueueSize()
                    msgId = queueMsg[0]
                    start = time.time()
                    self._processQueueMessage(queueMsg)
                    timeToProcess = time.time() - start
                    self._childProcQueueStats.update(qsize, msgId, timeInQueue, timeToProcess)
                except DatabaseError, e:
                    self._logger.error("Process message exception: %s", traceback.format_exc())
                    if e.message in kCorruptDbErrorStrings:
                        raise
                except QueueEmpty:
                    if timeout == 0:
                        isIdle = True
                except Exception:
                    self._logger.error("Process message exception: %s", traceback.format_exc())

                lastTime = curTime
                curTime = time.time()

                self._sendIftttState(prefs)

                if isIdleNeeded:
                    if not isIdle:
                        if idlePendingSince is None:
                            idlePendingSince = curTime
                        elif (curTime - idlePendingSince > _kMaxIdleDelay):
                            self._logger.warn(
                                "BackEnd never idle; forced: %.2f "
                                "(%d loops, last ID: %d, last loop: %.2f)" %
                                (curTime - idlePendingSince, loopCount,
                                 msgId, curTime - lastTime))
                            isIdle = True
                    if isIdle:
                        idlePendingSince = None
                        self._doIdleProcessing()

                # Flush any responses that might be waiting...
                self._flushResponses()

                # Restart any cameras that have unexpectedly terminated
                if curTime > self._lastCameraCheck+_kCameraCheckInterval:
                    locations = self._captureStreams.keys()

                    # If we've been sleeping we don't want to terminate cameras
                    # immediately on awake.
                    if self._lastCameraCheck and \
                       curTime > self._lastCameraCheck+_kCameraTimeout/2:
                        # If we haven't run through here in more than half of
                        # the camera timeout we've either been sleeping or we're
                        # really really behind on messages...increase the ping
                        # times for our cameras so they don't get shut down.
                        delay = curTime - self._lastCameraCheck
                        self._logger.warn("Big delay (%.1f sec) in main loop. Was asleep?" % ( delay ) )
                        for location in locations:
                            p, pipe, pipeId, _ = self._captureStreams[location]
                            self._captureStreams[location] = (p, pipe, pipeId, curTime)

                        self._lastResponseRunnerPing = curTime

                    self._lastCameraCheck = curTime
                    deadCameras = []

                    if not self._responseRunnerProc.is_alive() or \
                       self._processTimedOut(None):
                        if self._responseRunnerProc.is_alive():
                            self._responseRunnerProc.terminate()
                            self._logger.warn("terminated ResponseRunner")
                        else:
                            self._logger.info("ResponseRunner not alive, restarting")
                        self._initResponseRunner()

                    for location in locations:
                        p, _, _, _ = self._captureStreams[location]
                        if not p.is_alive() or self._processTimedOut(location):
                            if p.is_alive():
                                self._terminateCameraProcess(p)
                                self._logger.warn("terminated %s" % ensureUtf8(location))
                            self._delCaptureStream(location)
                            deadCameras.append(location)
                            self._logger.info("%s not alive, restarting" % ensureUtf8(location))

                    for location in self._cameraInfo:
                        self._syncCameraStateWithSchedule(location)

                    # If a camera was dead we don't want the 'connecting...'
                    # screen to display in the monitor view, as it might be in a
                    # dead loop. Skip straight to "could not connect" instead.
                    for cam in deadCameras:
                        self._setCameraStatus(cam, kCameraFailed)

                    pipeIds = self._deadPipes.keys()
                    for pipeId in pipeIds:
                        if self._deadPipes[pipeId] < curTime:
                            del self._deadPipes[pipeId]
                            if pipeId in self._dataMgrPipes:
                                del self._dataMgrPipes[pipeId]
                                del self._tempIdMap[pipeId]

                    # Ensure that the disk cleaner is still running
                    if not self._diskCleanupProc.is_alive():
                        self._logger.warn("Disk cleaner not running, restarting")
                        self._initDiskCleanup(self._maxStorage)

                    # Ensure that the platform wrapper is still running
                    if not self._platformHTTPWrapperProc or \
                        not self._platformHTTPWrapperProc.is_alive():
                        self._logger.warn("Platform wrapper is not running, restarting")
                        self._initPlatformHTTPWrapper()

                    # Give the license manager opportunity to do things.
                    try:
                        self._licenseManager.run()
                    except:
                        self._logger.error("license manager run error (%s)" %
                                           sys.exc_info()[1])
                        self._logger.error(traceback.format_exc())

                    # Periodically force the network message server to clear out
                    # the pending process updated queue.
                    try:
                        self._netMsgServerClient.updateCameraProgress()
                    except sockettimeout, e:
                        raise
                    except Exception, e:
                        # Not sure what we were catching here before, or whether
                        # it is still relevant... We now have threaded xmlrpc
                        # servers and timeout sockets... want to take this out
                        # but should ensure it isn't still necessary first.
                        #
                        # Follow up 10/8/2014 - ticket 11457
                        #     <class 'socket.error'>:
                        #         (10055, 'No buffer space available')
                        self._logger.error(
                                "Tell Ryan if you see this - eating " + str(e))

                    # Clean up any camera data hanging around as necessary.
                    for loc in self._pendingRuleCleanupDict.keys():
                        if self._pendingRuleCleanupDict[loc] < curTime:
                            self._cleanupCameraData(loc)

                    # Clean up any dead camera processes
                    for i in xrange(len(self._deadCameras)-1, -1, -1):
                        proc, quitTime = self._deadCameras[i]
                        if quitTime + _kRuleCleanupTimeout < curTime:
                            if proc.is_alive():
                                self._terminateCameraProcess(proc)
                            self._deadCameras.pop(i)

                    # If a camera was supposed to alert us to a rename but was
                    # frozen and never did, execute it now.
                    if self._pendingRenameMsg and \
                        self._pendingRenameMsg[0] < curTime:
                            self._logger.warn("Rename never processed, "
                                              "forcing now")
                            _, proc, msg = self._pendingRenameMsg
                            # Execute the rename.
                            self._processQueueMessage(msg)
                            # Terminate the old process.  We assume it never
                            # quit since it never gave us back the rename.
                            self._terminateCameraProcess(proc)

                if curTime>self._lastMessageServerPing+_kMessageServerPingTime:
                    self._lastMessageServerPing = curTime
                    self._netMsgServerClient.backEndPing()
                    self._moveTmpFiles()

            except DatabaseError, e:
                if e.message in kCorruptDbErrorStrings:
                    self._handleCorruptDatabase()
                else:
                    raise


    ###########################################################
    def _delCaptureStream(self, location):
        """Safely delete the given capture stream.

        This makes sure to add the pipe to self._deadPipes so we don't get
        any leaks.

        @param location  The location to delete.
        """
        _, _, pipeId, _ = self._captureStreams[location]

        if pipeId in self._dataMgrPipes:
            self._deadPipes[pipeId] = time.time() + _kPipeCleanupWait

        del self._captureStreams[location]


    ###########################################################
    def _isIdleTimeNeeded(self, force=False):
        """Return true if idle time is needed for processing.

        @param  force             If True, we'll return True if there are any
                                  searches pending, even if we've done one
                                  recently.
        @return isIdleTimeNeeded  True if idle time processing is needed.
        """
        return self._pendingAddFrames or self._wantRealtimeSearch(force)


    ###########################################################
    def _wantRealtimeSearch(self, force=False):
        """Return true if we'd like to do a realtime search now.

        @param  force               If True, we'll return True if there are any
                                    searches pending, even if we've done one
                                    recently.
        @return wantRealtimeSearch  True if idle time is needed.
        """
        if self._pendingRealTimeSearches:
            # We normally wait until we've accumulated 1 second of motion data
            # before doing a search.  This is for efficiency reasons...
            for camName, ms in self._pendingRealTimeSearches.iteritems():
                lastSearchTime = self._lastSearchTimes.get(camName, 0)
                dt = ms - lastSearchTime
                if dt > _kMinimumSearchDelayMs:
                    return True

            # We don't get given any new motion data after an object has left
            # the scene; thus, we need some extra logic here to catch the case
            # where we haven't seen motion data in a while...
            nowTime = time.time()
            timeSinceLast = nowTime - self._lastRealtimeSearch
            if timeSinceLast > _kStaleRealtimeSearchSeconds:
                return True

            # Also return True if we're forced.  Check this last, since it's
            # uncommon...
            if force:
                return True

        return False

    ###########################################################
    def _updateCameraUri(self, camLoc, protocol):
        uri, _, _, _ = self._cameraInfo[camLoc]
        newUri = self._realizeUri(uri)
        if newUri is None or newUri == "":
            # log a warning, but do not disrupt camera that is potentially running
            self._logger.warning(protocol + " search for '" + camLoc + "' returned empty URI")
        else:
            # Send a notification to camera process, so it can update the URI upon next connection
            self._logger.debug(protocol + " URI for '" + camLoc + "' is updated from " + uri + " to " + newUri)
            self._sendMsgLoc([MessageIds.msgIdCameraUriUpdated, newUri], camLoc)

    ###########################################################
    def _updateOnvif(self, allDevices, changedUuids, goneUuids):
        """Update ONVIF when the scanner tells us to
        """
        self._onvifDevices = allDevices
        # for dev in allDevices.keys():
        #     self._logger.info("Got device %s" % str(allDevices[dev]))

        if changedUuids or goneUuids:

            self._netMsgServerClient.setOnvifDevices(xmlrpclib.Binary(cPickle.dumps(allDevices)))

            self._logger.info("ONVIF UUIDs changed: %s, gone: %s" %
                              (str(changedUuids), str(goneUuids)))

            # Add gone UUIDs to changed ones...
            changedUuids |= goneUuids

            # Disable / reenable any affected cameras...
            for camLoc, _ in self._cameraInfo.iteritems():
                uri, enabled, _, extras = self._cameraInfo[camLoc]

                if enabled and isOnvifUrl(uri):
                    uuid = extractUuidFromOnvifUrl(uri)
                    if uuid in changedUuids:
                        self._updateCameraUri(camLoc, "ONVIF")
            # Restart test camera if it's running...
            if self._testCamProc is not None:
                uri = self._testCamUri
                assert uri is not None

                if isOnvifUrl(uri):
                    uuid = extractUuidFromOnvifUrl(uri)
                    if uuid in changedUuids:
                        self._stopTestCamera()
                        self._startTestCamera(uri, extras)


    ###########################################################
    def _updateUpnp(self, allDevices, changedUsns, goneUsns):
        """Update Upnp when the scanner tells us to
        """
        self._upnpDevices = allDevices
        # for dev in allDevices.keys():
        #     self._logger.info("Got device %s" % str(allDevices[dev]))

        if changedUsns or goneUsns:
            self._netMsgServerClient.setUpnpDevices(xmlrpclib.Binary(cPickle.dumps(self._upnpDevices)))

            self._logger.debug("UPNP USNs changed: %s, gone: %s" % (str(changedUsns), str(goneUsns)))

            # Add gone USNs to changed ones...
            changedUsns |= goneUsns

            # Disable / reenable any affected cameras...
            for camLoc, _ in self._cameraInfo.iteritems():
                uri, enabled, _, extras = self._cameraInfo[camLoc]

                if enabled and isUpnpUrl(uri):
                    usn = extractUsnFromUpnpUrl(uri)
                    if usn in changedUsns:
                        self._updateCameraUri(camLoc, "UPNP")
            # Restart test camera if it's running...
            if self._testCamProc is not None:
                uri = self._testCamUri
                assert uri is not None

                if isUpnpUrl(uri):
                    usn = extractUsnFromUpnpUrl(uri)
                    if usn in changedUsns:
                        self._stopTestCamera()
                        self._startTestCamera(uri, extras)

    ###########################################################
    def _doIdleProcessing(self, force=False):
        """Do any processing that should happen at idle time.

        This will also be called periodically even if the system isn't idle.

        This won't do _all_ queued up work that we need to do--just a piece.
        See self._flushIdleQueue().

        @param  force             If True, we'll return True if there are any
                                  searches pending, even if we've done one
                                  recently.
        """
        # Always add all pending frames.  It's important to do this before the
        # search...
        start = time.time()
        while self._pendingAddFrames:
            addFrameArgs = self._pendingAddFrames.pop(0)
            self._dataManager.addFrame(*addFrameArgs)
        self._dataManager.save()
        self._childProcQueueStats.update(None, _kFakeMessageIdDataManagerIdleProcessing, None, time.time()-start)

        if self._wantRealtimeSearch(force):
            # Keep track of the fact that we've now done a realtime search...
            self._lastRealtimeSearch = time.time()

            # Pop off the camera with the earliest ms value.  We will
            # eventually get to everything this way and in approx the
            # order they came in...
            camName, ms = min(self._pendingRealTimeSearches.iteritems(), key=operator.itemgetter(1))
            self._pendingRealTimeSearches.pop(camName)

            self._doRealTimeSearch(camName, ms)
            self._childProcQueueStats.update(None, _kFakeMessageIdRealTimeSearch, None, time.time()-self._lastRealtimeSearch)



    ###########################################################
    def _flushIdleQueue(self):
        """Make sure any things buffered to do at idle time are done."""
        while self._isIdleTimeNeeded(True):
            self._doIdleProcessing(True)


    ###########################################################
    def _cleanupCameraData(self, cameraLocation):
        """Remove any information tracked for a camera.

        @param  cameraLocation  The camera location to cleanup.
        """
        self._logger.info("Cleaning up remaining data for %s" % cameraLocation)
        if cameraLocation in self._pendingRuleCleanupDict:
            del self._pendingRuleCleanupDict[cameraLocation]
        if cameraLocation in self._ruleDicts:
            del self._ruleDicts[cameraLocation]
        if cameraLocation in self._lastTaggedTimes:
            del self._lastTaggedTimes[cameraLocation]
        if cameraLocation in self._lastSearchTimes:
            del self._lastSearchTimes[cameraLocation]
        if cameraLocation in self._maxProcessedTime:
            del self._maxProcessedTime[cameraLocation]
        if cameraLocation in self._cameraProcSizes:
            del self._cameraProcSizes[cameraLocation]


    ###########################################################
    def _loadRules(self, cameraManager):
        """Load real time rules.

        @param  cameraManager  The camera manager.
        """
        configuredCams = cameraManager.getCameraLocations()

        ruleDir = os.path.join(self._userLocalDataDir, kRuleDir)
        if not os.path.isdir(ruleDir):
            return
        fileNames = os.listdir(ruleDir)
        for fileName in fileNames:
            fileName = normalizePath(fileName)
            name, ext = os.path.splitext(fileName)
            if ext == kRuleExt:
                try:
                    # Load the rule
                    ruleFilePath = os.path.join(ruleDir, fileName)
                    ruleFile = file(ruleFilePath, 'r')
                    rule = cPickle.load(ruleFile)
                    ruleFile.close()

                    # Load it's associated query
                    queryFilePath = os.path.join(ruleDir,
                                                 rule.getQueryName()+kQueryExt)
                    queryFile = file(queryFilePath, 'r')
                    queryModel = cPickle.load(queryFile)
                    queryFile.close()

                    # First, convert old queries to have coordinate spaces.
                    convertOld2NewSavedQueryDataModel(
                        self._dataManager, queryModel
                    )

                    query = queryModel.getUsableQuery(self._dataManager)

                    # Remove rules created prior to the addition of responses
                    # in the saved query data model.
                    if not hasattr(queryModel, '_responses'):
                        self._logger.warn("Removing old rule %s" % ruleFile)
                        os.remove(queryFilePath)
                        os.remove(ruleFilePath)
                        continue

                    # Get the camera location and current schedule status
                    camLoc = queryModel.getVideoSource().getLocationName()
                    if camLoc == kAnyCameraStr:
                        continue

                    # Ensure that this rule is associated with a currently
                    # configured camera AND it's using the correct caps.
                    if camLoc not in configuredCams:
                        continue

                    isScheduled, nextSchedChange = rule.getScheduleInfo()

                    # Get the responses
                    responses = self._loadResponses(queryModel, camLoc, query,
                            name.lower())

                    # Add to the rules dict
                    if camLoc not in self._ruleDicts:
                        self._ruleDicts[camLoc] = {}

                    self._ruleDicts[camLoc][name.lower()] = \
                        (rule, isScheduled, nextSchedChange, query, responses)
                except Exception:
                    self._logger.error("Load rules exception", exc_info=True)


    ###########################################################
    def _loadResponses(self, query, camLoc, usableQuery, ruleName):
        """Load responses for a real time rule.

        @param  query        The SavedQueryDataModel to load responses from.
        @param  camLoc       The camera location of the rule.
        @param  usableQuery  The result of calling getUsableQuery() on the query
        @param  ruleName     The name of the corresponding rule.
        @return responses    A list of responses.
        """
        responses = []
        responseConfigList = query.getResponses()

        paid = hasPaidEdition(self._licenseManager.licenseData())

        for responseName, config in responseConfigList:
            if not config.get('isEnabled'):
                continue

            if responseName == kRecordResponse:
                config['msgList'] = self._recordResponseMsgs
                config['camLoc'] = camLoc
                responses.append(RecordResponse(config))
            elif responseName == kEmailResponse:
                responses.append(EmailResponse(query.getName(), camLoc,
                                               self._emailSettings,
                                               self._childProcQueue,
                                               self._responseRunnerQueue,
                                               config))
            elif responseName == kPushResponse and paid:
                startOffset, stopOffset = usableQuery.getClipLengthOffsets()
                responses.append(PushResponse(camLoc, query.getName(),
                            usableQuery.shouldCombineClips(),
                            startOffset, stopOffset, self._responseRunnerQueue))
            elif responseName == kIftttResponse and paid:
                startOffset, stopOffset = usableQuery.getClipLengthOffsets()
                responses.append(IftttResponse(camLoc, query.getName(),
                            usableQuery.shouldCombineClips(),
                            startOffset, stopOffset, self._responseRunnerQueue))
            elif responseName == kWebhookResponse and paid:
                responses.append(WebhookResponse(query.getName(), camLoc,
                                               self._responseRunnerQueue,
                                               config))
            elif responseName == kSoundResponse:
                responses.append(SoundResponse(config))
            elif responseName == kCommandResponse and paid:
                responses.append(CommandResponse(config))
            elif responseName == kFtpResponse and paid:
                playTimeOffset, preservePlayOffset = \
                    usableQuery.getPlayTimeOffset()
                responses.append(SendClipResponse(
                    self._logger,
                    kFtpProtocol,
                    query.getName(),
                    camLoc,
                    self._responseDb,
                    self._childProcQueue,
                    self._responseRunnerQueue, config,
                    playTimeOffset,
                    usableQuery.getClipLengthOffsets(),
                    usableQuery.shouldCombineClips(),
                    preservePlayOffset
                ))
            elif responseName == kLocalExportResponse and paid:
                playTimeOffset, preservePlayOffset = \
                    usableQuery.getPlayTimeOffset()
                responses.append(SendClipResponse(
                    self._logger,
                    kLocalExportProtocol,
                    query.getName(),
                    camLoc,
                    self._responseDb,
                    self._childProcQueue,
                    self._responseRunnerQueue, config,
                    playTimeOffset,
                    usableQuery.getClipLengthOffsets(),
                    usableQuery.shouldCombineClips(),
                    preservePlayOffset
                ))
                self._localExportSettings[ruleName] = config['exportPath']

        if not query.isOk():
            self._logger.error(
                "Invalid file path contained in responses <%s>" %
                (responseConfigList,)
            )

        return responses


    ###########################################################
    def _flushResponses(self, force=False):
        """Flush the responses.

        This is called at idle time, and during shutdown.

        @param  force   If True, we'll force a flush; else we'll only flush if
                        it's been long enough.
        """
        # If responses were added to the dict added before flushTime,
        # we'll flush the responses.
        timeNow = time.time()

        # Iterate over copy of keys, so we can delete...
        for camLoc in self._responsesToFlush.keys():
            allResponses, timeStopped = self._responsesToFlush[camLoc]
            if (timeStopped + _kResponseFlushTime <= timeNow) or force:
                for response in allResponses:
                    response.flush()
                del self._responsesToFlush[camLoc]


    ###########################################################
    def _openDatabases(self):
        """Open any databases needed by the back end."""
        self._clipManager = ClipManager(self._logger, self._clipMergeThreshold)
        self._clipManager.open(self._clipDbPath)
        self._dataManager = DataManager(self._logger,
                                        self._clipManager,
                                        self._videoDir)
        self._dataManager.open(self._objDbPath)


    ###########################################################
    def _reopenDatabases(self):
        """Reopen databases needed by the back end.

        Doesn't recreate the data manager and clip manager, since others may
        have pointers to them.
        """
        self._clipManager.open(self._clipDbPath)
        self._dataManager.open(self._objDbPath)


    ###########################################################
    def _openIPC(self):
        """Open routes of communication to the back end app.

        @return success  True if all IPC was successfully started.
        """
        # Begin a process for IPC from the front end
        self._processedTimesQueue = Queue(0)
        self._enableDiskLogging(False)
        try:
            licenseData = self._licenseManager.licenseData()
            hardwareDevices = getHardwareDevicesList()
            self._netMsgServerProc = startNetworkMessageServer(
                self._childProcQueue, self._userLocalDataDir,
                self._processedTimesQueue, self._clipDbPath, self._objDbPath,
                self._responseDbPath, licenseData, hardwareDevices
            )
        finally:
            self._enableDiskLogging(True)

        # Wait up to 10 seconds for the server to start
        try:
            msg = self._childProcQueue.get(True, 10)
        except Exception:
            self._logger.error("NetworkMessageServer was not started")
            return False, None

        self._netMsgServerClient = self._getXMLRPCClient()

        assert msg[0] == MessageIds.msgIdXMLRPCStarted, \
               "Expected MessageIds.msgIdXMLRPCStarted, not %s" % (msg[0])
        return msg[1], msg[2]


    ###########################################################
    def _initVideoStreams(self, cameraManager):
        """Start a process for each configured video stream.

        @param  cameraManager  The camera manager.
        """
        # Reset everything we knew about cameras.
        self._cameraInfo = {}

        locations = cameraManager.getCameraLocations()

        # Remove any old camera logs that are hanging around
        try:
            lowercaseLocations = [s.lower() for s in locations]
            cameraLogDir = os.path.join(self._logDir, "cameras")
            for logFile in os.listdir(cameraLogDir):
                logFile = normalizePath(logFile)
                if logFile.endswith('.log'):
                    logCam = logFile[:-4]
                    if logCam.lower() not in lowercaseLocations:
                        os.remove(os.path.join(cameraLogDir, logFile))
        except Exception:
            # We're just trying to do a bit of housekeeping, we really don't
            # care too much about this.
            pass

        # Load settings for configured cameras and start them if enabled.
        for location in locations:
            _, uri, enabled, extra = \
                                    cameraManager.getCameraSettings(location)
            self._cameraInfo[location] = (uri, enabled, False, extra)

            if not cameraManager.isCameraFrozen(location):
                isScheduled, _ = self._getCameraScheduleStatus(location)

                if enabled and isScheduled:
                    self._openCamera(location)


    ###########################################################
    def _removeTmpFiles(self):
        """Remove any files hanging around."""
        liveDir = os.path.join(self._userLocalDataDir, "live")
        if os.path.isdir(liveDir):
            liveFiles = os.listdir(liveDir)
            for liveFile in liveFiles:
                liveFile = normalizePath(liveFile)
                try:
                    os.remove(os.path.join(liveDir, liveFile))
                except Exception:
                    self._logger.warning("Couldn't remove file %s" % liveFile)


    ###########################################################
    def _openCamera(self, camLocation):
        """Start a process for a camera stream.

        @param  camLocation  The camera's location.
        @return camState     The new camera state if it changed, 'None'
                             otherwise.
        """
        assert camLocation in self._cameraInfo
        uri, enabled, monitored, extra = self._cameraInfo[camLocation]

        if extra.get('frozen', False):
            # If the camera is frozen then ignore this wish.
            return None

        if camLocation in self._captureStreams:
            # If the camera is already open don't do anything.
            return None

        # Remove it from the forced back end save times list.
        if camLocation in self._selfAddSavedTimes:
            self._selfAddSavedTimes.remove(camLocation)

        # Don't need to flush anymore--we're gonna get more data...
        self._responsesToFlush.pop(camLocation, None)

        # Inform any loaded rules for this camera about the new session.
        ruleDict = self._ruleDicts.get(camLocation, {})
        for _, _, _, _, responses in ruleDict.values():
            for response in responses:
                response.startNewSession()

        if not enabled:
            # Don't open the camera if it is disabled
            return None

        newURI = self._realizeUri(uri)

        if newURI == "" or newURI == None:
            if uri == "" or uri is None:
                # This means that the device could not be found, since its uri could
                # not be "real-ized".  Log this as a warning so that it stands out
                # in the logs, and then return.
                self._logger.warn(
                    "Cannot open '%s' - the camera could not be found." %
                    (camLocation,)
                )
                self._setCameraStatus(camLocation, kCameraFailed)
                return kCameraFailed
            else:
                self._logger.info("No ONVIF/UPNP results are available for " + \
                                camLocation + ". Using previously stored URI " + sanitizeUrl(uri))
        else:
            uri = newURI

        # If the camera already exists there could be pending searches, we don't
        # want to cause some data to not be considered.
        if camLocation not in self._lastSearchTimes:
            self._lastSearchTimes[camLocation] = time.time()*1000

        dmPipe1, dmPipe2 = Pipe()
        camPipe1, camPipe2 = Pipe()
        pipeId = self._nextPipeId
        self._nextPipeId += 1
        recSize = extra.get('recordSize', kDefaultRecordSize)

        # Shouldn't be able to get here with a large resolution if not licensed
        # for it, but check anyway.
        if not hasPaidEdition(self._licenseManager.licenseData()):
            if ((recSize[0] > kMaxRecordSize[0]) or
                (recSize[1] > kMaxRecordSize[1]) or
                (recSize == kMatchSourceSize)):

                extra['recordSize'] = kMaxRecordSize
                recSize = kMaxRecordSize

        elif not isLocalCamera(uri):

            # Match source resolution for all IP cameras with licensed app.
            extra['recordSize'] = kMatchSourceSize
            recSize = kMatchSourceSize

        self._putMsgRR([MessageIds.msgIdSetCamResolution, camLocation, recSize[0], recSize[1]])

        extra[kLiveMaxBitrate] = self.videoSettings[kLiveMaxBitrate]
        extra['enableTimestamps'] = self.videoSettings[kLiveEnableTimestamp]
        extra[kLiveEnableFastStart] = self.videoSettings[kLiveEnableFastStart]
        extra[kLiveMaxResolution] = self.videoSettings[kLiveMaxResolution]
        extra[kGenThumbnailResolution] = self.videoSettings[kGenThumbnailResolution]
        # This value determines analytics FPS. Take care when changing --
        # always take performance into consideration
        extra[kFpsLimit] = 10
        extra[kRecordInMemory] = self._recordInMemory
        extra[kClipMergeThreshold] = self._clipMergeThreshold
        extra['useUSDate'] = self._timePrefs[1]
        extra['use12HrTime'] = self._timePrefs[0]
        extra[kHardwareAccelerationDevice] = self._hardwareDevice
        if _kDebugConfig is not None:
            extra['debugConfig'] = _kDebugConfig

        # Let the new camera process know what moves are still pending
        pendingMoves = []
        for targetPath, (loc, _) in self._pendingFileMoves.items():
            if loc == camLocation:
                pendingMoves.append(os.path.basename(targetPath))
        extra['pendingMoves'] = pendingMoves

        self._enableDiskLogging(False)
        try:
            p = startCapture(self._childProcQueue, camPipe2, dmPipe2, pipeId,
                             camLocation, uri, self._clipDbPath, self._tmpDir,
                             self._videoDir, self._userLocalDataDir, extra)
        finally:
            self._enableDiskLogging(True)

        self._captureStreams[camLocation] = (p, camPipe1, pipeId, time.time())
        self._dataMgrPipes[pipeId] = dmPipe1
        self._tempIdMap[pipeId] = []

        self._setCameraStatus(camLocation, kCameraConnecting)

        if monitored:
            self._pendingLiveViewStatus[camLocation] = \
                                [MessageIds.msgIdEnableLiveView, camLocation]

        if _kDebugConfig is not None:
            self._sendMsg(camPipe1, [MessageIds.msgIdSetDebugConfig, _kDebugConfig], camLocation)
        if self._analyticsPort is not None:
            self._sendMsg(camPipe1, [MessageIds.msgIdAnalyticsPortChanged, self._analyticsPort], camLocation)

        # Update the disk cleaner with the number of active cameras
        self._putMsgDC([MessageIds.msgIdSetNumCameras, len(self._captureStreams)])

        return kCameraConnecting


    ###########################################################
    def _stopCamera(self, camLocation):
        """Stop a process for a camera stream.

        @param  camLocation  The camera's location.
        @return camState     The new camera state if it changed, 'None'
                             otherwise.
        """
        # If the camera isn't actually running we have nothing to do.
        if camLocation not in self._captureStreams:
            return None

        proc, pipe, _, _ = self._captureStreams[camLocation]
        self._sendMsg(pipe, [MessageIds.msgIdQuit], camLocation)

        # Update the disk cleaner with the number of active cameras
        self._putMsgDC([MessageIds.msgIdSetNumCameras, len(self._captureStreams)-1])

        self._setCameraStatus(camLocation, kCameraOff)

        self._delCaptureStream(camLocation)

        # Add the camera process to a list so we ensure it actually quits
        # or is terminated.
        self._deadCameras.append((proc, time.time()))

        # Note the fact that we'd like to flush the responses before too long...
        ruleDict = self._ruleDicts.get(camLocation, {})
        allResponses = []
        for _, _, _, _, responses in ruleDict.itervalues():
            allResponses.extend(responses)
        self._responsesToFlush[camLocation] = (allResponses, time.time())

        return kCameraOff

    ###########################################################
    def _realizeUri(self, uri):
        # We'll try to realize any UPNP/ONVIF URLs into real URLs...
        # ...we'll also kick off an active search; prolly too late for this
        # time, but if we try again (which we should), it may help...
        try:
            usn = extractUsnFromUpnpUrl(uri)
            uri = realizeUpnpUrl(self._upnpDevices, uri)
        except ValueError:
            pass # Expect this for non-upnp uris...
        try:
            devId = extractUuidFromOnvifUrl(uri)
            uri = realizeOnvifUrl(self._onvifDevices, uri)
        except ValueError:
            pass # Expect this for non-onvif uris...

        return uri

    ###########################################################
    def _startTestCamera(self, uri, extras):
        """Start streaming to test a camera uri.

        @param  uri     The camera's uri.
        @param  extras  The extras dict for the camera.
        """
        # Ensure that we don't have another test running.
        self._stopTestCamera()

        # Save test camera URI _before_ realizing it as UPNP/ONVIF...
        uri = self._realizeUri(uri)
        self._testCamUri = uri

        self._enableDiskLogging(False)
        extras[kLiveEnableFastStart] = False
        try:
            liveDataDir = os.path.join(self._userLocalDataDir, 'live')
            self._testCamProc = startStream(uri, liveDataDir, self._logDir,
                    self._userLocalDataDir, self._childProcQueue, extras)
        finally:
            self._enableDiskLogging(True)


    ###########################################################
    def _stopTestCamera(self):
        """Stop a process for a camera stream."""
        # If there is an existing process terminate it.
        if self._testCamProc is not None:
            if self._testCamProc.is_alive():
                self._terminateCameraProcess(self._testCamProc)
        self._testCamProc = None
        self._testCamUri = None

        # Remove live file
        liveFilePath = os.path.join(self._userLocalDataDir, 'live',
                                    kTestLiveFileName)
        if os.path.exists(liveFilePath):
            try:
                os.remove(liveFilePath)
            except Exception:
                self._logger.info("Couldn't remove the test live file")


    ###########################################################
    def _startPacketCapture(self, cameraLocation, delaySeconds, pcapDir):
        """Start streaming to test a camera uri.

        @param  cameraLocation  The camera's name.
        @param  delaySeconds    The time alloted for packet capture.
        """
        # Ensure that we don't have another packet capture running.
        self._stopPacketCapture()

        uri, enabled, monitored, extras = self._cameraInfo[cameraLocation]

        uri = self._realizeUri(uri)

        liveDataDir = os.path.join(self._userLocalDataDir, 'live')

        self._enableDiskLogging(False)
        try:
            self._pcapCamProc = startPacketCapture(
                uri, liveDataDir, pcapDir, self._userLocalDataDir,
                self._childProcQueue, extras, delaySeconds
            )
        finally:
            self._enableDiskLogging(True)


    ###########################################################
    def _stopPacketCapture(self):
        """Stop a process for a camera stream."""
        # If there is an existing process terminate it.
        if self._pcapCamProc is not None:
            if self._pcapCamProc.is_alive():
                self._terminateCameraProcess(self._pcapCamProc)
        self._pcapCamProc = None
        self._pcapInfo = {"pcapEnabled":None, "pcapStatus":None}


    ###########################################################
    def _createCertificateData(self):
        """ Creates contact information and name fields for the certificate to
        be used for remote access via HTTPS. Originally we wanted to put in real
        user information (name, e-mail), but that would have exposed it in the
        certificate to the public. For now we derive some identifier from the
        machine ID, so there is something static, but yet somewhat recognizable
        without the need for persistence.

        @return (contact,name)  The certificate data to use.
        """
        mid = machineId(True, self._logger)
        for _ in xrange(0, 32): # scramble the machine ID, don't expose it!
            mid = hashlib.sha1(mid.encode("UTF-8")).hexdigest()
        name = "remote" + mid[0:8]  # (and only return a portion of it)
        return (kSupportEmail, name)


    ###########################################################
    def _initWebServer(self, webPort, xmlRpcPort, auth, epo):
        """Start a process to run the web server and all the care it needs.

        @param webPort: The initial HTTP port number to use.
        @param xmlRpcPort: The XML/RPC port.
        @param auth: The authentication configuration.
        @param epo: The port opener enabling flag.
        """
        self._webServerQueue = Queue(0)
        self._enableDiskLogging(False)
        try:
            webDir = os.environ.get(kWebDirEnvVar)
            if not webDir:
                webDir = os.path.join(self._userLocalDataDir, kWebDirName)
            self._webServerProc = startWebServer(
                self._childProcQueue,
                self._webServerQueue,
                self._logDir,
                webDir,
                webPort,
                auth,
                "http://127.0.0.1:%d/" % xmlRpcPort,
                self._remoteDir,
                epo,
                self._createCertificateData())
        finally:
            self._enableDiskLogging(True)
        self._logger.info("web directory: %s" % webDir)

    ###########################################################
    def _initPlatformHTTPWrapper(self):
        """Start a process to run the web server and all the care it needs.
        """
        self._logger.info("Starting platform wrapper")
        self._enableDiskLogging(False)
        error = ""
        try:
            self._platformHTTPWrapperProc = startPlatformHTTPWrapper(
                self._childProcQueue,
                self._userLocalDataDir,
                0)
            self._logger.info("Successfully launched platform HTTP wrapper")
        except:
            error = traceback.format_exc()
        finally:
            self._enableDiskLogging(True)
            if len(error) > 0:
                self._logger.error("Failed to launch platform HTTP wrapper:" + error)

    ###########################################################
    def _initDiskCleanup(self, maxStorage):
        """Start a process to monitor and manage disk usage.

        @param  maxStorage  The maximum amount of space to use in bytes.
        """
        self._diskCleanupQueue = Queue(0)

        self._enableDiskLogging(False)
        try:
            tmpDir = os.path.join(self._dataStorageLocation, "tmp")
            self._diskCleanupProc = startDiskCleaner(
                self._childProcQueue, self._diskCleanupQueue, self._clipDbPath,
                self._objDbPath, len(self._captureStreams), maxStorage,
                self._videoDir, tmpDir, self._logDir, self._userLocalDataDir,
                self._remoteDir, self._disableDiskCleanup, self._cacheDuration
            )
        finally:
            self._enableDiskLogging(True)


    ###########################################################
    def _sendIftttState(self, prefs):
        """ Sends pending IFTTT state, given that there is nothing being sent
        at this very moment.

        @param  prefs  Preference to persist a flag indicating that we don't
                       have anything for IFTTT and that there is no reason for
                       sending things out.
        """

        if self._iftttStateCleared:
            self._iftttStateCleared = False
            prefs.setPref("iftttIdle", True)

        if self._iftttStateSending or \
           self._iftttStatePending is None:
            return

        empty = self._iftttStatePending == ([],[])

        idle = prefs.getPref("iftttIdle")
        if empty:
            if idle:
                self._iftttStatePending = None
                return
        else:
            if idle:
                prefs.setPref("iftttIdle", False)

        class IftttStateSender:
            def __init__(self, backEndApp, authToken, state):
                self._authToken = authToken
                self._backEndApp = backEndApp
                self._state = state
            def run(self):
                backEndApp = self._backEndApp
                logger = backEndApp._logger
                if backEndApp._iftttLastStateOut == self._state:
                    logger.info("no change in IFTTT state, no need to send")
                    backEndApp._iftttStateSending = False
                    sent = True
                else:
                    logger.info("sending IFTTT state %s ..." % str(self._state))
                    try:
                        ic = IftttClient(logger, self._authToken)
                        sent = ic.sendState(*self._state)
                    finally:
                        backEndApp._iftttStateSending = False
                if sent:
                    backEndApp._iftttLastStateOut = self._state
                    if self._state == ([],[]):
                        backEndApp._iftttStateCleared = True

        # Pretend to be sending right away, since the thread might be faster.
        self._iftttStateSending = True
        authToken = self._licenseManager.getAuthToken()
        # If the thread pool is blocked we will try later. Must not get stuck.
        self._logger.info("scheduling IFTTT state sending...")
        sender = IftttStateSender(self, authToken, self._iftttStatePending)
        if self._threadPool.schedule(sender, False):
            self._iftttStatePending = None
        else:
            self._iftttStateSending = False


    ###########################################################
    def _openLicenseManager(self, settings):
        """Open the license manager and schedule needed operations.

        @paramm settings  The (initial) license settings.
        @return           License manager instance.
        """
        machid = machineId(True, self._logger)
        self._logger.info("machine ID: %s" % machid)
        return LicenseManager(settings, machid, self._userLocalDataDir,
                              self._logger)


    ###########################################################
    def _syncCamerasWithLicense(self, camMgr):
        """Ensure that the camera (state)s are in compliance with the license.

        @param camMgr  Camera manager.
        """
        camFld = self._licenseManager.licenseData()[kCamerasField]
        maxCameras = int(camFld)
        res = camMgr.freezeCameras(maxCameras, True)
        self._logger.info(
            "cameras synched with license (max=%d) - frozen: %d, unfrozen: %d" %
            (maxCameras, len(res[0]), len(res[1])))
        camMgr.logLocations(self._logger)


    ###########################################################
    def _initResponseRunner(self):
        """Start a process to handle doing slow responses."""
        tmpDir = os.path.join(self._dataStorageLocation, "tmp")
        self._lastResponseRunnerPing = time.time()
        self._enableDiskLogging(False)
        try:
            self._responseRunnerProc = startResponseRunner(
                self._childProcQueue, self._responseRunnerQueue, self._clipDbPath,
                self._objDbPath, self._responseDbPath, self._videoDir, tmpDir,
                self._logDir, self._userLocalDataDir, self._ftpSettings,
                self._localExportSettings, self._notificationSettings,
                self._licenseManager.getAuthToken()
            )
        finally:
            self._enableDiskLogging(True)


    ###########################################################
    def _quit(self):
        """Terminate the application."""
        self._logger.info("User quit requested")
        self.wantQuit = True

    ###########################################################
    def _putMsg(self, q, msg, location):
        if q:
            start = time.time()
            q.put(msg)
            self._childProcQueueStats.update(None, _kFakeMessageIPCUtility, None, time.time()-start, location)

    ###########################################################
    def _putMsgDC(self, msg):
        self._putMsg(self._diskCleanupQueue, msg, "diskCleaner")

    ###########################################################
    def _putMsgRR(self, msg):
        self._putMsg(self._responseRunnerQueue, msg, "responseRunner")

    ###########################################################
    def _putMsgWS(self, msg):
        self._putMsg(self._webServerQueue, msg, "webServer")

    ###########################################################
    def _sendMsg(self, pipe, msg, location):
        start = time.time()
        pipe.send(msg)
        self._childProcQueueStats.update(None, _kFakeMessageIPCCamera, None, time.time()-start, location)

    ###########################################################
    def _sendMsgLoc(self, msg, location):
        if location in self._captureStreams:
            _, pipe, _, _ = self._captureStreams[location]
            self._sendMsg(pipe, msg, location)

    ###########################################################
    def _broadcastMsg(self, msg):
        for camLoc in self._captureStreams:
            try:
                _, pipe, _, _ = self._captureStreams[camLoc]
                self._sendMsg(pipe, msg, camLoc)
            except:
                self._logger.error("Failed to deliver message " + str(msg[0]) + " to camera '" + camLoc + "'")

    ###########################################################
    def _setLiveViewStatus(self, msg, delayed):
        cameraLocation = msg[1]
        op = "Processing" if delayed else "Received"
        value = msg[0] == MessageIds.msgIdEnableLiveView
        msgId = "msgIdEnableLiveView" if value else "msgIdDisableLiveView"
        self._logger.info("%s %s, loc: %s" % (op, msgId, cameraLocation))
        self._sendMsgLoc(msg, cameraLocation)
        if cameraLocation in self._cameraInfo:
            uri, enabled, _, extra = self._cameraInfo[cameraLocation]
            self._cameraInfo[cameraLocation] = (uri, enabled, value, extra)
        self._pendingLiveViewStatus.pop(cameraLocation, None)

    ###########################################################
    def _setLiveViewParams(self, msg, delayed):
        _kSmallViewFps = 2
        cameraLocation = msg[1]
        width = msg[2]
        height = msg[3]
        audioVolume = msg[4]
        fps = msg[5]
        op = "Processing" if delayed else "Received"
        self._logger.info("%s msgIdSetLiveViewParams " \
           "loc: %s, width: %d, height: %d, audio: %d, fps: %d" %
           (op, cameraLocation, width, height, audioVolume, fps))
        self._sendMsgLoc([MessageIds.msgIdSetMmapParams, True, width, height, fps], cameraLocation)
        self._sendMsgLoc([MessageIds.msgIdSetAudioVolume, audioVolume], cameraLocation)
        self._pendingLiveViewSettings.pop(cameraLocation, None)

    ###########################################################
    def _doRealTimeSearch(self, cameraLocation, ms):
        """Perform an incremental search for a camera.

        @param  cameraLocation  The camera location to perform the search on.
        @param  ms              The most recent time in milliseconds to search.
        """
        try:
            self._dataManager.setCameraFilter([cameraLocation])

            lastSearchTime = self._lastSearchTimes.get(cameraLocation, 0)
            for ruleName in self._ruleDicts.get(cameraLocation, {}):
                rule, scheduled, schedChange, query, responses = \
                                    self._ruleDicts[cameraLocation][ruleName]

                # Update if the rule is currently schedule or not if necessary.
                curScheduled = False
                if ms/1000 > schedChange:
                    curScheduled, nextSchedChange = rule.getScheduleInfo()
                    self._ruleDicts[cameraLocation][ruleName] = \
                        (rule, curScheduled, nextSchedChange, query, responses)
                else:
                    curScheduled = scheduled

                # If the rule is enabled, has responses, and was scheduled for
                # part of this time segment perform a search.
                if rule.isEnabled() and (scheduled or curScheduled) and \
                                                                    responses:
                    self._logger.debug("Searching %s with %s from %f, %f" %
                                (cameraLocation, ruleName, lastSearchTime, ms))
                    procSize = self._cameraProcSizes.get(cameraLocation, None)
                    procSizesMsRange = None
                    if procSize is not None:
                        procSizesMsRange = [(procSize[0], procSize[1], lastSearchTime, ms+1)]
                    results = query.search(lastSearchTime+1, ms, 'realtime', procSizesMsRange)
                    results.sort()
                    rangeDict = parseSearchResults(results,
                                                   query.shouldCombineClips())

                    # Always fire the responses, since they may need to do
                    # processing even if no current results...
                    for response in responses:
                        response.addRanges(ms, rangeDict)

                if scheduled and not curScheduled:
                    query.reset()

            self._lastSearchTimes[cameraLocation] = ms

            while len(self._recordResponseMsgs):
                msg = self._recordResponseMsgs.pop(0)
                self._processQueueMessage(msg)

            tagged = self._lastTaggedTimes.get(cameraLocation, 0)
            self._processedTimesQueue.put([cameraLocation, ms, tagged])
        except DatabaseError, e:
            self._logger.error("Real time search database exception",
                               exc_info=True)
            if e.message in kCorruptDbErrorStrings:
                self._handleCorruptDatabase()
        except Exception:
            self._logger.error("Real time search exception", exc_info=True)
        finally:
            self._dataManager.setCameraFilter(None)


    ###########################################################
    def _processTimedOut(self, location=None):
        """ Determine if a process timed out

        @param location             camera location associated with the process
                                    ResponseRunner, if None
        """
        isResponseRunner = location is None
        if isResponseRunner:
            timeout = _kResponseRunnerTimeout
            lastPingTime = self._lastResponseRunnerPing
            location = "ResponseRunner"
        else:
            timeout = _kCameraTimeout
            p, camPipe, dataMgrPipe, lastPingTime = self._captureStreams[location]

        # Check if we've timed out based on the last ping
        if lastPingTime+timeout > time.time():
            return False

        # Last ping may still be sitting in the queue, if we get backed up for some reason
        for (msg, depositTime) in self._childProcLocalQueue:
            if (msg[0] == MessageIds.msgIdResponseRunnerPing and
               isResponseRunner) or \
               (msg[0] == MessageIds.msgIdCameraCapturePing and \
                msg[1] == location and not isResponseRunner):
                lastPingTime = depositTime
                if depositTime+timeout > time.time():
                    self._logger.info("Process %s had timed out, but a ping was deposited to the queue %.1f sec ago and not yet processed" %
                            ( location, time.time() - lastPingTime ) )

                    # Update last ping time, so we won't keep scanning the queue
                    # for each message we process
                    if isResponseRunner:
                        self._lastResponseRunnerPing = lastPingTime
                    else:
                        self._captureStreams[location] = (p, camPipe, dataMgrPipe, lastPingTime)
                    return False

        # Nope, we did time out
        self._logger.debug("Process %s had timed out, last ping %.1f sec ago" %
                ( location, time.time() - lastPingTime ) )
        return True

    ###########################################################
    def _isCameraConnected(self, loc):
        """ Determines whether we can send messages to a camera
        """
        status, port, reason = self._cameras.get(loc, (kCameraUndefined, -1, "unknown"))
        return status == kCameraConnecting and port is not None


    ###########################################################
    def _processPendingLiveViewRequests(self, cam):
        """ If any live view requests are outstanding for the camera,
            process them
        """
        if not self._isCameraConnected(cam):
            return

        if cam in self._pendingLiveViewSettings:
            self._setLiveViewParams(self._pendingLiveViewSettings[cam], True)

        if cam in self._pendingLiveViewStatus:
            self._setLiveViewStatus(self._pendingLiveViewStatus[cam], True)

    ###########################################################
    def _processQueueMessage(self, msg): #PYCHECKER too many lines OK
        """Process a message from the queue.

        @param  msg  A list where the first entry is the message id and any
                     additional are parameters as described in MessageIds.py.
        """
        msgId = msg[0]

        if msgId == MessageIds.msgIdQuit:
            self._quit()

        elif msgId == MessageIds.msgIdAnalyticsPortChanged:
            # handle analytics port change here and now
            self._logger.info("Analytics port had changed to %d" % msg[1] )
            self._updateAnalyticsPort(msg)

        # Data manager messages
        elif msgId == MessageIds.msgIdDataAddObject:
            (pipeId, camObjId, addTime, objType, location) = msg[1:]

            dbId = self._dataManager.addObject(addTime, objType, location)

            self._logger.info("Received msgIdDataAddObject, loc: %s, time: %i,"
                              "type: %s, dbId: %i"
                              % (location, addTime, objType, dbId))

            self._tempIdMap[pipeId].append((camObjId, dbId))
            if location in self._captureStreams:
                dmPipe = self._dataMgrPipes[pipeId]
                dmPipe.send((camObjId, dbId))
        elif msgId == MessageIds.msgIdDataAddFrame:
            (pipeId, dbId, frame, frameTime, bbox, objType, action) = msg[1:]
            dbId = self._mapDbId(pipeId, dbId)

            if isinstance(dbId, tuple):
                self._logger.error("Received unknown temp ID: %s" % str(dbId))
            else:
                self._logger.debug("Received msgIdDataAddFrame, dbId: %i"
                                   ", time: %i, bbox: %s, type: %s"
                                   % (dbId, frameTime, bbox, objType))
                self._pendingAddFrames.append((dbId, frame, frameTime, bbox,
                                               objType, action))

        # Camera capture messages
        elif msgId == MessageIds.msgIdStreamOpenSucceeded:
            cam = msg[1]
            procSize = msg[2]
            self._logger.info("Received msgIdStreamOpenSucceeded from %s" % cam)
            if cam in self._captureStreams:
                p, camPipe, dataMgrPipe, _ = self._captureStreams[cam]
                self._captureStreams[cam] = (p, camPipe, dataMgrPipe,
                                             time.time())
                # NOTE: These terms should be revised. This message added so
                #       wsgi knows we're no longer in failed state (if we were)
                self._setCameraStatus(cam, kCameraConnecting)

            # Store the processing size for later use, like when new rules are
            # added, edited, or enabled.
            procWidth, procHeight = procSize
            if procWidth > 0 and procHeight > 0:
                self._cameraProcSizes[cam] = (procWidth, procHeight)

            # The camera could be opening with a new processing size; make sure
            # the rules are updated with the new coordinate space.
            if cam in self._cameraProcSizes:
                for ruleName in self._ruleDicts.get(cam, {}):
                    rule, _, _, query, _ = self._ruleDicts[cam][ruleName]
                    if rule.isEnabled():
                        query.setProcessingCoordSpace(self._cameraProcSizes[cam])

            self._processPendingLiveViewRequests(cam)

        elif msgId == MessageIds.msgIdStreamOpenFailed:
            cam = msg[1]
            reason = msg[2]
            self._logger.info("Received msgIdStreamOpenFailed from %s (%s)" % (cam, ensureUtf8(reason)))
            if cam in self._captureStreams:
                p, camPipe, dataMgrPipe, _ = self._captureStreams[cam]
                self._captureStreams[cam] = (p, camPipe, dataMgrPipe,
                                             time.time())
                self._setCameraStatus(cam, kCameraFailed, None, reason)

            # If this camera is a UPnP camera, initiate an active search for it,
            # just to make sure...
            if cam in self._cameraInfo:
                uri, _, _, _ = self._cameraInfo[cam]
                uri = self._realizeUri(uri)

        elif msgId == MessageIds.msgIdCameraCapturePing:
            cam = msg[1]
            self._logger.debug("Received msgIdCameraCapturePing from %s" % cam)
            if cam in self._captureStreams:
                p, camPipe, dataMgrPipe, _ = self._captureStreams[cam]
                self._captureStreams[cam] = (p, camPipe, dataMgrPipe,
                                             time.time())
        elif msgId == MessageIds.msgIdStreamUpdateFrameSize:
            cam = msg[1]
            size = msg[2]
            if cam in self._cameraInfo:
                uri, enabled, monitored, extra = self._cameraInfo[cam]
                prevSize = extra.get('initFrameSize', 0)
                self._logger.debug("Received msgIdStreamUpdateFrameSize from %s oldSize=%d size=%d"
                                % (cam, prevSize, size))
                if prevSize < size:
                    extra['initFrameSize'] = size
                    self._cameraInfo[cam] = (uri, enabled, monitored, extra)
                    # Update the server to propagate to the persistent configuration
                    self._netMsgServerClient.editCameraFrameStorageSize(cam, size)
            else:
                self._logger.debug("Received msgIdStreamUpdateFrameSize from unknown camera %s"
                                % cam)
        elif msgId == MessageIds.msgIdResponseRunnerPing:
            self._logger.debug("Received msgIdResponseRunnerPing")
            self._lastResponseRunnerPing = time.time()
        elif msgId == MessageIds.msgIdPipeFinished:
            self._logger.info("Received msgIdPipeFinished")
            if msg[1] in self._dataMgrPipes:
                del self._dataMgrPipes[msg[1]]
                del self._tempIdMap[msg[1]]
        elif msgId == MessageIds.msgIdStreamProcessedData:
            self._logger.debug("Received msgIdStreamProcessedData, cam: %s, "
                               "ms: %i" % (msg[1], msg[2]))
            self._pendingRealTimeSearches[msg[1]] = msg[2]
            self._maxProcessedTime[msg[1]] = msg[2]
        elif msgId == MessageIds.msgIdAddSavedTimes:
            cam, timeRanges = msg[1:]
            self._logger.debug("Received msgIdAddSavedTimes, loc: %s, times: %s"
                               % (cam, str(timeRanges)))
            # Track the highest tagged times for this camera
            prevTagged = self._lastTaggedTimes.get(cam, 0)
            for _, stop in timeRanges:
                prevTagged = max(prevTagged, stop)
            self._lastTaggedTimes[cam] = prevTagged

            if cam in self._captureStreams:
                _, pipe, _, _ = self._captureStreams[cam]
                # Ensure the camera can handle AddSavedTimes messages.
                if cam not in self._selfAddSavedTimes:
                    self._sendMsg(pipe, msg, cam)
                    return

            # If the camera didn't exist anymore or if we marked it terminated
            # will add the saved times to the database.

            retry = self._clipManager.markTimesAsSaved(cam, msg[2], True)
            if retry:
                self._delayedMessagesQueue.put((int(retry*1000), msg))

        elif msgId == MessageIds.msgIdTestCameraFailed:
            self._logger.info("Received msgIdTestCameraFailed")
            self._netMsgServerClient.setTestCameraFailed(True)
        elif msgId == MessageIds.msgIdSetCamCanTerminate:
            # Upon receiving this message we will no longer send AddSaveTime
            # messages to the camera process, and will send it a confirmation
            # that we received this.  When it recieves that message it will
            # tell us that it is ready to be killed.  This avoids a 'not saved
            # by a rule' occurance in certain timings.
            location = msg[1]
            self._logger.info("Received msgIdSetCamCanTerminate, loc: %s"
                              % location)
            if location in self._captureStreams:
                _, pipe, _, _ = self._captureStreams[location]
                self._selfAddSavedTimes.append(location)
                self._sendMsg(pipe, msg, location)
        elif msgId == MessageIds.msgIdSetTerminate:
            # Upon receiving this message we know the camera process is
            # waiting to be killed.  We will set its ping time to zero
            # causing it to be soon terminated by the run loop.
            location = msg[1]
            self._logger.info("Received msgIdSetTerminate, loc: %s"
                              % location)
            if location in self._captureStreams:
                p, pipe, pipeId, _ = self._captureStreams[location]
                self._captureStreams[location] = (p, pipe, pipeId, 0)
        elif msgId == MessageIds.msgIdWsgiPortChanged:
            # The camera process' web server is now operating on a new (or just
            # different) port, so we have to remember that.
            location = msg[1]
            port = msg[2]
            self._logger.info("Received msgIdWsgiPortChanged, loc: %s, port: %d" % (location, port))
            if location in self._captureStreams:
                self._setCameraStatus(location, None, port)
            self._processPendingLiveViewRequests(location)

        # Camera management messages
        elif msgId == MessageIds.msgIdCameraAdded:
            loc = msg[1]
            self._logger.info("Received msgIdCameraAdded, loc: %s, uri: %s"
                              % (loc, sanitizeUrl(msg[2])))

            # If we still have data from a prior cam with this name, remove it.
            self._cleanupCameraData(loc)

            # Save the camera URI
            self._cameraInfo[loc] = (msg[2], True, False, msg[3])
            self._syncCameraStateWithSchedule(loc)

            # If this location previously existed with alternate name
            # capitalization rename the old locations.
            dmNames = self._clipManager.getCameraLocations()
            for name in dmNames:
                if (name.lower() == loc.lower()) and (name != loc):
                    self._dataManager.updateLocationName(name, loc, 0)
                    self._clipManager.updateLocationName(name, loc, 0,
                            self._videoDir, self._userLocalDataDir)
                    self._dataManager.save()
                    self._clipManager.save()

        elif msgId == MessageIds.msgIdCameraEdited:
            origLoc = msg[1]
            newLoc = msg[2]
            uri = msg[3]
            extra = msg[4]
            changeSecs = msg[5]
            self._logger.info("Received msgIdCameraEdited, origLoc: %s, "
                              "curLoc: %s, uri: %s, extra: %s time: %s"
                              % (origLoc, newLoc, sanitizeUrl(uri), str(extra),
                                 str(changeSecs)))

            queuedMsg = [MessageIds.msgIdNone]

            if (changeSecs == -1) and (origLoc == newLoc):
                self._cameraInfo[newLoc] = (uri, self._cameraInfo[origLoc][1],
                                            self._cameraInfo[origLoc][2],
                                            extra)
            else:
                # For the rename at a given time we want to stop the old camera
                # and not yet run the new.  We'll set enabled to false now and
                # enable it after the rename is complete.
                self._cameraInfo[newLoc] = (uri, False,
                                            self._cameraInfo[origLoc][2],
                                            extra)
                if self._cameraInfo[origLoc][1]:
                    queuedMsg = [MessageIds.msgIdCameraEnabled, newLoc]

            if origLoc != newLoc:
                renameMessage = [MessageIds.msgIdRenameCamera, origLoc, newLoc, changeSecs, queuedMsg]
                cleanupTime = time.time() + _kRuleCleanupTimeout
                if origLoc in self._captureStreams:
                    proc, pipe, _, _ = self._captureStreams[origLoc]
                    self._sendMsg(pipe, [MessageIds.msgIdQuitWithResponse, renameMessage], origLoc)
                    self._pendingRenameMsg = (cleanupTime+10, proc, renameMessage)
                else:
                    # If the camera isn't running we won't be getting back the
                    # rename message so we need to send it to ourselves.
                    self._processQueueMessage(renameMessage)
                if origLoc in self._cameraInfo:
                    del self._cameraInfo[origLoc]
                if origLoc in self._ruleDicts:
                    self._pendingRuleCleanupDict[origLoc] = cleanupTime

                # If we still have data from a prior cam with this name, remove it.
                self._cleanupCameraData(newLoc)

            self._stopCamera(origLoc)

            # Open the camera with the new information if it is scheduled
            self._syncCameraStateWithSchedule(newLoc)
        elif msgId == MessageIds.msgIdCameraDeleted:
            camLoc = msg[1]
            self._logger.info("Received msgIdCameraDeleted, loc: %s" % camLoc)
            proc = None
            if camLoc in self._captureStreams:
                proc, _, _, _ = self._captureStreams[camLoc]
            self._stopCamera(camLoc)
            if camLoc in self._cameraInfo:
                del self._cameraInfo[camLoc]
            if camLoc in self._ruleDicts:
                self._pendingRuleCleanupDict[camLoc] = \
                                        time.time()+_kRuleCleanupTimeout
            if msg[2]:
                # We want to ensure that no more data will be added from this
                # location.  Since we don't care about anything pending or that
                # it will do, we just kill it.
                if proc:
                    self._terminateCameraProcess(proc)
                self._putMsgDC([MessageIds.msgIdRemoveDataAtLocation, camLoc])
                self._dataManager.removeCameraLocation(camLoc)
        elif msgId == MessageIds.msgIdCameraEnabled:
            camLoc = msg[1]
            self._logger.info("Received msgIdCameraEnabled, loc: %s" % (camLoc))
            # Update the enabled status.
            self._cameraInfo[camLoc] = (self._cameraInfo[camLoc][0], True,
                                        self._cameraInfo[camLoc][2],
                                        self._cameraInfo[camLoc][3])
            # Run the camera if it is currently scheduled.
            camState = self._syncCameraStateWithSchedule(camLoc)
            if camLoc not in self._captureStreams:
                if camState is None:
                    camState=kCameraOn
                self._setCameraStatus(camLoc, camState)
        elif msgId == MessageIds.msgIdCameraDisabled:
            camLoc = msg[1]
            self._logger.info("Received msgIdCameraDisabled, loc: %s" % camLoc)
            # Update the enabled status.
            self._cameraInfo[camLoc] = (self._cameraInfo[camLoc][0], False,
                                        self._cameraInfo[camLoc][2],
                                        self._cameraInfo[camLoc][3])
            # Stop the camera if it was running
            self._stopCamera(camLoc)
        elif msgId == MessageIds.msgIdRenameCamera:
            self._logger.info("Received msgIdRenameCamera, old: %s, new: %s, "
                              "changeTime: %s" % (msg[1], msg[2], str(msg[3])))
            # Convert to ms from seconds
            changeMs = msg[3]*1000

            # Remove any pending rename message.
            self._pendingRenameMsg = None

            # Ensure that objects and tagged times have been committed.
            self._flushIdleQueue()

            # TODO: This is slow....might need to fix this.  Unfortunately what
            #       follows is also slow (splitting clips, updating both
            #       databases...not sure where a 'good' place to put all this
            #       would really be...
            changeClip = self._clipManager.getFileAt(msg[1], changeMs, 1000)
            if changeMs != 0 and changeClip:
                # If we're going to be cutting a clip we need to find an exact
                # ms that occurred so we can properly update the created clips
                # and database objects.
                msList = getMsList(os.path.join(self._videoDir, changeClip), self._logger.getCLogFn())

                first, _ = self._clipManager.getFileTimeInformation(changeClip)

                bisectIndex = bisect.bisect_left(msList, changeMs-first)
                bisectIndex = max(0, min(bisectIndex, len(msList)))
                changeMs = msList[bisectIndex]+first

            self._dataManager.updateLocationName(msg[1], msg[2], changeMs)
            self._clipManager.updateLocationName(msg[1], msg[2], changeMs,
                    self._videoDir, self._userLocalDataDir)
            self._dataManager.save()
            self._clipManager.save()

            if len(msg) > 4:
                self._processQueueMessage(msg[4])
        elif msgId == MessageIds.msgIdRuleReloadAll or \
             msgId == MessageIds.msgIdHardwareAccelerationSettingUpdated:
            if msgId == MessageIds.msgIdHardwareAccelerationSettingUpdated:
                self._hardwareDevice = msg[2]
            try:
                self._logger.info("turning off all cameras...")
                for cameraLocation in self._captureStreams.keys():
                    self._stopCamera(cameraLocation)
                self._logger.info("loading updated camera info...")
                camMgr = CameraManager(self._logger)
                camMgr.load(msg[1])
                self._ruleDicts = {}
                self._logger.info("rules cleared, reloading them...")
                self._loadRules(camMgr)
                self._logger.info("restarting cameras...")
                self._initVideoStreams(camMgr)
            except:
                self._logger.error("rules reloading failed (%s)" %
                                   str(sys.exc_info()[1]))
                self._logger.error(traceback.format_exc())
            finally:
                self._netMsgServerClient.memstorePut(kMemStoreRulesLock,
                                                     False, -1)
                self._logger.info("rules got unlocked")
        elif msgId == MessageIds.msgIdCameraTestStart:
            uri = msg[1]
            forceTCP = msg[2]
            self._logger.info("Received msgIdCameraTestStart, uri: %s, tcp: %s" %
                              (sanitizeUrl(uri), forceTCP))
            self._startTestCamera(uri, {'forceTCP' : forceTCP})
        elif msgId == MessageIds.msgIdCameraTestStop:
            self._logger.info("Received msgIdCameraTestStop")
            self._stopTestCamera()
        elif msgId == MessageIds.msgIdPacketCaptureStart:
            cameraLocation = msg[1]
            delaySeconds = msg[2]
            pcapDir = msg[3]
            self._logger.info(
                "Received msgIdPacketCaptureStart, camLoc: %s, delaySeconds: %s, pcapDir: %s" %
                (cameraLocation, delaySeconds, pcapDir)
            )
            self._startPacketCapture(cameraLocation, delaySeconds, pcapDir)
            self._netMsgServerClient.setPacketCaptureInfo(
                    cPickle.dumps(self._pcapInfo)
            )
        elif msgId == MessageIds.msgIdPacketCaptureStop:
            self._logger.info("Received msgIdPacketCaptureStop")
            self._stopPacketCapture()
            self._netMsgServerClient.setPacketCaptureInfo(
                    cPickle.dumps({})
            )
        elif msgId == MessageIds.msgIdPacketCaptureStatus:
            code = msg[1]
            description = msg[2]
            self._pcapInfo['pcapStatus'] = code
            self._netMsgServerClient.setPacketCaptureInfo(
                    cPickle.dumps(self._pcapInfo)
            )
            self._logger.info(
                "Received msgIdPacketCaptureStatus, code: %s, description: %s" %
                (code, description)
            )
        elif msgId == MessageIds.msgIdPacketCaptureEnabled:
            code = msg[1]
            self._pcapInfo['pcapEnabled'] = code
            self._netMsgServerClient.setPacketCaptureInfo(
                    cPickle.dumps(self._pcapInfo)
            )
            self._logger.info("Received msgIdPacketCaptureEnabled, code: %s" %
                              code)
        elif msgId == MessageIds.msgIdDeleteVideo:
            camLoc = msg[1]
            startMs = msg[2]*1000
            stopMs = msg[3]*1000
            quick = msg[4]

            if camLoc in self._captureStreams and \
               camLoc in self._maxProcessedTime and \
               self._maxProcessedTime[camLoc] < stopMs:
                # If the camera is still running and hasn't finished processing
                # through our delete time we have to delay the delete, otherwise
                # it is possible that data will later come in and we'll wind up
                # with video not found errors.
                self._logger.info("Received msgIdDeleteVideo, loc: %s, start: %d, "
                                "stop: %d, cur: %d" % (camLoc, startMs, stopMs, self._maxProcessedTime[camLoc]))
                kDeletionRetryInterval = 1000
                self._delayedMessagesQueue.put((getTimeAsMs()+kDeletionRetryInterval,msg))
                return

            self._logger.info("Received msgIdDeleteVideo, loc: %s, start: %s, "
                              "stop: %s" % (camLoc, str(startMs), str(stopMs)))

            # Ensure that objects and tagged times have been committed.
            self._flushIdleQueue()

            self._dataManager.deleteCameraLocationDataBetween(camLoc, startMs,
                                                              stopMs)
            if quick:
                # If we're only doing a quick delete we can skip the clip
                # manager cleanup.
                return

            failedDeletes = self._clipManager.deleteCameraLocationDataBetween(
                                        camLoc, startMs, stopMs, self._videoDir,
                                        self._userLocalDataDir)
            for path in failedDeletes:
                self._logger.info("Queuing file for deletion: %s" % path)
                self._putMsgDC([MessageIds.msgIdDeleteFile, path])
        elif msgId == MessageIds.msgIdSetOnvifSettings:
            (uuid, selectedIp, username, password) = msg[1:]
            print("Set onvif settings %s" % username)
            self._onvifScanner.setDeviceSettings(uuid, (username, password), selectedIp)
        elif msgId == MessageIds.msgIdActiveCameraSearch:
            (isMajor, ) = msg[1:]
            self._logger.debug("Received msgIdActiveCameraSearch: %s" %
                               str(isMajor))

            # Do an active search on a major request; this is called once when
            # the camera wizard comes up...
            if isMajor:
                if not self._upnpScanner is None:
                    self._upnpScanner.force()
                if not self._onvifScanner is None:
                    self._onvifScanner.force()

            # Always do webcam search...
            # ...this is not super fast; hopefully we don't take up too much
            # back end time doing this...
            localCameraNames = strmGetLocalCameraNames(self._logger.getCLogFn())
            self._logger.info("Active camera search, found " +
                    str(localCameraNames))
            self._netMsgServerClient.setLocalCameraNames(localCameraNames)
        elif msgId == MessageIds.msgIdFileMoveFailed:
            self._logger.info("Received msgIdFileMoveFailed, target: %s"
                              % msg[1])
            self._pendingFileMoves[msg[1]] = (msg[2],
                                              time.time()+_kTmpFileLifetime)

        # Storage setting messages
        elif msgId == MessageIds.msgIdSetMaxStorage:
            self._logger.info("Received msgIdSetMaxStorage, size: %i" % msg[1])
            self._putMsgDC(msg)
            self._maxStorage = msg[1]
        elif msgId == MessageIds.msgIdSetVideoLocation:
            videoDir = msg[1]
            moveData = msg[2]
            preserveExisting = msg[3]
            self._logger.info("Received msgIdSetVideoLocation, loc: %s, "
                              "move: %s, preserveExisting: %s"
                              % (videoDir, moveData, preserveExisting))
            self._setNewVideoLocation(videoDir, moveData, preserveExisting)
        # Storage setting messages
        elif msgId == MessageIds.msgIdSetCacheDuration:
            self._logger.info("Received msgIdSetCacheDuration, hours: %i" % msg[1])
            self._putMsgDC(msg)
            self._cacheDuration = msg[1]
        elif msgId == MessageIds.msgIdSetRecordInMemory:
            self._logger.info("Received msgIdSetRecordInMemory, value: %s" % str(msg[1]))
            restart = (msg[1] != self._recordInMemory)
            self._recordInMemory = msg[1]
            # propagate this setting to camera processes
            if restart:
                for camLoc in self._captureStreams:
                    self._childProcLocalQueue.append(([MessageIds.msgIdCameraDisabled, camLoc], time.time()))
                    self._childProcLocalQueue.append(([MessageIds.msgIdCameraEnabled, camLoc], time.time()))
        elif msgId == MessageIds.msgIdSetClipMergeThreshold:
            value = msg[1]
            effectiveTime = getTimeAsMs()
            self._logger.info("Modifying clip merge preferences to %d at %d" % (value, effectiveTime))
            self._clipMergeThreshold = value
            self._clipManager.setClipMergeThreshold(effectiveTime, value, True)
            self._broadcastMsg([MessageIds.msgIdSetClipMergeThreshold, effectiveTime, value])
        elif msgId == MessageIds.msgIdSetEmailSettings:
            # Update existing settings so that response gets updated right away.
            self._emailSettings.update(msg[1])
            self._logger.info("Received msgIdSetEmailSettings")

        elif msgId == MessageIds.msgIdSetFtpSettings:
            # Forward onto the response runner queue...
            self._putMsgRR(msg)
            self._ftpSettings.update(msg[1])
            self._logger.info("Received msgIdSetFtpSettings")

        elif msgId == MessageIds.msgIdSetNotificationSettings:
            # Forward onto the response runner queue...
            self._putMsgRR(msg)
            self._notificationSettings.update(msg[1])
            self._logger.info("Received msgIdSetNotificationSettings")

        elif msgId == MessageIds.msgIdSetTimePrefs:
            self._logger.info("Received msgIdSetTimePrefs")
            self._timePrefs = (msg[1], msg[2])
            self._broadcastMsg([MessageIds.msgIdSetTimePrefs, msg[1], msg[2]])

        elif msgId == MessageIds.msgIdSetVideoSetting:
            self._logger.info("Received msgIdSetVideoSetting")
            self.videoSettings[msg[1]] = msg[2]
            # propagate live video quality setting to camera processes
            self._broadcastMsg(msg)

        elif msgId == MessageIds.msgIdSetDebugConfig:
            self._broadcastMsg(msg)
            self._putMsgDC(msg)
            self._putMsgRR(msg)
            self._putMsgWS(msg)
            global _kDebugConfig
            _kDebugConfig = msg[1]
            self._debugLogManager.SetLogConfig(_kDebugConfig)

        # Rule messages
        elif msgId == MessageIds.msgIdRuleAdded:
            ruleName = msg[1].lower()
            self._logger.info("Received msgIdRuleAdded, rule: %s" % ruleName)

            # Retrieve the new rule, query, schedule information, and responses
            rule = cPickle.loads(msg[2])
            queryModel = cPickle.loads(msg[3])
            query = queryModel.getUsableQuery(self._dataManager)
            camLoc = queryModel.getVideoSource().getLocationName()
            isScheduled, nextSchedChange = rule.getScheduleInfo()
            responses = self._loadResponses(queryModel, camLoc, query, ruleName)

            self._putMsgRR([MessageIds.msgIdSetLocalExportSettings, self._localExportSettings])

            # Tell the query about the processing size if the camera is open.
            if camLoc in self._cameraProcSizes:
                procSize = self._cameraProcSizes[camLoc]
                query.setProcessingCoordSpace(procSize)

            # Add to the rule dict
            if camLoc not in self._ruleDicts:
                self._ruleDicts[camLoc] = {}
            self._ruleDicts[camLoc][ruleName] = \
                        (rule, isScheduled, nextSchedChange, query, responses)

            # Ensure the related camera is now running if scheduled.
            self._syncCameraStateWithSchedule(camLoc)

        elif msgId == MessageIds.msgIdRuleScheduleUpdated:
            # Find the edited rule in ruleDicts
            ruleName = msg[1].lower()
            schedule = msg[2]

            self._logger.info("Received msgIdRuleScheduleUpdated, rule: %s"
                              % ruleName)

            for camLoc in self._ruleDicts:
                if ruleName in self._ruleDicts[camLoc]:
                    # Update the rule schedule
                    rule, _, _, query, responses = \
                                            self._ruleDicts[camLoc][ruleName]
                    rule.setSchedule(schedule)
                    isScheduled, nextChange = rule.getScheduleInfo()
                    self._ruleDicts[camLoc][ruleName] = \
                            (rule, isScheduled, nextChange, query, responses)
                    # Tell the query about the processing size if the camera is open.
                    if camLoc in self._cameraProcSizes:
                        procSize = self._cameraProcSizes[camLoc]
                        query.setProcessingCoordSpace(procSize)
                    if not isScheduled:
                        query.reset()

                    # Ensure the related camera is now running if scheduled.
                    self._syncCameraStateWithSchedule(camLoc)
        elif msgId == MessageIds.msgIdRuleDeleted:
            # Delete the specified rule
            ruleName = msg[1].lower()
            self._logger.info("Received msgIdRuleDeleted, rule: %s" % ruleName)

            for camLoc in self._ruleDicts:
                if ruleName in self._ruleDicts[camLoc]:
                    del self._ruleDicts[camLoc][ruleName]

                    # Ensure the related camera is stopped if not scheduled.
                    self._syncCameraStateWithSchedule(camLoc)

            if ruleName in self._localExportSettings:
                del self._localExportSettings[ruleName]

        elif msgId == MessageIds.msgIdRuleEnabled:
            # Enable or disable the specified rule
            ruleName = msg[1].lower()
            enabled = msg[2]

            self._logger.info("Received msgIdRuleEnabled, rule: %s, "
                              "enabled: %s" % (ruleName, str(enabled)))

            for camLoc in self._ruleDicts:
                if ruleName in self._ruleDicts[camLoc]:
                    rule, _, _, query, responses = \
                                            self._ruleDicts[camLoc][ruleName]
                    # Tell the query about the processing size if the camera is open.
                    if camLoc in self._cameraProcSizes:
                        procSize = self._cameraProcSizes[camLoc]
                        query.setProcessingCoordSpace(procSize)

                    rule.setEnabled(enabled)
                    if not enabled:
                        query.reset()

                    # Ensure the related camera is running if scheduled.
                    self._syncCameraStateWithSchedule(camLoc)

        # Camera viewing messages
        elif msgId == MessageIds.msgIdEnableLiveView:
            cameraLocation = msg[1]
            if not self._isCameraConnected(cameraLocation):
                self._logger.info("Delaying enabling live view until %s is connected" % ensureUtf8(cameraLocation))
                self._pendingLiveViewStatus[cameraLocation] = msg
            else:
                self._setLiveViewStatus(msg, False)
        elif msgId == MessageIds.msgIdDisableLiveView:
            cameraLocation = msg[1]
            if not self._isCameraConnected(cameraLocation):
                self._logger.info("Delaying disabling live view until %s is connected" % ensureUtf8(cameraLocation))
                self._pendingLiveViewStatus[cameraLocation] = msg
            else:
                self._setLiveViewStatus(msg, False)
        elif msgId == MessageIds.msgIdFlushVideo:
            cameraLocation = msg[1]
            if self._isCameraConnected(cameraLocation):
                self._logger.debug("Received msgIdFlushVideo, loc: %s" % cameraLocation)
                self._sendMsgLoc(msg, cameraLocation)

                # This likely means a search is about to occur.  Try to move any
                # pending files now to avoid video not founds.
                self._moveTmpFiles()
        elif msgId == MessageIds.msgIdSetLiveViewParams:
            cameraLocation = msg[1]
            if not self._isCameraConnected(cameraLocation):
                self._logger.debug("Delaying setting live view params until %s is connected"  % ensureUtf8(cameraLocation))
                self._pendingLiveViewSettings[cameraLocation] = msg
            else:
                self._setLiveViewParams(msg, False)
        # Error messages
        elif msgId == MessageIds.msgIdInsufficientSpace:
            self._logger.info("Received msgIdInsufficientSpace")
            self._netMsgServerClient.addMessage([MessageIds.msgIdOutOfDiskSpace,
                                                 self._videoDir])
            # TODO: What to do?  Start shutting down cameras?
            assert False, "Insufficient disk space available"
        elif msgId == MessageIds.msgIdDatabaseCorrupt:
            self._logger.info("Received msgIdDatabaseCorrupt")
            self._handleCorruptDatabase()

        # Webserver messages
        elif msgId == MessageIds.msgIdWebServerSetPort:
            newPort = msg[1]
            lic = self._licenseManager.licenseData()
            if -1 != newPort and not hasPaidEdition(lic):
                self._logger.warn("webserver disabled due to license")
                newPort = -1
            self._logger.info("web server port changing to %d ..." % newPort)
            self._putMsgWS([msg[0], newPort])
        elif msgId == MessageIds.msgIdWebServerSetAuth:
            self._logger.info("web server auth changed")
            self._putMsgWS([msg[0], msg[1]])
        elif msgId == MessageIds.msgIdWebServerEnablePortOpener:
            self._logger.info("port opener enabled flag changed (%s)" % msg[1])
            self._putMsgWS([msg[0], msg[1]])
        elif msgId == MessageIds.msgIdWebServerPing:
            pass

        # Licensing messages
        elif msgId == MessageIds.msgIdUserLogin:
            self._licenseManager.userLogin(msg[1], msg[2], msg[3])
            self._putMsgRR([MessageIds.msgIdSetServicesAuthToken, self._licenseManager.getAuthToken()])
        elif msgId == MessageIds.msgIdRefreshLicenseList:
            self._licenseManager.listRefresh(msg[1])
        elif msgId == MessageIds.msgIdAcquireLicense:
            self._licenseManager.acquire(msg[1], msg[2])
        elif msgId == MessageIds.msgIdUnlinkLicense:
            self._licenseManager.unlink(msg[1])
        elif msgId == MessageIds.msgIdUserLogout:
            self._licenseManager.userLogout()

        # Test IFTTT response
        elif msgId == MessageIds.msgIdTriggerIfttt:
            self._putMsgRR(msg)
        elif msgId == MessageIds.msgIdSendIftttState:
            self._iftttStatePending = (msg[1], msg[2])
        elif msgId == MessageIds.msgIdUpdateUpnp:
            self._updateUpnp(msg[1], msg[2], msg[3])
        elif msgId == MessageIds.msgIdUpdateOnvif:
            self._updateOnvif(msg[1], msg[2], msg[3])
        elif msgId == MessageIds.msgIdSubmitClipToSighthound:
            camera = msg[1]
            note = msg[2]
            startTime = int(msg[3])
            duration = int(msg[4])
            self._logger.info("Got a request to upload clip from %s at [%d-%d]" % \
                        (camera, startTime, startTime+duration))
            if self._clipUploader is None:
                self._clipUploader = ClipUploader(self._logger,
                                            self._licenseManager.getAccountId(),
                                            self._licenseManager.getAuthToken(),
                                            self._clipDbPath,
                                            self._objDbPath,
                                            self._videoDir,
                                            self._userLocalDataDir)
            self._clipUploader.queueUpload(camera, note, startTime, duration)
        else:
            self._logger.error("unknown message identifier %d" % msgId)


    ###########################################################
    def _mapDbId(self, pipeId, dbId):
        """Handle the fact that the queued data manger might give a temp ID.

        If the queued data manager needs to add object frames before it has
        received the real dbId on the pipe, it will use a temporary ID that
        is a tuple of (camId, camObjId).  This function will take in whatever
        type of ID the queued data manager provides and will return a real dbId.

        This function will also do maintenance on the self._tempIdMap.
        Specifically:
        - If the queued data manager provides us with a real dbId that is in
          our map, it means that the queued data manager has received the
          real ID on the pipe and will no longer be using the temp ID.  We
          can delete it from the map.  We also delete anything older just as
          a general cleanup task, since we know that the queued data manager
          always receives things in order.
        - If the queued data manager provides us with something that is in
          our map, we do the mapping.
        - If the queued data manager provides us with another ID, we assume it's
          a real dbId and just return.

        @param  pipeId    The pipeId ID.
        @param  dbId      The database ID from the queued data manager; may be
                          a real dbId or a temp one.
        @return realDbId  A dbId that is guaranteed to be real, unless there is
                          a serious error (in which case it might still be a
                          tuple).
        """
        # This shouldn't happen, but better to be paranoid...
        if pipeId not in self._tempIdMap:
            return dbId

        i = 0
        for (thisCamObjId, thisDbId) in self._tempIdMap[pipeId]:
            if dbId == thisDbId:
                self._logger.debug("Real ID (%d) used; deleting (%d, %d)" % (
                                   thisDbId, pipeId, thisCamObjId))

                # They're using the real DB ID.  Delete old temp mappings...
                del self._tempIdMap[pipeId][:i+1]
                break
            elif dbId == (pipeId, thisCamObjId):
                self._logger.debug("Temp ID (%d, %d) used; returning (%d)" % (
                                   pipeId, thisCamObjId, thisDbId))
                dbId = thisDbId
                break
            i += 1

        return dbId


    ###########################################################
    def alreadyRunning(self):
        """Determine whether an instance is already running.

        @return alreadyRunning  True if another instance is running.
        """
        client = self._getXMLRPCClient()
        if client is None:
            return False

        # if there is a port file but we can't connect to the server, assume
        # the previous server terminated improperly.
        try:
            if 'dead' != client.ping(): #PYCHECKER OK: Function exists on xmlrpc server
                return True
        except Exception:
            pass

        # Wait and try again in the off chance the server was still starting
        time.sleep(1)
        try:
            if 'dead' != client.ping(): #PYCHECKER OK: Function exists on xmlrpc server
                return True
        except Exception:
            pass

        return False


    ###########################################################
    def _getXMLRPCClient(self, timeout=_kNetworkMessageServerTimeout):
        """Return a connection to the xmlrpc server.

        @param  timeout  Connection timeout, in milliseconds.
        @return client   A client connection to the xmlrpc server, or None.
        """
        # If there is no port file, we're not running
        try:
            portFile = open(
                os.path.join(self._userLocalDataDir, kPortFileName), 'r')
            port = cPickle.load(portFile)
            portFile.close()
        except Exception:
            return None

        return ServerProxyWithClientId('http://127.0.0.1:%s' % str(port),
                TimeoutTransport(timeout), allow_none=True)


    ###########################################################
    def _getCameraScheduleStatus(self, cameraLocation, useCache=True):
        """Retrieve a camera's scheduled status

        @param  cameraLocation  The name of the camera to retrieve info for.
        @param  useCache        True if cached values should be used, False to
                                requery each rule.
        @return isScheduled     True if the camera is currently scheduled
        @return nextChange      The next time in ms the status will change, or
                                None.
        """
        ruleDict = self._ruleDicts.get(cameraLocation, {})

        isScheduled = False
        nextChange = None

        for ruleName in ruleDict:
            rule, scheduled, change, query, responses = ruleDict[ruleName]
            if (not rule.isEnabled()) or (not responses):
                continue

            if not useCache:
                scheduled, change = rule.getScheduleInfo()
                ruleDict[ruleName] = (rule, scheduled, change, query, responses)

            isScheduled = isScheduled or scheduled
            if change and (not nextChange or (nextChange > change)):
                nextChange = change

        return isScheduled, nextChange


    ###########################################################
    def _syncCameraStateWithSchedule(self, cameraLocation):
        """Ensure a camera is in the state dictated by its current schedule.

        @param  cameraLocation  The camera to check.
        @return camState        The new camera state if it changed, 'None'
                                otherwise.
        """
        camState = None
        if cameraLocation not in self._cameraInfo:
            return camState

        _, enabled, _, extra = self._cameraInfo[cameraLocation]

        if not enabled or extra.get('frozen', False):
            # If we're not currently enabled or frozen, ensure we're not running.
            camState = self._stopCamera(cameraLocation)

        # If we're in auto record mode, check the schedule and act accordingly.
        scheduled, changeTime = self._getCameraScheduleStatus(cameraLocation)

        if changeTime and changeTime < time.time():
            # If this is true we need to update the cache.
            scheduled, changeTime = self._getCameraScheduleStatus(
                cameraLocation, False)

        if scheduled:
            camState = self._openCamera(cameraLocation) or camState
        else:
            camState = self._stopCamera(cameraLocation) or camState

        return camState


    ###########################################################
    def _setNewVideoLocation(self, location, preserveData=True,
                             keepExisting=False):
        """Set a new video location to store archived video.

        @param  location      The path at which to store video.
        @param  preserveData  If True existing data should be moved to the new
                              location.
        @param  keepExisting  If True and preserveData is False, data at the
                              new location will not be removed and the
                              databases will not be reset.
        """
        if type(location) == str:
            location = location.decode('utf-8')
        success = False
        try:
            self._logger.info("Shutting down processes.")
            # Stop cameras, disk cleaner, and response runner.
            procs = [streamInfo[0] for streamInfo in self._captureStreams.values()]
            for cameraLocation in self._captureStreams.keys():
                self._stopCamera(cameraLocation)

            if self._diskCleanupProc:
                procs.append(self._diskCleanupProc)
                self._putMsgDC([MessageIds.msgIdQuit])

            if self._responseRunnerProc:
                procs.append(self._responseRunnerProc)
                self._putMsgRR([MessageIds.msgIdQuit])

            # We'll wait for a while to let them quit gracefully, but we don't
            # want it to be forever...
            startTime = time.time()
            anyAlive = True
            while anyAlive and (time.time()-startTime < 45):
                for proc in procs:
                    if proc.is_alive():
                        time.sleep(1)
                        break
                else:
                    anyAlive = False

            self._logger.info("Terminating any remaining processes.")

            # Ensure all processes are dead in case they didn't quit themselves.
            for proc in procs:
                self._terminateCameraProcess(proc)

            destination = os.path.join(location, kVideoFolder)
            if preserveData:
                # Move data.
                try:
                    if os.path.isdir(self._videoDir):
                        self._logger.info("Beginning move from %s to %s" % (self._videoDir, destination))
                        try:
                            origVolName, origVolType = getVolumeNameAndType(self._videoDir)
                            self._logger.info("Source drive = %s %s" % (origVolName, origVolType))
                            newVolName, newVolType = getVolumeNameAndType(location)
                            self._logger.info("Target drive = %s %s" % (newVolName, newVolType))
                        except Exception:
                            self._logger.error("Get volume information failed.", exc_info=True)
                        shutil.move(self._videoDir, destination)
                        self._logger.info("Finished move.")
                    else:
                        self._logger.info("Source video directory did not exist.")
                    success = True
                except Exception, e:
                    if WindowsError and (isinstance(e, WindowsError) and e.errno == errno.EACCES):
                        if os.path.isdir(destination):
                            # Windows error 32 = remove failed, file in use.
                            self._logger.warn("Access error, but we assume transfer completed.")
                            success = True
                        else:
                            # Windows error 5? = access is denied.
                            self._logger.error("Access error, couldn't move files.", exc_info=True)
                    elif (isinstance(e, OSError) and e.errno == errno.ENOTEMPTY):
                        success = True
                    else:
                        self._logger.error("Moving data failed.", exc_info=True)

                    if success:
                        # The move succeeded, but the fact that there was an exception signifies
                        # that the source could not be completely removed.
                        self._netMsgServerClient.addMessage(
                                        [MessageIds.msgIdDirectoryRemoveFailed,
                                         self._videoDir])
                        self._logger.warn("Not all data could be deleted "
                                          "from the previous video location.", exc_info=True)
            else:
                # Ensure the new directory can be created.
                try:
                    os.makedirs(destination)
                except Exception, e:
                    pass
                if os.path.isdir(destination):
                    success = True
                    if not keepExisting:
                        self._dataManager.reset()
                        self._clipManager.reset()

                        # Remove the existing data.
                        try:
                            if os.path.isdir(self._videoDir):
                                shutil.rmtree(self._videoDir)
                        except Exception:
                            self._logger.error("Removing data failed.",
                                               exc_info=True)
                        if os.path.isdir(self._videoDir):
                            self._logger.warn("Not all data could be deleted "
                                            "from the previous video location.")
                            self._netMsgServerClient.addMessage(
                                        [MessageIds.msgIdDirectoryRemoveFailed,
                                         self._videoDir])
                else:
                    self._logger.warn("The new directory could not be created, "
                                      "aborting location change.")
                    self._netMsgServerClient.addMessage(
                        [MessageIds.msgIdDirectoryCreateFailed, destination])

            # If we succeeded commit the change to the prefs file.
            if success:
                self._videoDir = destination
                self._dataManager.setVideoStoragePath(destination)
                self._clipUploader.updateVideoStoragePath(destination)

            self._logger.info("Move status: %s.  Restarting processes." % str(success))

            # Restart the disk cleaner.
            self._initDiskCleanup(self._maxStorage)

            # Restart the response runner.
            self._initResponseRunner()

            # Restart any cameras that should be running.
            for cameraName in self._cameraInfo:
                self._syncCameraStateWithSchedule(cameraName)
        finally:
            # Ensure that no matter what errors occur we always let the
            # front end know to stop blocking.
            self._netMsgServerClient.setVideoLocationChangeStatus(location,
                                                                  success)


    ###########################################################
    def _moveTmpFiles(self):
        """Move any pending tmp videos to their archive location."""
        now = time.time()

        kMinFreePercentageSys = 1          # Require at least 1% free drive space on system drive (start trim)
                                           # The idea is to start trimming pending moves, before camera processes deem
                                           # storage situation critical (which happens at 1GB)
        kMinFreeSpaceMB       = 2*1024     # require at least 2GB left, before we remove files
                                           # which previously failed to move to permanent storage location


        for targetPath, (loc, lastTime) in self._pendingFileMoves.items():
            src = os.path.join(self._tmpDir, loc, os.path.basename(targetPath))
            dst = os.path.join(self._videoDir, targetPath)
            moved = False
            try:
                if os.path.isfile(src):
                    shutil.move(src, dst)
                    moved = True
                else:
                    self._logger.error("Pending move item " + ensureUtf8(src) + " does not exist")
            except Exception, e:
                self._logger.error("Failed to move file (" + ensureUtf8(src) + "->" + ensureUtf8(dst) + "): " + str(e))

            if moved:
                # If it was successfully relocated remove it from the dict.
                self._logger.info("Moved tmp file %s" % ensureUtf8(src))
                del self._pendingFileMoves[targetPath]
            else:
                diskCritical = not checkFreeSpace(self._tmpDir, kMinFreeSpaceMB, kMinFreePercentageSys, None)

                if now > lastTime:
                    reason = "move timeout expired"
                elif diskCritical:
                    reason = "insufficient local storage"
                else:
                    reason = ""

                if now > lastTime or diskCritical:
                    # If it hasn't been moved in the time we allocated, delete the
                    # file and remove the associated time period from the databases.
                    self._logger.info("Removing tmp file %s due to %s" % (ensureUtf8(src), reason))
                    del self._pendingFileMoves[targetPath]
                    try:
                        os.remove(src)
                    except Exception:
                        self._logger.info("Queuing file for deletion: %s" % ensureUtf8(src))
                        self._putMsgDC([MessageIds.msgIdDeleteFile, src])
                    start, stop = \
                        self._clipManager.getFileTimeInformation(targetPath.lower())
                    if start != -1:
                        # Remove these times from the object database.
                        self._dataManager.deleteCameraLocationDataBetween(
                                                                loc, start, stop)
                        # Remove this file from the clip database.
                        self._clipManager.removeClip(targetPath.lower())


    ###########################################################
    def _handleCorruptDatabase(self):
        """Deal with a a corrupt database.
        """
        self._logger.error("Corrupt database files detected - quitting")
        if not setCorruptDatabaseStatus(["corrupted"], self._userLocalDataDir):
            self._logger.error("Could not drop corruption status file in %s" %
                               ensureUtf8(self._userLocalDataDir))
        self._quit()


    ###########################################################
    def _removeEmptyDirs(self, dirName):
        """Remove any empty directories we've left around.

        NOTE: It would be nice if this could happen periodically, but I'm a
              bit of afraid of conflicts with a camera process about to move a
              file and the destination directory is deleted from under it...
              At least folders don't really take up any disk space so deleting
              them only when the back end starts seems ok.

        @param dirName  The directory in which to remove empty directories.
        """
        _kMaxCleanupTime = 30 # Front-end will timeout after 90s ... lets not run this cleanup for longer than 30s
        _kWarnCleanupTime = 10

        status = "completed"
        start = time.time()
        for path, dirs, files in os.walk(dirName, False):
            # Note: we skip normalizePath() here since we do no
            # string comparisons.
            if not dirs and not files and path != dirName:
                try:
                    self._logger.info("Removing folder %s" % ensureUtf8(path))
                    os.rmdir(path)
                except Exception:
                    self._logger.warning("Couldn't remove %s" % ensureUtf8(path))
            diff = time.time() - start
            if diff > _kMaxCleanupTime:
                status = "aborted"
                break
        diff = time.time() - start
        if diff > _kWarnCleanupTime:
            self._logger.info("Finished empty folder cleanup in %d seconds, %s" % (int(diff), status))



##############################################################################
def _forcedQuitCallback():
    """A callback to notify the current app if a force quit ever happens.

    This is done here so that we don't keep registering if we restart; also
    doing things this way keeps anyone from holding a reference to the app.

    NOTE: the service nowadays takes care about detection a shutdown taking care
          about ending the callback, so it will only work during development ...
    """
    if _app is not None and not serviceAvailable():
        _app.forceQuit()
__callbackFunc = registerForForcedQuitEvents(_forcedQuitCallback) #PYCHECKER OK: (__callbackFunc) not used

##############################################################################
def main(userDataDir, *otherArgs):
    global _app

    userDataDir = os.path.expanduser(userDataDir.decode('utf-8'))
    wantQuit = False

    # We want to continually launch the app unless it explicitly terminated.
    while not wantQuit:
        _app = BackEndApp(userDataDir)
        try:
            _app.run()
        except BaseException:
            # Catch ALL exceptions, not just subclasses of Exception.  That will
            # catch things like KeyboardInterrupt.
            #
            # ...if we don't do this and we get a keyboard interrupt, badness
            # ensues.
            getLogger(_kLogName, None, _kLogSize).error("Unhandled exception", exc_info=True)

        # Retrieve whether or not the app meant to quit.
        wantQuit = _app.wantQuit

        try:
            # Ensure all resources used by the app are freed and destroyed
            # immediately rather than waiting for the destructor to be called.
            _app.cleanup()
        except BaseException:
            # We always want the back end to restart, so ignore any exceptions.
            getLogger(_kLogName, None, _kLogSize).error("Unhandled exception in cleanup", exc_info=True)

        sys.exc_clear()
        _app = None

    # make sure logging and all of its resources get closed properly
    logging.shutdown()
