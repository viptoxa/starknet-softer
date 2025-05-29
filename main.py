import asyncio
import copy
import json
import random
import traceback
from collections import defaultdict
from pathlib import Path

import requests

import accounts_loader
import constants
import enums
import modules
import utils
from file_logger import file_logger
from logger import logging

USE_TESTNET = False


async def run_function(
    bot_account: accounts_loader.BotAccount,
    network_name: enums.NetworkNames,
    task: accounts_loader.Task,
    function_name: enums.FunctionNames
):
    max_retries = max(bot_account.max_retries, 0)

    function_result = enums.TransactionStatus.SUCCESS

    for retry in range(max_retries + 1):
        try:
            if task.module_name == enums.ModuleNames.Avnu:
                from_token_name = task.module_kwargs.get('from_token_name', enums.TokenNames.ETH)
                to_token_name = task.module_kwargs.get('to_token_name', enums.TokenNames.USDT)
                if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                    min_amount_usd = task.module_kwargs['min_amount_usd']
                    max_amount_usd = task.module_kwargs['max_amount_usd']
                    min_amount = utils.usd_to_token(
                        token_name=from_token_name,
                        usd=min_amount_usd,
                        proxy=bot_account.proxy
                    )
                    max_amount = utils.usd_to_token(
                        token_name=from_token_name,
                        usd=max_amount_usd,
                        proxy=bot_account.proxy
                    )
                    amount = random.uniform(min_amount, max_amount)
                    percentage = None
                else:
                    min_percentage = task.module_kwargs.get('min_percentage', 1)
                    max_percentage = task.module_kwargs.get('max_percentage', 90)
                    percentage = round(random.uniform(min_percentage, max_percentage), 2)
                    amount = None
                slippage = task.module_kwargs.get('slippage', 1)
                function_result = await modules.avnu.swap(
                    private_key=bot_account.private_key,
                    address=bot_account.address,
                    network_name=network_name,
                    from_token_name=from_token_name,
                    to_token_name=to_token_name,
                    slippage=slippage,
                    cairo_version=bot_account.cairo_version,
                    amount=amount,
                    percentage=percentage,
                    proxy=bot_account.proxy
                )
            elif task.module_name == enums.ModuleNames.Deploy:
                function_result = await modules.wallet.deploy(
                    private_key=bot_account.private_key,
                    address=bot_account.address,
                    network_name=network_name,
                    wallet_name=bot_account.wallet_name,
                    proxy=bot_account.proxy
                )
            elif task.module_name == enums.ModuleNames.Dmail:
                function_result = await modules.dmail.send_email(
                    private_key=bot_account.private_key,
                    address=bot_account.address,
                    network_name=network_name,
                    cairo_version=bot_account.cairo_version,
                    proxy=bot_account.proxy
                )
            elif task.module_name == enums.ModuleNames.Fibrous:
                from_token_name = task.module_kwargs.get('from_token_name', enums.TokenNames.ETH)
                to_token_name = task.module_kwargs.get('to_token_name', enums.TokenNames.USDT)
                if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                    min_amount_usd = task.module_kwargs['min_amount_usd']
                    max_amount_usd = task.module_kwargs['max_amount_usd']
                    min_amount = utils.usd_to_token(
                        token_name=from_token_name,
                        usd=min_amount_usd,
                        proxy=bot_account.proxy
                    )
                    max_amount = utils.usd_to_token(
                        token_name=from_token_name,
                        usd=max_amount_usd,
                        proxy=bot_account.proxy
                    )
                    amount = random.uniform(min_amount, max_amount)
                    percentage = None
                else:
                    min_percentage = task.module_kwargs.get('min_percentage', 1)
                    max_percentage = task.module_kwargs.get('max_percentage', 90)
                    percentage = round(random.uniform(min_percentage, max_percentage), 2)
                    amount = None
                slippage = task.module_kwargs.get('slippage', 1)
                function_result = await modules.fibrous.swap(
                    private_key=bot_account.private_key,
                    address=bot_account.address,
                    network_name=network_name,
                    from_token_name=from_token_name,
                    to_token_name=to_token_name,
                    slippage=slippage,
                    cairo_version=bot_account.cairo_version,
                    amount=amount,
                    percentage=percentage,
                    proxy=bot_account.proxy
                )
            elif task.module_name == enums.ModuleNames.JediSwap:
                if function_name == enums.FunctionNames.SWAP:
                    from_token_name = task.module_kwargs.get('from_token_name', enums.TokenNames.ETH)
                    to_token_name = task.module_kwargs.get('to_token_name', enums.TokenNames.USDT)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=from_token_name,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=from_token_name,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 1)
                        max_percentage = task.module_kwargs.get('max_percentage', 90)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    slippage = task.module_kwargs.get('slippage', 2)
                    function_result = await modules.jediswap.swap(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        from_token_name=from_token_name,
                        to_token_name=to_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        amount=amount,
                        percentage=percentage,
                        proxy=bot_account.proxy
                    )
                elif function_name == enums.FunctionNames.ADD_LIQUIDITY:
                    first_token_name = task.module_kwargs.get('first_token_name', enums.TokenNames.ETH)
                    second_token_name = task.module_kwargs.get('second_token_name', enums.TokenNames.USDC)
                    slippage = task.module_kwargs.get('slippage', 2)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=first_token_name,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=first_token_name,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 1)
                        max_percentage = task.module_kwargs.get('max_percentage', 90)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    function_result = await modules.jediswap.add_liquidity(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        first_token_name=first_token_name,
                        second_token_name=second_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        amount=amount,
                        percentage=percentage,
                        proxy=bot_account.proxy
                    )
                elif function_name == enums.FunctionNames.REMOVE_LIQUIDITY:
                    first_token_name = task.module_kwargs.get('first_token_name', enums.TokenNames.ETH)
                    second_token_name = task.module_kwargs.get('second_token_name', enums.TokenNames.USDC)
                    withdraw_percentage = task.module_kwargs.get('withdraw_percentage', 100)
                    slippage = task.module_kwargs.get('slippage', 2)
                    function_result = await modules.jediswap.remove_liquidity(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        first_token_name=first_token_name,
                        second_token_name=second_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        percentage=withdraw_percentage,
                        proxy=bot_account.proxy
                    )
            elif task.module_name == enums.ModuleNames.LayerSwap:
                if task.function_name == enums.FunctionNames.DEPOSIT_TO_STARKNET:
                    if bot_account.evm_private_key is None:
                        logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no EVM private key. LayerSwap Deposit is not possible')
                        return enums.TransactionStatus.FAILED

                    from_network_name = task.module_kwargs.get('from_network', enums.NetworkNames.ETH)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    elif 'min_amount' in task.module_kwargs and 'max_amount' in task.module_kwargs:
                        min_amount = task.module_kwargs['min_amount']
                        max_amount = task.module_kwargs['max_amount']
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 100)
                        max_percentage = task.module_kwargs.get('max_percentage', 100)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    wait_for_receive = task.module_kwargs.get('wait_for_receive', True)

                    destination_address_str = task.module_kwargs.get('destination_address', None)

                    if destination_address_str == 'starknet_deposit_address':
                        destination_address = getattr(bot_account, destination_address_str)

                        if not destination_address:
                            logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no {destination_address_str}. Layerswap bridge is not possible')
                            return enums.TransactionStatus.FAILED
                    elif destination_address_str is not None:
                        destination_address = destination_address_str
                    else:
                        destination_address = bot_account.address

                    function_result = await modules.layerswap.deposit_to_starknet(
                        private_key=bot_account.evm_private_key,
                        from_network_name=from_network_name,
                        to_network_name=enums.NetworkNames.StarknetTestnet if USE_TESTNET else enums.NetworkNames.Starknet,
                        to_private_key=bot_account.private_key,
                        to_address=destination_address,
                        percentage=percentage,
                        amount=amount,
                        wait_for_receive=wait_for_receive,
                        proxy=bot_account.proxy
                    )
                elif task.function_name == enums.FunctionNames.WITHDRAW_FROM_STARKNET:
                    to_network_name = task.module_kwargs.get('to_network', enums.NetworkNames.ETH)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    elif 'min_amount' in task.module_kwargs and 'max_amount' in task.module_kwargs:
                        min_amount = task.module_kwargs['min_amount']
                        max_amount = task.module_kwargs['max_amount']
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 100)
                        max_percentage = task.module_kwargs.get('max_percentage', 100)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    wait_for_receive = task.module_kwargs.get('wait_for_receive', True)

                    destination_address_str = task.module_kwargs.get('destination_address', None)

                    if destination_address_str == 'evm_deposit_address':
                        destination_address = getattr(bot_account, destination_address_str)

                        if not destination_address:
                            logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no {destination_address_str}. Layerswap bridge is not possible')
                            return enums.TransactionStatus.FAILED
                    elif destination_address_str is not None:
                        destination_address = destination_address_str
                    else:
                        destination_address = bot_account.evm_address

                    function_result = await modules.layerswap.withdraw_from_starknet(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        from_network_name=enums.NetworkNames.StarknetTestnet if USE_TESTNET else enums.NetworkNames.Starknet,
                        to_network_name=to_network_name,
                        to_address=destination_address,
                        cairo_version=bot_account.cairo_version,
                        percentage=percentage,
                        amount=amount,
                        wait_for_receive=wait_for_receive,
                        proxy=bot_account.proxy
                    )
            elif task.module_name == enums.ModuleNames.mySwap:
                if function_name == enums.FunctionNames.SWAP:
                    from_token_name = task.module_kwargs.get('from_token_name', enums.TokenNames.ETH)
                    to_token_name = task.module_kwargs.get('to_token_name', enums.TokenNames.USDT)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=from_token_name,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=from_token_name,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 1)
                        max_percentage = task.module_kwargs.get('max_percentage', 90)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    slippage = task.module_kwargs.get('slippage', 2)
                    function_result = await modules.myswap.swap(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        from_token_name=from_token_name,
                        to_token_name=to_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        amount=amount,
                        percentage=percentage,
                        proxy=bot_account.proxy
                    )
                elif function_name == enums.FunctionNames.ADD_LIQUIDITY:
                    first_token_name = task.module_kwargs.get('first_token_name', enums.TokenNames.ETH)
                    second_token_name = task.module_kwargs.get('second_token_name', enums.TokenNames.USDC)
                    slippage = task.module_kwargs.get('slippage', 2)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=first_token_name,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=first_token_name,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 1)
                        max_percentage = task.module_kwargs.get('max_percentage', 90)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    function_result = await modules.myswap.add_liquidity(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        first_token_name=first_token_name,
                        second_token_name=second_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        amount=amount,
                        percentage=percentage,
                        proxy=bot_account.proxy
                    )
                elif function_name == enums.FunctionNames.REMOVE_LIQUIDITY:
                    first_token_name = task.module_kwargs.get('first_token_name', enums.TokenNames.ETH)
                    second_token_name = task.module_kwargs.get('second_token_name', enums.TokenNames.USDC)
                    withdraw_percentage = task.module_kwargs.get('withdraw_percentage', 100)
                    slippage = task.module_kwargs.get('slippage', 2)
                    function_result = await modules.myswap.remove_liquidity(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        first_token_name=first_token_name,
                        second_token_name=second_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        percentage=withdraw_percentage,
                        proxy=bot_account.proxy
                    )
            elif task.module_name == enums.ModuleNames.OKX:
                if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                    min_amount_usd = task.module_kwargs['min_amount_usd']
                    max_amount_usd = task.module_kwargs['max_amount_usd']
                    min_amount = utils.usd_to_token(
                        token_name=enums.TokenNames.ETH,
                        usd=min_amount_usd,
                        proxy=bot_account.proxy
                    )
                    max_amount = utils.usd_to_token(
                        token_name=enums.TokenNames.ETH,
                        usd=max_amount_usd,
                        proxy=bot_account.proxy
                    )
                    amount = random.uniform(min_amount, max_amount)
                    percentage = None
                elif 'min_amount' in task.module_kwargs and 'max_amount' in task.module_kwargs:
                    min_amount = task.module_kwargs['min_amount']
                    max_amount = task.module_kwargs['max_amount']
                    amount = random.uniform(min_amount, max_amount)
                    percentage = None
                else:
                    min_percentage = task.module_kwargs.get('min_percentage', 50)
                    max_percentage = task.module_kwargs.get('max_percentage', 100)
                    percentage = round(random.uniform(min_percentage, max_percentage), 2)
                    amount = None
                wait_for_receive = task.module_kwargs.get('wait_for_receive', True)
                if task.function_name == enums.FunctionNames.DEPOSIT_TO_OKX:
                    from_network_name = task.module_kwargs.get('from_network', enums.NetworkNames.Starknet)
                    min_deposit_amount = task.module_kwargs.get('min_deposit_amount', 0)
                    if from_network_name in {
                        enums.NetworkNames.Starknet,
                        enums.NetworkNames.StarknetTestnet
                    }:
                        if bot_account.starknet_deposit_address is None:
                            logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no starknet deposit address. OKX Deposit is not possible')
                            return enums.TransactionStatus.FAILED
                        function_result = await modules.okx_module.deposit_to_okx_from_starknet(
                            private_key=bot_account.private_key,
                            address=bot_account.address,
                            network_name=from_network_name,
                            to_address=bot_account.starknet_deposit_address,
                            cairo_version=bot_account.cairo_version,
                            amount=amount,
                            percentage=percentage,
                            min_deposit_amount=min_deposit_amount,
                            wait_for_receive=wait_for_receive,
                            proxy=bot_account.proxy
                        )
                    else:
                        if bot_account.evm_deposit_address is None:
                            logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no EVM deposit address. OKX Deposit is not possible')
                            return enums.TransactionStatus.FAILED
                        function_result = modules.okx_module.deposit_to_okx_from_evm(
                            private_key=bot_account.evm_private_key,
                            network_name=from_network_name,
                            to_address=bot_account.evm_deposit_address,
                            amount=amount,
                            percentage=percentage,
                            min_deposit_amount=min_deposit_amount,
                            wait_for_receive=wait_for_receive,
                            proxy=bot_account.proxy
                        )
                elif task.function_name == enums.FunctionNames.WITHDRAW_FROM_OKX:
                    if not all([
                        bot_account.okx_api_key,
                        bot_account.okx_secret_key,
                        bot_account.okx_passphrase
                    ]):
                        logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no OKX API credentials. OKX Withdrawal is not possible')
                        return enums.TransactionStatus.FAILED
                    to_network_name = task.module_kwargs.get('to_network', enums.NetworkNames.Starknet)

                    if to_network_name in {
                        enums.NetworkNames.Starknet,
                        enums.NetworkNames.StarknetTestnet
                    }:
                        to_address = bot_account.address
                    else:
                        if bot_account.evm_address is None:
                            logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no EVM address. OKX Withdrawal is not possible')
                            return enums.TransactionStatus.FAILED
                        to_address = bot_account.evm_address

                    function_result = modules.okx_module.withdraw_from_okx(
                        to_address=to_address,
                        network_name=to_network_name,
                        api_key=bot_account.okx_api_key,
                        api_secret_key=bot_account.okx_secret_key,
                        passphrase=bot_account.okx_passphrase,
                        amount=amount,
                        percentage=percentage,
                        wait_for_receive=wait_for_receive
                    )
                elif task.function_name == enums.FunctionNames.SUBS_TO_MAIN:
                    if not all([
                        bot_account.okx_api_key,
                        bot_account.okx_secret_key,
                        bot_account.okx_passphrase
                    ]):
                        logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no OKX API credentials. OKX Withdrawal is not possible')
                        return enums.TransactionStatus.FAILED
                    function_result = modules.okx_module.transfer_from_subs(
                        api_key=bot_account.okx_api_key,
                        api_secret_key=bot_account.okx_secret_key,
                        passphrase=bot_account.okx_passphrase
                    )
            elif task.module_name == enums.ModuleNames.Orbiter:
                if task.function_name == enums.FunctionNames.DEPOSIT_TO_STARKNET:
                    if bot_account.evm_private_key is None:
                        logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no EVM private key. Orbiter Deposit is not possible')
                        return enums.TransactionStatus.FAILED

                    from_network_name = task.module_kwargs.get('from_network', enums.NetworkNames.ETH)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    elif 'min_amount' in task.module_kwargs and 'max_amount' in task.module_kwargs:
                        min_amount = task.module_kwargs['min_amount']
                        max_amount = task.module_kwargs['max_amount']
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 100)
                        max_percentage = task.module_kwargs.get('max_percentage', 100)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    wait_for_receive = task.module_kwargs.get('wait_for_receive', True)
                    function_result = await modules.orbiter.deposit_to_starknet(
                        private_key=bot_account.evm_private_key,
                        from_network_name=from_network_name,
                        to_network_name=enums.NetworkNames.StarknetTestnet if USE_TESTNET else enums.NetworkNames.Starknet,
                        to_private_key=bot_account.private_key,
                        to_address=bot_account.address,
                        percentage=percentage,
                        amount=amount,
                        wait_for_receive=wait_for_receive,
                        proxy=bot_account.proxy
                    )
                elif task.function_name == enums.FunctionNames.WITHDRAW_FROM_STARKNET:
                    to_network_name = task.module_kwargs.get('to_network', enums.NetworkNames.ETH)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    elif 'min_amount' in task.module_kwargs and 'max_amount' in task.module_kwargs:
                        min_amount = task.module_kwargs['min_amount']
                        max_amount = task.module_kwargs['max_amount']
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 100)
                        max_percentage = task.module_kwargs.get('max_percentage', 100)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    wait_for_receive = task.module_kwargs.get('wait_for_receive', True)
                    function_result = await modules.orbiter.withdraw_from_starknet(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        from_network_name=enums.NetworkNames.StarknetTestnet if USE_TESTNET else enums.NetworkNames.Starknet,
                        to_network_name=to_network_name,
                        to_address=bot_account.evm_address,
                        cairo_version=bot_account.cairo_version,
                        percentage=percentage,
                        amount=amount,
                        wait_for_receive=wait_for_receive,
                        proxy=bot_account.proxy
                    )
            elif task.module_name == enums.ModuleNames.StarkGate:
                if task.function_name == enums.FunctionNames.DEPOSIT_TO_STARKNET:
                    if bot_account.evm_private_key is None:
                        logging.critical(f'[Main] Bot account {bot_account.short_private_key} has no EVM private key. StarkGate Deposit is not possible')
                        return enums.TransactionStatus.FAILED

                    from_network_name = enums.NetworkNames.ETH
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    elif 'min_amount' in task.module_kwargs and 'max_amount' in task.module_kwargs:
                        min_amount = task.module_kwargs['min_amount']
                        max_amount = task.module_kwargs['max_amount']
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 100)
                        max_percentage = task.module_kwargs.get('max_percentage', 100)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    wait_for_receive = task.module_kwargs.get('wait_for_receive', True)
                    function_result = await modules.starkgate.deposit_to_starknet(
                        private_key=bot_account.evm_private_key,
                        from_network_name=from_network_name,
                        to_network_name=enums.NetworkNames.StarknetTestnet if USE_TESTNET else enums.NetworkNames.Starknet,
                        to_private_key=bot_account.private_key,
                        to_address=bot_account.address,
                        percentage=percentage,
                        amount=amount,
                        wait_for_receive=wait_for_receive,
                        proxy=bot_account.proxy
                    )
                elif task.function_name == enums.FunctionNames.WITHDRAW_FROM_STARKNET:
                    to_network_name = enums.NetworkNames.ETH
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=enums.TokenNames.ETH,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    elif 'min_amount' in task.module_kwargs and 'max_amount' in task.module_kwargs:
                        min_amount = task.module_kwargs['min_amount']
                        max_amount = task.module_kwargs['max_amount']
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 100)
                        max_percentage = task.module_kwargs.get('max_percentage', 100)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    wait_for_receive = task.module_kwargs.get('wait_for_receive', True)
                    function_result = await modules.starkgate.withdraw_from_starknet(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        from_network_name=network_name,
                        to_network_name=to_network_name,
                        to_address=bot_account.evm_address,
                        cairo_version=bot_account.cairo_version,
                        percentage=percentage,
                        amount=amount,
                        wait_for_receive=wait_for_receive,
                        proxy=bot_account.proxy
                    )
            elif task.module_name == enums.ModuleNames.StarknetID:
                function_result = await modules.starknet_id.mint(
                    private_key=bot_account.private_key,
                    address=bot_account.address,
                    network_name=network_name,
                    cairo_version=bot_account.cairo_version,
                    proxy=bot_account.proxy
                )
            elif task.module_name == enums.ModuleNames.StarkVerse:
                function_result = await modules.starkverse.mint(
                    private_key=bot_account.private_key,
                    address=bot_account.address,
                    network_name=network_name,
                    cairo_version=bot_account.cairo_version,
                    proxy=bot_account.proxy
                )
            elif task.module_name == enums.ModuleNames.TenKSwap:
                if function_name == enums.FunctionNames.SWAP:
                    from_token_name = task.module_kwargs.get('from_token_name', enums.TokenNames.ETH)
                    to_token_name = task.module_kwargs.get('to_token_name', enums.TokenNames.USDT)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=from_token_name,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=from_token_name,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 1)
                        max_percentage = task.module_kwargs.get('max_percentage', 90)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    slippage = task.module_kwargs.get('slippage', 2)
                    function_result = await modules.tenkswap.swap(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        from_token_name=from_token_name,
                        to_token_name=to_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        amount=amount,
                        percentage=percentage,
                        proxy=bot_account.proxy
                    )
                elif function_name == enums.FunctionNames.ADD_LIQUIDITY:
                    first_token_name = task.module_kwargs.get('first_token_name', enums.TokenNames.ETH)
                    second_token_name = task.module_kwargs.get('second_token_name', enums.TokenNames.USDC)
                    slippage = task.module_kwargs.get('slippage', 2)
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=first_token_name,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=first_token_name,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 1)
                        max_percentage = task.module_kwargs.get('max_percentage', 90)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    function_result = await modules.tenkswap.add_liquidity(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        first_token_name=first_token_name,
                        second_token_name=second_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        amount=amount,
                        percentage=percentage,
                        proxy=bot_account.proxy
                    )
                elif function_name == enums.FunctionNames.REMOVE_LIQUIDITY:
                    first_token_name = task.module_kwargs.get('first_token_name', enums.TokenNames.ETH)
                    second_token_name = task.module_kwargs.get('second_token_name', enums.TokenNames.USDC)
                    withdraw_percentage = task.module_kwargs.get('withdraw_percentage', 100)
                    slippage = task.module_kwargs.get('slippage', 2)
                    function_result = await modules.tenkswap.remove_liquidity(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        first_token_name=first_token_name,
                        second_token_name=second_token_name,
                        slippage=slippage,
                        cairo_version=bot_account.cairo_version,
                        percentage=withdraw_percentage,
                        proxy=bot_account.proxy
                    )
            elif task.module_name == enums.ModuleNames.Upgrade:
                function_result = await modules.wallet.upgrade(
                    private_key=bot_account.private_key,
                    address=bot_account.address,
                    network_name=network_name,
                    wallet_name=bot_account.wallet_name,
                    cairo_version=bot_account.cairo_version,
                    proxy=bot_account.proxy
                )

                if function_result == enums.TransactionStatus.SUCCESS and bot_account.wallet_name == enums.WalletNames.ArgentXOld:
                    bot_account.cairo_version = 1
            elif task.module_name == enums.ModuleNames.zkLend:
                if function_name == enums.FunctionNames.SUPPLY:
                    supply_token_name = enums.TokenNames.ETH
                    if 'min_amount_usd' in task.module_kwargs and 'max_amount_usd' in task.module_kwargs:
                        min_amount_usd = task.module_kwargs['min_amount_usd']
                        max_amount_usd = task.module_kwargs['max_amount_usd']
                        min_amount = utils.usd_to_token(
                            token_name=supply_token_name,
                            usd=min_amount_usd,
                            proxy=bot_account.proxy
                        )
                        max_amount = utils.usd_to_token(
                            token_name=supply_token_name,
                            usd=max_amount_usd,
                            proxy=bot_account.proxy
                        )
                        amount = random.uniform(min_amount, max_amount)
                        percentage = None
                    else:
                        min_percentage = task.module_kwargs.get('min_percentage', 10)
                        max_percentage = task.module_kwargs.get('max_percentage', 90)
                        percentage = round(random.uniform(min_percentage, max_percentage), 2)
                        amount = None
                    function_result = await modules.zklend.supply(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        token_name=supply_token_name,
                        cairo_version=bot_account.cairo_version,
                        amount=amount,
                        percentage=percentage,
                        proxy=bot_account.proxy
                    )
                if function_name == enums.FunctionNames.BORROW:
                    min_borrow_percentage = task.module_kwargs.get('min_borrow_percentage', 10)
                    max_borrow_percentage = task.module_kwargs.get('max_borrow_percentage', 100)
                    borrow_percentage = round(random.uniform(min_borrow_percentage, max_borrow_percentage), 2)
                    function_result = await modules.zklend.borrow(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        token_name=enums.TokenNames.USDC,
                        cairo_version=bot_account.cairo_version,
                        percentage=borrow_percentage,
                        proxy=bot_account.proxy
                    )
                elif function_name == enums.FunctionNames.REPAY:
                    function_result = await modules.zklend.repay(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        token_name=enums.TokenNames.USDC,
                        cairo_version=bot_account.cairo_version,
                        percentage=100,
                        proxy=bot_account.proxy
                    )
                elif function_name == enums.FunctionNames.WITHDRAW:
                    withdraw_percentage = task.module_kwargs.get('withdraw_percentage', 100)
                    function_result = await modules.zklend.withdraw(
                        private_key=bot_account.private_key,
                        address=bot_account.address,
                        network_name=network_name,
                        token_name=enums.TokenNames.ETH,
                        cairo_version=bot_account.cairo_version,
                        percentage=withdraw_percentage,
                        proxy=bot_account.proxy
                    )
        except BaseException as e:
            function_result = enums.TransactionStatus.FAILED
            traceback.print_exc()

        if function_result == enums.TransactionStatus.INSUFFICIENT_BALANCE:
            logging.critical(f'[Main] Top up your balance in {network_name} network')
            input('[Main] Press enter to continue after top up')
        elif function_result != enums.TransactionStatus.FAILED:
            break

        utils.random_sleep()

    return function_result


