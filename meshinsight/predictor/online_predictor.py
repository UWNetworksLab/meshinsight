import logging
import pickle
import os, sys
import re
import numpy as np
import argparse
import subprocess
sys.path.append("./CRISP")

from CRISP.process import *
from config.parser import *


class Critical_Path():
    """
    Critical_Path contains critical path information of a single trace
    totalTime: response time of the request
    depth: depth of the critical path
    parsed_cp: parsed critical path from CRISP
    """
    def __init__(self, totalTime, depth, parsed_cp, trace_name):
        self.totalTime = totalTime
        self.depth = depth
        self.parsed_cp = parsed_cp
        self.trace_name = trace_name
        self.latency_overhead = 0.0
        self.cpu_overhead = 0.0 
    
    def __repr__(self):
        return f'Critical_Path(trace name={self.trace_name}, totalTime={self.totalTime}, depth={self.depth}, parsed_cp={self.parsed_cp}, latency overhead={self.latency_overhead}, cpu overhead={self.cpu_overhead})'


class Call():
    """
    Call represents a single network call in the critical path
    service_name: the service name of the calling service. (Jaeger terminology)
    protocol: the proxy type of the call. default: tcp 
    size: the size of the request (in bytes). default: 100 bytes
    rate: (for CPU prediction) request rate in terms of RPS. default: 1000
    """
    def __init__(self, service_name, protocol="tcp", size=100, rate=1000):
        self.service_name = service_name
        self.protocol = protocol
        self.size = size
        self.rate = rate
    
    def __repr__(self):
        return f'Call(service_name={self.service_name}, protocol={self.protocol}, size={self.size}, rate={self.rate})'


def parse_args(MESHINSIGHT_DIR):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-p", "--profile", type=str, default=os.path.join(MESHINSIGHT_DIR, \
        "meshinsight/profiles/profile.pkl"), help="path to the profile")
    parser.add_argument("-c", "--config", type=str, required=True, help="path to config file") 
    parser.add_argument("-s", "--speedup", type=str, required=False, help="path to component speed-up profile") 
    parser.add_argument("-d", "--deployment", type=str, required=False, default="", help="path to k8s deployment file") 
    return parser.parse_args()

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
    istio_info =  re.split(": |\n", subprocess.run("istioctl version", \
            shell=True, stdout=subprocess.PIPE, check=True).stdout.decode("utf-8"))[1]

    return ("CPU: "+cpu_info, "Kernel: "+kernel_info, "Kubernetes: " + k8s_info, "Istio: v"+istio_info)

def parse_call_graph_txt(calls):
    result = []
    for call in calls:
        strs = call.split(",")
        size = strs[2].strip()
        rate = strs[3].strip()
        protocol = strs[4].replace(")", "").strip()
        result.append([size, rate, protocol])
    return result

def predict(profile, type, size, protocol):
    components = ["read_reg", "write_reg", "epoll_reg", "ipc_reg", "envoy_reg"]

    models = profile[type][protocol]
    overhead = 0.0
    for component in components:
        overhead += models[component].predict(np.array([[size]]))

    return overhead
    
def predict_latency_overhead(parsed_critical_paths, profile):
    for parsed_critical_path in parsed_critical_paths:
        for call in parsed_critical_path.parsed_cp:
            parsed_critical_path.latency_overhead += predict(profile, "latency", call.size, call.protocol)

def predict_cpu_overhead(parsed_critical_paths, profile):
    for parsed_critical_path in parsed_critical_paths:
        for call in parsed_critical_path.parsed_cp:
            parsed_critical_path.cpu_overhead += (predict(profile, "cpu", call.size, call.protocol)*call.rate*1000)

def parse_critical_path_from_CRISP(critical_paths, service_to_proxy):
    parsed_cps = []

    for cp in critical_paths:
        metrics = cp[0]
        real_cp = cp[1]
        parsed_cp = []
        for call in real_cp:
            # TODO: add support for auto request size/rate collection
            if service_to_proxy and call.serviceName in service_to_proxy:
                parsed_cp.append(Call(call.serviceName, service_to_proxy[call.serviceName])) 
            else:
                parsed_cp.append(Call(call.serviceName))

        parsed_cps.append(Critical_Path(metrics.opTimeExclusive['totalTime'], metrics.depth, parsed_cp, cp[2]))

    return parsed_cps


if __name__ == '__main__':
    try:
        MESHINSIGHT_DIR = os.environ['MESHINSIGHT_DIR']
    except:
        raise ValueError('$MESHINSIGHT_DIR is not set. Example: "/home/username/meshinsight/".')

    args = parse_args(MESHINSIGHT_DIR)

    if args.verbose:
        logging.basicConfig(format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S', level=logging.INFO)

    cfg = get_config(os.path.join(MESHINSIGHT_DIR, args.config))
    
    logging.debug("Running CRISP to get the critical paths...")
    # Run CRISP to get the critical path for every trace. returns -> (metrics, critical path)
    critical_paths = run_CRISP(os.path.join(MESHINSIGHT_DIR,cfg.CRISP.TRACE_DIR), cfg.CRISP.SERVICE_NAME, cfg.CRISP.OPERATION_NAME, cfg.CRISP.ROOT_TRACE)

    # Read Profile
    logging.debug("Loading profile...")
    with open(args.profile, "rb") as fin:
        profile = pickle.load(fin)

    platform = get_platform_info()
    logging.debug("Platform info: "+str(platform))
    if platform not in profile:
        raise Exception("platform's profile not found. Please run offline profiler first\n")    
    profile = profile[platform]

    service_to_proxy = {}
    if args.deployment:
        service_to_proxy = parse_k8s(args.deployment)

    # Parse call graph
    parsed_critical_paths = parse_critical_path_from_CRISP(critical_paths, service_to_proxy)

    # Using the model to predict the latency overhead
    predict_latency_overhead(parsed_critical_paths, profile)
    predict_cpu_overhead(parsed_critical_paths, profile)

    for cp in parsed_critical_paths:
        print(f"Trace Name: {cp.trace_name}, (average) latency overhead: {cp.latency_overhead[0]} us, cpu overhead: {cp.cpu_overhead[0]} virtual cores")


    # Performance speedup prediction
    if args.speedup:
        speedup_profile = get_config(args.speedup)
        