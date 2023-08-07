#! /usr/local/bin/python

#*****************************************************************************
#
# ResponseRunner.py
#     Process responsible for generating responses to triggers (email, push notifications, etc)
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

# Python imports...
from Queue import Empty as QueueEmpty
import ftplib
import os, sys
import shutil
import time
import urllib
import threading
import traceback
import Queue

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.networking.SimpleEmail import sendSimpleEmail
from vitaToolbox.networking.HttpClient import HttpClient
from vitaToolbox.windows.winUtils import registerForForcedQuitEvents
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8, ensureUnicode
from vitaToolbox.sysUtils.TimeUtils import getTimeAsString, getDateAsString, formatTime

# Local imports...
from appCommon.CommonStrings import kAppName
from appCommon.CommonStrings import kFtpProtocol
from appCommon.CommonStrings import kLocalExportProtocol
from appCommon.CommonStrings import kGatewayHost
from appCommon.CommonStrings import kGatewayPath
from appCommon.CommonStrings import kVersionString
from appCommon.CommonStrings import kGatewayTimeoutSecs
from appCommon.CommonStrings import kDefaultNotificationSubject

from appCommon.hostedServices.ServicesClient import ServicesClient

from ClipManager import ClipManager
from DataManager import DataManager
from ResponseDbManager import ResponseDbManager
from appCommon.hostedServices.IftttClient import IftttClient
from DebugLogManager import DebugLogManager

import MessageIds

# Constants...
_kLogName = "Response.log"

# We'll name temporary clips like this, with %d as the milliseconds.  It's not
# super important for this to be unique (we only create one at a time), so I'm
# not too worried about managing to create two clips within the same clock tick.
# The only reason to include time in the filename is that if, somehow, someone
# makes one of the files busy (by mucking around in our temp directory), it
# won't impede our ability to make future clips.
_kClipTemplateMap = {
    kFtpProtocol:         "Clip-%d.mp4",
    kLocalExportProtocol: "Clip-%d.mp4",
}

# Set to True for a bit more debugging info...
_kDebug = False


# How long we'll keep trying to get video for the email...
_kGetImageRetrySleep = .5
_kGetImageTimeoutSeconds = 2
_kGetVideoTimeoutSeconds = 60


# How long we'll keep trying to send...
_kSendEmailRetrySleepSeconds = (60 * 2)
_kSendEmailNumTries          = 3


# The maximum size of images to send via email.
_kMaxEmailWidth = 640
_kMaxEmailHeight = 480


# The frequency at which we ping the back end to inform that we're still alive
_kPingSecInterval = 120

# How long we'll sleep waiting for a message; we won't retry anything faster
# than this unless another message comes in...
_kQueueSleepSeconds = 60


# Limit timeout to 30 seconds, 10 wasn't always enough on Windows.
_kFtpSocketTimeout = 30.0

# We'll delay processing things from the response DB by this long when we get
# a failed 'send clip'...
_kDelayForFailedSendClip = 60.0


# Default size of image to email / send.
_kDefaultResponseRes = (320, 240)

# Note that this is run through strftime first, then clipInfoDict (hence
# the %% for the clipInfoDict codes).  Also note the %L extension to strftime
# for milliseconds, which isn't standard.
# IMPORTANT: This name must be unique enough that clips won't clobber each
# other...
_kFtpNameTemplate = u"%%(ruleName)s %Y-%m-%d %H-%M-%S-%L"
_kStrftimeMsCode = "%L"


_kEmailBodySingle = (
    """The rule "%s" triggered a video event at %s on %s.\n\n"""
)
_kEmailBodyMultiple = (
    """The rule "%s" triggered %d video events at %s on %s.\n\n"""
)

_kEmailErrorFormatStr   = """Error sending email for the rule "%s": "%s". Exception: %s"""
_kEmailWarningFormatStr = (
    """Error sending email for the rule "%s": "%s". Will retry %d time(s). Exception: %s"""
)

_kEmailNotConfiguredErrorStr = (
    """Email response requested, but email is not configured."""
)

# This mapping is used in error messages, since we often share code (and error
# messages) between the different "send clips" pieces...
_kSendClipProtocolToName = {
    kFtpProtocol: "FTP",
    kLocalExportProtocol: "Local Export",
}
_kSendClipErrorFormatStr = 'Error uploading via %s for the rule "%s" (%s, %s).'

# Notification content, as shown to the user on reception on a device. There is
# more (structured) data sent along in a JSON container.
_kNotificationFormatStr = 'Alert for rule "%s"'

# Notification retry sleep times.
_kNotificationRetries = [2, 4, 20, 90]

# Number of seconds to wait between clip sender DB polls.
_kClipSenderPollInterval = 5

# Number of seconds to wait between purging stored push notifications.
_kPushNotificationsPurgeIntervalSecs = 3600

# Maximum number of push notifications to purge at once.
_kMaxPushNotificationsPurge = 10000

# Maximum age a stored push notification should have (in seconds, 10 days).
_kPushNotificationMaxAgeSecs = 10 * 24 * 3600

_kExecutorPollTime = 0.1
_kExecutorAlertTime = 60
_kExecutorNotifyTime = 2
_kExecutorRetryTime = 5 # Retry after 5 seconds
_kExecutorMaxAllocAttempts = 1 / _kExecutorPollTime # do not stall the main loop for more than 1 sec

###############################################################
def runResponseRunner(backEndQueue, responseQueue, clipMgrPath, dataMgrPath,
                      responseDbMgrPath, videoDir, tmpDir, logDir, configDir,
                      ftpSettings, localSettings, notificationSettings,
                      servicesToken):
    """Create and start a ResponseRunner process.

    @param  backEndQueue         A queue to add back end messages to.
    @param  responseQueue        A queue to listen for control messages on.
    @param  clipMgrPath          Path to the clip database.
    @param  dataMgrPath          Path to the object database.
    @param  responseDbMgrPath    Path to the response database manager.
    @param  videoDir             Path to the folder where clips are stored.
    @param  tmpDir               Path to a place to store temporary files.
    @param  logDir               Directory where log files should be stored.
    @param  configDir            Directory to search for config files.
    @param  ftpSettings          Dictionary of FTP settings.
    @param  localSettings        Dictionary of local export settings.
    @param  notificationSettings Dictionary for notification settings.
    @param  servicesToken        The current services token or None.
    """
    responseRunner = ResponseRunner(backEndQueue, responseQueue, clipMgrPath,
            dataMgrPath, responseDbMgrPath, videoDir, tmpDir, logDir, configDir,
            ftpSettings, localSettings, notificationSettings, servicesToken)
    responseRunner.run()


