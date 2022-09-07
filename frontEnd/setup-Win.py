#*****************************************************************************
#
# setup-Win.py
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

"""
Usage:
    ./run python frontEnd/setup-win.py py2exe
"""

# As stated from <http://www.py2exe.org/index.cgi/PyOpenGL>,
#   "As of PyOpenGL 3.0, add the following to any of your python files to
#   get py2exe to work."
# We need the couple of lines below for py2exe in Windows to make sure PyOpenGL
# gets packaged correctly.  We might be able to remove it once we switch over
# from py2exe to cx_Freeze...
import sys
if sys.platform == 'win32':
    from ctypes import util
    try:
        from OpenGL.platform import win32
    except AttributeError:
        pass

from glob import glob
from distutils.core import setup
import sys
import os

from appCommon.CommonStrings import kAppName, kOemName, kCopyrightYear
from appCommon.CommonStrings import kVersionString, kExeName


class Target:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        # for the versioninfo resources
        self.version = kVersionString
        self.company_name = kOemName
        self.copyright = kCopyrightYear
        self.name = kAppName

ARCH = os.getenv("SVARCH")
MS_VC90_CRT = "Microsoft.VC90.CRT"

cwd = os.path.abspath(os.path.curdir)

# Get the paths to the MSVC CRT dll's folders.
# They should be in the current working directory.
msvc90Dir = os.path.join(cwd, MS_VC90_CRT+"."+ARCH)
print("msvc90Dir=%s" % msvc90Dir)

# Add those locations to the path so that py2exe can find them during packaging.
sys.path.extend([msvc90Dir,])

# Prepare to tell py2app what DLL's to collect from those directories.
DATA_FILES = [
    (MS_VC90_CRT, glob(os.path.join(msvc90Dir,"*.*"))),
]


################################################################
# The manifest will be inserted as resource into the exe.  This
# gives the controls the Windows XP appearance when run on XP.
#
# Another option would be to store it in a file named
# <exename>.exe.manifest, and copy it with the data_files option into
# the dist-dir.
#
comctl_template= '''
<dependency>
    <dependentAssembly>
        <assemblyIdentity
            type="win32"
            name="Microsoft.Windows.Common-Controls"
            version="6.0.0.0"
            processorArchitecture="x86"
            publicKeyToken="6595b64144ccf1df"
            language="*"
        />
    </dependentAssembly>
</dependency>
'''

manifest_template = '''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
<assemblyIdentity
    version="5.0.0.0"
    processorArchitecture="%(arch)s"
    name="%(prog)s"
    type="win32"
/>
<description>%(prog)s Program</description>
%(comctlasm)s
<dependency>
    <dependentAssembly>
        <assemblyIdentity
            type="win32"
            name="Microsoft.VC90.CRT"
            version="9.0.21022.8"
            processorArchitecture="%(arch)s"
            publicKeyToken="1fc8b3b9a1e18e3b"
        />
    </dependentAssembly>
  </dependency>
</assembly>
'''


################################################################


excludes = [
    # TODO: Don't know which of these are still needed; they were copied from
    # the VitaKit configuration...
    "matplotlib",
    "Gnuplot",
    "Tkconstants",
    "Tkinter",
    "tcl",
    "macpath",
    "macurl2path",
    "xml.sax",
    "cv2",

    # I believe that we don't want to distribute this.  If I remember
    # correctly, it is released under GPL.  Developers might have this on
    # their system (like I did) because it's nice to use with ipython in
    # our development environment.  Not sure why it was getting pulled in.
    "pyreadline", "readline",

]

def generateExcludeList(versions):
    modules = [
        'core-string',
        'core-registry',
        'core-errorhandling',
        'core-profile',
        'core-libraryloader',
        'core-threadpool',
        'core-file',
        'core-processthread',
        'security-base',
        'core-localization',
        'core-sysinfo',
        'core-synch',
        'core-heap',
        'eventing-provider',
        'core-delayload',
        'core-com-midlproxystub',
        'core-psapi',
        'core-atoms',
        'core-sidebyside',
        'core-kernel32',
        'core-winrt-error',
        'core-shlwapi',
    ]
    res = []
    for version in versions:
        for module in modules:
            res = res + ['api-ms-win-' + module + '-l' + version + '.dll',
                    'api-ms-win-' + module + '-obsolete-l' + version + '.dll',
                    'api-ms-win-' + module + '-legacy-l' + version + '.dll']
    return res

dllexcludes = [
    # Don't know why this is here.  It was there from VitaKit.
    "w9xpopen.exe",

    # This gets pulled in when you're building on Vista, for some reason.
    # It causes problems if you try to run the built app on XP.
    "MSWSOCK.dll",

    # We're supposed to ship this wen building on Windows XP, but that will soon
    # be legacy and might not be necessary anymore. Hence for now we let it go.
    "IPHLPAPI.dll",

    # Stuff which started to get pulled in w/ py2exe 0.6.9 (Windows 8.1).
    # Caused execution to fail at least under Windows 7.
    "AVIFIL32.dll",
    "AVICAP32.dll",
    "CRYPT32.dll",
    "MSACM32.dll",
    "MSVFW32.dll",
    "SETUPAPI.dll",

    # More things that py2exe pulled, which caused failure to run under Server 2016
    "msimg32.dll",
    "oleacc.dll",
    "uxtheme.dll",

    'libopenblas.TXA6YQSD3GCQQC22GEQ54J2UDCXDXHWN.gfortran-win_amd64.dll',


] + generateExcludeList(["1-1-0", "1-1-1", "1-2-1", "1-1-2", "1-2-0", "2-1-0"])

