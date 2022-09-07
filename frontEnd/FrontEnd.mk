#*****************************************************************************
#
# FrontEnd.mk
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

# Makefile fragment for FrontEnd-related build stuff.
# ...this is intended to be included by the main smartvideo Makefile.
#
# Note: The smartvideo structure is probably not one to emulate.  Really, each
# of our apps (frontEnd, devTool, ...) should probably share libraries,
# but otherwise be separate projects.


FRONTEND_APPNAME           ?= Sighthound Video

FRONTEND_EXENAME           ?= Sighthound Video
BACKEND_EXENAME            ?= Sighthound Agent
WEBCAM_SERVER_EXENAME      ?= Sighthound USB

CWD_UNIX                   := $(shell pwd)
CWD                        := $(shell python -c 'import os; print os.path.abspath(".")' | sed 's/$$//g')

# Setup build directories. Specifically, this is here for Windows, since msys
# and Parallels don't want to play nicely together.  Msys is unable to run the
# "find" command when searching for files on a different file system. So for
# Windows, build in a temp file there, and then move whatever we want back to
# the actual path_to/smartvideo/build directory.
ifeq ($(PLATFORM),Win)
# We have to hardcode this, since the actual SVBUILDDIR isn't known until setupEnvironment runs (for the 3000th time)
# And in the unholy mess of makefiles and shell commands, it's too early for us to call it.
# And when running from source in the VM, we don't want this referencing shared Parallels partition, because bad juju.
    FRONTEND_BUILD_UNIXDIR   :=   /tmp/.build-obs
    FRONTEND_BUILD_DIR       :=   $(shell cygpath -w "$(FRONTEND_BUILD_UNIXDIR)")
else
    FRONTEND_BUILD_UNIXDIR  :=  $(CWD_UNIX)/build
    FRONTEND_BUILD_DIR      :=  $(CWD)/build
endif

EXTERNAL_DEPS_DIR               := $(shell basename "$(SV3RDPARTYDIR)")
FRONTEND_PACKAGE_UNIXDIR        := $(FRONTEND_BUILD_UNIXDIR)/package-out/frontEndPrep
FRONTEND_PACKAGE_UNIXDIR_STAGE2 := $(FRONTEND_BUILD_UNIXDIR)/package-out/frontEndPrep-stage2
FRONTEND_OBSFUCATE_UNIXDIR      := $(FRONTEND_BUILD_UNIXDIR)/package-out/frontEndPrep-stage2/smartvideo
FRONTEND_APPDIR                 := $(FRONTEND_BUILD_DIR)/app-out/FrontEnd-$(PLATFORM)
FRONTEND_APP_UNIXDIR            := $(FRONTEND_BUILD_UNIXDIR)/app-out/FrontEnd-$(PLATFORM)
FRONTEND_INSTALLER_UNIXDIR      := $(FRONTEND_BUILD_UNIXDIR)/installer-out/FrontEnd-$(PLATFORM)

ifeq ($(PLATFORM),Win)
    FRONTEND_MAINDIR       := $(FRONTEND_APP_UNIXDIR)
    APP_MAKER              := py2exe
    CERTFILE               := $(CWD_UNIX)/cert.pfx
	TIMESERVER             := http://timestamp.digicert.com
else
    FRONTEND_MAINDIR       := $(FRONTEND_APP_UNIXDIR)/$(FRONTEND_APPNAME).app/Contents/Resources
    FRONTEND_APPPATH       := $(FRONTEND_APP_UNIXDIR)/$(FRONTEND_APPNAME).app
    FRONTEND_DMGNAME       := $(FRONTEND_APPNAME).dmg
    APP_MAKER              := cx_Freeze
    APP_MAKER_CMD          := bdist_mac
endif



.PHONY : frontEndUpdater
frontEndUpdater:
ifeq ($(PLATFORM),Mac)
	$(CWD_UNIX)/scripts/buildMacosUpdaterApp.sh "$(CWD_UNIX)/frontEnd/updater"
else
	@echo "not Building Updater... $(PLATFORM)"
endif


