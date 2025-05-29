import json
from pathlib import Path

from starknet_py.net.client_models import TransactionExecutionStatus

import constants
import enums
import utils
from logger import logging


class ContractTypes(enums.AutoEnum):
    MARKET = enums.auto()
    ORACLE = enums.auto()


CONTRACT_ADRESSES = {
    ContractTypes.MARKET: {
        enums.NetworkNames.Starknet: '0x04c0a5193d58f74fbace4b74dcf65481e734ed1714121bdc571da345540efa05'
    },
    ContractTypes.ORACLE: {
        enums.NetworkNames.Starknet: '0x0346c57f094d641ad94e43468628d8e9c574dcb2803ec372576ccc60a40be2c4',
        enums.NetworkNames.StarknetTestnet: '0x446812bac98c08190dee8967180f4e3cdcd1db9373ca269904acb17f67f7093'
    }
}

ORACLE_PAIR_IDS = {
    enums.TokenNames.ETH: 19514442401534788,
    enums.TokenNames.USDC: 6148332971638477636,
    enums.TokenNames.DAI: 19212080998863684,
}


async def get_token_price(
    account: utils.Account,
    network_name: enums.NetworkNames,
    token_name: enums.TokenNames
) -> float:
    with open(Path(__file__).parent / 'abi' / 'Oracle.json') as file:
        oracle_abi = json.load(file)

    oracle_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.ORACLE][network_name],
        abi=oracle_abi,
        provider=account
    )

    pair_id = ORACLE_PAIR_IDS[token_name]

    token_price = (await oracle_contract.functions['get_spot_median'].call(
        pair_id=pair_id
    )).price

    price_decimals = (await oracle_contract.functions['get_spot_decimals'].call(
        pair_id=token_price
    )).decimals

    return token_price / 10 ** price_decimals



async def convert_to_usd(
    account: utils.Account,
    network_name: enums.NetworkNames,
    token_name: enums.TokenNames,
    amount: float
) -> float:
    token_price = await get_token_price(
        **locals()
    )

    return amount * token_price


async def supply(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    token_name: enums.TokenNames,
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

    with open(Path(__file__).parent / 'abi' / 'Market.json') as file:
        market_abi = json.load(file)

    market_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.MARKET][network_name],
        abi=market_abi,
        provider=account
    )

    token = constants.NETWORK_TOKENS[network_name, token_name]

    token_contract = utils.get_starknet_erc20_contract(
        token_address=token.contract_address,
        provider=account
    )

    balance_in_wei = await account.get_balance(token.contract_address)

    if amount is None:
        if percentage == 100:
            amount_in_wei = balance_in_wei
        else:
            amount_in_wei = int(balance_in_wei * percentage / 100)
        amount = amount_in_wei / 10 ** token.decimals
    else:
        amount_in_wei = int(amount * 10 ** token.decimals)

    logging.info(f'[zkLend] Supplying {amount} {token_name}')

    calls = [
        token_contract.functions['approve'].prepare(
            spender=market_contract.address,
            amount=amount_in_wei
        ),
        market_contract.functions['deposit'].prepare(
            token=token.int_contract_address,
            amount=amount_in_wei
        )
    ]

    collateral_enabled = await market_contract.functions['is_collateral_enabled'].call(
        user=account.address,
        token=token.int_contract_address
    )

    if not collateral_enabled.enabled:
        calls.append(
            market_contract.functions['enable_collateral'].prepare(
                token=token.int_contract_address
            )
        )

    resp = await account.execute(
        calls=calls,
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[zkLend] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='zkLend'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[zkLend] Successfully supplied {amount} {token_name}')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[zkLend Failed to supply {amount} {token_name}')
        return enums.TransactionStatus.FAILED


