"""
Group Management module for Telegram Media Downloader
Provides advanced group operations: export, leave, full content export, and message forwarding
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest, ForwardMessagesRequest
from telethon.tl.types import Channel, Chat, InputPeerEmpty
from tqdm import tqdm

from config import EXPORTS_DIR
from file_utils import sanitize_filename
from logger import get_logger, PerformanceLogger
from performance_utils import async_retry, DownloadPool, get_rate_limiter

logger = get_logger("group_management")


async def export_groups_only(client: TelegramClient) -> List[Dict]:
    """
    Export only groups (excluding channels and private chats)

    Args:
        client: Authenticated Telegram client

    Returns:
        List of group information dictionaries
    """
    logger.info("Exportando apenas grupos")
    print("📋 Exportando lista de grupos...")

    try:
        with PerformanceLogger("Export groups only", logger):
            # Get all dialogs
            result = await client(
                GetDialogsRequest(
                    offset_date=None,
                    offset_id=0,
                    offset_peer=InputPeerEmpty(),
                    limit=500,
                    hash=0,
                )
            )

            groups = []

            for chat in result.chats:
                # Filter only groups (Chat and Channel with megagroup=True)
                is_group = False

                if isinstance(chat, Chat):
                    is_group = True
                elif isinstance(chat, Channel):
                    # Supergroups are channels with megagroup=True
                    is_group = getattr(chat, "megagroup", False)

                if is_group:
                    group_info = {
                        "id": chat.id,
                        "title": getattr(chat, "title", f"Group_{chat.id}"),
                        "username": getattr(chat, "username", None),
                        "type": "Supergroup" if isinstance(chat, Channel) else "Group",
                        "participants_count": getattr(chat, "participants_count", 0),
                        "date": getattr(chat, "date", None),
                        "access_hash": getattr(chat, "access_hash", None),
                        "is_forum": getattr(chat, "forum", False),
                        "creator": getattr(chat, "creator", False),
                        "admin_rights": getattr(chat, "admin_rights", None) is not None,
                    }
                    groups.append(group_info)

            # Save to JSON file
            os.makedirs(EXPORTS_DIR, exist_ok=True)
            json_path = os.path.join(EXPORTS_DIR, "groups_list.json")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(groups, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"Lista de {len(groups)} grupos exportada para '{json_path}'")
            print(f"✅ Lista de {len(groups)} grupos exportada para '{json_path}'")

            # Display summary
            print(f"\n📊 Resumo dos Grupos:")
            print(f"   - Total de grupos: {len(groups)}")
            print(f"   - Supergrupos: {sum(1 for g in groups if g['type'] == 'Supergroup')}")
            print(f"   - Grupos normais: {sum(1 for g in groups if g['type'] == 'Group')}")
            print(f"   - Forums: {sum(1 for g in groups if g['is_forum'])}")
            print(f"   - Onde você é criador: {sum(1 for g in groups if g['creator'])}")
            print(f"   - Onde você é admin: {sum(1 for g in groups if g['admin_rights'])}")

            return groups

    except Exception as e:
        logger.error(f"Erro ao exportar grupos: {e}", exc_info=True)
        print(f"❌ Erro ao exportar grupos: {e}")
        return []


@async_retry(max_attempts=3, base_delay=1.0)
async def leave_group(
    client: TelegramClient,
    group_id: int,
    confirm: bool = True
) -> bool:
    """
    Leave a specific group

    Args:
        client: Telegram client
        group_id: Group ID to leave
        confirm: Ask for confirmation before leaving

    Returns:
        True if successfully left, False otherwise
    """
    logger.info(f"Tentando sair do grupo ID: {group_id}")
    print(f"🚪 Tentando sair do grupo ID: {group_id}")

    try:
        # Get group entity
        entity = await client.get_entity(group_id)
        group_name = getattr(entity, "title", f"Group_{group_id}")

        logger.info(f"Grupo encontrado: {group_name}")
        print(f"📱 Grupo: {group_name}")

        # Confirmation
        if confirm:
            response = input(f"\n⚠️  Tem certeza que deseja sair do grupo '{group_name}'? (s/N): ")
            if response.lower() not in ["s", "sim", "y", "yes"]:
                logger.info("Saída do grupo cancelada pelo usuário")
                print("❌ Operação cancelada")
                return False

        # Leave the group
        if isinstance(entity, Channel):
            await client(LeaveChannelRequest(entity))
        else:
            # For old-style groups, use delete_dialog
            await client.delete_dialog(entity)

        logger.info(f"Saiu do grupo com sucesso: {group_name}")
        print(f"✅ Você saiu do grupo '{group_name}' com sucesso!")
        return True

    except Exception as e:
        logger.error(f"Erro ao sair do grupo {group_id}: {e}", exc_info=True)
        print(f"❌ Erro ao sair do grupo: {e}")
        return False


async def leave_multiple_groups(
    client: TelegramClient,
    group_ids: List[int],
    confirm_each: bool = False
) -> Tuple[int, int]:
    """
    Leave multiple groups at once

    Args:
        client: Telegram client
        group_ids: List of group IDs to leave
        confirm_each: Ask confirmation for each group

    Returns:
        Tuple of (successful, failed)
    """
    logger.info(f"Saindo de {len(group_ids)} grupos")
    print(f"🚪 Saindo de {len(group_ids)} grupos...")

    if not confirm_each:
        response = input(f"\n⚠️  Tem certeza que deseja sair de {len(group_ids)} grupos? (s/N): ")
        if response.lower() not in ["s", "sim", "y", "yes"]:
            logger.info("Operação cancelada pelo usuário")
            print("❌ Operação cancelada")
            return 0, 0

    successful = 0
    failed = 0

    with PerformanceLogger(f"Leave {len(group_ids)} groups", logger):
        for i, group_id in enumerate(group_ids, 1):
            print(f"\n[{i}/{len(group_ids)}]")

            result = await leave_group(client, group_id, confirm=confirm_each)

            if result:
                successful += 1
            else:
                failed += 1

            # Small delay to avoid rate limiting
            if i < len(group_ids):
                await asyncio.sleep(1)

    logger.info(f"Saída de grupos concluída: {successful} sucessos, {failed} falhas")
    print(f"\n📊 Resultado:")
    print(f"   ✅ Saiu de {successful} grupos")
    print(f"   ❌ Falhou em {failed} grupos")

    return successful, failed


async def export_all_group_content(
    client: TelegramClient,
    group_id: int,
    include_media: bool = True,
    include_messages: bool = True,
    limit: Optional[int] = None
) -> Dict:
    """
    Export all content from a group (messages, media, metadata)

    Args:
        client: Telegram client
        group_id: Group ID to export
        include_media: Whether to download media files
        include_messages: Whether to export message text
        limit: Maximum number of messages (None = all)

    Returns:
        Dictionary with export statistics
    """
    logger.info(f"Exportando conteúdo completo do grupo ID: {group_id}")
    print(f"📦 Exportando conteúdo completo do grupo ID: {group_id}")

    try:
        with PerformanceLogger(f"Export all content from group {group_id}", logger):
            # Get group entity
            entity = await client.get_entity(group_id)
            group_name = getattr(entity, "title", f"Group_{group_id}")
            group_name_clean = sanitize_filename(group_name)

            logger.info(f"Grupo encontrado: {group_name}")
            print(f"📱 Grupo: {group_name}")

            # Create export directory
            export_dir = os.path.join(
                EXPORTS_DIR,
                "full_exports",
                f"{group_name_clean}_{group_id}"
            )
            os.makedirs(export_dir, exist_ok=True)

            # Export metadata
            metadata = {
                "group_id": group_id,
                "group_name": group_name,
                "export_date": datetime.now().isoformat(),
                "type": entity.__class__.__name__,
                "participants_count": getattr(entity, "participants_count", 0),
                "username": getattr(entity, "username", None),
                "is_forum": getattr(entity, "forum", False),
            }

            metadata_path = os.path.join(export_dir, "metadata.json")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            logger.info("Metadados exportados")
            print("✅ Metadados exportados")

            # Export messages
            messages_data = []
            media_count = 0
            message_count = 0

            print(f"📥 Exportando mensagens{' e mídias' if include_media else ''}...")

            # Determine limit
            if limit is None:
                # Get total message count
                total = await client.get_messages(entity, limit=1)
                limit = total.total if total else 10000
                logger.info(f"Total de mensagens no grupo: {limit}")

            pbar = tqdm(total=limit, desc="Processando mensagens", unit="msg")

            async for message in client.iter_messages(entity, limit=limit):
                message_count += 1
                pbar.update(1)

                if include_messages:
                    msg_data = {
                        "id": message.id,
                        "date": message.date.isoformat() if message.date else None,
                        "text": message.text,
                        "sender_id": message.sender_id,
                        "reply_to_msg_id": message.reply_to_msg_id,
                        "has_media": message.media is not None,
                        "views": getattr(message, "views", 0),
                        "forwards": getattr(message, "forwards", 0),
                    }
                    messages_data.append(msg_data)

                # Download media if requested
                if include_media and message.media:
                    try:
                        media_dir = os.path.join(export_dir, "media")
                        os.makedirs(media_dir, exist_ok=True)

                        filename = f"msg_{message.id}_{message.date.strftime('%Y%m%d_%H%M%S')}"
                        filepath = os.path.join(media_dir, filename)

                        await client.download_media(message, file=filepath)
                        media_count += 1
                    except Exception as e:
                        logger.warning(f"Erro ao baixar mídia da mensagem {message.id}: {e}")

            pbar.close()

            # Save messages to JSON
            if include_messages:
                messages_path = os.path.join(export_dir, "messages.json")
                with open(messages_path, "w", encoding="utf-8") as f:
                    json.dump(messages_data, f, ensure_ascii=False, indent=2)

                logger.info(f"Mensagens exportadas: {len(messages_data)}")
                print(f"✅ {len(messages_data)} mensagens exportadas")

            # Export participants (if accessible)
            try:
                participants = []
                async for user in client.iter_participants(entity, limit=None):
                    participant_data = {
                        "id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "is_bot": user.bot,
                    }
                    participants.append(participant_data)

                if participants:
                    participants_path = os.path.join(export_dir, "participants.json")
                    with open(participants_path, "w", encoding="utf-8") as f:
                        json.dump(participants, f, ensure_ascii=False, indent=2)

                    logger.info(f"Participantes exportados: {len(participants)}")
                    print(f"✅ {len(participants)} participantes exportados")

            except Exception as e:
                logger.warning(f"Não foi possível exportar participantes: {e}")
                print(f"⚠️  Não foi possível exportar lista de participantes")

            # Statistics
            stats = {
                "group_name": group_name,
                "messages_exported": message_count,
                "media_downloaded": media_count,
                "export_directory": export_dir,
            }

            logger.info(f"Exportação completa: {stats}")
            print(f"\n📊 Estatísticas da Exportação:")
            print(f"   - Mensagens exportadas: {message_count}")
            print(f"   - Mídias baixadas: {media_count}")
            print(f"   - Diretório: {export_dir}")

            return stats

    except Exception as e:
        logger.error(f"Erro ao exportar conteúdo do grupo: {e}", exc_info=True)
        print(f"❌ Erro ao exportar conteúdo do grupo: {e}")
        return {}


async def forward_conversation(
    client: TelegramClient,
    source_chat_id: int,
    destination_chat_id: int,
    message_ids: Optional[List[int]] = None,
    limit: Optional[int] = None,
    filter_text: Optional[str] = None
) -> int:
    """
    Forward messages from one chat to another

    Args:
        client: Telegram client
        source_chat_id: Source chat ID
        destination_chat_id: Destination chat ID
        message_ids: Specific message IDs to forward (if None, uses limit)
        limit: Number of recent messages to forward (if message_ids not provided)
        filter_text: Only forward messages containing this text

    Returns:
        Number of messages forwarded
    """
    logger.info(f"Encaminhando mensagens de {source_chat_id} para {destination_chat_id}")
    print(f"📨 Encaminhando mensagens...")

    try:
        with PerformanceLogger("Forward conversation", logger):
            # Get entities
            source_entity = await client.get_entity(source_chat_id)
            dest_entity = await client.get_entity(destination_chat_id)

            source_name = getattr(source_entity, "title", f"Chat_{source_chat_id}")
            dest_name = getattr(dest_entity, "title", f"Chat_{destination_chat_id}")

            logger.info(f"Origem: {source_name}, Destino: {dest_name}")
            print(f"📱 De: {source_name}")
            print(f"📱 Para: {dest_name}")

            # Collect messages to forward
            messages_to_forward = []

            if message_ids:
                # Forward specific message IDs
                logger.info(f"Encaminhando {len(message_ids)} mensagens específicas")
                messages_to_forward = message_ids
            else:
                # Collect recent messages
                if limit is None:
                    limit = 100  # Default limit

                logger.info(f"Coletando últimas {limit} mensagens")
                print(f"📥 Coletando últimas {limit} mensagens...")

                async for message in client.iter_messages(source_entity, limit=limit):
                    # Apply text filter if specified
                    if filter_text:
                        if message.text and filter_text.lower() in message.text.lower():
                            messages_to_forward.append(message.id)
                    else:
                        messages_to_forward.append(message.id)

            if not messages_to_forward:
                logger.warning("Nenhuma mensagem para encaminhar")
                print("⚠️  Nenhuma mensagem encontrada para encaminhar")
                return 0

            logger.info(f"Encaminhando {len(messages_to_forward)} mensagens")
            print(f"📨 Encaminhando {len(messages_to_forward)} mensagens...")

            # Forward messages in batches (Telegram limit: 100 per request)
            forwarded_count = 0
            batch_size = 100

            rate_limiter = get_rate_limiter()

            for i in range(0, len(messages_to_forward), batch_size):
                batch = messages_to_forward[i:i + batch_size]

                try:
                    await rate_limiter.acquire()

                    # Forward batch
                    await client.forward_messages(
                        dest_entity,
                        batch,
                        source_entity
                    )

                    forwarded_count += len(batch)
                    logger.debug(f"Batch {i//batch_size + 1}: {len(batch)} mensagens encaminhadas")
                    print(f"✅ Progresso: {forwarded_count}/{len(messages_to_forward)} mensagens")

                except Exception as e:
                    logger.error(f"Erro ao encaminhar batch: {e}")
                    print(f"⚠️  Erro em algumas mensagens: {e}")

            logger.info(f"Encaminhamento concluído: {forwarded_count} mensagens")
            print(f"\n🎉 Encaminhamento concluído!")
            print(f"📊 {forwarded_count} mensagens encaminhadas com sucesso")

            return forwarded_count

    except Exception as e:
        logger.error(f"Erro ao encaminhar conversas: {e}", exc_info=True)
        print(f"❌ Erro ao encaminhar conversas: {e}")
        return 0


async def copy_conversation(
    client: TelegramClient,
    source_chat_id: int,
    destination_chat_id: int,
    limit: Optional[int] = None,
    copy_media: bool = True
) -> int:
    """
    Copy messages from one chat to another (without forward attribution)

    Args:
        client: Telegram client
        source_chat_id: Source chat ID
        destination_chat_id: Destination chat ID
        limit: Number of messages to copy
        copy_media: Whether to copy media files

    Returns:
        Number of messages copied
    """
    logger.info(f"Copiando mensagens de {source_chat_id} para {destination_chat_id}")
    print(f"📋 Copiando mensagens...")

    try:
        with PerformanceLogger("Copy conversation", logger):
            # Get entities
            source_entity = await client.get_entity(source_chat_id)
            dest_entity = await client.get_entity(destination_chat_id)

            source_name = getattr(source_entity, "title", f"Chat_{source_chat_id}")
            dest_name = getattr(dest_entity, "title", f"Chat_{destination_chat_id}")

            logger.info(f"Origem: {source_name}, Destino: {dest_name}")
            print(f"📱 De: {source_name}")
            print(f"📱 Para: {dest_name}")

            if limit is None:
                limit = 100

            copied_count = 0
            rate_limiter = get_rate_limiter()

            print(f"📥 Copiando últimas {limit} mensagens...")

            async for message in client.iter_messages(source_entity, limit=limit):
                try:
                    await rate_limiter.acquire()

                    # Send message text
                    if message.text:
                        await client.send_message(dest_entity, message.text)
                        copied_count += 1

                    # Send media if requested
                    elif copy_media and message.media:
                        await client.send_file(dest_entity, message.media)
                        copied_count += 1

                    if copied_count % 10 == 0:
                        print(f"✅ Progresso: {copied_count} mensagens copiadas")

                except Exception as e:
                    logger.warning(f"Erro ao copiar mensagem {message.id}: {e}")

            logger.info(f"Cópia concluída: {copied_count} mensagens")
            print(f"\n🎉 Cópia concluída!")
            print(f"📊 {copied_count} mensagens copiadas com sucesso")

            return copied_count

    except Exception as e:
        logger.error(f"Erro ao copiar conversas: {e}", exc_info=True)
        print(f"❌ Erro ao copiar conversas: {e}")
        return 0
