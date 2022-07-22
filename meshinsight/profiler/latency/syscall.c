#include <stdio.h>
#include <unistd.h>
#include <sys/syscall.h>

int main(void)
{
    for(;;){
        getpid();
    }
    return 0;
}