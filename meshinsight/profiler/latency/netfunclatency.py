from __future__ import print_function
from bcc import BPF
from time import sleep, strftime
import argparse
import signal
import numpy as np


examples = """examples:
    sudo python3 netfunclatency.py 
"""
parser = argparse.ArgumentParser(
    description="Time network poll function and print latency as a histogram",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=examples)
parser.add_argument("-p", "--pid", type=int,
    help="trace this PID only")
parser.add_argument("-t", "--ret", type=int, default=-1,
    help="filter the function by return value")
parser.add_argument("-v", "--verbose", action="store_true",
    help="print the BPF program (for debugging purposes)")
parser.add_argument("-i", "--interval", type=int,
    help="summary interval, in seconds")
parser.add_argument("-T", "--timestamp", action="store_true",
    help="include timestamp on output")
parser.add_argument("-d", "--duration", type=int,
    help="total duration of trace, in seconds")
parser.add_argument("pattern",
    help="search expression for functions")
args = parser.parse_args()
if args.duration and not args.interval:
    args.interval = args.duration
if not args.interval:
    args.interval = 99999999

bpf_text= """
#include <uapi/linux/ptrace.h>
#include <uapi/linux/ip.h>
#include <linux/skbuff.h>
#include <linux/inet.h>

// Use unsigned int a1 = inet_addr("127.0.0.6"); and printf("0x%x", a1); to convert IP addr
#define LOOPBACK_IP 0x600007f

BPF_HISTOGRAM(latency_table, u64, 100000); // 100us 
BPF_HASH(start, u32);

int __netif_receive_skb_entry(struct pt_regs *ctx, struct sk_buff *skb) {
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 pid = pid_tgid;
    u32 tgid = pid_tgid >> 32;
    u64 ts = bpf_ktime_get_ns();

    FILTER

    u32 saddr = ((struct iphdr *)(skb->head + skb->network_header))->saddr;
    u32 daddr = ((struct iphdr *)(skb->head + skb->network_header))->daddr;

    // Filter by src/dst ip address
    if ( saddr != LOOPBACK_IP && daddr != LOOPBACK_IP ) {
        return 0;
    }
    
    start.update(&pid, &ts);

    return 0;
}


int __netif_receive_skb_return(struct pt_regs *ctx) {
    u64 *tsp, delta;
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 pid = pid_tgid;
    u32 tgid = pid_tgid >> 32;

    // calculate delta time

    tsp = start.lookup(&pid);
    if (tsp == 0) {
        return 0;   // missed start
    }
    delta = bpf_ktime_get_ns() - *tsp;
    start.delete(&pid);

    latency_table.atomic_increment((int)delta);

    return 0;
}
"""

if args.pid:
    bpf_text = bpf_text.replace('FILTER',
        'if (tgid != %d) { return 0; }' % args.pid)
else:
    bpf_text = bpf_text.replace('FILTER', '')

if args.verbose:
    print(bpf_text)

def signal_ignore(signal, frame):
    print()

# load BPF program
b = BPF(text=bpf_text)
# attach probes
b.attach_kprobe(event="__netif_receive_skb", fn_name="__netif_receive_skb_entry")
b.attach_kretprobe(event_re="__netif_receive_skb", fn_name="__netif_receive_skb_return")

matched = b.num_open_kprobes()
if matched == 0:
    print("0 functions matched by __netif_receive_skb Exiting.")
    exit()


print("Tracing %d functions for \"%s\"... Hit Ctrl-C to end." %
    (matched / 2, "__netif_receive_skb"))

seconds = 0
latency = b.get_table("latency_table")
while (1):
    try:
        sleep(args.interval)
        seconds += args.interval
    except KeyboardInterrupt:
        exiting = 1
        # as cleanup can take many seconds, trap Ctrl-C:
        signal.signal(signal.SIGINT, signal_ignore)
    if args.duration and seconds >= args.duration:
        exiting = 1

    print()
    if args.timestamp:
        print("%-8s\n" % strftime("%H:%M:%S"), end="")

    # Get the latency distribution
    latency_hist = [0] * 1024000 # nanosecond 
    for k, v in latency.items():
        if k.value >= 1024000:
            continue
        latency_hist[k.value] = v.value

    latency_vals = []
    for i, d in enumerate(latency_hist): # i is the latency and d is the number of times that latency appears in the trace
        for _ in range(0, d):
            latency_vals.append(i)

    print("Collected "+str(len(latency_vals))+" function latencies")
    print("Latency average is "+str(np.mean(np.array(latency_vals))))
    print("Latency median is "+str(np.median(np.array(latency_vals))))
    print("Latency std is "+str(np.std(np.array(latency_vals))))

    # latency.clear()

    if exiting:
        print("Detaching...")
        exit()