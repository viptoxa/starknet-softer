import json
from pathlib import Path
from typing import List

import constants
import create_accounts
import enums
import utils
from logger import logging
from starknet_py.cairo.felt import decode_shortstring
from starknet_py.hash.address import compute_address
from starknet_py.hash.transaction import compute_deploy_account_transaction_hash
from starknet_py.hash.utils import compute_hash_on_elements, message_signature
from starknet_py.net.account.account import Account
from starknet_py.net.account.account_deployment_result import AccountDeploymentResult
from starknet_py.net.client_models import TransactionFinalityStatus, TransactionExecutionStatus
from starknet_py.net.models import StarknetChainId, DeployAccount
from starknet_py.net.signer.stark_curve_signer import KeyPair, StarkCurveSigner

NETWORK_TO_CHAIN = {
    enums.NetworkNames.Starknet: StarknetChainId.MAINNET,
    enums.NetworkNames.StarknetTestnet: StarknetChainId.TESTNET
}

LAST_VERSIONS = {
    enums.WalletNames.ArgentX: '0.3.0',
    enums.WalletNames.ArgentXOld: '0.3.0',
    enums.WalletNames.Braavos: '000.000.011'
}


class BraavosSigner(StarkCurveSigner):
    def _sign_deploy_account_transaction(self, transaction: DeployAccount) -> List[int]:
        contract_address = compute_address(
            salt=transaction.contract_address_salt,
            class_hash=transaction.class_hash,
            constructor_calldata=transaction.constructor_calldata,
            deployer_address=0,
        )

        txn_hash = compute_deploy_account_transaction_hash(
            version=transaction.version,
            contract_address=contract_address,
            class_hash=transaction.class_hash,
            constructor_calldata=transaction.constructor_calldata,
            max_fee=transaction.max_fee,
            nonce=transaction.nonce,
            salt=transaction.contract_address_salt,
            chain_id=self.chain_id
        )

        r, s = message_signature(
            msg_hash=compute_hash_on_elements(
                [txn_hash, create_accounts.ACCOUNT_CLASS_HASHES[enums.WalletNames.Braavos], 0, 0, 0, 0, 0, 0, 0]
            ),
            priv_key=self.private_key
        )

        return [r, s, create_accounts.ACCOUNT_CLASS_HASHES[enums.WalletNames.Braavos], 0, 0, 0, 0, 0, 0, 0]


async def deploy(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    wallet_name: enums.WalletNames,
    proxy: dict[str, str] = None
):
    logging.info(f'[Deploy Account] Deploying account for {wallet_name} wallet')

    network = constants.NETWORKS[network_name]

    account = utils.get_account(
        network_name=network_name,
        private_key=private_key,
        address=address,
        proxy=proxy,
        signer_class=BraavosSigner if wallet_name == enums.WalletNames.Braavos else None
    )

    balance_in_wei = await account.get_balance(
        constants.NETWORK_TOKENS[network_name, enums.TokenNames.ETH].int_contract_address
    )

    key_pair = KeyPair.from_private_key(private_key)

    chain = NETWORK_TO_CHAIN[network_name]

    constructor_calldata = create_accounts.get_constructor_calldata(
        wallet_name=wallet_name,
        key_pair=key_pair
    )

    try:
        if wallet_name == enums.WalletNames.Braavos:
            deploy_account_tx = await account.sign_deploy_account_transaction(
                class_hash=create_accounts.PROXY_CLASS_HASHES[wallet_name],
                contract_address_salt=key_pair.public_key,
                constructor_calldata=constructor_calldata,
                nonce=0,
                max_fee=None,
                auto_estimate=True,
            )

            if deploy_account_tx.max_fee > balance_in_wei:
                logging.critical('[Deploy Account] Insufficient balance to deploy account')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

            result = await account.client.deploy_account(deploy_account_tx)

            result = AccountDeploymentResult(
                hash=result.transaction_hash,
                account=account,
                _client=account.client
            )
        else:
            if balance_in_wei == 0:
                logging.critical('[Deploy Account] Insufficient balance to deploy account')
                return enums.TransactionStatus.INSUFFICIENT_BALANCE

            result = await Account.deploy_account(
                address=address,
                class_hash=create_accounts.PROXY_CLASS_HASHES[wallet_name],
                salt=key_pair.public_key,
                key_pair=key_pair,
                client=account.client,
                chain=chain,
                constructor_calldata=constructor_calldata,
                auto_estimate=True
            )
    except BaseException as e:
        if 'is unavailable for deployment' in str(e):
            logging.info('[Deploy Account] Account is already deployed')
            return enums.TransactionStatus.SUCCESS
        elif 'Not enough tokens at the specified address to cover deployment costs' in str(e):
            logging.critical('[Deploy Account] Insufficient balance to deploy account')
            return enums.TransactionStatus.INSUFFICIENT_BALANCE
        logging.error(f'[Deploy Account] Failed to deploy account: {e}')
        return enums.TransactionStatus.FAILED

    logging.info(f'[Deploy Account] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(result.hash)}')

    receipt = await result.wait_for_acceptance()

    if receipt.status == TransactionFinalityStatus.NOT_RECEIVED:
        logging.error('[Deploy Account] Failed to deploy account')
        return enums.TransactionStatus.FAILED
    else:
        logging.info('[Deploy Account] Successfully deployed account')
        return enums.TransactionStatus.SUCCESS


