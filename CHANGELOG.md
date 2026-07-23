# Changelog — PromoWatcher

Todas as mudanças relevantes do projeto são registradas aqui, em
português, por etapa de evolução (ver
[docs/ESCOPO_MVP1.md](docs/ESCOPO_MVP1.md)).

## v2 — Central Inteligente de Produtos

Reescrita do frontend (API + site novo) e evolução do catálogo:
promoções deixam de ser eventos soltos e passam a convergir em perfis de
produto centralizados, com histórico de preço, detecção automática de
"bug" por desvio, cupons soltos numa seção própria, favoritos, alertas
por produto (além da whitelist global já existente) e administração
(bloqueio/mesclagem de produtos, fila de revisão de matching). Ver
[docs/ARQUITETURA.md](docs/ARQUITETURA.md) para o desenho completo.

### Bloco 15 — Orquestração e documentação
- `run_app.py` agora sobe watcher + API (FastAPI/uvicorn) + frontend web
  (Vite) juntos, com `taskkill /T` no Windows para encerrar a árvore de
  processos do `npm`/`node` por inteiro no `Ctrl+C`; a interface
  Streamlit sai da orquestração padrão e vira ferramenta de debug pontual.
- Atualiza `README.md`, `docs/ARQUITETURA.md` e
  `docs/SEGURANCA_E_BACKUPS.md` para refletir o sistema v2 completo
  (instalação do frontend, Ollama opcional, novo comando de backup que
  exclui `web/node_modules` corretamente).

### Bloco 14 — Frontend: Favoritos, Cupons e Admin
- Páginas `Favoritos` (grid de produtos favoritados, sem notificação),
  `Cupons` (`CouponCard` com código, desconto, loja e validade) e
  `Admin` (tabela de produtos com bloqueio/mesclagem, fila de revisão de
  matching com resolução manual em três ações: atribuir, criar novo,
  ignorar).
- Página `Alertas` migrada para CRUD completo via API, substituindo a
  edição direta de `alerts.json`.

### Bloco 13 — Frontend: Perfil de produto
- Página de perfil com gráfico de histórico de preço (`recharts`,
  janelas 30/60/90 dias), comparação de lojas já vistas e ações de
  favoritar/alertar.

### Bloco 12 — Frontend: Feed
- Grid de cards de produto com dados reais da API, filtro por categoria.

### Bloco 11 — Scaffold do frontend
- Novo app em `web/` (Vite + React + TypeScript), tema escuro/
  monoespaçado via variáveis CSS, proxy de dev (`/api` → `localhost:8000`)
  para evitar CORS em desenvolvimento.

### Bloco 10 — API: alertas globais e estático
- CRUD de `alerts.json` via API (paridade com a edição direta); mount
  condicional de `web/dist` (build de produção) no FastAPI.

### Bloco 9 — API: escrita
- Endpoints de favoritar, alerta por produto, bloquear/mesclar produto e
  resolução manual da fila de matching.

### Bloco 8 — API: leitura
- FastAPI novo (`app/api/`) sobre o SQLite existente: feed, perfil de
  produto + histórico, dashboard, cupons.

### Bloco 7 — Cupons soltos
- `app/parser/coupon_signal.py` classifica mensagens sem produto
  associável; `app/services/coupon_service.py` cuida da dedupe própria
  (`coupons_standalone`), sem poluir `promotions`.

### Bloco 6 — IA local (Ollama) para desambiguação
- `app/products/ollama_client.py`: cliente HTTP usando o recurso nativo
  de *structured outputs* do Ollama (parâmetro `format` com JSON Schema).
- `app/products/model_eval.py`: script de avaliação comparativa de
  modelos locais candidatos (acerto de extração + latência), usado para
  escolher `OLLAMA_MATCH_MODEL` com base em dados reais, não teoria.
- `app/products/enrichment_worker.py`: processa a fila de matching
  ambíguo (`product_match_queue`) em background, integrado ao loop do
  `watch_promos.py`; nunca bloqueia o handler do Telethon; degrada para
  `NEEDS_HUMAN` se o Ollama estiver indisponível.

### Bloco 5 — Histórico de preço e bug por desvio
- `product_price_history`; `evaluate_bug_by_deviation()` marca preço
  como candidato a bug quando desvia muito da média histórica (com
  mínimo de pontos antes de ativar).

### Blocos 2-4 — Extração, matching e integração
- `app/products/spec_extractor.py`: extração determinística de marca/
  modelo/RAM/armazenamento/ano (regex + dicionário de aliases de marca).