.PHONY : frontEnd
frontEnd : frontEndUpdater
	@echo "FRONTEND_BUILD_UNIXDIR=$(FRONTEND_BUILD_UNIXDIR)"
	@echo "FRONTEND_BUILD_DIR=$(FRONTEND_BUILD_DIR)"
	$(HUSH)$(MAKE) obfuscateFrontEnd
	$(HUSH)$(MAKE) frontEndApp
	$(HUSH)$(MAKE) frontEndInstaller
	@echo "Done!"

# Obfuscating frontEnd is tricky because of a number of reasons...
# 1. Obfuscator assumes that all subdirectories are to be obfuscated.  ...but
#    we don't want obfuscator to obfuscate things like scipy, multiprocessing,
#    etc.  Because of that, we need to work in a temp directory.  We use
#    PackageSources to get stuff in a temp dir, then tweak things around a bit.
# 2. We'd like to be able to run directory from the obfuscated sources (so we
#    don't need to build a full app in order to debug obfuscator problems).
#    That means we need to get everything over into the obfuscated dir.
#    PackageSources already handles some of that, so we leverage it.
#
# This target doesn't encode any dependencies and shouldn't be run directly
# except for debugging purposes...
.PHONY : obfuscateFrontEnd
obfuscateFrontEnd:
	@echo "Using PackageSources to get our sources into a temp location..."
	$(HUSH)rm -rf "$(FRONTEND_PACKAGE_UNIXDIR)"
	$(HUSH) \
	  source setupEnvironment --srcdir "$(CWD_UNIX)"; \
	  python PackageSources.py frontEndPrep "$(FRONTEND_BUILD_DIR)";

	@echo "Tweaking temp dir to prepare for obfuscation..."
	$(HUSH)rm -rf "$(FRONTEND_PACKAGE_UNIXDIR_STAGE2)"
	$(HUSH)mkdir  "$(FRONTEND_PACKAGE_UNIXDIR_STAGE2)"
	$(HUSH)mv "$(FRONTEND_PACKAGE_UNIXDIR)" "$(FRONTEND_PACKAGE_UNIXDIR_STAGE2)"/smartvideo

	@echo "Renaming math directory to work around obfuscator bug"
	$(HUSH)find $(FRONTEND_PACKAGE_UNIXDIR_STAGE2)/smartvideo -name '*.py' -exec \
	  sed -e 's/vitaToolbox\.math/vitaToolbox\.math2/g' -i'_' {} ';'
	$(HUSH)mv $(FRONTEND_PACKAGE_UNIXDIR_STAGE2)/smartvideo/vitaToolbox/math $(FRONTEND_PACKAGE_UNIXDIR_STAGE2)/smartvideo/vitaToolbox/math2

	@echo "Copying extra files from source package into obfuscation dir..."
	$(HUSH) \
	  cd $(FRONTEND_PACKAGE_UNIXDIR_STAGE2)/smartvideo; \
	  rm -f ../extraFiles.tar; \
	  find . -not '(' \
	        -type 'd' -or \
	        -name '*.py' -or -name '*.py_' -or -name '*.pyc' -or -name '*.pyo' -or \
	        -name '*.c' -or -name '*.cc' -or -name '*.cpp' -or \
	        -name '*.h' -or \
	        -name 'extraFiles.tar' ')' -exec \
	    tar rf ../extraFiles.tar {} '+'
	$(HUSH) \
	  mkdir -p $(FRONTEND_OBSFUCATE_UNIXDIR); \
	  cd $(FRONTEND_OBSFUCATE_UNIXDIR); \
	  tar xf $(FRONTEND_PACKAGE_UNIXDIR_STAGE2)/extraFiles.tar

	@echo "Done obfuscating!"


