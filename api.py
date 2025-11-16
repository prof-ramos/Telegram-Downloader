from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import DEFAULT_LIMIT_PER_CHAT
from telethon_handlers import export_chat_list, export_all_chats_media
from api_helpers import start_qr_login, check_qr_login, get_active_client
from group_management import (
    export_groups_only,
    leave_group,
    leave_multiple_groups,
    export_all_group_content,
    forward_conversation,
    copy_conversation
)
from logger import setup_logger, get_logger

# Setup logging for API
setup_logger(console_level="INFO", file_level="DEBUG")
logger = get_logger("api")

app = FastAPI(title="Telegram Downloader API")


# Pydantic models for request validation
class LeaveGroupRequest(BaseModel):
    group_id: int
    confirm: bool = False


class LeaveMultipleGroupsRequest(BaseModel):
    group_ids: List[int]
    confirm_each: bool = False


class ExportGroupContentRequest(BaseModel):
    group_id: int
    include_media: bool = True
    include_messages: bool = True
    limit: Optional[int] = None


class ForwardConversationRequest(BaseModel):
    source_chat_id: int
    destination_chat_id: int
    message_ids: Optional[List[int]] = None
    limit: Optional[int] = None
    filter_text: Optional[str] = None


class CopyConversationRequest(BaseModel):
    source_chat_id: int
    destination_chat_id: int
    limit: Optional[int] = None
    copy_media: bool = True


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


# Group Management Endpoints

@app.get("/groups/list")
async def groups_list():
    """List only groups (excluding channels and private chats)"""
    logger.info("Listagem de grupos solicitada via API")
    client = get_active_client()
    if not client:
        logger.warning("Tentativa de listar grupos sem autenticação")
        raise HTTPException(status_code=400, detail="not_authenticated")

    try:
        groups = await export_groups_only(client)
        logger.info(f"{len(groups)} grupos exportados via API")
        return {"count": len(groups), "groups": groups}
    except Exception as e:
        logger.error(f"Erro ao listar grupos via API: {e}", exc_info=True)
        raise


@app.post("/groups/leave")
async def group_leave(request: LeaveGroupRequest):
    """Leave a specific group"""
    logger.info(f"Saída do grupo {request.group_id} solicitada via API")
    client = get_active_client()
    if not client:
        logger.warning("Tentativa de sair de grupo sem autenticação")
        raise HTTPException(status_code=400, detail="not_authenticated")

    try:
        result = await leave_group(client, request.group_id, confirm=request.confirm)
        logger.info(f"Resultado da saída do grupo: {result}")
        return {"success": result, "group_id": request.group_id}
    except Exception as e:
        logger.error(f"Erro ao sair do grupo via API: {e}", exc_info=True)
        raise


@app.post("/groups/leave-multiple")
async def groups_leave_multiple(request: LeaveMultipleGroupsRequest):
    """Leave multiple groups"""
    logger.info(f"Saída de {len(request.group_ids)} grupos solicitada via API")
    client = get_active_client()
    if not client:
        logger.warning("Tentativa de sair de grupos sem autenticação")
        raise HTTPException(status_code=400, detail="not_authenticated")

    try:
        successful, failed = await leave_multiple_groups(
            client,
            request.group_ids,
            confirm_each=request.confirm_each
        )
        logger.info(f"Saída de grupos: {successful} sucessos, {failed} falhas")
        return {"successful": successful, "failed": failed}
    except Exception as e:
        logger.error(f"Erro ao sair de múltiplos grupos via API: {e}", exc_info=True)
        raise


@app.post("/groups/export-content")
async def group_export_content(request: ExportGroupContentRequest):
    """Export all content from a group"""
    logger.info(f"Exportação completa do grupo {request.group_id} solicitada via API")
    client = get_active_client()
    if not client:
        logger.warning("Tentativa de exportar conteúdo sem autenticação")
        raise HTTPException(status_code=400, detail="not_authenticated")

    try:
        stats = await export_all_group_content(
            client,
            request.group_id,
            include_media=request.include_media,
            include_messages=request.include_messages,
            limit=request.limit
        )
        logger.info(f"Exportação completa concluída: {stats}")
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Erro ao exportar conteúdo do grupo via API: {e}", exc_info=True)
        raise


@app.post("/conversations/forward")
async def conversation_forward(request: ForwardConversationRequest):
    """Forward messages from one chat to another"""
    logger.info(
        f"Forward de conversas de {request.source_chat_id} "
        f"para {request.destination_chat_id} solicitado via API"
    )
    client = get_active_client()
    if not client:
        logger.warning("Tentativa de forward sem autenticação")
        raise HTTPException(status_code=400, detail="not_authenticated")

    try:
        count = await forward_conversation(
            client,
            request.source_chat_id,
            request.destination_chat_id,
            message_ids=request.message_ids,
            limit=request.limit,
            filter_text=request.filter_text
        )
        logger.info(f"Forward concluído: {count} mensagens")
        return {"success": True, "messages_forwarded": count}
    except Exception as e:
        logger.error(f"Erro ao fazer forward de conversas via API: {e}", exc_info=True)
        raise


@app.post("/conversations/copy")
async def conversation_copy(request: CopyConversationRequest):
    """Copy messages from one chat to another (without forward attribution)"""
    logger.info(
        f"Cópia de conversas de {request.source_chat_id} "
        f"para {request.destination_chat_id} solicitada via API"
    )
    client = get_active_client()
    if not client:
        logger.warning("Tentativa de copiar conversas sem autenticação")
        raise HTTPException(status_code=400, detail="not_authenticated")

    try:
        count = await copy_conversation(
            client,
            request.source_chat_id,
            request.destination_chat_id,
            limit=request.limit,
            copy_media=request.copy_media
        )
        logger.info(f"Cópia concluída: {count} mensagens")
        return {"success": True, "messages_copied": count}
    except Exception as e:
        logger.error(f"Erro ao copiar conversas via API: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