##############################################################################
def _jsonEncodeDict(d):
    """ Quick and dirty JSON encoding for simple dictionaries containing
    numbers and strings (Unicode supported). UTF-8 strings won't be touched,
    so the receiver needs to be aware of proper encoding of the whole
    JSON document. This was written due to the lack of a JSON library in
    Python 2.5 and should be replaced as soon as possible. Too primitive to
    move into the toolbox btw, do NOT be tempted.

    @param d The dictionary to encode.
    @return The JSON expression.
    """
    result = ""
    for k, v in d.iteritems():
        item = '"%s":' % k
        if isinstance(v, (int, long, float, complex)):
            item += str(v)
        elif isinstance(v, unicode):
            v = v.replace('"', '\\"')
            enc = ""
            for c in v:
                o = ord(c)
                enc += ("\u%04X" % o) if o > 127 else c
            item += '"%s"' % enc
        else:
            v = str(v).replace('"', '\\"')
            item += '"%s"' % v
        if "" == result:
            result = "{%s" % item
        else:
            result += ",%s" % item
    result += "}"
    return result


###########################################################
def _waitUntilVideoAvailable(clipMgr, event, needFlush, camLoc, ms, queue, logger, maxDelay, pollDelay):
    """ Wait until we know timestamp is accessible in clip db

    @param clipMgr   ClipManager object
    @param camLoc    Name of the camera.
    @param event     Shutdown event object
    @param ms        Time (in ms) we need to be in the db
    """
    alreadyFlushedMs = clipMgr.getMostRecentTimeAt(camLoc)
    videoAvailable = alreadyFlushedMs >= ms
    if not videoAvailable:
        if needFlush:
            # TODO: we might need one lock per camera to avoid multiple flush
            #       requests triggered by different threads ...
            logger.info("requesting flush for camera '%s' ..." % camLoc)
            queue.put([MessageIds.msgIdFlushVideo, camLoc, ms])
        time1 = time.time()
        while (time.time() - time1) < maxDelay:
            alreadyFlushedMs = clipMgr.getMostRecentTimeAt(camLoc)
            videoAvailable = alreadyFlushedMs >= ms
            if videoAvailable:
                logger.debug("waited for %.2f s for clip to become available" % (time.time() - time1) )
                return True
            if event is None:
                time.sleep(pollDelay)
            else:
                event.wait(pollDelay)
                if (event.isSet()):
                    return False
    return videoAvailable



##############################################################################
class SynchronizedQueue:
    """ Wrapper around an IPC queue to make the essential calls thread-safe. """
    ###########################################################
    def __init__(self, instance):
        """TODO"""
        self._instance = instance
        self._lock = threading.RLock()

    ###########################################################
    def put(self, *args):
        """TODO"""
        self._lock.acquire()
        try:
            self._instance.put(*args)
        finally:
            self._lock.release()


##############################################################################
class SynchronizedResponseDbManager:
    """ Wrapper around the response DB manager to make it thread-safe. All of
    the sender threads share the same instance, hence this protection. We could
    give each sender its own instance, but since they all poll if might cause
    some issues with actual DB locking, hence we don't do it right now until we
    now better and have time to prove that it works and has benefits.

    NOTE: only the methods actually called by this module are protected!

    @see ResponseDbManager.ResponseDbManager
    """
    ###########################################################
    def __init__(self, instance):
        """Constructor for wrapping an instance.

        @param instance The instance to wrap"""
        self._instance = instance
        self._lock = threading.RLock()
    ###########################################################
    def areResponsesPending(self, *args):
        self._lock.acquire()
        try:
            return self._instance.areResponsesPending(*args)
        finally:
            self._lock.release()
    ###########################################################
    def getNextClipToSend(self, *args):
        self._lock.acquire()
        try:
            return self._instance.getNextClipToSend(*args)
        finally:
            self._lock.release()
    ###########################################################
    def clipDone(self, *args):
        self._lock.acquire()
        try:
            self._instance.clipDone(*args)
        finally:
            self._lock.release()
    ###########################################################
    def addPushNotification(self, *args):
        self._lock.acquire()
        try:
            return self._instance.addPushNotification(*args)
        finally:
            self._lock.release()
    ###########################################################
    def purgePushNotifications(self, *args):
        self._lock.acquire()
        try:
            return self._instance.purgePushNotifications(*args)
        finally:
            self._lock.release()
    ###########################################################
    def lockForever(self):
        """ Locks the instance, never releases it. Only used for shutdown. """
        self._lock.acquire()


