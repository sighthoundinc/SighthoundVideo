#!/usr/bin/env python

#*****************************************************************************
#
# FileCreationTime.py
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

import os
import sys

# Strange import to avoid obfuscator warnings on Win, where this doesn't exist.
# ...need to also make sure that obfuscator doesn't obfuscate any of the
# identifiers related to this module.
try:
    exec 'import Carbon.File, Carbon.Files'
except:
    pass

def fileCreationTime(path):
    """Return the file creation time

    NOTE: For *nix this will return last modification time. We also
    fall back to last modification time if creation time is not present.

    @parm    path        Path to the file
    @return  createTime  Time of file creation in seconds since epoch
    """
    if type(path) == str:
        path = path.decode('utf-8')

    # The file must exist
    if not os.path.exists(path):
        return -1

    if sys.platform == 'darwin':
        # If we're on OSX we need to use the carbon API

        cFile = Carbon.File.FSRef(path) #PYCHECKER OK, pychecker can't find module on Win
        cInfo, _, _, _ =\
            cFile.FSGetCatalogInfo(Carbon.Files.kFSCatInfoCreateDate) #PYCHECKER OK, pychecker can't find module on Win

        if cInfo.createDate[1] != 0:
            # 2212122496 = -((1970-1904)*365 + 17) * (24*60*60) + 0x100000000L
            return cInfo.createDate[1] + 2212122496
        else:
            return int(os.stat(path).st_ctime)

    # Any other os
    return int(os.stat(path).st_ctime)


