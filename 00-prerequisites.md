# Prerequisites

Reference material for the deployment: supported L1s, host tooling, component versions, secrets handling, and the wallet accounts you'll need to fund.

## Supported L1s

This guide targets the following L1 networks:

| L1 | Chain ID |
|---|---|
| Sepolia | `11155111` |
| Ethereum mainnet | `1` |

Examples in subsequent chapters use Sepolia by default. Substitute the mainnet chain ID and an RPC endpoint when deploying to mainnet.

## Host Tooling

Install the following on the machine you'll run the deployment from:

| Tool | Purpose | Notes |
|---|---|---|
| `docker` | Run Besu, aggkit, and the zkEVM Bridge Service containers | Required |
| `node` + `npm` | Run the Hardhat scripts in `agglayer-contracts` | Node.js 20 (LTS) or later recommended |
| `foundry` (`cast`) | On-chain calls and chain checks in chapters 03 to 06 | Required |
| `jq` | Manipulate genesis JSON | Required |
| `curl` | Download allocs files and send JSON-RPC requests | Required |
| `git` | Clone `agglayer-contracts` | Required |
| `python3` | Run `scripts/normalize-allocs.py` in chapter 03 | Required; standard library only |
| Besu CLI | Genesis generation, `extraData` encoding, and address export | Run through the `hyperledger/besu` Docker image; no separate install |

## Component Versions

**Besu**

| Component | Version | Docker Image |
|---|---|---|
| besu | 26.9.0 | `hyperledger/besu` |

**Polygon Stack**

| Component | Version | Docker Image |
|---|---|---|
| agglayer-contracts | v12.2.3 | - |
| aggkit | 0.10.0 | `ghcr.io/agglayer/aggkit` |
| zkevm-bridge-service | see note | `hermeznetwork/zkevm-bridge-service` |

> [!CAUTION]
> **Unverified:** Whether the aggkit 0.10.0 image tag carries a `v` prefix (`0.10.0` or `v0.10.0`). Check the tags on `ghcr.io/agglayer/aggkit` before you pull.

> [!CAUTION]
> **Unverified:** Which zkevm-bridge-service version to pin. Kurtosis tests `0.6.4-RC2`; the latest stable release is `v0.6.3`.

> [!WARNING]
> Use aggkit 0.9 or later. Earlier versions recompute L2 block hashes with go-ethereum header hashing, which never matches a QBFT block hash, so the L2 bridge syncer drops every block that carries bridge events and aggkit never builds a certificate.

## Secrets Handling

This guide shows commands that pass `--private-key 0x...` directly on the command line. That's fine for an isolated devnet, but for testnet and mainnet:

- Use a **keystore** (`cast wallet`) or a **hardware wallet** instead of literal private keys.
- Never paste a real private key into a shared terminal, screenshot, or chat.
- Never commit `.env` files containing private keys; add them to `.gitignore`.
- Treat the `DEPLOYER`, `ADMIN`, and Aggchain manager keys as the most sensitive. Compromise of any of them is unrecoverable.
- Treat Besu validator node keys (the `key` files from chapter 03) as sensitive. A leaked validator node key lets an attacker sign blocks as that validator.

## Wallet Accounts

You will need funded wallet accounts to deploy and operate the network.

**Common**

| Role      | Variable Name      | L1 Funds Required | L2 Funds Required |
|-----------|--------------------|:-----------------:|:-----------------:|
| Deployer  | `DEPLOYER_ADDRESS` |        ✅         |        ❌         |

**Polygon Stack**

| Role | Variable Name | L1 Funds Required | L2 Funds Required |
|---|---|:-:|:-:|
| Aggoracle | `AGGORACLE_ADDRESS` | ❌ | ✅ |
| Aggsender | `AGGSENDER_ADDRESS` | ❌ | ❌ |
| ClaimTxManager | `CLAIMTXMANAGER_ADDRESS` | ❌ | ✅ |
| Admin | `ADMIN_ADDRESS` | ❌ | ❌ |
| Aggsender validator *(consortium only)* | `AGGSENDER_VALIDATOR_<n>_ADDRESS` | ❌ | ❌ |

**Besu**

| Role | Variable Name | L1 Funds Required | L2 Funds Required |
|---|---|:-:|:-:|
| QBFT validator node key | `VALIDATOR_<n>_ADDRESS` | ❌ | ❌ |

> [!NOTE]
> Validator node keys identify Besu nodes and sign blocks. They are not funded accounts.

> [!TIP]
> The fastest way to get funds on L2 for devnets and testnets is to prefund accounts during genesis generation. When you follow step 2 (**[Genesis Generation](02-genesis.md)**), add any accounts you want funded directly to the genesis file with the desired balance. With the chapter 03 default (`zeroBaseFee: true`), transactions on L2 cost no gas, so the L2 funding for the Aggoracle and ClaimTxManager is a safeguard in case you later set a nonzero gas price.

---

**Next:** [Rollup Creation →](01-rollup-creation.md)
