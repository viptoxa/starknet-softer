import dataclasses
import json
import random
import re
import warnings
from copy import copy
from pathlib import Path

import pandas as pd
from eth_keys import keys
from hexbytes.main import HexBytes
from web3 import Web3

import constants
import create_accounts
import enums
from logger import logging, TelegramHandler


def shorten_private_key(private_key: str) -> str:
    if len(private_key) <= 16:
        return private_key
    return f'{private_key[:8]}...{private_key[-8:]}'


@dataclasses.dataclass
class Task:
    module_name: enums.ModuleNames
    function_name: enums.FunctionNames | None
    module_kwargs: dict

    @property
    def hash_string(self):
        return f'{self.module_name}:{self.function_name}:{self.module_kwargs}'


@dataclasses.dataclass
class TasksBlock:
    tasks: list[Task]
    mandatory: bool = False


@dataclasses.dataclass
class BotAccount:
    private_key: str
    address: str
    wallet_name: enums.WalletNames
    cairo_version: int
    tasks: list[Task]
    proxy: str
    mobile_proxy_changelink: str
    starknet_deposit_address: str
    evm_deposit_address: str
    evm_private_key: str
    evm_address: str
    okx_api_key: str
    okx_secret_key: str
    okx_passphrase: str
    min_sleep_time: float = 1
    max_sleep_time: float = 10
    max_retries: int = 0
    max_eth_gwei: float = float('inf')
    max_starknet_gwei: float = float('inf')

    @property
    def hash(self):
        return Web3.keccak(text=self.private_key).hex()

    @property
    def short_private_key(self):
        return shorten_private_key(self.private_key)


def extend_block(tasks_block: TasksBlock) -> list:
    tasks = []
    for task in tasks_block.tasks:
        if isinstance(task, TasksBlock):
            tasks.extend(extend_block(task))
        else:
            tasks.append(task)
    return tasks


def handle_random_tasks(tasks: list[Task]) -> list[Task]:
    new_tasks = []
    stack = []
    params_stack = []

    index = 0

    for index, task in enumerate(tasks):
        if task.module_name == enums.ModuleNames.Random:
            stack.append([])
            params_stack.append(task.module_kwargs)
        elif task.module_name == enums.ModuleNames.EndRandom:
            if not stack:
                logging.error(f'[Account Loader] An EndRandom module found that is not preceded by a Random module on line {index + 1}')
                return False

            random_list = stack.pop()
            params = params_stack.pop()

            min_amount = params.get('min_amount', 0)
            max_amount = params.get('max_amount', len(random_list))

            amount = random.randint(min_amount, max_amount)

            repeat = params.get('repeat', False)

            if not repeat:
                max_amount = min(max_amount, len(random_list))
                min_amount = min(min_amount, max_amount)

            random_tasks = []

            if repeat:
                random_tasks = random.choices(random_list, k=amount)

                mandatory_tasks = [task for task in random_list if (isinstance(task, Task) and task.module_kwargs.get('mandatory', False)) or (isinstance(task, TasksBlock) and task.mandatory)]
                not_mandatory_tasks = [task for task in random_list if not (isinstance(task, Task) and task.module_kwargs.get('mandatory', False)) or (isinstance(task, TasksBlock) and task.mandatory)]

                not_added_tasks = [task for task in mandatory_tasks if task not in random_tasks]
                added_not_manadatory_tasks = [task for task in random_tasks if task in not_mandatory_tasks]

                if not_added_tasks:
                    for mandatory_task, not_mandatory_task in zip(not_added_tasks, added_not_manadatory_tasks):
                        random_tasks.remove(not_mandatory_task)

                    random_tasks.extend(not_added_tasks)
            else:
                for sub_task in copy(random_list):
                    if isinstance(sub_task, TasksBlock):
                        mandatory = sub_task.mandatory
                    else:
                        mandatory = sub_task.module_kwargs.get('mandatory', False)
                    if mandatory:
                        random_tasks.append(sub_task)

                amount -= len(random_tasks)

                if amount > 0:
                    not_added_tasks = [task for task in random_list if task not in random_tasks]
                    if not_added_tasks:
                        random_tasks.extend(random.sample(not_added_tasks, min(amount, len(not_added_tasks))))

            random.shuffle(random_tasks)

            tasks_block = TasksBlock(random_tasks, params.get('mandatory', False))

            if stack:
                stack[-1].append(tasks_block)
            else:
                new_tasks.append(tasks_block)
        else:
            if stack:
                stack[-1].append(task)
            else:
                new_tasks.append(task)

    if stack:
        logging.error(f'[Account Loader] Found not closed random task on line {index + 1}')
        return False

    tasks = []

    for task in new_tasks:
        if isinstance(task, TasksBlock):
            tasks.extend(extend_block(task))
        else:
            tasks.append(task)

    return tasks


