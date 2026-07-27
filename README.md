# VennLedger

**A powerful, privacy-first desktop finance tracker engineered for the modern power user.** 

VennLedger combines the security of local data storage with the cutting-edge capabilities of local Large Language Models (LLMs). Effortlessly parse raw financial journals into structured data, manage complex multi-currency portfolios with historical exchange rates, and secure your financial history with automated, encrypted Google Drive backups—all without compromising your privacy.

---

## 🚀 Key Features

*   🧠 **Advanced AI Expense Parser (Local LLM):** Say goodbye to manual data entry. VennLedger integrates with Ollama to run `mistral:7b` locally, intelligently parsing unstructured text (like daily expense journals) into structured, database-ready JSON objects.
*   💱 **Multi-Currency & Historical FX:** Native support for handling multiple fiat and crypto currencies. Features a robust exchange rate engine that fetches historical FX rates based on transaction timestamps, ensuring your Net Worth is always accurately calculated in your Base Currency.
*   🔒 **Uncompromising Local Privacy:** Your financial data is yours. Everything is stored in a local SQLite database (`tracker.db`) using Write-Ahead Logging (WAL) for high performance and reliability. No telemetry, no third-party cloud databases.
*   ☁️ **Google Drive ZIP Backups:** Seamlessly backup your entire database and configuration state. VennLedger packages your data into a compressed ZIP archive and uploads it directly to your personal Google Drive via OAuth 2.0.
*   📊 **Interactive Financial Dashboard:** Visualize your cash flow, expense breakdowns, and net worth trends with dynamic, hover-responsive Matplotlib charts embedded directly into the CustomTkinter UI.
*   ⚙️ **Dynamic Master Data Management:** Fully customizable Categories, Payment Methods, Vendors, Payers, Streams, and Projects.
*   📝 **Comprehensive Ledger Management:** Intuitive data grids to manually add, edit, duplicate, and delete expenses, incomes, and account transfers with ease.

---

## 🛠️ Tech Stack

VennLedger is built on a robust, modern Python stack:

| Component | Technology / Library | Description |
| :--- | :--- | :--- |
| **GUI Framework** | `customtkinter` | Modern, dark-mode-first desktop UI components. |
| **Database ORM** | `SQLAlchemy` (v2.0+) | High-performance SQLite database interactions and schema management. |
| **AI Integration** | `ollama` | Python client for local LLM execution (Mistral 7B). |
| **Data Visualization**| `matplotlib` & `mplcursors` | Interactive financial charting and trend analysis. |
| **Cloud Backup** | `google-api-python-client` | Google Drive API integration for secure ZIP uploads. |
| **Date Handling** | `tkcalendar` | Interactive date-picker widgets for transaction logging. |

---

## 🛑 Prerequisites

Before installing VennLedger, you **must** have Ollama installed and the required model pulled to your local machine. The AI parsing features will fail to connect if the Ollama daemon is not running.

1. Install [Ollama](https://ollama.com/).
2. Open your terminal and pull the Mistral 7B model:
   ```bash
   ollama pull mistral:7b
   ```
3. Ensure the Ollama background service is running before launching VennLedger.

---

## 💻 Installation (Source)

Follow these steps to get VennLedger running in your local development environment:

**1. Clone the repository:**
```bash
git clone https://github.com/Venn77/venn-ledger.git
cd VennLedger
```

**2. Create and activate a virtual environment (Recommended):**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Install the required dependencies:**
```bash
pip install -r requirements.txt
```

**4. Launch the application:**
```bash
python main_app.py
```
*(Note: On the very first run, VennLedger will guide you through a First-Run Wizard to set up your Base Currency and initial account balances).*

---

## ☁️ Google Drive Setup

To enable the **Backup to Drive** feature, you must provide your own Google Cloud OAuth 2.0 credentials.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project and enable the **Google Drive API**.
3. Navigate to **APIs & Services > Credentials**.
4. Create a new **OAuth 2.0 Client ID** (Select "Desktop app" as the application type).
5. Download the JSON file and rename it to exactly `credentials.json`.
6. Open VennLedger, navigate to the **Master Data** (Settings) tab, and click **Open Config Folder**.
7. Move your `credentials.json` file into this configuration folder.
8. Click **Backup to Drive** in the app. A browser window will open asking you to authorize the app. Once authorized, a `token.json` will be generated automatically for future seamless backups.

---

## 🤖 AI Setup & Customization

To achieve 100% parsing accuracy, the AI must be tailored to your specific Master Data (your custom categories, payment methods, etc.). 

Navigate to the **AI Import** tab in VennLedger to customize the parser:

*   **Parser Rules:** Click the ⚙️ icon to open `ai_prompt_template.txt`. Here, you can edit the `<mapping_table>` and `<examples>` to perfectly match your database. For instance, if your database uses "Amex Card" instead of "Credit Card", update the mapping table so the LLM outputs the exact string VennLedger expects.
*   **Skip Terms:** Click the 🚫 icon to open `ai_skip_terms.txt`. Add keywords (one per line) like `Transfer`, `Withdrawal`, or `Ignore`. The parser will completely bypass any line in your raw text file starting with these words, saving processing time and preventing hallucinated transactions.

---

## 🛡️ Data Privacy Statement

**Your finances are strictly confidential.** 
VennLedger is architected with a local-first philosophy. 
* All financial records, master data, and configurations are stored locally on your machine in a SQLite database. 
* The AI Expense Parser utilizes Ollama to process your data locally—**no financial data is ever sent to OpenAI, Anthropic, or any external API.** 
* Network requests are only made if you explicitly trigger a Google Drive backup, which securely transfers an encrypted ZIP directly to your personal Google account.