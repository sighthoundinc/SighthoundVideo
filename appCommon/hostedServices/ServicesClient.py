#*****************************************************************************
#
# ServicesClient.py
#    Client to access all things services, APIs which need be authenticated
#    by a token. Our services all use the same authentication mechanism and
#    return errors the same way. Every service call populates a last error slot,
#    so extended information can be retrieved from there in case something goes
#    wrong. Hence this class is not thread-safe and multiple instances should be
#    used if needed. An instance holds no active state, meaning each call does a
#    separate connection to the server, thus it is very lightweight and just only
#    consumes a bit of memory. Notice that only one spot in the system should do
#    the actual login and manage the token, since the server keeps only one token
#    per account!
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


import sys, urllib, json, urlparse, os, httplib, ssl

from appCommon.CommonStrings import kServicesHost


# Request parameter: the password.
_kParamPassword = "password"

# Header name: authentication token (this is NOT the machine ID!).
_kHeaderToken = "X-Machine-Token"
# Header name: common HTTP accept information.
_kHeaderAccept = "Accept"

# Maximum number of characters of a response (body) to log.
_kMaxResponseLogSize = 1000

# Request parameter: the user name/e-mail.
_kParamEmail = "email"
# Response parameter: the auth token.
_kParamKey = "key"
# Response parameter: the account identifier.
_kParamAccountId = "account_id"

# The (relative) path for authentication requests to be sent to.
# NOTE: for legacy reasons this is in the license scope as of today
_kAuthPath = "/license/auth/"

# The services port. We talk HTTPS by default, hence the choice.
_kServicesPort = 443

# Request timeout, in seconds.
_kTimeoutSecs = 20

# Number of response bytes to read at once.
_kReadChunkSize = 4096

# Status code: if anything outside the regular HTTP request went wrong, e.g.
#              connection issue, bad parameters, etc.
kStatusError = 500


###########################################################################
def _censor(d):
    """ Remove sensitive information from parameters and headers.

    @param d The original dictionary.
    @return New dictionary with fields masked where necessary.
    """
    result = {}
    for k, v in d.iteritems():
        if k in [_kParamPassword, _kHeaderToken]:
            result[k] = '*' * len(v)
        else:
            result[k] = v
    return result


