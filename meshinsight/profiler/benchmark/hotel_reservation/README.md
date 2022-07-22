# Hotel Reservation Benchmark

### Deployment

- `kubectl apply -f service/service-tcp.yaml`
- `kubectl apply -f service/service-http.yaml`
- `kubectl apply -f pv.yaml`
- `kubectl apply -f pvc.yaml`
- `kubectl apply -f deployment.yaml`

### wrk script
- `./wrk/wrk -t1 -c1 -d400s -s <script> http://10.96.7.56:5000 --latency`