from sqlalchemy import create_engine, Column, String, DateTime, LargeBinary, Integer, Float, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL
from datetime import datetime, timedelta

Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    qb_connected = Column(Boolean, default=False)
    qb_realm_id = Column(String(255))
    qb_access_token_enc = Column(LargeBinary)
    qb_refresh_token_enc = Column(LargeBinary)
    qb_expires_in = Column(Integer)
    qb_token_updated_at = Column(DateTime)
    
    def is_token_expired(self):
        if not self.qb_token_updated_at or not self.qb_expires_in:
            return True
        expiry = self.qb_token_updated_at + timedelta(seconds=self.qb_expires_in)
        return datetime.utcnow() > expiry - timedelta(minutes=5)

class Invoice(Base):
    __tablename__ = 'invoices'
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    email_id = Column(String(255))
    storage_key = Column(String(500))  # R2/S3 key
    storage_type = Column(String(50))  # 'r2' or 'local'
    filename = Column(String(255))
    file_size = Column(Integer)
    
    status = Column(String(50), default='pending')
    error_message = Column(String(500))
    
    vendor_name = Column(String(255))
    vendor_email = Column(String(255))
    invoice_number = Column(String(100))
    invoice_date = Column(DateTime)
    due_date = Column(DateTime)
    total_amount = Column(Float)
    tax_amount = Column(Float)
    currency = Column(String(3), default='USD')
    line_items = Column(JSON)
    raw_extraction = Column(JSON)
    
    qb_bill_id = Column(String(255))
    qb_posted_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(engine)
