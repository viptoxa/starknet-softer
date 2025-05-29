import time

from okx.Funding import FundingAPI
from okx.SubAccount import SubAccountAPI
from starknet_py.net.client_models import TransactionExecutionStatus
from web3 import Web3

import constants
import enums
import utils
from logger import logging


class OKXTransactionStatus(enums.Enum):
    """
    https://www.okx.com/docs-v5/en/#funding-account-rest-api-get-withdrawal-history
    """
    CANCELING = -3
    CANCELED = -2
    FAILED = -1
    WAITING_WITHDRAWAL = 0
    WITHDRAWING = 1
    WITHDRAW_SUCCESS = 2
    APPROVED = 7
    WAITING_TRANSFER = 10
    WAITING_MANUAL_REVIEW_4 = 4
    WAITING_MANUAL_REVIEW_5 = 5
    WAITING_MANUAL_REVIEW_6 = 6
    WAITING_MANUAL_REVIEW_8 = 8
    WAITING_MANUAL_REVIEW_9 = 9
    WAITING_MANUAL_REVIEW_12 = 12


OKX_NETWORKS = {
    enums.NetworkNames.ETH: 'ERC20',
    enums.NetworkNames.Starknet: 'StarkNet',
    enums.NetworkNames.Arbitrum: 'Arbitrum One',
    enums.NetworkNames.Optimism: 'Optimism'
}


