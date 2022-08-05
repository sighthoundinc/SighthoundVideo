/*
#*****************************************************************************
#
# shsudo.m
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

#import <stdio.h>
#import <libgen.h>

#import <Foundation/Foundation.h>
#import <Security/Security.h>

// Simple sudo-like approach to elevate a command to admin level. When running
// in the UI there should be a dialog prompted to provide credentials.

// TODO: this is the legacy way to do get privileges - it still works under
//       OSX 10.10, but we need to change this to SMJobBless soon (that one
//       requires code signing though, so it won't be equally comfortable)

int main(int argc, char *argv[]) {

    bool wait = (1 < argc) && (0 == strcmp("--wait", argv[1]));

    if (( wait && 3 > argc) ||
        (!wait && 2 > argc)) {
        fprintf(stderr, "usage: %s {--wait} [command] {arg} {arg} ...\n",
                basename(argv[0]));
        return -1;
    }

    AuthorizationItem   authItem   = { kAuthorizationRightExecute, 0, NULL, 0 };
    AuthorizationRights authRights = {1, &authItem };
    AuthorizationFlags  authFlags  = kAuthorizationFlagDefaults           |
                                     kAuthorizationFlagInteractionAllowed |
                                     kAuthorizationFlagPreAuthorize       |
                                     kAuthorizationFlagExtendRights;

    AuthorizationRef authRef;
    OSStatus ostat = AuthorizationCreate(
         &authRights,
         kAuthorizationEmptyEnvironment,
         authFlags,
         &authRef);
    if (errAuthorizationSuccess != ostat)
        return ostat;

    FILE* out = NULL;
    ostat = AuthorizationExecuteWithPrivileges(
       authRef,
       argv[wait ? 2 : 1],     // the command passed in
       kAuthorizationFlagDefaults,
       &argv[wait ? 3 : 2],    // the NULL terminated argument list (or none)
       wait ? &out : NULL);

	if (errAuthorizationSuccess == ostat && out) {
        while (EOF != fgetc(out));
        fclose(out);
    }

cleanup:
    AuthorizationFree(authRef, kAuthorizationFlagDestroyRights);
    return ostat;
}
