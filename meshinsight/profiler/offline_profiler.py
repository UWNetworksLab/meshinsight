import time
import os
import subprocess
import logging
import argparse
import multiprocessing
import pickle
import re
import statistics
from pathlib import Path
from sklearn.linear_model import LinearRegression
from kubernetes import client, config
import numpy as np

from config.parser import *

# Disable kubernetes python client logging
logging.getLogger('kubernetes').setLevel(logging.FATAL)
logging.getLogger('docker').setLevel(logging.FATAL)

# (http) envoy_inbound_read, envoy_inbound_userspace, envoy_inbound_write, 
# envoy_outbound_read, envoy_outbound_userspace, envoy_outbound_write
size_list = {"tcp":{100:[100, 241], 1000:[983, 1125], 2000:[1884, 2026], 3000:[2934, 3101], \
    4000:[3834, 4001]}, "http":{100:[100, 100, 252, 388, 388, 509], 1000:[983, 983, 1135, 1272, \
    1272, 1393], 2000:[1884, 1884, 2036, 2197, 2197, 2312], 3000:[2934, 2934, 3086, 3248, 3248, \
    3362], 4000:[3834, 3834, 3986, 4148, 4148, 4262]}}
funclatency_path = "latency/funclatency_filter.py"

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-c", "--cpu", action="store_true", help="run offline latency profiling")
    parser.add_argument("-l", "--latency", action="store_true", help="run offline cpu profiling")
    parser.add_argument("-d", "--duration",  type=int, default=30, help="default duration is 15s")
    return parser.parse_args()

