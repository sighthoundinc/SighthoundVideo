#!/usr/bin/env python

#*****************************************************************************
#
# ClipManager.py
#     API for accessing and interacting with clip database (clibDb) and storage
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
Contains the ClipManager class.
"""

# Python imports...
from itertools import groupby
import bisect
import cPickle
import datetime
import os
import sqlite3 as sql
import time
import sys

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.listUtils.CompressRanges import compressRanges
from vitaToolbox.sql.TimedConnection import TimedConnection

# Local imports...
from appCommon.CommonStrings import kSqlAlertThreshold
from videoLib2.python.ClipReader import ClipReader, getMsList

# Constants
kCacheStatusNonCache  =  0  # This is not a cache file
kCacheStatusCache     =  1  # This is a cache file
kCacheStatusUnmanaged = -1  # This is 'unmanaged', neither cache nor noncache.

# If forced tags may not have been completed, the first and last retry times.
_kRetryFirst = 10*1000
_kRetryMax = 5*60*1000


###############################################################
class ClipManager(object):
    """A class for managing video clips"""
    ###########################################################
    def __init__(self, logger, clipMergeThreshold=0):
        """Initializer for the ClipManager class

        @param  logger  An instance of a VitaLogger to use.
        """
        self._logger = logger
        self._connection = None

        self._curDbPath = None

        # A cache: (fileName, procSize)
        self._procSizeCache = (None, None)

        # Key = cameraLocation, value = last ms time added to the db.
        self._maxTimeAdded = {}

        # Key = cameraLocation, value = time range list to be marked for saving
        #                               when cache is comitted.
        self._pendingSaves = {}

        self._clipMergeThreshold = clipMergeThreshold
        self._clipMergeThresholdCache = None

    ###########################################################
    def _addProcSize(self, cam, firstMs, width, height):
        """ Add a single proc size range entry for a specific camera
        """
        firstMsVal = firstMs if firstMs is not None else 0
        strval = '''INSERT INTO clipProcSizes (camLoc, firstMs, procWidth, procHeight) Values ''' \
                    '''('%s', %d, %d, %d)''' % (cam, firstMsVal, width, height)
        # self._logger.error("Running %s" % strval)
        self._cur.execute(strval)


    ###########################################################
    def _populateProcSizeTable(self):
        """ Use clips table to determine unique proc sizes, and populate clipProcSizes table with these values
        """
        camNames = self.getCameraLocations()
        for cam in camNames:
            procSizes = self.getUniqueProcSizesBetweenTimes_Legacy(cam, 0, int(time.time()*1000))
            # self._logger.error("ProcSizes for %s: %s" % (cam, str(procSizes)))
            for procSize in procSizes:
                self._addProcSize(cam, procSize[2], procSize[0], procSize[1])
        self.save()

    ###########################################################
    def _createProcSizeTable(self):
        """Create the proc size table

        clips:
            camLoc      - text, req, name of the camera location file is from
            firstMs     - int, req, absolute ms of the first time camera processed at this size
            procWidth   - int, req, width video was processed at (or 0).
            procHeight  - int, req, height video was processed at (or 0).
        """
        # Use a page size of 4096.  The thought (from google gears API docs),
        # is that: "Desktop operating systems mostly have default virtual
        # memory and disk block sizes of 4k and higher."
        self._cur.execute('''PRAGMA page_size = 4096''')

        try:
            self._cur.disableExecuteLogForNext()
            self._cur.execute(
                '''CREATE TABLE clipProcSizes ('''
                '''camLoc TEXT, firstMs INTEGER,'''
                '''procWidth INTEGER DEFAULT 0, procHeight INTEGER DEFAULT 0)''')
            self._populateProcSizeTable()
        except sql.OperationalError:
            # Ignore failures in creating the table, which can happen because
            # of race conditions...
            pass



    ###########################################################
    def _createClipPaddingTable(self):
        try:
            self._cur.disableExecuteLogForNext()
            self._cur.execute(
                '''CREATE TABLE clipPadding (updateTime INTEGER PRIMARY KEY, paddingSec INTEGER)''')
        except sql.OperationalError:
            # Ignore failures in creating the table, which can happen because
            # of race conditions...
            pass

    ###########################################################
    def _createClipsTable(self):
        """Create the necessary tables in the database

        clips:
            uid         - int, primary key
            filename    - text, req, name of the video
            camLoc      - text, req, name of the camera location file is from
            firstMs     - int, req, absolute ms of the first frame in the video
            lastMs      - int, req, absolute ms of the final frame in the video
            prevFile    - text, opt, name of the file being continued
            nextFile    - text, opt, name of the continuing file
            tags        - blob, opt, pickled dictionary of tags/values
                                     associated with the file
            isCache     - int, req, whether this is part of the cache or not
                           0 - not cache
                           1 - cache
                          -1 - file is unmanaged
                          Now that we have "unmanaged", really better name
                          is 'cacheStatus', but can't update old tables.
            procWidth   - int, req, width video was processed at (or 0).
            procHeight  - int, req, height video was processed at (or 0).
        """
        # Use a page size of 4096.  The thought (from google gears API docs),
        # is that: "Desktop operating systems mostly have default virtual
        # memory and disk block sizes of 4k and higher."
        self._cur.execute('''PRAGMA page_size = 4096''')

        try:
            self._cur.disableExecuteLogForNext()
            self._cur.execute(
                '''CREATE TABLE clips (uid INTEGER PRIMARY KEY, filename TEXT, '''
                '''camLoc TEXT, firstMs INTEGER, lastMs INTEGER, prevFile TEXT, '''
                '''nextFile TEXT, tags BLOB, isCache INTEGER, '''
                '''procWidth INTEGER DEFAULT 0, procHeight INTEGER DEFAULT 0)''')
        except sql.OperationalError:
            # Ignore failures in creating the table, which can happen because
            # of race conditions...
            pass


    ###########################################################
    def _upgradeOldTablesIfNeeded(self):
        """Upgrade from older versions of tables."""

        # From ~5590 and earlier
        # ----------------------

        # Get the SQL that was used to create the object table...
        ((clipsSql,),) = self._cur.execute(
            '''SELECT sql FROM sqlite_master'''
            ''' WHERE type="table" AND name="clips"''')

        if 'procWidth' not in clipsSql:
            # Expect that the first statement might fail; that can happen if
            # another process is running at nearly the same time and also
            # decided to upgrade the tables.  If the first statement succeeds,
            # we expect the rest to succeed.
            try:
                self._cur.disableExecuteLogForNext()
                self._cur.execute(
                    '''ALTER TABLE clips ADD COLUMN procWidth INTEGER DEFAULT 0'''
                )
                self._cur.execute(
                    '''ALTER TABLE clips ADD COLUMN procHeight INTEGER DEFAULT 0'''
                )
            except sql.OperationalError:
                # Happens if two processes try at same time...
                pass


    ###########################################################
    def _addIndices(self):
        """Add some indices to the database.

        Normally, this is just a helper for _createClipsTable(), but also might
        be called to update an old version of a database.
        """
        # Primary key: filename; add camLoc in there to try to handle cases
        # when both are needed...
        self._cur.execute('''CREATE INDEX IF NOT EXISTS'''
                          ''' IDX_CLIPS_FILENAME_CAMLOC on'''
                          ''' clips (filename, camLoc)''')

        # Make it easy to find places that refer to this file...
        self._cur.execute('''CREATE INDEX IF NOT EXISTS'''
                          ''' IDX_CLIPS_PREVFILE on'''
                          ''' clips (prevFile)''')
        self._cur.execute('''CREATE INDEX IF NOT EXISTS'''
                          ''' IDX_CLIPS_NEXTFILE on'''
                          ''' clips (nextFile)''')

        # These work as an index for camLoc and help for subsequent refinements
        # on firstMs / lastMs
        self._cur.execute('''CREATE INDEX IF NOT EXISTS'''
                          ''' IDX_CLIPS_CAMLOC_FIRSTMS on'''
                          ''' clips (camLoc, firstMs)''')
        self._cur.execute('''CREATE INDEX IF NOT EXISTS'''
                          ''' IDX_CLIPS_CAMLOC_LASTMS on'''
                          ''' clips (camLoc, lastMs)''')


        self._cur.execute('''CREATE INDEX IF NOT EXISTS'''
                          ''' IDX_CLIPS_ISCACHE_FIRSTMS on'''
                          ''' clips (isCache, firstMs)''')


    ###########################################################
    def open(self, filePath, timeout=15):
        """Open the database, creating tables if necessary

        @param  filePath  Path of the database file to open
        @param  timeout   The time in seconds connections will wait for locks
                          to free without throwing an exception.
        """
        assert type(filePath) == unicode

        self._curDbPath = filePath

        if self._connection:
            self.close()

        # Open the database file and retrieve a list of the tables
        self._connection = sql.connect(filePath.encode('utf-8'), timeout,
                factory=TimedConnection, check_same_thread=False)
        self._connection.setParameters(self._logger, float(kSqlAlertThreshold), os.path.exists(self._curDbPath+".debug"))
        self._cur = self._connection.cursor()

        # Use persistant mode for journal files.
        self._cur.execute("PRAGMA journal_mode=PERSIST").fetchall()

        tables = self._cur.execute('''SELECT name FROM sqlite_master '''
                                   '''WHERE type='table' ORDER BY name;''')

        hasClipsTable = False
        hasPaddingTable = False
        hasProcSizeTable = False
        for row in tables.fetchall():
            if 'clips' == row[0]:
                hasClipsTable = True
            if 'clipPadding' == row[0]:
                hasPaddingTable = True
            if 'clipProcSizes' == row[0]:
                hasProcSizeTable = True

        if not hasClipsTable:
            # Set up tables if they don't exist
            self._createClipsTable()
        else:
            # TEMPORARY (TODO: delete, or move to _upgradeOldTablesIfNeeded)
            # Add the isCache column if this is an old db
            result = self._cur.execute('''SELECT sql FROM sqlite_master WHERE'''
                                       ''' tbl_name="clips" AND type="table"''')
            tableCreateStr = result.fetchone()[0]
            if 'isCache' not in tableCreateStr:
                self._cur.execute('''ALTER TABLE clips ADD isCache INTEGER''')

            # Other upgrades for old tables...
            self._upgradeOldTablesIfNeeded()

        if not hasPaddingTable:
            self._createClipPaddingTable()

        if not hasProcSizeTable:
            self._createProcSizeTable()

        self._addIndices()

        self._connection.commit()


    ###########################################################
    def getPath(self):
        """Retrieve the database path.

        @return clipDbPath  Path to the clip database, or None.
        """
        return self._curDbPath


    ###########################################################
    def close(self):
        """Close the database"""
        if self._connection:
            self._connection.close()

        self._connection = None
        self._curDbPath = None


    ###########################################################
    def save(self):
        """Save all changes to the database"""
        assert self._connection is not None

        self._connection.commit()

    ###########################################################
    def disableCache(self):
        """Disable cache for this connection"""
        assert self._connection is not None

        self._connection.execute('''PRAGMA cache_size = 0''')

        self.save()

    ###########################################################
    def reset(self):
        """Reset the database"""
        assert self._connection is not None

        self._connection.execute('''DROP TABLE clips''')
        self._connection.execute('''DROP TABLE clipPadding''')

        self._createClipsTable()
        self._createClipPaddingTable()
        self._addIndices()
        self.save()


    ###########################################################
    def addClip(self, filename, camLoc, firstMs, lastMs, prevFile,
                nextFile, cacheStatus, procWidth, procHeight, updateProcSize=True):
        """Insert a clip into the database

        @param  filename    Name of the file to add
        @param  camLoc      The location of the camera the clip was recorded at
        @param  firstMs     The absolute millisecond time of the first frame
        @param  lastMs      The absolute millisecond time of the final frame
        @param  prevFile    The name of the file being continued if applicable
        @param  nextFile    The name of the continuing file if applicable
        @param  cacheStatus 1 if this is a cache file, 0 if not, -1 if
                            this file is unmanaged.
        @param  procWidth   The width this was processed at.
        @param  procHeight  The height this was processed at.
        @param  updateProcSize Update proc size for new clips (but not when editing existing clip)
        """
        assert self._connection is not None

        # Convert paths to posix.  Windows can read posix paths, osx can't
        # read windows paths.  We don't need to worry about drives or anything
        # since these videos should be in directorys relative to the database.
        filename = filename.replace(os.sep, '/')
        prevFile = prevFile.replace(os.sep, '/')
        nextFile = nextFile.replace(os.sep, '/')


        if prevFile:
            # Check that the previous file is actually in the database.
            exists = self._cur.execute(
                '''SELECT * FROM clips WHERE filename=?''', (prevFile,)
                ).fetchall()
            if not len(exists):
                # Check if the user deleted the previous file.  We only look
                # back for a maximum of 5 deletes.  It should be impossible
                # for the user to manage 2 deletes before we've flushed the
                # most recent video, doing five just to be extra cautious.
                nameBase = prevFile[:-4]
                nameChoices = ['"'+nameBase+'r'*i+'.mp4"' for i in range(1,6)]
                names = self._cur.execute('''SELECT filename FROM clips WHERE'''
                                          ''' filename IN (%s) ORDER BY '''
                                          '''filename''' % ','.join(nameChoices)
                                         ).fetchall()
                if not len(exists):
                    prevFile = ''
                else:
                    prevFile = names[len(names)-1][0]

        self._cur.execute('''INSERT INTO clips (filename, camLoc, firstMs, '''
                          '''lastMs, prevFile, nextFile, isCache, procWidth, '''
                          '''procHeight) Values '''
                          '''(?, ?, ?, ?, ?, ?, ?, ?, ?)''', (filename, camLoc,
                          firstMs, lastMs, prevFile, nextFile, cacheStatus,
                          procWidth, procHeight))

        if prevFile:
            self._cur.execute(
                '''UPDATE clips SET nextFile=? WHERE camLoc=? AND '''
                '''filename=?''', (filename, camLoc, prevFile))

        if nextFile:
            self._cur.execute(
                '''UPDATE clips SET prevFile=? WHERE camLoc=? AND '''
                '''filename=?''', (filename, camLoc, nextFile))

        if cacheStatus == kCacheStatusCache:
            # If this is a cache file being added, set any pending saved times
            # that fall within it's duration.
            self._maxTimeAdded[camLoc] = lastMs
            pendingSaves = compressRanges(sorted(self._pendingSaves.get(camLoc,
                                                                        [])))
            savedTimes = [(saveStart, saveEnd) for (saveStart, saveEnd) in
                          pendingSaves if (saveStart <= lastMs)]
            if savedTimes:
                self.setFileTags(filename, {'saveTimes':savedTimes}, False)

            # Remove any ranges completely consumed
            self._pendingSaves[camLoc] = [
                (saveStart, saveEnd) for (saveStart, saveEnd) in
                pendingSaves if (saveEnd > lastMs)
            ]

        if updateProcSize:
            oldProcSize = self.getLastProcSize(camLoc)
            if oldProcSize is None or oldProcSize[0] != procWidth or oldProcSize[1] != procHeight:
                self._logger.info("Updating procSize for %s from %s to %s as of %d" % (camLoc, str(oldProcSize), str((procWidth,procHeight)), firstMs))
                self._addProcSize(camLoc, firstMs, procWidth, procHeight)


        self.save()


    ###########################################################
    def removeClip(self, filename):
        """Remove a clip from the database.

        @param  filename  Name of the file to remove.
        """
        assert self._connection is not None

        filename = filename.replace(os.sep, '/')

        # Remove the entry for the given file
        self._cur.execute('''DELETE FROM clips WHERE filename=?''', (filename,))

        # Remove prev/next links
        self._cur.execute(
            '''UPDATE clips SET prevFile="" WHERE prevFile=?''',
            (filename,))
        self._cur.execute(
            '''UPDATE clips SET nextFile="" WHERE nextFile=?''',
            (filename,))

        self.save()


    ###########################################################
    def isVideoOnDay(self, date, camLoc=None):
        """Return if there is any video on the given date.

        @param  date    The datetime.date object to check.
        @param  camLoc  If non-None, we'll limit to this camera location.
        """
        # Figure out firstMs and lastMs (+1, which is easier...)
        firstMs = int(time.mktime(date.timetuple()) * 1000)
        date += datetime.timedelta(1)
        lastMsPlus1 = int(time.mktime(date.timetuple()) * 1000)

        # Separate query depending on whether we have a camera loc...
        #
        # TODO: Do we need to add an index to make 2nd case fast?  We don't
        # have an index on just lastMs without camera location...
        if camLoc:
            self._cur.execute('''SELECT uid FROM clips WHERE camLoc=? AND '''
                              '''lastMs >=? AND firstMs<? LIMIT 1''',
                              (camLoc, firstMs, lastMsPlus1))
        else:
            self._cur.execute('''SELECT uid FROM clips WHERE '''
                              '''lastMs >=? AND firstMs<? LIMIT 1''',
                              (firstMs, lastMsPlus1))

        return (len(self._cur.fetchall()) != 0)


    ###########################################################
    def getProcSize(self, filename):
        """Return the size that the given file was processed at.

        This should always be in the database, except for old (pre 1.0)
        databases.  In those cases, we'll just return (0, 0)

        @return procWidth   The width it was processed at, or 0.
        @return procHeight  The height it was processed at, or 0.
        """
        # Try the cache first.  We use a simple 1-entry cache to avoid a
        # database hit in many cases.  We don't have to worry about cache
        # coherency, since the size a given video was proceesed at is
        # permanent--it never changes for a given file.
        cacheFilename, cacheProcSize = self._procSizeCache

        # we should always get a DB hit, but be robust and return "unknown"
        # if somehow we do not
        retval = (0, 0)

        if cacheFilename == filename:
            # Cache hit!
            retval = cacheProcSize
        else:
            # Cache miss, so do the database access.
            self._cur.execute('''SELECT procWidth, procHeight FROM '''
                              '''clips WHERE filename=?''', (filename,))
            result = self._cur.fetchall()

            # The next assert failure could happen if another process deletes
            # a file at just the right time...
            assert len(result) == 1, ("Each file should be in clip DB once: %s" % filename)
            if result:
                # Re-cache and return...
                self._procSizeCache = (cacheFilename, result[0])
                retval = result[0]

        return retval

    ###########################################################
    def setClipMergeThreshold(self, time, value, updateDb):
        """ Remember when clip merge threshold had changed
        """
        self._logger.info("Updating clipManager's merge threshold to %d, updateDb=%s" % (value, str(updateDb)))
        self._clipMergeThreshold = value
        if updateDb:
            self._cur.execute('''INSERT INTO clipPadding (updateTime, paddingSec) Values '''
                '''(?, ?)''', (time, value))
            self.save()
        if not self._clipMergeThresholdCache is None:
            self._clipMergeThresholdCache.append((time,value))

    ###########################################################
    def getClipMergeThresholds(self, timeStart, timeStop):
        """ Get time ranges for different padding values effective throughout the search range
        """
        if self._clipMergeThresholdCache is None:
            # get the updates that occurred within the given time period
            self._cur.execute('''SELECT updateTime, paddingSec FROM clipPadding ORDER BY updateTime ASC''')
            self._clipMergeThresholdCache = self._cur.fetchall()

        result = []
        for item in self._clipMergeThresholdCache:
            if item[0] <= timeStart:
                result = [ item ]
            elif item[0] <= timeStop:
                result.append( item )
            else:
                break
        # print "Clip merge thresholds are " + str(result) + " for " + str((timeStart,timeStop)) + " r1=" + str(result1) + " r2=" + str(result2)
        return result

    ###########################################################
    def getFileAt(self, camLoc, ms, tolerance=3000, direction='any'):
        """Find the file corresponding to the given parameters

        @param  camLoc     The desired camera location
        @param  ms         The desired absolute ms
        @param  tolerance  ms before or after a file to still count a match;
                           If None, means infinite tolerance...
        @param  direction  If no file initially matches, the direction in which
                           to seek files, 'any', 'before', or 'after'.  If 'any'
                           it will return the closest result.
        @return filename   The name of the corresponding file, or None
        """
        assert self._connection is not None

        result = self._cur.execute(
                '''SELECT filename, procWidth, procHeight FROM clips '''
                '''WHERE camLoc=? AND firstMs<=? '''
                '''AND lastMs >=?''', (camLoc, ms, ms))

        result = result.fetchall()
        if result:
            # This shouldn't happen, but look for error conditions...
            if len(result) != 1:
                self._logger.warn("Multiple files matched: %s %d" % (camLoc,ms))

            # If we have a match, return the filename
            result = result[0]
            self._procSizeCache = (result[0], (result[1], result[2]))
            return result[0]

        beforeFile = None
        afterFile = None
        beforeMs = 0
        afterMs = 0

        # Search for the closest file after the given timepoint
        if direction == 'after' or direction == 'any':
            if tolerance is not None:
                toleranceStr = '''AND firstMs<%d''' % (ms + tolerance)
            else:
                toleranceStr = ''

            result = self._cur.execute(
                '''SELECT filename, firstMs FROM clips WHERE camLoc=? AND '''
                '''firstMs=(SELECT MIN(firstMs) FROM clips WHERE '''
                '''camLoc=? AND firstMs>? %s)''' % (toleranceStr),
                (camLoc, camLoc, ms))
            result = result.fetchone()
            if result:
                afterFile, afterMs = result

            if direction == 'after':
                return afterFile

        # Search for the closest file before the given timepoint
        if tolerance is not None:
            toleranceStr = '''AND lastMs>%d''' % (ms - tolerance)
        else:
            toleranceStr = ''

        result = self._cur.execute(
            '''SELECT filename, lastMs FROM clips WHERE camLoc=? AND lastMs='''
                    '''(SELECT MAX(lastMs) FROM clips WHERE '''
                    '''camLoc=? AND lastMs<? %s)''' % (toleranceStr),
            (camLoc, camLoc, ms))
        result = result.fetchone()
        if result:
            beforeFile, beforeMs = result

        if direction == 'before' or not afterFile:
            return beforeFile

        if beforeFile and (ms-beforeMs < afterMs-ms):
            return beforeFile

        return afterFile


    ###########################################################
    def getFilesBetween(self, camLoc, startTime, endTime):
        """Find files between two times.

        @param  camLoc     The desired camera location.
        @param  startTime  The first time to include in the search.
        @param  endTime    The last time to include in the search.
        @return fileList   A list of (filename, startTime, stopTime) for files
                           found between the given times, sorted by time
        """
        assert self._connection is not None

        results = self._cur.execute('''SELECT filename, firstMs, lastMs'''
                ''' FROM clips WHERE camLoc=? AND ((firstMs>=? AND firstMs<=?)'''
                ''' OR (firstMs<=? AND lastMs>=?))'''
                ''' ORDER BY firstMs ASC''',
                (camLoc, startTime, endTime, startTime, startTime))

        return results.fetchall()

    ###########################################################
    def getFilesAndProcSizeBetween(self, camLoc, startTime, endTime):
        """Find files between two times. Make sure proc size is consistent

        @param  camLoc     The desired camera location.
        @param  startTime  The first time to include in the search.
        @param  endTime    The last time to include in the search.
        @return fileList   A list of (filename, startTime, stopTime) for files
                           found between the given times, sorted by time.
        """
        assert self._connection is not None

        results = self._cur.execute('''SELECT filename, firstMs, lastMs, procWidth, procHeight'''
                ''' FROM clips WHERE camLoc=? AND ((firstMs>=? AND firstMs<=?)'''
                ''' OR (firstMs<=? AND lastMs>=?))'''
                ''' ORDER BY firstMs ASC''',
                (camLoc, startTime, endTime, startTime, startTime))

        res = results.fetchall()

        procSize = None
        prevFile = None
        retval = []
        for filename, firstMs, lastMs, procWidth, procHeight in res:
            if procSize is None:
                procSize = (procWidth, procHeight)
            if procSize != (procWidth, procHeight):
                raise Exception("Stream dimensions aren't consistent between %s (%dx%d) and %s (%dx%d)" %
                        str(prevFile), procSize[0], procSize[1], filename, procWidth, procHeight )
            retval.append((filename, firstMs, lastMs))
            prevFile = filename
        return (retval, procSize)

    ###########################################################
    def getFileTimeInformation(self, filename):
        """Find the start and end times contained in a file

        @param  filename  The name of the file
        @return startMs   The ms of the first frame in the file, or -1
        @return stopMs    The ms of the last frame in the file, or -1
        """
        assert self._connection is not None

        filename = filename.replace(os.sep, '/')

        result = self._cur.execute(
            '''SELECT firstMs, lastMs FROM clips WHERE filename=?''',
            (filename,))

        result = result.fetchall()
        if not result:
            return -1, -1

        # This shouldn't happen, but look for error conditions...
        if len(result) != 1:
            self._logger.warn("Multiple files matched: %s" % (filename))

        result = result[0]
        return int(result[0]), int(result[1])


    ###########################################################
    def isFileInDatabase(self, filename):
        """Return true if the given file is in the database.

        @param  filename  The name of the file.
        @return isInDb    True if the file is in the database; False otherwise.
        """
        # Just implement using the above function...
        startMs, stopMs = self.getFileTimeInformation(filename)
        if (startMs == -1) or (stopMs == -1):
            assert (startMs == -1) and (stopMs == -1), \
                   "If either startMs or stopMs is -1, both should be."
            return False
        return True


    ###########################################################
    def getNextFileStartTime(self, filename):
        """Find the starting time of the next file in a series

        @param  filename  The name of the current file
        @return ms        The ms of the first frame of the next file, or -1
        """
        assert self._connection is not None

        filename = filename.replace(os.sep, '/')

        result = self._cur.execute(
            '''SELECT firstMs FROM clips WHERE prevFile=?''', (filename,))

        result = result.fetchone()
        if not result:
            return -1

        return int(result[0])


    ###########################################################
    def getPrevFileEndTime(self, filename):
        """Find the ending time of the previous file in a series

        @param  filename  The name of the current file
        @return ms        The ms of the final frame of the previous file, or -1
        """
        assert self._connection is not None

        filename = filename.replace(os.sep, '/')

        result = self._cur.execute(
            '''SELECT lastMs FROM clips WHERE nextFile=?''', (filename,))

        result = result.fetchone()
        if not result:
            return -1

        return int(result[0])


    ###########################################################
    def getNextFile(self, filename):
        """Find the name of the next file in a series

        @param  filename  The name of the current file
        @return nextFile  The name of the next file, or None
        """
        assert self._connection is not None

        filename = filename.replace(os.sep, '/')

        result = self._cur.execute(
                '''SELECT nextFile FROM clips WHERE filename=?''', (filename,))

        result = result.fetchone()
        if not result:
            return None

        return result[0]


    ###########################################################
    def getPrevFile(self, filename):
        """Find the name of the previous file in a series

        @param  filename  The name of the current file
        @return prevFile  The name of the previous file, or None
        """
        assert self._connection is not None

        filename = filename.replace(os.sep, '/')

        result = self._cur.execute(
                '''SELECT prevFile FROM clips WHERE filename=?''', (filename,))

        result = result.fetchone()
        if not result:
            return None

        return result[0]


    ###########################################################
    def getFileFromLocation(self, camLoc):
        """Retrieve a recent file recorded from a camera location

        @param  camLoc     The desired camera location
        @return filename   The name of the file from this location or None
        """
        assert self._connection is not None

        result = self._cur.execute(
                '''SELECT filename FROM clips WHERE camLoc=? '''
                '''ORDER BY firstMs DESC LIMIT 1''', (camLoc,)).fetchone()

        if result:
            # If we have a match, return the first filename
            return result[0]
        return None


    ###########################################################
    def getAllFilesFromLocation(self, camLoc):
        """Retrieve a list of all files recorded at a camera location.

        @param  camLoc     The desired camera location.
        @return filenames  The names of the files from this location or None.
        """
        assert self._connection is not None

        results = self._cur.execute('''SELECT filename FROM clips WHERE '''
                                    '''camLoc=? ''', (camLoc,)).fetchall()
        return [row[0] for row in results]


    ###########################################################
    def getTimesFromLocation(self, camLoc, firstMs=None, lastMs=None,
                             savedOnly=False):
        """Get a list of times that we have clips for for the given location.

        The list will be bounded by the startTime and endTime, if they are
        provided.  Note that if we have a clip that goes through startTime
        or endTime, we'll pretend clip it to startTime/endTime.  Here's an
        example:

        If we have clips for:
            [(1000, 4500), (5000, 6000), (7500, 11000)]

        ...and firstMs = 5500 and lastMs = 9000, we'll return:
            [(5500, 6000), (7500, 9000)]

        @param  camLoc     The desired camera location.
        @param  firstMs    The first time that should be searched.
        @param  lastMs     The last time that should be searched.
        @param  savedOnly  If True will only return ranges that are no longer in
                           cache, or in cache but marked for saving.
        @return ranges     A list of ranges that looks like:
                             [(firstAvailMs, lastAvailMs), ..., ..., ...]
        """
        assert self._connection is not None

        if firstMs is not None:
            firstMs = int(firstMs)
        if lastMs is not None:
            lastMs = int(lastMs)

        timeParts = ['']
        if firstMs is not None:
            timeParts.append('lastMs >= %d' % firstMs)
        if lastMs is not None:
            timeParts.append('firstMs <= %d' % lastMs)

        if not savedOnly:
            results = self._cur.execute((
                '''SELECT filename, firstMs, lastMs, prevFile, nextFile'''
                ''' FROM clips WHERE camLoc=? %s ORDER BY firstMs''') %
                (' AND '.join(timeParts)), (camLoc,)).fetchall()
        else:
            # Get non-cache files within this time range
            files = self._cur.execute(
                '''SELECT filename, firstMs, lastMs, prevFile, nextFile, '''
                '''tags, isCache FROM clips WHERE camLoc=? %s ORDER BY '''
                '''firstMs''' % ' AND '.join(timeParts), (camLoc,)).fetchall()

            results = []
            for filename, start, stop, prev, next, tags, cacheStatus in files:
                if cacheStatus != kCacheStatusCache:
                    # For non cache files add the data and we're done.
                    results.append((filename, start, stop, prev, next))
                else:
                    # For cache files we need to try to grab the tags dict and
                    # look for marked times.
                    try:
                        tagDict = cPickle.loads(str(tags))
                        savedTimes = tagDict.get('saveTimes', [])
                        for first, last in savedTimes:
                            realPrev = prev
                            realNext = next
                            if first > last or last < first:
                                continue
                            if first > stop or last < start:
                                continue
                            if first > start:
                                realPrev = None
                            if last < stop:
                                realNext = None
                            results.append((filename, max(start, first),
                                            min(stop, last), realPrev,
                                            realNext))
                    except Exception:
                        pass

        # Combine adjacent pieces...
        seqFirstMs = None
        ranges = []
        numResults = len(results)
        for i in xrange(numResults):
            thisFilename, thisFirstMs, thisLastMs, _, thisNextFile = results[i]

            if seqFirstMs is None:
                seqFirstMs = thisFirstMs

            if i == numResults-1:
                ranges.append((seqFirstMs, thisLastMs))
            else:
                plus1Filename, _, _, plus1PrevFile, _ = results[i+1]
                if (thisNextFile != plus1Filename) or \
                   (thisFilename != plus1PrevFile):
                    ranges.append((seqFirstMs, thisLastMs))
                    seqFirstMs = None

        # Trim so nothing is outside of the proper ranges...
        if ranges:
            if (firstMs is not None) and (ranges[0][0] < firstMs):
                ranges[0] = (firstMs, ranges[0][1])
            if (lastMs is not None) and (ranges[-1][1] > lastMs):
                ranges[-1] = (ranges[-1][0], lastMs)

        return ranges


    ###########################################################
    def getCacheFiles(self):
        """Get a the video cache files.

        @return fileList  A list of (filepath, camLoc, startTime, endtTime).
        """
        assert self._connection is not None

        result = self._cur.execute(('''SELECT filename, camLoc, firstMs, '''
                                    '''lastMs FROM clips WHERE isCache=%d '''
                                    '''ORDER BY firstMs''') %
                                   kCacheStatusCache)

        return result.fetchall()


    ###########################################################
    def getNonCacheFiles(self):
        """Get video files outside the cache.

        @return fileList  A list of (filepath, camLoc, startTime, endtTime).
        """
        assert self._connection is not None

        result = self._cur.execute(('''SELECT filename, camLoc, firstMs, '''
                                    '''lastMs FROM clips WHERE isCache=%d '''
                                    '''ORDER BY firstMs''') %
                                   kCacheStatusNonCache)

        return result.fetchall()


    ###########################################################
    def getUnmanagedFiles(self):
        """Get video files that we are not managed by the disk cleaner.

        These files aren't counted as cache files nor as non-cache files.

        @return fileList  A list of (filepath, camLoc, startTime, endtTime).
        """
        assert self._connection is not None

        result = self._cur.execute(('''SELECT filename, camLoc, firstMs, '''
                                    '''lastMs FROM clips WHERE isCache=%d '''
                                    '''ORDER BY firstMs''') %
                                   kCacheStatusUnmanaged)

        return result.fetchall()


    ###########################################################
    def getFileTags(self, filename):
        """Get the tags associated with a file.

        @param  filename  The name of the file to get info for.
        @return tagsDict  A dict of tags for the file.
        """
        assert self._connection is not None

        filename = filename.replace(os.sep, '/')

        tagsDict = {}

        result = self._cur.execute(
            '''SELECT tags FROM clips WHERE filename=?''', (filename,))

        result = result.fetchone()
        if result:
            try:
                tagsDict = cPickle.loads(str(result[0]))
            except Exception:
                return {}

        return tagsDict


    ###########################################################
    def setFileTags(self, filename, tags, save=True):
        """Set the tags associated with a file.

        @param  filename  The name of the file to set tags for.
        @param  tags      Dict of tags to save
        @param  save      True if the database shoud be saved.
        """
        assert self._connection is not None

        filename = filename.replace(os.sep, '/')

        pDict = cPickle.dumps(tags)

        self._cur.execute('''UPDATE clips SET tags=? WHERE filename=?''',
                          (pDict, filename))

        if save:
            self.save()


    ###########################################################
    def getSaveTimeList(self, filename):
        """Get the times to save from a cache file.

        @param  filename  The name of the file to get info for.
        @return saveTimes A list of (firstMs, lastMs) tuples defining ranges
                          to save.
        """
        assert self._connection is not None

        tags = self.getFileTags(filename)

        return tags.get('saveTimes', [])

    ###########################################################
    def _padTimeRanges(self, timeRanges):
        """ Pad time ranges based on `clipMergeThreshold' configuration

            This ensures we always have video for padding, even if it
            doesn't directly correspond to saved events.
        """
        if self._clipMergeThreshold == 0:
            return timeRanges
        padding = self._clipMergeThreshold*1000 / 2
        result = []
        for timeRange in timeRanges:
            result.append((timeRange[0]-padding, timeRange[1]+padding))
        return result


    ###########################################################
    def markTimesAsSaved(self, camLoc, timeRanges, existingOnly=False):
        """Mark portions of cache to be saved.

        @param  camLoc        The camera location to add saved times to.
        @param  timeRanges    A list of (firstMs, lastMs) tuples defining ranges
                              to save.
        @param  existingOnly  If True ths marking will only apply to files that
                              have already been added to the database, and will
                              not be tracked to enable future times to be marked
                              on future clips.
        @return retryTime     Retry time in seconds if existingOnly and a retry
                              may be needed, else 0.
        """
        assert self._connection is not None

        if not timeRanges:
            return 0

        timeRanges = self._padTimeRanges(timeRanges)
        timeRanges = compressRanges(sorted(timeRanges))
        now = time.time()*1000
        maxAddTime = timeRanges[-1][1]
        startPassed = (timeRanges[0][0] <= self._maxTimeAdded.get(camLoc, now))

        if startPassed or existingOnly:
            maxEndTime = 0
            # If we're marking times in already saved files load their current
            # saved times, combine with new times and update.
            storedFiles = self.getFilesBetween(camLoc, timeRanges[0][0],
                                               maxAddTime)
            for filename, startTime, endTime in storedFiles:
                maxEndTime = max(endTime, maxEndTime)
                tags = self.getFileTags(filename)
                savedTimes = tags.get('saveTimes', [])
                savedTimes.extend((x, y) for (x, y) in timeRanges if
                                    (startTime <= x <= endTime) or
                                    (startTime <= y <= endTime) or
                                    (x <= startTime <= y) or
                                    (x <= endTime <= y)             )
                tags['saveTimes'] = compressRanges(sorted(savedTimes))
                self.setFileTags(filename, tags, False)

            self.save()

            if existingOnly:
                if maxEndTime < maxAddTime:
                    # If there may still be flushes pending either do a quick
                    # retry (file may make it into the clipdb within a second)
                    # or a long retry (file probably never existed, but try in
                    # a bit anyway in case things were just really jammed up).
                    if now < maxAddTime:
                        return (maxAddTime + _kRetryFirst)/1000
                    elif now < maxAddTime + _kRetryMax:
                        return (maxEndTime + _kRetryMax)/1000
                return 0

        # Save any times past what is currently in the db in the _pendingSaves
        # dict to be added later.
        pendingSaves = self._pendingSaves.get(camLoc, [])
        lastAddedMs = self._maxTimeAdded.get(camLoc, 0)
        pendingSaves.extend((x, y) for (x, y) in timeRanges if #PYCHECKER OK: Pychecker confused by genexpr
                            y >= lastAddedMs+1)
        self._pendingSaves[camLoc] = pendingSaves

        return 0


    ###########################################################
    def updateLocationName(self, oldName, newName, changeMs, videoFolder,
            configDir):
        """Change the name of a camera location.

        @param  oldName      The name of the camera location to change.
        @param  newName      The new name for the camera location.
        @param  changeMs     The absolute ms at which the change took place.
        @param  videoFolder  The directory where video files are stored.
        @param  configDir    Directory to search for config files.
        """
        import videoLib2.python.ClipUtils as ClipUtils  # Lazy--loaded on first need

        # We need to split files that occur across the time change.
        files = self._cur.execute('''SELECT * FROM clips WHERE camLoc=? AND '''
                                  '''lastMs>=? AND firstMs<?''',
                                  (oldName, changeMs, changeMs))
        for (uid, filename, loc, first, last, prev, next, tags, cache,
             procWidth, procHeight) in files:
            # Split the video files and remove the original.
            origFilePath = os.path.join(videoFolder, filename)
            clipNameA = filename[:-4]+'a.mp4'
            clipNameB = filename[:-4]+'b.mp4'
            clipPathA = os.path.join(videoFolder, clipNameA)
            clipPathB = os.path.join(videoFolder, clipNameB)

            newFirstLeft = ClipUtils.remuxSubClip(origFilePath, clipPathA, 0,
                                           changeMs-first+10, configDir,
                                           self._logger.getCLogFn())
            if newFirstLeft < 0:
                self._logger.warning("Couldn't create clipA from %s, %s"
                                     % (origFilePath, changeMs))
            else:
                newFirstLeft = first + newFirstLeft
            newFirstRight = ClipUtils.remuxSubClip(origFilePath, clipPathB,
                                           max(changeMs-10-first,0), last-first+10,
                                           configDir, self._logger.getCLogFn())
            if newFirstRight < 0:
                self._logger.warning("Couldn't create clipB from %s, %s"
                                     % (origFilePath, changeMs))
            else:
                newFirstRight = first + newFirstRight

            # print >> sys.stderr,  "first=%d, last=%d, change=%d, newFirstLeft=%d, newFirstRight=%d" % \
            #      (first, last, changeMs, newFirstLeft, newFirstRight)
            self._cur.execute('''DELETE FROM clips WHERE uid=?''', (uid,))

            try:
                os.remove(origFilePath)
            except Exception:
                self._logger.warning("Couldn't remove file %s" % origFilePath)

            # Update the old db entry to reflect the new clip.
            sanitizedName = clipNameA.replace(os.sep, '/')
            self._cur.execute('''INSERT INTO clips (filename, camLoc, '''
                '''firstMs, lastMs, prevFile, nextFile, tags, isCache, '''
                '''procWidth, procHeight) Values '''
                '''(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (sanitizedName, loc,
                newFirstLeft, changeMs, prev, "", tags, cache, procWidth, procHeight))
            self._cur.execute('''UPDATE clips SET nextFile=? '''
                              '''WHERE nextFile=?''', (sanitizedName, filename))
            self._trimFileSavedTimes(sanitizedName, tags, first, changeMs)

            # Add an entry for the second new clip.
            sanitizedName = clipNameB.replace(os.sep, '/')
            self._cur.execute('''INSERT INTO clips (filename, camLoc, '''
                '''firstMs, lastMs, prevFile, nextFile, tags, isCache, '''
                '''procWidth, procHeight) Values '''
                '''(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (sanitizedName, newName,
                newFirstRight, last, "", next, tags, cache, procWidth, procHeight))
            self._cur.execute('''UPDATE clips SET prevFile=? '''
                              '''WHERE prevFile=?''', (sanitizedName, filename))
            self._trimFileSavedTimes(sanitizedName, tags, changeMs, last)

        # Update files that start after the time change.
        self._cur.execute('''UPDATE clips SET camLoc=? WHERE camLoc=? '''
                          '''AND firstMs>=?''', (newName, oldName, changeMs))


    ###########################################################
    def deleteLocation(self, location):
        """Remove all information associated with a given location.

        @param  location  The name of the camera location to remove.
        """
        # Remove the entries for the given location
        self._cur.execute('''DELETE FROM clips WHERE camLoc=?''', (location,))
        self._cur.execute('''DELETE FROM clipProcSizes WHERE camLoc=?''', (location,))
        self.save()


    ###########################################################
    def deleteCameraLocationDataBetween(self, cameraLocation, startMs, stopMs,
                                        videoFolder, configDir):
        """Delete data associated with a camera locaiton.

        Automatically does a save() for you.

        @param  cameraLocation  The camera location to delete data at.
        @param  startMs         The first ms to remove.
        @param  stopMs          The last ms to remove.
        @param  videoFolder     The directory where video files are stored.
        @param  configDir       Directory to search for config files.
        @return failedDeletes   A list of paths to files that were not
                                successfully removed.
        """
        import videoLib2.python.ClipUtils as ClipUtils  # Lazy--loaded on first need

        failedDeletes = []

        # Split or remove any affected clips.
        affectedClips = self.getFilesBetween(cameraLocation, startMs, stopMs)

        for clip, _, _ in affectedClips:
            origFilePath = os.path.join(videoFolder, clip)
            msList = []
            uid, _, _, clipStart, clipStop, prev, next, tags, cache, w, h = \
                    self._cur.execute(
                        '''SELECT * FROM clips WHERE filename=?''', (clip,)
                    ).fetchone()

            # Only do the getMsList if we have to.
            if clipStart < startMs or clipStop > stopMs:
                msList = getMsList(origFilePath, self._logger.getCLogFn())

                if not msList:
                    # If the msList could not be loaded the file probably
                    # doesn't exist. No matter what the reason though, we
                    # aren't going to be able to splice this file so we're
                    # forced to delete the whole thing. To do this we simply
                    # use the file boundaries as the clip boundaries.
                    clipStart = startMs
                    clipStop = stopMs

            # We'll defer executes till after we create the clips so that we
            # don't hold the database lock...
            deferredExecuteList = []
            trimSavedTimesList = []

            if clipStart < startMs:
                # Calculate an ms value that actually exists in the file
                bisectIndex = bisect.bisect_left(msList, startMs-clipStart)
                bisectIndex = max(0, min(bisectIndex, len(msList)-1))
                changeMs = msList[bisectIndex]+clipStart

                # If this file starts before our removal start time make a
                # new clip preserving the beginning.
                newName = clip[:-4]+'l.mp4'
                newPath = os.path.join(videoFolder, newName)
                newClipStartLeft = ClipUtils.remuxSubClip(origFilePath, newPath, 0,
                                               changeMs-clipStart+10,
                                               configDir)
                if newClipStartLeft < 0:
                    self._logger.warning("Couldn't create left clip from %s"
                                         % origFilePath)
                else:
                    newClipStartLeft = clipStart + newClipStartLeft

                if newClipStartLeft != clipStart:
                    # This is unusual -- should be able to remux starting from first frame
                    self._logger.warning("Left clip from %s created with offset %d"
                                         % (origFilePath, newClipStartLeft))

                # print >> sys.stderr,  "first=%d, last=%d, change=%d, newFirstLeft=%d" % \
                #    (clipStart, clipStop, changeMs, newClipStartLeft)

                sanitizedName = newName.replace(os.sep, '/')
                deferredExecuteList.append((
                    '''INSERT INTO clips (filename, camLoc, '''
                    '''firstMs, lastMs, prevFile, nextFile, tags, isCache, '''
                    '''procWidth, procHeight) '''
                    '''Values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (sanitizedName, cameraLocation, newClipStartLeft, changeMs, prev,
                     "", tags, cache, w, h)
                ))
                deferredExecuteList.append((
                    '''UPDATE clips SET nextFile=? '''
                    '''WHERE nextFile=?''', (sanitizedName, clip)
                ))
                trimSavedTimesList.append((sanitizedName, tags, clipStart,
                                           changeMs))
            else:
                deferredExecuteList.append((
                    '''UPDATE clips SET nextFile=? WHERE '''
                    '''nextFile=?''', ("", clip)
                ))

            if clipStop > stopMs:
                # Calculate an ms value that actually exists in the file
                bisectIndex = bisect.bisect_right(msList, stopMs-clipStart)
                bisectIndex = max(0, min(bisectIndex, len(msList)-1))
                changeMs = msList[bisectIndex]+clipStart

                # If this file stops after our removal stop time make a new
                # clip preserving the ending.
                newName = clip[:-4]+'r.mp4'
                newPath = os.path.join(videoFolder, newName)
                newClipStartRight = ClipUtils.remuxSubClip(origFilePath, newPath,
                                               max(changeMs-10-clipStart,0),
                                               clipStop-clipStart+10,
                                               configDir)
                if newClipStartRight < 0:
                    self._logger.warning("Couldn't create right clip from %s"
                                         % origFilePath)
                else:
                    newClipStartRight = clipStart + newClipStartRight
                # print >> sys.stderr,  "first=%d, last=%d, change=%d, newFirstRight=%d" % \
                #     (clipStart, clipStop, changeMs, newClipStartRight)

                sanitizedName = newName.replace(os.sep, '/')
                deferredExecuteList.append((
                    '''INSERT INTO clips (filename, camLoc, '''
                    '''firstMs, lastMs, prevFile, nextFile, tags, isCache, '''
                    '''procWidth, procHeight) '''
                    '''Values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (sanitizedName, cameraLocation, newClipStartRight, clipStop, "",
                     next, tags, cache, w, h)
                ))
                deferredExecuteList.append((
                    '''UPDATE clips SET prevFile=? '''
                    '''WHERE prevFile=?''', (sanitizedName, clip)
                ))
                trimSavedTimesList.append((sanitizedName, tags, changeMs,
                                           clipStop))
            else:
                deferredExecuteList.append((
                    '''UPDATE clips SET prevFile=? WHERE '''
                    '''prevFile=?''', ("", clip)
                ))

            # Do our deferred stuff...
            for executeItem in deferredExecuteList:
                self._cur.execute(*executeItem)
            for trimItem in trimSavedTimesList:
                self._trimFileSavedTimes(*trimItem)

            # Remove the original file.
            self._cur.execute('''DELETE FROM clips WHERE uid=?''', (uid,))

            # Save the database before doing anything else to try to avoid
            # slow SQL stuff...
            self.save()

            try:
                os.remove(origFilePath)
            except Exception:
                failedDeletes.append(origFilePath)
                self._logger.info("Couldn't remove file %s" % origFilePath)


        return failedDeletes


    ###########################################################
    def getMostRecentTimeAt(self, camLoc):
        """Retrieve the most recent time for a location in the database.

        @param  camLoc    The desired camera location.
        @return recentMs  The most recent ms available for camLoc, or -1.
        """
        assert self._connection is not None

        result = self._cur.execute(
                '''SELECT MAX(lastMs) FROM clips WHERE camLoc=?''', (camLoc,)
                ).fetchone()

        if result:
            # If we have a match, return the first filename
            return result[0]
        return -1


    ###########################################################
    def _trimFileSavedTimes(self, filename, tags, firstMs, lastMs):
        """Ensure that saved times don't extend beyond the file boundaries.

        @param  filename  The name of the file to check.
        @param  tags      The value stored in the tags column for filename.
        @param  firstMs   The firstMs of the file.
        @param  lastMs    The lastMs of the file.
        """
        tagsChanged = False

        try:
            tagsDict = cPickle.loads(str(tags))
        except Exception:
            return

        savedTimes = tagsDict.get('saveTimes', [])
        newSavedTimes = []
        for start, stop in savedTimes:
            if stop < firstMs or start > lastMs:
                tagsChanged = True
                continue
            if start < firstMs or stop > lastMs:
                start = max(start, firstMs)
                stop = min(stop, lastMs)
                tagsChanged = True
            newSavedTimes.append((start, stop))

        if tagsChanged:
            tagsDict['saveTimes'] = newSavedTimes
            pickledTags = cPickle.dumps(tagsDict)
            self._cur.execute('''UPDATE clips SET tags=? WHERE filename=?''',
                              (pickledTags, filename))


    ###########################################################
    def getCameraLocations(self):
        """Retrieve a list of all camera locations in the database.

        @return locNames  A list of all camera locations in the database
        """
        results = self._cur.execute('''SELECT DISTINCT camLoc FROM clips''')
        return [result[0] for result in results]

    ###########################################################
    def getLastProcSize(self, camLoc):
        searchStr = '''SELECT firstMs, procWidth, procHeight FROM clipProcSizes ''' \
                    '''WHERE camLoc=? ORDER BY firstMs DESC LIMIT 1'''
        parameters = [camLoc]
        sqlres = self._cur.execute(searchStr, tuple(parameters)).fetchall()
        if len(sqlres) == 0:
            return None
        return (sqlres[0][1], sqlres[0][2])

    ###########################################################
    def getUniqueProcSizesBetweenTimes(self, camLoc, startTime=None, endTime=None):
        searchStr = '''SELECT firstMs, procWidth, procHeight FROM clipProcSizes ''' \
                    '''WHERE camLoc=? ORDER BY firstMs ASC'''
        parameters = [camLoc]
        sqlres = self._cur.execute(searchStr, tuple(parameters)).fetchall()

        if startTime is None:
            startTime = 0
        if endTime is None:
            endTime = int(time.time()*1000)

        result = []
        for item in sqlres:
            newItem = (item[1], item[2], item[0], 0)
            if item[0] <= startTime:
                result = [ newItem ]
            elif item[0] <= endTime:
                if len(result) > 0:
                    prev = result[len(result)-1]
                    result[len(result)-1] = (prev[0], prev[1], prev[2], item[0]-1)
                result.append( newItem )
            else:
                if len(result) > 0:
                    prev = result[len(result)-1]
                    result[len(result)-1] = (prev[0], prev[1], prev[2], item[0]-1)
                break

        if len(result) > 0:
            prev = result[len(result)-1]
            if prev[3] == 0:
                result[len(result)-1] = (prev[0], prev[1], prev[2], int(time.time()*1000))

        # print( "Proc sizes for " + camLoc + " are " + str(result) + " for " + str((startTime,endTime)) )
        return result

    ###########################################################
    def getUniqueProcSizesBetweenTimes_Legacy(self, camLoc, startTime=None, endTime=None):
        """Retrieve a list of sizes the camera was processed at between the given times.

        @param  camLoc     The desired camera location.
        @param  startTime  The time to begin the search, None for the beginning
        @param  endTime    The time to stop the search, None for most recent
        @return results    A list of sizes the camera was processed at for
                           certain ranges of time. Contains a list of 4-tuples
                           of (procWidth, procHeight, firstMs, lastMs).
                           Note: if the list contains only one 4-tuple, then
                           procWidth and procHeight is unique, and firstMs and
                           lastMs should be ignored; they may hold None values.
                           If the list contains more than one 4-tuple, then
                           procWidth and procHeight are not unique, and you must
                           use the firstMs and lastMs to determine which
                           procSize was used for a specified period of time.
        """

        # Construct a search criteria based on the requested times and
        # camera location...
        searchStr = 'SELECT DISTINCT procWidth, procHeight FROM clips ' \
                    'WHERE camLoc=?'
        parameters = [camLoc]

        # Contruct the extra part of the search string based on given values
        # for firstMs and lastMs...
        extraSearchStr = ''
        if startTime:
            extraSearchStr += ' AND lastMs>=?'
            parameters.append(str(int(startTime)))

        if endTime:
            extraSearchStr += ' AND firstMs<=?'
            parameters.append(str(int(endTime)))
        extraSearchStr += ' ORDER BY firstMs'

        # Retrieve the data from the database...
        result = self._cur.execute(searchStr + extraSearchStr, tuple(parameters)).fetchall()

        # If nothing was returned, return an empty list.
        if len(result) == 0:
            return []

        # One row from the database means we have a unique processing size
        # for the range of time given.  We're done, so return.
        if len(result) == 1:
            [(procWidth, procHeight)] = result
            return [(int(procWidth), int(procHeight), startTime, endTime,)]

        # If we got this far, that means we retrieved more than one row of
        # processing sizes. This means different clips were processed at
        # different sizes during the given range of time. We must query the
        # database again for more information, and group the processing sizes
        # based off of time. Reconstruct the search criteria, same as before,
        # but retrieve time information this time...
        searchStr = 'SELECT procWidth, procHeight, firstMs, lastMs FROM clips ' \
                    'WHERE camLoc=?'

        # Retrieve the data from the database...
        result = self._cur.execute(searchStr + extraSearchStr, tuple(parameters)).fetchall()

        # If nothing was returned, return an empty list.
        if len(result) == 0:
            return []

        # Create a compact list of processing sizes and time ranges.
        procSizesAndTimeRanges = []
        procWidth, procHeight, firstMs, lastMs = result[0]
        for i in xrange(0, len(result)):
            if procWidth == result[i][0] and procHeight == result[i][1]:
                lastMs = result[i][3]
            else:
                procSizesAndTimeRanges.append((procWidth, procHeight, firstMs, lastMs))
                procWidth, procHeight, firstMs, lastMs = result[i]
        else:
            procSizesAndTimeRanges.append((procWidth, procHeight, firstMs, lastMs))

        return procSizesAndTimeRanges