###########################################################################
class ServicesClient(object):
    """ Client to access all things services, APIs which need be authenticated
    by a token. Our services all use the same authentication mechanism and
    return errors the same way. Every service call populates a last error slot,
    so extended information can be retrieved from there in case something goes
    wrong. Hence this class is not thread-safe and multiple instances should be
    used if needed. An instance holds no active state, meaning each call does a
    separate connection to the server, thus it is very lightweight and just only
    consumes a bit of memory. Notice that only one spot in the system should do
    the actual login and manage the token, since the server keeps only one token
    per account!
    """

    ###########################################################################
    def __init__(self, logger, token=None, timeout=None, secure=True,
                 port=None, host=None):
        """ Constructor.
        @param  machineId  The machine identifier the client should present.
        @param  logger     Logger instance, mostly for error messages.
        @param  token      API access token, if available.
        @param  timeout    Request timeout in seconds.
        @param  secure     True to use HTTPS, False to do HTTP (for testing).
        @param  port       Port override. Optional, None defaults to 443.
        @param  host       Host override. Optional, None for default.
        """
        super(ServicesClient, self).__init__()
        self._logger = logger
        self._lastError = None
        self._timeout = _kTimeoutSecs if timeout is None else timeout
        self._token = token
        self._secure = secure
        self._port = _kServicesPort if port is None else port
        self._host = kServicesHost if host is None else host

        # for manual testing we allow environment variables override the server
        if port is None and host is None:
            port = os.environ.get('SH_SERVICES_PORT', None)
            if port:
                self._port = int(port)
                self._logger.warn("license server port override: %s" % port)
            host = os.environ.get('SH_SERVICES_HOST', None)
            if host:
                self._host = host
                self._logger.warn("license server host override: %s" % host)
            secure = os.environ.get('SH_SERVICES_SEC', None)
            if secure:
                self._secure = "0" != secure
                self._logger.warn("license server secure override: %s" % secure)


    ###########################################################################
    def setLastError(self, status, error, code=None):
        """ Sets the last error, also logs it.

        @param status  Status code.
        @param error   Error message.
        @param code    Code sent by the server. None if n/a.
        """
        self._lastError = (status, error, code)
        self._logger.error("last error set to %d, '%s', %s" % self._lastError)


    ###########################################################################
    def lastError(self):
        """ Returns error information of the last call.

        @return List (status, error message, server code) if the last call
                failed. None if such a call was successful.
        """
        return self._lastError


    ###########################################################################
    def authFailed(self):
        """ Convenience method to figure it if the last call failed due to an
        authentication issue, meaning either a bad token or invalid credentials
        were passed.

        @return True on auth error, False on other error or success.
        """
        return self._lastError is not None and  \
            (403 == self._lastError[0] or       \
             401 == self._lastError[0])


    ###########################################################################
    def request(self, method, path, params={}, headers={}, timeout=None,
                sendToken=True, progressFn=None, outStream=None):
        """ Performs an HTTP(S) request. Automatically adds a header with the
        auth token, if one is available.

        @param method      The HTTP(S) method (GET, DELETE, POST, PUT) string.
        @param path        The request path, must not contain a query string.
        @param params      Optional POST or GET query parameters.
        @param headers     Optional headers.
        @param timeout     Optional timeout override.
        @param sendToken   True if the token is required to be sent.
        @param progressFn  Progress function. Called with (read,length), for
                           which length is -1 if the size of the document is
                           unknown. If the function returns False the download
                           gets aborted and the request fails.
        @param outStream   Stream object where to write the data to, instead of
                           collecting it in memory.
        @return            The response body or file object if given. None on
                           error or if the progress callback aborted things.
        """
        try:
            if self._token:
                headers[_kHeaderToken] = self._token
            elif sendToken:
                self.setLastError(403, "token n/a")
                return None
            if timeout is None:
                timeout = self._timeout
            method = method.upper()
            self._lastError = None
            if method == 'GET':
                body = None
                if len(params) > 0:
                    path += '?' + urllib.urlencode(params)
            else:
                body = json.dumps(params)
                headers['Content-Type'] = "application/json"
                headers['Content-Length'] = len(body)
            if headers.get(_kHeaderAccept, None) is None:
                headers[_kHeaderAccept] = "*/*"
            try:
                url = urlparse.urlparse(path)
                host = url.hostname
                if host is None:
                    raise Exception()
                port = url.port
                if port is None:
                    port = 443 if url.scheme.lower() == "https" else 80
                path = url.path
            except:
                host = self._host
                port = self._port
            self._logger.info("%s request, path=%s, params=%s, headers=%s - connecting to %s:%d ..." %
                              (method, path, _censor(params), _censor(headers), host, port))
            try:
                if self._secure:
                    conn = httplib.HTTPSConnection(
                        host, port, None, None, False, self._timeout, None,
                        ssl._create_unverified_context())
                else:
                    conn = httplib.HTTPConnection(
                        host, port, False, self._timeout)
                self._logger.debug("requesting %s ..." % path)
                conn.request(method, path, body, headers)
                response = conn.getresponse()
                status = response.status
                contentLength = response.getheader("Content-Length", None)
                size = int(contentLength) if contentLength else -1
                read = 0
                body = outStream if outStream else ""
                while True:
                    if progressFn and not progressFn(read, size):
                        raise Exception("aborted by progress function")
                    chunk = response.read(_kReadChunkSize)
                    if not chunk:
                        break
                    if outStream:
                        outStream.write(chunk)
                    else:
                        body += chunk
                    read += len(chunk)

            except:
                err = 'request failed %s' % str(sys.exc_info()[1])
                self.setLastError(kStatusError, err)
                return None
            finally:
                try:
                    conn.close()
                except:
                    pass
            if outStream:
                bodyLog = "[stream]"
            else:
                bodyLog = body[:_kMaxResponseLogSize]
            self._logger.info("status: %d, body: '%s'" % (status, bodyLog))
            if 204 == status:
                return body if outStream else ""
            if 200 == status:
                return body
            try:
                doc = json.loads(body)
                code = doc.get('code', None)
                error = doc.get('error', None)
                if error is None:
                    error = body
            except:
                code = None
                error = body
            self.setLastError(status, error, code)
        except:
            uncaught = sys.exc_info()
            err = 'uncaught error %s (%s)' % (uncaught[0], str(uncaught[1]))
            self.setLastError(kStatusError, err)
        return None


    ###########################################################################
    def requestJson(self, method, path, params={}, headers={}, timeout=None,
                    sendToken=True):
        """ Performs an HTTPS request, on success parses the response as a
        JSON document.

        @param method     The HTTP method (GET, DELETE, POST, PUT) string.
        @param path       The request path, must not contain a query string.
        @param headers    Optional headers.
        @param timeout    Optional timeout override.
        @param sendToken  True if the token is required to be sent.
        @return           The response JSON data, or None on error.
        """
        result = self.request(method, path, params, headers, timeout, sendToken)
        if result is not None:
            try:
                result = result.decode('utf-8')
                result = json.loads(result)
            except:
                result = None
                self.setLastError(kStatusError,
                    'got invalid JSON: ' + str(sys.exc_info()[1]))
        return result


    ###########################################################################
    """ Logs a user in, gets the API access token. If this succeeds the token
    will then be available via the token() method and also used in any other
    method call for authentication.

    @param  user      The user name (e-mail).
    @param  password  The password.
    @return           (token,account id) in successful login. None on any error.
    """
    def userLogin(self, user, password):
        params = { _kParamEmail: user, _kParamPassword: password}
        result = self.requestJson('POST', _kAuthPath, params, {}, None, False)
        if result is not None:
            token = result.get(_kParamKey, None)
            accountId = result.get(_kParamAccountId, None)
            if token is not None and accountId is not None:
                self._logger.info("new token '%s...', account ID is '%s'" %
                                  (token[0:4], accountId))
                self._token = token
                return (token, str(accountId))
            self.setLastError(kStatusError,
                              'missing token or account ID in response')
        return None


    ###########################################################################
    """Logs a user out, and removes the current license.
    """
    def userLogout(self):
        self._logger.info("Logging out...")
        self._token = None


    ###########################################################################
    """ To get the current authentication token.

    @return  The token, or None if not logged in yet.
    """
    def token(self):
        return self._token


    ###########################################################################
    def updateToken(self, token):
        """Update the authentication token.

        @param  token  The new token to use.
        """
        self._token = token