async def run_module(
    bot_account: accounts_loader.BotAccount,
    task: accounts_loader.Task
):
    if task.module_name == enums.ModuleNames.Sleep:
        if 'sleep_time' in task.module_kwargs:
            sleep_time = task.module_kwargs['sleep_time']
        else:
            min_sleep_time = task.module_kwargs.get('min_sleep_time', 1)
            max_sleep_time = task.module_kwargs.get('max_sleep_time', 10)
            sleep_time = random.uniform(min_sleep_time, max_sleep_time)
        utils.sleep(sleep_time)
        return enums.TransactionStatus.SUCCESS
    else:
        if USE_TESTNET:
            networks = constants.TESTNET_MODULE_NETWORKS[task.module_name]
        else:
            networks = constants.MAINNET_MODULE_NETWORKS[task.module_name]
        if isinstance(networks, dict):
            network_name = networks[task.function_name]
        else:
            network_name = networks

    if network_name == enums.NetworkNames.DefinedInParams:
        network_name = task.module_kwargs.get('from_network', enums.NetworkNames.ETH)

    if network_name is None:
        logging.warning(f'[Main] Network name for module {task.module_name} is None')
        return enums.TransactionStatus.SUCCESS

    while True:
        try:
            current_gas_price = await utils.get_gas_price(
                network_name=network_name,
                proxy=bot_account.proxy
            )
        except BaseException as e:
            logging.error(f'[Main] Failed to get gas price for {network_name} network: {type(e)} - {e}')
            utils.sleep(10)
            continue

        if network_name in {
            enums.NetworkNames.ETH,
            enums.NetworkNames.Goerli
        }:
            if current_gas_price < bot_account.max_eth_gwei:
                break
            else:
                logging.info(f'[Main] Current gas price {round(current_gas_price, 3)} Gwei is higher than max {bot_account.max_eth_gwei} Gwei')
        elif network_name in {
            enums.NetworkNames.Starknet,
            enums.NetworkNames.StarknetTestnet
        }:
            if current_gas_price < bot_account.max_starknet_gwei:
                break
            else:
                logging.info(f'[Main] Current gas price {round(current_gas_price, 3)} Gwei is higher than max {bot_account.max_starknet_gwei} Gwei')
        else:
            break

        utils.sleep(10)

    function_dict = {
        'bot_account': bot_account,
        'network_name': network_name,
        'task': task,
        'function_name': task.function_name
    }
    logging.info(f'[Main] Running {task.module_name} module in {network_name} network')
    if task.module_name in constants.SWAP_PAIRS and task.function_name in {enums.FunctionNames.SWAP, None}:
        swaps = task.module_kwargs.get('swaps', 5)
        min_amount_usd = task.module_kwargs.get('min_amount_usd', None)
        max_amount_usd = task.module_kwargs.get('max_amount_usd', None)
        min_amount = task.module_kwargs.get('min_amount', None)
        max_amount = task.module_kwargs.get('max_amount', None)
        min_percentage = task.module_kwargs.get('min_percentage', 1)
        max_percentage = task.module_kwargs.get('max_percentage', 90)
        start_token = task.module_kwargs.get('start_token', enums.TokenNames.ETH)
        end_token = task.module_kwargs.get('end_token', enums.TokenNames.ETH)

        allowed_tokens = set()
        if 'swap_tokens' in task.module_kwargs:
            allowed_tokens = set(task.module_kwargs['swap_tokens'])
        else:
            for pair in constants.SWAP_PAIRS[task.module_name][network_name]:
                allowed_tokens |= set(pair)
        exclude_tokens = set(
            task.module_kwargs.get('exclude_tokens', set())
        )
        allowed_tokens -= exclude_tokens

        swap_tokens = defaultdict(set)

        for pair in constants.SWAP_PAIRS[task.module_name][network_name]:
            if pair[0] in allowed_tokens and pair[1] in allowed_tokens:
                swap_tokens[pair[0]].add(pair[1])
                swap_tokens[pair[1]].add(pair[0])

        if len(swap_tokens) < 2 and swaps != 1:
            logging.error(f'[Main] At least 2 tokens required for {task.module_name}')
            return enums.TransactionStatus.FAILED

        if start_token == enums.TokenNames.Random:
            start_token = random.choice(list(swap_tokens.keys()))
        elif start_token == enums.TokenNames.Last:
            start_token = getattr(main, 'last_swap_token', enums.TokenNames.ETH)

        if end_token == start_token and end_token != enums.TokenNames.Random and swaps == 1:
            end_token = enums.TokenNames.Random

        if end_token == enums.TokenNames.Random:
            if swaps == 1:
                end_token = random.choice(list(set(swap_tokens.keys()) - {start_token}))
            else:
                end_token = random.choice(list(swap_tokens.keys()))
        elif end_token == enums.TokenNames.Last:
            end_token = getattr(main, 'last_swap_token', enums.TokenNames.ETH)

        swap_result = enums.TransactionStatus.SUCCESS

        if start_token == enums.TokenNames.All:
            tokens_with_balance = await utils.get_tokens_with_balance(
                private_key=bot_account.private_key,
                address=bot_account.address,
                network_name=network_name,
                tokens=set(swap_tokens.keys()) - {end_token},
                min_amount=min_amount,
                min_amount_usd=min_amount_usd,
                proxy=bot_account.proxy
            )

            if not tokens_with_balance:
                logging.error(f'[Main] No tokens with balance for {task.module_name}')
                return enums.TransactionStatus.SUCCESS

            swaps = min(swaps, len(tokens_with_balance))

            tokens_with_balance = random.sample(tokens_with_balance, swaps)

            for from_token_name in tokens_with_balance:
                new_task = copy.deepcopy(task)

                new_task.module_kwargs.pop('min_amount_usd', None)
                new_task.module_kwargs.pop('max_amount_usd', None)
                new_task.module_kwargs.pop('min_amount', None)
                new_task.module_kwargs.pop('max_amount', None)

                new_task.module_kwargs['start_token'] = from_token_name
                new_task.module_kwargs['swaps'] = 1
                new_task.module_kwargs['min_percentage'] = min_percentage
                new_task.module_kwargs['max_percentage'] = max_percentage

                await run_module(
                    bot_account=bot_account,
                    task=new_task
                )
        else:
            from_token_name = start_token

            if swaps == 1:
                to_token_name = end_token
            else:
                to_token_name = random.choice(list(swap_tokens[from_token_name]))

            swap = 0
            successful_swaps = 0
            approves = 0
            error_tokens = set()

            while swap < swaps:
                function_dict['task'].module_kwargs['from_token_name'] = from_token_name
                function_dict['task'].module_kwargs['to_token_name'] = to_token_name
                if from_token_name == enums.TokenNames.ETH:
                    if successful_swaps > 0:
                        function_dict['task'].module_kwargs['min_percentage'] = min(min_percentage, 95)
                        function_dict['task'].module_kwargs['max_percentage'] = min(max_percentage, 95)
                elif from_token_name == start_token:
                    function_dict['task'].module_kwargs['min_percentage'] = min_percentage
                    function_dict['task'].module_kwargs['max_percentage'] = max_percentage
                else:
                    function_dict['task'].module_kwargs['min_percentage'] = 100
                    function_dict['task'].module_kwargs['max_percentage'] = 100

                if successful_swaps == 0 or from_token_name == start_token:
                    if min_amount_usd is not None and max_amount_usd is not None:
                        function_dict['task'].module_kwargs['min_amount_usd'] = min_amount_usd
                        function_dict['task'].module_kwargs['max_amount_usd'] = max_amount_usd
                    if min_amount is not None and max_amount is not None:
                        function_dict['task'].module_kwargs['min_amount'] = min_amount
                        function_dict['task'].module_kwargs['max_amount'] = max_amount
                else:
                    function_dict['task'].module_kwargs.pop('min_amount_usd', None)
                    function_dict['task'].module_kwargs.pop('max_amount_usd', None)
                    function_dict['task'].module_kwargs.pop('min_amount', None)
                    function_dict['task'].module_kwargs.pop('max_amount', None)

                if from_token_name == to_token_name:
                    swap_result = enums.TransactionStatus.SUCCESS
                else:
                    swap_result = await run_function(**function_dict)

                if swap_result == enums.TransactionStatus.SUCCESS:
                    main.last_swap_token = to_token_name
                    successful_swaps += 1
                    error_tokens = set()
                    swap += 1
                    from_token_name = to_token_name
                    if swap == swaps - 1:
                        if end_token not in swap_tokens[from_token_name]:
                            possible_tokens = swap_tokens[from_token_name] - {end_token}
                            possible_tokens = {token for token in possible_tokens if end_token in swap_tokens[token]}
                            if possible_tokens:
                                to_token_name = random.choice(
                                    list(swap_tokens[from_token_name] - {end_token})
                                )
                            else:
                                to_token_name = random.choice(
                                    list(swap_tokens[from_token_name])
                                )
                            swaps += 1
                        else:
                            to_token_name = end_token
                    elif swap == swaps - 2:
                        possible_tokens = swap_tokens[from_token_name] - {end_token}
                        if possible_tokens:
                            to_token_name = random.choice(
                                list(possible_tokens)
                            )
                        else:
                            to_token_name = end_token
                    elif swap != swaps:
                        to_token_name = random.choice(
                            list(swap_tokens[from_token_name])
                        )
                else:
                    error_tokens.add(to_token_name)
                    if len(error_tokens) == len(swap_tokens[from_token_name]):
                        logging.error(
                            f'[Main] Failed to swap {from_token_name} in {task.module_name} for {len(swap_tokens[from_token_name])} times in a row'
                        )
                        return swap_result
                    elif swap == swaps - 1 and swap != 0:
                        logging.error(
                            f'[Main] Failed to swap {from_token_name} to {to_token_name}'
                        )
                        return swap_result
                    else:
                        to_token_name = random.choice(
                            list(swap_tokens[from_token_name] - error_tokens)
                        )

                if swap != swaps:
                    utils.random_sleep()
        return swap_result
    elif task.module_name in constants.POOLS and task.function_name == enums.FunctionNames.POOL:
        include_tokens = task.module_kwargs.get('pool_tokens', set())
        exclude_tokens = task.module_kwargs.get('exclude_tokens', set())
        pools = constants.POOLS[task.module_name][network_name]
        if include_tokens:
            pools = {pool for pool in pools if len(include_tokens.intersection(pool)) == 2}
        if exclude_tokens:
            pools = {pool for pool in pools if not set(pool).intersection(exclude_tokens)}
        if not pools:
            logging.error(f'[Main] No pools specified for {task.module_name}')
            return enums.TransactionStatus.FAILED
        pool = random.choice(list(pools))
        function_dict['task'].module_kwargs['first_token_name'] = pool[0]
        function_dict['task'].module_kwargs['second_token_name'] = pool[1]
        function_dict['function_name'] = enums.FunctionNames.ADD_LIQUIDITY
        add_liquidity_result = await run_function(**function_dict)
        if add_liquidity_result != enums.TransactionStatus.SUCCESS:
            logging.error(f'[Main] Error occured while adding liquidity to {task.module_name}. Please, continue manually')
            return add_liquidity_result

        min_withdraw_percentage = task.module_kwargs.get('min_withdraw_percentage', 100)
        max_withdraw_percentage = task.module_kwargs.get('max_withdraw_percentage', 100)
        withdraw_percentage = round(random.uniform(min_withdraw_percentage, max_withdraw_percentage), 2)

        if withdraw_percentage > 0:
            min_withdraw_sleep_time = task.module_kwargs.get('min_withdraw_sleep_time', 1)
            max_withdraw_sleep_time = task.module_kwargs.get('max_withdraw_sleep_time', 10)

            withdraw_sleep_time = random.uniform(min_withdraw_sleep_time, max_withdraw_sleep_time)

            if withdraw_sleep_time > 0:
                utils.sleep(withdraw_sleep_time)

            function_dict['function_name'] = enums.FunctionNames.REMOVE_LIQUIDITY
            function_dict['task'].module_kwargs['withdraw_percentage'] = withdraw_percentage
            remove_liquidity_result = await run_function(**function_dict)
            if remove_liquidity_result != enums.TransactionStatus.SUCCESS:
                logging.error(f'[Main] Error occured while removing liquidity from {task.module_name}. Please, continue manually')
            return remove_liquidity_result

        return add_liquidity_result
    elif task.module_name == enums.ModuleNames.zkLend:
        function_dict['function_name'] = enums.FunctionNames.SUPPLY
        supply_result = await run_function(**function_dict)
        if supply_result != enums.TransactionStatus.SUCCESS:
            logging.error(f'[Main] Error occured while supplying to zkLend. Please, continue manually')
            return supply_result

        repay_result = supply_result

        if task.module_kwargs.get('min_borrow_percentage', 10) > 0 and task.module_kwargs.get('max_borrow_percentage', 100) > 0:
            function_dict['function_name'] = enums.FunctionNames.BORROW
            utils.random_sleep()
            borrow_result = await run_function(**function_dict)
            if borrow_result != enums.TransactionStatus.SUCCESS:
                logging.error(f'[Main] Error occured while borrowing from zkLend. Please, continue manually')
                return borrow_result

            function_dict['function_name'] = enums.FunctionNames.REPAY
            utils.random_sleep()
            repay_result = await run_function(**function_dict)
            if repay_result != enums.TransactionStatus.SUCCESS:
                logging.error(f'[Main] Error occured while repaying to zkLend. Please, continue manually')
                return repay_result

        min_withdraw_percentage = task.module_kwargs.get('min_withdraw_percentage', 100)
        max_withdraw_percentage = task.module_kwargs.get('max_withdraw_percentage', 100)
        withdraw_percentage = round(random.uniform(min_withdraw_percentage, max_withdraw_percentage), 2)

        if withdraw_percentage > 0:
            function_dict['function_name'] = enums.FunctionNames.WITHDRAW
            function_dict['task'].module_kwargs['withdraw_percentage'] = withdraw_percentage
            utils.random_sleep()
            withdraw_result = await run_function(**function_dict)
            if withdraw_result != enums.TransactionStatus.SUCCESS:
                logging.error(f'[Main] Error occured while withdrawing from zkLend. Please, continue manually')
                return withdraw_result

        return repay_result
    elif task.module_name in {
        enums.ModuleNames.Dmail,
        enums.ModuleNames.StarknetID,
        enums.ModuleNames.StarkVerse
    }:
        function_result = enums.TransactionStatus.SUCCESS

        min_amount = task.module_kwargs.get('min_amount', 1)
        max_amount = task.module_kwargs.get('max_amount', 1)
        amount = random.randint(min_amount, max_amount)

        for i in range(amount):
            function_result = await run_function(**function_dict)
            if function_result != enums.TransactionStatus.SUCCESS:
                return function_result
            if i != amount - 1:
                utils.random_sleep()

        return function_result
    else:
        return await run_function(**function_dict)


