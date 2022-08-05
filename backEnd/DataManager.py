#!/usr/bin/env python

#*****************************************************************************
#
# DataManager.py
#     API for accessing and interacting with object and motion database (objDb2)
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
import bisect
import itertools
import operator
import os.path
import os
import sqlite3 as sql
import time
import traceback
import glob
import shutil
from bisect import bisect_left

# Common 3rd-party imports...
from PIL import ImageDraw, ImageColor, Image

# Toolbox imports...
from vitaToolbox.sql.TimedConnection import TimedConnection
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8
from vitaToolbox.sysUtils.TimeUtils import getTimeAsMs
from vitaToolbox.profiling.MarkTime import TimerLogger

# Local imports...
from VideoMarkupModel import VideoMarkupModel
from videoLib2.python.ClipReader import ClipReader

# Constants...
from appCommon.CommonStrings import kThumbsSubfolder
from appCommon.CommonStrings import kSqlAlertThreshold

# ...we always work in a coordinate system that is this big...
_kCoordWidth = 320
_kCoordHeight = 240

# Never remove an entry from the objects table that has been updated in the
# past 10 minutes.  It could still have pending data that would be lost.
_kObjectSaveBuffer = 600000

# Flag to draw boxes and lines transparently. This was a proof-of-concept, but
# the lines drawn just appear weak and the transparency aspect really does not
# show very well. So put it on hold for now.
_kTransparentDraw = False

# drawBoxes - True to draw tracking boxes on the saved clip
# maxSize - Requested maximum size of created clip (may be smaller)
# max_bit_rate - Requested maximum bit rate
_kSaveClipDefaults = {
        "drawBoxes":False,
        "enableTimestamps":False,
        "maxSize":(0,0),
        "max_bit_rate":0,
}


