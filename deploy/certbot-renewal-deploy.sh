#!/bin/sh
set -eu

container_id=$(
    /usr/bin/docker ps \
        --filter label=com.docker.compose.project=b2b-ai-order-processing-agent \
        --filter label=com.docker.compose.service=frontend \
        --quiet |
        head -n 1
)

if [ -n "$container_id" ]; then
    /usr/bin/docker kill --signal HUP "$container_id" >/dev/null
fi
