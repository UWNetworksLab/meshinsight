# Rate Limit Filters

## Deploy filters
- `kubectl apply -f .`
- `kubectl apply -f <app>`

## Check filters
- `kubectl get envoyfilters`
- `istioctl pc listener deploy/<app> --port 15006 --address 0.0.0.0 -o yaml`

## Delete filters
- `kubectl delete envoyfilters --all`
- `kubectl delete configmaps hotel-ratelimit-config`
- `kubectl delete deployment redis`
- `kubectl delete deployment ratelimit`
- `kubectl delete service redis`
- `kubectl delete service ratelimit`


## Change rate limit setting

- Change `request_per_unit` in `rlsconfig.yaml`


