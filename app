#!/bin/bash

#*****************************************************************************
#
# app
#   Script for launching the app in debug mode
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


if [ `uname` == Darwin ]; then
   LIBSUB="lib"
else
   LIBSUB="bin"
fi

export SV3RDPARTYDIR=`pwd`/build/stagingRoot
export SVINSTALLDIR=$SV3RDPARTYDIR
if [ `uname` == Darwin ]; then
  export SV_DEVEL_LIB_FOLDER_CONAN=$SV3RDPARTYDIR/$LIBSUB
  export SV_DEVEL_LIB_FOLDER_LOCAL=$SVINSTALLDIR/$LIBSUB
else
  export SV_DEVEL_LIB_FOLDER_CONAN=`cygpath -w $SV3RDPARTYDIR/$LIBSUB`
  export SV_DEVEL_LIB_FOLDER_LOCAL=`cygpath -w $SVINSTALLDIR/$LIBSUB`
fi

if [ "$1" != "--no-libs" ]; then
    conan install . -if `pwd`/build
    conan build . -bf `pwd`/build
fi
pyfolderline=`conan info . --package-filter svpython* --paths 2>/dev/null | grep package_folder`
pyfolder=`echo $pyfolderline | sed 's/.*package_folder:[ \t]*//g'`
echo "pyfolder=${pyfolder}"

if [ `uname` == Darwin ]; then
  PYLOC="${pyfolder}/Python.framework/Versions/2.7"
  PYSUB="/bin"
  PYPATH="/lib/python2.7/site-packages"
  runCmd=""
else
  PYLOC=${pyfolder}
  PYSUB=""
  PYPATH="\Lib"
  runCmd="bash "
  export PATH=$PATH:$SV_DEVEL_LIB_FOLDER_CONAN:$SV_DEVEL_LIB_FOLDER_LOCAL
fi

if [[ $PATH == *"${pyfolder}"* ]]; then
    echo "Python is already activated!"
else
    echo "python activation goes here"
    export PATH=$PYLOC$PYSUB:$PATH
    echo $PATH
    export PYTHONPATH=$PYLOC$PYPATH
    echo $PYTHONPATH
fi

echo `which python`

export SVPYTHONROOT=$PYLOC


myPath=`dirname $0`
revNum=`./scripts/getRevision.sh`
runCmd="$runCmd$myPath/run"

if [ "$1" == "--no-libs" ]; then
    shift
fi

if [ -e .oldRevNum ]; then
  oldRevNum=`cat .oldRevNum`
  if [ "$revNum" != "$oldRevNum" ]; then
    echo "Detected git update; quitting backend."
    ${runCmd} python frontEnd/BackEndClient.py quit
  fi
fi
echo "$revNum" > .oldRevNum

echo "Running ${runCmd}"
source setupEnvironment
${runCmd} python frontEnd/FrontEnd.py "$@"


#=====================================================
# This can be used for sanity tests when Sentry fails to load
# python `pwd`/scripts/testDetections.py