# This assumes that you've already run obfuscation properly.
.PHONY : frontEndApp
frontEndApp :
	@echo "Running $(APP_MAKER)..."
	$(HUSH) \
	  rm -rf $(FRONTEND_APP_UNIXDIR); \
	  echo FRONTEND_OBSFUCATE_UNIXDIR=$(FRONTEND_OBSFUCATE_UNIXDIR); \
	  cd $(FRONTEND_OBSFUCATE_UNIXDIR); \
	  source setupEnvironment; \
	  python frontEnd/setup-$(PLATFORM).py $(APP_MAKER_CMD)

	@echo "Copying non-python files needed..."
	$(HUSH)mkdir -p "$(FRONTEND_MAINDIR)/frontEnd"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/frontEnd/bmps" "$(FRONTEND_MAINDIR)/frontEnd/bmps"
	$(HUSH)mkdir -p "$(FRONTEND_MAINDIR)/vitaToolbox/wx"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/vitaToolbox/wx/bmps" "$(FRONTEND_MAINDIR)/vitaToolbox/wx/bmps"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/frontEnd/sounds" "$(FRONTEND_MAINDIR)/frontEnd/sounds"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/icons" "$(FRONTEND_MAINDIR)/icons"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/frontEnd/docs"/* "$(FRONTEND_MAINDIR)"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/frontEnd/licenses" "$(FRONTEND_MAINDIR)/frontEnd/licenses"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/share" "$(FRONTEND_MAINDIR)/"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/fonts" "$(FRONTEND_MAINDIR)/fonts"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/config" "$(FRONTEND_MAINDIR)/config"
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/models" "$(FRONTEND_MAINDIR)/models"

	@echo "Adding the build time stamp..."
	$(HUSH)sh scripts/genBuildTimeStamp.sh > "$(FRONTEND_MAINDIR)/build.txt"

	@echo "Adding a link to documentation..."
	$(HUSH) \
	  cd $(FRONTEND_OBSFUCATE_UNIXDIR); \
	  source setupEnvironment; \
	  python frontEnd/MakeDocUrl.py "$(FRONTEND_APPDIR)"

ifeq ($(PLATFORM),Win)
	@echo "Make a copy of app for the backend to run..."
	$(HUSH)mkdir -p "$(FRONTEND_MAINDIR)/PipelineNodes"
	$(HUSH)cp "$(FRONTEND_MAINDIR)/$(FRONTEND_EXENAME)" "$(FRONTEND_MAINDIR)/$(BACKEND_EXENAME)"

	@echo "Copying all of our libraries, since py2exe is very likely to forget something (like .exe's we need)"
	$(HUSH)cp "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/bin/"*.exe "$(FRONTEND_MAINDIR)";
	$(HUSH)cp "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/bin/"*.dll "$(FRONTEND_MAINDIR)";
	$(HUSH)cp "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/lib/PipelineNodes/"*.dll "$(FRONTEND_MAINDIR)/PipelineNodes";
	@ls -la $(SVINSTALLDIR)
	$(HUSH)cp "$(SVINSTALLDIR)/bin/"* "$(FRONTEND_MAINDIR)";
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/redist" "$(FRONTEND_MAINDIR)/redist"
	$(HUSH)rm "$(FRONTEND_MAINDIR)"/api-ms-win*.dll || true;

	@echo "Attempting to sign dlls and exes..."
	$(CWD_UNIX)/scripts/signWindowsBinaries.sh "$(CERTFILE)" $(SV_CERTPASSWORD) $(TIMESERVER) "$(FRONTEND_MAINDIR)"/*.dll
	$(CWD_UNIX)/scripts/signWindowsBinaries.sh "$(CERTFILE)" $(SV_CERTPASSWORD) $(TIMESERVER) "$(FRONTEND_MAINDIR)"/*.exe
	$(CWD_UNIX)/scripts/signWindowsBinaries.sh "$(CERTFILE)" $(SV_CERTPASSWORD) $(TIMESERVER) "$(FRONTEND_MAINDIR)"/PipelineNodes/*.
endif

ifeq ($(PLATFORM),Mac)
	@echo "Copying all of our libraries, including symlinks, because cxFreeze sucks chunks, and doesn't"
	$(HUSH)mkdir -p "$(FRONTEND_APPPATH)/Contents/MacOS/PipelineNodes";
	$(HUSH)find $(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/lib -name *.dylib -exec install_name_tool -add_rpath "@loader_path" {} \; ;
	$(HUSH)cp -r "$(FRONTEND_OBSFUCATE_UNIXDIR)/frontEnd/updater" "$(FRONTEND_MAINDIR)/frontEnd/updater";
	# The libraries are copied anyway by cx_Freeze, but we're losing symlinks (which are followed through)... this should restore them
	$(HUSH)cp -a "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/lib/"*.dylib "$(FRONTEND_APPPATH)/Contents/MacOS";
	$(HUSH)cp -a "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/lib/"*.so "$(FRONTEND_APPPATH)/Contents/MacOS";
	$(HUSH)cp -a "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/lib/PipelineNodes/"*.so "$(FRONTEND_APPPATH)/Contents/MacOS/PipelineNodes";
	$(HUSH)cp -a "$(FRONTEND_OBSFUCATE_UNIXDIR)/$(EXTERNAL_DEPS_DIR)/bin/"* "$(FRONTEND_APPPATH)/Contents/MacOS";
	$(HUSH)cp -a "$(SVINSTALLDIR)/lib/"* "$(FRONTEND_APPPATH)/Contents/MacOS";
	$(HUSH)cp -a "$(SVINSTALLDIR)/bin/"* "$(FRONTEND_APPPATH)/Contents/MacOS";
	$(HUSH)ln -s . "$(FRONTEND_APPPATH)/Contents/MacOS/.dylibs";

	@echo "Stripping DLLs (ignore errors about libgcc_s)"
	$(HUSH)find "$(FRONTEND_APPPATH)" -name '*.$(DLL_EXT)' -or -name '*.$(BIN_EXT)' -type f -exec strip -x -S - {} ';'

	@echo "Adding a link to the Applications folder..."
	$(HUSH)ln -s /Applications "$(FRONTEND_APP_UNIXDIR)"
endif


.PHONY : frontEndInstaller
ifeq ($(PLATFORM),Win)
# Notes about the Windows installer:
# - We setup the environment and run from the package dir, so OEMs have a
#   chance to patch common strings and the installer script.  We run with CWD
#   as the main directory, though.
frontEndInstaller :
	@echo "Making Windows installer..."
	$(HUSH) \
	  rm -rf $(CWD_UNIX)/build/installer-out; \
	  rm -rf $(FRONTEND_BUILD_UNIXDIR)/installer-out; \
	  export REVISION=`./scripts/getRevision.sh`; \
	  cd $(FRONTEND_PACKAGE_UNIXDIR_STAGE2)/smartvideo; \
	  source setupEnvironment; \
	  cd $(CWD_UNIX); \
	  python "$(FRONTEND_PACKAGE_UNIXDIR_STAGE2)/smartvideo/frontEnd/WinInstaller.py" "$(FRONTEND_BUILD_DIR)";
	$(CWD_UNIX)/scripts/signWindowsBinaries.sh "$(CERTFILE)" $(SV_CERTPASSWORD) $(TIMESERVER) $(FRONTEND_INSTALLER_UNIXDIR)/*.exe ;
	$(HUSH) \
	  if [ ! -e $(CWD_UNIX)/build/installer-out ]; then \
	      mkdir -p $(CWD_UNIX)/build; \
	      mv $(FRONTEND_BUILD_UNIXDIR)/installer-out $(CWD_UNIX)/build/installer-out ; \
	  fi;
else
frontEndInstaller :
	echo "Making Mac DMG..." && \
	$(CWD_UNIX)/scripts/signMacosBinaries.sh "$(FRONTEND_APPPATH)" && \
	$(CWD_UNIX)/scripts/notarizeMacosApp.sh "$(FRONTEND_APPPATH)" && \
	echo "Copying our custom DMG installer icon before making DMG..." && \
	cp "$(FRONTEND_OBSFUCATE_UNIXDIR)/icons/InstallerIcon-mac.icns" "$(FRONTEND_APP_UNIXDIR)/.VolumeIcon.icns" && \
	echo "Making DMG..." && \
	$(CWD_UNIX)/scripts/createDmg.sh "$(FRONTEND_APP_UNIXDIR)" "$(FRONTEND_INSTALLER_UNIXDIR)"
endif