async def run_modules(bot_account: accounts_loader.BotAccount):
    for index, task in enumerate(bot_account.tasks):
        module_result = await run_module(bot_account=bot_account, task=task)
        if module_result in constants.CRITICAL_RESULTS:
            input(f'[Main] Critical result {module_result} received. Press enter to continue if account is ready to continue')

        logging.info(
            f'[Main] {index + 1}/{len(bot_account.tasks)} task ({task.module_name}{f" - {task.function_name}" if task.function_name else ""}) completed'
        )

        if module_result == enums.TransactionStatus.SUCCESS:
            method = file_logger.info
        elif module_result == enums.TransactionStatus.INSUFFICIENT_BALANCE:
            method = file_logger.critical
        elif module_result in {
            enums.TransactionStatus.FAILED,
            enums.TransactionStatus.ADDRESS_NOT_ALLOWLISTED,
            enums.TransactionStatus.INCORRECT_NETWORK
        }:
            method = file_logger.error
        else:
            method = file_logger.warning

        method(
            f'{index + 1}/{len(bot_account.tasks)} task ({task.module_name}' +
            f'{f" - {task.function_name}" if task.function_name else ""}) ' +
            f'completed with result {module_result}'
        )

        utils.random_sleep()


async def run_accounts(bot_accounts: list[accounts_loader.BotAccount]):
    if not bot_accounts:
        return

    accounts_hashes = [bot_account.hash for bot_account in bot_accounts]

    if Path('last_state.json').exists():
        with open('last_state.json', 'r') as file:
            last_state = json.load(file)

        order = last_state.get('order', [])

        if sorted(order) == sorted(accounts_hashes):
            last_bot_index = order.index(last_state['account_hash'])
            last_bot_account = next(
                filter(
                    lambda bot_account: bot_account.hash == last_state['account_hash'],
                    bot_accounts
                )
            )

            continue_result = input(f'[Main] Continue account with private_key {last_bot_account.short_private_key}? [y/n]: ')
            if continue_result.lower() == 'y':
                print('[Main] Select from which task to continue:')
                for task_index, task in enumerate(last_bot_account.tasks, 1):
                    print(f'{task_index}. {task.module_name}{f" - {task.function_name}" if task.function_name else ""}')
                if last_bot_account.tasks:
                    while True:
                        task_num = int(input('[Main] Task number: '))
                        if task_num > len(last_bot_account.tasks):
                            print(f'[Main] Task number must be less than {len(last_bot_account.tasks)}')
                        elif task_num < 1:
                            print('[Main] Task number must be greater than 1')
                        else:
                            break
                    last_bot_account.tasks = last_bot_account.tasks[task_num - 1:]
                bot_accounts = [bot_accounts[accounts_hashes.index(account_hash)] for account_hash in order]
                accounts_hashes = [bot_account.hash for bot_account in bot_accounts]
                bot_accounts = bot_accounts[last_bot_index + 1:]
                bot_accounts.insert(0, last_bot_account)
                logging.info(f'[Main] Continuing account with private_key {last_bot_account.short_private_key} with {len(last_bot_account.tasks)} tasks')

    with open('last_state.json', 'w') as file:
        json.dump(
            {
                'order': accounts_hashes,
                'account_hash': bot_accounts[0].hash
            },
            file,
            indent=4
        )

    logging.info(f'Accounts order: {" -> ".join(bot_account.short_private_key for bot_account in bot_accounts)}')

    logfile_path = Path(file_logger.handlers[0].baseFilename)
    if logfile_path.exists() and logfile_path.stat().st_size > 0:
        with open(logfile_path, 'a') as file:
            file.write('\n\n\n')

    file_logger.info(f'New session with {len(bot_accounts)} accounts started\n')

    for bot_account in bot_accounts:
        start_message = f'[Main] Starting account with private_key {bot_account.short_private_key} with {len(bot_account.tasks)} tasks'
        logging.info(start_message)
        file_logger.info(start_message)
        utils.random_sleep.min_sleep_time = bot_account.min_sleep_time
        utils.random_sleep.max_sleep_time = bot_account.max_sleep_time

        with open('last_state.json') as file:
            last_state = json.load(file)

        last_state['account_hash'] = bot_account.hash

        with open('last_state.json', 'w') as file:
            json.dump(
                last_state,
                file,
                indent=4
            )

        if bot_account.mobile_proxy_changelink:
            response = requests.get(bot_account.mobile_proxy_changelink)
            if response.status_code == 200:
                logging.info(f'[Main] Changed mobile proxy for account with private_key {bot_account.short_private_key}: {response.text}')
                utils.sleep(5)
            else:
                logging.warning(f'[Main] Failed to change mobile proxy for account with private_key {bot_account.short_private_key}')

        if bot_account.proxy:
            proxy_error = False

            while True:
                try:
                    proxy_test_result = utils.test_proxy(bot_account.proxy)
                    if isinstance(proxy_test_result, str):
                        logging.info(f'[Main] Outgoing IP for account with private_key {bot_account.short_private_key} - {proxy_test_result}')
                        break
                    elif proxy_test_result:
                        logging.warning(f'[Main] Failed to get outgoing IP for account with private_key {bot_account.short_private_key}')
                        break
                    else:
                        logging.error(f'[Main] Proxy specified for account with private_key {bot_account.short_private_key} is not working. Retrying...')
                        logging.info(f'[Main] To stop retrying, press Ctrl+C')
                        utils.time.sleep(15)
                except KeyboardInterrupt:
                    proxy_error = True
                    break

            if proxy_error:
                proxy_result = input(
                    '[Main] What to do? (possible options: [s]kip, [e]xit, [d]elete (deletes proxy)): '
                )
                if proxy_result.lower() in {'s', 'skip'}:
                    logging.warning(f'[Main] Skipping account with private_key {bot_account.short_private_key}')
                    file_logger.warning(f'Skipping account with private_key {bot_account.short_private_key}\n')
                    continue
                elif proxy_result.lower() in {'e', 'exit'}:
                    logging.error(f'[Main] Exiting session due to incorrect proxy')
                    file_logger.info(f'Exiting session due to incorrect proxy\n')
                    break
                else:
                    logging.info(f'[Main] Deleting proxy for account with private_key {bot_account.short_private_key}')
                    bot_account.proxy = None

        if bot_account.wallet_name == enums.WalletNames.ArgentXOld:
            try:
                supports_cairo_1 = await utils.supports_cairo_1(
                    private_key=bot_account.private_key,
                    address=bot_account.address,
                    network_name=enums.NetworkNames.StarknetTestnet if USE_TESTNET else enums.NetworkNames.Starknet,
                    wallet_name=bot_account.wallet_name,
                    proxy=bot_account.proxy
                )
            except BaseException as e:
                ...
            else:
                if supports_cairo_1:
                    bot_account.cairo_version = 1

        await run_modules(bot_account=bot_account)
        logging.info(f'[Main] Finished account with private_key {bot_account.short_private_key}')
        file_logger.info(f'Finished account with private_key {bot_account.short_private_key}\n')

    file_logger.info(f'Session with {len(bot_accounts)} accounts finished')


