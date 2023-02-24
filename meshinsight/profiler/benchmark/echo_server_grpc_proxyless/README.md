# gRPC echo server (with proxyless gRPC)

A simple echo server using Go and proxyless gRPC.

## Run as docker container 
- Change ":9000" to "server:9000" in frontend.go （only for docker depolyments)
- `docker build --tag echo-frontend-grpc-proxyless -f Dockerfile-frontend .`
- `docker build --tag echo-server-grpc-proxyless -f Dockerfile-server .`
- `docker network create test`
- `docker run --rm -d --net test -p 9000:9000 --name server echo-server-grpc-proxyless`
- `docker run --rm -d --net test -p 8080:8080 --name frontend echo-frontend-grpc-proxyless`
- `curl http://localhost:8080/echo`

## Push docker container
- Change ":9000" to "echo-server:9000" in frontend.go （only for k8s depolyments)
- `docker tag echo-frontend-grpc-proxyless xzhu0027/echo-frontend-grpc-proxyless`
- `docker push xzhu0027/echo-frontend-grpc-proxyless`
- `docker tag echo-server-grpc-proxyless xzhu0027/echo-server-grpc-proxyless`
- `docker push xzhu0027/echo-server-grpc-proxyless`