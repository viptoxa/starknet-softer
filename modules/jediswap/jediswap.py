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
        enums.NetworkNames.Starknet: '0x041fd22b238fa21cfcf5dd45a8548974d8263b3a531a60388411c5e230f97023',
        enums.NetworkNames.StarknetTestnet: '0x02bcc885342ebbcbcd170ae6cafa8a4bed22bb993479f49806e72d96af94c965',
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

    logging.info(f'[JediSwap] Swapping {amount} {from_token_name} to {to_token_name}')

    approve_call = from_token_contract.functions['approve'].prepare(
        spender=router_contract.address,
        amount=amount_in_wei
    )

    block_timestamp = (await account.client.get_block()).timestamp

    deadline = block_timestamp + 3600

    path = [
        int(from_token.contract_address, 16),
        int(to_token.contract_address, 16)
    ]

    optimal_amounts = await router_contract.functions['get_amounts_out'].call(
        amountIn=amount_in_wei,
        path=path
    )

    amount_out_min = int(optimal_amounts.amounts[-1] * (1 - slippage / 100))

    swap_call = router_contract.functions['swap_exact_tokens_for_tokens'].prepare(
        amountIn=amount_in_wei,
        amountOutMin=amount_out_min,
        path=[
            int(from_token.contract_address, 16),
            int(to_token.contract_address, 16)
        ],
        deadline=deadline,
        to=account.address
    )

    resp = await account.execute(
        [
            approve_call,
            swap_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[JediSwap] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='JediSwap'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[JediSwap] Successfully swapped {amount} {from_token_name} to {to_token_name}')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[JediSwap] Failed to swap {amount} {from_token_name} to {to_token_name}')
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

    logging.info(f'[JediSwap] Adding {amount} {first_token_name} to {first_token_name}/{second_token_name} liquidity pool')

    second_token_balance = await account.get_balance(second_token.contract_address)

    optimal_amounts = await router_contract.functions['get_amounts_out'].call(
        amountIn=amount_in_wei,
        path=[
            int(first_token.contract_address, 16),
            int(second_token.contract_address, 16)
        ]
    )

    first_token_desired, second_token_desired = optimal_amounts.amounts

    if second_token_balance < second_token_desired:
        amount /= 2
        amount_in_wei //= 2

        logging.info(f'[JediSwap] Swapping {amount} {first_token_name} to {second_token_name} to add liquidity')

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

        optimal_amounts = await router_contract.functions['get_amounts_out'].call(
            amountIn=amount_in_wei,
            path=[
                int(first_token.contract_address, 16),
                int(second_token.contract_address, 16)
            ]
        )

        first_token_desired, second_token_desired = optimal_amounts.amounts

    first_token_balance = await account.get_balance(first_token.contract_address)
    second_token_balance = await account.get_balance(second_token.contract_address)

    price = (second_token_desired / 10 ** second_token.decimals) / (first_token_desired / 10 ** first_token.decimals)

    if second_token_balance < second_token_desired:
        second_token_desired = second_token_balance
        first_token_desired = int(second_token_desired / 10 ** second_token.decimals / price * 10 ** first_token.decimals)

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

    sorted_tokens = await router_contract.functions['sort_tokens'].call(
        tokenA=int(first_token.contract_address, 16),
        tokenB=int(second_token.contract_address, 16)
    )

    if sorted_tokens.token0 != int(first_token.contract_address, 16):
        first_token_desired, second_token_desired = second_token_desired, first_token_desired

    deadline = (await account.client.get_block()).timestamp + 3600

    add_liquidity_call = router_contract.functions['add_liquidity'].prepare(
        tokenA=sorted_tokens.token0,
        tokenB=sorted_tokens.token1,
        amountADesired=first_token_desired,
        amountBDesired=second_token_desired,
        amountAMin=int(first_token_desired * (1 - slippage / 100)),
        amountBMin=int(second_token_desired * (1 - slippage / 100)),
        to=account.address,
        deadline=deadline
    )

    resp = await account.execute(
        [
            *approve_calls,
            add_liquidity_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[JediSwap] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='JediSwap'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[JediSwap] Successfully added liquidity to {first_token_name}/{second_token_name} pool')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[JediSwap] Failed to add liquidity to {first_token_name}/{second_token_name} pool')
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

    factory_address = (await router_contract.functions['factory'].call()).address

    with open(Path(__file__).parent / 'abi' / 'Factory.json') as file:
        factory_abi = json.load(file)

    factory_contract = utils.get_starknet_contract(
        address=factory_address,
        abi=factory_abi,
        provider=account
    )

    first_token = constants.NETWORK_TOKENS[network_name, first_token_name]
    second_token = constants.NETWORK_TOKENS[network_name, second_token_name]

    logging.info(f'[JediSwap] Removing {percentage}% of {first_token_name}/{second_token_name} liquidity pool')

    sorted_tokens = await router_contract.functions['sort_tokens'].call(
        tokenA=int(first_token.contract_address, 16),
        tokenB=int(second_token.contract_address, 16)
    )

    pair_address = (await factory_contract.functions['get_pair'].call(
        token0=sorted_tokens.token0,
        token1=sorted_tokens.token1
    )).pair

    with open(Path(__file__).parent / 'abi' / 'Pair.json') as file:
        pair_abi = json.load(file)

    pair_contract = utils.get_starknet_contract(
        address=pair_address,
        abi=pair_abi,
        provider=account
    )

    liquidity = (await pair_contract.functions['balanceOf'].call(
        account.address
    )).balance

    if percentage != 100:
        liquidity = int(liquidity * percentage / 100)

    total_supply = (await pair_contract.functions['totalSupply'].call()).totalSupply
    reserves = await pair_contract.functions['get_reserves'].call()

    token0_desired = liquidity / total_supply * reserves.reserve0
    token1_desired = liquidity / total_supply * reserves.reserve1

    token0_min = int(token0_desired * (1 - slippage / 100))
    token1_min = int(token1_desired * (1 - slippage / 100))

    deadline = (await account.client.get_block()).timestamp + 3600

    approve_call = pair_contract.functions['approve'].prepare(
        spender=router_contract.address,
        amount=liquidity
    )

    remove_liquidity_call = router_contract.functions['remove_liquidity'].prepare(
        tokenA=sorted_tokens.token0,
        tokenB=sorted_tokens.token1,
        liquidity=liquidity,
        amountAMin=token0_min,
        amountBMin=token1_min,
        to=account.address,
        deadline=deadline
    )

    resp = await account.execute(
        [
            approve_call,
            remove_liquidity_call
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[JediSwap] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='JediSwap'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[JediSwap] Successfully removed liquidity from {first_token_name}/{second_token_name} pool')
    else:
        logging.error(f'[JediSwap] Failed to remove liquidity from {first_token_name}/{second_token_name} pool')
        return enums.TransactionStatus.SUCCESS

    utils.random_sleep()

    second_token_balance = await account.get_balance(second_token.contract_address)

    second_token_desired = token1_desired

    if sorted_tokens.token1 != second_token.int_contract_address:
        second_token_desired = token0_desired

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
        logging.error(f'[JediSwap] Failed to swap {second_token_name} to {first_token_name}. Advise to swap manually')

    return enums.TransactionStatus.SUCCESS
