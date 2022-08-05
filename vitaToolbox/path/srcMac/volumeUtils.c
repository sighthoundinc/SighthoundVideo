/*
#*****************************************************************************
#
# volumeUtils.c
#
#
#
#*****************************************************************************
#
 *
 * Copyright 2013-2022 Sighthound, Inc.
 *
 * Licensed under the GNU GPLv3 license found at
 * https://www.gnu.org/licenses/gpl-3.0.txt
 *
 * Alternative licensing available from Sighthound, Inc.
 * by emailing opensource@sighthound.com
 *
 * This file is part of the Sighthound Video project which can be found at
 * https://github.url/thing
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; using version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02111, USA.
 *
#
#*****************************************************************************
*/
#include <Carbon/Carbon.h>


// This function based on code from a forum post at
// http://forums.macrumors.com/archive/index.php/t-249274.html
// Takes a char* specifying a path and returns the name of the volume it is on.
// The return value must be freed by the caller.
char* getVolumeName(char *path)
{
    CFStringRef pathRef = CFStringCreateWithCString(NULL, path,
                                                kCFStringEncodingUTF8);
    CFStringRef escapedPathRef = CFURLCreateStringByAddingPercentEscapes(
                                                NULL, pathRef, NULL, NULL,
                                                kCFStringEncodingUTF8);
    CFURLRef url = CFURLCreateWithString(NULL, escapedPathRef, NULL);
    FSRef bundleRef;
    FSCatalogInfo info;
    HFSUniStr255 volName;
    char* retName = NULL;

    if (url){
        if (CFURLGetFSRef(url, &bundleRef) &&
            (FSGetCatalogInfo(&bundleRef, kFSCatInfoVolume, &info, NULL, NULL,
                             NULL) == noErr) &&
            (FSGetVolumeInfo(info.volume, 0, NULL, kFSVolInfoNone, NULL,
                             &volName, NULL) == noErr))
        {

            CFStringRef stringRef = FSCreateStringFromHFSUniStr(NULL, &volName);
            if (stringRef) {
                CFIndex length = CFStringGetLength(stringRef);
                CFIndex maxSize = CFStringGetMaximumSizeForEncoding(length, kCFStringEncodingUTF8) + 1;
                retName = NewPtr(maxSize);
                CFStringGetCString(stringRef, retName, maxSize, kCFStringEncodingUTF8);
                CFRelease(stringRef);
            }
        }

        CFRelease(url);
        CFRelease(pathRef);
        CFRelease(escapedPathRef);
    }

    return retName;
}


// This function based on code from a forum post at
// http://forums.macrumors.com/archive/index.php/t-249274.html
// Takes a char* specifying a path and returns whether it is a Local Volume, a
// Remote Volume, or an Unknown Volume.
char* getVolumeType(char *path)
{
    CFStringRef pathRef = CFStringCreateWithCString(NULL, path,
                                                kCFStringEncodingUTF8);
    CFStringRef escapedPathRef = CFURLCreateStringByAddingPercentEscapes(
                                                NULL, pathRef, NULL, NULL,
                                                kCFStringEncodingUTF8);
    CFURLRef url = CFURLCreateWithString(NULL, escapedPathRef, NULL);
    FSRef bundleRef;
    FSCatalogInfo info;
    GetVolParmsInfoBuffer volParms;

    if (url){
        if (CFURLGetFSRef(url, &bundleRef) &&
            (FSGetCatalogInfo(&bundleRef, kFSCatInfoVolume, &info, NULL, NULL,
                             NULL) == noErr) &&
            (FSGetVolumeParms(info.volume, &volParms,
                              sizeof(volParms)) == noErr))
        {
            if (volParms.vMServerAdr != 0)
                return "Remote Volume";
            else
                return "Local Volume";
        }

        CFRelease(url);
        CFRelease(pathRef);
        CFRelease(escapedPathRef);
    }

    return "Unknown Volume";
}


// Frees a pointer that was allocated with NewPtr.
void freeVolumeName(void *volumeName) {
    DisposePtr(volumeName);
}


#ifdef _MAIN_VOLUMEUTILS

// build with this command, ignore the deprecation warnings:
// gcc -D_MAIN_VOLUMEUTILS -framework carbon volumeUtils.c -o volumeUtils

#include <stdio.h>

int main(int argc, char** argv)
{
    char *volType, *volName;

    if (2 != argc) {
        fprintf(stderr, "usage: %s [path]\n", argv[0]);
        return 1;
    }

    volType = getVolumeType(argv[1]);
    volName = getVolumeName(argv[1]);

    printf("type: %s\nname: %s\n", volType, volName);

    if (volName)
        freeVolumeName(volName);

    return 0;
}

#endif