def profile_syscall(duration):
    # Run getpid 
    subprocess.run("gcc ./latency/syscall.c -o ./latency/syscall", shell = True)
    proc = subprocess.Popen(["./latency/syscall"])
    pid = proc.pid

    # Get getpid latency
    cmd = ['python3', "./latency/funclatency.py", '-p '+str(pid), "c:getpid", '-d '+str(duration)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    result = result.stdout.decode("utf-8").split('\n')
    proc.terminate()
    syscall_overhead =  float(result[-4].split()[2])/1000.0

    return syscall_overhead

def wait_until_running(pod_name):
    config.load_kube_config()

    v1 = client.CoreV1Api()
    
    while True:
        ret = v1.list_namespaced_pod(namespace="default")
        status = [i.status.phase == "Running" for i in ret.items if "echo" in i.metadata.name]
        if False not in status:
            return 
        else:
            time.sleep(5)

def get_pid(process_name, allow_empty=False):
    result = subprocess.run(['pidof', process_name], stdout=subprocess.PIPE)
    pid = result.stdout.decode("utf-8")
    if not pid:
        if not allow_empty:
            raise Exception('%s process not found.'%process_name)
        else:
            pid = -1
    return int(pid)

def clean_up():
    # Clean up kubernetes deployments and wrks
    subprocess.run(["kubectl", "delete", "all", "--all"], stdout=subprocess.DEVNULL)

    wrk_pid = get_pid("wrk", allow_empty=True)
    if wrk_pid != -1:
        subprocess.run(["kill", "-9", str(wrk_pid)], stdout=subprocess.DEVNULL)

def run_funclatency(func, duration, pid, size=0, num_calls=0, lower_bound=0):

    if lower_bound != 0:
        cmd = ['python3', funclatency_path, '-p '+str(pid), func, '-d '+str(duration), '-w '+str(lower_bound)]
    elif num_calls == 0:
        # run funclatency by return value
        cmd = ['python3', funclatency_path, '-p '+str(pid), func, '-d '+str(duration), '-t '+str(size)]
    else:
        # run funclatency by number of calls when return value is not avaliable
        cmd = ['python3', funclatency_path, '-p '+str(pid), func, '-d '+str(duration), '-n '+str(num_calls)]

    logging.debug("Running cmd: " + " ".join(cmd))
    result = subprocess.run(cmd, stdout=subprocess.PIPE)

    result = result.stdout.decode("utf-8").split('\n')

    # extract avg latency, median latency and std from output
    avg_and_std = [0.0, 0.0, 0.0]     
    for r in result:
        if 'average' in r:
            avg_and_std[0] = round(float(r.split()[-1])/1000, 2)
        if 'median' in r:
            avg_and_std[1] = round(float(r.split()[-1])/1000, 2)
        if 'std' in r:
            avg_and_std[2] = round(float(r.split()[-1])/1000, 2)

    return avg_and_std

def run_tcp_proxy_latency_breakdown(app, envoy_pid, duration, num_calls, inbound_size, outbound_size, syscall):
    logging.debug("Running " + str(app) + " latency breakdown...")
    envoy_path = "/proc/PID/root/usr/local/bin/envoy".replace("PID", str(envoy_pid))
    breakdown = {}
    breakdown['envoy_ipc'] = run_funclatency('process_backlog', duration, envoy_pid, size=1, num_calls=num_calls)
    breakdown['envoy_read_outbound'] = run_funclatency('vfs_readv', duration, envoy_pid, size=outbound_size)
    breakdown['envoy_read_outbound'][0] += syscall
    breakdown['envoy_write_inbound'] = run_funclatency('vfs_writev', duration, envoy_pid, size=inbound_size) 
    breakdown['envoy_write_inbound'][0] += syscall
    breakdown['envoy_write_inbound'] = [i-j for i,j in zip(breakdown['envoy_write_inbound'], breakdown['envoy_ipc'])]
    breakdown['envoy_epoll'] = run_funclatency('ep_send_events_proc', duration, envoy_pid, num_calls=num_calls)
    breakdown['envoy_userspace'] = run_funclatency(envoy_path+':*onReadReady*', duration, envoy_pid, num_calls=num_calls) 
    return breakdown

def run_http_proxy_latency_breakdown(app, envoy_pid, duration, num_calls, size_list, syscall):
    logging.debug("Running " + str(app) + " latency breakdown...")
    envoy_path = "/proc/PID/root/usr/local/bin/envoy".replace("PID", str(envoy_pid))
    breakdown = {}
    breakdown['envoy_ipc'] = run_funclatency('process_backlog', duration, envoy_pid, size=1, num_calls=num_calls)
    breakdown['envoy_read_outbound'] = run_funclatency('vfs_readv', duration, envoy_pid, size=size_list[3])
    breakdown['envoy_read_outbound'][0] += syscall
    breakdown['envoy_write_inbound'] = run_funclatency('vfs_writev', duration, envoy_pid, size=size_list[2])
    breakdown['envoy_write_inbound'][0] += syscall
    breakdown['envoy_write_inbound'] = [i-j for i,j in zip(breakdown['envoy_write_inbound'], breakdown['envoy_ipc'])]
    
    breakdown['envoy_parsing_inbound'] = run_funclatency(envoy_path+':*http_parser_execute*', duration, envoy_pid, size=size_list[1])
    breakdown['envoy_parsing_outbound'] = run_funclatency(envoy_path+':*http_parser_execute*', duration, envoy_pid, size=size_list[4])
    breakdown['envoy_userspace'] = run_funclatency(envoy_path+':*onReadReady*', duration, envoy_pid, num_calls=num_calls, 
                            lower_bound=int(max(breakdown['envoy_parsing_inbound'][1], breakdown['envoy_parsing_outbound'][1])))
    breakdown['envoy_epoll'] = run_funclatency('ep_send_events_proc', duration, envoy_pid, num_calls=num_calls) 
    return breakdown

def run_app_latency_breakdown(app, app_pid, duration, inbound_size, outbound_size, syscall):
    inbound_size = min(inbound_size, 4096)
    outbound_size = min(outbound_size, 4096)
    logging.debug("Running " + str(app) + " latency breakdown...")
    breakdown = {}
    breakdown['app_ipc'] = run_funclatency('process_backlog', duration, app_pid, size=1)
    breakdown['app_read_inbound'] = run_funclatency('vfs_read', duration, app_pid, size=inbound_size)
    breakdown['app_read_inbound'][0] += syscall
    breakdown['app_write_outbound'] = run_funclatency('vfs_write', duration, app_pid, size=outbound_size)
    breakdown['app_write_outbound'][0] += syscall
    breakdown['app_write_outbound'] = [i-j for i,j in zip(breakdown['app_write_outbound'], breakdown['app_ipc'])]
    return breakdown

def run_latency_experiment(protocol, request_sizes, args, syscall_overhead):
    # Deploy echo server
    subprocess.run("kubectl label namespace default istio-injection=enabled", shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.debug("Deploying echo server for %s proxy...", protocol)
    subprocess.run(["kubectl", "apply", "-f", "./benchmark/echo_server/echo-server-"+protocol+"-latency.yaml"], stdout=subprocess.DEVNULL)
    
    # Waited until the echo server is running
    logging.debug("Waiting all pods to be ready ...")
    wait_until_running("echo")
    logging.debug("All echo server pod running...")

    time.sleep(15)
    result = {}

    for request_size in request_sizes:
        logging.debug("Running latency experiment for %s proxy with request size %d bytes", protocol, request_size)
        result[request_size] = {}
        
        # Run the wrk workload generator
        cmd = ["./wrk/wrk", "-t 1", "-c 1", "-s ./benchmark/wrk_scripts/echo_workload/request_b/echo_workload_size.lua".replace("size", str(request_size)), "http://10.96.88.88:80", "-d 400"]
        proc = subprocess.Popen(" ".join(cmd), shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE) 
        logging.debug("Running wrk as " + " ".join(cmd))

        # Get Application and Envoy process info
        wrk_pid = get_pid("wrk")
        envoy_pid = get_pid("envoy")
        echo_pid = get_pid("echo-server")
        logging.debug("wrk pid: %d", wrk_pid)
        logging.debug("Applcation pid: %d", echo_pid)
        logging.debug("Envoy proxy pid: %d", envoy_pid)

        logging.debug("Starting breakdown measurement...")

        if protocol == "tcp":
            proxy_breakdown = run_tcp_proxy_latency_breakdown("echo server", envoy_pid, args.duration, 0, size_list[protocol][request_size][0], size_list[protocol][request_size][1], syscall_overhead)
            app_breakdown = run_app_latency_breakdown("echo server", echo_pid, args.duration, size_list[protocol][request_size][0], size_list[protocol][request_size][1], syscall_overhead)
        else:
            proxy_breakdown = run_http_proxy_latency_breakdown("echo server", envoy_pid, args.duration, 0, size_list[protocol][request_size], syscall_overhead)
            app_breakdown = run_app_latency_breakdown("echo server", echo_pid, args.duration, size_list[protocol][request_size][2], size_list[protocol][request_size][3], syscall_overhead)
        
        total_overhead_breakdown = {}
        total_overhead_breakdown['read'] = app_breakdown["app_read_inbound"][0]+proxy_breakdown["envoy_read_outbound"][0]
        total_overhead_breakdown['write'] = app_breakdown["app_write_outbound"][0]+proxy_breakdown["envoy_write_inbound"][0]
        total_overhead_breakdown['ipc'] = app_breakdown["app_ipc"][0]+proxy_breakdown["envoy_ipc"][0]
        total_overhead_breakdown['epoll'] = proxy_breakdown["envoy_epoll"][0]*2

        if protocol == "tcp":
            total_overhead_breakdown['others(proxy)'] = proxy_breakdown["envoy_userspace"][0]*2
        else:
            total_overhead_breakdown['parsing(proxy)'] = proxy_breakdown["envoy_parsing_inbound"][0]+proxy_breakdown["envoy_parsing_outbound"][0]
            total_overhead_breakdown['others(proxy)'] = proxy_breakdown["envoy_userspace"][0]*2 - total_overhead_breakdown['parsing(proxy)']

        result[request_size] = total_overhead_breakdown

        # Kill the wrk process
        subprocess.run(["kill", "-9", str(wrk_pid)], stdout=subprocess.DEVNULL)
        time.sleep(15)
        

    # Clean up deployment
    logging.debug("Deleting echo server deployment ...")
    subprocess.run(["kubectl", "delete", "deployments", "echo"], stdout=subprocess.DEVNULL)
    time.sleep(15)

    return result

def linear_regression(label, input_data):
    """
    input_data: List[Tuple(x, y)]
    """
    X = np.array([[e[0]] for e in input_data])
    y = np.array([e[1] for e in input_data])

    reg = LinearRegression().fit(X, y)
    # logging.debug(label+ " reg score: %.2f", reg.score(X, y))

    return reg

def build_model(profile, request_sizes, protocol):
    models = {}

    read_data = [(i, profile[i]["read"]) for i in request_sizes]
    models['read_reg'] = linear_regression("read", read_data)

    write_data =  [(i, profile[i]["write"]) for i in request_sizes]
    models['write_reg']  = linear_regression("write", write_data)

    epoll_data = [(i, profile[i]["epoll"]) for i in request_sizes]
    models['epoll_reg']  = linear_regression("epoll", epoll_data)

    ipc_data = [(i, profile[i]["ipc"]) for i in request_sizes]
    models['ipc_reg']  = linear_regression("ipc", ipc_data)

    envoy_data = [(i, profile[i]["others(proxy)"]) for i in request_sizes] 
    models['envoy_reg']  = linear_regression("others(proxy)", envoy_data)

    if protocol != "tcp":
        parsing_data = [(i, profile[i]["parsing(proxy)"]) for i in request_sizes] 
        models['parsing_reg']  = linear_regression("parsing(proxy)", parsing_data)
        
    return models

# Get the CPU usage (in  virtual cores) using mpstat
def get_virtual_cores(core_count):
    logging.debug("Running mpstat...")
    cpu_util = []
    for _ in range(5):
        cmd = ['mpstat', '1', '20']
        # print("Running cmd: " + " ".join(cmd))
        # output = {}
        result = subprocess.run(cmd, stdout=subprocess.PIPE)
        result_average = result.stdout.decode("utf-8").split('\n')[-2].split()
        overall = 100.00 - float(result_average[-1])
        cpu_util.append(overall)

    virtual_cores = statistics.mean(cpu_util)*core_count/100
    return virtual_cores   

# Generate Flamegraph with profile
def generate_flamegraph(option="perf"):
    logging.debug("Generating Flamegraph...")

    # With BPF profile
    if option == "ebpf":
        cmd1 = ['python3', './cpu/profile.py', '-F 99', '-f', '45']
        with open("./result/out.profile-folded", "wb") as outfile1:
            subprocess.run(cmd1, stdout=outfile1)

        cmd2 = ['./cpu/flamegraph.pl', './result/out.profile-folded']
        with open("./result/profile.svg", "wb") as outfile2:
            subprocess.run(cmd2, stdout=outfile2)
    elif option == "perf":
        # With perf
        cmd1 = ['perf record -F 99 -a -g -- sleep 45']
        subprocess.run(cmd1, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        cmd2 = ["perf script | ./cpu/stackcollapse-perf.pl | ./cpu/flamegraph.pl > ./result/profile.svg"]
        subprocess.run(cmd2, shell=True)

# Get the X axis range of TARGET
def get_target_xrange(app_name):
    with open("./result/profile.svg", 'r') as fp:
        lines = fp.readlines()

    target = ">"+app_name+" ("
    for line in lines:
        if target in line:
            # print(line)
            temp = [l for l in line.split() if 'x' in l or 'width' in l]
            x1 = float(re.findall(r"\d+\.\d+", temp[0])[0])
            x2 = float(re.findall(r"\d+\.\d+", temp[1])[0]) + x1

    return (x1, x2)

def get_target_cpu_percentage(target, xranges=None, app_syscall=False):
    with open("./result/profile.svg", 'r') as fp:
        lines = fp.readlines()

    # Get the swapper thread
    idle_percentage = 0.0
    for line in lines:
        if ">swapper (" in line:
            l = re.findall(r"\d+\.\d+", line)
            idle_percentage += float(l[0])

    sum = 0.0
    for line in lines:
        if target in line:
            # print(line)
            if xranges:
                # We are only interested in function that is within the xranges
                temp = [l for l in line.split() if 'x' in l or 'width' in l]
                x = float(re.findall(r"\d+\.\d+", temp[0])[0])
                if x < xranges[0] or x > xranges[1]:
                    continue
                # if app_syscall:
                #     line = find_syscall_bottom(xranges, lines)

            l = re.findall(r"\d+\.\d+", line)
            sum += float(l[0])

    # Scale by idle thread
    # print(sum)
    # print(idle_percentage)
    # sum = sum/(1.0-idle_percentage/100)

    return sum

def get_cpu_breakdown(virtual_cores, proxy, proxy_xranges, app, app_xranges):
    logging.debug("Caculating CPU breakdown...")
    breakdown = {}

    # Get Proxy CPU breakdown
    if proxy != "none":
        # Envoy's read
        # breakdown['envoy_read'] = virtual_cores*get_target_cpu_percentage(">vfs_readv (", proxy_xranges)*0.01
        breakdown['envoy_read'] = virtual_cores*get_target_cpu_percentage(">Envoy::Network::IoSocketHandleImpl::readv", proxy_xranges)*0.01

        # Envoy's write
        breakdown['envoy_process_backlog'] = virtual_cores*get_target_cpu_percentage(">process_backlog (", proxy_xranges)*0.01
        breakdown['envoy_write'] = virtual_cores*get_target_cpu_percentage(">Envoy::Network::IoSocketHandleImpl::writev (", proxy_xranges)*0.01 -  breakdown['envoy_process_backlog']
        
        # Envoy's loopback
        breakdown['envoy_br_handle_frame'] = virtual_cores*get_target_cpu_percentage(">br_handle_frame (", proxy_xranges)*0.01
        breakdown['envoy_loopback'] = breakdown['envoy_process_backlog'] - breakdown['envoy_br_handle_frame']

        # Envoy' epoll
        breakdown['envoy_epoll'] = virtual_cores*get_target_cpu_percentage(">do_epoll_wait (", proxy_xranges)*0.01

        # Envoy's userspace
        breakdown['envoy_userspace'] = virtual_cores*get_target_cpu_percentage(">wrk:worker_0 (")*0.01+\
                                            virtual_cores*get_target_cpu_percentage(">wrk:worker_1 (")*0.01
        breakdown['envoy_userspace'] = breakdown['envoy_userspace']-(breakdown['envoy_read']+breakdown['envoy_write']+
                                            breakdown['envoy_epoll'])+breakdown['envoy_loopback'] 
    
    if proxy == 'http' or proxy =='grpc':
        breakdown['envoy_parsing'] = virtual_cores*get_target_cpu_percentage(">Envoy::Network::FilterManagerImpl::onContinueReading (")*0.01
    


    # Get application CPU breakdown
    if app != "none":
        # App's read
        breakdown['app_read'] = virtual_cores*get_target_cpu_percentage(">vfs_read (", app_xranges, app_syscall=True)*0.01

        # App's loopback
        breakdown['app_loopback'] = virtual_cores*get_target_cpu_percentage(">process_backlog (", app_xranges)*0.01

        # App's write
        breakdown['app_write'] = virtual_cores*get_target_cpu_percentage(">vfs_write (", app_xranges, app_syscall=True)*0.01 - breakdown['app_loopback']

        # App's userspace
        breakdown['app_userspace'] = virtual_cores*get_target_cpu_percentage(">"+app+" (")*0.01-\
                                        breakdown['app_read']-breakdown['app_write']-breakdown['app_loopback']

    # Get other background processes CPU usage
    breakdown['others'] = virtual_cores-sum(breakdown.values())


    if proxy == 'http' or proxy =='grpc':
        breakdown['others'] += breakdown['envoy_parsing']
    
    for k, v in breakdown.items():
        breakdown[k] = round(v, 4)

    return breakdown

def parse_cpu_breakdown(breakdown, scale, protocol):
    result = {}

    result['read'] = breakdown['envoy_read']/2 + breakdown['app_read']
    result['write'] = breakdown['envoy_write']/2 + breakdown['app_write']
    result['ipc'] = breakdown['envoy_loopback'] + breakdown['app_loopback']
    result['epoll'] = breakdown['envoy_epoll']
    result['app_userspace'] = breakdown['app_userspace']
    if protocol != "tcp":
        result["parsing(proxy)"] = breakdown['envoy_parsing']
    result["others(proxy)"] = breakdown['envoy_userspace']
    result['others'] = breakdown['others']

    for k, v in result.items():
        result[k] = round(v/scale, 6)

    return result

def run_cpu_experiment(protocol, request_sizes, args):
    # Create directory to store temp files
    Path("./result").mkdir(parents=True, exist_ok=True)

    # Get the number of CPUs
    core_count = multiprocessing.cpu_count()
    logging.debug("Detected %d cores", core_count)

    # Deploy echo server
    subprocess.run("kubectl label namespace default istio-injection=enabled", shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.debug("Deploying echo server ...")
    subprocess.run(["kubectl", "apply", "-f", "./benchmark/echo_server/echo-server-"+protocol+"-cpu.yaml"], stdout=subprocess.DEVNULL)
    time.sleep(15)

    # Waited until the echo server is running
    logging.debug("Waiting the pod ...")
    wait_until_running("echo")
    logging.debug("Echo server pod running...")
    time.sleep(15)

    # Find maximum rate for the largest request
    logging.debug("Running wrk2 to get the target service rate ...")
    cmd = ["./wrk2/wrk", "-t 2", "-c 100", "-s ./benchmark/wrk_scripts/echo_workload/request_b/echo_workload_size.lua".replace("size", str(request_sizes[-1])), "http://10.96.88.88:80", "-d 45", "-R 10000000"]
    result = subprocess.run(" ".join(cmd), shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode("utf-8").split('\n')
    rate = int(float([r for r in result if "Requests/sec" in r][0].split()[1])*0.9)
    logging.debug("Done, the target service rate is %d requests/second ...", rate)

    result = {}

    for request_size in request_sizes:
        logging.debug("Running CPU experiment for %s proxy with request size %d bytes", protocol, request_size)
        result[request_size] = {}
        
        # Run the wrk workload generator
        cmd = ["./wrk2/wrk", "-t 2", "-c 100", "-s ./benchmark/wrk_scripts/echo_workload/request_b/echo_workload_size.lua".replace("size", str(request_size)), "http://10.96.88.88:80", "-d 400", "-R "+str(rate)]
        subprocess.Popen(" ".join(cmd), shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE) 
        logging.debug("Running wrk2 as " + " ".join(cmd))
        wrk_pid = get_pid("wrk")

        # Get CPU usage in terms of virtual cores
        logging.debug("Running mpstat to get CPU usage...")
        virtual_cores = get_virtual_cores(core_count)
        logging.debug("%.2f virtual cores used ...", virtual_cores)

        # Generate FlameGraph and do some preprocessing
        logging.debug("Running perf to get CPU breakdown...")
        generate_flamegraph()
        app_xranges = get_target_xrange("echo-server")
        proxy_xranges = (get_target_xrange("wrk:worker_0")[0], get_target_xrange("wrk:worker_1")[1]) # wrk1 and wrk2 are always next to each other
        breakdown = get_cpu_breakdown(core_count, protocol, proxy_xranges, "echo-server", app_xranges)
        result[request_size] = parse_cpu_breakdown(breakdown, rate/1000, protocol)

        # Kill the wrk process
        subprocess.run(["kill", "-9", str(wrk_pid)], stdout=subprocess.DEVNULL)
        subprocess.run(["rm", "./result/profile.svg"], stdout=subprocess.DEVNULL)
        time.sleep(20)

    # Clean up deployment
    logging.debug("Deleting echo server deployment ...")
    subprocess.run(["kubectl", "delete", "deployments", "echo"], stdout=subprocess.DEVNULL)
    time.sleep(20)
    
    return result

def get_platform_info():
    # Get CPU Info
    cpu_info = subprocess.run("cat /proc/cpuinfo | grep 'model name' | uniq", \
            shell=True, stdout=subprocess.PIPE, check=True).stdout.decode("utf-8").split(": ")[1].rstrip('\n') 

    # Get Kernel Version
    kernel_info = subprocess.run("uname -r", \
            shell=True, stdout=subprocess.PIPE, check=True).stdout.decode("utf-8").rstrip('\n') 

    # Get Kubernetes verion
    k8s_info = re.split(":|\n", subprocess.run("kubectl version --client --short", shell=True, \
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True).stdout.decode("utf-8"))[1]

    # Get Envoy Version 
    istio_info =  re.split(": |\n", subprocess.run("$HOME/istio-1.14.1/bin/istioctl version", \
            shell=True, stdout=subprocess.PIPE, check=True).stdout.decode("utf-8"))[1]

    return ("CPU: "+cpu_info, "Kernel: "+kernel_info, "Kubernetes: " + k8s_info, "Istio: v"+istio_info)

if __name__ == '__main__':

    if not os.geteuid() == 0:
        raise Exception('This script should be run with "sudo".')

    try:
        MESHINSIGHT_DIR = os.environ['MESHINSIGHT_DIR']
    except:
        raise ValueError('$MESHINSIGHT_DIR env variabe is not set. Example: "/home/username/meshinsight/".')

    os.chdir(os.path.join(MESHINSIGHT_DIR, "meshinsight/profiler"))

    # cfg = get_config("config/base.yml")
    # cfg.merge_from_file("config/istio.yml")
    # cfg.update_path(MESHINSIGHT_DIR)

    start = time.time()
    args = parse_args()

    if args.verbose:
        logging.basicConfig(format='%(asctime)s | %(levelname)8s | %(message)s', datefmt='%d-%b-%y %H:%M:%S', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(asctime)s | %(levelname)8s | %(message)s', datefmt='%d-%b-%y %H:%M:%S', level=logging.INFO)

    # Get Platform info
    platform_config = get_platform_info()
    logging.debug("Platform info: "+str(platform_config))
    profile = {platform_config: {}}
    clean_up()

    # TODO(xz): Add support for grpc proxy
    protocols = ["tcp", "http"]
    request_sizes = [100, 1000, 2000, 3000, 4000]
    
    if args.latency:
        logging.info("Starting latency profiling!")
        # Profile syscall overheads
        logging.debug("Profiling system call overhead")
        syscall_overhead  = profile_syscall(args.duration)
        logging.debug("System call overhead is %.4f us", syscall_overhead)
        profile[platform_config]["latency"] = {}
        for p in protocols:
            # Run profiling
            latency_profile = run_latency_experiment(p, request_sizes, args, syscall_overhead)
            
            # Build latency prediction model via linear regression
            latency_models = build_model(latency_profile, request_sizes, p)
            profile[platform_config]["latency"][p] = latency_models
        logging.info("Latency profiling finished!")

    if args.cpu:
        logging.info("Starting CPU profiling!")
        profile[platform_config]["cpu"] = {}
        for p in protocols: 
            cpu_profile = run_cpu_experiment(p, request_sizes, args)
            
            # Build cpu prediction model via linear regression
            cpu_models = build_model(cpu_profile, request_sizes, p)
            profile[platform_config]["cpu"][p] = cpu_models
        logging.info("CPU profiling finished!")
    
    # Save profile results
    Path(os.path.join(MESHINSIGHT_DIR, "meshinsight/profiles")).mkdir(parents=True, exist_ok=True)
    with open(os.path.join(MESHINSIGHT_DIR, "meshinsight/profiles/profile.pkl"), "wb") as fout:
        pickle.dump(profile, fout)
    logging.info("Profile saved to %s", os.path.join(MESHINSIGHT_DIR, "meshinsight/profiles/profile.pkl"))

    clean_up()
    end = time.time()
    logging.info("Profile finished, took %.2f seconds", end-start)