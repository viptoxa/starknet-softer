import hashlib
from collections import OrderedDict
from pathlib import Path

import pandas as pd
import tqdm
from bip_utils import Bip39SeedGenerator
from eth_account import Account as ETHAccount
from hdwallet import HDWallet

import enums
import utils
from starknet_py.cairo.data_types import FeltType, ArrayType
from starknet_py.constants import EC_ORDER
from starknet_py.hash.address import compute_address
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.serialization import serializer_for_type
from starknet_py.serialization.data_serializers.payload_serializer import PayloadSerializer

IMPLEMENTATION_ADDRESSES = {
    enums.WalletNames.ArgentX: 0x01a736d6ed154502257f02b1ccdf4d9d1089f80811cd6acad48e6b6a9d1f2003,
    enums.WalletNames.ArgentXOld: 0x033434ad846cdd5f23eb73ff09fe6fddd568284a0fb7d1be20ee482f044dabe2,
    enums.WalletNames.Braavos: 0x5aa23d5bb71ddaa783da7ea79d405315bafa7cf0387a74f4593578c3e9e6570
}

INITIALIZE_SELECTORS = {
    enums.WalletNames.ArgentXOld: 0x79dc0da7c54b95f10aa182ad0a46400db63156920adb65eca2654c0945a463,
    enums.WalletNames.Braavos: 0x2dd76e7ad84dbed81c314ffe5e7a7cacfb8f4836f01af4e913f275f89a3de1a
}

PROXY_CLASS_HASHES = {
    enums.WalletNames.ArgentX: 0x01a736d6ed154502257f02b1ccdf4d9d1089f80811cd6acad48e6b6a9d1f2003,
    enums.WalletNames.ArgentXOld: 0x25ec026985a3bf9d0cc1fe17326b245dfdc3ff89b8fde106542a3ea56c5a918,
    enums.WalletNames.Braavos: 0x03131fa018d520a037686ce3efddeab8f28895662f019ca3ca18a626650f7d1e
}

ACCOUNT_CLASS_HASHES = {
    enums.WalletNames.Braavos: 0x05dec330eebf36c8672b60db4a718d44762d3ae6d1333e553197acb47ee5a062
}


def generate_mnemonic() -> str:
    ETHAccount.enable_unaudited_hdwallet_features()
    acct, mnemonic = ETHAccount.create_with_mnemonic()

    return mnemonic


def eip_2645(key_seed: bytearray) -> str:
    sha256_max_digest = 2 ** 256

    max_allowed_val = sha256_max_digest - (sha256_max_digest % EC_ORDER)

    i = 0
    while True:
        x = key_seed + bytearray.fromhex(f'{i:0>{2}}')
        key = int.from_bytes(hashlib.sha256(x).digest(), byteorder='big')

        if key < max_allowed_val:
            return hex(key % EC_ORDER)

        i += 1


def get_constructor_calldata(
    wallet_name: enums.WalletNames,
    key_pair: KeyPair
) -> list[int]:
    initializer_serializer = PayloadSerializer(
        OrderedDict(
            [
                ('public_key', serializer_for_type(FeltType()))
            ]
        )
    )

    if wallet_name == enums.WalletNames.ArgentX:
        proxy_serializer = PayloadSerializer(
            OrderedDict(
                [
                    ('owner', serializer_for_type(FeltType())),
                    ('guardian', serializer_for_type(FeltType()))
                ]
            )
        )

        return proxy_serializer.serialize(
            {
                'owner': key_pair.public_key,
                'guardian': 0
            }
        )
    else:
        calldata = [
            initializer_serializer.serialize(
                data={
                    'public_key': key_pair.public_key
                }
            )[0]
        ]

        if wallet_name == enums.WalletNames.ArgentXOld:
            calldata.append(0)

        proxy_serializer = PayloadSerializer(
            OrderedDict(
                [
                    ('implementation_address', serializer_for_type(FeltType())),
                    ('initializer_selector', serializer_for_type(FeltType())),
                    ('calldata', serializer_for_type(ArrayType(FeltType())))
                ]
            )
        )

        return proxy_serializer.serialize(
            {
                'implementation_address': IMPLEMENTATION_ADDRESSES[wallet_name],
                'initializer_selector': INITIALIZE_SELECTORS[wallet_name],
                'calldata': calldata
            }
        )


def wallet_from_private_key(
    private_key: str,
    wallet_name: enums.WalletNames
) -> tuple[KeyPair, str]:
    key_pair = KeyPair.from_private_key(private_key)

    constructor_calldata = get_constructor_calldata(
        wallet_name=wallet_name,
        key_pair=key_pair
    )

    address = hex(
        compute_address(
            salt=key_pair.public_key,
            class_hash=PROXY_CLASS_HASHES[wallet_name],
            constructor_calldata=constructor_calldata,
            deployer_address=0
        )
    )

    return key_pair, address


def wallet_from_mnemonic(
    mnemonic: str,
    wallet_name: enums.WalletNames
) -> tuple[KeyPair, str]:
    if wallet_name == enums.WalletNames.Braavos:
        seed = Bip39SeedGenerator(mnemonic).Generate().hex()
    else:
        ETHAccount.enable_unaudited_hdwallet_features()
        account = ETHAccount.from_mnemonic(mnemonic)
        seed = hex(int(account._private_key.hex(), 16))[2:]
        if len(seed) % 2 != 0:
            seed = '0' + seed

    hdwallet = HDWallet(symbol='ETH')

    hdwallet.from_seed(seed)

    hdwallet.from_index(44, hardened=True)
    hdwallet.from_index(9004, hardened=True)
    hdwallet.from_index(0, hardened=True)
    hdwallet.from_index(0)
    hdwallet.from_index(0)

    ground_key = eip_2645(bytearray.fromhex(hdwallet.private_key()))

    return wallet_from_private_key(ground_key, wallet_name)


def main():
    wallet_name = input('Input wallet name ([B]raavos or [A]rgentX): ')

    if wallet_name.lower() in {'b', 'braavos'}:
        wallet_name = enums.WalletNames.Braavos
    elif wallet_name.lower() in {'a', 'argentx'}:
        wallet_name = enums.WalletNames.ArgentX
    else:
        print('Wrong wallet name')
        return

    amount = int(input('Input amount of wallets to generate: '))

    if amount <= 0:
        print('Wrong amount')
        return

    wallets = []

    for i in tqdm.trange(amount):
        mnemonic = generate_mnemonic()
        key_pair, address = wallet_from_mnemonic(mnemonic, wallet_name)
        address = utils.extend_hex(address, 64)

        wallets.append([str(wallet_name), mnemonic, hex(key_pair.private_key), address])

    filepath = Path(__file__).parent / 'wallets.xlsx'

    open_mode = 'w'

    wallets_df = pd.DataFrame(wallets, columns=['wallet_name', 'mnemonic', 'private_key', 'address'])

    if filepath.exists():
        overwrite = input(f'File {filepath.name} already exists. Do you want to overwrite it? If not, wallets will be appended to it [y/n]: ')
        if overwrite.lower() == 'n':
            open_mode = 'a'
            existed_wallets_df = pd.read_excel(filepath, header=0)
            wallets_df = pd.concat([existed_wallets_df, wallets_df])
        elif overwrite.lower() != 'y':
            print('Wrong answer')
            return

    try:
        wallets_df.to_excel(filepath, index=False)
    except PermissionError:
        print(f'File {filepath} cannot be open. It is used by another process. Please close it and try again')
        return

    print(f'Wallets saved to {filepath}')


if __name__ == '__main__':
    main()