###############################################################
class DataManager(object):
    """A class controlling the object database"""
    ###########################################################
    def __init__(self, logger, clipManager=None, videoStoragePath=None):
        """Initializer for the DataManager class

        @param  logger            An instance of a VitaLogger to use.
        @param  clipManager       A clip manager, required to retrieve frames
        @param  videoStoragePath  Path to the directory videos are stored,
                                  required to retrieve frames
        """
        self._logger = logger
        self._connection = None
        self._clipManager = clipManager

        self._filterStr = ''
        self._targetFilter = ''
        self._cameraFilter = ''

        self._sizeFilter = ''

        self._curDbPath = None

        # Keyed by UID
        self._targetRangeFilterDict = {}

        self._vidStoragePath = videoStoragePath
        self._objList = []
        self._curVidPath = None
        self._curVidSize = None
        self._clipReader = None
        self._curMsIndex = -1
        self._curFrameMs = 0
        self._fileStart = 0
        self._fileStop = 0
        self._bboxCache = {}
        self._cacheKeys = {}
        self._thumbCache = {}
        self._videoDebugLines = []
        self._firstFile = None
        self._lastFile = None
        self._pendingNextFrame = None
        self._audioEnabled = False
        self._asyncReadEnabled = True
        self._curFileAudioEnabled = False

        self._muted = False

        # Init markupModel to defaults, though we expect it to
        # be changed later with setMarkupModel...
        self._markupModel = VideoMarkupModel()

        self._liveMs = 0

        self._procSizeCache = {}


    ###########################################################
    def _createTables(self):
        """Create the necessary tables in the database

        Table objects:
            uid        - int, primary key
            fileName   - text, filename of the associated video file (DEPRECATED - TODO: remove)
            camLoc     - text, name of the camera location the obj was captured
            timeStart  - int, first time the object was seen
            timeStop   - int, final time the object was seen
            rX1, rY1   - int, (DEPRECATED - TODO: remove)
            rX2, rY2   - int, (DEPRECATED - TODO: remove)
            type       - text, a lable for the object's classification
            confidence - real, (DEPRECATED - TODO: remove)
            thumbnail  - blob, (DEPRECATED - TODO: remove)
            minWidth   - int, the minimum height of the object
            maxWidth   - int, the maximum height of the object
            minHeight  - int, the minimum height of the object
            maxHeight  - int, the maximum height of the object

        Table motion:
            objUid - int, the object table uid of the motion object
            frame  - int, the frame number of this bbox
            time   - int, the time corresponding to this frame
            x1, y1 - int, upper left coordinates of the object's bbox
            x2, y2 - int, bottom right coordinates of the object's bbox

        Table actions:
            objUid     - int, the object table uid of the action object
            type       - text, the category, like "person"; this is a duplicate
                         of info in the objects table, but makes searching easy
            action     - text, the action string, like "walking"
            frameStart - int, the start frame number of the action
            timeStart  - int, the milliseconds associated with frameStart
            frameStop  - int, the stop frame number of the action; inclusive
                         (in other words, the action _includes_ this frame)
            timeStop   - int, the milliseconds associated with frameStop

        """
        # Use a page size of 4096.  The thought (from google gears API docs),
        # is that: "Desktop operating systems mostly have default virtual
        # memory and disk block sizes of 4k and higher."
        self._cur.execute('''PRAGMA page_size = 4096''')

        try:
            self._cur.disableExecuteLogForNext()
            self._cur.execute(
                '''CREATE TABLE objects (uid INTEGER PRIMARY KEY, '''
                '''fileName TEXT, camLoc TEXT, timeStart INTEGER, '''
                '''timeStop INTEGER, rX1 INTEGER, rY1 INTEGER, rX2 INTEGER, '''
                '''rY2 INTEGER, type TEXT, confidence REAL, thumbnail BLOB, '''
                '''minWidth INTEGER, maxWidth INTEGER, '''
                '''minHeight INTEGER, maxHeight INTEGER)''')

            self._cur.disableExecuteLogForNext()
            self._cur.execute(
                '''CREATE TABLE motion (objUid INTEGER, frame INTEGER, '''
                '''time INTEGER, x1 INTEGER, y1 INTEGER, x2 INTEGER, '''
                '''y2 INTEGER, '''
                '''PRIMARY KEY (objUid, time))''')

            self._cur.disableExecuteLogForNext()
            self._cur.execute(
                '''CREATE TABLE actions '''
                '''(objUid INTEGER, type TEXT, action TEXT, '''
                '''frameStart INTEGER, timeStart INTEGER, '''
                '''frameStop INTEGER, timeStop INTEGER)'''
            )
        except sql.OperationalError:
            # Happens if two processes try at same time...
            pass


    ###########################################################
    def _upgradeOldTablesIfNeeded(self):
        """Upgrade from older versions of tables."""

        # From 4901 and earlier
        # ---------------------

        # Get the SQL that was used to create the object table...
        ((objectSql,),) = self._cur.execute(
            '''SELECT sql FROM sqlite_master'''
            ''' WHERE type="table" AND name="objects"''')

        if 'minWidth' not in objectSql:
            # Expect that the first statement might fail; that can happen if
            # another process is running at nearly the same time and also
            # decided to upgrade the tables.  If the first statement succeeds,
            # we expect the rest to succeed.
            try:
                self._cur.disableExecuteLogForNext()
                self._cur.execute(
                    '''ALTER TABLE objects ADD COLUMN minWidth INTEGER'''
                )

                self._cur.execute(
                    '''ALTER TABLE objects ADD COLUMN maxWidth INTEGER'''
                )
                self._cur.execute(
                    '''ALTER TABLE objects ADD COLUMN minHeight INTEGER'''
                )
                self._cur.execute(
                    '''ALTER TABLE objects ADD COLUMN maxHeight INTEGER'''
                )
                self._cur.execute(
                    '''UPDATE objects SET minWidth='''
                    '''(SELECT MIN(x2-x1) FROM motion WHERE uid=objUid)'''
                )
                self._cur.execute(
                    '''UPDATE objects SET maxWidth='''
                    '''(SELECT MAX(x2-x1) FROM motion WHERE uid=objUid)'''
                )
                self._cur.execute(
                    '''UPDATE objects SET minHeight='''
                    '''(SELECT MIN(y2-y1) FROM motion WHERE uid=objUid)'''
                )
                self._cur.execute(
                    '''UPDATE objects SET maxHeight='''
                    '''(SELECT MAX(y2-y1) FROM motion WHERE uid=objUid)'''
                )
            except sql.OperationalError:
                # Happens if two processes try at same time...
                pass


    ###########################################################
    def _addIndices(self):
        """Add some indices to the database.

        This will auto-add any indices that are needed...
        """
        # As far as I can tell this index was actually slowing things down.
        # Indexes should typically be avoided for columns with low cardinality,
        # and we never have very many locations.
        self._cur.execute('''DROP INDEX IF EXISTS IDX_OBJECTS_CAMLOC''')

        # This index made getBboxAtFrame() faster, but at the expense of
        # inserts.  We insert more often than we call getBboxAtFrame(), so
        # we'll drop it...
        self._cur.execute('''DROP INDEX IF EXISTS IDX_MOTION_OBJUID_FRAME''')

        # Our most common database operation is searches between two times so
        # indexing times really helps us.  Specifically real time searches are
        # performed most often where timeStop >= ~1 second ago and
        # timeStart <= now.  Because the timeStop search is going to be much
        # smaller/quicker (nearly no values vs likely tens of thousands or
        # more in the timeStart) we want timeStop to be the index.
        # Runtimes: IDX (stop) < no index < IDX (start).
        self._cur.execute('''CREATE INDEX IF NOT EXISTS '''
                          '''IDX_OBJECTS_STOP on objects (timeStop)''')


    ###########################################################
    def open(self, filePath, timeout=45):
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

        tables = map(operator.itemgetter(0),
                     self._cur.execute('''SELECT name FROM sqlite_master '''
                                       '''WHERE type="table"'''))

        if 'objects' not in tables:
            # Set up tables if they don't exist
            self._createTables()

        self._upgradeOldTablesIfNeeded()

        # Always call addIndices to update old versions of databases...
        self._addIndices()

        # Do a big commit now...
        self.save()


    ###########################################################
    def setVideoStoragePath(self, videoStoragePath):
        """Update the video storage path.

        @param  videoStoragePath  Path to the directory videos are stored,
                                  required to retrieve frames.
        """
        self._vidStoragePath = videoStoragePath


    ###########################################################
    def setMarkupModel(self, markupModel):
        """Sets the data model that tells us how to markup video.

        @param  markUpModel  A VideoMarkupModel object.  We'll consult this
                             whenever asked for marked video.  Note that we
                             don't listen for changes--it's the client's job
                             to re-ask us for video if the markup changed.
        """
        self._markupModel = markupModel


    ###########################################################
    def getPaths(self):
        """Retrieve paths important to the data manager.

        @return objDbPath         Path to the object database or None
        @return clipDbPath        Path to the clip manager, or None.
        @return videoStoragePath  Path to the directory videos are stored or
                                  None.
        """
        clipDbPath = None
        if self._clipManager:
            clipDbPath = self._clipManager.getPath()
        return (self._curDbPath, clipDbPath, self._vidStoragePath)


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
    def reset(self):
        """Reset the database"""
        assert self._connection is not None

        self._connection.execute('''DROP TABLE objects''')
        self._connection.execute('''DROP TABLE motion''')

        self._createTables()
        self._addIndices()
        self.save()


    ###########################################################
    #def deleteObject(self, id):
    #    """Remove an object from the database
    #
    #    @param  id  The id of the object to remove from the database
    #    """
    #    assert self._connection is not None
    #
    #    self._cur.execute('''DELETE FROM objects WHERE uid=?''', (id,))
    #    self._cur.execute('''DELETE FROM motion WHERE objUid=?''', (id,))
    #    # TODO: Don't leave the database hanging.  DO A SAVE (!!!)


    ###########################################################
    def addObject(self, timeStart, objType="object", cameraLocation=''):
        """Insert an object into the database

        @param  timeStart       The time the object first came into view
        @param  objType         The type of this object, like 'person' or
                                'object'.
        @param  cameraLocation  The camera location for the object.
        @return dbId            The id for this object assigned by the database
        """
        assert self._connection is not None

        # Always use 'object' for 'unknown' and 'nonperson'
        if objType.lower() in ('unknown', 'nonperson'):
            objType = 'object'

        self._cur.execute(
            '''INSERT INTO objects '''
            '''(camLoc, timeStart, timeStop, type, '''
            '''minWidth, maxWidth, minHeight, maxHeight) Values '''
            '''(?, ?, ?, ?, ?, ?, ?, ?)''',
            (cameraLocation, int(timeStart), int(timeStart),
             objType, _kCoordWidth, 0, _kCoordHeight, 0))

        newId = self._cur.execute('''SELECT last_insert_rowid()''')
        newId = newId.fetchone()[0]

        # Do a save right away so that we don't block out other processes.
        # TODO: Does that hit our speed at all?
        self.save()

        return newId


    ###########################################################
    def addFrame(self, objId, frame, time, bbox, objType, action):
        """Add a new frame of data

        @param  objId    The id of the object in the database
        @param  frame    The number of the frame to add
        @param  time     The time in ms that matches frame
        @param  bbox     A bounding box for the object at the given frame
        @param  objType  The object's type; passed here for speed--
                         this should match the type used for addObject().
        @param  action   The action to add to the database; or None if none.
        """
        assert self._connection is not None

        # Make time an int...
        time = int(time)

        try:
            self._cur.execute('''INSERT INTO motion'''
                              ''' Values (?, ?, ?, ?, ?, ?, ?)''',
                    (objId, frame, time, bbox[0], bbox[1], bbox[2], bbox[3]))
        except sql.IntegrityError:
            # We get this when we violate the uniqueness requirement of the
            # primary key.  In other words: when we try to add a second entry
            # with the same objId and time...  My guess is that this happens
            # due to a tracker bug (?).  In any case, we'll just warn and
            # ignore, but we should get to the bottom of it.
            self._logger.warning("Skipping duplicate data: " +
                str((objId, frame, time, bbox[0], bbox[1], bbox[2], bbox[3])))
            return

        # Update the objects table with some summary info; note that we'll have
        # to update this summary info (if we care) if we ever delete stuff from
        # the motion table.
        # TODO - fix time here, always sets stop time
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        self._cur.execute(
            '''UPDATE objects SET timeStop=?, '''
            '''minWidth=MIN(?, minWidth), maxWidth=MAX(?, maxWidth), '''
            '''minHeight=MIN(?, minHeight), maxHeight=MAX(?, maxHeight) '''
            '''WHERE uid=?''',
            (time, width, width, height, height, objId))

        # Try to extend an action if it already exists; otherwise create a new
        # one.  If frames are always added in order, this is perfect.  If frames
        # are added out of order, there might be cases where we'll end up
        # creating a whole bunch of table rows for parts of the same action
        # sequence, like (10 - 12), (13 - 13), (14 - 20), etc.  If this happens
        # in reality, we should add some logic to condense these sequences.
        if action is not None:
            # First try to extend...
            self._cur.execute(
                '''UPDATE actions SET frameStop=?, timeStop=? '''
                '''WHERE objUID=? AND frameStop=? AND action=?''',
                (frame, time, objId, frame-1, action))

            # If the extend failed, do the insert...
            if self._cur.rowcount != 1:
                assert self._cur.rowcount == 0
                self._cur.execute(
                    '''INSERT INTO actions Values (?, ?, ?, ?, ?, ?, ?)''',
                    (objId, objType, action, frame, time, frame, time))


    ###########################################################
    #def updateFrame(self, objId, frame, bbox):
    #    """Change bbox data for an existing frame
    #
    #    @param  objId    The id of the object in the database
    #    @param  frame    The number of the frame to edit
    #    @param  bbox     A bounding box for the object at the given frame
    #    """
    #    assert self._connection is not None
    #
    #    # Right now, we never end up calling this function; if we ever do
    #    # again, we'll need to update to adjust the actions table...
    #    assert False, "May need to update actions table too!"
    #
    #    self._cur.execute(
    #        '''UPDATE motion SET x1=?, y1=?, x2=?, y2=? WHERE objUid=? AND frame=?''',
    #        (bbox[0], bbox[1], bbox[2], bbox[3], objId, frame))


    ###########################################################
    #def deleteFrame(self, objId, frame):
    #    """Remove a frame from the database
    #
    #    @param  objId  The id of the object in the database
    #    @param  frame  The frame number to delete
    #    """
    #    assert self._connection is not None
    #
    #    # Right now, we never end up calling this function; if we ever do
    #    # again, we'll need to update to adjust the actions table...
    #    assert False, "May need to update actions table too!"
    #
    #    self._cur.execute('''DELETE FROM motion WHERE objUid=? AND frame=?''',
    #                      (objId, frame))


    ###########################################################
    #def updateType(self, objId, objType):
    #    """Update the recognition information for an object
    #
    #    @param  objId       The id of the object in the database
    #    @param  objType     A label for the new type
    #    """
    #    assert self._connection is not None
    #
    #    # Right now, we never end up calling this function; if we ever do
    #    # again, we'll need to update to adjust the actions table...
    #    assert False, "May need to update actions table too!"
    #
    #    if objType.lower() in ('unknown', 'nonperson'):
    #        objType = 'object'
    #
    #    self._cur.execute(
    #        '''UPDATE objects SET type=? WHERE uid=?''',
    #        (objType, objId))


    ###########################################################
    def getObjectType(self, objId):
        """Return the type of a given object

        @param  objId  The id of the object to identify
        @return type   The type of the object
        """
        assert self._connection is not None

        result = self._cur.execute('''SELECT type FROM objects WHERE uid=?''',
                                   (objId,))
        result = result.fetchone()
        if result is not None:
            return result[0]
        else:
            # TODO: not sure why this happens, but be robust...
            return "unknown"


    ###########################################################
    def getObjectsBetweenTimes(self, startTime=None, endTime=None, includeAllFields=False):
        """Retrieve objects seen between the given times

        @param  startTime  The time to begin the search, None for the beginning
        @param  endTime    The time to stop the search, None for most recent
        @param  includeAllFields Whether to include more than just IDs
        @return idList     A list of ids (or tuples, if includeAllFields=True) of active objects
        """
        assert self._connection is not None

        # Construct a search criteria based on the requested times
        searchStr = ''
        if startTime:
            searchStr += 'timeStop >= %i' % int(startTime)
            if endTime:
                searchStr += ' AND '
        if endTime:
            searchStr += 'timeStart <= %i' % int(endTime)

        if searchStr and self._filterStr:
            searchStr = ' AND '.join([searchStr, self._filterStr])
        elif self._filterStr:
            searchStr = self._filterStr

        if searchStr:
            searchStr = "WHERE " + searchStr

        # Do the search...
        selection = "uid, timeStart, timeStop, type" if includeAllFields else "uid"
        objs = self._cur.execute('''SELECT %s FROM objects %s''' %
                                (selection, searchStr,)).fetchall()

        if includeAllFields:
            objList = objs
        else:
            # Parse the rows into a list of ids
            objList = [row[0] for row in objs]

        return objList


    ###########################################################
    def getActiveObjectsBetweenTimes(self, startTime=None, endTime=None):
        """Retrieve active objects seen between the given times.

        Similar to getObjectsBetweenTimes but additionally verifies that
        those objects actually have entries in the motion table in the
        specified time ranges.

        @param  startTime  The time to begin the search, None for the beginning
        @param  endTime    The time to stop the search, None for most recent
        @return idList     A list of ids of active objects
        """
        assert self._connection is not None

        objIds = self.getObjectsBetweenTimes(startTime, endTime)
        if not startTime and not endTime:
            return objIds

        searchStr = ''
        if startTime:
            searchStr += 'time >= %i' % int(startTime)
            if endTime:
                searchStr += ' AND '
        if endTime:
            searchStr += 'time <= %i' % int(endTime)
        if searchStr:
            searchStr = "WHERE " + searchStr

        motionIds = self._cur.execute('''SELECT DISTINCT objUid FROM motion '''
                                      '''%s''' % (searchStr,)).fetchall()
        motionIds = [row[0] for row in motionIds]

        return list(set(objIds).intersection(motionIds))


    ###########################################################
    def deleteCameraLocationDataBetween(self, camLoc, startMs, stopMs):
        """Delete data associated with a camera locaiton.

        Automatically does a save() for you.

        @param  camLoc     The camera location to delete data at.
        @param  startMs    The ms at which to start deleting data.
        @param  lastMs     The last ms at which to delete data.
        """
        assert self._connection is not None
        if stopMs < startMs:
            assert False, "stopMs must be >= startMs"
            return

        # Get any affected object ids
        objInfo = self._cur.execute('''SELECT uid, timeStart, timeStop FROM '''
                '''objects WHERE camLoc=? AND timeStart<=? AND timeStop>=?''',
                (camLoc, int(stopMs), int(startMs))).fetchall()

        idList = [info[0] for info in objInfo]

        # Delete non-existant times from the motion table
        if idList:
            timeStr = " AND time >=%i AND time <=%i" % (startMs, stopMs)

            if len(idList) == 1:
                searchStr = "DELETE FROM motion WHERE objUid=%i" % idList[0]
            else:
                searchStr = "DELETE FROM motion WHERE objUid in %s" % \
                            (str(tuple(idList)))

            self._cur.execute(searchStr + timeStr)

            # Remove objects that no longer have any motion data
            orphanedUids = []
            for uid in idList:
                isUidInMotion = self._cur.execute(
                    '''SELECT objUid FROM motion WHERE objUid=?'''
                    ''' LIMIT 1''', (uid,)).fetchone() is not None
                if not isUidInMotion:
                    orphanedUids.append(uid)

            if orphanedUids:
                self._deleteObjects(orphanedUids)

            for objId, start, stop in objInfo:
                if objId in orphanedUids:
                    continue

                if start < startMs:
                    if stop > stopMs:
                        # Add a new object
                        objType, minW, maxW, minH, maxH, = \
                            self._cur.execute('''SELECT type, '''
                                '''minWidth, maxWidth, minHeight, maxHeight '''
                                '''FROM objects WHERE '''
                                '''uid=?''', (objId,)).fetchone()
                        self._cur.execute('''INSERT INTO objects (camLoc, '''
                                '''timeStart, timeStop, type, '''
                                '''minWidth, maxWidth, minHeight, maxHeight) '''
                                '''Values '''
                                '''(?, ?, ?, ?, ?, ?, ?, ?)''',
                                (camLoc, start, stop, objType, minW, maxW,
                                 minH, maxH))
                        newObjId = self._cur.execute(
                                '''SELECT last_insert_rowid()''').fetchone()[0]
                        # Update the motion table with the new object id.
                        self._cur.execute('''UPDATE motion SET objUid=? WHERE'''
                                          ''' objUid=? AND time>?''',
                                          (newObjId, objId, stopMs))
                        # Set the min and max times on the new/old object.
                        self._cur.execute('''UPDATE objects SET timeStart='''
                            '''(SELECT MIN(time) FROM motion WHERE objUid=?) '''
                            '''WHERE uid=?''', (newObjId, newObjId))

                        # TODO: Probably should recalculate minWidth, maxWidth,
                        #       minHeight, maxHeight
                    # Set the new stop time
                    self._cur.execute('''UPDATE objects SET timeStop='''
                        '''(SELECT MAX(time) FROM motion WHERE objUid=?) '''
                        '''WHERE uid=?''', (objId, objId))

                elif stop > stopMs:
                    # Adjust the startMs to be the new minimum
                    self._cur.execute('''UPDATE objects SET timeStart='''
                            '''(SELECT MIN(time) FROM motion WHERE objUid=?) '''
                            '''WHERE uid=?''', (objId, objId))
                else:
                    assert False, "Should have been orphaned... %s" % \
                                   str((start, startMs, stop, stopMs, objId))

            # Save right away--don't leave it up to the client...
            self.save()


    ###########################################################
    def tidyObjectTable(self):
        """Tidy up the object table, removing orphaned objects.

        This could get slow with large numbers of objects.  Ideally, don't run
        it too often...
        """
        # Find orphaned UIDs.
        #
        # This is equivalent to the following SQL:
        #   oldObjects = [row[0] for row in self._cur.execute(
        #       '''SELECT uid FROM objects WHERE uid NOT IN'''
        #       ''' (SELECT DISTINCT objUid FROM motion)'''
        #   ).fetchall()]
        # ...but the above SQL slows down quite a bit with large databases.
        #
        # Actually: just the SELECT DISTINCT bit above is pretty slow in a DB
        # with 333 unique objUids and 463545 rows.
        #
        # Our code is faster because (apparently) detecting the presence of
        # an object is faster than finding all unique object IDs...


        # Get the timeStart of the last added object.  We won't look for
        # orphans that are younger than 15 minutes before that time.
        # ...we do this because there may be a delay between adding an object
        # and adding the first bit of motion data about it.  This shouldn't
        # count as an orphaned object...
        startTime = time.time()
        lastTime = self._cur.execute(
            '''SELECT timeStart FROM objects ORDER BY uid DESC LIMIT 1'''
        ).fetchone()
        if not lastTime:
            return
        (lastTime,) = lastTime

        # NOTE: No clue how this can happen but it was in case 17707 and dying
        #       below with "unsupported operand type(s) for -: 'NoneType' and
        #       'int'". DB corruption of some sort? Regardless, if this happens
        #       we'll log the error and pick a "safe" time of 24 hours ago.
        if lastTime is None:
            self._logger.error("Last added time retrieved as None")
            lastTime = long(time.time()*1000) - (1000*60*60*24)

        minStartTime = lastTime - (1000 * 60 * 15)

        orphanedUids = []
        prevUid = 0
        while True:
            # Get the next N uids in the object list.  We work with smaller
            # groups to keep from ever having a super-long database access.
            idList = [row[0] for row in self._cur.execute(
                '''SELECT uid FROM objects WHERE uid > ? AND timeStart < ?'''
                ''' ORDER BY uid LIMIT 1000''', (prevUid, minStartTime)
            ).fetchall()]

            # If no more UIDs, we're done looking for orphans!
            if not idList:
                break

            # Do this relatively quick query on motion
            for uid in idList:
                isUidInMotion = self._cur.execute(
                    '''SELECT objUid FROM motion WHERE objUid=?'''
                    ''' LIMIT 1''', (uid,)).fetchone() is not None
                if not isUidInMotion:
                    orphanedUids.append(uid)
            prevUid = idList[-1]

        if orphanedUids:
            self._logger.warn("Detected " + str(len(orphanedUids)) + " orphaned objects:" + str(orphanedUids))
            self._deleteObjects(orphanedUids)

            # Save right away--don't leave it up to the client...
            self.save()
        self._logger.info("tidyObjectTable took %.02fsec" % (time.time()-startTime))


    ###########################################################
    def getObjectBboxesBetweenTimes(self, objIds, startTime=None,
                                        endTime=None):
        """Retrieve bounding boxes for an object between the given times

        If objIds contains more than one object ID, the results will be
        ordered by the object ID.  For a given object ID, results will be
        ordered by time.

        @param  objIds     A list or set of object IDs in the database.
        @param  startTime  The time to begin the search, None for the beginning
        @param  endTime    The time to stop the search, None for most recent
        @return bboxes     A list of (x1, y1, x2, y2, frame, time, objId) tuples
                           for each bbox within the given times.
        """
        # No need to hit the database if no objects...
        if not objIds:
            return []

        # Create all the different pieces of our search string, which will
        # be combined with AND.
        if len(objIds) == 1:
            filterPieces = ['objUid = %i' % list(objIds)[0]]
        else:
            filterPieces = ['objUid in %s' % str(tuple(objIds))]
        if startTime:
            filterPieces.append('time >= %i' % int(startTime))
        if endTime:
            filterPieces.append('time <= %i' % int(endTime))

        searchStr = ' AND '.join(filterPieces)

        bboxes = self._cur.execute('''SELECT x1, y1, x2, y2, frame, time, '''
                                   '''objUid FROM motion WHERE %s '''
                                   '''ORDER BY objUid ASC, time ASC'''
                                   % searchStr)

        return bboxes.fetchall()


    ###########################################################
    def getObjectRangesBetweenTimes(self, startTime=None, endTime=None):
        """Retrieve time ranges for an object between the given times.

        Takes the current filter string into account.

        @param  startTime    The time to begin the search, None for the beginning
        @param  endTime      The time to stop the search, None for most recent
        @return resultItems  An iterable of tuples, like this: [
                               (objId, ((firstMs, firstFrame),
                                        (lastMs, lastFrame)), cameraLocation)
                               ...
                             ]
        """
        assert self._connection is not None

        # Construct a search criteria based on the requested times
        # Swiped from getObjectsBetweenTimes.
        objSearchStr = ''
        if startTime:
            objSearchStr += 'timeStop >= %i' % int(startTime)
            if endTime:
                objSearchStr += ' AND '
        if endTime:
            objSearchStr += 'timeStart <= %i' % int(endTime)

        if objSearchStr and self._filterStr:
            objSearchStr = ' AND '.join([objSearchStr, self._filterStr])
        elif self._filterStr:
            objSearchStr = self._filterStr

        if objSearchStr:
            objSearchStr = "WHERE " + objSearchStr

        # Create all the different pieces of our motion search string, which
        # will be combined with AND.
        # TODO: Use SQL's "between"!
        filterPieces = []
        if startTime:
            filterPieces.append('m.time >= %i' % int(startTime))
        if endTime:
            filterPieces.append('m.time <= %i' % int(endTime))
        searchStr = ' AND '.join(filterPieces)
        if searchStr:
            searchStr = "WHERE " + searchStr

        # Run the super-crazy execute to get all this stuff.  It seems pretty
        # quick for the most part, considering everything it's doing...
        results = self._cur.execute('''
          SELECT x.camLoc, x.objUid, y.time, y.frame, z.time, z.frame FROM (
            SELECT m.camLoc,m.objUid,min(m.time) as minTime,max(m.time) as maxTime FROM (
              SELECT * FROM (
                SELECT camLoc,uid as objUid FROM objects %s
              ) NATURAL JOIN (
                motion
              )
            ) m
            %s GROUP BY m.objUid
          ) x
          JOIN motion y ON y.objUid = x.objUid AND y.time = x.minTime
          JOIN motion z ON z.objUid = x.objUid AND z.time = x.maxTime
        ''' % (objSearchStr, searchStr)).fetchall()

        # Return in the right format
        # TODO: Change to just return results, then change callers.  That
        # should be slightly faster...
        return ((c[1], ((c[2], c[3]), (c[4], c[5])), c[0])
                for c in results                    )


    ###########################################################
    def getObjectStartTime(self, objId):
        """Retrieve the time an object first appeared

        @param  objId      The id of the object in the database
        @return startTime  The time of the object's appearance
        """
        result = self._cur.execute(
            '''SELECT timeStart FROM objects WHERE uid=?''', (objId,))
        return result.fetchone()[0]


    ###########################################################
    def getFrameAtTime(self, objId, time):
        """Retrieve the frame for the given time

        For this function to return a value there must be an entry in the
        motion table within 10 ms of the requested time

        @param  objId     An object that was tracked at the given time
        @param  time      The requested time
        @return frame     The frame closest to the requested time, or -1
        @return distance  The abs ms distance from the requested time, or -1
        """
        variability = 10
        # Find the closest time in the database
        results = self._cur.execute('''SELECT time FROM motion WHERE '''
                                    '''objUID=? AND time>? AND time<?''',
                                    (objId, int(time)-variability,
                                     int(time)+variability))
        bestTime = -1
        for row in results:
            if bestTime == -1:
                bestTime = row[0]
            else:
                distance = abs(time-row[0])
                if distance < abs(time-bestTime):
                    bestTime = row[0]
                else:
                    break

        if bestTime == -1:
            return -1, -1

        # Find the frame number of the closest time
        result = self._cur.execute(
            '''SELECT frame FROM motion WHERE time=? AND objUid=?''',
            (int(bestTime), objId))

        row = result.fetchone()

        if row:
            return row[0], abs(time-bestTime)

        return -1, -1


    ###########################################################
    def getBboxAtFrame(self, objId, frame):
        """Retrieve a bbox for an object at a given frame

        @param  objId  The id of the object in the database
        @param  frame  The requested frame
        @return bbox   The bbox, or None if it could not be found
        """
        result = self._cur.execute(
            '''SELECT x1, y1, x2, y2 FROM motion WHERE objUID=? AND frame=?''',
            (objId, frame))
        return result.fetchone()


    ###########################################################
    def getObjectStartFrame(self, objId):
        """Retrieve the frame an object first appeared

        @param  objId       The id of the object in the database
        @return startFrame  The frame of the object's appearance
        """
        startTime = self.getObjectStartTime(objId)
        return self.getFrameAtTime(objId, startTime)


    ###########################################################
    def getFirstObjectBbox(self, objId, startTime=None):
        """Retrieve the first bbox on or after a given time

        @param  objId       The id of the object in the database
        @param  startTime  The minimum time to search from, or None for all
        @return bbox       The first bbox found within the time specification
        @return frame      The frame number corresponding to the bbox
        @return time       The time corresponding to bbox, -1 on error
        """
        if startTime:
            timeQuery = '''AND time>= %i''' % int(startTime)
        else:
            timeQuery = ''

        searchStr = (
            '''SELECT x1, y1, x2, y2, frame, time FROM motion '''
            '''WHERE objUid=? %s ORDER BY time LIMIT 1'''
        ) % timeQuery
        result = self._cur.execute(searchStr, (objId,)).fetchone()
        if not result:
            return (-1, -1, -1, -1), -1, -1

        x1, y1, x2, y2, frame, objTime = result
        return (x1, y1, x2, y2), frame, objTime


    ###########################################################
    def getObjectFinalTime(self, objId):
        """Retrieve the last frame and time an object was tracked

        @param  objId  The id of the object in the database
        @return frame  The final frame the object was tracked
        @return time   The final time the object was tracked
        """
        result = self._cur.execute(
            '''SELECT timeStop FROM objects WHERE uid=?''', (objId,))

        time = result.fetchone()[0]
        frame, _ = self.getFrameAtTime(objId, time)

        return frame, time


    ###########################################################
    def doCustomSearch(self, searchStr):
        """Perform a custom database query

        @param  searchStr   A search query to present to the database
        @return resultRows  The rows returned by the query
        """
        # This should be a select query...no adding or deleting and whatnot...
        assert searchStr.startswith('SELECT')

        resultRows = self._cur.execute(searchStr).fetchall()

        return resultRows


    ###########################################################
    def setMinSizeFilter(self, minHeight):
        """Restrict future searches to objects that were at least minSize big.

        @param  minHeight  The number of pixels to restrict future searches
                           to.  If None, disables the restriction.
        """
        if minHeight:
            # Check against maxHeight.  We want to know about objects that
            # were bigger than minHeight at some point in time...
            self._sizeFilter = 'maxHeight >= %d' % minHeight
        else:
            self._sizeFilter = ''

        self._setFilterStr()


    ###########################################################
    def setTargetFilter(self, targetAndActionList,
                        timeStart=None, timeStop=None):
        """Restrict future searches to objects of certain types

        NOTE: Currently unused

        @param  targetAndActionList  An iterable of object types and actions to
                                     include in searches, or the empty list to
                                     search on all.  Looks like: [
                                       ('person', 'walking'),
                                       ('person', 'running'),
                                       ('vehicle', 'any'),
                                       ...
                                     ]
        @param  timeStart   The time to start searching from, None for beginning
                            DOESN'T FULLY FILTER USING THIS; it's just for
                            optimizing our searches--you must filter yourself
                            later.
        @param  timeStop    The time to stop searching at, None for present
                            DOESN'T FULLY FILTER USING THIS; it's just for
                            optimizing our searches--you must filter yourself
                            later.
        """
        # Initially, start target box filter as nothing...
        self._targetRangeFilterDict = {}

        if not targetAndActionList:
            self._targetFilter = ''
        else:
            # We'll do a global OR over all of the filters...
            filters = []

            # Make a simple search for things that have the 'any' action...
            # SECURITY WARNING: The following is dangerous because of potential
            # SQL injection.  Can we avoid?
            anyTargets = set([target
                              for (target, action) in targetAndActionList
                              if action == 'any'])
            if anyTargets:
                filters.append(
                    '(type in ("' + '", "'.join(anyTargets) + '"))'
                )

            # If we need a specific action, we need to look up in the 'actions'
            # table to figure out what times are appropriate for each individual
            # object.  We'll build up a (potentially large) filter string to
            # find these cases...  First, find all the actionTargets; note that
            # if you are looking for ('person', 'walking') OR ('person', 'any')
            # that's the same as just looking for ('person', 'any'), so we filter
            # out any targets that are in the "anyTargets" set.
            actionTargets = [(target, action)
                             for (target, action) in targetAndActionList
                             if (action != 'any') and (target not in anyTargets)]
            if actionTargets:
                # Make a string to narrow down the entries we'll be getting back
                # from the 'actions' table so it's not _too_ huge (it still may
                # end up being pretty big).  If necessary, we can try to do other
                # types of filters too?
                timeStr = ''
                if timeStart is not None:
                    timeStr += (' timeStop>=%d AND ' % timeStart)
                if timeStop is not None:
                    timeStr += (' timeStart<=%d AND ' % timeStop)

                # Make the string to handle all of the target/actions.  We go
                # through a little extra work (using itertools) to still use the
                # '?' syntax here to avoid SQL injection.
                actionQuery = ' OR '.join(
                    ['(type=? AND action=?)'] * len(actionTargets)
                )

                # Get all the places between timeStart and timeStop where the
                # right types of objects are performing the right types of
                # actions.
                objRanges = self._cur.execute(
                    '''SELECT objUid, timeStart, timeStop FROM actions '''
                    '''WHERE ''' + timeStr + actionQuery,
                    list(itertools.chain(*actionTargets))
                ).fetchall()
                objUids = map(str, map(operator.itemgetter(0), objRanges))

                # We know that these objects were performing the right actions
                # at some point during the time period, so add them in.
                # Note: Objects may not have been performing the actions the
                #       whole time during the range.  We do add the limits to
                #       the _targetRangeFilterDict
                # TODO: OK that this could be large?
                filters.append('(uid in (%s))' % ', '.join(objUids))

                # Any objects that needed a certain action to be present no
                # longer match the whole time--they only match during certain
                # ranges.  Other functions will need to take that into account.
                #
                # NOTE: Any objects not referenced in this dict that still match
                # the target filter should be assumed to match for all times.
                #
                # Right now, only getObjectBboxesBetweenTimes() uses this.  ...but
                # maybe we should think more about whether getObjectStartTime and
                # getObjectFinalTime should too, for enter/exit trigger?
                for (objUid, timeStart, timeEnd) in objRanges:
                    thisFilter = '(time>=%d AND time <=%d)' % \
                                 (timeStart, timeEnd)

                    if objUid not in self._targetRangeFilterDict:
                        self._targetRangeFilterDict[objUid] = thisFilter
                    else:
                        self._targetRangeFilterDict[objUid] += \
                            (' OR ' + thisFilter)

            self._targetFilter = ' OR '.join(filters)

        self._setFilterStr()


    ###########################################################
    def setCameraFilter(self, cameraList):
        """Restrict future searches to objects seen at certain camera locations

        @param  cameraList  A list of camera locations to include in searches,
                            or an empty list to search on all
        """
        if not cameraList:
            self._cameraFilter = ''
        else:
            self._cameraFilter = 'camLoc in ("' + '", "'.join(cameraList) + '")'

        self._setFilterStr()


    ###########################################################
    def _setFilterStr(self):
        """Construct a search string from the given filters"""
        filters = []
        if self._cameraFilter:
            filters.append(self._cameraFilter)
        if self._targetFilter:
            filters.append(self._targetFilter)
        if self._sizeFilter:
            filters.append(self._sizeFilter)

        self._filterStr = " AND ".join(filters)


    ###########################################################
    def getCameraLocations(self, forceUseOfObjdb=False):
        """Retrieve a list of all camera locations in the database

        NOTE: In most cases you should try to use getCameraLocations from
              ClipManager, as it will be faster.  This will attempt to do
              that if possible, unless you force it not to.

        @param  forceUseOfObjdb  Prevent the optimization of using the clipdb.
        @return locNames         A list of all camera locations in the database.
        """
        if self._clipManager and not forceUseOfObjdb:
            return self._clipManager.getCameraLocations()

        results = self._cur.execute('''SELECT DISTINCT camLoc FROM objects''')
        return [result[0] for result in results]


    ###########################################################
    def getObjectsInfoForRange(self, minId, maxId):
        """ Return information for objects within ID range
        """
        assert self._connection is not None

        # Get any associated object ids
        objects = self._cur.execute('''SELECT uid,camLoc,type FROM objects WHERE uid>=? AND uid<=?''',
                                (minId,maxId)).fetchall()
        objMap = {}
        for obj in objects:
            objMap[obj[0]] = obj[2]
        return objMap

    ###########################################################
    def removeCameraLocation(self, location):
        """Remove all data associated with a given camera location.

        @param  location  The name of the location to remove.
        """
        assert self._connection is not None

        # Get any associated object ids
        ids = self._cur.execute('''SELECT uid FROM objects WHERE camLoc=?''',
                                (location,)).fetchall()

        idList = [str(row[0]) for row in ids]
        if idList:
            idListStr = ','.join(idList)
            self._cur.execute('''DELETE FROM objects WHERE uid IN (%s)''' %
                              idListStr)
            self._cur.execute('''DELETE FROM motion WHERE objUid IN (%s)''' %
                              idListStr)
            self._cur.execute('''DELETE FROM actions WHERE objUid IN (%s)''' %
                              idListStr)
            self.save()


    ###########################################################
    def getCameraLocation(self, objId):
        """Retrieve the camera location for a given object

        @param  objId     The object to search for
        @return location  The name of the camera location for the object
        """
        results = self._cur.execute('''SELECT camLoc FROM objects WHERE uid=?''', (objId,))
        return results.fetchone()[0]


    ###########################################################
    def getSearchResults(self, query, timeStart=None, timeStop=None, procSizesMsRange=None):
        """Compute file and timepoints of interest for the given query

        @param  query             The trigger on which to perform the search
        @param  timeStart         The time to start searching from, None for all time
        @param  timeStop          The time to stop searching at, None for present
        @param  procSizesMsRange  A list of sizes the camera was processed at for
                                  certain ranges of time. Contains a list of 4-tuples
                                  of (procWidth, procHeight, firstMs, lastMs).
                                  Note: if the list contains only one 4-tuple, then
                                  procWidth and procHeight is unique, and firstMs and
                                  lastMs should be ignored; they may hold None values.
                                  If the list contains more than one 4-tuple, then
                                  procWidth and procHeight are not unique, and you must
                                  use the firstMs and lastMs to determine which
                                  procSize was used for a specified period of time.
        @return resultDict        A dict of [objId] = (triggerMsList)
        """
        # Perform the search
        results = query.search(timeStart, timeStop, 'single', procSizesMsRange)

        # key = objID, val = list of times triggered
        resultDict = {}
        for objId, frame, ms in results:
            if objId not in resultDict:
                resultDict[objId] = []
            resultDict[objId].append((ms, frame))

        return resultDict


    ###########################################################
    def getSearchResultsRanges(self, query, timeStart=None, timeStop=None, procSizesMsRange=None):
        """Like getSearchResults(), but returns a firstMs and lastMs per object.

        @param  query             The trigger on which to perform the search
        @param  timeStart         The time to start searching from, None for all time
        @param  timeStop          The time to stop searching at, None for present
        @param  procSizesMsRange  A list of sizes the camera was processed at for
                                  certain ranges of time. Contains a list of 4-tuples
                                  of (procWidth, procHeight, firstMs, lastMs).
                                  Note: if the list contains only one 4-tuple, then
                                  procWidth and procHeight is unique, and firstMs and
                                  lastMs should be ignored; they may hold None values.
                                  If the list contains more than one 4-tuple, then
                                  procWidth and procHeight are not unique, and you must
                                  use the firstMs and lastMs to determine which
                                  procSize was used for a specified period of time.
        @return resultItems       An iterable of tuples, like this: [
                                    (objId, ((firstMs, firstFrame),
                                             (lastMs, lastFrame)), camLoc)
                                    ...
                                  ]
        """
        # Perform the search
        return query.searchForRanges(timeStart, timeStop, procSizesMsRange)


    # The following is commented out since we don't use fileName
    # field in objdb2 any more.
    # Use the clipDb to re-implement this if we need it
    ###########################################################
    #def isFileInDb(self, fileName):
    #    """Check if data for a given file is in the database
    #
    #    @param  fileName  The file to look for
    #    @return exists    True if the file exists in the database
    #    """
    #    results = self._cur.execute(
    #        '''SELECT * FROM objects WHERE fileName=?''', (fileName,))
    #
    #    if results.fetchone():
    #        return True
    #    return False


    ###########################################################
    def updateLocationName(self, oldName, newName, changeMs):
        """Change the name of a camera location.

        @param  oldName   The name of the camera location to change.
        @param  newName   The new name for the camera location.
        @param  changeMs  The absolute ms at which the change took place.
        """
        # We need to split objects that occur across the time change.
        objs = self._cur.execute(
            '''SELECT uid, camLoc, timeStop, type, '''
            '''minWidth, maxWidth, minHeight, maxHeight '''
            '''FROM objects WHERE camLoc=? AND timeStop>=? AND timeStart<?''',
            (oldName, changeMs, changeMs)
        ).fetchall()
        for oldId, cam, stop, objType, minW, maxW, minH, maxH in objs:
            # Add a new object starting at changeMs.
            self._cur.execute(
                '''INSERT INTO objects (camLoc, timeStart, timeStop, type, '''
                '''minWidth, maxWidth, minHeight, maxHeight) Values '''
                '''(?, ?, ?, ?, ?, ?, ?, ?)''', (cam, changeMs,
                        stop, objType, minW, maxW, minH, maxH))
            newId = self._cur.execute('''SELECT last_insert_rowid()''')
            newId = newId.fetchone()[0]

            # Update the related entries in the motion table.
            self._cur.execute('''UPDATE motion SET objUid=? WHERE objUid=? '''
                              '''AND time>=?''', (newId, oldId, changeMs))

            # Update the stop time of the old object.
            self._cur.execute('''UPDATE objects SET timeStop=? WHERE uid=?''',
                              (changeMs-1, oldId))

        # Update all objects that start after the time change.
        self._cur.execute('''UPDATE objects SET camLoc=? WHERE camLoc=? AND '''
                          '''timeStart>=?''', (newName, oldName, changeMs))


    ###########################################################
    def getMostRecentObjectTime(self, cameraLocation):
        """Find the most recent ms an object was seen at a given location.

        @param  cameraLocation  The camera to search.
        @return recentMs        The most recent ms seen or -1.
        """
        recentMs = self._cur.execute('''SELECT MAX(timeStop) from objects '''
                                     '''WHERE camLoc=?''', (cameraLocation,)
                                     ).fetchone()
        if not recentMs or recentMs[0] is None:
            return -1
        return recentMs[0]


    ###########################################################
    def hasAudio(self):
        """Does the currently selected clip contain audio?

        @return  hasAudio   True if the current clip has audio, and False
                            otherwise.
        """
        if self._clipReader:

            return self._clipReader.hasAudio()

        return False


    ###########################################################
    def _deleteObjects(self, objUidList):
        """Remove entries from the objects table.

        NOTE: This will not remove any objects that have the highest
              id in the table. If we do this it messes up our algorithm for
              assigning new ids.  Assuming all associated motion data was
              removed this will be taken care of eventually by the disk cleaner.

        @param  objUidList  A list of object uid strings to remove.
        """
        now = time.time()*1000

        # We need to make a new copy of so we don't change it under our caller.
        objUidList = objUidList[:] #PYCHECKER OK: This does have an effect, it makes a copy

        maxId = self._cur.execute('''SELECT MAX(uid) FROM objects''').fetchone()
        if maxId and maxId[0] in objUidList:
            objUidList.remove(maxId[0])

        stopTimeList = self._cur.execute('''SELECT uid, timeStop FROM objects'''
                                         ''' WHERE uid IN (%s)''' % ','.join(
                                         str(objId) for objId in objUidList)
                                         ).fetchall()
        for uid, timeStop in stopTimeList:
            # Select timeStop
            if timeStop > (now-_kObjectSaveBuffer):
                objUidList.remove(uid)

        self._cur.execute('''DELETE FROM objects WHERE uid IN (%s)''' %
                          ','.join(str(objId) for objId in objUidList)) #PYCHECKER OK: This isn't redefining the genexpr from above since we have removed objects


