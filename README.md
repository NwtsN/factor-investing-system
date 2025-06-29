# Investment Analysis System 📈

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

A Python-based investment analysis system that fetches financial data, performs fundamental analysis, and provides investment insights using quantitative metrics like CROCI (Cash Return on Capital Invested).

## 🚀 Features

- **Intelligent Data Fetching**: Automated retrieval with smart caching to avoid redundant API calls
- **Financial Analysis**: CROCI calculation and other investment metrics
- **Database Storage**: SQLite-based data persistence with comprehensive schema
- **Robust Logging**: Database and console logging with session tracking
- **Rate Limiting**: Intelligent handling of API rate limits with exponential backoff
- **Timeout Protection**: Configurable program runtime limits to prevent indefinite execution
- **Transaction Modes**: Choose between all-or-nothing or individual database commits
- **Data Staging**: 24-hour staging cache with automatic cleanup every 5 minutes
- **Modular Architecture**: Clean separation of concerns for maintainability

## 📊 Supported Metrics

- Market Capitalization
- Enterprise Value / EBITDA
- Price-to-Earnings Ratio
- CROCI (Cash Return on Capital Invested)
- Revenue CAGR
- Dividend Growth Rate
- Technical Indicators (ATR, Moving Averages, MACD)
- 17+ extracted fundamental metrics including TTM, quarterly, and annual data

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

## 🎮 Command Line Options

```bash
python main.py [OPTIONS]

Options:
  --timeout, -t <minutes>      Maximum runtime in minutes before program stops
  --transaction-mode <mode>    Database insertion mode:
                              - all-or-nothing: Single transaction (default)
                              - individual: Commit each ticker separately

Examples:
  python main.py                              # Run with defaults
  python main.py --timeout 30                 # Limit runtime to 30 minutes
  python main.py --transaction-mode individual # Use individual commits
  python main.py -t 60 --transaction-mode all-or-nothing  # Combined options
```

## 📁 Project Structure

```
invsys/
├── src/
│   ├── main.py                  # Entry point with CLI argument parsing
│   ├── config.py                # Centralized configuration
│   ├── database/
│   │   ├── database_setup.py    # Database initialization & schema
│   │   ├── database_handler.py  # Data freshness & staging management
│   │   ├── data_inserter.py     # Database insertion with transaction support
│   │   └── fetch_data.py        # API data fetching & processing
│   ├── utils/
│   │   ├── logging.py           # Database & console logging
│   │   └── program_timer.py     # Timeout functionality
│   └── analysis/                # Analysis modules (future)
├── config/
│   ├── invsys_environment_template.yml  # Environment template
│   └── invsys_environment.yml           # Your config (gitignored)
├── data/
│   ├── database_schema.sql      # Database schema definition
│   └── *.db                     # Database files (gitignored)
└── docs/                        # Documentation
```

## 🛠️ Architecture

### Data Flow
```
main.py → DataManager → DataFetcher → API calls → Parse data → Stage → DataInserter → Database
           ↓                ↓                                     ↓
    Check freshness   Skip if recent                     24hr cache with cleanup
```

### Core Components

#### **DataFetcher** (`fetch_data.py`)
- Handles all Alpha Vantage API interactions
- Implements intelligent rate limiting (12 seconds between calls)
- Exponential backoff for rate limit errors (up to 5 minutes)
- Validates data quality (minimum 10 fields required)
- Supports batch operations with DataManager integration

#### **DataManager** (`database_handler.py`)
- Tracks data freshness to avoid unnecessary API calls
- Configurable refresh policies (90 days minimum, 365 days force)
- Manages staging cache with 24-hour expiration
- Automatic cleanup every 5 minutes
- Quarterly earnings cycle awareness

#### **DataInserter** (`data_inserter.py`)
- Handles all database insertions
- Supports transaction modes (all-or-nothing vs individual)
- Automatic stock record creation
- Comprehensive error handling with rollback

#### **DatabaseManager** (`database_setup.py`)
- Initializes SQLite database and schema
- Validates table existence
- Provides logger instances

#### **Logger** (`logging.py`)
- Dual logging to database and console
- Color-coded console output
- Session-based tracking

#### **Timeout** (`program_timer.py`)
- Prevents indefinite program execution
- Configurable timeout in minutes
- Clean shutdown with exit code 124

## 🔒 Security

- **API keys are gitignored** - never committed to version control
- **Database files excluded** from version control
- **Template-based configuration** for easy secure setup
- **Environment-based API key management**
- **Input validation** for all user inputs and API responses

## 📈 Supported Tickers

Currently configured for major stocks (AAPL, MSFT, GOOGL, TSLA). Easy to extend to full S&P 500 or custom ticker lists by modifying the `TICKERS` list in `main.py`.

## 🧮 Financial Calculations

### CROCI (Cash Return on Capital Invested)
The system calculates CROCI using:
- Operating Cash Flow (TTM)
- Working Capital changes
- Total Assets
- Total Debt
- Cash Equivalents

*Note: Investments in Associates are excluded from the denominator as they're not available via Alpha Vantage API, potentially biasing CROCI calculations downwards.*

### Effective Tax Rate
Smart tax rate calculation with edge case handling:
- Uses actual tax rate when available
- Defaults to 21% for unusual cases
- Handles tax refunds and loss-making companies

## 🚧 Development Status

### ✅ Completed
- Data fetching infrastructure with intelligent caching
- Complete database schema with 6 core tables
- Robust logging system with database storage
- Configuration management
- Data insertion layer with transaction support
- Timeout functionality for runtime limits
- Staging cache with automatic cleanup
- Command line interface

### 🔄 In Progress
- Additional financial metrics calculations
- Performance optimization for large ticker lists

### 📋 Future Plans
- Analysis algorithms for investment decisions
- Portfolio optimization features
- Backtesting framework
- Web interface for data visualization
- Support for additional data providers
- Real-time price updates

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guide
- Update documentation as needed

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

Message me on LinkedIn at [https://www.linkedin.com/in/nwtsn/](https://www.linkedin.com/in/nwtsn/)

Project Link: [https://github.com/NwtsN/factor-investing-system](https://github.com/NwtsN/factor-investing-system) 