
#include <stdio.h>
#include <wchar.h>
#include <inttypes.h>

// Test application to operate on the shared memory, the exchange between the
// front-end and the service ...

///////////////////////////////////////////////////////////////////////////////

void*    launch_open    ();
int32_t  launch_close   (void* handle);
int32_t  launch_do      (void* handle, int signal);
uint32_t launch_pid     (void* handle);
int32_t  launch_status  (void* handle);
wchar_t* launch_datadir (void* handle);
int32_t  launch_shutdown(void* handle);

///////////////////////////////////////////////////////////////////////////////

int main(int argc, char** argv)
{
    int err, c, l;
    void* h;
    wchar_t* dataDir;
    
    h = launch_open();
    if (!h) {
        puts("cannot open");
        goto fail;
    }
    printf("process ID: %d\nstatus: %d\n", launch_pid(h), launch_status(h));
    dataDir = launch_datadir(h);
    wprintf(L"datadir: %S\n", dataDir);
    puts("");
    puts("e[x]it, [k]ill, sh[u]tdown, [s]tart>");
    l = 0x200;
    while ('x' != (c = getchar())) {
        int cmd = 0;
        if ('s' == c) {
            cmd |= l++;
        }
        else if ('k' == c) {
            cmd |= 0x10000;
        }
        else if ('u' == c) {
            err = launch_shutdown(h);
            printf("launch_shutdown() returned %d\n", err);
            continue;
        }
        else {
            continue;
        }
        cmd = launch_do(h, cmd);
        printf("launch_do() returned x%08x\n", cmd);
    }
    err = launch_close(h);
    if (err) {
        printf("cannot close, error %d\n", err);
        goto fail;
    }
    puts("DONE.");

fail:
    
    return 0;
}