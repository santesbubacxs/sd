import discord
from discord.ext import commands
import json
import random
import asyncio
from datetime import datetime, timedelta
import math
import os

# Bot ayarları
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID'))
MAX_ALL_BET = 250000  # 'all' komutunda maksimum bahis

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='.', intents=intents, help_command=None)

# Veritabanı (JSON dosyası)
try:
    with open('database.json', 'r') as f:
        db = json.load(f)
except FileNotFoundError:
    db = {
        "users": {},
        "guilds": {},
        "shop": {
            "common": {"price": 100, "stock": 999},
            "uncommon": {"price": 300, "stock": 999},
            "rare": {"price": 500, "stock": 999},
            "epic": {"price": 1000, "stock": 999},
            "legendary": {"price": 2500, "stock": 999}
        }
    }

def save_db():
    with open('database.json', 'w') as f:
        json.dump(db, f, indent=4)

def get_user_data(user_id):
    if str(user_id) not in db["users"]:
        db["users"][str(user_id)] = {
            "cash": 1000,
            "bank": 0,
            "animals": [],
            "inventory": [],
            "level": 1,
            "xp": 0,
            "streak": 0,
            "last_daily": None,
            "last_vote": None,
            "quests": {"daily": {"progress": 0, "completed": False, "reward": 0}},
            "boss_streak": 0,
            "marriage": None,
            "emoji_unlocked": ["blush", "cry", "dance", "happy", "smile"],
            "total_xp": 0,
            "message_count": 0
        }
        save_db()
    return db["users"][str(user_id)]

def get_level_xp(level):
    """Seviye için gereken XP miktarı"""
    return level * 100

def add_xp(user_id, amount):
    """XP ekle ve seviye atlamasını kontrol et"""
    user_data = get_user_data(user_id)
    user_data["xp"] += amount
    user_data["total_xp"] += amount
    
    # Seviye atlama kontrolü
    leveled_up = False
    while user_data["xp"] >= get_level_xp(user_data["level"]):
        user_data["xp"] -= get_level_xp(user_data["level"])
        user_data["level"] += 1
        leveled_up = True
        
        # Seviye atlama bonusu
        level_bonus = user_data["level"] * 100
        user_data["cash"] += level_bonus
        
    save_db()
    return leveled_up

def parse_bet(ctx, bet_input):
    """Bahis miktarını parse et - sayı veya 'all'"""
    user_data = get_user_data(ctx.author.id)
    
    if str(bet_input).lower() == "all":
        bet = user_data["cash"]
        if bet > MAX_ALL_BET:
            bet = MAX_ALL_BET
        if bet < 1:
            return None, "❌ Hiç paran yok!"
        return bet, None
    else:
        try:
            bet = int(bet_input)
            if bet < 1:
                return None, "❌ En az 1 para bahis yap!"
            if bet > user_data["cash"]:
                return None, "❌ Yeterli paran yok!"
            return bet, None
        except ValueError:
            return None, "❌ Geçersiz miktar! Sayı veya 'all' girin."

# ==================== OWNER KOMUTLARI ====================
@bot.command(name="paragonder")
async def send_money(ctx, member: discord.Member, amount: int):
    """Sadece owner'ın kullanabileceği para gönderme komutu"""
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir!")
        return
    
    if amount < 1:
        await ctx.send("❌ En az 1 para gönderebilirsin!")
        return
    
    user_data = get_user_data(member.id)
    user_data["cash"] += amount
    save_db()
    
    await ctx.send(f"✅ {member.mention} hesabına {amount} para eklendi! Yeni bakiye: {user_data['cash']}")

@bot.command(name="xpver")
async def give_xp(ctx, member: discord.Member, amount: int):
    """Sadece owner'ın kullanabileceği XP verme komutu"""
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir!")
        return
    
    if amount < 1:
        await ctx.send("❌ En az 1 XP verebilirsin!")
        return
    
    leveled_up = add_xp(member.id, amount)
    user_data = get_user_data(member.id)
    
    msg = f"✅ {member.mention} kullanıcısına {amount} XP verildi! (Level: {user_data['level']})"
    if leveled_up:
        msg += f"\n🎉 **LEVEL ATLADI!** Yeni level: {user_data['level']} (Bonus: {user_data['level'] * 100} para!)"
    
    await ctx.send(msg)

