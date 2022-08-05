#*****************************************************************************
#
# ThreadPool.py
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

import sys, threading
import Queue

from vitaToolbox.loggingUtils.LoggingUtils import EmptyLogger

class ThreadPool:
    """Thread-pool implementation."""

    ###########################################################################
    def __init__(self, poolSize, queueSize=1024, daemonic=True,
                 threadNamePrefix=None, logger=None):
        """ Constructor. Makes it less of a mix-in actually.

        @param poolSize          Number of threads to run in the pool.
        @param queueSize         Size of the runnable queue.
        @param daemonic          True to create daemon threads.
        @param threadNamePrefix  Prefix to use for naming threads.
        @param logger            Logger to report trouble. Can be None.
        """
        self._threads = []
        self._queue = Queue.Queue(queueSize)
        self._running = True
        self._logger = EmptyLogger() if logger is None else logger
        if threadNamePrefix is None:
            threadNamePrefix = "threadpool"
        while 0 < poolSize:
            poolSize -= 1
            thread = threading.Thread(target=self._threadRun)
            thread.setDaemon(daemonic)
            thread.setName("%s-%03d" % (threadNamePrefix, poolSize))
            thread.start()
            self._threads.append(thread)


    ###########################################################################
    def shutdown(self, wait=False):
        """ Signals all of the threads to quit. Does not wait for them to end
        through, since they might be blocking for a very long time if e.g. one
        gets stuck on some network issue.

        @param wait  True to wait for the threads to end. False to just signal.
        @return      False if some thread is still alive. True if all are done.
        """
        self._running = False
        for _ in range(0, len(self._threads)):
            self._queue.put(None)
        if wait:
            for thread in self._threads:
                thread.join()
        for thread in self._threads:
            if thread.isAlive():
                return False
        return True


    ###########################################################################
    def _threadRun(self):
        """ The function each thread executes. Basically just polling on the
        shared queue for things to run until told to quit.
        """
        while self._running:
            runnable = self._queue.get(block=True)
            if runnable is None:
                break
            try:
                runnable.run()
            except:
                try:
                    self._logger.error("UNCAUGHT: %s" % sys.exc_info()[1])
                except:
                    pass


    ###########################################################################
    def schedule(self, runnable, block=True):
        """ To schedule something runnable.

        @param  runnable  The function to run. No arguments, no return value.
        @param  block     False to return if the queue is full.
        @return           True on success. False if the queue is full or if the
                          instance has been shut down.
        """
        if not self._running:
            return False
        try:
            self._queue.put(runnable, block)
            return True
        except Queue.Full:
            return False
