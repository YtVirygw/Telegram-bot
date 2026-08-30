# Bot de Cupons e Links para Telegram

O bot tem três formas de uso, todas enviando para o mesmo grupo fixo:

1. **Link direto** (sem comando) — manda qualquer link de produto no privado
   e o bot já envia pro grupo: Foto → Descrição → Link.
2. **`/cupom`** — o bot pergunta o texto do cupom e manda ele puro pro grupo
   (sem link, sem foto).
3. **`/linkcupon`** — o bot pergunta primeiro o link, depois o cupom, e envia
   pro grupo: Foto → Descrição → Cupom → Link.

Em todos os casos com link, o **link nunca é alterado** (importante pra links
afiliados) — ele é sempre repassado exatamente como você mandou.

## ⚠️ Antes de tudo: revogue o token antigo

Você compartilhou um token em uma conversa anteriormente. Antes de usar este
bot:

1. Abra o @BotFather no Telegram
2. Envie `/mybots` → selecione seu bot → **API Token** → **Revoke current token**
3. Copie o novo token gerado

Nunca cole o token direto em código ou em conversas. Use sempre variável de
ambiente (veja abaixo).

## 1. Instalar dependências

```bash
pip install -r requirements.txt
```

## 2. Descobrir o chat_id do grupo

1. Adicione o bot ao grupo desejado
2. Envie qualquer mensagem no grupo
3. Acesse no navegador (substituindo SEU_TOKEN):
   `https://api.telegram.org/botSEU_TOKEN/getUpdates`
4. Procure por `"chat":{"id":-100XXXXXXXXXX, ...}` — esse número (com o sinal
   de menos) é o `GROUP_CHAT_ID`

## 3. Configurar variáveis de ambiente

Crie um arquivo `.env` (ou exporte direto no terminal):

```bash
export TELEGRAM_BOT_TOKEN="seu_token_novo_aqui"
export TELEGRAM_GROUP_CHAT_ID="-100XXXXXXXXXX"
```

## 4. Rodar o bot

```bash
python bot.py
```

## 5. Testar

No privado com o bot:

- **Link direto:** mande um link de produto. O bot responde "Buscando
  informações do link...", extrai a imagem e descrição, e envia pro grupo
  na ordem Foto → Descrição → Link.
- **`/cupom`:** o bot pergunta o texto do cupom. Depois que você responder,
  ele manda esse texto puro pro grupo (sem link).
- **`/linkcupon`:** o bot pergunta o link, depois o cupom. Depois de
  responder os dois, ele envia pro grupo: Foto → Descrição → Cupom → Link.
- Em qualquer uma das conversas (`/cupom` ou `/linkcupon`), pode usar
  `/cancelar` para desistir no meio do caminho.

## Hospedagem 24/7

Para o bot ficar sempre ativo (sem precisar deixar seu computador ligado),
hospede em um serviço como Railway, Render ou uma VPS simples. Nesses
serviços, você configura as mesmas variáveis de ambiente (`TELEGRAM_BOT_TOKEN`
e `TELEGRAM_GROUP_CHAT_ID`) no painel do serviço, sem precisar deixar o token
no código.

## Limitações conhecidas

- Alguns sites bloqueiam requisições automatizadas (ex: exigem login ou têm
  proteção anti-bot) — nesses casos a extração da imagem pode falhar.
- Sites sem a tag `og:image` ou `twitter:image` não terão imagem encontrada.
