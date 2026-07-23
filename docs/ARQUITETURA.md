# Arquitetura — PromoWatcher v2 (Central Inteligente de Produtos)

## Estrutura de pastas

```text
PromoWatcher/
├── app/
│   ├── config.py              # carrega .env e expõe Config
│   ├── database.py            # SQLite (sqlite3 stdlib, sem ORM)
│   ├── models.py               # dataclasses (RawMessage, Promotion, Product, ...)
│   ├── schema.sql              # DDL de todas as tabelas
│   ├── migrations.py           # migrador idempotente (ALTER TABLE incremental)
│   ├── telegram_client.py      # factory do TelegramClient (Telethon)
│   ├── telegram_notifier.py    # reservado (notificação usa o client já autenticado)
│   ├── parser/
│   │   ├── normalizer.py       # normalização de texto (acentos, espaços, hífens)
│   │   ├── price_parser.py     # extração de preço/cupom em formato BR
│   │   ├── link_extractor.py   # extração de URLs do texto
│   │   ├── link_resolver.py    # limpeza + resolução de links, com fallback
│   │   ├── coupon_signal.py    # classifica mensagem como produto vs. cupom solto
│   │   └── text_parser.py      # orquestra os parsers acima
│   ├── rules/
│   │   ├── alert_matcher.py    # aplica alerts.json (whitelist global: required/any/exclude)
│   │   ├── score.py            # pontuação explicável
│   │   └── deduplicator.py     # chave de deduplicação hierárquica
│   ├── products/                # catálogo de produtos centralizado (ver seção própria)
│   │   ├── spec_extractor.py   # extração determinística de marca/modelo/specs
│   │   ├── matcher.py          # matching por regras + limiares conservadores
│   │   ├── product_service.py  # get_or_create_product, histórico de preço, favoritos, bloqueio, merge
│   │   ├── catalog_service.py  # consultas de leitura (feed, perfil, dashboard) para a API
│   │   ├── ollama_client.py    # cliente HTTP do Ollama (structured outputs)
│   │   ├── model_eval.py       # script de avaliação comparativa de modelos locais
│   │   └── enrichment_worker.py # processa a fila de matching ambíguo em background
│   ├── services/
│   │   ├── message_processor.py    # pipeline completo (orquestrador)
│   │   ├── coupon_service.py       # cupons soltos (sem produto associável)
│   │   ├── promotion_service.py    # consultas para a interface Streamlit legada
│   │   └── notification_service.py # monta o texto de notificação
│   ├── api/                     # API FastAPI (backend do frontend web)
│   │   ├── main.py              # app FastAPI, CORS, mount do build estático
│   │   ├── deps.py              # conexão SQLite por request
│   │   ├── schemas.py           # modelos Pydantic de request/response
│   │   └── routers/             # feed, products, dashboard, favorites, coupons, admin, alerts
│   └── ui/
│       └── streamlit_app.py    # interface legada (debug pontual, sem investimento novo)
├── web/                          # frontend novo (Vite + React + TypeScript)
│   └── src/
│       ├── api/                 # cliente HTTP tipado
│       ├── components/          # Navbar, ProductCard, PriceHistoryChart, CouponCard, ...
│       ├── pages/                # Feed, ProductProfile, Favoritos, Cupons, Alertas, Admin
│       └── theme/                # variáveis CSS do tema escuro/monoespaçado
├── data/                        # banco SQLite local (ignorado pelo Git)
├── logs/                        # logs locais (ignorado pelo Git)
├── backups/                     # backups locais (ignorado pelo Git)
├── alerts.json                  # alertas estruturados globais (fonte da verdade)
├── watch_promos.py               # entrypoint do watcher (Telethon) + worker de enriquecimento
├── run_ui.py                     # entrypoint da interface Streamlit legada
├── run_app.py                    # sobe watcher + API + frontend web juntos
└── tests/                        # testes pytest (backend) — frontend usa `tsc -b`
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
    4. coupon_signal.classify_message_kind() — mensagem é PRODUCT ou COUPON?
       Se COUPON: coupon_service.process_coupon_message() e para aqui
       (não vira promotion nem passa por matching de produto)
    5. deduplicator.compute_dedupe_key()   — clean_url > resolved_url > domínio+path > título+preço
    6. Se já existe promoção com essa chave:
           insert_occurrence()             — registra ocorrência, NÃO notifica de novo
       Senão:
           alert_matcher.match_alerts()    — aplica alerts.json (whitelist global)
           score.compute_score()           — pontua e explica o motivo
           product_service.get_or_create_product() — casa/cria o perfil de produto (ver abaixo)
           product_service.record_price_point()    — histórico de preço + candidato a "bug" por desvio
           insert_promotion()              — grava a promoção (APPROVED ou IGNORED)
↓
Se APPROVED e (alerta global pede notificação OU produto tem alerta próprio ativo):
    notification_service.build_notification_text()
    client.send_message(NOTIFY_DEST, texto)
    insert_notification()
↓
watch_promos.py roda em paralelo, no mesmo loop do Telethon:
    enrichment_worker_loop() — processa product_match_queue um item por vez,
    chamando o Ollama para os casos ambíguos (nunca bloqueia o handler)
↓
API FastAPI (app/api/) e frontend web (web/) leem o mesmo banco (modo WAL)
```

