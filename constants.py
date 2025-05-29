import json
import typing
from dataclasses import dataclass
from pathlib import Path

import enums
from starknet_py.net import networks as starknet_networks


@dataclass
class Network:
    chain_id: int
    name: str
    rpc_url: str
    txn_explorer_url: str

    def __repr__(self):
        return f'{self.name} (ID: {self.chain_id})'


@dataclass
class NetworkToken:
    network: Network
    token: enums.TokenNames
    contract_address: str
    decimals: int

    @property
    def int_contract_address(self) -> int:
        return int(self.contract_address, 16)

    def __lt__(self, other):
        return self.int_contract_address < other.int_contract_address

    def __le__(self, other):
        return self.int_contract_address <= other.int_contract_address

    def __eq__(self, other):
        return self.int_contract_address == other.int_contract_address

    def __ne__(self, other):
        return self.int_contract_address != other.int_contract_address

    def __gt__(self, other):
        return self.int_contract_address > other.int_contract_address

    def __ge__(self, other):
        return self.int_contract_address >= other.int_contract_address

    def __int__(self):
        return int(self.contract_address, 16)


class NetworksDict(dict):
    def __getitem__(self, item: typing.Union[enums.NetworkNames, int]) -> typing.Optional[Network]:
        if isinstance(item, int):
            item = enums.NetworkNames(item)
        return super().__getitem__(item)


with open(Path(__file__).parent / 'RPC.json') as file:
    rpc_list = json.load(file)

NETWORKS = NetworksDict({
    enums.NetworkNames.Starknet: Network(
        'SN_MAIN',
        'Starknet Mainnet',
        rpc_list.get(
            enums.NetworkNames.Starknet.name,
            'https://starknet-mainnet.public.blastapi.io'
        ),
        'https://starkscan.co/tx/'
    ),
    enums.NetworkNames.StarknetTestnet: Network(
        'SN_GOERLI',
        'Starknet Goerli',
        rpc_list.get(
            enums.NetworkNames.StarknetTestnet.name,
            'https://starknet-testnet.public.blastapi.io'
        ),
        'https://testnet.starkscan.co/tx/'
    ),
    enums.NetworkNames.ETH: Network(
        1,
        'Ethereum Mainnet',
        rpc_list.get(
            enums.NetworkNames.ETH.name,
            'https://rpc.ankr.com/eth'
        ),
        'https://etherscan.io/tx/'
    ),
    enums.NetworkNames.Arbitrum: Network(
        42161,
        'Arbitrum One',
        rpc_list.get(
            enums.NetworkNames.Arbitrum.name,
            'https://arb-mainnet-public.unifra.io'
        ),
        'https://arbiscan.io/tx/'
    ),
    enums.NetworkNames.Optimism: Network(
        10,
        'Optimism',
        rpc_list.get(
            enums.NetworkNames.Optimism.name,
            'https://optimism-mainnet.public.blastapi.io'
        ),
        'https://optimistic.etherscan.io/tx/'
    ),
    enums.NetworkNames.Goerli: Network(
        5,
        'Goerli',
        rpc_list.get(
            enums.NetworkNames.Goerli.name,
            'https://eth-goerli.public.blastapi.io'
        ),
        'https://goerli.etherscan.io/tx/'
    ),
    enums.NetworkNames.ArbitrumTestnet: Network(
        421613,
        'Arbitrum Goerli',
        rpc_list.get(
            enums.NetworkNames.ArbitrumTestnet.name,
            'https://arbitrum-goerli.public.blastapi.io'
        ),
        'https://goerli.arbiscan.io/tx/'
    ),
    enums.NetworkNames.OptimismTestnet: Network(
        420,
        'Optimism Goerli',
        rpc_list.get(
            enums.NetworkNames.OptimismTestnet.name,
            'https://optimism-goerli.public.blastapi.io'
        ),
        'https://goerli-optimism.etherscan.io/tx/'
    )
})


class NetworkTokensDict(dict):
    def __getitem__(
        self,
        item: typing.Union[
            enums.NetworkNames,
            int,
            typing.Tuple[
                typing.Union[enums.NetworkNames, int],
                typing.Union[enums.TokenNames, str]
            ]
        ]
    ) -> typing.Union[
        NetworkToken,
        typing.Dict[enums.TokenNames, NetworkToken],
    ]:
        if isinstance(item, enums.NetworkNames):
            return super().__getitem__(item)
        elif isinstance(item, int):
            return super().__getitem__(enums.TokenNames(item))
        elif isinstance(item, tuple):
            return self.__getitem__(item[0])[enums.TokenNames(item[1])]


