#!/usr/bin/env python

#*****************************************************************************
#
# TimedConnection.py
#
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
import sqlite3 as sql
import time
import weakref

# Local imports
from TimedCursor import TimedCursor

kDefaultArraySize=1000


##############################################################################
class TimedConnection(sql.Connection):
    """Debug class to time sql stuff and report when it's slow.

    Automatically creates TimedCursors for you...
    """

    ###########################################################
    def __init__(self, *args, **kwargs):
        """TimedConnection constructor.

        Since this is called directly by sqlite, it doesn't get any parameters.
        See setParameters().
        """
        super(TimedConnection, self).__init__(*args, **kwargs)

        # An instance of a VitaLogger to use...
        self._logger = None

        # If something takes more than this time, we'll log it...
        self._reportOver = None

        # Whether we want to log all queries
        self._debugMode = False

        # arraysize for cursor objects we create
        self._arraySize = kDefaultArraySize

        # Keep weakrefs to cursors...
        self._cursors = []


    ###########################################################
    def setParameters(self, logger, reportOver=5.0, debugMode=False, arraysize=kDefaultArraySize):
        """Actually setup the TimedConnection.

        @param  logger      An instance of a VitaLogger to use.
        @param  reportOver  If an SQL operation takes more than this time, we
                            will log it.
        @param  debugMode   loq all queries if True
        """
        self._logger = logger
        self._reportOver = reportOver
        self._debugMode = debugMode
        self._arraySize = arraysize


    ###########################################################
    def cursor(self):
        """Wrap the standard cursor() to create a TimedCursor.

        TODO: If someone calls execute() on the connection, does this get
        called?

        @return  cursor  The cursor.
        """
        cursor = super(TimedConnection, self).cursor(TimedCursor)
        cursor.setParameters(self._logger, self._reportOver, self._debugMode, self._arraySize)

        self._cursors.append(weakref.ref(cursor))

        return cursor


    ###########################################################
    def commit(self):
        """Wrap commit to time it; also notify cursors.

        TODO: How do we catch implicit commits?  Do we have any of those?
        """
        # Notify cursors, deleting stale references...
        # ...and keep a list of commands that modified the database...
        modifyExecs = []
        for i in xrange(len(self._cursors)-1, -1, -1):
            cursor = self._cursors[i]()
            if cursor is None:
                del self._cursors[i]
            else:
                # Get a list of commands that were used to modify data...
                modifyExecs.extend(cursor.getLastModifyExecs())

                # Tell the cursor that we committed...
                cursor.dataWasCommitted()

        # Start the clock on the commit...
        startTime = time.time()

        # Do the commit...
        try:
            super(TimedConnection, self).commit()
        except sql.OperationalError as e:
            # Sometimes these can be temporary.  Sleep briefly and retry
            self._logger.error("OperationalError on commit %s; retrying" %
                           str(e) )
            time.sleep(.2)
            super(TimedConnection, self).commit()

        # Check how slow it was...
        timeTook = time.time() - startTime
        if timeTook > self._reportOver:
            # Hack the list down so we don't flood the log file...
            if len(modifyExecs) > 1:
                modifyExecs = modifyExecs[:1] + \
                              ['... <%d more> ...' % (len(modifyExecs)-1)]

            modifyExecStr = ', '.join(str(modifyExec)
                                      for modifyExec in modifyExecs)
            self._logger.warning("SLOW SQL commit (%.1f): %s" % (
                                 timeTook, modifyExecStr))


