# Rollup Initialization

> [!WARNING]
> This step is irreversible. Once the rollup is initialized on-chain, it cannot be undone. Double-check all parameters before proceeding.

> [!WARNING]
> The Besu RPC node from [chapter 03](03-besu-network.md) must be running. The initialization script reads the L2 over RPC.

This chapter prepares the rollup initialization file and runs the initialization script, which registers the chain's `AggchainECDSAMultisig` consensus parameters on L1.

## References

- [Initialize Rollup README](https://github.com/agglayer/agglayer-contracts/blob/main/tools/initializeRollup/README.md) - Full usage details, configuration options, and examples

## Step 1: Prepare Rollup Initialization JSON

> [!NOTE]
> Run the commands in this step from the `agglayer-contracts` root directory.

Copy the example initialization JSON file:

```shell
cp ./tools/initializeRollup/initialize_rollup.json.example ./tools/initializeRollup/initialize_rollup.json
```

Edit the file with your values:

```json
{
    "type": "EOA",
    "trustedSequencerURL": "<besu_rpc_url>",
    "networkName": "<network-name>",
    "trustedSequencer": "<AGGSENDER_ADDRESS>",
    "chainID": <l2ChainID-from-combined.json>,
    "rollupAdminAddress": "<ADMIN_ADDRESS>",
    "consensusContractName": "AggchainECDSAMultisig",
    "gasTokenAddress": "0x0000000000000000000000000000000000000000",
    "deployerPvtKey": "",
    "maxFeePerGas": "",
    "maxPriorityFeePerGas": "",
    "multiplierGas": "",
    "timelockDelay": 0,
    "timelockSalt": "",
    "rollupManagerAddress": "<polygonRollupManagerAddress-from-combined.json>",
    "aggchainParams": {
        "useDefaultVkeys": true,
        "useDefaultSigners": false,
        "signers": [
            {
                "addr": "<AGGSENDER_ADDRESS>",
                "url": "https://<your_aggsender_rpc>"
            }
        ],
        "threshold": 1,
        "vKeyManager": "<ADMIN_ADDRESS>"
    }
}
```

Notes on the fields:

- `trustedSequencerURL` is informational. The contract stores it, and no Agglayer component (the Agglayer node, aggkit, or the bridge service) reads it. Set it to the public URL of your Besu RPC node, as Kurtosis does. It must not be empty. The rollup admin (`rollupAdminAddress`) can change it later with `setTrustedSequencerURL`.
- The first entry in `signers` must be `AGGSENDER_ADDRESS`. The aggsender refuses to send certificates unless it is the signer at index 0. The aggsender signs its own entry locally and never dials its own `url`, but the contract rejects an empty `url`, so set it to the aggsender host.
- The account that runs this script must be the aggchain manager: the EOA whose address you supplied as `initializeBytesAggchain` in the [chain integration runbook](01-rollup-creation.md). The script stops if the deployer key is a different account. The aggchain manager is a separate role from `rollupAdminAddress`, and it is the account that later changes the signer set (see [chapter 06](06-verification-and-operations.md#updating-the-signer-set)).

> [!NOTE]
> A consortium chain lists several signers and sets a `threshold` greater than one. See [Consortium Configuration](07-consortium-configuration.md#shared-certificate-approval-an-aggsender-validator-committee).

## Step 2: Run the Initialization Script

Install dependencies and run the Hardhat initialization script. Substitute `mainnet` for production deployments:

```shell
npm install
npx hardhat run ./tools/initializeRollup/initializeRollup.ts --network sepolia
```

---

**Next:** [Polygon Stack Components →](05-polygon-stack.md)