NETWORK_TOKENS = NetworkTokensDict({
    enums.NetworkNames.Starknet: {
        enums.TokenNames.ETH: NetworkToken(
            NETWORKS[enums.NetworkNames.Starknet],
            enums.TokenNames.ETH,
            '0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7',
            18
        ),
        enums.TokenNames.USDC: NetworkToken(
            NETWORKS[enums.NetworkNames.Starknet],
            enums.TokenNames.USDC,
            '0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8',
            6
        ),
        enums.TokenNames.DAI: NetworkToken(
            NETWORKS[enums.NetworkNames.Starknet],
            enums.TokenNames.DAI,
            '0x00da114221cb83fa859dbdb4c44beeaa0bb37c7537ad5ae66fe5e0efd20e6eb3',
            18
        ),
        enums.TokenNames.USDT: NetworkToken(
            NETWORKS[enums.NetworkNames.Starknet],
            enums.TokenNames.USDT,
            '0x068f5c6a61780768455de69077e07e89787839bf8166decfbf92b645209c0fb8',
            6
        ),
        enums.TokenNames.WBTC: NetworkToken(
            NETWORKS[enums.NetworkNames.Starknet],
            enums.TokenNames.WBTC,
            '0x3fe2b97c1fd336e750087d68b9b867997fd64a2661ff3ca5a7c771641e8e7ac',
            8
        )
    },
    enums.NetworkNames.StarknetTestnet: {
        enums.TokenNames.ETH: NetworkToken(
            NETWORKS[enums.NetworkNames.StarknetTestnet],
            enums.TokenNames.ETH,
            '0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7',
            18
        ),
        enums.TokenNames.USDC: NetworkToken(
            NETWORKS[enums.NetworkNames.StarknetTestnet],
            enums.TokenNames.USDC,
            '0x5a643907b9a4bc6a55e9069c4fd5fd1f5c79a22470690f75556c4736e34426',
            6
        ),
        enums.TokenNames.DAI: NetworkToken(
            NETWORKS[enums.NetworkNames.StarknetTestnet],
            enums.TokenNames.DAI,
            '0x03e85bfbb8e2a42b7bead9e88e9a1b19dbccf661471061807292120462396ec9',
            18
        )
    }
})

STABLECOINS = {
    enums.TokenNames.USDC,
    enums.TokenNames.DAI,
    enums.TokenNames.USDT
}

COINGECKO_NAMES = {
    enums.TokenNames.ETH: 'ethereum',
    enums.TokenNames.WBTC: 'wrapped-bitcoin'
}

DEFAULT_PRICES = {
    enums.TokenNames.ETH: 2034,
    enums.TokenNames.WBTC: 37300
}

CRITICAL_RESULTS = {
    enums.TransactionStatus.INSUFFICIENT_BALANCE,
    enums.TransactionStatus.FAILED,
    enums.TransactionStatus.ADDRESS_NOT_ALLOWLISTED
}

SWAP_PAIRS = {
    enums.ModuleNames.Avnu: {
        enums.NetworkNames.Starknet: {
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.ETH, enums.TokenNames.USDT),
            (enums.TokenNames.ETH, enums.TokenNames.WBTC),
            (enums.TokenNames.DAI, enums.TokenNames.USDC),
            (enums.TokenNames.DAI, enums.TokenNames.USDT),
            (enums.TokenNames.DAI, enums.TokenNames.WBTC),
            (enums.TokenNames.USDC, enums.TokenNames.USDT),
            (enums.TokenNames.USDC, enums.TokenNames.WBTC),
            (enums.TokenNames.USDT, enums.TokenNames.WBTC)
        },
        enums.NetworkNames.StarknetTestnet: {
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.DAI, enums.TokenNames.USDC),
        }
    },
    enums.ModuleNames.Fibrous: {
        enums.NetworkNames.Starknet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.ETH, enums.TokenNames.USDT),
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.USDC, enums.TokenNames.USDT),
            (enums.TokenNames.USDC, enums.TokenNames.DAI),
            (enums.TokenNames.USDT, enums.TokenNames.DAI)
        }
    },
    enums.ModuleNames.JediSwap: {
        enums.NetworkNames.Starknet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.ETH, enums.TokenNames.USDT),
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.USDC, enums.TokenNames.USDT),
            (enums.TokenNames.USDC, enums.TokenNames.DAI),
            (enums.TokenNames.USDT, enums.TokenNames.DAI)
        },
        enums.NetworkNames.StarknetTestnet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.USDC, enums.TokenNames.DAI),
        }
    },
    enums.ModuleNames.mySwap: {
        enums.NetworkNames.Starknet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.ETH, enums.TokenNames.USDT),
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.USDC, enums.TokenNames.USDT),
            (enums.TokenNames.USDC, enums.TokenNames.DAI),
        },
        enums.NetworkNames.StarknetTestnet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.USDC, enums.TokenNames.DAI),
        }
    },
    enums.ModuleNames.TenKSwap: {
        enums.NetworkNames.Starknet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.ETH, enums.TokenNames.USDT),
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.USDC, enums.TokenNames.USDT),
            (enums.TokenNames.USDC, enums.TokenNames.DAI),
            (enums.TokenNames.USDT, enums.TokenNames.DAI)
        },
        enums.NetworkNames.StarknetTestnet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
            (enums.TokenNames.ETH, enums.TokenNames.DAI),
            (enums.TokenNames.USDC, enums.TokenNames.DAI),
        }
    }
}

