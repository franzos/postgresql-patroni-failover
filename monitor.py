#!/usr/bin/env python3

import os
import time
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import sys

PG_HOST = os.environ.get('PGHOST', 'localhost')
PG_PORT = os.environ.get('PGPORT', '5432')
DB_USER = os.environ.get('PGUSER', 'postgres')
DB_PASSWORD = os.environ.get('PGPASSWORD', 'postgres')
DB_NAME = os.environ.get('PGDATABASE', 'postgres')

CONN_STR = f"host={PG_HOST} port={PG_PORT} user={DB_USER} password={DB_PASSWORD} dbname={DB_NAME}"

def create_table_if_not_exists(max_retries=30):
    """Create test table if it doesn't exist."""
    for retry in range(max_retries):
        try:
            with psycopg2.connect(CONN_STR) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS test_data (
                            id SERIAL PRIMARY KEY,
                            data TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            node_name TEXT
                        )
                    """)
                    conn.commit()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Table created/verified")
                    return True
        except OperationalError as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for database to be ready... ({retry+1}/{max_retries})")
            time.sleep(2)
    return False

def write_data(counter):
    """Write data through PgBouncer (connection pooling + failover)."""
    try:
        with psycopg2.connect(CONN_STR, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                # Get current node name
                try:
                    cur.execute("SELECT current_setting('cluster_name')")
                    result = cur.fetchone()
                    node_name = result[0] if result else 'unknown'
                except:
                    node_name = 'postgres-node'
                
                # Insert test data
                data = f"Test data #{counter}"
                cur.execute(
                    "INSERT INTO test_data (data, node_name) VALUES (%s, %s) RETURNING id",
                    (data, node_name)
                )
                record_id = cur.fetchone()[0]
                conn.commit()
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] WRITE: ID={record_id}, Data='{data}'")
                return True
    except OperationalError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] WRITE ERROR: Connection failed - {str(e)[:50]}...")
        return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] WRITE ERROR: {str(e)[:50]}...")
        return False

def read_data():
    """Read data through PgBouncer (connection pooling + failover)."""
    try:
        with psycopg2.connect(CONN_STR, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                # Count records
                cur.execute("SELECT COUNT(*) FROM test_data")
                count = cur.fetchone()[0]
                
                # Get latest record
                cur.execute("""
                    SELECT id, data, created_at 
                    FROM test_data 
                    ORDER BY id DESC 
                    LIMIT 1
                """)
                latest = cur.fetchone()
                
                if latest:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] READ: Total records={count}, Latest: ID={latest[0]}, Data='{latest[1]}'")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] READ: No records found")
                return True
    except OperationalError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] READ ERROR: Connection failed - {str(e)[:50]}...")
        return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] READ ERROR: {str(e)[:50]}...")
        return False

def main():
    """Main monitoring loop."""
    print("=" * 60)
    print("PostgreSQL HA Monitor")
    print("=" * 60)
    print(f"Database endpoint: {PG_HOST}:{PG_PORT} (via PgBouncer)")
    print("Connection flow: Monitor → PgBouncer → HAProxy → PostgreSQL")
    print("=" * 60)
    
    # Wait for database and create table
    if not create_table_if_not_exists():
        print("Failed to connect to database after multiple attempts")
        sys.exit(1)
    
    counter = 1
    consecutive_failures = 0
    max_consecutive_failures = 10
    
    print("\nStarting continuous monitoring (Ctrl+C to stop)...")
    print("-" * 60)
    
    while True:
        try:
            # Attempt write operation
            write_success = write_data(counter)
            
            # Attempt read operation
            read_success = read_data()
            
            # Track failures
            if not write_success or not read_success:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Too many consecutive failures. Check your setup.")
            else:
                if consecutive_failures > 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection restored after {consecutive_failures} failures")
                consecutive_failures = 0
                counter += 1
            
            # Sleep between operations
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
            break
        except Exception as e:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Unexpected error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
