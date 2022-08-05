#!/usr/bin/env python

#*****************************************************************************
#
# MakeDocUrl.py
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
import sys

# Common 3rd-party imports...

# Toolbox imports...

# Local imports...
from appCommon.CommonStrings import kAppName
from appCommon.CommonStrings import kDocumentationUrl, kDocumentationIconUrl


if kDocumentationIconUrl:
    kContents = (
        "[InternetShortcut]\n"
        "URL=%s\n"
        "IconFile=%s\n"
        "IconIndex=1\n"
    )% (kDocumentationUrl, kDocumentationIconUrl)
else:
    kContents = (
        "[InternetShortcut]\n"
        "URL=%s\n"
    )% (kDocumentationUrl)



##############################################################################
def main(destDir):
    """This just writes the URL file based on constants from appCommon."""

    destPath = os.path.join(destDir, "%s Documentation.url" % kAppName)
    open(destPath, "w").write(kContents)


##############################################################################
if __name__ == '__main__':
    main(*sys.argv[1:])
