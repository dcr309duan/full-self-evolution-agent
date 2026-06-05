import sqlite3
import time
import functools
import os
import threading
from contextlib import contextmanager
from typing import Callable, Optional, Dict, Any

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'performance_metrics.db')

# Thread-local storage for tracking current operation
_local = threading.local()

def _get_db_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database, creating tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS execution_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL,
            operation_name TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            duration REAL NOT NULL,
            success INTEGER NOT NULL,
            error_message TEXT,
            estimated_memory_mb REAL,
            estimated_cpu_percent REAL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_module_timestamp 
        ON execution_metrics(module_name, timestamp)
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_timestamp 
        ON execution_metrics(timestamp)
    ''')
    conn.commit()
    return conn

def _estimate_resource_usage() -> Dict[str, float]:
    """Estimate current resource usage (simplified estimation)."""
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
        cpu_percent = process.cpu_percent(interval=0.1)
        return {'memory_mb': round(memory_mb, 2), 'cpu_percent': round(cpu_percent, 2)}
    except ImportError:
        # Fallback estimation without psutil
        return {'memory_mb': 0.0, 'cpu_percent': 0.0}

def record_execution(
    module_name: str,
    operation_name: str,
    start_time: float,
    end_time: float,
    success: bool,
    error_message: Optional[str] = None,
    resource_usage: Optional[Dict[str, float]] = None
) -> None:
    """Record an execution metric into the database."""
    duration = end_time - start_time
    if resource_usage is None:
        resource_usage = _estimate_resource_usage()
    
    conn = _get_db_connection()
    try:
        conn.execute('''
            INSERT INTO execution_metrics 
            (module_name, operation_name, start_time, end_time, duration, success, error_message, estimated_memory_mb, estimated_cpu_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            module_name,
            operation_name,
            start_time,
            end_time,
            duration,
            1 if success else 0,
            error_message,
            resource_usage.get('memory_mb', 0.0),
            resource_usage.get('cpu_percent', 0.0)
        ))
        conn.commit()
    finally:
        conn.close()

