#!/usr/bin/env python

#*****************************************************************************
#
# LoadLibrary.py
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

# Imports...
import ctypes
import sys
import os
import traceback

libExtension = {
    'darwin': '.dylib',
    'win32': '.dll',
    'linux': '.so',
    'linux2': '.so',
    'cygwin': '.dll',
}

libFolder = {
    'darwin': 'lib',
    'win32': 'bin',
    'linux': 'lib',
    'linux2': 'lib',
    'cygwin': 'bin',
}

################################################################################
def _LoadLibrary(pathParam, libName):
    # If we are bundled, treat the path that was passed as relative to executable
    if hasattr(sys, 'frozen'):
        path = os.path.dirname(sys.executable)
        if pathParam is not None:
            path = os.path.join(path, pathParam)
    else:
        path = pathParam

    if path is not None:
      # Make sure we're only getting a directory, and not a file, for the path.
      path = path if os.path.isdir(path) else os.path.dirname(path)

      # Add the extension to the name of the library.
      libNameWithExt = libName + libExtension[sys.platform]

      # Create the path to the library now.
      libPath = os.path.join(path, libNameWithExt)
    else:
      libPath = libName + libExtension[sys.platform]


    # Load and return the library.
    try:
        res = ctypes.cdll.LoadLibrary(libPath)
    except:
        # print >> sys.stderr, "Attempting to load " + str(libPath) + " exc=" + traceback.format_exc()
        raise

    return res


################################################################################
def LoadLibrary(pathParam, libName):
    """Load the library at the absolute path "path" with the name "libName".

    If "path" is a file, then the library will be searched in the directory that
    the file is located.  This can happen if __file__ is passed in as an
    argument to "path".

    This function behaves differently when this project is packaged for
    delivery. Please read the note below for more details.

    @param    pathParam Path to the library relative to the executable.
                        Only considered if frozen (e.g. NOT running from source)
                        Empty, if None.
    @param    libName   Name of the library to load without the extension.

    @return   libObj    Library object loaded from ctypes.

    Note:  The "path" parameter should be the absolute path to the library
           "libName" when running from source. However, the "path" parameter
           is completely ignored when this code is bundled or packaged for
           delivery. Most of the time (if not all of the time) our libraries
           can be found in the same directory as the executable used to start
           or load the product. In this case, the "sys.executable" path is used
           to locate the library.

           This is just one general way to load libraries for all of our
           products.  If a project has different packaging requiremnts, then
           this function will have to be revisited, or a separate one needs to
           be made for that project.  This function was intended to be used by
           the Arden AI product source code, smartvideo.
    """

    altPaths = []
    if not hasattr(sys, 'frozen'):
        # we install the local build artifacts here
        for var in [ "_LOCAL", "_CONAN" ]:
            devLibFolder = os.getenv("SV_DEVEL_LIB_FOLDER"+var)
            if devLibFolder is not None:
                altPaths.append( devLibFolder )
                # if a relative path was provided, consider it relative to the above
                if pathParam is not None:
                    altPaths.append( os.path.join(devLibFolder, "..", pathParam ))
    altName = None if libName.startswith("lib") else "lib"+libName


    tried = ""
    params = [ (pathParam, libName) ]
    if altName is not None:
        params.append( (pathParam, altName) )

    for altPath in altPaths:
        params.append( (altPath, libName) )
        # try the same path and 'lib' prepended to the name
        if altName is not None:
            params.append( (altPath, altName) )

    for param in params:
        obj = None
        try:
            obj = _LoadLibrary(param[0], param[1])
        except:
            tried = tried + ";" + str(param[1]) + " in " + str(param[0])
            pass
        if obj is not None:
            return obj

    raise Exception("Could not load library " + libName + "; tried " + tried)

