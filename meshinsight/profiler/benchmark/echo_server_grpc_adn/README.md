# gRPC echo server (with gRPC and ADN)

A simple echo server using Go and gRPC with ADN.

## Run it locally
- Make sure you git the grpc-go library `git clone https://github.com/Romero027/grpc-go.git` to the directory specified in `go.mod`

## Run as docker container 
- Only required for Docker deployments:
    - Change ":9000" to "server:9000" in frontend.go 
    - Add `replace github.com/Romero027/grpc-go => ./grpc-go` in `go.mod`
- `docker build --tag echo-frontend-grpc-adn -f Dockerfile-frontend .`
- `docker build --tag echo-server-grpc-adn -f Dockerfile-server .`
- `docker network create test`
- `docker run --rm -d --net test -p 9000:9000 --name server echo-server-grpc-adn`
- `docker run --rm -d --net test -p 8080:8080 --name frontend echo-frontend-grpc-adn`
- `curl http://localhost:8080/echo`

## Push docker container
- Only required for k8s depolyments
    -  Change ":9000" to "echo-server:9000" in frontend.go 
    - Add `replace github.com/Romero027/grpc-go => ./grpc-go` in `go.mod`
- `docker build --tag echo-frontend-grpc-adn -f Dockerfile-frontend .`
- `docker build --tag echo-server-grpc-adn -f Dockerfile-server .`
- `docker tag echo-frontend-grpc-adn xzhu0027/echo-frontend-grpc-adn`
- `docker push xzhu0027/echo-frontend-grpc-adn`
- `docker tag echo-server-grpc-adn xzhu0027/echo-server-grpc-adn`
- `docker push xzhu0027/echo-server-grpc-adn`