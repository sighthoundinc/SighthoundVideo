#*****************************************************************************
#
# HttpClient.py
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

import base64
import httplib
import ssl
import sys
import urlparse

from vitaToolbox.loggingUtils.LoggingUtils import EmptyLogger


###############################################################################

# Default timeout for HTTP requests, in seconds.
_kDefaultTimeout = 30

# Number of bytes to read at a time.
_kReadSize = 1024

_kEmptyLogger = EmptyLogger()

###############################################################################
class HttpClient(object):
    """ Client able to deal both with HTTP and HTTPS requests.
    """

    ###########################################################
    def __init__(self, timeout=_kDefaultTimeout, logger=_kEmptyLogger):
        """ Constructor.

        @param  timeout  Timeout for a request, in seconds.
        @param  logger   The logger to use.
        """
        self._timeout = timeout
        self._logger = logger


    ###########################################################
    def _request(self, method, url, body=None, headers={}, output=None):
        """ Performs an HTTP or HTTPS request.

        @param  method   The request method (GET, POST, ...).
        @param  url      Fully qualified URL.
        @param  body     Content to submit. For POST, PUT, otherwise ignored.
                         The content length header is created automatically.
        @param  headers  Optional headers for the request.
        @param  output   Function to call with (data, length), data being a
                         chunk of data read. Length containing the content
                         length or -1 if unknown. Aborts when False is returned.
        @return          The status code (200, 404, etc). None on error.
        @return          Response body, None if output is set. Or error message.
        @return          Response headers. None on error.
        """
        try:
            u = urlparse.urlparse(url)
        except:
            err = "invalid URL '%s' (%s)" % (url, sys.exc_info()[1])
            self._logger.error(err)
            return None, err, None
        try:
            if body:
                headers["Content-Length"] = len(body)
            kargs = {}
            kargs["timeout"] = self._timeout
            if "https" == u.scheme.lower():
                port = u.port if u.port else 443
                try:
                    getattr(ssl, "_create_unverified_context")
                    kargs["context"] = ssl._create_unverified_context()
                except:
                    pass
                conn = httplib.HTTPSConnection(u.hostname, port, **kargs)
            else:
                port = u.port if u.port else 80
                conn = httplib.HTTPConnection(u.hostname, port, **kargs)
            path = u.path if u.path else ""
            if u.query:
                path += "?" + u.query
            if u.username and u.password:
                cred = "%s:%s" % (u.username, u.password)
                auth = base64.b64encode(cred).decode("ISO-8859-1")
                headers['Authorization'] = 'Basic %s' % auth
            method = method.upper()
            self._logger.info("sending %s request to %s ..." % (method, url))
            conn.request(method, path, body, headers)
            rsp = conn.getresponse()
            try:
                contLen = int(rsp.getheader("Content-Length"))
            except:
                contLen = -1
            if output:
                while True:
                    data = rsp.read(_kReadSize)
                    if not data:
                        break
                    if not output(data, contLen):
                        return None, "output abort", None
                data = None
            else:
                data = rsp.read()
            return (rsp.status, data, rsp.getheaders())
        except:
            err = "request failed (%s)" % sys.exc_info()[1]
            self._logger.error(err)
            return None, err, None
        finally:
            try:
                conn.close()
            except:
                pass


    ###############################################################################
    def get(self, url, headers={}, output=None):
        """ Makes a GET request.

        @param  url      Fully qualified URL.
        @param  headers  Optional headers for the request.
        @param  output   Function to call with (data, length), data being a
                         chunk of data read. Length containing the content
                         length or -1 if unknown. Aborts when False is returned.
        @return          The status code (200, 404, etc). None on error.
        @return          Response body, None if output is set. Or error message.
        @return          Response headers. None on error.
        """
        return self._request("GET", url, None, headers, output)


    ###############################################################################
    def post(self, url, body, headers={}, output=None):
        """ Makes a POST request.

        @param  url      Fully qualified URL.
        @param  body     Content to submit. The content length header is
                         created automatically.
        @param  headers  Optional headers for the request.
        @param  output   Function to call with (data, length), data being a
                         chunk of data read. Length containing the content
                         length or -1 if unknown. Aborts when False is returned.
        @return          The status code (200, 404, etc). None on error.
        @return          Response body, None if output is set. Or error message.
        @return          Response headers. None on error.
        """
        return self._request("POST", url, body, headers, output)
