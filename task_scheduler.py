import json
import threading
import time
import uuid
from queue import PriorityQueue
from typing import Callable, Optional, Dict, Any, List

class Task:
    """Represents a scheduled task with metadata."""
    
    def __init__(self, func: Callable, interval: float, task_id: Optional[str] = None, enabled: bool = True, priority: int = 0, retry_count: int = 0):
        self.id = task_id or str(uuid.uuid4())
        self.func = func
        self.interval = interval
        self.last_run = 0.0
        self.enabled = enabled
        self._timer: Optional[threading.Timer] = None
        self.completed_count = 0
        self.failed_count = 0
        self.total_execution_time = 0.0
        self.priority = priority
        self.retry_count = retry_count
        self.failure_pattern: List[float] = []  # Timestamps of recent failures
        self.injection_time = time.time()  # Track when task was added
        
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
            'total_execution_time': self.total_execution_time,
            'priority': self.priority,
            'retry_count': self.retry_count,
            'failure_pattern': self.failure_pattern,
            'injection_time': self.injection_time
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
        task.priority = data.get('priority', 0)
        task.retry_count = data.get('retry_count', 0)
        task.failure_pattern = data.get('failure_pattern', [])
        task.injection_time = data.get('injection_time', time.time())
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
        self._retry_goals: Dict[str, Task] = {}  # Store retry goal tasks
        self._exploration_tasks: Dict[str, Task] = {}  # Store exploration tasks
        self._exploration_completed_count = 0
        self._exploration_failed_count = 0
        self._exploration_total_time = 0.0
        
    def register_function(self, func: Callable, name: Optional[str] = None) -> None:
        """Register a function for deserialization from JSON."""
        func_name = name or func.__name__
        self._func_map[func_name] = func
        
    def add_task(self, func: Callable, interval: float, task_id: Optional[str] = None, enabled: bool = True, priority: int = 0) -> str:
        """Add a new task to the scheduler. Returns the task ID."""
        with self._lock:
            task = Task(func=func, interval=interval, task_id=task_id, enabled=enabled, priority=priority)
            self._tasks[task.id] = task
            if priority == 1:  # Exploration priority
                self._exploration_tasks[task.id] = task
            if enabled and self._running:
                self._schedule_task(task)
            self._save_tasks()
            return task.id
    
    def add_retry_goal(self, func: Callable, interval: float, task_id: Optional[str] = None, enabled: bool = True) -> Optional[str]:
        """Add a retry goal task with priority boosting. Returns the task ID or None if retry limit exceeded."""
        with self._lock:
            # Check failure pattern log for retry count
            if task_id and task_id in self._retry_goals:
                existing_task = self._retry_goals[task_id]
                if existing_task.retry_count >= 3:
                    print(f"Retry limit exceeded for task {task_id}")
                    return None
                
                # Check failure pattern within last hour
                current_time = time.time()
                recent_failures = [t for t in existing_task.failure_pattern if current_time - t < 3600]
                if len(recent_failures) >= 3:
                    print(f"Too many recent failures for task {task_id}")
                    return None
            
            # Priority boosting: higher than normal (0) but lower than critical (-1)
            priority = -2  # Retry goals get priority -2 (between normal 0 and critical -1)
            
            task = Task(func=func, interval=interval, task_id=task_id, enabled=enabled, priority=priority)
            if task_id:
                task.id = task_id
                task.retry_count = self._retry_goals.get(task_id, Task(func, interval)).retry_count + 1 if task_id in self._retry_goals else 1
            else:
                task.retry_count = 1
            
            self._retry_goals[task.id] = task
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
            self._retry_goals.pop(task_id, None)
            self._exploration_tasks.pop(task_id, None)
            self._save_tasks()
            return True
    
    def get_exploration_tasks(self) -> List[Task]:
        """Return all pending exploration tasks sorted by injection time."""
        with self._lock:
            pending_exploration = [
                task for task in self._exploration_tasks.values()
                if task.enabled and task._timer is not None
            ]
            return sorted(pending_exploration, key=lambda t: t.injection_time)
    
    def get_exploration_metrics(self) -> Dict[str, Any]:
        """Get metrics for exploration tasks."""
        with self._lock:
            total = self._exploration_completed_count + self._exploration_failed_count
            completion_rate = self._exploration_completed_count / total if total > 0 else 0.0
            avg_time = self._exploration_total_time / self._exploration_completed_count if self._exploration_completed_count > 0 else 0.0
            return {
                'completion_rate': completion_rate,
                'average_time_to_completion': avg_time,
                'completed_count': self._exploration_completed_count,
                'failed_count': self._exploration_failed_count
            }
    
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
        - Retry goal health (penalty for excessive retries)
        - Exploration task health
        
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
            
            # Retry goal health factor
            retry_goals_count = len(self._retry_goals)
            if retry_goals_count > 0:
                max_retries = max(task.retry_count for task in self._retry_goals.values())
                retry_penalty = min(1.0, max_retries / 3.0)  # Penalize based on max retries
                retry_health = 1.0 - retry_penalty
            else:
                retry_health = 1.0
            
            # Exploration task health factor
            exploration_metrics = self.get_exploration_metrics()
            exploration_health = exploration_metrics['completion_rate'] if exploration_metrics['completed_count'] > 0 else 1.0
            
            # Weighted combination
            health_score = (
                0.30 * completion_ratio +
                0.20 * time_score +
                0.10 * queue_factor +
                0.15 * uptime_score +
                0.15 * retry_health +
                0.10 * exploration_health
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
                
                # Check if there are higher priority tasks pending
                if task.priority == 1:  # Exploration task
                    higher_priority_tasks = [
                        t for t in self._tasks.values()
                        if t.enabled and t.priority < 1 and t.priority != -2
                    ]
                    if higher_priority_tasks:
                        # Reschedule exploration task to avoid blocking critical tasks
                        self._schedule_task(task)
                        return
                
                try:
                    start_time = time.time()
                    task.func()
                    execution_time = time.time() - start_time
                    task.completed_count += 1
                    task.total_execution_time += execution_time
                    # Clear failure pattern on success
                    task.failure_pattern = []
                    
                    # Track exploration metrics
                    if task.priority == 1:
                        self._exploration_completed_count += 1
                        self._exploration_total_time += execution_time
                except Exception as e:
                    print(f"Task {task.id} failed: {e}")
                    task.failed_count += 1
                    # Record failure timestamp
                    task.failure_pattern.append(time.time())
                    # Keep only last 10 failures
                    if len(task.failure_pattern) > 10:
                        task.failure_pattern = task.failure_pattern[-10:]
                    
                    # Track exploration failures
                    if task.priority == 1:
                        self._exploration_failed_count += 1
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
                    # Restore retry goals based on priority
                    if task.priority == -2:
                        self._retry_goals[task.id] = task
                    # Restore exploration tasks based on priority
                    if task.priority == 1:
                        self._exploration_tasks[task.id] = task
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Failed to load tasks: {e}")

# Example usage (commented out)
if __name__ == "__main__":
    def example_task():
        print("Task executed at:", time.time())
    
    def retry_goal_task():
        print("Retry goal executed at:", time.time())
    
    def exploration_task():
        print("Exploration task executed at:", time.time())
    
    scheduler = Scheduler("example_tasks.json")
    scheduler.register_function(example_task)
    scheduler.register_function(retry_goal_task)
    scheduler.register_function(exploration_task)
    
    # Add a normal task that runs every 5 seconds
    task_id = scheduler.add_task(example_task, 5.0)
    print(f"Added task: {task_id}")
    
    # Add a retry goal task
    retry_id = scheduler.add_retry_goal(retry_goal_task, 3.0)
    if retry_id:
        print(f"Added retry goal: {retry_id}")
    
    # Add an exploration task
    exploration_id = scheduler.add_task(exploration_task, 10.0, priority=1)
    print(f"Added exploration task: {exploration_id}")
    
    scheduler.start()
    
    try:
        time.sleep(15)
        print(f"Health score: {scheduler.get_health_score():.2f}")
        print(f"Tasks: {scheduler.list_tasks()}")
        print(f"Exploration tasks: {scheduler.get_exploration_tasks()}")
        print(f"Exploration metrics: {scheduler.get_exploration_metrics()}")
    finally:
        scheduler.stop()
        print("Scheduler stopped")
# Compatibility alias for agent-generated code
TaskScheduler = Scheduler
