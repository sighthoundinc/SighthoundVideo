#!/usr/bin/env python

#*****************************************************************************
#
# LoggingUtils.py
#
#
#
#*****************************************************************************
#
#
# Copyright 2013-2022 Arden.ai, Inc.
#
# Licensed under the GNU GPLv3 license found at
# https://www.gnu.org/licenses/gpl-3.0.txt
#
# Alternative licensing available from Arden.ai, Inc.
# by emailing opensource@ardenai.com
#
# This file is part of the Arden AI project which can be found at
# https://github.com/ardenaiinc/ArdenAI
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

import ctypes
import logging.handlers
import os
import sys
import traceback

try:
    import codecs
except ImportError:
    codecs = None

# Constants...
kLogLevelDebug = logging.DEBUG
kLogLevelInfo = logging.INFO
kLogLevelWarning = logging.WARNING
kLogLevelError = logging.ERROR
kLogLevelCritical = logging.CRITICAL


# singleton returned by getLogger
logger = None

def EnvToInt(name, default):
    result = default
    try:
        result = int(os.getenv(name))
    except:
        result = default
    return result


def LogLevelToInt(value, default):
    result = default
    try:
        result = int(value)
        if result < kLogLevelDebug or result > kLogLevelCritical:
            result = default
    except:
        valueLower = "";
        if value != None:
            valueLower = value.lower()
        if valueLower == "debug":
            result = kLogLevelDebug
        elif valueLower == "trace":
            result = kLogLevelDebug
        elif valueLower == "info":
            result = kLogLevelInfo
        elif valueLower == "warning":
            result = kLogLevelWarning
        elif valueLower == "critical":
            result = kLogLevelCritical
        elif valueLower == "error":
            result = kLogLevelError
        else:
            result = default

    return result



_kDefaultLogLevel = LogLevelToInt(os.getenv("SV_LOG_LEVEL"), kLogLevelInfo)
_kDefaultMaxSize  = EnvToInt("SV_LOG_FILE_SIZE_MB", 5)*1024*1024 # 1MB default
_kDefaultNumBackups = EnvToInt("SV_LOG_FILE_COUNT", 1)

_kLogLevel = _kDefaultLogLevel
_kMaxSize = _kDefaultMaxSize
_kNumBackups = _kDefaultNumBackups

_kMemoryLoggerSize = 131072 # 128K

# We use a console handler when there is no disk logging going. Has been there
# since the very beginning. Not really needed, but we keep it until we
# absolutely know better. However for load tests etc having an option not to do
# console is desired.
_kUseConsoleHandler = False

# Globals...

# We'll set this to the first logger gets created
_isInitted = False


# Keep track of the original stderr so we can always write to it, even if it's
# been redirected.
_origStderr = sys.stderr


# From logging module docs:
#
# Note The default value of raiseExceptions is True. This is because during
# development, you typically want to be notified of any exceptions that occur.
# It's advised that you set raiseExceptions to False for production usage.
logging.raiseExceptions = False


###########################################################
def setLogParams(lvlStr, maxSize, maxCount):
    global _kMaxSize
    global _kLogLevel
    global _kNumBackups
    global logger

    needReenable = False

    logLevel = LogLevelToInt(lvlStr, _kDefaultLogLevel)
    logSize = maxSize if maxSize > 0 else _kDefaultMaxSize
    logCount = maxCount if maxCount > 0 else _kDefaultNumBackups

    if logSize != _kMaxSize:
        _kMaxSize = logSize
        needReenable = True
    if logCount != _kNumBackups:
        _kNumBackups = logCount
        needReenable = True
    if logLevel != _kLogLevel:
        _kLogLevel = logLevel
        needReenable = True

    if logger is not None:
        logger.setLevel(_kLogLevel)
        logger.setLogSize(_kMaxSize)

        # the number of files we want to keep had changed
        # restart logging for that to take effect
        if logger.isDiskLoggingEnabled() and needReenable:
            logger.disableDiskLogging()
            logger.enableDiskLogging()

###########################################################
def flushingStderrLogCB(lvl, s):
    sys.stderr.write("%d: %s" % (lvl,s))
    sys.stderr.flush()

