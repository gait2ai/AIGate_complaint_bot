"""
AI Gate for Artificial Intelligence Applications
Database Manager Module

This module provides the DatabaseManager class for handling all SQLite database
interactions for the complaint management system. It manages connections,
table creation, and data manipulation operations.
"""

import sqlite3
import logging
import threading
import os
from datetime import datetime
from typing import Optional, List, Tuple


class DatabaseManager:
    """
    A comprehensive SQLite database manager for the complaint management system.
    
    This class handles database connections, table creation, and provides thread-safe
    methods for executing SQL queries. It manages three main tables: beneficiaries,
    complaints, and classification_keys.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the DatabaseManager with the specified database path.
        
        Args:
            db_path (str): Full path to the SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
        self._lock = threading.RLock()
        
        # Ensure the database file's directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> None:
        """
        Establish a connection to the SQLite database.
        
        Creates the database connection and cursor objects. Handles potential
        exceptions during connection establishment.
        
        Raises:
            sqlite3.Error: If database connection fails
        """
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self.logger.info(f"Successfully connected to database: {self.db_path}")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to database {self.db_path}: {e}")
            raise
    
    def close(self) -> None:
        """
        Close the database connection and reset connection objects.
        
        Safely closes the database connection and sets connection objects to None.
        """
        try:
            if self.conn:
                self.conn.close()
                self.logger.info("Database connection closed successfully")
        except sqlite3.Error as e:
            self.logger.error(f"Error closing database connection: {e}")
        finally:
            self.conn = None
            self.cursor = None
    
    def create_tables(self) -> None:
        """
        Create all required tables if they don't exist and initialize default data.
        
        Creates the beneficiaries, complaints, and classification_keys tables.
        Also populates classification_keys with default data if the table is empty.
        
        Raises:
            sqlite3.Error: If table creation fails
        """
        if not self.conn:
            raise sqlite3.Error("Database connection not established. Call connect() first.")
        
        try:
            with self._lock:
                # Create beneficiaries table
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS beneficiaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_telegram_id INTEGER UNIQUE,
                        name TEXT NOT NULL,
                        sex TEXT,
                        phone TEXT,
                        residence_status TEXT,
                        governorate TEXT,
                        directorate TEXT,
                        village_area TEXT,
                        created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                        updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
                    )
                """)
                
                # Create complaints table
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS complaints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        beneficiary_id INTEGER NOT NULL,
                        original_complaint_text TEXT NOT NULL,
                        complaint_summary_en TEXT,
                        complaint_type TEXT,
                        complaint_category TEXT,
                        complaint_sensitivity TEXT,
                        is_critical INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        assigned_to TEXT,
                        resolution_notes TEXT,
                        created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                        submitted_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                        updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                        resolved_at TEXT,
                        source_channel TEXT NOT NULL DEFAULT 'TELEGRAM',
                        internal_notes TEXT,
                        follow_up_required INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY (beneficiary_id) REFERENCES beneficiaries (id)
                    )
                """)
                
                # Create classification_keys table
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS classification_keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_type TEXT NOT NULL,
                        key_value TEXT NOT NULL,
                        parent_value TEXT,
                        description TEXT,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        sort_order INTEGER DEFAULT 0
                    )
                """)
                
                self.conn.commit()
                self.logger.info("All tables created successfully")
                
                # Initialize default classification keys if table is empty
                self._initialize_default_classification_keys()
                
        except sqlite3.Error as e:
            self.logger.error(f"Error creating tables: {e}")
            if self.conn:
                self.conn.rollback()
            raise
    
    def _initialize_default_classification_keys(self) -> None:
        """
        Initialize the classification_keys table with default data if it's empty.
        
        Populates the table with default complaint types, categories, and sensitivity levels.
        """
        try:
            # Check if table is empty
            count_result = self.fetch_one("SELECT COUNT(*) FROM classification_keys")
            if count_result and count_result[0] == 0:
                self.logger.info("Initializing default classification keys")
                
                # Default classification data
                default_data = [
                    # Complaint Types
                    ("Type of complaint", "Request for Information", None, None, 1, 1),
                    ("Type of complaint", "Request for Help", None, None, 1, 2),
                    ("Type of complaint", "Thank You Letter", None, None, 1, 3),
                    ("Type of complaint", "Suggestion", None, None, 1, 4),
                    ("Type of complaint", "Service Dissatisfaction", None, None, 1, 5),
                    ("Type of complaint", "Inappropriate Behavior", None, None, 1, 6),
                    ("Type of complaint", "Fraud Allegation", None, None, 1, 7),
                    ("Type of complaint", "PSEA", None, None, 1, 8),
                    
                    # Complaint Categories
                    ("Complaint category", "Water Trucking", "Request for Information", None, 1, 1),
                    ("Complaint category", "Rental Support", "Request for Help", None, 1, 2),
                    ("Complaint category", "Distributing Energy Kits", None, None, 1, 3),
                    ("Complaint category", "Distributing NFIs", None, None, 1, 4),
                    ("Complaint category", "Distributing B/C HKs", None, None, 1, 5),
                    ("Complaint category", "Rehabilitating Water Network", None, None, 1, 6),
                    ("Complaint category", "Waste Disposal", None, None, 1, 7),
                    ("Complaint category", "Distributing Chlorine Tablets", None, None, 1, 8),
                    ("Complaint category", "Replacing Damaged Sewage Line", None, None, 1, 9),
                    
                    # Complaint Sensitivity
                    ("Complaint sensitivity", "Sensitive", None, None, 1, 1),
                    ("Complaint sensitivity", "Insensitive", None, None, 1, 2),
                    ("Complaint sensitivity", "Highly Sensitive", None, None, 1, 3),
                ]
                
                # Insert default data
                insert_query = """
                    INSERT INTO classification_keys 
                    (key_type, key_value, parent_value, description, is_active, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                
                for data_row in default_data:
                    self.execute_query(insert_query, data_row)
                
                self.logger.info("Default classification keys initialized successfully")
            else:
                self.logger.debug("Classification keys table already contains data")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing default classification keys: {e}")
            raise
    
    def execute_query(self, query: str, params: Tuple = ()) -> None:
        """
        Execute a SQL query that modifies data (INSERT, UPDATE, DELETE).
        
        Args:
            query (str): SQL query string
            params (Tuple): Query parameters for parameterized queries
            
        Raises:
            sqlite3.Error: If query execution fails
        """
        if not self.conn:
            raise sqlite3.Error("Database connection not established. Call connect() first.")
        
        try:
            with self._lock:
                self.cursor.execute(query, params)
                self.conn.commit()
                self.logger.debug(f"Query executed successfully: {query[:50]}...")
        except sqlite3.Error as e:
            self.logger.error(f"Error executing query: {e}")
            if self.conn:
                self.conn.rollback()
            raise
    
    def fetch_one(self, query: str, params: Tuple = ()) -> Optional[Tuple]:
        """
        Execute a SELECT query expected to return a single row.
        
        Args:
            query (str): SQL SELECT query string
            params (Tuple): Query parameters for parameterized queries
            
        Returns:
            Optional[Tuple]: Single row as a tuple, or None if no row found
            
        Raises:
            sqlite3.Error: If query execution fails
        """
        if not self.conn:
            raise sqlite3.Error("Database connection not established. Call connect() first.")
        
        try:
            with self._lock:
                self.cursor.execute(query, params)
                result = self.cursor.fetchone()
                self.logger.debug(f"Fetch one query executed: {query[:50]}...")
                return result
        except sqlite3.Error as e:
            self.logger.error(f"Error executing fetch_one query: {e}")
            raise
    
    def fetch_all(self, query: str, params: Tuple = ()) -> List[Tuple]:
        """
        Execute a SELECT query and return all rows.
        
        Args:
            query (str): SQL SELECT query string
            params (Tuple): Query parameters for parameterized queries
            
        Returns:
            List[Tuple]: All rows as a list of tuples
            
        Raises:
            sqlite3.Error: If query execution fails
        """
        if not self.conn:
            raise sqlite3.Error("Database connection not established. Call connect() first.")
        
        try:
            with self._lock:
                self.cursor.execute(query, params)
                results = self.cursor.fetchall()
                self.logger.debug(f"Fetch all query executed: {query[:50]}...")
                return results
        except sqlite3.Error as e:
            self.logger.error(f"Error executing fetch_all query: {e}")
            raise


# Example usage and testing
if __name__ == "__main__":
    # Example usage
    db_manager = DatabaseManager("./app/database/ins_data.db")
    
    try:
        # Connect to database
        db_manager.connect()
        
        # Create tables
        db_manager.create_tables()
        
        # Example: Insert a beneficiary (timestamps will be set automatically by SQLite)
        db_manager.execute_query(
            """INSERT INTO beneficiaries 
               (user_telegram_id, name, sex, phone, residence_status, 
                governorate, directorate, village_area)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (123456789, "John Doe", "Male", "+1234567890", "Resident",
             "Baghdad", "Al-Karkh", "Al-Mansour")
        )
        
        # Example: Fetch beneficiary
        beneficiary = db_manager.fetch_one(
            "SELECT * FROM beneficiaries WHERE user_telegram_id = ?",
            (123456789,)
        )
        print(f"Beneficiary found: {beneficiary}")
        
        # Example: Fetch all classification keys
        keys = db_manager.fetch_all("SELECT * FROM classification_keys")
        print(f"Total classification keys: {len(keys)}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db_manager.close()
