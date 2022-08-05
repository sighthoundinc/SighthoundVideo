#!/usr/bin/env python

# ----------------------------------------------------------------------
#  Copyright (C) 2014 Sighthound, Inc. All rights reserved.
#
#  The information and source code contained herein is the
#  exclusive property of Sighthound, Inc. No part of this software
#  may be used, reproduced, stored or distributed in any form,
#  without explicit written authorization from Sighthound, Inc.
# ----------------------------------------------------------------------

# Local imports...
import sys, time, datetime, copy, os
from appCommon.CommonStrings import kLegacyLicDropDeadDate
from appCommon.CommonStrings import kMajorVersionFirstReleaseDate

# The types of editions that we have...
kTrialEdition = "Trial Edition"
kStarterEdition = "Starter Edition"
kBasicEdition = "Basic Edition"
kProEdition = "Pro Edition"

_kPaidEditions = [
    kTrialEdition,
    kBasicEdition,
    kProEdition,
]

kCamerasField = "Cameras"
kEmailField = "Email"
kEditionField = "Edition"
kExpiresField = "Expires"
kMachineField = "Machine ID"
kNameField = "Name"
kSerialField = "Serial Number"
kSignatureField = "Signature"
kSupportField = "Support Expires"
kTimestampField = "Timestamp"
kPurchaseDateField = "Original Purchase Date"

kOfflineInfo = "Offline"
kAvailableInfo = "Available"

kNoValueToken = "###"
kDefaultUser = "A Happy Sighthound Video User"
kDefaultSerial = "None"

kLegacyLicenseKeys = [kCamerasField, kEditionField, kEmailField, kExpiresField,
                      kNameField, kSerialField, kSignatureField]
kLicenseKeys = [kCamerasField, kEditionField, kEmailField, kExpiresField,
                kMachineField, kNameField, kSerialField, kSignatureField,
                kSupportField, kTimestampField]


kNoExpirationDate = "0/0/0000"

kMaxCameras = 1000


##############################################################################
def hasPaidEdition(licenseDict):
    """Determine whether a license has access to paid features.

    @return isPaid  True if the license unlocks paid features.
    """
    try:
        return licenseDict.get(kEditionField, kStarterEdition) in _kPaidEditions
    except:
        return False


##############################################################################
def isLegacyLicense(licenseDict):
    """Determine whether a license is a "legacy" license (pre server).

    @return isLegacy  True if the license is a legacy license.
    """
    keys = licenseDict.keys()
    keys.sort()
    return keys == kLegacyLicenseKeys


##############################################################################
def isOfflineLicense(licenseDict):
    """Determine whether a license does not require any contact with the
    licensing server, for the purposes of refreshing the actual license data.

    @return True if the license is of offline character.
    """
    # legacy things are offline by nature
    if isLegacyLicense(licenseDict):
        return True
    # starters are always offline
    if kStarterEdition == licenseDict.get(kEditionField, kStarterEdition):
        return True
    # expiration field needs have to be somewhat of a zero characteristic
    expires = licenseDict.get(kExpiresField, "")
    return not expires or "-1" == expires


##############################################################################
def parseDate(expr, allowEmpty=False):
    """ Flexible parse for the specific date format we're using.

    @param expr The date expression.
    @param allowEmpty Empty strings translate to None.
    @return The date in seconds since epoch, or None.
    """
    if allowEmpty and "" == expr:
        return None
    try:
        return long(expr)
    except:
        return None


##############################################################################
def _mmddyyyyToTimestamp(expr):
    """ Converts a date string of the format MM/DD/YYYY to an epoch timestamp.

    @param expr The date expression.
    @return The epoch timestamp, in seconds.
    """
    dt = datetime.datetime.strptime(expr, "%m/%d/%Y")
    return time.mktime(dt.timetuple())


##############################################################################
def legacyEndOfLife():
    """ Provides the end time of the legacy license format, in _local_ time.

    @return Time when legacy licenses do expire. Seconds-since-epoch.
    """
    return _mmddyyyyToTimestamp(kLegacyLicDropDeadDate)


##############################################################################
def majorVersionFirstReleaseDate():
    """ Provides the time the first release of the major version of the current
    kind has been made.

    @return Time of the first major version release. Seconds-since-epoch.
    """
    try:
        override = _mmddyyyyToTimestamp(os.environ["SH_UPDATE_RELEASEDATE"])
        if override > time.time(): # must not be usable for cheating
            return override
    except:
        pass
    return _mmddyyyyToTimestamp(kMajorVersionFirstReleaseDate)



##############################################################################
def validateLicenseData(licData):
    """ Checks for a malformed license, in case the server ever sends us bad
    or incomplete data, so the client won't get confused.

    @param  licenseDict  The license dictionary.
    @return              None if the license is valid, error message otherwise.
    """
    legacy = isLegacyLicense(licData)
    if not legacy:
        expectedKeys = copy.deepcopy(kLicenseKeys)
        for key in licData.keys():
            expectedKeys = filter(lambda k: k != key, expectedKeys)
        if 0 < len(expectedKeys):
            return "missing keys %s" % expectedKeys

    validEditions = [kStarterEdition, kBasicEdition, kProEdition]
    if not legacy:
        validEditions.append(kTrialEdition)
    edition = licData[kEditionField]
    if not edition in validEditions:
        return "invalid edition '%s'" % edition

    intRules = [(kCamerasField, (-1, kMaxCameras))]
    if not legacy:
        intRules.append((kExpiresField, (-1, sys.maxint)))
        intRules.append((kSupportField, (-1, sys.maxint)))
        intRules.append((kTimestampField, (1, sys.maxint)))
    for intRule in intRules:
        field = intRule[0]
        value = licData[field]
        try:
            value = int(value)
        except:
            return "invalid integer field '%s'" % value
        validRange = intRule[1]
        if value < validRange[0] or value > validRange[1]:
            return "value %d of field '%s' out of range %s" % \
                   (value, field, validRange)

    notEmpty = [kEmailField, kNameField, kSignatureField]
    if not legacy:
        notEmpty.append(kMachineField)
    for field in notEmpty:
        value = licData[field]
        if 1 > len(value.strip()):
            return "field '%s' is empty" % field

    return None


##############################################################################
def applySupportExpirationToLicenseList(licList):
    """ Modifies a license list based on the currently running version of the
    software. If the support expired before the major release we do not make a
    license available, since it would not be loaded if chosen.

    @param  licList  The license list. Will be modified if needed.
    @return          True if modification happened.
    """
    result = False
    for lic in licList:
        if not licenseValidForAppVersion(lic) and lic[kAvailableInfo]:
            result = True
            lic[kAvailableInfo] = False
    return result

##############################################################################
def licenseValidForAppVersion(license):
    """Determines whether a license is valid for the running app version.

    @param  license  A license dictionary.
    @return valid    True if the license can support this application version.
    """
    return license[kSupportField] >= majorVersionFirstReleaseDate()
