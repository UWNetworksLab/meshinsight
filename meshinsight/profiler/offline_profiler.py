import time
import os
import subprocess
import logging
import argparse
import multiprocessing
import pickle
import re
import sys
import statistics
from pathlib import Path
from sklearn.linear_model import LinearRegression
from kubernetes import client, config
import numpy as np
from rich.logging import RichHandler

from config.parser import *
from config.config import *

# Disable kubernetes python client logging
logging.getLogger('kubernetes').setLevel(logging.FATAL)
logging.getLogger('docker').setLevel(logging.FATAL)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-c", "--cpu", action="store_true", help="run offline latency profiling")
    parser.add_argument("-l", "--latency", action="store_true", help="run offline cpu profiling")
    parser.add_argument("-d", "--duration",  type=int, default=30, help="default duration is 15s")
    return parser.parse_args()

def profile_syscall(duration):
    # Run getpid 
    syscall_path = cfg.PATH.SYSCALL_PATH
    syscall_cmd = cfg.PATH.SYSCALL_PATH.replace(".c", "")
    subprocess.run("gcc "+syscall_path+" -o "+syscall_cmd, shell = True)
    proc = subprocess.Popen([syscall_cmd])
    pid = proc.pid

    # Get getpid latency
    cmd = ['python3', cfg.PATH.FUNCLATENCY_PATH, '-p '+str(pid), "c:getpid", '-d '+str(duration)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    result = result.stdout.decode("utf-8").split('\n')
    proc.terminate()
    syscall_overhead =  float(result[-4].split()[2])/1000.0

    return syscall_overhead

def wait_until_running(pod_name):
    config.load_kube_config()

    v1 = client.CoreV1Api()
    flag = False

    # Find the status of echo server and wait for it.
    while True:
        ret = v1.list_namespaced_pod(namespace="default")
        status = [i.status.phase == "Running" for i in ret.items if "echo" in i.metadata.name]
        if False not in status:
            return 
        else:
            flag = True
            time.sleep(5)

    # If we can not find echo server status, the yaml files are probably wrong
    if not flag:
        raise Exception("Error: echo server deployment not found. Please check the deployment yaml files.")
    
def get_pid(process_name, allow_empty=False):
    # Sometimes there are multiple envoy processes 
    if process_name == "envoy":
        result = subprocess.run("ps -auxfww | grep envoy", shell=True, stdout=subprocess.PIPE)
        result = result.stdout.decode("utf-8").split("\n")
        if len(result) < 3:
            raise Exception('%s process not found.'%process_name)
        pid = [i for i in result if "--concurrency" in i][0].split()[1]
    else:
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

    time.sleep(20)

def run_funclatency(func, duration, pid, size=0, num_calls=0, lower_bound=0):

    if lower_bound != 0:
        cmd = ['python3', cfg.PATH.FUNCLATENCY_FILTER_PATH, '-p '+str(pid), func, '-d '+str(duration), '-w '+str(lower_bound)]
    elif num_calls == 0:
        # run funclatency by return value
        # cmd = ['python3', cfg.PATH.FUNCLATENCY_FILTER_PATH, '-p '+str(pid), func, '-d '+str(duration), '-t '+str(size)]
        cmd = ['python3', cfg.PATH.FUNCLATENCY_FILTER_PATH, '-p '+str(pid), func, '-d '+str(duration)]
    else:
        # run funclatency by number of calls when return value is not avaliable
        cmd = ['python3', cfg.PATH.FUNCLATENCY_FILTER_PATH, '-p '+str(pid), func, '-d '+str(duration), '-n '+str(num_calls)]

    logging.debug("Running cmd: " + " ".join(cmd))
    # result = subprocess.run(cmd, stdout=subprocess.PIPE)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

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
    breakdown['envoy_ipc'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.TCP.IPC, duration, envoy_pid, size=1, num_calls=num_calls)
    breakdown['envoy_read_outbound'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.TCP.READ, duration, envoy_pid, size=outbound_size)
    breakdown['envoy_read_outbound'][0] += syscall
    breakdown['envoy_write_inbound'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.TCP.WRITE, duration, envoy_pid, size=inbound_size) 
    breakdown['envoy_write_inbound'][0] += syscall
    breakdown['envoy_write_inbound'] = [i-j for i,j in zip(breakdown['envoy_write_inbound'], breakdown['envoy_ipc'])]
    breakdown['envoy_epoll'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.TCP.EPOLL, duration, envoy_pid, num_calls=num_calls)
    breakdown['envoy_userspace'] = run_funclatency(envoy_path+cfg.ISTIO.LATENCY.PROXY.TCP.USER, duration, envoy_pid, num_calls=num_calls) 
    return breakdown

def run_http_proxy_latency_breakdown(app, envoy_pid, duration, num_calls, size_list, syscall):
    logging.debug("Running " + str(app) + " latency breakdown...")
    envoy_path = "/proc/PID/root/usr/local/bin/envoy".replace("PID", str(envoy_pid))
    breakdown = {}
    breakdown['envoy_ipc'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.HTTP.IPC, duration, envoy_pid, size=1, num_calls=num_calls)
    breakdown['envoy_read_outbound'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.HTTP.READ, duration, envoy_pid, size=size_list[3])
    breakdown['envoy_read_outbound'][0] += syscall
    breakdown['envoy_write_inbound'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.HTTP.WRITE, duration, envoy_pid, size=size_list[2])
    breakdown['envoy_write_inbound'][0] += syscall
    breakdown['envoy_write_inbound'] = [i-j for i,j in zip(breakdown['envoy_write_inbound'], breakdown['envoy_ipc'])]
    
    breakdown['envoy_parsing_inbound'] = run_funclatency(envoy_path+cfg.ISTIO.LATENCY.PROXY.HTTP.PARSE, duration, envoy_pid, size=size_list[1])
    breakdown['envoy_parsing_outbound'] = run_funclatency(envoy_path+cfg.ISTIO.LATENCY.PROXY.HTTP.PARSE, duration, envoy_pid, size=size_list[4])
    breakdown['envoy_userspace'] = run_funclatency(envoy_path+cfg.ISTIO.LATENCY.PROXY.HTTP.USER, duration, envoy_pid, num_calls=num_calls, 
                            lower_bound=int(max(breakdown['envoy_parsing_inbound'][1], breakdown['envoy_parsing_outbound'][1])))
    breakdown['envoy_epoll'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.HTTP.EPOLL, duration, envoy_pid, num_calls=num_calls) 
    return breakdown

def run_grpc_proxy_latency_breakdown(app, envoy_pid, duration, num_calls, size_list, syscall):
    logging.debug("Running " + str(app) + " latency breakdown...")
    envoy_path = "/proc/PID/root/usr/local/bin/envoy".replace("PID", str(envoy_pid))
    breakdown = {}
    breakdown['envoy_ipc'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.GRPC.IPC, duration, envoy_pid, size=1, num_calls=num_calls)
    breakdown['envoy_read_outbound'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.GRPC.READ, duration, envoy_pid, size=size_list[3])
    breakdown['envoy_read_outbound'][0] += syscall
    breakdown['envoy_write_inbound'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.GRPC.WRITE, duration, envoy_pid, size=size_list[2])
    breakdown['envoy_write_inbound'][0] += syscall
    breakdown['envoy_write_inbound'] = [i-j for i,j in zip(breakdown['envoy_write_inbound'], breakdown['envoy_ipc'])]
    
    breakdown['envoy_parsing_inbound'] = run_funclatency(envoy_path+cfg.ISTIO.LATENCY.PROXY.GRPC.PARSE, duration, envoy_pid, size=size_list[1])
    breakdown['envoy_parsing_outbound'] = run_funclatency(envoy_path+cfg.ISTIO.LATENCY.PROXY.GRPC.PARSE, duration, envoy_pid, size=size_list[4])
    breakdown['envoy_userspace'] = run_funclatency(envoy_path+cfg.ISTIO.LATENCY.PROXY.GRPC.USER, duration, envoy_pid, num_calls=num_calls, 
                            lower_bound=int(max(breakdown['envoy_parsing_inbound'][1], breakdown['envoy_parsing_outbound'][1])))
    breakdown['envoy_epoll'] = run_funclatency(cfg.ISTIO.LATENCY.PROXY.GRPC.EPOLL, duration, envoy_pid, num_calls=num_calls) 
    return breakdown

def run_app_latency_breakdown(app, app_pid, duration, inbound_size, outbound_size, syscall):
    inbound_size = min(inbound_size, 4096)
    outbound_size = min(outbound_size, 4096)
    logging.debug("Running " + str(app) + " latency breakdown...")
    breakdown = {}
    breakdown['app_ipc'] = run_funclatency(cfg.ISTIO.LATENCY.APP.IPC, duration, app_pid, size=1)
    breakdown['app_read_inbound'] = run_funclatency(cfg.ISTIO.LATENCY.APP.READ, duration, app_pid, size=inbound_size)
    breakdown['app_read_inbound'][0] += syscall
    breakdown['app_write_outbound'] = run_funclatency(cfg.ISTIO.LATENCY.APP.WRITE, duration, app_pid, size=outbound_size)
    breakdown['app_write_outbound'][0] += syscall
    breakdown['app_write_outbound'] = [i-j for i,j in zip(breakdown['app_write_outbound'], breakdown['app_ipc'])]
    return breakdown

def run_latency_experiment(protocol, request_sizes, args, syscall_overhead):
    # Deploy echo server
    subprocess.run("kubectl label namespace default istio-injection=enabled", shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.debug("Deploying echo server for %s proxy...", protocol)
    subprocess.run(["kubectl", "apply", "-f", "benchmark/echo_server/echo-server-"+protocol+"-latency.yaml"], stdout=subprocess.DEVNULL)
    
    # Waited until the echo server is running
    logging.debug("Waiting all pods to be ready ...")
    time.sleep(10)
    wait_until_running("echo")
    logging.debug("All echo server pod running...")
    time.sleep(10)
    result = {}

    for request_size in request_sizes:
        logging.debug("Running latency experiment for %s proxy with request size %d bytes", protocol, request_size)
        result[request_size] = {}
        
        # Run the wrk workload generator
        cmd = ["./wrk/wrk", "-t 1", "-c 1", "-s benchmark/wrk_scripts/echo_workload/echo_workload_PROTOCOL_SIZE.lua".replace("PROTOCOL", protocol).replace("SIZE", str(request_size)), "http://10.96.88.88:80", "-d 800"]
        proc = subprocess.Popen(" ".join(cmd), shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE) 
        logging.debug("Running wrk as " + " ".join(cmd))

        # Get Application and Envoy process info
        wrk_pid = get_pid("wrk")
        envoy_pid = get_pid("envoy")
        echo_pid = get_pid("echo-server") if protocol != "grpc" else get_pid("server")
        logging.debug("wrk pid: %d", wrk_pid)
        logging.debug("Applcation pid: %d", echo_pid)
        logging.debug("Envoy proxy pid: %d", envoy_pid)

        logging.debug("Starting breakdown measurement...")

        if protocol == "tcp":
            proxy_breakdown = run_tcp_proxy_latency_breakdown("echo server", envoy_pid, args.duration, 0, size_list[protocol][request_size][0], size_list[protocol][request_size][1], syscall_overhead)
            app_breakdown = run_app_latency_breakdown("echo server", echo_pid, args.duration, size_list[protocol][request_size][0], size_list[protocol][request_size][1], syscall_overhead)
        elif protocol == "http":
            proxy_breakdown = run_http_proxy_latency_breakdown("echo server", envoy_pid, args.duration, 0, size_list[protocol][request_size], syscall_overhead)
            app_breakdown = run_app_latency_breakdown("echo server", echo_pid, args.duration, size_list[protocol][request_size][2], size_list[protocol][request_size][3], syscall_overhead)
        elif protocol == "grpc":
            proxy_breakdown = run_grpc_proxy_latency_breakdown("echo server", envoy_pid, args.duration, 0, size_list[protocol][request_size], syscall_overhead)
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
    clean_up()
    time.sleep(15)
    
    return result

def linear_regression(label, input_data):
    """
    input_data: List[Tuple(x, y)]
    """
    X = np.array([[e[0]] for e in input_data])
    y = np.array([e[1] for e in input_data])

    reg = LinearRegression().fit(X, y)

    return reg

def build_latency_model(profile, request_sizes, protocol):
    models = {}

    read_data = [(i, profile[i]["read"]) for i in request_sizes]
    # print(read_data)
    models['read_reg'] = linear_regression("read", read_data)

    write_data =  [(i, profile[i]["write"]) for i in request_sizes]
    # print(write_data)
    models['write_reg']  = linear_regression("write", write_data)

    epoll_data = [(i, profile[i]["epoll"]) for i in request_sizes]
    # print(epoll_data)
    models['epoll_reg']  = linear_regression("epoll", epoll_data)

    ipc_data = [(i, profile[i]["ipc"]) for i in request_sizes]
    # print(ipc_data)
    models['ipc_reg']  = linear_regression("ipc", ipc_data)

    envoy_data = [(i, profile[i]["others(proxy)"]) for i in request_sizes] 
    # print(envoy_data)
    models['envoy_reg']  = linear_regression("others(proxy)", envoy_data)

    if protocol != "tcp":
        parsing_data = [(i, profile[i]["parsing(proxy)"]) for i in request_sizes] 
        # print(parsing_data)
        models['parsing_reg']  = linear_regression("parsing(proxy)", parsing_data)
        
    return models

def build_cpu_model(profile, request_sizes_rate_pairs, protocol):
    models = {}

    read_data = [(i[0]*i[1], profile[i]["read"]) for i in request_sizes_rate_pairs]
    models['read_reg'] = linear_regression("read", read_data)

    write_data =  [(i[0]*i[1], profile[i]["write"]) for i in request_sizes_rate_pairs]
    models['write_reg']  = linear_regression("write", write_data)

    epoll_data = [(i[0]*i[1], profile[i]["epoll"]) for i in request_sizes_rate_pairs]
    models['epoll_reg']  = linear_regression("epoll", epoll_data)

    ipc_data = [(i[0]*i[1], profile[i]["ipc"]) for i in request_sizes_rate_pairs]
    models['ipc_reg']  = linear_regression("ipc", ipc_data)

    envoy_data = [(i[0]*i[1], profile[i]["others(proxy)"]) for i in request_sizes_rate_pairs] 
    models['envoy_reg']  = linear_regression("others(proxy)", envoy_data)

    if protocol != "tcp":
        parsing_data = [(i[0]*i[1], profile[i]["parsing(proxy)"]) for i in request_sizes_rate_pairs] 
        models['parsing_reg']  = linear_regression("parsing(proxy)", parsing_data)
        
    return models

# Get the CPU usage (in  virtual cores) using mpstat
def get_virtual_cores(core_count, duration):
    logging.debug("Running mpstat...")
    cpu_util = []
    for _ in range(5):
        cmd = ['mpstat', '1', str(duration)]
        result = subprocess.run(cmd, stdout=subprocess.PIPE)
        result_average = result.stdout.decode("utf-8").split('\n')[-2].split()
        overall = 100.00 - float(result_average[-1])
        cpu_util.append(overall)

    virtual_cores = statistics.mean(cpu_util)*core_count/100
    return virtual_cores   

# Generate Flamegraph with profile
def generate_flamegraph(duration, option="perf"):
    logging.debug("Generating Flamegraph...")

    # With BPF profile
    if option == "ebpf":
        cmd1 = ['python3', './cpu/profile.py', '-F 99', '-f', duration]
        with open("./result/out.profile-folded", "wb") as outfile1:
            subprocess.run(cmd1, stdout=outfile1)

        cmd2 = ['./cpu/flamegraph.pl', './result/out.profile-folded']
        with open("./result/profile.svg", "wb") as outfile2:
            subprocess.run(cmd2, stdout=outfile2)
    elif option == "perf":
        # With perf
        cmd1 = ['perf record -F 99 -a -g -- sleep '+str(duration)]
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
        breakdown['envoy_read'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.PROXY.READ+ " (", proxy_xranges)*0.01

        # Envoy's write
        breakdown['envoy_process_backlog'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.PROXY.WRITE[0]+ " (", proxy_xranges)*0.01
        breakdown['envoy_write'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.PROXY.WRITE[1]+ " (", proxy_xranges)*0.01 -  breakdown['envoy_process_backlog']

        # Envoy's loopback
        breakdown['envoy_br_handle_frame'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.PROXY.IPC+ " (", proxy_xranges)*0.01
        breakdown['envoy_loopback'] = breakdown['envoy_process_backlog'] - breakdown['envoy_br_handle_frame']

        # Envoy' epoll
        breakdown['envoy_epoll'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.PROXY.EPOLL+ " (", proxy_xranges)*0.01

        # Envoy's userspace
        breakdown['envoy_userspace'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.PROXY.USER[0]+ " (")*0.01+\
                                            virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.PROXY.USER[1]+ " (")*0.01
        breakdown['envoy_userspace'] = breakdown['envoy_userspace']-(breakdown['envoy_read']+breakdown['envoy_write']+
                                            breakdown['envoy_epoll'])+breakdown['envoy_loopback'] 
    
    if proxy == 'http' or proxy =='grpc':
        breakdown['envoy_parsing'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.PROXY.PARSE+ " (")*0.01
    
    # Get application CPU breakdown
    if app != "none":
        # App's read
        breakdown['app_read'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.APP.READ+ " (", app_xranges, app_syscall=True)*0.01

        # App's loopback
        breakdown['app_loopback'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.APP.IPC+ " (", app_xranges)*0.01

        # App's write
        breakdown['app_write'] = virtual_cores*get_target_cpu_percentage(">" + cfg.ISTIO.CPU.APP.WRITE+ " (", app_xranges, app_syscall=True)*0.01 - breakdown['app_loopback']

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
    logging.debug("Running wrk2 to get the max service rate ...")
    cmd = ["./wrk2/wrk", "-t 2", "-c 100", "-s benchmark/wrk_scripts/echo_workload/echo_workload_PROTOCOL_SIZE.lua".replace("PROTOCOL", protocol).replace("SIZE", str(request_sizes[-1])), "http://10.96.88.88:80", "-d 45", "-R 10000000"]
    result = subprocess.run(" ".join(cmd), shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode("utf-8").split('\n')
    rate = int(float([r for r in result if "Requests/sec" in r][0].split()[1])*0.9)
    logging.debug("Done, the max service rate is %d requests/second ...", rate)
    
    target_rates = [int(i*rate) for i in [0.25, 0.5, 0.75, 1.00]]
    request_sizes_rate_pairs = []
    result = {}

    for request_size in request_sizes:
        for target_rate in target_rates:
            logging.debug("Running CPU experiment for %s proxy with request size %d bytes and request rate %d QPS", protocol, request_size, target_rate)
            result[(request_size,target_rate)] = {}
            
            # Run the wrk workload generator
            cmd = ["./wrk2/wrk", "-t 2", "-c 100", "-s benchmark/wrk_scripts/echo_workload/echo_workload_PROTOCOL_SIZE.lua".replace("PROTOCOL", protocol).replace("SIZE", str(request_size)), "http://10.96.88.88:80", "-d 800", "-R "+str(target_rate)]
            subprocess.Popen(" ".join(cmd), shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE) 
            logging.debug("Running wrk2 as " + " ".join(cmd))
            wrk_pid = get_pid("wrk")

            # Get CPU usage in terms of virtual cores
            logging.debug("Running mpstat to get CPU usage...")
            virtual_cores = get_virtual_cores(core_count, args.duration)
            logging.debug("%.2f virtual cores used ...", virtual_cores)

            # Generate FlameGraph and do some preprocessing
            logging.debug("Running perf to get CPU breakdown...")
            generate_flamegraph(args.duration)
            app_xranges = get_target_xrange("echo-server") if protocol != "grpc" else get_target_xrange("server")
            proxy_xranges = (get_target_xrange("wrk:worker_0")[0], get_target_xrange("wrk:worker_1")[1]) # wrk1 and wrk2 are always next to each other
            breakdown = get_cpu_breakdown(core_count, protocol, proxy_xranges, "echo-server", app_xranges)
            result[(request_size,target_rate)] = parse_cpu_breakdown(breakdown, rate/1000, protocol)
            request_sizes_rate_pairs.append((request_size,target_rate))

            # Kill the wrk process
            subprocess.run(["kill", "-9", str(wrk_pid)], stdout=subprocess.DEVNULL)
            subprocess.run(["rm", "./result/profile.svg"], stdout=subprocess.DEVNULL)
            time.sleep(20)
            

    # Clean up deployment
    logging.debug("Deleting echo server deployment ...")
    clean_up()
    time.sleep(20)
    return result, request_sizes_rate_pairs

def get_platform_info():
    # Get CPU Info
    cpu_info = subprocess.run("cat /proc/cpuinfo | grep 'model name' | uniq", \
            shell=True, stdout=subprocess.PIPE, check=True).stdout.decode("utf-8").split(": ")[1].rstrip('\n') 

    # Get Kernel Version
    kernel_info = subprocess.run("uname -r", \
            shell=True, stdout=subprocess.PIPE, check=True).stdout.decode("utf-8").rstrip('\n') 

    # Get Kubernetes verion
    k8s_info = re.split(":|\n", subprocess.run("kubectl version --client", shell=True, \
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True).stdout.decode("utf-8"))[1]

    # Get Envoy Version 
    istio_info =  re.split(": |\n", subprocess.run("istioctl version", \
            shell=True, stdout=subprocess.PIPE, check=True).stdout.decode("utf-8"))[1]

    return ("CPU: "+cpu_info, "Kernel: "+kernel_info, "Kubernetes: " + k8s_info, "Istio: v"+istio_info)

if __name__ == '__main__':

    if not os.geteuid() == 0:
        raise Exception('This script should be run with "sudo".')

    try:
        MESHINSIGHT_DIR = os.environ['MESHINSIGHT_DIR']
    except:
        raise ValueError('$MESHINSIGHT_DIR is not set. Example: "/home/username/meshinsight/".')

    os.chdir(os.path.join(MESHINSIGHT_DIR, "meshinsight/profiler"))
    
    cfg = get_config("config/base.yml")
    cfg.merge_from_file("config/istio.yml")
    cfg.update_path(MESHINSIGHT_DIR)

    start = time.time()
    args = parse_args()


    FORMAT = "%(message)s"
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    else:
        logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

    # Get Platform info
    platform_config = get_platform_info()
    logging.info("Platform info: "+str(platform_config))
    profile = {platform_config: {}}
    clean_up()

    protocols = cfg.PROTOCOLS
    request_sizes = cfg.REQUEST_SIZES

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
            latency_models = build_latency_model(latency_profile, request_sizes, p)
            profile[platform_config]["latency"][p] = latency_models
        logging.info("Latency profiling finished!")

    if args.cpu:
        logging.info("Starting CPU profiling!")
        profile[platform_config]["cpu"] = {}
        for p in protocols: 
            cpu_profile, request_sizes_rate_pairs = run_cpu_experiment(p, request_sizes, args)
            
            # Build cpu prediction model via linear regression
            cpu_models = build_cpu_model(cpu_profile, request_sizes_rate_pairs, p)
            profile[platform_config]["cpu"][p] = cpu_models
        logging.info("CPU profiling finished!")
    
    # Save profile results
    Path(os.path.join(MESHINSIGHT_DIR, "meshinsight/profiles")).mkdir(parents=True, exist_ok=True)
    with open(os.path.join(MESHINSIGHT_DIR, "meshinsight/profiles/profile.pkl"), "wb") as fout:
        pickle.dump(profile, fout)
    logging.info("Profile saved to %s", os.path.join(MESHINSIGHT_DIR, "meshinsight/profiles/profile.pkl"))

    clean_up()
    end = time.time()
    logging.info("Profile finished, took %.2f minutes", (end-start)/60)