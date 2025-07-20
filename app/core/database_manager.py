"""
AI Gate for Artificial Intelligence Applications
Database Manager Module

This module provides the DatabaseManager class for handling all SQLite database
interactions for the institution's complaint management system. It manages database
connections, schema creation, and provides thread-safe methods for data manipulation
operations across multiple interconnected tables including beneficiaries, complaints,
complaint_notes, and classification_keys. The class ensures data integrity through
proper foreign key constraints and supports comprehensive complaint tracking with
follow-up notes and user activity monitoring.
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
    methods for executing SQL queries. It manages four main tables: beneficiaries,
    complaints, complaint_notes, and classification_keys, with proper foreign key
    relationships and data integrity constraints.
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
        
        Creates the database connection and cursor objects. Enables foreign key
        constraints for proper referential integrity. Handles potential exceptions
        during connection establishment.
        
        Raises:
            sqlite3.Error: If database connection fails
        """
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # Enable foreign key constraints
            self.cursor.execute("PRAGMA foreign_keys = ON")
            self.conn.commit()
            
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
        
        Creates the beneficiaries, complaints, complaint_notes, and classification_keys
        tables with proper foreign key relationships. Also populates classification_keys
        with default data if the table is empty. All table creation is executed within
        a single transaction to ensure atomicity.
        
        Raises:
            sqlite3.Error: If table creation fails
        """
        if not self.conn:
            raise sqlite3.Error("Database connection not established. Call connect() first.")
        
        try:
            with self._lock:
                # Create beneficiaries table with enhanced schema
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
                        last_seen_at TEXT,
                        created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                        updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
                    )
                """)
                
                # Create complaints table with updated schema including submitter profile snapshot
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS complaints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reference_id TEXT UNIQUE,
                        beneficiary_id INTEGER NOT NULL,
                        -- Start: Submitter Profile Snapshot (NEW FIELDS)
                        submitter_name TEXT,
                        submitter_sex TEXT,
                        submitter_age INTEGER,
                        submitter_nationality TEXT,
                        submitter_phone TEXT,
                        submitter_email TEXT,
                        submitter_residence_status TEXT,
                        submitter_governorate TEXT,
                        submitter_directorate TEXT,
                        submitter_village TEXT,
                        submitter_disability TEXT,
                        -- End: Submitter Profile Snapshot
                        -- Renamed field: department -> sector
                        sector TEXT,
                        -- Existing Complaint and AI Analysis Fields
                        original_complaint_text TEXT NOT NULL,
                        complaint_summary_en TEXT,
                        complaint_type TEXT,
                        complaint_category TEXT,
                        complaint_sensitivity TEXT,
                        is_critical INTEGER NOT NULL DEFAULT 0,
                        -- Existing Management and Tracking Fields
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
                
                # Create complaint_notes table for tracking follow-ups and reminders
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS complaint_notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        complaint_id INTEGER NOT NULL,
                        note_text TEXT NOT NULL,
                        created_by TEXT,
                        created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                        FOREIGN KEY (complaint_id) REFERENCES complaints (id)
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
    
    def add_complaint_note(self, complaint_id: int, note_text: str, created_by: str = 'SYSTEM') -> bool:
        """
        Add a note to a specific complaint for tracking follow-ups and reminders.
        
        Args:
            complaint_id (int): The ID of the complaint to add a note to
            note_text (str): The content of the note
            created_by (str): Who created the note (default: 'SYSTEM')
            
        Returns:
            bool: True if the note was successfully added
            
        Raises:
            sqlite3.Error: If the note insertion fails
        """
        query = """
            INSERT INTO complaint_notes (complaint_id, note_text, created_by)
            VALUES (?, ?, ?)
        """
        self.execute_query(query, (complaint_id, note_text, created_by))
        self.logger.info(f"Note added to complaint {complaint_id} by {created_by}")
        return True
    
    def get_complaint_notes(self, complaint_id: int) -> List[Tuple]:
        """
        Retrieve all notes for a specific complaint.
        
        Args:
            complaint_id (int): The ID of the complaint to retrieve notes for
            
        Returns:
            List[Tuple]: All notes for the complaint as a list of tuples
        """
        query = """
            SELECT id, note_text, created_by, created_at
            FROM complaint_notes
            WHERE complaint_id = ?
            ORDER BY created_at DESC
        """
        return self.fetch_all(query, (complaint_id,))
    
    def get_complaints_export_data(self) -> List[Tuple]:
        """
        Fetch all complaints with associated beneficiary information for export purposes.
        
        This method performs a LEFT JOIN between complaints and beneficiaries tables
        to provide comprehensive complaint data including beneficiary details.
        The is_critical field is converted to human-readable 'Yes'/'No' format.
        
        Returns:
            List[Tuple]: All complaints with beneficiary information ordered by 
                        submission date (most recent first)
                        
        Raises:
            sqlite3.Error: If query execution fails
        """
        query = """
            SELECT 
                c.id,
                c.reference_id,
                b.name AS beneficiary_name,
                b.phone AS beneficiary_phone,
                b.governorate,
                b.directorate,
                b.village_area,
                c.submitter_name,
                c.submitter_sex,
                c.submitter_age,
                c.submitter_nationality,
                c.submitter_phone,
                c.submitter_email,
                c.submitter_residence_status,
                c.submitter_governorate,
                c.submitter_directorate,
                c.submitter_village,
                c.submitter_disability,
                c.sector,
                c.original_complaint_text,
                c.complaint_summary_en,
                c.complaint_type,
                c.complaint_category,
                c.complaint_sensitivity,
                CASE 
                    WHEN c.is_critical = 1 THEN 'Yes'
                    ELSE 'No'
                END AS is_critical,
                c.status,
                c.assigned_to,
                c.resolution_notes,
                c.created_at,
                c.submitted_at,
                c.updated_at,
                c.resolved_at,
                c.source_channel,
                c.internal_notes,
                c.follow_up_required
            FROM complaints c
            LEFT JOIN beneficiaries b ON c.beneficiary_id = b.id
            ORDER BY c.submitted_at DESC
        """
        
        try:
            results = self.fetch_all(query)
            self.logger.info(f"Retrieved {len(results)} complaints for export")
            return results
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching complaints export data: {e}")
            raise
    
    def get_beneficiaries_export_data(self) -> List[Tuple]:
        """
        Fetch all beneficiaries data for export purposes.
        
        This method retrieves all records and columns from the beneficiaries table
        ordered by creation date (most recent first).
        
        Returns:
            List[Tuple]: All beneficiaries data ordered by creation date
                        (most recent first)
                        
        Raises:
            sqlite3.Error: If query execution fails
        """
        query = """
            SELECT 
                id,
                user_telegram_id,
                name,
                sex,
                phone,
                residence_status,
                governorate,
                directorate,
                village_area,
                last_seen_at,
                created_at,
                updated_at
            FROM beneficiaries
            ORDER BY created_at DESC
        """
        
        try:
            results = self.fetch_all(query)
            self.logger.info(f"Retrieved {len(results)} beneficiaries for export")
            return results
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching beneficiaries export data: {e}")
            raise
    
    def get_notes_export_data(self) -> List[Tuple]:
        """
        Fetch all complaint notes with associated complaint reference IDs for export purposes.
        
        This method performs a LEFT JOIN between complaint_notes and complaints tables
        to provide note data with complaint context (reference_id).
        
        Returns:
            List[Tuple]: All complaint notes with complaint reference IDs ordered by 
                        note creation date (most recent first)
                        
        Raises:
            sqlite3.Error: If query execution fails
        """
        query = """
            SELECT 
                cn.id,
                cn.complaint_id,
                c.reference_id AS complaint_reference_id,
                cn.note_text,
                cn.created_by,
                cn.created_at
            FROM complaint_notes cn
            LEFT JOIN complaints c ON cn.complaint_id = c.id
            ORDER BY cn.created_at DESC
        """
        
        try:
            results = self.fetch_all(query)
            self.logger.info(f"Retrieved {len(results)} complaint notes for export")
            return results
        except sqlite3.Error as e:
            self.logger.error(f"Error fetching notes export data: {e}")
            raise
    
    def update_beneficiary_last_seen(self, user_telegram_id: int) -> None:
        """
        Update the last_seen_at timestamp for a beneficiary.
        
        Args:
            user_telegram_id (int): The Telegram ID of the beneficiary
            
        Raises:
            sqlite3.Error: If the update fails
        """
        query = """
            UPDATE beneficiaries 
            SET last_seen_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'),
                updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE user_telegram_id = ?
        """
        self.execute_query(query, (user_telegram_id,))
        self.logger.debug(f"Updated last_seen_at for user {user_telegram_id}")


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
        
        # Example: Create an anonymous user profile (NULL telegram_id)
        db_manager.execute_query(
            """INSERT INTO beneficiaries 
               (user_telegram_id, name, sex, phone, residence_status, 
                governorate, directorate, village_area)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (None, "Anonymous User", "Unknown", None, "Unknown",
             "Unknown", "Unknown", "Unknown")
        )
        
        # Example: Fetch beneficiary
        beneficiary = db_manager.fetch_one(
            "SELECT * FROM beneficiaries WHERE user_telegram_id = ?",
            (123456789,)
        )
        print(f"Beneficiary found: {beneficiary}")
        
        # Example: Update last seen timestamp
        db_manager.update_beneficiary_last_seen(123456789)
        
        # Example: Insert a complaint with new submitter snapshot fields
        db_manager.execute_query(
            """INSERT INTO complaints 
               (beneficiary_id, submitter_name, submitter_sex, submitter_age, 
                submitter_nationality, submitter_phone, submitter_email,
                submitter_residence_status, submitter_governorate, submitter_directorate,
                submitter_village, submitter_disability, sector, original_complaint_text, 
                complaint_type, complaint_category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (1, "John Doe", "Male", 35, "Iraqi", "+1234567890", "john@example.com",
             "Resident", "Baghdad", "Al-Karkh", "Al-Mansour", "None", "Water",
             "Need help with water supply", "Request for Help", "Water Trucking")
        )
        
        # Example: Add a note to the complaint
        success = db_manager.add_complaint_note(1, "User requested a reminder for follow-up", "SYSTEM")
        print(f"Note added successfully: {success}")
        
        # Example: Retrieve complaint notes
        notes = db_manager.get_complaint_notes(1)
        print(f"Complaint notes: {notes}")
        
        # Example: Fetch all classification keys
        keys = db_manager.fetch_all("SELECT * FROM classification_keys")
        print(f"Total classification keys: {len(keys)}")
        
        # Example: Test new export methods
        print("\n=== Testing Export Methods ===")
        
        # Test complaints export
        complaints_data = db_manager.get_complaints_export_data()
        print(f"Complaints export data: {len(complaints_data)} records")
        
        # Test beneficiaries export
        beneficiaries_data = db_manager.get_beneficiaries_export_data()
        print(f"Beneficiaries export data: {len(beneficiaries_data)} records")
        
        # Test notes export
        notes_data = db_manager.get_notes_export_data()
        print(f"Notes export data: {len(notes_data)} records")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db_manager.close()