POOLS = {
    enums.ModuleNames.JediSwap: {
        enums.NetworkNames.Starknet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
        },
        enums.NetworkNames.StarknetTestnet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
        }
    },
    enums.ModuleNames.mySwap: {
        enums.NetworkNames.Starknet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
        },
        enums.NetworkNames.StarknetTestnet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
        }
    },
    enums.ModuleNames.TenKSwap: {
        enums.NetworkNames.Starknet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
        },
        enums.NetworkNames.StarknetTestnet: {
            (enums.TokenNames.ETH, enums.TokenNames.USDC),
        }
    }
}

MAINNET_MODULE_NETWORKS = {
    enums.ModuleNames.Avnu: enums.NetworkNames.Starknet,
    enums.ModuleNames.Deploy: enums.NetworkNames.Starknet,
    enums.ModuleNames.Dmail: enums.NetworkNames.Starknet,
    enums.ModuleNames.Fibrous: enums.NetworkNames.Starknet,
    enums.ModuleNames.JediSwap: enums.NetworkNames.Starknet,
    enums.ModuleNames.LayerSwap: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET: enums.NetworkNames.DefinedInParams,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET: enums.NetworkNames.Starknet
    },
    enums.ModuleNames.mySwap: enums.NetworkNames.Starknet,
    enums.ModuleNames.OKX: {
        enums.FunctionNames.DEPOSIT_TO_OKX: enums.NetworkNames.DefinedInParams,
        enums.FunctionNames.WITHDRAW_FROM_OKX: enums.NetworkNames.Exchange,
        enums.FunctionNames.SUBS_TO_MAIN: enums.NetworkNames.Exchange
    },
    enums.ModuleNames.Orbiter: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET: enums.NetworkNames.DefinedInParams,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET: enums.NetworkNames.Starknet
    },
    enums.ModuleNames.StarkGate: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET: enums.NetworkNames.DefinedInParams,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET: enums.NetworkNames.Starknet
    },
    enums.ModuleNames.StarknetID: enums.NetworkNames.Starknet,
    enums.ModuleNames.StarkVerse: enums.NetworkNames.Starknet,
    enums.ModuleNames.TenKSwap: enums.NetworkNames.Starknet,
    enums.ModuleNames.Upgrade: enums.NetworkNames.Starknet,
    enums.ModuleNames.zkLend: enums.NetworkNames.Starknet
}

TESTNET_MODULE_NETWORKS = {
    enums.ModuleNames.Avnu: enums.NetworkNames.StarknetTestnet,
    enums.ModuleNames.Deploy: enums.NetworkNames.StarknetTestnet,
    enums.ModuleNames.Dmail: None,
    enums.ModuleNames.Fibrous: None,
    enums.ModuleNames.JediSwap: enums.NetworkNames.StarknetTestnet,
    enums.ModuleNames.LayerSwap: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET: enums.NetworkNames.DefinedInParams,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET: enums.NetworkNames.StarknetTestnet
    },
    enums.ModuleNames.mySwap: enums.NetworkNames.StarknetTestnet,
    enums.ModuleNames.OKX: None,
    enums.ModuleNames.Orbiter: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET: enums.NetworkNames.DefinedInParams,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET: enums.NetworkNames.StarknetTestnet
    },
    enums.ModuleNames.StarkGate: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET: enums.NetworkNames.DefinedInParams,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET: enums.NetworkNames.StarknetTestnet
    },
    enums.ModuleNames.StarknetID: enums.NetworkNames.StarknetTestnet,
    enums.ModuleNames.StarkVerse: None,
    enums.ModuleNames.TenKSwap: enums.NetworkNames.StarknetTestnet,
    enums.ModuleNames.Upgrade: enums.NetworkNames.StarknetTestnet,
    enums.ModuleNames.zkLend: None
}

MODULE_FUNCTIONS = {
    enums.ModuleNames.Avnu: {},
    enums.ModuleNames.Deploy: {},
    enums.ModuleNames.Dmail: {},
    enums.ModuleNames.Fibrous: {},
    enums.ModuleNames.JediSwap: {
        enums.FunctionNames.SWAP,
        enums.FunctionNames.POOL,
    },
    enums.ModuleNames.LayerSwap: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET,
    },
    enums.ModuleNames.mySwap: {
        enums.FunctionNames.SWAP,
        enums.FunctionNames.POOL,
    },
    enums.ModuleNames.OKX: {
        enums.FunctionNames.DEPOSIT_TO_OKX,
        enums.FunctionNames.WITHDRAW_FROM_OKX,
        enums.FunctionNames.SUBS_TO_MAIN
    },
    enums.ModuleNames.Orbiter: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET,
    },
    enums.ModuleNames.Sleep: {},
    enums.ModuleNames.StarkGate: {
        enums.FunctionNames.DEPOSIT_TO_STARKNET,
        enums.FunctionNames.WITHDRAW_FROM_STARKNET,
    },
    enums.ModuleNames.StarknetID: {},
    enums.ModuleNames.StarkVerse: {},
    enums.ModuleNames.TenKSwap: {
        enums.FunctionNames.SWAP,
        enums.FunctionNames.POOL,
    },
    enums.ModuleNames.Upgrade: {},
    enums.ModuleNames.zkLend: {},
    enums.ModuleNames.Random: {},
    enums.ModuleNames.EndRandom: {}
}
