import requests

import constants
import enums
import utils
from logger import logging
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.client_models import TransactionExecutionStatus, Call


class ContractTypes(enums.AutoEnum):
    ROUTER = enums.auto()


CONTRACT_ADRESSES = {
    ContractTypes.ROUTER: {
        enums.NetworkNames.Starknet: '0x03201e8057a781dca378564b9d3bbe9b5b7617fac4ad9d9deaa1024cf63f877e'
    }
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

    logging.info(f'[Fibrous] Swapping {amount} {from_token_name} to {to_token_name}')

    execute_response = requests.get(
        url='https://api.fibrous.finance/execute',
        params={
            'amount': hex(amount_in_wei),
            'tokenInAddress': from_token.contract_address,
            'tokenOutAddress': to_token.contract_address,
            'slippage': '0.01',
            'destination': address
        }
    )

    if execute_response.status_code != 200:
        logging.error(f'[Fibrous] Failed to execute: {execute_response.status_code} {execute_response.reason}')
        return enums.TransactionStatus.FAILED

    calldata = execute_response.json()

    router_address = CONTRACT_ADRESSES[ContractTypes.ROUTER][network_name]

    approve_call = from_token_contract.functions['approve'].prepare(
        spender=int(router_address, 16),
        amount=amount_in_wei
    )

    swap_call = Call(
        to_addr=int(router_address, 16),
        selector=get_selector_from_name('swap'),
        calldata=[int(str(value), 0) for value in calldata]
    )

    resp = await account.execute(
        [
            approve_call,
            swap_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[Fibrous] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='Fibrous'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[Fibrous] Successfully swapped {amount} {from_token_name} to {to_token_name}')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[Fibrous] Failed to swap {amount} {from_token_name} to {to_token_name}')
        return enums.TransactionStatus.FAILED
