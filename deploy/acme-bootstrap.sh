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

cert_domain="${CERT_DOMAIN:?CERT_DOMAIN is required}"
acme_ca="${ACME_CA:-letsencrypt}"

mkdir -p /certs

acme.sh --set-default-ca --server "$acme_ca"
set +e
acme.sh \
    --issue \
    --server "$acme_ca" \
    --dns dns_ali \
    --domain "$cert_domain" \
    --keylength ec-256 \
    --log /acme.sh/acme.sh.log \
    --log-level 1
issue_status=$?
set -e

# acme.sh returns 2 when an existing certificate is not due for renewal.
if [ "$issue_status" -ne 0 ] && [ "$issue_status" -ne 2 ]; then
    exit "$issue_status"
fi

acme.sh \
    --install-cert \
    --domain "$cert_domain" \
    --ecc \
    --key-file /certs/key.pem \
    --fullchain-file /certs/fullchain.pem

test -s /certs/key.pem
test -s /certs/fullchain.pem
chmod 600 /certs/key.pem
chmod 644 /certs/fullchain.pem
