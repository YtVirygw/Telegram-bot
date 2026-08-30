import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update, BotCommand
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

# Lista de IDs numéricos do Telegram autorizados a usar o bot, separados por
# vírgula (ex: "111111111,222222222"). Descubra o ID de alguém mandando uma
# mensagem para o bot @userinfobot.
_usuarios_raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
USUARIOS_AUTORIZADOS = {
    int(uid.strip()) for uid in _usuarios_raw.split(",") if uid.strip().isdigit()
}

URL_REGEX = re.compile(r"https?://\S+")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

CAPTION_LIMIT = 1024  # limite do Telegram para legenda de foto


async def usuario_autorizado(update: Update) -> bool:
    """Verifica se quem mandou a mensagem está na lista de autorizados.
    Se não estiver, avisa e retorna False."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id in USUARIOS_AUTORIZADOS:
        return True
    await update.message.reply_text("Você não tem permissão para usar este bot.")
    logger.info(f"Tentativa de uso bloqueada: user_id={user_id}")
    return False

# Estados das conversas
LINK_AGUARDANDO_LINK = 1
LINK_AGUARDANDO_PRECO = 2

LINKCUPON_AGUARDANDO_LINK = 3
LINKCUPON_AGUARDANDO_PRECO = 4
LINKCUPON_AGUARDANDO_CUPOM = 5

# Lista de comandos exibida no menu "/" do Telegram
COMANDOS = [
    BotCommand("link", "Link de produto + preço"),
    BotCommand("linkcupon", "Link de produto + preço + cupom"),
    BotCommand("cupom", "Enviar um cupom (texto livre, sem link)"),
    BotCommand("cancelar", "Cancelar o comando atual"),
]


# ==== EXTRAÇÃO DE METADADOS DA PÁGINA ====

def _find_meta_content(soup: BeautifulSoup, candidates: list[tuple[str, dict]]) -> str | None:
    """Procura a primeira tag que bater, entre uma lista de candidatas, e retorna seu 'content'."""
    for tag, attrs in candidates:
        found = soup.find(tag, attrs=attrs)
        if found and found.get("content"):
            return found["content"].strip()
    return None


def extract_page_metadata(url: str) -> dict:
    """Baixa a página e extrai imagem e título. Nunca lança erro — se falhar,
    retorna campos vazios e o bot segue sem imagem/título."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Falha ao baixar {url}: {e}")
        return {"image": None, "title": None}

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

    return {"image": image, "title": title}


def build_product_caption(title: str | None, preco: str, url: str, cupom: str | None = None) -> str:
    """Monta a legenda na ordem: 🔥 título / Preço / Cupom (se houver) / Link / anúncio.
    O link nunca é alterado — é sempre o link original recebido (afiliado)."""
    linhas = []

    if title:
        linhas.append(f"🔥 *{title}*")
    else:
        linhas.append("🔥")

    linhas.append(f"*Preço:* R$ {preco}")

    if cupom:
        linhas.append(f"*Cupom:* {cupom}")

    linhas.append(url)
    linhas.append("anúncio")

    caption = "\n\n".join(linhas)
    if len(caption) > CAPTION_LIMIT:
        caption = caption[: CAPTION_LIMIT - 3] + "..."
    return caption


async def enviar_produto_para_grupo(
    context: ContextTypes.DEFAULT_TYPE, url: str, preco: str, cupom: str | None = None
):
    """Extrai metadados do link e envia pro grupo: foto (se achar) + 🔥 título +
    preço + cupom (se houver) + link + anúncio."""
    metadata = extract_page_metadata(url)
    caption = build_product_caption(
        title=metadata.get("title"), preco=preco, url=url, cupom=cupom
    )

    if metadata.get("image"):
        try:
            await context.bot.send_photo(
                chat_id=GROUP_CHAT_ID,
                photo=metadata["image"],
                caption=caption,
                parse_mode="Markdown",
            )
            return
        except Exception as e:
            logger.warning(f"Falha ao enviar foto com Markdown: {e}")
            try:
                caption_sem_formatacao = caption.replace("*", "")
                await context.bot.send_photo(
                    chat_id=GROUP_CHAT_ID,
                    photo=metadata["image"],
                    caption=caption_sem_formatacao,
                )
                return
            except Exception as e2:
                logger.warning(f"Falha ao enviar foto sem formatação, mandando só texto: {e2}")

    # Sem imagem (não achou og:image ou falhou o envio da foto): manda só o texto
    try:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID, text=caption, parse_mode="Markdown"
        )
    except Exception:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID, text=caption.replace("*", "")
        )


# ==== /cupom — texto livre, preservando formatação, sem link ====

CUPOM_AGUARDANDO_TEXTO = 10


async def cupom_start_v2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await usuario_autorizado(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "Manda o texto do cupom (pode usar negrito, emojis etc — vou repassar exatamente como você escrever)."
    )
    return CUPOM_AGUARDANDO_TEXTO


