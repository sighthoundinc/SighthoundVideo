#! /usr/local/bin/python

#*****************************************************************************
#
# CameraManager.py
#     Object maintaining information about the provisioned cameras
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


"""
## @file
Contains the CameraManager class.
"""

# Python imports...
import cPickle
import os
import StringIO
import sys
import time
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8
from vitaToolbox.sysUtils.TimeUtils import formatTime

# Common 3rd-party imports...

# Local imports...

# Globals...
_kBackupDir = "backup"

# We really just need one for the corruption/deletion case (backups shouldn't
# ever be invalid) but keep a history as they take no space and this will give
# the possiblity of manual recovery if someone deletes all cameras.
_kMaxBackups = 50


##############################################################################
class CameraManager(object):
    """A class for managing video sources."""
    ###########################################################
    def __init__(self, logger, mgrPath=None):
        """Initialize CameraManager.

        @param  mgrPath  Path to the camera manager file. Can be None, saving
                         won't be possible then.
        """
        # Call the superclass constructor.
        super(CameraManager, self).__init__()

        self._mgrPath = mgrPath
        self._backupDir = None
        self._logger = logger

        # A persisted dictionary of camera settings.  Keys are camera
        # locations.  The value is a dictionary with keys of 'type', 'uri',
        # 'extra', 'enabled' and 'recordMode'.
        self._camSettings = {}

        if self._mgrPath is not None:
            self._backupDir = os.path.split(self._mgrPath)[0]
            self._backupDir = os.path.join(self._backupDir, _kBackupDir)

            try:
                self._openDb(self._mgrPath)
            except Exception, e:
                self._logger.error("Couldn't load camdb: " + str(e))
                # If we couldn't open the camdb see if we have any backups.
                if not os.path.exists(self._backupDir):
                    return

                # Reverse the directory list so newest will be first
                backups = sorted(os.listdir(self._backupDir))
                backups.reverse()

                for backup in backups:
                    try:
                        self._openDb(os.path.join(self._backupDir, backup))
                        self._logger.info("Loaded camera db backup from " + ensureUtf8(backup))
                        return
                    except:
                        self._logger.error("Failed to load camera db backup from " + ensureUtf8(backup))


    ###########################################################
    def __del__(self):
        """Free resources used by CameraManager."""
        return


    ###########################################################
    def _openDb(self, path):
        """Open and read a camera database file.

        @param  path  Path to the file to open.
        """
        f = open(path, "r")
        data = f.read()
        f.close()
        self.load(data)


    ###########################################################
    def _verifyLocation(self, camLocation):
        if camLocation not in self._camSettings:
            self._logger.error("Camera '" + camLocation + "' not found")
            assert camLocation in self._camSettings
            return False
        return True

    ###########################################################
    def addCamera(self, camLocation, camType, camUri, extra={}, save=True):
        """Add a new camera

        @param  camLocation  The location of the camera
        @param  camType      The camera's type
        @param  camUri       The uri used to access the camera
        @param  extra        An optional extra dict of settings.
        @param  save         Whether or not to persist the changes to file.
        """
        assert isinstance(extra, dict)

        # preserve former frozen flag if new one is not given ...
        if camLocation in self._camSettings:
            if extra.get('frozen', None) is None:
                extraOld = self._camSettings[camLocation].get('extra', None)
                if extraOld is not None:
                    extra['frozen'] = extraOld.get('frozen', False)

        self._camSettings[camLocation] = {'type':camType,
                                          'uri':camUri,
                                          'extra':extra,
                                          'enabled':True}
        if save:
            self.save()


    ###########################################################
    def removeCamera(self, camLocation, save=True):
        """Remove a camera.

        @param  camLocation  The location of the camera to remove.
        @param  save         Whether or not to persist the changes to file.
        """
        if not self._verifyLocation(camLocation):
            return

        del self._camSettings[camLocation]
        if save:
            self.save()


    ###########################################################
    def getCameraFrameStorageSize(self, camLocation):
        """Get the initial frame buffer size

        @param  camLocation  The location of the desired camera
        @param  extra  The dictionary of extra settings
        """
        if not self._verifyLocation(camLocation):
            return 0

        extra = self._camSettings[camLocation].get('extra', {});
        return extra.get('initFrameSize', 0);


    ###########################################################
    def editCameraFrameStorageSize(self, camLocation, size):
        """Update the initial frame buffer size

        @param  camLocation  The location of the desired camera
        @param  extra  The dictionary of extra settings
        """

        if not self._verifyLocation(camLocation):
            return False

        extra = self._camSettings[camLocation]['extra']

        prevSize = self.getCameraFrameStorageSize(camLocation)

        if prevSize < size:
            extra['initFrameSize'] = size
            self._camSettings[camLocation]['extra'] = extra
            self.save();

        return True


    ###########################################################
    def getCameraSettings(self, camLocation):
        """Retrieve the settings of a given camera

        @param  camLocation  The location of the desired camera
        @return camType      The camera's type
        @return camUri       The uri used to access the camera
        @return enabled      True if the camera is enabled
        @return extra        An optional extra dict of settings.
        """
        if not self._verifyLocation(camLocation):
            return None, None, None, None

        d = self._camSettings[camLocation]
        return d['type'], d['uri'], d['enabled'], d['extra']


    ###########################################################
    def isCameraEnabled(self, camLocation):
        """Check if a camera is enabled.

        @param  camLocation  The location of the camera to check.
        @return isEnabled    True if the camera is enabled.
        """
        if not self._verifyLocation(camLocation):
            return False

        d = self._camSettings.get(camLocation, {'enabled':False})
        return d['enabled']


    ###########################################################
    def enableCamera(self, camLocation, enable=True, save=True):
        """Enable or disable a camera.

        @param  camLocation  The location of the camera to edit.
        @param  enable       True if the camera should be enabled.
        @param  save         Whether or not to persist the changes to file.
        """
        if self._verifyLocation(camLocation):
            self._camSettings[camLocation]['enabled'] = enable
        if save:
            self.save()


    ###########################################################
    def isCameraFrozen(self, camLocation):
        """Checks if a camera is frozen, meaning if it has been deactivated due
        to the lack of a proper license.

        @param  camLocation  The location of the camera to check.
        @return isFrozen     True if the camera is frozen.
        """
        if not self._verifyLocation(camLocation):
            return False

        d = self._camSettings.get(camLocation, {'extra':{}})
        return d['extra'].get('frozen', False)


    ###########################################################
    def freezeCamera(self, camLocation, frozen=True, save=True):
        """Freeze or unfreeze a camera (logically).

        @param  camLocation  The location of the camera to edit.
        @param  frozen       True if the camera should be frozen.
        @param  save         Whether or not to persist the changes to file.
        """
        if self._verifyLocation(camLocation):
            self._camSettings[camLocation]['extra']['frozen'] = frozen
        if save:
            self.save()


    ###########################################################
    def save(self):
        """Persist the current state.

        @return False if saving failed or is not possible.
        """
        if self._mgrPath is not None:
            try:
                f = open(self._mgrPath, "w")
                cPickle.dump(self._camSettings, f)
                f.close()

                # Save a backup as well
                try:
                    if not os.path.exists(self._backupDir):
                        os.mkdir(self._backupDir)
                    backupName = "camdb" + formatTime("%Y-%m-%d %H%M%S")
                    f = open(os.path.join(self._backupDir, backupName), "w")
                    cPickle.dump(self._camSettings, f)
                    f.close()
                except:
                    pass

                self._trimBackups()

                return True
            except Exception:
                pass
        return False


    ###########################################################
    def _trimBackups(self):
        """Trim the camdb backups down to the maximum number."""
        if not os.path.exists(self._backupDir):
            return

        backups = sorted(os.listdir(self._backupDir))
        if len(backups) > _kMaxBackups:
            toTrim = backups[:-_kMaxBackups]
            for backup in toTrim:
                try:
                    os.remove(os.path.join(self._backupDir, backup))
                except:
                    pass


    ###########################################################
    def load(self, data):
        """Loads from a pickled state.

        @param data The picked state to load from
        """
        # For a while extra was a string.  Ensure it is now a dict.
        self._camSettings = cPickle.load(StringIO.StringIO(data))
        dirty = False
        for name in self._camSettings.keys():
            # I'm not sure how we got into this case, but bad things happen
            # if you end up with a blank camera name, or any camera name
            # that evaluates to False.  Delete it.
            if not name:
                del self._camSettings[name]
                dirty = True
                continue

            extra = self._camSettings[name].get('extra', None)
            if not isinstance(extra, dict):
                self._camSettings[name]['extra'] = {}
                dirty = True
        if dirty:
            self.save()


    ###########################################################
    def dump(self):
        """Pickles the current state.

        @return The current state.
        """
        result = StringIO.StringIO()
        cPickle.dump(self._camSettings, result)
        return result.getvalue()


    ###########################################################
    def getCameraLocations(self):
        """Return a list of locations of configured cameras.

        @return locations  A list of locations of configured cameras.
        """
        return self._camSettings.keys()


    ###########################################################
    def freezeCameras(self, maxCameras, save=True):
        """Freezes a certain number of cameras.

        @param maxCameras  Maximum number of cameras which should not be frozen.
                           Can be -1 for no cameras ever to be frozen.
        @param save        Whether or not to persist the changes to file.
        @return            Tuple of lists of camera locations which were
                           changed (frozen[], unfrozen[]). Naturally one (or
                           both) of the lists will be empty.
        """
        if -1 == maxCameras:
            maxCameras = sys.maxint
        camLocs = self._camSettings.keys()
        frozen = []
        unfrozen = []
        for camLoc in camLocs:
            if self.isCameraFrozen(camLoc):
                frozen.append(camLoc)
            else:
                unfrozen.append(camLoc)
        frozen.sort()
        unfrozen.sort(reverse=True)
        diff = len(unfrozen) - maxCameras
        result = ([], [])
        if 0 < diff:
            for camLoc in unfrozen[:diff]:
                self.freezeCamera(camLoc, True, False)
                result[0].append(camLoc)
        else:
            for camLoc in frozen[:-diff]:
                self.freezeCamera(camLoc, False, False)
                result[1].append(camLoc)
        if save:
            self.save()
        return result

    ###########################################################
    def logLocations(self, logger):
        """Logs the state of all cameras. One log message per camera location.

        @param logger  The logger to use.
        """
        camLocs = self._camSettings.keys()
        camLocs.sort()
        for cameraLocation in camLocs:
            cs = self._camSettings[cameraLocation]
            logger.info("%s: %s, %s, %s" % (cameraLocation,
                cs['type'], cs['enabled'], str(cs['extra'])))
