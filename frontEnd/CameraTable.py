#!/usr/bin/env python

#*****************************************************************************
#
# CameraTable.py
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


# Python imports...
import itertools
import operator
import sys

# Common 3rd-party imports...

# Toolbox imports...

# Local imports...


# Globals...

_kDebugWithoutSpecificUpnp = False
_kDebugWithoutGenericUpnp = False

# Constants

# Will be set to False by OEM patches...
kWantOtherCamOption = True


kOtherIpCamType = "Other IP camera"   # Stored in prefs!  Don't change...
kWebcamCamType = "Webcam"             # Stored in prefs!  Don't change...

kOtherCameraManufacturer = "Other"


# Maps used in settings that add in strings by resolution.  Note that the
# "None" resolution is used when none of the other resolutions match...
kResMaps = {
    # This is used for Instar cameras to construct the URL...
    'Instar': {
        (320, 240): "8",
        (640, 480): "32",
        None:       "32",
    },


    # This is used for IQinVision cameras to construct the URL...
    # They don't seem to recognize names above 'vga', so we just leave
    # downsampling off in that case...
    'IQinVision': {
        (320, 240): "&ds=QVGA",
        (640, 480): "&ds=VGA",
        None:       "",
    },

    # This is used for cameras that require that we specify a resolution and only
    # support 320x240 and 640x480.  Many Panasonic MPEG4 streams are like this.
    '640_480Required' : {
        (320, 240): "320x240",
        (640, 480): "640x480",
        None:       "640x480",
    },

    # This is used for Panasonic MJPEG streams that max out at 640x480.  Note
    # that we don't specify any resolution at all if the user has picked
    # something other than 320x240 or 640x480, which should be the most
    # compatible.
    'PanasonicMjpeg640_480': {
        (320, 240): "&Resolution=320x240",
        (640, 480): "&Resolution=640x480",
        None:       "",
    },

    # Special case for this camera, which supports MPEG4, but only at lower
    # resolutions (need to go to MJPEG for higher ones)...
    'PanasonicBB-HCM515': {
        ( 320,  240): "rtpOverHttp?Url=nphMpeg4/nil-320x240",
        ( 640,  480): "rtpOverHttp?Url=nphMpeg4/nil-640x480",
        (1024,  768): "nphMotionJpeg?Quality=Standard&Resolution=1280x1024",
        (1280, 1024): "nphMotionJpeg?Quality=Standard&Resolution=1280x1024",
        None:         "nphMotionJpeg?Quality=Standard",
    },

    # This is used for Axis cameras that max out at 640x480.  Note that we don't
    # specify any resolution at all if the user has picked something other than
    # 320x240 or 640x480, which should be the most compatible.
    'Axis640_480': {
        (320, 240): "&resolution=320x240",
        (640, 480): "&resolution=640x480",
        None:       "",
    },

    # The Logitech 750e and 750i use this scheme...
    # Resolution mapping is based on this URL:
    #   http://forums.logitech.com/t5/Alert-Security-Systems/Streaming-amp-Recording-Clarification/td-p/500862
    'Logitech750': {
        (320, 240): "LowResolutionVideo",
        (640, 480): "LowResolutionVideo",
        None:       "HighResolutionVideo",  # Said to be 960x720 (?)
    }
}


