#*****************************************************************************
#
# FileUtils.py
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

import cPickle
import ctypes
import os
import sys
import traceback
import subprocess

from vitaToolbox.path.GetDiskSpaceAvailable import checkFreeSpace
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8

_kMegabyte = 1024*1024

###############################################################
def writeStringToFile(filename, strToWrite, logger=None):
    """ Writes a string to file

    @param  filename        file to write to
    @param  strToWrite      string to be written
    @return                 True if successful, False if fails for whatever reason
    """
    objectFile = None
    try:
        needMB = len(strToWrite)/_kMegabyte+1
        if not checkFreeSpace(filename, needMB, 0, None):
            raise Exception("Not enough free disk space (" + str(needMB) +
                            ") to write " + ensureUtf8(filename))
        objectFile = file(filename, 'w+')
        if objectFile is None:
            raise Exception("Failed to open file at " + ensureUtf8(filename))
        objectFile.write(strToWrite)
    except:
        if logger is not None:
            logger.error("Failed to write string to file: " + traceback.format_exc())
        return False
    finally:
        if objectFile is not None:
            objectFile.close()

    return True

###############################################################
def writeObjectToFile(filename, object, logger=None):
    """ Pickles the object and writes it to file

    @param  filename        file to write to
    @param  object          object to be written
    @return                 True if successful, False if fails for whatever reason
    """
    try:
        pickledObject = cPickle.dumps(object)
        if not writeStringToFile(pickledObject):
            return False
    except:
        if logger is not None:
            logger.error("Failed to write object to file: " + traceback.format_exc())
        return False

    return True

###############################################################
def safeRemove(filename):
    try:
        os.remove(filename)
    except OSError:
        pass
