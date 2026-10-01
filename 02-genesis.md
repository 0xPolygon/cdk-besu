# Genesis File Generation

This chapter produces the Polygon genesis fragment that holds the sovereign bridge and GER (Global Exit Root) predeploys. Chapter 03 turns it into the Besu genesis.

## Overview

- **Recommended**: Generate the sovereign bridge and GER predeploys with `createSovereignGenesis` and place them in the Besu genesis `alloc`
- **Alternative**: Manual L2 contract deployment (outside the scope of this guide)

1. Check out the `agglayer-contracts` repository and install dependencies
2. Create and configure the parameter file using values from `combined.json`
3. Download the allocs file from `cdk-contracts-tooling` (Bali, Cardona, mainnet, etc.) as `genesis-base.json`
4. Run the Hardhat script to generate genesis files
5. Rename the output files to canonical names

## Prerequisites

- Host tooling installed per [Prerequisites](00-prerequisites.md#host-tooling) (`node`, `npm`, `jq`, `curl`)
- A `combined.json` produced by the chain integration runbook (see [Rollup Creation](01-rollup-creation.md))

## Step 1: Check Out Repository and Install

Clone the `agglayer-contracts` repository at the version that matches this guide:

```shell
# See Component Versions table in 00-prerequisites.md for current values
export agglayer_contracts_version="<agglayer_contracts_version>"
git clone --depth 1 --branch ${agglayer_contracts_version} https://github.com/agglayer/agglayer-contracts
cd agglayer-contracts
npm install
```

## Step 2: Create Parameter File

> [!WARNING]
> The `aggOracleOwner` address will be used on L2. Make sure this address is accessible (you control its private key) on the L2 network, otherwise you will lose the ability to manage the AggOracle.

Copy the example parameter file:

```shell
cp ./tools/createSovereignGenesis/create-genesis-sovereign-params.json.example ./tools/createSovereignGenesis/create-genesis-sovereign-params.json
```

Update the file with relevant information from your `combined.json`. Example configuration:

```json
{
    "rollupManagerAddress": "<polygonRollupManagerAddress-from-combined.json>",
    "rollupID": <rollupID-from-combined.json>,
    "chainID": <l2ChainID-from-combined.json>,
    "gasTokenAddress": "<gasTokenAddress-from-combined.json>",
    "bridgeManager": "<ADMIN_ADDRESS>",
    "sovereignWETHAddress": "0x0000000000000000000000000000000000000000",
    "sovereignWETHAddressIsNotMintable": false,
    "globalExitRootUpdater": "<AGGORACLE_ADDRESS>",
    "globalExitRootRemover": "<ADMIN_ADDRESS>",
    "emergencyBridgePauser": "<ADMIN_ADDRESS>",
    "emergencyBridgeUnpauser": "<ADMIN_ADDRESS>",
    "proxiedTokensManager": "<ADMIN_ADDRESS>",
    "setPreMintAccounts": true,
    "preMintAccounts": [
        {
            "balance": "1000000000000000000",
            "address": "<AGGORACLE_ADDRESS>"
        },
        {
            "balance": "1000000000000000000",
            "address": "<CLAIMTXMANAGER_ADDRESS>"
        }
    ],
    "setTimelockParameters": true,
    "timelockParameters": {
        "adminAddress": "<ADMIN_ADDRESS>",
        "minDelay": 0
    },
    "useAggOracleCommittee": false,
    "aggOracleCommittee": [],
    "quorum": 0,
    "aggOracleOwner": "<ADMIN_ADDRESS>",
    "formatGenesis": "geth"
}
```

> [!NOTE]
> The AggOracle committee is not supported on Besu chains. Keep `useAggOracleCommittee` set to `false`, so a single `AGGORACLE_ADDRESS`, set as `globalExitRootUpdater`, updates the GER on L2.

> [!CAUTION]
> **Unverified:** Why Kurtosis rejects the AggOracle committee for Besu chains, and whether production chains can enable it. This needs confirmation from the Agglayer team.

## Step 3: Download Allocs File

Download the allocs file from the [cdk-contracts-tooling](https://github.com/0xPolygon/cdk-contracts-tooling) repository for your target environment:

- **Bali**: [allocs.json](https://raw.githubusercontent.com/0xPolygon/cdk-contracts-tooling/main/genesis/pp/bali/allocs.json)
- **Cardona**: [allocs.json](https://raw.githubusercontent.com/0xPolygon/cdk-contracts-tooling/main/genesis/pp/cardona/allocs.json)
- **Mainnet**: [allocs.json](https://raw.githubusercontent.com/0xPolygon/cdk-contracts-tooling/main/genesis/pp/mainnet/allocs.json)

Save it as `genesis-base.json` in `./tools/createSovereignGenesis/`:

```shell
# For Bali (example)
curl -o ./tools/createSovereignGenesis/genesis-base.json \
  https://raw.githubusercontent.com/0xPolygon/cdk-contracts-tooling/main/genesis/pp/bali/allocs.json

# For Cardona
# curl -o ./tools/createSovereignGenesis/genesis-base.json \
#   https://raw.githubusercontent.com/0xPolygon/cdk-contracts-tooling/main/genesis/pp/cardona/allocs.json
```

## Step 4: Generate Genesis Files

Run the Hardhat script to assemble the sovereign genesis using your parameter file and the downloaded allocs file (substitute `mainnet` for production deployments):

```shell
npx hardhat run ./tools/createSovereignGenesis/create-sovereign-genesis.ts --network sepolia
```

The script produces `genesis-rollupID-*.json` and `output-rollupID-*.json` files under `./tools/createSovereignGenesis/` (the tool appends your `rollupID` and a datetime to each name).

## Step 5: Rename Outputs

Rename the generated artifacts to the canonical names used by later chapters:

```shell
mv ./tools/createSovereignGenesis/genesis-rollupID-*.json ./tools/createSovereignGenesis/polygon-genesis.json
mv ./tools/createSovereignGenesis/output-rollupID-*.json ./tools/createSovereignGenesis/polygon-genesis-info.json
```

`polygon-genesis-info.json` lists the addresses of the sovereign contracts under `genesisSCNames`. Later chapters read the bridge and GER proxy addresses from it:

```shell
jq -r '.genesisSCNames["AgglayerBridgeL2 proxy"]' ./tools/createSovereignGenesis/polygon-genesis-info.json
jq -r '.genesisSCNames["AgglayerGERL2 proxy"]' ./tools/createSovereignGenesis/polygon-genesis-info.json
```

---

**Next:** [Besu Network Deployment →](03-besu-network.md)
