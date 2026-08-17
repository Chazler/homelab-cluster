# Vault

This chart defines a three-replica Vault Community Edition deployment with
integrated Raft storage and Google Cloud KMS auto-unseal. The GCP service
account credential is stored only in the encrypted
`vault-auto-unseal-gcp` SealedSecret.

Vault Secrets Operator synchronizes the runtime secrets declared by the
`vault-secret-sync` platform chart. Each namespace has a dedicated
`vault-secrets` service account with access only to its own
`kv/<namespace>/` paths. Application credentials are stored in Vault KV v2;
runtime SealedSecrets are not used.

The client listener is TLS-only, served by a certificate issued by an
in-cluster CA (`templates/internal-ca.yaml`). See SETUP.md's "Vault TLS and
recovery" section for the certificate chain, rotation, and restart
procedure.
