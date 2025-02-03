# 🤖 LinkedIn Profile Sharing Bot

A powerful Telegram bot designed to facilitate professional networking by enabling users to share and discover LinkedIn profiles within their community. Perfect for educational institutions, professional groups, and networking communities.

## ✨ Features

### Core Features

- 🔄 Share LinkedIn profiles with automatic data extraction
- 👥 View other professionals' profiles in a paginated format
- 📊 Get network statistics and insights
- 🔍 Search profiles by keywords
- 📱 User-friendly button interface

### Advanced Features

- 📋 Export profiles to CSV (admin only)
- ⚡ Rate limiting to prevent spam
- 🔐 Profile management (update/delete)
- 🎯 Automatic profile data validation
- 📢 New connection notifications

## 🛠 Technical Stack

- **Framework**: `python-telegram-bot` 20.3
- **Database**: PostgreSQL with SQLAlchemy
- **API Integration**: LinkedIn API for profile data extraction
- **Authentication**: Environment-based configuration
- **Logging**: Rotating file logs with JSON formatting

## 🚀 Quick Start

1. **Clone the Repository**

   ```bash
   git clone https://github.com/Alpha-mintamir/linkedin-bot.git
   cd linkedin-bot
   ```

2. **Set Up Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Create a `.env` file with the following:

   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=your_db_name
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   LINKEDIN_USERNAME=your_linkedin_email
   LINKEDIN_PASSWORD=your_linkedin_password
   ```

4. **Initialize Database**

   ```bash
   python scripts/db_setup.py
   ```

5. **Start the Bot**
   ```bash
   python bot.py
   ```

## 🌐 Deployment on Render

1. **Create a Render Account**

   - Sign up at [render.com](https://render.com)
   - Connect your GitHub repository

2. **Create New Service**

   - Click "New +"
   - Select "Worker"
   - Choose your repository

3. **Configure Service**

   - Name: `linkedin-profile-bot`
   - Environment: `Python`
   - Region: Choose nearest to your users
   - Branch: `main`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`

4. **Set Environment Variables**

   - Add all variables from `.env` in Render's environment variables section:
     - `TELEGRAM_BOT_TOKEN`
     - `DB_HOST`
     - `DB_PORT`
     - `DB_NAME`
     - `DB_USER`
     - `DB_PASSWORD`
     - `LINKEDIN_USERNAME`
     - `LINKEDIN_PASSWORD`

5. **Deploy**
   - Click "Create Worker"
   - Wait for deployment to complete

> **Note**: Make sure to use a production-grade PostgreSQL database (like Render's managed PostgreSQL) instead of a local database for deployment.

## 💡 Usage

1. **Start the Bot**

   - Open Telegram and search for your bot
   - Send `/start` to begin

2. **Share Your Profile**

   - Simply send your LinkedIn profile URL
   - The bot will automatically extract and store your information

3. **View Other Profiles**

   - Click "👥 View Users" to see other profiles
   - Use navigation buttons to browse through pages
   - Click profile links to view full LinkedIn profiles

4. **Manage Your Profile**
   - Use "🔄 Update Profile" to update your information
   - Use "❌ Delete Profile" to remove your profile

## 🔧 Admin Commands

- `/stats` - View network statistics
- `/export` - Export profiles to CSV
- `/search` - Search through profiles

## 📝 Logging

Logs are stored in `logs/bot.log` with automatic rotation:

- Maximum file size: 1MB
- Backup count: 5 files
- Log level: INFO

## 🛡️ Security Features

- Rate limiting to prevent spam
- SQL injection protection
- Input validation
- Secure credential management

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Support

For support, email alpha.lencho@aau.edu.et or open an issue in the repository.

---

Made with ❤️ by collaboration of [Alpha Lencho](https://github.com/Alpha-mintamir) and cursor
