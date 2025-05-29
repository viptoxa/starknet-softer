from logger import logging
from modules.okx_module.okx_module import transfer_from_subs

try:
    from pwinput import pwinput

    kwargs = {'mask': '*'}
except ImportError as ie:
    from getpass import getpass as pwinput

    logging.warning('[OKX Subaccounts Transfer] pwinput not installed, use `pip install pwinput` to install it')
    kwargs = {}


def main():
    api_key = pwinput('Input API Key: ', **kwargs)
    api_secret = pwinput('Input API Secret: ', **kwargs)
    api_passphrase = pwinput('Input API Passphrase: ', **kwargs)
    transfer_from_subs(api_key, api_secret, api_passphrase)


if __name__ == '__main__':
    main()
