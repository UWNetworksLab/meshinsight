# gRPC echo server

A simple echo server using golang and gRPC.

## Run as docker container 
- `docker build --tag echo-frontend .`
- `docker build --tag echo-server .`
- Change ":9000" to "server:9000" in frontend.go 
- `docker network create test`
- `docker run --rm -d --net test -p 9000:9000 --name server echo-server`
- `docker run --rm -d --net test -p 8080:8080 --name frontend echo-frontend`
- `curl http://localhost:8080/echo`

## Push docker container
- `docker tag echo-frontend xzhu0027/echo-frontend-grpc`
- `docker push xzhu0027/echo-frontend-grpc`
- `docker tag echo-server xzhu0027/echo-server-grpc`
- `docker push xzhu0027/echo-server-grpc`