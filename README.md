# Building Sighthound Video #


## Build Environment Setup ##

### All OSs ###

* [CMake](https://cmake.org/download/) (3.5 or later is preferred)
* [git](https://git-scm.com/download/win)
* [git lfs](https://github.com/git-lfs/git-lfs/releases)

### macOS ###

* XCode
    
### Windows ###

* msys2 64-bit (obtain from [msys2.github.io](http://www.msys2.org/))
* setup `PATH` to add paths to Python and CMake in your msys2 `.bash_profile`)
* the rest of the tools can be set up using 
  [svdeps/blob/master/utils/setup-mingw.sh](https://github.com/sighthoundinc/svdeps/blob/master/utils/setup-mingw.sh). `svdeps` is also a subrepo of smartvideo, so you may have this script locally).

Unless you prefer to manually build the dependencies from source (not recommended), this should do it.

### Python ###

* [Python 2.7.17](https://www.python.org/downloads/release/python-2717/)
	* make sure to install 64-bit binaries. 

* (Windows/MINGW only) Apply the patch to distutils/cygwinccompiler.py as described in [this bug report](http://bugs.python.org/issue16472)

	This resolves the problem of Python including a hardcoded msvcrt90.dll when building dependencies.
	Without this patch, pyaudio binary doesn't come out right (since it depends on portaudio DLL, which pulls in a different version of the same runtime)

* [wxPython](https://wxpython.org/download.php) (3.0.2 only for the moment)
	
	Whether virtualenv is being used or not, wxPython has to be installed into the main Python location. There isn't much choice about that.
	
	Note: the stock wxPython 3.0.2 installer doesn't work on macOS 10.11 or later. Use [this repacked installer] (https://art.eng.sighthound.com/artifactory/sighthound-video/wxPython/wxPython3.0-osx-3.0.2.0-cocoa-py2.7-sh-repack.pkg). Your regular Artifactory credentials apply.

	wxPython works great in virtualenv on Windows. To make sure it is operational, symlinks will have to be established from virtual environment, to main Python install (see later)

	wxPython can be used in virtualenv on macOS as well. Build server does it by setting up a symlink:
	
		sudo ln -s /Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/wxredirect.pth \
               $VENV/lib/python2.7/site-packages
	However, I wasn't able to make the app start with wxPython being in virtualenv.
	
	
* [py2exe](https://sourceforge.net/projects/py2exe/files/py2exe/0.6.9)
	
	Download only. Will be installed with easy_install as part of other dependencies

* virtualenv (install using `pip install virtualenv virtualenvwrapper`)
	
	On Windows, virtualenv is clearly a way to go. I've also found this script handy:
	
			export PATH=/c/Python27-$SVARCH:/c/Python27-$SVARCH/Scripts:/c/bitboostObfuscator/bin:$PATH
			export SVDIR=/y/work/sh/smartvideo4.0 # Point this to your local copy
			export VENV=/c/Python-venvs/sv41-$SVARCH
			alias rmtemp="rm -rf /tmp/.build* /tmp/.install $SVDIR/build"
			cd $SVDIR
			source $VENV/Scripts/activate
	
			
	On macOS, I haven't been able to make ./app run from virtualenv (due to wxPython limitations). Also, unlike Windows, there's no choice where to install the Python (so no having both 32 and 64 bit versions at the same time) so I end up installing all the dependencies into the main Python folder.

	Word of warning: make sure virtualenv is installed for the python you're actually using.
	This is specifically important on OSX, where using virtualenv without explicitly installing it,
	may result in using system's python.

* Dependencies set up (either with activated virtualenv, or into main repo):

			pip install setuptools==35.0.1 PyOpenGL==3.1.0 markup==0.2 netifaces==0.10.5 pillow==4.1.0 requests==2.21.0
			# Portaudio package install (change value of SVARCH to i386 for 32-bit):
    		SVDEP=/tmp/portaudio-$SVARCH
    		rm -rf $SVDEP
    		git clone git@github.com:sighthoundinc/svdeps.git $SVDEP
    		cd $SVDEP
    		export PA_SRC=$SVDEP/.build/$SVARCH
    		./3rdparty/portaudio/build.sh -s3deps -builddir $PA_SRC -install $PA_SRC/.install
    		if [ `uname` == "Darwin" ]; then
    			PORTAUDIO_PATH=$PA_SRC/portaudio pip install --global-option='build_ext' --global-option="--static-link" pyaudio==0.2.11
    		else
   				pip install --global-option='build_ext' --global-option=-I${PA_SRC}/portaudio/include --global-option=-L${PA_SRC}/.install/lib --global-option --compiler=mingw32 pyaudio==0.2.11
   			fi
			
			# Only need the following if planning to build to installer
    		if [ `uname` == "Darwin" ]; then
				pip install cx_Freeze==4.3.4
    		else
    			# Obviously, you'd want to download this, and make it available
				easy_install /path/to/py2exe-0.6.9.win64-py2.7.exe
			fi


* (Windows/MinGW only) Setup symlinks for wxPython (make sure to run vrom virtualenv)

    	export VENVWLIB=`cygpath -w $VENV`\\Lib\\site-packages
    	cmd /c "mklink /h $VENVWLIB\\wx.pth c:\\Python27-$SVARCH\\Lib\\site-packages\\wx.pth"
    	cmd /c "mklink /h $VENVWLIB\\wxversion.py c:\\Python27-$SVARCH\\Lib\\site-packages\\wxversion.py"
    	cmd /c "mklink /j $VENVWLIB\\wx-3.0-msw c:\\Python27-$SVARCH\\Lib\\site-packages\\wx-3.0-msw\\"


## Obtaining Source ##

You're looking at this file, so obviously you got the source somehow.
That being said, you should get it from

	git@github.com:sighthoundinc/smartvideo.git

Once the repo is cloned, run
 
	git submodule update --init --recursive 
	git submodule foreach git lfs fetch 
	git submodule foreach git lfs checkout

and checkout the branch you want. We suggest *develop*, unless you're into weird experiments.

Oh, and do yourself a favor and put the commands above into an alias.


## Artifacts ##

Sighthound Video depends on great many libraries. Unless you have a good reason to modify their source, it's best you never see it. To help with that, we provide a nice prebuilt version of everything you need.

To retrieve those, you'd need access to Artifactory (ask Ryan for credentials).

Once you have the username and password, add an `~/.s3creds` file, with the following
contents:

	export SV_S3USER="yourname"
	export SV_S3PASSWORD="yourpassword"

The exact version of what needs to be retrieved is stored in
`./getDependencies.sh`.

### Notes ###

* If you update `gitDependencies.sh`, it is recommended the install folder 
is removed, so the actual dependency is guaranteed to be updated.
* If you've lost your credentials, _Artifactory_ is down, or some other disaster prevents you from pulling the artifacts from their permanent home, it is possible to use someone else's artifacts cache folder (see below). Just copy that cache folder where your build system will expect it (see below).

## Build ##

	make

That's all. Were you expecting anything else?

Well, quite a few things happen under wraps. An important bit is a script called setupEnvironment, which sets up all the paths and folders. By default, we'll use `./.build` as the build folder and `./.install` as the folder to install the binaries to. These can be overridden by setting `SVBUILDDIR` and `SVINSTALLDIR`.

The artifacts we've discussed above are cached in `./.cache`, which can be modified with `SVCACHEDIR`.

One other thing `setupEnvironment` does, is set up some variables (namely `SV_DEVEL_LIB_FOLDER`), to let our Python code know where the shared libraries we've built can be found. To make sure you never need to think of this again, set `DEVEL_ENV` to something in your `.bash_profile`.

To make the build process succeed you also need to get a copy of the obfuscator and declare its `bin` directory in the `PATH`. And for Windows the `signtool` command needs to be available - however if you do not want to install the Windows SDK for just that very reason you might also fake it via a (more or less) empty shell script, e.g. like

	#!/bin/bash
	echo DUMMY SIGNTOOL CALLED WITH $@

and ensure it's executable in the `PATH` somewhere.

For easier translation and starters, here's a working `.bash_profile` extension taken from a Windows development machine, where all of the build material is stored locally at `C:\_sv_dev_local`:

	PATH=/c/Python27:/c/Program\ Files/CMake/bin:$PATH
	PATH=$PATH:/c/Users/mhahn/Desktop/bitboostObfuscator/bin
	PATH=$PATH:$HOME/tools
	export PATH
	
	SV_DEV_LOCAL=/c/_sv_dev_local
	SVBUILDDIR=$SV_DEV_LOCAL/build
	SVINSTALLDIR=$SV_DEV_LOCAL/install
	SVCACHEDIR=$SV_DEV_LOCAL/cache
	export SVBUILDDIR
	export SVINSTALLDIR
	export SVCACHEDIR
	
	DEVEL_ENV=1
	export DEVEL_ENV

## Running From Source ##

	./app

or

	./app --no-libs

in case you prefer to skip running `make` on the C/C++ modules.

But seriously, don't forget to set `DEVEL_ENV` **before** you build.

## Rebuilding ##

While there's nothing wrong with `make clean`, the surest way is to

	rm -rf .build .install
	make

You pretty much never need to remove or otherwise touch `.cache` folder. Something must've gone seriously wrong, if this is required.


## Building Artifacts ##

Okay, you want your own ffmpeg. Or your own Sentry. In other words, you're brave.

The best way to accomplish this is to run

	./svdeps/3rdparty/[dependencyName]/build.sh --s3deps

for 3rd party dependencies, or

	./svdeps/sh/[dependencyName]/build.sh --s3deps

for external Sighthound projects we depend on (like Sentry)

You may want to export `SVBUILDDIR`, `SVINSTALLDIR` and `SVCACHEDIR` prior to running this, though, so the output goes to the same folders as SV build does. By default it'll be in the `svdeps` tree.

Note that additional tools may be needed (for example, clang on macOS, if it is Sentry you desire). Consult the relevant `build.sh` for additional details.

## Jenkins Setup ##

* macOS
	* Python is installed into the standard location /Library/Frameworks/Python.framework
	* Virtual environments are in /opt/python-venvs/sv41-$SVARCH (where SVARCH is i386 or x86_64)
	* All the python packages, except for wx, are set up in virtual envs
	* Due to this setup, ./app doesn't work on Jenkins for now

* Windows/MINGW:
	* Python is in /c/Python27-$SVARCH (where SVARCH is i386 or x86_64)
	* Virtual environments are in /c/python-venvs/sv41-$SVARCH (where SVARCH is i386 or x86_64)
	* There is also a virtual env /c/python-venvs/sv40-i386 for 4.0 branch build
	* Install Windows git client (make sure SSH keys are deployed to ~/.ssh in msys2, and c:\Users\Dev\.ssh)
