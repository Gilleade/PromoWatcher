# PromoWatcher

Central Inteligente de Promoções local: monitora grupos/canais do
Telegram, organiza as promoções em **perfis de produto centralizados**
(com histórico de preço e detecção automática de "bug" por desvio),
mantém cupons soltos separados, e expõe tudo via API + frontend web
próprio — além de alertas estruturados com pontuação explicável e
deduplicação inteligente.

## O que o PromoWatcher faz

1. Lê mensagens dos grupos/canais do Telegram configurados.
2. Salva as mensagens brutas em um banco SQLite local.
3. Extrai texto, links, preço e cupom.
4. Resolve links encurtados e remove parâmetros de afiliado/rastreamento
   (com fallback: nunca descarta uma promoção por falha ao limpar/resolver
   um link — ver [docs/ARQUITETURA.md](docs/ARQUITETURA.md)).
5. Aplica alertas estruturados (`alerts.json`, whitelist global) com
   pontuação (score) e motivo explicável para cada decisão.
6. Deduplica promoções repetidas entre diferentes grupos.
7. **Casa cada promoção a um perfil de produto** (`products`) de forma
   automática — a mesma promoção postada em grupos diferentes converge
   pro mesmo perfil; specs diferentes (ex.: 128GB vs 256GB) nunca se
   misturam. Matching determinístico (regex/regras) com reforço opcional
   de um modelo de IA local via Ollama para casos ambíguos; itens que
   nem assim resolvem caem numa fila de revisão manual. Ver
   [docs/ARQUITETURA.md](docs/ARQUITETURA.md#matching-de-produtos).
8. Registra o histórico de preço de cada produto e marca automaticamente
   como candidato a "bug" quando o preço desvia muito da média histórica.
9. Cupons sem produto associável (ex.: "R$20 OFF" genérico) viram um
   cupom solto, numa seção própria — não poluem o catálogo de produtos.
10. Permite favoritar produtos (sem notificar), criar alerta específico
    por produto, bloquear/mesclar produtos duplicados — tudo pela UI.
11. Envia ao chat/canal de destino as promoções aprovadas (alerta global
    ou alerta por produto) e não repetidas.
12. Exibe tudo — feed, perfil de produto com gráfico de preço, favoritos,
    cupons, alertas e administração — no **frontend web** (Vite + React).
    A interface Streamlit original continua disponível como ferramenta
    de depuração pontual, mas não é mais o frontend principal.

## Instalação

Pré-requisitos: Python 3.11+ (o projeto foi validado com o ambiente conda
`promowatcher` — veja `environment.yml`) e Node.js 18+ para o frontend
web.

```bash
pip install -r requirements.txt
# Para rodar os testes localmente, instale também as dependências de dev:
pip install -r requirements-dev.txt

# Frontend web (uma vez, ou sempre que as dependências mudarem):
npm install --prefix web
```

Opcional: [Ollama](https://ollama.com) rodando localmente
(`http://localhost:11434`) para reforçar o casamento automático de
produtos ambíguos com um modelo de IA local — sem Ollama, o catálogo
continua funcionando só com as regras determinísticas, e mais itens caem
na fila de revisão manual. Ver
[docs/ARQUITETURA.md](docs/ARQUITETURA.md#matching-de-produtos).

## Configuração do `.env`

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

Principais variáveis:

- `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`: credenciais do Telegram
  (https://my.telegram.org). **Nunca compartilhe ou commite esses valores.**
- `TELEGRAM_CHATS`: lista de chats a monitorar (vazio = monitora todos).
- `NOTIFY_CHAT`: chat/canal de destino das notificações aprovadas.
- `PROMO_BOT_ENABLED`, `PROMO_BOT_TOKEN`, `PROMO_BOT_CHAT_ID`: segundo destino opcional por bot dedicado. O envio atual por `NOTIFY_CHAT` continua independente.
- `ALERTS_FILE`: caminho do arquivo de alertas (padrão `alerts.json`).
- `DB_PATH`: caminho do banco SQLite (padrão `data/promowatcher.sqlite3`).
- `OLLAMA_ENABLED` / `OLLAMA_BASE_URL` / `OLLAMA_MATCH_MODEL`: IA local
  opcional para desambiguação de produtos (ver seção de instalação acima).

O `.env` e o arquivo de sessão do Telethon (`tg_promos_session.session`)
são obrigatórios para o funcionamento e ficam **fora do controle de
versão** (ver [docs/SEGURANCA_E_BACKUPS.md](docs/SEGURANCA_E_BACKUPS.md)).
Ao criar uma nova cópia/branch/worktree do projeto, copie manualmente
esses dois arquivos para o novo diretório — eles não são versionados.

## Como rodar (comando único — recomendado)

```bash
python run_app.py
```

Sobe o watcher (backend, faz o trabalho de verdade), a API (FastAPI, em
`http://localhost:8000`) e o frontend web (Vite, em
`http://localhost:5173`) juntos, em um único terminal, com logs
prefixados (`[watcher]`/`[api]`/`[web]`). Abra `http://localhost:5173`
no navegador para usar a interface. `Ctrl+C` encerra os três de forma
limpa (no Windows, a árvore de processos do `npm`/`node` é encerrada
inteira via `taskkill /T`). Se qualquer um dos três cair sozinho, os
outros são encerrados junto.

Na primeira execução (ou se a sessão expirar/for revogada), o Telethon
pedirá telefone e código de confirmação — isso é esperado e só acontece
quando a sessão salva não está mais autorizada pelo Telegram.

## Como rodar cada parte separadamente

Útil para depurar uma parte sem derrubar as outras:

```bash
python watch_promos.py                       # só o watcher
python -m uvicorn app.api.main:app --port 8000  # só a API
npm run dev --prefix web                      # só o frontend web (http://localhost:5173)
streamlit run run_ui.py                       # interface antiga (legado/debug)
```

A API e o watcher leem o mesmo banco SQLite em modo WAL, então podem
rodar em paralelo sem conflito de escrita — **mas não rode dois
watchers ao mesmo tempo** (`watch_promos.py` duas vezes, ou
`watch_promos.py` + `run_app.py`): os dois usariam o mesmo arquivo de
sessão do Telethon (`tg_promos_session.session`) simultaneamente, o que
pode causar erro de banco travado ou invalidar a sessão.

Páginas do frontend web: Feed, Perfil de produto, Favoritos, Cupons,
Alertas e Admin. Abas da interface Streamlit legada: Dashboard, Alertas,
Promoções e Mensagens Telegram.

## Como cadastrar alertas

Pela página "Alertas" do frontend web (criar, editar, ativar/desativar e
excluir — whitelist global), pela tela de perfil de um produto (alerta
específico daquele produto), ou editando `alerts.json` diretamente na
raiz do projeto. Veja o formato completo e exemplos em
[docs/ALERTAS.md](docs/ALERTAS.md). O watcher recarrega o arquivo
automaticamente quando ele é modificado (sem precisar reiniciar).

## Backups

Antes de qualquer alteração estrutural relevante, crie um backup local
em `backups/` (pasta ignorada pelo Git). Veja o padrão de nome e o
comando PowerShell recomendado em
[docs/SEGURANCA_E_BACKUPS.md](docs/SEGURANCA_E_BACKUPS.md).

## Evitando envio acidental ao GitHub

- `.env`, `*.session*`, `*.sqlite*`, `backups/`, `logs/`, `data/` e
  `exports/` já estão no `.gitignore`.
- Nunca use `git add -A`/`git add .` sem antes checar `git status`.
- Nunca rode `git push` sem confirmação explícita — o fluxo de trabalho
  deste projeto é local (branches e commits locais apenas).

## Testes

```bash
pytest                     # backend
cd web && npx tsc -b       # type-check do frontend web
```

## Estrutura do projeto

Ver [docs/ARQUITETURA.md](docs/ARQUITETURA.md) para o diagrama do
pipeline e a organização de pastas em `app/`.

## Utilitário: listar chats disponíveis

`list_chats.py` lista os chats/canais que sua conta acessa (útil para
preencher `TELEGRAM_CHATS`):

```bash
python list_chats.py
```
