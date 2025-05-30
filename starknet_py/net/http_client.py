from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from aiohttp import ClientResponse, ClientSession
from aiohttp_socks import ProxyConnector

from starknet_py.net.client_errors import ClientError


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"


class HttpClient(ABC):
    def __init__(
        self,
        url,
        session: Optional[ClientSession] = None,
        user_agent: Optional[str] = None,
        proxy: Optional[str] = None
    ):
        self.url = url
        self.session = session
        self.user_agent = user_agent
        self.proxy = proxy

    async def request(
        self,
        address: str,
        http_method: HttpMethod,
        params: Optional[dict] = None,
        payload: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    ):
        kwargs = {
            "address": address,
            "http_method": http_method,
            "params": params,
            "payload": payload,
        }
        if self.session:
            return await self._make_request(session=self.session, **kwargs)

        if self.proxy and self.proxy.startswith('socks5://'):
            connector = ProxyConnector.from_url(url=self.proxy, rdns=True)
        else:
            connector = None

        async with ClientSession(connector=connector) as session:
            return await self._make_request(session=session, **kwargs)

    async def _make_request(
        self,
        session: ClientSession,
        address: str,
        http_method: HttpMethod,
        params: dict,
        payload: dict,
    ) -> dict:
        # pylint: disable=too-many-arguments
        headers = None
        if self.user_agent:
            headers = {"User-Agent": self.user_agent}
        max_retries = 10
        for retry in range(max_retries):
            async with session.request(
                method=http_method.value,
                url=address,
                params=params,
                json=payload,
                headers=headers,
                proxy=None if self.proxy and self.proxy.startswith('socks5://') else self.proxy
            ) as request:
                if request.status == 502 and 'Please try again in 30 seconds.' in await request.text() and retry < max_retries - 1:
                    continue
                await self.handle_request_error(request)
                return await request.json(content_type=None)

    @abstractmethod
    async def handle_request_error(self, request: ClientResponse):
        """
        Handle an errors returned by make_request
        """


class GatewayHttpClient(HttpClient):
    async def call(self, method_name: str, params: Optional[dict] = None) -> dict:
        return await self.request(
            http_method=HttpMethod.GET, address=self.address(method_name), params=params
        )

    async def post(
        self,
        method_name: str,
        payload: Union[Dict[str, Any], List[Dict[str, Any]]],
        params: Optional[dict] = None,
    ) -> dict:
        return await self.request(
            http_method=HttpMethod.POST,
            address=self.address(method_name),
            payload=payload,
            params=params,
        )

    def address(self, method_name):
        return f"{self.url}/{method_name}"

    async def handle_request_error(self, request: ClientResponse):
        await basic_error_handle(request)


class RpcHttpClient(HttpClient):
    async def call(self, method_name: str, params: dict):
        payload = {
            "jsonrpc": "2.0",
            "method": f"starknet_{method_name}",
            "params": params,
            "id": 0,
        }

        result = await self.request(
            http_method=HttpMethod.POST, address=self.url, payload=payload
        )

        if "result" not in result:
            self.handle_rpc_error(result)
        return result["result"]

    @staticmethod
    def handle_rpc_error(result: dict):
        if "error" not in result:
            raise ServerError(body=result)
        raise ClientError(
            code=result["error"]["code"], message=result["error"]["message"]
        )

    async def handle_request_error(self, request: ClientResponse):
        await basic_error_handle(request)


async def basic_error_handle(request: ClientResponse):
    if request.status >= 300:
        raise ClientError(code=str(request.status), message=await request.text())


class ServerError(Exception):
    def __init__(self, body: dict):
        self.message = "RPC request failed."
        self.body = body
        super().__init__(self.message)
