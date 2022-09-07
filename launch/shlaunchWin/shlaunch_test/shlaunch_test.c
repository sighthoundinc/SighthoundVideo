
#include <Windows.h>
#include <tchar.h>
#include <stdio.h>
#include <conio.h>

#include "shlaunch.h"

int main() {

    int launchCode;
    HANDLE exchangeMap = NULL;
    struct Exchange* exchange = NULL;

    exchangeMap = OpenFileMapping(
            FILE_MAP_WRITE | FILE_MAP_READ,
            FALSE,
            EXCHANGE_NAME);
    if (!exchangeMap) {
        printf("cannot open map, error %ld\n", GetLastError());
        goto cleanup;
    }

    exchange = (struct Exchange*)MapViewOfFile(
            exchangeMap,
            FILE_MAP_READ | FILE_MAP_WRITE, 
            0, 0, 0);
    if (!exchange) {
        printf("cannot get to exchange, error %ld\n", GetLastError());
        goto cleanup;
    }

    _tprintf(_T("size: %ld\npid: %ld\nstatus: 0x%08lx\nshutdown: 0x%08lx\nlaunch: 0x%08lx\ndatadir: '%ls'\n"),
        exchange->size,
        exchange->processId,
        exchange->status,
        exchange->shutdown,
        exchange->launch,
        exchange->dataDir);

    for(launchCode = rand();;launchCode++) {
        int c = _getch();
        if (' ' == c)
            break;
        if ('L' != c || 'K' != c)
            continue;
        _tprintf(_T("setting launch code %d ...\n"), launchCode);
        exchange->launch = (launchCode & 0xffff) +
                           ('K' == c ? LAUNCH_FLAG_KILL_FIRST : 0);
        _putts(_T("waiting for launch confirmation..."));
        while (exchange->launch != exchange->status) {
            Sleep(1);        
        }
        _putts(_T("launch confirmed\n"));
    }
    
cleanup:
    if (exchange)
        UnmapViewOfFile(exchange);
    if (exchangeMap)
        CloseHandle(exchangeMap);

    return 0;
}

