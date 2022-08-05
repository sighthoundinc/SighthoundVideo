import sys
import time

#*****************************************************************************
#
# QueueStats.py
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

from vitaToolbox.profiling.StatItem import StatItem


##############################################################################
""" A simple aggregator for generic queue statistics, such as:
    - max and average size
    - max and average message processing size
    - max and average time-in-queue for the message
    - number of events where queue exceeded configured thresholds
"""
class QueueStats(object):
    ###########################################################
    """Creates the stats object

    @param  logger              logging sink
    @param  statsInterval       how often to output stats, in seconds
    @param  alertsInterval      max frequency of alerts ... currently unused
    @param  maxQSize            queue size over this value is considered an error condition
    @param  maxExecTime         exec time over this value is considered an error condition
    """
    def __init__(self, logger, statsInterval, alertInterval, maxQSize, maxExecTime):
        self._logger = logger
        self._statsInterval = statsInterval
        self._alertInterval = alertInterval
        self._maxQSize = maxQSize
        self._maxExecTime = maxExecTime
        self._alertsSkipped = 0
        self._lastAlertTime = 0
        self._reset()

    ###########################################################
    """ Reset stats to initial values
    """
    def _reset(self):
        self._lastStatsTime = time.time()
        self._eventCounter = 0
        self._qSize = StatItem("qSize", None, "%d", "%.1f")
        self._qSize.setLimit((0, self._maxQSize))
        self._execTime = StatItem("execTime", None, "%.2f", "%.1f")
        self._execTime.setLimit((0, self._maxExecTime))
        self._timeInQueue = StatItem("timeInQueue", None, "%.2f", "%.1f")
        self._msgCounts = {}

    ###########################################################
    def logStats(self, reset=False):
        """ Logs the stats, and optionally resets them
        """
        if self._qSize.count() == 0:
            return

        self._logger.info(
            "QueueStats: msgsCount=%d %s %s %s"
            % (self._qSize.count(),
               str(self._qSize),
               str(self._execTime),
               str(self._timeInQueue)))
        msgs = [str(k)+":"+str(self._msgCounts[k]) for k in sorted(self._msgCounts)]
        self._logger.info( "MessageStats: " + ",".join(msgs))
        if reset:
            self._reset()

    ###########################################################
    def update(self, qSize, msgId, timeInQueue, execTime, extraInfo=""):
        """ Update the stats after processing a queue message

        @param qSize            current queue size
        @param msgId            message type
        @param timeInQueue      how long this message spent in queue, in seconds
        @param execTime         time to process the message, in seconds
        @param extraInfo        extra information to relate in case of alert
        """
        if not qSize is None:
            self._qSize.report(qSize)
        self._execTime.report(execTime)
        if not timeInQueue is None:
            self._timeInQueue.report(timeInQueue)

        count, maxTime = self._msgCounts.get(msgId,(0,0))
        self._msgCounts[msgId] = ( count + 1, max(maxTime, round(execTime, 2) ) )

        if self._maxExecTime < execTime:
            # Alert about this!
            if time.time()-self._lastAlertTime >= self._alertInterval or self._alertInterval == 0:
                self._logger.warning("Execution of message %d took %.2f sec, extraInfo=%s, %d skipped alerts" % (msgId, execTime, extraInfo, self._alertsSkipped))
                self._lastAlertTime = time.time()
                self._alertsSkipped = 0
            else:
                self._alertsSkipped += 1

        if self._statsInterval > 0 and \
           self._lastStatsTime + self._statsInterval <= time.time():
            self.logStats(True)




