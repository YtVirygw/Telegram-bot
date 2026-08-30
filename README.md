# Bot de Cupons e Links para Telegram

O bot tem três comandos, todos enviando pro mesmo grupo fixo. Não existe
mais envio automático por link solto — tudo passa por um comando.

## Comandos

- **`/link`** — pergunta o link do produto, depois o preço. Envia pro grupo:
  foto (se achar) + 🔥 título + Preço + link + "anúncio".
- **`/linkcupom`** — pergunta o link, depois o preço, depois o cupom. Envia:
  foto (se achar) + 🔥 título + Preço + Cupom + link + "anúncio". (O bot
  também aceita `/linkcupon`, com "n", caso o autocorrect do celular troque
  a grafia — mas o nome oficial no menu é `linkcupom`.)
- **`/cupom`** — pergunta o texto do cupom. O que você mandar é repassado
  **exatamente como escrito** pro grupo (negrito, emojis, links dentro do
  texto — tudo preservado), sem exigir estrutura fixa. Ideal pra cupons com
  várias categorias, como o formato de canais grandes.
- **`/cancelar`** — cancela o comando em andamento a qualquer momento. Toda
  conversa também expira sozinha depois de 5 minutos sem resposta, então o
  bot nunca fica "travado" esperando pra sempre.

Em `/link` e `/linkcupon`, o **link do produto nunca é alterado** — é sempre
repassado exatamente como você mandou (importante pra link afiliado).

## Menu de comandos no Telegram

O bot registra os comandos automaticamente ao iniciar, então ao digitar `/`
no chat com ele já aparece a lista com descrição — sem precisar configurar
nada no @BotFather nem decorar os comandos.

## ⚠️ Antes de tudo: revogue tokens antigos

Se você já compartilhou um token em algum lugar que não devia (ex: aqui no
chat), revogue antes de usar:

1. Abra o @BotFather no Telegram
2. `/mybots` → seu bot → **API Token** → **Revoke current token**
3. Copie o novo token gerado

Nunca cole o token direto em código ou em conversas. Use sempre variável de
ambiente (veja abaixo).

## 1. Instalar dependências

```bash
pip install -r requirements.txt
```

## 2. Descobrir o chat_id do grupo

Opção mais simples pelo celular: abra **web.telegram.org** no navegador,
entre no grupo, e veja o número na barra de endereço (ex:
`web.telegram.org/a/#-1001234567890` → o chat_id é `-1001234567890`, com o
sinal de menos).

## 3. Configurar variáveis de ambiente

No Railway (ou serviço equivalente), aba "Variables":

```
TELEGRAM_BOT_TOKEN = seu_token_novo_aqui
TELEGRAM_GROUP_CHAT_ID = -100XXXXXXXXXX
TELEGRAM_ALLOWED_USER_IDS = 111111111,222222222
```

`TELEGRAM_ALLOWED_USER_IDS` é a lista de quem pode usar o bot — IDs
numéricos do Telegram separados por vírgula, sem espaço. Quem não estiver
nessa lista recebe "Você não tem permissão para usar este bot." e nada é
enviado ao grupo.

**Como descobrir o ID de alguém:** peça pra pessoa mandar uma mensagem para
o bot **@userinfobot** — ele responde na hora com o ID numérico. Faça isso
com o seu próprio usuário também, e inclua na lista.

## 4. Rodar o bot

```bash
python bot.py
```

## 5. Testar

- `/link` → manda um link de produto → manda o preço → confere se chegou no
  grupo com foto, título, preço e link.
- `/linkcupon` → manda link → preço → cupom → confere a ordem no grupo.
- `/cupom` → manda um texto com negrito/emoji → confere se chegou igualzinho
  no grupo.

## Limitações conhecidas

- Alguns sites bloqueiam requisições automatizadas (exigem login ou têm
  proteção anti-bot) — nesses casos o bot manda só o texto, sem foto.
- Sites sem a tag `og:image`/`og:title` podem não ter imagem ou título
  encontrados; o bot ainda assim envia o restante das informações.
