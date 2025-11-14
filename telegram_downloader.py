"""
Telegram Media Downloader - Main Application
Automated tool for downloading and organizing media from Telegram chats

This is the main entry point that orchestrates the entire download process
following the MVP specifications from the PRD.
"""

import asyncio
import sys
from typing import List, Dict

from config import DEFAULT_LIMIT_PER_CHAT
from telethon_handlers import login_with_qr, export_chat_list, export_all_chats_media
from logger import setup_logger, get_logger, PerformanceLogger

# Setup logger
logger = get_logger("main")


def print_banner():
    """Display application banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                  TELEGRAM MEDIA DOWNLOADER                  ║
║                         MVP v1.0                            ║
╠══════════════════════════════════════════════════════════════╣
║  📱 Login via QR Code                                        ║
║  📋 Export Chat Lists                                        ║
║  📥 Organized Media Downloads                                ║
║  📁 Forum Topics Support                                     ║
║  🔒 Private Chats Access                                     ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_usage_instructions():
    """Display usage instructions"""
    instructions = """
📖 INSTRUÇÕES DE USO:

1. Configure suas credenciais da API no arquivo config.py:
   - API_ID: Seu ID da API do Telegram
   - API_HASH: Seu hash da API do Telegram
   - Obtenha em: https://my.telegram.org/apps

2. Execute o aplicativo:
   python telegram_downloader.py

3. Escaneie o QR Code que aparecerá no terminal

4. Aguarde o processo de exportação automática

📁 ESTRUTURA DE SAÍDA:
exports/
├── chat_list.json (lista de todos os chats)
└── {ChatName}_{ChatID}/
    ├── fotos/
    ├── videos/
    ├── documentos/
    ├── audio/
    ├── mensagens_voz/
    ├── stickers/
    ├── outros/
    └── download_log.txt

