import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any
import json

DB_PATH = "signals.db"

def init_db():
    """初始化数据库表结构"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            signal_date TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            price REAL,
            indicator_type TEXT NOT NULL, -- 'DKX' or 'MA'
            indicator_values TEXT, -- 指标值的 JSON 字符串
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_signal(data: Dict[str, Any]):
    """
    保存检测到的信号到数据库。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 检查该特定信号 (标的, 日期, 类型) 是否已存在，避免重复
        c.execute('''
            SELECT id FROM signal_history 
            WHERE symbol = ? AND signal_date = ? AND signal_type = ? AND indicator_type = ?
        ''', (data['symbol'], data['date'], data['signal'], data.get('indicator_type', 'UNKNOWN')))
        
        if c.fetchone():
            conn.close()
            return # 已存在
            
        # 准备额外值的 JSON
        extra_values = {}
        for k in ['dkx', 'madkx', 'ma_short', 'ma_long']:
            if k in data and data[k] is not None:
                extra_values[k] = data[k]
                
        c.execute('''
            INSERT INTO signal_history (symbol, market, signal_date, signal_type, price, indicator_type, indicator_values)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['symbol'],
            data.get('market', 'stock'),
            data['date'],
            data['signal'],
            data['close'],
            data.get('indicator_type', 'UNKNOWN'),
            json.dumps(extra_values)
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving signal to DB: {e}")

def get_history(limit: int = 100) -> List[Dict[str, Any]]:
    """获取信号历史记录"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM signal_history ORDER BY signal_date DESC, id DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    
    results = []
    for row in rows:
        item = dict(row)
        if item['indicator_values']:
            try:
                vals = json.loads(item['indicator_values'])
                item.update(vals)
            except:
                pass
        del item['indicator_values']
        results.append(item)
        
    conn.close()
    return results
