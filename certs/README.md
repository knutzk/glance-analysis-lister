# GLANCE intermediate certificate

`sectigo-public-server-authentication-ca-ov-r36.pem` is the public Sectigo
intermediate omitted by GLANCE's server chain, not a server certificate or a
private key. The downloader combines it with Requests' trusted roots in a
temporary bundle; certificate and hostname verification remain enabled.

Source (the CA Issuers URL in GLANCE's certificate):
http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt

Retrieved on 2026-09-25 and converted from DER to PEM. Its signature chain was
verified against Requests' CA roots with `openssl verify -CAfile <roots.pem>
<intermediate.pem>`. The download transport is not the trust check: signature
verification against trusted roots is required when updating this file.

If GLANCE changes issuer, verify and replace the intermediate or remove this
workaround once the server provides a complete chain. Do not disable TLS
verification. `REQUESTS_CA_BUNDLE` (or `CURL_CA_BUNDLE`) overrides the entire
default bundle; custom bundles must include all required roots/intermediates.
