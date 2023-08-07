#! /usr/local/bin/python

#*****************************************************************************
#
# CameraCapture.py
#    Module responsible for running individual camera processes,
#    one instance/process per camera.
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Arden.ai, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Arden.ai, Inc.
# by emailing opensource@ardenai.com
#
# This file is part of the Arden AI project which can be found at
# https://github.com/ardenaiinc/ArdenAI
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
Contains the CameraCapture class.
"""

# Python imports...
import os, glob
import sys
import time
import collections
import cStringIO, PIL, random, cgi, traceback, re, threading

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.process.ProcessUtils import checkMemoryLimit
from vitaToolbox.windows.winUtils import registerForForcedQuitEvents
from vitaToolbox.networking.SanitizeUrl import processUrlAuth
from vitaToolbox.networking.WsgiServer import WsgiServer
from vitaToolbox.networking.WsgiServer import makeServerAddressInfos
from vitaToolbox.listUtils.RandomRange import randomRange
from vitaToolbox.strUtils.EnsureUnicode import simplifyString, ensureUtf8
from vitaToolbox.path.GetDiskSpaceAvailable import checkFreeSpace

# Local imports...
from appCommon.CommonStrings import kRemoteFolder, isLocalCamera, kMinFreeSysDriveSpaceMB
from ClipManager import ClipManager
import MessageIds
from QueuedDataManagerCloud import QueuedDataManagerCloud
from VideoPipeline import VideoPipeline
from videoLib2.python.StreamReader import StreamReader
from videoLib2.python.ffmpegLog import FFmpegLog
from videoLib2.python.VideoLibUtils import getTimestampFlags

from appCommon.TimingInfo import TimingInfo
from appCommon.DebugPrefs import getDebugPrefAsInt

from BackEndPrefs import BackEndPrefs, kLiveMaxBitrate, kLiveMaxBitrateDefault, kHardwareAccelerationDevice
from BackEndPrefs import kLiveEnableTimestamp, kLiveEnableTimestampDefault, kLiveMaxResolution, kLiveMaxResolutionDefault
from BackEndPrefs import kLiveEnableFastStart, kLiveEnableFastStartDefault, kGenThumbnailResolution, kGenThumbnailResolutionDefault
from BackEndPrefs import kClipMergeThreshold, kClipMergeThresholdDefault
from DebugLogManager import DebugLogManager

def OB_KEYARG(a): return a


# Constants...

# Time to wait between retry attempts when connecting to a camera
_kRetryTimeList = [0, 20, 20, 20, 60]
_kMaxRetries = 10

# Min time to sleep when we have a bogus URL...
_kBogusMinSleepTime = 10

# Time before giving up on the stream as 'lost', in milliseconds
_kTimeout = 15000

# Time how long an HLS request willing to wait before a file is available
_kStartStreamTimeout = 5000

# We'll always send out a notify (even if no object frames) ever this many
# milliseconds...
_kMaxNoNotifyMs = 1000

# The number of seconds considered to be a remote timeout. A remote client
# must repeatedly load a live stream (M3U8) to keep its generation going.
_kLiveStreamTimeoutSecs = 10

# The frequency at which we ping the back end to inform that we're still alive
_kPingSecInterval = 120

# For webcams, we skip the pipeline processing for this many initial frames.
# This avoids tracking initial AWB and AE changes caused by camera startup.
_kLocalCamFramesToSkip = 25

# Number of seconds to wait between opening new ports or trying to find a free
# port to bind to respectively.
_kWsgiServerPortOpenDelay = .5

# Number of seconds to wait if all ports are n/a. This is very unlikely though.
_kWsgiServerPortOpenLoopDelay = 30

# The IP address we bind out WSGI server to.
_kWsgiServerAddress = "127.0.0.1"

# WSGI query parameter and default: width of the JPEG image to return
_kWsgiParamWidth = "width"
_kWsgiParamWidthDefault = 320

# WSGI query parameter: height of the JPEG image to return
_kWsgiParamHeight = "height"
_kWsgiParamHeightDefault = 240

# Number of seconds to wait for the WSGI server to shut down. Past this point
# we commence closing everything, but there is the risk of course that we then
# run into something destroyed (and potentially crash).
_kWsgiShutdownTimeout = 5

# How often we check current drive utilization limits
_kFreeSpaceCheckInterval = 30

# Triggers a warning if we get more than that between frame arrival or timestamps
_kFrameWarningTimeout = 1000

# How often should we log memory stats
_kMemoryStatsInterval = 15*60*1000

# Message when we drop camera connection due to insufficient space
_kDiskSpaceMessage = "Low disk space on system volume"

###############################################################
def runCapture(msgQueue, cameraPipe, dataMgrPipe, dataMgrId, cameraLocation, #PYCHECKER OK: Function has too many arguments
               cameraUri, clipMgrPath, tmpPath, archivePath, userDir, extras):
    """Create and start a CameraCapture process.

    @param  msgQueue        A queue to add received commands to.
    @param  cameraPipe      A pipe to receive control messages on.
    @param  dataMgrPipe     A pipe to receive data manager feedback on.
    @param  dataMgrId       An id for referencing the connection to the dm.
    @param  cameraLocation  The name of the camera location.
    @param  cameraUri       The uri used to access the camera.
    @param  clipMgrPath     Path to the clip manager.
    @param  tmpPath         Path to the directory where currently recording
                            videos should be stored.
    @param  archivePath     Path to the directory where completed videos should
                            be stored.
    @param  userDir         Directory where user data should be stored
    @param  extras          A dict of configuration values.
    """
    camera = CameraCapture(msgQueue, cameraPipe, dataMgrPipe, dataMgrId,
                           cameraLocation, cameraUri, clipMgrPath, tmpPath,
                           archivePath, userDir, extras)
    camera.run()

##############################################################################
class OutOfSpaceException(Exception):
    pass

class TooManyFailuresException(Exception):
    pass

##############################################################################
class CameraCapture(object):
    """A class for capturing and processing a video stream."""
    ###########################################################
    def __init__(self, msgQueue, cameraPipe, dataMgrPipe, dataMgrId, #PYCHECKER OK: Function has too many arguments
                 cameraLocation, cameraUri, clipMgrPath, tmpPath, archivePath,
                 userDir, extras):
        """Initialize CameraCapture.

        @param  msgQueue        A queue to add received commands to.
        @param  cameraPipe      A pipe to receive control messages on.
        @param  dataMgrPipe     A pipe to receive data manager feedback on.
        @param  dataMgrId       An id for referencing the connection to the dm.
        @param  cameraLocation  The name of the camera location.
        @param  cameraUri       The uri used to access the camera.
        @param  clipMgrPath     Path to the clip manager.
        @param  tmpPath         Path to the directory where currently recording
                                videos should be stored.
        @param  archivePath     Path to the directory where completed videos
                                should be stored.
        @param  userDir         Directory where user data should be stored
        @param  extras          A dict of configuration values.
        """
        # Call the superclass constructor.
        super(CameraCapture, self).__init__()

        self._timingInfo    = TimingInfo({ TimingInfo.kOutputInterval : 10, TimingInfo.kSession : id( self )});

        # Save data dir and setup log dir...  SHOULD BE FIRST!
        self._userLocalDataDir = userDir
        self._logDir = os.path.join(self._userLocalDataDir, "logs", "cameras")
        self._logger = getLogger(cameraLocation + '.log', self._logDir)
        self._logger.grabStdStreams()

        assert type(userDir) == unicode
        assert type(clipMgrPath) == unicode

        self._lastMemoryStats = 0
        self._lastFreeSpaceCheck = 0
        self._cleaningUp = False
        self._userDir = userDir

        self._queue = msgQueue
        self._pipe = cameraPipe
        self._cameraUri = cameraUri
        self._cameraLocation = cameraLocation
        self._tmpPath = tmpPath
        self._archivePath = archivePath

        self._extras = extras
        width, height = extras.get('recordSize', (320, 240))
        self._liveImageMemorySize = width*height*3

        self._runner = None
        self._ms = 0
        self._finishedProcessingMs = 0
        self._nInitialFramesSkipped = 0

        self._liveViewEnabled = False

        self._m3u8Lock = threading.RLock()
        self._m3u8FileBase = simplifyString(self._cameraLocation)
        self._m3u8StreamingProfiles = {}    # profileId:(name,lastRequestTime,inited)

        clipMergeThreshold = extras.get(kClipMergeThreshold, kClipMergeThresholdDefault)
        self._clipMgr = ClipManager(self._logger, clipMergeThreshold)
        self._clipMgr.open(clipMgrPath)
        self._clipMgrLock = threading.RLock()

        self._wsgiServer = None
        self._wsgiServerMessages = collections.deque()

        self._hasMmap = False

        self._liveViewFile = os.path.join(userDir, 'live',
                                          cameraLocation+'.live')
        try:
            os.makedirs(os.path.join(userDir, 'live'))
        except Exception:
            pass

        self._clearSharedMemory()

        self._logger.info("Camera capture initialized, pid: %d" % os.getpid())

        self._queuedDataMgr = QueuedDataManagerCloud(msgQueue, dataMgrPipe,
                                                dataMgrId, cameraLocation,
                                                self._archivePath,
                                                self._extras.get(kGenThumbnailResolution, kGenThumbnailResolutionDefault),
                                                self._logger,
                                                extras.get('sioInProcess', False))
        self._queuedDataMgr.setDebugFolder(extras.get('analyticsDumpFolder', None))

        self._debugLogManager = DebugLogManager(self._cameraLocation, self._userDir)
        debugConfig = extras.get('debugConfig', None)
        if debugConfig:
            self._debugLogManager.SetLogConfig(debugConfig)

        # We need to protect against WSGI requests on arbitrary threads talking
        # to a stream reader which is closed, so during the image fetch time we
        # won't be able to change its status.
        self._streamReaderOpened = False
        self._streamReaderLock = threading.RLock()
        self._streamReader = StreamReader(cameraLocation,
                                                       self._clipMgr, self._clipMgrLock, tmpPath,
                                                       archivePath, userDir,
                                                       self._logger.getCLogFn(),
                                                       True, self._moveFailed,
                                                       extras.get('initFrameSize', 0),
                                                       getDebugPrefAsInt("cameraStreamStats", 3600, userDir) )

        # Keep track of the number of objectFrames that were processed since
        # we last sent out msgIdStreamProcessedData.
        self._numObjFramesSinceLastNotify = 0

        # Keep track of ms of last notify too; we want to notify periodically
        # even if nothing is going on...
        self._lastNotifyMs = 0

        # Track the we last pinged the back end
        self._lastPingTime = 0

        # NOTE: this is wrong because we leave it up to the caller to pass in
        #       the file name for the camera, which must always be the same, or
        #       otherwise only the first activation call will get the desired
        #       file name written; we don't have a mechanism yet telling the
        #       client "this is the path you want", has to do with historical
        #       reasons, but sooner or later it has to be solved, seriously...
        self._reGetFile = re.compile(".*/+(.*)\.m3u8");  # TODO: can we share this?
        self._reGetProfile = re.compile("([^-]*)-([0-9]+)")
        self._reGetIndex = re.compile(".*-[0-9]([0-9]+)\.ts")

        self._maxFileIndex = 0
        self._videoSettingsChanged = True

        self._lastFrameTime = None
        self._lastFrameTimestamp = None

        self._cleanupTmpStorage()

        self._framesProcessed = 0
        self._framesInterpolated = 0



    ###########################################################
    def __del__(self):
        """Free resources used by CameraCapture"""
        self._logger.info("Beginning camera shutdown")
        self._cleanup()

        try:
            # Handle any pending messages
            while(self._pipe.poll()):
                msg = self._pipe.recv()
                self._processMessage(msg, True)
        except Exception:
            pass

    ###########################################################
    def _cleanupTmpStorage(self):
        """ Delete all files in our tmp directory, except those for which
            move operation is still pending
        """
        pendingMoves = self._extras.pop("pendingMoves", [])
        recordDir = os.path.join(self._tmpPath, self._cameraLocation)
        for subdir, dirs, files in os.walk(recordDir):
            for name in files:
                if name in pendingMoves:
                    continue
                filePath = os.path.join(subdir, name)
                self._logger.info("Removing tmp file " +
                            ensureUtf8(filePath))
                try:
                    os.remove(filePath)
                except:
                    self._logger.warning("Couldn't remove %s: %s" %
                            (ensureUtf8(filePath), traceback.format_exc()))

    ###########################################################
    def _openStream(self):
        """Attempt to open the stream"""
        self._logger.info("Beginning stream open")
        self._timingInfo.associateKeys({ 'videoPath' : self._cameraLocation, 'source' : 'CameraCapture' })
        retry = 0

        self._flushPipeline()
        self._lastFrameTime = None
        self._lastFrameTimestamp = None

        hasSufficientSpace = self._checkFreeSpace()

        while not hasSufficientSpace or \
              not self._streamReader.open(self._cameraUri, self._extras):
            self._logger.info("Open failed")

            reason = None if hasSufficientSpace else _kDiskSpaceMessage

            # If we can't open the stream notify the backend and sleep
            if retry > 0:
                self._queue.put([MessageIds.msgIdStreamOpenFailed,
                                 self._streamReader.locationName,
                                 reason])

            sleepTime = _kRetryTimeList[min(retry, len(_kRetryTimeList)-1)]

            # If the URI is empty, this camera capture process is kinda bogus.
            # That happens when we've got a UPNP camera that is currently can't
            # be found.  Always sleep at least _kBogusMinSleepTime seconds...
            if self._cameraUri == "":
                sleepTime = max(sleepTime, _kBogusMinSleepTime)

            self._logger.info("Sleeping for %i" % sleepTime)

            try:
                # Handle incoming messages, specifically quit messages
                sleepTill = time.time() + sleepTime
                oldURI = self._cameraUri
                while sleepTime >= 0 and \
                        self._cameraUri == oldURI:
                    if self._pipe.poll(sleepTime):
                        while(self._pipe.poll()):
                            msg = self._pipe.recv()
                            self._processMessage(msg)
                            if not self._running:
                                return
                    sleepTime = sleepTill - time.time()
            except Exception:
                self._logger.warning("Camera open exception", exc_info=True)
                self._running = False
                return

            retry += 1

            hasSufficientSpace = self._checkFreeSpace()

            if hasSufficientSpace and retry > _kMaxRetries:
                raise TooManyFailuresException("Terminating camera process after " + \
                                    str(retry) + " retries")

        self._logger.info("Stream open successful")

        self._streamReaderLock.acquire()
        self._streamReaderOpened = True
        self._streamReaderLock.release()

        # Notify the backend we connected successfully.
        self._queue.put([
            MessageIds.msgIdStreamOpenSucceeded,
            self._streamReader.locationName,
            self._streamReader.getProcSize(),
        ])

        # Prevent a cleanup from executing if we don't have a frame ready on
        # the first call to _processFrame
        self._ms = time.time()*1000

        self._nInitialFramesSkipped = 0

        # Open the pipeline.
        self._runner = VideoPipeline(self._cameraLocation, self._queuedDataMgr)


    ###########################################################
    def run(self):
        try:
            self._run()
        except TooManyFailuresException:
            # exit, to be restarted by the backend
            e = sys.exc_info()[1]
            self._logger.error(e)
        except:
            t = traceback.format_exc()
            e = sys.exc_info()[1]
            self._logger.error(traceback.format_exc(t))
            self._logger.error(e)

    ###########################################################
    def _checkFreeSpace(self):
        kMinFreePercentage    = 0                           # do not limit storage dir based on percentage ... only on absolute value
        kMinFreeSpaceMB       = kMinFreeSysDriveSpaceMB     # require at least 1GB left on system drive
        self._lastFreeSpaceCheck = time.time()
        return checkFreeSpace(self._tmpPath,     kMinFreeSpaceMB, kMinFreePercentage, self._logger)

    ###########################################################
    def _run(self):
        """Run a camera capture process."""
        self.__callbackFunc = registerForForcedQuitEvents(self._cleanup)

        # Start with FFmpeg logging.
        ffmpegLog = FFmpegLog("videolib", "FFMPEG >> ")
        res = ffmpegLog.open(self._logger.log, 100)
        if res:
            self._logger.warn("FFmpeg logging not working (%d)" % res)
        ffmpegLogDrops = 0

        # Set running to True; this doesn't mean we've opened the stream yet,
        # just that we want to keep going...
        self._running = True

        # Open the stream; will set self._running to False if needed...
        self._openStream()

        # Only now we can actually think about running the WSGI server. This
        # will not block, the server runs completely in its own thread, which
        # we have to start.
        self._wsgiServer = self._createWsgiServer()
        self._wsgiServer.start()

        # Enter the main loop
        while(self._running):
            try:
                # Ping the back end if necessary
                now = time.time()
                if now > self._lastPingTime+_kPingSecInterval:
                    self._lastPingTime = now
                    self._queue.put([MessageIds.msgIdCameraCapturePing,
                                    self._streamReader.locationName])

                # Process the next frame
                if not self._processFrame():
                    time.sleep(.04)

                # Flush the FFmpeg logs
                ffmpegLogDrops += ffmpegLog.flush()

                # Process all pending messages
                while(self._running and self._pipe.poll()):
                    msg = self._pipe.recv()
                    self._processMessage(msg)

                # Do not attempt to do anything else if told to quit
                if not self._running:
                    break

                # Check our live stream lifetime
                self._checkLiveStream()

                # Make sure we're not filling up drive space
                if (now - self._lastFreeSpaceCheck) > _kFreeSpaceCheckInterval:
                    if not self._checkFreeSpace():
                        self._queue.put([MessageIds.msgIdStreamOpenFailed,
                                         self._streamReader.locationName,
                                         _kDiskSpaceMessage])
                        raise OutOfSpaceException("Terminating camera due to low disk space")

                # Send all WSGI messages up to the backend
                try:
                    while self._running:
                        msg = self._wsgiServerMessages.popleft()
                        self._queue.put(msg)
                except IndexError:
                    pass

            except Exception:
                # If we get an exception reading from the pipe the back end has
                # probably closed us.  If we get an exception in processFrame
                # we're probably out of memory.  Log the exception so we don't
                # miss anything else with this try block.
                self._logger.warning("Camera exception", exc_info=True)
                self._running = False

        # Finish FFmpeg logging
        ffmpegLogDrops += ffmpegLog.flush()
        ffmpegLog.close()
        if ffmpegLogDrops:
            self._logger.warn("%d FFmpeg logs dropped" % ffmpegLogDrops)

    ###########################################################
    def _updateVideoSettings(self):
        if not self._videoSettingsChanged:
            return
        maxRes = self._extras.get(kLiveMaxResolution, kLiveMaxResolutionDefault)
        maxBitrate = self._extras.get(kLiveMaxBitrate, kLiveMaxBitrateDefault)
        if self._streamReader.setLiveStreamLimits(maxRes, maxBitrate) < 0:
            self._logger.error("Error setting stream defaults")
        else:
            self._videoSettingsChanged = False

    ###########################################################
    def _processMessage(self, msg, ignoreCleanups=False):
        """Process an incoming message.

        @param  msg             The received message.
        @param  ignoreCleanups  If true we're already in a quit situation so
                                we want to avoid calls to cleanup.
        @return                 True to keep going, False to quit.
        """
        try:
            msgId = msg[0]

            if msgId == MessageIds.msgIdQuit or \
               msgId == MessageIds.msgIdQuitWithResponse:
                self._logger.info("Quit message received")
                if not ignoreCleanups:
                    self._cleanup()
                self._running = False
                if msgId == MessageIds.msgIdQuitWithResponse:
                    self._queue.put(msg[1])
            elif msgId == MessageIds.msgIdAnalyticsPortChanged:
                self._analyticsPort = msg[1]
                self._logger.info("Analytics port had changed to %d" % msg[1] )
                if self._queuedDataMgr is not None:
                    self._queuedDataMgr.setAnalyticsPort(self._analyticsPort)
            elif msgId == MessageIds.msgIdAddSavedTimes:
                self._logger.debug("Add saved times message received")
                self._clipMgrLock.acquire()
                try:
                    self._clipMgr.markTimesAsSaved(self._cameraLocation, msg[2])
                finally:
                    self._clipMgrLock.release()

            elif msgId == MessageIds.msgIdEnableLiveView:
                if not self._liveViewEnabled:
                    self._logger.info("Live view enabled")
                    self._liveViewEnabled = True

            elif msgId == MessageIds.msgIdDisableLiveView:
                if self._liveViewEnabled:
                    self._logger.info("Live view disabled")
                    self._liveViewEnabled = False
                self._closeSharedMemory()

            elif msgId == MessageIds.msgIdFlushVideo:
                self._logger.debug("Flushing video")
                self._streamReader.flush(*msg[2:])

            elif msgId == MessageIds.msgIdRenameCamera:
                self._streamReader.locationName = msg[2]
                if self._runner:
                    self._runner.updateVideoPath(msg[2])
                self._queue.put(msg)

            elif msgId == MessageIds.msgIdSetMmapParams:
                self._logger.debug("mmap params = %s %dx%d %d" % (str(msg[1]), msg[2], msg[3], msg[4]))
                self._streamReader.setMmapParams(msg[1], msg[2], msg[3], msg[4])

            elif msgId == MessageIds.msgIdSetTimePrefs:
                # TODO: may want to alter live stream? for now alter extras for future new live streams
                self._extras['use12HrTime'] = msg[1]
                self._extras['useUSDate'] = msg[2]

            elif msgId == MessageIds.msgIdSetClipMergeThreshold:
                self._logger.debug("Modifying clip merge threshold to %d " % msg[2])
                self._clipMgr.setClipMergeThreshold(msg[1], msg[2], False)

            elif msgId == MessageIds.msgIdSetVideoSetting:
                needsUpdate = msg[1] in [ kLiveMaxBitrate, kLiveEnableTimestamp, kLiveMaxResolution, kLiveEnableFastStart ]
                if needsUpdate:
                    if self._extras.get(msg[1],None) != msg[2]:
                        self._extras[msg[1]] = msg[2]
                        self._videoSettingsChanged = True
                elif msg[1] == kGenThumbnailResolution:
                    if self._queuedDataMgr is not None:
                        self._queuedDataMgr.setThumbnailResolution(msg[2])
                    if self._extras is not None:
                        self._extras[kGenThumbnailResolution] = msg[2]

            elif msgId == MessageIds.msgIdSetDebugConfig:
                self._debugLogManager.SetLogConfig(msg[1])
            elif msgId == MessageIds.msgIdSetAudioVolume:
                self._streamReader.setAudioVolume(msg[1])
            elif msgId == MessageIds.msgIdCameraUriUpdated:
                cameraUri = msg[1]
                if self._cameraUri != cameraUri:
                    _, sanitizedPath = processUrlAuth(cameraUri)
                    self._logger.info("Camera URI had been updated to " + ensureUtf8(sanitizedPath))
                    self._cameraUri = cameraUri
        except Exception:
            self._logger.error("Message exception: %s" % (msg), exc_info=True)


    ###########################################################
    def _processFrame(self):
        """Process the next frame.

        Note: frames may be processed but not passed to the pipeline.

        @return frameProcessed  True if a frame was processed.
        """
        self._timingInfo.inputItemMark( 'capture.ANoFrame' )
        self._timingInfo.inputItemMark( 'capture.BSkipped' )
        self._timingInfo.inputItemMark( 'capture.CToNumpy' )

        frame = self._streamReader.getNewFrame(self._liveViewEnabled)
        currentTimeMs = int(time.time()*1000)

        # Drop something in the log, if we've spent too much time without seeing a frame
        if self._lastFrameTime is not None:
            diff = currentTimeMs - self._lastFrameTime
            if diff < 0 or diff > _kFrameWarningTimeout:
                self._logger.warning("Large inter-frame delay: previousFrameTime=%d, currentTime=%d, diff=%d" %
                                    (self._lastFrameTime, currentTimeMs, diff))
        self._lastFrameTime = currentTimeMs

        if frame is None:
            if not self._streamReader.isRunning:
                self._logger.warning("Stream not running")
                self._cleanup(True, False)
                self._openStream()
            elif currentTimeMs > self._ms+_kTimeout:
                self._logger.warning("Stream timeout time=%d lastFrameTime=%s last=%d" %
                                    (currentTimeMs, str(self._lastFrameTime), self._ms))
                self._cleanup(True, False)
                #self._queue.put([MessageIds.msgIdStreamTimeout,
                #                 self._cameraLocation])
                self._openStream()
            self._timingInfo.inputItemIncrement( 'capture.ANoFrame' )
            return False

        self._timingInfo.inputIncrement( int( 1 ))

        self._ms = frame.ms

        if not self._hasMmap and self._liveViewEnabled:
            self._openSharedMemory(self._liveViewFile)

        # Process the frame
        if (isLocalCamera(self._cameraUri) and
            self._nInitialFramesSkipped < _kLocalCamFramesToSkip):
            self._nInitialFramesSkipped += 1
            self._timingInfo.inputItemIncrement( 'capture.BSkipped' )
        elif frame.dummy:
            # The frame was saved, but not given for analytics. We use it for interpolation
            self._framesInterpolated += 1
            self._queuedDataMgr.reportFrame(frame.ms)
        else:
            self._framesProcessed += 1
            self._queuedDataMgr.reportFrame(frame.ms, frame)

            self._timingInfo.inputItemIncrement( 'capture.CToNumpy' )

            if self._lastFrameTimestamp is not None:
                diff = self._ms - self._lastFrameTimestamp
                if diff <= 0 or diff >= _kFrameWarningTimeout:
                    self._logger.warning("Timestamp anomaly: previousFrame=%d, currentFrame=%d, diff=%d" %
                                            (self._lastFrameTimestamp, self._ms, diff))
            self._lastFrameTimestamp = self._ms

            self._runner.processClipFrame(frame, self._ms)
            self._numObjFramesSinceLastNotify = \
                self._queuedDataMgr.numObjectsAddedSinceLastCheck

            self._timingInfo.inputItemMark( 'capture.DProcessed' )


            # Inform the back end if more processing has completed.
            processedMs = self._queuedDataMgr.getFinishedTimestamp()
            if processedMs > self._finishedProcessingMs:
                # self._logger.debug("Finished processing %i" % int(processedMs))
                self._finishedProcessingMs = processedMs

                msSinceLastNotify = (processedMs - self._lastNotifyMs)

                if self._numObjFramesSinceLastNotify or \
                   (msSinceLastNotify > _kMaxNoNotifyMs):

                    self._queue.put([MessageIds.msgIdStreamProcessedData,
                                     self._cameraLocation, processedMs])
                    self._numObjFramesSinceLastNotify = 0
                    self._lastNotifyMs = processedMs
            self._timingInfo.inputItemIncrement( 'capture.DProcessed' )

        # Report memory stats every 15 minutes
        if (currentTimeMs - self._lastMemoryStats) > _kMemoryStatsInterval:
            memoryUnderLimit, memStats = checkMemoryLimit(os.getpid())

            if not memoryUnderLimit:
                self._logger.error("Quitting camera process due to excessive memory consumption:" + str(memStats))
                self._processMessage([MessageIds.msgIdQuit])
            else:
                self._logger.info(str(memStats))
                self._lastMemoryStats = currentTimeMs

        return True

    ###########################################################
    def _flushPipeline(self):
        # Close the pipeline runner first.  It is important to do this in
        # case we hang in StreamReader.close(), which would otherwise cause
        # us to lose processes frames.
        if self._runner:
            if self._lastFrameTimestamp is not None:
                self._logger.info("Flushing the pipeline")
                try:
                    self._runner.flush()
                except Exception:
                    self._logger.error("Cleanup exception", exc_info=True)
                    self._running = False
                try:
                    kFlushTimeout = 2.0 # wait for 2s if needed
                    self._queuedDataMgr.flush(kFlushTimeout)
                except:
                    self._logger.error(traceback.format_exc())
                self._logger.info("... finished flushing")
                self._queue.put([MessageIds.msgIdStreamProcessedData,
                                 self._cameraLocation, self._ms])
            # TODO: ADD CLEANUP CODE FOR PIPELINE
            self._runner = None
            self._queuedDataMgr.reset()
            self._logger.info("stream reader reset, %d/%d frames processed" % (self._framesProcessed, self._framesInterpolated))
            self._framesProcessed = 0
            self._framesInterpolated = 0


    ###########################################################
    def _cleanup(self, allowTerminate=False, isShutdown=True):
        """Ensure all data has been written.

        @param  allowTerminate  If True, allow the back end to terminate
                                this process anytime after the flush has
                                occurred.
        @param  isShutdown      Set to False if the web server should keep
                                running, which is only the case if the cleanup's
                                purpose is to reset for another round of
                                capture, due to a former failure of some sort.
        """


        self._streamReaderLock.acquire()
        self._streamReaderOpened = False
        self._streamReaderLock.release()

        if isShutdown:
            if self._cleaningUp:
                self._logger.warn("cleanup already in progress")
                return
            self._cleaningUp = True
            try:
                if self._wsgiServer:
                    self._logger.info("shutting down the WSGI server...")
                    if self._wsgiServer.shutdown(_kWsgiShutdownTimeout):
                        self._logger.info("WSGI server down")
                    else:
                        self._logger.warn("WSGI server is NOT down yet")
            except:
                self._logger.info("uncaught WSGI server shutdown error (%s)" %
                                  sys.exc_info()[1])
            finally:
                self._wsgiServer = None

        size = self._streamReader.getInitialFrameBufferSize()
        self._queue.put([MessageIds.msgIdStreamUpdateFrameSize,
                        self._streamReader.locationName,
                        size])

        self._closeSharedMemory()
        self._flushPipeline()

        self._queuedDataMgr.terminate()

        termFunc = None
        if allowTerminate:
            termFunc = self._allowBackendTermination

        self._streamReader.close(termFunc)
        self._logger.info("stream reader closed")
        self._removeM3U8All()


    ###########################################################
    def _clearSharedMemory(self):
        """Clear out the shared memory file if it's already there.

        This ensures that some old picture isn't sitting in there.
        """
        if os.path.exists(self._liveViewFile):
            try:
                # Try to open the live file; if it's not there, don't worry...
                f = open(self._liveViewFile, 'r+b')

                # Seek to the end of the file to find its size...
                f.seek(0, 2)
                fileSize = f.tell()

                # Clear out the file...
                f.seek(0)
                f.write('\x00'*fileSize)

                # Close it up...
                f.close()

            except Exception:
                pass


    ###########################################################
    def _openSharedMemory(self, filename):
        """Open shared memory.

        @param  size  The size in bytes of memory to open.
        """
        self._closeSharedMemory()

        self._hasMmap = self._streamReader.open_mmap(filename)

        if self._hasMmap:
            self._logger.info("Opened shared memory at %s" % filename)
        else:
            self._logger.error("Couldn't open shared memory at %s" % filename)

    ###########################################################
    def _closeSharedMemory(self):
        """Close any opened shared memory."""
        self._streamReader.close_mmap()
        self._hasMmap = False


    ###########################################################
    def _moveFailed(self, targetPath):
        """Inform the back end that a file could not be moved.

        @param  targetPath  Target relative path the file was to be moved to.
        """
        self._queue.put([MessageIds.msgIdFileMoveFailed, targetPath,
                         self._cameraLocation])


    ###########################################################
    def _allowBackendTermination(self):
        """Notify the backend that it is ok to kill this process."""
        # Tell the back end we're about to be ready for termination.
        self._queue.put([MessageIds.msgIdSetCamCanTerminate,
                         self._cameraLocation])

        # Handle messages until we receive confirmation that we won't be
        # sent any more times to save.
        try:
            while(self._pipe.poll(None)):
                msg = self._pipe.recv()
                if msg[0] == MessageIds.msgIdSetCamCanTerminate:
                    break
                self._processMessage(msg, True)
        except Exception:
            pass

        # If we got confirmation, or we broke somehow, go ahead and give
        # permission to terminate us.
        self._queue.put([MessageIds.msgIdSetTerminate,
                         self._cameraLocation])

        # Sleep, we're assuming we won't return from the close
        # most of the time on windows, so we ensure that we don't
        # to avoid any sporadic differences.
        while True:
            time.sleep(1000)

    ###########################################################
    def _removeM3U8(self, fileName):
        try:
            self._logger.info("Removing M3U8: " + fileName)
            os.remove(fileName)
            pattern = os.path.splitext(fileName)[0] + "*.ts"
            for f in glob.glob(pattern):
                os.remove(f)
        except Exception:
            pass

    ###########################################################
    def _removeM3U8All(self):
        filePath = os.path.join(self._userLocalDataDir, kRemoteFolder, self._m3u8FileBase)

        try:
            self._logger.info("Removing all M3U8: " + filePath)
            pattern = filePath + "*.ts"
            for f in glob.glob(pattern):
                os.remove(f)
            pattern = filePath + "*.m3u8local"
            for f in glob.glob(pattern):
                os.remove(f)
        except Exception:
            pass

    ###########################################################
    def _checkLiveStream(self):
        """Checks if client(s) haven't access an active live stream's M3U8
        file anymore since a certain amount of time. If so the live stream's
        stopped.
        """
        if self._streamReader is None:
            return
        turnOff = []
        turnOn  = []
        self._m3u8Lock.acquire()
        masterTuple = None
        for profileId in self._m3u8StreamingProfiles:
            fileName, lastAccessTime, started = self._m3u8StreamingProfiles[profileId]
            if not started:
                turnOn.append((profileId, fileName))
                self._m3u8StreamingProfiles[profileId] = (fileName, time.time(), True)
            elif time.time() > lastAccessTime + _kLiveStreamTimeoutSecs:
                if profileId == 0:
                    masterTuple = (profileId, fileName)
                    # master m3u8
                else:
                    turnOff.append((profileId,fileName))

        # Master M3U8 requires special handling. We will refresh it as long as at least
        # one another stream is active, and remove it when it's all alone and timed out.
        if masterTuple:
            if len(turnOff)+1 == len(self._m3u8StreamingProfiles):
                # master is the last one standing
                turnOff.append(masterTuple)
            else:
                # refresh master m3u8
                turnOn.append(masterTuple)
                self._m3u8StreamingProfiles[0] = (masterTuple[1], time.time(), True)

        for profileId, _ in turnOff:
            del self._m3u8StreamingProfiles[profileId]

        if len(self._m3u8StreamingProfiles) == 0 and len(turnOn) == 0:
            # No active profiles; reset the index
            self._maxFileIndex = 0
        self._m3u8Lock.release()

        for profileId, fileName in turnOff:
            self._logger.info("live stream timeout %d:%s" % (profileId, fileName))
            self._streamReader.disableLiveStream(profileId)
            self._removeM3U8(fileName)

        tsOption = getTimestampFlags(self._extras)

        for profileId, fileName in turnOn:
            if profileId == 0:
                self._updateVideoSettings()
            if self._streamReader.enableLiveStream(profileId, fileName, tsOption, self._maxFileIndex) < 0:
                self._logger.error("Error starting live stream %d:%s" % (profileId, fileName))


    ###########################################################
    def _wsgiAppImage(self, environ, startResponse):
        """ WSGI handler for sending the latest frame as a JPEG image. Supports
        passing of image dimensions, so the amount of data is optimally suited
        for the recipient's usage.

        @param  environ        The request information, CGI style.
        @param  startResponse  The WSGI response sender.
        """
        queryStr = environ.get('QUERY_STRING', '')
        query = cgi.parse_qs(queryStr)
        paramsWidth  = query.get(_kWsgiParamWidth , [_kWsgiParamWidthDefault])
        paramsHeight = query.get(_kWsgiParamHeight, [_kWsgiParamHeightDefault])
        width  = int(paramsWidth [0])
        height = int(paramsHeight[0])
        #self._logger.debug("width: %d, height: %d" % (width, height))
        if query.get("dummy", None) is not None:
            # undocumented query parameter: for testing purpose we can request a
            # dummy picture, which is rendered on the fly and right now consists
            # of random green lines on a black background. Nice to look at.
            outp = cStringIO.StringIO()
            img = PIL.Image.new("RGB", (width, height), "black")
            draw = PIL.ImageDraw.ImageDraw(img)
            for b in range(0, 255):
                draw.line((
                    random.randint(0,width-1),random.randint(0,height-1),
                    random.randint(0,width-1),random.randint(0,height-1)),
                    fill="rgb(0,%d,0)" % b)
            img.save(outp, "JPEG")
            jpeg = outp.getvalue()
            outp.close()
        else:
            # request of the latest frame and it getting encoded into a JPEG is
            # done in one single step (which might fail of course)
            self._streamReaderLock.acquire()
            try:
                # TODO: it might be beneficial to keep the very latest JPEG
                #       generated cached, in case multiple clients capable of
                #       fast polling are active; this however requires in the
                #       the stream reader to identify an image, meaning it would
                #       have to return an ID and also take one on the next call
                #       to check if something newer is available
                # NOTE: this direct access of the stream reader works only
                #       because the call has been made explicitly thread-safe;
                #       acceptable because frame extraction and JPEG compression
                #       is time-consuming and done in an optimized fashion in
                #       the videolib, but we do depend that the stream reader
                #       will always be valid though ...
                if not self._streamReaderOpened:
                    raise Exception("stream reader not opened")
                jpeg = self._streamReader.getNewestFrameAsJpeg(width, height)
                if jpeg is None:
                    raise Exception("frame retrieval failed")
                #self._logger.debug("got %d bytes of JPEG data" % len(jpeg))
            except:
                err = str(sys.exc_info()[1])
                startResponse('404 NO IMAGE',
                       [('Content-Type' , 'text/plain'),
                        ('Content-Length', str(len(err)))])
                return err
            finally:
                self._streamReaderLock.release()
        startResponse('200 OK',
               [('Content-Type' , 'image/jpeg'),
                ('Content-Length', str(len(jpeg))),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Pragma', 'no-cache'),
                ('Expires', '0')])
        return jpeg


    ###########################################################
    def _wsgiAppStreaming(self, environ, startResponse):
        """ WSGI handler for streaming video initiation and continuation. The
        requested m3u8 file gets read from its actual location and its content
        (the .ts files) adjusted. Main purpose of all of this redirection is
        to keep the lifetime of the stream as short as possible. If nobody's
        asking that URL anymore we can stop the HLS streaming.

        @param  environ        The request information, CGI style.
        @param  startResponse  The WSGI response sender.
        """
        # Not having an extension here causes a problem for the hls code in the
        # event there is a period in the username. It appears to be naively
        # searching for a file extension (expecting .m3u8) to strip and add a
        # counter + .ts for the movie files, and will wind up losing much
        # of the file path.
        # @markus - confirm we can't leave the .m3u8 ending here due to
        # conflicts with the routing? Using .m3u8local as a substitute.
        profileId = -1
        fileName  = None

        fileBaseMatch = self._reGetFile.match(environ['PATH_INFO'])
        if fileBaseMatch is not None:
            fileName = fileBaseMatch.group(1)
            if fileName == self._m3u8FileBase:
                profileId = 0
            else:
                profileMatch = self._reGetProfile.match(fileName)
                if profileMatch is not None and profileMatch.group(1) == self._m3u8FileBase:
                    profileId = int(profileMatch.group(2))

        if profileId < 0 or fileName is None:
            self._logger.error("Failed to serve request for " + environ['PATH_INFO'] + "; expecting " + self._m3u8FileBase + " derivatives")
            startResponse('404 NOT FOUND',
               [('Content-Type', 'text/plain'),
                ('Content-Length', "0")])
            return ""

        filePath = os.path.join(self._userLocalDataDir, kRemoteFolder, fileName+".m3u8local")

        self._m3u8Lock.acquire()
        streamActiveFlag = False
        if profileId in self._m3u8StreamingProfiles:
            # This profile is already active (but may not have been started, as would be the case
            # if the second request comes right after activation). For this situation, we need to be
            # careful to not overwrite the status flag (only _checkLiveStream should set it to True)
            _, _, streamActiveFlag = self._m3u8StreamingProfiles[profileId]
        else:
            self._logger.info("enabling live stream (%s)..." % filePath)

        self._m3u8StreamingProfiles[profileId] = (filePath, time.time(), streamActiveFlag)
        self._m3u8Lock.release()

        waited = 0
        if not streamActiveFlag:
            # wait a bit for the file to show up, instead of just asking for a
            # very likely failure to happen below ...
            start = time.time()
            while not os.path.exists(filePath) and waited < _kStartStreamTimeout:
                time.sleep(.2)
                waited = int((time.time() - start)*1000)
        result = ""
        h = None
        try:
            h = open(filePath, "r")
            m3u8 = h.read()
        except IOError:
            self._logger.info("returning 404 for (%s) - waited %d ms ..." % (filePath, waited))
            startResponse('404 NOT FOUND',
               [('Content-Type', 'text/plain'),
                ('Content-Length', "0")])
            return ""
        finally:
            if h is not None:
                try: h.close()
                except: pass

        fileIndex = -1
        for ln in cStringIO.StringIO(m3u8):
            ln = ln.rstrip()
            if ln.endswith(".ts"):
                if fileIndex < 0:
                    try:
                        fileIndexMatch = self._reGetIndex.match(ln)
                        if fileIndexMatch is not None:
                            fileIndex = int(fileIndexMatch.group(1))
                    except:
                        pass
                ln = "/" + kRemoteFolder + "/" + ln
            elif ln.endswith(".m3u8"):
                ln = "./" + ln
            result += ln + '\n'

        if fileIndex > self._maxFileIndex:
            self._maxFileIndex = fileIndex

        startResponse('200 OK',
           [('Content-Type' , 'application/x-mpegurl'),
            ('Content-Length', str(len(result))),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ('Pragma', 'no-cache'),
            ('Expires', '0')])
        return result


    ###########################################################
    def _wsgiApp(self, environ, startResponse):
        """ WSGI application i.e. the gateway for all incoming we requests. It's
        complete, meaning all requests (suitable or not) get handled.

        @param  environ        The request information, CGI style.
        @param  startResponse  The WSGI response sender.
        """
        path = None
        try:
            path = environ.get('PATH_INFO', "")
            if self._cleaningUp:
                errorText = "camera process about to stop"
                startResponse('500 UNAVAILABLE',
                   [('Content-Type' , 'text/plain'),
                    ('Content-Length', str(len(errorText)))])
                yield errorText
            else:
                if path == "/image.jpg":
                    yield self._wsgiAppImage(environ, startResponse)
                elif path.endswith(".m3u8"):
                    yield self._wsgiAppStreaming(environ, startResponse)
                else:
                    errorText = "unknown request path '%s'" % path
                    startResponse('404 WRONG PATH',
                       [('Content-Type' , 'text/plain'),
                        ('Content-Length', str(len(errorText)))])
                    yield errorText
        except:
            self._logger.error("uncaught WSGI error for path '%s'" % path)
            self._logger.error(traceback.format_exc())
            errorText = str(sys.exc_info()[1])
            try:
                startResponse('500 UNCAUGHT ERROR',
                   [('Content-Type' , 'text/plain'),
                    ('Content-Length', str(len(errorText)))])
                yield errorText
            except:
                self._logger.error("sending status 500 failed (%s)" %
                                   sys.exc_info()[1])

    ###########################################################
    def _wsgiServerNotify(self, currentAddress):
        """ Notification callback, invoked by the WSGI server.

        @param  currentPort  The port the web server just has opened.
        """
        msg = [MessageIds.msgIdWsgiPortChanged,
               self._cameraLocation, currentAddress[1]]
        self._wsgiServerMessages.append(msg)


    ###########################################################
    def _createWsgiServer(self):
        """ Creates a WSGI server instance. The task of starting it (and
        shutting it down is left the caller. Notice that after launching it the
        server will a (hopefully) short period of time to become ready to
        handle HTTP requests.

        @return  The new server instance.
        """
        # the port gets picked randomly out of a certain range
        serverAddressInfos = makeServerAddressInfos( [0],
            _kWsgiServerPortOpenDelay,
            _kWsgiServerPortOpenLoopDelay,
            _kWsgiServerAddress)

        # NOTE: choosing the server name explicitly solves an odd issue we
        #       encounter at least under OSX 10.6 where the call to getfqdn() in
        #       the server bind method caused issues with network connectivity,
        #       reaching from not being able to talk to the camera to sending
        #       messages to the backend via the pipe stalling ...
        serverNameOverride = "localhost"

        return WsgiServer(serverAddressInfos,
                          self._wsgiApp,
                          self._wsgiServerNotify,
                          sharedLogger = self._logger,
                          serverName = serverNameOverride)