async def cupom_receber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # copy_message preserva formatação (negrito, itálico, emojis) e também
    # funcionaria com foto/vídeo, se um dia você quiser mandar cupom com imagem.
    await context.bot.copy_message(
        chat_id=GROUP_CHAT_ID,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
    )
    await update.message.reply_text("Enviado para o grupo!")
    return ConversationHandler.END


# ==== /link — link + preço, sem cupom ====

async def link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await usuario_autorizado(update):
        return ConversationHandler.END
    await update.message.reply_text("Manda o link do produto.")
    return LINK_AGUARDANDO_LINK


async def link_receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = URL_REGEX.search(text)
    if not match:
        await update.message.reply_text("Isso não parece um link. Manda o link do produto:")
        return LINK_AGUARDANDO_LINK

    context.user_data["link_url"] = match.group(0)
    await update.message.reply_text("Agora manda o preço (ex: 153 ou 153,90).")
    return LINK_AGUARDANDO_PRECO


async def link_receber_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    preco = update.message.text.strip()
    url = context.user_data.pop("link_url", None)

    if not url:
        await update.message.reply_text("Algo deu errado, o link se perdeu. Use /link de novo.")
        return ConversationHandler.END

    await update.message.reply_text("Buscando informações do link...")
    await enviar_produto_para_grupo(context, url, preco)
    await update.message.reply_text("Enviado para o grupo!")
    return ConversationHandler.END


# ==== /linkcupon — link + preço + cupom ====

async def linkcupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await usuario_autorizado(update):
        return ConversationHandler.END
    await update.message.reply_text("Manda o link do produto.")
    return LINKCUPON_AGUARDANDO_LINK


async def linkcupon_receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = URL_REGEX.search(text)
    if not match:
        await update.message.reply_text("Isso não parece um link. Manda o link do produto:")
        return LINKCUPON_AGUARDANDO_LINK

    context.user_data["linkcupon_url"] = match.group(0)
    await update.message.reply_text("Agora manda o preço (ex: 153 ou 153,90).")
    return LINKCUPON_AGUARDANDO_PRECO


async def linkcupon_receber_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["linkcupon_preco"] = update.message.text.strip()
    await update.message.reply_text("Agora manda o cupom.")
    return LINKCUPON_AGUARDANDO_CUPOM


async def linkcupon_receber_cupom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cupom = update.message.text.strip()
    url = context.user_data.pop("linkcupon_url", None)
    preco = context.user_data.pop("linkcupon_preco", None)

    if not url or not preco:
        await update.message.reply_text("Algo deu errado no meio do caminho. Use /linkcupon de novo.")
        return ConversationHandler.END

    await update.message.reply_text("Buscando informações do link...")
    await enviar_produto_para_grupo(context, url, preco, cupom=cupom)
    await update.message.reply_text("Enviado para o grupo!")
    return ConversationHandler.END


# ==== Cancelar / fallback ====

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


async def mensagem_sem_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await usuario_autorizado(update):
        return
    await update.message.reply_text(
        "Use um comando para eu saber o que fazer:\n"
        "/link — link de produto + preço\n"
        "/linkcupon — link de produto + preço + cupom\n"
        "/cupom — cupom em texto livre, sem link"
    )


async def pos_inicializacao(app: Application):
    await app.bot.set_my_commands(COMANDOS)


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Defina a variável de ambiente TELEGRAM_BOT_TOKEN com o token do bot."
        )
    if not GROUP_CHAT_ID:
        raise RuntimeError(
            "Defina a variável de ambiente TELEGRAM_GROUP_CHAT_ID com o id do grupo."
        )

    app = Application.builder().token(BOT_TOKEN).post_init(pos_inicializacao).build()

    cupom_conv = ConversationHandler(
        entry_points=[CommandHandler("cupom", cupom_start_v2)],
        states={
            CUPOM_AGUARDANDO_TEXTO: [
                MessageHandler(filters.ALL & ~filters.COMMAND, cupom_receber)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    link_conv = ConversationHandler(
        entry_points=[CommandHandler("link", link_start)],
        states={
            LINK_AGUARDANDO_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, link_receber_link)
            ],
            LINK_AGUARDANDO_PRECO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, link_receber_preco)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    linkcupon_conv = ConversationHandler(
        entry_points=[CommandHandler("linkcupon", linkcupon_start)],
        states={
            LINKCUPON_AGUARDANDO_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, linkcupon_receber_link)
            ],
            LINKCUPON_AGUARDANDO_PRECO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, linkcupon_receber_preco)
            ],
            LINKCUPON_AGUARDANDO_CUPOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, linkcupon_receber_cupom)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(cupom_conv)
    app.add_handler(link_conv)
    app.add_handler(linkcupon_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensagem_sem_comando))

    logger.info("Bot iniciado. Aguardando mensagens...")
    app.run_polling()


if __name__ == "__main__":
    main()
