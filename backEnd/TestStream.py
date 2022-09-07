#! /usr/local/bin/python

#*****************************************************************************
#
# TestStream.py
#     A class for pulling frames from a video stream. Used when provisioning a new camera or
#     editing an existing one to generate visual feedback.
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

"""
## @file
Contains the TestStream class.
"""

# Python imports...
from ctypes import c_char
import mmap
import os
import time

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import getLogger

# Local imports...
from appCommon.CommonStrings import kTestLiveFileName
from appCommon.CommonStrings import kTestLiveHeaderSize
import MessageIds
from videoLib2.python.StreamReader import StreamReader

def OB_KEYARG(a): return a


# Constants...
_kCaptureWidth = 320
_kCaptureHeight = 240
_kLiveImageMemorySize = _kCaptureWidth*_kCaptureHeight*3
_kCaptureExtras = {'recordSize':(_kCaptureWidth, _kCaptureHeight)}

# Time before giving up on the stream as 'lost', in milliseconds
_kTimeout = 5000


###############################################################
def runStream(cameraUri, storageDir, logDir, configDir, queue, extras):
    """Create and start a test capture stream.

    @param  cameraUri       The uri used to access the camera.
    @param  storageDir      Directory where the mmap should be stored.
    @param  logDir          Directory where log file should be stored.
    @param  configDir       Directory to search for config files.
    @param  queue           A queue used to send messages to the back end.
    @param  extras          A dictionary of extra params for the camera.
    """
    assert type(storageDir) == unicode
    assert type(logDir) == unicode

    camera = TestStream(cameraUri, storageDir, logDir, configDir, queue, extras)
    camera.run()


##############################################################################
class TestStream(object):
    """A class for pulling frames from a video stream."""
    ###########################################################
    def __init__(self, cameraUri, storageDir, logDir, configDir, queue, extras):
        """Initializer for TestStream.

        @param  cameraUri       The uri used to access the camera.
        @param  storageDir      Directory where the mmap should be stored.
        @param  logDir          Directory where log file should be stored
        @param  configDir       Directory to search for config files.
        @param  queue           A queue used to send messages to the back end.
        @param  extras          A dictionary of extra params for the camera.
        """
        # Call the superclass constructor.
        super(TestStream, self).__init__()

        self._logDir = logDir
        self._logger = getLogger('CameraTest.log', self._logDir)
        self._logger.grabStdStreams()

        self._cameraUri = cameraUri
        self._queue = queue

        self._ms = 0

        self._extras = extras
        for k,v in _kCaptureExtras.iteritems():
            self._extras[k] = v

        self._mmap = None
        self._sharedFrameCounter = 0
        self._liveViewFile = os.path.join(storageDir, kTestLiveFileName)
        try:
            os.makedirs(storageDir)
        except Exception:
            pass

        self._logger.info("Camera capture initialized")

        self._streamReader = StreamReader('', None, None, storageDir,
                '.', configDir, self._logger.getCLogFn(), False)


    ###########################################################
    def __del__(self):
        """Free resources used by TestStream."""
        self._closeSharedMemory()


    ###########################################################
    def _openStream(self):
        """Attempt to open the stream"""
        self._logger.info("Beginning stream open")
        self._closeSharedMemory()

        retries = 0

        while not self._streamReader.open(self._cameraUri, self._extras):

            if retries == 1:
                self._queue.put([MessageIds.msgIdTestCameraFailed])
            retries += 1

            self._logger.debug("Open failed")
            time.sleep(.5)

        self._logger.info("Stream open successful")

        # Prevent a cleanup from executing if we don't have a frame ready on
        # the first call to _processFrame
        self._ms = time.time()*1000

        return True


    ###########################################################
    def run(self):
        """Run a test stream process."""
        if not self._openStream():
            return

        # Enter the main loop
        self._running = True
        while(self._running):
            try:
                # Process the next frame
                if not self._processFrame():
                    time.sleep(.04)
            except Exception:
                # If we get an exception reading from the pipe the back end has
                # probably closed us.  If we get an exception in processFrame
                # we're probably out of memory.  Log the exception so we don't
                # miss anything else with this try block.
                self._logger.warning("Camera test exception", exc_info=True)
                self._running = False


    ###########################################################
    def _processFrame(self):
        """Process the next frame.

        @return frameProcessed  True if a frame was processed.
        """
        frame = self._streamReader.getNewFrame()
        while frame is not None and frame.dummy:
            frame = self._streamReader.getNewFrame()

        if frame is None:
            if not self._streamReader.isRunning:
                self._logger.warning("Stream not running")
                self._openStream()
            elif time.time()*1000 > self._ms+_kTimeout:
                self._logger.warning("Stream timeout")
                self._openStream()
            return False

        self._ms = time.time()*1000

        if self._mmap is None:
            # Ensure that we open a buffer large enough to contain the image
            # and at least as large as the size our readers are expecting.
            # This really isn't necessary since we scale down to 320x240, but
            # it's a good safety check to do in case something changes elsewhere
            # in the code.
            imageSize = max(_kLiveImageMemorySize, frame.height*frame.width*3)
            self._openSharedMemory(self._liveViewFile,
                                   kTestLiveHeaderSize + imageSize)

        if self._mmap is not None:
            self._mmap.seek(0)
            dataArr = (c_char*(frame.height*frame.width*3)).from_address(
                                                            frame.buffer.value)
            header = "%d%4d%4d\n" % (self._sharedFrameCounter, frame.width,
                                   frame.height)
            self._mmap.write(header + dataArr.raw)
            self._sharedFrameCounter = (self._sharedFrameCounter+1) % 10

        return True


    ###########################################################
    def _openSharedMemory(self, filename, size):
        """Open shared memory.

        @param  size  The size in bytes of memory to open.
        """
        self._closeSharedMemory()

        # This is for windows.  OSX is happy with 'r+' always, vista
        # varies on whether the file already exists.
        # NOTE: must try r+ first, since otherwise the file will be truncated
        # if it already exists.  This can wreck havoc on any client that's
        # got it mmapped.
        try:
            f = open(filename, 'r+b')
        except Exception:
            f = open(filename, 'w+b')

        f.seek(0)
        f.write('\x00'*size)
        # OSX requires a flush
        f.flush()
        try:
            self._mmap = mmap.mmap(f.fileno(), size)
        except Exception:
            self._logger.error("Couldn't open shared memory at %s" % filename)


    ###########################################################
    def _closeSharedMemory(self):
        """Close any opened shared memory."""
        if self._mmap is None:
            return

        # Write 'black' to the file to mark it as no longer valid.
        self._mmap.seek(0)
        self._mmap.write('\x00'*self._mmap.size())
        self._mmap.close()
        self._mmap = None

        try:
            os.remove(self._liveViewFile)
        except Exception:
            self._logger.warning("Couldn't remove shared memory file %s" %
                                 self._liveViewFile)
