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

<!-- TODO(verify): the template sets trustedSequencerURL to the aggsender RPC; Kurtosis sets it to the Besu RPC URL. Confirm the correct value. -->

```json
{
    "type": "EOA",
    "trustedSequencerURL": "http://<your_aggsender_rpc>",
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
