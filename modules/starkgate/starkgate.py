import datetime as dt
import json
import time
from pathlib import Path

import requests
from starknet_py.net.client_models import TransactionExecutionStatus
from web3 import Web3

import constants
import enums
import utils
from logger import logging


class ContractTypes(enums.AutoEnum):
    BRIDGE = enums.auto()


CONTRACT_ADRESSES = {
    ContractTypes.BRIDGE: {
        enums.NetworkNames.Starknet: '0x073314940630fd6dcda0d772d4c972c4e0a9946bef9dabf4ef84eda8ef542b82',
        enums.NetworkNames.StarknetTestnet: '0x073314940630fd6dcda0d772d4c972c4e0a9946bef9dabf4ef84eda8ef542b82',
        enums.NetworkNames.ETH: '0xae0Ee0A63A2cE6BaeEFFE56e7714FB4EFE48D419',
        enums.NetworkNames.Goerli: '0xc3511006C04EF1d78af4C8E0e74Ec18A6E64Ff9e'
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
    starknet_account = utils.get_account(
        network_name=to_network_name,
        private_key=to_private_key,
        address=to_address,
        proxy=proxy
    )

    balance_in_wei = web3.eth.get_balance(evm_account.address)

    if amount is None:
        if percentage == 100:
            amount_in_wei = balance_in_wei
        else:
            amount_in_wei = int(balance_in_wei * percentage / 100)
        amount = web3.from_wei(amount_in_wei, 'ether')
    else:
        amount_in_wei = web3.to_wei(amount, 'ether')

    logging.info(f'[StarkGate] Bridging {amount} ETH from {from_network_name} to {to_network_name}')

    evm_contract_address = CONTRACT_ADRESSES[ContractTypes.BRIDGE][from_network_name]
    starknet_contract_address = CONTRACT_ADRESSES[ContractTypes.BRIDGE][to_network_name]

    message_entry_point_selector = '0x2d757788a8d8d6f21d1cd40bce38a8222d70654214e96ff95d8086e684fbee5'

    message_from_address = str(int(evm_contract_address, 16))

    message_payload = [
        to_address.lower(),
        hex(amount_in_wei),
        '0x0'
    ]

    message_fee = utils.estimate_message_fee(
        client=starknet_account.client,
        from_address=message_from_address,
        to_address=starknet_contract_address,
        entry_point_selector=message_entry_point_selector,
        payload=message_payload,
        proxy=proxy
    )

    if not message_fee or 'overall_fee' not in message_fee:
        logging.error(f'[StarkGate] Failed to estimate message fee: {message_fee}')
        return enums.TransactionStatus.FAILED

    message_fee = message_fee['overall_fee']

    if percentage is None or percentage != 100:
        amount_in_wei += message_fee

    with open(Path(__file__).parent / 'abi' / 'EVMBridge.json') as file:
        router_abi = json.load(file)

    bridge_contract = web3.eth.contract(
        address=CONTRACT_ADRESSES[ContractTypes.BRIDGE][from_network_name],
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
        'value': 1 + message_fee
    }

    contract_dict = {
        'amount': 1,
        'l2Recipient': starknet_account.address
    }

    txn = bridge_contract.functions.deposit(
        **contract_dict
    ).build_transaction(txn_dict)

    try:
        txn['gas'] = web3.eth.estimate_gas(txn)
    except Exception as e:
        if 'insufficient funds for transfer' in str(e):
            logging.critical(f'[StarkGate] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[StarkGate] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    transaction_fee = int(txn['gas'] * 1.05 * gas_price['maxFeePerGas'] + message_fee)

    if amount_in_wei + transaction_fee > balance_in_wei:
        if percentage is None:
            logging.critical(f'[StarkGate] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount_in_wei = balance_in_wei - transaction_fee

        if amount_in_wei <= 0:
            logging.critical(f'[StarkGate] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE

    contract_dict['amount'] = amount_in_wei
    txn_dict['value'] = amount_in_wei + message_fee

    txn = bridge_contract.functions.deposit(
        **contract_dict
    ).build_transaction(txn_dict)

    try:
        txn['gas'] = web3.eth.estimate_gas(txn)
    except Exception as e:
        if 'insufficient funds for transfer' in str(e):
            logging.critical(f'[StarkGate] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[StarkGate] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    signed_txn = evm_account.sign_transaction(txn)

    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

    logging.info(f'[StarkGate] Transaction: {from_network.txn_explorer_url}{txn_hash.hex()}')

    receipt = utils.wait_for_transaction_receipt(
        web3=web3.eth,
        txn_hash=txn_hash,
        logging_prefix='StarkGate'
    )

    if receipt and receipt['status'] == 1:
        logging.info(f'[StarkGate] Successfully bridged {amount} ETH from {from_network_name} to {to_network_name}')
    else:
        logging.error(f'[StarkGate] Failed to bridge {amount} ETH from {from_network_name} to {to_network_name}')
        return enums.TransactionStatus.FAILED

    if wait_for_receive:
        wait_amount_in_wei = amount_in_wei - transaction_fee
        wait_amount = web3.from_wei(wait_amount_in_wei, 'ether')
        logging.info(f'[StarkGate] Waiting for {wait_amount} ETH to be received on {to_network_name}. If you want to skip this step, press Ctrl+C')
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
                    logging.info(f'[StarkGate] Successfully received ~{wait_amount} ETH on {to_network_name}')
                    break
            except KeyboardInterrupt:
                logging.info(f'[StarkGate] Skipping waiting for {amount} ETH to be received on {to_network_name}')
                break
            except Exception as e:
                logging.warning(f'[StarkGate] Error while waiting: {e}')
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

    logging.info(f'[StarkGate] Bridging {amount} ETH from {from_network_name} to {to_network_name}')

    with open(Path(__file__).parent / 'abi' / 'StarknetBridge.json') as file:
        router_abi = json.load(file)

    router_address = CONTRACT_ADRESSES[ContractTypes.BRIDGE][from_network_name]

    router_contract = utils.get_starknet_contract(
        address=router_address,
        abi=router_abi,
        provider=account
    )

    if from_network_name == enums.NetworkNames.Starknet:
        network_url = 'starkgate'
    else:
        network_url = 'starkgate-testnet'

    timestamp = int(dt.datetime.utcnow().timestamp())

    response = requests.get(
        url=f'https://{network_url}.spaceshard.io/v1/gas-cost/{utils.extend_hex(router_address, 64)}/{timestamp}',
        proxies=proxy
    )

    if response.status_code != 200:
        logging.error(f'[StarkGate] Failed to estimate SpaceShard fee: {response.text}')
        return enums.TransactionStatus.FAILED

    gas_cost_json = response.json()['result']

    gas_cost = int(gas_cost_json['gasCost'])
    relayer_address = int(gas_cost_json['relayerAddress'], 16)

    token_contract = utils.get_starknet_erc20_contract(
        token_address=transfer_token.int_contract_address,
        provider=account
    )

    transfer_call = token_contract.functions['transfer'].prepare(
        recipient=relayer_address,
        amount=gas_cost
    )

    withdraw_call = router_contract.functions['initiate_withdraw'].prepare(
        l1_recipient=int(to_address, 16),
        amount=1
    )

    try:
        transaction = await account._prepare_invoke(
            calls=[
                transfer_call,
                withdraw_call
            ],
            cairo_version=cairo_version,
            auto_estimate=True
        )
    except Exception as e:
        if 'assert_not_zero' in str(e):
            logging.critical(f'[StarkGate] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[StarkGate] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    transaction_fee = transaction.max_fee + gas_cost

    if amount_in_wei + transaction_fee > balance_in_wei:
        if percentage is None:
            logging.critical(f'[StarkGate] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount_in_wei = balance_in_wei - transaction_fee

        if amount_in_wei < 0:
            logging.critical(f'[StarkGate] Insufficient balance to bridge {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE

    withdraw_call = router_contract.functions['initiate_withdraw'].prepare(
        l1_recipient=int(to_address, 16),
        amount=amount_in_wei
    )

    resp = await account.execute(
        calls=[
            transfer_call,
            withdraw_call
        ],
        cairo_version=cairo_version,
        max_fee=transaction.max_fee
    )

    logging.info(f'[StarkGate] Transaction: {from_network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='StarkGate'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[StarkGate] Successfully bridged {amount} ETH from {from_network_name} to {to_network_name}')
    else:
        logging.error(f'[StarkGate] Failed to bridge {amount} ETH from {from_network_name} to {to_network_name}')
        return enums.TransactionStatus.FAILED

    if wait_for_receive:
        logging.info(f'[StarkGate] Waiting for {amount} ETH to be received on {to_network_name}. If you want to skip this step, press Ctrl+C')
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
                    logging.info(f'[StarkGate] Successfully received {amount} ETH on {to_network_name}')
                    break
            except KeyboardInterrupt:
                logging.info(f'[StarkGate] Skipping waiting for {amount} ETH to be received on {to_network_name}')
                break
            except Exception as e:
                logging.warning(f'[StarkGate] Error while waiting: {e}')
            time.sleep(10)

    return enums.TransactionStatus.SUCCESS
