#!/usr/bin/env python3
"""
Web-based Dashboard for Trading System
Real-time monitoring and control
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import logging
from datetime import datetime
from typing import Dict, Any
import json

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'spy-spx-trading-dashboard'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', engineio_logger=False)

# Global reference to trading system (will be set by main.py)
trading_system = None


def set_trading_system(system):
    """Set reference to trading system"""
    global trading_system
    trading_system = system


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """Get current system status"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        status = trading_system.get_system_status()
        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions')
def get_positions():
    """Get current positions"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        positions = trading_system.get_positions_summary()
        return jsonify(positions)

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trades')
def get_trades():
    """Get trade history"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        trades = trading_system.get_trade_history(limit=limit)

        return jsonify(trades)

    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/account')
def get_account():
    """Get account information"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        account = trading_system.get_account_info()
        return jsonify(account)

    except Exception as e:
        logger.error(f"Error getting account: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/market')
def get_market():
    """Get current market prices"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        market = trading_system.get_market_prices()
        return jsonify(market)

    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/performance')
def get_performance():
    """Get performance metrics"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        performance = trading_system.get_performance_metrics()
        return jsonify(performance)

    except Exception as e:
        logger.error(f"Error getting performance: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/action/start', methods=['POST'])
def start_trading():
    """Start automated trading"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        trading_system.start_trading()
        return jsonify({'success': True, 'message': 'Trading started'})

    except Exception as e:
        logger.error(f"Error starting trading: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/action/stop', methods=['POST'])
def stop_trading():
    """Stop automated trading"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        trading_system.stop_trading()
        return jsonify({'success': True, 'message': 'Trading stopped'})

    except Exception as e:
        logger.error(f"Error stopping trading: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/action/close_all', methods=['POST'])
def close_all_positions():
    """Emergency close all positions"""
    try:
        if not trading_system:
            return jsonify({'error': 'Trading system not initialized'}), 500

        result = trading_system.emergency_close_all()
        return jsonify({'success': result, 'message': 'All positions closed'})

    except Exception as e:
        logger.error(f"Error closing positions: {e}")
        return jsonify({'error': str(e)}), 500


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('Client connected to dashboard')
    emit('connection_status', {'status': 'connected'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('Client disconnected from dashboard')


def broadcast_update(event_type: str, data: Dict[str, Any]):
    """
    Broadcast update to all connected clients

    Args:
        event_type: Type of event (position_update, trade_update, etc.)
        data: Event data
    """
    try:
        socketio.emit(event_type, data)
    except Exception as e:
        logger.error(f"Error broadcasting update: {e}")


def run_dashboard(host='127.0.0.1', port=5000):
    """
    Run the dashboard server

    Args:
        host: Host to bind to
        port: Port to listen on
    """
    logger.info(f"Starting dashboard on http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True, log_output=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_dashboard()