def wrap_function(module_name: str, operation_name: str, func: Callable) -> Callable:
    """Wrap a function with performance metrics collection."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        resource_before = _estimate_resource_usage()
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            resource_after = _estimate_resource_usage()
            # Use average resource usage during execution
            avg_resource = {
                'memory_mb': (resource_before['memory_mb'] + resource_after['memory_mb']) / 2,
                'cpu_percent': (resource_before['cpu_percent'] + resource_after['cpu_percent']) / 2
            }
            record_execution(module_name, operation_name, start_time, end_time, True, resource_usage=avg_resource)
            return result
        except Exception as e:
            end_time = time.time()
            resource_after = _estimate_resource_usage()
            avg_resource = {
                'memory_mb': (resource_before['memory_mb'] + resource_after['memory_mb']) / 2,
                'cpu_percent': (resource_before['cpu_percent'] + resource_after['cpu_percent']) / 2
            }
            record_execution(module_name, operation_name, start_time, end_time, False, str(e), resource_usage=avg_resource)
            raise
    return wrapper

def wrap_class_methods(module_name: str, cls: type, method_names: list) -> type:
    """Wrap specified methods of a class with metrics collection."""
    for method_name in method_names:
        if hasattr(cls, method_name) and callable(getattr(cls, method_name)):
            original_method = getattr(cls, method_name)
            wrapped = wrap_function(module_name, f"{cls.__name__}.{method_name}", original_method)
            setattr(cls, method_name, wrapped)
    return cls

# --- Query methods for dashboard ---

def get_average_execution_time(module_name: str, cycles: int = 10) -> Optional[float]:
    """Get average execution time for a module over the last N cycles."""
    conn = _get_db_connection()
    try:
        cursor = conn.execute('''
            SELECT AVG(duration) as avg_time
            FROM (
                SELECT duration FROM execution_metrics
                WHERE module_name = ?
                ORDER BY id DESC
                LIMIT ?
            )
        ''', (module_name, cycles))
        row = cursor.fetchone()
        return row['avg_time'] if row and row['avg_time'] is not None else None
    finally:
        conn.close()

def get_failure_rate_trend(module_name: str, cycles: int = 10) -> list:
    """Get failure rate trend over the last N cycles (each cycle is a group of 10 executions)."""
    conn = _get_db_connection()
    try:
        # Get the last N*10 records for the module, grouped into cycles of 10
        cursor = conn.execute('''
            SELECT 
                (row_num - 1) / 10 as cycle,
                COUNT(*) as total,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures
            FROM (
                SELECT success, ROW_NUMBER() OVER (ORDER BY id DESC) as row_num
                FROM execution_metrics
                WHERE module_name = ?
                ORDER BY id DESC
                LIMIT ?
            )
            GROUP BY cycle
            ORDER BY cycle DESC
        ''', (module_name, cycles * 10))
        
        trend = []
        for row in cursor.fetchall():
            if row['total'] > 0:
                failure_rate = (row['failures'] / row['total']) * 100
                trend.append({
                    'cycle': row['cycle'],
                    'total_executions': row['total'],
                    'failures': row['failures'],
                    'failure_rate_percent': round(failure_rate, 2)
                })
        return trend
    finally:
        conn.close()

def get_module_summary(module_name: str, cycles: int = 10) -> Dict[str, Any]:
    """Get a summary of metrics for a module over the last N cycles."""
    conn = _get_db_connection()
    try:
        cursor = conn.execute('''
            SELECT 
                COUNT(*) as total_executions,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
                AVG(duration) as avg_duration,
                MAX(duration) as max_duration,
                MIN(duration) as min_duration,
                AVG(estimated_memory_mb) as avg_memory,
                AVG(estimated_cpu_percent) as avg_cpu
            FROM (
                SELECT * FROM execution_metrics
                WHERE module_name = ?
                ORDER BY id DESC
                LIMIT ?
            )
        ''', (module_name, cycles))
        row = cursor.fetchone()
        if row and row['total_executions'] > 0:
            return {
                'module_name': module_name,
                'total_executions': row['total_executions'],
                'successful': row['successful'],
                'failed': row['failed'],
                'success_rate_percent': round((row['successful'] / row['total_executions']) * 100, 2),
                'avg_duration_ms': round(row['avg_duration'] * 1000, 2) if row['avg_duration'] else 0,
                'max_duration_ms': round(row['max_duration'] * 1000, 2) if row['max_duration'] else 0,
                'min_duration_ms': round(row['min_duration'] * 1000, 2) if row['min_duration'] else 0,
                'avg_memory_mb': round(row['avg_memory'], 2) if row['avg_memory'] else 0,
                'avg_cpu_percent': round(row['avg_cpu'], 2) if row['avg_cpu'] else 0
            }
        return {'module_name': module_name, 'total_executions': 0}
    finally:
        conn.close()

def get_all_module_names() -> list:
    """Get list of all module names that have recorded metrics."""
    conn = _get_db_connection()
    try:
        cursor = conn.execute('SELECT DISTINCT module_name FROM execution_metrics ORDER BY module_name')
        return [row['module_name'] for row in cursor.fetchall()]
    finally:
        conn.close()

def clear_metrics(module_name: Optional[str] = None) -> None:
    """Clear metrics for a specific module or all metrics if module_name is None."""
    conn = _get_db_connection()
    try:
        if module_name:
            conn.execute('DELETE FROM execution_metrics WHERE module_name = ?', (module_name,))
        else:
            conn.execute('DELETE FROM execution_metrics')
        conn.commit()
    finally:
        conn.close()

# --- Monkey-patching utility for evolution engine ---

def patch_evolution_engine(engine_module) -> None:
    """Monkey-patch the evolution engine's mutation executor with metrics collection."""
    if hasattr(engine_module, 'MutationExecutor'):
        executor_class = engine_module.MutationExecutor
        # Wrap key methods
        wrap_class_methods('evolution_engine', executor_class, [
            'execute_mutation',
            'apply_mutation',
            'evaluate_mutation'
        ])
    if hasattr(engine_module, 'EvolutionEngine'):
        engine_class = engine_module.EvolutionEngine
        wrap_class_methods('evolution_engine', engine_class, [
            'run_cycle',
            'evolve_population'
        ])