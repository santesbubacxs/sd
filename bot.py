import discord
from discord.ext import commands
from discord.ui import Button, View
import requests
import json
import random
import time
import asyncio
import os
from dotenv import load_dotenv

# ==================== AYARLAR ====================
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = 359199132906422273

if not TOKEN:
    print("❌ HATA: .env dosyasında BOT_TOKEN bulunamadı!")
    exit()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents, help_command=None)

# ==================== MAIL.TM API FONKSİYONLARI ====================
BASE_URL = "https://api.mail.tm"

def create_temp_email():
    domain_req = requests.get(f"{BASE_URL}/domains")
    domain_data = domain_req.json()
    domain = domain_data['hydra:member'][0]['domain']

    random_username = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email = f"{random_username}@{domain}"
    password = "Pass1234"

    payload = {"address": email, "password": password}
    headers = {"Content-Type": "application/json"}
    response = requests.post(f"{BASE_URL}/accounts", json=payload, headers=headers)
    
    if response.status_code == 201:
        data = response.json()
        return email, password, data['id']
    return None, None, None

def get_token(email, password):
    login_data = {"address": email, "password": password}
    response = requests.post(f"{BASE_URL}/token", json=login_data)
    if response.status_code == 200:
        return response.json()['token']
    return None

def check_inbox(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/messages", headers=headers)
    if response.status_code == 200:
        return response.json()['hydra:member']
    return []

def get_message_content(msg_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

# ==================== MAIL TAKİP SINIFI (DM İÇİN) ====================
class MailMonitor:
    def __init__(self, user_id, email, password, channel):
        self.user_id = user_id
        self.email = email
        self.password = password
        self.channel = channel  # Botun paneli gönderdiği kanal
        self.token = None
        self.seen_messages = set()  # Daha önce gönderilen mesaj ID'lerini tutar
        self.is_running = True

    async def start_monitoring(self):
        """Arka planda 7/24 maili dinler. Yeni mail gelince DM atar."""
        # Token al
        self.token = get_token(self.email, self.password)
        if not self.token:
            return

        # İlk başta gelen mailleri "görüldü" olarak işaretle (Eskileri tekrar atma)
        initial_messages = check_inbox(self.token)
        for msg in initial_messages:
            self.seen_messages.add(msg['id'])

        # Sürekli döngü başlat
        while self.is_running:
            try:
                messages = check_inbox(self.token)
                for msg in messages:
                    # Eğer bu mail daha önce görülmediyse
                    if msg['id'] not in self.seen_messages:
                        self.seen_messages.add(msg['id'])
                        
                        # Mesaj içeriğini al
                        content = get_message_content(msg['id'], self.token)
                        
                        # Kullanıcıyı bul
                        user = bot.get_user(self.user_id)
                        if user:
                            # DM Embed'i oluştur
                            embed = discord.Embed(
                                title="📩 SantesHub TempMail - Yeni Mesaj!",
                                description=f"📧 **Mail Adresin:** `{self.email}`",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="📌 Konu", value=msg.get('subject', 'Konusuz'), inline=False)
                            embed.add_field(name="👤 Gönderen", value=msg.get('from', {}).get('address', 'Bilinmiyor'), inline=False)
                            
                            # Mesaj içeriğini temizle ve göster
                            text_body = "Mesaj içeriği görüntülenemiyor."
                            if content and 'html' in content and content['html']:
                                import re
                                text_body = re.sub('<[^<]+?>', '', str(content['html'][0]))[:1000]
                            elif content and 'text' in content and content['text']:
                                text_body = content['text'][0][:1000]
                            
                            # İçeriği çok uzunsa parçala
                            if len(text_body) > 1000:
                                text_body = text_body[:997] + "..."
                                
                            embed.add_field(name="📝 Mesaj İçeriği", value=text_body, inline=False)
                            embed.set_footer(text="SantesHub TempMail | Bot DM'den iletti")
                            
                            try:
                                await user.send(embed=embed)
                            except:
                                # DM kapalıysa kanala düşsün
                                await self.channel.send(f"{user.mention} DM'lerin kapalı, mesaj burada:\n{text_body[:200]}...")

                # 15 saniye bekle ve tekrar kontrol et
                await asyncio.sleep(15)
                
            except Exception as e:
                print(f"Mail takip hatası: {e}")
                await asyncio.sleep(30)

    def stop_monitoring(self):
        self.is_running = False

# ==================== BUTONLU GÖRÜNÜM (VIEW) ====================
class TempMailView(View):
    def __init__(self):
        super().__init__(timeout=300)
        self.monitor = None

    @discord.ui.button(label="📧 Yeni Geçici Mail Oluştur", style=discord.ButtonStyle.success)
    async def generate_mail(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=False)

        # 1. Mail oluştur
        email, password, user_id = create_temp_email()
        if not email:
            await interaction.followup.send("❌ Mail oluşturulurken hata oluştu.", ephemeral=True)
            return

        # 2. Embed'i kanala at
        embed = discord.Embed(
            title="📧 SantesHub TempMail Oluşturuldu!",
            description=f"🟢 **Mail Adresin:** `{email}`\n\n📬 **Bu maile gelen tüm mesajlar bot tarafından size Özel Mesaj (DM) olarak iletilecektir!**",
            color=discord.Color.blue()
        )
        embed.set_footer(text="SantesHub TempMail System | DM'lerin açık olsun!")
        await interaction.followup.send(embed=embed)

        # 3. DM Takip sistemini başlat
        monitor = MailMonitor(interaction.user.id, email, password, interaction.channel)
        self.monitor = monitor
        asyncio.create_task(monitor.start_monitoring())

# ==================== KOMUTLAR ====================

@bot.command(name="tempmail")
async def tempmail_panel(ctx):
    embed = discord.Embed(
        title="📧 SantesHub TempMail System",
        description="Aşağıdaki butona basarak **geçici bir mail adresi** oluşturun.\n\n✅ **Özellik:** Oluşturulan maile gelen her mesaj, **Discord DM (Özel Mesaj)** üzerinden size iletilir!",
        color=discord.Color.purple()
    )
    embed.set_footer(text="SantesHub TempMail | DM'lerinizin açık olduğundan emin olun!")
    await ctx.send(embed=embed, view=TempMailView())

# ==================== OWNER KOMUTLARI ====================
@bot.command(name="mailgonder")
async def owner_send_mail(ctx, member: discord.Member = None):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ Bu komutu sadece Bot Sahibi kullanabilir!")
        return

    member = member or ctx.author
    email, _, _ = create_temp_email()
    if not email:
        await ctx.send("❌ Mail oluşturma hatası.")
        return

    embed = discord.Embed(
        title="👑 Owner Özel TempMail",
        description=f"**{member.mention}** için özel mail oluşturuldu.\n📧 **Mail:** `{email}`",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name="maildurum")
async def owner_mail_status(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ Bu komutu sadece Bot Sahibi kullanabilir!")
        return

    embed = discord.Embed(
        title="📊 SantesHub TempMail Sistem Durumu",
        description="✅ **API Durumu:** `mail.tm` ile bağlantı aktif.\n✅ **Bot Durumu:** Çevrimiçi.\n🟢 **Özellik:** DM İletim sistemi aktif.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="temizle")
async def owner_clear(ctx, limit: int = 10):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ Bu komutu sadece Bot Sahibi kullanabilir!")
        return

    if limit > 100: limit = 100
    await ctx.channel.purge(limit=limit)
    await ctx.send(f"✅ Son **{limit}** mesaj temizlendi.", delete_after=3)

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="📖 SantesHub TempMail Yardım",
        color=discord.Color.blue()
    )
    embed.add_field(name="📧 `.tempmail`", value="TempMail sistemini açar. Mail oluşturur ve tüm mesajlar DM'den gelir.", inline=False)
    embed.add_field(name="👑 **Owner Komutları**", value="`.mailgonder`, `.maildurum`, `.temizle`", inline=False)
    embed.set_footer(text="SantesHub TempMail")
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} olarak giriş yapıldı!")
    print(f"👑 Owner ID: {OWNER_ID}")
    await bot.change_presence(activity=discord.Game(name=".help | DM TempMail"))

if __name__ == "__main__":
    bot.run(TOKEN)
