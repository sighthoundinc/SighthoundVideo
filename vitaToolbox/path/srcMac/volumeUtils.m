/*
#*****************************************************************************
#
# volumeUtils.m
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
 * https://github.com/sighthoundinc/SighthoundVideo
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
#include <objc/objc.h>


uint64_t getFsAttribute(char* path, const NSString* key)
{
    uint64_t freeSpace = (uint64_t)-1;
    @autoreleasepool {
        CFStringRef pathRef = CFStringCreateWithCString(NULL, path,
                                                    kCFStringEncodingUTF8);
        NSFileManager *fileManager = [NSFileManager defaultManager];
        NSDictionary *dictionary = [fileManager attributesOfFileSystemForPath:(NSString *)pathRef error:nil];
        if (dictionary) {
            NSNumber *freeFileSystemSizeInBytes = [dictionary objectForKey:key];
            freeSpace = [freeFileSystemSizeInBytes unsignedLongLongValue];
        }
        CFRelease(pathRef);
    }
    return freeSpace;
}

uint64_t getFreeDiskspace(char* path)
{
    return getFsAttribute(path, NSFileSystemFreeSize);
}


uint64_t getTotalDiskspace(char* path)
{
    return getFsAttribute(path, NSFileSystemSize);
}