##############################################################################
class ClipSender(threading.Thread):
    """ Base class to achieve asynchronous execution of response tasks. Runs
    as a single thread, getting the items to send via a queue.
    """
    ###########################################################
    def __init__(self, protocol, logger, backEndQueue, execContext,
                 configDir, tmpDir, cameraResolutions, responseDbMgr,
                 initialSettings):
        """ Creates a new sender thread. Must be started manually though.

        @param protocol             The name of the protocol used for sending.
        @param logger               The logger instance to use.
        @param backEndQueue         The queue to talk to the backend.
        @param execContext          The context for data manager/clip manager
        @param dataMgrPath          Path to the object database.
        @param videoDir             Path to the folder where clips are stored.
        @param configDir            Directory to search for config files.
        @param tmpDir               Directory for temporary stuff.
        @param cameraResolutions    Shared dictionary to determine camera
                                    resolutions. Only for simple gets.
        @param responseDbMgr        Response DB access.
        @param initialSettings      The initial settings specific to the type.
        """
        threading.Thread.__init__(self)
        self.protocol = protocol
        self._logger = logger
        self._backEndQueue = backEndQueue
        self._executionContext = execContext
        self._configDir = configDir
        self._tmpDir = tmpDir
        self._cameraResolutions = cameraResolutions
        self._responseDbMgr = responseDbMgr
        self._delayResponsesUntil = 0
        self._settings = initialSettings
        self.shutdown = threading.Event()

    ###########################################################
    def updateSettings(self, newSettings):
        """ Update settings. The settings will be access get-only, hence in a
        thread-safe fashion.

        @param newSettings The new settings to use.
        """
        self._settings = newSettings
        self._delayResponsesUntil = 0

    ###########################################################
    def _send(self, clipPath, ruleName, startTime, stopTime):
        """ To be implemented by the inherited classes. NOP for this class.

        @param clipPath File path of the clip.
        @param ruleName The name of the rule for which the item got created.
        @param startTime When the event started.
        @param stopTime When the event stopped.
        """
        pass


    ###########################################################
    def _processClip(self, uid, camLoc, ruleName, startTime, stopTime,
                     playStart, previewMs, objList, startList):
        """ Process a single clip to send.

        @param camLoc    Name of the camera.
        @param ruleName  Name of the rule.
        @param startTime Start time (in ms) of the clip to send.
        @param stopTime  Stop time (in ms) of the clip to send.
        @param playStart Time (in ms) that the clip should start playing.
        @param previewMs Time (in ms) that the thumbnail should show.
        @param objList   List of DB IDs in the clip.
        @param startList List of start times of triggers in the clip.
        @param uid       ID of the clip in the response database (for removal).
        """

        clipMgr = self._executionContext.getClipMgr()
        dataMgr = self._executionContext.getDataMgr()

        canProceed = _waitUntilVideoAvailable(clipMgr, self.shutdown, True,
                                                camLoc, stopTime,
                                                self._backEndQueue, self._logger,
                                                _kGetVideoTimeoutSeconds, _kGetImageRetrySleep)
        if not canProceed:
            if self.shutdown.isSet():
                return
            # Not an error.  Why?  ...this often happens when you turn off
            # your camera.  We want to add some padding to the last clip,
            # but probably won't be able to get all of our padding.
            # ...we'll just hit the timeout, then make the best clip we can
            #self._logger.warning("Not all video was available to send")
            #return True

        clipTemplate = _kClipTemplateMap[self.protocol]
        clipPath = os.path.join(self._tmpDir,
                                clipTemplate % int(time.time() * 1000))
        wantRetry = False
        wasSent = False
        try:
            res = self._cameraResolutions.get(camLoc, _kDefaultResponseRes)
            realStartTime, realStopTime = dataMgr.openMarkedVideo(camLoc,
                startTime, stopTime, playStart, objList, res, False, False)
            if (realStartTime == -1) or (realStopTime == -1):
                self._logger.error("Error opening video: (%s, %d, %d)" % (
                                   camLoc, startTime, stopTime))
                # Don't retry--just give up; error will not fix itself.
            else:
                success = dataMgr.saveCurrentClip(clipPath, realStartTime,
                        realStopTime, self._configDir)
                if success:
                    self._send(clipPath, ruleName, startTime, stopTime)
                    wasSent = True
                else:
                    self._logger.error("Error making clip: (%s, %s, %d, %d)" % (
                                       camLoc, clipPath, realStartTime,
                                       realStopTime))
                    # Don't retry--just give up; error will not fix itself.
        except:
            self._logger.error(_kSendClipErrorFormatStr % (
                           _kSendClipProtocolToName[self.protocol],
                           ruleName, sys.exc_info()[1], traceback.format_exc()), exc_info=True)
            wantRetry = True
        finally:
            try:
                if os.path.exists(clipPath):
                    os.unlink(clipPath)
            except Exception:
                self._logger.warning("Unable to delete '%s'" % clipPath)

        if wantRetry:
            self._delayResponsesUntil = time.time() + _kDelayForFailedSendClip
        else:
            self._responseDbMgr.clipDone(uid, wasSent)

    ###########################################################
    def run(self):
        """ Thread main loop. Polls on the response database asking for clips
        of the particular protocol. If it gets one it tries to send it.
        """
        self._logger.info("sender '%s' ready" % self.protocol)
        while not self.shutdown.isSet():
            # check if there are any responses, if not wait
            if not self._responseDbMgr.areResponsesPending(self.protocol):
                self.shutdown.wait(_kClipSenderPollInterval)
                continue
            # get the next response, wait in the unlikely case of nothingness
            clip = self._responseDbMgr.getNextClipToSend(self.protocol)
            if clip is None:
                self.shutdown.wait(_kClipSenderPollInterval)
                continue
            # delay if some former operation recommended some idle time
            delay = max(0, self._delayResponsesUntil - time.time())
            self.shutdown.wait(delay)
            if self.shutdown.isSet():
                break
            # now try to get the clip material and then send it out ...
            self._processClip(*clip)

        self._logger.info("sender '%s' exited" % self.protocol)


##############################################################################
class ResponseWorkerThread(threading.Thread):
    def __init__(self, owner, execContext, msgId):
        threading.Thread.__init__(self)
        self._queue = Queue.Queue()
        self._owner = owner
        self._msgId = msgId
        self._executionContext = execContext
        self._creationTime = time.time()

    def logState(self):
        action = self._executionContext._currentAction
        actionState = "undefined"
        if action:
            actionState = action.getProgressStr()

        self._owner._logger.info("Worker thread has been processing msgId=%d for %.2f, currently on %s" % (self._msgId, time.time()-self._creationTime, actionState) )

    def getType(self):
        return self._msgId

    def queueAction(self, tryNum, msg):
        self._queue.put((msg, tryNum))

    def run(self):
        msg, tryNum = self._queue.get(True, timeout=_kQueueSleepSeconds)
        self._owner._processMessage(self._executionContext, msg, tryNum, False)


##############################################################################
def _getFtpName(clipPath, ruleName, startTime, stopTime):
    """ Create a more readable output name to store FTP clips.

    @param  clipPath      Path to the source clip that was created that
                          we wish to send.  We will send this via FTP,
                          though we'll give it a different name based
                          on the _kFtpNameTemplate
    @param  ruleName      Name of the rule.
    @param  startTime     Start time (in ms) of the clip to send.
    @param  stopTime      Stop time (in ms) of the clip to send.
    @return startTimeStr  A string representing the start time.
    @return stopTimeStr   A string representing the stop time.
    @return dstName       A name for the destination file.
    """
    startTimeStr = getTimeAsString(startTime)
    stopTimeStr = getTimeAsString(stopTime)

    # Resolve the template name into a real name.
    startTimeSec, startTimeMsec = divmod(startTime, 1000)
    dstName = _kFtpNameTemplate
    dstName = dstName.replace(_kStrftimeMsCode, str(startTimeMsec))
    dstName = formatTime(dstName, time.localtime(startTimeSec))
    dstName = (dstName % {'ruleName': ruleName}) + \
              os.path.splitext(clipPath)[1]

    return startTimeStr, stopTimeStr, dstName


