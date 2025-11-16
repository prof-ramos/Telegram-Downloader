"""
Interactive CLI for Group Management
Provides a user-friendly interface for managing Telegram groups
"""

import asyncio
import sys
from typing import List, Dict

from telethon_handlers import login_with_qr
from group_management import (
    export_groups_only,
    leave_group,
    leave_multiple_groups,
    export_all_group_content,
    forward_conversation,
    copy_conversation
)
from logger import setup_logger, get_logger

# Setup logger
setup_logger(console_level="INFO", file_level="DEBUG")
logger = get_logger("group_manager_cli")


def print_banner():
    """Display application banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           TELEGRAM GROUP MANAGER - Interactive CLI          ║
║                           v1.0                               ║
╠══════════════════════════════════════════════════════════════╣
║  🔹 Listar grupos                                            ║
║  🔹 Sair de grupos                                           ║
║  🔹 Exportar conteúdo completo                               ║
║  🔹 Encaminhar conversas                                     ║
║  🔹 Copiar conversas                                         ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_main_menu():
    """Display main menu"""
    print("\n" + "=" * 60)
    print("MENU PRINCIPAL")
    print("=" * 60)
    print("1. 📋 Listar meus grupos")
    print("2. 🚪 Sair de um grupo")
    print("3. 🚪 Sair de múltiplos grupos")
    print("4. 📦 Exportar conteúdo completo de um grupo")
    print("5. 📨 Encaminhar conversas entre chats")
    print("6. 📋 Copiar conversas entre chats")
    print("0. ❌ Sair")
    print("=" * 60)


async def list_groups_menu(client):
    """List all groups"""
    logger.info("Menu: Listar grupos")
    print("\n📋 LISTANDO GRUPOS...")

    groups = await export_groups_only(client)

    if not groups:
        print("❌ Nenhum grupo encontrado")
        return []

    print(f"\n{'='*80}")
    print(f"{'Nº':<4} {'Título':<40} {'ID':<15} {'Membros':<10} {'Tipo':<12}")
    print(f"{'='*80}")

    for i, group in enumerate(groups, 1):
        title = group['title'][:37] + "..." if len(group['title']) > 40 else group['title']
        print(
            f"{i:<4} {title:<40} {group['id']:<15} "
            f"{group['participants_count']:<10} {group['type']:<12}"
        )

    return groups


async def leave_group_menu(client, groups: List[Dict]):
    """Leave a single group"""
    logger.info("Menu: Sair de grupo")

    if not groups:
        print("\n📋 Listando grupos primeiro...")
        groups = await list_groups_menu(client)

    if not groups:
        return

    print("\n🚪 SAIR DE GRUPO")
    selection = input("Digite o número do grupo para sair (ou 'c' para cancelar): ").strip()

    if selection.lower() == 'c':
        return

    try:
        index = int(selection) - 1
        if 0 <= index < len(groups):
            group = groups[index]
            await leave_group(client, group['id'], confirm=True)
        else:
            print("❌ Número inválido!")
    except ValueError:
        print("❌ Entrada inválida!")


async def leave_multiple_groups_menu(client, groups: List[Dict]):
    """Leave multiple groups"""
    logger.info("Menu: Sair de múltiplos grupos")

    if not groups:
        print("\n📋 Listando grupos primeiro...")
        groups = await list_groups_menu(client)

    if not groups:
        return

    print("\n🚪 SAIR DE MÚLTIPLOS GRUPOS")
    print("💡 Formatos aceitos:")
    print("   - Um grupo: 1")
    print("   - Múltiplos: 1,3,5")
    print("   - Intervalo: 1-5")
    print("   - Combinado: 1,3-5,8")

    selection = input("\nDigite os números dos grupos (ou 'c' para cancelar): ").strip()

    if selection.lower() == 'c':
        return

    try:
        indices = parse_selection(selection, len(groups))
        group_ids = [groups[i - 1]['id'] for i in indices]

        print(f"\n📌 Grupos selecionados ({len(group_ids)}):")
        for i in indices:
            print(f"   - {groups[i - 1]['title']}")

        await leave_multiple_groups(client, group_ids, confirm_each=False)

    except ValueError as e:
        print(f"❌ Erro na seleção: {e}")


async def export_group_content_menu(client, groups: List[Dict]):
    """Export all content from a group"""
    logger.info("Menu: Exportar conteúdo de grupo")

    if not groups:
        print("\n📋 Listando grupos primeiro...")
        groups = await list_groups_menu(client)

    if not groups:
        return

    print("\n📦 EXPORTAR CONTEÚDO COMPLETO DE GRUPO")
    selection = input("Digite o número do grupo (ou 'c' para cancelar): ").strip()

    if selection.lower() == 'c':
        return

    try:
        index = int(selection) - 1
        if 0 <= index < len(groups):
            group = groups[index]

            print("\n⚙️  Opções de exportação:")
            include_media = input("Incluir mídias? (S/n): ").strip().lower() != 'n'
            include_messages = input("Incluir textos de mensagens? (S/n): ").strip().lower() != 'n'

            limit_input = input("Limite de mensagens (Enter para todas): ").strip()
            limit = int(limit_input) if limit_input else None

            await export_all_group_content(
                client,
                group['id'],
                include_media=include_media,
                include_messages=include_messages,
                limit=limit
            )
        else:
            print("❌ Número inválido!")
    except ValueError:
        print("❌ Entrada inválida!")


async def forward_conversation_menu(client):
    """Forward conversation between chats"""
    logger.info("Menu: Encaminhar conversas")

    print("\n📨 ENCAMINHAR CONVERSAS")

    source_id = input("ID do chat de origem: ").strip()
    dest_id = input("ID do chat de destino: ").strip()

    try:
        source_id = int(source_id)
        dest_id = int(dest_id)

        limit_input = input("Quantas mensagens encaminhar? (padrão: 100): ").strip()
        limit = int(limit_input) if limit_input else 100

        filter_text = input("Filtrar por texto (Enter para não filtrar): ").strip()
        filter_text = filter_text if filter_text else None

        await forward_conversation(
            client,
            source_id,
            dest_id,
            limit=limit,
            filter_text=filter_text
        )

    except ValueError:
        print("❌ IDs inválidos!")


async def copy_conversation_menu(client):
    """Copy conversation between chats"""
    logger.info("Menu: Copiar conversas")

    print("\n📋 COPIAR CONVERSAS")

    source_id = input("ID do chat de origem: ").strip()
    dest_id = input("ID do chat de destino: ").strip()

    try:
        source_id = int(source_id)
        dest_id = int(dest_id)

        limit_input = input("Quantas mensagens copiar? (padrão: 100): ").strip()
        limit = int(limit_input) if limit_input else 100

        copy_media = input("Copiar mídias também? (S/n): ").strip().lower() != 'n'

        await copy_conversation(
            client,
            source_id,
            dest_id,
            limit=limit,
            copy_media=copy_media
        )

    except ValueError:
        print("❌ IDs inválidos!")


def parse_selection(selection: str, max_count: int) -> List[int]:
    """Parse user selection like '1,3-5,8'"""
    indices = set()

    for part in selection.split(","):
        part = part.strip()

        if "-" in part:
            start, end = map(int, part.split("-"))
            if start < 1 or end > max_count or start > end:
                raise ValueError(f"Intervalo inválido: {part}")
            indices.update(range(start, end + 1))
        else:
            num = int(part)
            if num < 1 or num > max_count:
                raise ValueError(f"Número fora do intervalo: {num}")
            indices.add(num)

    return sorted(list(indices))


async def main():
    """Main interactive loop"""
    logger.info("=== Iniciando Group Manager CLI ===")
    print_banner()

    # Authentication
    print("🔐 AUTENTICAÇÃO")
    client = await login_with_qr()

    if not client:
        logger.error("Falha na autenticação")
        print("❌ Falha na autenticação")
        return

    print("✅ Autenticado com sucesso!")

    # Cache for groups list
    groups_cache = []

    # Main loop
    while True:
        try:
            print_main_menu()
            choice = input("\n❓ Escolha uma opção: ").strip()

            if choice == "0":
                logger.info("Encerrando por solicitação do usuário")
                print("👋 Até logo!")
                break

            elif choice == "1":
                groups_cache = await list_groups_menu(client)

            elif choice == "2":
                await leave_group_menu(client, groups_cache)

            elif choice == "3":
                await leave_multiple_groups_menu(client, groups_cache)

            elif choice == "4":
                await export_group_content_menu(client, groups_cache)

            elif choice == "5":
                await forward_conversation_menu(client)

            elif choice == "6":
                await copy_conversation_menu(client)

            else:
                print("❌ Opção inválida!")

            input("\n⏸️  Pressione Enter para continuar...")

        except KeyboardInterrupt:
            logger.warning("Interrupção por teclado")
            print("\n\n❌ Operação interrompida")
            break

        except Exception as e:
            logger.error(f"Erro no menu: {e}", exc_info=True)
            print(f"❌ Erro: {e}")
            input("\n⏸️  Pressione Enter para continuar...")

    # Cleanup
    if client:
        await client.disconnect()
        logger.info("Cliente desconectado")
        print("🔌 Cliente desconectado")

    logger.info("=== Encerrando Group Manager CLI ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Aplicação interrompida")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        sys.exit(1)
