#! /usr/local/bin/python

#*****************************************************************************
#
# DiskCleaner.py
#    Core disk maintenance utility.
#    Running as a separate process and performing cleanup of video/image files
#    according to the retention policy.
#    If this module fails to run, or runs too slow, the video storage device will run out of space.
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
import bisect
import datetime
import gc
import os
import fnmatch
from sqlite3 import DatabaseError
import time
import traceback
from bisect import bisect_left

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.path.GetDiskSpaceAvailable import getDiskSpaceAvailable, getDiskUsage
from vitaToolbox.path.PathUtils import normalizePath
from vitaToolbox.path.VolumeUtils import getStorageSizeStr
from vitaToolbox.loggingUtils.LoggingUtils import getLogger
from vitaToolbox.windows.winUtils import registerForForcedQuitEvents
from vitaToolbox.process.ProcessUtils import setProcessPriority, kPriorityLow, checkMemoryLimit
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8
from vitaToolbox.profiling.MarkTime import TimerLogger

# Local imports...
from appCommon.CommonStrings import kCorruptDbErrorStrings, kMinFreeSysDriveSpaceMB, kThumbsSubfolder
from ClipManager import kCacheStatusNonCache
from ClipManager import ClipManager
from DataManager import DataManager
from DebugLogManager import DebugLogManager
import MessageIds
from videoLib2.python.ClipReader import ClipReader, getMsList, getDuration
import videoLib2.python.ClipUtils as ClipUtils

# Constants...

# We'll delay 20 seconds at startup before we start processing.  That way, if
# back end decides to quit us right away, we'll be responsive.
_kInitialDelaySeconds = 20

_kMaxUnresponsiveTime = 10              # We'll go look for messages after this many seconds.

_kMbToBytes = 1024*1024
_kGbToBytes = 1024*_kMbToBytes

_kMinSpacePerCam = _kGbToBytes
_kTargetFreeSpacePerCam = _kGbToBytes/2
# we'll target _kMinFreeSpaceStayAheadRatio*kMinFreeSysDriveSpaceMB min free drive space
_kMinFreeSpaceStayAheadRatio = 2

_kMinCacheBlockPerCam = _kGbToBytes
_kFirstClipBlockPerCam = _kGbToBytes*2

_kMbToBytesF = 1024.0 * 1024.0

# Windows complains if the total free disk space dips below 200MB, so we'll try
# to keep that much space free.  We go ahead and do it on OSX too since it's
# probably a decent idea in general...
# We'll try and keep a gig free at all times
_kReservedDiskSpace = 1024 * _kMbToBytesF

_kLogName = "DiskCleaner.log"

_kDatabaseTimeoutSecs = 120

# We'll check for orphaned files to clean up a few times a day.
_kOrphanFileCleanupPeriod = 60*60*24

# A lowercase list of non-video files it's alright to remove
_kRemovableFiles = ['.ds_store', 'thumbs.db']

# If we see a file in the tmp dir longer than this we'll try to remove it.
_kTmpFileLifespan = 60*60*1

# Try to remove remote files that haven't been modified in longer than this.
_kRemoteFileLifespan = 60*5

# Maximum amount of time to keep files in the size cache.
#
# Theoretically this should be infinity, but being cautious about leaking
# memory ATM. Introducing cache to reduce *insanely* frequent re-querying
# of 500k files for user with 30 camera system (case 12238).
#
# Ideally this would be infinite (and we'd persist file size info in the db)
# but for now we just want to ensure we aren't constantly requerying file size
# info during a given cleanup as we were before - _doCleanup is re-entrant for
# a given cycle.
_kFileSizeCacheLifespan = 60*120
# Stagger renewal of file size cache items, to make sure we don't rescan all
# of the files at once (except the first time)
_kMaxFileCacheExpirationsAtOnce = 1000

_kMicrosecInMsec = 1000

# Note that it isn't the same functionality as merging the event-generated clips,
# based on user-specified max time distance.
# This is strictly to avoid fragmenting on-disk, physical clip files.
_kMergeClipThresholdMs = 4000

# How often to tidy object table. Doesn't need to happen often.
_kMinTidyObjectTablePeriod = 60*60*24

# Globals...

# Keep a reference to the current instance, for the forced quit callback to use.
_cleaner = None


###############################################################
def runDiskCleaner(backEndQueue, cleanerQueue, clipMgrPath, dataMgrPath, #PYCHECKER OK: Too many arguments
                   numCameras, maxStorage, videoDir, tmpDir, logDir, configDir,
                   remoteDir, infiniteMode, maxCache):
    """Create and start a DiskCleaner process.

    @param  backEndQueue  A queue to add back end messages to.
    @param  cleanerQueue  A queue to listen for control messages on.
    @param  clipMgrPath   A path to the clip manager database.
    @param  dataMgrPath   A path to the data manager database.
    @param  numCameras    The number of cameras being recorded.
    @param  maxStorage    The maximum GB to be used.
    @param  videoDir      The top level directory where videos are stored.
    @param  tmpDir        The top level directory where temporary video
                          files are stored.
    @param  logDir        Directory where log files should be stored
    @param  configDir     Directory to search for config files.
    @param  remoteDir     Directory where remote access files are stored.
    @param  infiniteMode  If True the disk cleaner will pretend it has
                          infinite disk space.
    @param  maxCache      The maximum number of hours of cache to keep.
    """
    global _cleaner
    _cleaner = DiskCleaner(backEndQueue, cleanerQueue, clipMgrPath, dataMgrPath,
                           numCameras, maxStorage, videoDir, tmpDir, logDir,
                           configDir, remoteDir, infiniteMode, maxCache)
    _cleaner.run()
    _cleaner = None


