import accounts_loader
import utils


def main():
    accounts = accounts_loader.read_accounts()

    if accounts is False:
        print('Failed to load accounts')
        return

    for account in accounts:
        if not account.proxy:
            continue

        test_result = utils.test_proxy(account.proxy)

        if isinstance(test_result, str):
            print(f'Proxy {account.proxy["http"]} - SUCCESS - {test_result}')
        elif test_result:
            print(f'Proxy {account.proxy["http"]} - SUCCESS - Failed to get IP address')
        else:
            print(f'Proxy {account.proxy["http"]} - FAILED')


if __name__ == '__main__':
    main()
