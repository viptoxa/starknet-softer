import json
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
        enums.NetworkNames.Starknet: '0x060582df2cd4ad2c988b11fdede5c43f56a432e895df255ccd1af129160044b8',
        enums.NetworkNames.StarknetTestnet: '0x075cca7baf8b5985c16a44092c492c28f76e2c617324dc0ab7d1d499c5d47161'
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

    logging.info(f'[StarkVerse] Minting NFT')

    with open(Path(__file__).parent / 'abi' / 'ERC721.json') as file:
        nft_abi = json.load(file)

    nft_contract = utils.get_starknet_contract(
        address=CONTRACT_ADRESSES[ContractTypes.NFT][network_name],
        abi=nft_abi,
        provider=account
    )

    resp = await account.execute(
        calls=[
            nft_contract.functions['publicMint'].prepare(
                to=account.address
            )
        ],
        cairo_version=cairo_version,
        auto_estimate=True
    )

    logging.info(f'[StarkVerse] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

    receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='StarkVerse'
    )

    if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
        logging.info(f'[StarkVerse] Successfully minted NFT')
        return enums.TransactionStatus.SUCCESS
    else:
        logging.error(f'[StarkVerse] Failed to mint NFT')
        return enums.TransactionStatus.FAILED
