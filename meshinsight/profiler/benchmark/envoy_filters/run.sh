# Get envoy filters
kubectl get envoyfilters
kubectl delete envoyfilters --all


# Check filters
istioctl pc listener deploy/<app> --port 15006 --address 0.0.0.0 -o yaml