## Matching de produtos

O problema central do v2: convergir a mesma promoção postada em grupos
diferentes para um único perfil de produto (`products`), sem nunca
misturar variantes diferentes (ex.: 128GB vs 256GB de armazenamento).
Três camadas, cada uma um fallback da anterior:

1. **Extração determinística** (`spec_extractor.py`): regex + dicionário
   de aliases de marca extraem marca/modelo/RAM/armazenamento/ano do
   texto da mensagem, sem depender de IA.
2. **Matcher por regras** (`matcher.py`): match exato por `variant_key`
   (marca+modelo+armazenamento+RAM); senão, pontuação por similaridade
   com limiares conservadores — `AUTO_MATCH_THRESHOLD=0.85` funde
   automaticamente, `NEEDS_REVIEW_THRESHOLD=0.55` manda para a fila de
   revisão, abaixo disso cria produto novo. Um guard especial evita
   confundir códigos de modelo sequenciais (ex.: "g54" vs "g55").
   **Nunca** funde marca ou armazenamento diferentes, mesmo com alta
   similaridade textual.
3. **Desambiguação por IA local** (`ollama_client.py` +
   `enrichment_worker.py`): só entra em jogo para os itens que caíram
   na fila de revisão (`product_match_queue`). Chama o Ollama local
   (`http://localhost:11434`) usando o recurso nativo de **structured
   outputs** (parâmetro `format` com JSON Schema), o que restringe a
   geração ao formato esperado em vez de só pedir JSON no prompt.
   Processa um item por vez, num loop assíncrono dentro do próprio
   `watch_promos.py`, para nunca bloquear o handler do Telethon. Se o
   Ollama estiver fora do ar ou a resposta não bater o schema, o item
   vira `NEEDS_HUMAN` — o catálogo continua funcionando, só com mais
   itens esperando resolução manual pela tela de Admin.

A escolha do modelo local (`OLLAMA_MATCH_MODEL` no `.env`) foi feita por
avaliação prática, não teórica: `app/products/model_eval.py` roda um
conjunto de casos de teste reais contra os modelos candidatos instalados
e imprime acerto/latência de cada um — trocar de modelo é só baixar outro
no Ollama e apontar a variável de ambiente para ele.

Resolução manual de um item da fila (tela de Admin) sempre tem três
saídas: atribuir a um produto existente, criar um produto novo, ou
ignorar — nunca uma mesclagem automática sem confirmação.

## Cupons soltos

Mensagens com sinal de desconto/cupom mas sem produto associável (ex.:
"R$20 OFF em qualquer compra", ao estilo Pelando) são desviadas antes do
pipeline de matching de produto — `coupon_signal.classify_message_kind()`
decide `PRODUCT` vs `COUPON`, e `coupon_service.py` cuida da própria
dedupe (`coupons_standalone`), sem poluir a tabela `promotions` nem o
catálogo de produtos.

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
