import platform
import subprocess
from pathlib import Path


def main():
    system = platform.system()
    python_version = platform.python_version()

    python_version = ''.join(python_version.split('.')[:2])

    libs_path = Path(__file__).parent / 'ed25519_blake2b'

    if system == 'Darwin':
        libs_path /= 'macos'

        if python_version == '37':
            architecture = 'macosx_10_9_x86_64'
        elif python_version == '38':
            architecture = 'macosx_11_0_universal2'
        else:
            architecture = 'macosx_10_9_universal2'

        lib_path = libs_path / f'ed25519_blake2b-1.4-cp{python_version}-cp{python_version}-{architecture}.whl'
    elif system == 'Windows':
        libs_path /= 'win'
        architecure = platform.architecture()[0]

        if architecure == '32bit':
            architecure = 'win32'
        else:
            architecure = 'win_amd64'

        lib_path = libs_path / f'ed25519_blake2b-1.4-cp{python_version}-cp{python_version}-{architecure}.whl'
    else:
        libs_path /= 'linux'
        lib_path = libs_path / f'ed25519_blake2b-1.4-cp{python_version}-cp{python_version}-linux_x86_64.whl'

    if not lib_path.exists():
        print(f'Library {lib_path} not found')
        print(f'Please, install it manually or contact developer')

        print('\n-------------------------------------------------------------------\n')

        print(f'platform.system = {platform.system()}')
        print(f'platform.machine = {platform.machine()}')
        print(f'platform.release = {platform.release()}')
        print(f'platform.version = {platform.version()}')
        print(f'platform.machine = {platform.machine()}')
        print(f'platform.architecture = {platform.architecture()}')
        print(f'platform.uname = {platform.uname()}')
        print(f'platform.platform = {platform.platform()}', end='\n\n')

        return

    subprocess.run(['pip', 'install', str(lib_path)])


if __name__ == '__main__':
    main()
