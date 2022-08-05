#!/usr/bin/env python

#*****************************************************************************
#
# PackerCaptureStream.py
#     Utility for generating pcap capture of traffic to the camera.
#     Used for troubleshooting
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
import signal
import os
import subprocess
import sys
import time
import cPickle
import shutil
import ctypes
from multiprocessing.managers import BaseManager
from Queue import Queue
from Queue import Empty as QueueEmpty
from threading import Thread

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger, kLogLevelDebug

# Local imports...
from appCommon.CommonStrings import kExeName
from appCommon.CommonStrings import kTestLiveFileName
from videoLib2.python import StreamReader
from videoLib2.python.StreamReader import kPacketCaptureErrCodes
from MessageIds import msgIdPacketCaptureStatus, msgIdPacketCaptureEnabled


LOGFUNC = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p)

_kIsWin = "win32" == sys.platform

# Constants...
_kCaptureWidth = 320
_kCaptureHeight = 240
_kCaptureExtras = {'recordSize':(_kCaptureWidth, _kCaptureHeight)}

# Time before giving up on the stream as 'lost', in milliseconds
_kTimeout = 5000

# Time we wait for process to terminate and clean itself up.
_kProcTimeout = 2

# Time we sleep to prevent thrashing the cpu in tight loops.
_kSleepTime = 0.1

# Time to wait till we try to process the next frame.
_kProcessNextFrameTime = .04

# The sudo application we use to run the service with administrative rights.
_kSudoExe = "SighthoundVideoLauncher"

# Authentication key generated by using:
# ''.join(x.encode('hex') for x in os.urandom(32))
_kAuthKey = '371de6d98bdb30f28a1d650c4a6dfc6dc368736865476d921f2509de988b9986'

# Command to send to child process when it's time to terminate.
_kCmdTerminate = "terminate"

# Pcap filename and log filenames.
kPcapFilename = 'packet_capture'
kRunPacketCaptureLogFilename = 'RunPacketCapture.log'
kDoRunPacketCaptureLogFilename = 'DoRunPacketCapture.log'

# Max file size for the logs.
_kLogSize = 1024*1024*5

# Result codes.
_kPcapSuccess = 0
_kStreamOpen = 1
_kStreamFailed = -1
_kGeneralFailure = -2

# Descriptions to the result codes.
_kPcapSuccessStr = "Packet capture completed successfully"
_kStreamOpenStr = "Stream open successful"
_kStreamFailedStr = "Stream open failed!!"
_kGeneralFailureStr = "An unknown error has occurred!!"

# Dict that translates result code to description.
kPcapStatusResultCodes = {
    _kPcapSuccess:_kPcapSuccessStr,
    _kStreamOpen:_kStreamOpenStr,
    _kStreamFailed:_kStreamFailedStr,
    _kGeneralFailure:_kGeneralFailureStr,
}

# Messages with pcap result codes and descriptions to be sent to the backend.
_kMsgPcapSuccess = [msgIdPacketCaptureStatus, _kPcapSuccess,
                    kPcapStatusResultCodes[_kPcapSuccess]]
_kMsgPcapStreamOpen = [msgIdPacketCaptureStatus, _kStreamOpen,
                       kPcapStatusResultCodes[_kStreamOpen]]
_kMsgPcapStreamFailed = [msgIdPacketCaptureStatus, _kStreamFailed,
                          kPcapStatusResultCodes[_kStreamFailed]]
_kMsgPcapGeneralFailure = [msgIdPacketCaptureStatus, _kGeneralFailure,
                           kPcapStatusResultCodes[_kGeneralFailure]]


###############################################################################
def getCLogFunc(filename):
    def logFile(logLevel, msg):
        with open(filename, "a") as fp:
            fp.write("%s - %s\n" % (logLevel, msg))
    return LOGFUNC(logFile)


###############################################################################
class SignalHandler(object):
    signalReceived = False
    def __init__(self):
        super(SignalHandler, self).__init__()
        signal.signal(signal.SIGINT, self.handleSignal)
        signal.signal(signal.SIGTERM, self.handleSignal)

    def handleSignal(self, signum, frame):
        self.signalReceived = True


###############################################################################
class QueueManager(BaseManager): pass


###############################################################################
class FakeQueue(object):
    def __init__(self):
        super(FakeQueue, self).__init__()
    def get(self, timeout):
        time.sleep(timeout)
        raise QueueEmpty
    def put(self, *args, **kwargs):
        pass
    def get_nowait(self):
        raise QueueEmpty


