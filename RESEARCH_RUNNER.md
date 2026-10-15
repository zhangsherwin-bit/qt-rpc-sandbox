# QT read-only API/RPC runner

This is a bounded, public-data diagnostic run on GitHub-hosted Actions, controlled from the GPT-6 Pro chat. No API keys, wallets, signatures, principal or transactions.

## Operations

- Morpho Midnight REST: four Base USDC loan-token market states and offer-book sides
- Base JSON-RPC: `eth_chainId`, `eth_blockNumber`, `eth_getBlockByNumber`, `eth_getCode`, `eth_call`
- Public core address only; historical Base block 52,601,237 is checked separately
- Maximum 30 HTTP requests, body limit 1 MB, 0.45-second minimum pause
- Raw request/response bodies, SHA-256 hashes, errors, and `evidence/report.json` saved as a seven-day GitHub Actions artifact
- A failing provider request is reported as missing evidence, not zero profit

## Running

The `.github/workflows/qt-rpc-readonly.yml` job is triggered by the pull request. Its build/test and data collection steps require only Python's standard library.

This is *not* a real EVM trading simulation, a fully reconciled market census, an executable offer check or a profitability measurement. REST offers are not synchronized atomically with the RPC state.

Source is in `src/qt_probe.py`. Run offline tests using `python3 -m unittest discover -s tests -v`. No transactions are signed or broadcast.