Para grupos com tópicos, subdiretórios serão criados automaticamente.
    """
    print(instructions)


def display_chat_summary(chat_list: List[Dict]) -> None:
    """
    Display summary of found chats

    Args:
        chat_list: List of chat information dictionaries
    """
    if not chat_list:
        print("❌ Nenhum chat encontrado")
        return

    print(f"\n📋 RESUMO DOS CHATS ENCONTRADOS ({len(chat_list)} total):")
    print("-" * 80)

    # Group by type
    by_type = {}
    for chat in chat_list:
        chat_type = chat["type"]
        if chat_type not in by_type:
            by_type[chat_type] = []
        by_type[chat_type].append(chat)

    # Display summary by type
    for chat_type, chats in by_type.items():
        print(f"📂 {chat_type}: {len(chats)} chats")

    print("-" * 80)

    # Show first 10 chats as examples
    print("🔍 Primeiros 10 chats (exemplo):")
    for i, chat in enumerate(chat_list[:10], 1):
        forum_indicator = " 📁[FORUM]" if chat.get("is_forum") else ""
        participants = chat.get("participants_count", 0)
        print(
            f"{i:2d}. {chat['title'][:50]:<50} | {chat['type']:<10} | "
            f"{participants:>6} membros{forum_indicator}"
        )

    if len(chat_list) > 10:
        print(f"    ... e mais {len(chat_list) - 10} chats")


async def interactive_chat_selection(chat_list: List[Dict]) -> List[Dict]:
    """
    Allow user to interactively select which chats to process

    Args:
        chat_list: List of all available chats

    Returns:
        List of selected chats to process
    """
    print(f"\n🎯 SELEÇÃO DE CHATS PARA DOWNLOAD")
    print("Escolha uma das opções:")
    print("1. 📋 Selecionar da lista de chats")
    print("2. 🆔 Inserir ID específico do chat")
    print("3. 🔗 Inserir link do chat")
    print("4. 🚀 Processar primeiros 5 chats (modo automático)")

    while True:
        choice = input("\n❓ Digite sua opção (1-4): ").strip()

        if choice == "1":
            return await select_from_chat_list(chat_list)
        elif choice == "2":
            return await select_by_chat_id(chat_list)
        elif choice == "3":
            return await select_by_chat_link()
        elif choice == "4":
            return await select_auto_mode(chat_list)
        else:
            print("❌ Opção inválida! Digite 1, 2, 3 ou 4")


async def select_from_chat_list(chat_list: List[Dict]) -> List[Dict]:
    """Select chats from the exported list"""
    print(f"\n📋 LISTA DE CHATS DISPONÍVEIS ({len(chat_list)} total):")
    print("-" * 80)

    # Show numbered list
    for i, chat in enumerate(chat_list, 1):
        forum_indicator = " 📁[FORUM]" if chat.get("is_forum") else ""
        participants = chat.get("participants_count", 0)
        print(
            f"{i:3d}. {chat['title'][:60]:<60} | {chat['type']:<12} | "
            f"ID: {chat['id']:<12} | {participants:>6} membros{forum_indicator}"
        )

    print(f"\n💡 Exemplos de entrada:")
    print("  - Um chat: 1")
    print("  - Múltiplos chats: 1,3,5")
    print("  - Intervalo: 1-5")
    print("  - Combinado: 1,3-5,8")

    while True:
        selection = input(
            "\n❓ Digite os números dos chats (ou 'c' para cancelar): "
        ).strip()

        if selection.lower() == "c":
            return []

        try:
            selected_indices = parse_selection_input(selection, len(chat_list))
            selected_chats = [chat_list[i - 1] for i in selected_indices]

            print(f"\n📌 Chats selecionados ({len(selected_chats)}):")
            for chat in selected_chats:
                forum_indicator = " 📁[FORUM]" if chat.get("is_forum") else ""
                print(f"  - {chat['title']} (ID: {chat['id']}){forum_indicator}")

            confirmation = input("\n❓ Confirmar seleção? (s/N): ").lower().strip()
            if confirmation in ["s", "sim", "y", "yes"]:
                return selected_chats
            else:
                print("❌ Seleção cancelada")
                continue

        except ValueError as e:
            print(f"❌ Erro na seleção: {e}")
            continue


async def select_by_chat_id(chat_list: List[Dict]) -> List[Dict]:
    """Select chat by specific ID"""
    print(f"\n🆔 SELEÇÃO POR ID DO CHAT")
    print("💡 Você pode inserir um ou múltiplos IDs separados por vírgula")

    while True:
        ids_input = input(
            "\n❓ Digite o(s) ID(s) do(s) chat(s) (ou 'c' para cancelar): "
        ).strip()

        if ids_input.lower() == "c":
            return []

        try:
            # Parse multiple IDs
            chat_ids = []
            for id_str in ids_input.split(","):
                chat_id = int(id_str.strip())
                chat_ids.append(chat_id)

            # Find chats by ID
            selected_chats = []
            for chat_id in chat_ids:
                found_chat = None
                for chat in chat_list:
                    if chat["id"] == chat_id:
                        found_chat = chat
                        break

                if found_chat:
                    selected_chats.append(found_chat)
                    print(
                        f"✅ Chat encontrado: {found_chat['title']} (ID: {found_chat['id']})"
                    )
                else:
                    # Create custom chat entry for unknown IDs
                    custom_chat = {
                        "id": chat_id,
                        "title": f"Chat_ID_{chat_id}",
                        "type": "Unknown",
                        "username": None,
                        "participants_count": 0,
                        "is_forum": False,
                    }
                    selected_chats.append(custom_chat)
                    print(
                        f"⚠️ Chat não encontrado na lista: ID {chat_id} (tentaremos acessar)"
                    )

            if selected_chats:
                confirmation = (
                    input(
                        f"\n❓ Confirmar download de {len(selected_chats)} chat(s)? (s/N): "
                    )
                    .lower()
                    .strip()
                )
                if confirmation in ["s", "sim", "y", "yes"]:
                    return selected_chats
                else:
                    continue
            else:
                print("❌ Nenhum chat válido encontrado")
                continue

        except ValueError:
            print("❌ IDs inválidos! Use apenas números separados por vírgula")
            continue


async def select_by_chat_link() -> List[Dict]:
    """Select chat by Telegram link"""
    print(f"\n🔗 SELEÇÃO POR LINK DO CHAT")
    print("💡 Formatos aceitos:")
    print("  - https://t.me/username")
    print("  - https://t.me/c/1234567890/1")
    print("  - @username")
    print("  - Múltiplos links separados por vírgula")

    while True:
        links_input = input(
            "\n❓ Digite o(s) link(s) ou username(s) (ou 'c' para cancelar): "
        ).strip()

        if links_input.lower() == "c":
            return []

        selected_chats = []

        for link_str in links_input.split(","):
            link = link_str.strip()

            # Parse different link formats
            username = None
            chat_id = None

            if link.startswith("https://t.me/c/"):
                # Private chat link: https://t.me/c/1234567890/1
                try:
                    parts = link.split("/")
                    chat_id = int(parts[4])
                    # Convert to proper chat ID format
                    chat_id = int(f"-100{chat_id}")
                except:
                    print(f"❌ Link inválido: {link}")
                    continue

            elif link.startswith("https://t.me/"):
                # Public chat link: https://t.me/username
                username = link.split("/")[-1]

            elif link.startswith("@"):
                # Username format: @username
                username = link[1:]

            else:
                # Assume it's a username
                username = link

            # Create chat entry
            if chat_id:
                custom_chat = {
                    "id": chat_id,
                    "title": f"Chat_Link_{abs(chat_id)}",
                    "type": "Channel",
                    "username": None,
                    "participants_count": 0,
                    "is_forum": False,
                    "access_hash": None,
                }
            elif username:
                custom_chat = {
                    "id": 0,  # Will be resolved later
                    "title": f"@{username}",
                    "type": "Channel",
                    "username": username,
                    "participants_count": 0,
                    "is_forum": False,
                }
            else:
                continue

            selected_chats.append(custom_chat)
            print(f"✅ Chat adicionado: {custom_chat['title']}")

        if selected_chats:
            confirmation = (
                input(
                    f"\n❓ Confirmar download de {len(selected_chats)} chat(s)? (s/N): "
                )
                .lower()
                .strip()
            )
            if confirmation in ["s", "sim", "y", "yes"]:
                return selected_chats
            else:
                continue
        else:
            print("❌ Nenhum chat válido encontrado")
            continue


async def select_auto_mode(chat_list: List[Dict]) -> List[Dict]:
    """Auto select first 5 chats"""
    selected_chats = chat_list[:5]

    print(f"\n📌 Modo automático - Primeiros 5 chats selecionados:")
    for i, chat in enumerate(selected_chats, 1):
        forum_indicator = " 📁[FORUM]" if chat.get("is_forum") else ""
        print(f"{i}. {chat['title']}{forum_indicator}")

    confirmation = input("\n❓ Continuar com estes chats? (s/N): ").lower().strip()

    if confirmation in ["s", "sim", "y", "yes"]:
        return selected_chats
    else:
        print("❌ Operação cancelada pelo usuário")
        return []


def parse_selection_input(selection: str, max_count: int) -> List[int]:
    """
    Parse user selection input like '1,3-5,8' into list of indices

    Args:
        selection: User input string
        max_count: Maximum valid number

    Returns:
        List of selected indices
    """
    indices = set()

    for part in selection.split(","):
        part = part.strip()

        if "-" in part:
            # Range like '3-5'
            try:
                start, end = map(int, part.split("-"))
                if start < 1 or end > max_count or start > end:
                    raise ValueError(f"Intervalo inválido: {part}")
                indices.update(range(start, end + 1))
            except ValueError:
                raise ValueError(f"Formato de intervalo inválido: {part}")
        else:
            # Single number
            try:
                num = int(part)
                if num < 1 or num > max_count:
                    raise ValueError(f"Número fora do intervalo: {num}")
                indices.add(num)
            except ValueError:
                raise ValueError(f"Número inválido: {part}")

    return sorted(list(indices))


async def main():
    """
    Main application function that orchestrates the entire process:
    1. QR Code Login
    2. Chat List Export
    3. Organized Media Download
    """
    logger.info("=== Iniciando Telegram Media Downloader ===")
    print_banner()

    try:
        with PerformanceLogger("Complete download process", logger):
            # Step 1: Authentication via QR Code
            logger.info("ETAPA 1: AUTENTICAÇÃO")
            print("🔐 ETAPA 1: AUTENTICAÇÃO")
            client = await login_with_qr()

            if not client:
                logger.error("Falha na autenticação")
                print("❌ Falha na autenticação. Encerrando aplicação.")
                return

            # Step 2: Export chat list
            logger.info("ETAPA 2: EXPORTAÇÃO DA LISTA DE CHATS")
            print("\n📋 ETAPA 2: EXPORTAÇÃO DA LISTA DE CHATS")
            chat_list = await export_chat_list(client)

            if not chat_list:
                logger.error("Não foi possível obter lista de chats")
                print("❌ Não foi possível obter lista de chats")
                await client.disconnect()
                return

            # Step 3: Display chat summary
            display_chat_summary(chat_list)

            # Step 4: Chat selection (for MVP, automatic selection)
            logger.info("ETAPA 3: SELEÇÃO DE CHATS")
            print("\n🎯 ETAPA 3: SELEÇÃO DE CHATS")
            selected_chats = await interactive_chat_selection(chat_list)

            if not selected_chats:
                logger.info("Nenhum chat selecionado para download")
                print("ℹ️ Nenhum chat selecionado para download")
                await client.disconnect()
                return

            # Step 5: Media download
            logger.info(f"ETAPA 4: DOWNLOAD DE MÍDIAS - {len(selected_chats)} chats selecionados")
            print("\n📥 ETAPA 4: DOWNLOAD DE MÍDIAS")
            print(f"🎯 Limite de mensagens por chat: {DEFAULT_LIMIT_PER_CHAT}")

            successful, failed = await export_all_chats_media(
                client, selected_chats, DEFAULT_LIMIT_PER_CHAT
            )

            # Final report
            logger.info(f"Processo concluído: {successful} sucessos, {failed} falhas")
            print("\n" + "=" * 60)
            print("📊 RELATÓRIO FINAL")
            print("=" * 60)
            print(f"✅ Chats processados com sucesso: {successful}")
            print(f"❌ Chats com falha: {failed}")
            print(f"📊 Total de chats tentados: {len(selected_chats)}")
            print(f"📁 Arquivos salvos no diretório: exports/")

            if successful > 0:
                logger.info("Download concluído com sucesso")
                print("\n🎉 DOWNLOAD CONCLUÍDO COM SUCESSO!")
                print("📁 Verifique o diretório 'exports/' para seus arquivos")
            else:
                logger.warning("Nenhum chat foi processado com sucesso")
                print("\n⚠️ Nenhum chat foi processado com sucesso")

    except KeyboardInterrupt:
        logger.warning("Operação interrompida pelo usuário")
        print("\n\n❌ Operação interrompida pelo usuário")

    except Exception as e:
        logger.error(f"Erro durante execução: {e}", exc_info=True)
        print(f"\n❌ Erro durante execução: {e}")
        print("💡 Dica: Verifique suas credenciais da API no arquivo config.py")

    finally:
        # Always disconnect client
        if "client" in locals() and client:
            await client.disconnect()
            logger.info("Cliente desconectado")
            print("🔌 Cliente desconectado")

        logger.info("=== Encerrando Telegram Media Downloader ===")
        print("\n👋 Obrigado por usar o Telegram Media Downloader!")


def check_configuration():
    """Check if API credentials are configured"""
    from config import API_ID, API_HASH

    if API_ID == 12345 or API_HASH == "0123456789abcdef0123456789abcdef":
        print("❌ ERRO: Credenciais da API não configuradas!")
        print("📖 Por favor, edite o arquivo config.py com suas credenciais:")
        print("   1. Vá para https://my.telegram.org/apps")
        print("   2. Crie uma nova aplicação")
        print("   3. Copie API_ID e API_HASH para config.py")
        print("   4. Execute novamente o aplicativo")
        return False

    return True


if __name__ == "__main__":
    # Setup logging system
    setup_logger(console_level="INFO", file_level="DEBUG")

    logger.info("=== Sistema de logging inicializado ===")
    print("🚀 Iniciando Telegram Media Downloader...")

    # Check configuration first
    if not check_configuration():
        logger.error("Configuração inválida")
        sys.exit(1)

    # Print usage instructions
    print_usage_instructions()

    # Confirm execution
    start_confirmation = input("❓ Deseja iniciar o processo? (s/N): ").lower().strip()

    if start_confirmation not in ["s", "sim", "y", "yes"]:
        logger.info("Operação cancelada pelo usuário")
        print("❌ Operação cancelada pelo usuário")
        sys.exit(0)

    # Run the main application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Aplicação interrompida pelo usuário")
        print("\n❌ Aplicação interrompida pelo usuário")
    except Exception as e:
        logger.critical(f"Erro fatal: {e}", exc_info=True)
        print(f"\n❌ Erro fatal: {e}")
        sys.exit(1)
