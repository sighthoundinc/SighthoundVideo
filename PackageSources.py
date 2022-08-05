#!/usr/bin/env python

# ----------------------------------------------------------------------
#  Copyright (C) 2009 Vitamin D, Inc. All rights reserved.
#  Copyright (C) 2014 Sighthound, Inc. All rights reserved.
#
#  The information and source code contained herein is the
#  exclusive property of Sighthound, Inc. No part of this software
#  may be used, reproduced, stored or distributed in any form,
#  without explicit written authorization from Sighthound, Inc.
# ----------------------------------------------------------------------

"""Extract pieces of our source for a given purpose.

Usage: ./run python PackageSources.py settingsName [dstDir]

We use this as a helper when making a source distribution for a certain part
of SmartVideo.

A few notes about how this works:
1. First, we use python's modulefinder to find all of the _local_ dependencies
   for the top-level scripts.  This means that it will find any dependencies
   that live UNDER THE CURRENT WORKING DIRECTORY.  We'll ignore any
   dependencies that are in one of the 'wholeDirs' specified.
   WARNING: I don't report any of modulefinder's errors (!)
2. We'll take all of the dependencies, plus all of the extra files, and copy
   them to the right places in the destination directory.
3. We'll look for ".dll", ".so", and ".dylib" files (AKA shared objects)
   UNDER THE CURRENT WORKING DIRECTORY.  If we find a shared object and we've
   already created the destination directory for that shared object (which
   means that the shared object is in the same directory as something copied
   in step #2), we'll copy the shared object to the destination.  This is a bit
   complicated, but should get all of the important shared objects.
4. We'll use 'svn export' to export any wholeDirs specified.  This will copy
   something without the ".svn" directories and will ignore any files only
   present in the user's directory (like .pyc files, etc).
   IMPORTANT: At the moment, this WON'T get a clean version of the files, so
   any local changes to versioned files will be included.  We could avoid this
   by adding @BASE to our command, but I'm not sure that's what we want.
   IMPORTANT2: This is no longer the case with the git switch. Look into a
   git equivalent?
"""

# Python imports...
import os
import shutil
import sys
import modulefinder
from glob import glob
import re

# Local imports...
from appCommon.CommonStrings import kAppName, kWebcamExeName
from appCommon.CommonStrings import kSoftwareLicenseAgreementRtf

# Allow overriding from the environment...
# ...this is important in an OEM environment because we run this script before
# the OEM scripts can patch CommonStrings.
# NOTE: We don't worry about the license agreement--later scripts get that.
# TODO: Can we always use the environment variable versions of these strings?
if 'FRONTEND_APPNAME' in os.environ:
    kAppName = os.environ['FRONTEND_APPNAME']
if 'WEBCAM_SERVER_EXENAME' in os.environ:
    kWebcamExeName = os.environ['WEBCAM_SERVER_EXENAME']

##############################################################################
def isLink(path):
    return (os.stat(path)!=os.lstat(path) or os.path.islink(path))

##############################################################################
def copyFilePreservingLinks(src, dst):
    if isLink(src):
        linkto = os.readlink(src)
        os.symlink(linkto, dst)
    elif src != dst:
        shutil.copy(src,dst)

##############################################################################
# Helper function to grab the files we need.
def GetFilesFromDir(dirPath, pattern='*.*', regexp=re.compile(r'.+'), followLinks=True):
    """Retrieve files from directory 'dirPath' that match pattern 'pattern'.

    @param      dirPath     Directory to search in as a string. Can be absolute
                            or relative path.
    @param      pattern     Wildcard pattern as a string.  The string is a
                            wildcard pattern if it contains any of '?',
                            '*' or '['.
    @param      regexp      A compiled regular expression object. Only the
                            'match' function will be used. It will be applied to
                            the 'os.path.basename' of every string in the
                            globbed results list.

    @return     filePaths   Filepaths that match the given pattern that were
                            found in the given directory as a list of strings,
                            [
                                "filepath1/file1", "filepath2/file2", ...,
                                "filepathN/fileN",
                            ].
    """

    globResults = []

    for f in glob(os.path.join(dirPath, pattern)):
        if os.path.isfile(f) and (followLinks or not isLink(f)):
            globResults.append(f)

    res =  [
        f for f in globResults if regexp.match(os.path.basename(f)) is not None
    ]
    print ("dir=%s, pattern=%s, res=%s re=%s" % (dirPath, pattern, res, regexp.pattern))
    return res

if sys.platform == 'darwin':
    _isWin = False
    _isMac = not _isWin
    _platform = 'Mac'
    _libExt = 'dylib'
    _libPrefix = 'lib'
    _exeExt = 'so'
    _icoExt = 'icns'
    _regexp = re.compile(r'[^.]+(\.[0-9A-Z]*)*\.' + _libExt)
    _dllDir = "lib"
else:
    _isWin = True
    _isMac = not _isWin
    _platform = 'Win'
    _libExt = 'dll'
    _libPrefix = ''
    _exeExt = 'exe'
    _icoExt = 'ico'
    _regexp = re.compile(r'[^.]+-?[0-9A-Z]+\.' + _libExt)
    _dllDir = "bin"