###############################################################################
#                File manipulation functions below this point                 #
###############################################################################


    ###########################################################
    def setupMarkedVideo(self, cameraLoc, firstMs, lastMs, playMs, objList=[],
                        displaySize=(320, 240), enableAudio=False, asyncRead=True):
        """Open a video with optional object borders

        @param  cameraLoc    The name of the camera location to view
        @param  firstMs      The absolute ms of the first frame to play
        @param  lastMs       The absolute ms of the last frame to play
        @param  playMs       The absolute ms of the start play time
        @param  objList      A list of object id's to draw bounding boxes for
        @param  displaySize  A (w,h) tuple of the desired frame size
        @return realFirstMs  The first requestable ms if firstMs didn't exist,
                             -1 on error
        @return realLastMs   The last requestable ms if lastMs didn't exist,
                             -1 on error
        """
        if not self._clipManager:
            return

        self._curVidCameraLoc = cameraLoc
        self._objList = objList
        self._displaySize = displaySize
        self._curVidPath = None
        self._curFrameMs = -1
        self._audioEnabled = enableAudio
        self._asyncReadEnabled = asyncRead

        # Find files we can access, starting from the play point and going
        # ahead and back.
        self._firstFile = self._clipManager.getFileAt(cameraLoc, playMs,
                                                      lastMs-playMs, 'after')
        self._lastFile  = self._firstFile
        if not self._firstFile:
            # If we couldn't find a file in the range of the play start to the
            # end, something is terribly wrong.
            return -1, -1

        firstFileStart, lastFileStop = \
                    self._clipManager.getFileTimeInformation(self._firstFile)

        # Walk forward until we reach our stop time or we break the file chain.
        while lastFileStop < lastMs:
            nextFile = self._clipManager.getNextFile(self._lastFile)
            if not nextFile:
                break

            tempStart, tempStop = self._clipManager.getFileTimeInformation(nextFile)
            if tempStart > lastMs:
                # clip's last frame's timestamp falls between the previous and current file ... trim to the last frame of the previous
                break
            lastFileStop = tempStop
            self._lastFile = nextFile

        # Walk back until we reach our start time or we break the file chain.
        while firstFileStart > firstMs:
            prevFile = self._clipManager.getPrevFile(self._firstFile)
            if not prevFile:
                break

            tempStart, tempStop = self._clipManager.getFileTimeInformation(prevFile)
            if tempStop < firstMs:
                break
            firstFileStart = tempStart
            self._firstFile = prevFile

        # A cache of bounding boxes for objects active in the video
        self._bboxCache = {}

        # Ensure we aren't requesting times that aren't recorded
        self._firstMs = max(firstFileStart, firstMs)
        self._lastMs = min(lastFileStop, lastMs)

        return self._firstMs, self._lastMs

    ###########################################################
    def openMarkedVideo(self, cameraLoc, firstMs, lastMs, playMs, objList=[],
                        displaySize=(320, 240), enableAudio=False, asyncRead=True):
        self._firstMs, self._lastMs = \
            self.setupMarkedVideo(cameraLoc, firstMs, lastMs, playMs, objList, displaySize, enableAudio, asyncRead)
        if self._firstMs == -1:
            return -1, -1
        # Open the first video file
        if not self._openMarkedFile(self._firstFile, self._objList):
            return -1, -1

        # Sanitize firstMs and lastMs even further...
        self.getFrameAt(self._lastMs)
        self._lastMs = self._curFrameMs + self._fileStart
        self.getFrameAt(self._firstMs)
        self._firstMs = self._curFrameMs + self._fileStart
        self._curFrameMs = -1

        return self._firstMs, self._lastMs


    ###########################################################
    def updateVideoSize(self, resolution):
        """Update the size of retrieved frames in the currently opened video.

        @param  resolution  The desired resolution to begin receiving frames in.
        """
        if self._clipReader:
            self._clipReader.setOutputSize(resolution)
            self._displaySize = resolution


    ###########################################################
    def forceCloseVideo(self):
        """Close any open video files.

        NOTE: This can leave things in an odd state.  Don't call functions
              like getNextFrame before reopening the video.
        """
        if self._clipReader:
            self._clipReader.close()


    ###########################################################
    def getVideoState(self):
        """Return an object describing the current video state.

        @return videoState  An opaque object describing the current state.
        """
        return (self._curVidPath, self._curFrameMs+self._fileStart)


    ###########################################################
    def restoreVideoState(self, videoState):
        """Restore the video state.

        NOTE: If any videos were opened between a call to getVideoState
              and a call to this function, it will not work.

        @param videoState  An object describing the state to restore.
        """
        self._curVidPath = None
        if self._openMarkedFile(videoState[0], self._objList):
            self.getFrameAt(videoState[1])


    ###########################################################
    def saveCurrentClip(self, filePath, desiredFirstMs, desiredLastMs,
            configDir, extras={}):
        """Save the clip definied by the last call to openMarkedVideo.

        @param  filePath       The path where the clip should be stored.
        @param  desiredFirstMs The absolute ms where we'd like to start the
                               video.  May be before the start of the current
                               clip.  If so, we'll try to rewind a bit as long
                               as there is continuous video.
        @param  desiredLastMs  The absolute ms where we'd like to stop; if
                               None, assumes that we'd like to stop at the end
                               of the clip.
        @param  configDir      Directory to search for config files.
        @param  extras         Dict of extras, see _kSaveClipDefaults
        @return success        True if the clip was saved successfully.
        """
        from videoLib2.python.ClipUtils import remuxClip  # Lazy--loaded on first need
        from videoLib2.python.ClipUtils import getRealClipSize # Lazy--loaded on first need

        if not self._firstFile or not self._lastFile:
            return False

        drawBoxes = extras.get("drawBoxes", _kSaveClipDefaults["drawBoxes"])
        overlayTimestamp = extras.get("enableTimestamps", _kSaveClipDefaults["enableTimestamps"])
        firstFileStart, _ = self._clipManager.getFileTimeInformation(
                                                            self._firstFile)

        if desiredLastMs is None:
            desiredLastMs = self._lastMs

        if desiredFirstMs < firstFileStart:
            # Move back one file at a time, breaking out of the loop if we run
            # out of continuous clips (in which case we'll just start from
            # the earliest)...
            curFile = self._firstFile
            while True:
                # Move to previous if it's there...
                prevFile = self._clipManager.getPrevFile(curFile)
                if not prevFile:
                    break
                curFile = prevFile

                # If we've found our answer, break out too
                start, stop = self._clipManager.getFileTimeInformation(curFile)
                if desiredFirstMs >= start:
                    assert desiredFirstMs <= stop
                    break
        else:
            assert desiredFirstMs <= self._lastMs
            curFile = self._clipManager.getFileAt(self._curVidCameraLoc,
                                                  desiredFirstMs,
                                                  self._lastMs - desiredFirstMs,
                                                  'after')
            if not curFile:
                assert False, "Couldn't find file for start time."
                return False

        boxOverlay = []
        if drawBoxes:
            boxOverlay = self._getBoundingBoxes(curFile, self._objList, desiredFirstMs-10, desiredLastMs+10)
        extras['boxList'] = boxOverlay
        extras['enableTimestamps'] = overlayTimestamp


        # Build the list of filenames and gaps from the first
        # file to the last.
        start, stop = self._clipManager.getFileTimeInformation(curFile)
        fileList = [(os.path.join(self._vidStoragePath, curFile), start)]
        while stop < desiredLastMs:
            curFile = self._clipManager.getNextFile(curFile)
            if not curFile:
                break
            start, stop = self._clipManager.getFileTimeInformation(curFile)
            fileList.append((os.path.join(self._vidStoragePath, curFile),
                             start))

        return remuxClip(fileList, filePath, desiredFirstMs, desiredLastMs,
                           configDir, extras, self._logger.getCLogFn())>=0

    ###########################################################
    def getBoundingBoxesBetweenTimes(self, camLoc, firstMs, lastMs, procSize, format="videoLib"):
        ''' Get all bounding boxes between times.
        '''
        backupFilter = self._cameraFilter
        try:
            self.setCameraFilter([camLoc])
            objs = self.getObjectsBetweenTimes(firstMs, lastMs, True)
            if format == "json":
                filename = self._clipManager.getFileAt(camLoc, firstMs, lastMs-firstMs, 'after' )
                result = self._getBoundingBoxesJSON(filename, objs, firstMs, lastMs)
            else:
                result = self._getBoundingBoxes(None, objs, firstMs, lastMs, procSize)
            return result
        finally:
            self.setCameraFilter(backupFilter)


    ###########################################################
    def _getBoundingBoxes(self, filename, objList, firstMs, lastMs,
                        procSize=None):
        procW, procH = self._figureOutProcSize2(filename) if procSize is None else procSize
        if procW == 0 or procH == 0:
            self._logger.warning( "Couldn't get bounding boxes: procW=" + str(procW) + " procH=" + str(procH) )
            return []


        boxOverlay = []
        for obj in objList:
            if isinstance(obj, tuple):
                id = obj[0]
                labelColor = self._getLabelColorForType(obj[3])
            else:
                id = obj
                labelColor = self._getLabelColor(obj)

            bboxes = self.getObjectBboxesBetweenTimes([id], firstMs, lastMs)
            if not bboxes:
                continue

            for x1, y1, x2, y2, _, frameTime, uid in bboxes:
                boxOverlay.append([frameTime, "drawbox=%d:%d:%d:%d:%d:%d:%d:%s:t=0" %
                        (x1, y1, x2-x1, y2-y1, procW, procH, uid, labelColor)])
        boxOverlay.sort()
        return boxOverlay

    ###########################################################
    def _getBoundingBoxesJSON(self, filename, objList, firstMs, lastMs):
        """ Return list of objects between times as json of shape
            { "uid": uid,label": label,
              "boxes": [ { "time":time, "x":x, "y":y, "w":w, "h":h },
                         ...
                       ]
                      },
              ...
            }
        """
        inW, inH = self._getClipSize(filename)
        procW, procH = self._figureOutProcSize(filename, (inW, inH))
        if procW == 0 or procH == 0:
            self._logger.warning( "Couldn't get bounding boxes: procW=" + str(procW) + " procH=" + str(procH) )
            return []

        objects = []
        for obj in objList:
            object = {}
            id = obj[0]
            object["id"] = id
            object["label"] = obj[3]
            boxList = []

            bboxes = self.getObjectBboxesBetweenTimes([id], firstMs, lastMs)

            if bboxes:
                wRatio = inW/float(procW)
                hRatio = inH/float(procH)
                for x1, y1, x2, y2, _, frameTime, uid in bboxes:
                    box = {}
                    box["time"] = frameTime
                    box["x"] = int(x1*wRatio)
                    box["y"] = int(y1*hRatio)
                    box["h"] = int((x2-x1)*wRatio)
                    box["w"] = int((y2-y1)*hRatio)
                    boxList.append(box)
                object["boxes"] = boxList
            objects.append( object )
        return objects

    ###########################################################
    def _getRegionZones(self, filename):
        procW, procH = self._figureOutProcSize2(filename)
        if procW == 0 or procH == 0:
            print "Couldn't get region boxes: procW=" + str(procW) + " procH=" + str(procH)
            return []

        zonesOverlay = []
        for triggerObj in self._videoDebugLines:

            points = triggerObj.getPoints((procW, procH))

            numPts = len(points)
            for i in range(0, numPts):
                (x1, y1), (x2, y2) = points[i], points[(i+1)%numPts]
                # format the lines as we would boxes ... they are still defined by two points
                zonesOverlay.append([-1, "drawbox=%d:%d:%d:%d:%d:%d:%d:%s:t=0" %
                        (x1, y1, x2, y2, procW, procH, 0, "red")])
        self._logger.debug("Overlay zones: " + str(zonesOverlay))
        return zonesOverlay


    ###########################################################
    def _openMarkedFile(self, filePath, objList):
        """Open a file with optional object borders

        @param  filePath  The path of the file to open.
        @return success   True if the open was successful.
        """
        if not filePath:
            return False
        # Open this file if it isn't already open
        if filePath != self._curVidPath or self._curFileAudioEnabled != self._audioEnabled:
            fullPath = os.path.join(self._vidStoragePath, filePath)
            if not os.path.exists(fullPath):
                self._logger.error("Failed to open %s" % (ensureUtf8(fullPath)))
                return False

            self._curFrameMs = -1
            self._curVidPath = filePath
            self._curFileAudioEnabled = self._audioEnabled
            self._clipReader = ClipReader(self._logger.getCLogFn())

            self._fileStart, self._fileStop = \
                self._clipManager.getFileTimeInformation(filePath)

            outW = self._displaySize[ 0 ]
            outH = self._displaySize[ 1 ]

            extras = {}
            if self._markupModel.getShowBoxesAroundObjects():
                boxOverlay = self._getBoundingBoxes(self._curVidPath, objList, self._fileStart-10, self._fileStop+10)
                extras ['boxList'] = boxOverlay
            if self._markupModel.getShowRegionZones():
                zonesOverlay = self._getRegionZones(self._curVidPath)
                if zonesOverlay is not None:
                    extras ['zonesList'] = zonesOverlay

            if self._markupModel.getPlayAudio():
                extras ['enableAudio'] = self._audioEnabled
                extras ['audioMute'] = self._muted
            extras ['asyncRead'] = 1 if self._asyncReadEnabled else 0
            extras ['enableTimestamps'] = self._markupModel.getOverlayTimestamp()
            extras ['useUSDate'] = self._markupModel.getUSDate()
            extras ['use12HrTime'] = self._markupModel.get12HrTime()
            extras ['enableDebug'] = 1 if self._markupModel.getShowObjIds() else 0
            extras ['keyframeOnly'] = 1 if self._markupModel.getKeyframeOnlyPlayback() else 0

            openedOk = self._clipReader.open( fullPath, outW, outH, self._fileStart, extras )
            if openedOk and self._audioEnabled:
                self._clipReader.setMute( self._muted )

            assert openedOk, "Can't open: '%s'" % (filePath)
            return openedOk

    ###########################################################
    def setMute(self, mute):
        if mute == self._muted:
            return
        self._muted = mute
        if not self._audioEnabled:
            return
        if self._clipReader is not None:
            self._clipReader.setMute( self._muted )


    ###########################################################
    def setVideoDebugLines(self, triggerLines):
        """Set lines to be overlayed on the video when marking is enabled.

        @param  triggerLines  A list of TriggerLineSegment or TriggerRegion
                              objects, which can be used to retrieve a list of
                              (x1,y1,x2,y2) tuples defining lines to display on
                              the screen by calling their getPoints(coordSpace)
                              instance method.
        """
        self._videoDebugLines = triggerLines


    ###########################################################
    def getFrameAt(self, frameTime):
        """Retrieve the frame corresponding to the given time

        @param  frameTime  The absolute time of the frame to retrieve
        @return img        A PIL/raw image of the requested frame
        """
        afterCurFile = frameTime > self._fileStop
        beforeCurFile = frameTime < self._fileStart

        if afterCurFile or beforeCurFile:
            direction = 'after' if afterCurFile else 'before'
            newFile = self._clipManager.getFileAt(self._curVidCameraLoc,
                                                  frameTime,
                                                  3000,
                                                  direction)
            if not newFile or not self._openMarkedFile(newFile, self._objList):
                return None

            # Handlle cases where the desired frame time falls between physical files
            # When that happens, take the next closest frame
            if afterCurFile and self._fileStart > frameTime:
                frameTime = self._fileStart
            elif beforeCurFile and frameTime > self._fileStop:
                frameTime = self._fileStop

        frame = self._clipReader.seek(frameTime-self._fileStart)

        return self._setCurrentFrame(frame)


    ###########################################################
    def getNextFrame(self):
        """Retrieve the next frame.

        @return frame  A PIL image of the next frame, or None if no next
        """
        # If we're already past the end of the clip return None.
        if self._curFrameMs+self._fileStart > self._lastMs:
            return None

        nextClipReaderFrame = self._clipReader.getNextFrame()

        nextFrame = self._setCurrentFrame(nextClipReaderFrame)

        if self._curFrameMs+self._fileStart > self._lastMs:
            # If we're past the end now also return None
            return None

        if not nextClipReaderFrame:
            # If next frame was None try to open the next file.
            nextFile = self._clipManager.getNextFile(self._curVidPath)
            if not nextFile or not self._openMarkedFile(nextFile, self._objList):
                return None
            return self.getNextFrame()

        # Return the marked-up frame
        return nextFrame


    ###########################################################
    def getPrevFrame(self):
        """Retrieve the previous frame from the currently opened video

        @return frame  A PIL image of the requested frame, or None if no prev
        """
        if self._curFrameMs != -1 and \
           (self._curFrameMs + self._fileStart < self._firstMs):
            # If we're already before the beginning return None.
            return None

        prevClipReaderFrame = self._clipReader.getPrevFrame()

        prevFrame = self._setCurrentFrame(prevClipReaderFrame)
        if self._curFrameMs + self._fileStart < self._firstMs:
            # If we're before the beginning now, also return None.
            return None

        if not prevFrame:
            # if prevFrame was None try to open the previous file.
            prevFile = self._clipManager.getPrevFile(self._curVidPath)
            if not prevFile or not self._openMarkedFile(prevFile, self._objList):
                return None
            return self.getFrameAt(self._fileStop)

        return prevFrame


    ###########################################################
    def getFirstFrame(self):
        """Retrieve the first frame from the currently opened video

        @return frame  A PIL image of the requested frame
        """
        return self.getFrameAt(self._firstMs)


    ###########################################################
    def getLastFrame(self):
        """Retrieve the last frame from the currently opened video

        @return frame  A PIL image of the requested frame
        """
        return self.getFrameAt(self._lastMs)


    ###########################################################
    def _minimalFrameData( self, frame ):
        if not frame:
            self._curFrameMs = -1
        else:
            self._curFrameMs = frame.ms


    ###########################################################
    def _setCurrentFrame(self, frame):
        """Mark up frame with object and debug information.

        @param  frame        The frame to mark up.
        @param  procSize     The size of the image that processing happened on.
        @return markedFrame  A PIL image of the requested frame, or None.
        """
        if not frame:
            self._curFrameMs = -1
            return None

        self._curFrameMs = frame.ms
        return frame


    ###########################################################
    def getNextFrameOffset(self):
        """Return the offset of the next frame in the video.

        This is relative to the realFirstMs returned by openMarkedVideo().

        @return offset  The offset of the next frame, or -1 if no next frame
        """
        ms = self._clipReader.getNextFrameOffset()
        if -1 == ms:
            nextStart = self._clipManager.getNextFileStartTime(self._curVidPath)
            if nextStart == -1:
                return -1
            return nextStart-self._firstMs

        nextOffset = ms+self._fileStart-self._firstMs

        # If we're past the end of this clip, return -1...
        duration = (self._lastMs - self._firstMs + 1)
        if nextOffset >= duration:
            return -1

        return nextOffset


    ###########################################################
    def getCurFrameOffset(self):
        """Return the offset of the current video frame

        @return offset  The offset of the current frame
        """
        if self._curFrameMs == -1:
            return -1
        return self._curFrameMs+self._fileStart-self._firstMs


    ###########################################################
    def getFileStartMs(self):
        """Return the current start of the current file.

        @return fileStartMs  The start of the current file, in absolute ms.
        """
        return self._fileStart


    ###########################################################
    def getCurFilename(self):
        """Return the name of the currently open file

        @return filename  The name of the currently open file
        """
        return os.path.split(self._curVidPath)[1]


    ###########################################################
    def getSingleFrame(self, camLoc, ms=0, size=(0,240), useTolerance=True,
                       wantProcSize=False, markupObjList=None):
        """Retrieve a single frame from a video file; NOT marked up.

        @param  camLoc        The camera location to obtain a frame from
        @param  ms            The absolute ms of the frame to retreive.
        @param  useTolerance  If False, we will not allow the clip manager
                              to use a tolerance value when getting the file.
        @param  wantProcSize  If True, we'll return a 3rd value: procSize.
        @return img           A PIL image of the requested frame; not a copy,
                              so please don't draw on this.
        @return ms            The absolute ms from this frame.
        @return [procSize]    Only returned if wantProcSize is True; is always
                              None if img is None.
        """
        if wantProcSize:
            defaultReturn = (None, ms, None)
        else:
            defaultReturn = (None, ms)

        if useTolerance:
            fileName = self._clipManager.getFileAt(camLoc, ms)
        else:
            fileName = self._clipManager.getFileAt(camLoc, ms, 0)

        if not fileName:
            return defaultReturn

        filePath = os.path.join(self._vidStoragePath, fileName)
        if not filePath or not os.path.exists(filePath):
            return defaultReturn

        # Requested timestamp may occur between the last frame of the previous file
        # and the first frame of this file ... this makes sure we get a frame in the area.
        fileStart, fileStop = self._clipManager.getFileTimeInformation(fileName)
        ms = min(fileStop, max(fileStart, ms))

        extras=None
        if self._markupModel.getShowBoxesAroundObjects():
            if markupObjList is not None:
                extras={}
                boxOverlay = self._getBoundingBoxes(fileName, markupObjList, ms-100, ms+100)
                extras['boxList'] = boxOverlay


        clipReader = ClipReader(self._logger.getCLogFn())
        fileStartTime, fileStopTime = \
            self._clipManager.getFileTimeInformation(fileName)
        if int(os.getenv("SV_CLIP_DEBUG", "0")) > 0:
            self._logger.info("Getting a frame from %s starting at %d at ms %d (extras=%s)" % (filePath, fileStartTime, ms, str(extras)) )
        openedOk = clipReader.open(filePath, size[0], size[1], fileStartTime, extras)
        assert openedOk, "Can't open: '%s'" % (filePath)
        if not openedOk:
            return defaultReturn
        frame = clipReader.seek(ms-fileStartTime)
        if not frame:
            return defaultReturn

        if wantProcSize:
            procSize = self._figureOutProcSize(fileName,
                                               clipReader.getInputSize())
            return frame.asPil(), \
                   min((frame.ms + fileStartTime), fileStopTime), \
                   procSize
        else:
            return frame.asPil(), \
                   min((frame.ms + fileStartTime), fileStopTime)

    ###########################################################
    def makeThumbnail(self, camLoc, ms, outputFile, maxSize=(0, 0)):
        """Retrieve a thumbnail for the camera at the given time.

        @param  camLoc      The camera location to use.
        @param  ms          The absolute ms of the thumbnail frame.
        @param  outputFile  The file to save the thumbnail to.
        @param  maxSize     The maximum size of the create image.
        @return True if thumbnail was created, False on error.
        """
        # TODO: may need to check the requested size, but for now
        #       pre-created thumbs should work for all existing clients
        thumbFile, _ = self.getThumbFileFromCache(camLoc, ms)
        if thumbFile is not None:
            shutil.copy(thumbFile, outputFile)
            return True

        # Find the file path.
        fileName = self._clipManager.getFileAt(camLoc, ms)
        if not fileName:
            # smart logging: since this happens quite often only warn if we know
            # if that file should already exist and isn't being moved from
            # temp ...
            if time.time() > ms/1000 + 20*60:
                self._logger.warning("file for %d@%s not found" % (ms, camLoc))
            return False

        fullPath = os.path.join(self._vidStoragePath, fileName)
        if not fullPath or not os.path.exists(fullPath):
            self._logger.error("no output path for %d@%s" % (ms, camLoc))
            return False

        # Encoder is *terrible* at tiny resolution, and we need to force a min
        # anyway to guard against nonsensical values like 5, 5
        thumbWidth, thumbHeight = maxSize
        if thumbWidth  > 0: thumbWidth  = max(thumbWidth, 160)
        if thumbHeight > 0: thumbHeight = max(thumbHeight, 120)

        # We need to fetch an image from the file to retrieve the actual ms
        # and file resolution.
        clipReader = ClipReader(self._logger.getCLogFn())
        openedOk = clipReader.open(fullPath, thumbWidth, thumbHeight, 0, None)
        assert openedOk, "Can't open: '%s'" % (fullPath)
        if not openedOk:
            self._logger.error("cannot open clip for %d@%s" % (ms, camLoc))
            return False

        fileStartTime, _ = self._clipManager.getFileTimeInformation(fileName)

        frame = clipReader.seek(ms-fileStartTime)
        if not frame:
            self._logger.warning("no frame available for %d@%s" % (ms, camLoc))
            return False

        frame.asPil().save(outputFile, "JPEG")
        return True

    ###########################################################
    def _getClipSize(self, filename):
        if self._clipReader is not None:
            clipSize = self._clipReader.getInputSize()
        else:
            clipReader = ClipReader(self._logger.getCLogFn())
            fullPath = os.path.join(self._vidStoragePath, filename)
            if not os.path.exists(fullPath) or \
               not clipReader.open( fullPath, 0, 0, 0, {} ):
                clipSize = (0,0)
            else:
                clipSize = clipReader.getInputSize()
            clipReader = None
        return clipSize

    ###########################################################
    def _figureOutProcSize2(self, filename):
        """ Same as _figureOutProcSize, except attempting to determine
            clipSize from currently active clipReader
        """
        return self._figureOutProcSize(filename, self._getClipSize(filename))

    ###########################################################
    def _figureOutProcSize(self, fileName, inputSize):
        """Figure out what size the given fileName was processed at.

        Normally the clip manager holds this, but for old data it might
        not have it.  In that case, we guess using the input file size.

        @param  fileName   The filename of the clip.
        @param  inputSize  The size of the input video.
        @return procSize   The size the video was (probably) processed at.
        """
        procSize = self._clipManager.getProcSize(fileName)
        if procSize == (0, 0):
            # If we're here, we're looking at video recorded before 1.0
            # release.  In that video, processing and recording always
            # happened at the same size, so just use the input size.
            procWidth, procHeight = inputSize

            # OK, I lied.  The above statement is almost true, except if
            # procWidth / procHeight is big.  In that case, it means that we're
            # looking at video recorded in high resolution of one of the lucky
            # beta testers of 1.0.  Due to the way the code worked, if one of
            # the saved file dimensions is > (320, 240), it means we tried to
            # record at 640x480.  Processing size should be roughly half that,
            # and always divisible by 8.  This might be off by a pixel, but
            # it's as close as we'll get (sorry beta testers!)
            #
            # NOTE: Internal users (not using official build 5543) might have
            # video recorded with slightly different math.  Tough luck.
            #
            # I think the only case that the math really matters is with non-
            # standard camera resolutions.  If the camera gave us 640x480,
            # everyone should be good.
            if (procWidth > 320) or (procHeight > 240):
                procHeight = int(procHeight / 2) & (~7)
                procWidth  = int(procWidth / 2) & (~7)

            return (procWidth, procHeight)
        else:
            return procSize

    ###########################################################
    def _thumbDebug(self, msg):
        self._logger.debug(msg)

    ###########################################################
    def _getLabelColor(self, obj):
        label = self.getObjectType(obj)
        return self._getLabelColorForType(label)

    ###########################################################
    def _getLabelColorForType(self, label):
        if self._markupModel.getShowDifferentColorBoxes():
            labelColor = {"person":"yellow", "vehicle":"orange", "animal":"pink"}.get(label, "green")
        else:
            labelColor = "blue"
        return labelColor

    ###########################################################
    def _markThumb(self, camLoc, thumb, ms, objList):
        """ Apply bounding boxes to the thumb image
        @param thumb    - PIL Image object containing the thumb
        @param objList  - list of bounding boxes
        """
        # Determine proc size
        # TODO: does it always work?
        thumbH = thumb.height
        procW, procH = self._getProcSize(camLoc, ms=ms)
        if procH == 0:
            # Should not happen on any of the modern versions
            procH = 240
        draw = ImageDraw.Draw(thumb)

        objectsAreTuples = False
        for obj in objList:
            if isinstance(obj, tuple):
                id = obj[0]
                labelColor = self._getLabelColorForType(obj[3])
            else:
                id = obj
                labelColor = self._getLabelColor(obj)

            bboxes = self.getObjectBboxesBetweenTimes([id], ms, ms)
            if not bboxes:
                continue

            for x1, y1, x2, y2, _, _, _ in bboxes:
                bbox = (round((x1 * thumbH)/float(procH)),
                        round((y1 * thumbH)/float(procH)),
                        round((x2 * thumbH)/float(procH)) - 1,
                        round((y2 * thumbH)/float(procH)) - 1)
                draw.rectangle( bbox, outline=labelColor)

    ###########################################################
    def _populateThumbCache(self, camLoc, timeIndex):
        dirname = os.path.join(self._vidStoragePath, camLoc, timeIndex, kThumbsSubfolder)

        resTimes = []
        if os.path.isdir(dirname):
            thumbmask = os.path.join(dirname, "*.jpg")
            files = glob.glob(thumbmask)
            for file in files:
                fileMs = int(os.path.splitext(os.path.basename(file))[0])
                resTimes.append(fileMs)
            resTimes.sort()
        self._thumbCache[camLoc][timeIndex] = (getTimeAsMs(), resTimes)

    ###########################################################
    def _reduceThumbCache(self, camLoc, timeIndex):
        """ Reduce the cached thumb entries if needed
        """
        _kMaxCachedEntries = 5
        if len(self._thumbCache[camLoc]) < _kMaxCachedEntries:
            return
        diff = 0
        toDelete = None
        for key in self._thumbCache[camLoc]:
            newDiff = abs(int(key)-int(timeIndex))
            if newDiff == 0:
                # repopulation of this entry had been requested
                toDelete = key
                break
            if newDiff > diff:
                # remove the entry furthest in time from the current one
                toDelete = key
                diff = newDiff
        del self._thumbCache[camLoc][toDelete]



    ###########################################################
    def _closestValue(self, myList, myNumber):
        """
        Assumes myList is sorted. Returns closest value to myNumber.

        If two numbers are equally close, return the smallest number.
        """
        if len(myList) == 0:
            return None

        pos = bisect_left(myList, myNumber)
        if pos == 0:
            return myList[0]
        if pos == len(myList):
            return myList[-1]
        before = myList[pos - 1]
        after = myList[pos]
        if after - myNumber < myNumber - before:
           return after
        else:
           return before

    ###########################################################
    def getThumbFileFromCache(self, camLoc, ms, tolerance=3000):
        """ Retrieve best thumbnail image, caching file list for the folder
            This prevents repetitive glob operations when retrieving a sequential
            list of thumbs, which is beneficial for slower file systems
        """
        _kMaxCacheAge = 10*60*1000
        _kSafetyTimeBuffer = 10*000

        try:
            reqMsAsStr=str(ms)
            prevMsAsStr=str(ms-tolerance)
            nextMsAsStr=str(ms+tolerance)

            toCheck = [reqMsAsStr]

            # when we're close to the edge of folder, the closest thumb may be in the prev/next folder
            if (reqMsAsStr[:5] != prevMsAsStr[:5]):
                toCheck.append(prevMsAsStr)
            elif (reqMsAsStr[:5] != str(ms+tolerance)[:5]):
                toCheck.append(nextMsAsStr)


            if not camLoc in self._thumbCache:
                self._thumbCache[camLoc] = {}

            closestTime = None
            for msAsStr in toCheck:
                timeIndex = msAsStr[:5]

                cacheEntry = self._thumbCache[camLoc].get(timeIndex, None)
                # Populate the cache when the entry isn't found
                # ... or when requested time occurs after the time entry was cached or very close to it
                # ... or when the cache is older than a configured age
                if cacheEntry is None or \
                    cacheEntry[0] <= ms + _kSafetyTimeBuffer or \
                    getTimeAsMs() - cacheEntry[0] > _kMaxCacheAge:
                    # need to populate thumb entries for a camera/timeIndex
                    self._reduceThumbCache(camLoc, timeIndex)
                    self._populateThumbCache(camLoc, timeIndex)
                    cacheEntry = self._thumbCache[camLoc][timeIndex]

                if cacheEntry is None:
                    continue

                timesArray = cacheEntry[1]
                closestTimeInFolder = self._closestValue(timesArray, ms)
                if closestTimeInFolder is not None:
                    if closestTime is None or \
                        abs(closestTime-ms) > abs(closestTimeInFolder-ms):
                        closestTime = closestTimeInFolder

            closestTimeAsStr = str(closestTime)
            filename = os.path.join(self._vidStoragePath, camLoc, closestTimeAsStr[:5], kThumbsSubfolder, closestTimeAsStr + ".jpg")

            if os.path.isfile(filename):
                res = filename, closestTime
            else:
                res = None, None
        except:
            self._logger.error(traceback.format_exc())
            res = None, None
        return res

    ###########################################################
    def getThumb(self, camLoc, ms, size, objList, tolerance=3000):
        # Requesting a full-size frame -- thumbs are inherently smaller
        if size == (0,0):
            return None

        try:
            # Figure out the location of our thumbnail
            thumbFile, fileMs = self.getThumbFileFromCache(camLoc, ms, tolerance)

            if thumbFile is not None:
                # Resize and return the thumb if found
                img = Image.open(thumbFile)

                # Do not return pre-created thumb if a requested dimension
                # greater than the actual thumb dimension
                imgSize = img.size
                if imgSize[0] < size[0] or \
                   imgSize[1] < size[1]:
                    return None

                if size[0] == 0:
                    size = (10000, size[1])
                elif size[1] == 0:
                    size = (size[0], 10000)
                img.thumbnail(size, Image.ANTIALIAS)

                if objList is not None:
                    self._markThumb(camLoc, img, fileMs, objList)
                return img

            return None
        except:
            self._logger.error(traceback.format_exc())
            return None



    ###########################################################
    def getSingleMarkedFrame(self, camLoc, ms=0, objList=[], size=(320,240),
                             useTolerance=True):
        """Retrieve a single frame from a video file; marked up.

        @param  camLoc        The camera location to obtain a frame from
        @param  ms            The absolute ms of the frame to retreive.
        @param  objList       A list of the objects to draw bounding boxes for
        @param  useTolerance  If False, we will not allow the clip manager
                              to use a tolerance value when getting the file.
        @return frame         A PIL image of the requested frame
        """
        # Don't even attempt to use a cached thumb, if asking for a full-size
        if size != (0,0):
            img = self.getThumb(camLoc, ms, size, objList)
            if img is not None:
                return img

        img, _ = self.getSingleFrame(
            camLoc, ms, size, useTolerance, False, objList
        )
        return img


    ###########################################################
    def isCameraLocationLive(self, cameraLocation):
        """Determine whether a given camera location is live

        @param  cameraLocation  The name of the camera Location
        @return isLive          True if the location is live
        """
        if cameraLocation == "Live camera":
            return True
        return False


    ###########################################################
    def getImageAt(self, cameraLocation, ms, tolerance, direction='any', size=(0,240)):
        """Retrieve a single frame from a camera location.

        This won't be marked up at all.

        TODO: Figure out when clients should use this vs. getSingleFrame().
        I think this function will give you the closest frame if ms is not
        available, and that's the only difference (?).

        NOTE: This currently doesn't allow you to select the frame size,
              always returning a 320x240 image.  Only used by the
              QueryConstructionView so that's probably ok.

        @param  cameraLocation  The location to retrieve a sample image for.
        @param  ms              The absolute ms desired.
        @param  tolerance       The surrounding time to search before or after
                                if no image was found at ms
                                If None, means infinite tolerance...
        @param  direction       If no image initially matches, the direction in
                                which to seek.  Values are 'any', 'before', or
                                'after'.  If 'any' it will return the closest
                                result.
        @return frame           A PIL image of the live video or None
        @return ms              The ms of the frame.
        """
        if not self._clipManager:
            return (None, ms)

        filename = self._clipManager.getFileAt(cameraLocation, ms, tolerance,
                                               direction)
        if not filename:
            return (None, ms)

        fileStart, fileStop = self._clipManager.getFileTimeInformation(filename)
        ms = min(fileStop, max(fileStart, ms))

        return self.getSingleFrame(cameraLocation, ms, size)

    ###########################################################
    def getProcSize(self, cameraLocation):
        """ Legacy version of _getProcSize, without specifying ms
        """
        return self._getProcSize(cameraLocation)

    ###########################################################
    def _getProcSize(self, cameraLocation, ms=None):
        """Retrieve the resolution size that the camera at cameraLocation was
        processed at.

        @param  cameraLocation  The location to retrieve the processing size for.
        @return procSize        Resolution size that the camera at cameraLocation
                                was processed at. This will be (0,0) if the
                                data manager is unable to retrieve the processing
                                size of the given camera location.
        """

        # Initial processing size. We set this to (0,0) in case we can't get
        # the information requested.
        procSize = (0, 0)

        if not self._clipManager:
            return procSize

        if ms is None:
            ms = int(time.time()*1000)

        # see if we can get all procSizes in one sweep and cache them
        procSizes = self._procSizeCache.get(cameraLocation, None)
        if procSizes is None or ms > procSizes[len(procSizes)-1][3]:
            procSizes = self._clipManager.getUniqueProcSizesBetweenTimes(cameraLocation, None, int(time.time()*1000))
            if procSizes and len(procSizes) > 0:
                self._procSizeCache[cameraLocation] = procSizes
            else:
                procSizes = None

        # use cache, if possible
        if procSizes is not None:
            for w, h, start, end in procSizes:
                if (start is None or start <= ms) and end >= ms:
                    return (w, h)

        # Get the filename of the most recent clip saved in the database.
        filename = self._clipManager.getFileAt(cameraLocation, ms, None, 'before')

        if not filename:
            return procSize

        return self._figureOutProcSize(filename, procSize)


    ###########################################################
    def getUniqueProcSizesBetweenTimes(self, camLoc, startTime=None, endTime=None):
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
        if not self._clipManager:
            return []

        return self._clipManager.getUniqueProcSizesBetweenTimes(
            camLoc, startTime, endTime
        )