#! /usr/local/bin/python

#*****************************************************************************
#
# ConfigBitmapWindow.py
#    An object for reading BitmapWindow config
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




import ConfigParser
import os


##############################################################################
class ConfigBitmapWindow( object ):
    """An object for reading BitmapWindow config."""


    kConfigFilename         = 'bitmapWindow.cfg'
    kSectionTop             = 'top'
    kFieldMode              = 'mode'
    kModeLegacy             = 'Legacy'
    kModeMediaCtrl          = 'MediaCtrl'
    kConfigDefaultsTop      = { kFieldMode : kModeMediaCtrl }


    ###########################################################
    def __init__( self ):
        self._bLoaded   = False


    ###########################################################
    def _loadConfig( self ):
        if self._bLoaded:
            return

        pathConfigFile  = os.path.join( '.', ConfigBitmapWindow.kConfigFilename )
        parser          = ConfigParser.SafeConfigParser()
        parser.read( pathConfigFile )
        if not parser.has_section( ConfigBitmapWindow.kSectionTop ):
            parser.add_section( ConfigBitmapWindow.kSectionTop )

        try:
            self._foundMode             = parser.get( ConfigBitmapWindow.kSectionTop,
                                                  ConfigBitmapWindow.kFieldMode,
                                                  ConfigBitmapWindow.kConfigDefaultsTop[ ConfigBitmapWindow.kFieldMode ])
        except ConfigParser.NoOptionError:
            # No Mode?
            self._foundMode             = ConfigBitmapWindow.kConfigDefaultsTop[ ConfigBitmapWindow.kFieldMode ]

        self._bLoaded   = True


    ###########################################################
    def getMode( self ):
        self._loadConfig()
        return self._foundMode


    ###########################################################
    def IsModeMediaCtrl( self ):
        self._loadConfig()
        return self.getMode() == self.kModeMediaCtrl