async def borrow(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    token_name: enums.TokenNames,
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

    with open(Path(__file__).parent / 'abi' / 'Market.json') as file:
        market_abi = json.load(file)

    market_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.MARKET][network_name],
        abi=market_abi,
        provider=account
    )

    supply_token_name = enums.TokenNames.ETH

    collateral_token = constants.NETWORK_TOKENS[network_name, supply_token_name]
    borrow_token = constants.NETWORK_TOKENS[network_name, token_name]

    collateral_reserve_data = await market_contract.functions['get_reserve_data'].call(
        token=collateral_token.int_contract_address
    )
    borrow_reserve_data = await market_contract.functions['get_reserve_data'].call(
        token=borrow_token.int_contract_address
    )

    if amount is None:
        z_token_contract = utils.get_starknet_erc20_contract(
            token_address=collateral_reserve_data.data['z_token_address'],
            provider=account
        )

        with open(Path(__file__).parent / 'abi' / 'Oracle.json') as file:
            oracle_abi = json.load(file)

        oracle_contract = utils.get_starknet_contract(
            address=CONTRACT_ADRESSES[ContractTypes.ORACLE][network_name],
            abi=oracle_abi,
            provider=account
        )

        collateral_pair_id = ORACLE_PAIR_IDS[supply_token_name]
        borrow_pair_id = ORACLE_PAIR_IDS[token_name]

        collateral_token_price = (await oracle_contract.functions['get_spot_median'].call(
            pair_id=collateral_pair_id
        )).price
        borrow_token_price = (await oracle_contract.functions['get_spot_median'].call(
            pair_id=borrow_pair_id
        )).price

        collateral_price_decimals = (await oracle_contract.functions['get_spot_decimals'].call(
            pair_id=collateral_pair_id
        )).decimals
        borrow_price_decimals = (await oracle_contract.functions['get_spot_decimals'].call(
            pair_id=borrow_pair_id
        )).decimals

        balance_in_wei = (await z_token_contract.functions['balanceOf'].call(
            account.address
        )).balance

        collateral_factor = borrow_reserve_data.data['collateral_factor'] / 10 ** 27

        max_borrow_amount_in_wei = int(
            balance_in_wei / 10 ** collateral_token.decimals * collateral_token_price /
            borrow_token_price * 10 ** borrow_token.decimals * collateral_factor
        )

        if percentage == 100:
            amount_in_wei = max_borrow_amount_in_wei
        else:
            amount_in_wei = int(max_borrow_amount_in_wei * percentage / 100)

        amount = amount_in_wei / 10 ** borrow_token.decimals
    else:
        amount_in_wei = int(amount * 10 ** borrow_token.decimals)

    logging.info(f'[zkLend] Borrowing {amount} {token_name}')

    resp = await account.execute(
        calls=[
            market_contract.functions['borrow'].prepare(
                token=borrow_token.int_contract_address,
                amount=amount_in_wei
            )
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[zkLend] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='zkLend'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[zkLend] Successfully borrowed {amount} {token_name}')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[zkLend Failed to borrow {amount} {token_name}')
        return enums.TransactionStatus.FAILED


async def repay(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    token_name: enums.TokenNames,
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

    with open(Path(__file__).parent / 'abi' / 'Market.json') as file:
        market_abi = json.load(file)

    market_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.MARKET][network_name],
        abi=market_abi,
        provider=account
    )

    token = constants.NETWORK_TOKENS[network_name, token_name]

    token_contract = utils.get_starknet_erc20_contract(
        token_address=token.contract_address,
        provider=account
    )

    debt_in_wei = (await market_contract.functions['get_user_debt_for_token'].call(
        user=account.address,
        token=token.int_contract_address
    )).debt

    if amount is None:
        if percentage == 100:
            amount_in_wei = debt_in_wei
        else:
            amount_in_wei = int(debt_in_wei * percentage / 100)
    else:
        amount_in_wei = int(amount * 10 ** token.decimals)

    token_balance = await account.get_balance(token.int_contract_address)

    amount_in_wei = min(amount_in_wei, token_balance)
    amount = amount_in_wei / 10 ** token.decimals

    logging.info(f'[zkLend] Repaying {amount} {token_name}')

    allow_call = token_contract.functions['approve'].prepare(
        spender=market_contract.address,
        amount=amount_in_wei
    )

    repay_call = market_contract.functions['repay'].prepare(
        token=token.int_contract_address,
        amount=amount_in_wei
    )

    resp = await account.execute(
        calls=[
            allow_call,
            repay_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[zkLend] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='zkLend'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[zkLend] Successfully repaid {amount} {token_name}')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[zkLend Failed to repay {amount} {token_name}')
        return enums.TransactionStatus.FAILED


async def withdraw(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    token_name: enums.TokenNames,
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

    with open(Path(__file__).parent / 'abi' / 'Market.json') as file:
        market_abi = json.load(file)

    market_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.MARKET][network_name],
        abi=market_abi,
        provider=account
    )

    token = constants.NETWORK_TOKENS[network_name, token_name]

    reserve_data = await market_contract.functions['get_reserve_data'].call(
        token=token.int_contract_address
    )

    z_token_contract = utils.get_starknet_erc20_contract(
        token_address=reserve_data.data['z_token_address'],
        provider=account
    )

    balance_in_wei = (await z_token_contract.functions['balanceOf'].call(
        account.address
    )).balance

    if amount is None:
        borrow_token_name = enums.TokenNames.USDC
        borrow_token = constants.NETWORK_TOKENS[network_name, borrow_token_name]

        debt_in_wei = (await market_contract.functions['get_user_debt_for_token'].call(
            user=account.address,
            token=borrow_token.int_contract_address
        )).debt

        supply_token_price = await get_token_price(
            account=account,
            network_name=network_name,
            token_name=token_name
        )

        borrow_token_price = await get_token_price(
            account=account,
            network_name=network_name,
            token_name=borrow_token_name
        )

        borrow_reserve_data = await market_contract.functions['get_reserve_data'].call(
            token=borrow_token.int_contract_address
        )

        collateral_factor = borrow_reserve_data.data['collateral_factor'] / 10 ** 27

        max_borrow_amount_in_wei = int(
            balance_in_wei / 10 ** token.decimals * supply_token_price /
            borrow_token_price * 10 ** borrow_token.decimals * collateral_factor
        )

        borrow_percentage = debt_in_wei / max_borrow_amount_in_wei

        max_withdraw_amount = int(
            balance_in_wei * (1 - borrow_percentage * 2)
        )

        if percentage == 100:
            amount_in_wei = max_withdraw_amount
        else:
            amount_in_wei = int(max_withdraw_amount * percentage / 100)
        amount = amount_in_wei / 10 ** token.decimals
    else:
        amount_in_wei = int(amount * 10 ** token.decimals)

    logging.info(f'[zkLend] Withdrawing {amount} {token_name}')

    call = market_contract.functions['withdraw'].prepare(
        token=token.int_contract_address,
        amount=amount_in_wei
    )

    resp = await account.execute(
        calls=[
            call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[zkLend] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='zkLend'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[zkLend] Successfully withdrew {amount} {token_name}')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[zkLend Failed to withdraw {amount} {token_name}')
        return enums.TransactionStatus.FAILED
