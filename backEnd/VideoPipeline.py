#! /usr/local/bin/python

#*****************************************************************************
#
# VideoPipeline.py
#      A subclassed Sentry pipeline with video path data.
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


# Python imports...
import sys
import os

# Common 3rd-party imports...
#   None for now...

# Toolbox imports...
from svsentry.Sentry import VideoPipeline as _VideoPipeline
from svsentry.Sentry import loadSentry, kDefaultPipelineConfigFile


from vitaToolbox.ctypesUtils.LoadLibrary import LoadLibrary
loadSentry(LoadLibrary, None)

##############################################################################
class VideoPipeline (_VideoPipeline):
    """A subclassed Sentry pipeline with video path data.
    """

    ##################################################
    def __init__(self, videoPath, objectCollector, pipelineConfigFile=kDefaultPipelineConfigFile):
        """Initializes the pipeline. Overloaded to initialize with a video path.

        @param videoPath            The video path where the frames will be
                                    coming from.
        @param objectCollector      an ObjectCollector instance which will
                                    receive events from this pipeline.
        @param pipelineConfigFile   (optional) A configuration file that defines
                                    this pipeline.
        """
        super(VideoPipeline, self).__init__(objectCollector, pipelineConfigFile)

        self._videoPath = videoPath


    ###########################################################
    def updateVideoPath(self, videoPath):
        """Update the video path.

        @param  videoPath  The new video path
        """
        self._videoPath = videoPath
        self.objectCollector.cameraLocation = videoPath