###############################################################################
def runPacketCapture(cameraUri, storageDir, pcapDir, configDir, queue, extras, delaySeconds):
    """

    @param  cameraUri       The uri used to access the camera.
    @param  storageDir      Directory where the mmap should be stored.
    @param  pcapDir         Directory where pcap files should be stored.
    @param  configDir       Directory to search for config files.
    @param  queue           MsgQueue to send messages to the backend.
    @param  extras          A dictionary of extra params for the camera.
    @param  delaySeconds    Time alloted for capturing packets.
    """
    signalHandler = SignalHandler()

    try:
        if os.path.exists(pcapDir):
            shutil.rmtree(pcapDir)
        os.makedirs(pcapDir)
    except:
        pass

    logger = getLogger(kRunPacketCaptureLogFilename, pcapDir, _kLogSize)
    logger.grabStdStreams()

    cmdQueue = Queue()
    msgQueue = Queue()

    server = None
    address = None
    try:
        QueueManager.register('getCmdQueue', callable=lambda:cmdQueue)
        QueueManager.register('getMsgQueue', callable=lambda:msgQueue)
        qManager = QueueManager(address=None, authkey=_kAuthKey)
        server = qManager.get_server()
        t = Thread(target=server.serve_forever)
        t.daemon = True
        t.start()
        address = server.address
    except:
        cmdQueue = FakeQueue()
        msgQueue = FakeQueue()
        logger.error("Command and message queues could not be setup!!", exc_info=True)

    try:
        sudoExePath=""
        if hasattr(sys, 'frozen'):
            exeDir = os.path.dirname(sys.executable)
            sudoExePath = os.path.join(exeDir, _kSudoExe)
            openParams = [os.path.join(exeDir, kExeName)]
        else:
            if not _kIsWin:
                exeDirBase = os.getenv("SV_DEVEL_LIB_FOLDER_LOCAL")
                if exeDirBase is None:
                    raise Exception("'SV_DEVEL_LIB_FOLDER' environment variable has to be defined when running in dev environment")
                sudoExePath = os.path.abspath(os.path.join(exeDirBase, '..', 'bin', _kSudoExe))
            openParams = [sys.executable, "FrontEndLaunchpad.py"]

        os.environ["SV_LOG_LEVEL"] = str(kLogLevelDebug)
        os.environ["SV_LOG_FILE_SIZE_MB"] = "50"
        os.environ["SV_LOG_FILE_COUNT"] = "10"

        params = []
        if not _kIsWin:
            params.append(sudoExePath)
            params.append("--wait")
        params += openParams
        params.append("--pcap")
        params.append(cameraUri)
        params.append(storageDir)
        params.append(pcapDir)
        params.append(configDir)
        params.append(cPickle.dumps(address))
        params.append(cPickle.dumps(extras))
        params.append(cPickle.dumps(delaySeconds))

        logger.info("Parameters: %s" % str(params))

        p = subprocess.Popen(
            params,
            stdin =subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for s in [p.stdin, p.stdout, p.stderr]:
            s.close()

        while True:
            msg = None
            try:
                msg = msgQueue.get_nowait()
            except QueueEmpty:
                pass
            except:
                logger.error("Uncaught exception", exc_info=True)
                break

            if msg is not None:
                queue.put(msg)
                logger.info("msg=%s" % msg)

            exitCode = p.poll()
            if exitCode is not None:
                logger.info("Child process returned with exit code %s.", exitCode)
                break

            if signalHandler.signalReceived:
                logger.info("Termination signal received!")
                break

            # Don't thrash the processor... sleep for a little while...
            time.sleep(_kSleepTime)

        # The two commands below may seem a bit like a tautology. The reason
        # why we send a termination message and then immediately send a
        # termination signal afterwards is OS specific:
        #
        # (OS X) - The process we created earlier gained root access from
        # the and then spawned its own child that runs the pcap code.
        # Sending the termination signal to the privilege raiser only kills
        # that process and _NOT_ its child, which is the one we really want
        # to kill. So first, we send a message to the pcap process via the
        # queues we created earlier. _THEN_ we kill the privilege raiser.
        # In the off-chance that the message queues were not constructed
        # correctly, the pcap process kills itself after "delaySeconds"
        # seconds pass. This process and the pcap process both intercept the
        # termination signal to run any cleanup code before actually killing
        # themselves.
        #
        # (MS Windows) The process we created earlier is the same process
        # as the pcap process. So technically, these two commands are a
        # tautology. However, it doesn't hurt to do this, since the
        # terminaion signal and termination message both lead to the same
        # cleanup code.
        try:
            cmdQueue.put(_kCmdTerminate)
        except:
            pass
        try:
            p.terminate()
        except:
            pass

        try:
            # We need to give the process time to receive the message to
            # terminate, since we own the "real" message queues, while our
            # pcap process only contains the "proxies" to the queues.
            time.sleep(_kProcTimeout)
        except:
            pass

        if server is not None:
            try:
                server.close()
            except:
                pass

    except:
        logger.error("Uncaught exception!", exc_info=True)

    finally:
        sys.exit(0)


###############################################################################
def doRunPacketCapture(cameraUri, storageDir, pcapDir, configDir, address, extras, delaySeconds):
    """Create and start a test capture stream.

    @param  cameraUri       The uri used to access the camera.
    @param  storageDir      Directory where the mmap should be stored.
    @param  pcapDir         Directory where pcap files should be stored.
    @param  configDir       Directory to search for config files.
    @param  address         A pickled IP address for communicating with parent
                            process.
    @param  extras          A pickled dictionary of extra params for the camera.
    @param  delaySeconds    A pickled number indicating the number of seconds
                            the packet capturing should run for.
    """

    signalHandler = SignalHandler()

    logger = getLogger(kDoRunPacketCaptureLogFilename, pcapDir, _kLogSize)
    logger.grabStdStreams()

    try:
        if address and isinstance(address, str):
            address = cPickle.loads(address)
        if extras and isinstance(extras, str):
            extras = cPickle.loads(extras)
        if delaySeconds and isinstance(delaySeconds, str):
            delaySeconds = cPickle.loads(delaySeconds)

        cmdQueue = FakeQueue()
        msgQueue = FakeQueue()
        try:
            QueueManager.register('getCmdQueue')
            QueueManager.register('getMsgQueue')
            qManager = QueueManager(address=address, authkey=_kAuthKey)
            qManager.connect()
            cmdQueue = qManager.getCmdQueue()
            msgQueue = qManager.getMsgQueue()
        except:
            # Catch everything here. If we get an exception and we can't make
            # the message queues, it's not the end of the world. Just log it,
            # and keep going.
            logger.error("Command and message queues could not be setup!!", exc_info=True)

        try:
            camera = PacketCaptureStream(
                logger, cameraUri, storageDir, pcapDir, configDir, cmdQueue,
                msgQueue, extras, delaySeconds
            )
            camera.run()
        except:
            # Catch everything here so we can continue to cleanup this process
            # for termination.  Log it, and move on...
            logger.error("Uncaught exception in camera stream!", exc_info=True)

        # Give time for any messages sent thru the msgQueue to make it to our
        # parent process.
        time.sleep(_kProcTimeout)

    except:
        logger.error("Uncaught exception!! ", exc_info=True)

    finally:
        sys.exit(0)


###############################################################################
class PacketCaptureStream(object):
    """A class for pulling frames from a video stream."""
    ###########################################################
    def __init__(self, logger, cameraUri, storageDir, pcapDir, configDir,
                 cmdQueue, msgQueue, extras, delaySeconds):
        """Initializer for camera stream.

        @param  logger          Logger instance.
        @param  cameraUri       The uri used to access the camera.
        @param  storageDir      Directory where the mmap should be stored.
        @param  pcapDir         Directory where pcap files should be stored.
        @param  configDir       Directory to search for config files.
        @param  cmdQueue        A queue where commands are received from our parent
                                process.
        @param  msgQueue        A queue where we can send messages to our parent
                                process.
        @param  extras          A pickled dictionary of extra params for the camera.
        @param  delaySeconds    A pickled number indicating the number of seconds
                                the packet capturing should run for.
        """
        # Call the superclass constructor.
        super(PacketCaptureStream, self).__init__()

        self._signalHandler = SignalHandler()
        self._logger = logger
        self._cameraUri = cameraUri
        self._pcapDir = pcapDir
        self._cmdQueue = cmdQueue
        self._msgQueue = msgQueue

        self._extras = extras
        for k,v in _kCaptureExtras.iteritems():
            self._extras[k] = v

        self._delaySeconds = delaySeconds

        self._mmap = None
        self._sharedFrameCounter = 0
        self._liveViewFile = os.path.join(storageDir, kTestLiveFileName)
        try:
            os.makedirs(storageDir)
        except Exception:
            pass

        self._ms = 0

        self._running = False

        self._logger.info("Camera capture initialized")
        self._logger.setLevel(kLogLevelDebug)
        self._logger.debug("Debug logging activated...")

        self._streamReader = StreamReader.StreamReader('', None, None, storageDir,
                '.', configDir, self._logger.getCLogFn(), False)
        # self._streamReader = StreamReader.StreamReader('', None, storageDir,
        #         '.', configDir, getCLogFunc(os.path.join(pcapDir, 'mypcap.log')), False)
        self._logger.info("Stream reader initialized")


    ###########################################################
    def _openStream(self):
        """Attempt to open the stream"""
        self._logger.info("Beginning stream open")

        if not self._streamReader.open(self._cameraUri, self._extras):
            self._msgQueue.put(_kMsgPcapStreamFailed)
            self._logger.info(_kStreamFailed)
            return False

        self._msgQueue.put(_kMsgPcapStreamOpen)
        self._logger.info(_kStreamOpenStr)

        # Prevent a cleanup from executing if we don't have a frame ready on
        # the first call to _processFrame
        self._ms = time.time()*1000

        return True


    ###########################################################
    def _processFrame(self):
        """Process the next frame.

        @return frameProcessed  True if a frame was processed.
        """
        frame = self._streamReader.getNewFrame()

        if frame is None:
            if not self._streamReader.isRunning:
                self._logger.info("Stream not running")
                self._openStream()
            elif time.time()*1000 > self._ms+_kTimeout:
                self._logger.info("Stream timeout")
                self._openStream()
            return False

        self._ms = time.time()*1000


    ###########################################################
    def _enablePacketCapture(self):
        """Enables packet capture

        @return  result             0 on success,
                                    -1 on insufficient priveledges,
                                    -2 if driver isn't installed or inactive,
                                    -3 if the capture is already enabled,
                                    None if the StreamReader object could not
                                        be created/init'ed.
        """
        captureLocation = os.path.abspath(
            os.path.join(self._pcapDir, kPcapFilename)
        )

        if self._streamReader:
            result = self._streamReader.enablePacketCapture(
                captureLocation, self._cameraUri, self._logger.getCLogFn()
            )
            # result = self._streamReader.enablePacketCapture(
            #     captureLocation, self._cameraUri, getCLogFunc(os.path.join(self._pcapDir, 'mypcap.log'))
            # )
            return result
        else:
            return None


    ###########################################################
    def run(self):
        """Run a test stream process."""

        self._logger.info("Trying to enable packet capture...")
        result = self._enablePacketCapture()

        if result is None:
            self._msgQueue.put(_kMsgPcapGeneralFailure)
            self._logger.error(_kGeneralFailureStr)
            return

        self._msgQueue.put([msgIdPacketCaptureEnabled, result])

        if result != 0:
            self._logger.error(
                "ErrCode=%s: %s" %
                (
                    result,
                    kPacketCaptureErrCodes.get(result, "Unknown error code!!")
                )
            )
            return

        self._logger.info(
            "Packet capture initialized. Starting camera process..."
        )

        # Initialize loop conditions...
        self._running = True
        endTime = time.time() + self._delaySeconds

        # Enter the main loop
        while endTime - time.time() > 0:

            if self._openStream():

                while self._running:
                    try:
                        # Process the next frame
                        self._processFrame()
                    except:
                        self._logger.error("Camera run exception", exc_info=True)
                        self._running = False

                    if self._signalHandler.signalReceived:
                        self._logger.info("Termination signal received...")
                        break

                    try:
                        if self._cmdQueue.get_nowait() == _kCmdTerminate:
                            self._logger.info("Received message to close...")
                            break
                    except QueueEmpty:
                        pass

                    time.sleep(_kProcessNextFrameTime)

            time.sleep(_kProcessNextFrameTime)

            self._msgQueue.put(_kMsgPcapSuccess)
            self._logger.info(_kPcapSuccessStr)

        try:
            if self._streamReader:
                self._logger.info("Closing stream...")
                self._streamReader.close()
        except:
            self._logger.error("Stream close fail!!", exc_info=True)


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
