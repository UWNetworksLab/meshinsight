#!/bin/bash
set -ex

sudo docker build --tag echo-frontend -f Dockerfile-frontend .
sudo docker build --tag echo-server -f Dockerfile-server  .
sudo docker tag echo-frontend xzhu0027/echo-frontend-grpc
sudo docker tag echo-server xzhu0027/echo-server-grpc
sudo docker push xzhu0027/echo-frontend-grpc
sudo docker push xzhu0027/echo-server-grpc

set +ex