def withdraw_from_okx(
    to_address: str,
    network_name: enums.NetworkNames,
    api_key: str,
    api_secret_key: str,
    passphrase: str,
    *,
    amount: float = None,
    percentage: float = None,
    wait_for_receive: bool = True
) -> enums.TransactionStatus:
    if not any([amount, percentage]):
        raise ValueError('Either amount or percentage must be specified')
    elif all([amount, percentage]):
        raise ValueError('Only one of amount or percentage must be specified')

    client = FundingAPI(
        api_key=api_key,
        api_secret_key=api_secret_key,
        passphrase=passphrase,
        flag='0'
    )

    with utils.suppress_print():
        eth_balance = client.get_balances('ETH')

    if eth_balance['code'] != '0':
        logging.error(f'[OKX Withdraw] Failed to get ETH balance: {eth_balance["msg"]}')
        return enums.TransactionStatus.FAILED

    balance = float(eth_balance['data'][0]['availBal'])

    if amount is None:
        if percentage == 100:
            amount = balance
        else:
            amount = float(balance) * percentage / 100

    logging.info(f'[OKX Withdraw] Withdrawing {amount} ETH to {to_address}')

    with utils.suppress_print():
        eth_currencies = client.get_currencies('ETH')

    if eth_currencies['code'] != '0':
        logging.error(f'[OKX Withdraw] Failed to get ETH currencies: {eth_currencies["msg"]}')
        return enums.TransactionStatus.FAILED

    try:
        okx_network_name = OKX_NETWORKS[network_name]
    except KeyError:
        logging.error(f'[OKX Withdraw] Unsupported network: {network_name}')
        return enums.TransactionStatus.FAILED

    for currency in eth_currencies['data']:
        if currency['chain'].lower() == f'ETH-{okx_network_name}'.lower():
            eth_currency = currency
            break
    else:
        logging.error(f'[OKX Withdraw] Failed to get ETH info from currencies: {eth_currencies["msg"]}')
        return enums.TransactionStatus.FAILED

    min_amount = float(eth_currency['minWd'])

    fee = float(eth_currency['minFee'])

    if min_amount * 2 <= amount:
        amount -= fee

    if balance < amount + fee:
        if percentage is None:
            logging.critical(f'[OKX Withdraw] Insufficient balance to withdraw {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount = balance - fee
            if amount <= 0:
                logging.critical(f'[OKX Withdraw] Insufficient balance to withdraw {amount} ETH')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

    if amount < min_amount:
        logging.error(f'[OKX Withdraw] Amount {amount} is less than minimum withdrawal amount {min_amount}')
        return enums.TransactionStatus.FAILED

    with utils.suppress_print():
        withdrawal_data = client.withdrawal(
            ccy='ETH',
            amt=str(amount),
            dest='4',
            toAddr=to_address,
            fee=str(fee),
            chain=eth_currency['chain']
        )

    if withdrawal_data['code'] != '0':
        if 'Withdrawal address is not allowlisted' in withdrawal_data['msg']:
            logging.critical(f'[OKX Withdraw] Withdrawal address is not allowlisted. Please add {to_address} to allowlist')
            return enums.TransactionStatus.ADDRESS_NOT_ALLOWLISTED
        logging.error(f'[OKX Withdraw] Failed to withdraw ETH: {withdrawal_data["msg"]}')
        return enums.TransactionStatus.FAILED

    withdrawal_id = withdrawal_data['data'][0]['wdId']

    logging.info(f'[OKX Withdraw] Withdrawal request sent, withdrawal ID: {withdrawal_id}')

    if wait_for_receive:
        logging.info(f'[OKX Withdraw] Waiting for funds to be received. If you want to skip this, press Ctrl+C')
        while True:
            try:
                with utils.suppress_print():
                    history = client.get_withdrawal_history(wdId=withdrawal_id)
                if history['code'] != '0':
                    logging.error(f'[OKX Withdraw] Failed to get withdrawal history: {history["msg"]}')
                    return enums.TransactionStatus.SUCCESS

                state = OKXTransactionStatus(int(history['data'][0]['state']))

                if state == OKXTransactionStatus.WITHDRAW_SUCCESS:
                    logging.info(f'[OKX Withdraw] Successfully received funds on {network_name}')
                    break
                elif state in {OKXTransactionStatus.CANCELING, OKXTransactionStatus.CANCELED}:
                    logging.error(f'[OKX Withdraw] Withdrawal canceled by user')
                    return enums.TransactionStatus.FAILED
                elif state == OKXTransactionStatus.FAILED:
                    logging.error(f'[OKX Withdraw] Withdrawal failed')
                    return enums.TransactionStatus.FAILED

                time.sleep(10)
            except KeyboardInterrupt:
                logging.info(f'[OKX Withdraw] Skipping waiting for receive')
                break
            except BaseException as e:
                logging.warning(f'[OKX Withdraw] Exception occurred while waiting for receive: {e}')

    logging.info(f'[OKX Withdraw] Successfully withdrew {amount} ETH to {to_address}')
    return enums.TransactionStatus.SUCCESS


def deposit_to_okx_from_evm(
    private_key: str,
    network_name: enums.NetworkNames,
    to_address: str,
    *,
    amount: float = None,
    percentage: float = None,
    min_deposit_amount: float = None,
    wait_for_receive: bool = True,
    proxy: dict[str, str] = None
) -> enums.TransactionStatus:
    if not any([amount, percentage]):
        raise ValueError('Either amount or percentage must be specified')

    if network_name not in {
        enums.NetworkNames.Arbitrum,
        enums.NetworkNames.Optimism,
        enums.NetworkNames.ETH
    }:
        logging.error(f'[OKX Deposit] Invalid network: {network_name}')
        return enums.TransactionStatus.INCORRECT_NETWORK

    if percentage is not None:
        percentage = min(max(percentage, 0.001), 100)

    network = constants.NETWORKS[network_name]

    web3 = Web3(
        Web3.HTTPProvider(
            network.rpc_url,
            request_kwargs={
                'proxies': proxy
            }
        )
    )
    account = web3.eth.account.from_key(private_key)

    balance = web3.eth.get_balance(account.address)

    if amount is None:
        if percentage == 100:
            amount_in_wei = balance
        else:
            amount_in_wei = int(balance * percentage / 100)
        amount = web3.from_wei(amount_in_wei, 'ether')
    else:
        amount_in_wei = web3.to_wei(amount, 'ether')

    to_address = web3.to_checksum_address(to_address)

    logging.info(f'[OKX Deposit] Depositing {amount} ETH to {to_address} on {network_name} network')

    gas_price = utils.suggest_gas_fees(
        network_name=network_name,
        proxy=proxy
    )

    if not gas_price:
        return enums.TransactionStatus.FAILED

    txn = {
        'chainId': web3.eth.chain_id,
        'nonce': web3.eth.get_transaction_count(account.address),
        'from': account.address,
        'to': to_address,
        'gas': 0,
        **gas_price,
        'value': 0
    }

    try:
        txn['gas'] = web3.eth.estimate_gas(txn)
    except Exception as e:
        if 'insufficient funds' in str(e):
            logging.critical(f'[OKX Deposit] Insufficient balance to deposit {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[OKX Deposit] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    transaction_fee = txn['gas'] * txn['maxFeePerGas']

    if amount_in_wei + transaction_fee > balance:
        if percentage is None:
            logging.critical(f'[OKX Deposit] Insufficient balance to deposit {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount_in_wei = balance - transaction_fee
            if amount_in_wei <= 0:
                logging.critical(f'[OKX Deposit] Insufficient balance to deposit {amount} ETH')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

    amount = web3.from_wei(amount_in_wei, 'ether')

    txn['value'] = amount_in_wei

    if min_deposit_amount is not None and amount < min_deposit_amount:
        logging.info(f'[OKX Deposit] Deposit amount is less than {min_deposit_amount} ETH, skipping deposit')
        return enums.TransactionStatus.SUCCESS

    signed_txn = web3.eth.account.sign_transaction(txn, private_key=private_key)
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

    logging.info(f'[OKX Deposit] Transaction: {network.txn_explorer_url}{txn_hash.hex()}')

    receipt = utils.wait_for_transaction_receipt(
        web3=web3.eth,
        txn_hash=txn_hash,
        logging_prefix='OKX Deposit'
    )

    if receipt and receipt['status'] == 1:
        logging.info(f'[OKX Deposit] Successfully deposited {amount} ETH to {to_address}')
    else:
        logging.error(f'[OKX Deposit] Failed to deposit {amount} ETH to {to_address}')
        return enums.TransactionStatus.FAILED

    if wait_for_receive:
        logging.info(f'[OKX Deposit] Waiting for deposit to be received by OKX')
        input(f'[OKX Deposit] Module cannot get OKX balance, please check manually and then press Enter')

    return enums.TransactionStatus.SUCCESS


async def deposit_to_okx_from_starknet(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    to_address: str,
    cairo_version: int,
    *,
    amount: float = None,
    percentage: float = None,
    min_deposit_amount: float = None,
    wait_for_receive: bool = True,
    proxy: dict[str, str] = None
) -> enums.TransactionStatus:
    if not any([amount, percentage]):
        raise ValueError('Either amount or percentage must be specified')

    if network_name not in {
        enums.NetworkNames.Starknet
    }:
        logging.error(f'[OKX Deposit] Invalid network: {network_name}')
        return enums.TransactionStatus.INCORRECT_NETWORK

    if percentage is not None:
        percentage = min(max(percentage, 0.001), 100)

    network = constants.NETWORKS[network_name]
    token = constants.NETWORK_TOKENS[network_name, enums.TokenNames.ETH]

    account = utils.get_account(
        network_name=network_name,
        private_key=private_key,
        address=address,
        proxy=proxy
    )

    balance_in_wei = await account.get_balance(token.int_contract_address)

    if amount is None:
        if percentage == 100:
            amount_in_wei = balance_in_wei
        else:
            amount_in_wei = int(balance_in_wei * percentage / 100)
        amount = amount_in_wei / 10 ** token.decimals
    else:
        amount_in_wei = int(amount * 10 ** token.decimals)

    if min_deposit_amount is not None and amount < min_deposit_amount:
        logging.info(f'[OKX Deposit] Deposit amount is less than {min_deposit_amount} ETH, skipping deposit')
        return enums.TransactionStatus.SUCCESS

    logging.info(f'[OKX Deposit] Depositing {amount} ETH to {to_address} on {network_name} network')

    token_contract = utils.get_starknet_erc20_contract(
        token_address=token.int_contract_address,
        provider=account,
    )

    transfer_call = token_contract.functions['transfer'].prepare(
        recipient=int(to_address, 16),
        amount=1
    )

    try:
        transaction = await account._prepare_invoke(
            calls=[
                transfer_call
            ],
            cairo_version=cairo_version,
            auto_estimate=True
        )
    except Exception as e:
        if 'assert_not_zero' in str(e):
            logging.critical(f'[OKX Deposit] Insufficient balance to deposit {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[OKX Deposit] Exception occured while estimating gas: {e}')
        return enums.TransactionStatus.FAILED

    if amount_in_wei + transaction.max_fee > balance_in_wei:
        if percentage is None:
            logging.critical(f'[OKX Deposit] Insufficient balance to deposit {amount} ETH')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        else:
            amount_in_wei = balance_in_wei - transaction.max_fee
            if amount_in_wei <= 0:
                logging.critical(f'[OKX Deposit] Insufficient balance to deposit {amount} ETH')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

    amount = amount_in_wei / 10 ** token.decimals

    if min_deposit_amount is not None and amount < min_deposit_amount:
        logging.info(f'[OKX Deposit] Deposit amount is less than {min_deposit_amount} ETH, skipping deposit')
        return enums.TransactionStatus.SUCCESS

    transfer_call = token_contract.functions['transfer'].prepare(
        recipient=int(to_address, 16),
        amount=amount_in_wei
    )

    resp = await account.execute(
        calls=[
            transfer_call
        ],
        cairo_version=cairo_version,
        max_fee=transaction.max_fee
    )

    logging.info(f'[OKX Deposit] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='OKX Deposit'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[OKX Deposit] Successfully deposited {amount} ETH to {to_address}')
    else:
        logging.error(f'[OKX Deposit] Failed to deposit {amount} ETH to {to_address}')
        return enums.TransactionStatus.FAILED

    if wait_for_receive:
        logging.info(f'[OKX Deposit] Waiting for deposit to be received by OKX')
        input(f'[OKX Deposit] Module cannot get OKX balance, please check manually and then press Enter')

    return enums.TransactionStatus.SUCCESS


def transfer_from_subs(
    api_key: str,
    api_secret_key: str,
    passphrase: str
):
    subaccount_client = SubAccountAPI(
        api_key=api_key,
        api_secret_key=api_secret_key,
        passphrase=passphrase,
        flag='0'
    )
    funding_client = FundingAPI(
        api_key=api_key,
        api_secret_key=api_secret_key,
        passphrase=passphrase,
        flag='0'
    )

    logging.info(f'[OKX Subaccounts Transfer] Transferring ETH from subaccounts to main account')

    with utils.suppress_print():
        subaccounts = subaccount_client.get_subaccount_list()

    if subaccounts['code'] != '0':
        logging.error(f'[OKX Subaccounts Transfer] Failed to get subaccount list: {subaccounts["msg"]}')
        return enums.TransactionStatus.FAILED

    subaccounts = subaccounts['data']

    for subaccount in subaccounts:
        with utils.suppress_print():
            balances_response = subaccount_client.get_funding_balance(
                subAcct=subaccount['subAcct']
            )
        if balances_response['code'] != '0':
            logging.error(f'[OKX Subaccounts Transfer] Failed to get subaccount {subaccount["subAcct"]} balances: {balances_response["msg"]}')
            return enums.TransactionStatus.FAILED
        balances = balances_response['data']
        for balance in balances:
            if balance['ccy'] == 'ETH':
                eth_balance = balance['availBal']
                if float(eth_balance) > 0:
                    logging.info(f'[OKX Subaccounts Transfer] Transferring {eth_balance} ETH from subaccount {subaccount["subAcct"]}')
                    with utils.suppress_print():
                        transfer_result = funding_client.funds_transfer(
                            ccy='ETH',
                            amt=eth_balance,
                            from_='6',
                            to='6',
                            subAcct=subaccount['subAcct'],
                            type='2'
                        )
                    if transfer_result['code'] == '58127':
                        logging.critical(f'[OKX Subaccounts Transfer] API key does not have permission to transfer funds')
                        return enums.TransactionStatus.FAILED
                    elif transfer_result['code'] != '0':
                        logging.error(f'[OKX Subaccounts Transfer] Failed to transfer {eth_balance} ETH from subaccount {subaccount["subAcct"]}: {transfer_result["msg"]}')
                        return enums.TransactionStatus.FAILED
                    else:
                        logging.info(f'[OKX Subaccounts Transfer] Successfully transferred {eth_balance} ETH from subaccount {subaccount["subAcct"]}')
            time.sleep(0.5)

    logging.info(f'[OKX Subaccounts Transfer] Successfully transferred ETH from subaccounts to main account')

    return enums.TransactionStatus.SUCCESS