##############################################################################
class LocalClipSender(ClipSender):
    """ Sender which simply moves the clips into a different directory on the
    local file system. """
    ###########################################################
    def __init__(self, *args):
        """TODO"""
        ClipSender.__init__(self, kLocalExportProtocol, *args)

    ###########################################################
    def _send(self, clipPath, ruleName, startTime, stopTime):
        """TODO"""
        # Log that we're queuing this up for sending.
        startTimeStr, stopTimeStr, dstName = \
            _getFtpName(clipPath, ruleName, startTime, stopTime)

        logInfo = "Sending clip via local copy for rule \"%s\": %s - %s" % (
                ruleName, startTimeStr, stopTimeStr
            )

        targetDir = self._settings.get(ruleName.lower())
        if not targetDir:
            self._logger.error("%s: No directory configured for rule %s" %
                    (logInfo, str(self._settings)))
            return

        if not os.path.exists(targetDir):
            try:
                os.makedirs(targetDir)
            except OSError:
                # If we're here, it's most likely because os.path.exists returned
                # false even though the directory does exist. According to the
                # Python docs, this can happen if this calling process does not
                # have permission to check existence of the that dir. So, we
                # log the error, as well as permission information to make sure
                # this is the case, or if a deeper issue is taking place here.
                # We shouldn't have to worry about os.access raising an
                # exception, even if the targetDir doesn't exist, so it should
                # be safe to call inside the exception handler.
                self._logger.error(
                    "%s: Permissions on '%s': existence=%s, read=%s, write=%s" %
                    (
                        logInfo,
                        targetDir,
                        os.access(targetDir, os.F_OK),
                        os.access(targetDir, os.R_OK),
                        os.access(targetDir, os.W_OK),
                    ),
                    exc_info=True
                )

        targetPath = os.path.join(targetDir, dstName)
        # Try a move, followed by a copy if that fails.
        try:
            shutil.move(clipPath, targetPath)
        except Exception, e:
            self._logger.error("%s: move failed - %s" % (logInfo, str(e)))

        try:
            if not os.path.exists(targetPath):
                shutil.copy(clipPath, targetPath)
            self._logger.info( "%s: success" % logInfo )
        except:
            self._logger.error( "%s: failure" % logInfo, exc_info=True )


##############################################################################
class FtpClipSender(ClipSender):
    """ Sender which takes clips and uploads them to an FTP site. """
    ###########################################################
    def __init__(self, *args):
        """TODO"""
        ClipSender.__init__(self, kFtpProtocol, *args)

    ###########################################################
    def _send(self, clipPath, ruleName, startTime, stopTime):
        """TODO"""
        # Log that we're queuing this up for sending.
        startTimeStr, stopTimeStr, dstName = \
            _getFtpName(clipPath, ruleName, startTime, stopTime)
        self._logger.info(
            "Sending clip via FTP for rule \"%s\": %s - %s" % (
                ruleName, startTimeStr, stopTimeStr
            )
        )
        # Send via FTP.  Any exceptions that happen will be propagated up to
        # our caller, who will handle retrying. The only exceptions that we do
        # swallow here are any that come from the `quit()` method from the `FTP`
        # object, because there is a chance it might use a socket in an invalid
        # state.
        ftpConfig = self._settings
        ftpObj = ftplib.FTP(timeout=_kFtpSocketTimeout)
        try:
            # Prepare for file delivery...
            ftpObj.connect(ftpConfig['host'], int(ftpConfig['port']))
            ftpObj.login(ftpConfig['user'], ftpConfig['password'])
            ftpObj.cwd(ftpConfig['directory'])
            ftpObj.set_pasv(ftpConfig['isPassive'])

            # Send the file...
            clipFp = open(ensureUtf8(clipPath), 'rb')
            try:
                ftpObj.storbinary('STOR %s' % (dstName,), clipFp)
            finally:
                clipFp.close()

            # Tell the server we are finished...
            try:
                ftpObj.quit()
            except Exception:
                # The ftp object attempts to send a command to the server when
                # quitting; if the socket it tries to use is not connected or
                # doesn't exist, it will throw an exception. This exception
                # is safe to ignore. We will, however, need to call `close()`
                # on this object in a `finally` clause later to ensure proper
                # cleanup.
                pass
            self._logger.info(
                "...sent clip via FTP for rule \"%s\": %s - %s" % (
                    ruleName, startTimeStr, stopTimeStr
                )
            )
        finally:
            ftpObj.close()

##############################################################################
class ExecutionContext(object):
    """ Since DataManager and ClipManager aren't thread-safe, each threaded entity
        needs to have its own copy of these two.
        Whenever new thread that needs to use those is created, we will clone the
        existing context from the creating thread.
    """
    ###########################################################
    def __init__(self, logger, clipMgrPath, dataMgrPath, videoDir):
        self._clipMgr = ClipManager(logger)
        self._clipMgr.open(clipMgrPath)
        self._dataMgr = DataManager(logger, self._clipMgr,
                                    videoDir)
        self._dataMgr.open(dataMgrPath)

        self._clipMgrPath = clipMgrPath
        self._dataMgrPath = dataMgrPath
        self._logger = logger
        self._currentAction = None
        self._videoDir = videoDir

    ###########################################################
    def clone(self):
        return ExecutionContext(self._logger, self._clipMgrPath, self._dataMgrPath, self._videoDir)

    ###########################################################
    def getDataMgr(self):
        return self._dataMgr

    ###########################################################
    def getClipMgr(self):
        return self._clipMgr


