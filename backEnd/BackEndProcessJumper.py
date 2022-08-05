#! /usr/local/bin/python

#*****************************************************************************
#
# BackEndProcessJumper.py
#   Spawning of child processes (web, camera, NMS, etc) by the backEnd.
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
# https://github.url/thing
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



import sys
from multiprocessing import Process
import traceback


# Here's an attempt to describe what's going on here, and why it's different
# between different platforms.
#
# On MacOS, we use "fork" to start our subprocesses.  What happens here is that
# the current process is cloned (using a whole bunch of virtual memory tricks)
# and then the parent and child go along their merry ways.  If a parent
# allocated a bunch of memory (or imported a library) before the child forked
# and neither the parent or the child changes that memory, then they both get
# to share that memory/import.  This can be good.  However, if a parent
# allocates a bunch of memory (or imports libraries) that the child doesn't
# really need, forks the child, then changes that memory, then the child has
# a wasted copy of memory.  It's hard to balance these two things, but here's
# what we do on Mac:
#   We do the import of the required module _just before_ forking. Any future
#   processes will get the benefit (or penalty) of already having the import.
#   This is especially interesting for the camera processes, which have a large
#   overhead for import (but can potentially share stuff between processes
#   through us, the parent).
#
# ...if we wanted to, we could pick and choose different strategies for
# different imports depending on how much shared import state we thought the
# different children could share with each other.
#
# On Windows, we don't have "fork".  That means that each subprocess starts up
# a whole new copy of python and there is no memory sharing (other than read-
# only memory).  In this case, we really don't want the parent to load up
# anything it doesn't have to--there's no chance that children will share it.

if sys.platform=='darwin':
    def doRunCapture(*args):
        import CameraCapture
        CameraCapture.runCapture(*args)

    def startCapture(*args):
        p = Process(target=doRunCapture, args=args)
        p.start()
        return p

    def startDiskCleaner(*args):
        from DiskCleaner import runDiskCleaner
        p = Process(target=runDiskCleaner, args=args)
        p.start()
        return p

    def startNetworkMessageServer(*args):
        from NetworkMessageServer import runNetworkMessageServer
        p = Process(target=runNetworkMessageServer, args=args)
        p.start()
        return p

    def startResponseRunner(*args):
        from ResponseRunner import runResponseRunner
        p = Process(target=runResponseRunner, args=args)
        p.start()
        return p

    def startStream(*args):
        from TestStream import runStream
        p = Process(target=runStream, args=args)
        p.start()
        return p

    def startWebServer(*args):
        from WebServer import runWebServer
        p = Process(target=runWebServer, args=args)
        p.start()
        return p

    def startPlatformHTTPWrapper(*args):
        from PlatformHTTPWrapper import runPlatformHTTPWrapper
        p = Process(target=runPlatformHTTPWrapper, args=args)
        p.start()
        return p

    def startPacketCapture(*args):
        from PacketCaptureStream import runPacketCapture
        p = Process(target=runPacketCapture, args=args)
        p.start()
        return p
else:
    def runCapture(*args):
        import CameraCapture
        CameraCapture.runCapture(*args)
    def startCapture(*args): #PYCHECKER OK: redefining attribute startCapture
        p = Process(target=runCapture, args=args)
        p.start()
        return p

    def runDiskCleaner(*args):
        import DiskCleaner
        DiskCleaner.runDiskCleaner(*args)
    def startDiskCleaner(*args): #PYCHECKER OK: redefining attribute startDiskCleaner
        p = Process(target=runDiskCleaner, args=args)
        p.start()
        return p

    def runNetworkMessageServer(*args):
        import NetworkMessageServer
        NetworkMessageServer.runNetworkMessageServer(*args)
    def startNetworkMessageServer(*args): #PYCHECKER OK: redefining attribute startNetworkMessageServer
        p = Process(target=runNetworkMessageServer, args=args)
        p.start()
        return p

    def runResponseRunner(*args):
        import ResponseRunner
        ResponseRunner.runResponseRunner(*args)
    def startResponseRunner(*args): #PYCHECKER OK: redefining attribute startResponseRunner
        p = Process(target=runResponseRunner, args=args)
        p.start()
        return p

    def runStream(*args):
        import TestStream
        TestStream.runStream(*args)
    def startStream(*args): #PYCHECKER OK: redefining attribute startStream
        p = Process(target=runStream, args=args)
        p.start()
        return p

    def runWebServer(*args):
        import WebServer
        WebServer.runWebServer(*args)
    def startWebServer(*args):
        p = Process(target=runWebServer, args=args)
        p.start()
        return p

    def runPlatformHTTPWrapper(*args):
        import PlatformHTTPWrapper
        PlatformHTTPWrapper.runPlatformHTTPWrapper(*args)

    def startPlatformHTTPWrapper(*args):
        import os
        intelPath = os.environ.get('INTEL_DEV_REDIST')
        if intelPath is None or len(intelPath) == 0:
            raise Exception( "Error: INTEL_DEV_REDIST not defined; analytics process will fail" )
        backupPath = os.environ.get('PATH',None)
        os.environ['PATH'] = os.path.join(intelPath, "redist", "intel64", "compiler") + ";" + backupPath
        p = Process(target=runPlatformHTTPWrapper, args=args)
        p.start()
        os.environ['PATH'] = backupPath
        return p

    def runPacketCapture(*args):
        import PacketCaptureStream
        PacketCaptureStream.runPacketCapture(*args)
    def startPacketCapture(*args):
        p = Process(target=runPacketCapture, args=args)
        p.start()
        return p