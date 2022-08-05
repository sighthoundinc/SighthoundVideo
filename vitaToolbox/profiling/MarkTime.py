#!/usr/bin/env python

# ----------------------------------------------------------------------
#  Copyright (C) 2007 Vitamin D, Inc. All rights reserved.
#
#  The information and source code contained herein is the
#  exclusive property of Vitamin D, Inc. No part of this software
#  may be used, reproduced, stored or distributed in any form,
#  without explicit written authorization from Vitamin D, Inc.
# ----------------------------------------------------------------------

# Python imports...
from collections import defaultdict
import operator
import time
import datetime

# Common 3rd-party imports...


# Constants...

# Set to True to enable...
_kEnable = False

# Labels given when reporting each indent level...
_kIndentLabels = {-1: " total", 0: "", 1: " start"}



# Globals...

# ...our current indentation level
_indentLevel = 0

# The last time that something happened, per indent level...
_lastTimes = [None]

# Total time taken, per description...
_totalDict   = defaultdict(int)


##############################################################################
def resetMarkedTime():
    """Reset the state of the marktime functions."""
    global _indentLevel, _lastTimes, _totalDict
    _indentLevel = 0
    _lastTimes = [None]
    _totalDict = defaultdict(int)


##############################################################################
def markTime(desc, indent):
    """Mark a point in time, for profiling purposes.
    
    @param  desc    The description of this point in time.  If indent is 1, this
                    is the start of a duration.  If indent is -1, this is the
                    end of the duration.  If indent is 0, this is an interrim
                    mark.
    @param  indent  See the description of 'desc' for details.
    """
    if not _kEnable:
        return
    
    global _indentLevel
    
    # Get the time right now...
    nowTime = time.time()
    
    # The label is modified with a description of whether this is the
    # start or the end of a duration...
    label = _kIndentLabels[indent]
    desc += label
    
    # Show relative time between the last mark and this one, unless this is
    # the end of a time period and there were no interrim marks.
    if (indent >= 0) or (_lastTimes[-1] is not None):
        # Get the last time at the current indentation level...
        lastTime = _lastTimes[-1]
        
        # If nothing at this indent level, get the last time at the level
        # up; if this is the _very_ first time we saw, just start with
        # nowTime...
        if lastTime is None:
            if len(_lastTimes) == 1:
                lastTime = nowTime
            else:
                lastTime = _lastTimes[-2]
        
        # Now, we can find out how much time has passed...
        delta = (nowTime - lastTime) * 1000
        
        # Mark this time so next time can find the delta too...
        _lastTimes[-1] = nowTime
        
        # If we're indenting, start a new level...
        if indent > 0:
            _lastTimes.append(None)
        
        # Print the info, keeping track in our totals too...
        #print "%-54s%.2f" % ('.' * (2*_indentLevel) + "before " + desc, delta)
        _totalDict["before " + desc] += delta
    
    # Now, adjust indent level...
    _indentLevel += indent
    
    # If we're unindenting, we want to summarize what we just saw...
    if indent < 0:
        _lastTimes.pop()
        delta = (nowTime - _lastTimes[-1]) * 1000
        _lastTimes[-1] = nowTime
        
        #print "%-54s%.2f" % ('.' * (2*_indentLevel) + desc, delta)
        _totalDict[desc] += delta


##############################################################################
def summarizeMarkedTime():
    """Sumarrize (print totals) for all the time that was marked."""
    
    if not _kEnable:
        return
    print '\n'.join(map(str, sorted(_totalDict.items(), key=operator.itemgetter(1, 0))))


##############################################################################
""" Help profiling execution duration of chunks of code
"""
class TimerLogger:
    def __init__(self, descr, paused=False):
        self._cumulative = datetime.timedelta(0,0,0)
        self._descr = descr
        self._start = datetime.datetime.now()
        self._paused = paused

    def pause(self):
        if not self._paused:
            self._cumulative = self.diff()
            self._paused = True

    def start(self):
        if self._paused:
            self._start = datetime.datetime.now()
            self._paused = False

    def diff(self):
        if self._paused:
            return self._cumulative
        return datetime.datetime.now() - self._start + self._cumulative

    def diff_sec(self):
        return self.diff().total_seconds()

    def diff_ms(self):
        return int(self.diff().total_seconds()*1000)


    def status(self):
        return self._descr + " took " + str(self.diff_ms()) + "ms"

