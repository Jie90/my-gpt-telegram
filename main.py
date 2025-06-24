import os, json, logging, tempfile
from io import BytesIO

import openai
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ─────────── 环境变量 ───────────
TG_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAIKEY = os.environ["OPENAI_API_KEY"]
ALLOW_IDS = [int(x) for x in os.getenv("ALLOWED_USER_IDS","").split(",") if x]
MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

openai.api_key = OPENAIKEY
MEM_FILE = "memory.json"

if not os.path.exists(MEM_FILE):
    json.dump({}, open(MEM_FILE, "w"))

def load_mem(uid:int)->str:
    return json.load(open(MEM_FILE)).get(str(uid),"")
def save_mem(uid:int, txt:str):
    data = json.load(open(MEM_FILE))
    data[str(uid)] = txt
    json.dump(data, open(MEM_FILE,"w"))

# ─────────── 指令处理 ───────────
async def start(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "你好！发文字或语音即可聊天。\n"
        "用 /remember 让机器人永久记住一段信息。"
    )

async def remember(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("在命令后写要记住的内容。")
    save_mem(update.effective_user.id, " ".join(ctx.args))
    await update.message.reply_text("已记住 ✅")

# ─────────── GPT 处理通用函数 ───────────
async def ask_gpt(uid:int, user_msg:str)->str:
    memory = load_mem(uid)
    messages=[
        {"role":"system",
         "content":f"You are a helpful AI assistant. "
                   f"Here are permanent facts about the user: {memory}"},
        {"role":"user","content":user_msg}
    ]
    rsp=openai.chat.completions.create(
        model=MODEL, messages=messages)
    return rsp.choices[0].message.content.strip()

# ─────────── 文字消息 ───────────
async def on_text(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if ALLOW_IDS and uid not in ALLOW_IDS:
        return
    reply=await ask_gpt(uid, update.message.text)
    await update.message.reply_text(reply)

# ─────────── 语音消息 ───────────
async def on_voice(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if ALLOW_IDS and uid not in ALLOW_IDS:
        return
    voice_file=await ctx.bot.get_file(update.message.voice.file_id)
    ogg=BytesIO(await voice_file.download_as_bytearray())
    with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
        tmp.write(ogg.getbuffer()); tmp.flush()
        text=openai.audio.transcriptions.create(
            model="whisper-1",
            file=open(tmp.name,"rb"),
            response_format="text"
        )
    reply=await ask_gpt(uid, text)
    await update.message.reply_text(reply)

# ─────────── 主入口 ───────────
def main():
    logging.basicConfig(level=logging.INFO)
    app=ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("remember", remember))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    print("Bot Online …")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
