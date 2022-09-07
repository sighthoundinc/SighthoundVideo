# This is a simple Makefile to execute the most common build-related commands
# for SmartVideo.

# Run shell as bash to keep things consistent everywhere...
SHELL := /bin/bash

# Comment this out to see more verbose makefiles...
HUSH := @

# See if we're on Mac or Windows...
_UNAME_RESULT := $(shell uname)
ifeq ($(_UNAME_RESULT),Darwin)
  PLATFORM := Mac
  DLL_EXT  := dylib
  BIN_EXT  := so
else
  PLATFORM := Win
  DLL_EXT  := dll
endif

# We want local video incorporated when building smartvideo
export LOCAL_CAMERA_SUPPORT = 1



# We'll clean out .pyc files in these directories...
cleanPycDirs := appCommon backEnd devTools frontEnd \
                markup vitaToolbox pilMac pilWin \
                pyaudioMac pyaudioWin webstuffMac webstuffWin launch \
                netifacesMac netifacesWin xnat

.PHONY : all
all: frontEnd
	@echo "Done!"


test_%:
	$(HUSH) \
	    set -e; \
        source setupEnvironment; \
	    $(MAKE) -C $* test;

clean_%:
	$(HUSH) \
	    set -e; \
        source setupEnvironment; \
	    $(MAKE) -C $* clean;

.PHONY : clean
clean:
	$(HUSH) \
	    set -e; \
	    source setupEnvironment; \
	    for subLibrary in $(subLibraries); do \
	        if [ -e "$$subLibrary" ]; then \
			    echo "...cleaning $$subLibrary"; \
			    $(MAKE) -C $$subLibrary clean; \
			fi; \
	    done

	@echo '...clearing out sessions and generated files'
	$(HUSH)rm -rf sessions/
	$(HUSH)rm -rf build/
	$(HUSH)find . -name .DS_Store -exec rm -vf "{}" \;
	$(HUSH)rm -f *.pyc *.pyo *.poic
	$(HUSH)rm -f *.iss .DS_Store
	$(HUSH)rm -f *~
	$(HUSH) \
	  for pycDir in $(cleanPycDirs); do \
	    if [ -e $$pycDir ]; then \
	      echo "......cleaning pyc/pyo from $$pycDir"; \
	      find $$pycDir '(' -name '*\.pyc' -or -name '*\.pyo' ')' -exec \
	           rm {} '+'; \
	    fi; \
	  done




.PHONY : realclean realClean
realclean realClean: clean
	@echo '...deleting old analysis'
	$(HUSH)rm -rf oldAnalysis
	$(HUSH)rm -f .oldRevNum


.PHONY : metricsQuick metricsBaseline metricsDaily
metricsQuick:
	sh devTools/RunMetrics.sh quick
metricsBaseline:
	sh devTools/RunMetrics.sh baseline
metricsDaily:
	sh devTools/RunMetrics.sh daily


# Sub projects which might or might not be there...
-include frontEnd/FrontEnd.mk



# Useful debugging rule: Typing 'make show_VARS' will show you
# the value of VARS in the makefile...
show_%:
	@echo "$* = $($*)"