###########################################################
def nonFlushingStderrLogCB(lvl, s):
    sys.stderr.write("%d: %s" % (lvl,s))

###########################################################
def getStderrLogCB():
    if _kLogLevel == kLogLevelDebug:
        return flushingStderrLogCB
    return nonFlushingStderrLogCB

###########################################################
def getLogger(logName, logDirectory=None, logSize=_kMaxSize):
    """Get a logger and point it at the given directory.

    This is just a wrapper for the python call "logging.getLogger".  It does
    a few extra things:
    - The first time it's called, it installs our VitaLogger logger as the
      logger class, so we get our special functionality.
    - It will set the logDirectory on the logger for you, if you want.

    @param  logName       The name of the log to create.
    @param  logDirectory  The directory in which to store the log file; if
                          None, we won't change directories; if None and this
                          is the first time we've been called for a given log,
                          we will start by logging to console and memory.
                          You can later call setLogDirectory() to set this.
    @param  logSize       The size in bytes to dedicate to the log.  Note
                          that up to twice this size may be used as we keep
                          one rollover log.
    """
    global _isInitted
    global logger

    if not _isInitted:
        logging.setLoggerClass(VitaLogger)
        _isInitted = True

    try:
        # Get the logger for the given log name, initting it if this is the
        # first time...
        logger = logging.getLogger(logName)
        logger.setLogSize(logSize)

        # Set the log directory if it's different than what was there before.
        # Enable disk logging if it was enabled, or if there was no log
        # directory before...
        if logDirectory is not None:
            oldLogDirectory = logger.getLogDirectory()
            if logDirectory != oldLogDirectory:
                wasEnabled = logger.isDiskLoggingEnabled()
                if wasEnabled:
                    logger.disableDiskLogging()

                logger.setLogDirectory(logDirectory)

                wantEnabled = (oldLogDirectory is None) or (wasEnabled)
                if wantEnabled:
                    logger.enableDiskLogging()

        return logger

    except Exception:
        pass

    # Return an empty logger if we were unable to create a real for any reason
    return EmptyLogger()


##############################################################################
def formatExceptionConcisely(exc_info):
    """Format the given exception in a concise manner.

    >>> def fn1():
    ...   raise Exception("Bogus")
    >>> def fn2():
    ...    fn1()
    >>> try:
    ...   fn2()
    ... except Exception, e:
    ...   print formatExceptionConcisely(sys.exc_info())
    <type 'exceptions.Exception'>: Bogus - <doctest __main__.formatExceptionConcisely[2]>(2); <doctest __main__.formatExceptionConcisely[1]>(2); <doctest __main__.formatExceptionConcisely[0]>(2)

    @param  exc_info  Info from sys.exc_info()
    @return s         String representation of the exception.
    """
    excType, excValue, excTraceback = exc_info

    strList = []

    tbList = traceback.extract_tb(excTraceback)
    for (filename, lineNum, _, _) in tbList:
        strList.append("%s(%d)" % (os.path.split(filename)[1], lineNum))

    return "%s: %s - %s" % (str(excType), str(excValue), '; '.join(strList))


##############################################################################
def formatStackConcisely():
    """Format the current stack in a concise manner.

    @param  f  The stack frame.

    >>> def fn1():
    ...   tbStr = formatStackConcisely()
    ...   loc = tbStr.find('<doctest')
    ...   print tbStr[loc:]
    >>> def fn2():
    ...   fn1()
    >>> fn2()
    <doctest __main__.formatStackConcisely[2]>(1); <doctest __main__.formatStackConcisely[1]>(2); <doctest __main__.formatStackConcisely[0]>(2)

    @return s  String representation of the stack trace.
    """
    strList = []

    tbList = traceback.extract_stack()
    for (filename, lineNum, _, _) in tbList[:-1]:
        strList.append("%s(%d)" % (os.path.split(filename)[1], lineNum))

    return "TB: %s" % ('; '.join(strList))


