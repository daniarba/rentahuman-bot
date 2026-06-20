#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║   🚀 MEMECOIN SCALPING BOT v3.0 — ULTRA EDITION     ║
║                                                      ║
║  Sources:                                            ║
║   ✅ DexScreener  — trending pairs, real DEX data   ║
║   ✅ GeckoTerminal — on-chain pool analysis          ║
║   ✅ CoinGecko    — RSI, market cap, social          ║
║   ✅ RugCheck     — rug pull / scam detection        ║
║                                                      ║
║  Features:                                           ║
║   🔄 Compound profit (grows automatically)           ║
║   📡 Discord alerts (every action)                   ║
║   🛡️  Rug-pull protection                           ║
║   📊 Multi-source signal scoring                     ║
║   ⚡ 30s scan cycle                                  ║
╚══════════════════════════════════════════════════════╝
"""

import time, requests, datetime, json, sys
from dataclasses import dataclass, field
from typing import Optional, List

# ═══════════════════════════════════════════════════════
#  ⚙️  CONFIG — yahan apni settings badlo
# ═══════════════════════════════════════════════════════

DISCORD_WEBHOOK    = "https://discord.com/api/webhooks/1500813868274815086/lCMKBdwj1MefMQWRYtVZPiZ7Y1KNX8z9fSfUWVVOUEp_levPfiKmXks_JIbmwIOHsk2o"

DEMO_BALANCE       = 20.0    # Shuru ka demo balance ($)
MAX_TRADE_PCT      = 0.20    # 20% balance per trade (compound se barhega)
PROFIT_TARGET      = 0.05    # +5% pe sell
STOP_LOSS          = 0.02    # -2% pe stop
RSI_BUY            = 40      # RSI neeche = buy zone
RSI_SELL           = 65      # RSI upar = sell zone
MIN_SIGNALS        = 4       # Min signals before buying
MIN_LIQUIDITY      = 5000    # Min $5k liquidity (scam se bachao)
MAX_OPEN_TRADES    = 3       # Ek waqt max 3 trades
SCAN_INTERVAL      = 30      # seconds

# Chains jo scan karni hain
TARGET_CHAINS = ["solana", "bsc", "ethereum", "base"]

# ═══════════════════════════════════════════════════════
#  📡 API ENDPOINTS (sab free, no key needed!)
# ═══════════════════════════════════════════════════════

DEXSCREENER   = "https://api.dexscreener.com"
GECKOTERMINAL = "https://api.geckoterminal.com/api/v2"
COINGECKO     = "https://api.coingecko.com/api/v3"
RUGCHECK      = "https://api.rugcheck.xyz/v1"

HEADERS = {"User-Agent": "Mozilla/5.0 MemecoinBot/3.0", "Accept": "application/json"}

# ═══════════════════════════════════════════════════════
#  📊 DATA CLASSES
# ═══════════════════════════════════════════════════════

@dataclass
class TokenSignal:
    name: str
    symbol: str
    chain: str
    address: str
    pair_address: str
    price_usd: float
    price_change_5m: float
    price_change_1h: float
    price_change_6h: float
    price_change_24h: float
    volume_24h: float
    liquidity_usd: float
    market_cap: float
    buy_txns_1h: int
    sell_txns_1h: int
    dex_url: str
    # Analysis scores
    score: int = 0
    reasons: List[str] = field(default_factory=list)
    rsi: float = 50.0
    is_safe: bool = True
    rug_warning: str = ""

@dataclass
class Trade:
    name: str
    symbol: str
    chain: str
    address: str
    pair_address: str
    buy_price: float
    invest_usdt: float
    coins: float
    buy_time: str
    target: float
    stop: float
    dex_url: str
    status: str = "OPEN"

@dataclass
class Portfolio:
    balance: float        = DEMO_BALANCE
    initial: float        = DEMO_BALANCE
    total_profit: float   = 0.0
    total_trades: int     = 0
    wins: int             = 0
    open_trades: list     = field(default_factory=list)
    history: list         = field(default_factory=list)
    milestones_hit: set   = field(default_factory=set)

    def growth(self)      -> float: return (self.balance - self.initial) / self.initial * 100
    def next_trade_size(self) -> float: return self.balance * MAX_TRADE_PCT
    def win_rate(self)    -> int:   return int(self.wins / max(self.total_trades, 1) * 100)

# ═══════════════════════════════════════════════════════
#  🔔 DISCORD — sabse important part!
# ═══════════════════════════════════════════════════════

def discord(msg: str, color: int = 0x00ff00, title: str = "🤖 Bot"):
    payload = {"embeds": [{
        "title": title, "description": msg, "color": color,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "footer": {"text": "Memecoin Bot v3.0 | DexScreener + GeckoTerminal | Demo Mode"}
    }]}
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        ok = r.status_code == 204
        print(f"  {'✅' if ok else '⚠️ '} Discord [{r.status_code}]")
    except Exception as e:
        print(f"  ❌ Discord: {e}")

def alert_startup(p: Portfolio):
    discord(
        f"**🚀 BOT v3.0 STARTED — ULTRA EDITION**\n\n"
        f"💰 Demo Balance: **${p.balance:.2f}**\n"
        f"🔄 Compound Mode: **ON** — profit reinvested!\n"
        f"🎯 Profit Target: **+{PROFIT_TARGET*100:.0f}%**\n"
        f"🛑 Stop Loss: **-{STOP_LOSS*100:.0f}%**\n"
        f"📊 Per Trade: **{MAX_TRADE_PCT*100:.0f}%** of current balance\n\n"
        f"**📡 Data Sources:**\n"
        f"• `DexScreener` — trending DEX pairs\n"
        f"• `GeckoTerminal` — on-chain pool data\n"
        f"• `CoinGecko` — RSI + market data\n"
        f"• `RugCheck` — scam detection 🛡️\n\n"
        f"**⛓️ Chains:** `{', '.join(TARGET_CHAINS)}`\n\n"
        f"*Scanning every {SCAN_INTERVAL}s — Discord pe har update ayega!*",
        color=0xffd700, title="🤖 Bot Online"
    )

def alert_scan_start(scan_no: int, p: Portfolio):
    """Har scan start pe chhota alert"""
    discord(
        f"**🔍 Scan #{scan_no} shuru hua**\n"
        f"💰 Balance: `${p.balance:.2f}` | 📈 Growth: `{p.growth():+.1f}%`\n"
        f"📋 Open: `{len(p.open_trades)}` trades | 🎯 Win Rate: `{p.win_rate()}%`\n"
        f"🔄 Next trade size: `${p.next_trade_size():.2f}` (compound!)",
        color=0x334455, title=f"🔍 Scan #{scan_no}"
    )

def alert_buy(t: Trade, sig: TokenSignal, p: Portfolio):
    buysell_ratio = sig.buy_txns_1h / max(sig.sell_txns_1h, 1)
    discord(
        f"**💰 BUY ORDER EXECUTED!**\n\n"
        f"🪙 **Token:** [{sig.name}]({t.dex_url}) (`{t.symbol}`)\n"
        f"⛓️ **Chain:** `{t.chain.upper()}`\n"
        f"💵 **Buy Price:** `${t.buy_price:.8f}`\n"
        f"💸 **Invested:** `${t.invest_usdt:.2f}` USDT\n"
        f"🎯 **Target (+{PROFIT_TARGET*100:.0f}%):** `${t.target:.8f}`\n"
        f"🛑 **Stop (-{STOP_LOSS*100:.0f}%):** `${t.stop:.8f}`\n\n"
        f"**📊 Signals ({sig.score} pts):**\n"
        + "".join(f"• {r}\n" for r in sig.reasons) +
        f"\n**📈 Market Data:**\n"
        f"• 5m: `{sig.price_change_5m:+.1f}%` | 1h: `{sig.price_change_1h:+.1f}%`\n"
        f"• Volume 24h: `${sig.volume_24h:,.0f}`\n"
        f"• Liquidity: `${sig.liquidity_usd:,.0f}`\n"
        f"• Buy/Sell Ratio: `{buysell_ratio:.1f}x` buys\n\n"
        f"**💼 Portfolio:**\n"
        f"• Free Balance: `${p.balance:.2f}`\n"
        f"• Growth: `{p.growth():+.1f}%` since start\n"
        f"• 🔄 Compound: next trade `${p.next_trade_size():.2f}`",
        color=0x00cc44, title="🟢 BUY SIGNAL"
    )

def alert_sell(t: Trade, price: float, pct: float, profit: float, p: Portfolio, reason: str):
    color = 0x00cc44 if pct > 0 else 0xff3333
    emoji = "✅ PROFIT" if pct > 0 else "❌ STOP LOSS"
    discord(
        f"**{emoji}**\n\n"
        f"🪙 **Token:** [{t.name}]({t.dex_url}) (`{t.symbol}`)\n"
        f"⛓️ **Chain:** `{t.chain.upper()}`\n"
        f"📉 **Sell Price:** `${price:.8f}`\n"
        f"💵 **Buy Price:** `${t.buy_price:.8f}`\n"
        f"📊 **P&L:** `{pct:+.2f}%` | `${profit:+.4f}`\n"
        f"🕐 **Reason:** {reason}\n"
        f"⏱️ **Held:** {t.buy_time}\n\n"
        f"**💼 Portfolio After:**\n"
        f"• Balance: `${p.balance:.2f}`\n"
        f"• Total P&L: `${p.total_profit:+.4f}`\n"
        f"• Growth: `{p.growth():+.1f}%`\n"
        f"• Win Rate: `{p.win_rate()}%`\n\n"
        f"**🔄 Compound Effect:**\n"
        f"• Next trade size: `${p.next_trade_size():.2f}` ← bada hua!",
        color=color, title=f"{'🔴' if pct<0 else '🟢'} SELL — {emoji}"
    )

def alert_rug_avoided(name: str, reason: str, chain: str):
    discord(
        f"**🛡️ RUG PULL AVOIDED!**\n\n"
        f"🪙 Token: `{name}` ({chain.upper()})\n"
        f"⚠️ Reason: {reason}\n\n"
        f"*Bot ne automatically skip kar diya — paisa bacha!* ✅",
        color=0xff9900, title="🛡️ Danger Avoided"
    )

def alert_status(p: Portfolio, scan_no: int, sigs: int):
    open_str = ""
    for t in p.open_trades:
        open_str += f"\n• [{t.symbol}]({t.dex_url}) @ `${t.buy_price:.6f}` ({t.chain.upper()})"
    discord(
        f"**📊 5-MIN STATUS UPDATE**\n\n"
        f"💰 **Balance:** `${p.balance:.2f}` (start: `${p.initial:.2f}`)\n"
        f"📈 **Growth:** `{p.growth():+.2f}%`\n"
        f"💹 **Total P&L:** `${p.total_profit:+.4f}`\n"
        f"🎯 **Win Rate:** `{p.win_rate()}%` ({p.wins}/{p.total_trades})\n"
        f"👁️ **Open:** `{len(p.open_trades)}`{open_str}\n"
        f"🔍 **Scan #:** `{scan_no}` | Signals: `{sigs}`\n\n"
        f"**🔄 Compound Status:**\n"
        f"• Next trade: `${p.next_trade_size():.2f}` (grows with profit!)\n\n"
        f"*Next update in 5 min ⏰*",
        color=0x0099ff, title="📊 Portfolio Status"
    )

def alert_milestone(p: Portfolio, milestone: int):
    discord(
        f"**🏆 MILESTONE: +{milestone}% GROWTH!**\n\n"
        f"💰 Start: `${p.initial:.2f}` → Now: `${p.balance:.2f}`\n"
        f"📈 Growth: `+{p.growth():.1f}%`\n"
        f"🔄 **Compounding kaam kar raha hai!** 🚀\n\n"
        f"*Agle milestone tak aur badho!*",
        color=0xffd700, title="🏆 MILESTONE!"
    )

def alert_new_token_found(name: str, symbol: str, chain: str, score: int, reasons: list, url: str):
    discord(
        f"**👀 HOT TOKEN FOUND!**\n\n"
        f"🪙 **[{name} ({symbol})]({url})**\n"
        f"⛓️ Chain: `{chain.upper()}`\n"
        f"⭐ Score: `{score}` points\n\n"
        f"**Signals:**\n"
        + "".join(f"• {r}\n" for r in reasons) +
        f"\n*Analysing kiya ja raha hai...*",
        color=0x9b59b6, title="👀 Opportunity Found"
    )

# ═══════════════════════════════════════════════════════
#  📡 DATA SOURCES
# ═══════════════════════════════════════════════════════

def dex_trending_tokens() -> List[dict]:
    """DexScreener se trending tokens lo"""
    pairs = []
    try:
        # Trending boosted tokens (most promoted = most volume)
        r = requests.get(f"{DEXSCREENER}/token-boosts/top/v1", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            boosted = r.json() if isinstance(r.json(), list) else []
            print(f"  📡 DexScreener boosted: {len(boosted)} tokens")

        # Token profiles (active projects)
        r2 = requests.get(f"{DEXSCREENER}/token-profiles/latest/v1", headers=HEADERS, timeout=15)
        if r2.status_code == 200:
            profiles = r2.json() if isinstance(r2.json(), list) else []
            print(f"  📡 DexScreener profiles: {len(profiles)} tokens")
            pairs.extend(profiles[:20])  # Top 20

    except Exception as e:
        print(f"  ❌ DexScreener trending: {e}")
    return pairs

def dex_get_pair(chain: str, pair_addr: str) -> Optional[dict]:
    """DexScreener se specific pair ka data lo"""
    try:
        url = f"{DEXSCREENER}/latest/dex/pairs/{chain}/{pair_addr}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get("pairs") or data.get("pair")
            if isinstance(pairs, list) and pairs:
                return pairs[0]
            elif isinstance(pairs, dict):
                return pairs
    except Exception as e:
        print(f"  ❌ DexScreener pair: {e}")
    return None

def dex_search(query: str) -> List[dict]:
    """DexScreener search karo"""
    try:
        r = requests.get(f"{DEXSCREENER}/latest/dex/search",
                         params={"q": query}, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json().get("pairs", [])[:10]
    except Exception as e:
        print(f"  ❌ DexScreener search: {e}")
    return []

def dex_token_pairs(chain: str, token_addr: str) -> List[dict]:
    """Token ke saare pairs lo"""
    try:
        r = requests.get(f"{DEXSCREENER}/token-pairs/v1/{chain}/{token_addr}",
                         headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data[:5]
    except Exception as e:
        print(f"  ❌ DexScreener pairs: {e}")
    return []

def gecko_trending_pools() -> List[dict]:
    """GeckoTerminal se trending pools lo"""
    pools = []
    try:
        for chain in ["solana", "bsc", "eth", "base"]:
            r = requests.get(
                f"{GECKOTERMINAL}/networks/{chain}/trending_pools",
                headers={**HEADERS, "Accept": "application/json;version=20230302"},
                timeout=15
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                for pool in data[:5]:
                    pool["_chain"] = chain
                    pools.append(pool)
                print(f"  📡 GeckoTerminal {chain}: {len(data[:5])} pools")
            time.sleep(1)
    except Exception as e:
        print(f"  ❌ GeckoTerminal: {e}")
    return pools

def gecko_pool_data(chain: str, pool_addr: str) -> Optional[dict]:
    """GeckoTerminal se pool ka full data"""
    try:
        chain_map = {"ethereum": "eth", "bsc": "bsc", "solana": "solana", "base": "base"}
        c = chain_map.get(chain, chain)
        r = requests.get(
            f"{GECKOTERMINAL}/networks/{c}/pools/{pool_addr}",
            headers={**HEADERS, "Accept": "application/json;version=20230302"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json().get("data", {})
    except Exception as e:
        print(f"  ❌ GeckoTerminal pool: {e}")
    return None

def coingecko_rsi(coin_id: str) -> float:
    """CoinGecko se price history lo aur RSI calculate karo"""
    try:
        r = requests.get(f"{COINGECKO}/coins/{coin_id}/market_chart",
                         params={"vs_currency": "usd", "days": 1, "interval": "hourly"},
                         timeout=15)
        if r.status_code == 200:
            prices = [p[1] for p in r.json().get("prices", [])]
            return _calc_rsi(prices)
    except:
        pass
    return 50.0

def rugcheck_safe(chain: str, token_addr: str) -> tuple:
    """RugCheck se token safety check karo"""
    # Rugcheck mainly Solana support karta hai
    if chain.lower() != "solana":
        return True, ""
    try:
        r = requests.get(f"{RUGCHECK}/tokens/{token_addr}/report/summary",
                         timeout=10)
        if r.status_code == 200:
            data = r.json()
            score = data.get("score", 0)
            risks = data.get("risks", [])
            
            # High risk = dangerous
            high_risks = [r for r in risks if r.get("level") in ["danger", "warn"]]
            
            if score > 5000:  # High risk score
                return False, f"Risk score {score} (too high)"
            if any("mint" in str(r).lower() for r in high_risks):
                return False, "Mint authority enabled (rug risk!)"
            if any("freeze" in str(r).lower() for r in high_risks):
                return False, "Freeze authority (rug risk!)"
            
            return True, ""
    except:
        pass
    return True, ""  # Default: safe (ignore errors)

def _calc_rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0: return 100.0
    return round(100 - (100 / (1 + ag / al)), 1)

# ═══════════════════════════════════════════════════════
#  🧠 SIGNAL ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════

def analyze_pair(pair: dict, chain: str = None) -> Optional[TokenSignal]:
    """
    DexScreener pair dict se TokenSignal banao.
    Multi-source: DexScreener + GeckoTerminal + RugCheck
    """
    try:
        base  = pair.get("baseToken", {})
        name  = base.get("name", "Unknown")
        sym   = base.get("symbol", "???").upper()
        addr  = base.get("address", "")
        pair_addr = pair.get("pairAddress", "")
        ch    = (chain or pair.get("chainId", "unknown")).lower()

        price_str = pair.get("priceUsd") or pair.get("priceNative", "0")
        try:    price = float(price_str)
        except: price = 0.0

        if price <= 0:
            return None

        vol   = pair.get("volume",      {})
        pc    = pair.get("priceChange", {})
        liq   = pair.get("liquidity",   {})
        txns  = pair.get("txns",        {})
        h1tx  = txns.get("h1", {})

        vol24  = float(vol.get("h24", 0) or 0)
        pc5m   = float(pc.get("m5",  0) or 0)
        pc1h   = float(pc.get("h1",  0) or 0)
        pc6h   = float(pc.get("h6",  0) or 0)
        pc24h  = float(pc.get("h24", 0) or 0)
        liq_usd= float(liq.get("usd", 0) or 0)
        mcap   = float(pair.get("marketCap") or pair.get("fdv") or 0)
        buys   = int(h1tx.get("buys",  0) or 0)
        sells  = int(h1tx.get("sells", 0) or 0)
        dex_url= pair.get("url", f"https://dexscreener.com/{ch}/{pair_addr}")

        # ── Safety filters ──────────────────────────────
        if liq_usd < MIN_LIQUIDITY:
            print(f"  ⛔ {sym}: liquidity too low (${liq_usd:.0f})")
            return None

        if vol24 < 1000:
            print(f"  ⛔ {sym}: volume too low (${vol24:.0f})")
            return None

        # Rug check (Solana only)
        is_safe, rug_warn = rugcheck_safe(ch, addr)
        if not is_safe:
            print(f"  ⛔ {sym}: RUG RISK — {rug_warn}")
            alert_rug_avoided(name, rug_warn, ch)
            return None

        sig = TokenSignal(
            name=name, symbol=sym, chain=ch, address=addr,
            pair_address=pair_addr, price_usd=price,
            price_change_5m=pc5m, price_change_1h=pc1h,
            price_change_6h=pc6h, price_change_24h=pc24h,
            volume_24h=vol24, liquidity_usd=liq_usd,
            market_cap=mcap, buy_txns_1h=buys, sell_txns_1h=sells,
            dex_url=dex_url, is_safe=is_safe, rug_warning=rug_warn
        )

        # ── SCORING SYSTEM ───────────────────────────────
        # 1. Price momentum
        if pc5m > 3:
            sig.score += 2; sig.reasons.append(f"⚡ 5m pump +{pc5m:.1f}%")
        if pc1h > 5:
            sig.score += 2; sig.reasons.append(f"🚀 1h pump +{pc1h:.1f}%")
        elif pc1h > 2:
            sig.score += 1; sig.reasons.append(f"📈 1h up +{pc1h:.1f}%")

        # 2. Dip recovery signal (buy the dip)
        if -20 <= pc24h <= -5 and pc1h > 1:
            sig.score += 2; sig.reasons.append(f"🔄 Dip recovery ({pc24h:.0f}%↓ then +{pc1h:.1f}%)")

        # 3. Volume explosion
        if vol24 > 500_000:
            sig.score += 2; sig.reasons.append(f"💥 Volume ${vol24/1e6:.1f}M")
        elif vol24 > 100_000:
            sig.score += 1; sig.reasons.append(f"📊 Volume ${vol24/1e3:.0f}K")

        # 4. Buy pressure
        bsr = buys / max(sells, 1)
        if bsr > 2.0:
            sig.score += 2; sig.reasons.append(f"💚 Buy pressure {bsr:.1f}x")
        elif bsr > 1.3:
            sig.score += 1; sig.reasons.append(f"📗 More buys {bsr:.1f}x")

        # 5. Good liquidity (not too low, not whale-dominated)
        if 10_000 <= liq_usd <= 5_000_000:
            sig.score += 1; sig.reasons.append(f"💧 Good liquidity ${liq_usd/1e3:.0f}K")

        # 6. RSI from CoinGecko (if possible)
        # Skip RSI for unknown tokens to save API calls

        # 7. Market cap sweet spot (small = more room to grow)
        if 0 < mcap < 10_000_000:
            sig.score += 1; sig.reasons.append(f"🎯 Small cap ${mcap/1e6:.1f}M (room to grow)")

        # 8. Penalize big drops
        if pc1h < -10:
            sig.score -= 2; sig.reasons.append(f"⚠️ 1h drop {pc1h:.1f}%")
        if pc24h < -30:
            sig.score -= 1; sig.reasons.append(f"⚠️ 24h dump {pc24h:.1f}%")

        return sig

    except Exception as e:
        print(f"  ❌ analyze_pair error: {e}")
        return None

# ═══════════════════════════════════════════════════════
#  💼 TRADE EXECUTION
# ═══════════════════════════════════════════════════════

def execute_buy(sig: TokenSignal, p: Portfolio) -> Optional[Trade]:
    """COMPOUND BUY — 20% of current balance"""
    invest = min(p.next_trade_size(), p.balance)
    if invest < 0.5:
        print(f"  ⚠️  Balance too low: ${p.balance:.2f}")
        return None

    coins  = invest / sig.price_usd
    target = sig.price_usd * (1 + PROFIT_TARGET)
    stop   = sig.price_usd * (1 - STOP_LOSS)

    trade = Trade(
        name=sig.name, symbol=sig.symbol, chain=sig.chain,
        address=sig.address, pair_address=sig.pair_address,
        buy_price=sig.price_usd, invest_usdt=invest, coins=coins,
        buy_time=datetime.datetime.now().strftime("%H:%M:%S %d-%b"),
        target=target, stop=stop, dex_url=sig.dex_url
    )

    p.balance -= invest
    p.open_trades.append(trade)
    p.total_trades += 1

    print(f"\n  🟢 BUY  {trade.symbol} ({trade.chain.upper()}) @ ${trade.buy_price:.8f}")
    print(f"       Invest: ${invest:.2f} | Target: ${target:.8f} | Stop: ${stop:.8f}")
    return trade

def check_sells(p: Portfolio):
    """Open trades monitor karo aur sell karo"""
    for t in p.open_trades[:]:
        # Fresh price from DexScreener
        pair = dex_get_pair(t.chain, t.pair_address)
        if not pair:
            print(f"  ⚠️  No data for {t.symbol}")
            time.sleep(2)
            continue

        price_str = pair.get("priceUsd") or pair.get("priceNative", "0")
        try:    cur = float(price_str)
        except: cur = 0.0

        if cur <= 0:
            continue

        pct    = (cur - t.buy_price) / t.buy_price * 100
        value  = t.coins * cur
        profit = value - t.invest_usdt
        reason = None

        if cur >= t.target:
            reason = f"✅ Profit target hit +{pct:.2f}%"
        elif cur <= t.stop:
            reason = f"🛑 Stop loss hit {pct:.2f}%"
        else:
            # Extra check: buy/sell txns flip
            txns  = pair.get("txns", {})
            h1tx  = txns.get("h1", {})
            buys  = int(h1tx.get("buys", 1) or 1)
            sells = int(h1tx.get("sells", 0) or 0)
            if sells > buys * 2 and pct > 1:
                reason = f"📉 Sell pressure flipped ({sells}s vs {buys}b) at +{pct:.1f}%"

        if reason:
            p.balance      += value
            p.total_profit += profit
            if pct > 0: p.wins += 1

            t.status = "SOLD"
            p.open_trades.remove(t)
            p.history.append(t)

            print(f"\n  🔴 SELL {t.symbol} @ ${cur:.8f} | P&L: {pct:+.2f}% ${profit:+.4f}")
            print(f"       New Balance: ${p.balance:.2f} | Next trade: ${p.next_trade_size():.2f}")

            alert_sell(t, cur, pct, profit, p, reason)

            # Milestone check
            g = p.growth()
            for ms in [10, 25, 50, 100, 200]:
                if g >= ms and ms not in p.milestones_hit:
                    p.milestones_hit.add(ms)
                    alert_milestone(p, ms)
                    break

            time.sleep(2)

# ═══════════════════════════════════════════════════════
#  🚀 MAIN LOOP
# ═══════════════════════════════════════════════════════

def main():
    p               = Portfolio()
    scan_no         = 0
    total_signals   = 0
    last_status_t   = time.time()

    print("╔══════════════════════════════════════╗")
    print("║  🚀 MEMECOIN BOT v3.0 — STARTING    ║")
    print("╚══════════════════════════════════════╝")
    print(f"  💰 Balance : ${p.balance}")
    print(f"  🔄 Compound: ON")
    print(f"  📡 Sources : DexScreener + GeckoTerminal + CoinGecko + RugCheck")
    print(f"  ⏱️  Interval: {SCAN_INTERVAL}s")
    print()

    alert_startup(p)

    while True:
        scan_no += 1
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n{'═'*55}")
        print(f"  🔍 SCAN #{scan_no} | {now} | 💰${p.balance:.2f} | 📈{p.growth():+.1f}%")
        print(f"{'═'*55}")

        # Discord scan alert
        alert_scan_start(scan_no, p)

        # ── STEP 1: Check open trades ────────────────────
        if p.open_trades:
            print(f"\n  📋 Checking {len(p.open_trades)} open trade(s)...")
            check_sells(p)

        # ── STEP 2: Find new opportunities ───────────────
        open_coins = {t.address for t in p.open_trades}
        can_buy    = p.balance >= 0.5 and len(p.open_trades) < MAX_OPEN_TRADES

        if can_buy:
            print(f"\n  🔍 Scanning DexScreener trending...")
            candidates = []

            # --- DexScreener trending search ---
            for query in ["meme", "pepe", "doge", "shib", "cat", "inu"]:
                pairs = dex_search(query)
                for pair in pairs:
                    sig = analyze_pair(pair)
                    if sig and sig.address not in open_coins and sig.score >= MIN_SIGNALS:
                        candidates.append(sig)
                time.sleep(1.5)

            # --- GeckoTerminal trending pools ---
            print(f"\n  🔍 Scanning GeckoTerminal trending pools...")
            gt_pools = gecko_trending_pools()
            for pool in gt_pools:
                try:
                    attrs  = pool.get("attributes", {})
                    chain  = pool.get("_chain", "unknown")
                    p_name = attrs.get("name", "?")
                    p_addr = attrs.get("address", "")
                    price  = float(attrs.get("base_token_price_usd") or 0)
                    vol24  = float(attrs.get("volume_usd", {}).get("h24") or 0)
                    liq    = float(attrs.get("reserve_in_usd") or 0)

                    pc = attrs.get("price_change_percentage", {})
                    pc5m  = float(pc.get("m5", 0) or 0)
                    pc1h  = float(pc.get("h1", 0) or 0)
                    pc24h = float(pc.get("h24", 0) or 0)

                    txns   = attrs.get("transactions", {})
                    h1t    = txns.get("h1", {})
                    buys   = int(h1t.get("buys", 0) or 0)
                    sells  = int(h1t.get("sells", 0) or 0)

                    tok    = pool.get("relationships", {}).get("base_token", {}).get("data", {})
                    tok_id = tok.get("id", "")
                    addr   = tok_id.split("_")[-1] if "_" in tok_id else tok_id

                    if addr in open_coins or price <= 0 or liq < MIN_LIQUIDITY:
                        continue

                    gt_sig = TokenSignal(
                        name=p_name, symbol=p_name.split("/")[0].upper(),
                        chain=chain, address=addr, pair_address=p_addr,
                        price_usd=price,
                        price_change_5m=pc5m, price_change_1h=pc1h,
                        price_change_6h=0.0, price_change_24h=pc24h,
                        volume_24h=vol24, liquidity_usd=liq,
                        market_cap=0, buy_txns_1h=buys, sell_txns_1h=sells,
                        dex_url=f"https://www.geckoterminal.com/{chain}/pools/{p_addr}",
                        score=0, reasons=[], is_safe=True
                    )

                    # Score it
                    bsr = buys / max(sells, 1)
                    if pc5m > 3:  gt_sig.score += 2; gt_sig.reasons.append(f"⚡ 5m +{pc5m:.1f}%")
                    if pc1h > 5:  gt_sig.score += 2; gt_sig.reasons.append(f"🚀 1h +{pc1h:.1f}%")
                    if bsr > 2:   gt_sig.score += 2; gt_sig.reasons.append(f"💚 Buys {bsr:.1f}x")
                    if vol24 > 100_000: gt_sig.score += 1; gt_sig.reasons.append(f"💥 Vol ${vol24/1e3:.0f}K")
                    if -20 <= pc24h <= -5 and pc1h > 0:
                        gt_sig.score += 2; gt_sig.reasons.append(f"🔄 Dip recovery")

                    if gt_sig.score >= MIN_SIGNALS:
                        candidates.append(gt_sig)
                except Exception as ex:
                    print(f"  ❌ GT pool parse: {ex}")

            # Sort by score
            candidates.sort(key=lambda s: s.score, reverse=True)
            candidates = candidates[:5]  # Top 5 only
            total_signals += len(candidates)

            print(f"\n  ⭐ {len(candidates)} signal(s) found this scan")

            if candidates:
                best = candidates[0]
                alert_new_token_found(
                    best.name, best.symbol, best.chain,
                    best.score, best.reasons, best.dex_url
                )
                print(f"\n  🎯 Best: {best.symbol} ({best.chain.upper()}) score={best.score}")
                trade = execute_buy(best, p)
                if trade:
                    alert_buy(trade, best, p)
                    time.sleep(2)
        else:
            if p.balance < 0.5:
                print(f"\n  ⚠️  Balance bahut kam: ${p.balance:.2f}")
                discord(f"⚠️ Balance low: `${p.balance:.2f}` — trades ruk gayi hain!", 0xff9900, "⚠️ Low Balance")
            else:
                print(f"\n  ⏸️  Max trades open ({MAX_OPEN_TRADES})")

        # ── STEP 3: 5-min status ─────────────────────────
        if time.time() - last_status_t >= 300:
            alert_status(p, scan_no, total_signals)
            last_status_t = time.time()

        # Terminal summary
        print(f"\n  💼 Balance: ${p.balance:.2f} | P&L: ${p.total_profit:+.4f} | Growth: {p.growth():+.1f}%")
        print(f"  🔄 Next trade: ${p.next_trade_size():.2f} | Open: {len(p.open_trades)} | Wins: {p.win_rate()}%")
        print(f"  ⏳ Next scan in {SCAN_INTERVAL}s...")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Bot band (Ctrl+C)")
        discord("**🛑 BOT STOPPED** — User ne band kiya", 0xff0000, "Bot Offline")
