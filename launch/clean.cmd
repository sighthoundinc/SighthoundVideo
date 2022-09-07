@echo off

REM ---------------------------------------------------------------------------
REM  Call this file in administrator mode, after you did some development with
REM  Visual Studio run as admin and ended up with files and folders which can
REM  not be deleted due to missing permissions in a regular account.
REM ---------------------------------------------------------------------------

cd "%~d0%~p0"

rmdir shlaunchWin\Debug		/s /q
rmdir shlaunchWin\Release	/s /q
rmdir shlaunchWin\ipch		/s /q

rmdir shlaunchWin\shlaunch\Debug   	/s /q
rmdir shlaunchWin\shlaunch\Release 	/s /q
rmdir shlaunchWin\shlaunch\ipch		/s /q

rmdir shlaunchWin\shlaunch_test\Debug   /s /q
rmdir shlaunchWin\shlaunch_test\Release	/s /q
rmdir shlaunchWin\shlaunch_test\ipch	/s /q

del shlaunchWin\*.sdf	/s /q
del shlaunchWin\*.suo	/s /q
del shlaunchWin\*.users	/s /q

del shlaunch.exe /q
