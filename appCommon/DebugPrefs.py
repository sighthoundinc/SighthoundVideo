#*****************************************************************************
#
# DebugPrefs.py
#   Utility methods to access ad-hoc debug properties, which are stored in a file
#   editable by hand, so it can be dropped in at will
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
def getDebugPref(prefName, defaultValue, userDataDir):
    """Utility method to access configuration values which may be added to activate
       various debugging features.
       This will allow activation of certain debugging facilities by hand, with no UI
       involved
    """
    fLoc = os.path.join(userDataDir, 'debugPrefs')
    if os.path.isfile(fLoc):
        f = open(fLoc, 'r')
        if f is not None:
            try:
                content = f.readlines()
                # you may also want to remove whitespace characters like `\n` at the end of each line
                for line in content:
                    if line.lower().startswith(prefName.lower()+"="):
                        line = line[len(prefName)+1:].strip()
                        return line
            except:
                pass
            finally:
                f.close()
    return defaultValue

##############################################################################
def getDebugPrefScoped(prefName, scope, defaultValue, userDataDir):
    """ Same as getDebugPref, except attempting to read global setting
        "prefName" first, and then "prefName-scope"
    """
    res = getDebugPref(prefName, defaultValue, userDataDir)
    return getDebugPref(prefName+"-"+scope, res, userDataDir)


##############################################################################
def getDebugPrefAsInt(prefName, defaultValue, userDataDir):
    """getDebugPref, but returns int (or the default value, if conversion fails)
    """
    res = getDebugPref(prefName,
                None if defaultValue is None else str(defaultValue),
                userDataDir)
    if res is not None:
        try:
            res = int(res)
        except:
            res = defaultValue
    return res

##############################################################################
def getDebugPrefAsIntScoped(prefName, scope, defaultValue, userDataDir):
    """ Same as getDebugPrefInt, except attempting to read global setting
        "prefName" first, and then "prefName-scope"
    """
    res = getDebugPrefAsInt(prefName, defaultValue, userDataDir)
    return getDebugPrefAsInt(prefName+"-"+scope, res, userDataDir)

##############################################################################
def getDebugPrefAsFloat(prefName, defaultValue, userDataDir):
    """getDebugPref, but returns float (or the default value, if conversion fails)
    """
    res = getDebugPref(prefName,
                None if defaultValue is None else str(defaultValue),
                userDataDir)
    if res is not None:
        try:
            res = float(res)
        except:
            res = defaultValue
    return res

##############################################################################
def getDebugPrefAsFloatScoped(prefName, scope, defaultValue, userDataDir):
    """ Same as getDebugPrefFloat, except attempting to read global setting
        "prefName" first, and then "prefName-scope"
    """
    res = getDebugPrefAsFloat(prefName, defaultValue, userDataDir)
    return getDebugPrefAsFloat(prefName+"-"+scope, res, userDataDir)