def parse_settings(settings_string) -> dict | list:
    known_settings = {
        'token_list_values': [
            'swap_tokens', 'pool_tokens', 'exclude_tokens'
        ],
        'token_values': [
            'start_token', 'end_token'
        ],
        'integer_values': ['swaps'],
        'boolean_values': ['wait_for_receive', 'mandatory', 'repeat'],
        'string_values': ['destination_address'],
        'network_values': ['to_network', 'from_network'],
        'float_values': [
            'min_percentage', 'max_percentage',
            'min_supply_percentage', 'max_supply_percentage',
            'min_borrow_percentage', 'max_borrow_percentage',
            'min_withdraw_percentage', 'max_withdraw_percentage',
            'slippage', 'max_price', 'min_amount', 'max_amount', 'sleep_time',
            'min_sleep_time', 'max_sleep_time', 'min_amount_usd',
            'max_amount_usd', 'min_withdraw_sleep_time',
            'max_withdraw_sleep_time', 'min_deposit_amount'
        ]
    }

    if not settings_string:
        return {}

    patterns = {
        'token_list_values': fr'(?:\w+(?: \w+)*)?',
        'token_values': r'[A-Za-z]+',
        'integer_values': r'\d+',
        'boolean_values': r'(?:yes|no)',
        'string_values': r'[\w\d]+',
        'network_values': r'[A-Za-z]+',
        'float_values': r'\d+(?:\.\d+)?'
    }

    refined_patterns = []
    for type_name, names in known_settings.items():
        for name in names:
            refined_patterns.append(fr'{name}:\s+{patterns[type_name]}')

    segment_combined_pattern = '|'.join(refined_patterns)
    full_pattern = fr'^(?:{segment_combined_pattern})(?:,\s+(?:{segment_combined_pattern}))*$'
    regex_error = False

    if not re.match(full_pattern, settings_string, re.IGNORECASE):
        regex_error = True

    settings_list = settings_string.split(',')
    settings_dict = {}
    unknown_settings = []

    for setting in settings_list:
        try:
            name, value = setting.split(':')
        except ValueError:
            logging.error(f'[Account Loader] Invalid settings string: {settings_string}')
            return False
        name = name.strip().lower()
        value = value.strip()

        if any(name in values for values in known_settings.values()):
            try:
                if name in known_settings['token_list_values']:
                    values = value.split(' ')
                    converted_values = {enums.TokenNames.from_string(value) for value in values}
                    settings_dict[name] = converted_values
                elif name in known_settings['token_values']:
                    settings_dict[name] = enums.TokenNames.from_string(value)
                elif name in known_settings['boolean_values']:
                    settings_dict[name] = True if value.lower() == 'yes' else False
                elif name in known_settings['integer_values']:
                    settings_dict[name] = int(value)
                elif name in known_settings['string_values']:
                    settings_dict[name] = value
                elif name in known_settings['network_values']:
                    network_name = enums.NetworkNames.from_string(value)
                    if network_name is None:
                        logging.error(f'[Account Loader] Unknown network name {value} in {name} setting')
                        return False
                    settings_dict[name] = network_name
                else:
                    settings_dict[name] = float(value.replace(',', '.'))
            except ValueError as ve:
                logging.error(f'[Account Loader] Invalid value {value} for {name} setting')
                logging.error(f'[Account Loader] {str(ve).capitalize()}')
                return False
        else:
            unknown_settings.append(name)

    if unknown_settings:
        logging.error(f'[Account Loader] Unknown settings: {", ".join(unknown_settings)}')
        return False
    elif regex_error:
        logging.error(f'[Account Loader] Invalid settings string: {settings_string}')
        return False

    return settings_dict


