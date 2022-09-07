#!/usr/bin/env python
# -*- coding: utf8 -*-

#*****************************************************************************
#
# SimpleEmail.py
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
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.utils import formatdate
from email.utils import make_msgid

import smtplib
import socket

import StringIO

import re
import sys

# Common 3rd-party imports...

# Local imports...
from vitaToolbox.strUtils.EnsureUnicode import ensureUtf8


# Lame trick to make py2app find all the email modules (it has problems because
# of capitalization changes).
if False:
    from email import generator, iterators

# Constants...

kEncryptionNone = "none"
kEncryptionSsl = "ssl"
kEncryptionTls = "tls"

kEncryptionList = [
    kEncryptionNone,
    kEncryptionSsl,
    kEncryptionTls,
]

kStandardPortList = [
    "25",
    "465",
    "587",
]

kDefaultPort = kStandardPortList[-1]
kDefaultEncryption = kEncryptionTls


_kOpeningConnection = (0, "Opening connection to %s:%s...")
_kStartingTls       = (1, "Initiating TLS...")
_kLoggingIn         = (2, "Logging in...")
_kSendingMessage    = (3, "Sending message...")
_kDone              = (4, "Done Sending")
kNumProgressSteps   =  4
kProgressInitialSpacing = (
    "                                                                          "
)

_kTryTlsError = "Server wouldn't allow login; try using TLS."
_kSslError = "Error establishing SSL connection."
_kNoAuthExtensionLoginError = \
    "Error logging into the server. " \
    "The server may not require a user ID and password: %s"
_kGeneralLoginError = \
    "Error logging into the server. Please check your user ID and password: %s"
_kTlsNotSupportedError = \
    "Server doesn't support TLS security."

_kRecipientsRefusedError = \
    "The server refused some email addresses:\n\n%s"

_kSendersRefusedError = \
    "The server refused your \"from\" address: %s\n\n%s %s"

# Limit timeout to 15 seconds, since we are blocking...
_kSocketTimeout = 15.0
_kInline = 'inline'
_kAttachment = 'attachment'

