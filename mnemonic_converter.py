import pandas as pd
import tqdm

import create_accounts
import enums
import utils


def main():
    wallets_df = pd.read_csv(
        'convert.csv',
        header=0,
        index_col='mnemonic',
        dtype={
            'mnemonic': str,
            'wallet_name': str,
            'address': str,
            'private_key': str
        }
    )

    if wallets_df.wallet_name.isna().any():
        print('Some wallets are missing names. Please fill them in and try again.')
        return

    for index, row in tqdm.tqdm(list(wallets_df.iterrows())):
        try:
            wallet_name = enums.WalletNames.from_string(row.wallet_name)
        except ValueError:
            print(f'Wallet {index} has invalid wallet name. Please fix it and try again.')
            return

        key_pair, address = create_accounts.wallet_from_mnemonic(
            mnemonic=row.name,
            wallet_name=wallet_name
        )

        wallets_df.loc[index, 'address'] = utils.extend_hex(address, 64)
        wallets_df.loc[index, 'private_key'] = hex(key_pair.private_key)

    print('Saving results to convert.csv')

    try:
        wallets_df.to_csv('convert.csv')
    except PermissionError:
        print('Please close convert.csv and try again.')
        return

    print('Done!')


if __name__ == '__main__':
    main()
