import accounts_loader

def main():
    accounts = accounts_loader.read_accounts()

    for account in accounts:
        print(f'Account {account.short_private_key}:')
        for index, task in enumerate(account.tasks):
            print(f'{task.module_name}', end='')
            if task.function_name:
                print(f' - {task.function_name}', end='')
            if index != len(account.tasks) - 1:
                print(' ➔ ', end='')

        print('\n')


if __name__ == '__main__':
    main()
