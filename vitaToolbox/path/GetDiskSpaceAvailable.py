#!/usr/bin/env python

#*****************************************************************************
#
# GetDiskSpaceAvailable.py
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

import ctypes
from ctypes import c_char_p, c_void_p, c_longlong
import os
import statvfs
import sys

from vitaToolbox.ctypesUtils.LoadLibrary import LoadLibrary
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8


_kMegabyte = 1024*1024

if sys.platform == 'darwin':

    _libName = 'volumeUtils'

    _volumeUtils = LoadLibrary(None, _libName)

    _volumeUtils.getFreeDiskspace.argtypes = [c_char_p]
    _volumeUtils.getFreeDiskspace.restype = c_longlong
    _volumeUtils.getTotalDiskspace.argtypes = [c_char_p]
    _volumeUtils.getTotalDiskspace.restype = c_longlong


###############################################################
def checkFreeSpace(path, minSizeMb, minPercentage,logger=None):
    """ Check if volume containing space satisfies specified free space constraints

    @param  path            Path on the volume to be checked
    @param  minSizeMb       Minimum required free space in megabytes, or 0 if not a constraint
    @param  minPercentage   Minimum required percentage of free space, or 0 if not a constraint
    @param  logger          logger object
    @return                 True if space on the volume within provided constraints, False otherwise
    """
    usageTuple = getDiskUsage(path)

    free = usageTuple[2]
    pctFree = usageTuple[3]

    if (minSizeMb > 0 and free <= minSizeMb*_kMegabyte) or \
       (minPercentage > 0 and pctFree <= minPercentage):
        if not logger is None:
            logger.error("Only " + str(free/_kMegabyte) + "MB (" + str(pctFree) + "%) are free on drive containing path " + ensureUtf8(path) + \
                   ". Arden AI requires at least " + str(minSizeMb) + "MB and " + str(minPercentage) + "% free to record video.")
        return False
    return True

###############################################################
def getDiskUsage(path):
    """ Return volume utilization info

    @param  path            Path on the volume to be checked
    @return                 a tuple of (totalDiskSize, usedDiskSize, freeDiskSize, percentFreeDiskSize) -- with size values in bytes
    """
    def pct(part, total):
        return 0 if total == 0 else 100*float(part)/float(total)

    # We'd fail if the path doesn't exist (for example, it's a file we're going to create,
    # so backtrack to the actual point in the path that exists)
    localPath = path
    while not os.path.exists(localPath) or \
          not os.path.isdir(localPath):
        newLocalPath = os.path.dirname(localPath)
        if newLocalPath == localPath:
            break
        localPath = newLocalPath

    if hasattr(os, 'statvfs'):  # POSIX
        total = _volumeUtils.getTotalDiskspace(ensureUtf8(localPath))
        free  = _volumeUtils.getFreeDiskspace(ensureUtf8(localPath))
        used = total - free
        percentFree = pct(free, total)
        #print "Total=" + str(total) + " free=" + str(free) + " pct=" + str(percentFree)
        return (total, used, free, percentFree)

    elif os.name == 'nt':       # Windows
        import ctypes

        _, total, free = ctypes.c_ulonglong(), ctypes.c_ulonglong(), \
                           ctypes.c_ulonglong()
        if sys.version_info >= (3,) or isinstance(localPath, unicode):
            fun = ctypes.windll.kernel32.GetDiskFreeSpaceExW
        else:
            fun = ctypes.windll.kernel32.GetDiskFreeSpaceExA
        ret = fun(localPath, ctypes.byref(_), ctypes.byref(total), ctypes.byref(free))
        if ret == 0:
            raise ctypes.WinError()
        used = total.value - free.value
        percentFree = pct(free.value, total.value)
        return (total.value, used, free.value, percentFree)
    else:
        raise NotImplementedError("platform not supported")


###############################################################
def getDiskSpaceAvailable(dirPath):
    """Return the amount of space left on a drive.

    @param  dirPath     A path on the drive to return results for.
    @return bytesAvail  The number of bytes available, or -1.
    """
    _, _, freeDiskSize, _ = getDiskUsage(dirPath)
    return freeDiskSize


