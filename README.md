# General
* Sighthound Video is an open-source, flexible, intelligent VMS.
* The following are the present and future objectives of the project:
   * To run on as many platforms as possible.  At present, x64 Windows and macOS are supported.
   * To leverage intelligent computer vision to improve information signal-to-noise ratio, and to make things or events easy to find, in real-time or after the fact.
   * To be easy to build, install, and use.
   * To support the widest variety of cameras possible
   * Avoid "death by configuration" by providing the necessary minimum of settings, and using automatic configuration whenever possible.
   * To support and provide integration for standards whenever possible, actual or defacto, such as ONVIF, RTSP, WebRTC, HLS, and HomeKit Secure Video (HKSV)

# Source Package
* Sighthound Video package consists of the following components
  * source.zip - Sighthound Video source code distribution
  * libs.zip - packaged binary dependencies
  * tools.zip - python 2.7.18 package with relevant packages installed
    * TBD: describe how the package is created


# Build environment - MacOS
* Requirements
    * Intel Mac with MacOS 12.3 or better
        * Apple Silicon Mac may work - untested
        * Previous versions of MacOS may work - untested
    * XCode 13.4 with command line tools
        * Previous versions of XCode may work - untested
    * CMake


# Build environment - Windows
* Requirements
    * Microsoft Visual Studio 2017 or better
    * llvm 10 (https://releases.llvm.org/download.html)
    * cmake 3.17.1
    * Git for Windows (https://gitforwindows.org/)
    * make
        * we use `make` from msys2 install (used in a standalone fashion)
        * `make` from https://sourceforge.net/projects/ezwinports/ did not work
    * ninja (https://ninja-build.org/)
    * Inno Setup (https://jrsoftware.org/isinfo.php)
* Build Preparation
    * Open an MSVC shell (x64 Native Tools Command Prompt for VS2017)
    * Set up additional environment
        * set PATH=/path/to/cmake/bin;/path/to/git/bin;/path/to/git/usr/bin;%PATH%;/path/to/llvm10/bin;/path/to/ninja;/path/to/make
        * set CC=clang-cl
        * set CXX=clang-cl
* Create installer
    * `bash ./buildSV.sh`

# Project structure
* `appCommon` - modules used in all components
* `backEnd` - background processes and searches
  * `responses` - a collection of classes defining actions available in response to triggered real-time events
  * `triggers` - a collection of classes defining real-time events that may cause responses to be executed
* fonts
* frontEnd - native application front end
  * `bmps` - various images used in UI components
  * `constructionComponents` - query construction view elements
  * `docs` - license text for the code and dependent libraries
  * `resources`
  * `sounds` - bundled sounds used in 'Play Sound' response
  * `updater` - updated app used in MacOS version
* `icons` - icon images
* `launch` - service/daemon component
* `Microsoft.VC90.CRT.x86_64` - MS runtime (its best to install the redistributable)
* `scripts`
* `vitaToolbox` - collection of odds and ends used in SV
* `xnat` - NAT traversal library
* `FrontEndLaunchpad.py`
* `Makefile`
* `PackageSources.py` - part of build and packaging process