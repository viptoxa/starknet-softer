import re
import warnings
from typing import Dict, List, Optional, Tuple, Union, cast

import aiohttp
from marshmallow import EXCLUDE

from starknet_py.constants import RPC_CONTRACT_ERROR
from starknet_py.net.client import Client
from starknet_py.net.client_errors import ClientError
from starknet_py.net.client_models import (
    BlockHashAndNumber,
    BlockStateUpdate,
    BlockTransactionTraces,
    Call,
    ContractClass,
    DeclareTransactionResponse,
    DeployAccountTransactionResponse,
    EstimatedFee,
    EventsChunk,
    Hash,
    PendingBlockStateUpdate,
    PendingStarknetBlock,
    PendingStarknetBlockWithTxHashes,
    SentTransactionResponse,
    SierraContractClass,
    StarknetBlock,
    StarknetBlockWithTxHashes,
    SyncStatus,
    Tag,
    Transaction,
    TransactionReceipt,
    TransactionType,
)
from starknet_py.net.http_client import RpcHttpClient
from starknet_py.net.models.transaction import (
    AccountTransaction,
    Declare,
    DeclareSchema,
    DeclareV2,
    DeclareV2Schema,
    DeployAccount,
    Invoke,
)
from starknet_py.net.networks import Network
from starknet_py.net.schemas.rpc import (
    BlockHashAndNumberSchema,
    BlockStateUpdateSchema,
    ContractClassSchema,
    DeclareTransactionResponseSchema,
    DeployAccountTransactionResponseSchema,
    EstimatedFeeSchema,
    EventsChunkSchema,
    PendingBlockStateUpdateSchema,
    PendingStarknetBlockSchema,
    PendingStarknetBlockWithTxHashesSchema,
    PendingTransactionsSchema,
    SentTransactionSchema,
    SierraContractClassSchema,
    StarknetBlockSchema,
    StarknetBlockWithTxHashesSchema,
    SyncStatusSchema,
    TransactionReceiptSchema,
    TypesOfTransactionsSchema,
)
from starknet_py.transaction_errors import TransactionNotReceivedError
from starknet_py.utils.sync import add_sync_methods


@add_sync_methods
class FullNodeClient(Client):
    # pylint: disable=too-many-public-methods
    def __init__(
        self,
        node_url: str,
        net: Optional[Network] = None,
        session: Optional[aiohttp.ClientSession] = None,
        user_agent: Optional[str] = None,
        proxy: Optional[str] = None
    ):
        """
        Client for interacting with Starknet json-rpc interface.

        :param node_url: Url of the node providing rpc interface
        :param net: Starknet network identifier
        :param session: Aiohttp session to be used for request. If not provided, client will create a session for
                        every request. When using a custom session, user is responsible for closing it manually.
        """
        self.url = node_url
        self._client = RpcHttpClient(
            url=node_url,
            session=session,
            user_agent=user_agent,
            proxy=proxy
        )

        if net is not None:
            warnings.warn("Parameter net is deprecated.", category=DeprecationWarning)
        self._net = net

    @property
    def net(self) -> Optional[Network]:
        warnings.warn(
            "Property net is deprecated in the FullNodeClient.",
            category=DeprecationWarning,
        )
        return self._net

    async def get_block(
        self,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> Union[StarknetBlock, PendingStarknetBlock]:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        res = await self._client.call(
            method_name="getBlockWithTxs",
            params=block_identifier,
        )
        if block_identifier == {"block_id": "pending"}:
            return cast(
                PendingStarknetBlock,
                PendingStarknetBlockSchema().load(res, unknown=EXCLUDE),
            )
        res['l1_gas_price'] = int(res['l1_gas_price']['price_in_wei'], 16)
        return cast(StarknetBlock, StarknetBlockSchema().load(res, unknown=EXCLUDE))

    async def get_block_with_txs(
        self,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> Union[StarknetBlock, PendingStarknetBlock]:
        return await self.get_block(block_hash=block_hash, block_number=block_number)

    async def get_block_with_tx_hashes(
        self,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> Union[StarknetBlockWithTxHashes, PendingStarknetBlockWithTxHashes]:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        res = await self._client.call(
            method_name="getBlockWithTxHashes",
            params=block_identifier,
        )

        if block_identifier == {"block_id": "pending"}:
            return cast(
                PendingStarknetBlockWithTxHashes,
                PendingStarknetBlockWithTxHashesSchema().load(res, unknown=EXCLUDE),
            )
        return cast(
            StarknetBlockWithTxHashes,
            StarknetBlockWithTxHashesSchema().load(res, unknown=EXCLUDE),
        )

    async def get_block_traces(
        self,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> BlockTransactionTraces:
        raise NotImplementedError()

    # TODO (#809): add tests with multiple emitted keys
    async def get_events(
        self,
        address: Optional[Hash] = None,
        keys: Optional[List[List[Hash]]] = None,
        *,
        from_block_number: Optional[Union[int, Tag]] = None,
        from_block_hash: Optional[Union[Hash, Tag]] = None,
        to_block_number: Optional[Union[int, Tag]] = None,
        to_block_hash: Optional[Union[Hash, Tag]] = None,
        follow_continuation_token: bool = False,
        continuation_token: Optional[str] = None,
        chunk_size: int = 1,
    ) -> EventsChunk:
        # pylint: disable=too-many-arguments
        """
        :param address: The address of the contract that emitted the event.
        :param keys: List consisting lists of keys by which the events are filtered. They match the keys *by position*,
            e.g. given an event with 3 keys, [[1,2],[],[3]] which should return events that have either 1 or 2 in
            the first key, any value for their second key and 3 for their third key.
        :param from_block_number: Number of the block from which events searched for **starts**
            or literals `"pending"` or `"latest"`. Mutually exclusive with ``from_block_hash`` parameter.
            If not provided, query starts from block 0.
        :param from_block_hash: Hash of the block from which events searched for **starts**
            or literals `"pending"` or `"latest"`. Mutually exclusive with ``from_block_number`` parameter.
            If not provided, query starts from block 0.
        :param to_block_number: Number of the block to which events searched for **end**
            or literals `"pending"` or `"latest"`. Mutually exclusive with ``to_block_hash`` parameter.
            If not provided, query ends at block `"pending"`.
        :param to_block_hash: Hash of the block to which events searched for **end**
            or literals `"pending"` or `"latest"`. Mutually exclusive with ``to_block_number`` parameter.
            If not provided, query ends at block `"pending"`.
        :param follow_continuation_token: Flag deciding whether all events should be collected during one function call,
            defaults to False.
        :param continuation_token: Continuation token from which the returned events start.
        :param chunk_size: Size of chunk of events returned by one ``get_events`` call, defaults to 1 (minimum).

        :return: ``EventsResponse`` dataclass containing events and optional continuation token.
        """

        if chunk_size <= 0:
            raise ValueError("Argument chunk_size must be greater than 0.")

        if keys is None:
            keys = []
        if address is not None:
            address = _to_rpc_felt(address)
        if from_block_number is None and from_block_hash is None:
            from_block_number = 0

        from_block = _get_raw_block_identifier(from_block_hash, from_block_number)
        to_block = _get_raw_block_identifier(to_block_hash, to_block_number)
        keys = [[_to_rpc_felt(key) for key in inner_list] for inner_list in keys]

        events_list = []
        while True:
            events, continuation_token = await self._get_events_chunk(
                from_block=from_block,
                to_block=to_block,
                address=address,
                keys=keys,
                chunk_size=chunk_size,
                continuation_token=continuation_token,
            )
            events_list.extend(events)
            if not follow_continuation_token or continuation_token is None:
                break

        events_response = cast(
            EventsChunk,
            EventsChunkSchema().load(
                {"events": events_list, "continuation_token": continuation_token}
            ),
        )

        return events_response

    async def _get_events_chunk(
        self,
        from_block: Union[dict, Hash, Tag, None],
        to_block: Union[dict, Hash, Tag, None],
        keys: List[List[Hash]],
        chunk_size: int,
        address: Optional[Hash] = None,
        continuation_token: Optional[str] = None,
    ) -> Tuple[list, Optional[str]]:
        # pylint: disable=too-many-arguments
        params = {
            "chunk_size": chunk_size,
            "from_block": from_block,
            "to_block": to_block,
            "keys": keys,
        }
        if continuation_token is not None:
            params["continuation_token"] = continuation_token
        if address is not None:
            params["address"] = address

        res = await self._client.call(
            method_name="getEvents",
            params={"filter": params},
        )

        if "continuation_token" in res:
            return res["events"], res["continuation_token"]
        return res["events"], None

    async def get_state_update(
        self,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> Union[BlockStateUpdate, PendingBlockStateUpdate]:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        res = await self._client.call(
            method_name="getStateUpdate",
            params=block_identifier,
        )

        if block_identifier == {"block_id": "pending"}:
            return cast(
                PendingBlockStateUpdate,
                PendingBlockStateUpdateSchema().load(res, unknown=EXCLUDE),
            )
        return cast(
            BlockStateUpdate, BlockStateUpdateSchema().load(res, unknown=EXCLUDE)
        )

    async def get_storage_at(
        self,
        contract_address: Hash,
        key: int,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> int:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        res = await self._client.call(
            method_name="getStorageAt",
            params={
                "contract_address": _to_rpc_felt(contract_address),
                "key": _to_storage_key(key),
                **block_identifier,
            },
        )
        res = cast(str, res)
        return int(res, 16)

    async def get_transaction(
        self,
        tx_hash: Hash,
    ) -> Transaction:
        try:
            res = await self._client.call(
                method_name="getTransactionByHash",
                params={"transaction_hash": _to_rpc_felt(tx_hash)},
            )
        except ClientError as ex:
            raise TransactionNotReceivedError() from ex
        return cast(Transaction, TypesOfTransactionsSchema().load(res, unknown=EXCLUDE))

    async def get_transaction_receipt(self, tx_hash: Hash) -> TransactionReceipt:
        res = await self._client.call(
            method_name="getTransactionReceipt",
            params={"transaction_hash": _to_rpc_felt(tx_hash)},
        )
        return cast(
            TransactionReceipt, TransactionReceiptSchema().load(res, unknown=EXCLUDE)
        )

    async def estimate_fee(
        self,
        tx: Union[AccountTransaction, List[AccountTransaction]],
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> Union[EstimatedFee, List[EstimatedFee]]:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        if single_transaction := isinstance(tx, AccountTransaction):
            tx = [tx]

        res = await self._client.call(
            method_name="estimateFee",
            params={
                "request": [_create_broadcasted_txn(transaction=t) for t in tx],
                **block_identifier,
            },
        )

        if single_transaction:
            res = res[0]

        return cast(
            EstimatedFee,
            EstimatedFeeSchema().load(
                res, unknown=EXCLUDE, many=(not single_transaction)
            ),
        )

    async def estimate_message_fee(
        self,
        from_address: str,
        to_address: Hash,
        entry_point_selector: Hash,
        payload: List[Hash],
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> EstimatedFee:
        # pylint: disable=too-many-arguments
        """
        :param from_address: The address of the L1 (Ethereum) contract sending the message.
        :param to_address: The target L2 (Starknet) address the message is sent to.
        :param entry_point_selector: The selector of the l1_handler in invoke in the target contract.
        :param payload: Payload of the message.
        :param block_hash: Hash of the requested block or literals `"pending"` or `"latest"`.
            Mutually exclusive with ``block_number`` parameter. If not provided, queries block `"pending"`.
        :param block_number: Number (height) of the requested block or literals `"pending"` or `"latest"`.
            Mutually exclusive with ``block_hash`` parameter. If not provided, queries block `"pending"`.
        """
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        assert _is_valid_eth_address(
            from_address
        ), f"Argument 'from_address': {from_address} is not a valid Ethereum address."

        message_body = {
            "from_address": from_address,
            "to_address": _to_rpc_felt(to_address),
            "entry_point_selector": _to_rpc_felt(entry_point_selector),
            "payload": [_to_rpc_felt(x) for x in payload],
        }

        try:
            res = await self._client.call(
                method_name="estimateMessageFee",
                params={
                    "message": message_body,
                    **block_identifier,
                },
            )
            return cast(EstimatedFee, EstimatedFeeSchema().load(res, unknown=EXCLUDE))
        except ClientError as err:
            if err.code == RPC_CONTRACT_ERROR:
                raise ClientError(
                    err.message
                    + f" Note that your ETH address ('from_address': {from_address}) might be invalid"
                ) from err
            raise err

    async def get_block_number(self) -> int:
        """Get the most recent accepted block number"""
        return await self._client.call(method_name="blockNumber", params={})

    async def get_block_hash_and_number(self) -> BlockHashAndNumber:
        """Get the most recent accepted block hash and number"""
        res = await self._client.call(method_name="blockHashAndNumber", params={})
        return cast(BlockHashAndNumber, BlockHashAndNumberSchema().load(res))

    async def get_chain_id(self) -> int:
        """Return the currently configured Starknet chain id"""
        return await self._client.call(method_name="chainId", params={})

    async def get_syncing_status(self) -> Union[bool, SyncStatus]:
        """Returns an object about the sync status, or false if the node is not syncing"""
        sync_status = await self._client.call(method_name="syncing", params={})
        if isinstance(sync_status, bool):
            return sync_status
        return cast(SyncStatus, SyncStatusSchema().load(sync_status))

    async def call_contract(
        self,
        call: Call,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> List[int]:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )
        res = await self._client.call(
            method_name="call",
            params={
                "request": {
                    "contract_address": _to_rpc_felt(call.to_addr),
                    "entry_point_selector": _to_rpc_felt(call.selector),
                    "calldata": [_to_rpc_felt(i1) for i1 in call.calldata],
                },
                **block_identifier,
            },
        )
        return [int(i, 16) for i in res]

    async def send_transaction(self, transaction: Invoke) -> SentTransactionResponse:
        params = _create_broadcasted_txn(transaction=transaction)

        res = await self._client.call(
            method_name="addInvokeTransaction",
            params={"invoke_transaction": params},
        )

        return cast(
            SentTransactionResponse, SentTransactionSchema().load(res, unknown=EXCLUDE)
        )

    async def deploy_account(
        self, transaction: DeployAccount
    ) -> DeployAccountTransactionResponse:
        params = _create_broadcasted_txn(transaction=transaction)

        res = await self._client.call(
            method_name="addDeployAccountTransaction",
            params={"deploy_account_transaction": params},
        )

        return cast(
            DeployAccountTransactionResponse,
            DeployAccountTransactionResponseSchema().load(res, unknown=EXCLUDE),
        )

    async def declare(
        self, transaction: Union[Declare, DeclareV2]
    ) -> DeclareTransactionResponse:
        params = _create_broadcasted_txn(transaction=transaction)

        res = await self._client.call(
            method_name="addDeclareTransaction",
            params={"declare_transaction": {**params}},
        )

        return cast(
            DeclareTransactionResponse,
            DeclareTransactionResponseSchema().load(res, unknown=EXCLUDE),
        )

    async def get_class_hash_at(
        self,
        contract_address: Hash,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> int:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )
        res = await self._client.call(
            method_name="getClassHashAt",
            params={
                "contract_address": _to_rpc_felt(contract_address),
                **block_identifier,
            },
        )
        res = cast(str, res)
        return int(res, 16)

    async def get_class_by_hash(
        self,
        class_hash: Hash,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> Union[SierraContractClass, ContractClass]:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        res = await self._client.call(
            method_name="getClass",
            params={
                "class_hash": _to_rpc_felt(class_hash),
                **block_identifier,
            },
        )

        if "sierra_program" in res:
            return cast(
                SierraContractClass,
                SierraContractClassSchema().load(res, unknown=EXCLUDE),
            )
        return cast(ContractClass, ContractClassSchema().load(res, unknown=EXCLUDE))

    # Only RPC methods

    async def get_transaction_by_block_id(
        self,
        index: int,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> Transaction:
        """
        Get the details of transaction in block identified by block_hash and transaction index.

        :param index: Index of the transaction
        :param block_hash: Hash of the block
        :param block_number: Block's number or literals `"pending"` or `"latest"`
        :return: Transaction object
        """
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        res = await self._client.call(
            method_name="getTransactionByBlockIdAndIndex",
            params={
                **block_identifier,
                "index": index,
            },
        )
        return cast(Transaction, TypesOfTransactionsSchema().load(res, unknown=EXCLUDE))

    async def get_block_transaction_count(
        self,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> int:
        """
        Get the number of transactions in a block given a block id

        :param block_hash: Block's hash or literals `"pending"` or `"latest"`
        :param block_number: Block's number or literals `"pending"` or `"latest"`
        :return: Number of transactions in the designated block
        """
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        res = await self._client.call(
            method_name="getBlockTransactionCount",
            params=block_identifier,
        )
        res = cast(int, res)
        return res

    async def get_class_at(
        self,
        contract_address: Hash,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> Union[SierraContractClass, ContractClass]:
        """
        Get the contract class definition in the given block at the given address

        :param contract_address: The address of the contract whose class definition will be returned
        :param block_hash: Block's hash or literals `"pending"` or `"latest"`
        :param block_number: Block's number or literals `"pending"` or `"latest"`
        :return: Contract declared to Starknet
        """
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )

        res = await self._client.call(
            method_name="getClassAt",
            params={
                **block_identifier,
                "contract_address": _to_rpc_felt(contract_address),
            },
        )

        if "sierra_program" in res:
            return cast(
                SierraContractClass,
                SierraContractClassSchema().load(res, unknown=EXCLUDE),
            )
        return cast(ContractClass, ContractClassSchema().load(res, unknown=EXCLUDE))

    async def get_pending_transactions(self) -> List[Transaction]:
        """
        Returns the transactions in the transaction pool, recognized by sequencer

        :returns: List of transactions
        """
        res = await self._client.call(method_name="pendingTransactions", params={})
        res = {"pending_transactions": res}

        return cast(
            List[Transaction], PendingTransactionsSchema().load(res, unknown=EXCLUDE)
        )

    async def get_contract_nonce(
        self,
        contract_address: Hash,
        block_hash: Optional[Union[Hash, Tag]] = None,
        block_number: Optional[Union[int, Tag]] = None,
    ) -> int:
        block_identifier = get_block_identifier(
            block_hash=block_hash, block_number=block_number
        )
        res = await self._client.call(
            method_name="getNonce",
            params={
                "contract_address": _to_rpc_felt(contract_address),
                **block_identifier,
            },
        )
        res = cast(str, res)
        return int(res, 16)


def get_block_identifier(
    block_hash: Optional[Union[Hash, Tag]] = None,
    block_number: Optional[Union[int, Tag]] = None,
) -> dict:
    return {"block_id": _get_raw_block_identifier(block_hash, block_number)}


def _get_raw_block_identifier(
    block_hash: Optional[Union[Hash, Tag]] = None,
    block_number: Optional[Union[int, Tag]] = None,
) -> Union[dict, Hash, Tag, None]:
    if block_hash is not None and block_number is not None:
        raise ValueError(
            "Arguments block_hash and block_number are mutually exclusive."
        )

    if block_hash in ("latest", "pending") or block_number in ("latest", "pending"):
        return block_hash or block_number

    if block_hash is not None:
        return {"block_hash": _to_rpc_felt(block_hash)}

    if block_number is not None:
        return {"block_number": block_number}

    return "pending"


def _create_broadcasted_txn(transaction: AccountTransaction) -> dict:
    txn_map = {
        TransactionType.DECLARE: _create_broadcasted_declare_properties,
        TransactionType.INVOKE: _create_broadcasted_invoke_properties,
        TransactionType.DEPLOY_ACCOUNT: _create_broadcasted_deploy_account_properties,
    }

    common_properties = _create_broadcasted_txn_common_properties(transaction)
    transaction_specific_properties = txn_map[transaction.type](transaction)

    return {
        **common_properties,
        **transaction_specific_properties,
    }


def _create_broadcasted_declare_properties(
    transaction: Union[Declare, DeclareV2]
) -> dict:
    if isinstance(transaction, DeclareV2):
        return _create_broadcasted_declare_v2_properties(transaction)

    contract_class = cast(Dict, DeclareSchema().dump(obj=transaction))["contract_class"]
    declare_properties = {
        "contract_class": {
            "entry_points_by_type": contract_class["entry_points_by_type"],
            "program": contract_class["program"],
        },
        "sender_address": _to_rpc_felt(transaction.sender_address),
    }
    if contract_class["abi"] is not None:
        declare_properties["contract_class"]["abi"] = contract_class["abi"]

    return declare_properties


def _create_broadcasted_declare_v2_properties(transaction: DeclareV2) -> dict:
    contract_class = cast(Dict, DeclareV2Schema().dump(obj=transaction))[
        "contract_class"
    ]
    declare_v2_properties = {
        "contract_class": {
            "entry_points_by_type": contract_class["entry_points_by_type"],
            "sierra_program": contract_class["sierra_program"],
            "contract_class_version": contract_class["contract_class_version"],
        },
        "sender_address": _to_rpc_felt(transaction.sender_address),
        "compiled_class_hash": _to_rpc_felt(transaction.compiled_class_hash),
    }
    if contract_class["abi"] is not None:
        declare_v2_properties["contract_class"]["abi"] = contract_class["abi"]

    return declare_v2_properties


def _create_broadcasted_invoke_properties(transaction: Invoke) -> dict:
    invoke_properties = {
        "sender_address": _to_rpc_felt(transaction.sender_address),
        "calldata": [_to_rpc_felt(data) for data in transaction.calldata],
    }
    return invoke_properties


def _create_broadcasted_deploy_account_properties(transaction: DeployAccount) -> dict:
    deploy_account_txn_properties = {
        "contract_address_salt": _to_rpc_felt(transaction.contract_address_salt),
        "constructor_calldata": [
            _to_rpc_felt(data) for data in transaction.constructor_calldata
        ],
        "class_hash": _to_rpc_felt(transaction.class_hash),
    }
    return deploy_account_txn_properties


def _create_broadcasted_txn_common_properties(transaction: AccountTransaction) -> dict:
    broadcasted_txn_common_properties = {
        "type": transaction.type.name,
        "max_fee": _to_rpc_felt(transaction.max_fee),
        "version": _to_rpc_felt(transaction.version),
        "signature": [_to_rpc_felt(sig) for sig in transaction.signature],
        "nonce": _to_rpc_felt(transaction.nonce),
    }
    return broadcasted_txn_common_properties


def _to_storage_key(key: int) -> str:
    """
    Convert a value to RPC storage key matching a ``^0x0[0-7]{1}[a-fA-F0-9]{0,62}$`` pattern.

    :param key: The key to convert.
    :return: RPC storage key representation of the key.
    """

    hashed_key = hex(key)[2:]

    if hashed_key[0] not in ("0", "1", "2", "3", "4", "5", "6", "7"):
        hashed_key = "0" + hashed_key

    hashed_key = "0x0" + hashed_key

    if not re.match(r"^0x0[0-7]{1}[a-fA-F0-9]{0,62}$", hashed_key):
        raise ValueError(f"Value {key} cannot be represented as RPC storage key.")

    return hashed_key


def _to_rpc_felt(value: Hash) -> str:
    """
    Convert the value to RPC felt matching a ``^0x(0|[a-fA-F1-9]{1}[a-fA-F0-9]{0,62})$`` pattern.

    :param value: The value to convert.
    :return: RPC felt representation of the value.
    """
    if isinstance(value, str):
        value = int(value, 16)

    rpc_felt = hex(value)
    assert re.match(r"^0x(0|[a-fA-F1-9]{1}[a-fA-F0-9]{0,62})$", rpc_felt)
    return rpc_felt


def _is_valid_eth_address(address: str) -> bool:
    """
    A function checking if an address matches Ethereum address regex. Note that it doesn't validate any checksums etc.
    """
    return bool(re.fullmatch("^0x[a-fA-F0-9]{40}$", address))
