#! /usr/local/bin/python

#*****************************************************************************
#
# XmlRpcClientIdWrappers.py
#   XML RPC utility methods and classes
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

# Python imports...
import os
import sys
import threading
import time
import xmlrpclib

from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

from xml.parsers.expat import ExpatError

# Toolbox imports...
from vitaToolbox.loggingUtils.LoggingUtils import formatStackConcisely
from appCommon.CommonStrings import kExecAlertThreshold


# When we pass retry info, we always prefix it with this magic string so
# we can tell it's retry info.  This allows old servers to communicate
# with new clients and the other way around (it seems safe enough that
# this string will prefix the first arg).
kRetryPrefix = "VdvRetryInfo "

# We'll try up to this many times.
kNumTries = 10

# We'll clear the cache every this many calls.
kCleanEvery = 500

# When we clean, we'll clean enteries older than this (seconds)
kCacheExpireTime = 60

_kExecAlertThreshold = float(kExecAlertThreshold)

##############################################################################
class _ServerProxyLocalStorage(threading.local):
    """Thread local storage for ServerProxyWithClientId.

    ServerProxyWithClientId effectively needs a unique ID per method call that
    it can send to the remote server.  This allows the server to detect
    duplicate requests for the same method call and avoid performing the same
    action twice.

    Method IDs need to be completely unique, even if there are several
    processes all trying to talk to the same server.  Luckily, we only
    communicate on one machine, so we can use the PID to help facilitate this.
    We then use thread-local storage to get yet more unique (note that I don't
    think we ever actually communicate on more than one thread in a given
    process, but I haven't tracked down every XMLRPC call (especially those
    called in some indrect way with wx), so I'm being super paranoid.

    >>> l = _ServerProxyLocalStorage()
    >>> ids = []
    >>> class myThread(threading.Thread):
    ...     def run(self):
    ...         ids.append(l.clientId)
    >>> t1 = myThread()
    >>> t2 = myThread()
    >>> t1.start()
    >>> t2.start()
    >>> len(ids)
    2
    >>> ids[0] == ids[1]
    False
    >>> ids[0] == l.clientId
    False
    >>> ids[1] == l.clientId
    False
    """

    def __init__(self):
        """_ServerProxyLocalStorage constructor."""
        super(_ServerProxyLocalStorage, self).__init__()

        # This ought to be completely unique on a given computer.  There
        # should be only one process with a given process ID, and within
        # that each thread should get a different thread local object (so we
        # can use that object's unique ID to differentiate threads).
        self.clientId = "%x_%x" % (os.getpid(), id(threading.currentThread()))

        # We'll just increment request numbers within a thread.
        self.requestNum = 0;


class ServerProxyWithClientId(xmlrpclib.ServerProxy):
    """Wrap xmlrpclib.ServerProxy to send retry info.

    Basically, we have to know that we're talking to a XMLRPCServerWithClientId.
    We'll prepend some retry info as the first argument to every call.  That'll
    be stripped off on the other side and is usued to detect retries.  Here's
    how things work:

    1. If this is a new request and the server gets it, it will do it.
    2. If the communcation failed on the way _to_ the server, we'll get an error
       (I think), then we'll try again.  Assuming the 2nd one gets through, then
       the request will look new to the server and it will do it.
    3. If the communication failed on the way back form the server, we'll also
       get an error.  When we send the retry, the server will realize that it
       was the same request again (which is why we have the retry info) and
       will return us back the result from its cache.

    The server caches only the most recent request from each client.
    """

    ###########################################################
    def __init__(self, *args, **kwargs):
        """ServerProxyWithClientId constructor.

        This just extends xmlrpclib.ServerProxy, so all arguments match
        that class.  We just do some of our own init.
        """
        # Start out not knowing if the serer is compatible (None).  We'll
        # move to True/False later once we've determined things.
        self.__isCompatibleServer = None

        self.__local = _ServerProxyLocalStorage()
        xmlrpclib.ServerProxy.__init__(self, *args, **kwargs)


    ###########################################################
    def __checkIsCompatibleServer(self):
        """Check if the server is compatible.

        We'll wait to do the check till the first call to __getattr__(), since
        people aren't expecting communcation with the server during the
        constructor.  NOTE: still might want to even wait until the first
        actual function call, but during __getattr__ is probably enough.

        @return isCompatible  True if the server is compatible.
        """
        if self.__isCompatibleServer is None:
            self.__isCompatibleServer = False
            try:
                if self.IsXMLRPCServerWithClientId(): #PYCHECKER OK: It's really there.
                    self.__isCompatibleServer = True
                else:
                    # Should never have the function and have it return False.
                    assert False
            except xmlrpclib.Fault, e:
                print >>sys.stderr, \
                    "Not talking to a server that supports retries: %s" % str(e)
        return self.__isCompatibleServer


    ###########################################################
    def __getattr__(self, attrName):
        """The implementation of xmlrpclib.ServerProxy.

        This function is supposed to return a function pointer that will
        call the remote server.  We override to add the retry info to all calls.
        """
        superfn = xmlrpclib.ServerProxy.__getattr__(self, attrName)

        if self.__checkIsCompatibleServer():
            def fn(*args):
                start = time.time()
                clientId = self.__local.clientId
                requestNum = self.__local.requestNum
                self.__local.requestNum += 1

                for retryNum in xrange(kNumTries):
                    try:
                        retval = superfn("%s%s %d" % (kRetryPrefix, clientId, requestNum), *args)
                        duration = time.time()-start
                        if duration > _kExecAlertThreshold:
                            print >>sys.stderr, "XMLRPC request %s took %.2f sec in %d tries" % (str(attrName), duration, retryNum)
                        return retval
                    except (ExpatError, xmlrpclib.ProtocolError), e:
                        if retryNum == kNumTries-1:
                            print >>sys.stderr, "Client %s giving up: %s" % (clientId, str(e))
                            raise
                        else:
                            # Don't print an error for ping, since we call
                            # it as we're starting up and shutting down and
                            # errors are expected then.
                            # ...also quit, where we were already ignoring
                            # ExpadErrors
                            if attrName not in ('quit', 'ping'):
                                time.sleep(.05)

                                print >>sys.stderr, "Client %s retry #%d: %s" % (clientId, retryNum, str(e))

                                # Print out a stack trace so we can debug
                                # if we get this unexpectedly.
                                print >>sys.stderr, formatStackConcisely()
                            else:
                                # For ignored errors we just raise what we got.
                                raise
            return fn
        else:
            return superfn


