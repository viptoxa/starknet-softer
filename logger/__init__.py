import logging
from uuid import uuid4

from telebot import TeleBot


class TelegramHandler(logging.Handler):
    def __init__(self, token: str, chat_id: int):
        super().__init__()
        self.bot = TeleBot(token=token)
        self.chat_id = chat_id
        self.session = str(uuid4()).replace('-', '')
        self.bot.send_message(
            chat_id=self.chat_id,
            text=f'Starting session with ID #{self.session}'
        )

    def emit(self, record: logging.LogRecord) -> None:
        log_entry = self.format(record)
        log_entry = f'#{self.session}\n{log_entry}'
        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=log_entry,
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f'Error while sending log message using Telegram bot: {e}')


logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.CRITICAL,
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('Starknet')
logger.setLevel(logging.INFO)
logging = logger
