import logging
import pickle
import os
import re
import numpy as np
import argparse
import subprocess

def parse_args(MESHINSIGHT_DIR):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-p", "--profile", type=str, default=os.path.join(MESHINSIGHT_DIR, \
        "meshinsight/profiles/profile.pkl"), help="path to the profile")
    parser.add_argument("-c", "--call_graph", type=str, required=True, help="path to call graph file")    
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
    istio_info =  re.split(": |\n", subprocess.run("$HOME/istio-1.14.1/bin/istioctl version", \
            shell=True, stdout=subprocess.PIPE, check=True).stdout.decode("utf-8"))[1]

    return ("CPU: "+cpu_info, "Kernel: "+kernel_info, "Kubernetes: " + k8s_info, "Istio: v"+istio_info)

def parse_call_graph(calls):
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

    models = profile[type]
    overhead = 0.0
    for component in components:
        overhead += models[component].predict(np.array([[size]]))

    return overhead

    
def predict_latency_overhead(profile, parsed_call_graph):
    latency_overhead = 0.0

    for call in parsed_call_graph:
        size = float(call[0])
        protocol = call[2].lower()
        
        latency_overhead += predict(profile, "latency", size, protocol)
        print(latency_overhead)

    return latency_overhead

def predict_cpu_overhead(profile, parsed_call_graph):
    cpu_overhead = 0.0

    for call in parsed_call_graph:
        size = float(call[0])
        rate = float(call[1])/1000.0
        protocol = call[2].lower()
        cpu_overhead += (predict(profile, "cpu", size, protocol)*rate)
        print(cpu_overhead)
    return cpu_overhead


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

    # Read call graph
    with open(args.call_graph, "r") as fin:
        calls = [line.rstrip() for line in fin.readlines()]

    # Read Profile
    with open(args.profile, "rb") as fin:
        profile = pickle.load(fin)

    platform = get_platform_info()
    logging.debug("Platform info: "+str(platform))
    if platform not in profile:
        raise Exception("platform's profile not found. Please run offline profiler first\n")    
    profile = profile[platform]

    # Parse call graph
    parsed_call_graph = parse_call_graph(calls)


    # Using the model to predict the latency overhead
    latency_overhead = predict_latency_overhead(profile, parsed_call_graph)
    cpu_overhead = predict_cpu_overhead(profile, parsed_call_graph)
    
    logging.info("The predicted latency overhead is %.2f microseconds", latency_overhead)
    logging.info("The predicted latency overhead is %.2f virtual cores", cpu_overhead)