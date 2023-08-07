#*****************************************************************************
#
# PlatformHTTPWrapper.py
#     Singleton process wrapping SIO and providing the ability to classify
#     the moving objects we track.
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

import os
import sys
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import SocketServer
import MessageIds
import traceback
import json
import time
import threading
from SIOWrapper.SIOWrapper import SIOWrapper


#from DebugLogManager import DebugLogManager

from vitaToolbox.loggingUtils.LoggingUtils import getLogger

################################################################################
# TODO: duplicated into ObjectDetectorClient.py, too small for its own module ... resolve the redundancy
def _getModelDir():
    if hasattr(sys, 'frozen'):
        path = os.path.dirname(sys.executable)
        if sys.platform == 'darwin':
            return os.path.join(path, "..", "Resources", "models" )
        return os.path.join(path, "models" )
    else:
        devLibFolder = os.getenv("SV_DEVEL_LIB_FOLDER_CONAN")
        if devLibFolder is not None and devLibFolder != "":
            res = os.path.join(devLibFolder, "..", "models")
            if os.path.isdir(res):
                return res
        # This likely won't work
        return os.path.join("..", "models")

################################################################################
def HandlerFactory(logger, sio):
    class PlatformHTTPWrapperHandler(BaseHTTPRequestHandler, object):
        #---------------------------------------------------------------------------
        def __init__(self, *args, **kwargs):
            self._logger = logger
            self._sio = sio
            self._sioInitialized = (self._sio.init() >= 0)
            super(PlatformHTTPWrapperHandler, self).__init__(*args, **kwargs)

        #---------------------------------------------------------------------------
        def _sendResponse(self, response, text, contentType):
            self.send_response(response)
            self.send_header('Content-type', contentType)
            self.end_headers()
            self.wfile.write(text)
            self.wfile.close()

        #---------------------------------------------------------------------------
        def _sendJSONResponse(self, json):
            self._sendResponse(200, json, 'application/json')

        #---------------------------------------------------------------------------
        def _sendErrorResponse(self, error):
            self._sendResponse(500, error+"\n", 'text/plain')

        #---------------------------------------------------------------------------
        def do_GET(self):
            self._sendErrorResponse("GET is not supported")

        #---------------------------------------------------------------------------
        def do_HEAD(self):
            self._sendErrorResponse("HEAD is not supported")

        #---------------------------------------------------------------------------
        def do_POST(self):
            self._logger.debug("Processing POST - %d!" % threading.current_thread().ident)
            if not self._sioInitialized:
                self._sendErrorResponse("SIO pipeline failed to initialize")
            kMaxPostLen = 25*1024*1024 # 25MB
            start = time.time()
            try:
                contentLength = int(self.headers.getheader('content-length'))
                w = int(self.headers.getheader('x-width'))
                h = int(self.headers.getheader('x-height'))
                if contentLength is None \
                    or contentLength > kMaxPostLen \
                    or contentLength <= 0:
                    self._sendErrorResponse("Invalid content length: " + str(contentLength))
                    return

                if w is None or w<=0 or h is None or h<=0:
                    self._sendErrorResponse("Invalid dims: x=" + str(w) + " y="+str(h))
                    return

                image = self.rfile.read(contentLength)
                idIn = self._sio.addInput(image, w, h)
                if idIn < 0:
                    self._sendErrorResponse("Failed to submit input for processing")
                    return
                self._logger.debug(str(idIn) + ": Processing image of size " + str(len(image)) + " dims=[" + str(w) + "," + str(h) + "]")

                idOut, detections = self._sio.getOutput(True)
                if idOut != idIn:
                    # TODO: keep this until we do multi-threaded HTTP request processing
                    self._sendErrorResponse("Something went terribly wrong")
                    return

                duration = int((time.time() - start)*1000)
                output = json.dumps(detections)
                self._logger.debug("Got output for " + str(idOut) + " (" + str(duration) + "ms) :" + output)
            except:
                self._logger.error("Error while processing POST request: " + traceback.format_exc())
                self._sendErrorResponse("Failed to parse POST parameters")

            self._sendJSONResponse(output)

    return PlatformHTTPWrapperHandler


################################################################################
class PlatformHTTPWrapper(object):
    _kLogName = "PlatformHTTPWrapper.log"

    #---------------------------------------------------------------------------
    def __init__(self, msgQ, serverAddress, localDataDir):
        """Initialize PlatformHTTPWrapper.

        @param  port             The port to run on
        @param  localDataDir     The directory in which to store application data.
        """
        # Call the superclass constructor.
        super(PlatformHTTPWrapper, self).__init__()

        # Save data dir and setup logging...  SHOULD BE FIRST!
        self._localDataDir = localDataDir
        self._logDir = os.path.join(self._localDataDir, "logs")
        self._logger = getLogger(PlatformHTTPWrapper._kLogName, self._logDir)
        self._logger.grabStdStreams()
        self._msgQ = msgQ

        enableGpu = True # until we decide to make configurable
        self._sio = SIOWrapper(self._logger, _getModelDir(), enableGpu)
        if self._sio.init() <= 0:
            raise Exception("Failed to init SIO!")

        HandlerClass = HandlerFactory(self._logger, self._sio)
        HTTPServer.allow_reuse_address = True
        self._httpServer = HTTPServer(serverAddress, HandlerClass)
        port = self._httpServer.server_address[1]
        if not self._msgQ is None:
            # The opposite should only happen in unit test context
            self._msgQ.put([MessageIds.msgIdAnalyticsPortChanged, port])

        #self._debugLogManager = DebugLogManager("PlatformHTTPWrapper", localDataDir)
        self._logger.info("PlatformHTTPWrapper running on port %i, pid: %d, tid %d" %
                          (port, os.getpid(), threading.current_thread().ident))

    #---------------------------------------------------------------------------
    def getPort(self):
        return self._httpServer.server_address[1]

    #---------------------------------------------------------------------------
    def run(self):
        self._httpServer.serve_forever()

    #---------------------------------------------------------------------------
    def getLogger(self):
        return self._logger


################################################################################
def runPlatformHTTPWrapper(msgQ, localDataDir, port):
    # should only be accessible via localhost
    serverAddress = ('127.0.0.1', port)
    httpd = PlatformHTTPWrapper(msgQ, serverAddress, localDataDir)
    httpd.run()

################################################################################
if __name__ == "__main__":
    from sys import argv
    runPlatformHTTPWrapper("/tmp", 7050)
