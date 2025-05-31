import asyncio
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler
import re
import json
import requests
from bs4 import BeautifulSoup
import os

# Bot token
TOKEN = "7695882385:AAGfCKZrgDfNfLjDdjdee5Cp5OIBqaXz4E8"

# Channel ID (numeric)
CHANNEL_IDS = [
    "-1002665968223",
    "-1002633120419"
]

# Admin Chat ID 
ADMIN_CHAT_ID = "1451384311"

# Webhook URL
WEBHOOK_URL = "https://telegrambot-production-51d4.up.railway.app/webhook"

# Function to get current gold price from website
def get_gold_price():
    url = "https://www.tgju.org/profile/geram18"  # URL for 18k gold price
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        price_tag = soup.find("span", {"data-col": "info.last_trade.PDrCotVal"})
        if price_tag:
            price_str = price_tag.text.strip().replace(",", "")
            return int(price_str), None
        else:
            return None, "قیمت طلا پیدا نشد!"
    
    except requests.exceptions.RequestException as e:
        return None, f"خطا در دریافت قیمت: {e}"

# Function to extract product info from post caption
def extract_product_info(caption):
    print(f"Extracting info from caption: {caption}")
    if not caption:
        print("No caption found!")
        return None
    
    lines = caption.split('\n')
    name = lines[0].strip() if lines else "محصول ناشناخته"
    print(f"Product name: {name}")
    
    weight = re.search(r'وزن:\s*([\d.]+)\s*گرم', caption)
    ajrat = re.search(r'اجرت:\s*([\d.]+)%', caption)
    profit = re.search(r'سود:\s*([\d.]+)%', caption)
    
    weight = float(weight.group(1)) if weight else 0
    ajrat = float(ajrat.group(1)) if ajrat else 0
    profit = float(profit.group(1)) if profit else 0
    
    print(f"Extracted - Weight: {weight}, Ajrat: {ajrat}, Profit: {profit}")
    
    return {
        "name": name,
        "weight": weight,
        "ajrat": ajrat,
        "profit": profit
    }

# Function to calculate final price
def calculate_price(weight, ajrat, profit, price_per_gram):
    base_price = weight * price_per_gram
    ajrat_amount = base_price * (ajrat / 100)
    profit_amount = base_price * (profit / 100)
    total_price = base_price + ajrat_amount + profit_amount
    return int(total_price)

# Function to handle new posts
async def handle_new_post(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("New post detected!")
    message = update.channel_post
    
    print(f"Chat ID: {message.chat_id}, Expected: {CHANNEL_IDS}")
    if str(message.chat_id) not in CHANNEL_IDS:
        print("Chat ID does not match!")
        return
    
    caption = message.caption if message.caption else ""
    print(f"Caption: {caption}")
    
    product_info = extract_product_info(caption)
    if not product_info or product_info["weight"] == 0:
        print("Product info incomplete or weight is 0!")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text="لطفاً اطلاعات محصول رو به این شکل وارد کنید:\n"
                     "نام محصول\nوزن: (عدد و برای ممیز نقطه) گرم\nاجرت: (عدد)%\nسود: (عدد)%"
            )
        except Exception as e:
            print(f"Error sending message to admin: {e}")
        return
    
    product_data = {
        "weight": product_info["weight"],
        "ajrat": product_info["ajrat"],
        "profit": product_info["profit"]
    }
    product_data_json = json.dumps(product_data)
    
    keyboard = [
        [InlineKeyboardButton("محاسبه قیمت آنلاین", callback_data=f'calculate_price|{product_data_json}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Edit post to add button
    try:
        await context.bot.edit_message_caption(
            chat_id=message.chat_id,
            message_id=message.message_id,
            caption=message.caption + "\n\nبرای مشاهده قیمت به‌روز، روی دکمه زیر کلیک کنید:",
            reply_markup=reply_markup
        )
        print("Post edited successfully!")
    except Exception as e:
        print(f"Error editing post: {e}")

# Function to handle button clicks
async def button_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    callback_data = query.data.split('|', 1)
    if len(callback_data) != 2 or callback_data[0] != 'calculate_price':
        await query.answer("خطا: داده‌های نامعتبر!", show_alert=True)
        return
    
    try:
        product_data = json.loads(callback_data[1])
    except json.JSONDecodeError:
        await query.answer("خطا: اطلاعات محصول نامعتبر است!", show_alert=True)
        return
    
    price_per_gram, error = get_gold_price()
    if price_per_gram is None:
        await query.answer(f"خطا: {error}", show_alert=True)
        return
    
    total_price = calculate_price(
        product_data['weight'],
        product_data['ajrat'],
        product_data['profit'],
        price_per_gram
    )
    
    # Show price in popup
    message = (
        f"قیمت کل: {total_price // 10 :,} تومان\n"
        f"قیمت فعلی طلا (هر گرم): {price_per_gram // 10 :,} تومان"
    )
    await query.answer(message, show_alert=True)

# Initialize the application
application = Application.builder().token(TOKEN).build()

# Add handlers
application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_new_post))
application.add_handler(CallbackQueryHandler(button_callback))

# Set webhook and run
async def start_webhook():
    print("Starting bot with webhook...")
    # Delete any existing webhook to avoid conflicts
    await application.bot.delete_webhook()
    # Set the new webhook
    await application.bot.set_webhook(url=WEBHOOK_URL)
    port = int(os.getenv("PORT", 8443))  # Use PORT from environment or default to 8443
    # Start the webhook
    await application.initialize()
    await application.start()
    await application.updater.start_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=WEBHOOK_URL.split('/')[-1],
        webhook_url=WEBHOOK_URL
    )
    print(f"Webhook set and running on port {port}...")
    # Keep the bot running
    await asyncio.Event().wait()

# Main function to run the bot
async def main():
    try:
        await start_webhook()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

# Run the bot
if __name__ == "__main__":
    asyncio.run(main())
