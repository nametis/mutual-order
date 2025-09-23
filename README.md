# Mutual Order - Discogs Group Buying App

A Flask web application for organizing group purchases from Discogs sellers.

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Discogs API Credentials
```bash
python get_discogs_token.py
```
Follow the prompts to get your API credentials.

### 3. Configure Environment
Copy the credentials to a `.env` file:
```bash
# Copy from get_discogs_token.py output
DISCOGS_CONSUMER_KEY=your_consumer_key_here
DISCOGS_CONSUMER_SECRET=your_consumer_secret_here  
DISCOGS_ACCESS_TOKEN=your_access_token_here
DISCOGS_ACCESS_SECRET=your_access_secret_here
FLASK_SECRET_KEY=your_super_secret_flask_key
```

### 4. Set Currency to EUR
1. Go to https://www.discogs.com/settings/buyer
2. Set "Currency" to "EUR - Euro"
3. This will make all prices display in EUR

### 5. Run the App
```bash
python app.py
```

### 6. Add Test Data (Optional)
```bash
python setup_test_data.py
```

## 🔐 Security Features

- ✅ **Environment Variables**: API credentials stored securely in `.env`
- ✅ **Git Protection**: `.env` file excluded from version control  
- ✅ **Password Hashing**: User passwords properly hashed
- ✅ **Session Management**: Secure user authentication

## 🧪 Test Data

- **User:** `test_user1` (password: `password123`)
- **Order:** Contains sample listings for testing

## 🎯 Features

- **Multi-user system** with authentication
- **Group orders** organized by seller  
- **Real-time Discogs data** fetching
- **User permissions** (only edit your own listings)
- **Admin badges** for order creators 👑
- **Persistent storage** with SQLite
- **EUR currency support** via user settings

## 🔒 Production Checklist

- [ ] Change `FLASK_SECRET_KEY` to a strong random value
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set up HTTPS
- [ ] Use environment variables on your hosting platform
- [ ] Never commit `.env` file to version control

## 🗂️ File Structure

```
mutual_order/
├── app.py                 # Main Flask application
├── get_discogs_token.py   # Token generation script  
├── setup_test_data.py     # Test data creation
├── migrate_db.py          # Database migration script
├── requirements.txt       # Dependencies
├── .env                   # Environment variables (create this)
├── .gitignore            # Git ignore file
├── templates/            # HTML templates
│   ├── login.html
│   ├── register.html  
│   ├── dashboard.html
│   └── order.html
└── mutual_order.db       # SQLite database (auto-created)
```