#!/usr/bin/env python


#*****************************************************************************
#
# FrontEndEvents.py
#   Contains custom event classes for the front end.
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

# Common 3rd-party imports...
import wx

# Local imports...

# Globals...


TYPE_EVT_CAMERA_ADDED = wx.NewEventType()
EVT_CAMERA_ADDED = wx.PyEventBinder(TYPE_EVT_CAMERA_ADDED)
TYPE_EVT_CAMERA_REMOVED = wx.NewEventType()
EVT_CAMERA_REMOVED = wx.PyEventBinder(TYPE_EVT_CAMERA_REMOVED)
TYPE_EVT_CAMERA_EDITED = wx.NewEventType()
EVT_CAMERA_EDITED = wx.PyEventBinder(TYPE_EVT_CAMERA_EDITED)

##############################################################################
class CameraAddedEvent(wx.PyCommandEvent):
    """An event fired when cameras are added."""
    ###########################################################
    def __init__(self, cameraLocation):
        """Initializer for CameraAddedEvent.

        @param  cameraLocation  The location of the added camera.
        """
        wx.PyCommandEvent.__init__(self, TYPE_EVT_CAMERA_ADDED)
        self._cameraLocation = cameraLocation


    ###########################################################
    def getLocation(self):
        """Retrieve the name of the added camera.

        @return cameraLocation  The location of the added camera.
        """
        return self._cameraLocation


##############################################################################
class CameraRemovedEvent(wx.PyCommandEvent):
    """An event fired when cameras are removed."""
    ###########################################################
    def __init__(self, cameraLocation):
        """Initializer for CameraRemovedEvent.

        @param  cameraLocation  The location of the removed camera.
        """
        wx.PyCommandEvent.__init__(self, TYPE_EVT_CAMERA_REMOVED)
        self._cameraLocation = cameraLocation


    ###########################################################
    def getLocation(self):
        """Retrieve the name of the removed camera.

        @return cameraLocation  The location of the removed camera.
        """
        return self._cameraLocation


##############################################################################
class CameraEditedEvent(wx.PyCommandEvent):
    """An event fired when cameras are edited."""
    ###########################################################
    def __init__(self, originalLocation, currentLocation):
        """Initializer for CameraEditedEvent.

        @param  originalLocation  The pre-edit location of the camera.
        @param  currentLocation   The post-edit location of the edited camera.
        """
        wx.PyCommandEvent.__init__(self, TYPE_EVT_CAMERA_EDITED)
        self._originalLocation = originalLocation
        self._currentLocation = currentLocation


    ###########################################################
    def getLocations(self):
        """Retrieve the pre and post edit locations of the camera.

        @return originalLocation  The pre-edit location of the camera.
        @return currentLocation   The post-edit location of the edited camera.
        """
        return self._originalLocation, self._currentLocation
