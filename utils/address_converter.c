#include <stdio.h>
#include <arpa/inet.h>

int main() {
  unsigned int a1 = inet_addr("127.0.0.6");
  printf("0x%x\n", a1);
}