ignores  = [
    # Specifically exclude these--we don't want them shipping with the built
    # application...
    "IqtPipelines",
    "DevelopmentPipelines",

    # Ignore these two.  Stupid email module and capitalization...  Note that
    # we explicitly include the lowercase versions of these where used in
    # the python code.
    "email.Generator",
    "email.Iterators",

    # I'm not sure why all the rest of these errors come up, but it seems worth
    # it to ignore them since they don't seem to hurt, and it's important
    # to know about any other errors that might come up...
    'win32com.shell',
    'multiprocessing._mmap25',
    'mx',

    'Carbon',

    'IPython.Shell',

    'nose',
    'nose.plugins',
    'nose.plugins.base',
    'nose.plugins.builtin',
    'nose.plugins.errorclass',
    'nose.tools',
    'nose.util',

    'Pyrex.Compiler.Main',

    '__svn_version__',

    '_curses',
    '_imaging_gif',
    '_imagingagg',

    'core.abs',
    'core.max',
    'core.min',
    'core.round',

    'dbgp.client',

    'enthought.pyface.action.action_item',
    'enthought.pyface.api',
    'enthought.pyface.dock.dock_sizer',
    'enthought.pyface.dock.dock_window',
    'enthought.pyface.image_button',
    'enthought.traits',
    'enthought.traits.api',
    'enthought.traits.ui.api',
    'enthought.traits.ui.menu',
    'enthought.traits.ui.wx.basic_editor_factory',

    'email.Utils',
    'email.base64MIME',

    'fcompiler.FCompiler',
    'fcompiler.show_fcompilers',

    'lib.add_newdoc',

    'matplotlib.backend_bases',
    'matplotlib.backends.backend_agg',
    'matplotlib.backends.backend_wx',
    'matplotlib.backends.backend_wxagg',
    'matplotlib.figure',

    'numscons',
    'numscons.core.utils',

    'pylab',

    'setuptools',
    'setuptools.command',
    'setuptools.command.bdist_rpm',
    'setuptools.command.develop',
    'setuptools.command.egg_info',
    'setuptools.command.install',
    'setuptools.command.sdist',

    'testing.Tester',

    'Numeric',
    'numarray',
]

includes  = [
    # PyOpenGL is completely missed because they do a lot of delayed imports
    # in their modules, so we specifically include them here...
    "OpenGL.GL.*",
    "OpenGL.wrapper.*",
    "OpenGL.converters.*",
    "OpenGL.latebind.*",
    "OpenGL.arrays.*",
    "OpenGL.platform.win32",
    "OpenGL.platform.baseplatform.*",
    # ImageSensor needs PIL.ImageOps
    "PIL.ImageOps",
    "multiprocessing.*",
    # We used to include these things in VitaKit, but I'm not sure why.  They
    # don't seem needed any more...
    #"functools",
    #"pydoc",
    #"pywintypes",
    #"shutil",
    #"win32con",
    #"win32file",
    #"distutils.ccompiler",
    #"distutils.sysconfig",
    #"distutils.version",
    #"distutils.msvccompiler",
    #"distutils.unixccompiler",
    #"Queue",
    #"sets",
]

options = {
    "py2exe": {
        "compressed": 1,
        "optimize": 1,
        "excludes": excludes,
        "ignores": ignores,
        "includes": includes,
        "dll_excludes": dllexcludes,
        "dist_dir": "..\\..\\..\\app-out\\frontEnd-Win",
    }
}

RT_MANIFEST = 24


################################################################
if __name__ == '__main__':
    import py2exe

    # If run without args, build executables, in quiet mode.
    if len(sys.argv) == 1:
        sys.argv.append("py2exe")
        sys.argv.append("-q")

    comCtl=""
    try:
        svarch = os.getenv("SVARCH")
        if svarch == "x86_64":
            processorArchitecture = "amd64"
        elif svarch == "i386":
            processorArchitecture = "x86"
            comCtl=comctl_template
        else:
            processorArchitecture = "amd64"
    except:
        processorArchitecture = "amd64"


    myApp = Target(
        # used for the versioninfo resource
        description = kAppName,

        # what to build
        script = "FrontEndLaunchpad.py",
        other_resources = [(RT_MANIFEST, 1, manifest_template % dict(prog=kExeName, arch=processorArchitecture, comctlasm=comCtl))],
        icon_resources = [(0, "icons/SmartVideoApp.ico")],
        dest_base = kExeName)

    setup(
        data_files = DATA_FILES,
        options = options,
        windows = [myApp],
        )
