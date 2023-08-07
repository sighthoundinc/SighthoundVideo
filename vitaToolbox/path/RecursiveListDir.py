#!/usr/bin/env python

#*****************************************************************************
#
# RecursiveListDir.py
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

import os

##############################################################################
def recursiveListDir(pathToDir, substitutePath=None):
    """Do a recursive list of a directory.

    This is really just equivalent to 'find -name pathToDir'; well, except
    that it doesn't include the directories in the list.

    Here's a quick testcase, which creates a temp directory and make sure that
    we get the files we expect.

    >>> import tempfile, shutil
    >>> tmpDir = tempfile.mkdtemp()
    >>> open(os.path.join(tmpDir, "one"), "w").close()
    >>> open(os.path.join(tmpDir, "two"), "w").close()
    >>> open(os.path.join(tmpDir, "three"), "w").close()
    >>> os.mkdir(os.path.join(tmpDir, "dir1"))
    >>> open(os.path.join(tmpDir, "dir1", "a"), "w").close()
    >>> open(os.path.join(tmpDir, "dir1", "b"), "w").close()
    >>> open(os.path.join(tmpDir, "dir1", "c"), "w").close()
    >>> os.mkdir(os.path.join(tmpDir, "dir2"))
    >>> open(os.path.join(tmpDir, "dir2", "d"), "w").close()
    >>> open(os.path.join(tmpDir, "dir2", "e"), "w").close()
    >>> open(os.path.join(tmpDir, "dir2", "f"), "w").close()
    >>> l = recursiveListDir(tmpDir)
    >>> tmps = [ x[:len(tmpDir)] for x in l]
    >>> files = [ x[len(tmpDir):] for x in l]
    >>> assert tmps == [tmpDir] * 9
    >>> sorted(files)
    ['/dir1/a', '/dir1/b', '/dir1/c', '/dir2/d', '/dir2/e', '/dir2/f', '/one', '/three', '/two']
    >>> shutil.rmtree(tmpDir)

    @param  pathToDir       The path to do the recursive list of.
    @param  substitutePath  Pass a path in to use as a substitute for 'pathToDir'
                            in the returned files.  Useful for making a
                            directory tree that mirrors the original.
    @return files           A list of all files under the directory.
    """
    if type(pathToDir) == str:
        pathToDir = pathToDir.decode('utf-8')

    pathList = []
    sPath = None
    for f in os.listdir(pathToDir):
        # Skip dot files.  This means that we avoid "." and ".." too...
        if f[0] == '.':
            continue

        fPath = os.path.join(pathToDir, f)
        if substitutePath:
            sPath = os.path.join(substitutePath, f)

        if os.path.isdir(fPath):
            pathList.extend(recursiveListDir(fPath, sPath))
        else:
            if sPath:
                pathList.append(sPath)
            else:
                pathList.append(fPath)

    return pathList


##############################################################################
def test_main():
    """OB_REDACT
    Our main function, which runs test code
    """
    import doctest
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    test_main()
