#!/usr/bin/env python

#*****************************************************************************
#
# TimedCursor.py
#
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
import sqlite3 as sql
import time


##############################################################################
class TimedCursor(sql.Cursor):
    """Debug class to time cursor execute calls and report slow ones.

    You should pass this as the cursor class when you get a cursor from a
    connection object.
    """

    ###########################################################
    def __init__(self, *args, **kwargs):
        """TimedCursor constructor.

        Since this is called directly by sqlite, it doesn't get any parameters.
        See setParameters().
        """
        super(TimedCursor, self).__init__(*args, **kwargs)

        # An instance of a VitaLogger to use...
        self._logger = None

        # If something takes more than this time, we'll log it...
        self._reportOver = None

        # The time.time() at the start/end of the last execute call...
        self._lastExecuteStart = None
        self._lastExecuteFinish = None

        # The time.time() and (args, kwArgs) when we last modified data...
        self._lastModifyStart = None
        self._lastModifyExecList = []

        # Count of how many fetches we've done for a given execute...
        self._fetchCount = None

        # Stores (args, kwArgs) from the previous exec...
        self._prevExec = None

        # Whether we want to log all queries
        self._debugMode = False

        # Normally, we log execute errors, but client can request it to be
        # disabled for a few statements...
        self._executeErrorsOkForNext = 0


    ###########################################################
    def setParameters(self, logger, reportOver, debugMode, arraysize):
        """Actually setup the TimedCursor.

        @param  logger      An instance of a VitaLogger to use.
        @param  reportOver  If an SQL execute takes more than this time, we will
                            log it.
        @param  debugMode   loq all queries if True
        """
        self._logger = logger
        self._reportOver = reportOver
        self._debugMode = debugMode
        self.arraysize = arraysize


    ###########################################################
    def disableExecuteLogForNext(self, numExecutes=1):
        """Disable exception logging for the next "numExecutes" execute statements.

        @param  numExecutes  The number of executes to disable logging for.
                             Nearly always should be 1, unless we have a whole
                             bunch of execute statements in their own try/catch
                             blocks.
        """
        self._executeErrorsOkForNext += numExecutes


    ###########################################################
    def execute(self, *args, **kwargs):
        """Wrapper for execute.

        @param  ...  See real SQL cursor.
        @return ...  See real SQL cursor.
        """
        # Give a warning if there's old data in the queue.  This is bad because
        # it can block writes from happening in other processes (they can't
        # commit until the reader is done).
        oldData = super(TimedCursor, self).fetchone()
        if oldData:
            oldArgs, oldKwargs = self._prevExec
            self._logger.warning("Not all data was fetched from: %s %s" % (
                str(oldArgs), str(oldKwargs)))

        # Save this as prev execute for logging purposes...
        self._prevExec = (args, kwargs)

        # Get the start time of this statement...
        self._lastExecuteStart = time.time()

        # Keep track of number of changes before statement so we can tell
        # if the call modified the database...
        totalChanges = self.connection.total_changes

        # Call the super to run it...
        try:
            result = super(TimedCursor, self).execute(*args, **kwargs)
        except sql.OperationalError as e:
            # Sometimes these can be temporary.  Sleep briefly and retry.
            if self._executeErrorsOkForNext == 0:
                # Only give the message if we're not supposed to be silent..
                self._logger.error("OperationalError %s on execute; retrying: %s %s" %
                                   (str(e), str(args), str(kwargs)) )
            time.sleep(.2)
            result = super(TimedCursor, self).execute(*args, **kwargs)
        except Exception as e:
            if self._executeErrorsOkForNext == 0:
                self._logger.error("Failed execute %s: %s %s" %
                                   (str(e), str(args), str(kwargs)) )
            raise
        finally:
            self._executeErrorsOkForNext = max(0,self._executeErrorsOkForNext-1)

        # Report slow statements...
        self._lastExecuteFinish = time.time()
        timeTook = self._lastExecuteFinish - self._lastExecuteStart
        if self._debugMode:
            timeTook = int(timeTook*1000)
            self._logger.warning("SQL EXEC (%d ms): %s %s" % (
                timeTook, str(args), str(kwargs)))
        elif timeTook > self._reportOver:
            self._logger.warning("SLOW SQL EXEC (%.1f): %s %s" % (
                timeTook, str(args), str(kwargs)))

        # If the database changes, keep track of the change time...
        if (self.connection.total_changes != totalChanges):
            if self._lastModifyStart is None:
                self._lastModifyStart = self._lastExecuteFinish
            self._lastModifyExecList.append((args, kwargs))

        # Init fetchCount
        self._fetchCount = 0

        # Give the result...
        return result


    ###########################################################
    def fetchall(self):
        """Wrapper for fetchall.

        @return  result  The result of the wrapped fetchall().
        """
        # Call the original...
        result = super(TimedCursor, self).fetchall()

        # See how long it took...
        if self._lastExecuteFinish is not None:
            timeTook = time.time() - self._lastExecuteFinish
            if self._debugMode:
                timeTook = int(timeTook*1000)
                oldArgs, oldKwargs = self._prevExec
                self._logger.warning("SQL FETCHALL (%d ms): %s %s" % (timeTook, str(oldArgs), str(oldKwargs)))
            elif timeTook > self._reportOver:
                oldArgs, oldKwargs = self._prevExec
                self._logger.warning("SLOW SQL fetchall (%.1f): %s %s" % (
                    timeTook, str(oldArgs), str(oldKwargs)))

            self._lastExecuteFinish = None

        return result


    ###########################################################
    def fetchone(self):
        """Wrapper for fetchone.

        @return  result  The result of the wrapped fetchone().
        """
        self._fetchCount += 1

        # Call the original...
        result = super(TimedCursor, self).fetchone()

        # If fetchone is returning None, then we must be done fetching.  See
        # how long since execute finished...
        if (result is None) and (self._lastExecuteFinish is not None):
            timeTook = time.time() - self._lastExecuteFinish
            if timeTook > self._reportOver:
                oldArgs, oldKwargs = self._prevExec
                self._logger.warning("SLOW SQL fetchones (%d - %.1f): %s %s" % (
                    self._fetchCount, timeTook, str(oldArgs), str(oldKwargs)))

            self._lastExecuteFinish = None

        return result


    ###########################################################
    def getLastModifyExecs(self):
        """Get the execs that modified data since the last commit.

        @return execCallList  A list of (args, kwargs) of execs that modified
                              data.
        """
        return self._lastModifyExecList


    ###########################################################
    def dataWasCommitted(self):
        """Notify the timed cursor that a commit happened.

        This should automatically be called when you use TimedConnection().

        This allows us to log how long a process was hodling the write lock.
        """
        if self._lastModifyStart is not None:
            timeTook = time.time() - self._lastModifyStart
            if timeTook > self._reportOver:
                oldArgs, oldKwargs = self._lastModifyExecList[0]
                self._logger.warning("Delay between write/update (%.1f): %s %s" % (
                    timeTook, str(oldArgs), str(oldKwargs)))

            self._lastModifyStart = None
            self._lastModifyExecList = []


    ###########################################################
    def next(self):
        """Wrapper for next.

        We treat this just like fetchone(), but with a slightly different stop
        mechanism...

        @return  result  The result of the wrapped fetchone().
        """
        self._fetchCount += 1

        try:
            # Call the original...
            result = super(TimedCursor, self).next()
        except StopIteration:
            # If fetchone is returning None, then we must be done fetching.  See
            # how long since execute finished...
            if self._lastExecuteFinish is not None:
                timeTook = time.time() - self._lastExecuteFinish
                if timeTook > self._reportOver:
                    oldArgs, oldKwargs = self._prevExec
                    self._logger.warning("SLOW SQL nexts (%d - %.1f): %s %s" % (
                        self._fetchCount, timeTook, str(oldArgs), str(oldKwargs)))

                self._lastExecuteFinish = None

            raise

        return result



