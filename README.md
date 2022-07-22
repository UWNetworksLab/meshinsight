# MeshInsight

# Overview
MeshInsight is a tool we developed to systematically characterize the overhead of service meshes and to help developers quantify overhead in deployment scenarios of interest. Read the [paper](https://arxiv.org/abs/2207.00592) for how MeshInsight works!

Note: MeshInsight currently only works on Istio. We plan to extend it to other service meshes (e.g., Cilium or Linkerd) in the future

# Installation
Please find installation instructions for MeshInsight in [INSTALL.md](INSTALL.md).

# Run MeshInsight
![workflow](./workflow.png)
MeshInsight has an offline profiling phase and an online prediction phase. The offline phase generates performance
profiles of individual service mesh components, and the online phase predicts overhead based on these profiles, service
mesh configuration, and application workload.

Step 1: Run offline profiler
```
cd meshinsight/profiler
sudo python3 offline_profiler.py [-h] [--duration DURATION] [--cpu] [--latency] [--verbose] 
```

Step 2: Run online predictor
```
cd meshinsight/predictor
python3 online_predictor.py [-h] [-v] [-p PROFILE] -c CALL_GRAPH
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
|---- samples       # Demo of service mesh performance analysis
```

# Reference
Please consider citing our paper if you find MeshInsight related to your research.
```bibtex
@misc{https://doi.org/10.48550/arxiv.2207.00592,
  url = {https://arxiv.org/abs/2207.00592}, 
  author = {Zhu, Xiangfeng and She, Guozhen and Xue, Bowen and Zhang, Yu and Zhang, Yongsu and Zou, Xuan Kelvin and Duan, Xiongchun and He, Peng and Krishnamurthy, Arvind and Lentz, Matthew and Zhuo, Danyang and Mahajan, Ratul},
  title = {Dissecting Service Mesh Overheads},
  publisher = {arXiv},
  year = {2022}
}
```

# Contact
If you have any questions or comments, please contact Xiangfeng Zhu (xfzhu@cs.washington.edu).