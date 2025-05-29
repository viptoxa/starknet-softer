import contextlib
import datetime as dt
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Union

import requests
from eth_typing import Hash32, HexStr
from hexbytes import HexBytes
from web3 import Web3
from web3.eth import Eth
from web3.types import TxReceipt

import constants
import enums
from logger import logging
from starknet_py.cairo.felt import decode_shortstring
from starknet_py.common import int_from_bytes
from starknet_py.contract import Contract
from starknet_py.net.account.account import Account
from starknet_py.net.client_models import TransactionReceipt
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.models import StarknetChainId
from starknet_py.net.signer.stark_curve_signer import KeyPair, StarkCurveSigner
from starknet_py.transaction_errors import TransactionRejectedError, TransactionNotReceivedError, TransactionRevertedError


def int_hash_to_hex(hast_int: int, hash_lenght: int = 64) -> str:
    hash_hex = hex(hast_int)[2:]
    hash_hex = hash_hex.rjust(hash_lenght, '0')
    return f'0x{hash_hex}'


def get_account(
    network_name: enums.NetworkNames,
    private_key: str,
    address: str,
    proxy: dict[str, str] = None,
    signer_class=None
) -> Account:
    network = constants.NETWORKS[network_name]

    client = FullNodeClient(
        network.rpc_url,
        proxy=proxy if proxy is None else proxy['http'],
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
    )

    key_pair = KeyPair.from_private_key(
        key=private_key
    )

    if signer_class is None:
        signer_class = StarkCurveSigner

    chain_id = StarknetChainId(int_from_bytes(network.chain_id.encode()))

    signer = signer_class(
        account_address=address,
        key_pair=key_pair,
        chain_id=chain_id
    )

    return Account(
        client=client,
        address=address,
        signer=signer,
        chain=chain_id
    )


def get_starknet_contract(
    address: str,
    abi: list,
    provider: Account
) -> Contract:
    return Contract(
        address=address,
        abi=abi,
        provider=provider
    )


def get_starknet_erc20_contract(
    token_address: str,
    provider: Account
) -> Contract:
    with open(Path(__file__).parent / 'abi' / 'STARKNET_ERC20.json') as file:
        erc20_abi = json.load(file)

    return get_starknet_contract(
        address=token_address,
        abi=erc20_abi,
        provider=provider
    )


def sleep(sleep_time: float):
    logging.info(f'[Sleep] Sleeping for {round(sleep_time, 2)} seconds. If you want to skip this, press Ctrl+C')
    try:
        time.sleep(sleep_time)
    except KeyboardInterrupt:
        logging.info('[Sleep] Skipping sleep')


def random_sleep():
    min_sleep_time = getattr(random_sleep, 'min_sleep_time', 1)
    max_sleep_time = getattr(random_sleep, 'max_sleep_time', 10)
    sleep_time = round(random.uniform(min_sleep_time, max_sleep_time), 2)
    sleep(sleep_time)


def estimate_message_fee(
    client: FullNodeClient,
    from_address: str,
    to_address: str,
    entry_point_selector: str,
    payload: list[str],
    proxy: dict[str, str] = None
) -> dict[str, Union[int, str]]:
    response = requests.post(
        url=f'{client._client.url}/estimate_message_fee?blockNumber=pending',
        json={
            'entry_point_selector': entry_point_selector,
            'from_address': from_address,
            'payload': payload,
            'to_address': to_address
        },
        proxies=proxy
    )

    if response.status_code != 200:
        logging.error(f'[Estimate Message Fee] Failed to estimate message fee: {response.text}')
        return

    return response.json()


