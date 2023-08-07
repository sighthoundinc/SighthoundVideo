#*****************************************************************************
#
# FileUploader.py
#   Basic file upload via HTTP client
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

import requests
import sys

from appCommon.CommonStrings import kUploaderProxyHost, kUploaderProxyPath, kVersionString

from appCommon.hostedServices.ServicesClient import ServicesClient


#===========================================================================
class FileUploader(ServicesClient):
    def __init__(self, logger, token):
        """ Constructor.

        @param  logger      Logger instance, mostly for error messages.
        @param  token       API access token.
        @param  updatePath  Update path override, None for production/default.
        @param  secure      True to use HTTPS, False to do HTTP (for testing).
        @param  port        Port override. Optional, None defaults to 443.
        @param  host        Host override. Optional, None for default.
        @return             True if the request succeeded.
        """
        super(FileUploader, self).__init__(logger, token, host=kUploaderProxyHost)

    ###########################################################
    def uploadFile(self, accountId, localFileName, remoteFilePrefix):
        res = False
        extension = os.path.splitext(localFileName)[1]
        params = {
            "accountId": str(accountId),
            "filename": "%s%s" % ( remoteFilePrefix, extension )
        }
        jsonData = self.requestJson("POST", kUploaderProxyPath, params)
        if jsonData is not None:
            try:
                self._logger.debug("Got JSON: %s" % str(jsonData))
                headers = jsonData['headers']
                method  = jsonData['method']
                uri     = jsonData['uri']

                session = requests.Session()
                headersMap = {}
                for h in headers:
                    self._logger.debug("Header: %s" % str(h))
                    headersMap[h[0]] = h[1]
                if method == "GET":
                    funct = session.get
                elif method == "POST":
                    funct = session.post
                elif method == "PUT":
                    funct = session.put
                else:
                    raise Exception("Unsupported HTTP method %s" % method)
                res = False
                with open(localFileName,'rb') as file:
                    response = funct(uri, headers=headersMap, data=file)
                    status = response.status_code
                    self._logger.debug("Upload result: %d" % status)
                    res = (status >= 200 and status < 300)
            except:
                self.setLastError(500,
                    'invalid response from server (%s - %s)' % (sys.exc_info()[1], str(jsonData)))
        return res
