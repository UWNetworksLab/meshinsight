#!/usr/bin/env bash

docker run --rm -v `pwd`:/go/src/go-filter -w /go/src/go-filter \
    golang:1.19 \
    go build -v -o libgolang.so -buildmode=c-shared .

cp libgolang.so /tmp