##############################################################################
class ActionContext(object):
    """ Action context keeps track of an outstanding action, and its corresponding
        execution context. This allows us to pass control from ResponseRunner's
        _processMessage to a threaded executor and back to ResponseRunner's
        _processMessage (but in the context of a worker thread, this time)

        The class also keeps track of requsts statistics and result, allowing us
        to log some messages with telemetry.
    """
    ###########################################################
    def __init__(self):
        self._executionContext = None
        self._actionName = None
        self._cameraName = None
        self._ruleName = None
        self._eventTime = None
        self._eventDuration = None
        self._attemptNumber = None
        self._uri = None
        self._actionStartTime = None
        self._success = None
        self._descr = None
        self._progressStr = "initializing..."

    ###########################################################
    def init(self, actionName, cameraName, ruleName, eventTime, eventDuration, attemptNumber, uri):
        self._actionName = actionName
        self._cameraName = cameraName
        self._ruleName = ruleName
        self._eventTime = eventTime
        self._eventDuration = eventDuration
        self._attemptNumber = attemptNumber
        self._uri = uri
        self._actionStartTime = int(time.time()*1000)
        self._success = None
        self._descr = ""

    ###########################################################
    def setProgressStr(self, pstr):
        self._progressStr = pstr
        return True

    ###########################################################
    def getProgressStr(self):
        return self._progressStr

    ###########################################################
    def setStatus(self, success, descr=""):
        self._success = success
        self._descr = descr

    ###########################################################
    def format(self):
        duration = int(time.time()*1000) - self._actionStartTime
        status = "completed successfully" if self._success else "failed"
        evtDuration = " evtDuration=%d" % self._eventDuration if self._eventDuration else ""
        uri = " uri=%s" % self._uri if self._uri else ""
        msg = "%s (%d) for %s in %s has %s in %dms. triggerDelay=%s%s%s %s" % (self._actionName, self._attemptNumber, self._ruleName, self._cameraName, status, duration,
                                self._actionStartTime-self._eventTime, evtDuration, uri, self._descr)
        return msg


