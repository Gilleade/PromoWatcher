# Segurança e Backups — PromoWatcher

## Arquivos sensíveis

O projeto depende de dois arquivos locais que **nunca** devem ser
commitados, impressos, copiados para fora do ambiente local ou
compartilhados:

- `.env` — contém `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `NOTIFY_CHAT`,
  credenciais de SMTP, entre outros.
- `tg_promos_session.session` (e `*.session-journal`) — sessão
  autenticada do Telethon. Quem tiver esse arquivo tem acesso à conta
  do Telegram sem precisar de senha/código.

Ambos são obrigatórios para o funcionamento e devem ser preservados a
cada nova cópia do projeto (branch, worktree, backup), mas **fora do
Git**.

## `.gitignore`

O `.gitignore` do projeto cobre:

```gitignore
*.bat
.env
*.session
*.session-journal
__pycache__/
*.pyc
*.db
*.sqlite
*.sqlite3
backups/
logs/
exports/
data/
.claude/
```

Antes de qualquer commit, rode `git status` e confirme que nenhum
arquivo sensível aparece na lista de mudanças.

## O que nunca fazer

- Nunca exibir ou logar valores reais de `TELEGRAM_API_ID`,
  `TELEGRAM_API_HASH`, `NOTIFY_CHAT`, tokens ou sessão — inclusive em
  mensagens de erro (prefira `type(e).__name__` a `str(e)` quando a
  exceção pode conter dados sensíveis).
- Nunca rodar `git push` sem confirmação explícita — o fluxo de
  trabalho é local (branches e commits locais).
- Nunca usar `git add -A`/`git add .` sem revisar `git status` antes.

## Backups locais

Antes de qualquer alteração estrutural relevante (mudar pastas, trocar
lógica principal do watcher, adicionar/alterar banco de dados,
interface, envio ao Telegram, ou leitura de variáveis de ambiente),
crie um backup local completo:

```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$dest = "backups\promowatcher_backup_${ts}_antes_<descricao>.zip"
$items = Get-ChildItem -Path . -Exclude ".git",".claude","backups"
Compress-Archive -Path $items.FullName -DestinationPath $dest -Force
```

Padrão de nome:

```text
backups/promowatcher_backup_YYYYMMDD_HHMMSS_antes_<descricao>.zip
```

A pasta `backups/` fica fora do controle de versão (pode conter `.env`
e a sessão do Telethon).

## Versionamento local

```bash
git status                                   # antes de qualquer mudança
git checkout -b feature/algo                 # branch local para a evolução
git add <arquivos específicos>                # nunca git add -A às cegas
git commit -m "feat: descrição da etapa"     # commit de checkpoint
```

**Nunca `git push`** sem que o usuário peça explicitamente.
