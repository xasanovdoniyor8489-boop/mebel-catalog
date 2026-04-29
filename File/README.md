# 🪑 Mebel Katalog — Telegram Web App

## Loyiha tuzilmasi
```
mebel_app/
├── main.py          # FastAPI backend
├── bot.py           # Telegram bot
├── start.py         # Ishga tushirish
├── requirements.txt
├── nixpacks.toml    # Railway sozlamalari
├── templates/
│   ├── admin.html   # Admin panel
│   └── catalog.html # Mijozlar katalogi
└── static/
    └── uploads/     # Rasmlar
```

## Sahifalar
- `/` — Admin panel (guruh, kategoriya, mahsulot qo'shish)
- `/catalog` — Mijozlar ko'radigan katalog (Telegram Web App)

## Railway Variables
```
BOT_TOKEN=your_bot_token
WEB_APP_URL=https://your-app.railway.app/catalog
```

## Ishlatish
1. Admin panel: `https://your-app.railway.app/`
2. Guruh qo'shing → Kategoriya qo'shing → Mahsulot qo'shing
3. Telegram botda /start → Katalogni ochish