async def main():
    print(r' $$$$$$\    $$\                         $$\                            $$\           $$$$$$$\             $$\     ')
    print(r'$$  __$$\   $$ |                        $$ |                           $$ |          $$  __$$\            $$ |    ')
    print(r'$$ /  \__|$$$$$$\    $$$$$$\   $$$$$$\  $$ |  $$\ $$$$$$$\   $$$$$$\ $$$$$$\         $$ |  $$ | $$$$$$\ $$$$$$\   ')
    print(r'\$$$$$$\  \_$$  _|   \____$$\ $$  __$$\ $$ | $$  |$$  __$$\ $$  __$$\\_$$  _|        $$$$$$$\ |$$  __$$\\_$$  _|  ')
    print(r' \____$$\   $$ |     $$$$$$$ |$$ |  \__|$$$$$$  / $$ |  $$ |$$$$$$$$ | $$ |          $$  __$$\ $$ /  $$ | $$ |    ')
    print(r'$$\   $$ |  $$ |$$\ $$  __$$ |$$ |      $$  _$$<  $$ |  $$ |$$   ____| $$ |$$\       $$ |  $$ |$$ |  $$ | $$ |$$\ ')
    print(r'\$$$$$$  |  \$$$$  |\$$$$$$$ |$$ |      $$ | \$$\ $$ |  $$ |\$$$$$$$\  \$$$$  |      $$$$$$$  |\$$$$$$  | \$$$$  |')
    print(r' \______/    \____/  \_______|\__|      \__|  \__|\__|  \__| \_______|  \____/       \_______/  \______/   \____/ ')
    bot_accounts = accounts_loader.read_accounts()
    if isinstance(bot_accounts, list):
        await run_accounts(bot_accounts=bot_accounts)


if __name__ == '__main__':
    asyncio.run(main())