# ==================== RANKINGS ====================
@bot.command(name="top")
async def top_ranking(ctx, category: str = "my"):
    """Sıralama komutu"""
    if category == "my":
        user_data = get_user_data(ctx.author.id)
        wealth = user_data["cash"] + user_data["bank"]
        
        all_users = []
        for user_id, data in db["users"].items():
            total = data["cash"] + data["bank"]
            all_users.append((user_id, total))
        
        all_users.sort(key=lambda x: x[1], reverse=True)
        
        rank = 1
        for i, (uid, _) in enumerate(all_users, 1):
            if int(uid) == ctx.author.id:
                rank = i
                break
        
        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name} - İstatistikler",
            color=0x00ff00
        )
        embed.add_field(name="💰 Nakit", value=user_data["cash"], inline=True)
        embed.add_field(name="🏦 Banka", value=user_data["bank"], inline=True)
        embed.add_field(name="📈 Level", value=user_data["level"], inline=True)
        embed.add_field(name="⭐ XP", value=f"{user_data['xp']}/{get_level_xp(user_data['level'])}", inline=True)
        embed.add_field(name="📊 Toplam XP", value=user_data["total_xp"], inline=True)
        embed.add_field(name="💬 Mesaj", value=user_data["message_count"], inline=True)
        embed.add_field(name="#️⃣ Sıralama", value=f"#{rank}", inline=True)
        
        await ctx.send(embed=embed)
    
    elif category == "global":
        all_users = []
        for user_id, data in db["users"].items():
            total = data["cash"] + data["bank"]
            all_users.append((user_id, total))
        
        all_users.sort(key=lambda x: x[1], reverse=True)
        
        embed = discord.Embed(
            title="🏆 Küresel Sıralama",
            color=0xffd700
        )
        
        top_10 = all_users[:10]
        for i, (uid, total) in enumerate(top_10, 1):
            try:
                user = await bot.fetch_user(int(uid))
                name = user.display_name
            except:
                name = f"Kullanıcı #{uid}"
            embed.add_field(
                name=f"#{i} {name}",
                value=f"💰 {total} para",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    elif category == "level":
        all_users = []
        for user_id, data in db["users"].items():
            all_users.append((user_id, data["level"], data["total_xp"]))
        
        all_users.sort(key=lambda x: x[1], reverse=True)
        
        embed = discord.Embed(
            title="🏆 Level Sıralaması",
            color=0x00ff00
        )
        
        top_10 = all_users[:10]
        for i, (uid, level, xp) in enumerate(top_10, 1):
            try:
                user = await bot.fetch_user(int(uid))
                name = user.display_name
            except:
                name = f"Kullanıcı #{uid}"
            embed.add_field(
                name=f"#{i} {name}",
                value=f"📈 Level {level} (Toplam XP: {xp})",
                inline=False
            )
        
        await ctx.send(embed=embed)

# ==================== EKONOMİ ====================
@bot.command(name="daily")
async def daily_reward(ctx):
    """Günlük ödül - Seviyeye göre para verir"""
    user_data = get_user_data(ctx.author.id)
    
    now = datetime.now()
    if user_data["last_daily"]:
        last = datetime.fromisoformat(user_data["last_daily"])
        if (now - last).days == 0:
            await ctx.send("❌ Bugün zaten günlük ödülünü aldın! Yarın tekrar dene.")
            return
        
        if (now - last).days == 1:
            user_data["streak"] += 1
        else:
            user_data["streak"] = 0
    
    # Seviyeye göre ödül hesapla
    level = user_data["level"]
    base_reward = 200 + (level * 50)  # Her seviyede 50 para artar
    streak_bonus = min(user_data["streak"] * 50, 500)
    level_bonus = level * 10
    total_reward = base_reward + streak_bonus + level_bonus
    
    user_data["cash"] += total_reward
    user_data["last_daily"] = now.isoformat()
    user_data["streak"] += 1 if user_data["streak"] == 0 else 0
    
    # Daily için XP ver
    xp_gain = 50 + (level * 5)
    add_xp(ctx.author.id, xp_gain)
    
    save_db()
    
    embed = discord.Embed(
        title="📅 Günlük Ödül",
        color=0x00ff00
    )
    embed.add_field(name="💰 Para", value=f"+{total_reward}", inline=True)
    embed.add_field(name="⭐ XP", value=f"+{xp_gain}", inline=True)
    embed.add_field(name="🔥 Streak", value=f"{user_data['streak']} gün", inline=True)
    embed.add_field(name="📈 Level", value=f"{user_data['level']}", inline=True)
    embed.add_field(name="💵 Yeni Bakiye", value=user_data["cash"], inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="xp")
async def xp_command(ctx):
    """XP ve level durumunu göster"""
    user_data = get_user_data(ctx.author.id)
    current_level_xp = user_data["xp"]
    needed_xp = get_level_xp(user_data["level"])
    progress = int((current_level_xp / needed_xp) * 100)
    
    # Progress bar
    bar_length = 20
    filled = int(bar_length * progress / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    embed = discord.Embed(
        title=f"📊 {ctx.author.display_name} - XP Durumu",
        color=0x00ff00
    )
    embed.add_field(name="📈 Level", value=user_data["level"], inline=True)
    embed.add_field(name="⭐ XP", value=f"{current_level_xp}/{needed_xp}", inline=True)
    embed.add_field(name="📊 İlerleme", value=f"{bar} **{progress}%**", inline=False)
    embed.add_field(name="🎯 Toplam XP", value=user_data["total_xp"], inline=True)
    embed.add_field(name="💬 Mesaj Sayısı", value=user_data["message_count"], inline=True)
    
    # Sonraki seviye ödülü
    next_level_bonus = (user_data["level"] + 1) * 100
    embed.set_footer(text=f"🎁 Sonraki seviye bonusu: {next_level_bonus} para")
    
    await ctx.send(embed=embed)

@bot.command(name="give")
async def give_money(ctx, member: discord.Member, amount: int):
    """Başka bir kullanıcıya para ver"""
    if amount < 1:
        await ctx.send("❌ En az 1 para verebilirsin!")
        return
    
    giver_data = get_user_data(ctx.author.id)
    receiver_data = get_user_data(member.id)
    
    if giver_data["cash"] < amount:
        await ctx.send("❌ Yeterli paran yok!")
        return
    
    giver_data["cash"] -= amount
    receiver_data["cash"] += amount
    save_db()
    
    await ctx.send(f"✅ {member.mention} kullanıcısına **{amount}** para verdin!")

@bot.command(name="shop")
async def shop_command(ctx):
    """Mağaza"""
    embed = discord.Embed(
        title="🛒 Mağaza",
        description="Satın almak için `.buy <ürün>` yaz",
        color=0x00ff00
    )
    
    shop_items = {
        "common": 100,
        "uncommon": 300,
        "rare": 500,
        "epic": 1000,
        "legendary": 2500
    }
    
    for item, price in shop_items.items():
        embed.add_field(
            name=item.upper(),
            value=f"💰 {price} para",
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command(name="buy")
async def buy_item(ctx, item: str):
    """Mağazadan ürün satın al"""
    user_data = get_user_data(ctx.author.id)
    
    shop_items = {
        "common": 100,
        "uncommon": 300,
        "rare": 500,
        "epic": 1000,
        "legendary": 2500
    }
    
    if item.lower() not in shop_items:
        await ctx.send("❌ Geçersiz ürün! `.shop` ile ürünleri gör.")
        return
    
    price = shop_items[item.lower()]
    if user_data["cash"] < price:
        await ctx.send(f"❌ Yeterli paran yok! {price} para lazım.")
        return
    
    user_data["cash"] -= price
    user_data["inventory"].append(item.lower())
    
    # Satın alma için XP ver
    add_xp(ctx.author.id, 10)
    save_db()
    
    await ctx.send(f"✅ **{item.upper()}** satın aldın! Kalan para: {user_data['cash']} (+10 XP)")

# ==================== KUMAR ====================
@bot.command(name="slots")
async def slots_command(ctx, bet_input):
    """Slot makinesi - .slots <miktar/all>"""
    user_data = get_user_data(ctx.author.id)
    
    bet, error = parse_bet(ctx, bet_input)
    if error:
        await ctx.send(error)
        return
    
    if bet < 1:
        await ctx.send("❌ En az 1 para bahis yap!")
        return
    
    symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "⭐"]
    result = [random.choice(symbols) for _ in range(3)]
    
    if result[0] == result[1] == result[2]:
        multiplier = 10 if result[0] == "💎" else 5 if result[0] == "⭐" else 3
        win = bet * multiplier
        user_data["cash"] += win
        xp_gain = win // 10
        add_xp(ctx.author.id, xp_gain)
        msg = f"🎰 {result[0]} {result[1]} {result[2]} - JACKPOT! **{win}** para kazandın! (+{xp_gain} XP)"
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        win = bet * 2
        user_data["cash"] += win
        xp_gain = win // 20
        add_xp(ctx.author.id, xp_gain)
        msg = f"🎰 {result[0]} {result[1]} {result[2]} - İki eşit! **{win}** para kazandın! (+{xp_gain} XP)"
    else:
        user_data["cash"] -= bet
        xp_gain = bet // 30
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"🎰 {result[0]} {result[1]} {result[2]} - Kaybettin! **{bet}** para kaybettin. (+{max(1, xp_gain)} XP)"
    
    save_db()
    await ctx.send(msg)

@bot.command(name="cf", aliases=["coinflip"])
async def coinflip_command(ctx, choice: str, bet_input):
    """Yazı tura - .cf <yazı/tura> <miktar/all>"""
    if choice.lower() not in ["yazı", "tura", "heads", "tails"]:
        await ctx.send("❌ Lütfen 'yazı' veya 'tura' seç!")
        return
    
    user_data = get_user_data(ctx.author.id)
    
    bet, error = parse_bet(ctx, bet_input)
    if error:
        await ctx.send(error)
        return
    
    if bet < 1:
        await ctx.send("❌ En az 1 para bahis yap!")
        return
    
    result = random.choice(["yazı", "tura"])
    user_choice = "yazı" if choice.lower() in ["yazı", "heads"] else "tura"
    
    if result == user_choice:
        user_data["cash"] += bet
        xp_gain = bet // 20
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"🪙 **{result}** geldi! **{bet}** para kazandın! (+{max(1, xp_gain)} XP)"
    else:
        user_data["cash"] -= bet
        xp_gain = bet // 30
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"🪙 **{result}** geldi! **{bet}** para kaybettin. (+{max(1, xp_gain)} XP)"
    
    save_db()
    await ctx.send(msg)

@bot.command(name="lottery")
async def lottery_command(ctx, bet_input):
    """Piyango - .lottery <miktar/all>"""
    user_data = get_user_data(ctx.author.id)
    
    bet, error = parse_bet(ctx, bet_input)
    if error:
        await ctx.send(error)
        return
    
    if bet < 10:
        await ctx.send("❌ Minimum 10 para bahis yap!")
        return
    
    number = random.randint(1, 100)
    win_number = random.randint(1, 100)
    
    if number == win_number:
        win = bet * 50
        user_data["cash"] += win
        xp_gain = win // 10
        add_xp(ctx.author.id, xp_gain)
        msg = f"🎯 **{number}** - JACKPOT! **{win}** para kazandın! (+{xp_gain} XP)"
    elif abs(number - win_number) <= 5:
        win = bet * 5
        user_data["cash"] += win
        xp_gain = win // 20
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"🎯 **{number}** (Kazanan: {win_number}) - Yaklaştın! **{win}** para kazandın! (+{max(1, xp_gain)} XP)"
    elif abs(number - win_number) <= 10:
        win = bet * 2
        user_data["cash"] += win
        xp_gain = win // 30
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"🎯 **{number}** (Kazanan: {win_number}) - Biraz daha! **{win}** para kazandın! (+{max(1, xp_gain)} XP)"
    else:
        user_data["cash"] -= bet
        xp_gain = bet // 40
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"🎯 **{number}** (Kazanan: {win_number}) - Kaybettin! **{bet}** para kaybettin. (+{max(1, xp_gain)} XP)"
    
    save_db()
    await ctx.send(msg)

@bot.command(name="bj", aliases=["blackjack"])
async def blackjack_command(ctx, bet_input):
    """Blackjack - .bj <miktar/all>"""
    user_data = get_user_data(ctx.author.id)
    
    bet, error = parse_bet(ctx, bet_input)
    if error:
        await ctx.send(error)
        return
    
    if bet < 10:
        await ctx.send("❌ Minimum 10 para bahis yap!")
        return
    
    player_cards = [random.randint(1, 11), random.randint(1, 11)]
    dealer_cards = [random.randint(1, 11), random.randint(1, 11)]
    
    player_total = sum(player_cards)
    dealer_total = sum(dealer_cards)
    
    if player_total > 21:
        user_data["cash"] -= bet
        xp_gain = bet // 30
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"🃏 Elin: {player_cards} = {player_total}\nKartların 21'i geçti! Kaybettin! (+{max(1, xp_gain)} XP)"
    elif player_total == 21:
        win = int(bet * 1.5)
        user_data["cash"] += win
        xp_gain = win // 10
        add_xp(ctx.author.id, xp_gain)
        msg = f"🃏 Elin: {player_cards} = {player_total}\nBLACKJACK! **{win}** para kazandın! (+{xp_gain} XP)"
    else:
        while dealer_total < 17:
            dealer_cards.append(random.randint(1, 11))
            dealer_total = sum(dealer_cards)
        
        if dealer_total > 21 or player_total > dealer_total:
            user_data["cash"] += bet
            xp_gain = bet // 15
            add_xp(ctx.author.id, max(1, xp_gain))
            msg = f"🃏 Elin: {player_cards} = {player_total}\nKasa: {dealer_cards} = {dealer_total}\nKazandın! **{bet}** para kazandın! (+{max(1, xp_gain)} XP)"
        elif player_total == dealer_total:
            xp_gain = 5
            add_xp(ctx.author.id, xp_gain)
            msg = f"🃏 Elin: {player_cards} = {player_total}\nKasa: {dealer_cards} = {dealer_total}\nBerabere! (+{xp_gain} XP)"
        else:
            user_data["cash"] -= bet
            xp_gain = bet // 30
            add_xp(ctx.author.id, max(1, xp_gain))
            msg = f"🃏 Elin: {player_cards} = {player_total}\nKasa: {dealer_cards} = {dealer_total}\nKaybettin! **{bet}** para kaybettin. (+{max(1, xp_gain)} XP)"
    
    save_db()
    await ctx.send(msg)

@bot.command(name="mines")
async def mines_command(ctx, bet_input):
    """Mayın tarlası - .mines <miktar/all>"""
    user_data = get_user_data(ctx.author.id)
    
    bet, error = parse_bet(ctx, bet_input)
    if error:
        await ctx.send(error)
        return
    
    if bet < 10:
        await ctx.send("❌ Minimum 10 para bahis yap!")
        return
    
    grid = ["⬛"] * 25
    mine_positions = random.sample(range(25), 5)
    
    first_click = random.choice([i for i in range(25) if i not in mine_positions])
    grid[first_click] = "🟩"
    
    safe_positions = [i for i in range(25) if i not in mine_positions and i != first_click]
    for pos in random.sample(safe_positions, min(3, len(safe_positions))):
        grid[pos] = "🟩"
    
    for pos in mine_positions:
        grid[pos] = "💣"
    
    grid_str = ""
    for i in range(0, 25, 5):
        grid_str += "".join(grid[i:i+5]) + "\n"
    
    user_data["cash"] -= bet
    xp_gain = bet // 20
    add_xp(ctx.author.id, max(1, xp_gain))
    save_db()
    
    embed = discord.Embed(
        title="💣 Mayın Tarlası",
        description=f"**{bet}** para kaybettin! (+{max(1, xp_gain)} XP)\n\n{grid_str}",
        color=0xff0000
    )
    await ctx.send(embed=embed)

@bot.command(name="highlow")
async def highlow_command(ctx, bet_input, guess: str):
    """Yüksek/Düşük - .highlow <miktar/all> <high/low>"""
    user_data = get_user_data(ctx.author.id)
    
    bet, error = parse_bet(ctx, bet_input)
    if error:
        await ctx.send(error)
        return
    
    if bet < 10:
        await ctx.send("❌ Minimum 10 para bahis yap!")
        return
    
    if guess.lower() not in ["high", "low", "yuksek", "dusuk"]:
        await ctx.send("❌ 'high' veya 'low' seç!")
        return
    
    number = random.randint(1, 100)
    previous_number = random.randint(1, 100)
    
    user_guess = "high" if guess.lower() in ["high", "yuksek"] else "low"
    result = "high" if number > previous_number else "low"
    
    if user_guess == result:
        win = bet * 2
        user_data["cash"] += win
        xp_gain = win // 15
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"📈 Sayı: {number} (Önceki: {previous_number})\nDoğru tahmin! **{win}** para kazandın! (+{max(1, xp_gain)} XP)"
    else:
        user_data["cash"] -= bet
        xp_gain = bet // 30
        add_xp(ctx.author.id, max(1, xp_gain))
        msg = f"📈 Sayı: {number} (Önceki: {previous_number})\nYanlış tahmin! **{bet}** para kaybettin. (+{max(1, xp_gain)} XP)"
    
    save_db()
    await ctx.send(msg)

# ==================== SOSYAL KOMUTLAR ====================
@bot.command(name="profile")
async def profile_command(ctx, member: discord.Member = None):
    """Profil"""
    if member is None:
        member = ctx.author
    
    user_data = get_user_data(member.id)
    current_level_xp = user_data["xp"]
    needed_xp = get_level_xp(user_data["level"])
    progress = int((current_level_xp / needed_xp) * 100)
    
    # Progress bar
    bar_length = 15
    filled = int(bar_length * progress / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    
    embed = discord.Embed(
        title=f"👤 {member.display_name}'nin Profili",
        color=0x00ff00
    )
    embed.add_field(name="💰 Nakit", value=user_data["cash"], inline=True)
    embed.add_field(name="🏦 Banka", value=user_data["bank"], inline=True)
    embed.add_field(name="📈 Level", value=user_data["level"], inline=True)
    embed.add_field(name="⭐ XP", value=f"{current_level_xp}/{needed_xp} ({bar})", inline=False)
    embed.add_field(name="📊 Toplam XP", value=user_data["total_xp"], inline=True)
    embed.add_field(name="💬 Mesaj", value=user_data["message_count"], inline=True)
    embed.add_field(name="🎯 Boss Streak", value=user_data["boss_streak"], inline=True)
    embed.add_field(name="💍 Evli", value="Evet" if user_data["marriage"] else "Hayır", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="marry")
async def marry_command(ctx, member: discord.Member):
    """Evlenme teklifi"""
    if member.id == ctx.author.id:
        await ctx.send("❌ Kendine evlenme teklif edemezsin!")
        return
    
    user_data = get_user_data(ctx.author.id)
    target_data = get_user_data(member.id)
    
    if user_data["marriage"]:
        await ctx.send("❌ Zaten evlisin!")
        return
    
    if target_data["marriage"]:
        await ctx.send("❌ Bu kişi zaten evli!")
        return
    
    user_data["marriage"] = member.id
    target_data["marriage"] = ctx.author.id
    add_xp(ctx.author.id, 100)
    add_xp(member.id, 100)
    save_db()
    
    await ctx.send(f"💍 {ctx.author.mention} ve {member.mention} evlendiler! Tebrikler! (+100 XP)")

# ==================== EMOJİ KOMUTLARI ====================
@bot.command(name="blush")
async def blush_command(ctx):
    add_xp(ctx.author.id, 2)
    await ctx.send(f"{ctx.author.mention} 😊 *utanıyor* (+2 XP)")

@bot.command(name="cry")
async def cry_command(ctx):
    add_xp(ctx.author.id, 2)
    await ctx.send(f"{ctx.author.mention} 😢 *ağlıyor* (+2 XP)")

@bot.command(name="dance")
async def dance_command(ctx):
    add_xp(ctx.author.id, 2)
    await ctx.send(f"{ctx.author.mention} 💃 *dans ediyor* (+2 XP)")

@bot.command(name="happy")
async def happy_command(ctx):
    add_xp(ctx.author.id, 2)
    await ctx.send(f"{ctx.author.mention} 😄 *mutlu* (+2 XP)")

@bot.command(name="smile")
async def smile_command(ctx):
    add_xp(ctx.author.id, 2)
    await ctx.send(f"{ctx.author.mention} 🙂 *gülümsüyor* (+2 XP)")

@bot.command(name="hug")
async def hug_command(ctx, member: discord.Member = None):
    if member is None:
        add_xp(ctx.author.id, 3)
        await ctx.send(f"{ctx.author.mention} 🤗 *kendine sarılıyor* (+3 XP)")
    else:
        add_xp(ctx.author.id, 5)
        add_xp(member.id, 5)
        await ctx.send(f"{ctx.author.mention} 🤗 {member.mention} *sarılıyor* (+5 XP)")

@bot.command(name="kiss")
async def kiss_command(ctx, member: discord.Member = None):
    if member is None:
        add_xp(ctx.author.id, 3)
        await ctx.send(f"{ctx.author.mention} 😘 *kendini öpüyor* (+3 XP)")
    else:
        add_xp(ctx.author.id, 5)
        add_xp(member.id, 5)
        await ctx.send(f"{ctx.author.mention} 😘 {member.mention} *öpüyor* (+5 XP)")

@bot.command(name="pat")
async def pat_command(ctx, member: discord.Member = None):
    if member is None:
        add_xp(ctx.author.id, 3)
        await ctx.send(f"{ctx.author.mention} 🖐️ *kendini okşuyor* (+3 XP)")
    else:
        add_xp(ctx.author.id, 5)
        add_xp(member.id, 5)
        await ctx.send(f"{ctx.author.mention} 🖐️ {member.mention} *okşuyor* (+5 XP)")

# ==================== YARDIM ====================
@bot.command(name="help")
async def help_command(ctx, command: str = None):
    """Yardım menüsü"""
    if command:
        cmd = bot.get_command(command)
        if cmd:
            embed = discord.Embed(
                title=f"📖 {cmd.name}",
                description=cmd.help or "Bu komut hakkında bilgi yok.",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ '{command}' komutu bulunamadı!")
        return
    
    embed = discord.Embed(
        title="📚 SantesHub Komut Listesi",
        description="`.help <komut>` ile detaylı bilgi alabilirsin.\n`all` kullanarak tüm paranı riske atabilirsin (max 250k)",
        color=0x00ff00
    )
    
    categories = {
        "💎 Ekonomi": ["daily", "give", "shop", "buy", "xp"],
        "🎰 Kumar": ["slots", "cf/coinflip", "lottery", "bj/blackjack", "mines", "highlow"],
        "👤 Sosyal": ["profile", "marry"],
        "😊 Emoji/Aksiyon": ["blush", "cry", "dance", "happy", "smile", "hug", "kiss", "pat"],
        "📊 Sıralama": ["top", "top global", "top level"]
    }
    
    for category, commands in categories.items():
        embed.add_field(
            name=category,
            value=", ".join([f"`{cmd}`" for cmd in commands]),
            inline=False
        )
    
    embed.add_field(
        name="🎯 Kullanım Örnekleri",
        value="`.bj all` - Tüm paranı blackjack'te oyna (max 250k)\n`.cf yazı all` - Tüm paranı yazı-turada oyna (max 250k)\n`.xp` - XP ve level durumunu göster\n`.top level` - Level sıralamasını göster",
        inline=False
    )
    
    embed.set_footer(text="SantesHub v1.0 | 🎮 Her işlem XP kazandırır! | Bot Sahibi: .paragonder ile para gönderebilir")
    await ctx.send(embed=embed)

# ==================== MESAJ OLAYI (XP İÇİN) ====================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Her mesaj için XP ver
    user_data = get_user_data(message.author.id)
    user_data["message_count"] += 1
    
    # Rastgele XP (5-15 arası)
    xp_gain = random.randint(5, 15)
    leveled_up = add_xp(message.author.id, xp_gain)
    
    if leveled_up:
        level = user_data["level"]
        bonus = level * 100
        await message.channel.send(f"🎉 {message.author.mention} **Level {level}** oldu! (+{bonus} para bonus!)")
    
    save_db()
    await bot.process_commands(message)

# ==================== BOT OLAYI ====================
@bot.event
async def on_ready():
    print(f"✅ {bot.user} olarak giriş yapıldı!")
    print(f"📊 {len(db['users'])} kullanıcı yüklendi!")
    print(f"👑 Bot sahibi ID: {OWNER_ID}")
    print(f"💰 Max 'all' bahis: {MAX_ALL_BET}")
    await bot.change_presence(activity=discord.Game(name=".help | SantesHub"))

# Bot'u çalıştır
if __name__ == "__main__":
    bot.run(TOKEN)