def suggest_gas_fees(
    network_name: enums.NetworkNames,
    proxy: dict[str, str] = None
):
    last_update = getattr(suggest_gas_fees, 'last_update', dt.datetime.fromtimestamp(0))
    last_network = getattr(suggest_gas_fees, 'network_name', None)
    if dt.datetime.now() - last_update > dt.timedelta(seconds=10) or last_network != network_name:
        try:
            response = requests.get(
                url=f'https://gas-api.metaswap.codefi.network/networks/{network_name.value}/suggestedGasFees',
                proxies=proxy
            )
        except Exception:
            logging.error(f'[Gas] Failed to get gas price for {network_name.value}')
            return None
        else:
            if response.status_code != 200:
                logging.error(f'[Gas] Failed to get gas price for {network_name.value}: {response.text}')
                return None
            gas_json = response.json()
            medium_gas = gas_json['medium']
            gas_price = {
                'maxFeePerGas': Web3.to_wei(medium_gas['suggestedMaxFeePerGas'], 'gwei'),
                'maxPriorityFeePerGas': Web3.to_wei(medium_gas['suggestedMaxPriorityFeePerGas'], 'gwei')
            }
            suggest_gas_fees.gas_price = gas_price
            suggest_gas_fees.last_update = dt.datetime.now()
            suggest_gas_fees.network_name = network_name
            return gas_price
    else:
        return getattr(suggest_gas_fees, 'gas_price', None)


def wait_for_transaction_receipt(
    web3: Eth,
    txn_hash: Hash32 | HexBytes | HexStr,
    timeout: int = 300,
    logging_prefix: str = 'Receipt'
) -> TxReceipt:
    try:
        receipt = web3.wait_for_transaction_receipt(
            transaction_hash=txn_hash,
            timeout=timeout
        )
    except Exception as e:
        answer = input(f'[{logging_prefix}] Failed to get transaction receipt. Press Enter when transaction will be processed')
        try:
            receipt = web3.wait_for_transaction_receipt(
                transaction_hash=txn_hash,
                timeout=5
            )
        except Exception as e:
            logging.error(f'[{logging_prefix}] Failed to get transaction receipt: {e}')
            return None

    return receipt


@contextlib.contextmanager
def suppress_print():
    original_stdout = sys.stdout
    with open(os.devnull, 'w') as devnull:
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = original_stdout


def test_proxy(proxy: dict[str, str]) -> str | bool:
    try:
        response = requests.get(
            url='https://geo.geosurf.io/',
            proxies=proxy,
            timeout=5
        )
    except KeyboardInterrupt:
        raise
    except Exception:
        try:
            response = requests.get(
                url='https://google.com',
                proxies=proxy,
                timeout=5
            )
        except KeyboardInterrupt:
            raise
        except Exception as e:
            return False
        else:
            return True
    else:
        ip_json = response.json()
        if 'ip' in ip_json:
            ip = ip_json['ip']
            country = ip_json['country']
            return f'{ip} ({country})'
        else:
            return True


async def get_gas_price(
    network_name: enums.NetworkNames,
    proxy: dict[str, str] = None
) -> float:
    if network_name in {None, enums.NetworkNames.Exchange}:
        return 0

    network = constants.NETWORKS[network_name]

    if network_name in {
        enums.NetworkNames.ETH,
        enums.NetworkNames.Goerli
    }:
        web3 = Web3(
            Web3.HTTPProvider(
                network.rpc_url,
                request_kwargs={
                    'proxies': proxy
                }
            )
        )
        gas_wei = int(web3.eth.gas_price)

        return float(Web3.from_wei(gas_wei, 'gwei'))
    elif network_name in {
        enums.NetworkNames.Starknet,
        enums.NetworkNames.StarknetTestnet
    }:
        client = FullNodeClient(
            network.rpc_url,
            proxy=proxy if proxy is None else proxy['http'],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
        )

        last_block = await client.get_block('latest')

        return float(Web3.from_wei(last_block.gas_price, 'gwei'))

    return 0


