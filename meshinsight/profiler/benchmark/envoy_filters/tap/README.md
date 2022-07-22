# tap Filters

## Deploy filters
- `kubectl apply -f tap-filter.yaml`


## Check outputs
- `kubectl exec -it <pod-name> -c istio-proxy -- /bin/bash` 
- `ls etc/istio/proxy/`


