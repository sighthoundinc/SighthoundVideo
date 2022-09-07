#*****************************************************************************
#
# ThreadPoolMixIn.py
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
# https://github.com/sighthoundinc/SighthoundVideo
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

import sys

from ThreadPool import ThreadPool

""" Mixin to handle socket server connection in parallel by using a thread pool.
"""

###############################################################################
class RequestRunnable:
    """ The runnable executing the requests.
    """
    def __init__(self, mixin, request, clientAddress):
        """ Constructor.
        @param mixin           The parent mixin, where we process the request.
        @param request         The request object (socket connection).
        @param client_address  Where the request is coming from.
        """
        self._request = request
        self._clientAddress = clientAddress
        self._mixin = mixin

    def run(self):
        """ Handles the request (in the mixin).
        """
        self._mixin._handleRequest(self._request, self._clientAddress)


###############################################################################
class ThreadPoolMixIn:
    """Mix-in class to handle requests via a thread-pool. Goes together with
    the common SocketServer and its derivatives."""

    ###########################################################################
    def __init__(self, poolSize, queueSize=1024, daemonic=True,
                 threadNamePrefix=None, logger=None):
        """ Constructor. Makes it less of a mix-in actually.

        @param poolSize   Number of threads to run in the pool.
        @param queueSize  Size of the request queue. If the queue gets full the
                          process_request() calls will block.
        @param daemonic   True to create daemon threads.
        @param prefix     Prefix to use for naming threads.
        @param logger     Logger to request execution errors. Can be None.
        """
        self._threadPool = ThreadPool(poolSize, queueSize, daemonic,
                                      threadNamePrefix, logger)
        self._logger = logger


    ###########################################################################
    def shutdown(self, wait=False):
        """ Signals the threadpool to shut down.

        @param wait  True to wait for the threads processing current requests
                     to finish. False to return right after stop notification.
        """
        self._threadPool.shutdown(wait)


    ###########################################################################
    def _handleRequest(self, request, clientAddress):
        """ The actual request processing. Same way as ThreadMixIn does it.

        @param request        The request object.
        @param clientAddress  What TCP/IP end-point we're dealing with.
        """
        try:
            self.finish_request(request, clientAddress)
            self.close_request(request)
        except:
            if self._logger:
                self._logger.warning("request processing failed: %s" %
                                     sys.exc_info()[1])
            try:
                self.handle_error(request, clientAddress)
                self.close_request(request)
            except:
                # this can happen quite often, if the socket's prematurely
                # proper request shutdown won't happen of course, so we catch
                # this here
                if self._logger:
                    self._logger.warning("error cleanup failed: %s" %
                                         sys.exc_info()[1])


    ###########################################################################
    def process_request(self, request, client_address):
        """ To process a request. Gets packed into a runnable and then executed
        by one of the threads eventually. Blocks if the internal thread pool's
        queue with outstanding requests is full.

        @param request         The request object (socket connection).
        @param client_address  Where the request is coming from.
        @return                False if the instance has been shut down.
        """
        runnable = RequestRunnable(self, request, client_address)
        return self._threadPool.schedule(runnable)
