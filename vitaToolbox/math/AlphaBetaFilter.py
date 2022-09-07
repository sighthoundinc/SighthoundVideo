#!/usr/bin/env python

#*****************************************************************************
#
# AlphaBetaFilter.py
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


# Python imports...
import getopt
import sys

# Common 3rd-party imports...
import numpy

# Local imports...


# Constants
_kZeroVel = numpy.array([[0.0, 0.0]], 'float32')


class AlphaBetaFilter(object):
    """
    This class implements a variant of an alpha-beta filter (simplified
    form of Kalman filter) to improve point tracking in the presence of
    noisy measurements.

    NOTES:
    - Points may be added or removed at any point in time.  However, it
      is the user's responsibility to keep track of which points are
      added/removed.
    """

    ###########################################################
    def __init__(self, alpha=0.75, beta=0.75, initialPosition=None):
        """Initializer for AlphaBetaFilter filter.

        @param alpha           -- update weight for position.  A value closer
                                  to 0 means that measurement has no effect;
                                  a value closer to 1 means that history has no
                                  effect.
        @param beta            -- update weight for velocity.  A value closer
                                  to 0 means that measurement has no effect;
                                  a value closer to 1 means that history has no
                                  effect.
        @param initialPosition -- NumPy array containing the initial position
                                  of points to track.  initialPosition should
                                  be a 2D NumPy with each row containing the
                                  initial coordinates of one of the points to
                                  track.
        """
        # Check arguments
        assert 0 <= alpha <= 1
        assert 0 <= beta <= 1

        # Set filter parameters
        self._alpha = alpha
        self._beta = beta

        # Initialize positions and velocities
        self._posSmoothed = None
        self._velSmoothed = None
        self._posPredicted = None
        self._velPredicted = None

        # Add points to track
        if initialPosition is not None:
            for i in xrange(initialPosition.shape[0]):
                pos = initialPosition[i,:].tolist()
                self.addPoint(pos)


    ###########################################################
    def addPoint(self, pos):
        """Add point to track.

        @param  pos  initial position of new point to track input
                     as a list or tuple of two floating point numbers.

        @return      number points currently being tracked
        """
        # Convert pos to a 2D numpy array with dtype 'float32'
        posFloat32 = numpy.array([pos], 'float32')

        # Append new point to list of points to track
        if self._posSmoothed is None:
            self._posSmoothed = posFloat32;
            self._velSmoothed = numpy.array(_kZeroVel)
        else:
            self._posSmoothed = numpy.append(self._posSmoothed,
                                             posFloat32, axis=0)
            self._velSmoothed = numpy.append(self._velSmoothed,
                                             _kZeroVel, axis=0)

        # Return number of points currently being tracked
        return self._posSmoothed.shape[0]


    ###########################################################
    def deletePoint(self, idx):
        """Remove point to track.

        @param idx  index (in list of positions) of point to stop tracking
        """
        self._posSmoothed = numpy.delete(self._posSmoothed, idx, axis=0)
        self._velSmoothed = numpy.delete(self._velSmoothed, idx, axis=0)


    ###########################################################
    def getPositions(self):
        """Return current smoothed positions of all tracked points.

        @return  current smoothed positions of all tracked points
        """
        return self._posSmoothed


    ###########################################################
    def getVelocities(self):
        """Return current smoothed velocities of all tracked points.

        @return  current smoothed velocities of all tracked points
        """
        return self._velSmoothed


    ###########################################################
    def getPredictedPositions(self):
        """Return predicted positions of all tracked points.

        @return  predicted positions of all tracked points
        """
        return self._posPredicted


    ###########################################################
    def getPredictedVelocities(self):
        """Return predicted velocities of all tracked points.

        @return  predicted velocities of all tracked points
        """
        return self._velPredicted


    ###########################################################
    def getLastMeasuredPosition(self):
        """Return last measured positions of all tracked points.

        @return  last measured positions of all tracked points
        """
        return self._posLastMeasured


    ###########################################################
    def predict(self, dt):
        """
        Compute predicted positions and velocities of all tracked points.

        @param dt  time step between previous and current point

        @return    tuple containing predicted positions and velocities
                   of all tracked points
        """
        # Predict positions of points
        self._posPredicted = self._posSmoothed + dt*self._velSmoothed
        self._velPredicted = self._velSmoothed

        return (self._posPredicted, self._velPredicted)


    ###########################################################
    def update(self, posMeasured, dt):
        """
        Update current positions and velocities of all tracked points.

        @param posMeasured   measured positions of all tracked points
                             at current time
        @param dt            time step between previous and current point

        @return              tuple containing updated positions and
                             velocities of all tracked points
        """
        # Udpate last measured position
        self._posLastMeasured = posMeasured

        # Update positions and velocities using measured positions
        # (only if predict() has been called at least once).
        if self._posPredicted is not None:
            posDiff = posMeasured - self._posPredicted
            self._posSmoothed = self._posPredicted + self._alpha*posDiff
            self._velSmoothed = self._velPredicted + self._beta/dt*posDiff
        else:
            self._posSmoothed = self._posLastMeasured
            self._velSmoothed = numpy.array(_kZeroVel)

        return (self._posSmoothed, self._velSmoothed)


#================================================================
# Command-line use of filter.
#================================================================
def usage():
    print
    print "Usage:  python AlphaBetaFilter.py [options] < dataFile >"
    print
    print "  \"dataFile\"  -- File containing measurements to process."
    print "                   Each row should contain a space-separated,"
    print "                   interleaved list of coordinates for the"
    print "                   points."
    print
    print "                   For example, the line '1 1 2 2' represents"
    print "                   two points with coordinates (1, 1) and (2, 2)"
    print "                   respectively."
    print
    print
    print "  Options:"
    print "    -h, --help:  show this help"
    print

if __name__ == '__main__':

    # Process command-line arguments
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'h', ['help'])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    for opt in opts:
        if (opt[0] == '-h' or opt[0] == 'help'):
            usage()
            sys.exit(0)
        else:
            usage()
            sys.exit(1)

    if len(args) < 1:
        sys.stderr.write('Incorrect number of arguments.\n')
        usage()
        sys.exit(1)
    else:
        dataFile = args[0]

    # Create AlphaBetaFilter
    alphaBetaFilter = AlphaBetaFilter()

    # Read data from file
    FILE = open(dataFile, "r")
    lines = FILE.readlines()
    FILE.close()

    # Process first line to determine the number of points
    # and add them to the AlphaBetaFilter
    line = lines[0]
    splitLine = line.split()
    assert len(splitLine) % 2 == 0  # check for even number of columns
    numPoints = len(splitLine)/2
    for n in xrange(numPoints):
        newPoint = [float(splitLine[2*n]), float(splitLine[2*n+1])]
        _ = alphaBetaFilter.addPoint(newPoint)

    # Process remaining lines
    dt = 0.1
    posMeasured = numpy.zeros([numPoints, 2], dtype='float32')
    for line in lines[1:]:
        splitLine = line.split()
        for n in xrange(numPoints):
            posMeasured[n,:] = \
              [float(splitLine[2*n]), float(splitLine[2*n+1])]
        posPredicted, _ = alphaBetaFilter.predict(dt)
        posSmoothed, _ = alphaBetaFilter.update(posMeasured, dt)
        print "Predicted positions: \n", posPredicted
        print "Smoothed positions: \n", posSmoothed


