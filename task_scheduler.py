import json
import threading
import time
import uuid
from queue import PriorityQueue
from typing import Callable, Optional, Dict, Any

class Task:
    """Represents a scheduled task with metadata."""
    
    def __init__(self, func: Callable, interval: float, task_id: Optional[str] = None, enabled: bool = True):
        self.id = task_id or str(uuid.uuid4())
        self.func = func
        self.interval = interval
        self.last_run = 0.0
        self.enabled = enabled
        self._timer: Optional[threading.Timer] = None
        self.completed_count = 0
        self.failed_count = 0
        self.total_execution_time = 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to dictionary for JSON persistence."""
        return {
            'id': self.id,
            'func_name': self.func.__name__,
            'interval': self.interval,
            'last_run': self.last_run,
            'enabled': self.enabled,
            'completed_count': self.completed_count,
            'failed_count': self.failed_count,
            'total_execution_time': self.total_execution_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], func_map: Dict[str, Callable]) -> Optional['Task']:
        """Deserialize task from dictionary, using func_map to resolve function references."""
        func = func_map.get(data.get('func_name'))
        if func is None:
            return None
        task = cls(func=func, interval=data['interval'], task_id=data['id'], enabled=data['enabled'])
        task.last_run = data.get('last_run', 0.0)
        task.completed_count = data.get('completed_count', 0)
        task.failed_count = data.get('failed_count', 0)
        task.total_execution_time = data.get('total_execution_time', 0.0)
        return task

class Scheduler:
    """Lightweight task scheduler with priority queue and JSON persistence."""
    
    def __init__(self, persistence_file: str = 'tasks.json'):
        self._lock = threading.Lock()
        self._running = False
        self._tasks: Dict[str, Task] = {}
        self._priority_queue = PriorityQueue()
        self._persistence_file = persistence_file
        self._func_map: Dict[str, Callable] = {}
        self._scheduler_thread: Optional[threading.Thread] = None
        self._start_time = 0.0
        
    def register_function(self, func: Callable, name: Optional[str] = None) -> None:
        """Register a function for deserialization from JSON."""
        func_name = name or func.__name__
        self._func_map[func_name] = func
        
    def add_task(self, func: Callable, interval: float, task_id: Optional[str] = None, enabled: bool = True) -> str:
        """Add a new task to the scheduler. Returns the task ID."""
        with self._lock:
            task = Task(func=func, interval=interval, task_id=task_id, enabled=enabled)
            self._tasks[task.id] = task
            if enabled and self._running:
                self._schedule_task(task)
            self._save_tasks()
            return task.id
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task by ID. Returns True if removed, False if not found."""
        with self._lock:
            task = self._tasks.pop(task_id, None)
            if task is None:
                return False
            if task._timer:
                task._timer.cancel()
            self._save_tasks()
            return True
    
    def start(self) -> None:
        """Start the scheduler in a background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._start_time = time.time()
            self._load_tasks()
            for task in self._tasks.values():
                if task.enabled:
                    self._schedule_task(task)
            self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self._scheduler_thread.start()
    
    def stop(self) -> None:
        """Stop the scheduler and cancel all pending tasks."""
        with self._lock:
            self._running = False
            for task in self._tasks.values():
                if task._timer:
                    task._timer.cancel()
            self._save_tasks()
    
    def list_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Return a dictionary of all tasks with their metadata."""
        with self._lock:
            return {tid: task.to_dict() for tid, task in self._tasks.items()}
    
    def get_health_score(self) -> float:
        """Calculate and return a health score based on task performance metrics.
        
        The score is calculated using:
        - Task completion ratio (completed vs failed)
        - Average execution time
        - Queue length (number of tasks)
        - Scheduler uptime
        
        Returns a float between 0.0 (unhealthy) and 1.0 (healthy).
        """
        with self._lock:
            if not self._tasks:
                return 1.0  # No tasks means no issues
            
            total_completed = sum(task.completed_count for task in self._tasks.values())
            total_failed = sum(task.failed_count for task in self._tasks.values())
            total_executions = total_completed + total_failed
            
            # Task completion ratio (0.0 to 1.0)
            if total_executions > 0:
                completion_ratio = total_completed / total_executions
            else:
                completion_ratio = 1.0
            
            # Average execution time penalty (inverse relationship)
            total_time = sum(task.total_execution_time for task in self._tasks.values())
            if total_completed > 0:
                avg_execution_time = total_time / total_completed
                # Normalize: assume 10 seconds as baseline for perfect score
                time_penalty = min(1.0, avg_execution_time / 10.0)
                time_score = 1.0 - time_penalty
            else:
                time_score = 1.0
            
            # Queue length factor (more tasks = more load, but not necessarily unhealthy)
            num_tasks = len(self._tasks)
            queue_factor = max(0.0, 1.0 - (num_tasks / 100.0))  # Penalize after 100 tasks
            
            # Uptime factor (longer uptime = more stable)
            if self._running:
                uptime = time.time() - self._start_time
                # Normalize: assume 1 hour (3600 seconds) as baseline for perfect score
                uptime_score = min(1.0, uptime / 3600.0)
            else:
                uptime_score = 0.0
            
            # Weighted combination
            health_score = (
                0.4 * completion_ratio +
                0.3 * time_score +
                0.1 * queue_factor +
                0.2 * uptime_score
            )
            
            return max(0.0, min(1.0, health_score))
    
    def _schedule_task(self, task: Task) -> None:
        """Schedule a single task to run after its interval."""
        if not self._running or not task.enabled:
            return
        if task._timer:
            task._timer.cancel()
        
        # Calculate delay based on last run time
        now = time.time()
        elapsed = now - task.last_run
        delay = max(0.0, task.interval - elapsed)
        
        def wrapper():
            with self._lock:
                if not self._running or not task.enabled:
                    return
                try:
                    start_time = time.time()
                    task.func()
                    execution_time = time.time() - start_time
                    task.completed_count += 1
                    task.total_execution_time += execution_time
                except Exception as e:
                    print(f"Task {task.id} failed: {e}")
                    task.failed_count += 1
                task.last_run = time.time()
                self._save_tasks()
                if task.enabled:
                    self._schedule_task(task)
        
        task._timer = threading.Timer(delay, wrapper)
        task._timer.daemon = True
        task._timer.start()
    
    def _run_scheduler(self) -> None:
        """Background thread to manage the scheduler lifecycle."""
        while self._running:
            time.sleep(1.0)
    
    def _save_tasks(self) -> None:
        """Persist tasks to JSON file."""
        try:
            tasks_data = [task.to_dict() for task in self._tasks.values()]
            with open(self._persistence_file, 'w') as f:
                json.dump(tasks_data, f, indent=2)
        except Exception as e:
            print(f"Failed to save tasks: {e}")
    
    def _load_tasks(self) -> None:
        """Load tasks from JSON file."""
        try:
            with open(self._persistence_file, 'r') as f:
                tasks_data = json.load(f)
            for data in tasks_data:
                task = Task.from_dict(data, self._func_map)
                if task:
                    self._tasks[task.id] = task
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Failed to load tasks: {e}")

# Example usage (commented out)
if __name__ == "__main__":
    def example_task():
        print("Task executed at:", time.time())
    
    scheduler = Scheduler("example_tasks.json")
    scheduler.register_function(example_task)
    
    # Add a task that runs every 5 seconds
    task_id = scheduler.add_task(example_task, 5.0)
    print(f"Added task: {task_id}")
    
    scheduler.start()
    
    try:
        time.sleep(15)
        print(f"Health score: {scheduler.get_health_score():.2f}")
    finally:
        scheduler.stop()
        print("Scheduler stopped")