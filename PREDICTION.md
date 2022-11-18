# Online Prediction

MeshInsight relies on critical path and sidecar proxy configurations to generate overhead prediction. To this end, we have integrated MeshInsight with [CRISP](https://github.com/uber-research/CRISP), a critical path extractor developed by Uber. 


## CRISP
To use CRISP, you need to provide a few parameters (in yaml format) listed below. 

```YAML
CRISP:
  # path of the trace directory (traces must be in JSON format)
  TRACE_DIR: meshinsight/predictor/CRISP/example1
  # service name and operation name are in Jaeger terminology
  SERVICE_NAME: service-a
  OPERATION_NAME: ping-receive
  # Should the service and operation be the root span of the trace
  ROOT_TRACE: False
  # number of concurrent python processes.
  PARALLELISM: 1
```

Full example is shown in `meshinsight/predictor/config/example1.yml`. We provide two sample traces in `meshinsight/predictor/CRISP/example1` and `meshinsight/predictor/CRISP/example2`


## Sidecar Proxy Configurations

We will automatically parse the proxy configurations if you give MeshInsight the deployment files (i.e., Kubernetes yaml files). If we cannot match the service name in the trace and in the deployment files, MeshInsight will assume the proxy is configured as a TCP proxy. 


## Quantifying the impact of service mesh optimizations

MeshInsight an also predict the end-to-end impact of an optimization (e.g., using Unix domain socket instead of loopback). To enable this estimation, you need to provide information (i,e., a speedup profile) on the impact of the optization for the component(s) you have optimized. See `meshinsight/predictor/config/speedup.yml` for an example speedup profile.

Alternatively, new performance profiles may be based on running offline profiling after implementing the optimization.