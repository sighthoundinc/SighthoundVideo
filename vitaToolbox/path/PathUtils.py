#!/usr/bin/env python

#*****************************************************************************
#
# PathUtils.py
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

import os
import sys
import unicodedata
import errno

# Used for validating strings that are used in file and directory names.
# The list includes the superset of characters that are invalid in Windows
# and Mac OS X paths.
kInvalidPathChars = r'|/:*"<>?\\'
kInvalidPathCharsDesc = "| / \\ : * \" < > ?"


###############################################################
def abspathU(path):
    """A version of abspath that works if cwd() has non-ascii chars on Mac.

    This only matters if path parameter is a 'unicode' type.

    This is important because:
    1. On Mac, os.getcwd() returns a UTF-8 encoded str, not a unicode type.
    2. If the CWD has weird characters, they are encoded using UTF8
    3. If the relative path is unicode, python will try to convert the absolute
       part and relative part to unicode to join them.  This will fail, since
       the default str to unicode conversion assumes the str is ASCII.

    The fix is to use os.getcwdu().  Note that we only do this upon failure.
    Why?
    * On Windows, the default abspath() doesn't seem to have problems, and
      it goes through a different code path.  We want that other code path on
      Windows.
    * On Mac, we will preserve the notion that if the relative path is
      non-unicode, we'll still return a non-unicode value here.  That's not
      super great, but it is certainly the safest.

    @param  path  The path to make absolute; may be unicode or str type.
                  If str, should be in native path encoding.
    @return path  An absolute version of path.
    """
    try:
        return os.path.abspath(path)
    except UnicodeDecodeError:
        return os.path.normpath(os.path.join(os.getcwdu(), path))


###############################################################
def getDirSize(path):
    """Find the size of a directory.

    @param  path  The path to the directory whose size should be calculated.
    @return size  The size of the directory in bytes.
    """
    if type(path) == str:
        path = path.decode('utf-8')

    dirSize = 0
    if not os.path.isdir(path):
        return dirSize

    for dirpath, dirnames, filenames in os.walk(path):
        dirpath = normalizePath(dirpath)
        for dirname in dirnames:
            dirname = normalizePath(dirname)
            try:
                dirSize += os.path.getsize(os.path.join(dirpath, dirname))
            except OSError:
                # Not much we can do other than just not crashing.
                pass
        for filename in filenames:
            filename = normalizePath(filename)
            try:
                dirSize += os.path.getsize(os.path.join(dirpath, filename))
            except OSError:
                # Not much we can do other than just not crashing.
                pass

    return dirSize


###############################################################
def normalizePath(path):
    """ Normalizes a path to NFC form and returns it as a unicode string

    Converts a path to NFC form (Canonical Decomposition, followed
    by Canonical Composition). Returns a Unicode string.

    This function is useful because on the Mac, the file system returns
    file and folder paths in decomposed form, which when compared to
    e.g. a user-input filename, will not match when doing string comparisons,
    if there are any composite characters, like accented chars, in the name.

    @param  path            The path to normalize. Must be of unicode
                            or UTF-8-encoded str type.
    @param  forceConversion If true, convert regardless of platform
    @return normPath            The normalized path, in Unicode format
    """
    if type(path) == str:
        path = path.decode('utf-8')

    if sys.platform == 'darwin':
        return unicodedata.normalize('NFC', path)

    return path


###############################################################
def existsInPath(path, fileType=None):
    """Check if a file exists, including searching the environment path

    @param  path     The path to the file to look for
    @param fileType  "file", "dir", or None.  If not None,
                     also verifies that it is a file or directory.
    @return exists   True if path exists.

    Note that paths that include directories do not use the
    environment path search.
    """
    if not path:
        return False

    if fileType == "file":
        testExists = os.path.isfile
    elif fileType == "dir":
        testExists = os.path.isdir
    else:
        testExists = os.path.exists

    d, f = os.path.split(path)
    if d:
        if testExists(path):
            return True
    else:
        if 'PATH' in os.environ:
            envpath = os.environ['PATH']
        else:
            envpath = os.defpath
        envpath = envpath.split(os.pathsep)
        for d in envpath:
            if testExists(os.path.join(d,f)):
                return True

    return False


###############################################################
def safeMkdir(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise