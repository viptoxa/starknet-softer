import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

from hexbytes import HexBytes
from starknet_py.net.client_models import TransactionExecutionStatus
from web3 import Web3

import constants
import enums
import utils
from logger import logging


class ContractTypes(enums.AutoEnum):
    ROUTER = enums.auto()


CONTRACT_ADRESSES = {
    ContractTypes.ROUTER: {
        enums.NetworkNames.Starknet: '0x0173f81c529191726c6e7287e24626fe24760ac44dae2a1f7e02080230f8458b',
        enums.NetworkNames.StarknetTestnet: '0x0457bf9a97e854007039c43a6cc1a81464bd2a4b907594dabc9132c162563eb3',
        enums.NetworkNames.ETH: '0xD9D74a29307cc6Fc8BF424ee4217f1A587FBc8Dc',
        enums.NetworkNames.Goerli: '0xD9D74a29307cc6Fc8BF424ee4217f1A587FBc8Dc',
        enums.NetworkNames.Arbitrum: '0xD9D74a29307cc6Fc8BF424ee4217f1A587FBc8Dc',
        enums.NetworkNames.ArbitrumTestnet: '0x1AC6a2965Bd55376ec27338F45cfBa55d8Ba380a',
        enums.NetworkNames.Optimism: '0xD9D74a29307cc6Fc8BF424ee4217f1A587FBc8Dc',
        enums.NetworkNames.OptimismTestnet: '0x89EBCf7253f5E27b45E82cd228c977Fd03E47f54'
    }
}

NETWORK_IDENTIFIERS = {
    enums.NetworkNames.ETH: 9001,
    enums.NetworkNames.Goerli: 9005,
    enums.NetworkNames.Starknet: 9004,
    enums.NetworkNames.StarknetTestnet: 9044,
    enums.NetworkNames.Arbitrum: 9002,
    enums.NetworkNames.ArbitrumTestnet: 9022,
    enums.NetworkNames.Optimism: 9007,
    enums.NetworkNames.OptimismTestnet: 9077,
}


@dataclass
class MakerData:
    addresses: tuple[str]
    min_price: float
    max_price: float
    trading_fee: float
    gas_fee: float


MAKERS_DATA = {
    enums.NetworkNames.Starknet: {
        enums.NetworkNames.Arbitrum: MakerData(
            addresses=(
                '0x07b393627bd514d2aa4c83e9f0c468939df15ea3c29980cd8e7be3ec847795f0',
                '0x064A24243F2Aabae8D2148FA878276e6E6E452E3941b417f3c33b1649EA83e11'
            ),
            min_price=0.005,
            max_price=3,
            trading_fee=0.0008,
            gas_fee=0.035
        ),
        enums.NetworkNames.Optimism: MakerData(
            addresses=(
                '0x07b393627bd514d2aa4c83e9f0c468939df15ea3c29980cd8e7be3ec847795f0',
                '0x064A24243F2Aabae8D2148FA878276e6E6E452E3941b417f3c33b1649EA83e11'
            ),
            min_price=0.005,
            max_price=3,
            trading_fee=0.0013,
            gas_fee=0.035
        )
    },
    enums.NetworkNames.StarknetTestnet: {
        enums.NetworkNames.ArbitrumTestnet: MakerData(
            addresses=(
                '0x50e5ba067562e87b47d87542159e16a627e85b00de331a53b471cee1a4e5a4f',
            ),
            min_price=0.005,
            max_price=3,
            trading_fee=0.0008,
            gas_fee=0.035
        ),
        enums.NetworkNames.OptimismTestnet: MakerData(
            addresses=(
                '0x50e5ba067562e87b47d87542159e16a627e85b00de331a53b471cee1a4e5a4f',
            ),
            min_price=0.005,
            max_price=3,
            trading_fee=0.0013,
            gas_fee=0.035
        )
    },
    enums.NetworkNames.ETH: {
        enums.NetworkNames.Starknet: MakerData(
            addresses=(
                '0x80C67432656d59144cEFf962E8fAF8926599bCF8',
                '0xE4eDb277e41dc89aB076a1F049f4a3EfA700bCE8'
            ),
            min_price=0.005,
            max_price=3,
            trading_fee=0.0012,
            gas_fee=0
        )
    },
    enums.NetworkNames.Arbitrum: {
        enums.NetworkNames.Starknet: MakerData(
            addresses=(
                '0x80C67432656d59144cEFf962E8fAF8926599bCF8',
                '0xE4eDb277e41dc89aB076a1F049f4a3EfA700bCE8'
            ),
            min_price=0.005,
            max_price=3,
            trading_fee=0.0012,
            gas_fee=0.001
        )
    },
    enums.NetworkNames.Optimism: {
        enums.NetworkNames.Starknet: MakerData(
            addresses=(
                '0x80C67432656d59144cEFf962E8fAF8926599bCF8',
                '0xE4eDb277e41dc89aB076a1F049f4a3EfA700bCE8'
            ),
            min_price=0.005,
            max_price=3,
            trading_fee=0.0012,
            gas_fee=0.001
        )
    },
    enums.NetworkNames.Goerli: {
        enums.NetworkNames.StarknetTestnet: MakerData(
            addresses=(
                '0x4eaf936c172b5e5511959167e8ab4f7031113ca3',
            ),
            min_price=0.01,
            max_price=5,
            trading_fee=0.01,
            gas_fee=0.05
        )
    }
}


