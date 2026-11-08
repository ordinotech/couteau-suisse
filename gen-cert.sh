#!/bin/sh
# Certificat auto-signé pour alltools.lan et *.alltools.lan (valide 5 ans)
mkdir -p certs
openssl req -x509 -nodes -newkey rsa:2048 -days 1825 \
  -keyout certs/lab.key -out certs/lab.crt \
  -subj "/CN=alltools.lan" \
  -addext "subjectAltName=DNS:alltools.lan,DNS:*.alltools.lan"
echo "OK: certs/lab.crt et certs/lab.key créés"
