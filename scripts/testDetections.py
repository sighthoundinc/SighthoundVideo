# export PYTHONPATH=`pwd`:`pwd`/.install/x86_64-apple-darwin/3rdparty/lib/python2.7/site-packages
# export SV_DEVEL_LIB_FOLDER=`pwd`/.install/x86_64-apple-darwin/lib/

from collections import defaultdict
import operator
import logging
import sys
import glob
from datetime import datetime
import traceback
import time
import os

from vitaToolbox.loggingUtils.LoggingUtils import VitaLogger
from vitaToolbox.strUtils.EnsureUnicode import ensureUnicode
from vitaToolbox.path.PathUtils import safeMkdir
from vitaToolbox.math.Rect import Rect

from videoLib2.python.StreamReader import StreamReader
from backEnd.QueuedDataManagerCloud import QueuedDataManagerCloud
from backEnd.QueuedDataManagerCloud import QueuedDataManagerCloud
from backEnd.VideoPipeline import VideoPipeline

_kRecordDir = "/tmp/testRun/fauxRecordDir"
_kStorageDir = "/tmp/testRun/fauxStorageDir"
_kConfigDir = "/tmp/testRun/fauxConfig"
_kThumbsRes = 240

#===========================================================================
class ClibManagerStub(object):
    def addClip(self, filename, camLoc, firstMs, lastMs, prevFile,
                nextFile, cacheStatus, procWidth, procHeight):
        pass

#===========================================================================
class QueueStub(object):
    def put(self, msg):
        pass

#===========================================================================
class PipeStub(object):
    def poll(self, timeout):
        pass

#===========================================================================
class Runner(object):
    #===========================================================================
    def __init__(self, logger, file, output):
        self._cameraLocation = "faux"
        self._logger = logger
        self._file = file
        self._clipManager = ClibManagerStub()
        self._streamReader = StreamReader( self._cameraLocation, self._clipManager, None, _kRecordDir, _kStorageDir, _kConfigDir, self._logger.getCLogFn(), True, None, 0, 0)
        self._logger.info("Created stream reader")
        self._fauxPipe = PipeStub()
        self._fauxQueue = QueueStub()
        self._queuedDataMgr = QueuedDataManagerCloud(self._fauxQueue, self._fauxPipe, 0, self._cameraLocation, _kStorageDir, _kThumbsRes, self._logger, True)
        self._logger.info("Created QDM")
        self._pipeline = VideoPipeline(self._cameraLocation, self._queuedDataMgr)
        self._framesRead = 0
        self._timestampsRead = 0
        self._lastTs = 0
        self._firstTs = 0
        self._start = time.time()
        if output is not None:
            self._queuedDataMgr.setDebugFolder(output)
        self._logger.info("Created video pipeline")

    #===========================================================================
    def __del__(self):
        self._logger.info("Flusing the pipeline")
        self._pipeline.flush()
        self._logger.info("Destroying the reader")
        self._streamReader.close()
        self._streamReader = None
        self._logger.info("Flushing pipeline")
        self._pipeline.flush()
        self._logger.info("Destroying QDM")
        self._queuedDataMgr.terminate()
        self._queuedDataMgr = None
        self._logger.info("Runner is kaput ... processed %d frames / %d dummies / %d ms in %d s" %
                        (self._framesRead, self._timestampsRead, self._lastTs - self._firstTs, time.time() - self._start ) )

    #===========================================================================
    def open(self):
        extras = {}
        return self._streamReader.open(self._file, extras)

    #===========================================================================
    def getFrame(self):
        newFrame = self._streamReader.getNewFrame()
        if newFrame is None:
            self._logger.info("Flusing the pipeline")
            self._pipeline.flush()
        return newFrame

    #===========================================================================
    def processFrame(self, frame):
        if self._framesRead == 0:
            self._firstTs = frame.ms
        self._lastTs = frame.ms
        if frame.dummy:
            # The frame was saved, but not given for analytics. We use it for interpolation
            self._queuedDataMgr.reportFrame(frame.ms)
            self._timestampsRead += 1
        else:
            self._queuedDataMgr.reportFrame(frame.ms, frame)
            self._pipeline.processClipFrame(frame, frame.ms)
            self._framesRead += 1
        # give detector time to catch up
        # delay = self._queuedDataMgr.getDetectionDelay()
        # print ("Delay is " + str(delay))
        # time.sleep(0.03)

#===========================================================================
def _setupLogger(verbose, outputFolder):
    # create logger with 'spam_application'
    logger = VitaLogger('SIO')
    logger.setLevel(logging.DEBUG)

    safeMkdir(outputFolder)
    handlers = [ logging.StreamHandler(), logging.FileHandler(os.path.join(outputFolder, "log.txt")) ]
    for ch in handlers:
        ch.setLevel(logging.DEBUG if verbose else logging.INFO)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logger.addHandler(ch)
    logger.info("Logging started .. verbose="+str(verbose))
    return logger

#===========================================================================
def _getopts(argv):
    opts = {}  # Empty dictionary to store key-value pairs.
    while argv:  # While there are arguments left to parse...
        if argv[0][0] == '-':  # Found a "-name value" pair.
            opts[argv[0]] = argv[1] if len(argv) > 1 else "" # Add key and value to the dictionary.
        argv = argv[1:]  # Reduce the argument list by copying it starting from index 1.
    return opts

#===========================================================================
def _printUsage():
    print "Usage ./testDetections.py (-f file|-d folder) [-v]"

#===========================================================================
def main():
    args = _getopts(sys.argv)

    fileName = args.get("-f", "/tmp/test3.mp4")
    folderName = args.get("-d", None)
    verbose = True # args.get("-v", None) != None

    if folderName is not None:
        mask = os.path.join(folderName, "*.mp4")
        allFiles = glob.glob(mask)
    elif fileName is not None:
        allFiles = [ fileName ]
    else:
        _printUsage()
        return -1

    for file in allFiles:
        output = file + ".output"
        _logger = _setupLogger(verbose, output)
        try:
            runner = Runner(_logger, file, output)
            runner.open()
            while (True):
                frame = runner.getFrame()
                if frame is None:
                    _logger.info("Failed to get a frame!")
                    break
                # _logger.info("Got frame " + str(frame.ms) + "!")
                runner.processFrame(frame)

            runner = None
        except:
            _logger.error(traceback.format_exc())

#===========================================================================
if __name__ == "__main__":
    main()