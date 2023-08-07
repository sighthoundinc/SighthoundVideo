#! /usr/local/bin/python

#*****************************************************************************
#
# TimingInfo.py
#   An object for tracking and logging staged timing information intentionally formatted for consumption by Splunk
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


from collections import defaultdict
import ConfigParser
import os
import time


##############################################################################
class TimingInfo( object ):
    """An object for tracking and logging staged timing information intentionally formatted for consumption by Splunk."""


    kConfigFilenameTimingInfo   = 'timingInfo.cfg'
    kSectionEnabled             = 'enabled'
    kConfigDefaultsEnabled      = { 'CameraCapture' : 0, 'VideoPipeline' : 0 }

    kOutputInterval             = 'kOutputInterval'
    kSession                    = 'kSession'
    kEnabled                    = 'kEnabled'

    kKeySource                  = 'source'

    kOutputIntervalDefault      = 10
    kSessionDefault             = 37
    kTimingMarkerDefault        = 11111


    ###########################################################
    def __init__( self, timingParams ):
        self.timingSums             = defaultdict( float )
        self.inputItemMarkers       = { '_dummy' : 0 }
        self.trackMaxes             = { '_dummy' : 0 }
        self.outputLastCountWritten = -1
        self.inputCount             = 0

        self.outputInterval         = timingParams.get( TimingInfo.kOutputInterval, TimingInfo.kOutputIntervalDefault )
        self.session                = timingParams.get( TimingInfo.kSession, TimingInfo.kSessionDefault )
        self.bEnabled               = timingParams.get( TimingInfo.kEnabled, False )

        self.logPrefix              = 'TimingInfo session=' + str( self.session ) + '  '

        if self.bEnabled:
            self._prvLog( 'bEnabled=' + str( self.bEnabled ) + '  timingParams: ' + str( timingParams ))


    ###########################################################
    def _checkConfigForEnabled( self ):
        pathTimingConfigFile    = os.path.join( '.', TimingInfo.kConfigFilenameTimingInfo )
        parser = ConfigParser.RawConfigParser( TimingInfo.kConfigDefaultsEnabled )
        parser.read( pathTimingConfigFile )
        if not parser.has_section( TimingInfo.kSectionEnabled ):
            parser.add_section( TimingInfo.kSectionEnabled )

        parserFoundEnabled          = parser.getint( TimingInfo.kSectionEnabled, self.sourceName )
        self.bEnabled               = ( 0 != parserFoundEnabled )
        if self.bEnabled:
            self._prvLog( 'sourceName=' + self.sourceName + '  parserFoundEnabled=' + str( parserFoundEnabled ) + '  bEnable=' + str( self.bEnabled ))


    ###########################################################
    def associateKeys( self, dictIn ):
        msg = ''
        for key in dictIn:
            # maybe non-ascii chars
            valueAsUnicode  = unicode( dictIn[ key ])
            valueAsAscii    = valueAsUnicode.encode( 'ascii', errors='replace' )

            msg += str( key ) + '=\"' + valueAsAscii + '\"  '
            if TimingInfo.kKeySource == key:
                self.sourceName = valueAsAscii
                self._checkConfigForEnabled()
        if self.bEnabled:
            self._prvLog( 'timingParams: ' + msg )


    ###########################################################
    def associateTrackMax( self, key, valueIn ):
        if not self.bEnabled:
            return

        if not key in self.trackMaxes:
            self.trackMaxes[ key ] = valueIn
        elif self.trackMaxes[ key ] < valueIn:
            self.trackMaxes[ key ] = valueIn


    ###########################################################
    def inputIncrement( self, delta ):
        if not self.bEnabled:
            return

        self.inputCount += delta

        if 0 == ( self.inputCount % self.outputInterval ):
            self._outputTimingInfo()
            self._resetTimingInfo()


    ###########################################################
    def inputItemMark( self, inputItemKey ):
        if not self.bEnabled:
            return

        theKey  = str( inputItemKey )
        self.inputItemMarkers[ theKey ]     = time.time()


    ###########################################################
    def inputItemIncrement( self, inputItemKey ):
        if not self.bEnabled:
            return

        theKey          = str( inputItemKey )
        theTimingMarker = self.inputItemMarkers.get( theKey, TimingInfo.kTimingMarkerDefault )
        if TimingInfo.kTimingMarkerDefault == theTimingMarker:
            self._prvLog( 'NO MARKER for inputItemKey=' + theKey + '  inputItemMarkers: ' + str( self.inputItemMarkers ))
            return

        self.timingSums[ theKey ]   += time.time() - theTimingMarker


    ###########################################################
    def outputForce( self ):
        if not self.bEnabled:
            return

        self._outputTimingInfo()
        self._resetTimingInfo()


    ###########################################################
    def _outputTimingInfo( self ):
        if not self.bEnabled:
            return

        for key, itemSum in self.timingSums.items():
            self._prvLog( 'key=\"%s\"  itemSum=%.4f  runningInputCount=%i' % ( key, itemSum, self.inputCount ))
        for key, valueMax in self.trackMaxes.items():
            if '_dummy' != key:
                self._prvLog( key + '=' + str( valueMax ))


    ###########################################################
    def _resetTimingInfo( self ):
        self.timingSums = defaultdict( float )
        self.trackMaxes = { '_dummy' : 0 }


    ###########################################################
    def _prvLog( self, msg ):
        print( self.logPrefix + msg )
