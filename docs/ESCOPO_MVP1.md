# Documento de escopo e instruções de desenvolvimento — PromoWatcher

**Versão:** 0.1 — Escopo inicial para evolução estruturada  
**Data:** 01/07/2026  
**Objetivo:** orientar Claude, Codex ou outro agente de desenvolvimento a evoluir o projeto PromoWatcher de forma limpa, escalável, documentada, versionada localmente e com backups locais obrigatórios.

---

## 1. Contexto do projeto

O projeto atual, chamado **PromoWatcher**, já está funcional e monitora mensagens de grupos/canais do Telegram. A versão atual usa uma lógica simples baseada em palavras-chave, por exemplo `bug`, `notebook`, `amazon`, `lava e seca`, etc. Essa abordagem funciona parcialmente, mas tem limitações importantes:

- muitos alertas repetidos quando vários grupos publicam a mesma promoção;
- baixa precisão quando o produto aparece com nome incompleto, abreviado ou em formato diferente;
- dificuldade para diferenciar produto desejado, produto parecido, acessório, item usado ou anúncio irrelevante;
- links podem vir encurtados, com afiliado, com redirecionamento ou apontando para página intermediária;
- ausência de interface para cadastrar, editar e auditar alertas;
- ausência de histórico estruturado das mensagens capturadas, promoções aceitas, duplicadas e ignoradas;
- ausência de explicação clara do motivo pelo qual uma oferta foi aprovada ou rejeitada.

A evolução desejada para o futuro é um sistema completo de descoberta, comparação e análise de promoções. Porém, neste momento, o foco é melhorar a base atual sem alterar a premissa principal: **as promoções continuarão vindo inicialmente dos grupos/canais do Telegram**.

---

## 2. Objetivo do MVP 1

Criar uma **Central Inteligente de Promoções do Telegram**, mantendo o monitoramento atual, mas adicionando uma camada estruturada de processamento, deduplicação, cadastro de alertas e interface local.

O MVP 1 deve fazer:

1. Ler mensagens dos grupos/canais do Telegram já configurados.
2. Salvar mensagens brutas no banco local.
3. Extrair texto, links, preço, cupom, origem e mídia quando disponível.
4. Resolver links encurtados/redirecionados quando possível.
5. Limpar parâmetros de afiliado e rastreamento quando possível.
6. Preservar o link original quando a limpeza/resolução falhar.
7. Aplicar regras de alertas cadastradas pelo usuário.
8. Deduplicar promoções repetidas entre diferentes grupos.
9. Enviar para o grupo/canal de destino apenas promoções aprovadas e não repetidas.
10. Exibir mensagens, promoções e decisões em uma interface gráfica local.

Fora do MVP 1:

- scraping direto da Amazon, Mercado Livre, Shopee, Kabum, Magalu, Pichau ou outras lojas;
- integração com APIs oficiais de afiliados;
- OCR de imagens;
- IA classificadora avançada;
- histórico avançado de preço por loja;
- WhatsApp;
- app mobile;
- publicação automática em site próprio.

---

## 3. Regras não negociáveis

### 3.1 Não perder promoção por falha técnica

O sistema nunca deve descartar uma promoção apenas porque não conseguiu limpar ou resolver o link.

Regra obrigatória:

```text
Se conseguir link limpo:
    usar link limpo
Senão, se conseguir link final resolvido:
    usar link final resolvido
Senão, se houver link original:
    usar link original
Senão:
    registrar mensagem como NO_LINK e seguir o fluxo de análise textual
```

### 3.2 Preservar funcionamento atual

Antes de qualquer alteração, o agente deve garantir que o funcionamento atual continue preservado. O script existente não deve ser destruído sem alternativa funcional.

### 3.3 Desenvolvimento incremental

Cada etapa deve ser pequena, testável e documentada. Evitar reescrever tudo de uma vez.

### 3.4 Backups locais obrigatórios

Antes de qualquer modificação relevante, criar backup local completo da pasta do projeto.

### 3.5 Não subir alterações para GitHub

O projeto pode estar em um repositório Git, mas as alterações devem ficar apenas no ambiente local. É permitido criar branches e commits locais. Não executar `git push`.

### 3.6 Não vazar segredos

O projeto pode conter chaves do Telegram, sessão local do Telethon, tokens e outros dados sensíveis. O agente não deve copiar, imprimir, commitar, compactar para envio externo ou documentar esses valores.

