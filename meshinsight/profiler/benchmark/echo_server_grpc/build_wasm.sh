#!/usr/bin/env bash

WORKDIR=`dirname $(realpath $0)`
cd $WORKDIR

pushd ./wasm
cargo build --target=wasm32-unknown-unknown --release
cp target/wasm32-unknown-unknown/release/content_based_acl.wasm /tmp
popd

