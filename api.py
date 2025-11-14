from typing import List

from fastapi import FastAPI, HTTPException

from config import DEFAULT_LIMIT_PER_CHAT
from telethon_handlers import export_chat_list, export_all_chats_media
from api_helpers import start_qr_login, check_qr_login, get_active_client
from logger import setup_logger, get_logger

# Setup logging for API
setup_logger(console_level="INFO", file_level="DEBUG")
logger = get_logger("api")

app = FastAPI(title="Telegram Downloader API")


@app.on_event("startup")
async def startup_event():
    """Log API startup"""
    logger.info("=== Telegram Downloader API iniciada ===")


@app.on_event("shutdown")
async def shutdown_event():
    """Log API shutdown"""
    logger.info("=== Telegram Downloader API encerrada ===")


@app.get("/health")
async def health_check():
    logger.debug("Health check solicitado")
    return {"status": "ok"}


@app.post("/login/start")
async def login_start():
    logger.info("Login QR iniciado via API")
    try:
        result = await start_qr_login()
        logger.info(f"Login QR: {result}")
        return result
    except Exception as e:
        logger.error(f"Erro ao iniciar login QR: {e}", exc_info=True)
        raise


@app.post("/login/status")
async def login_status(password: str | None = None):
    logger.info("Verificando status de login via API")
    try:
        result = await check_qr_login(password)
        logger.info(f"Status de login: {result.get('authorized', False)}")
        return result
    except Exception as e:
        logger.error(f"Erro ao verificar status de login: {e}", exc_info=True)
        raise


@app.post("/chats/export")
async def chats_export():
    logger.info("Exportação de chats solicitada via API")
    client = get_active_client()
    if not client:
        logger.warning("Tentativa de exportar chats sem autenticação")
        raise HTTPException(status_code=400, detail="not_authenticated")

    try:
        chats = await export_chat_list(client)
        logger.info(f"{len(chats)} chats exportados via API")
        return {"count": len(chats), "chats": chats}
    except Exception as e:
        logger.error(f"Erro ao exportar chats via API: {e}", exc_info=True)
        raise


@app.post("/media/download")
async def media_download(chat_ids: List[int], limit: int = DEFAULT_LIMIT_PER_CHAT):
    logger.info(f"Download de mídia solicitado via API: {len(chat_ids)} chats, limite {limit}")
    client = get_active_client()
    if not client:
        logger.warning("Tentativa de download sem autenticação")
        raise HTTPException(status_code=400, detail="not_authenticated")

    try:
        chat_list = [{"id": cid, "title": str(cid), "type": "Unknown"} for cid in chat_ids]
        success, failed = await export_all_chats_media(client, chat_list, limit)
        logger.info(f"Download concluído via API: {success} sucessos, {failed} falhas")
        return {"success": success, "failed": failed}
    except Exception as e:
        logger.error(f"Erro ao fazer download via API: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
