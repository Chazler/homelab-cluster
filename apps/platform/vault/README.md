# Vault operations

## Auto-unseal migration

The chart configures Google Cloud KMS auto-unseal with the
`vault-auto-unseal-gcp` SealedSecret.  The Google service-account key is only
present in that encrypted manifest; its plaintext must never be committed.

Migrating an existing Shamir-sealed integrated-Raft cluster requires a short
outage.  Complete the following with the unseal key and recovery material
available in a password manager.  Do not delete the Cloud KMS key or disable
the service account after migration.

1. Take and verify a Raft snapshot before changing the Vault release.
2. Sync the committed Vault configuration, then stop all existing Vault pods.
3. Bring the existing peers back up together.  On one peer, enter the existing
   Shamir key interactively using `vault operator unseal -migrate`.
4. Confirm `vault status` reports Google Cloud KMS as the seal type and that
   `vault operator raft list-peers` has the original two voters.
5. Allow `vault-2` to join using the configured `retry_join` peers, then verify
   all three members are voters before considering the migration complete.

The migration cannot be safely automated because the current Shamir unseal key
must not be stored in Git, a command history, or automation logs.

## Raft snapshots

Create snapshots manually on the administrator Mac and save them in a locally
synced OneDrive folder.  A snapshot is not a backup until OneDrive reports it
has synchronized.  Test a restore into an isolated Vault instance after each
significant configuration change and at regular intervals.

Keep the snapshot, recovery keys, and KMS project/key identifiers in separate
recovery records outside the cluster and this repository.
