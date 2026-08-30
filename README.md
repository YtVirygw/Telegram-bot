# Bot de Link → Imagem para Telegram

Envie um link de site para o bot no privado. Ele extrai a imagem de capa
(meta tag `og:image`) da página e envia a imagem + o link para um grupo fixo.

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

No privado com o bot, envie um link de uma página qualquer (ex: uma notícia,
produto, post de blog). O bot vai:
1. Responder "Buscando imagem do link..."
2. Extrair a imagem `og:image` da página
3. Enviar a imagem + link para o grupo configurado

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
