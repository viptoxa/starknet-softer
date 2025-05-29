import json
import secrets
from pathlib import Path

from starknet_py.net.client_models import TransactionExecutionStatus

import constants
import enums
import utils
from logger import logging


class ContractTypes(enums.AutoEnum):
    NFT = enums.auto()


CONTRACT_ADRESSES = {
    ContractTypes.NFT: {
        enums.NetworkNames.Starknet: '0x05dbdedc203e92749e2e746e2d40a768d966bd243df04a6b712e222bc040a9af',
        enums.NetworkNames.StarknetTestnet: '0x0783a9097b26eae0586373b2ce0ed3529ddc44069d1e0fbc4f66d42b69d6850d'
    }
}


async def mint(
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

    logging.info(f'[Starknet ID] Minting NFT')

    with open(Path(__file__).parent / 'abi' / 'ERC721.json') as file:
        nft_abi = json.load(file)

    nft_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.NFT][network_name],
        abi=nft_abi,
        provider=account
    )

    resp = await account.execute(
        calls=[
            nft_contract.functions['mint'].prepare(
                starknet_id=int(secrets.token_hex(5), 16)
            )
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[Starknet ID] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='Starknet ID'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[Starknet ID] Successfully minted NFT')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[Starknet ID] Failed to mint NFT')
        return enums.TransactionStatus.FAILED
