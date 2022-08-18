import os
import yaml
from easydict import EasyDict as edict

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
    
    # Change to absolute path
    def update_path(self, path):
        path_dict = {}
        for k, v in self.PATH.items():
            if "PATH" in k:
                path_dict[k] = os.path.join(path, v)
        self.PATH.update(path_dict)
        # for k, v in self.PATH.items():
        #         print(k, v)


def get_config(config_file=None):
    return YamlParser(config_file=config_file)
