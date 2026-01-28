#!/usr/bin/env python3
"""
Database models for trade tracking
"""

from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class Trade(Base):
    """Trade record"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    trade_date = Column(DateTime, default=datetime.now)

    # Entry details
    spy_price = Column(Float)
    spx_price = Column(Float)
    spy_strike = Column(Float)
    spx_strike = Column(Float)

    spy_entry_bid = Column(Float)
    spy_entry_ask = Column(Float)
    spx_entry_bid = Column(Float)
    spx_entry_ask = Column(Float)

    entry_credit = Column(Float)
    entry_time = Column(DateTime)
    entry_filled = Column(Boolean, default=False)

    # Exit details
    spy_exit_price = Column(Float, nullable=True)
    spx_exit_price = Column(Float, nullable=True)
    exit_cost = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    exit_reason = Column(String, nullable=True)

    # P&L
    final_pnl = Column(Float, nullable=True)
    commissions = Column(Float, default=0.0)

    # Status
    status = Column(String, default='PENDING')  # PENDING, ACTIVE, CLOSED, ERROR

    def __repr__(self):
        return f"<Trade(id={self.id}, date={self.trade_date}, pnl={self.final_pnl})>"


class DailySummary(Base):
    """Daily summary statistics"""
    __tablename__ = 'daily_summary'

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.now)

    trades_count = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)

    total_pnl = Column(Float, default=0.0)
    total_commissions = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)

    max_drawdown = Column(Float, default=0.0)

    def __repr__(self):
        return f"<DailySummary(date={self.date}, pnl={self.net_pnl})>"


class SystemState(Base):
    """System state for persistence"""
    __tablename__ = 'system_state'

    id = Column(Integer, primary_key=True)
    last_updated = Column(DateTime, default=datetime.now)

    # Current state
    is_trading = Column(Boolean, default=False)
    open_positions = Column(Integer, default=0)
    daily_pnl = Column(Float, default=0.0)

    # Counters
    trades_today = Column(Integer, default=0)
    errors_today = Column(Integer, default=0)

    def __repr__(self):
        return f"<SystemState(trading={self.is_trading}, positions={self.open_positions})>"


# Database manager
class DatabaseManager:
    """Manage database connections and operations"""

    def __init__(self, db_path: str = "data/trading.db"):
        """Initialize database"""
        self.db_path = db_path

        # Create directory if needed
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Create engine
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)

        # Create tables
        Base.metadata.create_all(self.engine)

        # Create session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def add_trade(self, trade_data: dict) -> Trade:
        """Add a new trade"""
        trade = Trade(**trade_data)
        self.session.add(trade)
        self.session.commit()
        return trade

    def update_trade(self, trade_id: int, updates: dict) -> Trade:
        """Update a trade"""
        trade = self.session.query(Trade).filter_by(id=trade_id).first()
        if trade:
            for key, value in updates.items():
                setattr(trade, key, value)
            self.session.commit()
        return trade

    def get_active_trades(self):
        """Get all active trades"""
        return self.session.query(Trade).filter_by(status='ACTIVE').all()

    def get_todays_trades(self):
        """Get today's trades"""
        today = datetime.now().date()
        return self.session.query(Trade).filter(
            Trade.trade_date >= datetime.combine(today, datetime.min.time())
        ).all()

    def get_all_trades(self):
        """Get all trades"""
        return self.session.query(Trade).all()

    def update_daily_summary(self, summary_data: dict):
        """Update daily summary"""
        today = datetime.now().date()
        summary = self.session.query(DailySummary).filter(
            DailySummary.date >= datetime.combine(today, datetime.min.time())
        ).first()

        if not summary:
            summary = DailySummary(**summary_data)
            self.session.add(summary)
        else:
            for key, value in summary_data.items():
                setattr(summary, key, value)

        self.session.commit()
        return summary

    def get_system_state(self) -> SystemState:
        """Get or create system state"""
        state = self.session.query(SystemState).first()
        if not state:
            state = SystemState()
            self.session.add(state)
            self.session.commit()
        return state

    def update_system_state(self, updates: dict):
        """Update system state"""
        state = self.get_system_state()
        for key, value in updates.items():
            setattr(state, key, value)
        state.last_updated = datetime.now()
        self.session.commit()
        return state

    def close(self):
        """Close database connection"""
        self.session.close()
