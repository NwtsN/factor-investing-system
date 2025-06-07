# Investment Analysis System 📈

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

A Python-based investment analysis system that fetches financial data, performs fundamental analysis, and provides investment insights using quantitative metrics like CROCI (Cash Return on Capital Invested).

## 🚀 Features

- **Data Fetching**: Automated retrieval of fundamental data from Alpha Vantage API
- **Financial Analysis**: CROCI calculation and other investment metrics
- **Database Storage**: SQLite-based data persistence with comprehensive schema
- **Robust Logging**: Database and console logging with session tracking
- **Rate Limiting**: Handles API rate limits automatically
- **Modular Architecture**: Clean separation of concerns for maintainability

## 📊 Supported Metrics

- Market Capitalization
- Enterprise Value / EBITDA
- Price-to-Earnings Ratio
- CROCI (Cash Return on Capital Invested)
- Revenue CAGR
- Dividend Growth Rate
- Technical Indicators (ATR, Moving Averages, MACD)

## 🔧 Quick Start

### Prerequisites
- Python 3.10+
- Conda package manager
- Alpha Vantage API key ([Get one free here](https://www.alphavantage.co/support/#api-key))

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd invsys
```

2. **Create your configuration file**
```bash
cp config/invsys_environment_template.yml config/invsys_environment.yml
```

3. **Add your API key**
Edit `config/invsys_environment.yml`:
```yaml
api_keys:
  alpha_vantage: "YOUR_ACTUAL_API_KEY_HERE"
```

4. **Create the environment**
```bash
conda env create -f config/invsys_environment.yml
conda activate invsys
```

5. **Run the system**
```bash
cd src
python main.py
```

## 📁 Project Structure

```
invsys/
├── src/
│   ├── main.py                 # Entry point
│   ├── config.py               # Centralized configuration
│   ├── database/
│   │   ├── database_setup.py   # Database initialization
│   │   └── insert_data.py      # Data fetching & processing
│   ├── utils/
│   │   └── logging.py          # Logging utilities
│   ├── analysis/               # Analysis modules (future)
│   └── data_collection/        # Data collection (future)
├── config/
│   ├── invsys_environment_template.yml  # Environment template
│   └── invsys_environment.yml          # Your config (gitignored)
├── data/
│   ├── database_schema.sql     # Database schema
│   └── *.db                    # Database files (gitignored)
└── docs/                       # Documentation (future)
```

## 🛠️ Architecture

### Data Flow
```
main.py → DataFetcher → API calls → Parse data → Cache → Future: DataInserter → Database
```

### Core Components
- **DataFetcher**: Handles API interactions with Alpha Vantage
- **DatabaseManager**: Manages SQLite database and schema
- **Logger**: Provides structured logging to database and console
- **DataInserter**: (Future) Handles data persistence
- **DataManager**: (Future) Manages data freshness and updates

## 🔒 Security

- **API keys are gitignored** - never committed to version control
- **Database files excluded** from version control
- **Template-based configuration** for easy secure setup
- **Environment-based API key management**

## 📈 Supported Tickers

Currently configured for major stocks (AAPL, MSFT, GOOGL, TSLA). Easy to extend to full S&P 500 or custom ticker lists.

## 🧮 CROCI Calculation

The system calculates **Cash Return on Capital Invested** using:
- Operating Cash Flow
- Working Capital changes  
- Total Assets
- Total Debt
- Cash Equivalents

*Note: Investments in Associates are excluded from the denominator as they're not available via Alpha Vantage API, biasing CROCI calculations upward.*

## 🚧 Development Status

- ✅ Data fetching infrastructure
- ✅ Database schema design
- ✅ Logging system
- ✅ Configuration management
- 🔄 Currently working on: Data insertion layer
- 📋 Future: Analysis algorithms, portfolio optimization, backtesting

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the GNU Affero General Public License v3.0 - see the LICENSE file for details.

### 🔒 License Compliance

If you use this software:
- **For personal use**: You're free to use, modify, and study the code
- **If you distribute or modify**: You must provide source code under AGPL-3.0
- **If you run as a web service**: You must provide source code to users (AGPL Section 13)
- **Commercial use**: Allowed, but modifications must remain open source

For questions about licensing or commercial exceptions, please open an issue or contact via LinkedIn.

## 📧 Contact

Message me on Linkedin at (https://www.linkedin.com/in/nwtsn/)
Project Link: [https://github.com/NwtsN/invsys](https://github.com/NwtsN/invsys) 