---

## 4. Segurança e tratamento de segredos

O arquivo `.env` real deve ser tratado como sensível.

Regras:

- nunca alterar o `.env` sem necessidade;
- nunca remover chaves existentes;
- nunca exibir valores reais de `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `BOT_TOKEN`, `SESSION`, `NOTIFY_CHAT` ou similares;
- garantir que `.env`, arquivos `.session`, bancos locais e backups com credenciais não sejam enviados ao GitHub;
- manter `.env.example` com nomes de variáveis, mas sem valores reais;
- revisar `.gitignore` para incluir arquivos sensíveis.

Sugestão de `.gitignore` mínimo:

```gitignore
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
```

Observação: backups locais podem conter segredos. Portanto, a pasta `backups/` deve permanecer local e ignorada pelo Git.

---

## 5. Versionamento local e backups

### 5.1 Fluxo obrigatório antes de modificar

Ao iniciar o trabalho:

```bash
git status
```

Se houver alterações não commitadas, não sobrescrever. Registrar o estado atual.

Criar backup local:

```bash
mkdir -p backups
# Windows PowerShell, exemplo:
Compress-Archive -Path .\* -DestinationPath .\backups\promowatcher_backup_YYYYMMDD_HHMMSS.zip -Force
```

Criar branch local:

```bash
git checkout -b feature/mvp1-central-inteligente-telegram
```

Criar commit de checkpoint quando concluir blocos funcionais:

```bash
git add .
git commit -m "feat: adiciona base de processamento estruturado de promoções"
```

Importante: **não executar `git push`**.

### 5.2 Backups por etapa

Criar backup antes de:

- alterar estrutura de pastas;
- trocar lógica principal do watcher;
- adicionar banco de dados;
- adicionar interface gráfica;
- alterar envio de mensagens ao Telegram;
- alterar leitura de variáveis de ambiente.

Padrão de nome:

```text
backups/promowatcher_backup_YYYYMMDD_HHMMSS_antes_<descricao>.zip
```

Exemplo:

```text
backups/promowatcher_backup_20260701_1500_antes_banco_sqlite.zip
```

---

## 6. Arquitetura inicial desejada

Manter Python como base principal.

Sugestão de estrutura:

```text
PromoWatcher/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── telegram_client.py
│   ├── telegram_notifier.py
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── text_parser.py
│   │   ├── price_parser.py
│   │   ├── link_extractor.py
│   │   ├── link_resolver.py
│   │   └── normalizer.py
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── alert_matcher.py
│   │   ├── score.py
│   │   └── deduplicator.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── message_processor.py
│   │   ├── promotion_service.py
│   │   └── notification_service.py
│   └── ui/
│       ├── __init__.py
│       └── streamlit_app.py
├── data/
│   └── promowatcher.sqlite3
├── logs/
├── backups/
├── alerts.json
├── .env
├── .env.example
├── requirements.txt
├── watch_promos.py
├── run_ui.py
└── README.md
```

A estrutura pode ser adaptada, mas deve manter separação clara entre:

- leitura do Telegram;
- parsing/normalização;
- regras de alerta;
- deduplicação;
- banco de dados;
- interface;
- envio de notificações.

---

## 7. Modelo de dados mínimo

### 7.1 Tabela `raw_messages`

Armazena tudo que chegou do Telegram.

Campos sugeridos:

```text
id
telegram_message_id
chat_id
chat_title
sender_id
message_text
message_date
has_media
media_type
raw_json opcional
created_at
```

### 7.2 Tabela `promotions`

Armazena a promoção normalizada.

Campos sugeridos:

```text
id
raw_message_id
title_guess
price
old_price
discount_percent
coupon
source_chat_title
original_links
selected_original_url
resolved_url
clean_url
link_status
store_domain
dedupe_key
status
score
matched_alert_id
first_seen_at
last_seen_at
repeat_count
created_at
updated_at
```

### 7.3 Tabela `alerts`

Armazena alertas configurados pelo usuário.

Campos sugeridos:

```text
id
name
enabled
alert_type
required_terms
optional_terms
excluded_terms
min_price
max_price
min_discount_percent
bug_mode
min_score
send_to_telegram
created_at
updated_at
```

### 7.4 Tabela `promotion_occurrences`

Registra aparições repetidas da mesma promoção em diferentes grupos.

Campos sugeridos:

```text
id
promotion_id
raw_message_id
chat_title
message_date
original_url
created_at
```

### 7.5 Tabela `notifications`

Registra o que foi enviado ao grupo final.

Campos sugeridos:

```text
id
promotion_id
alert_id
channel
message_sent
sent_at
status
error_message
```

---

## 8. Pipeline de processamento

Fluxo esperado:

```text
Nova mensagem do Telegram
↓
Salvar raw_message
↓
Extrair links
↓
Resolver e limpar links com fallback
↓
Extrair preço, cupom e possível desconto
↓
Gerar título provável
↓
Normalizar texto
↓
Aplicar alertas cadastrados
↓
Calcular score
↓
Gerar chave de deduplicação
↓
Verificar se já existe promoção equivalente
↓
Se duplicada: registrar ocorrência e não notificar novamente
↓
Se nova e aprovada: registrar promoção e notificar
↓
Exibir tudo na interface
```

---

## 9. Tratamento de links

### 9.1 Extração

Extrair todos os links do texto, incluindo:

```text
https://...
http://...
amzn.to/...
meli.la/...
s.shopee.com.br/...
link.amazon/...
aoferta.net/...
```

### 9.2 Resolução

Para cada link:

1. tentar completar protocolo, se necessário;
2. tentar seguir redirecionamentos HTTP com timeout curto;
3. limitar número de redirecionamentos;
4. tratar erro sem quebrar o pipeline.

### 9.3 Limpeza

Remover parâmetros comuns de afiliado e rastreamento:

```text
utm_source
utm_medium
utm_campaign
utm_content
utm_term
tag
ascsubtag
linkCode
camp
creative
ref
ref_
psc
smid
sprefix
crid
keywords
qid
```

A limpeza deve ser conservadora. Se a remoção de parâmetros quebrar o link ou causar dúvida, manter o original/final.

### 9.4 Status de link

Usar enum ou constantes:

```text
CLEANED
RESOLVED
ORIGINAL_FALLBACK
MULTIPLE_LINKS
NO_LINK
INTERMEDIATE_PAGE
ERROR_RESOLVING
```

### 9.5 Regra de fallback

Obrigatória:

```text
Nenhuma promoção deve ser descartada por falha de limpeza ou resolução de link.
```

---

## 10. Deduplicação inteligente

A deduplicação deve evitar que o mesmo bug/promoção seja enviado várias vezes quando aparece em grupos diferentes.

Ordem sugerida de deduplicação:

1. `clean_url`, quando disponível;
2. `resolved_url`, quando disponível;
3. domínio + caminho normalizado da URL;
4. SKU/código de produto extraído do link ou do texto;
5. título normalizado + preço;
6. similaridade textual simples como fallback futuro.

Comportamento esperado:

```text
Primeira ocorrência:
    criar promoção
    notificar, se aprovada

