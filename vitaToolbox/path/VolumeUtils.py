#! /usr/local/bin/python

#*****************************************************************************
#
# VolumeUtils.py
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

"""
## @file
Contains an interface to c volume information modules.
"""

import ctypes
from ctypes import c_char_p, c_void_p
import os
import sys
import subprocess

from PathUtils import abspathU

from vitaToolbox.ctypesUtils.LoadLibrary import LoadLibrary


if sys.platform == 'darwin':

    _libName = 'volumeUtils'

    _volumeUtils = LoadLibrary(None, _libName)

    _volumeUtils.getVolumeName.argtypes = [c_char_p]
    _volumeUtils.getVolumeName.restype = c_void_p
    _volumeUtils.freeVolumeName.argtypes = [c_void_p]
    _volumeUtils.getVolumeType.argtypes = [c_char_p]
    _volumeUtils.getVolumeType.restype = c_char_p


kWinIntToDriveType = { 0 : "Unknown Drive",
                       1 : "Unknown Drive",
                       2 : "Removable Drive",
                       3 : "Local Drive",
                       4 : "Remote Drive",
                       5 : "CD Drive",
                       6 : "RAM Disk" }

kUnknownDiskTypes = ["Unknown Drive", "Unknown Volume", ""]

kVolumeTypeRemote = "Remote Volume"
kVolumeTypeLocal = "Local Volume"

kRemoteDiskTypes = ["Remote Drive", kVolumeTypeRemote]

###############################################################
def getStorageSizeStr(size):
    """ Returns the string best reflecting a storage size
    """
    kKilo    = 1024.0
    suffixes = [ "B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB" ]
    maxIter  = len(suffixes)
    curr     = 0

    sign = "-" if (size < 0) else ""
    floatSize = abs(float(size))
    while curr < maxIter and floatSize >= kKilo:
        curr += 1
        floatSize /= kKilo

    return "%s%.2f%s" % (sign, floatSize, suffixes[curr])


###############################################################
def getVolumeNameAndType(path):
    """Return a volume's name from its path.

    @param  path     The path whose volume should be retrieved.
    @return volName  The name of the volume.
    @return volType  On mac, one of Local Volume, Remote Volume, or Unknown
                     Volume. On windows, a value from kWinIntToDriveType.
    """
    volName = ""
    volType = ""

    # Make sure our path is Unicode.  Convert to Unicode if it isn't.
    if type(path) == str:
        path = path.decode('utf-8')

    if sys.platform == 'darwin':
        volNamePtr = _volumeUtils.getVolumeName(path.encode('utf-8'))
        if volNamePtr:
            volName = c_char_p(volNamePtr).value
            _volumeUtils.freeVolumeName(volNamePtr)
        volType = _volumeUtils.getVolumeType(path.encode('utf-8'))
    else:
        # The path must end in a trailing backslash, see
        # http://msdn.microsoft.com/en-us/library/aa364993%28VS.85%29.aspx
        if not path.endswith('\\'):
            path += '\\'
        volInt = ctypes.windll.kernel32.GetDriveTypeW(path) #PYCHECKER OK: No module attribute (windll) found
        volType = kWinIntToDriveType.get(volInt, kWinIntToDriveType[0])

        path = abspathU(path)
        volName, _ = os.path.splitdrive(path)
        if not volName:
            # If we weren't on a drive attpmpt to get the unc volume name
            unc, _ = os.path.splitunc(path)
            if unc:
                volName = unc.split('\\')[-1]

    return volName, volType


###############################################################
def automountDisksWithoutUserLoginEnabled():
    """ Checks, on OSX only, if local volumes will be mounted at startup or
    outside of a user login respectively

    @return  True if such auto-mounting is enabled. False if not or None if the
             status couldn't be determined (e.g. if we're not on a Mac).
    """
    if sys.platform == 'darwin':
        args = ["defaults", "read",
                "/Library/Preferences/SystemConfiguration/autodiskmount",
                "AutomountDisksWithoutUserLogin"]
        try:
            output = subprocess.check_output(args)
            output = output.strip()
            if output == "1":
                return True
            if output == "0":
                return False
        except:
            pass
    return None


###############################################################################
def isRemotePath(path):
    """Checks and returns True if the given path is a network drive.

    Note:   For Mac, it will check if the path is a network drive or an attached
            drive. If a drive's local and auto-mounting outside user sessions
            are enabled the drive won't be treated as a remote one.

    @param  path           The path to check.
    @return dynamicVolume  True if the path is a network path (or an attached
                           drive, for Mac); False otherwise.
    """

    dynamicVolume = False

    (_, volType) = getVolumeNameAndType(path)

    if sys.platform == 'darwin':
        dynamicVolume = \
            path.startswith('/Volumes/') or (volType in kRemoteDiskTypes)
        if dynamicVolume and kVolumeTypeLocal == volType and \
           automountDisksWithoutUserLoginEnabled():
            dynamicVolume = False
    else:
        dynamicVolume = (volType in kRemoteDiskTypes)

    return dynamicVolume