##############################################################################
def sendSimpleEmail(message, fromAddr, toAddrs, subject, #PYCHECKER OK: Too many args
                    host, user, password,
                    port=kDefaultPort, encryption=kDefaultEncryption,
                    imageParts=[], textParts=[],
                    progressFn=None, debug=False, messageId=None,
                    sendTextInline=False, sendImageInline=True):
    """A simple function to send a text email with some images attached.

    Note: this function requires ASCII types for all strings passed in
    except message, which can be either type str (must be ASCII) or type
    unicode (we'll mail with UTF-8 encoding).

    @param  message     The main message; it's probably good to append a \n.
    @param  fromAddr    A single "from" address.
    @param  toAddrs     A single string of "to" address, may be comma separated
                        if you want more than one; may also be a list.
    @param  subject     The subject for the message.
    @param  host        The server to connect to.
    @param  user        The user name to log into the server with.
    @param  password    The password to use for the server.
    @param  port        The port to connect to on the server.
    @param  encryption  The encryption to use.
    @param  imageParts  A list of tuples: (name, pilImage) to attach.
    @param  textParts   A list of tuples: (name, str) that represent the text
                        parts to attach.
    @param  progressFn  A progress dialog that will be called with (value, msg)
                        periodically; should return False to abort.  When done,
                        we'll pass kNumProgressSteps as the value.  May be None
                        if you don't want progress.
    @param  debug       If True, will print out debugging info.
    @param  messageId   If non-None, we'll use this as a message ID.  Useful if
                        you're going to retry and don't want duplicates.
    """
    # Check / convert parameters...
    assert encryption in kEncryptionList
    port = int(port)
    if isinstance(toAddrs, basestring):
        toAddrs = map(str.strip, toAddrs.split(','))
    if progressFn is None:
        progressFn = lambda val, msg: True
    if messageId is None:
        messageId = make_msgid("SighthoundVideo")

    if sendTextInline:
        textDisposition = _kInline
    else:
        textDisposition = _kAttachment
    if sendImageInline:
        imgDisposition = _kInline
    else:
        imgDisposition = _kAttachment

    # Make the message...
    msg = MIMEMultipart()
    if isinstance(message, unicode):
        msg.attach(MIMEText(message.encode('utf-8'), _charset='utf-8'))
    else:
        msg.attach(MIMEText(message))
    for (partName, img) in imageParts:
        partName = ensureUtf8(partName)
        f = StringIO.StringIO()
        img.save(f, 'JPEG')
        mimeImg = MIMEImage(f.getvalue())
        mimeImg.add_header('Content-Disposition', imgDisposition,
                           filename=partName)
        msg.attach(mimeImg)
    for (partName, textPart) in textParts:
        partName = ensureUtf8(partName)
        mimeText = MIMEText(textPart)
        mimeText.add_header('Content-Disposition', textDisposition,
                            filename=partName)
        msg.attach(mimeText)

    msg["From"] = fromAddr
    msg["To"] = ", ".join(toAddrs)
    msg["Subject"] = subject
    msg["Date"] = formatdate()
    msg["X-Mailer"] = "SighthoundVideo"
    msg["Message-ID"] = messageId

    # Start up a server...
    isOk = progressFn(_kOpeningConnection[0],
                      _kOpeningConnection[1] % (host, port))
    if not isOk: return

    oldStderr = smtplib.stderr
    try:
        # smtplib grabs a pointer to stderr on load; make sure it's up to date
        # in case our client overrode sys.stderr...
        smtplib.stderr = sys.stderr

        if encryption == kEncryptionSsl:
            try:
                server = smtplib.SMTP_SSL(host, port, timeout=_kSocketTimeout)
            except socket.sslerror:
                # Put a prettier face on SSL errors...
                raise smtplib.SMTPException(_kSslError)

            if debug:
                server.set_debuglevel(1)
        else:
            server = smtplib.SMTP(host, port, timeout=_kSocketTimeout)

            if debug:
                server.set_debuglevel(1)

            if encryption == kEncryptionTls:
                isOk = progressFn(*_kStartingTls)
                if not isOk: return

                # On python 2.5, need to send hello command first (python 2.6 fixes
                # this).  I _think_ this is the proper way to do it...
                ehloResponseCode, ehloMessage = server.ehlo()
                if not (200 <= ehloResponseCode <= 299):
                    # Don't expect it to not support ehlo, and if it does, it
                    # ain't gonna support TLS anyway...

                    # Raise a generic "TLS not supported" error so someone has
                    # a chance of figuring out what to do...
                    #raise smtplib.SMTPConnectError(ehloResponseCode, ehloMessage)
                    raise smtplib.SMTPException(_kTlsNotSupportedError)

                tlsResponseCode, tlsMessage = server.starttls()
                if tlsResponseCode != 220:
                    # 220 came from smtplib code; if it's not 220, the TLS won't
                    # start right anyway...

                    # Raise a generic "TLS not supported" error so someone has
                    # a chance of figuring out what to do...
                    #raise smtplib.SMTPConnectError(tlsResponseCode, tlsMessage)
                    raise smtplib.SMTPException(_kTlsNotSupportedError)

        if user or password:
            isOk = progressFn(*_kLoggingIn)
            if not isOk: return

            try:
                try:
                    # This will throw if bad username / password...
                    server.login(user, password)
                except smtplib.SMTPException, e:
                    # If we tried CRAM-MD5, try logging in without it.  This
                    # is a hack that fixes authsmtp.streamline.net as well
                    # as other servers that advertise CRAM-MD5 but don't
                    # actually work with it.  See bug #2154.
                    authMechs = set(server.esmtp_features["auth"].split())
                    if ("CRAM-MD5" in authMechs) and (len(authMechs) != 1):
                        authMechs.remove('CRAM-MD5')
                        server.esmtp_features["auth"] = ' '.join(authMechs)
                        server.login(user, password)
                    else:
                        raise
            except smtplib.SMTPException, e:
                # Give some slightly better error messages...
                if (encryption == kEncryptionNone) and server.has_extn("starttls"):
                    # Suggest TLS
                    raise smtplib.SMTPException(_kTryTlsError)
                elif (not server.has_extn("auth")):
                    # Maybe server doesn't require login?
                    raise smtplib.SMTPException(
                        _kNoAuthExtensionLoginError % str(e)
                    )
                else:
                    # Make sure that the error indicates that they were logging
                    # in...
                    raise smtplib.SMTPException(_kGeneralLoginError % str(e))

        isOk = progressFn(*_kSendingMessage)
        if not isOk: return

        try:
            server.sendmail(fromAddr, toAddrs, msg.as_string())
        except smtplib.SMTPSenderRefused, e:
            # Give a good response for bad sender...
            raise smtplib.SMTPException(_kSendersRefusedError % (
                                        e.sender, e.smtp_code, e.smtp_error))
        except smtplib.SMTPRecipientsRefused, e:
            # Give a good response for bad recipients...
            errStr = "\n\n".join("%s: %d %s" % (toAddr, code,
                                                _formatSmtpResponse(resp))
                                 for toAddr, (code, resp)
                                 in e.recipients.iteritems())
            raise smtplib.SMTPException(_kRecipientsRefusedError % errStr)
        except Exception:
            raise
        progressFn(*_kDone)

        server.quit()
    finally:
        smtplib.stderr = oldStderr