##############################################################################
class VitaLogger(logging.Logger):
    """Our logging class.

    This is only instantiated once for each log name.

    This class creates and sets up a formatter and log handlers.  You shouldn't
    need to add / change any of those.  Generally, a user of this class would:
    - Implicitly create this class by using the 'getLogger' above.
    - Log using the standard "debug()", "error()", ... methods.
    - If desired, grab the standard streams (stderr/stdout).  Only one logger
      per process should do this.
    - If needed, later set the logDirectory.  This is needed for wx on Windows
      where you need to redirect streams before wx inits, but don't know your
      log directory until after wx inits.
    - If needed, turn off/on disk logging.  This is needed when forking a sub-
      process that shouldn't share our file handle.


    Note that whenever disk logging is not enabled, logs will be written to
    the console (stderr).  They will also be buffered up and written to the
    disk log later when it's set.
    """

    ###########################################################
    def __init__(self, logName):
        """VitaLogger constructor.

        This is only allowed to take one argument: the name of the log.

        @param  logName  The name of the log.
        """
        logging.Logger.__init__(self, logName)

        # Save parameters...
        self._logName = logName

        # Init members...
        if _kUseConsoleHandler:
            self._consoleHandler = None
        self._memoryHandler = None
        self._diskHandler = None
        self._logDirectory = None
        self._logSize = _kMaxSize

        # Init our log level...
        self.setLevel(_kLogLevel)

        # Create the formatter.  All Arden AI logs have this format.
        self._formatter = _VitaFormatter("%(asctime)s - %(process)s-%(thread)s - %(levelname)s - "
                                         "%(filename)s - %(funcName)s - "
                                         "%(message)s")

        # Filter out blank records
        self._filter = _FilterBlanks()
        self.addFilter(self._filter)

        # Create our basic handlers...
        # ...note that we use the original stderr from when we were first
        # initted.  This allows someone to catch stderr, then redirect it to
        # our logger without it causing a loop...
        self._memoryHandler = logging.handlers.MemoryHandler(_kMemoryLoggerSize)
        self._memoryHandler.setFormatter(self._formatter)
        if _kUseConsoleHandler:
            self._consoleHandler = logging.StreamHandler(_origStderr)
            self._consoleHandler.setFormatter(self._formatter)

        # Install basic handlers for now...
        self.addHandler(self._memoryHandler)
        if _kUseConsoleHandler:
            self.addHandler(self._consoleHandler)

        # Keep a pointer to a ctypes log function as a convenience to our
        # clients.
        LOGFUNC = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p)
        self._cLogFn = LOGFUNC(self.log)


    ###########################################################
    def setLogSize(self, logSize):
        """Set the maximum size of the individual log files.

        @param  logSize  The size in bytes to dedicate to the log.  Note
                         that up to twice this size may be used as we keep
                         one rollover log.
        """
        self._logSize = logSize


    ###########################################################
    def getCLogFn(self):
        """Returns a logging function that can be passed to ctypes calls.

        This function will output a warning.

        @return cLogFn  A function that takes an integer level and a string
                        to log.
        """
        return self._cLogFn


    ###########################################################
    def setLogDirectory(self, logDirectory):
        """Set the directory for logging to.

        Should be called while disk logging is turned off.  This doesn't
        actually turn disk logging on--see enableDiskLogging().

        @param  logDirectory  The directory in which to store the log file.
                              This does not need to exist yet.
        """
        assert (self._diskHandler is None), \
               "Should turn off disk logging before setting log directory."

        if type(logDirectory) == str:
            logDirectory = logDirectory.decode('utf-8')
        self._logDirectory = logDirectory


    ###########################################################
    def getLogDirectory(self):
        """Get the current log directory.

        @return logDirectory  The current log directory.
        """
        return self._logDirectory


    ###########################################################
    def isDiskLoggingEnabled(self):
        """Return whether disk logging is enabled.

        @return isDiskLoggingEnabled  True if enabled; False if not.
        """
        return self._diskHandler is not None


    ###########################################################
    def enableDiskLogging(self, wantEnable=True):
        """Turn on (or off) disk logging.

        When disk logging is turned on, anything in the memory logging buffer
        will be flushed to disk, then the memory and console loggers will be
        turned disabled.

        When disk logging is turned off, the memory logger and console logger
        will be re-enabled and the disk logger will be closed.

        @param  wantEnable  If True, we're enabling; else disabling.
        """
        if wantEnable:
            assert not self.isDiskLoggingEnabled(), \
                   "Disk logger can't be enabled twice."

            try:
                # Ensure the target directory exists
                if not os.path.isdir(self._logDirectory):
                    os.makedirs(self._logDirectory)

                # Make the disk handler
                logName = self._logName.decode("utf-8")
                logPath = os.path.join(self._logDirectory, logName)
                self._diskHandler = _VitaRotatingFileHandler(
                    logPath, maxBytes=self._logSize,
                    backupCount=_kNumBackups
                )
                self._diskHandler.setFormatter(self._formatter)

                # Install it and turn off the console/memory handler...
                self.addHandler(self._diskHandler)
                if _kUseConsoleHandler:
                    self.removeHandler(self._consoleHandler)
                self.removeHandler(self._memoryHandler)

                # Send anything that was buffered in the memory handler to
                # the disk...
                self._memoryHandler.setTarget(self._diskHandler)
                self._memoryHandler.flush()
                self._memoryHandler.setTarget(None)
            except Exception:
                pass
        else:
            assert self.isDiskLoggingEnabled(), \
                   "Disk logger can't be disabled when not enabled."

            self._diskHandler.invalidate(self._memoryHandler)
            self.addHandler(self._memoryHandler)
            if _kUseConsoleHandler:
                self.addHandler(self._consoleHandler)
            self.removeHandler(self._diskHandler)

            self._diskHandler.close()
            self._diskHandler = None


    ###########################################################
    def disableDiskLogging(self):
        """Shorthand for enableDiskLogging(False)"""
        self.enableDiskLogging(False)


    ###########################################################
    def grabStdStreams(self):
        """This will grab the standard streams (sys.stdout, sys.stderr).

        This should only be done by one logger and should only be done once!
        """
        stdoutLogger = _LoggerStream(self.info)
        stderrLogger = _LoggerStream(self.warn)

        # Note: we'd like to test this error case, but on Mac when we fork due
        # to multiprocessing, the sys.stdout and sys.stderr objects actually
        # get copied from our parent process.
        #assert not isinstance(sys.stderr, _LoggerStream), \
        #       "Shouldn't grab stdout/stderr more than once!"

        sys.stdout = stdoutLogger
        sys.stderr = stderrLogger



