#!/bin/bash

# ----------------------------------------------------------------------
#  Copyright (C) 2008 Vitamin D, Inc. All rights reserved.
#
#  The information and source code contained herein is the
#  exclusive property of Vitamin D, Inc. No part of this software
#  may be used, reproduced, stored or distributed in any form,
#  without explicit written authorization from Vitamin D, Inc.
# ----------------------------------------------------------------------

# Use the "run" script to run "FrontEnd.py" with the right environment.

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