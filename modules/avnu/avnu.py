import requests

import constants
import enums
import utils
from logger import logging
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.client_models import TransactionExecutionStatus, Call

BASE_URLS = {
    enums.NetworkNames.Starknet: 'https://starknet.api.avnu.fi',
    enums.NetworkNames.StarknetTestnet: 'https://goerli.app.avnu.fi'
}


async def swap(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    from_token_name: enums.TokenNames,
    to_token_name: enums.TokenNames,
    slippage: float,
    cairo_version: int,
    *,
    amount: float = None,
    percentage: float = None,
    proxy: dict[str, str] = None
) -> enums.TransactionStatus:
    if not any([amount, percentage]):
        raise ValueError('Either amount or percentage must be specified')
    elif all([amount, percentage]):
        raise ValueError('Only one of amount or percentage must be specified')

    network = constants.NETWORKS[network_name]

    account = utils.get_account(
        network_name=network_name,
        private_key=private_key,
        address=address,
        proxy=proxy
    )

    from_token = constants.NETWORK_TOKENS[network_name, from_token_name]
    to_token = constants.NETWORK_TOKENS[network_name, to_token_name]

    from_token_contract = utils.get_starknet_erc20_contract(
        token_address=from_token.contract_address,
        provider=account
    )

    amount_in_wei = await account.get_balance(from_token.contract_address)

    if amount is None:
        if percentage == 100:
            amount_in_wei = amount_in_wei
        else:
            amount_in_wei = int(amount_in_wei * percentage / 100)
        amount = amount_in_wei / 10 ** from_token.decimals
    else:
        amount_in_wei = int(amount * 10 ** from_token.decimals)

    logging.info(f'[Avnu] Swapping {amount} {from_token_name} to {to_token_name}')

    base_url = BASE_URLS[network_name]

    quotes_response = requests.get(
        url=f'{base_url}/swap/v1/quotes',
        params={
            'sellTokenAddress': from_token.contract_address,
            'buyTokenAddress': to_token.contract_address,
            'sellAmount': hex(amount_in_wei),
            'size': 1,
            'takerAddress': address,
            'integratorName': 'AVNU Portal'
        }
    )

    if quotes_response.status_code != 200:
        logging.error(f'[Avnu] Failed to get quotes: {quotes_response.status_code} {quotes_response.reason}')
        return enums.TransactionStatus.FAILED

    quotes_json = quotes_response.json()

    quote = quotes_json[0]

    build_response = requests.post(
        url=f'{base_url}/swap/v1/build',
        json={
            'quoteId': quote['quoteId'],
            'takerAddress': address,
            'slippage': str(slippage / 100)
        }
    )

    if build_response.status_code != 200:
        logging.error(f'[Avnu] Failed to build swap: {build_response.status_code} {build_response.reason}')
        return enums.TransactionStatus.FAILED

    build_json = build_response.json()
    router_address = build_json['contractAddress']

    approve_call = from_token_contract.functions['approve'].prepare(
        spender=int(router_address, 16),
        amount=amount_in_wei
    )

    swap_call = Call(
        to_addr=int(router_address, 16),
        selector=get_selector_from_name(build_json['entrypoint']),
        calldata=[
            int(value, 16) for value in build_json['calldata']
        ]
    )

    resp = await account.execute(
        [
            approve_call,
            swap_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[Avnu] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='Avnu'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[Avnu] Successfully swapped {amount} {from_token_name} to {to_token_name}')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[Avnu] Failed to swap {amount} {from_token_name} to {to_token_name}')
        return enums.TransactionStatus.FAILED
