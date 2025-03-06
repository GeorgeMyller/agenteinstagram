import os
import threading
import time
import uuid
import json
from enum import Enum
from datetime import datetime
from queue import Queue
from typing import Dict, List, Any, Optional

# Custom exceptions
class RateLimitExceeded(Exception):
    """Raised when API rate limits are exceeded"""
    pass

class ContentPolicyViolation(Exception):
    """Raised when content violates Instagram guidelines"""
    pass

class PostStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    CONTENT_VIOLATION = "content_violation"

class PostQueue:
    """
    Queue system for processing Instagram posts asynchronously
    """
    
    def __init__(self, max_workers=2, poll_interval=5):
        self.queue = Queue()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self.active_workers = 0
        self.lock = threading.Lock()
        self.history: List[Dict[str, Any]] = []
        self.max_history = 100
        self.workers = []
        self.running = False
        
        # Metrics
        self.total_posts = 0
        self.successful_posts = 0
        self.failed_posts = 0
        self.rate_limited_posts = 0
        self.content_violations = 0
        self.last_processing_times = []  # Store last 10 processing times
        
        # Load history if exists
        self._load_history()
    
    def start(self):
        """Start the queue processing"""
        if self.running:
            return
            
        self.running = True
        
        # Start worker threads
        for _ in range(self.max_workers):
            worker = threading.Thread(target=self._worker_thread, daemon=True)
            worker.start()
            self.workers.append(worker)
            
        print(f"Post queue started with {self.max_workers} workers")
    
    def stop(self):
        """Stop the queue processing"""
        self.running = False
        
        # Wait for workers to finish
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=30)
        
        self.workers = []
        print("Post queue stopped")
    
    def add_job(self, image_path: str, caption: str, inputs: Optional[Dict] = None) -> str:
        """
        Add a new job to the queue
        
        Args:
            image_path: Path to the image file
            caption: Caption text
            inputs: Additional configuration
            
        Returns:
            job_id: Unique identifier for tracking the job
        """
        # Check if content violates policy
        if self._check_content_policy(image_path, caption):
            raise ContentPolicyViolation("O conteúdo viola as diretrizes do Instagram")
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Create job data
        job = {
            "id": job_id,
            "image_path": image_path,
            "caption": caption,
            "inputs": inputs or {},
            "status": PostStatus.QUEUED.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None,
            "result": None
        }
        
        # Add to jobs dictionary
        with self.lock:
            self.jobs[job_id] = job
            self.total_posts += 1
        
        # Add to queue
        self.queue.put(job_id)
        
        print(f"Job added to queue: {job_id}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Dict:
        """
        Get the status of a job
        
        Args:
            job_id: The job identifier
            
        Returns:
            job status information
        """
        with self.lock:
            if job_id in self.jobs:
                return self.jobs[job_id].copy()
            
            # Check in history
            for job in self.history:
                if job["id"] == job_id:
                    return job.copy()
        
        return {"error": "Job not found", "status": "not_found"}
    
    def get_queue_stats(self) -> Dict:
        """Get current queue statistics"""
        with self.lock:
            pending_jobs = self.queue.qsize()
            active_jobs = self.active_workers
            
            avg_time = 0
            if self.last_processing_times:
                avg_time = sum(self.last_processing_times) / len(self.last_processing_times)
            
            return {
                "pending_jobs": pending_jobs,
                "active_jobs": active_jobs,
                "total_posts": self.total_posts,
                "successful_posts": self.successful_posts,
                "failed_posts": self.failed_posts,
                "rate_limited_posts": self.rate_limited_posts,
                "content_violations": self.content_violations,
                "average_processing_time": avg_time,
                "queue_length": self.queue.qsize()
            }
    
    def get_job_history(self, limit=10) -> List[Dict]:
        """Get recent job history"""
        with self.lock:
            return self.history[:limit]
    
    def _worker_thread(self):
        """Worker thread that processes jobs from the queue"""
        while self.running:
            try:
                # Get a job from the queue with timeout
                try:
                    job_id = self.queue.get(timeout=1.0)
                except Exception:
                    # Timeout, no jobs available
                    continue
                
                # Get job details
                with self.lock:
                    if job_id not in self.jobs:
                        self.queue.task_done()
                        continue
                    
                    job = self.jobs[job_id]
                    job["status"] = PostStatus.PROCESSING.value
                    job["updated_at"] = datetime.now().isoformat()
                    self.active_workers += 1
                
                # Process the job
                start_time = time.time()
                try:
                    # Import here to avoid circular imports
                    from src.services.instagram_send import InstagramSend
                    
                    # Process the post
                    result = InstagramSend.send_instagram(
                        job["image_path"], 
                        job["caption"], 
                        job["inputs"]
                    )
                    
                    # Update job with success
                    with self.lock:
                        if job_id in self.jobs:
                            job = self.jobs[job_id]
                            if result:
                                job["status"] = PostStatus.COMPLETED.value
                                job["result"] = result
                                self.successful_posts += 1
                            else:
                                job["status"] = PostStatus.FAILED.value
                                job["error"] = "Failed to post image, but no specific error was returned"
                                self.failed_posts += 1
                            
                            job["completed_at"] = datetime.now().isoformat()
                            job["updated_at"] = datetime.now().isoformat()
                    
                except RateLimitExceeded as e:
                    with self.lock:
                        if job_id in self.jobs:
                            self.jobs[job_id]["status"] = PostStatus.RATE_LIMITED.value
                            self.jobs[job_id]["error"] = str(e)
                            self.jobs[job_id]["updated_at"] = datetime.now().isoformat()
                            self.rate_limited_posts += 1
                            
                    # Requeue with delay
                    threading.Timer(300, lambda: self.queue.put(job_id)).start()
                    
                except ContentPolicyViolation as e:
                    with self.lock:
                        if job_id in self.jobs:
                            self.jobs[job_id]["status"] = PostStatus.CONTENT_VIOLATION.value
                            self.jobs[job_id]["error"] = str(e)
                            self.jobs[job_id]["updated_at"] = datetime.now().isoformat()
                            self.jobs[job_id]["completed_at"] = datetime.now().isoformat()
                            self.content_violations += 1
                            
                            # Move to history
                            self._move_to_history(job_id)
                    
                except Exception as e:
                    with self.lock:
                        if job_id in self.jobs:
                            self.jobs[job_id]["status"] = PostStatus.FAILED.value
                            self.jobs[job_id]["error"] = str(e)
                            self.jobs[job_id]["updated_at"] = datetime.now().isoformat()
                            self.jobs[job_id]["completed_at"] = datetime.now().isoformat()
                            self.failed_posts += 1
                            
                            # Move to history
                            self._move_to_history(job_id)
                
                finally:
                    # Calculate processing time
                    process_time = time.time() - start_time
                    
                    with self.lock:
                        self.active_workers -= 1
                        self.last_processing_times.append(process_time)
                        if len(self.last_processing_times) > 10:
                            self.last_processing_times.pop(0)
                        
                        # If job is completed or failed, move to history
                        if job_id in self.jobs:
                            job = self.jobs[job_id]
                            if job["status"] in [PostStatus.COMPLETED.value, PostStatus.FAILED.value, 
                                            PostStatus.CONTENT_VIOLATION.value]:
                                self._move_to_history(job_id)
                    
                    # Mark task as done
                    self.queue.task_done()
                    
            except Exception as e:
                print(f"Error in worker thread: {e}")
                with self.lock:
                    self.active_workers -= 1
    
    def _move_to_history(self, job_id: str):
        """Move a job from active jobs to history"""
        with self.lock:
            if job_id in self.jobs:
                # Add to history
                self.history.insert(0, self.jobs[job_id])
                
                # Remove from active jobs
                del self.jobs[job_id]
                
                # Trim history if needed
                if len(self.history) > self.max_history:
                    self.history = self.history[:self.max_history]
                    
                # Save history
                self._save_history()
    
    def _save_history(self):
        """Save job history to disk"""
        try:
            with open("instagram_post_history.json", "w") as f:
                json.dump(self.history, f)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def _load_history(self):
        """Load job history from disk"""
        try:
            if os.path.exists("instagram_post_history.json"):
                with open("instagram_post_history.json", "r") as f:
                    self.history = json.load(f)
                    
                # Update metrics from history
                for job in self.history:
                    if job["status"] == PostStatus.COMPLETED.value:
                        self.successful_posts += 1
                    elif job["status"] == PostStatus.FAILED.value:
                        self.failed_posts += 1
                    elif job["status"] == PostStatus.RATE_LIMITED.value:
                        self.rate_limited_posts += 1
                    elif job["status"] == PostStatus.CONTENT_VIOLATION.value:
                        self.content_violations += 1
                        
                print(f"Loaded {len(self.history)} items from history")
        except Exception as e:
            print(f"Error loading history: {e}")
            self.history = []
    
    def _check_content_policy(self, image_path: str, caption: str) -> bool:
        """
        Check if content violates Instagram policies
        
        Returns:
            bool: True if content violates policy
        """
        # Check for obvious policy violations
        forbidden_words = [
            "porn", "nude", "naked", "sex", "viagra", "cialis", "gambling",
            "casino", "bet", "drugs", "cocaine", "heroin", "marijuana"
        ]
        
        # Check caption for forbidden words
        if caption:
            caption_lower = caption.lower()
            for word in forbidden_words:
                if word in caption_lower:
                    return True
        
        # TODO: Implement image content checking with ML model
        # For now, just check if file exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")
        
        return False


# Create a global instance
post_queue = PostQueue(max_workers=2)

# Auto-start the queue
post_queue.start()