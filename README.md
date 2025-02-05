# 🤖 IS_Connect Bot

A Telegram bot designed to facilitate professional networking within the Information Systems community by enabling students to share and discover LinkedIn profiles. Perfect for IS students, alumni, and faculty members.

![IS_Connect Bot Logo](https://github.com/user-attachments/assets/86853d30-4479-4550-ab69-e3d2e55fc077)

## ✨ Features

### Core Features

- **LinkedIn Profile Sharing:**  
  Users can share their LinkedIn profiles, and the bot automatically extracts key data.  

- **Community Browsing:**  
  View community members' profiles in a paginated format for easy exploration and networking.  

- **Bot Status Monitoring:**  
  Check the current status of the bot to ensure smooth operation.  

- **Profile Search:**  
  Search through profiles using keywords to find the right connections.

- **User-Friendly Button Interface:**  
  Navigate the bot using an intuitive button-based interface.


### Advanced Features

- 📋 Export profiles to CSV (admin only)
- ⚡ Rate limiting to prevent spam
- 🔐 Profile management (update/delete)
- 🎯 Automatic profile data validation
- 📢 New member notifications


## 🛠 Technical Stack

- **Framework**: `python-telegram-bot` 20.3
- **Database**: PostgreSQL with SQLAlchemy
- **API Integration**: LinkedIn API for profile data extraction
- **Authentication**: Environment-based configuration
- **Logging**: Rotating file logs with structured formatting

## 🚀 Quick Start

1. **Clone the Repository**

   ```bash
   git clone https://github.com/Alph_Mintamir/IS-Connect.git
   cd is-connect-bot
   ```

2. **Set Up Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Create a `.env` file with:

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

## 💡 Usage

1. **Start the Bot**

   - Search for the bot on Telegram
   - Click "Start" or send `/start`
   - Use the main menu buttons to navigate

2. **Add Your Profile**

   - Click "➕ Add Profile"
   - Send your LinkedIn profile URL
   - Format: `https://www.linkedin.com/in/username`

3. **View Community Members**

   - Click "👥 View Users"
   - Browse through paginated profiles
   - Click profile links to view on LinkedIn

4. **Manage Your Profile**
   - "🔄 Update Profile": Modify your information
   - "❌ Delete Profile": Remove your profile

## 📝 Logging

Logs are stored in `logs/bot.log`:

- Maximum size: 1MB
- Backup count: 5 files
- Log level: INFO

## 🛡️ Security Features

- Rate limiting for spam prevention
- SQL injection protection via SQLAlchemy
- Input validation for LinkedIn URLs
- Secure environment variable management

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Support

For support, email Alphalencho4@gmail.com or open an issue in the repository.

---

Built with Python and ❤️ for the Information Systems Community