def get_token_price(token_name: enums.TokenNames, proxy: dict[str, str]) -> float:
    if token_name in constants.STABLECOINS:
        return 1

    last_update = getattr(get_token_price, 'last_update', {})

    last_price = None

    if token_name in last_update:
        last_price = last_update[token_name]['price']
        if dt.datetime.now() - last_update[token_name]['time'] < dt.timedelta(minutes=1):
            return last_price

    last_token = getattr(get_token_price, 'token_price', None)
    coingecko_name = constants.COINGECKO_NAMES[token_name]
    try:
        response = requests.get(
            f'https://api.coingecko.com/api/v3/simple/price?ids={coingecko_name}&vs_currencies=usd',
            proxies=proxy
        )
        price = response.json()[coingecko_name]['usd']
    except Exception as e:
        logging.warning(f'[Token Price] Failed to get {token_name} price: {e}')
        default_price = constants.DEFAULT_PRICES[token_name]
        if last_price is not None:
            price = last_price
            logging.warning(f'[Token Price] Setting {token_name} price to last known price: {last_price}')
        else:
            price = default_price
            logging.warning(f'[Token Price] Setting {token_name} price to default price: {default_price}')
    last_update[token_name] = {
        'price': price,
        'time': dt.datetime.now()
    }
    get_token_price.last_update = last_update
    return price


def usd_to_token(token_name: enums.TokenNames, usd: float, proxy: dict[str, str]) -> float:
    token_price = get_token_price(token_name, proxy)
    return usd / token_price


def extend_hex(hex_str: str | int, length: int) -> str:
    if isinstance(hex_str, int):
        hex_str = hex(hex_str)
    return hex_str.replace('0x', '0x' + '0' * (length - len(hex_str) + 2))


async def supports_cairo_1(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    wallet_name: enums.WalletNames,
    proxy: dict[str, str] = None
) -> bool:
    network = constants.NETWORKS[network_name]

    account = get_account(
        network_name=network_name,
        private_key=private_key,
        address=address,
        proxy=proxy
    )

    if wallet_name == enums.WalletNames.Braavos:
        abi_filename = 'braavos.json'
        version_func_name = 'get_impl_version'
        version_attr = 'res'
    else:
        abi_filename = 'argentx.json'
        version_func_name = 'getVersion'
        version_attr = 'version'

    with open(Path(__file__).parent / 'modules' / 'wallet' / 'abi' / abi_filename) as file:
        wallet_abi = json.load(file)

    account_contract = get_starknet_contract(
        address=address,
        abi=wallet_abi,
        provider=account,
    )

    version = (
        await account_contract.functions[version_func_name].call()
    )

    version = decode_shortstring(getattr(version, version_attr))

    res = re.match(r'\d+\.(\d+).\d+', version)

    if res is None:
        return False

    return int(res.group(1)) >= 3


async def wait_for_starknet_receipt(
    client: FullNodeClient,
    transaction_hash: int,
    wait_seconds: float = 300,
    logging_prefix: str = 'Receipt'
) -> TransactionReceipt:
    start_time = time.time()
    while True:
        try:
            return await client.wait_for_tx(transaction_hash)
        except (TransactionRejectedError, TransactionNotReceivedError, TransactionRevertedError):
            raise
        except BaseException as e:
            if time.time() - start_time > wait_seconds:
                input(f'[{logging_prefix}] Failed to get transaction receipt. Press Enter when transaction will be processed')
                try:
                    return await client.wait_for_tx(transaction_hash)
                except BaseException as new_e:
                    logging.error(f'[{logging_prefix}] Failed to get transaction receipt: {new_e}')
                    raise
            logging.warning(f'[{logging_prefix}] Error while getting transaction receipt: {e}')


async def get_tokens_with_balance(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    tokens: list[enums.TokenNames],
    min_amount: float = None,
    min_amount_usd: float = None,
    proxy: dict[str, str] = None
):
    tokens_with_balance = []

    if min_amount is None:
        min_amount = 0

    network = constants.NETWORKS[network_name]

    account = get_account(
        network_name=network_name,
        private_key=private_key,
        address=address
    )

    for token_name in tokens:
        token = constants.NETWORK_TOKENS[network_name, token_name]
        balance_in_wei = await account.get_balance(token.contract_address)
        balance = balance_in_wei / 10 ** token.decimals

        if min_amount_usd is not None:
            min_amount = max(
                usd_to_token(token_name, min_amount_usd, proxy),
                min_amount
            )

        if balance > min_amount:
            tokens_with_balance.append(token_name)

    return tokens_with_balance