##############################################################################
class _FilterBlanks(logging.Filter):
    """Simple logging filter that will filter out blank records.

    This also has the side effect of stripping trailing blanks (including
    newlines) from messages.
    """

    ###########################################################
    def filter(self, record):
        """Filter blank records.

        NOTE: We actually modify the passed in record.  I'm not sure if this is
        OK, but it seems to work.

        @param  record  The record to look at.
        @return isGood  True if we want to keep; False to filter.
        """
        if isinstance(record.msg, basestring):
            record.msg = record.msg.rstrip()
        return record.msg != ""


##############################################################################
class _VitaFormatter(logging.Formatter):
    """Formatter subclass that formats a little differently.

    Specifically:
    - tracebacks are made more concise
    """

    ###########################################################
    def formatException(self, exc_info):
        """Format the given exception for the logs.

        @param  exc_info  Info from sys.exc_info()
        @return s         String representation of the exception.
        """
        return formatExceptionConcisely(exc_info)


##############################################################################
class _VitaRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that doesn't get stuck in infinite recursion and
    is also thread-safe (atomic her emission call).

    The default RotatingFileHandler can get stuck in an infinite loop in due to
    the way that we're using it.  Specifically, if it fails to rotate the log
    file, it will try to print an error.  Since we have it capturing stderr,
    this will loop back around and it will try to rotate again, which will
    cause another error, ...

    We see this type of stack crawl:
        File "c:\Python25\lib\logging\__init__.py", line 985, in info
          apply(self._log, (INFO, msg, args), kwargs)
        File "c:\Python25\lib\logging\__init__.py", line 1101, in _log
          self.handle(record)
        File "c:\Python25\lib\logging\__init__.py", line 1111, in handle
          self.callHandlers(record)
        File "c:\Python25\lib\logging\__init__.py", line 1148, in callHandlers
          hdlr.handle(record)
        File "c:\Python25\lib\logging\__init__.py", line 655, in handle
          self.emit(record)
        File "c:\Python25\lib\logging\handlers.py", line 79, in emit
          self.handleError(record)
        File "c:\Python25\lib\logging\__init__.py", line 706, in handleError
          traceback.print_exception(ei[0], ei[1], ei[2], None, sys.stderr)
        File "c:\Python25\lib\traceback.py", line 124, in print_exception
          _print(file, 'Traceback (most recent call last):')
        File "c:\Python25\lib\traceback.py", line 13, in _print
          file.write(str+terminator)
        File "c:\Python25\lib\logging\__init__.py", line 999, in warning
          apply(self._log, (WARNING, msg, args), kwargs)
        File "c:\Python25\lib\logging\__init__.py", line 1101, in _log
          self.handle(record)
        File "c:\Python25\lib\logging\__init__.py", line 1111, in handle
          self.callHandlers(record)
        File "c:\Python25\lib\logging\__init__.py", line 1148, in callHandlers
          hdlr.handle(record)
        File "c:\Python25\lib\logging\__init__.py", line 655, in handle
          self.emit(record)
        File "c:\Python25\lib\logging\handlers.py", line 79, in emit
          self.handleError(record)
        File "c:\Python25\lib\logging\__init__.py", line 706, in handleError
        ...
        ...
        ...

    We fix the problem by ignoring rollover failurs...
    """

    # None for normal operation, the next handler in line to get logs after this
    # instance has been taken out of orbit. Avoids a race condition, as a matter
    # of fact hard crash (under OSX) when we enable/disable disk logging.
    _nextHandler = None

    ###########################################################
    def invalidate(self, nextHandler):
        """Invalidates this instance, so it won't emit data to the current
        file anymore, but pass it in to a new handler.

        @param  nextHandler  The next handler which is meant to get the log
                             data from now on.
        """
        self.acquire()
        try:
            self._nextHandler = nextHandler
        finally:
            self.release()

    ###########################################################
    def emit(self, record):
        """ Emit a record, in a synchronized fashion.

        @param  record  The log record.
        """
        self.acquire()
        try:
            if self._nextHandler:
                self._nextHandler.emit(record)
            else:
                logging.handlers.RotatingFileHandler.emit(self, record)
        finally:
            self.release()

    ###########################################################
    def doRollover(self):
        """Wrap superclass doRollover() and prevent recursion."""

        try:
            logging.handlers.RotatingFileHandler.doRollover(self)
        except Exception:
            # Ignore roll-over exceptions--just re-open the file...
            # ...open in 'w+' mode, which should clear it.  That's better
            # than having it grow forever...
            try:
                if self.encoding:
                    self.stream = codecs.open(self.baseFilename,
                                              'w+', self.encoding)
                else:
                    self.stream = open(self.baseFilename, 'w+')
            except Exception:
                pass


##############################################################################
class _LoggerStream(object):
    """An object responsible for redirecting stdout/stderr to a logger."""

    ###########################################################
    def __init__(self, logFn):
        """_LoggerStream constructor.

        @param  logFn   The logging function to call.
        """
        super(_LoggerStream, self).__init__()

        # Store log function as "write" directly.  This makes it so that the
        # logger can find the calling function...
        self.write = logFn


    ###########################################################
    def writelines(self, seq):
        """The writelines() function just wraps write().

        @param  seq  An iterable of strings to write.
        """
        for l in seq:
            self.write(l)


    ###########################################################
    def flush(self):
        """Flush the output string.

        After this function, all previous writes should take effect.
        """
        pass


##############################################################################
class EmptyLogger(object):
    """A logger that does nothing."""
    def __init__(self):
        self.handlers=[]
    def debug(self, msg, *args, **kwargs):
        pass
    def info(self, msg, *args, **kwargs):
        pass
    def warning(self, msg, *args, **kwargs):
        pass
    def warn(self, msg, *args, **kwargs):
        pass
    def error(self, msg, *args, **kwargs):
        pass
    def critical(self, msg, *args, **kwargs):
        pass
    def removeHandler(self, handler=None):
        pass


##############################################################################
class MsgChangeLogger(object):
    """Logger wrapper which allows the modification of the messag(es)."""
    def __init__(self, logger):
        """ Constructor.
        @param logger  The logger to wrap.
        """
        super(MsgChangeLogger, self).__init__()
        self.handlers=[]
        self._logger = logger
    def debug(self, msg, *args, **kwargs):
        self._logger.debug(self._changeMessage(msg), *args, **kwargs)
    def info(self, msg, *args, **kwargs):
        self._logger.info(self._changeMessage(msg), *args, **kwargs)
    def warning(self, msg, *args, **kwargs):
        self._logger.warning(self._changeMessage(msg), *args, **kwargs)
    def warn(self, msg, *args, **kwargs):
        self._logger.warn(self._changeMessage(msg), *args, **kwargs)
    def error(self, msg, *args, **kwargs):
        self._logger.error(self._changeMessage(msg), *args, **kwargs)
    def critical(self, msg, *args, **kwargs):
        self._logger.critical(self._changeMessage(msg), *args, **kwargs)
    def removeHandler(self, handler=None):
        self._logger.removeHandler(handler)
    def _changeMessage(self, msg):
        """ To change the message. Override when inheriting. Throughput here.
        @param msg  The original message.
        @return     Modified message.
        """
        return msg


##############################################################################
class MsgPrefixLogger(MsgChangeLogger):
    """Logger wrapper which puts a prefix on every message going through it."""
    def __init__(self, logger, prefix):
        """ Constructor.
        @param logger  The logger to wrap.
        """
        super(MsgPrefixLogger, self).__init__(logger)
        self._prefix = prefix
    def _changeMessage(self, msg):
        return self._prefix + msg


##############################################################################
def test_main(prefix=""):
    """OB_REDACT
       Contains various self-test code.

    @param  prefix  A prefix to append to all log entries; useful if you're
                    trying to debug what happens when multiple processes are
                    logging.
    """
    import random
    import time

    wantLoopTest = False   # Useful to try multiple processes...

    _kTestLog = "testLog"
    _kTestLogDir = "."
    _kTestLogPath = os.path.join(_kTestLogDir, _kTestLog)

    if not wantLoopTest:
        print prefix, "Deleting old log..."
        if os.path.exists(_kTestLogPath):
            os.unlink(_kTestLogPath)
        print prefix, "...deleted"

    print prefix, "Creating logger w/ no directory and logging error/warning/info..."
    print prefix, "...expect these to go to console."
    logger = getLogger(_kTestLog)
    logger.error(prefix + " test error")
    logger.warning(prefix + " test warning")
    logger.info(prefix + " test info")

    print prefix, "Setting '%s' as directory and enabling..." % (_kTestLogDir)
    print prefix, "...old logs should get flushed to log."
    logger.setLogDirectory(_kTestLogDir)
    logger.enableDiskLogging()

    print prefix, "A few more logs; should go to disk not console"
    logger.error(prefix + " test error, disk only")
    logger.warning(prefix + " test warning, disk only")
    logger.info(prefix + " test info, disk only")

    print prefix, "Disabling disk logging, then logging..."
    print prefix, "...these should go to console"
    logger.disableDiskLogging()
    logger.error(prefix + " test error 2")
    logger.warning(prefix + " test warning 2")
    logger.info(prefix + " test info 2")

    print prefix, "Reenabling disk logging; that should flush previous to disk."
    logger.enableDiskLogging()

    if wantLoopTest:
        print prefix, "Logging every ~.1 seconds for 30 seconds"
        startTime = time.time()
        i = 0
        while (time.time() - startTime < 30):
            logger.error("%s - %d - %.2f" % (prefix, i, time.time()))
            time.sleep(random.randint(5, 15) / 100.0)
            i += 1

    print prefix, "Redirecting stderr and stdout; no more prints after this!"
    logger.grabStdStreams()

    print >>sys.stderr, "Here's a print to stderr"
    print "Here's a print to stdout"

    logger.disableDiskLogging()
    print >>sys.stderr, "Disk logging is disabled, you should see this."
    print "...and this (stdout)"




##############################################################################
def _runTests():
    """OB_REDACT
       Run any self-tests.  This will be removed from obfuscated code.
    """
    import doctest
    test_main(*sys.argv[2:])
    doctest.testmod(verbose=True)


##############################################################################
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        _runTests()
    else:
        print "Try calling with 'test' as the argument."
