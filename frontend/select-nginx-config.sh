#!/bin/sh
set -eu

public_host="${PUBLIC_HOST:-localhost}"
certificate="/etc/letsencrypt/live/${public_host}/fullchain.pem"
private_key="/etc/letsencrypt/live/${public_host}/privkey.pem"

if [ -f "$certificate" ] && [ -f "$private_key" ]; then
    sed "s|__PUBLIC_HOST__|${public_host}|g" \
        /etc/nginx/templates/order-agent-https.conf \
        > /etc/nginx/conf.d/default.conf
else
    cp /etc/nginx/templates/order-agent-http.conf /etc/nginx/conf.d/default.conf
fi