def read_accounts() -> list[BotAccount]:
    warnings.filterwarnings(
        'ignore',
        category=UserWarning,
        module='openpyxl'
    )

    telegram_path = Path(__file__).parent / 'telegram.json'
    if telegram_path.exists():
        with open(telegram_path) as f:
            bot_info = json.load(f)
            required_bot_fields = {'token', 'chat_id', 'log_level'}
            missing_bot_fields = required_bot_fields - set(bot_info.keys())
            if missing_bot_fields:
                logging.error(f'[Account Loader] Missing fields in telegram.json: {", ".join(missing_bot_fields)}')
                return False

            telegram_token = bot_info['token']
            telegram_chat_id = bot_info['chat_id']
            telegram_log_level = bot_info['log_level']

            if telegram_token and telegram_chat_id:
                try:
                    tg_handler = TelegramHandler(telegram_token, telegram_chat_id)
                except Exception as e:
                    logging.error(f'[Account Loader] Failed to initialize Telegram logging handler: {e}')
                    return False
                tg_handler.setLevel(telegram_log_level or logging.INFO)
                tg_handler.setFormatter(logging.root.handlers[0].formatter)
                logging.addHandler(tg_handler)
            elif telegram_token:
                logging.error(f'[Account Loader] Missing chat_id in {telegram_path.name}')
                return False
            elif telegram_chat_id:
                logging.error(f'[Account Loader] Missing token in {telegram_path.name}')
                return False

    logging.info('[Account Loader] Loading accounts')

    accounts = []

    default_account_values = {}
    for field in dataclasses.fields(BotAccount):
        if field.default != dataclasses.MISSING:
            default_account_values[field.name] = field.default

    acounts_file_path = Path(__file__).parent / 'accounts.xlsx'

    if not acounts_file_path.exists():
        logging.error(f'[Account Loader] File "{acounts_file_path.name}" does not exist')
        return False

    accounts_file = pd.ExcelFile(acounts_file_path)
    sheets = [sheet.lower() for sheet in accounts_file.sheet_names]
    del accounts_file

    dtypes = {
        'private_key': str,
        'address': str,
        'min_sleep_time': 'float64',
        'max_sleep_time': 'float64',
        'max_retries': 'float64',
        'max_eth_gwei': 'float64',
        'max_starknet_gwei': 'float64',
        'proxy': str,
        'mobile_proxy_changelink': str,
        'metamask_private_key': str,
        'starknet_okx_deposit_address': str,
        'evm_okx_deposit_address': str,
        'okx_api_key': str,
        'okx_secret_key': str,
        'okx_passphrase': str
    }

    accounts_df = pd.read_excel(
        acounts_file_path,
        sheet_name='accounts',
        dtype=dtypes
    )
    accounts_df = accounts_df.apply(lambda x: x.str.strip() if x.dtype == object else x)
    unknown_account_columns = set(accounts_df.columns) - set(dtypes.keys())

    if unknown_account_columns:
        logging.error(f'[Account Loader] Unknown account columns in "accounts" sheet: {", ".join(unknown_account_columns)}')
        return False

    accounts_df.dropna(subset=['private_key', 'address'], inplace=True, how='all')
    for column in accounts_df.columns:
        if column in default_account_values:
            accounts_df[column] = accounts_df[column].fillna(
                default_account_values[column]
            )
        else:
            accounts_df[column] = accounts_df[column].fillna(-31294912).replace(-31294912, None)

    for row in accounts_df.itertuples():
        cairo_version = 0
        wallet_name = enums.WalletNames.Braavos

        if not row.private_key:
            logging.error(f'[Account Loader] Missing private key on row {row.Index + 1} of "accounts" sheet')
            return False
        if row.private_key.lower() not in {'random', 'endrandom'}:
            if not row.address:
                logging.error(f'[Account Loader] Missing address on row {row.Index + 1} of "accounts" sheet')
                return False
            elif not re.match(r'^(0x)?[a-fA-F0-9]+$', row.private_key):
                short_private_key = shorten_private_key(row.private_key)
                logging.error(f'[Account Loader] Invalid private key "{short_private_key}" on row {row.Index + 1} of "accounts" sheet')
                return False
            elif not re.match(r'^(0x)?[a-fA-F0-9]+$', row.address):
                logging.error(f'[Account Loader] Invalid address "{row.address}" on row {row.Index + 1} of "accounts" sheet')
                return False

            for test_wallet_name in enums.WalletNames:
                _, address = create_accounts.wallet_from_private_key(
                    row.private_key,
                    test_wallet_name
                )

                if int(row.address, 16) == int(address, 16):
                    wallet_name = test_wallet_name
                    break
            else:
                logging.error(f'[Account Loader] Invalid address "{row.address}" for private key "{shorten_private_key(row.private_key)}" on row {row.Index + 1} of "accounts" sheet')
                return False

            if wallet_name == enums.WalletNames.ArgentX:
                cairo_version = 1

        tasks_sheet_name = f'tasks_{row.Index + 1}'

        for sheet_name in sheets:
            if sheet_name.strip() == tasks_sheet_name:
                tasks_sheet_name = sheet_name
                break
        else:
            tasks_sheet_name = 'tasks'

        tasks_df = pd.read_excel(
            acounts_file_path,
            sheet_name=tasks_sheet_name,
            dtype={
                'module_name': str,
                'function_name': str,
                'settings': str
            }
        )

        unknown_tasks_columns = set(tasks_df.columns) - {'module_name', 'function_name', 'settings'}
        if unknown_tasks_columns:
            logging.error(f'[Account Loader] Unknown columns in "{tasks_sheet_name}" sheet: {", ".join(unknown_tasks_columns)}')
            return False

        tasks_columns = list(tasks_df.columns)
        required_tasks_columns = ['module_name', 'function_name', 'settings']
        missing_columns = set(required_tasks_columns) - set(tasks_columns)
        if missing_columns:
            logging.error(f'[Account Loader] Missing columns in "{tasks_sheet_name}" sheet: {", ".join(missing_columns)}')
            return False
        elif set(required_tasks_columns) == set(tasks_columns) and tasks_columns != required_tasks_columns:
            logging.error(f'[Account Loader] Invalid order of columns in "{tasks_sheet_name}" sheet')
            return False
        elif list(tasks_df.columns) != required_tasks_columns:
            logging.error(f'[Account Loader] Invalid columns in "{tasks_sheet_name}" sheet')
            return False

        tasks_df.module_name = tasks_df.module_name.str.strip()
        tasks_df.function_name = tasks_df.function_name.str.strip()
        tasks_df.settings = tasks_df.settings.str.strip()

        tasks_df.dropna(subset=['module_name'], inplace=True)
        tasks_df.function_name = tasks_df.function_name.fillna(0).replace(0, None)
        tasks_df.settings = tasks_df.settings.fillna('')
        tasks = []
        for index, task_row in tasks_df.iterrows():
            settings_line = task_row.settings
            parse_result = parse_settings(settings_line)
            if parse_result is False:
                logging.error(f'[Account Loader] Failed to parse settings in "{tasks_sheet_name}" sheet, "{task_row.module_name}" module, "{settings_line}" line')
                return False
            try:
                module_name = enums.ModuleNames.from_string(task_row.module_name)
            except ValueError:
                logging.error(f'[Account Loader] Unknown module name "{task_row.module_name}" in "{tasks_sheet_name}" sheet')
                return False
            function_name = None
            if task_row.function_name is not None:
                try:
                    function_name = enums.FunctionNames.from_string(task_row.function_name)
                except ValueError:
                    logging.error(f'[Account Loader] Unknown function name "{task_row.function_name}" in "{tasks_sheet_name}" sheet, "{task_row.module_name}" module')
                    return False
                if function_name not in constants.MODULE_FUNCTIONS[module_name]:
                    logging.error(f'[Account Loader] Function "{function_name}" is not available in "{task_row.module_name}" module ("{tasks_sheet_name}" sheet)')
                    return False
            elif constants.MODULE_FUNCTIONS[module_name]:
                logging.error(f'[Account Loader] Function name must be specified for "{task_row.module_name}" module in "{tasks_sheet_name}" sheet')
                return False
            tasks.append(Task(
                module_name=module_name,
                function_name=function_name,
                module_kwargs=parse_result
            ))

        tasks = handle_random_tasks(tasks)

        if tasks is False:
            logging.error(f'[Account Loader] Failed to handle random tasks in "{tasks_sheet_name}" sheet')
            return False

        if row.proxy:
            if re.match(r'(socks5|http)://', row.proxy):
                proxy = {
                    'http': row.proxy,
                    'https': row.proxy
                }
            elif '/' not in row.proxy:
                proxy = {
                    'http': f'http://{row.proxy}',
                    'https': f'http://{row.proxy}'
                }
            else:
                logging.error(f'[Account Loader] Invalid proxy "{row.proxy}"')
                return False
        else:
            proxy = None

        if row.metamask_private_key:
            try:
                metamask_address = keys.PrivateKey(HexBytes(row.metamask_private_key)).public_key.to_checksum_address()
            except Exception as e:
                logging.error(f'[Account Loader] Failed to load metamask private key: {e}')
                return False
        else:
            metamask_address = None

        try:
            account = BotAccount(
                private_key=row.private_key,
                address=row.address,
                wallet_name=wallet_name,
                cairo_version=cairo_version,
                tasks=tasks,
                min_sleep_time=row.min_sleep_time,
                max_sleep_time=row.max_sleep_time,
                max_retries=int(row.max_retries),
                max_eth_gwei=row.max_eth_gwei,
                max_starknet_gwei=row.max_starknet_gwei,
                evm_private_key=row.metamask_private_key,
                evm_address=metamask_address,
                proxy=proxy,
                mobile_proxy_changelink=row.mobile_proxy_changelink,
                starknet_deposit_address=row.starknet_okx_deposit_address,
                evm_deposit_address=row.evm_okx_deposit_address,
                okx_api_key=row.okx_api_key,
                okx_secret_key=row.okx_secret_key,
                okx_passphrase=row.okx_passphrase,
            )
        except AttributeError as e:
            res = re.search("has no attribute '(?P<attribute>.+)'", str(e))
            if res:
                attribute = res.group('attribute')
                logging.error(f'[Account Loader] Missing {attribute} column in "accounts" sheet')
            else:
                logging.error(f'[Account Loader] Failed to load account: {e}')
            return
        okx_keys = [account.okx_api_key, account.okx_secret_key, account.okx_passphrase]
        if any(okx_keys) and not all(okx_keys):
            logging.error(f'[Account Loader] All or none of OKX keys must be specified for "{account.short_private_key}"')
            return
        accounts.append(account)


    random_indexes = []

    for index, account in enumerate(accounts):
        if account.private_key.lower() == 'random':
            if random_indexes and len(random_indexes[-1]) == 1:
                logging.error(f'[Account Loader] Found not closed random account on line {random_indexes[-1][0] + 2}')
                return False
            random_indexes.append([index])
        elif account.private_key.lower() == 'endrandom':
            if not random_indexes or len(random_indexes[-1]) == 2:
                logging.error(f'[Account Loader] An EndRandom account found that is not preceded by a Random account on line {index + 3}')
                return False
            random_indexes[-1].append(index)

    if random_indexes:
        if len(random_indexes[-1]) != 2:
            logging.error(f'[Account Loader] Found not closed random account on line {random_indexes[-1][0] + 1}')
            return False

        for start_index, end_index in reversed(random_indexes):
            difference = end_index - start_index - 1
            if difference:
                accounts[start_index:end_index + 1] = random.sample(accounts[start_index + 1:end_index], difference)
            else:
                accounts[start_index:end_index + 1] = []

    return accounts
