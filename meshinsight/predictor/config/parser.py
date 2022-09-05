import os
import yaml
from easydict import EasyDict as edict
import glob

class YamlParser(edict):
    """
    This is yaml parser based on EasyDict.
    """
    def __init__(self, cfg_dict=None, config_file=None):
        if cfg_dict is None:
            cfg_dict = {}

        if config_file is not None:
            assert(os.path.isfile(config_file))
            with open(config_file, 'r') as f:
                cfg_dict.update(yaml.load(f, Loader=yaml.FullLoader))

        super(YamlParser, self).__init__(cfg_dict)

    
    def merge_from_file(self, config_file):
        with open(config_file, 'r') as f:
            self.update(yaml.load(f, Loader=yaml.FullLoader))

    
    def merge_from_dict(self, config_dict):
        self.update(config_dict)

def dirPathCheck(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(
            f"readable_dir:{path} is not a valid path")

def get_config(config_file=None):
    return YamlParser(config_file=config_file)

def parse_name(name):
    name = name.lower()

    if "tcp" in name:
        return "tcp"
    elif "grpc" in name:
        return "grpc"
    elif "http2" in name:
        return "grpc"
    elif "http" in name:
        return "http"
    else:
        return "unknown"

def parse_k8s(deployment_dir):
    dirPathCheck(deployment_dir)
    k8s_files = glob.glob(os.path.join(deployment_dir, '*.yml'))
    service_to_proxy = {}
    for k8s_file in k8s_files:
        assert(os.path.isfile(k8s_file))
        with open(k8s_file, 'r') as f:
            for data in yaml.load_all(f, Loader=yaml.FullLoader):
                if not data:
                    continue
                if 'kind' in data and data['kind'] == "Service":
                    serviceName = data['metadata']['labels']['app']
                    # Note: we assume there is only one port
                    if 'name' in data['spec']['ports'][0]:
                        proxy_type = parse_name(data['spec']['ports'][0]['name'])
                    else:
                        proxy_type = 'unknown'
                    service_to_proxy[serviceName]=proxy_type
    return service_to_proxy