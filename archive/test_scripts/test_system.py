#!/usr/bin/env python3
"""
System Test Script
Verifies all components are working correctly
"""

import sys
import os
import requests
import time
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

def print_header(text):
    """Print section header"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}{text}")
    print(f"{Fore.CYAN}{'='*70}")

def print_success(text):
    """Print success message"""
    print(f"{Fore.GREEN}✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"{Fore.RED}❌ {text}")

def print_info(text):
    """Print info message"""
    print(f"{Fore.YELLOW}ℹ️  {text}")

def test_dependencies():
    """Test that all required packages are installed"""
    print_header("Testing Dependencies")

    required = [
        'ib_insync',
        'pandas',
        'flask',
        'flask_socketio',
        'schedule',
        'sqlalchemy',
        'yaml',
        'dotenv'
    ]

    all_ok = True
    for package in required:
        try:
            if package == 'yaml':
                __import__('yaml')
            elif package == 'dotenv':
                __import__('dotenv')
            else:
                __import__(package)
            print_success(f"{package}")
        except ImportError:
            print_error(f"{package} - not installed")
            all_ok = False

    return all_ok

def test_file_structure():
    """Test that all required files exist"""
    print_header("Testing File Structure")

    required_files = [
        'main.py',
        'config.yaml',
        '.env',
        'src/broker/ibkr_client.py',
        'src/strategy/spy_spx_strategy.py',
        'src/strategy/position_monitor.py',
        'src/database/models.py',
        'src/ui/dashboard.py',
        'src/ui/templates/dashboard.html',
    ]

    all_ok = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print_success(f"{file_path}")
        else:
            print_error(f"{file_path} - missing")
            all_ok = False

    return all_ok

def test_dashboard_connection():
    """Test dashboard HTTP connection"""
    print_header("Testing Dashboard Connection")

    url = "http://127.0.0.1:5000"

    try:
        print_info("Attempting to connect to dashboard...")
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            print_success(f"Dashboard responding on {url}")
            print_info(f"Response size: {len(response.content)} bytes")

            # Check if HTML contains expected content
            if b"SPY/SPX Trading Dashboard" in response.content:
                print_success("Dashboard HTML content verified")
                return True
            else:
                print_error("Dashboard HTML missing expected content")
                return False
        else:
            print_error(f"Dashboard returned status code: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print_error("Could not connect to dashboard")
        print_info("Is main.py running?")
        return False
    except requests.exceptions.Timeout:
        print_error("Connection timed out")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_api_endpoints():
    """Test dashboard API endpoints"""
    print_header("Testing API Endpoints")

    base_url = "http://127.0.0.1:5000"
    endpoints = [
        '/api/status',
        '/api/account',
        '/api/positions',
        '/api/trades',
        '/api/market',
        '/api/performance'
    ]

    all_ok = True
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print_success(f"{endpoint} - OK")
            else:
                print_error(f"{endpoint} - Status {response.status_code}")
                all_ok = False
        except Exception as e:
            print_error(f"{endpoint} - {str(e)}")
            all_ok = False

    return all_ok

def test_database():
    """Test database connection and tables"""
    print_header("Testing Database")

    try:
        from src.database.models import DatabaseManager

        # Try to create/open database
        db = DatabaseManager('data/trading.db')
        print_success("Database connection successful")

        # Test basic operations
        state = db.get_system_state()
        print_success("System state table accessible")

        trades = db.get_all_trades()
        print_info(f"Total trades in database: {len(trades)}")

        db.close()
        print_success("Database operations working")

        return True

    except Exception as e:
        print_error(f"Database error: {e}")
        return False

def test_ibkr_connection():
    """Test IB Gateway connection"""
    print_header("Testing IB Gateway Connection")

    try:
        from src.broker.ibkr_client import IBKRClient
        from dotenv import load_dotenv

        load_dotenv()

        host = os.getenv('IB_HOST', '127.0.0.1')
        port = int(os.getenv('IB_PORT', 4002))

        print_info(f"Attempting connection to {host}:{port}...")

        client = IBKRClient(host=host, port=port)

        if client.connect():
            print_success("Connected to IB Gateway")

            # Get account info
            account = client.get_account_summary()
            if account:
                print_success(f"Account: {account.get('account_id', 'Unknown')}")
                print_success(f"Balance: ${account.get('net_liquidation', 0):,.2f}")

            # Test market data
            print_info("Testing market data access...")
            spy_price = client.get_current_price('SPY')
            if spy_price:
                print_success(f"SPY Price: ${spy_price:.2f}")
            else:
                print_info("SPY price unavailable (market may be closed)")

            client.disconnect()
            print_success("IB Gateway test completed")
            return True
        else:
            print_error("Could not connect to IB Gateway")
            print_info("Make sure:")
            print_info("  1. IB Gateway or TWS is running")
            print_info("  2. API is enabled (Configure → Settings → API)")
            print_info("  3. Port is correct (4002 for paper, 4001 for live)")
            return False

    except Exception as e:
        print_error(f"IB Gateway connection error: {e}")
        return False

def main():
    """Run all tests"""
    print(f"{Fore.MAGENTA}{Style.BRIGHT}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║          SPY/SPX TRADING SYSTEM - COMPREHENSIVE TEST             ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(Style.RESET_ALL)

    results = {}

    # Run tests
    results['Dependencies'] = test_dependencies()
    results['File Structure'] = test_file_structure()
    results['Dashboard'] = test_dashboard_connection()
    results['API Endpoints'] = test_api_endpoints()
    results['Database'] = test_database()
    results['IB Gateway'] = test_ibkr_connection()

    # Summary
    print_header("Test Summary")

    all_passed = True
    for test_name, result in results.items():
        if result:
            print_success(f"{test_name:<20} PASSED")
        else:
            print_error(f"{test_name:<20} FAILED")
            all_passed = False

    print(f"\n{Fore.CYAN}{'='*70}\n")

    if all_passed:
        print(f"{Fore.GREEN}{Style.BRIGHT}🎉 ALL TESTS PASSED! System is ready to use.")
        print(f"\n{Fore.CYAN}Next steps:")
        print(f"  1. Open dashboard: {Fore.WHITE}http://localhost:5000")
        print(f"  2. Click 'Start' to enable trading")
        print(f"  3. System will trade automatically at 9:35 AM ET")
        return 0
    else:
        print(f"{Fore.RED}{Style.BRIGHT}⚠️  SOME TESTS FAILED")
        print(f"\n{Fore.YELLOW}Please fix the failed tests before using the system.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
