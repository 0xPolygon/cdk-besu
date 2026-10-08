# Besu Network Deployment

This chapter builds the QBFT (Besu's Byzantine fault tolerant proof-of-authority consensus) genesis from the Polygon genesis fragment of chapter 02, then starts the Besu validators and an RPC node. The sovereign bridge and GER (Global Exit Root) contracts are part of the genesis `alloc`, so the chain has them from block 0 and needs no separate L2 contract deployment.

> [!NOTE]
> Run the commands in this chapter from the root of this repository.

## References

- [Besu QBFT documentation](https://besu.hyperledger.org/private-networks/how-to/configure/consensus/qbft) - Genesis options, validator management, and network setup
- [Besu CLI reference](https://besu.hyperledger.org/public-networks/reference/cli/options) - Every node flag used below

## Overview

1. Choose the validator set
2. Normalize the Polygon allocs
3. Build the QBFT genesis
4. Start the validators and the RPC node
5. Confirm the chain is producing blocks

### Environment Variables

```shell
export l2_chain_id=<l2ChainID-from-combined.json>
export polygon_genesis_path=<path/to/polygon-genesis.json>
# See Component Versions table in 00-prerequisites.md for current values
export besu_version="<besu_version>"
export validator_count=4
```

## Step 1: Choose the Validator Set

QBFT tolerates `f` faulty validators when the set has at least `3f + 1` members. Four validators tolerate one faulty node, which makes four the smallest set with any fault tolerance.

A single validator works for devnets and matches the tested Kurtosis setup, but one failure halts the chain. Use four or more validators for testnet and mainnet.

Run at least one RPC node separate from the validators. aggkit, the bridge service, and users connect to the RPC node, and the validators stay off the public network.

> [!IMPORTANT]
> The automated end-to-end test, the Kurtosis `besu/sovereign-ecdsa-multisig` preset, runs a single QBFT validator. The Agglayer stack does not depend on the validator count: aggkit and the bridge service read the chain through the RPC node only, and aggkit 0.9 and later takes block hashes from the JSON-RPC response, so the committed seals in `extraData`, which differ with the validator set, do not affect it. The validator count only changes Besu's own consensus behavior. Before a testnet or mainnet launch, run the [verification checklist](06-verification-and-operations.md#verification-checklist) against your multi-validator network, including a run with one validator stopped.

## Step 2: Normalize the Polygon Allocs

Convert the Polygon genesis from chapter 02 into an account map:

```shell
python3 scripts/normalize-allocs.py "${polygon_genesis_path}" polygon-allocs.json
```

The script accepts every output shape `createSovereignGenesis` produces and writes a flat account map with lowercase `0x` addresses, which is the form the Besu genesis `alloc` field expects. The map includes the sovereign bridge and GER predeploys and the `preMintAccounts` from your parameter file.

## Step 3: Build the QBFT Genesis

Choose the sub-section that matches how you run the chain. A single operator generates every validator key in one place (3a). In a consortium, each member keeps its own key and shares only its address (3b).

### 3a. Single-operator: generate keys and genesis together

Create `qbftConfigFile.json`. The `genesis` object is the Besu genesis without `extraData`, and the `blockchain` object tells Besu how many validator keys to generate:

```json
{
  "genesis": {
    "config": {
      "chainId": <l2_chain_id>,
      "homesteadBlock": 0,
      "eip150Block": 0,
      "eip155Block": 0,
      "eip158Block": 0,
      "byzantiumBlock": 0,
      "constantinopleBlock": 0,
      "petersburgBlock": 0,
      "istanbulBlock": 0,
      "berlinBlock": 0,
      "londonBlock": 0,
      "shanghaiTime": 0,
      "zeroBaseFee": true,
      "qbft": {
        "blockperiodseconds": 1,
        "epochlength": 30000,
        "requesttimeoutseconds": 4
      }
    },
    "nonce": "0x0",
    "timestamp": "0x0",
    "gasLimit": "0x1c9c380",
    "difficulty": "0x1",
    "mixHash": "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365",
    "coinbase": "0x0000000000000000000000000000000000000000",
    "alloc": {}
  },
  "blockchain": {
    "nodes": {
      "generate": true,
      "count": <validator_count>
    }
  }
}
```

The `qbft` values set a one-second block period, an epoch of 30000 blocks, and a four-second round timeout. `mixHash` is the fixed value QBFT uses to identify its blocks.

Copy the Polygon allocs into the genesis:

```shell
jq --slurpfile allocs polygon-allocs.json '.genesis.alloc = $allocs[0]' qbftConfigFile.json > qbftConfigFile.tmp \
  && mv qbftConfigFile.tmp qbftConfigFile.json
```

Generate the validator keys and the genesis:

```shell
docker run --rm -u "$(id -u):$(id -g)" \
  -v "$(pwd)":/work \
  hyperledger/besu:${besu_version} \
  operator generate-blockchain-config \
  --config-file=/work/qbftConfigFile.json \
  --to=/work/networkFiles \
  --private-key-file-name=key
```

The command writes:

- `networkFiles/genesis.json`, with `extraData` already encoding the validator addresses
- one `networkFiles/keys/<address>/` directory per validator, holding the node private key `key` and public key `key.pub`

The directory name is the validator address (`VALIDATOR_<n>_ADDRESS`). The command refuses to write into an existing `networkFiles/` directory, so move or remove it before you run the command again.

`zeroBaseFee: true` in the genesis and `--min-gas-price=0` on each node (step 4) work together: transactions cost no gas, which suits a permissioned chain. If you want a fee market, remove both settings.

### 3b. Consortium: each member keeps its own key

[Chapter 07](07-consortium-configuration.md#shared-block-production-one-qbft-validator-per-member) walks through this flow in full. In short:

1. Each member generates its node key on its own machine and exports the address with `besu public-key export-address`.
2. Each member sends only the address to the coordinator.
3. The coordinator writes the addresses to a JSON array and encodes it into `extraData`:

   ```shell
   docker run --rm -u "$(id -u):$(id -g)" \
     -v "$(pwd)":/work \
     hyperledger/besu:${besu_version} \
     rlp encode --type=QBFT_EXTRA_DATA \
     --from=/work/validators.json \
     --to=/work/extraData.rlp
   ```

4. The coordinator builds `qbftConfigFile.json` and copies in the allocs as in 3a (the `blockchain` object is not used here), then writes the genesis with the encoded `extraData`:

   ```shell
   mkdir -p networkFiles
   jq --arg extra_data "$(cat extraData.rlp)" '.genesis | .extraData = $extra_data' qbftConfigFile.json \
     > networkFiles/genesis.json
   ```

Do not assemble the `extraData` bytes by hand. Use `besu rlp encode`, which handles any number of validators.

> [!WARNING]
> Every node must start from the byte-identical `genesis.json`. Distribute the file, not the config used to build it. A node started from a different genesis forms a separate chain.

## Step 4: Start the Validators and the RPC Node

Each node runs in its own container, on its own host in production. Nodes find each other through a static peer list, and discovery stays off because the validator set is fixed.

### Build the static peer list

Each node's enode URL combines its public key (without the `0x` prefix) with its host and P2P port. Build `static-nodes.json` with one entry per validator, using the IP address the other nodes reach it on:

```shell
# Repeat the enode line for each validator
cat > static-nodes.json <<EOF
[
  "enode://$(cut -c3- networkFiles/keys/<VALIDATOR_1_ADDRESS>/key.pub)@<validator_1_ip>:30303",
  "enode://$(cut -c3- networkFiles/keys/<VALIDATOR_2_ADDRESS>/key.pub)@<validator_2_ip>:30303"
]
EOF
```

Copy `genesis.json`, `static-nodes.json`, and each validator's own `key` to that validator's host. Keep each `key` on its own host only.

### Start each validator

Run this on each validator host, with that validator's address:

```shell
docker run -d --name besu-validator \
  -p 30303:30303 \
  -p 127.0.0.1:8545:8545 \
  -p 9545:9545 \
  -v "$(pwd)/networkFiles/genesis.json":/etc/besu/genesis.json:ro \
  -v "$(pwd)/networkFiles/keys/<VALIDATOR_ADDRESS>/key":/etc/besu/key:ro \
  -v "$(pwd)/static-nodes.json":/etc/besu/static-nodes.json:ro \
  -v besu-data:/data \
  hyperledger/besu:${besu_version} \
  --genesis-file=/etc/besu/genesis.json \
  --data-path=/data \
  --node-private-key-file=/etc/besu/key \
  --static-nodes-file=/etc/besu/static-nodes.json \
  --discovery-enabled=false \
  --p2p-port=30303 \
  --rpc-http-enabled \
  --rpc-http-host=0.0.0.0 \
  --rpc-http-port=8545 \
  --rpc-http-api=ETH,NET,WEB3,QBFT,TXPOOL,DEBUG,TRACE \
  --rpc-ws-enabled \
  --rpc-ws-host=0.0.0.0 \
  --rpc-ws-port=8546 \
  --rpc-ws-api=ETH,NET,WEB3,QBFT,TXPOOL \
  --min-gas-price=0 \
  --sync-mode=FULL \
  --metrics-enabled \
  --metrics-host=0.0.0.0 \
  --metrics-port=9545
```

The validator publishes its P2P port and its metrics port, and publishes HTTP RPC on the host's loopback interface only. You use that local RPC on the validator host to cast validator votes (see [chapter 06](06-verification-and-operations.md#changing-the-validator-set)); Besu's default `--host-allowlist` accepts `localhost` and `127.0.0.1`. Expose the metrics port only to your monitoring network.

### Start the RPC node

The RPC node follows the chain without a validator key. Besu generates a node key in `/data/key` on first start. It uses the same genesis and static peer list, and it publishes its RPC ports for aggkit, the bridge service, and users:

```shell
docker run -d --name besu-rpc \
  -p 30303:30303 \
  -p 8545:8545 \
  -p 8546:8546 \
  -p 9545:9545 \
  -v "$(pwd)/networkFiles/genesis.json":/etc/besu/genesis.json:ro \
  -v "$(pwd)/static-nodes.json":/etc/besu/static-nodes.json:ro \
  -v besu-rpc-data:/data \
  hyperledger/besu:${besu_version} \
  --genesis-file=/etc/besu/genesis.json \
  --data-path=/data \
  --static-nodes-file=/etc/besu/static-nodes.json \
  --discovery-enabled=false \
  --p2p-port=30303 \
  --rpc-http-enabled \
  --rpc-http-host=0.0.0.0 \
  --rpc-http-port=8545 \
  --rpc-http-api=ETH,NET,WEB3,QBFT,DEBUG \
  --rpc-ws-enabled \
  --rpc-ws-host=0.0.0.0 \
  --rpc-ws-port=8546 \
  --rpc-ws-api=ETH,NET,WEB3,QBFT \
  --host-allowlist=<besu_rpc_hostname> \
  --min-gas-price=0 \
  --sync-mode=FULL \
  --metrics-enabled \
  --metrics-host=0.0.0.0 \
  --metrics-port=9545
```

`--host-allowlist` lists the hostnames clients use to reach the RPC node. Besu accepts only `localhost` and `127.0.0.1` by default, so aggkit and the bridge service fail to connect unless their hostname for the node is on the list.

The RPC node enables only the API namespaces its clients use:

| Namespace | Used by |
|---|---|
| `ETH` | aggkit and the bridge service: blocks, logs, transactions, gas estimation, and sending GER and claim transactions |
| `NET`, `WEB3` | Not called by aggkit or the bridge service; kept for standard tooling and health checks |
| `DEBUG` | aggkit: `debug_traceTransaction` with the `callTracer`, which the bridge and claim syncers use to find the original sender when a bridge or claim reaches the bridge contract through another contract |
| `QBFT` | The validator set check in step 5 |

Neither client calls `TRACE` or `TXPOOL` methods, so the RPC node leaves them off. Kurtosis enables both on its devnet node, but nothing in the stack needs them. `DEBUG` lets callers run expensive traces, so expose the RPC node only to aggkit, the bridge service, and the users you intend to serve.

### Differences from the Kurtosis devnet

- Kurtosis sets `--host-allowlist=*` and `--rpc-http-cors-origins=*` for a local devnet. In production, restrict both to known hosts and origins.
- Validators do not need to expose HTTP RPC publicly. The RPC node exposes it to aggkit and the bridge service.
- Kurtosis sets `--discovery-enabled=false` because it runs one validator. With a fixed validator set, discovery off plus static peers is the expected setup.

### Account and node permissioning

> [!IMPORTANT]
> If you enable Besu account permissioning (an allowlist of addresses allowed to send transactions), add these addresses before you start aggkit or the bridge service: `AGGORACLE_ADDRESS`, which writes GERs to L2, and `CLAIMTXMANAGER_ADDRESS`, which submits bridge claims on L2. Add `ADMIN_ADDRESS` if it will call the bridge or GER contracts on L2 (for example to pause the bridge). Any user who bridges or claims on L2 must also be on the allowlist, unless the ClaimTxManager submits claims on their behalf. If you enable node permissioning, allow every validator and RPC node. aggkit and the bridge service connect over RPC and do not need node permissioning entries.

The aggsender and aggsender validators sign certificates off-chain and send no L2 transactions, so they do not need allowlist entries.

Besu local permissioning reads a TOML file. A minimal `permissions_config.toml`:

```toml
accounts-allowlist=["<AGGORACLE_ADDRESS>", "<CLAIMTXMANAGER_ADDRESS>", "<ADMIN_ADDRESS>"]
```

Mount the file into every node and add these flags to each node's command:

```shell
  -v "$(pwd)/permissions_config.toml":/etc/besu/permissions_config.toml \
  ...
  --permissions-accounts-config-file-enabled \
  --permissions-accounts-config-file=/etc/besu/permissions_config.toml
```

Mount the file writable, not with `:ro`. Besu writes to it when the allowlist changes and fails to start with `ERROR_ALLOWLIST_PERSIST_FAIL` if it cannot. A node with account permissioning rejects transactions from any other sender with error `-32007` ("Sender account not authorized to send transactions").

For node permissioning, add a `nodes-allowlist` entry with the enode URL of every validator and RPC node, and enable it with `--permissions-nodes-config-file-enabled` and `--permissions-nodes-config-file`. Read the RPC node's public key from its data volume with `besu --data-path=/data public-key export`.

> [!IMPORTANT]
> Enable account permissioning with the same file on every validator and on every RPC node. Besu checks the local allowlist when a transaction enters a node's transaction pool and when that node builds a block, but not when it imports a block that another validator produced. The Besu documentation says the same: local permissioning affects only your node, and your rules are not enforced in blocks that other nodes produce. A node without the allowlist can therefore accept a transaction from any sender and gossip it to the validators, and a validator without it can put that transaction in a block, which every other node then imports. The allowlist is local policy rather than a consensus rule. Every node operator has to apply it for it to hold, which matters in a consortium (see [chapter 07](07-consortium-configuration.md#consortium-permissioning)).

## Step 5: Confirm the Chain Is Producing Blocks

Run these checks against the RPC node:

```shell
export besu_rpc_url="http://<besu_rpc_hostname>:8545"

# The block number increases between calls
cast block-number --rpc-url "${besu_rpc_url}"

# The sovereign bridge predeploy has code at block 0
export sovereign_bridge_proxy_addr=$(jq -r '.genesisSCNames["AgglayerBridgeL2 proxy"]' <path/to/polygon-genesis-info.json>)
cast code "${sovereign_bridge_proxy_addr}" --rpc-url "${besu_rpc_url}"

# The validator set contains every validator address
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"qbft_getValidatorsByBlockNumber","params":["latest"],"id":1}' \
  "${besu_rpc_url}" | jq
```

`cast code` returns non-empty bytecode, and the validator list matches your `VALIDATOR_<n>_ADDRESS` set.

> [!WARNING]
> Keep Besu running. Chapter 04 reads the L2 during rollup initialization.

---

**Next:** [Rollup Initialization →](04-rollup-initialization.md)