# Cache is keyed by client ID.  Values look like this:
# (requestId, result, False, time)
_cache = {}


class CrossDomainXMLRPCRequestHandler(SimpleXMLRPCRequestHandler ):
#                                      SimpleHTTPRequestHandler):
    """ SimpleXMLRPCRequestHandler subclass which attempts to do CORS

    CORS is Cross-Origin-Resource-Sharing (http://www.w3.org/TR/cors/)
    which enables xml-rpc calls from a different domain than the xml-rpc server
    (such requests are otherwise denied)
    """
    def do_OPTIONS(self):
        """ Implement the CORS pre-flighted access for resources """
        self.send_response(200)
        #self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-METHODS", "POST,GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "origin,content-type,X-Requested-With")
        #self.send_header("Access-Control-Max-Age", "60")
        self.send_header("Content-length", "0")
        self.end_headers()

    #def do_GET(self):
    #    """ Handle http requests to serve html/image files only """
    #    print self.path, self.translate_path(self.path)
    #    permitted_extensions = ['.html','.png','.svg','.jpg', '.js']
    #    if not os.path.splitext(self.path)[1] in permitted_extensions:
    #        self.send_error(404, 'File Not Found/Allowed')
    #    else:
    #        SimpleHTTPRequestHandler.do_GET(self)

    def end_headers(self):
        """ End response header with adding Access-Control-Allow-Origin

        This is done to enable CORS request from all clients """
        self.send_header("Access-Control-Allow-Origin", "*")
        SimpleXMLRPCRequestHandler.end_headers(self)

class XMLRPCServerWithClientId(SimpleXMLRPCServer):
    """A SimpleXMLRPCServer that wraps all registered functions with retry info.

    This works together with ServerProxyWithClientId to try to make XML RPC
    reliable even in the context of a slightly flaky communication method,
    like if a rogue firewall or virus scanner is interfering with us.
    """

    ###########################################################
    def __init__(self, *args, **kwargs):
        """XMLRPCServerWithClientId constructor.

        See SimpleXMLRPCServer.
        """
        # To avoid spewing warnings, we only warn once per function call.
        self.__warnedAbout = set()
        self.__numCalls = 0

        SimpleXMLRPCServer.__init__(self, *args, **kwargs)

        # Make it easy for client to tell we're the right server; client
        # may try to call us before retry info is present, so don't warn...
        self.register_function(self.IsXMLRPCServerWithClientId,
                               "IsXMLRPCServerWithClientId")
        self.__warnedAbout.add("IsXMLRPCServerWithClientId")


    ###########################################################
    @staticmethod
    def IsXMLRPCServerWithClientId(*args):
        """Return True; ignore any args"""
        return True


    ###########################################################
    def register_function(self, fn, fnName):
        """Wrap register function to add add retry info arg to each function.

        The function will be wrapped to strip away the retry info (after
        checking it).
        """
        # This function wraps the real function with all the retry logic...
        def fn_wrapper(*args):
            # Handle the case where the person calling us doesn't send us
            # the retry info.  This could happen because an old version is
            # talking with a new version or because some 3rd party app is
            # running...
            if not (args and isinstance(args[0], basestring) and
                    args[0].startswith(kRetryPrefix)):
                if fnName not in self.__warnedAbout:
                    print >>sys.stderr, \
                          "Missing retry info for call to %s" % fnName
                    self.__warnedAbout.add(fnName)
                return fn(*args)

            _, clientId, requestId = args[0].split()
            args = args[1:]

            if clientId in _cache:
                cachedRequestId, cachedResult, isException, _ = _cache[clientId]
                if cachedRequestId == requestId:
                    print >>sys.stderr, \
                        "Received duplicate request for %s, %s" % \
                        (clientId, cachedRequestId)
                    if isException:
                        raise cachedResult
                    return cachedResult

            self.__numCalls += 1
            if (self.__numCalls % kCleanEvery) == 0:
                for thisClientId in _cache.keys():
                    _, _, _, lastTime = _cache[thisClientId]
                    timeDelta = time.time() - lastTime
                    if timeDelta > kCacheExpireTime:
                        del _cache[thisClientId]

            try:
                result = fn(*args)
                _cache[clientId] = (requestId, result, False, time.time())
                return result
            except BaseException, e:
                _cache[clientId] = (requestId, e, True, time.time())
                raise

        SimpleXMLRPCServer.register_function(self, fn_wrapper, fnName)


##############################################################################
def _runTests():
    """OB_REDACT
       Run any self-tests.  This will be removed from obfuscated code.
    """
    import doctest
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    _runTests()
