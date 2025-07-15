# sarimaforecast
capstone 

# 🍽️ Restaurant Inventory and Forecasting System

A capstone project developed using **Flask**, **SQLite**, and **Bootstrap** to help restaurants manage inventory, forecast ingredient usage, and generate dynamic grocery lists based on consumption patterns.

---

- ✅ **Track daily usage** of menu items with quantity and date
- 🍳 **Recipe management**: define which ingredients are used in each menu item
- 📅 **Monitor daily orders** to understand which menu items are being sold
- 📊 **Forecast ingredient demand** using SARIMA models
- 🧾 **Auto-generate grocery lists** based on forecasted consumption
- 📉 **Inventory tracking** with dynamic stock level progress bars
- 🔐 **Role-based access control** (Admin, Staff, Approver) for secure operations

---

## 🛠️ Tech Stack

- **Backend**: Python (Flask), SQLAlchemy, Flask-Migrate  
- **Frontend**: HTML, CSS (Bootstrap), JavaScript  
- **Database**: SQLite  
- **Forecasting**: SARIMA (via `statsmodels`)  
- **Deployment**: Render  

---

## 🚀 Getting Started

Follow these steps to set up the project locally:

```bash
# 1. Clone the repository
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env  # Then update the .env file with your values

# 5. Initialize the database
flask db upgrade

# 6. Run the app
flask run

📚 What I Learned
Implemented a full-stack system with Flask and SQLAlchemy

Applied SARIMA for real-world demand forecasting

Managed data flow between forecasting, inventory, daily usage of menu items, and UI

Practiced secure deployment and environment variable handling

Understood the importance of role-based access and workflow control
