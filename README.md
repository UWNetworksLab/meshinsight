# MeshInsight

# Overview
MeshInsight is a tool we developed to systematically characterize the overhead of service meshes and to help developers quantify overhead in deployment scenarios of interest. Read the [paper](https://arxiv.org/abs/2207.00592) for how MeshInsight works!


# Installation
Please find installation instructions for MeshInsight in [INSTALL.md](INSTALL.md).

# Run MeshInsight
Step 1: Run offline profiler
```
cd meshinsight/profiler
sudo python3 offline_profiler.py [-h] [--duration DURATION] [--cpu] [--latency] [--verbose] 
```
Note: 
1. If you have multiple nodes in your kubernetes cluster, please make sure the profiler and the application run on the same machine (e.g., use [node selector](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)) by changing the yamls files in `meshinsight/profiler/benchmark/echo-server`.

Step 2: Run online predictor
```

```

# Repo Structure
```
Repo Root
|---- benchmark   
|---- meshinsight   # MeshInsight source code
  |---- profiler    # Source code for offline profiler
  |---- predictor   # Source code for online predictor
  |---- benchmark   # Benchmarks used in the paper and their wrk scripts
|---- utils         # Some other tools for analyzing service mesh deployments
|---- samples       # Contains various samples of service mesh performance analysis
```

# Reference
Please consider citing our paper if you find MeshInsight related to your research.
```bibtex
@misc{https://doi.org/10.48550/arxiv.2207.00592,
  url = {https://arxiv.org/abs/2207.00592}, 
  author = {Zhu, Xiangfeng and She, Guozhen and Xue, Bowen and Zhang, Yu and Zhang, Yongsu and Zou, Xuan Kelvin and Duan, Xiongchun and He, Peng and Krishnamurthy, Arvind and Lentz, Matthew and Zhuo, Danyang and Mahajan, Ratul},
  title = {Dissecting Service Mesh Overheads},
  publisher = {arXiv},
  year = {2022},
  copyright = {arXiv.org perpetual, non-exclusive license}
}
```

# Contact
If you have any question or comments, please contact Xiangfeng Zhu (xfzhu@cs.washington.edu)