Ocorrência repetida:
    incrementar repeat_count
    registrar em promotion_occurrences
    não reenviar alerta padrão
```

Possível melhoria futura:

```text
Se repeat_count aumentar muito em poucos minutos e a promoção estiver marcada como BUG:
    opcionalmente enviar atualização: "promoção apareceu em vários grupos"
```

Essa melhoria é futura, não obrigatória no MVP 1.

---

## 11. Regras de alertas

Substituir gradualmente `keywords.txt` por alertas estruturados.

Formato inicial possível em `alerts.json`:

```json
[
  {
    "name": "Notebook RTX 4050 até 4500",
    "enabled": true,
    "alert_type": "PRODUCT_RULE",
    "required": ["notebook", "rtx 4050"],
    "any": ["16gb", "512gb", "lenovo loq", "acer nitro", "asus tuf", "dell g15"],
    "exclude": ["rtx 3050", "gtx", "usado", "recondicionado", "peças", "capa"],
    "max_price": 4500,
    "min_discount_percent": 0,
    "bug_mode": false,
    "min_score": 70
  },
  {
    "name": "Lava e seca LG 18kg",
    "enabled": true,
    "alert_type": "PRODUCT_RULE",
    "required": ["lava e seca", "lg"],
    "any": ["18kg", "18 kg", "vc4", "smart inverter"],
    "exclude": ["usada", "usado", "peças", "defeito", "conserto"],
    "max_price": 4000,
    "min_discount_percent": 0,
    "bug_mode": false,
    "min_score": 70
  },
  {
    "name": "Possível BUG geral",
    "enabled": true,
    "alert_type": "BUG_RULE",
    "required": [],
    "any": ["bug", "provável bug", "possível bug", "preço errado", "erro de preço"],
    "exclude": ["golpe", "cuidado", "cancelado"],
    "max_price": null,
    "min_discount_percent": 50,
    "bug_mode": true,
    "min_score": 65
  }
]
```

A interface poderá editar esses alertas posteriormente. No início, `alerts.json` é aceitável, desde que a estrutura já seja compatível com interface futura.

---

## 12. Score da promoção

Criar pontuação simples e explicável.

Exemplo:

```text
+40 se todos os termos obrigatórios foram encontrados
+15 se algum termo opcional foi encontrado
+20 se preço está abaixo do máximo definido
+15 se texto contém bug/provável bug/preço errado
+10 se link é de loja conhecida
-50 se contém termo bloqueado
-30 se não foi possível identificar preço quando o alerta exige preço
```

A decisão deve registrar o motivo:

```text
Aprovado porque encontrou: notebook, rtx 4050, preço abaixo de 4500.
Ignorado porque contém termo bloqueado: usado.
Duplicado porque link limpo já havia sido registrado.
```

Essas justificativas devem aparecer na interface.

---

## 13. Interface gráfica local

A interface pode ser feita inicialmente em Streamlit para acelerar desenvolvimento.

### 13.1 Aba Dashboard

Exibir:

```text
Promoções capturadas hoje
Alertas enviados hoje
Duplicadas ignoradas
Possíveis bugs
Top grupos de origem
Últimas promoções aprovadas
```

### 13.2 Aba Alertas

Permitir:

```text
Criar alerta
Editar alerta
Ativar/desativar alerta
Configurar termos obrigatórios
Configurar termos opcionais
Configurar termos bloqueados
Configurar preço máximo
Configurar modo bug
Configurar score mínimo
```

### 13.3 Aba Promoções

Tabela com:

```text
Data/hora
Título provável
Preço
Alerta relacionado
Status
Score
Link selecionado
Status do link
Grupo de origem
Repetições
```

Filtros:

```text
Hoje
Últimas 24h
Apenas bugs
Apenas notificadas
Apenas duplicadas
Por alerta
Por grupo
```

### 13.4 Aba Mensagens Telegram

Mostrar fluxo bruto para auditoria:

```text
Texto original
Grupo de origem
Links extraídos
Preço extraído
Status do processamento
Motivo da aprovação/rejeição
```

---

## 14. Notificação no Telegram

A saída final continua sendo no grupo/canal de destino configurado.

Formato sugerido:

```text
🚨 PromoWatcher
Alerta: Notebook RTX 4050 até 4500
Score: 92
Origem: Nome do grupo
Repetições detectadas: 1

