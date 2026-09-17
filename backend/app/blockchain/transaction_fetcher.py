import asyncio
import json

from app.blockchain.chains import Chain
from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.blockchain import RawTransaction


class TransactionUnavailable(Exception):
    pass


async def fetch_transaction(rpc: RpcClient, chain: Chain, tx_hash: str) -> RawTransaction:
    network, transaction, receipt = await asyncio.gather(
        rpc.call("eth_chainId", []),
        rpc.call("eth_getTransactionByHash", [tx_hash]),
        rpc.call("eth_getTransactionReceipt", [tx_hash]),
    )
    if int(network, 16) != chain.chain_id:
        raise RpcError("RPC network does not match the selected chain.")
    if transaction is None:
        raise TransactionUnavailable("Transaction not found on this network.")
    if receipt is None or transaction.get("blockNumber") is None:
        raise TransactionUnavailable("Transaction is pending; analyze after inclusion in a block.")
    block = await rpc.call("eth_getBlockByNumber", [receipt["blockNumber"], False])
    if not block:
        raise RpcError("Transaction block is unavailable.")
    if (
        transaction["hash"].lower() != tx_hash.lower()
        or receipt["transactionHash"].lower() != tx_hash.lower()
        or transaction["blockHash"] != receipt["blockHash"]
        or block["hash"] != receipt["blockHash"]
    ):
        raise RpcError("Inconsistent transaction evidence; possible chain reorganization.")
    return RawTransaction(
        chain=chain.slug,
        tx_hash=tx_hash.lower(),
        transaction_json=json.dumps(transaction),
        receipt_json=json.dumps(receipt),
        block_json=json.dumps(block),
    )