async def deposit_to_starknet(
    private_key: str,
    from_network_name: enums.NetworkNames,
    to_network_name: enums.NetworkNames,
    to_private_key: str,
    to_address: str,
    *,
    amount: float = None,
    percentage: float = None,
    wait_for_receive: bool = True,
    proxy: dict[str, str] = None
) -> enums.TransactionStatus:
    if not any([amount, percentage]):
        raise ValueError('Either amount or percentage must be specified')
    elif all([amount, percentage]):
        raise ValueError('Only one of amount or percentage must be specified')

    from_network = constants.NETWORKS[from_network_name]
    to_network = constants.NETWORKS[to_network_name]

    web3 = Web3(
        Web3.HTTPProvider(
            from_network.rpc_url,
            request_kwargs={
                'proxies': proxy
            }
        )
    )

    evm_account = web3.eth.account.from_key(private_key)

    balance_in_wei = web3.eth.get_balance(evm_account.address)

    if amount is None:
        if percentage == 100:
            amount_in_wei = balance_in_wei
        else:
            amount_in_wei = int(balance_in_wei * percentage / 100)
        amount = web3.from_wei(amount_in_wei, 'ether')
    else:
        amount_in_wei = web3.to_wei(amount, 'ether')

    logging.info(f'[Orbiter] Sending {amount} ETH from {from_network_name} to {to_network_name}')

    if from_network_name not in MAKERS_DATA:
        logging.error(f'[Orbiter] Selected incorrect source network: {from_network_name}')
        return enums.TransactionStatus.FAILED
    elif to_network_name not in MAKERS_DATA[from_network_name]:
        logging.error(f'[Orbiter] Selected incorrect destination network: {to_network_name}')
        return enums.TransactionStatus.FAILED

    maker_data = MAKERS_DATA[from_network_name][to_network_name]

    maker_address = random.choice(maker_data.addresses)

    if amount < maker_data.min_price:
        logging.error(f'[Orbiter] Amount is less than min price: {maker_data.min_price}')
        return enums.TransactionStatus.FAILED
    if amount > maker_data.max_price:
        logging.warning(f'[Orbiter] Amount is more than max price: {maker_data.max_price}')
        amount = maker_data.max_price - maker_data.trading_fee

    amount_in_wei = amount_in_wei // 10 ** 4 * 10 ** 4
    amount_in_wei += NETWORK_IDENTIFIERS[to_network_name]

    if amount_in_wei > balance_in_wei:
        amount_in_wei -= 10000

    with open(Path(__file__).parent / 'abi' / 'EVMRouter.json') as file:
        router_abi = json.load(file)

    router_contract = web3.eth.contract(
        address=CONTRACT_ADRESSES[ContractTypes.ROUTER][from_network_name],
        abi=router_abi
    )

    gas_price = utils.suggest_gas_fees(
        network_name=from_network_name,
        proxy=None
    )

    if not gas_price:
        return enums.TransactionStatus.FAILED

    txn_dict = {
        'chainId': web3.eth.chain_id,
        'nonce': web3.eth.get_transaction_count(evm_account.address),
        'from': evm_account.address,
        'gas': 0,
        **gas_price,
        'value': 1
    }

    contract_dict = {
        '_to': web3.to_checksum_address(maker_address),
        '_ext': HexBytes(f'0x03{to_address[2:]}')
    }

    txn = router_contract.functions.transfer(
        **contract_dict
    ).build_transaction(txn_dict)

    try:
        txn['gas'] = web3.eth.estimate_gas(txn)
    except Exception as e:
        if 'insufficient funds for transfer' in str(e):
            logging.critical(f'[Orbiter] Insufficient balance to send {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[Orbiter] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    txn['gas'] = int(txn['gas'] * 1.05)
    transaction_fee = int(txn['gas'] * gas_price['maxFeePerGas'])

    if amount_in_wei + transaction_fee > balance_in_wei:
        if percentage is None:
            logging.critical(f'[Orbiter] Insufficient balance to send {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount_in_wei = balance_in_wei - transaction_fee
            amount_in_wei = amount_in_wei // 10 ** 4 * 10 ** 4
            amount_in_wei += NETWORK_IDENTIFIERS[to_network_name]
            amount_in_wei -= 10000

            if amount_in_wei <= 0:
                logging.critical(f'[Orbiter] Insufficient balance to bridge {amount} ETH')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

    txn_dict['value'] = amount_in_wei

    txn = router_contract.functions.transfer(
        **contract_dict
    ).build_transaction(txn_dict)

    try:
        txn['gas'] = web3.eth.estimate_gas(txn)
    except Exception as e:
        if 'insufficient funds for transfer' in str(e):
            logging.critical(f'[Orbiter] Insufficient balance to send {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[Orbiter] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    signed_txn = evm_account.sign_transaction(txn)

    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

    logging.info(f'[Orbiter] Transaction: {from_network.txn_explorer_url}{txn_hash.hex()}')

    receipt = utils.wait_for_transaction_receipt(
        web3=web3.eth,
        txn_hash=txn_hash,
        logging_prefix='Orbiter'
    )

    if receipt and receipt['status'] == 1:
        logging.info(f'[Orbiter] Successfully sent {amount} ETH from {from_network_name} to {to_network_name}')
    else:
        logging.error(f'[Orbiter] Failed to send {amount} ETH from {from_network_name} to {to_network_name}')
        return enums.TransactionStatus.FAILED

    if wait_for_receive:
        logging.info(f'[Orbiter] Waiting for {amount} ETH to be received on {to_network_name}. If you want to skip this step, press Ctrl+C')
        starknet_account = utils.get_account(
            network_name=to_network_name,
            private_key=to_private_key,
            address=to_address,
            proxy=proxy
        )
        transfer_token = constants.NETWORK_TOKENS[to_network_name, enums.TokenNames.ETH]
        balance_before = await starknet_account.get_balance(
            transfer_token.int_contract_address
        )

        while True:
            try:
                balance_after = await starknet_account.get_balance(
                    transfer_token.int_contract_address
                )
                if balance_after > balance_before:
                    logging.info(f'[Orbiter] Successfully received {amount} ETH on {to_network_name}')
                    break
            except KeyboardInterrupt:
                logging.info(f'[Orbiter] Skipping waiting for {amount} ETH to be received on {to_network_name}')
                break
            except Exception as e:
                logging.warning(f'[Orbiter] Error while waiting: {e}')
            time.sleep(10)

    return enums.TransactionStatus.SUCCESS


async def withdraw_from_starknet(
    private_key: str,
    address: str,
    from_network_name: enums.NetworkNames,
    to_network_name: enums.NetworkNames,
    to_address: str,
    cairo_version: int,
    *,
    amount: float = None,
    percentage: float = None,
    wait_for_receive: bool = True,
    proxy: dict[str, str] = None
) -> enums.TransactionStatus:
    if not any([amount, percentage]):
        raise ValueError('Either amount or percentage must be specified')
    elif all([amount, percentage]):
        raise ValueError('Only one of amount or percentage must be specified')

    from_network = constants.NETWORKS[from_network_name]
    to_network = constants.NETWORKS[to_network_name]

    transfer_token = constants.NETWORK_TOKENS[from_network_name, enums.TokenNames.ETH]

    account = utils.get_account(
        network_name=from_network_name,
        private_key=private_key,
        address=address,
        proxy=proxy
    )

    balance_in_wei = await account.get_balance(
        transfer_token.int_contract_address
    )

    if amount is None:
        if percentage == 100:
            amount_in_wei = balance_in_wei
        else:
            amount_in_wei = int(balance_in_wei * percentage / 100)
        amount = amount_in_wei / 10 ** transfer_token.decimals
    else:
        amount_in_wei = int(amount * 10 ** transfer_token.decimals)

    logging.info(f'[Orbiter] Sending {amount} ETH from {from_network_name} to {to_network_name}')

    if to_network_name not in MAKERS_DATA[from_network_name]:
        logging.error(f'[Orbiter] Selected incorrect destination network: {to_network_name}')
        return enums.TransactionStatus.FAILED

    maker_data = MAKERS_DATA[from_network_name][to_network_name]

    maker_address = random.choice(maker_data.addresses)

    if amount < maker_data.min_price:
        logging.error(f'[Orbiter] Amount is less than min price: {maker_data.min_price}')
        return enums.TransactionStatus.FAILED
    if amount > maker_data.max_price:
        logging.warning(f'[Orbiter] Amount is more than max price: {maker_data.max_price}')
        amount = maker_data.max_price - maker_data.trading_fee

    amount_in_wei = amount_in_wei // 10 ** 4 * 10 ** 4
    amount_in_wei += NETWORK_IDENTIFIERS[to_network_name]

    if amount_in_wei > amount_in_wei:
        amount_in_wei -= 10000

    with open(Path(__file__).parent / 'abi' / 'StarknetRouter.json') as file:
        router_abi = json.load(file)

    router_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.ROUTER][from_network_name],
        abi=router_abi,
        provider=account
    )

    token_contract = utils.get_starknet_erc20_contract(
        token_address=transfer_token.contract_address,
        provider=account
    )

    transfer_dict = {
        '_token': transfer_token.int_contract_address,
        '_to': int(maker_address, 16),
        '_amount': 1,
        '_ext': int(to_address, 16)
    }

    calls = []

    allowance = await token_contract.functions['allowance'].call(
        owner=account.address,
        spender=router_contract.address
    )

    if allowance.remaining == 0:
        calls.append(
            token_contract.functions['approve'].prepare(
                spender=router_contract.address,
                amount=2 ** 256 - 1
            )
        )

    calls.append(
        router_contract.functions['transferERC20'].prepare(
            **transfer_dict
        )
    )

    try:
        transaction = await account._prepare_invoke(
            calls=calls,
            cairo_version=cairo_version,
            auto_estimate=True
        )
    except Exception as e:
        if 'assert_not_zero' in str(e):
            logging.critical(f'[Orbiter] Insufficient balance to send {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[Orbiter] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    if amount_in_wei + transaction.max_fee > balance_in_wei:
        if percentage is None:
            logging.critical(f'[Orbiter] Insufficient balance to send {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount_in_wei = balance_in_wei - transaction.max_fee
            amount_in_wei = amount_in_wei // 10 ** 4 * 10 ** 4
            amount_in_wei += NETWORK_IDENTIFIERS[to_network_name]
            amount_in_wei -= 10000
            if amount_in_wei <= 0:
                logging.critical(f'[Orbiter] Insufficient balance to send {amount} ETH')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

    transfer_dict['_amount'] = amount_in_wei

    calls[-1] = router_contract.functions['transferERC20'].prepare(
        **transfer_dict
    )

    resp = await account.execute(
        calls=calls,
        cairo_version=cairo_version,
        max_fee=transaction.max_fee
    )

    logging.info(f'[Orbiter] Transaction: {from_network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='Orbiter'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[Orbiter] Successfully sent {amount} ETH from {from_network_name} to {to_network_name}')
    else:
        logging.error(f'[Orbiter] Failed to send {amount} ETH from {from_network_name} to {to_network_name}')
        return enums.TransactionStatus.FAILED

    if wait_for_receive:
        logging.info(f'[Orbiter] Waiting for {amount} ETH to be received on {to_network_name}. If you want to skip this step, press Ctrl+C')
        web3 = Web3(
            Web3.HTTPProvider(
                constants.NETWORKS[to_network_name].rpc_url,
                request_kwargs={
                    'proxies': proxy
                }
            )
        )
        balance_before = web3.eth.get_balance(to_address)

        while True:
            try:
                balance_after = web3.eth.get_balance(to_address)
                if balance_after > balance_before:
                    logging.info(f'[Orbiter] Successfully received {amount} ETH on {to_network_name}')
                    break
            except KeyboardInterrupt:
                logging.info(f'[Orbiter] Skipping waiting for {amount} ETH to be received on {to_network_name}')
                break
            except Exception as e:
                logging.warning(f'[Orbiter] Error while waiting: {e}')
            time.sleep(10)

    return enums.TransactionStatus.SUCCESS
