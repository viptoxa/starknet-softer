import json
import random
import string
from pathlib import Path

import constants
import enums
import utils
from logger import logging
from starknet_py.cairo.felt import encode_shortstring
from starknet_py.net.client_models import TransactionExecutionStatus


class ContractTypes(enums.AutoEnum):
    MAIL = enums.auto()


CONTRACT_ADRESSES = {
    ContractTypes.MAIL: {
        enums.NetworkNames.Starknet: '0x0454f0bd015e730e5adbb4f080b075fdbf55654ff41ee336203aa2e1ac4d4309'
    }
}


async def send_email(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    cairo_version: int,
    proxy: dict[str, str] = None
) -> enums.TransactionStatus:
    network = constants.NETWORKS[network_name]

    account = utils.get_account(
        network_name=network_name,
        private_key=private_key,
        address=address,
        proxy=proxy
    )

    logging.info(f'[Dmail] Sending an email')

    with open(Path(__file__).parent / 'abi' / 'Mail.json') as file:
        mail_abi = json.load(file)

    min_value = 452312848583266388373324160190187140051835877600158453279131187530910662656
    max_value = 3618502788666131213697322783095070105623107215331596699973092056135872020481

    theme = ''.join(map(str, [random.choice(string.hexdigits[:16]) for _ in range(31)]))

    random.seed(account.address)

    to = ''.join(map(str, [random.choice(string.hexdigits[:16]) for _ in range(31)]))

    to = encode_shortstring(to)
    theme = encode_shortstring(theme)

    mail_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.MAIL][network_name],
        abi=mail_abi,
        provider=account
    )

    resp = await account.execute(
        calls=[
            mail_contract.functions['transaction'].prepare(
                to=to,
                theme=theme
            )
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[Dmail] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='Dmail'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[Dmail] Successfully sent an email')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[Dmail] Failed to send an email')
        return enums.TransactionStatus.FAILED
