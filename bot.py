import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==== CONFIGURAÇÕES ====
# Nunca coloque o token direto no código. Use variável de ambiente.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ID do grupo fixo para onde tudo será enviado.
GROUP_CHAT_ID = os.environ.get("TELEGRAM_GROUP_CHAT_ID")

URL_REGEX = re.compile(r"https?://\S+")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

# Estados usados pelas conversas de /cupom e /linkcupon
AGUARDANDO_CUPOM_TEXTO = 1
AGUARDANDO_LINK = 2
AGUARDANDO_CUPOM_DO_LINK = 3

CAPTION_LIMIT = 1024  # limite do Telegram para legenda de foto


# ==== EXTRAÇÃO DE METADADOS DA PÁGINA ====

def _find_meta_content(soup: BeautifulSoup, candidates: list[tuple[str, dict]]) -> str | None:
    """Procura a primeira tag que bater, entre uma lista de candidatas, e retorna seu 'content'."""
    for tag, attrs in candidates:
        found = soup.find(tag, attrs=attrs)
        if found and found.get("content"):
            return found["content"].strip()
    return None


def extract_page_metadata(url: str) -> dict | None:
    """Baixa a página e extrai imagem, título e descrição para preview."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Falha ao baixar {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    image = _find_meta_content(
        soup,
        [
            ("meta", {"property": "og:image"}),
            ("meta", {"name": "og:image"}),
            ("meta", {"property": "twitter:image"}),
            ("meta", {"name": "twitter:image"}),
        ],
    )

    title = _find_meta_content(
        soup,
        [
            ("meta", {"property": "og:title"}),
            ("meta", {"name": "twitter:title"}),
        ],
    )
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    description = _find_meta_content(
        soup,
        [
            ("meta", {"property": "og:description"}),
            ("meta", {"name": "description"}),
            ("meta", {"name": "twitter:description"}),
        ],
    )

    return {"image": image, "title": title, "description": description}


def build_product_caption(title: str | None, description: str | None, cupom: str | None, url: str) -> str:
    """Monta a legenda na ordem: título (se houver), descrição, cupom, link.
    O link nunca é alterado — é sempre o link original recebido (afiliado)."""
    parts = []
    if title:
        parts.append(f"*{title}*")
    if description:
        parts.append(description)
    if cupom:
        parts.append(f"🎟️ Cupom: `{cupom}`")
    parts.append(url)

    caption = "\n\n".join(parts)
    if len(caption) > CAPTION_LIMIT:
        # Corta primeiro a descrição, nunca o link nem o cupom
        overflow = len(caption) - CAPTION_LIMIT
        if description:
            nova_descricao = description[: max(0, len(description) - overflow - 3)] + "..."
            parts_sem_desc = [p for p in parts if p != description]
            idx = 1 if title else 0
            parts_sem_desc.insert(idx, nova_descricao)
            caption = "\n\n".join(parts_sem_desc)
        else:
            caption = caption[: CAPTION_LIMIT - 3] + "..."
    return caption


async def send_product_to_group(context: ContextTypes.DEFAULT_TYPE, url: str, cupom: str | None = None) -> bool:
    """Extrai metadados do link e envia foto + descrição + cupom (opcional) + link pro grupo.
    Retorna True se enviou com sucesso."""
    metadata = extract_page_metadata(url)

    if not metadata or not metadata.get("image"):
        return False

    caption = build_product_caption(
        title=metadata.get("title"),
        description=metadata.get("description"),
        cupom=cupom,
        url=url,
    )

    try:
        await context.bot.send_photo(
            chat_id=GROUP_CHAT_ID,
            photo=metadata["image"],
            caption=caption,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Falha com Markdown, tentando sem formatação: {e}")
        # Remove os caracteres de formatação e tenta de novo, sem quebrar por causa deles
        caption_sem_formatacao = caption.replace("*", "").replace("`", "")
        await context.bot.send_photo(
            chat_id=GROUP_CHAT_ID,
            photo=metadata["image"],
            caption=caption_sem_formatacao,
        )
    return True


# ==== FLUXO: LINK ENVIADO DIRETO (sem comando) ====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = URL_REGEX.search(text)

    if not match:
        # Mensagem sem link e sem estar em nenhuma conversa: ignora ou orienta
        await update.message.reply_text(
            "Me manda um link de produto que eu envio pro grupo. "
            "Ou use /cupom para mandar um cupom sem link, ou /linkcupon para link + cupom."
        )
        return

    url = match.group(0)
    await update.message.reply_text("Buscando informações do link...")

    sucesso = await send_product_to_group(context, url)

    if not sucesso:
        await update.message.reply_text(
            "Não consegui encontrar uma imagem nesse link. "
            "O site pode não ter imagem de preview (og:image)."
        )
        return

    await update.message.reply_text("Enviado para o grupo!")


# ==== FLUXO: /cupom (texto livre, sem link) ====

async def cupom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Beleza! Manda o texto do cupom que você quer publicar.")
    return AGUARDANDO_CUPOM_TEXTO


async def cupom_receber_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=texto)
    await update.message.reply_text("Enviado para o grupo!")
    return ConversationHandler.END


# ==== FLUXO: /linkcupon (link + cupom separados) ====

async def linkcupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Manda o link do produto.")
    return AGUARDANDO_LINK


async def linkcupon_receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = URL_REGEX.search(text)

    if not match:
        await update.message.reply_text("Isso não parece um link. Manda o link do produto:")
        return AGUARDANDO_LINK

    context.user_data["linkcupon_url"] = match.group(0)
    await update.message.reply_text("Beleza, agora manda o cupom.")
    return AGUARDANDO_CUPOM_DO_LINK


async def linkcupon_receber_cupom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cupom = update.message.text
    url = context.user_data.pop("linkcupon_url", None)

    if not url:
        await update.message.reply_text("Algo deu errado, o link se perdeu. Use /linkcupon de novo.")
        return ConversationHandler.END

    await update.message.reply_text("Buscando informações do link...")
    sucesso = await send_product_to_group(context, url, cupom=cupom)

    if not sucesso:
        await update.message.reply_text(
            "Não consegui encontrar uma imagem nesse link. "
            "O site pode não ter imagem de preview (og:image)."
        )
        return ConversationHandler.END

    await update.message.reply_text("Enviado para o grupo!")
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("linkcupon_url", None)
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Defina a variável de ambiente TELEGRAM_BOT_TOKEN com o token do bot."
        )
    if not GROUP_CHAT_ID:
        raise RuntimeError(
            "Defina a variável de ambiente TELEGRAM_GROUP_CHAT_ID com o id do grupo."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    cupom_conv = ConversationHandler(
        entry_points=[CommandHandler("cupom", cupom_start)],
        states={
            AGUARDANDO_CUPOM_TEXTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cupom_receber_texto)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    linkcupon_conv = ConversationHandler(
        entry_points=[CommandHandler("linkcupon", linkcupon_start)],
        states={
            AGUARDANDO_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, linkcupon_receber_link)
            ],
            AGUARDANDO_CUPOM_DO_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, linkcupon_receber_cupom)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    # As conversas (/cupom e /linkcupon) precisam ser registradas ANTES do
    # handler genérico de mensagens, senão ele "rouba" as respostas do usuário.
    app.add_handler(cupom_conv)
    app.add_handler(linkcupon_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot iniciado. Aguardando mensagens...")
    app.run_polling()


if __name__ == "__main__":
    main()
