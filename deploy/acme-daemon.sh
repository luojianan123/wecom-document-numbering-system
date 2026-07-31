#!/bin/sh
set -eu
umask 077

read_secret() {
    secret_file="$1"
    if [ ! -s "$secret_file" ]; then
        echo "Required secret file is missing: $secret_file" >&2
        exit 1
    fi
    tr -d '\r\n' <"$secret_file"
}

export Ali_Key="$(read_secret /run/secrets/aliyun_dns_key)"
export Ali_Secret="$(read_secret /run/secrets/aliyun_dns_secret)"

exec /entry.sh daemon
