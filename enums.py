from enum import Enum, auto


class AutoEnum(Enum):
    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name

    @classmethod
    def from_string(cls, name):
        for member in cls:
            if isinstance(member.value, str):
                if member.value.lower() == name.lower():
                    return member
            else:
                if member.name.lower() == name.lower():
                    return member
        raise ValueError(f'No {cls.__name__} member with name {name}')


class NetworkNames(AutoEnum):
    ETH = 1
    Goerli = 5
    Arbitrum = 42161
    ArbitrumTestnet = 421613
    Optimism = 10
    OptimismTestnet = 420
    Starknet = -1
    StarknetTestnet = -2
    Exchange = -3
    DefinedInParams = -4


class TokenNames(AutoEnum):
    ETH = auto()
    DAI = auto()
    USDC = auto()
    USDT = auto()
    WBTC = auto()
    Random = auto()
    Last = auto()
    All = auto()


class TransactionStatus(AutoEnum):
    SUCCESS = auto()
    INSUFFICIENT_LIQUIDITY = auto()
    INSUFFICIENT_BALANCE = auto()
    FAILED = auto()
    NO_LIQUIDITIES = auto()
    NO_COLLECTIONS = auto()
    LIMIT_REACHED = auto()
    INCORRECT_NETWORK = auto()
    ADDRESS_NOT_ALLOWLISTED = auto()


class ModuleNames(AutoEnum):
    Avnu = auto()
    Deploy = auto()
    Dmail = auto()
    Fibrous = auto()
    JediSwap = auto()
    LayerSwap = auto()
    mySwap = auto()
    OKX = auto()
    Orbiter = auto()
    Sleep = auto()
    StarkGate = auto()
    StarknetID = auto()
    StarkVerse = auto()
    TenKSwap = '10KSwap'
    Upgrade = auto()
    zkLend = auto()
    Random = auto()
    EndRandom = auto()


class FunctionNames(AutoEnum):
    SWAP = auto()
    POOL = auto()
    ADD_LIQUIDITY = auto()
    REMOVE_LIQUIDITY = auto()
    SUPPLY = auto()
    BORROW = auto()
    REPAY = auto()
    WITHDRAW = auto()
    DEPOSIT_TO_OKX = auto()
    WITHDRAW_FROM_OKX = auto()
    SUBS_TO_MAIN = auto()
    DEPOSIT_TO_STARKNET = auto()
    WITHDRAW_FROM_STARKNET = auto()


class WalletNames(AutoEnum):
    ArgentX = auto()
    ArgentXOld = auto()
    Braavos = auto()