Produto:
ASUS Vivobook S14 16GB 512GB

Preço: R$ 4.299,00
Cupom: NOTE600
Status do link: CLEANED

Link:
https://www.amazon.com.br/...

Motivo:
Encontrou termos obrigatórios e preço abaixo do limite configurado.
```

Para duplicados, não enviar novamente por padrão.

---

## 15. Logs e auditoria

Criar logs simples em arquivo local:

```text
logs/promowatcher.log
```

Registrar:

- início e parada do watcher;
- grupos monitorados;
- mensagem recebida;
- erros de resolução de link;
- erros de banco;
- promoções notificadas;
- duplicadas ignoradas;
- exceções não tratadas.

Nunca registrar segredos no log.

---

## 16. Testes mínimos

Criar testes para:

```text
extração de preço
extração de links
limpeza de link Amazon
limpeza de link Mercado Livre
fallback quando link falha
match de alerta com termo obrigatório
bloqueio por termo excluído
deduplicação por clean_url
deduplicação por título + preço
score básico
```

Sugestão de pasta:

```text
tests/
├── test_price_parser.py
├── test_link_extractor.py
├── test_link_cleaner.py
├── test_alert_matcher.py
└── test_deduplicator.py
```

---

## 17. Critérios de aceite do MVP 1

O MVP 1 será considerado pronto quando:

1. o watcher continuar capturando mensagens do Telegram;
2. mensagens brutas forem salvas no banco;
3. links forem extraídos e tratados com fallback seguro;
4. links limpos forem usados quando possível;
5. links originais forem preservados quando a limpeza falhar;
6. alertas estruturados substituírem a dependência exclusiva de `keywords.txt`;
7. promoções repetidas não forem reenviadas ao grupo final;
8. interface local exibir dashboard, alertas, promoções e mensagens;
9. cada decisão tiver status e motivo;
10. backups locais existirem antes das alterações relevantes;
11. commits locais documentarem cada etapa;
12. nenhum segredo real for exposto, commitado ou enviado ao GitHub.

---

## 18. Ordem recomendada de implementação

### Etapa 1 — Preparação segura

- Verificar `git status`.
- Criar backup local.
- Criar branch local.
- Revisar `.gitignore`.
- Garantir que `.env` e sessões estão ignorados.

### Etapa 2 — Banco SQLite

- Criar camada `database.py`.
- Criar tabelas mínimas.
- Salvar mensagens brutas.

### Etapa 3 — Parser

- Extrair links.
- Extrair preços.
- Extrair cupom simples.
- Normalizar texto.

### Etapa 4 — Link resolver/cleaner

- Resolver redirecionamentos com timeout.
- Limpar parâmetros comuns.
- Implementar fallback obrigatório.
- Registrar `link_status`.

### Etapa 5 — Alertas estruturados

- Criar `alerts.json`.
- Criar matcher.
- Criar score.
- Registrar motivo da decisão.

### Etapa 6 — Deduplicação

- Criar `dedupe_key`.
- Registrar ocorrência repetida.
- Não reenviar duplicados.

### Etapa 7 — Interface

- Criar Streamlit inicial.
- Mostrar dashboard.
- Mostrar promoções.
- Mostrar mensagens.
- Permitir editar alertas, se viável nesta etapa.

### Etapa 8 — Notificação final

- Melhorar mensagem enviada ao Telegram.
- Incluir link selecionado.
- Incluir motivo resumido.

### Etapa 9 — Testes e documentação

- Criar testes mínimos.
- Atualizar README.
- Criar changelog local.

---

## 19. Documentação esperada no projeto

Atualizar ou criar:

```text
README.md
CHANGELOG.md
docs/ESCOPO_MVP1.md
docs/ARQUITETURA.md
docs/SEGURANCA_E_BACKUPS.md
docs/ALERTAS.md
```

O README deve explicar:

- como instalar;
- como configurar `.env`;
- como rodar watcher;
- como rodar interface;
- como cadastrar alertas;
- como funcionam backups;
- como evitar envio acidental ao GitHub.

---

## 20. Instrução direta para Claude/Codex

Você receberá acesso a um projeto funcional chamado PromoWatcher. Ele já monitora grupos/canais do Telegram e filtra mensagens por palavras-chave. Sua tarefa é evoluir o projeto para o MVP 1 descrito neste documento.

Siga estas regras:

1. Não faça `git push`.
2. Não exponha, copie, imprima ou documente valores reais de chaves, tokens, sessões ou variáveis sensíveis.
3. Antes de alterar arquivos, crie backup local em `backups/`.
4. Antes de alterar, verifique `git status`.
5. Crie uma branch local para a evolução.
6. Faça commits locais por etapas pequenas e lógicas.
7. Preserve o funcionamento atual do watcher.
8. Não reescreva tudo de uma vez.
9. Implemente primeiro banco, parser, link cleaner com fallback, alertas estruturados e deduplicação.
10. Só depois avance para interface.
11. Registre decisões e motivos de aceite/rejeição das promoções.
12. Nunca descarte promoção apenas por falha ao limpar/resolver link.
13. Quando não conseguir limpar o link, use o link original.
14. Quando detectar duplicidade, registre ocorrência, mas não envie alerta repetido.
15. Documente tudo em português.
16. Ao final, entregue um resumo das alterações, arquivos modificados, comandos usados, testes executados e próximos passos.

Prioridade máxima: segurança dos segredos, backup local, funcionamento preservado e evolução incremental.

---

## 21. Resultado esperado da primeira entrega do agente

Ao final da primeira entrega, espera-se:

```text
- branch local criada;
- backup local criado;
- .gitignore revisado;
- banco SQLite inicial funcionando;
- mensagens do Telegram sendo salvas;
- parser básico funcionando;
- link cleaner com fallback funcionando;
- alerts.json estruturado;
- matcher de alertas funcionando;
- deduplicação básica funcionando;
- envio ao Telegram filtrado e sem repetição simples;
- README/CHANGELOG atualizados;
- nenhum segredo exposto;
- nenhum push feito.
```
