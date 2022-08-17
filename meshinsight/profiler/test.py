from config.parser import *

def read():
    print(cfg)

if __name__ == '__main__':
    global cfg
    cfg = get_config("config/base.yml")
    cfg.merge_from_file("config/istio.yml")
    print(cfg.REQUEST_SIZE)
    read()