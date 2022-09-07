#!/bin/bash

function buildCMakeProject()
{
  local proj=$1
  local projname=`basename $proj`
  echo "Building $projname from $proj into $SVINSTALLDIR"
  shift 1
  rm -rf $TMPDIR/$projname/.build
  mkdir -p $TMPDIR/$projname/.build
  pushd $TMPDIR/$projname/.build

  if [ `uname` = "Darwin" ]; then
    echo "Building $proj for Mac"
    cmake -DCMAKE_INSTALL_PREFIX=$SVINSTALLDIR -DCMAKE_OSX_ARCHITECTURES=x86_64 $@ $proj
	  if [ $? -ne 0 ]; then
        echo "Failed to build $proj (cmake)"
        exit -1
    fi
    make VERBOSE=1 install
	  if [ $? -ne 0 ]; then
        echo "Failed to build $proj (make)"
        exit -1
    fi
  else
    echo "Building $proj for Windows"
    cmake -DCMAKE_INSTALL_PREFIX=$SVINSTALLDIR -G "Ninja" $@ $proj
	  if [ $? -ne 0 ]; then
        echo "Failed to build $proj (cmake)"
        exit -1
    fi
    ninja install
	  if [ $? -ne 0 ]; then
        echo "Failed to build $proj (ninja)"
        exit -1
    fi
  fi
  echo "Building $projname from $proj into $SVINSTALLDIR - done"
  popd
}


SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [ `uname` = "Darwin" ]; then
  OS="mac"
else
  OS="win"
fi

cd $SCRIPT_DIR

if [ -z $TMPDIR ]; then
    TMPDIR=/tmp/svbuild/$OS
fi

# Extract the source
for value in libs tools
do
  rm -rf $TMPDIR/$value
  mkdir -p $TMPDIR/$value
  tar xvzf $SCRIPT_DIR/$OS/$value.tgz -C $TMPDIR/$value
done



# Tell the build where Python is
export SVPYTHONROOT=$TMPDIR/tools/svpython/


if [ `uname` = "Darwin" ]; then
	# Make sure the python package can run
	xattr -d com.apple.quarantine $SVPYTHONROOT/Python.framework
	chmod +x $SCRIPT_DIR/scripts/*
	# Setup minimum OS version
	export MACOSX_DEPLOYMENT_TARGET="10.11"
	# Help OpenGL Python package set up the paths (proprietary patch to PyOpenGL uses this on Mac only)
	export SV_BUILDING_PACKAGE=1
	# Mac Python is finicky, and needs to be in a known location to properly run
	TMPPYTHON="/tmp/Library/Frameworks"
	rm -rf $TMPPYTHON
	mkdir -p $TMPPYTHON
	ln -s $SVPYTHONROOT/Python.framework $TMPPYTHON/Python.framework
	export SVPYTHONROOT=$TMPPYTHON/Python.framework/Versions/2.7
	# Update Python path
	export PYTHONPATH=$SVPYTHONROOT/lib/python2.7/site-packages
	# Update PATH
	export PATH=$SVPYTHONROOT/bin:$PATH
	# Skip notarization by default; look at ./scripts/notarizeMacosApp.sh to understand how to set it up
	export SV_SKIP_NOTARIZATION=1
else
	# Update Python path
	export PYTHONPATH=$SVPYTHONROOT/Lib/site-packages
	# Update PATH
	export PATH=$SVPYTHONROOT:$PATH
fi

# Tell the build where all the binary dependencies are
export SV3RDPARTYDIR=$TMPDIR/libs
echo "SV3RDPARTYDIR=$SV3RDPARTYDIR"
# Target architecture
export SVARCH=x86_64
# Where to place build product
export SVINSTALLDIR=$TMPDIR/install
export SVINSTALLDIR_NATIVE=$TMPDIR/install
rm -rf $SVINSTALLDIR
mkdir -p $SVINSTALLDIR
# Where to place temporary build files
export SVBUILDDIR=$TMPDIR/build

# We may not have git history to determine the revision
# This variable is important for service start and configuration:
# it gets baked into shlaunch, and depending on the value decision
# pertaining to service configuration are being taken.
# It is recommended to at least increment this for each public release
export SV_BUILD_REVISION=12345


buildCMakeProject $SCRIPT_DIR/launch
buildCMakeProject $SCRIPT_DIR/xnat -DCONAN_INCLUDE_DIRS_MINIUPNPC=$SV3RDPARTYDIR/include \
										-DCONAN_INCLUDE_DIRS_LIBNATPMP=$SV3RDPARTYDIR/include \
										-DCONAN_LIB_DIRS_MINIUPNPC=$SV3RDPARTYDIR/lib \
										-DCONAN_LIB_DIRS_LIBNATPMP=$SV3RDPARTYDIR/lib \
										-DCONAN_LIBS_MINIUPNPC=miniupnpc \
										-DCONAN_LIBS_LIBNATPMP=natpmp

buildCMakeProject $SCRIPT_DIR/backEnd/triggers
if [ `uname` = "Darwin" ]; then
  buildCMakeProject $SCRIPT_DIR/vitaToolbox/path
fi


echo "Building final SV project"
echo ">>>>> PATH=$PATH"
echo ">>>>> PYTHON=`which python`"
export SHELL=/bin/bash
cd $SCRIPT_DIR
make
if [ $? -ne 0 ]; then
	echo "Failed to build SV package"
	exit -1
fi