##############################################################################
class ResponseRunner(object):
    """A class for running slow responses."""
    ###########################################################
    def __init__(self, backEndQueue, responseQueue, clipMgrPath, dataMgrPath,
                 responseDbMgrPath, videoDir, tmpDir, logDir, configDir,
                 ftpSettings, localSettings, notificationSettings,
                 servicesToken):
        """Initialize ResponseRunner.

        @param  backEndQueue         A queue to add back end messages to.
        @param  responseQueue        A queue to listen for control messages on.
        @param  clipMgrPath          Path to the clip database.
        @param  dataMgrPath          Path to the object database.
        @param  responseDbMgrPath    Path to the response database manager.
        @param  videoDir             Path to the folder where clips are stored.
        @param  tmpDir               Path to a place to store temporary files.
        @param  logDir               Directory where log files should be stored.
        @param  configDir            Directory to search for config files.
        @param  ftpSettings          Dictionary of FTP settings.
        @param  localSettings        Dictionary of local export settings.
        @param  notificationSettings Dictionary for notification settings.
        @param  servicesToken        The current services token or None.
        """
        # Call the superclass constructor.
        super(ResponseRunner, self).__init__()

        # Setup logging...  SHOULD BE FIRST!
        self._logDir = logDir
        self._logger = getLogger(_kLogName, logDir)
        self._logger.grabStdStreams()

        assert type(clipMgrPath) == unicode
        assert type(dataMgrPath) == unicode
        assert type(responseDbMgrPath) == unicode
        assert type(videoDir) == unicode
        assert type(tmpDir) == unicode
        assert type(logDir) == unicode
        assert type(configDir) == unicode

        self._cameraResolutions = {}

        self._backEndQueue = SynchronizedQueue(backEndQueue)
        self._commandQueue = responseQueue
        self._notificationSettings = notificationSettings
        self._nextPushNotificationPurge = 0

        self._executionContext = ExecutionContext(self._logger, clipMgrPath, dataMgrPath, videoDir)

        self._responseDbMgr = ResponseDbManager(self._logger)
        self._responseDbMgr.open(responseDbMgrPath)
        self._responseDbMgr = SynchronizedResponseDbManager(self._responseDbMgr)

        self._servicesClient = ServicesClient(self._logger, servicesToken)

        # A list of tuples: (retryAfter, tryNum, msg)
        # ...this is messages that need to be "retried" at a later time.
        self._retryList = []
        self._retryListLock = threading.RLock()

        # A mapping of message IDs to processing code...
        self._dispatchTable = {
            MessageIds.msgIdQuit:                       ( 0,  self._processQuit ),
            MessageIds.msgIdSendEmail:                  ( 32, self._processSendEmail ),
            MessageIds.msgIdSendPush:                   ( 32, self._processSendPush ),
            MessageIds.msgIdSetCamResolution:           ( 0,  self._processSetCamResolution ),
            MessageIds.msgIdSendClip:                   ( 0,  self._processSendClip ),
            MessageIds.msgIdSetFtpSettings:             ( 0,  self._processSetFtpSettings),
            MessageIds.msgIdSetLocalExportSettings:     ( 0,  self._processSetLocalExportSettings),
            MessageIds.msgIdSetNotificationSettings:    ( 0,  self._processSetNotificationSettings),
            MessageIds.msgIdTriggerIfttt:               ( 32, self._processIfttt),
            MessageIds.msgIdSetServicesAuthToken:       ( 0,  self._setAuthToken),
            MessageIds.msgIdSendWebhook:                ( 32, self._processWebhook),
            MessageIds.msgIdSetDebugConfig:             ( 0,  self._setDebugConfig),
        }

        self._executorCounts = {}

        # Create the senders and launch them
        self._senders = {}

        for senderType in ((LocalClipSender, localSettings),
                           (FtpClipSender  , ftpSettings)):

            sender = senderType[0](self._logger, self._backEndQueue,
                self._executionContext.clone(), configDir, tmpDir,
                self._cameraResolutions, self._responseDbMgr,
                senderType[1])

            self._senders[sender.protocol] = sender
            sender.setDaemon(True)
            sender.setName("sender_%s" % sender.protocol)
            sender.start()

        # Track the we last pinged the back end
        self._lastPingTime = 0

        self._workerThreads = []

        self._debugLogManager = DebugLogManager("Response", configDir)

        self._logger.info("ResponseRunner initialized, pid: %d" % os.getpid())


    ###########################################################
    def __del__(self):
        """Free resources used by ResponseRunner"""
        self._logger.info("ResponseRunner exiting")


    ###########################################################
    def run(self):

        """Run a response manager process."""
        self.__callbackFunc = registerForForcedQuitEvents()

        # Enter the main loop
        self._running = True
        while(self._running):

            # Ping the back end if necessary
            now = time.time()
            if now > self._lastPingTime+_kPingSecInterval:
                self._lastPingTime = now
                self._backEndQueue.put([MessageIds.msgIdResponseRunnerPing])

            # Calculate timeout
            currentTime=time.time()
            latestWakeup=_kQueueSleepSeconds+currentTime
            for i in xrange(len(self._retryList)):
                retryAfter, _, _ = self._retryList[i]
                latestWakeup = min(latestWakeup, retryAfter)
            queueTimeout = latestWakeup-currentTime if latestWakeup>currentTime else 0

            # Process pending messages
            try:
                msg = self._commandQueue.get(timeout=queueTimeout)
            except QueueEmpty:
                pass
            else:
                if len(msg):
                    try:
                        self._processMessage(self._executionContext, msg, 1, True)
                    except Exception:
                        self._logger.error("Response exception:" + traceback.format_exc())

            # See if there's anything in our retry list that needs to be
            # tried again...

            # Walk through in forward order (most predictable to user)
            # retrying; but keep track of indices to delete (if we actually
            # retried them)...
            toDeleteFromRetryList = []
            for i in xrange(len(self._retryList)):
                (retryAfter, tryNum, msg) = self._retryList[i]

                if time.time() >= retryAfter:
                    toDeleteFromRetryList.append(i)
                    try:
                        self._processMessage(self._executionContext, msg, tryNum, True)
                    except Exception:
                        self._logger.error("Process message exception",
                                           exc_info=True)

            # Delete things in reversed order from the list.
            for i in reversed(toDeleteFromRetryList):
                del self._retryList[i]

            # Do some little push notification purging.
            self._purgePushNotifications()


        # Bring down the senders
        for _, sender in self._senders.iteritems():
            sender.shutdown.set()

        # Wait a little bit on each sender to exit, this is mostly useful to
        # just let idle threads exit and clean up properly.
        for _, sender in self._senders.iteritems():
            sender.join(1)
        # Prevent the response DB from getting corrupted, a still existing
        # sender thread will then block on this and (because of its daemon
        # nature) be killed at process exit.
        self._responseDbMgr.lockForever()

        # Wait for worker threads
        self._waitForExecutors()

        self._logger.info("all senders are down now")


    ###########################################################
    def _waitForExecutors(self):
        _kTimeoutWarning = 30
        counter = 0
        for thrd in self._workerThreads:
            while thrd.isAlive():
                counter += 1
                if counter % _kTimeoutWarning:
                    self._logger.warning("Executor thread still alive, waiting for %d executors for %d seconds!" % (len(self._workerThreads), counter))
                time.sleep(1)

    ###########################################################
    def _cleanUpExecutors(self, logState=False):
        for thrd in list(self._workerThreads):
            if not thrd.isAlive():
                msgId = thrd.getType()
                self._executorCounts[msgId] = self._executorCounts[msgId] - 1
                self._workerThreads.remove(thrd)
            else:
                if logState:
                    thrd.logState()

    ###########################################################
    def _allocateExecutor(self, msgId, tryNum, maxExecutors):
        """ Allocate worker thread.
            Initial implementation: just create a new one. Add pooling later.
        """
        attempt = 0

        while self._executorCounts.get(msgId, 0) > maxExecutors:
            self._cleanUpExecutors(attempt == _kExecutorMaxAllocAttempts)
            attempt += 1
            time.sleep(_kExecutorPollTime)
            if attempt > _kExecutorMaxAllocAttempts:
                self._logger.warning("Failed to allocate executor: messageId=%d, tryNum=%d, maxExecutors=%d" % (msgId, tryNum, maxExecutors))
                return None, _kExecutorRetryTime

        self._executorCounts[msgId] = self._executorCounts.get(msgId, 0) + 1
        res = ResponseWorkerThread(self, self._executionContext.clone(), msgId)
        self._workerThreads.append( res )
        res.start()
        return res, None


    ###########################################################
    def _processMessage(self, execContext, msg, tryNum, allowAsync):
        """Process an incoming message.

        @param  msg     The received message.
        @param  tryNum  The attempt # for processing this message; starts at 1.
        """
        msgId = msg[0]

        retryAfter = None

        # Dispatch out messages using dispatch table, passing all of the
        # parameters (except the message ID) as parameters.
        maxExecutors, fn = self._dispatchTable.get(msgId, (0, None))
        if fn is not None:
            if maxExecutors>0 and allowAsync:
                thread, retryAfter = self._allocateExecutor(msgId, tryNum, maxExecutors)
                if not thread is None:
                    thread.queueAction(tryNum, msg)
            else:
                actionCtx = ActionContext()
                actionCtx._executionContext = execContext
                execContext._currentAction = actionCtx
                try:
                    retryAfter = fn(actionCtx, tryNum, *msg[1:])
                finally:
                    execContext._currentAction = None
                self._onActionEnd(actionCtx)
        else:
            self._logger.warning("Unexpected message: %d" % msgId)

        if retryAfter:
            self._retryListLock.acquire()
            self._retryList.append((retryAfter, tryNum+1, msg))
            self._retryListLock.release()
            # if we've just appended an item to the retry list, processing queue timeout
            # may have changed, and we need to wake it up
            if not allowAsync:
                self._commandQueue.put([])

        # Collect completed worker threads
        if allowAsync:
            # This ensures thread GC isn't called from worker threads
            self._cleanUpExecutors()


    ###########################################################
    def _processQuit(self, actionCtx, tryNum):
        """Process MessageIds.msgIdQuit.

        @param  tryNum      The attempt number--ignored.
        @return retryAfter  Always returns None; we never retry quit.
        """
        _ = tryNum

        self._logger.info("Received quit message")
        self._running = False

        return None


    ###########################################################
    def _processSetFtpSettings(self, actionCtx, tryNum, ftpSettings):
        """Process MessageIds.msgIdSetFtpSettings.

        @param  tryNum      The attempt number--ignored.
        @param  ftpSettings The FTP settings dictionary.
        @return retryAfter  Always returns None; we never retry this.
        """
        _ = tryNum
        self._senders[kFtpProtocol].updateSettings(ftpSettings)
        return None


    ###########################################################
    def _processSetLocalExportSettings(self, actionCtx, tryNum, exportSettings):
        """Process MessageIds.msgIdSetLocalExportSettings.

        @param  tryNum          The attempt number--ignored.
        @param  exportSettings  The local export settings dictionary.
        @return retryAfter      Always returns None; we never retry this.
        """
        _ = tryNum
        self._senders[kLocalExportProtocol].updateSettings(exportSettings)
        return None


    ###########################################################
    def _processSetNotificationSettings(self, actionCtx, tryNum, notificationSettings):
        """Process MessageIds.msgIdSetNotificationSettings.

        @param  tryNum                The attempt number--ignored.
        @param  notificationSettings  The local export settings dictionary.
        @return retryAfter            Always returns None; we never retry this.
        """
        _ = tryNum
        self._notificationSettings = notificationSettings
        return None


    ###########################################################
    def _processSetCamResolution(self, actionCtx, tryNum, loc, width, height):
        """Process MessageIds.msgIdSetCamResolution.

        @param  tryNum      The attempt number--ignored.
        @param  loc         The camera location.
        @param  width       The width to set the resolution to.
        @param  height      The height to set the resolution to.
        @return retryAfter  Always returns None; we never retry this.
        """
        _ = tryNum

        self._logger.info("Received camera resolution of %dx%d for %s"
                          % (width, height, loc))
        self._cameraResolutions[loc] = (width, height)

        return None


    ###########################################################
    def _processSendClip(self, actionCtx, tryNum):
        """Process MessageIds.msgIdSendClip.

        This is a no-op and is just sent to wake up the ResponseRunner.  We
        actually get our information and handle retries using the response
        database.

        @param  tryNum      The attempt number--ignored.
        @return retryAfter  Always returns None.
        """
        _ = tryNum
        return None


    ###########################################################
    def _setAuthToken(self, actionCtx, tryNum, authToken):
        """Update the user's auth token.

        @param  authToken  The new auth token.
        """
        self._servicesClient.updateToken(authToken)

    ###########################################################
    def _setDebugConfig(self, actionCtx, tryNum, debugConfig):
        """Update the user's auth token.

        @param  debugConfig  The new debugConfig
        """
        self._debugLogManager.SetLogConfig(debugConfig)

    ###########################################################
    def _processIfttt(self, actionCtx, tryNum, camLoc, ruleName, triggerTime):
        """Send an ifttt response for the given rule.

        @param  tryNum      The try number; starts at 1.
        @param  camLoc      The camera location.
        @param  ruleName    The name of the rule containing this response.
        @return retryAfter  If non-None, we'll retry after time.time()
                            returns a value greater than this.
        """
        self._onActionBegin(actionCtx, "IFTTT trigger", camLoc, ruleName, triggerTime, None, tryNum, None)

        token = self._servicesClient.token()
        result = False
        if token is None:
            actionCtx.setStatus(False, "cannot trigger IFTTT, no auth token available")
        else:
            ic = IftttClient(self._logger, token)
            result = ic.trigger(camLoc, ruleName, triggerTime)
            actionCtx.setStatus(result)

        if result or tryNum >= len(_kNotificationRetries):
            return None

        return time.time() + _kNotificationRetries[tryNum - 1]

    ###########################################################
    def _processWebhook(self, actionCtx, tryNum, camLoc, ruleName, uri, ms, contentType, content, obj):
        self._onActionBegin(actionCtx, "webhook trigger", camLoc, ruleName, ms, None, tryNum, None)

        headers = { 'Content-Type': contentType,
                    'Accept': 'text/plain' }
        hc = HttpClient(kGatewayTimeoutSecs, self._logger)
        status, body, _ = hc.post(uri, content, headers)

        if status is not None:
            if 200 == status:
                actionCtx.setStatus(True)
            else:
                actionCtx.setStatus(False, "%d: %s (%s)" % (status, body, content))
        else:
            actionCtx.setStatus(False)

        # Never retry webhooks
        return None

    ###########################################################
    def _onActionBegin(self, actionCtx, actionName, camName, ruleName, ms, duration, attempt, uri):
        actionCtx.init(actionName, camName, ruleName, ms, duration, attempt, uri)

    ###########################################################
    def _onActionEnd(self, actionCtx):
        if actionCtx._actionName is None:
            # hasn't been initialized
            return

        method = self._logger.info if actionCtx._success else self._logger.error
        method( actionCtx.format() )

    ###########################################################
    def _processSendPush(self, actionCtx, tryNum, camLoc, ruleName, ms):
        """Send a push notification for the given rule.

        @param  tryNum      The try number; starts at 1.
        @param  camLoc      The camera location.
        @param  ruleName    The name of the rule containing this response.
        @param  ms          The ms to include in the push metadata.
        @return retryAfter  If non-None, we'll retry after time.time()
                            returns a value greater than this.
        """

        if not self._notificationSettings.get("enabled", False):
            self._logger.info("notifications disabled")
            return None

        self._onActionBegin(actionCtx, "push notification", camLoc, ruleName, ms, None, tryNum, None)

        # Initiate flush, if needed, but only on the first retry ... do not wait for the video to become avaialble
        clipMgr = actionCtx._executionContext.getClipMgr()
        canProceed = _waitUntilVideoAvailable(clipMgr, None, tryNum == 1,
                                                    camLoc, ms,
                                                    self._backEndQueue, self._logger,
                                                    _kGetImageTimeoutSeconds, _kGetImageRetrySleep)
        if not canProceed:
            # Video isn't available yet ... fail this operation, and schedule a retry
            actionCtx.setStatus(False, "image isn't available yet")
            return time.time() + _kNotificationRetries[tryNum - 1]



        guid = self._notificationSettings.get('gatewayGUID', None)
        password = self._notificationSettings.get('gatewayPassword', None)

        if not guid or not password:
            actionCtx.setStatus(False, "missing gateway credentials!?")
            return None

        # limit the content, see below for why ...
        def limit_text(text, maxLen, ending="..."):
            if len(text) <= maxLen:
                return text
            result = text[0:maxLen] + ending
            return result
        content = ensureUtf8(_kNotificationFormatStr % limit_text(ruleName, 64))

        data = { 'camLoc'  : camLoc,
                 'ruleName': ruleName,
                 'ms': ms }
        jsdata = _jsonEncodeDict(data)
        try:
            uid = self._responseDbMgr.addPushNotification(ensureUnicode(content), \
                                                        ensureUnicode(jsdata))
        except:
            actionCtx.setStatus(False, "error storing push notification: %s" %
                               sys.exc_info()[1])
            return None

        # send the pointer (UID) along, since the actual JSON data could exceed
        # the maximum notification limit (on iOS around 255 chars), what gets
        # send to the client (full set or just the UID) is decided at the
        # gateway...
        data['uid'] = uid
        jsdata = _jsonEncodeDict(data)

        params = { 'action':     'createMessage',
                   'iosBadges': '+1',
                   'content':    ensureUtf8(content),
                   'data':       ensureUtf8(jsdata),
                   'guid':       guid,
                   'password':   password,
                   'svversionstring': kVersionString }

        url = "https://%s%s" % (kGatewayHost, kGatewayPath)
        payload = urllib.urlencode(params)
        headers = { 'Content-Type': 'application/x-www-form-urlencoded;' +
                                    'charset=utf-8',
                    'Accept': 'text/plain' }
        hc = HttpClient(kGatewayTimeoutSecs, self._logger)
        status, body, _ = hc.post(url, payload, headers)

        if status is not None:
            if 200 == status:
                actionCtx.setStatus(True)
                return None
            actionCtx.setStatus(False, "sending failed, %d: %s" % (status, body))
            if 500 != status:
                # something fundamental is wrong, sadly no need to retry
                return None
        else:
            actionCtx.setStatus(False, "invalid API response")

        if tryNum >= len(_kNotificationRetries):
            self._logger.error("maximum number of retries, giving up this push")
            return None

        return time.time() + _kNotificationRetries[tryNum - 1]


    ###########################################################
    def _processSendEmail(self, actionCtx, tryNum, ruleName, camLoc, emailSettings,
                          configDict, numTriggers, objList, firstMs, lastMs,
                          messageId):
        """Send the email for the given object.

        This is imported / used by the response runner.

        @param  tryNum         The try number; starts at 1.
        @param  ruleName       The name of the rule containing this response.
        @param  camLoc         The camera location.
        @param  emailSettings  A dictionary of email settings; see BackEndPrefs.
        @param  configDict     A dictionary of config info relating to this
                               particular rule.
        @param  numTriggers    The number of times the rule was triggered.
        @param  objList        List of objects to highlight.
        @param  firstMs        The first ms that the object was seen.
        @param  lastMs         The last ms that the object was seen.
        @param  messageId      The messageID to use.
        @return retryAfter     If non-None, we'll retry after time.time()
                               returns a value greater than this.
        """
        previewMs = (lastMs + firstMs) / 2
        self._logger.debug("Want to send email: %s, %ld, %ld, %ld" %
                           (str(objList), firstMs, lastMs, previewMs ))

        # Get the 'toAddrs'.  First priority is the configDict.  If it's not
        # there, fall back to emailSettings (the site-wide setting, which was
        # used in the betas.
        toAddrs = configDict.get('toAddrs', emailSettings.get('toAddrs', ""))
        subject = configDict.get('subject', kDefaultNotificationSubject )

        self._onActionBegin(actionCtx, "send email", camLoc, ruleName, firstMs, lastMs-firstMs, tryNum, toAddrs)

        if not toAddrs.strip():
            actionCtx.setStatus(False, _kEmailNotConfiguredErrorStr)
            return None

        startTime = int(time.time()*1000)

        clipMgr = actionCtx._executionContext.getClipMgr()
        dataMgr = actionCtx._executionContext.getDataMgr()

        actionCtx.setProgressStr("waiting for thumb")
        canProceed = _waitUntilVideoAvailable(clipMgr, None, False,
                                                    camLoc, previewMs,
                                                    self._backEndQueue, self._logger,
                                                    _kGetImageTimeoutSeconds, _kGetImageRetrySleep)
        if not canProceed:
            # Video isn't available yet ... fail this operation, and schedule a retry
            actionCtx.setStatus(False, "image isn't available yet")
            return time.time() + _kNotificationRetries[tryNum - 1]

        hasVideoTime = int(time.time()*1000)

        actionCtx.setProgressStr("generating a thumb")
        imgRes = configDict.get('maxRes', 320)
        img = dataMgr.getSingleMarkedFrame(camLoc, previewMs, objList,
                                           (0, imgRes))
        if img is not None:
            self._logger.debug("Got an image")
            imgList = [("%s-%s-%s.jpg" % (camLoc,
                            getDateAsString(previewMs),
                            getTimeAsString(previewMs,"",False)), img)]
        else:
            self._logger.warning('Failed to get image to email: rule="%s" cam="%s" ts=%ld.' %
                                 (ruleName, camLoc, previewMs) )
            imgList = []


        frameAquiredTime = int(time.time()*1000)

        try:
            timeStruct = time.localtime(firstMs / 1000)
            timeStr = getTimeAsString(firstMs)
            dateStr = formatTime('%x', timeStruct)

            if numTriggers == 1:
                body = _kEmailBodySingle % (ruleName, timeStr, dateStr)
            else:
                body = _kEmailBodyMultiple % (ruleName, numTriggers,
                                              timeStr, dateStr)

            textInline = emailSettings.get('textInline', False)
            imageInline = emailSettings.get('imageInline', True)

            actionCtx.setProgressStr("preparing to send email")
            sendSimpleEmail(body,
                            emailSettings['fromAddr'],
                            toAddrs, ensureUtf8(subject),
                            emailSettings['host'], emailSettings['user'],
                            emailSettings['password'], emailSettings['port'],
                            emailSettings['encryption'], imgList, [],
                            lambda val, msg: actionCtx.setProgressStr(msg + "(" + str(val) + ")"),
                            _kDebug, messageId,
                            textInline,
                            imageInline )
            msg = "imgWait=%d imgRetrieval=%d imgSending=%d objs=%s" % ( hasVideoTime-startTime, frameAquiredTime-hasVideoTime, int(time.time()*1000)-frameAquiredTime, str(objList) )
            actionCtx.setStatus(True, msg)
        except Exception, e:
            if tryNum < _kSendEmailNumTries:
                triesLeft = (_kSendEmailNumTries - tryNum)
                actionCtx.setStatus(False, _kEmailWarningFormatStr % (ruleName, str(e), triesLeft, traceback.format_exc()))
                return time.time() + _kSendEmailRetrySleepSeconds
            else:
                actionCtx.setStatus(False, _kEmailErrorFormatStr % (ruleName, str(e), traceback.format_exc()))
        return None

    ###########################################################
    def _purgePushNotifications(self):
        """ Purges notifications"""
        now = time.time()
        if now > self._nextPushNotificationPurge:
            try:
                purgeCount = self._responseDbMgr.purgePushNotifications(
                    _kPushNotificationMaxAgeSecs,
                    _kMaxPushNotificationsPurge)

                self._logger.info("%d notifications purged" % purgeCount)
                # only get comfortable if we were able to remove all of the
                # notifications, otherwise we will be back as soon as possible
                if purgeCount < _kMaxPushNotificationsPurge:
                    self._nextPushNotificationPurge = now + \
                        _kPushNotificationsPurgeIntervalSecs
            except:
                self._logger.error("notification purge failed (%s)" %
                                   sys.exc_info()[1])

