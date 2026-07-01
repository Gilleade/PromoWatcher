# Arquitetura — PromoWatcher MVP1

## Estrutura de pastas

```text
PromoWatcher/
├── app/
│   ├── config.py              # carrega .env e expõe Config
│   ├── database.py            # SQLite (sqlite3 stdlib, sem ORM)
│   ├── models.py               # dataclasses (RawMessage, Promotion, AlertDef, ...)
│   ├── schema.sql              # DDL das 5 tabelas
│   ├── telegram_client.py      # factory do TelegramClient (Telethon)
│   ├── telegram_notifier.py    # reservado (notificação usa o client já autenticado)
│   ├── parser/
│   │   ├── normalizer.py       # normalização de texto (acentos, espaços, hífens)
│   │   ├── price_parser.py     # extração de preço/cupom em formato BR
│   │   ├── link_extractor.py   # extração de URLs do texto
│   │   ├── link_resolver.py    # limpeza + resolução de links, com fallback
│   │   └── text_parser.py      # orquestra os parsers acima
│   ├── rules/
│   │   ├── alert_matcher.py    # aplica alerts.json (required/any/exclude)
│   │   ├── score.py            # pontuação explicável
│   │   └── deduplicator.py     # chave de deduplicação hierárquica
│   ├── services/
│   │   ├── message_processor.py    # pipeline completo (orquestrador)
│   │   ├── promotion_service.py    # consultas para a interface
│   │   └── notification_service.py # monta o texto de notificação
│   └── ui/
│       └── streamlit_app.py    # Dashboard, Alertas, Promoções, Mensagens
├── data/                        # banco SQLite local (ignorado pelo Git)
├── logs/                        # logs locais (ignorado pelo Git)
├── backups/                     # backups locais (ignorado pelo Git)
├── alerts.json                  # alertas estruturados (fonte da verdade)
├── watch_promos.py               # entrypoint do watcher (Telethon)
├── run_ui.py                     # entrypoint da interface (Streamlit)
└── tests/                        # testes pytest
```

## Pipeline de processamento

```text
Nova mensagem do Telegram (events.NewMessage)
↓
watch_promos.handler(): monta dados brutos do evento
↓
ThreadPoolExecutor: abre conexão SQLite própria da worker thread
↓
message_processor.process():
    1. insert_raw_message()               — salva a mensagem bruta
    2. text_parser.parse_message()         — extrai título/preço/cupom/links/normaliza
    3. link_resolver.resolve_links()       — limpa e resolve, com fallback garantido
    4. deduplicator.compute_dedupe_key()   — clean_url > resolved_url > domínio+path > título+preço
    5. Se já existe promoção com essa chave:
           insert_occurrence()             — registra ocorrência, NÃO notifica de novo
       Senão:
           alert_matcher.match_alerts()    — aplica alerts.json
           score.compute_score()           — pontua e explica o motivo
           insert_promotion()              — grava a promoção (APPROVED ou IGNORED)
↓
Se APPROVED e alerta pede notificação:
    notification_service.build_notification_text()
    client.send_message(NOTIFY_DEST, texto)
    insert_notification()
↓
Interface Streamlit lê o mesmo banco (modo WAL) e exibe tudo
```

## Por que SQLite puro (sem ORM)

O escopo tem 5 tabelas com relações simples e não há migrations
complexas previstas para o MVP1. `sqlite3` da biblioteca padrão com
schema SQL explícito (`app/schema.sql`) evita uma dependência nova,
facilita testes com banco `:memory:` e mantém a filosofia de script
simples do projeto original.

## Concorrência: watcher + interface no mesmo banco

O banco é aberto com `PRAGMA journal_mode = WAL`, permitindo que o
watcher (escrita) e a interface Streamlit (leitura) operem ao mesmo
tempo sem bloqueio, desde que cada processo/thread abra sua **própria**
conexão SQLite (nunca compartilhando um objeto `Connection` entre
threads — isso já causou um bug real corrigido durante o
desenvolvimento, ver `CHANGELOG.md`).

## Resolução de links sem travar o Telethon

`link_resolver.resolve_url_sync()` usa `requests` de forma síncrona,
mas é sempre chamado a partir de uma worker thread via
`loop.run_in_executor(...)`, para não bloquear o loop de eventos do
Telethon. Timeout curto e captura de exceções garantem que uma falha
de rede nunca derruba o handler nem descarta a promoção (fallback
obrigatório).
