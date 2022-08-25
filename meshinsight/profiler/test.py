from sklearn.linear_model import LinearRegression
import numpy as np

def linear_regression(label, input_data):
    """
    input_data: List[Tuple(x, y)]
    """
    X = np.array([[e[0]] for e in input_data])
    y = np.array([e[1] for e in input_data])

    reg = LinearRegression().fit(X, y)
    # logging.debug(label+ " reg score: %.2f", reg.score(X, y))

    return reg

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


profile = {(100, 10228): {'read': 0.004722, 'write': 0.010677, 'ipc': 0.006296, 'epoll': 0.004517, 'app_userspace': 0.046539, 'parsing(proxy)': 0.069671, 'others(proxy)': 0.09431, 'others': 1.181541}}
request_sizes_rate_pairs = [(100, 10228)]
protocol = "http"

print(build_cpu_model(profile,request_sizes_rate_pairs,protocol))

 