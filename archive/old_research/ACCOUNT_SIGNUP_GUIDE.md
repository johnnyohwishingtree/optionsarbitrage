# Account Signup Guide - Alpaca + IBKR
## Get Both Paper Trading Accounts Set Up

## Strategy: Parallel Signup

### Timeline:
- **Alpaca**: 15 minutes → Instant approval → API keys today
- **IBKR**: 30 minutes → 1-2 days approval → API keys in 2 days

**Plan**: Sign up for both now, start building with Alpaca while IBKR approves!

---

## Part 1: Alpaca Signup (Do This First - 15 minutes)

### Step 1: Create Account (5 minutes)

1. **Go to**: https://alpaca.markets
2. **Click**: "Get Started" or "Sign Up"
3. **Choose**: "Paper Trading" (it's free!)
4. **Fill out**:
   - Name
   - Email
   - Password
   - Phone (optional)

**Note**: You DON'T need to fund anything or link a bank for paper trading!

### Step 2: Verify Email (2 minutes)

1. Check your email
2. Click verification link
3. Log back into Alpaca

### Step 3: Get API Keys (5 minutes)

1. **After logging in**, go to: https://app.alpaca.markets/paper/dashboard/overview
2. **Left sidebar** → Click "API Keys" or "Your API Keys"
3. **Click**: "Generate New Key"
4. **Name it**: "SPY-SPX-Bot" (or anything)
5. **IMPORTANT**: Copy both:
   - API Key ID (starts with "PK...")
   - Secret Key (starts with "...")

**Save these keys immediately!**

Create a file on your computer:
```
alpaca_keys.txt

API Key: PK...
Secret Key: ...
```

### Step 4: Enable Paper Trading for Options (Already enabled!)

Good news: Alpaca enables options trading on paper accounts by default!

Just verify:
1. Go to: https://app.alpaca.markets/paper/dashboard/overview
2. You should see "Paper Trading" badge
3. Try searching for "SPY" - you should see options data

**✅ Done! You have Alpaca API keys and can trade immediately.**

---

## Part 2: Interactive Brokers Signup (Do This Next - 30 minutes)

### Step 1: Create Account (15 minutes)

1. **Go to**: https://www.interactivebrokers.com
2. **Click**: "Open Account"
3. **Choose**: "Individual" account
4. **Select**: "Paper Trading Account" (VERY IMPORTANT!)

### Step 2: Fill Out Application (15 minutes)

**Personal Information:**
- Name, address, DOB
- SSN (for US residents)
- Employment status
- Net worth, income (estimates are fine for paper)

**Trading Experience:**
- Say you have "Good" knowledge
- Options experience: "Limited" is fine
- This is just paper trading, so they'll approve you

**Account Configuration:**
- Enable: "US Stocks"
- Enable: "US Options"
- Enable: "Index Options" (for SPX!)

### Step 3: Submit & Wait for Approval (1-2 days)

1. Review application
2. Sign electronically
3. Submit

**Expected timeline:**
- Approval email: 1-2 business days
- Paper account: Instant access after approval
- API setup: After account approval

### Step 4: API Setup (After Account Approved)

**Will need to:**
1. Download TWS or IB Gateway
2. Enable API in settings
3. Get API credentials

**I'll guide you through this step when your account is approved!**

For now, just submit the application.

---

## What to Do While Waiting

### Today (Right After Alpaca Signup):

**You give me:**
- Alpaca API Key
- Alpaca Secret Key

**I'll build:**
- Complete automated system for Alpaca
- Can start paper trading Monday!

### In 1-2 Days (When IBKR Approves):

**You:**
- Let me know IBKR approved
- I'll guide you through TWS setup

**I'll:**
- Extend system to support IBKR
- Same code, just config switch
- Now you can compare both!

---

## Security Best Practices

### How to Share API Keys Securely:

**Option 1: Create .env file** (I'll read it)
```bash
# Create this file on your Mac:
/Users/johnnyhuang/personal/optionsarbitrage/.env

# Add this content:
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_PAPER=true
```

**Option 2: Paste in chat**
- Less secure but works
- I'll immediately save to .env
- You can regenerate keys later

**Option 3: I'll create template**
- I'll create .env.template
- You fill in your keys
- Keep it local, never commit to git

---

## Parallel Development Strategy

### Week 1: Alpaca System
```
Day 1 (Today):
├── You: Sign up for Alpaca (15 min)
├── You: Sign up for IBKR (30 min)
└── You: Share Alpaca keys with me

Day 1 (Today - Evening):
├── Me: Build complete Alpaca system (2-3 hours)
└── Me: Test with your keys

Day 2 (Weekend):
├── We: Test together
├── We: Verify paper trades work
└── System: Ready for Monday!

Day 3-4 (Mon-Tue):
└── System: Runs automatically, collects Alpaca data
```

### Week 2: IBKR Integration
```
Day 1-2:
└── IBKR: Approves your account

Day 3:
├── You: Download TWS/IB Gateway
├── Me: Guide you through API setup
└── Me: Extend system to support IBKR

Day 4-5:
└── System: Runs on BOTH platforms simultaneously
```

### Week 3-4: Validation
```
Both Systems Running:
├── Alpaca: Collects data
├── IBKR: Collects data
└── Compare results

End of Week 4:
└── Analyze which platform is better for live trading
```

---

## Expected Results

### After 4 Weeks:

**You'll know:**
1. Does strategy work? (Yes/No)
2. Real profit per trade? ($400-600 expected)
3. Which platform is better? (Alpaca vs IBKR)
4. Real bid/ask spreads?
5. Assignment risk frequency?

**You'll have:**
- 40-80 real paper trades
- Complete P&L history
- CSV exports for analysis
- Confidence to go live (or not)

---

## Cost Analysis

### Alpaca:
- **Paper trading**: FREE ✅
- **Live trading** (if you go that route):
  - Options: ~$0.50-1.00 per contract
  - No minimums

### IBKR:
- **Paper trading**: FREE ✅
- **Live trading** (if you go that route):
  - Options: ~$0.25-0.65 per contract (CHEAPEST!)
  - No minimums
  - Best for serious trading

### Our Strategy (Live):
- 22 contracts per day (2 spreads × 11 contracts)
- Alpaca: $11-22/day in commissions
- IBKR: $5.50-14.30/day in commissions
- **IBKR saves ~$1,500/year** if going live

---

## What Happens After Signups

### You'll Give Me:

**From Alpaca (today):**
```
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
```

**From IBKR (in 2 days):**
```
IBKR_ACCOUNT_ID=...
IBKR_TWS_PORT=7497  # Paper trading port
```

### I'll Build:

**Single System, Dual Platform:**
```python
# config.yaml
active_brokers:
  - alpaca
  - ibkr

alpaca:
  api_key: ${ALPACA_API_KEY}
  secret: ${ALPACA_SECRET_KEY}
  paper: true

ibkr:
  host: "127.0.0.1"
  port: 7497  # Paper trading
  client_id: 1
```

**One command runs both:**
```bash
python main.py --brokers alpaca,ibkr
```

---

## Quick Checklist

### Right Now:
- [ ] Sign up for Alpaca (15 min)
- [ ] Get Alpaca API keys
- [ ] Save keys securely
- [ ] Share with me (securely)
- [ ] Sign up for IBKR (30 min)
- [ ] Submit IBKR application

### While You're Doing That:
- [ ] I'll set up project structure
- [ ] Create .env template
- [ ] Prepare to build Alpaca system

### After You Share Alpaca Keys:
- [ ] I build complete system (2-3 hours)
- [ ] We test together
- [ ] Ready for Monday!

### In 1-2 Days (IBKR Approval):
- [ ] You notify me
- [ ] I guide through TWS setup
- [ ] I extend system to IBKR
- [ ] Now running on both!

---

## FAQs

**Q: Do I need to fund these accounts?**
A: NO! Paper trading is completely free, no funding needed.

**Q: Will they ask for bank info?**
A: Alpaca won't. IBKR might ask but it's optional for paper trading.

**Q: Are these real accounts?**
A: Yes, but they trade with FAKE money (paper trading).

**Q: Can I see the trades happening?**
A: Yes! Both platforms have dashboards to watch trades.

**Q: How do I share API keys securely?**
A: I'll create a .env template file. You fill it in locally.

**Q: What if I make a mistake in signup?**
A: Both are forgiving. You can contact support or create new account.

**Q: When will I start paper trading?**
A: Alpaca: This Monday! IBKR: Later this week!

---

## Next Steps - Action Items for You

### 🎯 Do These Now (45 minutes total):

1. **Alpaca Signup** (15 min)
   - Go to: https://alpaca.markets
   - Sign up for paper trading
   - Get API keys
   - Save them securely

2. **IBKR Signup** (30 min)
   - Go to: https://www.interactivebrokers.com
   - Sign up for paper trading account
   - Enable options trading
   - Submit application

3. **Share Alpaca Keys with Me**
   - Create .env file OR
   - Paste in chat (I'll secure them)

4. **Wait for My Build** (2-3 hours)
   - I'll build complete Alpaca system
   - We'll test together
   - Ready for Monday!

---

## 🚀 Ready to Start?

Go ahead and sign up for both now!

**Start with Alpaca** (easier, faster) → Share keys → I'll build while you do IBKR signup!

Let me know when you have the Alpaca keys and I'll get started! 🎉
