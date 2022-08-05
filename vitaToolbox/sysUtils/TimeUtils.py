#*****************************************************************************
#
# TimeUtils.py
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

import time
import datetime
import locale

###########################################################
def getTimeAsMs():
    return int(time.time()*1000)


###########################################################
def formatTime(formatStr, timeStruct=None):
    if timeStruct is None:
        timeStruct = datetime.datetime.now()
    try:
        currentLocale = locale.getlocale()
    except:
        currentLocale = (None, None)
    if isinstance(timeStruct, datetime.date):
        retval = timeStruct.strftime(formatStr)
    else:
        retval = time.strftime(formatStr, timeStruct)
    if currentLocale is not None and currentLocale[1] is not None:
        retval = retval.decode(currentLocale[1])
    return retval


###########################################################
def getTimezoneOffset():
    """ Return timezone offset from UTC, in hours
    """
    ts = time.time()
    localTime = datetime.datetime.fromtimestamp(ts)
    utcTime = datetime.datetime.utcfromtimestamp(ts)
    diffInSeconds = (localTime - utcTime).total_seconds()
    diffInHours = diffInSeconds/(60*60)
    return diffInHours

###########################################################
def getDateAsString(ms, separator=""):
    """ Format the time
    """
    timeStruct = time.localtime(ms/1000.)
    formatStr = "%%Y%s%%m%s%%d" % (separator, separator)
    retVal = formatTime(formatStr, timeStruct).swapcase()
    return retVal

###########################################################
def getDebugTime(ms, needDate=False):
    _kTimeDebug = '%H:%M:%S.%f'
    _kDateTimeDebug = '%Y-%m-%d %H:%M:%S.%f'
    fmt = _kDateTimeDebug if needDate else _kTimeDebug

    timeStruct = datetime.datetime.fromtimestamp(ms/1000.)
    return formatTime(fmt,timeStruct)[:-3]


###########################################################
def getTimeAsString(ms, separator=":", noLeadZeros=True, use24Hrs=False):
    """ Format the time
    """
    timeStruct = time.localtime(ms/1000.)
    if use24Hrs:
        formatStr = "%%H%s%%M%s%%S" % (separator, separator)
    else:
        formatStr = "%%I%s%%M%s%%S %%p" % (separator, separator)
    retVal = formatTime(formatStr, timeStruct).swapcase()
    if retVal[0] == '0' and noLeadZeros:
        retVal = retVal[1:]
    return retVal

###########################################################
def dateToMs(date):
    return int(time.mktime(date.timetuple()) * 1000)
