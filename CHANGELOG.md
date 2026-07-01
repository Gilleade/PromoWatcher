# Changelog — PromoWatcher

Todas as mudanças relevantes do projeto são registradas aqui, em
português, por etapa de evolução (ver
[docs/ESCOPO_MVP1.md](docs/ESCOPO_MVP1.md)).

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
