# Verification and Operations

This chapter confirms that the chain settles on the Agglayer, then covers the day-to-day tasks of running it: monitoring, validator set changes, Besu upgrades, and key rotation.

## Verification Checklist

Set the endpoints and addresses used below:

```shell
export l1_rpc_url="https://<your_l1_rpc>"
export besu_rpc_url="http://<besu_rpc_hostname>:8545"
export bridge_service_url="http://<bridge_service_hostname>:<bridge_service_port>"
export l1_bridge_addr="<L1_BRIDGE_ADDRESS-from-combined.json>"
export sovereign_bridge_proxy_addr="<AgglayerBridgeL2-proxy-from-polygon-genesis-info.json>"
export l2_network_id=<rollupID-from-combined.json>
```

Work through the checks in order. Each one depends on the previous checks passing.

1. **Blocks advance on the Besu RPC node.** Run `cast block-number --rpc-url "${besu_rpc_url}"` twice, a few seconds apart. The second number is higher.

2. **The `finalized` tag returns an error.** Run `cast block finalized --rpc-url "${besu_rpc_url}"`. Besu answers with error `-39001` ("Unknown block"). This is expected QBFT behavior, not a fault: QBFT finalizes every block when it is produced, and aggkit tracks `latest` instead (see [chapter 05](05-polygon-stack.md#besu-specific-configuration)).

3. **aggkit updates GERs on L2 and sends certificates.** The aggkit logs show the Aggoracle sending GER update transactions to L2 and the aggsender sending certificates to the Agglayer. You can also confirm GER updates on-chain: the Aggoracle's L2 nonce increases as it writes GERs.

   ```shell
   cast nonce "<AGGORACLE_ADDRESS>" --rpc-url "${besu_rpc_url}"
   ```

4. **An L1 to L2 deposit arrives.** Bridge a small amount of ETH from L1 to an L2 address you control:

   ```shell
   cast send "${l1_bridge_addr}" \
     "bridgeAsset(uint32,address,uint256,address,bool,bytes)" \
     "${l2_network_id}" "<L2_RECIPIENT_ADDRESS>" 10000000000000000 \
     0x0000000000000000000000000000000000000000 true 0x \
     --value 10000000000000000 \
     --rpc-url "${l1_rpc_url}" \
     --private-key 0x...
   ```

   The bridge service lists the deposit, and its `claim_tx_hash` fills in once the ClaimTxManager claims it on L2. The recipient's L2 balance then increases:

   ```shell
   curl -s "${bridge_service_url}/bridges/<L2_RECIPIENT_ADDRESS>" | jq
   cast balance "<L2_RECIPIENT_ADDRESS>" --rpc-url "${besu_rpc_url}"
   ```

5. **An L2 to L1 withdrawal arrives after the next certificate settles.** Bridge from L2 back to L1 (network ID `0`):

   ```shell
   cast send "${sovereign_bridge_proxy_addr}" \
     "bridgeAsset(uint32,address,uint256,address,bool,bytes)" \
     0 "<L1_RECIPIENT_ADDRESS>" 1000000000000000 \
     0x0000000000000000000000000000000000000000 true 0x \
     --value 1000000000000000 \
     --rpc-url "${besu_rpc_url}" \
     --private-key 0x...
   ```

   Once aggkit has sent a certificate that includes this bridge and the certificate has settled, the bridge service marks the deposit `ready_for_claim`. Fetch the proof with the deposit's `deposit_cnt`, then call `claimAsset` on the L1 bridge with the proof, the deposit's `global_index`, and the exit roots from the response:

   ```shell
   curl -s "${bridge_service_url}/bridges/<L1_RECIPIENT_ADDRESS>" | jq
   curl -s "${bridge_service_url}/merkle-proof?net_id=${l2_network_id}&deposit_cnt=<deposit_cnt>" | jq
   ```

6. **The first certificate settles on the Agglayer.** Query the Agglayer JSON-RPC API with your rollup ID:

   ```shell
   # Bali: https://agglayer-dev.polygon.technology
   # Cardona: https://agglayer-test.polygon.technology
   # Mainnet: https://agglayer.polygon.technology
   export agglayer_rpc_url="https://agglayer-dev.polygon.technology"

   # Latest certificate the Agglayer has received, in any state
   cast rpc interop_getLatestKnownCertificateHeader "${l2_network_id}" --rpc-url "${agglayer_rpc_url}" | jq

   # Latest certificate that has settled on L1
   cast rpc interop_getLatestSettledCertificateHeader "${l2_network_id}" --rpc-url "${agglayer_rpc_url}" | jq '{height, status, certificate_id, settlement_tx_hash}'
   ```

   The settled header shows `"status": "Settled"` and a `settlement_tx_hash` on L1. Before your first certificate settles, `interop_getLatestSettledCertificateHeader` returns `null`. A certificate moves through `Pending`, `Proven`, and `Candidate` to `Settled`. `interop_getLatestPendingCertificateHeader` shows one still in progress; a failed certificate shows `InError` with the error in its `status`. `interop_getNetworkInfo` returns the settled height and the latest pending status in one call. A settled certificate is also what makes the withdrawal in check 5 claimable. The [Agglayer observability docs](https://docs.polygon.technology/interoperability/agglayer/observability) cover the certificate lifecycle in more detail.

## Operations

### Monitoring

- **Besu:** each node serves metrics in Prometheus format on port `9545` (`--metrics-enabled`). Scrape every validator and the RPC node, and alert when block height stops advancing or peer count drops.
- **aggkit:** the `[Profiling]` section of the aggkit configuration enables a profiling server (`ProfilingHost`, `ProfilingPort`, default port `6060`). Keep it on an internal network.
- **Agglayer:** see the [Agglayer observability docs](https://docs.polygon.technology/interoperability/agglayer/observability) for certificate status.

### Changing the validator set

QBFT adds or removes a validator by vote. Each current validator proposes the change through its own RPC, with the validator address and `true` to add or `false` to remove:

```shell
# Run on each validator host, against that validator's local RPC
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"qbft_proposeValidatorVote","params":["<VALIDATOR_ADDRESS>", true],"id":1}' \
  http://127.0.0.1:8545
```

A majority of the current validators must submit the same vote before the change takes effect. When you add a validator, start its node from the same `genesis.json` and add its enode URL to every node's static peer list (and to the node allowlist if you use node permissioning). Confirm the change with `qbft_getValidatorsByBlockNumber` as in [chapter 03, step 5](03-besu-network.md#step-5-confirm-the-chain-is-producing-blocks).

> **Source of Truth**: See the [Besu QBFT documentation](https://besu.hyperledger.org/private-networks/how-to/configure/consensus/qbft) for validator voting and its limits.

### Upgrading Besu

Upgrade one node at a time. After each node restarts on the new version, confirm it has peers and imports new blocks before you move to the next node. With four validators, the chain keeps producing blocks while one is down. Keep the running version in step with the pin in [Prerequisites](00-prerequisites.md#component-versions).

### Key rotation

- **Validator node keys:** add a validator with the new key and remove the old one, both through the validator vote above. Do the add first, so the set never shrinks below the size you need.
- **Aggsender and aggsender validator keys:** these keys are registered as signers on the `AggchainECDSAMultisig` contract. Change them by updating the signer set, as described next, then restart the affected service with the new keystore.

### Updating the signer set

Only the aggchain manager can change the signers or the threshold. That is the EOA you supplied as `initializeBytesAggchain` in the [chain integration runbook](01-rollup-creation.md) and used to run the initialization script in [chapter 04](04-rollup-initialization.md). It is a separate role from `rollupAdminAddress`. Read the current holder from the rollup contract:

```shell
export rollup_addr="<sovereign_rollup_address>"   # see chapter 05
cast call "${rollup_addr}" "aggchainManager()(address)" --rpc-url "${l1_rpc_url}"
```

Read the current signer list and threshold before every change. Removals refer to signers by their position in this list:

```shell
cast call "${rollup_addr}" "getAggchainSignerInfos()((address,string)[])" --rpc-url "${l1_rpc_url}"
cast call "${rollup_addr}" "threshold()(uint256)" --rpc-url "${l1_rpc_url}"
```

`updateSignersAndThreshold` removes signers, appends new ones, and sets the new threshold in a single transaction:

```shell
cast send "${rollup_addr}" \
  "updateSignersAndThreshold((address,uint256)[],(address,string)[],uint256)" \
  "[(<SIGNER_TO_REMOVE>,<its_index>)]" \
  "[(<NEW_SIGNER_ADDRESS>,\"https://<new_signer_host>:<validator_grpc_port>\")]" \
  <new_threshold> \
  --rpc-url "${l1_rpc_url}" \
  --private-key 0x...   # aggchain manager key
```

The contract enforces these rules:

- Removals are `(address, index)` pairs. When you remove several signers, list them in strictly descending index order, or the call reverts with `IndicesNotInDescendingOrder`.
- Removing a signer moves the last signer into the freed position, and new signers are appended at the end.
- The new threshold must be at least 1 and at most the new number of signers. A `url` cannot be empty, and the list holds at most 255 signers.

Because aggkit requires the proposer's `AGGSENDER_ADDRESS` to stay at index 0, the swap-on-remove rule matters. Removing or adding validators at other positions leaves the proposer in place. To rotate the proposer's own key, remove every signer (highest index first) and add the full list back in one call, with the new `AGGSENDER_ADDRESS` first, then restart the aggsender with the new keystore.

The aggsender reads the committee from the contract for each certificate, so validators added or removed take effect on the next certificate without a proposer restart.

This applies only while `useDefaultSigners` is `false`, as set in chapter 04. With `useDefaultSigners` set to `true`, the contract uses the AgglayerGateway's default signer set and ignores its own list.

To hand the aggchain manager role to another account, such as a consortium multisig, the current manager calls `transferAggchainManagerRole(address)` and the new account then calls `acceptAggchainManagerRole()`.

---

**Next:** [Consortium Configuration →](07-consortium-configuration.md) *(consortium only)* - single-operator deployments end here.
