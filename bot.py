import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==== CONFIGURAÇÕES ====
# Nunca coloque o token direto no código. Use variável de ambiente.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ID do grupo fixo para onde as imagens serão enviadas.
# Para descobrir o chat_id do seu grupo, veja as instruções no README.
GROUP_CHAT_ID = os.environ.get("TELEGRAM_GROUP_CHAT_ID")

URL_REGEX = re.compile(r"https?://\S+")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


def extract_og_image(url: str) -> str | None:
    """Baixa a página e tenta extrair a imagem de capa (og:image)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Falha ao baixar {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Tenta várias tags comuns de preview, em ordem de prioridade
    candidates = [
        ("meta", {"property": "og:image"}),
        ("meta", {"name": "og:image"}),
        ("meta", {"property": "twitter:image"}),
        ("meta", {"name": "twitter:image"}),
    ]

    for tag, attrs in candidates:
        found = soup.find(tag, attrs=attrs)
        if found and found.get("content"):
            return found["content"]

    return None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = URL_REGEX.search(text)

    if not match:
        await update.message.reply_text(
            "Me manda um link de site que eu pego a imagem e envio pro grupo."
        )
        return

    url = match.group(0)
    await update.message.reply_text("Buscando imagem do link...")

    image_url = extract_og_image(url)

    if not image_url:
        await update.message.reply_text(
            "Não consegui encontrar uma imagem nesse link. "
            "O site pode não ter imagem de preview (og:image)."
        )
        return

    try:
        await context.bot.send_photo(
            chat_id=GROUP_CHAT_ID,
            photo=image_url,
            caption=url,
        )
        await update.message.reply_text("Enviado para o grupo!")
    except Exception as e:
        logger.error(f"Erro ao enviar para o grupo: {e}")
        await update.message.reply_text(
            f"Encontrei a imagem, mas não consegui enviar pro grupo. Erro: {e}"
        )


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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot iniciado. Aguardando mensagens...")
    app.run_polling()


if __name__ == "__main__":
    main()
