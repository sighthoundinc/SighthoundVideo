#!/usr/bin/env python

#*****************************************************************************
#
# EnterExitTrigger.py
#     Trigger: entering or exiting a region
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



from BaseTrigger import BaseTrigger

# NOTE: This trigger doesn't currently return the same results when running in
#       real time and non-real time.  When running in non-real time it will
#       alert only the object's first frame and the object's last frame.  When
#       running in non-real time it will also alert exits each time the object
#       is absent for a frame, which is currently only possible in ground truth.

###############################################################
class EnterExitTrigger(BaseTrigger):
    ###########################################################
    def __init__(self, dataMgr, alertType='both'):
        """Initializer for the EnterExitTrigger class

        @param  dataMgr    An interface to the stored motion data
        @param  alertType  Specifies the conditions under which the trigger
                           should fire.  When objects 'enter' the frame, 'exit'
                           the frame, or 'both'.
        """
        BaseTrigger.__init__(self)

        self._dataMgr = dataMgr

        # Save the tracking location preference
        assert alertType in ['enter', 'exit', 'both']
        self._type = alertType

        self._activeObjects = set()


    ###########################################################
    def __str__(self):
        """Create a string representation of the trigger

        @return strDesc  A string description of the trigger
        """
        return 'EnterExitTrigger - alertType = %s' % self._type


    ###########################################################
    def search(self, timeStart=None, timeStop=None, type='single', procSizesMsRange=None):
        """Search the database for objects tripping the trigger

        @param  timeStart        The time to start searching from, None for beginning
        @param  timeStop         The time to stop searching at, None for present
        @param  type             The type of search to be performed
                                   'single'   - The database is presumed complete
                                   'realtime' - Maintain state between searches
        @param  procSizesMsRange A list of sizes the camera was processed at for
                                 certain ranges of time. Contains a list of 4-tuples
                                 of (procWidth, procHeight, firstMs, lastMs).
                                 Note: if the list contains only one 4-tuple, then
                                 procWidth and procHeight is unique, and firstMs and
                                 lastMs should be ignored; they may hold None values.
                                 If the list contains more than one 4-tuple, then
                                 procWidth and procHeight are not unique, and you must
                                 use the firstMs and lastMs to determine which
                                 procSize was used for a specified period of time.
        @return triggered        A list of dbId, frame, time tuples for objects that
                                 set off the trigger
        """
        triggered = []

        curActive = set()
        for objId in self._dataMgr.getObjectsBetweenTimes(timeStart, timeStop):
            curActive.add(objId)

        if self._type != 'exit':
            for objId in curActive.difference(self._activeObjects):
                # Get the real start time, verify it isn't before timeStart
                time = self._dataMgr.getObjectStartTime(objId)
                if time >= timeStart:
                    frame = self._dataMgr.getFrameAtTime(objId, time)
                    triggered.append((objId, frame, time))

        if type == 'single' and self._type != 'enter':
            # If we're doing a single search we can presume all data is present.
            # Check to see if any objects in this time period also exit.
            for objId in curActive:
                frame, time = self._dataMgr.getObjectFinalTime(objId)
                if timeStop is None or time <= timeStop:
                    triggered.append((objId, frame, time))

        if type != 'single':
            self._activeObjects = curActive

        return triggered


    ###########################################################
    def finalize(self, objList, procSizesMsRange=None):
        """Do a final search on some objects assuming all data has been received

        @param  objList          A list or set of dbIds of objects to search
        @param  procSizesMsRange A list of sizes the camera was processed at for
                                 certain ranges of time. Contains a list of 4-tuples
                                 of (procWidth, procHeight, firstMs, lastMs).
                                 Note: if the list contains only one 4-tuple, then
                                 procWidth and procHeight is unique, and firstMs and
                                 lastMs should be ignored; they may hold None values.
                                 If the list contains more than one 4-tuple, then
                                 procWidth and procHeight are not unique, and you must
                                 use the firstMs and lastMs to determine which
                                 procSize was used for a specified period of time.
        @return triggered        A list of dbId, frame, time tuples for objects that
                                 set off the trigger presuming no more data will come
        """
        triggered = []

        if self._type == 'enter':
            return triggered

        for objId in objList:
            # Add each object that exited the scene to the triggered list
            frame, time = self._dataMgr.getObjectFinalTime(objId)
            triggered.append((objId, frame, time))

        return triggered


    ###########################################################
    def reset(self):
        """Remove any continuation data from a trigger"""
        self._activeObjects = set()


    ###########################################################
    def setDataManager(self, dataManager):
        """Set the data manager containing the desired search information

        @param  dataMgr  The new data manager
        """
        self._dataMgr = dataManager