async def upgrade(
    private_key: str,
    address: str,
    network_name: enums.NetworkNames,
    wallet_name: enums.WalletNames,
    cairo_version: int,
    proxy: dict[str, str] = None
):
    logging.info(f'[Upgrade Account] Upgrading account for {wallet_name} wallet')

    if wallet_name == enums.WalletNames.Braavos:
        logging.warning('[Upgrade Account] Upgrade function is not supported for Braavos wallet')
        return enums.TransactionStatus.SUCCESS

    network = constants.NETWORKS[network_name]

    account = utils.get_account(
        network_name=network_name,
        private_key=private_key,
        address=address,
        proxy=proxy
    )

    balance_in_wei = await account.get_balance(
        constants.NETWORK_TOKENS[network_name, enums.TokenNames.ETH].int_contract_address
    )

    if balance_in_wei == 0:
        logging.critical('[Upgrade Account] Insufficient balance to upgrade account')
        return enums.TransactionStatus.INSUFFICIENT_BALANCE

    if wallet_name == enums.WalletNames.Braavos:
        abi_filename = 'braavos.json'
        version_func_name = 'get_impl_version'
        version_attr = 'res'
    else:
        abi_filename = 'argentx.json'
        version_func_name = 'getVersion'
        version_attr = 'version'

    with open(Path(__file__).parent / 'abi' / abi_filename) as file:
        wallet_abi = json.load(file)

    account_contract = utils.get_starknet_contract(
        address=address,
        abi=wallet_abi,
        provider=account,
    )

    version = (
        await account_contract.functions[version_func_name].call()
    )

    version = decode_shortstring(getattr(version, version_attr))

    if version == LAST_VERSIONS[wallet_name]:
        logging.info('[Upgrade Account] Account is already upgraded')
        return enums.TransactionStatus.SUCCESS

    if wallet_name == enums.WalletNames.ArgentXOld:
        implementation_address = create_accounts.IMPLEMENTATION_ADDRESSES[enums.WalletNames.ArgentX]

        upgrade_call = account_contract.functions['upgrade'].prepare(
            implementation=implementation_address,
            calldata=[
                0
            ]
        )

        resp = await account.execute(
            [
                upgrade_call
            ],
            cairo_version=cairo_version,
            auto_estimate=True
        )

        logging.info(f'[Upgrade Account] Transaction: {network.txn_explorer_url}{utils.int_hash_to_hex(resp.transaction_hash)}')

        receipt = await utils.wait_for_starknet_receipt(
        client=account.client,
        transaction_hash=resp.transaction_hash,
        logging_prefix='Upgrade Account'
    )

        if receipt.execution_status == TransactionExecutionStatus.SUCCEEDED:
            logging.info(f'[Upgrade Account] Successfully upgraded account')
            return enums.TransactionStatus.SUCCESS
        else:
            logging.error(f'[Upgrade Account] Failed to upgrade account')
            return enums.TransactionStatus.FAILED

    return enums.TransactionStatus.SUCCESS
