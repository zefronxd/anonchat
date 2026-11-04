# 🤖 Anonymous Telegram Bot

A modern and feature-rich Anonymous Telegram Bot built with **Python**, **Aiogram**, and **MongoDB**.

## ✨ Features

- 🔐 Anonymous messaging
- 👤 User profile system
- 🎁 Referral system
- 🛡️ Admin panel
- 📊 User statistics
- 💾 MongoDB database (PyMongo async driver)
- ⚡ Middleware support

---

## 🛠️ Tech Stack

- Python 3.11+
- Aiogram 3
- MongoDB (local or Atlas) via `pymongo` `AsyncMongoClient`

---

## 📂 Project Structure

```text
anonymous-telegram-bot/
├── database/        # mongo.py (connection+indexes), models.py, repo.py (all queries)
├── handlers/
├── keyboards/
├── middlewares/
├── utils/
├── scripts/         # migrate_sqlite_to_mongo.py
├── main.py
├── config.py
├── requirements.txt
└── .env.example
```

---

## 🚀 Installation

Clone the repository:

```bash
git clone https://github.com/alimn-code/anonymous-telegram-bot.git
```

Go to the project directory:

```bash
cd anonymous-telegram-bot
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in `BOT_TOKEN`, `ADMIN_IDS`, `MONGO_URI` and `MONGO_DB`, then run:

```bash
python main.py
```

### 🗄️ MongoDB setup

- **Local:** install MongoDB and use `MONGO_URI=mongodb://localhost:27017`
- **Cloud (free):** create a cluster on MongoDB Atlas and paste its
  `mongodb+srv://...` connection string into `MONGO_URI` (also allow your server's IP in Atlas → Network Access).

Indexes are created automatically on startup.

### 🔁 Migrating old SQLite data (optional)

```bash
python scripts/migrate_sqlite_to_mongo.py ./data/db.sqlite3
```

---

## 📌 Roadmap

- [ ] Multi-language support
- [ ] Web Admin Panel
- [ ] Docker support
- [ ] Logging improvements

---

## 👨‍💻 Author

**Ali**

GitHub: https://github.com/alimn-code

---

## 📄 License

This project is available for educational and personal learning purposes.
