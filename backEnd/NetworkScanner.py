#*****************************************************************************
#
# NetworkScanner.py
#     Helper class running periodic network scans for UPNP/ONVIF clients.
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

import time
import threading
import traceback
import Queue

kMaxLogDistance = 60.0 # log at least every 60 seconds
kMaxDurationWithoutLog = 0.5 # force log if scan took longer than that

##############################################################################
class NetworkScanner(threading.Thread):
    #---------------------------------------------------------------------------
    def __init__(self, logger, callback, period, manager, name):
        threading.Thread.__init__(self)
        self._manager = manager
        self._callback = callback
        self._period = period
        self._logger = logger
        self._stopped = False
        self._name = name
        self._event = threading.Event()
        self._lastLogTime = time.time()
        self._skippedLogs = 0
        self._requestQueue = Queue.Queue()
        self.start()


    #---------------------------------------------------------------------------
    def force(self):
        self._event.set()

    #---------------------------------------------------------------------------
    def shutdown(self):
        self._logger.info("Shutting down " + self._name + " manager ...")
        self._stopped = True
        self.force()
        if self.isAlive():
            self.join()
        self._logger.info("... done")

    #---------------------------------------------------------------------------
    def _processRequest(self, request):
        # only ONVIF can handle messages
        pass

    #---------------------------------------------------------------------------
    def run(self):
        _kMaxRequestsInOneIteration = 5
        self._logger.info("Starting " + self._name + " scanner")
        while not self._stopped:
            requestsProcessed = 0
            while not self._requestQueue.empty() and \
                    requestsProcessed < _kMaxRequestsInOneIteration:
                request = self._requestQueue.get()
                self._processRequest(request)
                requestsProcessed += 1

            start = time.time()
            changed = []
            gone = []
            devices = {}
            deviceStr = ""
            try:
                changed, gone = self._manager.pollForChanges()
                self._manager.activeSearch()
                if changed or gone:
                    devices = self._manager.getDevices()
                    deviceStr = " %d devices," % len(devices)
                    self._callback.onUpdate(devices, changed, gone)
            except:
                self._logger.error("Exception running %s scan. Error: %s" % (self._name, traceback.format_exc()))
            finish = time.time()
            duration = finish - start
            if duration > kMaxDurationWithoutLog or \
                finish - self._lastLogTime > kMaxLogDistance or \
                len(changed) > 0 or len(gone) > 0:
                self._logger.info("Scanning %s completed in %.02fsec.%s %d changed %d gone. Skipped %d times." %
                                (self._name, duration, deviceStr, len(changed), len(gone), self._skippedLogs))
                self._skippedLogs = 0
                self._lastLogTime = finish
            else:
                self._skippedLogs += 1
            self._event.clear()
            self._event.wait(self._period)
        self._logger.info("Finished " + self._name + " scanner")

##############################################################################
class OnvifNetworkScanner(NetworkScanner):
    #---------------------------------------------------------------------------
    def __init__(self, logger, callback, period, manager, name):
        NetworkScanner.__init__(self, logger, callback, period, manager, name)

    #---------------------------------------------------------------------------
    def setDeviceSettings(self, uuid, credentials, selectedIp):
        self._requestQueue.put( (uuid, credentials, selectedIp) )
        self.force()

    #---------------------------------------------------------------------------
    def _processRequest(self, request):
        # Only one type of request sent to us for now
        uuid, credentials, selectedIp = request
        if self._manager.setDeviceSettings(uuid, credentials, selectedIp):
            self._manager.activeSearch(uuid, True)
