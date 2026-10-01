# Polygon Stack Deployment

This chapter configures and runs the two Polygon Stack services that connect the Besu chain to the Agglayer: aggkit, which updates GERs (Global Exit Roots) on L2 and sends certificates to the Agglayer, and the zkEVM Bridge Service, which indexes bridge events and submits claims on L2.

> [!NOTE]
> Docker images have been tested on AMD64 (linux/amd64). Other architectures are not guaranteed to work.

## Aggkit

> [!WARNING]
> Use aggkit 0.9 or later. Earlier versions recompute L2 block hashes with go-ethereum RLP header hashing, which never matches a QBFT block hash because QBFT strips the committed seals from `extraData` before hashing. The L2 bridge syncer then drops every block that carries bridge events, and aggkit never builds a certificate. aggkit 0.9 reads the block hash from the JSON-RPC response instead ([agglayer/aggkit#1397](https://github.com/agglayer/aggkit/pull/1397)).

### Prerequisites

- Access to L1 and L2 RPC endpoints
- The Besu RPC node from [chapter 03](03-besu-network.md), with the aggkit hostname on its `--host-allowlist`
- Keystore files for the aggsender and Aggoracle keys

### Environment Variables

```shell
# See Component Versions table in 00-prerequisites.md for current values
export aggkit_version="<aggkit_version>"
```

### Configuration

> **Source of Truth**: For complete configuration documentation, see the [Aggkit Documentation](https://github.com/agglayer/aggkit/blob/develop/docs/SUMMARY.md).

Aggkit uses a TOML configuration file. Create a configuration file at `/etc/aggkit/config.toml`. See the [example configuration file](https://github.com/agglayer/aggkit/blob/develop/config.toml.example) for reference, then apply the Besu-specific settings below.

### Besu-specific configuration

```toml
L2URL = "<besu_rpc_url>"
RPCURL = "<besu_rpc_url>"

SequencerPrivateKeyPath = "/etc/aggkit/aggsender.keystore"
SequencerPrivateKeyPassword = "<keystore_password>"

[L1Config]
polygonZkEVMAddress = "<sovereign_rollup_address>"

[L2Config]
GlobalExitRootAddr = "<sovereign_ger_proxy_address>"
BridgeAddr = "<sovereign_bridge_proxy_address>"

[AggSender]
Mode = "PessimisticProof"
AggSenderPrivateKey = {Path = "/etc/aggkit/aggsender.keystore", Password = "<keystore_password>"}

[AggOracle]
EnableAggOracleCommittee = false

[AggOracle.EVMSender]
GlobalExitRootL2 = "<sovereign_ger_proxy_address>"

[AggOracle.EVMSender.EthTxManager.Etherman]
L1ChainID = "<l2_chain_id>"

[BridgeL2Sync]
BridgeAddr = "<sovereign_bridge_proxy_address>"
BlockFinality = "LatestBlock"

[ReorgDetectorL2]
FinalizedBlock = "LatestBlock"

[L2GERSync]
BlockFinality = "LatestBlock"
```

Every block-tag setting is `LatestBlock`, because QBFT finalizes each block when it is produced and Besu serves no `safe` or `finalized` tag. Besu answers a request for either tag with error `-39001` ("Unknown block"). If you leave `[ReorgDetectorL2] FinalizedBlock` at its default, the L2 reorg detector fails with that error.

`L1ChainID` under `[AggOracle.EVMSender.EthTxManager.Etherman]` takes the **L2** chain ID. That section configures the transaction manager that sends GER updates to L2, and the key name is inherited from its L1 counterpart. Do not change it to the L1 chain ID.

`SequencerPrivateKeyPath` and `AggSenderPrivateKey` point to the same keystore, the one holding the `AGGSENDER_ADDRESS` key that you registered as a signer in [chapter 04](04-rollup-initialization.md). Kurtosis mounts this key as `sequencer.keystore`; the file name does not matter as long as both settings reference the same file.

> [!CAUTION]
> **Unverified:** Whether `SequencerPrivateKeyPath` and `AggSenderPrivateKey` must reference the same key for `AggchainECDSAMultisig`. Kurtosis points both at the same keystore.

Fill in the placeholders from these sources:

| Placeholder | Source |
|---|---|
| `<besu_rpc_url>` | The Besu RPC node from chapter 03, for example `http://<besu_rpc_hostname>:8545` |
| `<l2_chain_id>` | `l2ChainID` in `combined.json` |
| `<sovereign_rollup_address>` | The rollup contract registered on L1 for your `rollupID` (see below) |
| `<sovereign_bridge_proxy_address>` | `genesisSCNames["AgglayerBridgeL2 proxy"]` in `polygon-genesis-info.json` |
| `<sovereign_ger_proxy_address>` | `genesisSCNames["AgglayerGERL2 proxy"]` in `polygon-genesis-info.json` |

Take the other L1 addresses in the full configuration, such as the rollup manager and the L1 bridge, from `combined.json`. To read the sovereign rollup address from the rollup manager, call `rollupIDToRollupData` on L1. The first returned value is the rollup address:

```shell
cast call "<polygonRollupManagerAddress-from-combined.json>" \
  "rollupIDToRollupData(uint32)(address,uint64,address,uint64,bytes32,uint64,uint64,uint64,uint64,uint64,uint64,uint8)" \
  "<rollupID-from-combined.json>" \
  --rpc-url "<l1_rpc_url>" | head -1
```

### Running the Container

Run Aggkit using Docker with the configuration file and keystores mounted. The command specifies which components to run:

```shell
docker run --rm -it \
  -v /path/to/config.toml:/etc/aggkit/config.toml \
  -v /path/to/aggsender.keystore:/etc/aggkit/aggsender.keystore:ro \
  -v /path/to/aggoracle.keystore:/etc/aggkit/aggoracle.keystore:ro \
  -v /path/to/data:/data \
  ghcr.io/agglayer/aggkit:${aggkit_version} \
  aggkit run --cfg=/etc/aggkit/config.toml --components=aggoracle,aggsender
```

The Aggoracle signs its GER transactions with the `AGGORACLE_ADDRESS` key. Point `PrivateKeys` under `[AggOracle.EVMSender.EthTxManager]` at the mounted file:

```toml
[AggOracle.EVMSender.EthTxManager]
PrivateKeys = [{Path = "/etc/aggkit/aggoracle.keystore", Password = "<keystore_password>"}]
```

**Components:**
- `aggoracle`: AggOracle service that writes GERs to L2
- `aggsender`: AggSender service that builds and sends certificates

You can run individual components or any combination by adjusting the `--components` flag.

### Additional Resources
- **GitHub**: [agglayer/aggkit](https://github.com/agglayer/aggkit)

## zkEVM Bridge Service

### Prerequisites

- A dedicated PostgreSQL database (set up separately)
- Access to L1 and L2 RPC endpoints

### Environment Variables

```shell
# See Component Versions table in 00-prerequisites.md for current values
export zkevm_bridge_service_version="<zkevm_bridge_service_version>"
```

### Configuration

> **Source of Truth**: For complete configuration documentation, see the [zkevm-bridge-service Documentation](https://github.com/0xPolygon/zkevm-bridge-service/tree/develop/docs).

The zkEVM Bridge Service uses a TOML configuration file. See the [example configuration file](https://github.com/0xPolygon/zkevm-bridge-service/blob/develop/config/config.local.toml) for reference. Point its L2 RPC at the Besu RPC node and use the sovereign contract addresses:

```toml
[Etherman]
l1URL = "<l1_rpc_url>"
L2URLs = ["<besu_rpc_url>"]

[NetworkConfig]
PolygonZkEVMAddress = "<sovereign_rollup_address>"
L2PolygonBridgeAddresses = ["<sovereign_bridge_proxy_address>"]
RequireSovereignChainSmcs = [true]
L2PolygonZkEVMGlobalExitRootAddresses = ["<sovereign_ger_proxy_address>"]
```

The placeholders come from the same sources as the aggkit table above. Set the L1 addresses in `[NetworkConfig]` (`PolygonBridgeAddress`, `PolygonZkEVMGlobalExitRootAddress`, `PolygonRollupManagerAddress`) from `combined.json`, and configure the `[ClaimTxManager]` section with the `CLAIMTXMANAGER_ADDRESS` key.

If you enabled account permissioning on Besu, add `AGGORACLE_ADDRESS` and `CLAIMTXMANAGER_ADDRESS` to the allowlist before you start these services, as described in [chapter 03, step 4](03-besu-network.md#account-and-node-permissioning).

### Running the Container

```shell
docker run --rm -it \
  -v /path/to/config.toml:/app/config.toml \
  hermeznetwork/zkevm-bridge-service:${zkevm_bridge_service_version} \
  run --cfg=/app/config.toml
```

### Additional Resources
- **GitHub**: [0xPolygon/zkevm-bridge-service](https://github.com/0xPolygon/zkevm-bridge-service)

---

**Next:** [Verification and Operations →](06-verification-and-operations.md)
