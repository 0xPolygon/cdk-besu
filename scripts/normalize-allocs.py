#!/usr/bin/env python3
"""Normalize the createSovereignGenesis output into a Besu genesis "alloc" map.

The agglayer-contracts createSovereignGenesis tool can emit its predeployed
accounts in several shapes. This script accepts each of them and writes a flat
account map keyed by lowercase 0x addresses, with hex "balance" and "nonce",
"code", and "storage", which is the form the Besu genesis "alloc" field expects.

Accepted input shapes:
  - {"genesis": [{"address", "balance", "nonce", "bytecode" | "code", "storage"}, ...]}
  - {"genesis": {"alloc": {<address>: {...}, ...}}}
  - {<address>: {...}, ...}

Derived from 0xPolygon/kurtosis-cdk static_files/contracts/create_op_allocs.py.

Usage: normalize-allocs.py <input_genesis.json> <output_allocs.json>
"""

import json
import sys

USAGE = "usage: normalize-allocs.py <input_genesis.json> <output_allocs.json>"


def to_hex(value, field, addr):
    """Return a quantity given as a hex string, decimal string, or int as a hex string."""
    try:
        if isinstance(value, str) and value.lower().startswith("0x"):
            return hex(int(value, 16))
        return hex(int(value))
    except (TypeError, ValueError):
        raise ValueError(f"invalid {field} {value!r} for account {addr}")


def normalize_address(addr):
    if not isinstance(addr, str) or not addr:
        raise ValueError(f"invalid account address {addr!r}")
    addr = addr.lower()
    return addr if addr.startswith("0x") else "0x" + addr


def normalize_account(addr, data):
    if not isinstance(data, dict):
        raise ValueError(f"account {addr} is not a JSON object")
    account = {"balance": to_hex(data.get("balance", "0x0"), "balance", addr)}
    if "nonce" in data:
        account["nonce"] = to_hex(data["nonce"], "nonce", addr)
    if "bytecode" in data:
        account["code"] = data["bytecode"]
    if "code" in data:
        account["code"] = data["code"]
    if "storage" in data:
        account["storage"] = data["storage"]
    return account


def select_accounts(doc):
    """Return (address, data) pairs for whichever input shape doc uses."""
    if not isinstance(doc, dict):
        raise ValueError("expected a JSON object at the top level")

    if "genesis" in doc:
        genesis = doc["genesis"]
        if isinstance(genesis, list):
            return [
                (item["address"], item)
                for item in genesis
                if isinstance(item, dict) and "address" in item
            ]
        if isinstance(genesis, dict) and isinstance(genesis.get("alloc"), dict):
            return list(genesis["alloc"].items())
        raise ValueError(
            "unrecognized 'genesis' field: expected a list of accounts or an object with an 'alloc' map"
        )

    if all(isinstance(value, dict) for value in doc.values()):
        return list(doc.items())

    raise ValueError(
        "unrecognized input shape: expected a 'genesis' list, a 'genesis.alloc' map, or a bare account map"
    )


def main(argv):
    if len(argv) != 3 or argv[1] in ("-h", "--help"):
        print(USAGE, file=sys.stderr)
        return 2

    input_path, output_path = argv[1], argv[2]
    try:
        with open(input_path, "r") as f:
            doc = json.load(f)
        allocs = {}
        for addr, data in select_accounts(doc):
            addr = normalize_address(addr)
            allocs[addr] = normalize_account(addr, data)
    except (OSError, json.JSONDecodeError, ValueError) as err:
        print(f"error: {input_path}: {err}", file=sys.stderr)
        return 1

    if not allocs:
        print(f"error: {input_path}: no accounts found", file=sys.stderr)
        return 1

    with open(output_path, "w") as f:
        json.dump(allocs, f, indent=4)
        f.write("\n")
    print(f"Wrote {len(allocs)} accounts to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