##############################################################################
class DiskCleaner(object):
    """A class for regulating disk space usage."""
    ###########################################################
    def __init__(self, backEndQueue, cleanerQueue, clipMgrPath, dataMgrPath, #PYCHECKER OK: Too many arguments
                 numCameras, maxStorage, videoDir, tmpDir, logDir, configDir,
                 remoteDir, infiniteMode, maxCache):
        """Initialize CameraCapture.

        @param  backEndQueue  A queue to add back end messages to.
        @param  cleanerQueue  A queue to listen for control messages on.
        @param  clipMgrPath   A path to the clip manager database.
        @param  dataMgrPath   A path to the data manager database.
        @param  numCameras    The number of cameras being recorded
        @param  maxStorage    The maximum GB to be used.
        @param  videoDir      The top level directory where videos are stored.
        @param  tmpDir        The top level directory where temporary video
                              files are stored.
        @param  logDir        Directory where log files should be stored
        @param  configDir     Directory to search for config files.
        @param  remoteDir     Directory where remote access files are stored.
        @param  infiniteMode  If True the disk cleaner will pretend it has
                              infinite disk space.
        @param  maxCache      The maximum number of hours of cache to keep.
        """
        # Call the superclass constructor.
        super(DiskCleaner, self).__init__()

        # Setup logging...  SHOULD BE FIRST!
        self._logDir = logDir
        self._logger = getLogger(_kLogName, logDir, 1024*1024*5)
        self._logger.grabStdStreams()

        self._backEndQueue = backEndQueue
        self._commandQueue = cleanerQueue
        # num cameras should never be 0 or all files will be deleted
        self._numCameras = max(1, numCameras)
        self._maxStorage = maxStorage*_kGbToBytes
        self._videoDir = videoDir
        self._tmpDir = tmpDir
        self._configDir = configDir
        self._remoteDir = remoteDir
        self._infiniteMode = infiniteMode
        self._maxCacheDuration = maxCache*60*60*1000

        self._pendingDeletes = []
        self._tmpFileDict = {}
        self._lastOrphanFileCleanup = 0
        self._thumbsSize = 0
        self._thumbsCount = 0
        self._thumbsPartial = False
        self._thumbStats = {}
        self._cleanupCycleStartTime = time.time()
        self._cleanupCycleLastInterruptCheckTime = time.time()
        self._lastTidyObjectTableTime = time.time()

        # A dictionary of file size information to avoid frequent expensive
        # getsize calls. Key = file name relative to root storage dir,
        # Value = (filesize, cachedtime)
        self._fileSizeCache = {}

        self._clipMgr = ClipManager(self._logger)
        self._clipMgr.open(clipMgrPath, _kDatabaseTimeoutSecs)

        self._dataMgr = DataManager(self._logger)
        self._dataMgr.open(dataMgrPath, _kDatabaseTimeoutSecs)

        self._logger.info("DiskCleaner initialized, pid: %d" % os.getpid())
        assert type(self._videoDir) == unicode
        assert type(self._tmpDir) == unicode
        assert type(self._logDir) == unicode

        self._debugLogManager = DebugLogManager("DiskCleaner", self._configDir)

        if self._infiniteMode:
            self._logger.warning("Disk cleaning disabled")


    ###########################################################
    def __del__(self):
        """Free resources used by DiskCleaner"""
        self._logger.info("DiskCleaner exiting")


    ###########################################################
    def _markDone(self):
        """Set the running flag to False."""
        self._running = False


    ###########################################################
    def run(self):
        """Run a disk cleaner process."""
        startTime = time.time()

        # In general disk cleanup should be a background event and never pull
        # CPU away from anything else. This can be a particular problem if the
        # the app is closed and not run for several days - on the next launch
        # there will be several days of cache ready to be clipped at once. Set
        # a lower priority to help avoid this.
        setProcessPriority(kPriorityLow)

        # Enter the main loop
        self._running = True
        while(self._running):
            # default timeout; will be changed in some circumstances
            timeout = 1

            # Run the cleanup
            try:
                self._logger.info("Starting cleanup loop")
                timeSinceStart = time.time() - startTime
                if timeSinceStart > _kInitialDelaySeconds:
                    memoryUnderLimit, memStats = checkMemoryLimit(os.getpid())

                    if not memoryUnderLimit:
                        self._logger.error("Quitting disk cleaner process due to excessive memory consumption:" + str(memStats))
                        self._processMessage([MessageIds.msgIdQuit])
                        continue

                    moreToDo = self._doCleanup()
                    if not moreToDo:
                        # Collect garbage if we're gonna sleep...
                        gc.collect()
                        timeout = 30
                else:
                    timeout = _kInitialDelaySeconds - timeSinceStart
            except DatabaseError, e:
                if e.message in kCorruptDbErrorStrings:
                    # If the database is corrupt, notify the back end and exit.
                    self._backEndQueue.put([MessageIds.msgIdDatabaseCorrupt])
                self._logger.error("Database error", exc_info=True)
                return
            except Exception:
                # If we get an uenexpected exception log it and exit.
                self._logger.error("Disk cleaner unexpected exception",
                                   exc_info=True)
                return

            # Process pending messages
            try:
                msg = self._commandQueue.get(timeout=timeout)
                self._processMessage(msg)

                # Get all pending messages before doing a new cleanup
                while True:
                    msg = self._commandQueue.get(timeout=1)
                    self._processMessage(msg)
            except Exception:
                pass


    ###########################################################
    def _processMessage(self, msg):
        """Process an incoming message.

        @param  msg  The received message.
        """
        msgId = msg[0]

        if msgId == MessageIds.msgIdQuit:
            self._logger.info("Received quit message")
            self._running = False
        elif msgId == MessageIds.msgIdSetMaxStorage:
            self._logger.info("Changing max storage to %i" % msg[1])
            self._maxStorage = msg[1]*_kGbToBytes
        elif msgId == MessageIds.msgIdSetNumCameras:
            self._numCameras = max(1, msg[1])
            self._logger.info("Changing num cams to %i" % self._numCameras)
        elif msgId == MessageIds.msgIdRemoveDataAtLocation:
            location = msg[1]
            # After this message finishes we'll immediately go into _doCleanup
            # which will delete files from _pendingDeletes
            indexPaths = self._clipMgr.getAllFilesFromLocation(location)
            fullPaths = [os.path.join(self._videoDir, path)
                         for path in indexPaths]
            self._pendingDeletes.extend(fullPaths)
            self._clipMgr.deleteLocation(location)
        elif msgId == MessageIds.msgIdDeleteFile:
            self._pendingDeletes.append(msg[1])
        elif msgId == MessageIds.msgIdSetCacheDuration:
            self._logger.info("Changing cache duration to %i" % msg[1])
            self._maxCacheDuration = msg[1]*60*60*1000
        elif msgId == MessageIds.msgIdSetDebugConfig:
            self._debugLogManager.SetLogConfig(msg[1])


    ###########################################################
    def _removeRemoteFiles(self):
        """Remove any remote files that are no longer necessary."""
        now = time.time()

        for base, dirs, files in os.walk(self._remoteDir):
            for f in files:
                path = os.path.join(base, f)
                age = now-os.path.getmtime(path)
                if age > _kRemoteFileLifespan:
                    self._pendingDeletes.append(path)

        finished = time.time()
        self._logger.info("Remote files cleanup took %d seconds" % int(finished-now))


    ###########################################################
    def _listSearch(self, alist, item):
        'Locate the leftmost value exactly equal to item'
        i = bisect_left(alist, item)
        if i != len(alist) and alist[i] == item:
            return i
        return -1

    ###########################################################
    def _removeOrphanFiles(self):
        """Remove any files on disk that shouldn't be there."""
        now = time.time()

        if now < self._lastOrphanFileCleanup+_kOrphanFileCleanupPeriod:
            return

        # Only run orphan scan between 2am and 5am
        currentHour = datetime.datetime.now().hour
        kMinOrphanScanHour = 2
        kMaxOrphanScanHour = 5
        if currentHour < kMinOrphanScanHour or currentHour > kMaxOrphanScanHour:
            return

        self._lastOrphanFileCleanup = now
        disablePath = os.path.join(self._configDir, "disableOrphanScan")
        if os.path.isfile(disablePath):
            self._logger.info("Skipping orphan file detection, %s is present" % disablePath)
            return

        filesScanned = 0
        markedForDeletion = 0
        allCameras = self._clipMgr.getCameraLocations()
        currentCameraName = ""
        camFiles = []
        fileEntryStart = len(self._videoDir)+1

        # Remove any movie files that aren't in the database.
        for path, _, files in os.walk(self._videoDir):
            if os.path.dirname(path) == self._videoDir:
                # We're in a camera subfolder
                currentCameraName = os.path.basename(path).lower()
                # Camera name is case sensitive, folder names may not be
                for cam in allCameras:
                    if cam.lower() == currentCameraName:
                        camFiles = self._clipMgr.getAllFilesFromLocation(cam)
                        camFiles.sort()
                        self._logger.info("Processing folder for '%s' with %d files in database" % (currentCameraName, len(camFiles)))
                        break

            for curFile in files:
                indexPath = normalizePath(os.path.join(path, curFile))
                if curFile.lower() in _kRemovableFiles:
                    self._pendingDeletes.append(indexPath)
                    markedForDeletion += 1
                    continue

                if not curFile.lower().endswith('.mp4'):
                    continue

                searchPath = indexPath[fileEntryStart:]
                filesScanned += 1
                filePresent = (self._listSearch(camFiles, searchPath) >= 0)

                # We grab the full list of file for the camera early on, and use it
                # for the majority files that are currently in database.
                # For the few that may need to be deleted, or may have been added in the
                # last few moments, we perform individual queries
                if not filePresent:
                    startTime, _ = self._clipMgr.getFileTimeInformation(searchPath)
                    if startTime == -1:
                        self._pendingDeletes.append(indexPath)
                        markedForDeletion += 1

        for dirPath, _, files in os.walk(self._tmpDir, True):
            for filename in files:
                filesScanned += 1
                filename = normalizePath(os.path.join(dirPath, filename))
                if filename not in self._tmpFileDict:
                    self._tmpFileDict[filename] = now

        # Add old files to the pending deletes list
        dictFiles = self._tmpFileDict.keys()
        for filename in dictFiles:
            filesScanned += 1
            if self._tmpFileDict[filename]+_kTmpFileLifespan < now:
                # If this file has expired, add it to the pending deletes list.
                del self._tmpFileDict[filename]
                if filename not in self._pendingDeletes:
                    self._pendingDeletes.append(filename)
                    markedForDeletion += 1
        finished = time.time()
        self._logger.info("Orphan files cleanup scanned %d files in %d seconds, %d marked for deletion" % (filesScanned, int(finished-now), markedForDeletion))

    ###########################################################
    def _canDeleteFolder(self, name):
        """ Determine is a folder can be deleted.
        """
        # we'd let the folder be 60 seconds in the past, before allowing to delete it
        _kSafeDeletionDistance = 60

        folderName = os.path.basename(name)
        if not folderName.isdigit():
            # folders we managed will only have digits in their names
            return False

        # see which folder was current a minute ago
        currentFolder = str(time.time() - _kSafeDeletionDistance)[:5]

        # we can only delete folders prior to that folder
        return int(folderName) < int(currentFolder)


    ###########################################################
    def _removeEmptyFolder(self, name):
        """ Remove empty folder we may have creeated
            This method will only remove folders named "thumbs" or similar to "15123"
            (e.g. first five characters of the timestamp).
            In the latter case, it also won't remove the folder if it corresponds to the current
            or recent (within the last few seconds) timestamp.
        """
        if len(os.listdir(name)) != 0:
            return

        if os.path.basename(name) == kThumbsSubfolder:
            pathToCheck = os.path.dirname(name)
        else:
            pathToCheck = name

        if self._canDeleteFolder(pathToCheck):
            try:
                self._logger.debug("Removing folder " + ensureUtf8(name))
                os.rmdir(name)
            except:
                self._logger.warning("Couldn't remove %s: %s" % (ensureUtf8(name), traceback.format_exc()))

    ###########################################################
    def _getThumbsStats(self, camID, timeID):
        """ For a pair of cameraID/timeID returns a tuple of (size,count,needsUpdate)
            of the cached values for the corresponding thumbs subfolder.
            If no cached value found, (0,0,True) will be returned
        """
        result = (0, 0, True)
        camThumbs = self._thumbStats.get(camID, None)
        if camThumbs is not None:
            timeThumbs = camThumbs.get(timeID, None)
            if timeThumbs is not None:
                result = timeThumbs
        return result

    ###########################################################
    def _updateThumbsStats(self, camID, timeID, size, count):
        """ Store cached values for thumbs size and count, given
            the corresponding cameraID/timeID.
            The cache only gets populated, if the timeID does not match
            the current time;  in other words, only if we'd stopped
            writing to this thumbs location
        """
        try:
            # updating only makes sense if we've finished writing to this folder
            if int(timeID) < int(str(time.time())[:5]):
                if size > 0:
                    self._thumbStats.setdefault(camID, {})[timeID] = (size, count, False)
                else:
                    try:
                        del self._thumbStats[camID][timeID]
                    except:
                        pass
        except:
            self._logger.error("Error updating thumb stats: %s" % traceback.format_exc())

    ###########################################################
    def _updateRemovedThumbsStats(self, camID, timeID, deletedSize, deletedCount):
        """ Update the cached thumbs statistics, to reflect the deleted thumb files
        """
        if deletedCount == 0:
            return

        timeThumbs = self._getThumbsStats(camID, timeID)
        if not timeThumbs[2]:
            if timeThumbs[1] - deletedCount <= 0 or \
               timeThumbs[0] - deletedSize <= 0:
                try:
                    del self._thumbStats[camID][timeID]
                except:
                    pass
            else:
                newVal = (timeThumbs[0]-deletedSize,
                          timeThumbs[1]-deletedCount,
                          False)
                self._thumbStats[camID][timeID] = newVal

    ###########################################################
    def _shouldProcessDir(self, root, dirname):
        """ Determine if the subfolder should be scanned in order to
            populate thumbs storage cache, and check whether the subfolder is empty
        """
        # never skip processing of camera dirs
        if root == self._videoDir:
            return True

        # Process thumbs folders, if not found in cache
        if dirname == kThumbsSubfolder:
            timeSubfolder = os.path.dirname(root)
            timeID = os.path.basename(timeSubfolder)
            camSubfolder = os.path.dirname(timeSubfolder)
            camID = os.path.basename(camSubfolder)

            _, _, needsUpdate = self._getThumbsStats(camID, timeID)
            return needsUpdate

        # "time"-based folders only need to be processed once, as long as:
        # 1.  They're not currently being written to, and
        # 2a. Their corresponding thumbs subfolder doesn't exist, or
        # 2b. Their corresponding thumbs subfolder is in cache
        if len(dirname) == 5 and dirname.isdigit():
            if dirname == str(time.time())[:5]:
                # Ignore "current" folders while they're still being written to
                # We will be 10-40MB off per camera in size calculations,
                # But the saved runtime makes it worth the discrepancy.
                return False
            timeID = dirname
            camID = os.path.basename(root)
            thumbsSize, thumbsCount, needsUpdate = self._getThumbsStats(camID, timeID)
            if needsUpdate:
                # no cache entry
                thumbsPath = os.path.join(root, dirname, kThumbsSubfolder)
                if not os.path.isdir(thumbsPath):
                    # no thumbs subfolder ... store the cached value for thumbs,
                    # so we don't rescan this folder in the future,
                    # but rescan it this once, in case it's empty
                    # and needs to be deleted
                    self._updateThumbsStats(camID, timeID, 1, 0)

            # Update the totals using cached values (will be 0's if not in cache)
            self._thumbsSize += thumbsSize
            self._thumbsCount += thumbsCount
            return needsUpdate

        # Process everything else
        return True



    ###########################################################
    def _scanVideoStorage(self):
        """ Scan video storage, and perform housekeeping tasks like:
            -- detect and eliminate empty dirs
            -- calculate the size of thumbnails
            -- remove orphaned thumbnails
        """
        kMaxRuntime = 5000
        timerLogger = TimerLogger("Video storage scan")
        thumbsDirsScanned = 0
        nonThumbDirsScanned = 0
        orphanedThumbs = []

        self._thumbsPartial = False
        self._thumbsSize = 0
        self._thumbsCount = 0

        for root, dirnames, filenames in os.walk(self._videoDir):
            # Pare down subfolders, so we don't keep re-checking the same ones twice
            # This will also count all the cached thumb folders
            dirnames[:] = [d for d in dirnames if self._shouldProcessDir(root, d)]

            dirsCount = len(dirnames)
            filesCount = len(filenames)

            # self._logger.error("Processing " + root + " " + str(dirsCount) + " dirs,  " + str(filesCount) + " files")

            # Process folders with no files
            if filesCount == 0:
                # no files in the currrent dir
                if dirsCount == 0 and root != self._videoDir:
                    # no folders either, and it's not the rootdir ... attempt to delete
                    self._removeEmptyFolder(root)
                elif dirsCount == 1 and dirnames[0] == kThumbsSubfolder:
                    # there's only thumbs folder, left behind somehow
                    # schedule it for cleanup, unless the video folder is still "current"
                    self._logger.debug("Found an orphaned dir " + ensureUtf8(root))
                    if os.path.basename(root) != str(time.time())[:5]:
                        orphanedThumbs.append(os.path.join(root,kThumbsSubfolder))

            # Process thumbs folders
            if os.path.basename(root) == kThumbsSubfolder:
                timeSubfolder = os.path.dirname(root)
                timeID = os.path.basename(timeSubfolder)
                camSubfolder = os.path.dirname(timeSubfolder)
                camID = os.path.basename(camSubfolder)
                orphaned = root in orphanedThumbs

                folderThumbsSize, folderThumbsCount, folderNeedsUpdate = self._getThumbsStats(camID, timeID)

                if orphaned or folderNeedsUpdate:
                    folderThumbsCount = 0
                    folderThumbsSize = 0

                    if orphaned:
                        # thumbs with no corresponding videos ... delete all, and delete folder if empty
                        orphanedThumbs.remove(root)
                        deleted = 0
                        for filename in fnmatch.filter(filenames, '*.jpg'):
                            fullPath = os.path.join(root, filename)
                            try:
                                os.remove(fullPath)
                                deleted += 1
                            except:
                                self._logger.warning("Couldn't remove %s: %s" % (ensureUtf8(fullPath), traceback.format_exc()))
                        # schedule this thumbs folder for deletion, if empty
                        if deleted == filesCount and dirsCount == 0:
                            self._removeEmptyFolder(root)
                            # should try to delete the parent as well, now it's empty
                            self._removeEmptyFolder(os.path.dirname(root))
                    else:
                        for filename in fnmatch.filter(filenames, '*.jpg'):
                            folderThumbsSize += os.path.getsize(os.path.join(root, filename))
                            folderThumbsCount += 1

                    self._updateThumbsStats(camID, timeID, folderThumbsSize, folderThumbsCount)
                    thumbsDirsScanned += 1

                    self._thumbsSize += folderThumbsSize
                    self._thumbsCount += folderThumbsCount

            else:
                nonThumbDirsScanned += 1


            if timerLogger.diff_ms() > kMaxRuntime:
                self._thumbsPartial = True
                self._logger.info("Aborting storage scan: thumbsDirsScanned=" + str(thumbsDirsScanned) + \
                                    " nonThumbDirsScanned=" + str(nonThumbDirsScanned))
                break

        self._logger.info(timerLogger.status())

    ###########################################################
    def _populateFileSizeCacheItem(self, filePath, deleteIfNotFound, currentTime):
        fullPath = os.path.join(self._videoDir, filePath)
        if os.path.exists(fullPath):
            fileSize = os.path.getsize(fullPath)
            self._fileSizeCache[filePath] = (fileSize, currentTime)
            return fileSize
        if deleteIfNotFound:
            try:
                del self._fileSizeCache[filePath]
            except:
                pass
        return 0


    ###########################################################
    def _getFileListSize(self, fileList):
        """Calculate the amount of disk space used by some files.

        @param  fileList  A list of (file, _,  _, _) tuples.
        @return size      The size in bytes used by the files in fileList.
        """
        now = time.time()

        size = 0

        cached = 0
        nonCached = 0
        expired = 0

        expiredItems = {}

        for filePath, _, _, _ in fileList:
            try:
                fileSize, cacheTime = self._fileSizeCache.get(filePath, (None,None))
                if not fileSize is None:
                    itemExpired = (now-cacheTime > _kFileSizeCacheLifespan)
                    if itemExpired:
                        # organized expired items into buckets based on the expiration time
                        expiredItems.setdefault(cacheTime,[]).append(filePath)
                    size += fileSize
                    cached += 1
                else:
                    size += self._populateFileSizeCacheItem(filePath, False, now)
                    nonCached += 1
            except Exception:
                self._logger.warning("Couldn't get size of %s" % filePath)

        # Renew expired items, oldest first. Limit renewals to _kMaxFileCacheExpirationsAtOnce items
        expirationTimes = sorted(expiredItems.keys())
        for expirationTime in expirationTimes:
            for expiredItem in expiredItems[expirationTime]:
                self._populateFileSizeCacheItem(filePath, True, now)
                expired += 1
                if expired > _kMaxFileCacheExpirationsAtOnce:
                    break
            if expired > _kMaxFileCacheExpirationsAtOnce:
                break



        self._logger.info("Querying list of size " + str(len(fileList)) + " took " + str(time.time()-now) + "s; " + str(cached) + " cached, " + str(nonCached) + " non-cached, " + str(expired) + " expired items")
        return size


    ###########################################################
    def _deleteFile(self, file, camLoc, firstMs, lastMs, allowClips=False):
        """Delete a file.

        @param  file         The file to delete.
        @param  camLoc       The camera location of the file.
        @param  firstMs      The ms of the first frame in the file.
        @param  lastMs       The ms of the last frame in the file.
        @param  allowClips   If true, allow clips to be made.
        @return fileSize     The size in bytes freed by deleting the file.
        @return spaceGained  The fileSize - the size of any clips created
                             from the file.
        @return clipList     A list of (clip, camLoc, firstMs, lastMs) created
                             when deleting the file.
        """
        fileSize = 0
        clipSizes = 0
        clipList = []
        fullPath = os.path.join(self._videoDir, file)
        timesToRemove = [(firstMs, lastMs)]
        clipsAdded = 0

        # Save any information we need as we're about to remove it
        saveTimeList = self._clipMgr.getSaveTimeList(file)
        saveTimeList.sort()
        prevFile = self._clipMgr.getPrevFile(file)
        nextFile = self._clipMgr.getNextFile(file)
        procWidth, procHeight = self._clipMgr.getProcSize(file)

        # Remove the file from the clip db
        self._clipMgr.removeClip(file)

        self._logger.info("Removing ./%s, allowClips=%s saveTimeList=%s firstMs=%s lastMs=%s" %
                          (file, str(allowClips), str(saveTimeList), str(firstMs), str(lastMs)))

        # Check if we need to make any clips
        if allowClips and saveTimeList:
            # Retrieve the msList of the original file
            origFileMsList = getMsList(fullPath, self._logger.getCLogFn())

            if not origFileMsList:
                self._logger.warn("Couldn't retrieve msList for file %s, "
                                  "aborting." % fullPath)
                saveTimeList = []

            saveTimeListCopy = saveTimeList
            saveTimeList = []
            i = 0
            while i<len(saveTimeListCopy):
                if ( i+1 < len(saveTimeListCopy) and
                    saveTimeListCopy[i][1] < saveTimeListCopy[i+1][0] and
                    saveTimeListCopy[i][1] + _kMergeClipThresholdMs >= saveTimeListCopy[i+1][0] ):
                    # The two ranges are within 4s of each other. Merge the two ranges, and skip the next entry
                    self._logger.debug("file="+file+" i="+str(i)+" merging ranges ["+
                                        str(saveTimeListCopy[i][0])+","+
                                        str(saveTimeListCopy[i][1])+"] and ["+
                                        str(saveTimeListCopy[i+1][0])+","+
                                        str(saveTimeListCopy[i+1][1])+"]")
                    saveTimeList.append((saveTimeListCopy[i][0], saveTimeListCopy[i+1][1]))
                    i+=1
                else:
                    saveTimeList.append(saveTimeListCopy[i])
                i+=1

            i = 0
            for (saveStart, saveStop) in saveTimeList:
                origSaveStart = saveStart
                origSaveStop = saveStop

                # Find the actual file times closest to our desired save times
                msListLen = len(origFileMsList)
                bisectIndex = bisect.bisect_left(origFileMsList,
                                                 (saveStart-firstMs))
                if bisectIndex == msListLen:
                    self._logger.warn("Save requested for times not in file. "
                                      "Requested, file: %s" %
                                      str((saveStart-firstMs, saveStop-firstMs,
                                           origFileMsList[0],
                                           origFileMsList[msListLen-1])))
                    bisectIndex -= 1
                startOffset = origFileMsList[bisectIndex]
                saveStart = firstMs + startOffset
                bisectIndex = bisect.bisect_left(origFileMsList,
                                                 (saveStop-firstMs))
                if bisectIndex == msListLen:
                    bisectIndex -= 1
                stopOffset = origFileMsList[bisectIndex]
                saveStop = firstMs + stopOffset

                newClipName = file[:-4] + "-%i.mp4" % i
                newClipPath = os.path.join(self._videoDir, newClipName)


                # actual offset may vary, as we search backwards for keyframe
                actualStartOffset = ClipUtils.remuxSubClip(fullPath, newClipPath, startOffset,
                        stopOffset, self._configDir, self._logger.getCLogFn())
                if actualStartOffset < 0:
                    self._logger.warning("Couldn't create clip %s from %s, %s"
                                         %(fullPath, newClipPath, str(
                                           (saveStart, saveStop, startOffset, stopOffset))))
                    continue

                if startOffset > actualStartOffset:
                    startOffsetAdjustment = startOffset-actualStartOffset
                else:
                    startOffsetAdjustment = 0
                saveStart = saveStart - startOffsetAdjustment


                # If the new clip is at the beginning or end of the original
                # clip, maintain any prev/next links
                prev = ''
                next = ''
                if saveStart == firstMs and prevFile:
                    prev = prevFile
                if saveStop == lastMs and nextFile:
                    next = nextFile


                # If the last timestamp is off (we've seen mostly off-by-1 errors),
                # correct based on the actual duration of the file
                clipDuration = getDuration(newClipPath, self._logger.getCLogFn())
                if saveStart+clipDuration < saveStop:
                    self._logger.warning("Correcting last timestamp value of " + str(saveStop) +
                                        " to " + str(saveStart+clipDuration) + " based on duration of " + str(clipDuration))
                    saveStop = saveStart+clipDuration

                self._logger.debug("Created new clip %s from %s: startMs=%d/%d/%d stopMs=%d/%d/%d duration=%d/%d/%d startOffset=%d actualStartOffset=%d startOffsetAdjustment=%d"
                                     %(newClipName, file,
                                     saveStart, origSaveStart, saveStart-origSaveStart,
                                     saveStop, origSaveStop, saveStop-origSaveStop,
                                     saveStop-saveStart, origSaveStop-origSaveStart, saveStop-saveStart-origSaveStop+origSaveStart,
                                     startOffset, actualStartOffset, startOffsetAdjustment))


                # Add the new clip to the clipMgr
                # self._logger.warning("Adding a clip at '" + newClipName + "'" +
                #                     " rangeRequested=["+str(origStart)+","+str(origStop)+","+str(origStop-origStart)+"]" +
                #                     " rangeSaved=["+str(saveStart)+","+str(saveStop)+","+str(saveStop-saveStart)+"]" +
                #                     " rangeVerified=["+str(saveStart+firstNewFileMs)+","+str(saveStart+lastNewFileMs)+","+str(lastNewFileMs-firstNewFileMs)+"]" );
                self._clipMgr.addClip(newClipName, camLoc, saveStart, saveStop,
                                      prev, next, kCacheStatusNonCache,
                                      procWidth, procHeight, False)
                clipsAdded += 1

                try:
                    fileSize = os.path.getsize(newClipPath)
                    self._fileSizeCache[newClipName] = (fileSize, time.time())
                except:
                    self._logger.error("Failed to update file size for " + newClipName)

                # Get the new clip file size and add to clipSizes
                try:
                    clipSizes += os.path.getsize(newClipPath)
                except Exception:
                    self._logger.warning("Couldn't get size of %s"
                                         % newClipPath)

                # Remove the span of the new clip from the times to delete
                lastTimeSet = timesToRemove.pop()
                if lastTimeSet[0] < saveStart:
                    timesToRemove.append((lastTimeSet[0], saveStart-1))
                if lastTimeSet[1] > saveStop:
                    timesToRemove.append((saveStop+1, lastTimeSet[1]))

                # Add the clip to the clip list
                clipList.append((newClipName, camLoc, saveStart, saveStop))

                i += 1

        for start, stop in timesToRemove:
            self._dataMgr.deleteCameraLocationDataBetween(camLoc, start, stop)
            self._deleteThumbs(camLoc, start, stop)

        try:
            del self._fileSizeCache[file]
        except:
            self._logger.error("Failed to cleanup file size cache for " + file)

        try:
            fileSize = os.path.getsize(fullPath)
            os.remove(fullPath)
            if clipsAdded == 0:
                # don't even attempt to delete folder if clips were added
                dirname = os.path.dirname(fullPath)
                self._removeEmptyFolder(dirname)
        except Exception:
            self._logger.warning("Couldn't remove %s: %s" % (fullPath, traceback.format_exc()))
            self._pendingDeletes.append(fullPath)

        return fileSize, fileSize-clipSizes, clipList

    ###########################################################
    def _deleteThumbs(self, camLoc, start, stop):
        """ Removes thumbnail files for camera in a specific time range
        """
        camLoc = camLoc.lower() # camera name is always converted to lower case when creating paths
        firstFolder = int(str(start)[:5])
        lastFolder = int(str(stop)[:5])
        subfolders = []
        totalFilesDeleted = 0
        for prefix in range(firstFolder, lastFolder+1):
            subfolders.append( str(prefix) )
        self._logger.debug("Removing thumbs between " + str(start) + " and " + str(stop) + "; folders=" + ensureUtf8(str(subfolders)))
        for folder in subfolders:
            thumbFolder = os.path.join(self._videoDir, camLoc, folder, kThumbsSubfolder )

            # Thumbs folder may not exist, check for it first
            if not os.path.isdir(thumbFolder):
                continue

            keptFiles = 0
            deletedSize = 0
            deletedCount = 0

            for file in os.listdir(thumbFolder):
                fileMs = int(os.path.splitext(os.path.basename(file))[0])
                if fileMs >= start and fileMs <= stop:
                    fullFilePath = os.path.join(thumbFolder, file)
                    try:
                        size = os.path.getsize(fullFilePath)
                        os.remove(fullFilePath)
                        self._logger.debug("Deleted " + ensureUtf8(fullFilePath))
                        deletedSize += size
                        deletedCount += 1
                    except:
                        self._logger.error("Failed to delete " + ensureUtf8(fullFilePath))
                else:
                    keptFiles += 1

            if keptFiles == 0:
                self._removeEmptyFolder(thumbFolder)

            totalFilesDeleted += deletedCount
            self._updateRemovedThumbsStats(camLoc, folder, deletedSize, deletedCount)

        if totalFilesDeleted > 0:
            self._logger.debug("Deleted " + str(totalFilesDeleted) + " thumb files")

    ###########################################################
    def _checkForInterrupts(self, currentOperation):
        if (time.time()-self._cleanupCycleLastInterruptCheckTime) > _kMaxUnresponsiveTime:
            self._cleanupCycleLastInterruptCheckTime = time.time()
            try:
                # If there's a message pending, process it and exit the cleanup loop; otherwise proceed as needed
                msg = self._commandQueue.get(False)
                self._logger.info("Reached time limit while " + currentOperation + ". Ran uninterrupted for " + str(int(time.time() - self._cleanupCycleStartTime)) + "sec")
                self._processMessage(msg)
                return True
            except Exception:
                pass
        return False


    ###########################################################
    def _doCleanup(self):
        """Perform disk cleanup.

        @return  moreToDo  If True, we'd like to be called again, if possible.
        """
        # Cleanup orphan files if necessary
        self._removeOrphanFiles()

        # Cleanup any remote files hanging around
        self._removeRemoteFiles()

        # Attempt to remove any pending deletes before calculating disk space.
        for i in xrange(len(self._pendingDeletes)-1, -1, -1):
            try:
                os.remove(self._pendingDeletes[i])
                self._pendingDeletes.pop(i)
            except Exception:
                if not os.path.exists(self._pendingDeletes[i]):
                    self._pendingDeletes.pop(i)

        if self._infiniteMode:
            # If we're running with 'infinite' disk space we skip all the
            # cache/clip cleanup code.
            return

        # Get the current state of the disk.
        try:
            os.makedirs(self._videoDir)
        except Exception:
            pass

        if not os.path.isdir(self._videoDir):
            self._logger.warning("Video directory %s could not be found." %
                                 self._videoDir)
            return


        diskFree = 0
        diskPctFree = 0
        systemDiskFree = 0
        systemDiskPctFree = 0

        try:
            diskUsageTupleArchive = getDiskUsage(self._videoDir)
            diskFree = diskUsageTupleArchive[2] - _kReservedDiskSpace
            diskPctFree = diskUsageTupleArchive[3]
        except Exception:
            self._logger.error("Could not retrieve disk space from %s" %
                               self._videoDir, exc_info=True)

        try:
            diskUsageTupleArchive = getDiskUsage(self._tmpDir)
            systemDiskFree = diskUsageTupleArchive[2]
            systemDiskPctFree = diskUsageTupleArchive[3]
        except Exception:
            self._logger.error("Could not retrieve disk space from %s" %
                               self._tmpDir, exc_info=True)

        cacheFiles = self._clipMgr.getCacheFiles()
        clipFiles = self._clipMgr.getNonCacheFiles()
        unmanagedFiles = self._clipMgr.getUnmanagedFiles()
        cacheSpaceUsed = self._getFileListSize(cacheFiles)
        clipSpaceUsed = self._getFileListSize(clipFiles)
        self._scanVideoStorage() # determines thumbs size, and processes empty dirs
        unmanagedSpaceUsed = self._getFileListSize(unmanagedFiles)
        usedSpace = cacheSpaceUsed + clipSpaceUsed + self._thumbsSize

        # The amount we are allowed to use is the minimum of the user setting
        # and the maximum possible.
        totalUsableSpace = min(self._maxStorage, usedSpace+diskFree)

        # Verify that we have enough space available to operate.
        minRequiredSpace = _kMinSpacePerCam*self._numCameras
        self._logger.debug("Max space %d, min space %d, numCameras %i" %
                           (totalUsableSpace, minRequiredSpace,
                            self._numCameras))

        targetFreeSpace = max(_kTargetFreeSpacePerCam*self._numCameras,
                            kMinFreeSysDriveSpaceMB*_kMbToBytes*_kMinFreeSpaceStayAheadRatio)
        curFree = totalUsableSpace-usedSpace

        self._logger.info(("Free: %s (%d%%) disk, %s cur, %s tgt; "
                           "Used: %s cache, %s clip, %s/%d/%s thumbs, %s xtra, %s cfg; "
                           "TmpFree: %s (%d%%) disk") % (
                           getStorageSizeStr(diskFree),
                           diskPctFree,
                           getStorageSizeStr(curFree),
                           getStorageSizeStr(targetFreeSpace),
                           getStorageSizeStr(cacheSpaceUsed),
                           getStorageSizeStr(clipSpaceUsed),
                           getStorageSizeStr(self._thumbsSize),
                           self._thumbsCount,
                           "p" if self._thumbsPartial else "f",
                           getStorageSizeStr(unmanagedSpaceUsed),
                           getStorageSizeStr(self._maxStorage),
                           getStorageSizeStr(systemDiskFree),
                           systemDiskPctFree ))
        if minRequiredSpace > totalUsableSpace:
            # If not, notify the back end and quit.
            self._logger.warning("Insufficient space: %i MB per camera expected"
                               % (_kMinSpacePerCam/1024/1024))
            self._backEndQueue.put([MessageIds.msgIdInsufficientSpace])

        # Start timing now; that means that if the above is slow we'll be
        # unresponsive for longer, but at least we can be guaranteed that
        # we'll get a decent amount done.  Hopefully the above isn't slow...
        self._cleanupCycleStartTime = time.time()
        self._cleanupCycleLastInterruptCheckTime = self._cleanupCycleStartTime

        # Trim cache files over the specified number of hours, check space
        # Note: works on newer files first...
        lowestTime = time.time()*1000-self._maxCacheDuration
        #lowestTime = time.time()*1000-2*60*1000 # run after 2 min ... useful for debugging
        i = len(cacheFiles)-1
        preTrimFree = curFree
        while i > -1:
            curFile, camLoc, firstMs, lastMs = cacheFiles[i]
            i -= 1
            if lastMs < lowestTime:
                fileSize, spaceGained, clipList = self._deleteFile(curFile,
                                                                   camLoc,
                                                                   firstMs,
                                                                   lastMs, True)
                curFree += spaceGained
                cacheSpaceUsed -= fileSize
                clipFiles.extend(clipList)

                if self._checkForInterrupts("cleaning cache"):
                    return True

        if preTrimFree != curFree:
            self._logger.info("Post cache trim %.1fM free" % (curFree / _kMbToBytesF))

        if curFree > targetFreeSpace:
            self._logger.debug("No further work necessary")
            self._tidyObjectTable()
            # if we have partial thumbs stats, run again immediately
            return self._thumbsPartial

        usableSpacePerCam = totalUsableSpace/self._numCameras

        if usableSpacePerCam > _kMinCacheBlockPerCam:
            if usableSpacePerCam > _kMinCacheBlockPerCam+_kFirstClipBlockPerCam:
                self._logger.info("Trimming clips to min size")
                # Delete clips down to _kFirstClipBlockPerCam
                while (curFree < targetFreeSpace) and \
                      (clipSpaceUsed > _kFirstClipBlockPerCam*self._numCameras)\
                      and clipFiles:

                    curFile, camLoc, firstMs, lastMs = clipFiles.pop(0)
                    fileSize, _, _ = self._deleteFile(curFile, camLoc, firstMs,
                                                      lastMs)
                    clipSpaceUsed -= fileSize
                    curFree += fileSize
                    self._logger.debug("%d free, %d cacheUsed, %d clipUsed" %
                                       (curFree, cacheSpaceUsed, clipSpaceUsed))

                    if self._checkForInterrupts("trimming clips"):
                        return True


            self._logger.info("Trimming cache to min size")
            # Delete cache down to _kMinCacheBlockPerCam
            while (curFree < targetFreeSpace) and \
                  (cacheSpaceUsed > _kMinCacheBlockPerCam*self._numCameras) \
                  and cacheFiles:

                curFile, camLoc, firstMs, lastMs = cacheFiles.pop(0)
                fileSize, spaceGained, clipList = self._deleteFile(curFile,
                                                                   camLoc,
                                                                   firstMs,
                                                                   lastMs, True)
                curFree += spaceGained
                cacheSpaceUsed -= fileSize
                clipFiles.extend(clipList)
                self._logger.debug("%d free, %d cacheUsed, %d clipUsed" %
                                   (curFree, cacheSpaceUsed, clipSpaceUsed))

                if self._checkForInterrupts("trimming to min cache size"):
                    return True

            # If we're still not free enough, delete clips.  If we started by
            # deleting clips this is relevant as deleting cache may have
            # produced clips, so some previously skipped now need to go.
            self._logger.info("Trimming clips again as necessary")
            while (curFree < targetFreeSpace) and clipFiles:
                curFile, camLoc, firstMs, lastMs = clipFiles.pop(0)
                spaceGained, _, _ = self._deleteFile(curFile, camLoc, firstMs,
                                                     lastMs)
                curFree += spaceGained
                self._logger.debug("%d free" % curFree)

                if self._checkForInterrupts("trimming clips (round 2)"):
                    return True

        else:
            # Dire space constraints...Delete clips, then delete cache files
            # WITHOUT making clips for marked times.
            self._logger.info("Low space - removing clips")
            while (curFree < targetFreeSpace) and clipFiles:
                curFile, camLoc, firstMs, lastMs = clipFiles.pop(0)
                fileSize, _, _ = self._deleteFile(curFile, camLoc, firstMs,
                                                  lastMs)
                curFree += fileSize
                self._logger.debug("%d free" % curFree)

                # Dire crunch, allow more time
                if self._checkForInterrupts("removing clips on low space"):
                    return True

            self._logger.info("Low space - removing cache")
            while (curFree < targetFreeSpace) and cacheFiles:
                curFile, camLoc, firstMs, lastMs = cacheFiles.pop(0)
                fileSize, _, _ = self._deleteFile(curFile, camLoc, firstMs,
                                                  lastMs)
                curFree += fileSize
                self._logger.debug("%d free" % curFree)

                # Dire crunch, allow more time
                if self._checkForInterrupts("removing cache on low space"):
                    return True

        self._tidyObjectTable()

        self._logger.info("Finished cleaning")
        return False

    ###########################################################
    def _tidyObjectTable(self):
        # This is a very expensive operation (took 30s on my system), that seems to not
        # come across many things to tidy. Make sure not to run it too often
        if time.time()-self._lastTidyObjectTableTime > _kMinTidyObjectTablePeriod:
            # Tidy up the object table in case there's anything we missed
            # Ideally this shouldn't do anything, but it pays to be paranoid...
            self._dataMgr.tidyObjectTable()
            self._lastTidyObjectTableTime = time.time()


##############################################################################
def _forcedQuitCallback():
    """A callback to notify the current app if a force quit ever happens.

    This is done here so that we don't keep registering if we restart; also
    doing things this way keeps anyone from holding a reference to the app.
    """
    if _cleaner is not None:
        _cleaner._markDone()
__callbackFunc = registerForForcedQuitEvents(_forcedQuitCallback) #PYCHECKER Not intended to be used; just here to keep refCount
