#*****************************************************************************
#
# webstuff.py
#     various utilities for web server
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

import sys, os

def _get_exe_path(exe,sub):
    if hasattr(sys, "frozen"):
        return os.path.abspath(os.path.join(os.path.dirname(sys.executable), exe))
    dir=os.getenv("SV_DEVEL_LIB_FOLDER_CONAN")
    if dir is None:
        dir=os.path.dirname(__file__)
    return os.path.join(dir, "..", sub, exe)

def server_exe():
    suffix = ".exe" if "win32" == sys.platform else ""
    return _get_exe_path("Sighthound Web"+suffix, "bin")

def shared_library():
    if "win32" == sys.platform:
        return None
    return _get_exe_path("Sighthound Web", "bin")

def openssl_exe():
    if "win32" == sys.platform:
        return _get_exe_path("openssl.exe", "bin")
    return "openssl" # use OSX's OpenSSL

def normalize_path(path, isdir=False):
    if "win32" == sys.platform:
        path = path.replace('\\', '/')
    if isdir and not path.endswith('/'):
        path += '/'
    return path
