from typing import Protocol
import httpx
from app.config import get_settings
class TelegramGateway(Protocol):
    async def send_business_message(self,business_connection_id:str,chat_id:int,text:str)->dict: ...
    async def get_business_connection(self,business_connection_id:str)->dict: ...
class TelegramClient:
    def __init__(self): self.s=get_settings(); self.base=f"https://api.telegram.org/bot{self.s.telegram_bot_token}"
    async def _call(self,method,payload):
        async with httpx.AsyncClient(timeout=10) as client: response=await client.post(f"{self.base}/{method}",json=payload)
        response.raise_for_status(); data=response.json()
        if not data.get("ok"): raise RuntimeError("Telegram API rejected request")
        return data["result"]
    async def send_business_message(self,business_connection_id,chat_id,text): return await self._call("sendMessage",{"business_connection_id":business_connection_id,"chat_id":chat_id,"text":text})
    async def get_business_connection(self,business_connection_id): return await self._call("getBusinessConnection",{"business_connection_id":business_connection_id})
