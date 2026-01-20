# 🚀 Quick Start - Chạy Bot Ngay

## ✅ Checklist trước khi chạy

### 1. Config đã setup chưa?
```bash
# Check file config tồn tại
ls config/secrets.env
```

File `config/secrets.env` phải có:
- `PRIVATE_KEY=your_private_key_here`
- `PROXY_ADDRESS=your_proxy_wallet_address`

### 2. Dependencies đã cài chưa?
```bash
pip install -r requirements.txt
```

### 3. Test kết nối API
```bash
python test_tp_logic.py
```

Nếu chạy OK → sẵn sàng!

---

## 🎯 Chạy Bot - 1 Command Duy Nhất

### Cách 1: Auto-restart (Khuyên dùng)
```bash
run_bot_forever.bat
```
- Bot tự restart nếu crash
- Chạy mãi mãi cho đến khi đóng cửa sổ
- **Best cho production**

### Cách 2: Chạy thông thường
```bash
start_bot.bat
```
hoặc
```bash
python trading_bot.py
```
- Chạy 1 lần
- Dừng khi có lỗi

---

## 📊 Bot sẽ làm gì?

**Mỗi 5 phút:**
1. Scan LOL markets (Volume > $1k)
2. Đặt limit orders theo strategy ($3.5/entry)
3. Check positions filled → Auto TP
4. Recreate disappeared orders
5. Cleanup old orders

**Strategy:**
- Strong team 61-100¢
- 2 entries theo bảng giá
- 2 TPs (50/50 split)

---

## 🛑 Dừng Bot

- Đóng cửa sổ terminal
- Hoặc Ctrl + C

---

## 📝 Logs & Monitoring

Bot sẽ hiển thị:
```
======================================================================
SCAN CYCLE - 2026-01-18 15:50:00
======================================================================
Balance: $XX.XX USDC.e

[1] Scanning LOL markets...
Found 5 markets:
  - Team A vs Team B...

[2] Adding new markets to queue...
Added 2 new markets

[3] Checking for markets ready for entry...
Found 1 markets ready

  → Fetching fresh data for market-slug...
[ENTRY] Placing 2 orders for market-slug
✓ Placed Team X Entry 1: $3.5 at $0.420
✓ Placed Team X Entry 2: $3.5 at $0.270

[4] Checking disappeared orders...
  All orders are active

[5] Checking filled positions...
✓ Placed 2 take profit orders
  TP1: 50% at start price
  TP2: 50% at 0.96

======================================================================
Cycle complete. Next check in 5 minutes
======================================================================
```

---

## ⚠️ Important Notes

- **Không tắt máy** nếu muốn bot chạy 24/7
- Có thể **minimize window**, bot vẫn chạy background
- **Check logs** thỉnh thoảng để đảm bảo mọi thứ OK
- Bot **không giới hạn số markets** - đặt tất cả markets đủ điều kiện
- Polymarket sẽ **tự reject** khi hết balance

---

## 🔧 Troubleshooting

### Bot không chạy?
1. Check `config/secrets.env` có đúng không
2. Check balance > $10
3. Check internet connection

### Không tìm thấy markets?
- Có thể không có LOL matches lúc này
- Check filter: Volume > $1k, Strong > 60¢

### Orders không được đặt?
- Check balance
- Check Polymarket API status
- Restart bot

---

## 📞 Support Files

- `README.md` - Overview
- `SETUP_GUIDE.md` - Chi tiết setup
- `BOT_GUIDE.md` - Chi tiết bot hoạt động
- `test_tp_logic.py` - Test TP strategy

---

**Ready? → Double-click `run_bot_forever.bat` và để bot tự chạy!** 🚀