##############################################################################
def _formatSmtpResponse(msg):
    """Format an SMTP response nicely.

    This removes carriage returns and replaces with spaces, and also tries to
    clear our repetitive numeric codes.  NDR=non delivery report.

    @param  msg  The message to format.
    @return msg  The message, formatted.
    """
    # Look for messages where each line starts with a numeric code, like
    #   5.1.2 The message you are
    #   5.1.2 trying to send is invalid.
    #   5.1.2 Please try again.
    if re.match(r'^\d\.\d\.\d\s', msg):
        # It starts with a code; strip all copies...
        ndrCode = msg.split()[0]
        lines = []
        for line in msg.splitlines():
            if line.startswith(ndrCode):
                line = line[len(ndrCode):]
            lines.append(line.strip())

        # Re-join, stripping CR/LF and adding a single copy of the code...
        msg = ndrCode + ' ' + ' '.join(lines)
    else:
        # No code--just rejoin without CR/LF...
        msg = ' '.join(line.strip() for line in msg.splitlines())

    return msg


##############################################################################
def test_main():
    """OB_REDACT
       Contains various self-test code.
    """
    wantTestSendToMx = False
    wantTestTls = False
    wantTestSsl = True

    smtpServer = "smtp.gmail.com"
    fromUser = "engserver@vitamindinc.com"
    fromPass = "xxxxxxx"

    # Note: if testing "sendToMx", all of these must have the mx servers
    # listed below in mxServers...
    toUsers = ["doug@example.com"]

    from PIL import Image, ImageDraw

    img = Image.new('RGB', (320, 240), (255, 0, 0))
    imgDraw = ImageDraw.Draw(img)
    imgDraw.rectangle((20, 20, 100, 100), outline=(0, 0, 0))

    img2 = Image.new('RGB', (320, 240), (0, 255, 0))
    imgDraw = ImageDraw.Draw(img2)
    imgDraw.text((100, 100), "Hello there...")

    message = "Here's the main message.\n"
    subject = "My simple email test"

    imageParts = [("RedWithRect.jpg", img), ("GreenWithText.jpg", img2)]
    textParts = [
        ("TxtPart1.txt", "This is text part 1"),
        ("LargePart.txt", "ABCD" * (1024 * 100))
    ]

    if wantTestSendToMx:
        # Ideally, these should be queried from DNS (use PyDNS?), but since
        # we own vitamindinc.com, we should be able to hardcode.  NOTE: It means
        # that using this would break if we switched away from google apps, or
        # if google ever changed their config (which would break lots of people
        # I'd think).
        mxServers = [
            "aspmx.l.google.com.",
            "alt1.aspmx.l.google.com.",
            "alt2.aspmx.l.google.com.",
            "aspmx2.googlemail.com.",
            "aspmx3.googlemail.com.",
        ]

        errors = []
        for mxServer in mxServers:
            try:
                sendSimpleEmail(message, fromUser, toUsers, subject,
                                mxServer, "", "", "25", kEncryptionNone,
                                imageParts, textParts, None, True)
            except socket.error, e:
                errors.append(e)
            else:
                break
        else:
            print "Couldn't connect to any servers.  Errors:\n"
            for e in errors:
                print "%s\n\n" % (str(e))

    if wantTestTls:
        sendSimpleEmail(message, fromUser, toUsers, subject,
                        smtpServer, fromUser, fromPass, "587", kEncryptionTls,
                        imageParts, textParts, None, True)

    if wantTestSsl:
        sendSimpleEmail(message, fromUser, toUsers, subject,
                        smtpServer, fromUser, fromPass, "465", kEncryptionSsl,
                        imageParts, textParts, None, True)


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_main()
    else:
        print "Try calling with 'test' as the argument."
