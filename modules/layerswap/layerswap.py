import json
import random
import time
from pathlib import Path

import requests
from starknet_py.net.client_models import TransactionExecutionStatus
from web3 import Web3

import constants
import enums
import utils
from logger import logging

LAYERSWAP_NETWORKS = {
    enums.NetworkNames.ETH: 'ETHEREUM_MAINNET',
    enums.NetworkNames.Starknet: 'STARKNET_MAINNET',
    enums.NetworkNames.Arbitrum: 'ARBITRUM_MAINNET',
    enums.NetworkNames.Optimism: 'OPTIMISM_MAINNET',
    enums.NetworkNames.Goerli: 'ETHEREUM_GOERLI',
    enums.NetworkNames.StarknetTestnet: 'STARKNET_GOERLI',
    enums.NetworkNames.ArbitrumTestnet: 'ARBITRUM_GOERLI',
}


class ContractTypes(enums.AutoEnum):
    ROUTER = enums.auto()


CONTRACT_ADRESSES = {
    ContractTypes.ROUTER: {
        enums.NetworkNames.Starknet: '0x05f5b269a57ec59a5fedf10f0f81cbbb7fbe005d3c9f0e0273601a122338f08a',
        enums.NetworkNames.StarknetTestnet: '0x056b277d1044208632456902079f19370e0be63b1a4745f04f96c8c652237dbc'
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
        amount = float(web3.from_wei(amount_in_wei, 'ether'))
    else:
        amount_in_wei = web3.to_wei(amount, 'ether')

    logging.info(f'[Layerswap] Bridging {amount} ETH from {from_network_name} to {to_network_name}')

    if from_network_name not in LAYERSWAP_NETWORKS:
        logging.error(f'[Layerswap] Selected incorrect source network: {from_network_name}')
        return enums.TransactionStatus.FAILED

    connect_response = requests.post(
        url='https://identity-api.layerswap.io/connect/token',
        data={
            'client_id': 'layerswap_bridge_ui',
            'grant_type': 'credentialless'
        },
        proxies=proxy
    )

    if connect_response.status_code != 200:
        logging.error(f'[Layerswap] Error connecting: {connect_response.status_code}')
        if connect_response.status_code == 500:
            logging.info('[Layerswap] This is likely because the Layerswap bridge is down for maintenance')
        return enums.TransactionStatus.FAILED

    connect_json = connect_response.json()

    access_token = connect_json['access_token']

    swap_response = requests.post(
        url='https://bridge-api.layerswap.io//api/swaps',
        data=json.dumps({
            'amount': amount,
            'destination': LAYERSWAP_NETWORKS[to_network_name],
            'destination_address': to_address,
            'destination_asset': 'ETH',
            'refuel': False,
            'source': LAYERSWAP_NETWORKS[from_network_name],
            'source_address': evm_account.address,
            'source_asset': 'ETH'
        }),
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        },
        proxies=proxy
    )

    if swap_response.status_code != 200:
        logging.error(f'[Layerswap] Error creating swap: {swap_response.status_code}')
        if swap_response.status_code == 400:
            logging.info(f'[Layerswap] This error usually means that the swap amount is too small')
        return enums.TransactionStatus.FAILED

    swap_response_json = swap_response.json()

    if swap_response_json['error']:
        logging.error(f'[Layerswap] Error creating swap: {swap_response_json["error"]}')
        return enums.TransactionStatus.FAILED

    swap_id = swap_response_json['data']['swap_id']

    deposit_address_response = requests.post(
        f'https://bridge-api.layerswap.io//api/deposit_addresses/{LAYERSWAP_NETWORKS[from_network_name]}',
        headers={
            'Authorization': f'Bearer {access_token}'
        },
        proxies=proxy
    )

    if deposit_address_response.status_code != 200:
        logging.error(f'[Layerswap] Error getting deposit address: {deposit_address_response.status_code}')
        return enums.TransactionStatus.FAILED

    deposit_address_response_json = deposit_address_response.json()

    deposit_address = deposit_address_response_json['data']['address']

    swap_info_response = requests.get(
        f'https://bridge-api.layerswap.io//api/swaps/{swap_id}',
        headers={
            'Authorization': f'Bearer {access_token}'
        },
        proxies=proxy
    )

    swap_json = swap_info_response.json()

    gas_price = utils.suggest_gas_fees(
        network_name=from_network_name,
        proxy=None
    )

    if not gas_price:
        return enums.TransactionStatus.FAILED

    txn = {
        'chainId': web3.eth.chain_id,
        'nonce': web3.eth.get_transaction_count(evm_account.address),
        'from': evm_account.address,
        'to': Web3.to_checksum_address(deposit_address),
        'gas': 0,
        **gas_price,
        'value': 1,
        'data': hex(swap_json['data']['sequence_number'])
    }

    try:
        txn['gas'] = web3.eth.estimate_gas(txn)
    except Exception as e:
        if 'insufficient funds for transfer' in str(e):
            logging.critical(f'[Layerswap] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[Layerswap] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    txn['gas'] = int(txn['gas'] * 1.05)
    transaction_fee = int(txn['gas'] * (gas_price['maxFeePerGas'] + gas_price['maxPriorityFeePerGas']))

    if amount_in_wei + transaction_fee > balance_in_wei:
        if percentage is None:
            logging.critical(f'[Layerswap] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount_in_wei = balance_in_wei - transaction_fee

            if amount_in_wei <= 0:
                logging.critical(f'[Layerswap] Insufficient balance to bridge {amount} ETH')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

    txn['value'] = amount_in_wei

    try:
        txn['gas'] = web3.eth.estimate_gas(txn)
    except Exception as e:
        if 'insufficient funds for transfer' in str(e):
            logging.critical(f'[Layerswap] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[Layerswap] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    signed_txn = evm_account.sign_transaction(txn)

    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

    logging.info(f'[Layerswap] Transaction: {from_network.txn_explorer_url}{txn_hash.hex()}')

    receipt = utils.wait_for_transaction_receipt(
        web3=web3.eth,
        txn_hash=txn_hash,
        logging_prefix='Layerswap'
    )

    if receipt and receipt['status'] == 1:
        logging.info(f'[Layerswap] Successfully bridged {amount} ETH from {from_network_name} to {to_network_name}')
    else:
        logging.error(f'[Layerswap] Failed to bridge {amount} ETH from {from_network_name} to {to_network_name}')
        return enums.TransactionStatus.FAILED

    if wait_for_receive:
        logging.info(f'[Layerswap] Waiting for {to_network_name} transaction to be completed. If you want to skip this, press Ctrl+C')
        while True:
            try:
                swap_info_response = requests.get(
                    f'https://bridge-api.layerswap.io//api/swaps/{swap_id}',
                    headers={
                        'Authorization': f'Bearer {access_token}'
                    },
                    proxies=proxy
                )

                swap_json = swap_info_response.json()

                status = swap_json['data']['status']

                if status not in {'user_transfer_pending', 'ls_transfer_pending', 'completed'}:
                    logging.error(f'[Layerswap] Swap failed: {status}. Full data: {swap_json}')
                    return enums.TransactionStatus.FAILED
                elif status == 'completed':
                    for transaction in swap_json['data']['transactions']:
                        if transaction['type'] == 'output':
                            logging.info(f'[Layerswap] {to_network_name} transaction: {transaction["explorer_url"]}')
                    break
            except KeyboardInterrupt:
                logging.info(f'[Layerswap] Skipping waiting for {to_network_name} transaction')
                break
            except BaseException as e:
                logging.warning(f'[Layerswap] Error while waiting: {e}')
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

    account = utils.get_account(
        network_name=from_network_name,
        private_key=private_key,
        address=address,
        proxy=proxy
    )

    transfer_token = constants.NETWORK_TOKENS[from_network_name][enums.TokenNames.ETH]

    balance_in_wei = await account.get_balance(transfer_token.int_contract_address)

    if amount is None:
        if percentage == 100:
            amount_in_wei = balance_in_wei
        else:
            amount_in_wei = int(balance_in_wei * percentage / 100)
        amount = amount_in_wei / 10 ** transfer_token.decimals
    else:
        amount_in_wei = int(amount * 10 ** transfer_token.decimals)

    logging.info(f'[Layerswap] Bridging {amount} ETH from {from_network_name} to {to_network_name}')

    if from_network_name not in LAYERSWAP_NETWORKS:
        logging.error(f'[Layerswap] Selected incorrect source network: {from_network_name}')
        return enums.TransactionStatus.FAILED

    connect_response = requests.post(
        url='https://identity-api.layerswap.io/connect/token',
        data={
            'client_id': 'layerswap_bridge_ui',
            'grant_type': 'credentialless'
        },
        proxies=proxy
    )

    if connect_response.status_code != 200:
        logging.error(f'[Layerswap] Error connecting: {connect_response.status_code}')
        if connect_response.status_code == 500:
            logging.info('[Layerswap] This is likely because the Layerswap bridge is down for maintenance')
        return enums.TransactionStatus.FAILED

    connect_json = connect_response.json()

    access_token = connect_json['access_token']

    swap_response = requests.post(
        url='https://bridge-api.layerswap.io//api/swaps',
        data=json.dumps({
            'amount': amount,
            'destination': LAYERSWAP_NETWORKS[to_network_name],
            'destination_address': Web3.to_checksum_address(to_address),
            'destination_asset': 'ETH',
            'refuel': False,
            'source': LAYERSWAP_NETWORKS[from_network_name],
            'source_address': to_address,
            'source_asset': 'ETH'
        }),
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        },
        proxies=proxy
    )

    if swap_response.status_code != 200:
        logging.error(f'[Layerswap] Error creating swap: {swap_response.status_code}')
        if swap_response.status_code == 400:
            logging.info(f'[Layerswap] This error usually means that the swap amount is too small')
        return enums.TransactionStatus.FAILED

    swap_response_json = swap_response.json()

    if swap_response_json['error']:
        logging.error(f'[Layerswap] Error creating swap: {swap_response_json["error"]}')
        return enums.TransactionStatus.FAILED

    swap_id = swap_response_json['data']['swap_id']

    swap_data_response = requests.get(
        url=f'https://www.layerswap.io/app/_next/data/i4WW7fZZ3mOPR-Fb0-34i/en/swap/{swap_id}.json?swapId={swap_id}'
    )

    if swap_data_response.status_code != 200:
        logging.error(f'[Layerswap] Error getting swap data: {swap_data_response.status_code}')
        return enums.TransactionStatus.FAILED

    deposit_address_response_json = swap_data_response.json()

    layerswap_networks = deposit_address_response_json['pageProps']['settings']['networks']

    for layerswap_network in layerswap_networks:
        if layerswap_network['internal_name'] == LAYERSWAP_NETWORKS[from_network_name]:
            deposit_address = random.choice(layerswap_network['managed_accounts'])['address']
            break
    else:
        logging.error(f'[Layerswap] Error getting deposit address: {deposit_address_response_json}')
        return enums.TransactionStatus.FAILED

    swap_info_response = requests.get(
        f'https://bridge-api.layerswap.io//api/swaps/{swap_id}',
        headers={
            'Authorization': f'Bearer {access_token}'
        },
        proxies=proxy
    )

    if swap_info_response.status_code != 200:
        logging.error(f'[Layerswap] Error getting swap info: {swap_info_response.status_code}')
        return enums.TransactionStatus.FAILED

    swap_json = swap_info_response.json()

    token_contract = utils.get_starknet_erc20_contract(
        token_address=transfer_token.contract_address,
        provider=account
    )

    transfer_call = token_contract.functions['transfer'].prepare(
        recipient=int(deposit_address, 16),
        amount=int(10e18)
    )

    with open(Path(__file__).parent / 'abi' / 'Router.json') as file:
        router_abi = json.load(file)

    router_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.ROUTER][from_network_name],
        abi=router_abi,
        provider=account
    )

    watch_call = router_contract.functions['watch'].prepare(
        _Id=swap_json['data']['sequence_number']
    )

    try:
        transaction = await account._prepare_invoke(
            calls=[
                transfer_call,
                watch_call
            ],
            cairo_version=cairo_version,
            auto_estimate=True
        )
    except Exception as e:
        if 'assert_not_zero' in str(e):
            logging.critical(f'[Layerswap] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[Layerswap] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    if transaction.max_fee + amount_in_wei > balance_in_wei:
        if percentage is None:
            logging.critical(f'[Layerswap] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount_in_wei = balance_in_wei - transaction.max_fee
            if amount_in_wei <= 0:
                logging.critical(f'[Layerswap] Insufficient balance to bridge {amount} ETH')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

    transfer_call = token_contract.functions['transfer'].prepare(
        recipient=int(deposit_address, 16),
        amount=amount_in_wei
    )

    resp = await account.execute(
        [
            transfer_call,
            watch_call
        ],
        cairo_version=cairo_version,
        max_fee=transaction.max_fee
    )

    logging.info(f'[Layerswap] Transaction: {from_network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='Layerswap'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[Layerswap] Successfully bridged {amount} ETH from {from_network_name} to {to_network_name}')
    else:
        logging.error(f'[Layerswap] Failed to bridge {amount} ETH from {from_network_name} to {to_network_name}')
        return enums.TransactionStatus.FAILED

    if wait_for_receive:
        logging.info(f'[Layerswap] Waiting for {to_network_name} transaction to be completed. If you want to skip this, press Ctrl+C')
        while True:
            try:
                swap_info_response = requests.get(
                    f'https://bridge-api.layerswap.io//api/swaps/{swap_id}',
                    headers={
                        'Authorization': f'Bearer {access_token}'
                    },
                    proxies=proxy
                )

                swap_json = swap_info_response.json()

                status = swap_json['data']['status']

                if status not in {'user_transfer_pending', 'ls_transfer_pending', 'completed'}:
                    logging.error(f'[Layerswap] Swap failed: {status}. Full data: {swap_json}')
                    return enums.TransactionStatus.FAILED
                elif status == 'completed':
                    for transaction in swap_json['data']['transactions']:
                        if transaction['type'] == 'output':
                            logging.info(f'[Layerswap] {to_network_name} transaction: {transaction["explorer_url"]}')
                    break
            except KeyboardInterrupt:
                logging.info(f'[Layerswap] Skipping waiting for {to_network_name} transaction')
                break
            except BaseException as e:
                logging.warning(f'[Layerswap] Error while waiting: {e}')
            time.sleep(10)

    return enums.TransactionStatus.SUCCESS
