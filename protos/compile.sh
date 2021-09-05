#!/bin/bash
set -e

BASEDIR=`pwd`

PROTO_DIR="$BASEDIR/"
OUTPUT_DIR="$BASEDIR/../mapadroid/grpc/compiled/"
GRPC_OUT_DIR="$BASEDIR/../mapadroid/grpc/stubs/"

echo "Converting files from $PROTO_DIR to $SWIFTPROTO_DIR"

FILES=$(find . -type f -name "*.proto")

for proto in $FILES; do
    echo $proto;
    echo "Running in $PROTO_DIR"
    python3 -m grpc_tools.protoc -I="." -I="./mitm_mapper" -I="./shared"  --python_out="$OUTPUT_DIR" --grpc_python_out="$GRPC_OUT_DIR" "$proto";
    python3 -m grpc_tools.protoc -I="." -I="./mapping_manager" -I="./shared"  --python_out="$OUTPUT_DIR" --grpc_python_out="$GRPC_OUT_DIR" "$proto";
done
