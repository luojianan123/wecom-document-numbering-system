#!/bin/sh
set -eu

if [ "${TLS_CERT_RELOAD_ENABLED:-false}" != "true" ]; then
    exit 0
fi

cert_file=/etc/nginx/certs/fullchain.pem
key_file=/etc/nginx/certs/key.pem

certificate_checksum() {
    if [ ! -r "$cert_file" ] || [ ! -r "$key_file" ]; then
        return 1
    fi

    sha256sum "$cert_file" "$key_file" | sha256sum | cut -d ' ' -f 1
}

(
    previous_checksum="$(certificate_checksum || true)"

    while sleep 300; do
        current_checksum="$(certificate_checksum || true)"
        if [ -z "$current_checksum" ] || [ "$current_checksum" = "$previous_checksum" ]; then
            continue
        fi

        if nginx -t; then
            nginx -s reload
            previous_checksum="$current_checksum"
        fi
    done
) &
