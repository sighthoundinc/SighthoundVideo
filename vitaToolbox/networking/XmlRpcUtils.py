#*****************************************************************************
#
# XmlRpcUtils.py
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

import xmlrpclib
import httplib

##############################################################################
class TimeoutTransport(xmlrpclib.SafeTransport):
    """An XML-RPC ServerProxy Transport supporting timeouts.

    Allows the client to recover if the server is blocking forever as in the
    following example:

    def testServer():
        from SimpleXMLRPCServer import SimpleXMLRPCServer
        import time

        def block():
            while True: time.sleep(60)

        s = SimpleXMLRPCServer(("localhost", 9999))
        s.register_function(block)
        s.serve_forever()

    def testClient():
        client = xmlrpclib.ServerProxy("http://localhost:9999",
                                       TimeoutTransport(5))
        client.block()

    """
    ###########################################################
    def __init__(self, timeout=0):
        """Initializer for TimeoutTransport

        @param  timeout The timeout to use on the socket, or 0
        """
        xmlrpclib.SafeTransport.__init__(self)
        self._timeout = timeout
        if self._timeout == 0:
            self._timeout = None


    ###########################################################
    def make_connection(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        self._connection = host, httplib.HTTPConnection(
                self.get_host_info(host)[0], timeout=self._timeout)
        return self._connection[1]
