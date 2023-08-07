#!/usr/bin/env python

#*****************************************************************************
#
# GetLaunchParameters.py
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


# Python imports...
import os
import sys

# Local imports...
from appCommon.CommonStrings import kExeName
from appCommon.CommonStrings import kBackendExeName


#####################################################################
def getLaunchParameters(name=kBackendExeName):
    """Return parameters that will call the launcher.

    @param  name        A name to attempt to give to the launched process.
    @return openParams  A list of parameters to give to Popen.
    """
    frozen = getattr(sys, "frozen", None)

    # Launch the back end application
    if frozen is not None:
        # Windows and OSX Built -

        # On Windows, Replace the name--we have a copy of the executable so it
        # shows up better in the Task Manager.
        exeDir = os.path.split(sys.executable)[0]

        if sys.platform == 'darwin':
            name = kExeName

        backendExeName = os.path.join(exeDir, name)

        # On frozen windows, the sys.executable is our .exe file.
        # Re-launch it with a --backEnd flag to launch the backend.
        # On frozen Mac the frontend is also the backend, the actual launch
        # points have to ensure that the --backend flag is added to the params
        openParams = [backendExeName]
    else:
        # Windows and OSX non-built -
        openParams = [sys.executable, "FrontEndLaunchpad.py"]

    return openParams


