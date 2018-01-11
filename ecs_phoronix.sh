#!/bin/sh
sudo apt install phoronix-test-suite build-essential unzip
phoronix-test-suite benchmark pts/tiobench pts/system-decompress-gzip pts/nginx pts/compress-gzip pts/aio-stress