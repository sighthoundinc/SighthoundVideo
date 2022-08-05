#!/usr/bin/env python

#*****************************************************************************
#
# BitmapFromFile.py
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

# Python imports...
import os

# Common 3rd-party imports...
from PIL import Image
import wx

# Local imports...

# Constants...


##############################################################################
def bitmapFromFile(f, platformBmps=True):
    """Create a wx.Bitmap from a file.

    We will use PIL to do the opening, then convert to a wx.Bitmap.  This
    shouldn't be needed (the wx constructor will open up an image file), but
    is used because wx.Bitmap seems to have trouble recognizing when a .png
    file has an alpha channel.  It seems to work OK with Photoshop-generated
    files, but doesn't seem to work with any of the files that I touch.

    This function also has the special feature of looking for platform-specific
    alternate bitmaps.

    @param  f             The path to the file to open; may also be a file-like
                          object (in that case, platformBmps is ignored).
    @param  platformBmps  If True and bitmaps were specified as paths to
                          bitmap files, we'll look for platform specific
                          bitmap files.  If they exist, they will be used.
                          See the main class docstring.
    """
    if type(f) == str:
        f = f.decode('utf-8')

    if platformBmps and isinstance(f, basestring):
        platformExt = ""

        if wx.Platform == "__WXMAC__":
            platformExt = "_Mac"
        elif wx.Platform == "__WXMSW__":
            platformExt = "_Win"

        if platformExt:
            fileName, fileExt = os.path.splitext(f)
            platformFileName = fileName + platformExt + fileExt
            if os.path.isfile(platformFileName):
                f = platformFileName

    img = Image.open(f)

    if img.mode == 'RGBA':
        bmp = wx.Bitmap.FromBufferRGBA(img.size[0], img.size[1], img.tobytes())
    else:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        bmp = wx.Bitmap.FromBuffer(img.size[0], img.size[1], img.tobytes())

    return bmp


