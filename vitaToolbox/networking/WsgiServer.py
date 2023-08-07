#*****************************************************************************
#
# WsgiServer.py
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

import sys, threading, time

from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
from vitaToolbox.loggingUtils.LoggingUtils import EmptyLogger
from vitaToolbox.threading.ThreadPoolMixIn import ThreadPoolMixIn

###############################################################################
class NoRequestLogWSGIRequestHandler(WSGIRequestHandler):
    """ To suppress excessive logging of every request.
    """
    def log_request(self, code='-', size='-'):
        pass


###############################################################################
class _WsgiServer(ThreadPoolMixIn, WSGIServer):
    """ Default WSGI server, multi-threaded and also listening to accept
        errors, so we can end an instance if such a thing happens.
    """

    allow_reuse_address = True

    ###########################################################
    def __init__(self, serverAddress, app, threadPoolSize,
                 handlerClass=WSGIRequestHandler,
                 serverNameOverride=None, logger=None):
        """ Constructor

        @param serverAddress       Address where to run the server at.
        @param app                 The WSGI application instance.
        @param threadPoolSize      Number of threads to run in parallel.
        @param serverNameOverride  To override the server name. Can be None.
        @param logger              Logger for request errors. Can be None.
        """
        self._serverNameOverride = serverNameOverride
        self.timeout = .1  # to poll every 100 ms for shutdown flag
        WSGIServer.__init__(self, serverAddress, handlerClass,
                            bind_and_activate=False)
        try:
            self.server_bind()
            if serverNameOverride:
                self.server_name = serverNameOverride
            self.server_activate()
        except:
            self.server_close()
            raise
        ThreadPoolMixIn.__init__(self, threadPoolSize, threadNamePrefix="wsgi",
                                 logger=logger)
        self.set_app(app)


###############################################################################
class WsgiServer(threading.Thread):
    """ App-server capable in trying different addresses based on generators.
        Being a thread in always runs in the background. Notice that it must
        actually run, no activity happens during construction!
    """

    ###########################################################
    def __init__(self, addressInfos, app, notify=None, minUptime=10,
                 sharedLogger=None, threadPoolSize=20, serverName=None):
        """ Constructor.

        @param addressInfos    Generator which produces (address, delay) pairs
                               pairs, so e.g. multiple ports can be tried and
                               delays after each attempt can be completely
                               controlled based on the desired policy.
        @param app             The WSGI application. Be aware of the
                               multi-threaded nature, some non-thread-safe
                               application sharing some state might have an
                               issue with that!
        @param notify          Notification function, receiving the server
                               address (host, port) after the server got
                               started. Remember that this will be called from
                               a different thread, so some locking may be
                               required.
        @param minUptime       Minimum uptime for a server instance, basically
                               to prevent hotlooping. Uptime is measured after
                               a server has been started successfully, and not
                               before opening the port.
        @param sharedLogger    The logger to use. It should be synchronized
                               since multiple threads will be using it at the
                               same time.
        @param threadPoolSize  Number of request processing threads to run.
        @param serverName      Explicit server (host) name, None for auto.
        """
        threading.Thread.__init__(self)
        logger = sharedLogger if sharedLogger is not None else EmptyLogger()
        self._addressInfos = addressInfos
        self._app = app
        self._notify = notify
        self._minUptime = minUptime
        self._logger = logger
        self._shutDownEvent = threading.Event()
        self._server = None
        self._serverLock = threading.RLock()
        self._threadPoolSize = threadPoolSize
        self._serverName = serverName


    ###########################################################
    def shutdown(self, wait=60):
        """ Shuts down the currently running server instance or interrupts
        some idle time in the middle of them.

        @param wait  Number of seconds to wait for the thread to join.
        @return      True if the thread ended. False if still active.
        """
        self._logger.info("shutting down...")
        self._shutDownEvent.set()
        self._serverLock.acquire()
        if self._server:
            try:
                self._server.shutdown = True
            except:
                pass
        self._serverLock.release()
        if wait:
            self.join(wait)
        self._logger.info("shutdown completed")
        return not self.isAlive()


    ###########################################################
    def run(self):
        """ The thread's main loop.
        """
        while not self._shutDownEvent.isSet():
            startedAt = time.time()
            # get the next address to try to open, plus the time we should wait
            # if that doesn't work out
            try:
                serverAddressInfo = self._addressInfos.next()
            except StopIteration:
                self._logger.warn("no more server addresses!?")
                return
            serverAddress = serverAddressInfo[0]
            retryDelay    = serverAddressInfo[1]
            # launch the server (meaning opening the server socket)
            self._logger.info(
                "launching server %s with %d request thread(s)..." %
                (serverAddress, self._threadPoolSize))
            self._serverLock.acquire()
            try:
                self._server = _WsgiServer(serverAddress, self._app,
                    self._threadPoolSize, NoRequestLogWSGIRequestHandler,
                    serverNameOverride=self._serverName, logger=self._logger)
            except:
                self._logger.error("server creation error (%s)" %
                                   sys.exc_info()[1])
                self._shutDownEvent.wait(retryDelay)
                continue
            finally:
                self._serverLock.release()
            self._logger.info("server running %s" % str(self._server.server_address))
            if self._notify is not None:
                try:
                    self._notify(self._server.server_address)
                except:
                    self._logger.error("notify error: %s" % sys.exc_info[1])
            # start serving, in a loop, so we can count the overall requests
            requestCount = 0
            while not self._shutDownEvent.isSet():
                requestCount += 1
                try:
                    self._server.handle_request()
                except:
                    # since the server is backed by a thread-pool errors
                    # bubbling up here can only mean that the server (socket)
                    # itself has gone bad (or something close to it), i.e. we
                    # have to consider it to be invalid and have it recreated
                    self._logger.error("request initiation error (%s)" %
                                       sys.exc_info()[1])
                    break
            self._logger.info("%d requests served" % requestCount)
            # clean up the server
            self._serverLock.acquire()
            try:
                self._server.server_close()
            except:
                pass
            self._server = None
            self._serverLock.release()
            self._logger.info("server closed")
            # wait a minimum amount of time to avoid hot-looping, just in case
            # the server's lifetime is always short due to some circumstance
            extraIdleTime = self._minUptime - (time.time() - startedAt)
            if 0 < extraIdleTime:
                self._logger.info("waiting for %.3f seconds..." % extraIdleTime)
                self._shutDownEvent.wait(extraIdleTime)
                continue


###############################################################################
def makeServerAddressInfos(ports, nextDelay, repeatDelay, address="127.0.0.1"):
    """ Address generator which loops through a given set of ports and repeats
    this procedure indefinitely.

    @param ports        The port generator. Must produce at least one entry.
    @param nextDelay    Number of seconds to wait between each port.
    @param repeatDelay  Number of seconds to wait when the end of the list has
                        been reached and things will be tried all over again.
    @param address      The IP/host to bind to.
    """
    while True:
        nextPort = None
        for port in ports:
            if nextPort is None:
                nextPort = port
                continue
            yield ((address, nextPort), nextDelay)
            nextPort = port
        yield ((address, nextPort), repeatDelay)
