from typing import Optional, Dict, Any

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config import API_ID, API_HASH, SESSION_NAME
from logger import get_logger

logger = get_logger("api_helpers")

_active_client: Optional[TelegramClient] = None
_qr_login = None


async def start_qr_login() -> Dict[str, Any]:
    """Start QR code login and return the URL."""
    global _active_client, _qr_login

    logger.info("Iniciando processo de login QR")
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()
    logger.debug("Cliente Telegram conectado")

    if await client.is_user_authorized():
        _active_client = client
        logger.info("Cliente já autorizado (sessão existente)")
        return {"authorized": True}

    _qr_login = await client.qr_login()
    _active_client = client
    logger.info(f"QR Code gerado: {_qr_login.url}")
    return {"authorized": False, "qr_url": _qr_login.url}


async def check_qr_login(password: Optional[str] = None) -> Dict[str, Any]:
    """Check login status. Provide password if 2FA is required."""
    global _active_client, _qr_login

    if _active_client is None:
        logger.warning("Verificação de login sem cliente ativo")
        return {"authorized": False, "detail": "login_not_started"}

    if _qr_login is None:
        authorized = await _active_client.is_user_authorized()
        logger.debug(f"Status de autorização (sem QR): {authorized}")
        return {"authorized": authorized}

    try:
        await _qr_login.wait(1)
    except TimeoutError:
        logger.debug("QR login timeout (aguardando scan)")
        return {"authorized": False}
    except SessionPasswordNeededError:
        logger.info("2FA necessário")
        if password:
            logger.info("Tentando login com senha 2FA")
            await _active_client.sign_in(password=password)
        else:
            return {"authorized": False, "detail": "2fa_required"}
    except Exception as e:
        logger.error(f"Erro durante verificação de login: {e}")
        return {"authorized": False, "detail": str(e)}

    if await _active_client.is_user_authorized():
        _qr_login = None
        logger.info("Login QR concluído com sucesso")
        return {"authorized": True}

    logger.debug("Login ainda não concluído")
    return {"authorized": False}


def get_active_client() -> Optional[TelegramClient]:
    """Return the active authenticated client if available."""
    if _active_client:
        logger.debug("Cliente ativo retornado")
    else:
        logger.debug("Nenhum cliente ativo disponível")
    return _active_client
