"""
Telethon handlers module for Telegram Media Downloader
Contains all Telethon-specific functionality including authentication,
chat listing, media downloading, and forum topic handling
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from telethon import TelegramClient
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import Channel, InputPeerEmpty
from qrcode import QRCode
from tqdm import tqdm

from config import (
    API_ID,
    API_HASH,
    SESSION_NAME,
    EXPORTS_DIR,
    MAX_FILE_SIZE,
    CONCURRENT_DOWNLOADS,
)
from file_utils import (
    sanitize_filename,
    create_media_directories,
    ensure_directories_exist,
    get_media_type_name,
    generate_filename,
    write_download_log,
    format_file_size,
)
from logger import get_logger, PerformanceLogger
from performance_utils import (
    async_retry,
    DownloadPool,
    DownloadMetrics,
    get_rate_limiter,
)

# Module logger
logger = get_logger("telethon_handlers")


def generate_qr_code(token: str) -> None:
    """Generate and display QR code in terminal"""
    qr = QRCode()
    qr.clear()
    qr.add_data(token)
    qr.print_ascii()


def display_url_as_qr(url: str) -> None:
    """Display URL and QR code in terminal"""
    print(f"URL do QR Code: {url}")
    generate_qr_code(url)


async def login_with_qr(max_attempts: int = 5) -> Optional[TelegramClient]:
    """
    Perform QR code login with error handling
    Args:
        max_attempts: Number of tries before giving up

    Returns:
        Authenticated Telegram client or None if failed
    """
    logger.info("=== INICIANDO LOGIN VIA QR CODE ===")
    print("=== INICIANDO LOGIN VIA QR CODE ===")

    with PerformanceLogger("QR Code Login", logger):
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

        if not client.is_connected():
            await client.connect()
            logger.debug("Cliente Telegram conectado")

        # Check if already authenticated
        if await client.is_user_authorized():
            logger.info("Sessão existente encontrada - Login automático realizado")
            print("✅ Sessão existente encontrada - Login automático realizado!")
            return client

        logger.info("Iniciando processo de autenticação via QR Code")
        print("🔐 Iniciando processo de autenticação via QR Code...")
        qr_login = await client.qr_login()
        logger.debug(f"Cliente conectado: {client.is_connected()}")
        print("📱 Cliente conectado:", client.is_connected())

        authenticated = False
        attempt = 1

        while not authenticated and attempt <= max_attempts:
            logger.info(f"Tentativa de login {attempt}/{max_attempts}")
            print(f"\n--- Tentativa {attempt}/{max_attempts} ---")
            display_url_as_qr(qr_login.url)
            print("📱 Escaneie o QR Code com seu Telegram...")
            print("⏱️  Aguardando 30 segundos...")

            try:
                authenticated = await qr_login.wait(30)  # 30 second timeout
                if authenticated:
                    logger.info("Login realizado com sucesso")
                    print("✅ Login realizado com sucesso!")

            except TimeoutError:
                logger.warning(f"QR Code expirou na tentativa {attempt}")
                print("⏰ QR Code expirou, gerando novo...")
                await qr_login.recreate()

            except Exception as e:
                error_str = str(e)
                if "SessionPasswordNeededError" in error_str:
                    logger.info("Autenticação 2FA necessária")
                    print("🔐 Autenticação 2FA necessária")
                    password = input("Digite sua senha 2FA: ")
                    try:
                        await client.sign_in(password=password)
                        authenticated = True
                        logger.info("Login com 2FA realizado com sucesso")
                        print("✅ Login com 2FA realizado com sucesso!")
                    except Exception as auth_error:
                        logger.error(f"Erro na autenticação 2FA: {auth_error}")
                        print(f"❌ Erro na autenticação 2FA: {auth_error}")
                        return None
                else:
                    logger.error(f"Erro durante login: {e}")
                    print(f"❌ Erro durante login: {e}")

            if not authenticated:
                attempt += 1

        if not authenticated:
            logger.error(f"QR Code não escaneado após {max_attempts} tentativas")
            print(f"❌ QR Code não escaneado após {max_attempts} tentativas.")
            return None

        logger.info("Autenticação concluída com sucesso")
        print("🎉 Autenticação concluída com sucesso!")
        return client


async def export_chat_list(client: TelegramClient) -> List[Dict]:
    """
    Export complete list of chats, groups and channels

    Args:
        client: Authenticated Telegram client

    Returns:
        List of chat information dictionaries
    """
    logger.info("Exportando lista de chats")
    print("📋 Exportando lista de chats...")

    try:
        with PerformanceLogger("Export chat list", logger):
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

            chat_list = []

            for chat in result.chats:
                chat_info = {
                    "id": chat.id,
                    "title": getattr(chat, "title", f"Chat_{chat.id}"),
                    "username": getattr(chat, "username", None),
                    "type": chat.__class__.__name__,
                    "participants_count": getattr(chat, "participants_count", 0),
                    "date": getattr(chat, "date", None),
                    "access_hash": getattr(chat, "access_hash", None),
                    "is_forum": getattr(chat, "forum", False),
                }
                chat_list.append(chat_info)

            logger.debug(f"Encontrados {len(chat_list)} chats")

            # Save to JSON file
            os.makedirs(EXPORTS_DIR, exist_ok=True)
            json_path = os.path.join(EXPORTS_DIR, "chat_list.json")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(chat_list, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"Lista de {len(chat_list)} chats exportada para '{json_path}'")
            print(f"✅ Lista de {len(chat_list)} chats exportada para '{json_path}'")
            return chat_list

    except Exception as e:
        logger.error(f"Erro ao exportar lista de chats: {e}", exc_info=True)
        print(f"❌ Erro ao exportar lista de chats: {e}")
        return []


async def get_forum_topics(client: TelegramClient, chat_entity) -> Dict[int, str]:
    """
    Get forum topics from a forum group

    Args:
        client: Telegram client
        chat_entity: Chat entity object

    Returns:
        Dictionary mapping topic ID to topic name
    """
    topics = {}

    try:
        if isinstance(chat_entity, Channel) and getattr(chat_entity, "forum", False):
            logger.info("Detectado grupo forum - obtendo tópicos")
            print("📁 Detectado grupo forum - obtendo tópicos...")

            result = await client(
                GetForumTopicsRequest(
                    channel=chat_entity,
                    offset_date=None,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )

            for topic in result.topics:
                if hasattr(topic, "id") and hasattr(topic, "title"):
                    topics[topic.id] = topic.title

            logger.info(f"Encontrados {len(topics)} tópicos no grupo forum")
            print(f"📁 Encontrados {len(topics)} tópicos no grupo forum")
            for topic_id, topic_name in topics.items():
                logger.debug(f"Tópico: {topic_name} (ID: {topic_id})")
                print(f"   - {topic_name} (ID: {topic_id})")

        return topics

    except Exception as e:
        logger.warning(f"Erro ao obter tópicos: {e}")
        print(f"⚠️ Erro ao obter tópicos: {e}")
        return {}


async def export_media_organized(
    client: TelegramClient, chat_entity, limit: int = 1000
) -> int:
    """
    Export media from a chat in organized structure with improved performance

    Args:
        client: Telegram client
        chat_entity: Chat entity to download from
        limit: Maximum number of messages to process

    Returns:
        Number of files downloaded
    """
    # Get chat information
    chat_info = await client.get_entity(chat_entity)
    chat_name = getattr(chat_info, "title", f"Chat_{chat_info.id}")
    chat_name_clean = sanitize_filename(chat_name)

    logger.info(f"Iniciando download de mídias do chat: {chat_name}")
    print(f"📥 Iniciando download de mídias do chat: {chat_name}")

    with PerformanceLogger(f"Download chat {chat_name}", logger):
        # Get forum topics if applicable
        topics = await get_forum_topics(client, chat_info)
        is_forum = len(topics) > 0

        # Create base directory structure
        base_dir = os.path.join(EXPORTS_DIR, f"{chat_name_clean}_{chat_info.id}")

        # Main media directories (for messages without topics)
        main_media_dirs = create_media_directories(base_dir)
        ensure_directories_exist(main_media_dirs)

        # Topic-specific directories (if forum)
        topic_media_dirs = {}
        if is_forum:
            for topic_id, topic_name in topics.items():
                topic_dirs = create_media_directories(base_dir, topic_name)
                topic_media_dirs[topic_id] = topic_dirs
                ensure_directories_exist(topic_dirs)

        # Setup logging
        log_file = os.path.join(base_dir, "download_log.txt")

        # Counters
        downloaded_count = 0
        topic_counts = {}
        processed_count = 0
        skipped_count = 0

        # Create download pool with improved concurrency
        download_pool = DownloadPool(
            max_concurrent=CONCURRENT_DOWNLOADS,
            rate_limiter=get_rate_limiter()
        )

        logger.info(f"Estrutura de diretórios criada em: {base_dir}")
        print(f"📁 Estrutura de diretórios criada em: {base_dir}")
        if is_forum:
            logger.info(f"Grupo com tópicos detectado - {len(topics)} tópicos organizados")
            print(f"📂 Grupo com tópicos detectado - {len(topics)} tópicos organizados")

        # Process messages with progress bar
        logger.info(f"Processando até {limit} mensagens")
        print("🔄 Processando mensagens...")

        # Collect download tasks
        download_tasks = []

        # Initialize progress bar manually for async iteration
        pbar = tqdm(total=limit, desc="Analisando mensagens", unit="msg")

        async for message in client.iter_messages(chat_entity, limit=limit):
            processed_count += 1
            pbar.update(1)

            # Skip messages without media
            if message.media is None:
                continue

            try:
                # Determine message topic (if applicable)
                topic_id = None
                topic_name = None
                current_dirs = main_media_dirs

                if (
                    is_forum
                    and hasattr(message, "reply_to")
                    and message.reply_to
                    and hasattr(message.reply_to, "reply_to_top_id")
                ):

                    top_msg_id = message.reply_to.reply_to_top_id
                    if top_msg_id in topics:
                        topic_id = top_msg_id
                        topic_name = topics[top_msg_id]
                        current_dirs = topic_media_dirs.get(top_msg_id, main_media_dirs)

                        # Initialize topic counter
                        if topic_name not in topic_counts:
                            topic_counts[topic_name] = 0

                # Determine media type and target directory
                media_type = get_media_type_name(message)
                target_dir = current_dirs.get(media_type, current_dirs["other"])

                # Generate filename
                filename = generate_filename(message, topic_name)
                filepath = os.path.join(target_dir, filename)

                # Get file size
                file_size = 0
                if hasattr(message, "document") and hasattr(message.document, "size"):
                    file_size = message.document.size or 0

                # Skip if document size exceeds limit
                if file_size > MAX_FILE_SIZE:
                    size_str = format_file_size(file_size)
                    logger.warning(f"Tamanho excede o limite ({size_str}). Pulando {filename}")
                    print(f"⚠️ Tamanho excede o limite ({size_str}). Pulando {filename}")
                    skipped_count += 1
                    continue

                # Create download task
                async def download_and_log(msg, fpath, fname, mtype, tname, fsize):
                    start = time.time()
                    logger.debug(f"Baixando: {fname}")
                    await client.download_media(msg, file=fpath)
                    duration = time.time() - start

                    write_download_log(
                        log_file,
                        fname,
                        mtype,
                        msg.id,
                        msg.date,
                        tname,
                    )

                    logger.debug(f"Download concluído: {fname} em {duration:.2f}s")
                    return (tname, fsize, duration)

                # Add to download pool
                download_tasks.append((
                    download_and_log,
                    (message, filepath, filename, media_type, topic_name, file_size),
                    {}
                ))

            except Exception as e:
                logger.error(f"Erro ao processar mensagem {message.id}: {e}")
                print(f"❌ Erro ao processar mensagem {message.id}: {e}")
                continue

        # Close progress bar
        pbar.close()

        logger.info(f"Iniciando downloads: {len(download_tasks)} arquivos")
        print(f"📥 Iniciando downloads de {len(download_tasks)} arquivos...")

        # Execute downloads with pool
        results = await download_pool.download_batch(download_tasks, show_progress=True)

        # Process results
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Erro em tarefa de download: {res}")
                print(f"❌ Erro em tarefa de download: {res}")
                continue

            downloaded_count += 1
            topic_name, file_size, duration = res
            if topic_name:
                topic_counts[topic_name] = topic_counts.get(topic_name, 0) + 1

        # Get metrics
        metrics = download_pool.get_metrics()

        # Final report
        logger.info("Download concluído")
        logger.info(f"Mensagens processadas: {processed_count}, Arquivos baixados: {downloaded_count}, Pulados: {skipped_count}")
        print(f"\n✅ Download concluído!")
        print(f"📊 Estatísticas:")
        print(f"   - Mensagens processadas: {processed_count}")
        print(f"   - Arquivos baixados: {downloaded_count}")
        print(f"   - Arquivos pulados: {skipped_count}")
        print(f"   - Total de dados: {metrics['total_mb']:.2f} MB")
        print(f"   - Velocidade média: {metrics['average_speed_mbps']:.2f} MB/s")
        print(f"   - Taxa de sucesso: {metrics['success_rate']:.1f}%")
        print(f"   - Diretório: {base_dir}")

        if topic_counts:
            logger.info(f"Downloads por tópico: {topic_counts}")
            print(f"📁 Downloads por tópico:")
            for topic, count in topic_counts.items():
                print(f"   - {topic}: {count} arquivos")

        return downloaded_count


async def export_all_chats_media(
    client: TelegramClient, chat_list: List[Dict], limit_per_chat: int = 500
) -> Tuple[int, int]:
    """
    Export media from multiple chats

    Args:
        client: Telegram client
        chat_list: List of chat information dictionaries
        limit_per_chat: Message limit per chat

    Returns:
        Tuple of (successful_exports, failed_exports)
    """
    successful_exports = 0
    failed_exports = 0

    logger.info(f"Iniciando exportação de {len(chat_list)} chats")
    print(f"🚀 Iniciando exportação de {len(chat_list)} chats...")

    with PerformanceLogger(f"Export {len(chat_list)} chats", logger):
        for i, chat_info in enumerate(chat_list, 1):
            logger.info(f"Processando chat {i}/{len(chat_list)}: {chat_info['title']}")
            print(f"\n{'='*60}")
            print(f"📱 Processando chat {i}/{len(chat_list)}: {chat_info['title']}")
            print(f"   ID: {chat_info['id']} | Tipo: {chat_info['type']}")

            try:
                # Get entity using improved resolution
                entity = await get_chat_entity_safe(client, chat_info)

                if not entity:
                    logger.warning(f"Não foi possível acessar o chat: {chat_info['title']}")
                    print(f"❌ Não foi possível acessar o chat: {chat_info['title']}")
                    failed_exports += 1
                    continue

                # Check read permissions
                try:
                    async for _ in client.iter_messages(entity, limit=1):
                        break
                    logger.debug("Permissão de leitura confirmada")
                    print(f"✅ Permissão de leitura confirmada")
                except Exception as e:
                    logger.warning(f"Sem permissão para ler histórico: {e}")
                    print(f"❌ Sem permissão para ler histórico: {e}")
                    failed_exports += 1
                    continue

                # Export media
                downloaded = await export_media_organized(client, entity, limit_per_chat)

                if downloaded > 0:
                    successful_exports += 1
                    logger.info(f"Chat concluído: {downloaded} arquivos baixados")
                    print(f"✅ Concluído: {downloaded} arquivos baixados")
                else:
                    logger.info("Nenhuma mídia encontrada neste chat")
                    print(f"ℹ️ Nenhuma mídia encontrada neste chat")

            except Exception as e:
                logger.error(f"Erro ao processar chat {chat_info['title']}: {e}", exc_info=True)
                print(f"❌ Erro ao processar chat {chat_info['title']}: {e}")
                failed_exports += 1
                continue

        logger.info(f"Exportação concluída: {successful_exports} sucessos, {failed_exports} falhas")

    return successful_exports, failed_exports


async def get_chat_entity_safe(client: TelegramClient, chat_info: Dict):
    """
    Safely get chat entity with multiple fallback methods

    Args:
        client: Telegram client
        chat_info: Chat information dictionary

    Returns:
        Chat entity or None if failed
    """
    entity = None
    chat_title = chat_info.get("title", "Unknown")

    logger.info(f"Tentando acessar chat: {chat_title}")
    print(f"🔍 Tentando acessar chat: {chat_title}")

    # Method 1: Try username first (most reliable for public chats)
    if chat_info.get("username"):
        try:
            logger.debug(f"Tentativa 1: Username @{chat_info['username']}")
            print(f"   📝 Tentativa 1: Username @{chat_info['username']}")
            entity = await client.get_entity(chat_info["username"])
            logger.info("Sucesso via username")
            print(f"   ✅ Sucesso via username")
            return entity
        except Exception as e:
            logger.debug(f"Falha via username: {e}")
            print(f"   ❌ Falha via username: {e}")

    # Method 2: Try by ID
    if chat_info.get("id") and chat_info["id"] != 0:
        try:
            logger.debug(f"Tentativa 2: ID {chat_info['id']}")
            print(f"   🆔 Tentativa 2: ID {chat_info['id']}")
            entity = await client.get_entity(chat_info["id"])
            logger.info("Sucesso via ID")
            print(f"   ✅ Sucesso via ID")
            return entity
        except Exception as e:
            logger.debug(f"Falha via ID: {e}")
            print(f"   ❌ Falha via ID: {e}")

    # Method 3: Try with access_hash if available
    if chat_info.get("access_hash"):
        try:
            logger.debug("Tentativa 3: ID + access_hash")
            print(f"   🔑 Tentativa 3: ID + access_hash")
            from telethon.tl.types import PeerChannel, PeerChat, PeerUser

            chat_id = chat_info["id"]
            if chat_id < 0:
                if str(chat_id).startswith("-100"):
                    # Channel/Supergroup
                    peer = PeerChannel(int(str(chat_id)[4:]))
                else:
                    # Legacy group
                    peer = PeerChat(-chat_id)
            else:
                # User
                peer = PeerUser(chat_id)

            entity = await client.get_entity(peer)
            logger.info("Sucesso via access_hash")
            print(f"   ✅ Sucesso via access_hash")
            return entity
        except Exception as e:
            logger.debug(f"Falha via access_hash: {e}")
            print(f"   ❌ Falha via access_hash: {e}")

    # Method 4: Try resolving username without @ prefix
    if chat_info.get("username"):
        try:
            username_clean = chat_info["username"].lstrip("@")
            logger.debug(f"Tentativa 4: Username limpo '{username_clean}'")
            print(f"   📝 Tentativa 4: Username limpo '{username_clean}'")
            entity = await client.get_entity(username_clean)
            logger.info("Sucesso via username limpo")
            print(f"   ✅ Sucesso via username limpo")
            return entity
        except Exception as e:
            logger.debug(f"Falha via username limpo: {e}")
            print(f"   ❌ Falha via username limpo: {e}")

    logger.warning(f"Todas as tentativas falharam para: {chat_title}")
    print(f"   ❌ Todas as tentativas falharam para: {chat_title}")
    return None


async def validate_chat_access(client: TelegramClient, entity) -> bool:
    """
    Validate if we have read access to a chat

    Args:
        client: Telegram client
        entity: Chat entity

    Returns:
        True if access is available, False otherwise
    """
    try:
        async for _ in client.iter_messages(entity, limit=1):
            return True
    except:
        return False

    return False