# Get install directory of the videoLib library from the environment...
if 'SVINSTALLDIR' in os.environ and 'SV3RDPARTYDIR' in os.environ:
    _localCppInstall =  os.path.abspath(os.environ['SVINSTALLDIR'])
    _externalInstallDir =  os.path.abspath(os.environ['SV3RDPARTYDIR'])
    _externalPythonDir =  os.path.join(_externalInstallDir, "lib", "python2.7", "site-packages")
else:
    raise RuntimeError(
        "'SVINSTALLDIR' or 'SV3RDPARTYDIR' environment variable is not set! "
        "Did you remember to run 'source setupEnvironment' before calling "
        "this (" + str(os.path.basename(__file__)) + ") script?"
    )



_iconsDir = os.path.join('icons',)
_icons = [
    os.path.join(_iconsDir, 'InstallerIcon-%s.%s' % (_platform.lower(), _icoExt)),
    os.path.join(_iconsDir, 'SmartVideoApp.%s' % _icoExt),
]

_extraDllDirs = [
    # Windows's extra DLL directories to include...
    'Microsoft.VC90.CRT.'+os.getenv("SVARCH"),
] if _isWin else [
    # Mac's extra DLL directories to include...
]

# Include installer script for Mac
_updater = [ os.path.join("frontEnd", "updater", "installScriptApp.tar") ] if _isMac else []

# Contains settings for our different extraction tasks...
# - topLevelScripts: We'll use modulefinder to find dependencies on these
#                    python scripts.  Those dependencies will automatically
#                    be copied to the output dir.
# - extraFiles: Extra files that should be copied to the output dir.
#               MUST BE A RELATIVE PATH!
# - wholeDirs: Whole directories that will be "exported" to the output dir using
#              svn export.
_settingsDict = {
    # We don't actually distribute the source to the front end, but we use this target to
    # Move the important parts of the front end to another directory in preparation for
    # obfuscation and building.
    'frontEndPrep': {
        'topLevelScripts': [
            os.path.join("FrontEndLaunchpad.py"),
        ],
        'extraFiles': _icons + [
            "run",
            "setupEnvironment",
            "app",

            # Builtin starter license...
            os.path.join("frontEnd", "licenses", "Builtin.lic"),

            # End user license agreemements...
            os.path.join("frontEnd", "docs", kSoftwareLicenseAgreementRtf),    # NOTE: This is pre-OEM-patching (!)
            os.path.join("frontEnd", "docs", "FFmpeg license lgpl-2.1.txt"),
            os.path.join("frontEnd", "docs", "Live555 Streaming Media license lgpl-3.0.txt"),
            os.path.join("frontEnd", "docs", "Live555 Streaming Media license reference gpl-3.0.txt"),

            # Include these so that we can build executable from package dir...
            os.path.join("frontEnd", "setup-Win.py"),
            os.path.join("frontEnd", "setup-Mac.py"),
            os.path.join("frontEnd", "MakeDocUrl.py"),
            os.path.join("frontEnd", "WinInstaller.py"),
        ] + _updater,
        'wholeDirs': _extraDllDirs + [
            "xnat",
            "fonts",
            "config",
            "icons",
            os.path.join("frontEnd", "bmps"),
            os.path.join("frontEnd", "resources"),
            os.path.join("frontEnd", "sounds"),
            os.path.join("vitaToolbox", "wx", "bmps"),
            _externalInstallDir,
            _localCppInstall,
            # Obfuscator is picky, and wants those directly under obfuscation directory root
            # Being on PYTHONPATH isn't sufficient
            os.path.join(_externalPythonDir, "SIOWrapper"),
            os.path.join(_externalPythonDir, "svsentry"),
            os.path.join(_externalPythonDir, "videoLib2"),
        ],
    },

}

