/*
#*****************************************************************************
#
# UpdaterAppDelegate.m
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

#import "UpdaterAppDelegate.h"
#import <Cocoa/Cocoa.h>
#import "NTSynchronousTask.h"

@implementation UpdaterAppDelegate

@synthesize window;

- (void)applicationDidFinishLaunching:(NSNotification *)aNotification {
	[progressBar setIndeterminate:YES];
	[NSThread detachNewThreadSelector:@selector(_extractDMG:) toTarget:self withObject:nil];
}


// Opens the DMG, copies out the app and launches the application
-(void)_extractDMG:(id) sender
{
    NSError* err = nil;
	NSString* archivePath = @"";
	NSString* dst = @"/Applications/";
    NSString* appName = @"Sighthound Video.app";
	NSArray* args = [[NSProcessInfo processInfo] arguments];

	bool origRenamed = false;
	//pause();
	if ([args count]>3)
	{
		id arg1 = [args objectAtIndex:1];
		id arg2 = [args objectAtIndex:2];
		id arg3 = [args objectAtIndex:3];
		archivePath = arg1;
		dst = arg2;
                appName = arg3;
	} else {
        NSLog(@"Error: Invalid number of arguments!!");
		goto finally;
	}

        NSString* appBackupName = [NSString stringWithFormat:@"Backup of %@", appName];
	NSString* dstPath = [dst stringByAppendingPathComponent:appName];

	// start the animation up
	[progressBar performSelectorOnMainThread: @selector(startAnimation:)
									withObject: self
								 waitUntilDone: NO];

	NSAutoreleasePool *pool = [[NSAutoreleasePool alloc] init];
	BOOL mountedSuccessfully = NO;

	// get a unique mount point path
    NSString *mountPoint = [NSTemporaryDirectory() stringByAppendingPathComponent:[[NSProcessInfo processInfo] globallyUniqueString]];
    // uncomment below to get a unique mount point path in the same directory where this app is located.
	//NSString *mountPoint = [[[[NSBundle mainBundle] bundlePath] stringByDeletingLastPathComponent] stringByAppendingPathComponent:[[NSProcessInfo processInfo] globallyUniqueString]];

	if ([[NSFileManager defaultManager] fileExistsAtPath:mountPoint])
    {
        NSLog(@"Error: Mounting point directory '%@' already exists!!", mountPoint);
        goto finally;
    }

    NSLog(@"Info: Using directory '%@' as the mounting point.", mountPoint);

	// create mount point folder
	[[NSFileManager defaultManager] createDirectoryAtPath:mountPoint withIntermediateDirectories:YES attributes:nil error:&err];
	if (![[NSFileManager defaultManager] fileExistsAtPath:mountPoint])
    {
        NSString* errStr = @"";
        if (err != nil) {
            errStr = [err localizedDescription];
        }
        NSLog(@"Error: Could not create mounting point directory!! %@", errStr);
        goto finally;
    }

	NSArray* arguments = [NSArray arrayWithObjects:@"attach", archivePath, @"-mountpoint", mountPoint, @"-noverify", @"-nobrowse", @"-noautoopen", nil];
	// Push a Yes into the pipe to accept the license agreement
	NSData* yesData = [[[NSData alloc] initWithBytes:"yes\n" length:4] autorelease];

	NSData *result = [NTSynchronousTask task:@"/usr/bin/hdiutil" directory:@"/" withArgs:arguments input:yesData];
	if (!result)
    {
        NSLog(@"Error: Could not mount '%@' at '%@'!!", archivePath, mountPoint);
        goto finally;
    }
	mountedSuccessfully = YES;

	// Copy over the app file
	NSString *currentFullPath = [mountPoint stringByAppendingPathComponent:appName];
	NSString *dstPathCopy = [dst stringByAppendingPathComponent:appBackupName];
    err = nil;
    // Remove back up file if it exists
	if ([[NSFileManager defaultManager] fileExistsAtPath:dstPathCopy]){
		[[NSFileManager defaultManager] removeItemAtPath:dstPathCopy error:&err];
        if (err != nil) {
            NSLog(@"Warning: Could not remove back up file!! %@", [err localizedDescription]);
        }
	}
	// rename dst if it exists
	if ([[NSFileManager defaultManager] fileExistsAtPath:dstPath]){
        err = nil;
		[[NSFileManager defaultManager] moveItemAtPath:dstPath toPath:dstPathCopy error:&err];
		if (err != nil) {
			NSLog(@"Error: Could not rename the file!! %@", [err localizedDescription]);
			goto finally;
		} else {
			origRenamed = true;
		}
	}

    err = nil;
	[[NSFileManager defaultManager] copyItemAtPath:currentFullPath toPath:dstPath error:&err];
	if (err!=nil){
		NSLog(@"Warning: Copy failed!! %@", [err localizedDescription]);

		// Copy original back
		if (origRenamed)
			[[NSFileManager defaultManager] moveItemAtPath:dstPathCopy toPath:dstPath error:&err];
	} else {
		if (origRenamed)
			[[NSFileManager defaultManager] removeItemAtPath:dstPathCopy error:&err];
	}
finally:
	[NSTask launchedTaskWithLaunchPath:@"/usr/bin/open" arguments:[NSArray arrayWithObjects:dstPath, nil]];

	if (mountedSuccessfully)
		[NSTask launchedTaskWithLaunchPath:@"/usr/bin/hdiutil" arguments:[NSArray arrayWithObjects:@"detach", mountPoint, @"-force", nil]];

	[progressBar performSelectorOnMainThread: @selector(stopAnimation:)
								  withObject: self
							      waitUntilDone: NO];
	[pool drain];
	exit(0);
}
@end
