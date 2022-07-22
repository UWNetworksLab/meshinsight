import logging
import os
import argparse

def parse_args(MESHINSIGHT_DIR):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-p", "--profile", type=str, default=os.path.join(MESHINSIGHT_DIR, \
        "meshinsight/profiles/profile.pkl"), help="path to the profile")
    parser.add_argument("-c", "--call_graph", type=str, required=True, help="path to call graph file")    
    return parser.parse_args()

def parse_call_graph(calls):
    result = []
    for call in calls:
        strs = call.split(",")
        size = strs[2]
        rate = strs[3]
        protocol = strs[4].replace(")", "")
        result.append([size, rate, protocol])
    return result

def predict_latency_overhead(parsed_call_graph):
    return 0

def predict_cpu_overhead(parsed_call_graph):
    return 0

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
    # print(calls)
    # Read Profile
    # with open(args.profile, "rb") as fin:
    #     profile = pickle.load(fin)

    # Parse call graph
    parsed_call_graph = parse_call_graph(calls)

    # Using the model to predict the latency overhead
    latency_overhead = predict_latency_overhead(parsed_call_graph)
    cpu_overhead = predict_cpu_overhead(parsed_call_graph)
    

    logging.info("The predicted latency overhead is %.2f microseconds", latency_overhead)
    logging.info("The predicted latency overhead is %.2f virtual cores", cpu_overhead)