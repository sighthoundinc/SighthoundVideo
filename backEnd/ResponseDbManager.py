#!/usr/bin/env python

#*****************************************************************************
#
# ResponseDbManager.py
#    API for accessing and interacting with response database (responseDb)
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
import cPickle as pickle
import sqlite3 as sql
import time
import os

# Common 3rd-party imports...

# Toolbox imports...
from vitaToolbox.sql.TimedConnection import TimedConnection

# Local imports...
from appCommon.CommonStrings import kSqlAlertThreshold

# Constants...

# We'll delete any clips that started more than this many ms ago...
_kOldClipHours = 24
_kOldClipMs    = (_kOldClipHours * 60 * 60 * 1000)

_kOldClipWarning = (
    "Deleting %%d clips from the queue of clips to send, since they started "
    "more than %d hours ago."
) % (_kOldClipHours)


_kMaxTries   = 3
_kRetryDelay = (60 * 1000)


_kSendClipWarningFormatStr = (
    "...we will retry sending the clip %d more time(s)."
)



###############################################################
class ResponseDbManager(object):
    """A class for keeping track of responses that we need to process.

    We store responses in here that take a while to do and that, if we don't
    finish them and the app quits, we should resume when the app restarts.
    """
    ###########################################################
    def __init__(self, logger):
        """Initializer for the ResponseDbManager class

        @param  logger  An instance of a VitaLogger to use.
        """
        self._logger = logger
        self._connection = None
        self._curDbPath = None


    ###########################################################
    def _createTables(self):
        """Create the necessary tables in the database

        clipsToSend:
            uid         - int, req, primary key
            processAt   - int, req, time to process this clip at (ms)
            failures    - int, req, number of times we've tried to send.
            protocol    - text, req, the protocol to use to send
            camLoc      - text, req, name of the camera
            ruleName    - text, req, name of the rule
            startTime   - int, req, time of the start of the clip.
            stopTime    - int, req, time of the end of the clip.
            playStart   - int, req, time that the clip should start playing
            previewMs   - int, req, time to show for a thumbnail (unused,
                          at the moment).
            objList     - blob, req, pickled list of objects IDs in the clip.
            startList   - blob, req, pickled list of start times in the clip.

        lastSentInfo: (one entry in this table, per protocol)
            protocol    - text, req, primary key
            startTime   - int, req, startTime from last sent clip.
            stopTime    - int, req, stopTime from last sent clip.
            processAt   - int, req, processAt from last sent clip.
            sentAt      - int, req, ms that the last clip was marked sent.
            ruleName    - int, req, ruleName from last sent clip.

        pushNotifications:
            data      - blob, req, JSON encoded data of the associated response
            content   - text, req, UTF-8 text to be shown to the user
            createdAt - int, req, time the notification was created (ms)
            uid       - int, req, the sequence number of the notification

        """
        # Use a page size of 4096.  The thought (from google gears API docs),
        # is that: "Desktop operating systems mostly have default virtual
        # memory and disk block sizes of 4k and higher."
        self._cur.execute('''PRAGMA page_size = 4096''')

        for query in (
                '''CREATE TABLE clipsToSend (uid INTEGER PRIMARY KEY, '''
                '''failures INTEGER, processAt INTEGER, '''
                '''protocol TEXT, camLoc TEXT, ruleName TEXT, '''
                '''startTime INTEGER, stopTime INTEGER, '''
                '''playStart INTEGER, previewMs INTEGER, '''
                '''objList BLOB, startList BLOB)''',

                '''CREATE TABLE lastSentInfo (protocol TEXT PRIMARY KEY, '''
                '''startTime INTEGER, stopTime INTEGER, processAt INTEGER, '''
                '''sentAt INTEGER, ruleName TEXT)''',

                '''CREATE TABLE pushNotifications ('''
                '''uid INTEGER PRIMARY KEY AUTOINCREMENT, '''
                '''createdAt INTEGER, content TEXT, data TEXT)'''):
            try:
                self._cur.disableExecuteLogForNext()
                self._cur.execute(query)
                self._logger.info("executed: %s..." % query[0:32])
            except sql.OperationalError:
                # Ignore failures in creating the table, which can happen
                # because of race conditions...
                pass


    ###########################################################
    def _upgradeOldTablesIfNeeded(self):
        """Upgrade from older versions of tables."""
        pass


    ###########################################################
    def _addIndices(self):
        """Add some indices to the database."""
        pass


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
        self._connection = self._getNewConnection()
        self._cur = self._connection.cursor()

        # Use persistent mode for journal files.
        self._cur.execute("PRAGMA journal_mode=PERSIST").fetchall()

        # Use synchronous FULL, which is slower but means that we shouldn't
        # need to deal with corruption.  Speed isn't important in this DB.
        self._cur.execute('''PRAGMA synchronous=FULL''').fetchall()

        # Set up tables if they don't exist
        self._createTables()

        # Other upgrades for old tables...
        self._upgradeOldTablesIfNeeded()

        # Add indices...
        self._addIndices()

        self._connection.commit()


    ###########################################################
    def _getNewConnection(self, timeout=15):
        """Return a new connection to the current database

        @return connection  A new database connection.
        """
        if not self._curDbPath:
            return None

        connection = sql.connect(self._curDbPath.encode('utf-8'), timeout,
                factory=TimedConnection, check_same_thread=False)
        connection.setParameters(self._logger, float(kSqlAlertThreshold), os.path.exists(self._curDbPath+".debug"))

        return connection


    ###########################################################
    def getPath(self):
        """Retrieve the database path.

        @return clipDbPath  Path to the database, or None.
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
    def reset(self):
        """Reset the database"""
        assert self._connection is not None

        self._connection.execute('''DROP TABLE clipsToSend''')

        self._createTables()
        self._addIndices()
        self.save()


    ###########################################################
    def addClipToSend(self, protocol, camLoc, ruleName, startTime, stopTime,
                      playStart, previewMs, objList, startList):
        """Add a clip to send.

        @param  protocol   Name of the protocol to use to send the response.
        @param  camLoc     Name of the camera.
        @param  ruleName   Name of the rule.
        @param  startTime  Start time (in ms) of the clip to send.
        @param  stopTime   Stop time (in ms) of the clip to send.
        @param  playStart  Time (in ms) that the clip should start playing.
        @param  previewMs  Time (in ms) that the thumbnail should show.
        @param  objList    List of DB IDs in the clip.
        @param  startList  List of start times of triggers in the clip.
        """
        # Pickle objList and startList.
        objList = pickle.dumps(objList)
        startList = pickle.dumps(startList)

        # We always want to start processing right away...
        processAt = int(time.time() * 1000)

        self._cur.execute('''INSERT INTO clipsToSend '''
                          '''(failures, processAt, protocol, camLoc, ruleName, '''
                          '''startTime, stopTime, playStart, previewMs, '''
                          '''objList, startList) '''
                          '''Values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (0, processAt, protocol, camLoc, ruleName,
                           startTime, stopTime, playStart, previewMs,
                           objList, startList))

        self.save()


    ###########################################################
    def areResponsesPending(self, protocol):
        """Returns True if there is anything in our database.

        This will return False if there's something pending, but it's deferred
        until sometime after right now.

        @param protocol Look for just a particular protocol.
        @return areResponsesPending  True if there's something in the database
                                     that needs to be processed.
        """
        msNow = int(time.time() * 1000)
        self._cur.execute('''SELECT * FROM clipsToSend '''
                          '''WHERE processAt <= ? AND protocol = ? LIMIT 1''',
                          (msNow, protocol))
        return bool(self._cur.fetchall())


    ###########################################################
    def countQueueLength(self, protocol):
        """Count the number of items in the database, by protocol.

        @param  protocol  The protocol whose items we want to count.
        @return count     The number of items in the database.
        """
        connection = self._getNewConnection()

        (theCount,) = connection.cursor().execute(
            '''SELECT COUNT() FROM clipsToSend '''
            '''WHERE protocol = ?''', (protocol,)
        ).fetchone()
        connection.close()
        return theCount


    ###########################################################
    def _clearOldClips(self):
        """Clear out any clips that are really old.

        At the moment, this is hardcoded to 24H.
        """
        # If they start before this time, they're old...
        oldMs = int(time.time() * 1000) - _kOldClipMs

        # Do a read first so that we don't need to grab any locks in the common
        # case.
        self._cur.execute('''SELECT ruleName FROM clipsToSend '''
                          '''WHERE startTime <= ?''', (oldMs,))
        toDelete = self._cur.fetchall()

        if toDelete:
            self._logger.warning(_kOldClipWarning % (len(toDelete)))
            self._cur.execute('''DELETE FROM clipsToSend '''
                              '''WHERE startTime <= ?''', (oldMs,))
            self.save()


    ###########################################################
    def getNextClipToSend(self, protocol):
        """Return the next clip to send.  DOESN'T DELETE.

        Will return None instead of the big tuple of results if nothing is
        there.

        @param  protocol   The protocol to filter for.
        @return uid        The UID; used for deleting.
        @return camLoc     Name of the camera.
        @return ruleName   Name of the rule.
        @return startTime  Start time (in ms) of the clip to send.
        @return stopTime   Stop time (in ms) of the clip to send.
        @return playStart  Time (in ms) that the clip should start playing.
        @return previewMs  Time (in ms) that the thumbnail should show.
        @return objList    List of DB IDs in the clip.
        @return startList  List of start times of triggers in the clip.
        """
        # Clear out any really old clips...
        self._clearOldClips()

        msNow = int(time.time() * 1000)
        self._cur.execute('''SELECT uid, protocol, camLoc, ruleName, '''
            '''startTime, stopTime, playStart, previewMs, '''
            '''objList, startList '''
            '''FROM clipsToSend WHERE processAt <= ? AND protocol = ? '''
            '''ORDER BY uid LIMIT 1''', (msNow, protocol))
        result = self._cur.fetchone()
        if result is None:
            return None

        (uid, protocol, camLoc, ruleName, startTime, stopTime,
         playStart, previewMs, objList, startList) = result
        objList = pickle.loads(str(objList))
        startList = pickle.loads(str(startList))

        return (uid, camLoc, ruleName, startTime, stopTime,
                playStart, previewMs, objList, startList)


    ###########################################################
    def clipFailed(self, uid):
        """Note that the given clip failed to send.

        This might delete the clip, or defer it for later processing.

        @param  uid     The uid that was returned by getNextClipToSend().
        """
        # NOTE NOTE:
        #   This code is not used at the moment, since we never fail individual
        #   clips--we always just block the whole queue on any failure (assuming
        #   that the net connection is down, or that all other clips will fail
        #   too).  We might use it in the future, though?
        # NOTE NOTE

        # Update the entry to say that we've got one more failure, and to move
        # the process time up...
        msNow = int(time.time() * 1000)
        retryTime = msNow + _kRetryDelay
        self._cur.execute('''UPDATE clipsToSend SET '''
                          '''failures=failures+1, '''
                          '''processAt=?'''
                          '''WHERE uid=?''', (retryTime, uid))

        # Check the number of failures; be paranoid and handle the case where
        # we can't find this UID anymore (don't expect that)...
        failures = self._cur.execute(
            '''SELECT failures FROM clipsToSend WHERE uid=?''', (uid,)
        ).fetchone()
        if failures is None:
            self.save()
            assert False, "Couldn't find clip uid %s" % (uid)
            return
        (failures,) = failures

        # If we've failed too many times, delete the clip...
        if failures >= _kMaxTries:
            self._deleteClip(uid)
        else:
            triesLeft = (_kMaxTries - failures)
            self._logger.warn(_kSendClipWarningFormatStr % triesLeft)

        self.save()


    ###########################################################
    def clipDone(self, uid, wasSent):
        """Note that we're done with the given clip.

        @param  uid      The uid that was returned by getNextClipToSend().
        @param  wasSent  If True, the clip was sent successfull.
        """
        if wasSent:
            # Keep track of info about the last clip that was sent, per
            # protocol.  This magic statement will automatically handle
            # updating on a per protocol basis, since protocol is a unique key
            # for the lastSentInfo and we're using the "OR REPLACE" syntax...
            self._cur.execute(
                '''INSERT OR REPLACE INTO lastSentInfo (protocol, '''
                '''startTime, stopTime, processAt, sentAt, ruleName) SELECT '''
                '''protocol, startTime, stopTime, processAt, ?, ruleName '''
                '''FROM clipsToSend WHERE uid=?''', (int(time.time()*1000), uid)
            )

        self._deleteClip(uid)
        self.save()


    ###########################################################
    def getLastSentInfo(self, protocol):
        """Returns info about the last clip sent, or None.

        Will return None instead of big tuple if there's no info.

        @param  protocol       The protocol we'd like info about.
        @return startTime      The start time of the last clip sent.
        @return stopTime       The stop time of the last clip sent.
        @return processAtTime  The time that the last clip was requested to
                               be processed at (currently the time the clip
                               was intended to be put in the queue).
        @return sentAtTime     The time that the last clip was marked as sent.
        @return ruleName       The name of the rule that was used to send
                               the last clip.
        """
        connection = self._getNewConnection()
        result = connection.cursor().execute(
            '''SELECT startTime, stopTime, processAt, sentAt, ruleName FROM '''
            '''lastSentInfo WHERE protocol=?''', (protocol,)
        ).fetchone()
        connection.close()
        return result


    ###########################################################
    def purgePendingClips(self, protocol):
        """Delete everything with a given protocol.

        @param  protocol  The protocol whose clips we want to purge.
        """
        connection = self._getNewConnection()
        cur = connection.cursor()
        cur.execute( '''DELETE FROM clipsToSend WHERE protocol=?''',
                (protocol,))
        _ = cur.fetchall()
        connection.commit()


    ###########################################################
    def _deleteClip(self, uid):
        """Delete something from the clipsToSend table.

        DOESN'T DO A self.save()

        @param  uid  The uid that was returned by getNextClipToSend().
        """
        self._cur.execute('''DELETE FROM clipsToSend WHERE uid=?''', (uid,))
        _ = self._cur.fetchall()


    ###########################################################
    def addPushNotification(self, content, data):
        """Adds an item (plus date) to the pushNotifications table.

        @param content The notification content (textual, for direct display)
        @param data The notification content, as a JSON string.
        @return The unique identifier for the notification. Like a sequence
        number, always increasing.
        """
        createdAt = int(time.time() * 1000)
        self._cur.execute('''INSERT INTO pushNotifications '''
                          '''(createdAt, content, data) VALUES (?, ?, ?)''',
                          (createdAt, content, data))
        result = self._cur.lastrowid
        self.save()
        return result


    ###########################################################
    def getPushNotifications(self, lowestUID, limit):
        """Get push notifications.

        @param lowestUID The lowest identifier for a notification to be part
                         of the result set. The lowest valid value is zero.
        @param limit Maximum number of notifications to return.
        @return The notifications. List, each item contains (uid,content,data).
        """
        self._cur.execute('''SELECT uid,content,data FROM pushNotifications'''
                          ''' WHERE uid >= ? ORDER BY uid LIMIT ?''',
                          (lowestUID, limit))
        result = []
        for row in self._cur.fetchall():
            (uid, content, data) = row
            item = (int(uid), content, data)
            result.append(item)
        return result


    ###########################################################
    def getLastPushNotificationUID(self):
        """Get the identifier of the last notification stored.

        @return The UID of the latest entry or -1 if no entries at all exist.
        """
        self._cur.execute('''SELECT MAX(uid) FROM pushNotifications''')
        result = self._cur.fetchone()
        if result is None or result[0] is None:
            return -1
        return int(result[0])


    ###########################################################
    def purgePushNotifications(self, olderThanSecs, limit):
        """Gets rid of old(er) push notifications.

        @param olderThanSecs Maximum age a stored notification should have.
        @param limit Maximum number of rows to remove.
        @return Number of notifications removed.
        """
        totalChangesOld = self._connection.total_changes
        createdAtMin = max(0, int((time.time() - olderThanSecs) * 1000))

        # NOTE: no LIMIT support for DELETE in Python at this moment, hence we
        #       use a more complicated query ...

        self._cur.execute('''DELETE FROM pushNotifications WHERE rowid IN '''
            '''(SELECT rowid FROM pushNotifications '''
            '''WHERE createdAt < ? LIMIT ?)''',
            (createdAtMin, limit))

        self.save()
        return self._connection.total_changes - totalChangesOld
