import json
from pathlib import Path

from starknet_py.net.client_models import TransactionExecutionStatus

import constants
import enums
import utils
from logger import logging


class ContractTypes(enums.AutoEnum):
    ROUTER = enums.auto()


CONTRACT_ADRESSES = {
    ContractTypes.ROUTER: {
        enums.NetworkNames.Starknet: '0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28',
        enums.NetworkNames.StarknetTestnet: '0x018a439bcbb1b3535a6145c1dc9bc6366267d923f60a84bd0c7618f33c81d334',
    }
}

POOL_IDS = {
    enums.NetworkNames.Starknet: {
        frozenset({enums.TokenNames.ETH, enums.TokenNames.USDC}): 1,
        frozenset({enums.TokenNames.ETH, enums.TokenNames.DAI}): 2,
        frozenset({enums.TokenNames.ETH, enums.TokenNames.USDT}): 4,
        frozenset({enums.TokenNames.USDC, enums.TokenNames.USDT}): 5,
        frozenset({enums.TokenNames.USDC, enums.TokenNames.DAI}): 6,
    },
    enums.NetworkNames.StarknetTestnet: {
        frozenset({enums.TokenNames.ETH, enums.TokenNames.USDC}): 1,
        frozenset({enums.TokenNames.ETH, enums.TokenNames.DAI}): 2,
        frozenset({enums.TokenNames.USDC, enums.TokenNames.DAI}): 3
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

    with open(Path(__file__).parent / 'abi' / 'Router.json') as file:
        router_abi = json.load(file)

    router_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.ROUTER][network_name],
        abi=router_abi,
        provider=account
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

    logging.info(f'[mySwap] Swapping {amount} {from_token_name} to {to_token_name}')

    tokens_set = frozenset({from_token_name, to_token_name})

    if tokens_set not in POOL_IDS[network_name]:
        logging.error(f'[mySwap] Selected incorrect pool: {from_token_name}/{to_token_name}')
        return enums.TransactionStatus.FAILED

    pool_id = POOL_IDS[network_name][tokens_set]

    pool_info = await router_contract.functions['get_pool'].call(
        pool_id
    )

    token_addresses = {
        pool_info.pool['token_a_address'],
        pool_info.pool['token_b_address']
    }

    if {from_token.int_contract_address, to_token.int_contract_address} != token_addresses:
        logging.error(f'[mySwap] Selected incorrect pool: {from_token_name}/{to_token_name}')
        return enums.TransactionStatus.FAILED

    from_token_reserve = pool_info.pool['token_a_reserves']
    to_token_reserve = pool_info.pool['token_b_reserves']

    if to_token < from_token:
        from_token_reserve, to_token_reserve = to_token_reserve, from_token_reserve

    price = (to_token_reserve / 10 ** to_token.decimals) / (from_token_reserve / 10 ** from_token.decimals)

    amount_to_min = int(amount * price * 10 ** to_token.decimals * (1 - slippage / 100))

    approve_call = from_token_contract.functions['approve'].prepare(
        spender=router_contract.address,
        amount=amount_in_wei
    )

    swap_call = router_contract.functions['swap'].prepare(
        pool_id=pool_id,
        token_from_addr=from_token.int_contract_address,
        amount_from=amount_in_wei,
        amount_to_min=amount_to_min,
    )

    resp = await account.execute(
        [
            approve_call,
            swap_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[mySwap] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='mySwap'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[mySwap] Successfully swapped {amount} {from_token_name} to {to_token_name}')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[mySwap] Failed to swap {amount} {from_token_name} to {to_token_name}')
        return enums.TransactionStatus.FAILED


async def add_liquidity(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    first_token_name: enums.TokenNames,
    second_token_name: enums.TokenNames,
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

    with open(Path(__file__).parent / 'abi' / 'Router.json') as file:
        router_abi = json.load(file)

    router_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.ROUTER][network_name],
        abi=router_abi,
        provider=account
    )

    first_token = constants.NETWORK_TOKENS[network_name, first_token_name]
    second_token = constants.NETWORK_TOKENS[network_name, second_token_name]

    first_token_contract = utils.get_starknet_erc20_contract(
        token_address=first_token.contract_address,
        provider=account
    )
    second_token_contract = utils.get_starknet_erc20_contract(
        token_address=second_token.contract_address,
        provider=account
    )

    amount_in_wei = await account.get_balance(first_token.contract_address)

    if amount is None:
        if percentage == 100:
            amount_in_wei = amount_in_wei
        else:
            amount_in_wei = int(amount_in_wei * percentage / 100)
        amount = amount_in_wei / 10 ** first_token.decimals
    else:
        amount_in_wei = int(amount * 10 ** first_token.decimals)

    logging.info(f'[mySwap] Adding {amount} {first_token_name} to {first_token_name}/{second_token_name} liquidity pool')

    second_token_balance = await account.get_balance(second_token.contract_address)

    tokens_set = frozenset({first_token_name, second_token_name})

    if tokens_set not in POOL_IDS[network_name]:
        logging.error(f'[mySwap] Selected incorrect pool: {first_token_name}/{second_token_name}')
        return enums.TransactionStatus.FAILED

    pool_id = POOL_IDS[network_name][tokens_set]

    pool_info = await router_contract.functions['get_pool'].call(
        pool_id
    )

    token_addresses = {
        pool_info.pool['token_a_address'],
        pool_info.pool['token_b_address']
    }

    if {first_token.int_contract_address, second_token.int_contract_address} != token_addresses:
        logging.error(f'[mySwap] Selected incorrect pool: {first_token_name}/{second_token_name}')
        return enums.TransactionStatus.FAILED

    from_token_reserve = pool_info.pool['token_a_reserves']
    to_token_reserve = pool_info.pool['token_b_reserves']

    if second_token < first_token:
        from_token_reserve, to_token_reserve = to_token_reserve, from_token_reserve

    price = (to_token_reserve / 10 ** second_token.decimals) / (from_token_reserve / 10 ** first_token.decimals)

    second_token_desired = int(amount * price * 10 ** second_token.decimals)

    if second_token_balance < second_token_desired:
        amount /= 2
        amount_in_wei //= 2

        logging.info(f'[mySwap] Swapping {amount} {first_token_name} to {second_token_name} to add liquidity')

        swap_result = await swap(
            private_key=private_key,
            address=address,
            network_name=network_name,
            from_token_name=first_token_name,
            to_token_name=second_token_name,
            slippage=slippage,
            cairo_version=cairo_version,
            amount=amount,
            proxy=proxy
        )

        if swap_result != enums.TransactionStatus.SUCCESS:
            return swap_result

        utils.random_sleep()

        second_token_desired = int(amount * price * 10 ** second_token.decimals)

    first_token_balance = await account.get_balance(first_token.contract_address)
    second_token_balance = await account.get_balance(second_token.contract_address)

    first_token_desired = amount_in_wei

    price = (second_token_desired / 10 ** second_token.decimals) / (first_token_desired / 10 ** first_token.decimals)

    if second_token_balance < second_token_desired:
        second_token_desired = second_token_balance
        first_token_desired = int(second_token_desired / 10 ** second_token.decimals / price * 10 ** first_token.decimals)

    first_token_min = int(first_token_desired * (1 - slippage / 100))
    second_token_min = int(second_token_desired * (1 - slippage / 100))

    approve_calls = [
        first_token_contract.functions['approve'].prepare(
            spender=router_contract.address,
            amount=first_token_desired
        ),
        second_token_contract.functions['approve'].prepare(
            spender=router_contract.address,
            amount=second_token_desired
        )
    ]

    add_liquidity_call = router_contract.functions['add_liquidity'].prepare(
        a_address=first_token.int_contract_address,
        a_amount=first_token_desired,
        a_min_amount=first_token_min,
        b_address=second_token.int_contract_address,
        b_amount=second_token_desired,
        b_min_amount=second_token_min
    )

    resp = await account.execute(
        [
            *approve_calls,
            add_liquidity_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[mySwap] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='mySwap'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[mySwap] Successfully added liquidity to {first_token_name}/{second_token_name} pool')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[mySwap] Failed to add liquidity to {first_token_name}/{second_token_name} pool')
        return enums.TransactionStatus.FAILED


async def remove_liquidity(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    first_token_name: enums.TokenNames,
    second_token_name: enums.TokenNames,
    slippage: float,
    cairo_version: int,
    percentage: float = 100,
    proxy: dict[str, str] = None
) -> enums.TransactionStatus:
    network = constants.NETWORKS[network_name]

    account = utils.get_account(
        network_name=network_name,
        private_key=private_key,
        address=address,
        proxy=proxy
    )

    with open(Path(__file__).parent / 'abi' / 'Router.json') as file:
        router_abi = json.load(file)

    router_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.ROUTER][network_name],
        abi=router_abi,
        provider=account
    )

    logging.info(f'[mySwap] Removing {percentage}% of {first_token_name}/{second_token_name} liquidity pool')

    first_token = original_first_token = constants.NETWORK_TOKENS[network_name, first_token_name]
    second_token = original_second_token = constants.NETWORK_TOKENS[network_name, second_token_name]

    tokens_set = frozenset({first_token_name, second_token_name})

    if tokens_set not in POOL_IDS[network_name]:
        logging.error(f'[mySwap] Selected incorrect pool: {first_token_name}/{second_token_name}')
        return enums.TransactionStatus.FAILED

    pool_id = POOL_IDS[network_name][tokens_set]

    pool_info = await router_contract.functions['get_pool'].call(
        pool_id
    )

    token_addresses = {
        pool_info.pool['token_a_address'],
        pool_info.pool['token_b_address']
    }

    if {first_token.int_contract_address, second_token.int_contract_address} != token_addresses:
        logging.error(f'[mySwap] Selected incorrect pool: {first_token_name}/{second_token_name}')
        return enums.TransactionStatus.FAILED

    first_token_reserve = pool_info.pool['token_a_reserves']
    second_token_reserve = pool_info.pool['token_b_reserves']

    if second_token < first_token:
        first_token, second_token = second_token, first_token

    liq_token_address = pool_info.pool['liq_token']

    liq_token_contract = utils.get_starknet_erc20_contract(
        token_address=liq_token_address,
        provider=account
    )

    total_supply = (await liq_token_contract.functions['totalSupply'].call()).totalSupply
    balance = (await liq_token_contract.functions['balanceOf'].call(account.address)).balance

    liquidity_desired = int(balance * percentage / 100)

    first_token_desired = liquidity_desired / total_supply * first_token_reserve
    second_token_desired = liquidity_desired / total_supply * second_token_reserve

    first_token_min = int(first_token_desired * (1 - slippage / 100))
    second_token_min = int(second_token_desired * (1 - slippage / 100))

    approve_call = liq_token_contract.functions['approve'].prepare(
        spender=router_contract.address,
        amount=liquidity_desired
    )

    remove_liquidity_call = router_contract.functions['withdraw_liquidity'].prepare(
        pool_id=pool_id,
        shares_amount=liquidity_desired,
        amount_min_a=first_token_min,
        amount_min_b=second_token_min
    )

    resp = await account.execute(
        [
            approve_call,
            remove_liquidity_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[mySwap] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='mySwap'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[mySwap] Successfully removed liquidity from {first_token_name}/{second_token_name} pool')
    else:
        logging.error(f'[mySwap] Failed to remove liquidity from {first_token_name}/{second_token_name} pool')
        return enums.TransactionStatus.FAILED

    utils.random_sleep()

    if original_first_token != first_token:
        second_token_desired = first_token_desired

    second_token_balance = await account.get_balance(original_second_token.contract_address)

    swap_amount = min(second_token_desired, second_token_balance)

    if swap_amount == second_token_balance:
        swap_percentage = 100
    else:
        swap_percentage = swap_amount / second_token_balance * 100

    swap_result = await swap(
        private_key=private_key,
        address=address,
        network_name=network_name,
        from_token_name=second_token_name,
        to_token_name=first_token_name,
        slippage=slippage,
        cairo_version=cairo_version,
        percentage=swap_percentage,
        proxy=proxy
    )

    if swap_result != enums.TransactionStatus.SUCCESS:
        logging.error(f'[mySwap] Failed to swap {second_token_name} to {first_token_name}. Advise to swap manually')

    return enums.TransactionStatus.SUCCESS
