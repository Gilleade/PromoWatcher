# PromoWatcher

Monitor de promoções em grupos/canais do Telegram, com deduplicação
inteligente, alertas estruturados e uma Central Inteligente de Promoções
(MVP1) local.

## O que o PromoWatcher faz

1. Lê mensagens dos grupos/canais do Telegram configurados.
2. Salva as mensagens brutas em um banco SQLite local.
3. Extrai texto, links, preço e cupom.
4. Resolve links encurtados e remove parâmetros de afiliado/rastreamento
   (com fallback: nunca descarta uma promoção por falha ao limpar/resolver
   um link — ver [docs/ARQUITETURA.md](docs/ARQUITETURA.md)).
5. Aplica alertas estruturados (`alerts.json`) com pontuação (score) e
   motivo explicável para cada decisão.
6. Deduplica promoções repetidas entre diferentes grupos.
7. Envia ao chat/canal de destino apenas promoções aprovadas e não
   repetidas.
8. Exibe tudo (mensagens, promoções, alertas, dashboard) em uma interface
   local Streamlit.

## Instalação

Pré-requisito: Python 3.11+ (o projeto foi validado com o ambiente conda
`promowatcher`).

```bash
pip install -r requirements.txt
# Para rodar os testes localmente, instale também as dependências de dev:
pip install -r requirements-dev.txt
```

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
- `ALERTS_FILE`: caminho do arquivo de alertas (padrão `alerts.json`).
- `DB_PATH`: caminho do banco SQLite (padrão `data/promowatcher.sqlite3`).

O `.env` e o arquivo de sessão do Telethon (`tg_promos_session.session`)
são obrigatórios para o funcionamento e ficam **fora do controle de
versão** (ver [docs/SEGURANCA_E_BACKUPS.md](docs/SEGURANCA_E_BACKUPS.md)).
Ao criar uma nova cópia/branch/worktree do projeto, copie manualmente
esses dois arquivos para o novo diretório — eles não são versionados.

## Como rodar (comando único — recomendado)

```bash
python run_app.py
```

Sobe o watcher (backend, faz o trabalho de verdade) e a interface
Streamlit (frontend, para acompanhamento e gerenciamento básico —
dashboard, promoções, mensagens e alertas) juntos, em um único terminal,
com logs prefixados (`[watcher]`/`[ui]`). `Ctrl+C` encerra os dois de
forma limpa. Se um dos dois cair sozinho, o outro é encerrado junto.

Na primeira execução (ou se a sessão expirar/for revogada), o Telethon
pedirá telefone e código de confirmação — isso é esperado e só acontece
quando a sessão salva não está mais autorizada pelo Telegram.

## Como rodar cada parte separadamente

Útil para depurar um lado sem derrubar o outro:

```bash
python watch_promos.py      # só o watcher
streamlit run run_ui.py     # só a interface
```

A interface lê o mesmo banco SQLite em modo WAL, então pode ser aberta
em paralelo ao watcher sem conflito de escrita — **mas não rode dois
watchers ao mesmo tempo** (`watch_promos.py` duas vezes, ou
`watch_promos.py` + `run_app.py`): os dois usariam o mesmo arquivo de
sessão do Telethon (`tg_promos_session.session`) simultaneamente, o que
pode causar erro de banco travado ou invalidar a sessão.

Abas disponíveis: Dashboard, Alertas, Promoções e Mensagens Telegram.

## Como cadastrar alertas

Pela aba "Alertas" da interface (criar, editar, ativar/desativar e
excluir), ou editando `alerts.json` diretamente na raiz do projeto.
Veja o formato completo e exemplos em
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
pytest
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
