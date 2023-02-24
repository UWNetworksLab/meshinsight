# gRPC echo server (with gRPC and ADN)

A simple echo server using Go and gRPC with ADN.

## Run as docker container 
- Change ":9000" to "server:9000" in frontend.go （only for docker depolyments)
- `docker build --tag echo-frontend-grpc-adn -f Dockerfile-frontend .`
- `docker build --tag echo-server-grpc-adn -f Dockerfile-server .`
- `docker network create test`
- `docker run --rm -d --net test -p 9000:9000 --name server echo-server-grpc-adn`
- `docker run --rm -d --net test -p 8080:8080 --name frontend echo-frontend-grpc-adn`
- `curl http://localhost:8080/echo`

## Push docker container
- Change ":9000" to "echo-server:9000" in frontend.go （only for k8s depolyments)
- `docker tag echo-frontend-grpc-adn xzhu0027/echo-frontend-grpc-adn`
- `docker push xzhu0027/echo-frontend-grpc-adn`
- `docker tag echo-server-grpc-adn xzhu0027/echo-server-grpc-adn`
- `docker push xzhu0027/echo-server-grpc-adn`