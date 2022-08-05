#*****************************************************************************
#
# DebugLogManager.py
#    loading debug preferences (used for enhanced logging/troubleshooting)
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


from vitaToolbox.loggingUtils.LoggingUtils import getLogger, kLogLevelInfo
from videoLib2.python.VideoLibUtils import SetVideoLibDebugConfig, SetVideoLibDebugConfigSimple
from appCommon.DebugPrefs import getDebugPrefAsIntScoped, getDebugPrefScoped


class DebugLogManager(object):
    def __init__(self, moduleName, userDataDir):
        logLevel = getDebugPrefAsIntScoped("cameraLogLevel", moduleName, kLogLevelInfo, userDataDir)
        self._logDrivenByConfig = False
        if logLevel < 0:
            modules=getDebugPrefScoped("cameraLogModules", moduleName, None, userDataDir)
            logFfmpeg = getDebugPrefAsIntScoped("cameraLogFfmpeg", moduleName, 0, userDataDir)
            SetVideoLibDebugConfigSimple(logFfmpeg>0, modules);
            self._logDrivenByConfig = True

    def SetLogConfig(self, configStruct):
        if not self._logDrivenByConfig:
            SetVideoLibDebugConfig(configStruct)