##############################################################################
def main(settingsName, buildDir='build'):
    """The main program for PackageSources.

    @param  settingsName    The name of the settings to use for extraction.
    @param  destinationDir  Directory to place the source in.
    """
    # This is hardcoded (for now)...
    obfuscatedResultsDir = os.path.join(buildDir, "obfuscated-out", "results")

    # Get settings...
    settings = _settingsDict[settingsName]
    topLevelScripts = settings['topLevelScripts']
    wholeDirs = settings['wholeDirs']
    extraFiles = settings['extraFiles']
    dataSetFiles = []

    destinationDir = os.path.join(buildDir, "package-out", settingsName)
    if os.path.exists(destinationDir):
        raise Exception("Please delete %s before calling PackageSources" %
                        destinationDir)

    # Find dependencies of the top level scripts...
    print "* Looking for python dependencies..."
    dependencies = []
    for targetPath in topLevelScripts:
        sys.stdout.write("  %-65s " % (targetPath + "..."))
        sys.stdout.flush()
        dependencies += _findDependencies(targetPath, wholeDirs,
                                          obfuscatedResultsDir)
        sys.stdout.write("done!\n")
        sys.stdout.flush()
    print "  ...done looking for dependencies."

    # Copy dependencies + extra files...
    print "* Copying dependencies and extra files..."
    for srcPath in dependencies + extraFiles + dataSetFiles:
        # Figure out if the source file came from obfuscation.  If
        # so, take the obfuscation prefix away when deciding on
        # a destination path...
        relSrcPath = _relPath(srcPath, obfuscatedResultsDir)
        if relSrcPath is not None:
            dstPath = os.path.join(destinationDir, relSrcPath)
        else:
            dstPath = os.path.join(destinationDir, srcPath)

        dstDir, _ = os.path.split(dstPath)
        if not os.path.isdir(dstDir):
            os.makedirs(dstDir)

        # print("copyFilePreservingLinks(%s, %s" % (srcPath, dstPath))
        copyFilePreservingLinks(srcPath, dstPath)
    print "  ...done copying dependencies."


    # Copy any DLLs or .so files that exist in directories corresponding
    # to the destination directories.  This assumption means that there might
    # be files that the user does not want to package.  Make sure we don't
    # search in excluded directories.
    print "* Finding and copying any shared objects..."
    for root, dirs, files in os.walk("."):
        dstRoot = os.path.abspath(os.path.join(destinationDir, root))

        # If this dir isn't in the destionation, skip (and prevent further
        # recursion)...
        if (not os.path.isdir(dstRoot)):
            dirs[:] = []
            continue

        for f in files:
            _, ext = os.path.splitext(f)
            if ext.lower() in ('.dll', '.so', '.dylib'):
                srcPath = os.path.join(root, f)
                dstPath = os.path.join(dstRoot, f)
                copyFilePreservingLinks(srcPath, dstPath)
    print "  ...done copying shared objects."

    # Export directories...
    print "* Copying whole directories to %s (through svn export if needed)..." % destinationDir
    for wholeModuleDir in wholeDirs:
        if os.path.isabs(wholeModuleDir):
            dstPath = destinationDir
        else:
            dstPath = os.path.join(destinationDir, wholeModuleDir)
        try:
            os.makedirs(os.path.split(dstPath)[0])
        except Exception:
            pass

        sys.stdout.write("  %-65s " % (wholeModuleDir + "..."))
        sys.stdout.flush()
        os.system("cp -pPR '%s' '%s'" % (wholeModuleDir, dstPath))
        sys.stdout.write("done!\n")
        sys.stdout.flush()
    print "  ...done copying directories."




##############################################################################
def _findDependencies(targetScript, ignoreDirs, obfuscatedResultsDir):
    """Find local dependencies for the given target script.

    @param  targetScript          The python script we're looking for
                                  dependencies for.
    @param  ignoreDirs            We'll ignore dependencies in these subdirs.
    @param  obfuscatedResultsDir  The dir containing obfuscated results.  This
                                  is prepended to sys.path when looking for
                                  modules.
    @return dependencies          The dependency files.
    """
    targetDir, _ = os.path.split(targetScript)
    cwd = os.path.abspath(os.path.curdir)

    # Note: excludes avoid strange warnings on python 2.5.4 on Mac.  Basically,
    # python was warning me that an applescript module was using an identifier
    # that would be a reserved word in python 2.6.
    mf = modulefinder.ModuleFinder(
        [obfuscatedResultsDir] + sys.path + [targetDir],
        excludes=['aetools', 'StdSuites.AppleScript_Suite']
    )
    mf.run_script(targetScript)
    dependencies = []
    for (_, module) in mf.modules.iteritems():
        if not module.__file__:
            continue

        filePath = _relPath(module.__file__, cwd)
        if filePath is None:
            continue

        for ignoreDir in ignoreDirs:
            if filePath.startswith(ignoreDir):
                break
        else:
            dependencies.append(filePath)

    dependencies.sort()
    return dependencies


##############################################################################
def _relPath(path, relativeTo):
    """Return the given path relative to another path.

    >>> print _relPath("frontEnd/constructionComponents", "frontEnd")
    constructionComponents
    >>> print _relPath("dirThatDoesntExist", "frontEnd")
    None
    >>> print _relPath("/tmp", '.')
    None

    @param  path        The path we want to know about.
    @param  relativeTo  The path we should be relative to.
    @return relPath     The relative path, or None if path isn't a child of
                        relativeTo.
    """
    # First, convert both to abspath...
    path = os.path.abspath(path)
    relativeTo = os.path.abspath(relativeTo)

    # The 'relativeTo' must start with the given path
    if not path.startswith(relativeTo):
        return None

    # Trim the base part off...
    path = path[len(relativeTo):]

    # Make sure it doesn't start with a separator...
    if path.startswith(os.sep):
        path = path[len(os.sep):]

    return path



##############################################################################
def test_main():
    """Contains various self-test code."""
    import doctest
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        try:
            main(*sys.argv[1:])
        except Exception, e:
            print "Error calling main: '%s'" % (str(e))
