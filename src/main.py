#!/usr/bin/env python3
"""
Investment Analysis System (invsys)
Main entry point for the investment analysis system.

Copyright (C) 2025 Neil Donald Watson

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import sys
import yaml
import uuid

# Add src directory to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))

from database.database_setup import DatabaseManager
from database.insert_data import DataFetcher, DataManager
from config import CONFIG_FILE_PATH

# Optional: Load tickers from file or hardcode a few for testing
TICKERS = ["AAPL", "MSFT", "GOOGL", "TSLA"]  # You can swap in your full S&P 500 list later

def load_config() -> dict:
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load config file at {CONFIG_FILE_PATH}: {e}")
        exit(1)

def main() -> None:
    config = load_config()
    api_key = config.get("api_keys", {}).get("alpha_vantage")

    if not api_key:
        print("[ERROR] API key not found in config.")
        exit(1)

    session_id = str(uuid.uuid4())
    print(f"[INFO] Starting session {session_id}")

    with DatabaseManager() as db:
        logger = db.get_logger(session_id)
        fetcher = DataFetcher(logger=logger)

        success_count = 0
        fail_count = 0
        cached_data = {}  # Store raw API responses for later insertion

        for i, ticker in enumerate(TICKERS):
            logger.log("Main", f"Fetching fundamentals for {ticker}", level="INFO")
            success, fundamentals, raw_data = fetcher.fetch_fundamentals(ticker, api_key=api_key)
            if success:
                success_count += 1
                cached_data[ticker] = {
                    'fundamentals': fundamentals,
                    'raw_api_data': raw_data
                }
            else:
                fail_count += 1

            # Alpha Vantage free plan = 5 requests per minute
            if (i + 1) % 5 == 0:
                logger.log("Main", "Sleeping 60s to avoid Alpha Vantage rate limit", level="INFO")
                time.sleep(60)

        logger.log("Main", f"Session complete: {success_count} successful, {fail_count} failed", level="INFO")
        logger.log("Main", f"Cached data available for {len(cached_data)} tickers", level="INFO")
        
        # TODO: Later implement DataInserter to process cached_data

if __name__ == "__main__":
    main()