- `app/products/matcher.py` + `product_service.py`: matching por regras
  com limiares conservadores (nunca funde marca/armazenamento
  diferentes); guard contra falsa similaridade entre códigos de modelo
  sequenciais (ex.: "g54" vs "g55").
- Integração no `message_processor.py`: toda promoção aprovada passa a
  tentar casar/criar um perfil de produto.

### Bloco 0-1 — Migrador e schema estendido
- `app/migrations.py`: migrador idempotente (SQLite não suporta
  `ADD COLUMN IF NOT EXISTS`) + `PRAGMA busy_timeout=5000` para reduzir
  contenção entre watcher e API escrevendo no mesmo banco.
- Schema estendido com 9 tabelas novas (`products`, `product_specs`,
  `product_price_history`, `product_images`, `favorites`,
  `product_alerts`, `coupons_standalone`, `product_match_queue`,
  `product_merges`) sem alterar as 5 tabelas originais do MVP1; catálogo
  de produtos começa do zero (sem backfill retroativo das mensagens
  antigas).

## MVP1 — Central Inteligente de Promoções

### Etapa 9 — Testes finais e documentação
- Remove `keywords.txt` (paridade já garantida por `alerts.json`).
- Cria `requirements-dev.txt` (dependências de desenvolvimento/teste).
- Atualiza `.env.example` (remove variáveis obsoletas `KEYWORDS_FILE`,
  `COOLDOWN_SECONDS`, `DEDUP_WINDOW`; adiciona `ALERTS_FILE`, `DB_PATH`,
  `LINK_RESOLVE_TIMEOUT`).
- Adiciona `README.md`, `CHANGELOG.md` e `docs/` (arquitetura,
  segurança/backups, alertas, escopo).

### Etapas 7-8 — Pipeline, interface Streamlit e integração
- Adiciona `app/services/message_processor.py`: orquestra o pipeline
  completo (raw message → parser → link resolver → alertas → score →
  deduplicação → banco → decisão de notificar).
- Adiciona `app/services/promotion_service.py` e
  `app/services/notification_service.py` (mensagem de notificação com
  score, origem, repetições e motivo).
- Adiciona interface Streamlit (`app/ui/streamlit_app.py`, `run_ui.py`)
  com abas Dashboard, Alertas, Promoções e Mensagens Telegram.
- Refatora `watch_promos.py` para usar o pipeline novo, mantendo o
  fluxo de login/autenticação Telethon intacto. Remove
  `load_keywords`/`match_keywords`; `alerts.json` passa a ser a fonte
  de alertas, sincronizada com a tabela `alerts` do banco.
- Corrige bugs encontrados em teste manual real: conexão SQLite
  compartilhada entre threads, timeout de resolução de link nunca
  repassado, filtro de data do dashboard incompatível com o formato do
  SQLite, e remove exposição do canal de destino (`NOTIFY_CHAT`) nos
  logs.
- Validado com sessão Telegram real: pipeline completo + envio real ao
  canal de destino configurado; watcher e interface rodando em
  paralelo sem conflito de escrita no SQLite (modo WAL).

### Etapas 4-6 — Link resolver, alertas estruturados e deduplicação
- Adiciona `app/parser/link_resolver.py`: limpeza de parâmetros de
  afiliado/rastreamento, resolução de redirecionamentos com timeout
  curto e fallback obrigatório (nunca descarta uma promoção por falha
  de link).
- Cria `alerts.json` migrando a regra "bug" com paridade ao
  `keywords.txt` original.
- Adiciona `app/rules/alert_matcher.py` (termos obrigatórios/opcionais/
  bloqueados, tolerante a acentos e hífens) e `app/rules/score.py`
  (pontuação explicável com motivo textual).
- Adiciona `app/rules/deduplicator.py` com hierarquia de deduplicação:
  `clean_url` → `resolved_url` → domínio+path → título+preço.

### Etapas 1-3 — Preparação, banco SQLite e parser
- Revisa `.gitignore` para cobrir `.env`, sessões do Telethon, banco
  local, backups, logs e exports.
- Cria a estrutura `app/` (config, models, database, parser, rules,
  services, ui).
- Adiciona schema SQLite (`raw_messages`, `promotions`, `alerts`,
  `promotion_occurrences`, `notifications`) e camada `database.py`.
- Adiciona parser de texto/preço/link (`normalizer`, `price_parser`,
  `link_extractor`, `text_parser`).

## Antes do MVP1

- Script único (`watch_promos.py`) monitorando Telegram via Telethon,
  filtro por palavras-chave (`keywords.txt`), deduplicação em memória
  (perdida a cada reinício), envio ao chat de destino e opcionalmente
  por e-mail.
