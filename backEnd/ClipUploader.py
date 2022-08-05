#*****************************************************************************
#
# ClipUploader.py
#    Utility for uploading clips to Sighthound on request
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

import threading
import time
from datetime import datetime
import tempfile
import os
import sys
import traceback
import json

from Queue import Queue

from ClipManager import ClipManager
from DataManager import DataManager

from appCommon.hostedServices.FileUploader import FileUploader

from vitaToolbox.sysUtils.FileUtils import safeRemove
from vitaToolbox.networking.RequestsUtils import fixupCacertLocation, cacertLocation
from vitaToolbox.sysUtils.TimeUtils import formatTime

fixupCacertLocation()



kReopenDb               = 1
kUploadClip             = 2
kQuit                   = 3
kSetVideoStoragePath    = 4

#===========================================================================
class ClipUploader(object):

    #===========================================================================
    def __init__(self, logger, accountID, authToken, clipDbPath, objDbPath, videoDir, dataDir):
        super(ClipUploader, self).__init__()
        self._logger = logger
        self._queue = Queue()
        self._thread = ClipUploader.UploaderThread(self)
        self._thread.start()
        self._shuttingDown = False
        self._dataDir = dataDir
        self._accountID = accountID
        self._authToken = authToken

        # Stats
        self._itemsUploaded = 0
        self._uploadErrors = 0

        self._queue.put( (kReopenDb, (clipDbPath, objDbPath, videoDir)))

    #===========================================================================
    def updateVideoStoragePath(self, path):
        self._queue.put ( (kSetVideoStoragePath, path) )

    #===========================================================================
    def reopenDb(self, clipDbPath, objDbPath, videoDir):
        self._queue.put( (kReopenDb, (clipDbPath, objDbPath, videoDir)))

    #===========================================================================
    def shutdown(self):
        self._logger.info("ClipUploader is shutting down")
        self._shuttingDown = True
        self._queue.put((kQuit, None))
        self._thread.join()

    #===========================================================================
    def queueUpload(self, camera, note, startTime, duration):
        self._logger.info("Requested upload for %s %d-%d, cacert location=%s" % (camera, startTime, startTime+duration, cacertLocation()))
        self._queue.put( (kUploadClip, (camera,note,startTime,duration)) )



    #===========================================================================
    class UploaderThread(threading.Thread):
        ''' Internal class for processing upload queue
            thread, so to not delay incoming stream processing.
        '''
        ###########################################################
        def __init__(self, owner):
            threading.Thread.__init__(self)
            self._owner = owner
            self._logger = owner._logger
            self._clipManager = None
            self._dataManager = None

        ###########################################################
        def uploadItem(self, camera, note, start, duration):
            exportTo = None
            end = start + duration
            try:
                startTime, stopTime = self._dataManager.openMarkedVideo(
                    camera, start, end, start, [], (0, 0) )

                remoteFilePrefix = formatTime('%y%m%d-%H%M%S%f')
                exportTo = os.path.join(tempfile.gettempdir(), "export." + str(time.time()))
                exportToMP4 = exportTo + ".mp4"
                exportToJSON = exportTo + ".json"

                success = self._dataManager.saveCurrentClip(
                    exportToMP4, start, end, self._owner._dataDir, {} )

                if not success:
                    self._owner._uploadErrors += 1
                    self._logger.error("Failed to upload a clip!")
                    return

                uploader = FileUploader(self._logger, self._owner._authToken)
                if not uploader.uploadFile( self._owner._accountID, exportToMP4, remoteFilePrefix ):
                    self._owner._uploadErrors += 1
                    # Don't even attempt to upload JSON
                    return


                filesAndProcSize = self._clipManager.getFilesAndProcSizeBetween(camera, start, end)
                procSize = filesAndProcSize[1]
                bboxes = self._dataManager.getBoundingBoxesBetweenTimes(camera, start, end, procSize, "json" )

                jsonObj = {
                    "apiVersion": "1.0", # TODO: change this version, when changing JSON object
                    "appVersion": kVersionString,
                    "accountID" : str(self._owner._accountID),
                    "cameraName": camera,
                    "userNote"  : note,
                    "startTime" : start,
                    "objects"   : bboxes,
                }

                with open(exportToJSON, 'w') as jsonFile:
                    jsonFile.write(json.dumps(jsonObj))
                if uploader.uploadFile( self._owner._accountID, exportToJSON, remoteFilePrefix ):
                    self._owner._itemsUploaded += 1
                else:
                    self._owner._uploadErrors += 1

            finally:
                if exportTo is not None:
                    safeRemove(exportToMP4)
                    safeRemove(exportToJSON)

        ###########################################################
        def reopenDb(self, clipDbPath, objDbPath, videoDir):
            self._clipManager = ClipManager(self._logger)
            self._clipManager.open(clipDbPath)
            self._dataManager = DataManager(self._logger,
                                            self._clipManager,
                                            videoDir)
            self._dataManager.open(objDbPath)

        ###########################################################
        def processMsg(self, msg, item):
            if msg == kQuit:
                return False
            elif msg == kUploadClip:
                self._logger.info("Uploader thread is processing %s [%d-%d], %d clips uploaded so far, %d errors, %d in queue" % \
                        (item[0], item[2], item[2]+item[3], self._owner._itemsUploaded, self._owner._uploadErrors, self._owner._queue.qsize()))
                self.uploadItem(item[0], item[1], item[2], item[3])
            elif msg == kReopenDb:
                self._logger.info("Reopening the database")
                self.reopenDb( item[0], item[1], item[2])
            elif msg == kSetVideoStoragePath:
                self._logger.info("Updating video storage path")
                self._dataManager.updateVideoStoragePath(item)
            else:
                self._logger.info("Unknown message!")
            return True

        ###########################################################
        def run(self):
            self._logger.info("Uploader thread is starting...")
            running = True
            while running:
                msg, item = self._owner._queue.get(True, None)
                try:
                    running = self.processMsg(msg, item)
                    if running and self._owner._shuttingDown:
                        running = False
                        self._logger.info("Shutting down clip uploaded. Current queue size is %d" % self._owner._queue.qsize())
                except:
                    self._logger.error("Exception while processing message (%d-%s):\n%s" % (msg, sys.exc_info()[1], traceback.format_exc()))
            self._logger.info("Uploader thread is shutting down ...")