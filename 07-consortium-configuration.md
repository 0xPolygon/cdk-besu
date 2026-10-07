# Consortium Configuration (Optional)

> [!NOTE]
> This chapter is optional. It applies when several organizations jointly operate one chain. The Agglayer supports this configuration.

In a consortium, no single member should be able to produce blocks or settle a certificate alone. This guide gets there with two independent controls: each member runs its own QBFT validator, so block production needs agreement among members, and each member runs a certificate signer, so settlement on the Agglayer needs agreement among members too. This chapter covers each control in turn, then the permissioning and agreements they depend on.

## Shared block production: one QBFT validator per member

Each member holds its own validator key, and no one else ever sees it. This replaces [chapter 03, step 3a](03-besu-network.md#3a-single-operator-generate-keys-and-genesis-together), where one operator generates every key. Pick one member as the coordinator who assembles the genesis.

1. **Each member generates a node key on its own infrastructure** and exports the address. Besu creates the key in the data directory if none exists:

   ```shell
   # See Component Versions table in 00-prerequisites.md for current values
   export besu_version="<besu_version>"
   mkdir -p besu-node
   docker run --rm -u "$(id -u):$(id -g)" \
     -v "$(pwd)/besu-node":/data \
     hyperledger/besu:${besu_version} \
     --data-path=/data public-key export-address --to=/data/address
   ```

   The key is in `besu-node/key` and the address in `besu-node/address`. Keep `besu-node/key` on this host only. Export the public key as well, since the other members need it for the static peer list:

   ```shell
   docker run --rm -u "$(id -u):$(id -g)" \
     -v "$(pwd)/besu-node":/data \
     hyperledger/besu:${besu_version} \
     --data-path=/data public-key export --to=/data/key.pub
   ```

2. **Each member sends only its validator address to the coordinator**, along with its public key and the IP address its validator listens on for P2P.

3. **The coordinator encodes the address list and distributes the genesis.** Write the addresses to `validators.json`:

   ```json
   ["<VALIDATOR_1_ADDRESS>", "<VALIDATOR_2_ADDRESS>", "<VALIDATOR_3_ADDRESS>", "<VALIDATOR_4_ADDRESS>"]
   ```

   Then run the `rlp encode` and `jq` commands from [chapter 03, step 3b](03-besu-network.md#3b-consortium-each-member-keeps-its-own-key). They write the encoded list into `extraData` and produce `networkFiles/genesis.json`. Build `static-nodes.json` from the members' public keys and IP addresses in the same format as chapter 03, step 4, and send both files to every member.

4. **Each member starts its validator** with its own key and the shared genesis, using the validator command from [chapter 03, step 4](03-besu-network.md#start-each-validator). Mount `besu-node/key` as `/etc/besu/key`. Every member confirms that `sha256sum genesis.json` matches the coordinator's value before starting.

5. **Later membership changes use the validator vote** from [chapter 06](06-verification-and-operations.md#changing-the-validator-set). A majority of the current validators must vote to add or remove a member.

## Shared certificate approval: an aggsender validator committee

`AggchainECDSAMultisig` requires M of N registered signers to approve each certificate before the Agglayer accepts it. One member runs the proposing aggsender from [chapter 05](05-polygon-stack.md#aggkit), and each other member runs an aggsender validator that checks the certificate against its own view of the chain and signs it.

### Keys

Each member other than the proposer creates a keystore for its `AGGSENDER_VALIDATOR_<n>_ADDRESS`. The proposer's `AGGSENDER_ADDRESS` also counts as a signer.

### Rollup initialization changes

In [chapter 04](04-rollup-initialization.md), list every signer in `aggchainParams.signers` with its `addr` and `url`, and set `threshold` to M. For example, with four signers and a threshold of three:

```json
    "aggchainParams": {
        "useDefaultVkeys": true,
        "useDefaultSigners": false,
        "signers": [
            {
                "addr": "<AGGSENDER_ADDRESS>",
                "url": "https://<member_1_aggsender_rpc>"
            },
            {
                "addr": "<AGGSENDER_VALIDATOR_2_ADDRESS>",
                "url": "https://<member_2_validator_rpc>"
            },
            {
                "addr": "<AGGSENDER_VALIDATOR_3_ADDRESS>",
                "url": "https://<member_3_validator_rpc>"
            },
            {
                "addr": "<AGGSENDER_VALIDATOR_4_ADDRESS>",
                "url": "https://<member_4_validator_rpc>"
            }
        ],
        "threshold": 3,
        "vKeyManager": "<ADMIN_ADDRESS>"
    }
```

This is an example, not a recommendation. Choose M based on how many members must agree and how many can be offline at once. `threshold` cannot exceed the number of signers.

### Running a validator

Each validating member runs aggkit with only the `aggsender-validator` component:

```shell
docker run --rm -it \
  -v /path/to/config.toml:/etc/aggkit/config.toml \
  -v /path/to/aggsendervalidator.keystore:/etc/aggkit/aggsendervalidator.keystore:ro \
  -v /path/to/data:/data \
  ghcr.io/agglayer/aggkit:${aggkit_version} \
  aggkit run --cfg=/etc/aggkit/config.toml --components=aggsender-validator
```

Its configuration holds the top-level `L1URL` and `L2URL` from chapter 05 plus a `[Validator]` section:

```toml
[Validator]
EnableRPC = true
Signer = { Method = "local", Path = "/etc/aggkit/aggsendervalidator.keystore", Password = "<keystore_password>" }
Mode = "PessimisticProof"

[Validator.ServerConfig]
Host = "0.0.0.0"
Port = <validator_grpc_port>
MaxDecodingMessageSize = 1073741824

[Validator.LerQuerierConfig]
RollupManagerAddr = "<polygonRollupManagerAddress-from-combined.json>"
RollupCreationBlockL1 = "<rollup_manager_creation_block>"

[Validator.AgglayerClient]
Cached = true

[Validator.AgglayerClient.ConfigurationCache]
TTL = "15m"
Capacity = 100

[Validator.AgglayerClient.GRPC]
URL = "<agglayer_grpc_url>"
UseTLS = false
```

Point each member's `L2URL` at a Besu RPC node that member trusts, ideally its own, so that its signature reflects its own view of the chain. A validator that reads the chain through another member's node signs whatever that node reports.

### Proposer changes

The proposer finds the validators on-chain. For each certificate, the aggsender reads the signer list and threshold from the `AggchainECDSAMultisig` contract and opens a gRPC connection to the `url` of every signer. It sends the certificate to all of them at once and stops as soon as it holds `threshold` signatures, its own included. The proposer signs its own entry locally with `AggSenderPrivateKey`, so its own `url` is never dialed.

This puts two requirements on the signer list from [chapter 04](04-rollup-initialization.md):

- The proposer's `AGGSENDER_ADDRESS` must be the first signer. The aggsender refuses to send a certificate otherwise.
- Each validator's `url` must reach that member's `[Validator.ServerConfig]` gRPC port from the proposer host, for example `https://<member_2_validator_host>:<validator_grpc_port>`. aggkit strips an `http://` or `https://` prefix before dialing, so a bare `host:port` works too. The prefix does not turn on TLS: set `UseTLS = true` under `[AggSender.ValidatorClient]` when the validators serve gRPC over TLS.

`[AggSender.ValidatorClient]` holds no endpoint list. It only sets the gRPC client options, such as timeouts and TLS, that the aggsender applies to every validator connection. If the proposer reaches a validator through a different address from the one registered on-chain, for example over a private network, map it in `[AggSender.CommitteeOverride]`:

```toml
[AggSender.CommitteeOverride]
URLMapping = { "https://<member_2_validator_host>:<validator_grpc_port>" = "http://<private_address>:<validator_grpc_port>" }
```

The keys are the URLs exactly as registered on-chain.

The proposer and each validator can also set `RequireCommitteeMembershipCheck = true` (under `[AggSender]` and `[Validator]` respectively). At startup, the service then checks that its signing address is in the on-chain committee and fails to start if it isn't. With the default `false`, it only logs a warning.

## Consortium permissioning

Apply the permissioning rules from [chapter 03, step 4](03-besu-network.md#account-and-node-permissioning) across every member:

- Every member's RPC node needs the same account allowlist, including `AGGORACLE_ADDRESS` and `CLAIMTXMANAGER_ADDRESS`. A member whose node lacks an entry rejects that sender's transactions.
- Node permissioning must list every member's validator and RPC nodes. When a member joins or leaves, every member updates its node allowlist.

## Operational agreements

Members agree on the following before launch:

- Who holds `ADMIN_ADDRESS`, which can pause the bridge and manage the L2 contracts, and whether it is a multisig controlled by several members.
- The certificate threshold M, and what happens if enough members go offline that the threshold cannot be met.
- The procedure for adding or removing a member: a validator vote on the QBFT set, plus a signer set update on `AggchainECDSAMultisig` (see [chapter 06](06-verification-and-operations.md#updating-the-signer-set)).
- The upgrade window for Besu and aggkit, and who coordinates it.

---

**Back to:** [README](README.md)
