import os
import sqlite3
import json
import logging
import time
from datetime import datetime
import re

logger = logging.getLogger("db_manager")

DB_DIR = "./data"
DOCS_DIR = "./data/documents"
DB_PATH = os.path.join(DB_DIR, "organizer.db")

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            type TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            masked_text TEXT NOT NULL,
            json_data TEXT NOT NULL,
            is_confidential INTEGER DEFAULT 1,
            llm_engine TEXT DEFAULT 'Local Rule Parser',
            process_time_seconds REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Auto-migration for existing tables
    cursor.execute("PRAGMA table_info(documents)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'is_confidential' not in columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN is_confidential INTEGER DEFAULT 1")
    if 'llm_engine' not in columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN llm_engine TEXT DEFAULT 'Local Rule Parser'")
    if 'process_time_seconds' not in columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN process_time_seconds REAL DEFAULT 0.0")

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

def sanitize_filename(filename):
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    return f"{name}{ext}"

def save_document(file_name, file_bytes, doc_type, raw_text, masked_text, json_data, is_confidential=True, llm_engine="Local Rule Parser", process_time_seconds=0.0):
    init_db()
    san_name = sanitize_filename(file_name)
    timestamp = int(time.time())
    unique_name = f"{timestamp}_{san_name}"
    stored_path = os.path.join(DOCS_DIR, unique_name)
    
    with open(stored_path, "wb") as f:
        f.write(file_bytes)
        
    if isinstance(json_data, dict):
        json_data_str = json.dumps(json_data, indent=2)
    else:
        json_data_str = str(json_data)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO documents (name, stored_path, type, raw_text, masked_text, json_data, is_confidential, llm_engine, process_time_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (file_name, stored_path, doc_type, raw_text, masked_text, json_data_str, 1 if is_confidential else 0, llm_engine, float(process_time_seconds or 0.0)))
    
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Document saved with ID: {doc_id}, path: {stored_path}")
    return doc_id

def get_documents(search_query=None, doc_type=None):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM documents WHERE 1=1"
    params = []
    
    if doc_type and doc_type.lower() != "all":
        dt = doc_type.lower()
        if dt in ["ktp", "id_card"]:
            query += " AND type IN ('ktp', 'id_card')"
        elif dt in ["passport", "paspor"]:
            query += " AND type IN ('passport', 'paspor')"
        elif dt in ["invoice", "receipt", "struk"]:
            query += " AND type IN ('invoice', 'receipt', 'struk')"
        elif dt in ["vendor", "vendor_doc", "procurement"]:
            query += " AND type IN ('vendor', 'vendor_doc', 'procurement')"
        elif dt in ["business_card", "kartu_nama"]:
            query += " AND type IN ('business_card', 'kartu_nama')"
        else:
            query += " AND type = ?"
            params.append(dt)
        
    if search_query:
        query += " AND (name LIKE ? OR raw_text LIKE ? OR json_data LIKE ?)"
        like_param = f"%{search_query}%"
        params.extend([like_param, like_param, like_param])
        
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    documents = []
    for row in rows:
        try:
            parsed_json = json.loads(row['json_data'])
        except Exception:
            parsed_json = {"raw": row['json_data']}
            
        doc_dict = {
            'id': row['id'],
            'name': row['name'],
            'stored_path': row['stored_path'],
            'type': row['type'],
            'raw_text': row['raw_text'],
            'masked_text': row['masked_text'],
            'json_data': parsed_json,
            'created_at': row['created_at']
        }
        if 'is_confidential' in row.keys():
            doc_dict['is_confidential'] = bool(row['is_confidential'])
        else:
            doc_dict['is_confidential'] = True

        if 'llm_engine' in row.keys():
            doc_dict['llm_engine'] = row['llm_engine'] or 'Local Rule Parser'
        else:
            doc_dict['llm_engine'] = 'Local Rule Parser'

        if 'process_time_seconds' in row.keys():
            doc_dict['process_time_seconds'] = round(float(row['process_time_seconds'] or 0.0), 2)
        else:
            doc_dict['process_time_seconds'] = 0.0

        documents.append(doc_dict)
        
    conn.close()
    return documents

