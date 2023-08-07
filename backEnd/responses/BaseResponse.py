#!/usr/bin/env python

#*****************************************************************************
#
# BaseResponse.py
#    Base response class, common code for all responses
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


###############################################################
class BaseResponse(object):
    """Base class for rule responses."""
    ###########################################################
    def __init__(self):
        """Empty initializer for BaseResponse class"""
        pass


    ###########################################################
    def addRanges(self, ms, rangeDict):
        """Add ranges generated from processing.

        @param  ms      The most recent time in milliseconds that has been
                        processed.
        @param  ranges  A dictionary of response ranges.  Key = objId, value =
                        list of ((firstFrame, firstTime), (lastFrame, lastTime))
        """
        _ = ms, rangeDict

        # Required for subclasses to implement...
        raise NotImplementedError()


    ###########################################################
    def startNewSession(self):
        """Do anything necessary to respond to a new camera session."""
        return


    ###########################################################
    def __del__(self):
        """SendClipResponse destructor.

        We send out anything pending here.  TODO: a more formal way to do this?
        """
        self.flush()


    ###########################################################
    def flush(self):
        """Flush out any pending data.

        Nothing more will be given.
        """
        pass




