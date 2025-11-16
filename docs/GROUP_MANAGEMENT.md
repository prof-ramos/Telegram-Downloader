# 🔧 Group Management - Gerenciamento Avançado de Grupos

Documentação completa das funcionalidades de gerenciamento de grupos do Telegram Media Downloader.

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [CLI Interativo](#cli-interativo)
3. [API REST Endpoints](#api-rest-endpoints)
4. [Funcionalidades](#funcionalidades)
5. [Exemplos de Uso](#exemplos-de-uso)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O módulo de Group Management adiciona funcionalidades avançadas para:

- ✅ **Listar grupos** - Filtrar e exportar apenas grupos (exclui canais e chats privados)
- ✅ **Sair de grupos** - Sair de um ou múltiplos grupos de forma automatizada
- ✅ **Exportar conteúdo completo** - Backup completo: mensagens, mídias, metadados e participantes
- ✅ **Encaminhar conversas** - Forward de mensagens entre chats (com atribuição)
- ✅ **Copiar conversas** - Cópia de mensagens sem forward (sem atribuição)

---

## 🖥️ CLI Interativo

### Executar o Group Manager CLI

```bash
python group_manager_cli.py
```

### Menu Principal

```
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

MENU PRINCIPAL
==============================================================
1. 📋 Listar meus grupos
2. 🚪 Sair de um grupo
3. 🚪 Sair de múltiplos grupos
4. 📦 Exportar conteúdo completo de um grupo
5. 📨 Encaminhar conversas entre chats
6. 📋 Copiar conversas entre chats
0. ❌ Sair
```

---

## 🌐 API REST Endpoints

### Base URL

```
http://localhost:8000
```

### 1. Listar Grupos

**GET** `/groups/list`

Lista apenas grupos (exclui canais e chats privados).

**Response:**
```json
{
  "count": 15,
  "groups": [
    {
      "id": -1001234567890,
      "title": "Meu Grupo",
      "username": "meu_grupo",
      "type": "Supergroup",
      "participants_count": 150,
      "is_forum": false,
      "creator": true,
      "admin_rights": true
    }
  ]
}
```

### 2. Sair de um Grupo

**POST** `/groups/leave`

Sai de um grupo específico.

**Request Body:**
```json
{
  "group_id": -1001234567890,
  "confirm": false
}
```

**Response:**
```json
{
  "success": true,
  "group_id": -1001234567890
}
```

### 3. Sair de Múltiplos Grupos

**POST** `/groups/leave-multiple`

Sai de vários grupos de uma vez.

**Request Body:**
```json
{
  "group_ids": [-1001234567890, -1009876543210],
  "confirm_each": false
}
```

**Response:**
```json
{
  "successful": 2,
  "failed": 0
}
```

### 4. Exportar Conteúdo Completo

**POST** `/groups/export-content`

Exporta todo o conteúdo de um grupo.

**Request Body:**
```json
{
  "group_id": -1001234567890,
  "include_media": true,
  "include_messages": true,
  "limit": null
}
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "group_name": "Meu Grupo",
    "messages_exported": 1500,
    "media_downloaded": 450,
    "export_directory": "exports/full_exports/Meu_Grupo_-1001234567890"
  }
}
```

### 5. Encaminhar Conversas

**POST** `/conversations/forward`

Encaminha mensagens entre chats (com atribuição "Forwarded from").

**Request Body:**
```json
{
  "source_chat_id": -1001234567890,
  "destination_chat_id": -1009876543210,
  "message_ids": null,
  "limit": 100,
  "filter_text": "importante"
}
```

**Response:**
```json
{
  "success": true,
  "messages_forwarded": 75
}
```

### 6. Copiar Conversas

**POST** `/conversations/copy`

Copia mensagens entre chats (sem forward, como se fossem novas).

**Request Body:**
```json
{
  "source_chat_id": -1001234567890,
  "destination_chat_id": -1009876543210,
  "limit": 100,
  "copy_media": true
}
```

**Response:**
```json
{
  "success": true,
  "messages_copied": 98
}
```

---

## 🚀 Funcionalidades

### 1. 📋 Listar Grupos

Exporta uma lista completa de grupos que você participa, incluindo:

- **Informações básicas:** ID, título, username
- **Estatísticas:** Número de participantes
- **Permissões:** Se você é criador ou admin
- **Tipo:** Grupo normal ou Supergrupo
- **Forum:** Se o grupo tem tópicos ativados

**Saída:**
- Arquivo JSON: `exports/groups_list.json`
- Resumo no console com estatísticas

### 2. 🚪 Sair de Grupos

Permite sair de grupos de forma automatizada:

**Opções:**
- **Sair de um grupo:** Com confirmação individual
- **Sair de múltiplos grupos:** Seleção por intervalo (ex: 1-5) ou lista (ex: 1,3,5,8)
- **Confirmação:** Opcional para evitar saídas acidentais

**Segurança:**
- Sempre solicita confirmação antes de sair
- Logs detalhados de todas as operações
- Retry automático em caso de erros de rede

### 3. 📦 Exportar Conteúdo Completo

Realiza backup completo de um grupo:

**O que é exportado:**
- ✅ **Mensagens:** Texto completo com metadados
- ✅ **Mídias:** Fotos, vídeos, documentos, áudios
- ✅ **Participantes:** Lista completa de membros (se acessível)
- ✅ **Metadados:** Informações do grupo (criação, tipo, etc)

**Estrutura de saída:**
```
exports/full_exports/NomeDoGrupo_ID/
├── metadata.json           # Informações do grupo
├── messages.json           # Todas as mensagens
├── participants.json       # Lista de participantes
└── media/                  # Arquivos de mídia
    ├── msg_123_20250114_120000.jpg
    ├── msg_124_20250114_120005.mp4
    └── ...
```

**Opções:**
- `include_media`: Baixar ou não arquivos de mídia
- `include_messages`: Exportar ou não textos das mensagens
- `limit`: Limitar número de mensagens (None = todas)

### 4. 📨 Encaminhar Conversas

Encaminha mensagens de um chat para outro (mantém atribuição original).

**Características:**
- ✅ Mantém "Forwarded from [Nome]"
- ✅ Forward em lote (até 100 por vez)
- ✅ Rate limiting automático
- ✅ Filtro por texto (opcional)
- ✅ Seleção de mensagens específicas ou por limite

**Casos de uso:**
- Compartilhar conversas importantes
- Consolidar informações de múltiplos grupos
- Arquivar discussões em grupo de backup

### 5. 📋 Copiar Conversas

Copia mensagens sem atribuição de forward (como mensagens novas).

**Características:**
- ✅ Sem "Forwarded from"
- ✅ Mensagens aparecem como novas
- ✅ Opção de copiar mídias junto
- ✅ Útil para duplicar conteúdo entre chats pessoais

**Diferença do Forward:**
| Forward | Copy |
|---------|------|
| Com atribuição | Sem atribuição |
| Mais rápido (batch) | Mais lento (1 por 1) |
| Mantém contexto original | Parece novo |
| Até 100/request | 1/request |

---

## 📚 Exemplos de Uso

### Exemplo 1: Listar e Sair de Grupos Inativos

#### Via CLI:

```python
# 1. Executar CLI
python group_manager_cli.py

# 2. Escolher opção 1 (Listar grupos)
# 3. Identificar grupos inativos
# 4. Escolher opção 3 (Sair de múltiplos)
# 5. Selecionar: 1,3-5,8
```

#### Via API:

```bash
# 1. Listar grupos
curl -X GET http://localhost:8000/groups/list

# 2. Sair de múltiplos grupos
curl -X POST http://localhost:8000/groups/leave-multiple \
  -H "Content-Type: application/json" \
  -d '{
    "group_ids": [-1001234567890, -1009876543210],
    "confirm_each": false
  }'
```

### Exemplo 2: Backup Completo de um Grupo

#### Via Python:

```python
from telethon import TelegramClient
from group_management import export_all_group_content

client = TelegramClient('session', api_id, api_hash)

async with client:
    stats = await export_all_group_content(
        client,
        group_id=-1001234567890,
        include_media=True,
        include_messages=True,
        limit=None  # Todas as mensagens
    )

    print(f"Exportados: {stats['messages_exported']} mensagens")
    print(f"Baixados: {stats['media_downloaded']} arquivos")
```

### Exemplo 3: Forward com Filtro de Texto

#### Via Python:

```python
from group_management import forward_conversation

# Encaminhar apenas mensagens com palavra "urgente"
count = await forward_conversation(
    client,
    source_chat_id=-1001234567890,
    destination_chat_id=-1009876543210,
    limit=500,
    filter_text="urgente"
)

print(f"{count} mensagens encaminhadas")
```

### Exemplo 4: Cópia de Conversa Privada

```python
from group_management import copy_conversation

# Copiar últimas 50 mensagens sem atribuição
count = await copy_conversation(
    client,
    source_chat_id=123456789,  # Chat privado
    destination_chat_id=987654321,  # Saved Messages
    limit=50,
    copy_media=True
)
```

---

## 🐛 Troubleshooting

### Erro: "ChatAdminRequiredError"

**Problema:** Não tem permissão para acessar participantes do grupo.

**Solução:** Normal em grupos onde você não é admin. A exportação continua sem lista de participantes.

### Erro: "FloodWaitError"

**Problema:** Muitas operações em pouco tempo.

**Solução:** O sistema possui rate limiting automático. Aguarde o tempo indicado.

### Erro: "PeerIdInvalidError"

**Problema:** ID do chat inválido ou você não tem acesso.

**Solução:**
1. Verifique se o ID está correto
2. Certifique-se que você está no chat/grupo
3. Use `export_chat_list()` para ver IDs válidos

### Arquivo de log não encontrado

**Problema:** Grupo foi excluído ou você saiu.

**Solução:** Use `export_groups_only()` para atualizar lista de grupos.

### Forward não funciona

**Problema:** Pode ser um canal privado ou chat restrito.

**Solução:** Use `copy_conversation()` ao invés de `forward_conversation()`.

---

## ⚠️ Avisos Importantes

### Limites do Telegram

- **Forward:** Máximo 100 mensagens por request
- **Export:** Sem limite teórico, mas pode levar tempo
- **Leave:** Rate limit de ~20 grupos por minuto

### Permissões Necessárias

- Para listar participantes: Admin ou grupo público
- Para forward/copy: Permissão de leitura no chat origem
- Para sair: Membro do grupo

### Uso Responsável

⚠️ **NÃO use para:**
- Spam ou flood
- Violação de privacidade
- Compartilhamento não autorizado
- Ações maliciosas

✅ **Use para:**
- Backups pessoais
- Organização de informações
- Limpeza de grupos inativos
- Migração de dados autorizada

---

## 📊 Logging e Monitoramento

Todos os logs são salvos em:

```
logs/
├── telegram_downloader.log         # Log geral
├── telegram_downloader_errors.log  # Apenas erros
└── telegram_downloader_YYYYMMDD.log # Log diário
```

**Níveis de log:**
- **DEBUG:** Operações detalhadas
- **INFO:** Operações principais
- **WARNING:** Avisos (ex: FloodWait)
- **ERROR:** Erros capturados
- **CRITICAL:** Erros fatais

---

## 🔄 Atualizações Futuras

Planejado para próximas versões:

- [ ] Exportação agendada (cron)
- [ ] Filtros avançados (data, sender, tipo)
- [ ] Compressão automática de exports
- [ ] Dashboard web para gerenciamento
- [ ] Notificações de novos membros/saídas
- [ ] Auto-moderação básica

---

## 📞 Suporte

Para problemas ou dúvidas:

1. Verifique os [logs](#logging-e-monitoramento)
2. Consulte [Troubleshooting](#troubleshooting)
3. Abra uma issue no GitHub

---

**Desenvolvido com ❤️ para gerenciamento eficiente de grupos Telegram**