def get_document_by_id(doc_id):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
        
    try:
        parsed_json = json.loads(row['json_data'])
    except Exception:
        parsed_json = {"raw": row['json_data']}
        
    doc = {
        'id': row['id'],
        'name': row['name'],
        'stored_path': row['stored_path'],
        'type': row['type'],
        'raw_text': row['raw_text'],
        'masked_text': row['masked_text'],
        'json_data': parsed_json,
        'created_at': row['created_at'],
        'is_confidential': bool(row['is_confidential']) if 'is_confidential' in row.keys() else True,
        'llm_engine': row['llm_engine'] if 'llm_engine' in row.keys() else 'Local Rule Parser',
        'process_time_seconds': round(float(row['process_time_seconds'] or 0.0), 2) if 'process_time_seconds' in row.keys() else 0.0
    }
    
    conn.close()
    return doc

def delete_document(doc_id):
    doc = get_document_by_id(doc_id)
    if not doc:
        logger.warning(f"Document with ID {doc_id} not found for deletion.")
        return False
        
    stored_path = doc['stored_path']
    if os.path.exists(stored_path):
        try:
            os.remove(stored_path)
            logger.info(f"Deleted physical file: {stored_path}")
        except Exception as e:
            logger.error(f"Error removing physical file {stored_path}: {e}")
    else:
        logger.warning(f"Physical file not found at: {stored_path}")
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    logger.info(f"Deleted DB record for document ID: {doc_id}")
    return True

def delete_all_documents():
    docs = get_documents()
    for doc in docs:
        delete_document(doc['id'])
        
    # Reset SQLite autoincrement ID sequence back to 0 so next document ID starts at #1
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='documents'")
        conn.commit()
        conn.close()
        logger.info("Reset document ID sequence back to 1.")
    except Exception as e:
        logger.error(f"Error resetting ID sequence: {e}")

    if os.path.exists("temp_uploads"):
        for f in os.listdir("temp_uploads"):
            try:
                os.remove(os.path.join("temp_uploads", f))
            except Exception:
                pass
    return True

def clean_and_parse_price(price_str):
    if not price_str or not isinstance(price_str, str):
        return 0.0
    val = re.sub(r'(?i)Rp\.?|IDR|\$|€|£|USD|EUR|SGD', '', price_str).strip()
    if ',' in val and '.' in val:
        if val.index('.') < val.index(','):
            val = val.replace('.', '').replace(',', '.')
    elif ',' in val:
        parts = val.split(',')
        if len(parts[-1]) == 2:
            val = val.replace(',', '.')
        else:
            val = val.replace(',', '')
    elif '.' in val:
        parts = val.split('.')
        if len(parts[-1]) == 3 and len(parts) == 2:
            val = val.replace('.', '')
            
    num_match = re.search(r'\d+(?:\.\d+)?', val)
    if num_match:
        try:
            return float(num_match.group())
        except ValueError:
            return 0.0
    return 0.0

def get_analytics_summary():
    docs = get_documents(doc_type="All")
    type_counts = {}
    for doc in docs:
        t = doc['type'].capitalize()
        type_counts[t] = type_counts.get(t, 0) + 1
        
    monthly_spend = {}
    frequent_vendors = {}
    total_spend = 0.0
    
    invoice_docs = [d for d in docs if d['type'] == 'invoice']
    for doc in invoice_docs:
        meta = doc['json_data']
        vendor = meta.get('vendor_name', 'Unknown Vendor').strip()
        total_str = meta.get('total_amount', '0')
        date_str = meta.get('invoice_date', '')
        
        price_val = clean_and_parse_price(total_str)
        total_spend += price_val
        
        if vendor and vendor != 'Unknown Vendor':
            frequent_vendors[vendor] = frequent_vendors.get(vendor, 0.0) + price_val
            
        month_key = "Unknown Month"
        if date_str:
            match = re.search(r'(\d{4})[-/](\d{2})', date_str)
            if match:
                month_key = f"{match.group(1)}-{match.group(2)}"
            else:
                try:
                    dt = datetime.strptime(doc['created_at'], "%Y-%m-%d %H:%M:%S")
                    month_key = dt.strftime("%Y-%m")
                except Exception:
                    month_key = "Other"
        else:
            try:
                dt = datetime.strptime(doc['created_at'], "%Y-%m-%d %H:%M:%S")
                month_key = dt.strftime("%Y-%m")
            except Exception:
                month_key = "Other"
                
        monthly_spend[month_key] = monthly_spend.get(month_key, 0.0) + price_val
        
    sorted_monthly_spend = dict(sorted(monthly_spend.items()))
    sorted_vendors = dict(sorted(frequent_vendors.items(), key=lambda x: x[1], reverse=True)[:10])
    
    return {
        'total_documents': len(docs),
        'document_type_counts': type_counts,
        'total_spending': total_spend,
        'monthly_spending_trend': sorted_monthly_spend,
        'top_vendors_by_spending': sorted_vendors
    }