# Private camera table, used to make other (generated) tables...
_kCameraTable = [
    # ACTi notes:
    # - ACTi RTSP runs on port 7070 by default, so we've got to tell the user
    #   this (or fix the code to default to 7070).
    # - ACTi ACM series works over http://, but only with newer firmware.
    #   It first started working with firmware v3.11.11, which is now nowhere
    #   to be seen.  It continutes to work with v3.11.13
    # - ACTi TCM series support UPnP, but badly.  They respond incorrectly to
    #   our MSEARCH.  We've worked around this, and some other UPnP issues, but
    #   they still sometimes tell us the wrong IP (if their IP changes).
    #   Also, since TCM only supports rtsp, this doesn't help (we can't find
    #   out rtsp port number from UPnP)
    # - ACTi ACM series support UPnP too, but you need a hidden URL to turn
    #   it on.
    # - In order to get ACM series to work with RTSP, user needs to manually
    #   turn on RTP over UDP under 'video setting'.  Luckily, we don't suggest
    #   RTSP on ACM series.
    # - H264 and MPEG4 seem to work fine over RTSP, but not MJPEG.  Over http,
    #   MPEG4 and MJPEG work fine (H264 is only supported on TCM, which doesn't
    #   support http).  Note that H.264 doesn't seem to send as many keyframes.
    #   ...this is bad, since we seem to get glitches when the resolution is
    #   high (even with MPEG4).  Description suggests MPEG4 and asks the user
    #   to provide a lower resolution.
    # - Some ACTi models have N vs. P versions.  The N is NTSP and P is PAL.
    #   It appears that this gives them different resolution choices.
    # - All ACM and all TCM are supposed to behave alike, which is why we've
    #   added all of them that we know about.
    # - All ACTi cameras tested do DHCP by default.
    # - Default user: Admin.  Default pass: 123456
    ("ACTi", "ACTi ACM-1011",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-1231",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-1232",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-1311N",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-1311P",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-1431N",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-1431P",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-1432N",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-1432P",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-1511",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-3001",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3011",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3211N",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3211P",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3311N",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3311P",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3401",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3411",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3511",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-3601",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3603",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-3701",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-3703",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-4000",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-4001",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet, Tested in-house
    ("ACTi", "ACTi ACM-4200",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-4201",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    ("ACTi", "ACTi ACM-5001",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-5601",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-5611",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-5711N",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-5711P",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-7411",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet
    #("ACTi", "ACTi ACM-7511",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # In ACTi material, but not ACTi web.
    ("ACTi", "ACTi ACM-8201",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-8211",     ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #
    ("ACTi", "ACTi ACM-8511N",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # Spreadsheet, Tested in-house (loaner program)
    ("ACTi", "ACTi ACM-8511P",    ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   #

    ("ACTi", "ACTi D32",          ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),   # User confirmed, case 7768
    ("ACTi", "ACTi E77",          ("rtsp://", "/", 7070)),                                # User reported, 10508

    ("ACTi", "ACTi TCM-4101",     ("rtsp://", "/", 7070)),                                # Spreadsheet
    ("ACTi", "ACTi TCM-4301",     ("rtsp://", "/", 7070)),                                # Spreadsheet, Tested in-house (loaner program)
    ("ACTi", "ACTi TCM-5311",     ("rtsp://", "/", 7070)),                                #
    ("ACTi", "ACTi TCM-5312",     ("rtsp://", "/", 7070)),                                #

    ("ACTi", "ACTi (other ACM)",            ("http://", "/cgi-bin/encoder?USER=__USERNAME__&PWD=__PASSWORD__&GET_STREAM", None)),
    ("ACTi", "ACTi (other ACM - old)",     ("http://", "/cgi-bin/cmd/system?GET_STREAM", None)),
    ("ACTi", "ACTi (other TCM)",            ("rtsp://", "/", 7070)),


    # Airlink notes:
    # - See TV-IP312W notes for a discussion on some Airlink cameras.
    ("Airlink", "Airlink AIC250",             ("http://", "/mjpeg.cgi", None)),                 # Tested in-house
    ("Airlink", "Airlink AIC250W",            ("http://", "/mjpeg.cgi", None)),                 #
    ("Airlink", "Airlink AICN500",            ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)), #
    ("Airlink", "Airlink AICN500W",           ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)), # User confirmed
    ("Airlink", "Airlink (other - type A)",   ("http://", "/mjpeg.cgi", None)),
    ("Airlink", "Airlink (other - type B)",   ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    #("Airlink", "Airlink (other - type C)",   ("http://", "/cgi/mjpg/mjpg.cgi", None)),

    ("AirLive", "AirLive AirCam OD-600HD",    ("rtsp://", "/h264/media.amp", None)),  # User reported, bug 3108.
    ("AirLive", "AirLive (other)",            ("rtsp://", "/h264/media.amp", None)),  # User reported, bug 3108.


    # Alibi - user confirmed, http://www.sighthound.com/forums/topic11615
    ("Alibi", "Alibi ALI-IPU3013R",  ("rtsp://", "/play1.sdp", None)),
    ("Alibi", "Alibi (other)",       ("rtsp://", "/play1.sdp", None)),


    ("Android Device", "IP Webcam",     ("http://", "/video", 8080)),
    ("Android Device", "Ocular",        ("rtsp://", "/", None)),


    # Apexis - Reported by manufacturer, bug 3094
    ("Apexis", "Apexis APM-J010-WS",          ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis APM-J011-WS",          ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis APM-J012-WS",          ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis APM-J018-WS",          ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis APM-J0111-WS",         ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis APM-J0118-WS",         ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis APM-J0233-WS-IR",      ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis APM-J601-WS-IR",       ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis APM-J602-WS-IR",       ("http://", "/videostream.cgi", None)),
    ("Apexis", "Apexis (other)",              ("http://", "/videostream.cgi", None)),

    # Asante Notes:
    # The suggested RTSP urls are /cam1/mpeg4 and /cam1/mjpeg, we don't
    # currently work with those.
    #
    # IMPORTANT: Keep CameraTable in sync w/ Asante OEM CameraTable here.
    #
    # Default user/pass: root/root
    ("Asante", "Asante Voyager I", ("http://", "/image.cgi?type=motion", None)), # Tested remotely
    ("Asante", "Asante Voyager II", ("http://", "/image.cgi?type=motion", None)), # Tested remotely
    ("Asante", "Asante (other)",   ("http://", "/image.cgi?type=motion", None)), # Tested remotely

    ("Asgari", "Asgari 720U",     ("http://", "/videostream.cgi", 99)), # Manufacturer reported, 8237
    ("Asgari", "Asgari EZPT",     ("http://", "/videostream.cgi", 99)), # Manufacturer reported, 8237
    ("Asgari", "Asgari PTG2",     ("http://", "/videostream.cgi", 99)), # Manufacturer reported, 8237
    ("Asgari", "Asgari PTG3",     ("rtsp://", "/11", None)),            # Manufacturer reported, 15257
    ("Asgari", "Asgari UIR",      ("http://", "/videostream.cgi", 99)), # Manufacturer reported, 8237
    ("Asgari", "Asgari (other)",  ("http://", "/videostream.cgi", 99)), # Manufacturer reported, 8237

    # AVTech, user reported in bug 4107
    ("AVTech", "AVTech AVI321 PTZ",   ("http://", "/cgi-bin/guest/video.cgi", None)),
    ("AVTech", "AVTech AVM542B",      ("rtsp://", "/live/video/H264/profile1", None)),
    ("AVTech", "AVTech (other HTTP)", ("http://", "/cgi-bin/guest/video.cgi", None)),
    ("AVTech", "AVTech (other RTSP)", ("rtsp://", "/live/video/H264/profile1", None)),

    # AvertX - forum reported, AvertX response to him:
    # From: Clinton
    # To: JPElectron
    # Thank you for contacting customer support.
    # Yes, our cameras do work with Vitamin D software. The streams for the camera are:
    # rtsp://<ip addr>/h264
    # rtsp://<ip addr>/h264_2
    # rtsp://<ip addr>/mjpeg
    # Please note that Vitamin D does not support the camera's native resolution
    # at 2MP, and will turn the camera stream down.  In addition, if you are
    # using the Vitamin D software, you will not be able to connect using an
    # AvertX recorder. Please let us know if you have any other questions.
    ("AvertX", "AvertX (other H264)",      ("rtsp://", "/h264", None)),
    ("AvertX", "AvertX (other MJPEG)",     ("rtsp://", "/mjpeg", None)),

    # Axis notes:
    # - On some cameras (I noticed it on Axis 213 PTZ), the camera doesn't
    #   actually give us QVGA/VGA resolution back.  Instead, it gives us a
    #   resolution that is sorta close.  When we request VGA, we get 704x576.
    # - On other cameras, the camera will squish the image to fit into VGA.
    ####("Axis", "Axis 206",             ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 207",             ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet, Tested via: extcam-1.se.axis.com, not Axis in product list on web
    ("Axis", "Axis 207W",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet, Tested in-house
    ("Axis", "Axis 207MW",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet, Tested via: extcam-2.se.axis.com
    ("Axis", "Axis 209FD",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 209FD-R",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 209MFD",          ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-3.se.axis.com
    ("Axis", "Axis 209MFD-R",        ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 210",             ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet, Tested via: extcam-4.se.axis.com
    ("Axis", "Axis 210A",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet
    ("Axis", "Axis 211",             ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-5.se.axis.com
    ("Axis", "Axis 211A",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 211M",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-6.se.axis.com
    ("Axis", "Axis 211W",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 212 PTZ",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-7.se.axis.com
    ("Axis", "Axis 212 PTZ-V",       ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 213 PTZ",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-8.se.axis.com
    ("Axis", "Axis 214 PTZ",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-9.se.axis.com
    ("Axis", "Axis 215 PTZ",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-10.se.axis.com
    ("Axis", "Axis 215 PTZ-E",       ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 216FD",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-11.se.axis.com
    ("Axis", "Axis 216FD-V",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 216MFD",          ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-12.se.axis.com
    ("Axis", "Axis 216MFD-V",        ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 221",             ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-13.se.axis.com (also on extcam-14.se.axis.com (night) and -22)
    ("Axis", "Axis 223M",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-15.se.axis.com
    ("Axis", "Axis 225FD",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-16.se.axis.com
    ("Axis", "Axis 231D+",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 232D+",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis 233D",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-17.se.axis.com
    # NOTE: purposely don't support Axis 240Q, since it only provides 6FPS...
    ("Axis", "Axis 241Q - port 1",   ("http://", "/axis-cgi/mjpg/video.cgi?camera=1&fps=10", None)),  # VIDEO ENCODER.  See <https://vitamind.fogbugz.com/default.asp?1644#11069>
    ("Axis", "Axis 241Q - port 2",   ("http://", "/axis-cgi/mjpg/video.cgi?camera=2&fps=10", None)),  # ...TODO: Test to see if 'resolution' is accepted here
    ("Axis", "Axis 241Q - port 3",   ("http://", "/axis-cgi/mjpg/video.cgi?camera=3&fps=10", None)),  # ...
    ("Axis", "Axis 241Q - port 4",   ("http://", "/axis-cgi/mjpg/video.cgi?camera=4&fps=10", None)),  # ...
    ("Axis", "Axis 241QA - port 1",  ("http://", "/axis-cgi/mjpg/video.cgi?camera=1&fps=10", None)),  # Same as 241Q, but with Audio...
    ("Axis", "Axis 241QA - port 2",  ("http://", "/axis-cgi/mjpg/video.cgi?camera=2&fps=10", None)),  # ...
    ("Axis", "Axis 241QA - port 3",  ("http://", "/axis-cgi/mjpg/video.cgi?camera=3&fps=10", None)),  # ...
    ("Axis", "Axis 241QA - port 4",  ("http://", "/axis-cgi/mjpg/video.cgi?camera=4&fps=10", None)),  # ...
    ("Axis", "Axis 243Q",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # User on forum: https://vitamind.fogbugz.com/default.asp?video.1.200.1
    ("Axis", "Axis 247S",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10", None)),                     # VIDEO ENCODER.  User reported.  See <https://vitamind.fogbugz.com/default.asp?2770>
    ("Axis", "Axis 2120",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10", None)), # User confirmed, bug 2858
                                                                                                                #   TODO: squarepixel?  resolution?
    ("Axis", "Axis M1004-W",         ("rtsp://", "/axis-media/media.amp", None)),  # Axis Manual
    ("Axis", "Axis M1011",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet
    ("Axis", "Axis M1011-W",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet, Tested in-house (Bob)
    ("Axis", "Axis M1013",           ("rtsp://", "/axis-media/media.amp", None)),  # Axis Manual
    ("Axis", "Axis M1014",           ("rtsp://", "/axis-media/media.amp", None)),  # Axis Manual
    ("Axis", "Axis M1025",           ("rtsp://", "/axis-media/media.amp", None)),  # User reported, case 13201
    ("Axis", "Axis M1031-W",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet, Tested in-house (also on extcam-20.se.axis.com)
    ("Axis", "Axis M1033-W",         ("rtsp://", "/axis-media/media.amp", None)),  # Axis Manual
    ("Axis", "Axis M1034-W",         ("rtsp://", "/axis-media/media.amp", None)),  # Axis Manual
    ("Axis", "Axis M1054",           ("rtsp://", "/axis-media/media.amp", None)),  # Tested in house
    ("Axis", "Axis M1103",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Datasheet; similar to M1104 (but not widescreen).
    ("Axis", "Axis M1104",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10", None)),  # Datasheet says same as M1114.
    ("Axis", "Axis M1113",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Datasheet; similar to M1114 (but not widescreen).
    ("Axis", "Axis M1114",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10", None)),  # User, bug 3134.  Widescreen so don't use Res_Axis640_480 or it will crop.
    ("Axis", "Axis M3011",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # User confirmed: http://vitamindvideo.com/forums/viewtopic.php?f=5&t=48
    ("Axis", "Axis M3014",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-25.se.axis.com
    ("Axis", "Axis M3024-LVE",       ("rtsp://", "/axis-media/media.amp", None)),  # Tested via: extcam-25.se.axis.com
    ("Axis", "Axis P1311",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet, Tested via: extcam-23.se.axis.com
    ("Axis", "Axis P1343",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet
    ("Axis", "Axis P1344",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Spreadsheet; User confirmed: http://vitamindvideo.com/forums/viewtopic.php?f=5&t=48
    ("Axis", "Axis P1346",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # (not in VAPIX list)
    ("Axis", "Axis P3301",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-18.se.axis.com
    ("Axis", "Axis P3301-V",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis P3343",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis P3343-V",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis P3343-VE",        ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis P3344",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-26.se.axis.com
    ("Axis", "Axis P3344-V",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis P3344-VE",        ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis Q1755",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # Tested via: extcam-24.se.axis.com
    ("Axis", "Axis Q1910",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # (not in VAPIX list)
    ("Axis", "Axis Q1910-E",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  # (not in VAPIX list)
    ("Axis", "Axis Q6032-E",         ("http://", "/axis-cgi/mjpg/video.cgi?fps=10%(Res_Axis640_480)s", None)),  #
    ("Axis", "Axis Q7401",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10&squarepixel=1", None)),                    # Tested via: extcam-19.se.axis.com, VIDEO ENCODER
    ("Axis", "Axis Q7404",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10&squarepixel=1", None)),                    #
    ("Axis", "Axis Q7406",           ("http://", "/axis-cgi/mjpg/video.cgi?fps=10&squarepixel=1", None)),                    # User on forum: https://vitamind.fogbugz.com/default.asp?video.1.200.1
    # TODO: 1-channel video encoders?
    # ...like M7001, 241S, 243SA, 247S

    ("Axis", "Axis (other H264)",             ("rtsp://", "/axis-media/media.amp", None)),
    ("Axis", "Axis (other MJPEG)",            ("http://", "/axis-cgi/mjpg/video.cgi?fps=10", None)),
    ("Axis", "Axis (other MPEG-4 - type A)",  ("rtsp://", "/mpeg4/media.amp", None)),
    ("Axis", "Axis (other MPEG-4 - type B)",  ("rtsp://", "/mpeg4/media.amp", None)),


    # Reported by the manufactuer, no specific models mentioned, https://ayrstone.zendesk.com/attachments/token/lgo9eyfwlg4dysp/?name=VitaminD.pdf
    ("Ayrstone", "Ayrstone (other)",  ("http://", "/videostream.cgi", None)),


    ("Brickcom", "Brickcom WOB-100Ap", ("rtsp://", "/channel1", None)), # User reported
    ("Brickcom", "Brickcom WOB-130Np", ("rtsp://", "/channel1", None)), # User reported
    ("Brickcom", "Brickcom (other)",   ("rtsp://", "/channel1", None)), # User reported

    # User reported... the bluepix on the manufacturers website is a webcam
    # and the only camera they seem to make currently.  Not even going to add
    # an "Other" because I don't know that they've ever had or ever will have others...
    ("Bluestork", "Bluestork Bluepix IP Camera",  ("http://", "/mjpg/video.mjpg", None)), # User reported, but 2718


    # Canon - Canon provided three loaner cameras and information in 10597, 10232, 9943
    ("Canon", "Canon VB-H41",                 ("rtsp://", "/stream/profile1=r", None)), # Tested in house
    ("Canon", "Canon VB-H610VE",              ("rtsp://", "/stream/profile1=r", None)),
    ("Canon", "Canon VB-H610D",               ("rtsp://", "/stream/profile1=r", None)),
    ("Canon", "Canon VB-H710F",               ("rtsp://", "/stream/profile1=r", None)),
    ("Canon", "Canon VB-M40",                 ("rtsp://", "/profile1=r", None)),
    ("Canon", "Canon VB-M600D",               ("rtsp://", "/profile1=r", None)), # Tested in house
    ("Canon", "Canon VB-M600VE",              ("rtsp://", "/profile1=r", None)),
    ("Canon", "Canon VB-S30D",                ("rtsp://", "/stream/profile1=r", None)), # Tested in house
    ("Canon", "Canon VB-S31D",                ("rtsp://", "/stream/profile1=r", None)),
    ("Canon", "Canon VB-S800D",               ("rtsp://", "/stream/profile1=r", None)),
    ("Canon", "Canon VB-S900F",               ("rtsp://", "/stream/profile1=r", None)),
    ("Canon", "Canon VB-S905F",               ("rtsp://", "/stream/profile1=r", None)),
    ("Canon", "Canon (other H.264 type A)",   ("rtsp://", "/stream/profile1=r", None)),
    ("Canon", "Canon (other H.264 type B)",   ("rtsp://", "/profile1=r", None)),
    ("Canon", "Canon (other H.264 type C)",   ("rtsp://", "/rtpstream/config1=r", None)),


    ("Compro", "Compro IP60",                ("rtsp://", "/medias1", None)), # Source: forum (https://vitamind.fogbugz.com/default.asp?video.1.487.4)
    ("Compro", "Compro IP540",               ("rtsp://", "/medias1", None)), # Source: ticket 2780
    ("Compro", "Compro IP570",               ("rtsp://", "/medias1", None)), # Source: ticket 2780
    ("Compro", "Compro (other - stream 1)",  ("rtsp://", "/medias1", None)), # Source: forum (https://vitamind.fogbugz.com/default.asp?video.1.487.4)
    ("Compro", "Compro (other - stream 2)",  ("rtsp://", "/medias2", None)), # Source: forum (https://vitamind.fogbugz.com/default.asp?video.1.487.4)
    ("Compro", "Compro (other - MJPEG)",     ("http://", "/mjpeg.cgi", None)), # Source: ticket 2780


    ("Cisco", "Cisco CIVS-IPC-2421",          ("rtsp://", "/img/video.sav", None)),
    ("Cisco", "Cisco CIVS-IPC-2500",          ("rtsp://", "/img/video.sav", None)),
    ("Cisco", "Cisco CIVS-IPC-2500W",         ("rtsp://", "/img/video.sav", None)),
    ("Cisco", "Cisco CIVS-IPC-2520V",         ("rtsp://", "/img/video.sav", None)),
    ("Cisco", "Cisco CIVS-IPC-2521V",         ("rtsp://", "/img/video.sav", None)),
    ("Cisco", "Cisco CIVS-IPC-2530V",         ("rtsp://", "/img/video.sav", None)),
    ("Cisco", "Cisco CIVS-IPC-2531V",         ("rtsp://", "/img/video.sav", None)),
    ("Cisco", "Cisco WV210",                  ("rtsp://", "/img/media.sav", None)), # User reported
    ("Cisco", "Cisco (other RTSP - type A)",  ("rtsp://", "/img/video.sav", None)),
    ("Cisco", "Cisco (other RTSP - type B)",  ("rtsp://", "/img/media.sav", None)),

    ("DB Power", "DB Power IP030",    ("http://", "/videostream.cgi", None)),    # User reported
    ("DB Power", "DB Power (other)",  ("http://", "/videostream.cgi", None)),


    ("Dericam", "Dericam M801W",    ("http://", "/videostream.asf", None)),    # User reported, http://www.sighthound.com/forums/topic11519
    ("Dericam", "Dericam (other)",  ("http://", "/videostream.asf", None)),


    ("Digitus", "Digitus DN-16053",       ("http://", "/live/mpeg4", None)), # 6026
    ("Digitus", "Digitus (other MPEG4)",  ("http://", "/live/mpeg4", None)),


    # Default username/password for D-Link cameras: admin, blank
    ("D-Link", "D-Link DCS-2120",               ("rtsp://", "/live.sdp", None)),
    ("D-Link", "D-Link DCS-2132LB1",            ("rtsp://", "/live1.sdp", None)),
    ("D-Link", "D-Link DCS-3110",               ("http://", "/video.mjpg", None)),
    ("D-Link", "D-Link DCS-5220",               ("rtsp://", "/live.sdp", None)),
    ("D-Link", "D-Link DCS-6110",               ("rtsp://", "/live.sdp", None)),
    ("D-Link", "D-Link DCS-7010L",              ("rtsp://", "/live1.sdp", None)),
    ("D-Link", "D-Link DCS-910",                ("http://", "/video.cgi", None)), # User reported
    ("D-Link", "D-Link DCS-920",                ("http://", "/video.cgi", None)),
    ("D-Link", "D-Link DCS-930L",               ("http://", "/mjpeg.cgi", None)), # User reported
    ("D-Link", "D-Link DCS-930LB1",             ("http://", "/mjpeg.cgi", None)), # User reported
    ("D-Link", "D-Link DCS-932L",               ("http://", "/video.cgi", None)), # User reported, 5070
    ("D-Link", "D-Link DCS-942L",               ("rtsp://", "/play1.sdp", None)), # User reported, forums
    ("D-Link", "D-Link (other HTTP - type A)",  ("http://", "/video.cgi", None)),
    ("D-Link", "D-Link (other HTTP - type B)",  ("http://", "/video.mjpg", None)),
    ("D-Link", "D-Link (other RTSP - type A)",  ("rtsp://", "/live.sdp", None)),
    ("D-Link", "D-Link (other RTSP - type B)",  ("rtsp://", "/live.sdp", None)),


    # Edimax reported by user, ticket 3731
    ("Edimax", "Edimax IC-3030PoE",    ("http://", "/mjgpg/video.mjpg", None)), # User reported
    ("Edimax", "Edimax (other)",       ("http://", "/mjgpg/video.mjpg", None)), # User reported


    ("Encore", "Encore ENVCWI-PTG1",    ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)), # User reported
    ("Encore", "Encore (other MJPEG)",  ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),


    ("EyeSpy247", "EyeSpy247 PTZ",             ("http://", "/img/video.asf", None)),    # Confirmed in house
    ("EyeSpy247", "EyeSpy247 F+",              ("http://", "/img/video.asf", None)),    # Confirmed in house
    ("EyeSpy247", "EyeSpy247 EXT",             ("http://", "/img/video.asf", None)),    # Reported by manufacturer
    ("EyeSpy247", "EyeSpy247 UCam247",         ("http://", "/live/0/mjpeg.jpg", None)), # Reported by manufacturer, 6152
    ("EyeSpy247", "EyeSpy247 (other MPEG-4)",  ("http://", "/img/video.asf", None)),    # Confirmed in house
    ("EyeSpy247", "EyeSpy247 (other MJPEG)",   ("http://", "/img/video.mjpeg", None)),  # Confirmed in house

    ("EYEsurv", "EYEsurv ESIP-MP1.3-BT1",  ("rtsp://", "/cam/realmonitor?channel=1&subtype=0", None)),  # Reported by a user
    ("EYEsurv", "EYEsurv (other)",         ("rtsp://", "/cam/realmonitor?channel=1&subtype=0", None)),  # Reported by a user

    ("Forenix", "Forenix D0100",   ("rtsp://", "/channel1", None)), # Reported by manufacturer, #4502
    ("Forenix", "Forenix (other)", ("rtsp://", "/channel1", None)),

    ("Foscam", "Foscam FI8620W",  ("rtsp://", "/11", None)),                 # User reported, # 5461
    ("Foscam", "Foscam FI8904W",  ("http://", "/videostream.cgi", None)),    # User reported
    ("Foscam", "Foscam FI8905W",  ("http://", "/videostream.cgi", None)),    # User reported
    ("Foscam", "Foscam FI8906W",  ("http://", "/videostream.asf?user=__USERNAME__&pwd=__PASSWORD__", None)),  # User reported
    ("Foscam", "Foscam FI8908W",  ("http://", "/videostream.cgi", None)),    # User reported
    ("Foscam", "Foscam FI8910W",  ("http://", "/videostream.cgi", None)),    # User reported, # 4332
    ("Foscam", "Foscam FI8916W",  ("http://", "/videostream.cgi", None)),    # Have in house
    ("Foscam", "Foscam FI8918W",  ("http://", "/videostream.cgi", None)),    # User reported, # 3777, now have in house
    ("Foscam", "Foscam FI9801W",  ("rtsp://", "/videoMain", 88)),            # From foscam's site
    ("Foscam", "Foscam FI9802W",  ("rtsp://", "/videoMain", 88)),            # From foscam's site, user confirmed in 7073
    ("Foscam", "Foscam FI9804P",  ("rtsp://", "/videoMain", 88)), # Employee reported
    ("Foscam", "Foscam FI9818W",  ("rtsp://", "/videoMain", 88)),            # From foscam's site
    ("Foscam", "Foscam FI9820W",  ("rtsp://", "/11", None)),                 # User reported, # 4892
    ("Foscam", "Foscam FI9821W",  ("rtsp://", "/videoMain", 88)),            # From foscam's site, user confirmed
    ("Foscam", "Foscam (other H264)",            ("rtsp://", "/videoMain", 88)), # http://foscam.us/forum/how-to-use-rtsp-and-https-for-hd-cameras-t4926.html
    ("Foscam", "Foscam (other MJPEG - type A)",  ("http://", "/videostream.cgi", None)),    # User reported
    ("Foscam", "Foscam (other MJPEG - type B)",  ("http://", "/cgi-bin/CGIStream.cgi?cmd=GetMJStream&usr=__USERNAME__&pwd=__PASSWORD__", None)),


    ("GeoVision", "GeoVision GV-BL1210",  ("rtsp://", "/CHOO1.sdp", 8554)),  # User reported
    ("GeoVision", "GeoVision (other)",    ("rtsp://", "/CHOO1.sdp", 8554)),  # User reported


    # Grandstream:
    #   - User reported on forums at http://vitamindvideo.com/forums/viewtopic.php?f=5&t=718
    ("Grandstream", "Grandstream GXV3611_HD",              ("rtsp://", "/", None)),  # In house, we own one
    ("Grandstream", "Grandstream GVX3615WP_HD",            ("rtsp://", "/", None)),  # In house, we own one
    ("Grandstream", "Grandstream GXV3651_FHD",             ("rtsp://", "/", None)),  # In house, we own one
    ("Grandstream", "Grandstream (other)",                 ("rtsp://", "/", None)),
    ("Grandstream", "Grandstream (other - High quality)",  ("rtsp://", "/0", None)), # User reported
    ("Grandstream", "Grandstream (other - Low quality)",   ("rtsp://", "/4", None)), # User reported

    # Hikvision notes:
    # - We had some success with a Hikvision DS-2CD852MF-E camera, which we got
    #   on loan from Hikvision.  However, we needed to load a custom firmware
    #   on the camera that sent a MPEG-4 stream (rather than a H.264 one) in
    #   order to get things to work.  When we tried the H.264 one, we had
    #   partial success, but got lots of strange distortions, indicating that
    #   FFMPEG was having trouble decoding the stream.  We got the firmware
    #   directly from the Hikvision support--we couldn't find it on their
    #   web site anywhere.
    # - Because we had such trouble with the camera, we didn't add it directly.
    #   Instead, we added it just as an "other".  This was sorta a compromise
    #   to the fact that we really didn't want to say that we supported the
    #   camera, but wanted to make it a little easier if a customer had one and
    #   wanted to try to make it work.
    # - Default username/password is: admin/12345
    # - Default IP address is: 192.0.0.64
    # - You must use IE6 to work with the camera.  On IE8, it seems to partially
    #   work, but acts as if username/password are wrong.
    # - There doesn't appear to be a way to hard reset this camera.  Make sure
    #   you put it back to its default IP so someone else can find it!
    ("Hikvision", "Hikvision DS-2CD752MF-FB",     ("rtsp://", "/", None)), # In house
    ("Hikvision", "Hikvision DS-2CD793NFWD-E",    ("rtsp://", "/", None)), # In house
    ("Hikvision", "Hikvision DS-2CD2232-I5",      ("rtsp://", "/video.h264",  None)), # In house
    ("Hikvision", "Hikvision (other H264)",       ("rtsp://", "/", None)),
    ("Hikvision", "Hikvision (other MPEG-4)",     ("rtsp://", "/", None)),


    ("Honeywell", "Honeywell iPCAM-WI2HCV701",      ("http://", "/img/video.asf", 554)),     # User reported case 14040
    ("Honeywell", "Honeywell (other MJPEG)",        ("http://", "/img/video.mjpeg", None)),
    ("Honeywell", "Honeywell (other MPEG-4)",       ("http://", "/img/video.asf", 554)),


    ("HooToo", "HooToo HT-IP206",      ("http://", "/video.cgi", None)),  # User reported
    ("HooToo", "HooToo HT-IP211HDP",   ("rtsp://", "/11", None)),         # User reported, case 13006
    ("HooToo", "HooToo (other HTTP)",  ("http://", "/video.cgi", None)),  # User reported
    ("HooToo", "HooToo (other RTSP)",  ("rtsp://", "/11", None)),         # User reported

    ("Huacam", "Huacam HCV701",        ("rtsp://", "/", None)),                     # In house
    ("Huacam", "Huacam (other HTTP)",  ("http://", "/goform/stream?cmd=get&channel=0", None)),  # Reported by user, case 6800
    ("Huacam", "Huacam (other RTSP)",  ("rtsp://", "/", None)),                     # In house

    # Instar notes:
    # - Instar main page: http://instar-shop.de/
    # - See https://vitamind.fogbugz.com/default.asp?2646 for details about
    #   this camera support, including the CGI spec.
    # - Note that rate=6 is 10FPS according to CGI spec.
    # - To test these cameras, I used user=test, pwd=test.  That seemed
    #   to be setup on the instar test camera (instar-cam.dyndns.org:85).
    # - Default user on the instar camera is admin.  Default pass is blank.
    # - Instar cameras also support specifying user and pass in the URL
    #   (user= and pwd=).  Based on testing, that doesn't seem to be required
    #   as long as you auth properly.
    # - The instar manual for the 2901 (which is in German!) implies that the
    #   .asf file is MPEG-4, which is why I've listed it here.  Strangely, it
    #   seemed like VLC identified it as MJPEG (though maybe I read the logs
    #   incorrectly).  In any case, it worked when I tried to connect to it,
    #   so I'm listing it.  However, I'm not going to make it default without
    #   more testing.
    # - These cameras might have UPnP, but we don't know the info nor do we
    #   know how reliable their UPnP implementation may be.
    ("Instar", "Instar IN-2901", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # Assumed to match IN-3005
    ("Instar", "Instar IN-2904", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # From Instar, case 2646
    ("Instar", "Instar IN-2905", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # Assumed to match IN-3005
    ("Instar", "Instar IN-2907", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # From Instar, case 2646
    ("Instar", "Instar IN-3001", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # Assumed to match IN-3005
    ("Instar", "Instar IN-3005", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # Tested via admin:@instar-cam.dyndns.org:85
    ("Instar", "Instar IN-3010", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # Assumed to match IN-3005
    ("Instar", "Instar IN-3011", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # From Instar, case 2646
    ("Instar", "Instar IN-4009", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # From Instar, case 2646
    ("Instar", "Instar IN-4010", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # From Instar, case 2646
    ("Instar", "Instar IN-4011", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),        # From Instar, case 2646
    ("Instar", "Instar IN-5907 HD",     ("rtsp://", "/11", None)),                                    # case 7754
    ("Instar", "Instar IN-6011 HD",     ("rtsp://", "/11", None)),                                    # From Instar, case 2646
    ("Instar", "Instar IN-6012 HD",     ("rtsp://", "/11", None)),                                    # Tested remotely, case 7754
    ("Instar", "Instar IN-7011 HD",     ("rtsp://", "/11", None)),                                    # case 7754
    ("Instar", "Instar (other H264)",   ("rtsp://", "/11", None)),                                    # Tested remotely, case 7754
    ("Instar", "Instar (other MJPEG)", ("http://", "/videostream.cgi?resolution=%(Res_Instar)s&rate=6", None)),
    ("Instar", "Instar (other MPEG-4)", ("http://", "/videostream.asf?resolution=%(Res_Instar)s&rate=6", None)), # Tested via admin:@instar-cam.dyndns.org:85


    # Insteon - Foscam clones
    ("Insteon", "Insteon 75790",           ("http://", "/videostream.cgi", None)), # In house, 7503
    ("Insteon", "Insteon (other MJPEG)",   ("http://", "/videostream.cgi", None)), # In house, 7503


    ("IPCAM Central", "IPCAM Central IPCC-7207E",  ("rtsp://", "/0/main", None)),  # User reported, 12672
    ("IPCAM Central", "IPCAM Central IPCC-9605E",  ("rtsp://", "/0/main", None)),  # User reported, 12531
    ("IPCAM Central", "IPCAM Central IPCC-9610",   ("rtsp://", "/0/main", None)),  # User reported, 12671
    ("IPCAM Central", "IPCAM Central (other)",     ("rtsp://", "/0/main", None)),


    ("IPS", "IPS EO1312VW",  ("rtsp://", "/11", None)),  # User reported, 9432
    ("IPS", "IPS (other)",   ("rtsp://", "/11", None)),

    # IQinVision notes:
    # - The spush0.1 requests 10FPS from camera.
    # - Lots of virtual cameras are available on IQA22SI-B2.  Any good way
    #   to support?  ...especially if they add UPnP (add a port to UPnP flow?)
    # - On IQ041SI-V10, UPnP is on by default, but not DHCP.  Seems to work OK.
    # - On IQA22SI-B2, neither UPnP nor DHCP.  Need to find utility.
    # - Default user: root.  Default pass: SYSTEM (or system)
    # - TODO: Using ds=VGA makes sure we're VGA-sized, but can cut off the top
    #   of the picture (tested on IQ711).
    ("IQinVision", "IQinVision IQ040SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # Spreadsheet, Tested via 192.73.220.120, original is 720x480
    ("IQinVision", "IQinVision IQ041SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # Spreadsheet, Tested in-house (loaner program), Tested via 192.73.220.121, original is 1280x1024
    ("IQinVision", "IQinVision IQ042SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # Spreadsheet, Tested via 192.73.220.122, original is 1600x1200
    ("IQinVision", "IQinVision IQ510",                 ("http://", "/now.jpg?snap=spush0.1", None)),                # Tested via 192.73.220.111, original is 752x480, TODO: ds=1, 2, ...
    ("IQinVision", "IQinVision IQ511",                 ("http://", "/now.jpg?snap=spush0.1", None)),                # Tested via 192.73.220.112, original is 1280x1024, TODO: ds=1, 2, ...
    ("IQinVision", "IQinVision IQ540SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # untested
    ("IQinVision", "IQinVision IQ541SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # Tested via 192.73.220.136, original is 1280x1024
    ("IQinVision", "IQinVision IQ542SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # untested
    ("IQinVision", "IQinVision IQ702",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.114, original is 1600x1200
    ("IQinVision", "IQinVision IQ703",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.115, original is 2048x1536
    ("IQinVision", "IQinVision IQ705",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.116, original is 2560x1920
    ("IQinVision", "IQinVision IQ711",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.113, original is 1280x1024
    #("IQinVision", "IQinVision IQ732NI",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.135, original is 480x270 (??????)
    #("IQinVision", "IQinVision IQ732SI",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), #
    ("IQinVision", "IQinVision IQ751",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.131, original is 1280x1024
    ("IQinVision", "IQinVision IQ752",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.117, original is 1600x1200
    ("IQinVision", "IQinVision IQ753",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.118, original is 2048x1536
    ("IQinVision", "IQinVision IQ755",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.119, original is 2560x1920
    ("IQinVision", "IQinVision IQ802",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Specs claim same as IQ852
    ("IQinVision", "IQinVision IQ803",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Specs claim same as IQ853
    ("IQinVision", "IQinVision IQ805",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Specs claim same as IQ855
    ("IQinVision", "IQinVision IQ811",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Specs claim same as IQ851
    ("IQinVision", "IQinVision IQ851",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.127, original is 1280x1024
    ("IQinVision", "IQinVision IQ852",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.128, original is 1600x912 (not sure why not x1200)
    ("IQinVision", "IQinVision IQ853",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.129, original is 2048x1536
    ("IQinVision", "IQinVision IQ855",                 ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.130, original is 2560x1920
    ("IQinVision", "IQinVision IQD40SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # Spreadsheet, Tested via 192.73.220.132, original is 720x480
    ("IQinVision", "IQinVision IQD41SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # Spreadsheet, Tested via 192.73.220.133, original is 1280x1024
    ("IQinVision", "IQinVision IQD42SI",               ("http://", "/now.jpg?snap=spush0.1", None)),                # Spreadsheet, Tested via 192.73.220.134, original is 1600x1200
    #("IQinVision", "IQinVision IQA10N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA10S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA11N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA11S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA12N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA12S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA13N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA13S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA15N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    #("IQinVision", "IQinVision IQA15S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    ("IQinVision", "IQinVision IQA20N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Specs claim same as IQA20S
    ("IQinVision", "IQinVision IQA20S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.123, original is 640x480
    ("IQinVision", "IQinVision IQA21N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    ("IQinVision", "IQinVision IQA21S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # untested
    ("IQinVision", "IQinVision IQA22N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Specs claim same as IQA22S
    ("IQinVision", "IQinVision IQA22S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Spreadsheet, Tested in-house (loaner program), Tested via 192.73.220.124, original is 1600x1200
    ("IQinVision", "IQinVision IQA23N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Specs claim same as IQA23S
    ("IQinVision", "IQinVision IQA23S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.125, original is 2048x1536
    ("IQinVision", "IQinVision IQA25N",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Specs claim same as IQA25S
    ("IQinVision", "IQinVision IQA25S",                ("http://", "/now.jpg?snap=spush0.1%(Res_IQinVision)s", None)), # Tested via 192.73.220.126, original is 2560x1920
    ("IQinVision", "IQinVision (other IQA2xx MPEG-4)", ("rtsp://", "/now.mp4", None)),
    ("IQinVision", "IQinVision (other MJPEG)",         ("http://", "/now.jpg?snap=spush0.1", None)),
    ("IQinVision", "IQinVision (other MJPEG 1/2 scale)",("http://", "/now.jpg?snap=spush0.1&ds=2", None)),
    ("IQinVision", "IQinVision (other MJPEG 1/4 scale)",("http://", "/now.jpg?snap=spush0.1&ds=4", None)),
    #("IQinVision", "IQinVision (other IQ73xx MPEG-4)", ("http://", "/rtsp/now.mp4", None)),                         # UNTESTED, but in theory from the docs should work...


    # KARE - reported by manufacturer
    ("KARE", "KARE N5402JV",  ("http://", "/video.cgi", None)),
    ("KARE", "KARE N5403JV",  ("http://", "/video.cgi", None)),
    ("KARE", "KARE N7205JV",  ("http://", "/video.cgi", None)),
    ("KARE", "KARE (other)",   ("http://", "/video.cgi", None)),


    ("Keebox", "Keebox IPC1000W",  ("http://", "/mjpeg.cgi", None)), # User reported
    ("Keebox", "Keebox (other)",   ("http://", "/mjpeg.cgi", None)),


    # Linksys notes:
    # - no notes
    ("Linksys", "Linksys WVC11B",                  ("http://", "/img/video.asf", None)),
    ("Linksys", "Linksys WVC54GC",                 ("http://", "/img/mjpeg.cgi", None)),
    ("Linksys", "Linksys WVC54GCA",                ("http://", "/img/video.mjpeg", None)),
    ("Linksys", "Linksys WVC80N",                  ("http://", "/img/video.mjpeg", None)),
    ("Linksys", "Linksys (other MJPEG - type A)",  ("http://", "/img/video.mjpeg", None)),
    ("Linksys", "Linksys (other MJPEG - type B)",  ("http://", "/img/mjpeg.cgi", None)),
    ("Linksys", "Linksys (other MPEG-4)",          ("http://", "/img/video.asf", None)),


    # Loftek - user reported in 3941
    ("Loftek", "Loftek CXS 2200",  ("http://", "/videostream.cgi", None)),
    ("Loftek", "Loftek Nexus 543", ("http://", "/videostream.cgi", None)), # In house
    ("Loftek", "Loftek (other)",   ("http://", "/videostream.cgi", None)),


    # Logitech notes:
    # - This is all based on user reports and web searches...
    ("Logitech", "Logitech Alert 750e", ("rtsp://", "/%(Res_Logitech750)s", None)),   # User report: http://vitamindvideo.com/forums/viewtopic.php?f=5&t=119
    ("Logitech", "Logitech Alert 750i", ("rtsp://", "/%(Res_Logitech750)s", None)),   # User report: http://vitamindvideo.com/forums/viewtopic.php?f=5&t=119
    ("Logitech", "Logitech (other)",    ("rtsp://", "/%(Res_Logitech750)s", None)),   # User report: http://vitamindvideo.com/forums/viewtopic.php?f=5&t=119

    # Lorex
    ("Lorex", "Lorex LNB2153",      ("rtsp://", "/ch0_0.h264", None)), # User report: case 13164
    ("Lorex", "Lorex (other H264)", ("rtsp://", "/ch0_0.h264", None)), # User report: case 13164


    # NEO Coolcam
    ("NEO Coolcam", "NEO Coolcam NIP-06",  ("http://", "/videostream.asf?user=__USERNAME__&pwd=__PASSWORD__", None)),   # User report: http://www.sighthound.com/forums/viewtopic.php?f=5&t=5&start=10
    ("NEO Coolcam", "NEO Coolcam (other)", ("http://", "/videostream.asf?user=__USERNAME__&pwd=__PASSWORD__", None)),   # User report: http://www.sighthound.com/forums/viewtopic.php?f=5&t=5&start=10


    # Marmitek notes:
    # In bug 2892 a Marmitek employee gave URL that he claimed worked with all current cameras.
    # NOTE: I left the ?svforcemjpeg as it was required for us before and I didn't get to test the new URL.
    ("Marmitek", "Marmitek IP Eye Anywhere10",        ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek IP Eye Anywhere11",        ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek IP Eye Anywhere20",        ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek IP Eye Anywhere21",        ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek IP Eye Anywhere470",       ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek IP Robocam8",              ("http://", "/video.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek IP Robocam10",             ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek IP Robocam11",             ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek IP Robocam21",             ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek (other MJPEG - type A)",   ("http://", "/video.cgi?svforcemjpeg", None)),
    ("Marmitek", "Marmitek (other MJPEG - type B)",   ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),


    # MOBOTIX - reported by users to work. The following URLs use MJPEG rather than their
    # proprietary MxPEG format. Theoretically we could try supporting that to, but don't
    # currently compile it into our FFMpeg build.
    ("MOBOTIX", "MOBOTIX T25",            ("http://", "/cgi-bin/faststream.jpg?stream=full&needlength&fps=10", None)), # 8214
    ("MOBOTIX", "MOBOTIX (other MJPEG)",  ("http://", "/cgi-bin/faststream.jpg?stream=full&needlength&fps=10", None)), # 6160


    # Nilox reported by user
    ("Nilox", "Nilox 16NX2601FI002",  ("http://", "/snapshots.cgi", None)), # User reported
    ("Nilox", "Nilox (other)",        ("http://", "/snapshots.cgi", None)), # User reported


    # OpenEye reported by user
    ("OpenEye", "OpenEye CM-715",        ("rtsp://", "/H264", None)), # User reported
    ("OpenEye", "OpenEye (other H264)",  ("rtsp://", "/H264", None)), # User reported


    # Panasonic notes:
    # - Can choose different quality levels from the URL.  TODO: can we let the user choose.  Known values:
    #   - Standard
    #   - Clarity
    # - Even though we've only seen a few of these cameras, put lots in since Panasonic seems to be very
    #   consistent.  See Panasonic docs.
    # - TODO: HCM7xx series is supposed to support h.264.  Can we test this?
    ("Panasonic", "Panasonic BB-HCE481",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BB-HCM311",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BB-HCM331",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BB-HCM371",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BB-HCM381",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BB-HCM403",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BB-HCM511",      ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),              # Spreadsheet
    ("Panasonic", "Panasonic BB-HCM515",      ("http://", "/%(Res_PanasonicBB-HCM515)s", None)),                                        # Spreadsheet - NOTE: supports 1280x1024 using MJPEG
    ("Panasonic", "Panasonic BB-HCM527",      ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),
    ("Panasonic", "Panasonic BB-HCM531",      ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),              # Spreadsheet
    ("Panasonic", "Panasonic BB-HCM547",      ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),
    ("Panasonic", "Panasonic BB-HCM580",      ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),
    ("Panasonic", "Panasonic BB-HCM581",      ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),
    #("Panasonic", "Panasonic BB-HCM701",      ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),  # 640x480 max, supports EITHER MPEG4 or H.264
    #("Panasonic", "Panasonic BB-HCM705",      ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),
    #("Panasonic", "Panasonic BB-HCM715",      ("http://", "/nphH264AACauth?Resolution=1280x960", None)),
    #("Panasonic", "Panasonic BB-HCM735",      ("http://", "/nphH264AACauth?Resolution=1280x960", None)),
    ("Panasonic", "Panasonic BB-HCS301",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BL-C1",          ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BL-C10",         ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic BL-C20",         ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)), # Spreadsheet, Tested in-house (us)
    ("Panasonic", "Panasonic BL-C30",         ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)), # Kirkwood tester
    ("Panasonic", "Panasonic BL-C101",        ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),              # Spreadsheet, Guess (same as 121), not in CGI doc
    ("Panasonic", "Panasonic BL-C111",        ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),              # Spreadsheet
    ("Panasonic", "Panasonic BL-C121",        ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),              # Spreadsheet, Tested in-house (Greg), not in CGI doc
    ("Panasonic", "Panasonic BL-C131",        ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),              # Spreadsheet, Tested in-house (Numenta)
    ("Panasonic", "Panasonic BL-C140",        ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),              # Spreadsheet, Tested in-house (Mitch H)
    ("Panasonic", "Panasonic BL-C160",        ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),              # Spreadsheet
    ("Panasonic", "Panasonic BL-C230",        ("http://", "/nphH264AACauth?Resolution=%(Res_640_480Required)s", None)),                 # User reported
    ("Panasonic", "Panasonic KX-HCM110",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic KX-HCM280",      ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic (other MJPEG)",  ("http://", "/nphMotionJpeg?Quality=Standard%(Res_PanasonicMjpeg640_480)s", None)),
    ("Panasonic", "Panasonic (other MPEG-4)", ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),
    #("Panasonic", "Panasonic (other H.264)",  ("http://", "/nphH264AACauth", None)),
    #("Panasonic", "Panasonic (other MPEG-4 1280x960)", ("http://", "/rtpOverHttp?Url=nphMpeg4/nil-%(Res_640_480Required)s", None)),

    # Polaroid
    ("Polaroid", "Polaroid IP302",    ("http://", "/videostream.asf?user=__USERNAME__&pwd=__PASSWORD__", None)),  # User reported
    ("Polaroid", "Polaroid (other)",  ("http://", "/videostream.asf?user=__USERNAME__&pwd=__PASSWORD__", None)),  # User reported

    ("Samsung", "SNZ-5200",                          ("rtsp://", "/profile1/media.smp", None)), # User reported, 8367
    ("Samsung", "Samsung SmartCam HD Pro",           ("rtsp://", "/profile5/media.smp", None)), # User reported, 12670, Brent owns
    ("Samsung", "Samsung (other RTSP - Profile 1)",  ("rtsp://", "/profile1/media.smp", None)),
    ("Samsung", "Samsung (other RTSP - Profile 5)",  ("rtsp://", "/profile5/media.smp", None)),


    ("Sanyo", "Sanyo VCC-HD4600",  ("rtsp://", "/videoinput/1/h264/1", None)), # User reported
    ("Sanyo", "Sanyo (other)",     ("rtsp://", "/videoinput/1/h264/1", None)),


    ("Sharx", "Sharx SCNC2607", ("http://", "/stream.jpg", None)),
    ("Sharx", "Sharx (other)",  ("http://", "/stream.jpg", None)),

    # Sony notes:
    # - Default username / password is admin/admin
    # - Need to use "IP Setup Program" to find.
    # - When getting 'image', Sony cameras will try to get MPEG4 or MJPEG
    #   stream according to how the camera is configured (at least, that's true
    #   on 2nd and 4th gen)
    # - When models have N and P, I believe this is NTSC and PAL.
    # - 3rd and 5th gen have H.264, which has been tested to work.
    #   That means if you ask for /image, you might get any of MJPEG, MPEG4, or H.264
    # - 5th gen manual says implies that you might not be able to put ?speed=10
    #   on the end of an /image request.  The stream works, the parameter is likely just
    #   ignored.  Note that speed=10 really only makes sense on MJPEG streams, so I assume
    #   that gens 2-4 ignore it when you request "image" and the codec is MPEG4.
    ("Sony", "Sony SNC-CM120",      ("http://", "/image?speed=10", None)),    # 4th gen
    ("Sony", "Sony SNC-CH140",      ("http://", "/image?speed=10", None)),    # 5th gen, tested remotely
    ("Sony", "Sony SNC-CH180",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-CS10",       ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-CS11",       ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-CS20",       ("http://", "/image?speed=10", None)),    # 4th gen
    ("Sony", "Sony SNC-CS50N",      ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-CS50P",      ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-DF40N",      ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-DF40P",      ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-DF50N",      ("http://", "/image?speed=10", None)),    # 3rd gen, tested remotely
    ("Sony", "Sony SNC-DF50P",      ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-DF70N",      ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-DF70P",      ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-DF80N",      ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-DF80P",      ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-DF85N",      ("http://", "/image?speed=10", None)),    # 3rd gen, tested remotely
    ("Sony", "Sony SNC-DF85P",      ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-DH140",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-DH180",      ("http://", "/image?speed=10", None)),    # 5th gen, tested remotely
    ("Sony", "Sony SNC-DM110",      ("http://", "/image?speed=10", None)),    # Spreadsheet, 4th gen, Tested in-house (loaner program)
    ("Sony", "Sony SNC-DM160",      ("http://", "/image?speed=10", None)),    # 4th gen
    ("Sony", "Sony SNC-DS10",       ("http://", "/image?speed=10", None)),    # 4th gen, tested remotely
    ("Sony", "Sony SNC-DS60",       ("http://", "/image?speed=10", None)),    # 4th gen, tested remotely
    ("Sony", "Sony SNC-P1",         ("http://", "/image?speed=10", None)),    # Spreadsheet, Second gen, Tested in-house (loaner program)
    ("Sony", "Sony SNC-P5",         ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-RZ25N",      ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-RZ25P",      ("http://", "/image?speed=10", None)),    # Second gen
    ("Sony", "Sony SNC-RH124",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RH164",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RS44N",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RS44P",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RS46N",      ("http://", "/image?speed=10", None)),    # 5th gen, tested remotely
    ("Sony", "Sony SNC-RS46P",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RS84N",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RS84P",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RS86N",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RS86P",      ("http://", "/image?speed=10", None)),    # 5th gen
    ("Sony", "Sony SNC-RX530N",     ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-RX530P",     ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-RX550N",     ("http://", "/image?speed=10", None)),    # 3rd gen, tested remotely
    ("Sony", "Sony SNC-RX550P",     ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-RX570N",     ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-RX570P",     ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-RZ50N",      ("http://", "/image?speed=10", None)),    # 3rd gen
    ("Sony", "Sony SNC-RZ50P",      ("http://", "/image?speed=10", None)),    # 3rd gen

    ("Sony", "Sony (other)",        ("http://", "/image?speed=10", None)),
    ("Sony", "Sony (other MJPEG)",  ("http://", "/mjpeg?speed=10", None)),
    ("Sony", "Sony (other MPEG-4)", ("http://", "/mpeg4", None)),


    ("Sricam", "Sricam AP008",   ("http://", "/videostream.cgi?rate=0&user=__USERNAME__&pwd=__PASSWORD__", None)), # User reported, case 11999
    ("Sricam", "Sricam (other)", ("http://", "/videostream.cgi?rate=0&user=__USERNAME__&pwd=__PASSWORD__", None)),


    # SURIP notes:
    # URLs reported by manufacturer. They provided screenshots of cams working
    # in VDV, did not provide remote access.
    #   "Our ip camera default ip address is http://192.168.1.128
    #    default http port:80 ,default rtsp port:554 ,default upnp port :
    #    and RTSP format is like rtsp://192.168.1.128:554/ch0_0.h264"
    ("SURIP", "SURIP SI-E534",      ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-E536V2",    ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-E537",      ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-E538",      ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-E553R",     ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-E555R",     ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-F1034",     ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-F1037",     ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-F1038",     ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-F1053R",    ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-F1055R",    ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-L934",      ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-L936V2",    ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-L937",      ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-L938",      ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-L953R",     ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP SI-L955R",     ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported
    ("SURIP", "SURIP (other)",      ("rtsp://", "/ch0_0.h264", None)), # Manufacturer reported


    ("Tenvis", "Tenvis JPT3815W",  ("http://", "/videostream.cgi", None)), # User reported, foscam clone, 6933
    ("Tenvis", "Tenvis (other)",   ("http://", "/videostream.cgi", None)), # User reported


    ("Toshiba", "Toshiba IK-WB11A", ("http://", "/getstream.cgi?10&&__USERNAME__&__PASSWORD__&0&0&0&0&0&svforcemjpeg", None)), # User reported, 7283
    ("Toshiba", "Toshiba IK-WD01A", ("rtsp://", "/live.sdp", None)), # User reported
    ("Toshiba", "Toshiba (other)",  ("rtsp://", "/live.sdp", None)), # User reported

    # TRENDnet notes:
    #
    # - TV-IP312W notes (also applies to some others too):
    #   - The '/cgi/mjpg/mjpeg.cgi' stream is interesting because it doesn't
    #     contain the 'Content-Type: image/jpeg' in the stream.  That's why we
    #     need the '?svforcemjpeg' hint at the end to get FFMPEG to choose the right
    #     stream (TRENDnet seems to ignore this extra post request)
    #   - As of Feb 2010, the TV-IP312W and TV-IP110W both seemed to allow
    #     access to '/cgi/mjpg/mjpeg.cgi' without any authentication data,
    #     regardless of settings on the camera (!?!?!).  This seems to be a
    #     huge security hole.  This might be fixed in the newest TV-IP110W
    #     firmware.
    #   - The '/cgi/mjpg/mjpg.cgi' stream DOES contain the 'Content-Type:
    #     image/jpeg' in the stream and requires authentication.  ...but some
    #     comments on the web indicate that it was added only in more recent
    #     firmware, so it's probably less safe to default to?  I'm including it
    #     on the off chance that on some version of the firmware it will work
    #     while thue mjpeg.cgi one won't.
    #   - As of our current FFMPEG (2/24/10) and the current TV-IP312W build,
    #     the MPEG-4 stream doesn't really work very well.  Specifically:
    #     - I let the "http" one run on my camera for a few days, and found a
    #       period of time where my camera was all static.  This was after
    #       dumbing my stream down to 10fps w/ "high" video quality.
    #     - The rtsp one glitches semi-constantly with my camera.
    ("TRENDnet", "TRENDnet TV-IP100W-N",            ("http://", "/video.cgi?svforcemjpeg", None)),
    ("TRENDnet", "TRENDnet TV-IP110",               ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),  #
    ("TRENDnet", "TRENDnet TV-IP110W",              ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),  # Tesed in-house
    ("TRENDnet", "TRENDnet TV-IP200W",              ("http://", "/video.cgi?svforcemjpeg", None)),
    ("TRENDnet", "TRENDnet TV-IP302PI",             ("rtsp://", "/v1", None)), # tested remotely, 7196
    ("TRENDnet", "TRENDnet TV-IP312",               ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),  #
    ("TRENDnet", "TRENDnet TV-IP312W",              ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),  # Tesed in-house
    ("TRENDnet", "TRENDnet TV-IP400W",              ("http://", "/video.cgi?svforcemjpeg", None)),
    ("TRENDnet", "TRENDnet TV-IP572P",              ("rtsp://", "/play1.sdp", None)), # tested remotly, 7196
    ("TRENDnet", "TRENDnet TV-IP572PI",             ("rtsp://", "/play1.sdp", None)), # 7196
    ("TRENDnet", "TRENDnet TV-IP572W",              ("rtsp://", "/play1.sdp", None)), # 7196
    ("TRENDnet", "TRENDnet TV-IP572WI",             ("rtsp://", "/play1.sdp", None)), # 7196
    ("TRENDnet", "TRENDnet TV-IP672P",              ("rtsp://", "/play1.sdp", None)), # 7196
    ("TRENDnet", "TRENDnet TV-IP672PI",             ("rtsp://", "/play1.sdp", None)), # 7196
    ("TRENDnet", "TRENDnet TV-IP672W",              ("rtsp://", "/play1.sdp", None)), # 7196
    ("TRENDnet", "TRENDnet TV-IP672WI",             ("rtsp://", "/play1.sdp", None)), # tested remotly, 7196
    ("TRENDnet", "TRENDnet TV-VS1P",                ("rtsp://", "/mpeg4", None)),
    ("TRENDnet", "TRENDnet (other RTSP)",           ("rtsp://", "/play1.sdp", None)), # tested remotly with TV-IP672WI
    ("TRENDnet", "TRENDnet (other MJPEG - type A)", ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),
    ("TRENDnet", "TRENDnet (other MJPEG - type B)", ("http://", "/video.cgi?svforcemjpeg", None)),
    ("TRENDnet", "TRENDnet (other MPEG-4)",         ("rtsp://", "/mpeg4", None)),
    #("TRENDnet", "TRENDnet (other - type C)",       ("http://", "/cgi/mjpg/mjpg.cgi", None)),
    #("TRENDnet TV-IP312W (MPEG-4)",                 ("http://", "/cgi/mpeg4/mpeg4.cgi?.mp4", None)),  # Won't work if no .mp4

    # Ubiquiti:
    #   - Reported by a forums user at http://vitamindvideo.com/forums/viewtopic.php?f=5&t=773
    ("Ubiquiti", "Ubiquiti airCam Dome", ("rtsp://", "/live/ch00_0", None)),
    ("Ubiquiti", "Ubiquiti (other)",     ("rtsp://", "/live/ch00_0", None)),

    ("Wansview", "Wansview NC541W",        ("http://", "/videostream.cgi", None)),   # User reported
    ("Wansview", "Wansview NCB541W",       ("http://", "/videostream.cgi", None)),   # Tested in-house
    ("Wansview", "Wansview NCM621W",       ("rtsp://", "/11", None)),     # User reported, case 7246
    ("Wansview", "Wansview (other HTTP)",  ("http://", "/videostream.cgi", None)),
    ("Wansview", "Wansview (other RTSP)",  ("rtsp://", "/11", None)),     # User reported, case 7246

    # Vivotek notes:
    # - live.sdp is the default stream name for stream 1.  Some Vivotek cameras
    #   have more than one stream, which are different settings / subviews
    #   of the main camera view (FD8134 manual is the one I looked at).
    # - The mjpeg equivalent of the streams are streams like "video.mjpg",
    #   "video2.mjpg", etc. (looked at FD8134).
    # - I see references like "videoany.mjpg" and "liveany.sdp" talking about
    #   stream 5.  What does that do?
    ("Vivotek", "Vivotek CC8130",  ("rtsp://", "/live.sdp", None)), # In house
    ("Vivotek", "Vivotek FD8134",  ("rtsp://", "/live.sdp", None)), # User reported: http://vitamindvideo.com/forums/viewtopic.php?f=5&t=630&p=1081
    ("Vivotek", "Vivotek FD8369A-V",  ("rtsp://", "/live.sdp", None)), # In house
    ("Vivotek", "Vivotek IP7131",  ("rtsp://", "/live.sdp", None)),
    ("Vivotek", "Vivotek IP7132",  ("rtsp://", "/live.sdp", None)),
    ("Vivotek", "Vivotek IP7330",  ("rtsp://", "/live.sdp", None)), # User reported
    ("Vivotek", "Vivotek IP7361",  ("rtsp://", "/live.sdp", None)), # Tested remotely, bug 2103.
    ("Vivotek", "Vivotek IP8330",  ("rtsp://", "/live.sdp", None)), # User reported
    ("Vivotek", "Vivotek (other H264)", ("rtsp://", "/live.sdp", None)),
    # TODO: How did we wind up with identical type A and type B URLs?
    #       Should remove one, drop the "type", and update kOldCameraNameMap
    ("Vivotek", "Vivotek (other MPEG-4 - type A)", ("rtsp://", "/live.sdp", None)),
    ("Vivotek", "Vivotek (other MPEG-4 - type B)", ("rtsp://", "/live.sdp", None)),
    ("Vivotek", "Vivotek (other MJPEG)", ("http://", "/video.mjpg", None)),


    ("Wirepath", "Wirepath WPS-750-DOM-IP",  ("rtsp://", "/v2", None)),  # User reported, 9374
    ("Wirepath", "Wirepath (other)",   ("rtsp://", "/v2", None)),


    ("Y-Cam", "Y-Cam Black",   ("http://", "/stream.jpg", None)),
    ("Y-Cam", "Y-Cam Knight",  ("http://", "/stream.jpg", None)),
    ("Y-Cam", "Y-Cam White",   ("http://", "/stream.jpg", None)),
    ("Y-Cam", "Y-Cam (other)", ("http://", "/stream.jpg", None)),


    # Yanmix reported by manufacturer, ticket 4206
    ("Yanmix", "Yanmix EasySE-IR1",      ("http://", "/videostream.cgi", None)),
    ("Yanmix", "Yanmix EasySE-IR2",      ("http://", "/videostream.cgi", None)),
    ("Yanmix", "Yanmix EasySE-F1",       ("http://", "/videostream.cgi", None)),
    ("Yanmix", "Yanmix EasySE-F2",       ("http://", "/videostream.cgi", None)),
    ("Yanmix", "Yanmix EasySE-H3",       ("http://", "/videostream.cgi", None)),
    ("Yanmix", "Yanmix (other)",         ("http://", "/videostream.cgi", None)),


    ("Zavio", "Zavio F731E",          ("http://", "/video.mp4", None)),
    ("Zavio", "Zavio (other MJPEG)",  ("http://", "/video.mjpg", None)),
    ("Zavio", "Zavio (other MPEG-4)", ("http://", "/video.mp4", None)),

    # Zonet notes:
    # - See TV-IP312W notes for a discussion on some Zonet cameras.
    # - UPnP for these cameras reports them as csXXXX.  This looks to be the
    #   model numbers of Fitivision cameras, which you can see here:
    #     http://www.fitivision.com/pdt/pdt1_2.htm
    #   These look identical to the Zonet cameras, but with different color
    #   plastics.  I'm guessing that Zonet didn't bother to update the UPnP data
    #   with their own name.  Since Fitivision cameras don't seem to be for sale
    #   directly, we'll identify them as Zonet cameras in the UPnP table below.
    ("Zonet", "Zonet ZVC7610",             ("http://", "/cgi/mjpg/mjpg.cgi", None)),           # Guess
    ("Zonet", "Zonet ZVC7610W",            ("http://", "/cgi/mjpg/mjpg.cgi", None)),           # Guess
    ("Zonet", "Zonet ZVC7630",             ("http://", "/cgi/mjpg/mjpg.cgi", None)),           # Tested by user (Evance) on FW 1.0.0.77
    ("Zonet", "Zonet ZVC7630W",            ("http://", "/cgi/mjpg/mjpg.cgi", None)),           # Guess
    ("Zonet", "Zonet (other - type A)",    ("http://", "/cgi/mjpg/mjpg.cgi", None)),
    ("Zonet", "Zonet (other - type B)",    ("http://", "/cgi/mjpg/mjpeg.cgi?svforcemjpeg", None)),

    ("Zmodo", "Zmodo ZP-IBH13-W",    ("rtsp://", "/tcp/av0_0", 10554)), # User reported, 8053
    ("Zmodo", "Zmodo ZH-IXC15-WC",   ("rtsp://", "/tcp/av0_0", 10554)), # User reported, 8770
    ("Zmodo", "Zmodo (other)",       ("rtsp://", "/tcp/av0_0", 10554)), # User reported, 8770

    ("ZyXEL", "ZyXEL IPC-3605N",  ("rtsp://", "/medias1", None)), # From Markus
    ("ZyXEL", "ZyXEL (other)",    ("rtsp://", "/medias1", None)), # From Markus
]

# When we start up the wizard, if the user's type/URL match these regular
# expressions then we'll move them to the third value.
#
# Contains:
#     (deprecatedTypeRe, deprecatedUriRe, cameraType)
kDeprecatedSettings = [
    (
        r"^ACTi ACM-.*",
        r".*/cgi-bin/cmd/system\?GET_STREAM$",
        'ACTi (other ACM - old)'
    ),
]

# If we rename a camera, add the old name here so that we can handle old
# settings properly...
kOldCameraNameMap = {
    "Airlink AIC250(W)":         "Airlink AIC250W",
    "Airlink AICN500(W)":        "Airlink AICN500W",
    "AVTech (other)":            "AVTech (other HTTP)",
    "Axis 207(W)":               "Axis 207W",
    "Axis M1011(W)":             "Axis M1011-W",
    "Axis M1031W":               "Axis M1031-W",
    "Axis (other)":              "Axis (other MJPEG)",
    "Axis (other MPEG-4)":       "Axis (other MPEG-4 - type B)",
    "Canon VB-S900D":            "Canon VB-S900F",
    "Cisco (other)":             'Cisco (other RTSP - type A)',
    "D-Link (other)":            "D-Link (other HTTP - type A)",
    "D-Link (other RTSP)":       "D-Link (other RTSP - type B)",
    "Foscam (other)":            "Foscam (other MJPEG - type A)",
    "HooToo (other)":            "HooToo (other HTTP)",
    "Linksys (other)":           "Linksys (other MJPEG - type A)",
    "Marmitek Robocam 8":        "Marmitek IP Robocam8",
    "Marmitek (other)":          "Marmitek (other MJPEG - type A)",
    "Panasonic (other MP4)":     "Panasonic (other MPEG-4)",
    "Samsung (other)":           "Samsung (other RTSP - Profile 1)",
    "TRENDnet (other - type A)": "TRENDnet (other MJPEG - type A)",
    "TRENDnet (other - type B)": "TRENDnet (other MJPEG - type B)",
    "Vivotek (other)":           "Vivotek (other MPEG-4 - type B)",
    "Wansview (other)":          "Wansview (other HTTP)"
}

# Cameras that have this in their name are generics...
kGenericIndicator = "(other"

# Mapping from UPNP models to camera types...
kUpnpModelMap = {
    'ACTi Corporation ACM1011':  ["ACTi ACM-1011"],                     # Source: guess
    'ACTi Corporation ACM1231':  ["ACTi ACM-1231"],                     # Source: guess
    'ACTi Corporation ACM1232':  ["ACTi ACM-1232"],                     # Source: guess
    'ACTi Corporation ACM1311':  ["ACTi ACM-1311N", "ACTi ACM-1311P"],  # Source: guess
    'ACTi Corporation ACM1311N': ["ACTi ACM-1311N"],                    # Source: hope
    'ACTi Corporation ACM1311P': ["ACTi ACM-1311P"],                    # Source: hope
    'ACTi Corporation ACM1431':  ["ACTi ACM-1431N", "ACTi ACM-1431P"],  # Source: guess
    'ACTi Corporation ACM1431N': ["ACTi ACM-1431N"],                    # Source: hope
    'ACTi Corporation ACM1431P': ["ACTi ACM-1431P"],                    # Source: hope
    'ACTi Corporation ACM1432':  ["ACTi ACM-1432N", "ACTi ACM-1432P"],  # Source: guess
    'ACTi Corporation ACM1432N': ["ACTi ACM-1432N"],                    # Source: hope
    'ACTi Corporation ACM1432P': ["ACTi ACM-1432P"],                    # Source: hope
    'ACTi Corporation ACM1511':  ["ACTi ACM-1511"],                     # Source: guess
    'ACTi Corporation ACM3001':  ["ACTi ACM-3001"],                     # Source: guess
    'ACTi Corporation ACM3011':  ["ACTi ACM-3011"],                     # Source: guess
    'ACTi Corporation ACM3211':  ["ACTi ACM-3211N", "ACTi ACM-3211P"],  # Source: guess
    'ACTi Corporation ACM3211N': ["ACTi ACM-3211N"],                    # Source: hope
    'ACTi Corporation ACM3211P': ["ACTi ACM-3211P"],                    # Source: hope
    'ACTi Corporation ACM3311':  ["ACTi ACM-3311N", "ACTi ACM-3311P"],  # Source: guess
    'ACTi Corporation ACM3311N': ["ACTi ACM-3311N"],                    # Source: hope
    'ACTi Corporation ACM3311P': ["ACTi ACM-3311P"],                    # Source: hope
    'ACTi Corporation ACM3401':  ["ACTi ACM-3401"],                     # Source: guess
    'ACTi Corporation ACM3411':  ["ACTi ACM-3411"],                     # Source: guess
    'ACTi Corporation ACM3511':  ["ACTi ACM-3511"],                     # Source: guess
    'ACTi Corporation ACM3601':  ["ACTi ACM-3601"],                     # Source: guess
    'ACTi Corporation ACM3603':  ["ACTi ACM-3603"],                     # Source: guess
    'ACTi Corporation ACM3701':  ["ACTi ACM-3701"],                     # Source: guess
    'ACTi Corporation ACM3703':  ["ACTi ACM-3703"],                     # Source: guess
    'ACTi Corporation ACM4000':  ["ACTi ACM-4000"],                     # Source: guess
    'ACTi Corporation ACM4001':  ["ACTi ACM-4001"],                     # Source: in-house testing
    'ACTi Corporation ACM4200':  ["ACTi ACM-4200"],                     # Source: guess
    'ACTi Corporation ACM4201':  ["ACTi ACM-4201"],                     # Source: guess
    'ACTi Corporation ACM5001':  ["ACTi ACM-5001"],                     # Source: guess
    'ACTi Corporation ACM5601':  ["ACTi ACM-5601"],                     # Source: guess
    'ACTi Corporation ACM5611':  ["ACTi ACM-5611"],                     # Source: guess
    'ACTi Corporation ACM5711':  ["ACTi ACM-5711N", "ACTi ACM-5711P"],  # Source: guess
    'ACTi Corporation ACM5711N': ["ACTi ACM-5711N"],                    # Source: hope
    'ACTi Corporation ACM5711P': ["ACTi ACM-5711P"],                    # Source: hope
    'ACTi Corporation ACM7411':  ["ACTi ACM-7411"],                     # Source: guess
    #'ACTi Corporation ACM7511':  ["ACTi ACM-7511"],                     # Source: guess
    'ACTi Corporation ACM8201':  ["ACTi ACM-8201"],                     # Source: guess
    'ACTi Corporation ACM8211':  ["ACTi ACM-8211"],                     # Source: guess
    'ACTi Corporation ACM8511':  ["ACTi ACM-8511N", "ACTi ACM-8511P"],  # Source: in-house testing
    'ACTi Corporation ACM8511N': ["ACTi ACM-8511N"],                    # Source: hope
    'ACTi Corporation ACM8511P': ["ACTi ACM-8511P"],                    # Source: hope
    'ACTi Corporation D32':      ["ACTi D32"],                          # Source: hope

    'ACTi Corporation TCM4101':  ["ACTi TCM-4101"],                     # Source: guess
    'ACTi Corporation TCM4301':  ["ACTi TCM-4301"],                     # Source: in-house testing
    'ACTi Corporation TCM5311':  ["ACTi TCM-5311"],                     # Source: guess
    'ACTi Corporation TCM5312':  ["ACTi TCM-5312"],                     # Source: guess


    'AIC250':   ["Airlink AIC250"],       # Source: in-house testing
    'AIC250W':  ["Airlink AIC250W"],      # Source: guess
    'AICN500':  ["Airlink AICN500"],      # Source: guess
    'AICN500W': ["Airlink AICN500W"],     # Source: user log (Evance)

    'AirCam OD-600HD': ['AirLive AirCam OD-600HD'], # Source: bug 3108

    # Asante Notes:
    # - From testing, the Voyager I has no info identifying it as a Voyager I.
    #   I'm assuming that a Voyager II has the same info.
    # IMPORTANT: Keep CameraTable in sync w/ Asante OEM CameraTable here.
    'ASANTE IPCam':  ["Asante Voyager I", "Asante Voyager II"],         # Source: Asante Voyager I testing

    'AXIS 207':       ["Axis 207"],       # Source: Axis
    'AXIS 207W':      ["Axis 207W"],      # Source: Axis (confirmed in-house)
    'AXIS 207MW':     ["Axis 207MW"],     # Source: Axis
    'AXIS 209FD':     ["Axis 209FD"],     # Source: guess
    'AXIS 209FD-R':   ["Axis 209FD-R"],   # Source: guess
    'AXIS 209MFD':    ["Axis 209MFD"],    # Source: guess
    'AXIS 209MFD-R':  ["Axis 209MFD-R"],  # Source: guess
    'AXIS 210':       ["Axis 210"],       # Source: Axis
    'AXIS 210A':      ["Axis 210A"],      # Source: Axis
    'AXIS 211':       ["Axis 211"],       # Source: guess
    'AXIS 211A':      ["Axis 211A"],      # Source: guess
    'AXIS 211M':      ["Axis 211M"],      # Source: guess
    'AXIS 211W':      ["Axis 211W"],      # Source: guess
    'AXIS 212 PTZ':   ["Axis 212 PTZ"],   # Source: guess
    'AXIS 212 PTZ-V': ["Axis 212 PTZ-V"], # Source: guess
    'AXIS 213 PTZ':   ["Axis 213 PTZ"],   # Source: guess
    'AXIS 214 PTZ':   ["Axis 214 PTZ"],   # Source: guess
    'AXIS 215 PTZ':   ["Axis 215 PTZ"],   # Source: guess
    'AXIS 215 PTZ-E': ["Axis 215 PTZ-E"], # Source: guess
    'AXIS 216FD':     ["Axis 216FD"],     # Source: guess
    'AXIS 216FD-V':   ["Axis 216FD-V"],   # Source: guess
    'AXIS 216MFD':    ["Axis 216MFD"],    # Source: guess
    'AXIS 216MFD-V':  ["Axis 216MFD-V"],  # Source: guess
    'AXIS 221':       ["Axis 221"],       # Source: guess
    'AXIS 223M':      ["Axis 223M"],      # Source: guess
    'AXIS 225FD':     ["Axis 225FD"],     # Source: guess
    'AXIS 231D+':     ["Axis 231D+"],     # Source: guess
    'AXIS 232D+':     ["Axis 232D+"],     # Source: guess
    'AXIS 233D':      ["Axis 233D"],      # Source: guess
    'AXIS 241Q':      ["Axis 241Q - port 1",   # Source: guess
                       "Axis 241Q - port 2",   # Source: guess
                       "Axis 241Q - port 3",   # Source: guess
                       "Axis 241Q - port 4"],  # Source: guess
    'AXIS 241QA':     ["Axis 241QA - port 1",  # Source: guess
                       "Axis 241QA - port 2",  # Source: guess
                       "Axis 241QA - port 3",  # Source: guess
                       "Axis 241QA - port 4"], # Source: guess
    'AXIS 243Q':      ["Axis 243Q"],      # Source: user on forum
    'AXIS 247S':      ["Axis 247S"],      # Source: guess
    'AXIS 2120':      ["Axis 2120"],      # Source: guess
    'AXIS M1004-W':   ["Axis M1004-W"],   # Source: Axis
    'AXIS M1011':     ["Axis M1011"],     # Source: Axis
    'AXIS M1011-W':   ["Axis M1011-W"],   # Source: Axis (confirmed in-house)
    'AXIS M1013':     ["Axis M1013"],     # Source: Axis
    'AXIS M1014':     ["Axis M1014"],     # Source: Axis
    'AXIS M1031-W':   ["Axis M1031-W"],   # Source: Axis (confirmed in-house)
    'AXIS M1033-W':   ["Axis M1033-W"],   # Source: Axis
    'AXIS M1034-W':   ["Axis M1034-W"],   # Source: Axis
    'AXIS M1054':     ["Axis M1054"],     # Source: In house
    'AXIS M3011':     ["Axis M3011"],     # Source: guess
    'AXIS M3014':     ["Axis M3014"],     # Source: guess
    'AXIS P1311':     ["Axis P1311"],     # Source: Axis
    'AXIS P1343':     ["Axis P1343"],     # Source: Axis
    'AXIS P1344':     ["Axis P1344"],     # Source: Axis
    'AXIS P1346':     ["Axis P1346"],     # Source: guess
    'AXIS P3301':     ["Axis P3301"],     # Source: guess
    'AXIS P3301-V':   ["Axis P3301-V"],   # Source: guess
    'AXIS P3343':     ["Axis P3343"],     # Source: guess
    'AXIS P3343-V':   ["Axis P3343-V"],   # Source: guess
    'AXIS P3343-VE':  ["Axis P3343-VE"],  # Source: guess
    'AXIS P3344':     ["Axis P3344"],     # Source: guess
    'AXIS P3344-V':   ["Axis P3344-V"],   # Source: guess
    'AXIS P3344-VE':  ["Axis P3344-VE"],  # Source: guess
    'AXIS Q1755':     ["Axis Q1755"],     # Source: guess
    'AXIS Q1910':     ["Axis Q1910"],     # Source: guess
    'AXIS Q1910-E':   ["Axis Q1910-E"],   # Source: guess
    'AXIS Q6032-E':   ["Axis Q6032-E"],   # Source: guess
    'AXIS Q7401':     ["Axis Q7401"],     # Source: guess
    'AXIS Q7404':     ["Axis Q7404"],     # Source: guess
    'AXIS Q7406':     ["Axis Q7406"],     # Source: guess

    'Compro IP50':    ["Compro (other - stream 1)"],    # Source: guess
    'Compro IP50W':   ["Compro (other - stream 1)"],    # Source: guess
    'Compro IP55':    ["Compro (other - stream 1)"],    # Source: guess
    'Compro IP60':    ["Compro IP60"],    # Source: forum (https://vitamind.fogbugz.com/default.asp?video.1.487.4)
    'Compro IP530':   ["Compro (other - stream 1)"],    # Source: guess
    'Compro IP530W':  ["Compro (other - stream 1)"],    # Source: guess
    'Compro IP540':   ["Compro IP540"],   # Source: guess
    'Compro IP540P':  ["Compro IP540"],   # Source: guess
    'Compro IP570':   ["Compro IP570"],   # Source: guess
    'Compro IP570P':  ["Compro IP570"],   # Source: guess

    'D-Link Corporation DCS-2120': ["D-Link DCS-2120"], # Source: in-house testing
    'D-Link DCS-2120':             ["D-Link DCS-2120"], # Guess, some might not have 'Corporation'
    'D-Link Corporation DCS-2132LB1': ["D-Link DCS-2132LB1"], # Source: in-house testing
    'D-Link Corporation DCS-2132L':["D-Link DCS-2132LB1"], # Guess, some might not have 'B1'
    'D-Link Corporation DCS-3110': ["D-Link DCS-3110"], # Guess, some might have 'Corporation'
    'D-Link DCS-3110':             ["D-Link DCS-3110"], # Source: in-house testing
    'D-Link Corporation DCS-5220': ["D-Link DCS-5220"], # Guess, some might have 'Corporation'
    'D-Link DCS-5220':             ["D-Link DCS-5220"], # Guess, some might not have 'Corporation'
    'D-Link DCS-6100':             ["D-Link DCS-6110"], # Guess, might happen
    'D-Link Coporation DCS-6100':  ["D-Link DCS-6110"], # Source: in-house testing
    'D-Link Corporation DCS-6100': ["D-Link DCS-6110"], # Guess that they might have fixed the above typo at some point?
    'D-Link Corporation DCS-910':  ["D-Link DCS-910"],  # Guess, might happen
    'D-Link Corporation DCS-920':  ["D-Link DCS-920"],  # Guess, might happen
    'D-Link DCS-910':              ["D-Link DCS-910"],  # Guess, might happen
    'D-Link DCS-920':              ["D-Link DCS-920"],  # Source: in-house testing
    'D-Link DCS-930L':             ["D-Link DCS-930L"], # Source: in-house testing
    'D-Link DCS-930LB1':           ["D-Link DCS-930LB1"], # Source: in-house testing
    'D-Link DCS-942L':             ["D-Link DCS-942L"], # Source: in-house testing

    'GrandStream INC. 1.0':    ["Grandstream GXV3611_HD"], # Source: in-house testing

    'Hikvision DS-2CD2232-I5': ["Hikvision DS-2CD2232-I5"], # Source: in-house testing
    'HIKVISION DS-2CD2232-I5': ["Hikvision DS-2CD2232-I5"], # Source: in-house testing

    'Linksys WVC11B':   ["Linksys WVC11B"],       # Guess
    'Linksys WVC54GC':  ["Linksys WVC54GC"],      # TODO: CONFIRM! (this is a guess)
    'Linksys WVC54GCA': ["Linksys WVC54GCA"],     # Source: in-house testing
    'Linksys WVC80N':   ["Linksys WVC80N"],       # TODO: CONFIRM! (this is a guess)

    'IQ040S': ["IQinVision IQ040SI"],             # Source: guess
    'IQ041S': ["IQinVision IQ041SI"],             # Source: in-house testing
    'IQ042S': ["IQinVision IQ042SI"],             # Source: guess
    'IQD40S': ["IQinVision IQD40SI"],             # Source: guess
    'IQD41S': ["IQinVision IQD41SI"],             # Source: guess
    'IQD42S': ["IQinVision IQD42SI"],             # Source: guess

    'Panasonic BB-HCE481':    ["Panasonic BB-HCE481"],  # Source:
    'Panasonic BB-HCE481A':   ["Panasonic BB-HCE481"],  # Source:
    'Panasonic BB-HCE481E':   ["Panasonic BB-HCE481"],  # Source:
    'Panasonic BB-HCE481CE':  ["Panasonic BB-HCE481"],  # Source:

    'Panasonic BB-HCM311':    ["Panasonic BB-HCM311"],  # Source:
    'Panasonic BB-HCM311A':   ["Panasonic BB-HCM311"],  # Source:
    'Panasonic BB-HCM311E':   ["Panasonic BB-HCM311"],  # Source:
    'Panasonic BB-HCM311CE':  ["Panasonic BB-HCM311"],  # Source:

    'Panasonic BB-HCM331':    ["Panasonic BB-HCM331"],  # Source:
    'Panasonic BB-HCM331A':   ["Panasonic BB-HCM331"],  # Source:
    'Panasonic BB-HCM331E':   ["Panasonic BB-HCM331"],  # Source:
    'Panasonic BB-HCM331CE':  ["Panasonic BB-HCM331"],  # Source:

    'Panasonic BB-HCM371':    ["Panasonic BB-HCM371"],  # Source:
    'Panasonic BB-HCM371A':   ["Panasonic BB-HCM371"],  # Source:
    'Panasonic BB-HCM371E':   ["Panasonic BB-HCM371"],  # Source:
    'Panasonic BB-HCM371CE':  ["Panasonic BB-HCM371"],  # Source:

    'Panasonic BB-HCM381':    ["Panasonic BB-HCM381"],  # Source:
    'Panasonic BB-HCM381A':   ["Panasonic BB-HCM381"],  # Source:
    'Panasonic BB-HCM381E':   ["Panasonic BB-HCM381"],  # Source:
    'Panasonic BB-HCM381CE':  ["Panasonic BB-HCM381"],  # Source:

    'Panasonic BB-HCM403':    ["Panasonic BB-HCM403"],  # Source:
    'Panasonic BB-HCM403A':   ["Panasonic BB-HCM403"],  # Source:
    'Panasonic BB-HCM403E':   ["Panasonic BB-HCM403"],  # Source:
    'Panasonic BB-HCM403CE':  ["Panasonic BB-HCM403"],  # Source:

    'Panasonic BB-HCM511':    ["Panasonic BB-HCM511"],  # Source: UPnP doc
    'Panasonic BB-HCM511A':   ["Panasonic BB-HCM511"],  # Source: UPnP doc
    'Panasonic BB-HCM511E':   ["Panasonic BB-HCM511"],  # Source: UPnP doc
    'Panasonic BB-HCM511CE':  ["Panasonic BB-HCM511"],  # Source: UPnP doc

    'Panasonic BB-HCM515':    ["Panasonic BB-HCM515"],  # Source: UPnP doc
    'Panasonic BB-HCM515A':   ["Panasonic BB-HCM515"],  # Source: UPnP doc
    'Panasonic BB-HCM515E':   ["Panasonic BB-HCM515"],  # Source: UPnP doc
    'Panasonic BB-HCM515CE':  ["Panasonic BB-HCM515"],  # Source: UPnP doc

    'Panasonic BB-HCM527':    ["Panasonic BB-HCM527"],  # Source:
    'Panasonic BB-HCM527A':   ["Panasonic BB-HCM527"],  # Source:
    'Panasonic BB-HCM527E':   ["Panasonic BB-HCM527"],  # Source:
    'Panasonic BB-HCM527CE':  ["Panasonic BB-HCM527"],  # Source:

    'Panasonic BB-HCM531':    ["Panasonic BB-HCM531"],  # Source: UPnP doc
    'Panasonic BB-HCM531A':   ["Panasonic BB-HCM531"],  # Source: UPnP doc
    'Panasonic BB-HCM531E':   ["Panasonic BB-HCM531"],  # Source: UPnP doc
    'Panasonic BB-HCM531CE':  ["Panasonic BB-HCM531"],  # Source: UPnP doc

    'Panasonic BB-HCM547':    ["Panasonic BB-HCM547"],  # Source:
    'Panasonic BB-HCM547A':   ["Panasonic BB-HCM547"],  # Source:
    'Panasonic BB-HCM547E':   ["Panasonic BB-HCM547"],  # Source:
    'Panasonic BB-HCM547CE':  ["Panasonic BB-HCM547"],  # Source:

    'Panasonic BB-HCM580':    ["Panasonic BB-HCM580"],  # Source:
    'Panasonic BB-HCM580A':   ["Panasonic BB-HCM580"],  # Source:
    'Panasonic BB-HCM580E':   ["Panasonic BB-HCM580"],  # Source:
    'Panasonic BB-HCM580CE':  ["Panasonic BB-HCM580"],  # Source:

    'Panasonic BB-HCM581':    ["Panasonic BB-HCM581"],  # Source:
    'Panasonic BB-HCM581A':   ["Panasonic BB-HCM581"],  # Source:
    'Panasonic BB-HCM581E':   ["Panasonic BB-HCM581"],  # Source:
    'Panasonic BB-HCM581CE':  ["Panasonic BB-HCM581"],  # Source:

    #'Panasonic BB-HCM701':    ["Panasonic BB-HCM701"],  # Source:
    #'Panasonic BB-HCM701A':   ["Panasonic BB-HCM701"],  # Source:
    #'Panasonic BB-HCM701E':   ["Panasonic BB-HCM701"],  # Source:
    #'Panasonic BB-HCM701CE':  ["Panasonic BB-HCM701"],  # Source:
    #
    #'Panasonic BB-HCM705':    ["Panasonic BB-HCM705"],  # Source:
    #'Panasonic BB-HCM705A':   ["Panasonic BB-HCM705"],  # Source:
    #'Panasonic BB-HCM705E':   ["Panasonic BB-HCM705"],  # Source:
    #'Panasonic BB-HCM705CE':  ["Panasonic BB-HCM705"],  # Source:
    #
    #'Panasonic BB-HCM715':    ["Panasonic BB-HCM715"],  # Source:
    #'Panasonic BB-HCM715A':   ["Panasonic BB-HCM715"],  # Source:
    #'Panasonic BB-HCM715E':   ["Panasonic BB-HCM715"],  # Source:
    #'Panasonic BB-HCM715CE':  ["Panasonic BB-HCM715"],  # Source:
    #
    #'Panasonic BB-HCM735':    ["Panasonic BB-HCM735"],  # Source:
    #'Panasonic BB-HCM735A':   ["Panasonic BB-HCM735"],  # Source:
    #'Panasonic BB-HCM735E':   ["Panasonic BB-HCM735"],  # Source:
    #'Panasonic BB-HCM735CE':  ["Panasonic BB-HCM735"],  # Source:

    'Panasonic BB-HCS301':    ["Panasonic BB-HCS301"],  # Source:
    'Panasonic BB-HCS301A':   ["Panasonic BB-HCS301"],  # Source:
    'Panasonic BB-HCS301E':   ["Panasonic BB-HCS301"],  # Source:
    'Panasonic BB-HCS301CE':  ["Panasonic BB-HCS301"],  # Source:

    'Panasonic BL-C1':    ["Panasonic BL-C1"],  # Source:
    'Panasonic BL-C1A':   ["Panasonic BL-C1"],  # Source:
    'Panasonic BL-C1E':   ["Panasonic BL-C1"],  # Source:
    'Panasonic BL-C1CE':  ["Panasonic BL-C1"],  # Source:

    'Panasonic BL-C10':    ["Panasonic BL-C10"],  # Source:
    'Panasonic BL-C10A':   ["Panasonic BL-C10"],  # Source:
    'Panasonic BL-C10E':   ["Panasonic BL-C10"],  # Source:
    'Panasonic BL-C10CE':  ["Panasonic BL-C10"],  # Source:

    'Panasonic BL-C20':    ["Panasonic BL-C20"],  # Source:
    'Panasonic BL-C20A':   ["Panasonic BL-C20"],  # Source: in-house testing
    'Panasonic BL-C20E':   ["Panasonic BL-C20"],  # Source:
    'Panasonic BL-C20CE':  ["Panasonic BL-C20"],  # Source:

    'Panasonic BL-C30':    ["Panasonic BL-C30"],  # Source:
    'Panasonic BL-C30A':   ["Panasonic BL-C30"],  # Source:
    'Panasonic BL-C30E':   ["Panasonic BL-C30"],  # Source:
    'Panasonic BL-C30CE':  ["Panasonic BL-C30"],  # Source:

    'Panasonic BL-C101':    ["Panasonic BL-C101"],  # Source: UPnP doc
    'Panasonic BL-C101A':   ["Panasonic BL-C101"],  # Source: UPnP doc
    'Panasonic BL-C101E':   ["Panasonic BL-C101"],  # Source: UPnP doc
    'Panasonic BL-C101CE':  ["Panasonic BL-C101"],  # Source: UPnP doc

    'Panasonic BL-C111':    ["Panasonic BL-C111"],  # Source: UPnP doc
    'Panasonic BL-C111A':   ["Panasonic BL-C111"],  # Source: UPnP doc
    'Panasonic BL-C111E':   ["Panasonic BL-C111"],  # Source: UPnP doc
    'Panasonic BL-C111CE':  ["Panasonic BL-C111"],  # Source: UPnP doc

    'Panasonic BL-C121':    ["Panasonic BL-C121"],  # Source:
    'Panasonic BL-C121A':   ["Panasonic BL-C121"],  # Source: in-house testing
    'Panasonic BL-C121E':   ["Panasonic BL-C121"],  # Source:
    'Panasonic BL-C121CE':  ["Panasonic BL-C121"],  # Source:

    'Panasonic BL-C131':    ["Panasonic BL-C131"],  # Source:
    'Panasonic BL-C131A':   ["Panasonic BL-C131"],  # Source: in-house testing
    'Panasonic BL-C131E':   ["Panasonic BL-C131"],  # Source:
    'Panasonic BL-C131CE':  ["Panasonic BL-C131"],  # Source:

    'Panasonic BL-C140':    ["Panasonic BL-C140"],  # Source: UPnP doc
    'Panasonic BL-C140A':   ["Panasonic BL-C140"],  # Source: UPnP doc
    'Panasonic BL-C140E':   ["Panasonic BL-C140"],  # Source: UPnP doc
    'Panasonic BL-C140CE':  ["Panasonic BL-C140"],  # Source: UPnP doc

    'Panasonic BL-C160':    ["Panasonic BL-C160"],  # Source: UPnP doc
    'Panasonic BL-C160A':   ["Panasonic BL-C160"],  # Source: UPnP doc
    'Panasonic BL-C160E':   ["Panasonic BL-C160"],  # Source: UPnP doc
    'Panasonic BL-C160CE':  ["Panasonic BL-C160"],  # Source: UPnP doc

    "Panasonic BL-C230":    ["Panasonic BL-C230"],  # Guess
    "Panasonic BL-C230A":   ["Panasonic BL-C230"],  # Guess
    "Panasonic BL-C230E":   ["Panasonic BL-C230"],  # Guess
    "Panasonic BL-C230CE":  ["Panasonic BL-C230"],  # Guess

    'Panasonic KX-HCM110':    ["Panasonic KX-HCM110"],  # Source:
    'Panasonic KX-HCM110A':   ["Panasonic KX-HCM110"],  # Source:
    'Panasonic KX-HCM110E':   ["Panasonic KX-HCM110"],  # Source:
    'Panasonic KX-HCM110CE':  ["Panasonic KX-HCM110"],  # Source:

    'Panasonic KX-HCM280':    ["Panasonic KX-HCM280"],  # Source:
    'Panasonic KX-HCM280A':   ["Panasonic KX-HCM280"],  # Source:
    'Panasonic KX-HCM280E':   ["Panasonic KX-HCM280"],  # Source:
    'Panasonic KX-HCM280CE':  ["Panasonic KX-HCM280"],  # Source:


    'TV-IP100W-N': ["TRENDnet TV-IP100W-N"], # TODO: CONFIRM! (this is a guess)
    'TV-IP110':    ["TRENDnet TV-IP110"],    # TODO: CONFIRM! (this is a guess)
    'TV-IP110W':   ["TRENDnet TV-IP110W"],
    'TV-IP200W':   ["TRENDnet TV-IP200W"],   # TODO: CONFIRM! (this is a guess)
    'TV-IP302PI':  ["TRENDnet TV-IP302PI"],  # GUESS
    'TV-IP312':    ["TRENDnet TV-IP312"],    # TODO: CONFIRM! (this is a guess)
    'TV-IP312W':   ["TRENDnet TV-IP312W"],
    'TV-IP400W':   ["TRENDnet TV-IP400W"],   # TODO: CONFIRM! (this is a guess)
    'TV-IP572P':   ["TRENDnet TV-IP572P"],   # GUESS
    'TV-IP572PI':  ["TRENDnet TV-IP572PI"],  # GUESS
    'TV-IP572W':   ["TRENDnet TV-IP572W"],   # GUESS
    'TV-IP572WI':  ["TRENDnet TV-IP572WI"],  # GUESS
    'TV-IP672P':   ["TRENDnet TV-IP672P"],   # GUESS
    'TV-IP672PI':  ["TRENDnet TV-IP672PI"],  # GUESS
    'TV-IP672W':   ["TRENDnet TV-IP672W"],   # GUESS
    'TV-IP672WI':  ["TRENDnet TV-IP672WI"],  # GUESS


    'Y-CAM:BLACK':  ["Y-Cam Black"],  # Guess
    'Y-CAM:KNIGHT': ["Y-Cam Knight"], # Guess
    'Y-CAM:WHITE':  ["Y-Cam White"],


    'Zavio F731E': ["Zavio F731E"],

    'ZyXEL IPC-3605N': ["ZyXEL IPC-3605N"],


    # Zonet cameras identify themselves as Fitivision cameras.  See note above.
    'cs100a': ["Zonet ZVC7610"],      # Source: guess (fitivision website)
    'cs101a': ["Zonet ZVC7610W"],     # Source: guess (fitivision website)
    'cs1003': ["Zonet ZVC7630"],      # Source: user (Evance).
    'cs1013': ["Zonet ZVC7630W"],     # Source: guess (fitivision website)
}

# For debugging, we may want disable these...
if _kDebugWithoutSpecificUpnp:
    kUpnpModelMap = {}

# A list that we'll go through (in order) if we don't find a match in the
# kUpnpModelMap...
kUpnpGenericList = [
    (r'ACTi Corporation ACM.*', "ACTi (other ACM)"),
    (r'ACTi Corporation TCM.*', "ACTi (other TCM)"),

    (r'AIC.*',        'Airlink (other - type A)'),
    (r'AIC.*',        'Airlink (other - type B)'),
    #(r'AIC.*',        'Airlink (other - type C)'),

    (r'AirCam.*',     'AirLive (other)'),

    # Source: Testing Asante Voyager I
    (r'ASANTE.*',     'Asante (other)'),

    (r'AXIS .*',      'Axis (other H264)'),
    (r'AXIS .*',      'Axis (other MJPEG)'),
    (r'AXIS .*',      'Axis (other MPEG-4 - type A)'),
    (r'AXIS .*',      'Axis (other MPEG-4 - type B)'),

    (r'Compro .*',    'Compro (other - stream 1)'),
    (r'Compro .*',    'Compro (other - stream 2)'),
    (r'Compro .*',    'Compro (other - MJPEG)'),

    (r'D-Link .*',    'D-Link (other HTTP - type A)'),
    (r'D-Link .*',    'D-Link (other HTTP - type B)'),
    (r'D-Link .*',    'D-Link (other RTSP - type A)'),
    (r'D-Link .*',    'D-Link (other RTSP - type B)'),

    (r'Linksys .*',   'Linksys (other MJPEG - type A)'),
    (r'Linksys .*',   'Linksys (other MJPEG - type B)'),# TODO: CONFIRM!
    (r'Linksys .*',   'Linksys (other MPEG-4)'),

    (r'IQ.*',         'IQinVision (other IQA2xx MPEG-4)'),
    (r'IQ.*',         'IQinVision (other MJPEG)'),
    (r'IQ.*',         'IQinVision (other MJPEG 1/2 scale)'),
    (r'IQ.*',         'IQinVision (other MJPEG 1/4 scale)'),

    (r'Panasonic .*', 'Panasonic (other MJPEG)'),
    (r'Panasonic .*', 'Panasonic (other MPEG-4)'),

    (r'TV-IP.*',      'TRENDnet (other RTSP)'),
    (r'TV-IP.*',      'TRENDnet (other MPEG-4)'),
    (r'TV-IP.*',      'TRENDnet (other MJPEG - type A)'),
    (r'TV-IP.*',      'TRENDnet (other MJPEG - type B)'),     # TODO: CONFIRM!
    #(r'TV-IP.*',      'TRENDnet (other - type C)'),


    (r'Y-CAM\:.*',    'Y-Cam (other)'),

    (r'Zavio .*',     'Zavio (other MJPEG)'),
    (r'Zavio .*',     'Zavio (other MPEG-4)'),

    (r'ZyXEL *',      'ZyXEL (other)'),
]

# For debugging, we may want disable these...
if _kDebugWithoutGenericUpnp:
    kUpnpGenericList = []

# A list of camera descriptions...
# Camera name must match exactly.  See kCameraGenericDescriptions for regular
# expression matches.
kCameraDescriptions = {
    'ACTi (other ACM)':
    """These settings have been tested with firmware v3.11.13-AC or newer. """
    """These settings use HTTP to access the camera. If you see """
    """glitches, try lowering the frame rate on the camera web page.""",

    'ACTi (other ACM - old)':
    """These settings have been tested with firmware v3.11.11-AC. """
    """These settings use HTTP to access the camera. If you see """
    """glitches, try lowering the frame rate on the camera web page.""",

    'ACTi (other TCM)':
    """Settings have been tested on firmware v4.06.09-AC using """
    """MPEG4. These settings use RTSP, which may not work """
    """across firewalls. If you see glitches, try lowering the """
    """resolution on camera web page. Default port is 7070.""",


    'Airlink (other - type A)':
    """These settings have been tested on AIC250; """
    """may work on other cameras.""",

    'Airlink (other - type B)':
    """These settings have been reported to work on AICN500; """
    """may work on other cameras.""",

    #'Airlink (other - type C)':
    #"""These settings have been reported to work on some models of """
    #"""Airlink cameras.""",

    'Alibi (other)':
    """These settings were reported to work by a user with the ALI-IPU3013R"""
    """ and my work with other models.""",

    'AirLive (other)':
    """These settings were reported to work by a user with the AirLive """
    """AirCam OD-600HD and my work with other models.""",

    'Apexis (other)':
    """These settings should work on most Apexis cameras.  They use """
    """MJPEG over HTTP.""",


    'Asante Voyager I':
    """These settings have been tested on this model and may work on """
    """similar models.  Autodetecting this camera may be unreliable for """
    """camera firmware version 2.08 and older.""",

    'Asante Voyager II':
    """These settings have been tested on this model and may work on """
    """similar models.  Autodetecting this camera may be unreliable for """
    """camera firmware version 2.08 and older.""",

    'Asante (other)':
    """These settings have been tested on the Asante Voyager I and II """
    """and may work on other cameras.""",


    'Asgari (other)':
    """These settings were reported to work by the manufacturer with the """
    """720U, EZPT, PTG2, and UIR; may work with other models.""",


    'AVTech (other HTTP)':
    """These settings were reported to work by a user with the AVI321 PTZ """
    """and may work on other cameras.""",

    'AVTech (other RTSP)':
    """These settings were reported to work by a user with the AVM542B """
    """and may work on other cameras.""",


    'AvertX (other H264)':
    """These settings were reported by the manufacturer to work with """
    """most models.""",


    'Axis (other MJPEG)':
    """These settings should work on most modern Axis cameras; they use """
    """MJPEG over HTTP.""",

    'Axis (other MPEG-4 - type A)':
    """These settings work on newer Axis cameras; they use """
    """MPEG-4 over RTSP, which may not work across some firewalls.""",

    'Axis (other MPEG-4 - type B)':
    """These settings work on most modern Axis cameras; they use """
    """MPEG-4 over RTSP, which may not work across some firewalls.""",

    'Axis (other H264)':
    """These settings work on most modern Axis cameras; they use """
    """H264 over RTSP.""",

    'Axis 247S':
    """These settings have been reported to work on Axis 247S cameras; """
    """they use MJPEG over HTTP.""",

    'Axis 2120':
    """These settings have been reported to work on Axis 2120 cameras; """
    """they use MJPEG over HTTP.""",


    'Ayrstone (other)':
    """These settings were reported by the manufactuer to work with all """
    """AyrScout cameras.""",


    'Brickcom (other)':
    """These settings were reported by a user to work with the WOB-100A """
    """and WOB-130Np; may work with other models. They use the primary """
    """video channel over rtsp.""",


    'Canon (other H.264 type A)':
    """These settings have been tested on the VB-H41 and VB-S30D; may work """
    """with other cameras.""",

    'Canon (other H.264 type B)':
    """These settings have been tested on the VB-M600D; may work """
    """with other cameras.""",

    'Canon (other H.264 type C)':
    """These settings use configuration 1 as configured on the RTP tab """
    """of VB-H and VB-S series cameras; may work with other cameras.""",


    'Compro IP60':
    """These settings have been reported to work with this model to """
    """access stream 1; they use RTSP, which may not work across firewalls. """,

    'Compro (other - stream 1)':
    """These settings have been reported to work on Compro IP60 cameras to """
    """access stream 1, but may work on other cameras; they use RTSP, which """
    """may not work across firewalls. """,

    'Compro (other - stream 2)':
    """These settings have been reported to work on Compro IP60 cameras to """
    """access stream 2, but may work on other cameras; they use RTSP, which """
    """may not work across firewalls. """,

    'Compro (other - MJPEG)':
    """These settings have been reported to work on Compro IP60 cameras to """
    """access stream 2, but may work on other cameras; they use http and """
    """require stream 2 to be configured to use MJPEG.""",


    'Cisco CIVS-IPC-2421':
    """These settings use RTSP, which may not work across firewalls. """
    """Your primary stream must be configured as MPEG-4.""",

    "Cisco WV210":
    """These settings were reported to work by a user.  These settings """
    """use RTSP, which may not work across firewalls. Your primary """
    """stream must be configured as MPEG-4.""",

    'Cisco (other RTSP - type A)':
    """These settings have been tested on the CIVS-IPC-2421; may work """
    """with other cameras. These settings use RTSP, which may not work """
    """across firewalls. Your primary stream must be configured as MPEG-4.""",

    'Cisco (other RTSP - type B)':
    """These settings have been tested on the WV210; may work """
    """with other cameras. These settings use RTSP, which may not work """
    """across firewalls. Your primary stream must be configured as MPEG-4.""",


    'D-Link DCS-2120':
    """These settings require the default access name of "live.sdp".  They """
    """have been tested on this model and may work on similar models.""",

    'D-Link DCS-3110':
    """These settings require the default access name of "video.mjpg" and """
    """JPEG as the codec type.  They have been tested on this model and may """
    """work on other cameras.""",

    'D-Link DCS-5220':
    """These settings use rtsp and require the default access name of"""
    """ "live.sdp" and audio settings of "mute" or "AAC". """
    """They have been tested on this model and may work on similar models.""",

    'D-Link DCS-6110':
    """These settings require the default access name of "live.sdp", """
    """authentication of "disable" or "basic" and MPEG-4 as the codec type. """
    """They have been tested on this model and may work on similar models.""",

    'D-Link (other HTTP - type A)':
    """These settings have been tested on D-Link DCS-920; """
    """may work on other cameras.""",

    'D-Link (other HTTP - type B)':
    """These settings require the default access name of "video.mjpg" and """
    """JPEG as the codec type.  They have been tested on the """
    """D-Link DCS-3110; may work on other cameras.""",

    'D-Link (other RTSP - type A)':
    """These settings require the default access name of "live.sdp", """
    """authentication of "disable" or "basic" and MPEG-4 as the codec type. """
    """They have been tested on the D-Link DCS-5220; may work on other cameras.""",

    'D-Link (other RTSP - type B)':
    """These settings require the default access name of "live.sdp", """
    """authentication of "disable" or "basic" and MPEG-4 as the codec type. """
    """They have been tested on the D-Link DCS-6110; may work on other cameras.""",


    'Edimax (other)':
    """These reported to work by a user with the IC-3030PoE. They use the """
    """MJPEG stream and my work with other cameras.""",


    'Encore ENVCWI-PTG1':
    """These settings were tested and reported to work by a user. They """
    """use MPEG-4 over RTSP which may not work across some firewalls.""",

    'Encore (other MJPEG)':
    """These settings have been tested on ENVCWI-PTG1; they """
    """use MPEG-4 over RTSP which may not work across some firewalls.""",


    'DB Power IP030':
    """These settings were reported by a user to work with the IP030; may """
    """work with other cameras.""",


    'Dericam (other)':
    """These settings were reported by a user to work with the M801W; may """
    """work with other cameras.""",


    'Digitus (other MPEG4)':
    """These settings were reported by a user to work with the DN-16053; may """
    """work with other cameras.""",


    "EyeSpy247 EXT":
    """These settings use the MPEG-4 stream.  If you camera is configured """
    """for MJPEG please use "EyeSpy247 (other MJPEG)" instead.""",

    "EyeSpy247 UCam247":
    """These settings use MJPEG over http. Please make sure you have the """
    """latest firmware installed for your camera.""",

    "EyeSpy247 (other MPEG-4)":
    """These settings have been confirmed to work with the PTZ, F+ and EXT """
    """models; may work with other cameras.""",

    "EyeSpy247 (other MJPEG)":
    """These settings have been confirmed to work with the PTZ, F+ and EXT """
    """models; may work with other cameras.""",


    'EYEsurv (other)':
    """These settings were reported by a user to work with the ESIP-MP1.3-BT1; """
    """may work with other cameras.""",


    'Forenix (other)':
    """These settings were reported by the manufacturer to work with the """
    """D0100 and may work with other models. The user name and password """
    """fields should be set to "admin".""",


    'Foscam FI8906W':
    """These settings were reported to work by a user. If you experience """
    """trouble try using the user account "admin" and ensuring the password """
    """is not empty.""",

    'Foscam FI9820W':
    """These settings were reported to work by a user and use H264 over """
    """rtsp. If you experience trouble try using the user account"""
    """ "admin" and ensuring the password is not empty.""",

    'Foscam (other MJPEG - type A)':
    """These settings have been reported to work on FI8904W and FI8908W; """
    """may work on other cameras. If you experience trouble try using the """
    """user account "admin" and ensuring the password is not empty.""",

    'Foscam (other MJPEG - type B)':
    """These settings have been reported to work on FI9802W and FI9821W; """
    """may work on other cameras. If you experience trouble try using the """
    """user account "admin" and ensuring the password is not empty.""",

    'Foscam (other H264)':
    """These settings use H264 over rtsp. Please make sure your camera has """
    """the latest firmware. If you experience trouble try using the user """
    """account "admin" and ensuring the password is not empty.""",


    'GeoVision (other)':
    """These settings were reported by a user to work with the GV-BL1210; """
    """may work with other models. You must have rtsp enabled in the """
    """camera's settings.""",


    'Grandstream (other)':
    """These settings were tested with the GXV3611_HD, GVX3615WP_HD, and """
    """GXV3651_FHD; may work with other models.""",

    'Grandstream (other - High quality)':
    """These settings were reported by a user to work with Grandstream IP """
    """cameras.""",

    'Grandstream (other - Low quality)':
    """These settings were reported by a user to work with Grandstream IP """
    """cameras.""",


    'Huacam (other RTSP)':
    """These settings were tested with the HCV701; may work with other """
    """models.""",


    'Instar (other MJPEG)':
    """These settings have been reported by Instar to work with """
    """Instar cameras.""",

    'Instar (other MPEG-4)':
    """These settings may work on Instar cameras and provide better picture """
    """quality than the MJPEG settings, but have not been well tested.""",

    'Instar (other H264)':
    """These settings were reported to work with IN-5907 HD, IN-6012 HD, """
    """and IN-7011 HD; may work with other models. They use H264 over rtsp.""",


    'Insteon (other MJPEG)':
    """These settings were tested with the Insteon 75790; may work with """
    """other models.""",


    'IPCAM Central (other)':
    """These settings were tested with the IPCC-7207E, IPCC-9605E, and """
    """IPCC-9610; may work with other models.""",

    'IPS (other)':
    """These settings were tested with the IPS EO1312VW; may work with """
    """other models.""",


    'KARE (other)':
    """These settings were reported to work by the manufacturer with the """
    """N5402JV, N5403JV, and N7205JV models; may work on other cameras.""",


    'Keebox (other)':
    """These settings were reported by a user to work with the IPC1000W; """
    """may work on other cameras.""",


    'Linksys (other MJPEG - type A)':
    """These settings have been tested on Linksys WVC54GCA; """
    """may work on other cameras; uses MJPEG.""",

    'Linksys (other MJPEG - type B)':
    """These settings have been tested on Linksys WVC54GC; """
    """may work on other cameras; uses MJPEG.""",

    'Linksys (other MPEG-4)':
    """These settings have been tested on Linksys WVC54GCA V1.1.00 build 02; """
    """does not work with earlier firmware.""",


    'Loftek (other)':
    """These settings were tested with the CXS 2200 and Nexus 543; """
    """may work with other cameras.""",


    'Logitech (other)':
    """These settings have been reported to work on the Logitech Alert 750e """
    """and 750i; may work on other cameras. They connect over RTSP, which """
    """may not work across some firewalls.""",


    'Lorex (other H264)':
    """These settings were reported by a user to work with the LNB2153; may """
    """work with other models.""",


    'Marmitek (other MJPEG - type A)':
    """These settings have been reported to work on the Robocam 8; """
    """may work on other cameras.""",

    'Marmitek (other MJPEG - type B)':
    """These settings should work with most current Marmitek cameras.  """
    """They use MJPEG over HTTP.""",


    'MOBOTIX (other MJPEG)':
    """These settings were reported to work by a user and should work with """
    """most MOBOTIX cameras.""",

    'NEO Coolcam (other)':
    """These settings were reported by a user to work with the NIP-06; may """
    """work with other models.""",

    'Nilox (other)':
    """These settings have been reported to work on model 16NX2601FI002; """
    """may work with other cameras.""",


    'Hikvision (other H264)':
    """These settings have been tested to work on some Hikvision cameras. """
    """They use the primary stream over rtsp.""",

    'Hikvision (other MPEG-4)':
    """These settings have been tested to work on some Hikvision cameras. """
    """They use the primary stream over rtsp.""",


    'Honeywell (other MPEG-4)':
    """These settings were reported to work with the iPCAM-WI2HCV701; may work """
    """with other cameras.""",

    'Honeywell (other MJPEG)':
    """These settings were reported to work with the iPCAM-WI2HCV701; may work """
    """with other cameras.""",


    'HooToo (other HTTP)':
    """These settings were reported to work with the HT-IP206; may work """
    """with other cameras.""",


    'HooToo (other RTSP)':
    """These settings were reported to work with the HT-IP211HDP; may work """
    """with other cameras.""",


    'IQinVision (other MJPEG)':
    """These settings use MJPEG over http and work across a number of """
    """IQinVision cameras.""",

    'IQinVision (other MJPEG 1/2 scale)':
    """These settings use MJPEG over http and work across a number of """
    """IQinVision cameras.  We request 1/2 scale image from the camera, """
    """which may reduce bandwidth usage on some cameras.""",

    'IQinVision (other MJPEG 1/4 scale)':
    """These settings use MJPEG over http and work across a number of """
    """IQinVision cameras.  We request 1/4 scale image from the camera, """
    """which may reduce bandwidth usage on some cameras.""",

    'IQinVision (other IQA2xx MPEG-4)':
    """These settings have been tested on IQinVision IQA22SI-B2; """
    """may work on other cameras; uses MPEG-4 over RTSP, which may not work """
    """across some firewalls.""",


    'OpenEye (other H264)':
    """These settings were reported by a user to work with the CM-715; may """
    """work with other models.""",


    'Panasonic BB-HCM515':
    """These settings use MPEG-4 over HTTP for 320x240 or 640x480 and MJPEG """
    """over HTTP for higher resolutions.""",

    "Panasonic BL-C230":
    """These settings were tested and reported to work by a user.""",

    'Panasonic (other MJPEG)':
    """These settings should work on most modern Panasonic network cameras """
    """and use MJPEG over HTTP.""",

    'Panasonic (other MPEG-4)':
    """These settings should work on most modern higher-end Panasonic """
    """network cameras and use MPEG-4 over HTTP. If the video signal shows """
    """glitches, try the MJPEG stream.""",

    'Polaroid (other)':
    """These settings were reported by a user to work with the IP302; """
    """may work with other models.""",

    'Samsung (other RTSP - Profile 1)':
    """These settings were reported by a user to work with the SNZ-5200. """
    """They use profile 1 over rtsp; may work with other models.""",

    'Samsung (other RTSP - Profile 5)':
    """These settings were reported by a user to work with the SmartCam HD """
    """Pro. They use profile 5 over rtsp; may work with other models.""",


    'Sanyo VCC-HD4600':
    """These settings were reported by a user to work with the VCC-HD4600. """
    """They use stream 1 over rtsp; may work with other models.""",


    'Sony (other)':
    """These settings have been tested on Sony SNC-DM110/SNC-P1 and use """
    """the camera's default video codec over HTTP; """
    """may work on other cameras.""",

    'Sony (other MJPEG)':
    """These settings have been tested on Sony SNC-DM110/SNC-P1 and use """
    """MJPEG over HTTP; to use them, you must enable the MJPEG video """
    """codec on the camera; may work on other cameras.""",

    'Sony (other MPEG-4)':
    """These settings have been tested on Sony SNC-DM110/SNC-P1 and use """
    """MPEG-4 over HTTP; to use them, you must enable the MPEG-4 video """
    """codec on the camera; may work on other cameras.""",


    'Sharx (other)':
    """These settings have been tested on Sharx SCNC2607; """
    """may work on other cameras.""",

    'Sricam (other)':
    """These settings were reported by a user to work with the AP008; """
    """may work with other models.""",

    'SURIP (other)':
    """These settings were reported by the manufacturer to work with many """
    """cameras in the SI-E5XX, SI-F10XX, and SI-L9XX lines; may work with """
    """other models.""",


    "Tenvis (other)":
    """These settings have been reported to work on JPT3815W; may work """
    """on other cameras.""",


    "Toshiba IK-WB11A":
    """These settings have been reported to work on IK-WB11A. They use """
    """MJPEG over http.""",

    "Toshiba IK-WD01A":
    """These settings have been reported to work on IK-WD01A. They require """
    """MPEG-4 and the default stream name of live.sdp.""",

    "Toshiba (other)":
    """These settings have been reported to work on IK-WD01A; may work """
    """on other cameras.  They require MPEG-4 and the default stream name """
    """of live.sdp.""",

    'TRENDnet TV-IP100W-N':
    """These settings have been reported to work on TV-IP100W-N.""",

    'TRENDnet TV-IP200W':
    """These settings have been reported to work on TV-IP200W.""",

    'TRENDnet TV-IP400W':
    """These settings have been reported to work on TV-IP400W.""",

    'TRENDnet (other MJPEG - type A)':
    """These settings have been tested on TV-IP110W and TV-IP312W; """
    """may work on other cameras.""",

    'TRENDnet (other MJPEG - type B)':
    """These settings have been reported to work on TV-IP100W-N, TV-IP200W """
    """and TV-IP400W; may work on other cameras.""",

    'TRENDnet (other MPEG-4)':
    """These settings have been tested on TV-IP312W with the latest """
    """firmware; they use MPEG-4 over RTSP which may not work across """
    """some firewalls.""",

    'TRENDnet (other RTSP)':
    """These settings have been tested on TV-IP672WI; may work with other """
    """models. They use the primary stream over rtsp.""",

    #'TRENDnet (other - type C)':
    #"""These settings have been reported to work on some models of """
    #"""TRENDnet cameras.""",

    'Ubiquiti (other)':
    """These settings were reported by a user to work with the airCam Dome """
    """and may work with other models. They require user name, password, """
    """and the "RTSP stream" checkbox to be set in the camera's """
    """configuration. """,


    'Vivotek (other MPEG-4 - type A)':
    """These settings have been tested on the Vivotek IP7361; """
    """may work on other cameras. Requires the configured access name """
    """to be "live.sdp", authentication to be "basic" or "disable", and """
    """audio to be anything other than GSM-AMR.""",

    'Vivotek (other MPEG-4 - type B)':
    """These settings have been tested on the Vivotek IP7131; """
    """may work on other cameras. Requires the configured access name """
    """to be "live.sdp", authentication to be "basic" or "disable", and """
    """audio to be anything other than GSM-AMR.""",

    'Vivotek (other H264)':
    """These settings have been tested on the Vivotek CC8130 and FD8369A-V; """
    """may work on other cameras. Requires the configured access name """
    """for rtsp to be "live.sdp".""",

    'Vivotek IP7361':
    """These settings require the default access name of "live.sdp", """
    """authentication to be "basic" or "disable", and audio to be """
    """anything other than GSM-AMR.""",

    'Vivotek (other MJPEG)':
    """These settings have been tested on the Vivotek IP7361; """
    """may work on other cameras.""",


    'Wansview NC541W':
    """These settings have been verified with the NC541W and NCB541W; may """
    """work with other cameras.""",

    'Wansview (other RTSP)':
    """These settings have been verified with the NCM621W; may """
    """work with other cameras.""",


    'Wirepath (other)':
    """These settings were reported to work with the WPS-750-DOM-IP; may """
    """work with other cameras.""",


    'Y-Cam (other)':
    """These settings have been tested on Y-Cam White; """
    """may work on other cameras.""",


    'Yanmix (other)':
    """These reported to work with the EasySE-IR1, EasySE-IR2, EasySE-F1, """
    """EasySE-F2, and EasySE-H3; may work on other cameras.""",


    'Zavio F731E':
    """These settings require you to disable RTSP in """
    """Basic > Camera > General of the camera settings. For older """
    """firmware, manually specify port 8090. """
    """Autodetecting this camera may be unreliable.""",

    'Zavio (other MJPEG)':
    """These settings have been tested with model F731E and may work on other"""
    """ cameras. These settings require you to disable RTSP in """
    """Basic > Camera > General of the camera settings. For older """
    """firmware, manually specify port 8070. """
    """Autodetecting this camera may be unreliable.""",

    'Zavio (other MPEG-4)':
    """These settings have been tested with model F731E and may work on other"""
    """ cameras. These settings require you to disable RTSP in """
    """Basic > Camera > General of the camera settings. For older """
    """firmware, manually specify port 8090. """
    """Autodetecting this camera may be unreliable.""",


    'Zonet ZVC7610':
    """These settings have been tested on Zonet ZVC7630 with updated """
    """camera firmware; may work on other cameras.""",

    'Zonet ZVC7610W':
    """These settings have been tested on Zonet ZVC7630 with updated """
    """camera firmware; may work on other cameras.""",

    'Zonet ZVC7630':
    """These settings have been tested on Zonet ZVC7630 with updated """
    """camera firmware; may work on other cameras.""",

    'Zonet ZVC7630W':
    """These settings have been tested on Zonet ZVC7630 with updated """
    """camera firmware; may work on other cameras.""",

    'Zonet (other - type A)':
    """These settings have been tested on Zonet ZVC7630 with updated """
    """camera firmware; may work on other cameras.""",

    'Zonet (other - type B)':
    """These settings have been reported to work on some models of Zonet """
    """cameras.""",

    'Zmodo (other)':
    """These settings were reported to work with the ZH-IXC15-WC; may work """
    """with other models. They use the primary stream over rtsp.""",

    'ZyXEL (other)':
    """These settings have been tested with the IPC-3605N and may work on """
    """other models. They use the primary media stream over rtsp.""",

}

kCameraGenericDescriptions = [
    (
        r'ACTi .*ACM.*',
        kCameraDescriptions['ACTi (other ACM)']
    ),
    (
        r'ACTi .*TCM.*',
        kCameraDescriptions['ACTi (other TCM)']
    ),
    (
        r'AvertX.*',
        kCameraDescriptions['AvertX (other H264)']
    ),
    (
        r'Brickcom.*',
        kCameraDescriptions['Brickcom (other)']
    ),
    (
        r'Compro.*',
        kCameraDescriptions['Compro IP60']
    ),
    (
        r'Cisco CIVS-IPC-.*',
        kCameraDescriptions['Cisco CIVS-IPC-2421']
    ),
    (
        r'DB Power.*',
        kCameraDescriptions['DB Power IP030']
    ),
    (
        r'Edimax.*',
        kCameraDescriptions['Edimax (other)']
    ),
    (
        r'EyeSpy247.*',
        kCameraDescriptions['EyeSpy247 (other MPEG-4)']
    ),
    (
        r'EYEsurv.*',
        kCameraDescriptions['EYEsurv (other)']
    ),
    (
        r'Forenix.*',
        kCameraDescriptions['Forenix (other)']
    ),
    (
        r'Foscam FI89.*',
        kCameraDescriptions['Foscam (other MJPEG - type A)']
    ),
    (
        r'Foscam FI98.*',
        kCameraDescriptions['Foscam (other H264)']
    ),
    (
        r'GeoVision.*',
        kCameraDescriptions['GeoVision (other)']
    ),
    (
        r'Grandstream.*',
        kCameraDescriptions['Grandstream (other)']
    ),
    (
        r'Huacam.*',
        kCameraDescriptions['Huacam (other RTSP)']
    ),
    (
        r'Instar.*HD',
        kCameraDescriptions['Instar (other H264)']
    ),
    (
        r'Instar.*',
        kCameraDescriptions['Instar (other MJPEG)']
    ),
    (
        r'KARE.*',
        kCameraDescriptions['KARE (other)']
    ),
    (
        r'Keebox.*',
        kCameraDescriptions['Keebox (other)']
    ),
    (
        r'Loftek.*',
        kCameraDescriptions['Loftek (other)']
    ),
    (
        r'Logitech.*',
        kCameraDescriptions['Logitech (other)']
    ),
    (
        r'Nilox.*',
        kCameraDescriptions['Nilox (other)']
    ),
    (
        r'Sanyo.*',
        kCameraDescriptions['Sanyo VCC-HD4600']
    ),
    (
        r'SURIP.*',
        kCameraDescriptions['SURIP (other)']
    ),
    (
        r'Ubiquiti.*',
        kCameraDescriptions['Ubiquiti (other)']
    ),
    (
        r'Vivotek IP.*',
        kCameraDescriptions['Vivotek (other MPEG-4 - type B)']
    ),
    (
        r'Wansview NCM.*',
        kCameraDescriptions['Wansview (other RTSP)']
    ),
    (
        r'Wansview.*',
        kCameraDescriptions['Wansview NC541W']
    ),
    (
        r'ZyXEL.*',
        kCameraDescriptions['ZyXEL (other)']
    ),
    (
        r'.*',
        """These settings have been tested on this model and may work on """
        """similar models."""
    ),
]



# Generated tables and mappings
# -----------------------------
# If it takes too long to load this file, we could consider pre-computing these
# from the above...

# A mapping from camera type to stream path tuple...
kTypeToStreamPath = dict(map(operator.itemgetter(1, 2), _kCameraTable))

# A mapping from camera type to manufacturer...
kTypeToManufacturer = dict(map(operator.itemgetter(1, 0), _kCameraTable))

# An ordered list of all IP camera types (includes other)...
kIpCameraTypes = [__camInfo[1] for __camInfo in _kCameraTable]
if kWantOtherCamOption:
    kIpCameraTypes.append(kOtherIpCamType)

# An ordered list of all camera types...
kCameraTypes = kIpCameraTypes + [kWebcamCamType]

# A list of all camera manufacturers, sorted (and with "Other" at the end)...
kCameraManufacturers = sorted(set(__camInfo[0]
                                   for __camInfo in _kCameraTable))
if kWantOtherCamOption:
    kCameraManufacturers.append(kOtherCameraManufacturer)


# A list of UPNP manufacturers, sorted (includes "other")
# ...figure this out from UPNP tables...
# TODO: Probably could just use the generic list, then add an assert
# that we have a generic for every manufacturer...
kUpnpManufactrers = sorted(
    set(kTypeToManufacturer[__camType] for __camType in                        #PYCHECKER gets confused by genexpr
        itertools.chain(*kUpnpModelMap.values())       ) |
    set(kTypeToManufacturer[__camType] for __, __camType in kUpnpGenericList)  #PYCHECKER gets confused by genexpr
)
if kWantOtherCamOption:
    kUpnpManufactrers.append(kOtherCameraManufacturer)



# Sanity checking tables above, with good error messages.
# ...these should effectively manifest themselves as compile-time errors, since
# you won't even be able to pycheck this module without hitting them...
assert (set(__x[1] for __x in kUpnpGenericList) <=                             #PYCHECKER gets confused by genexpr
        set(kCameraDescriptions.iterkeys())      ), \
       "UPNP generics must all have descriptions: %s" % str(
            set(__x[1] for __x in kUpnpGenericList) -                          #PYCHECKER gets confused by genexpr
            set(kCameraDescriptions.iterkeys())
        )
assert (set(kCameraDescriptions.iterkeys()) <=
        set(kTypeToStreamPath.iterkeys())      ), \
       "Some described cameras not in kTypeToStreamPath: %s" % str(
            set(kCameraDescriptions.iterkeys()) -
            set(kTypeToStreamPath.iterkeys())
        )
assert (set(itertools.chain(*kUpnpModelMap.values())) <=
        set(kTypeToStreamPath.iterkeys())               ), \
       "Some UPNP models not in kTypeToStreamPath: %s" % str(
            set(itertools.chain(*kUpnpModelMap.values())) -
            set(kTypeToStreamPath.iterkeys())
        )
assert [__path for __, __path, __ in kTypeToStreamPath.itervalues()            #PYCHECKER __ doesn't need to be used.
        if not __path.startswith('/')                              ] == [], \
       "All paths in kTypeToStreamPath should start with '/': %s" % str(
            [__path for __, __path, __ in kTypeToStreamPath.itervalues()
             if not __path.startswith('/')                              ]
        )
assert set(kUpnpManufactrers) <= set(kCameraManufacturers), \
       "All UPNP manufacturers must be manufacturers: %s" % str(
            set(kUpnpManufactrers) - set(kCameraManufacturers)
        )

assert set(kOldCameraNameMap.itervalues()) <= set(kIpCameraTypes), \
       "New names for old cameras must be valid cameras: %s" % str(
            set(kOldCameraNameMap.itervalues()) - set(kIpCameraTypes)
        )


# Delete ACTi, since their UPnP is off by default, and kinda broken.
# ...this will prevent users from being led through the UPnP flow if they
# choose ACTi, but at least ACTi cams will work (other than the DHCP / UPnP
# issue) if the user chooses "Other"...
kUpnpManufactrers.remove('ACTi')


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    currManufacturer = ""
    models = []

    for manufacturer, cameraModel, _ in _kCameraTable + [("", "", "")]:
        if manufacturer != currManufacturer:
            if currManufacturer:
                if not models:
                    models.append("Various")
                print "<strong>%s</strong><br />\n%s<br />\n<br />" % (currManufacturer, ', '.join(models))
            currManufacturer = manufacturer
            models = []

        if kGenericIndicator not in cameraModel:
            if cameraModel.lower().startswith(manufacturer.lower()):
                cameraModel = cameraModel[len(manufacturer):].strip()

            models.append(cameraModel)


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
