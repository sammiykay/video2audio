"""Threaded job runner with progress reporting and cancellation support."""

import logging
import queue
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from PySide6.QtCore import QObject, Signal

from .converter import AudioConverter, ConversionError, ConversionParams, FFmpegNotFoundError
from .fsutils import OverwritePolicy, ValidationError, get_safe_output_directory

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status enumeration."""
    QUEUED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    SKIPPED = auto()


@dataclass
class JobResult:
    """Result of a conversion job."""
    success: bool
    message: str
    output_path: Optional[Path] = None
    error_code: Optional[str] = None
    duration: float = 0.0


@dataclass
class ConversionJob:
    """A single conversion job."""
    id: str
    input_path: Path
    output_path: Path
    params: ConversionParams
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    result: Optional[JobResult] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: str = ""
    _signals_sent: set = None  # Track which signals were already sent for this job
    
    def __post_init__(self) -> None:
        """Initialize after dataclass creation."""
        if self._signals_sent is None:
            self._signals_sent = set()
    
    @property
    def duration(self) -> float:
        """Get job duration in seconds."""
        if self.started_at is None:
            return 0.0
        end_time = self.completed_at or time.time()
        return end_time - self.started_at
    
    @property
    def eta_seconds(self) -> Optional[float]:
        """Estimate time remaining in seconds."""
        if self.status != JobStatus.RUNNING or self.progress <= 0:
            return None
        
        elapsed = self.duration
        if elapsed <= 0:
            return None
        
        estimated_total = elapsed / self.progress
        return max(0, estimated_total - elapsed)


class WorkerSignals(QObject):
    """Signals emitted by the worker for GUI updates."""
    
    # Job lifecycle signals
    job_started = Signal(str)  # job_id
    job_progress = Signal(str, float)  # job_id, progress (0-1)
    job_completed = Signal(str, JobResult)  # job_id, result
    job_failed = Signal(str, str)  # job_id, error_message
    job_cancelled = Signal(str)  # job_id
    job_skipped = Signal(str, str)  # job_id, reason
    
    # Queue management signals
    queue_updated = Signal()  # Queue contents changed
    all_jobs_completed = Signal(dict)  # Summary stats
    
    # Error signals
    worker_error = Signal(str)  # Critical worker error


class ConversionWorker:
    """Thread-safe conversion worker with job queue management."""
    
    def __init__(self, max_workers: int = 4) -> None:
        """Initialize worker with maximum concurrent jobs."""
        self.max_workers = max_workers
        self.signals = WorkerSignals()
        
        # Job queue and tracking
        self._jobs: Dict[str, ConversionJob] = {}
        self._job_queue: queue.Queue[str] = queue.Queue()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: Dict[str, Future] = {}
        
        # State management
        self._is_running = False
        self._is_paused = False
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._completion_signaled = False  # Track if completion signal was sent
        
        # Converter instance
        self._converter: Optional[AudioConverter] = None
        
        # Lock for thread safety
        self._lock = threading.RLock()
    
    def initialize_converter(self, ffmpeg_path: Optional[str] = None) -> None:
        """Initialize FFmpeg converter."""
        try:
            self._converter = AudioConverter(ffmpeg_path)
            logger.info("FFmpeg converter initialized successfully")
        except FFmpegNotFoundError as e:
            error_msg = f"FFmpeg not found: {e.message}"
            logger.error(error_msg)
            self.signals.worker_error.emit(error_msg)
            raise
        except Exception as e:
            error_msg = f"Failed to initialize converter: {str(e)}"
            logger.error(error_msg)
            self.signals.worker_error.emit(error_msg)
            raise
    
    def add_job(
        self,
        job_id: str,
        input_path: Path,
        output_path: Path,
        params: ConversionParams,
        overwrite_policy: str = OverwritePolicy.UNIQUE
    ) -> bool:
        """Add a new conversion job to the queue."""
        try:
            # Validate input
            if not input_path.exists():
                logger.error(f"Input file not found: {input_path}")
                return False
            
            # Resolve output path based on overwrite policy
            resolved_output, should_skip = OverwritePolicy.resolve_output_path(
                output_path, overwrite_policy
            )
            
            if should_skip:
                # Create a skipped job
                job = ConversionJob(
                    id=job_id,
                    input_path=input_path,
                    output_path=resolved_output,
                    params=params,
                    status=JobStatus.SKIPPED
                )
                job.error_message = f"File already exists: {resolved_output}"
                
                with self._lock:
                    self._jobs[job_id] = job
                    job._signals_sent.add("skipped")  # Mark as already signaled
                
                self.signals.job_skipped.emit(job_id, job.error_message)
                self.signals.queue_updated.emit()
                return True
            
            # Create job
            job = ConversionJob(
                id=job_id,
                input_path=input_path,
                output_path=resolved_output,
                params=params
            )
            
            with self._lock:
                self._jobs[job_id] = job
                self._job_queue.put(job_id)
                # Reset completion signal when new jobs are added
                self._completion_signaled = False
            
            self.signals.queue_updated.emit()
            logger.info(f"Added job {job_id}: {input_path} -> {resolved_output}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {str(e)}")
            return False
    
    def add_batch_jobs(
        self,
        input_files: List[Path],
        output_directory: Optional[Path],
        params: ConversionParams,
        overwrite_policy: str = OverwritePolicy.UNIQUE
    ) -> Dict[str, bool]:
        """Add multiple jobs in batch."""
        results = {}
        
        for i, input_path in enumerate(input_files):
            job_id = f"job_{int(time.time())}_{i}"
            
            # Determine output directory
            if output_directory is not None:
                # Use specified output directory
                final_output_dir = output_directory
            else:
                # Use source file directory
                final_output_dir = input_path.parent
            
            # Generate output path
            output_filename = input_path.stem + f".{params.output_format}"
            output_path = final_output_dir / output_filename
            
            success = self.add_job(job_id, input_path, output_path, params, overwrite_policy)
            results[job_id] = success
        
        return results
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue (only if not running)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            
            if job.status == JobStatus.RUNNING:
                # Cancel running job
                return self.cancel_job(job_id)
            
            # Remove from queue and jobs
            if job.status == JobStatus.QUEUED:
                # Remove from queue (inefficient but works for our use case)
                temp_jobs = []
                while not self._job_queue.empty():
                    try:
                        queued_id = self._job_queue.get_nowait()
                        if queued_id != job_id:
                            temp_jobs.append(queued_id)
                    except queue.Empty:
                        break
                
                for queued_id in temp_jobs:
                    self._job_queue.put(queued_id)
            
            del self._jobs[job_id]
            
        self.signals.queue_updated.emit()
        logger.info(f"Removed job {job_id}")
        return True
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a specific job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            
            if job.status == JobStatus.RUNNING:
                # Cancel the future
                future = self._futures.get(job_id)
                if future:
                    future.cancel()
                
                job.status = JobStatus.CANCELLED
                job.completed_at = time.time()
                
                if "cancelled" not in job._signals_sent:
                    job._signals_sent.add("cancelled")
                    self.signals.job_cancelled.emit(job_id)
                self.signals.queue_updated.emit()
                return True
            
            elif job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                if "cancelled" not in job._signals_sent:
                    job._signals_sent.add("cancelled")
                    self.signals.job_cancelled.emit(job_id)
                self.signals.queue_updated.emit()
                return True
        
        return False
    
    def cancel_all_jobs(self) -> None:
        """Cancel all jobs."""
        with self._lock:
            job_ids = list(self._jobs.keys())
        
        for job_id in job_ids:
            self.cancel_job(job_id)
    
    def clear_completed_jobs(self) -> None:
        """Remove completed/failed/cancelled jobs from the list."""
        with self._lock:
            completed_jobs = [
                job_id for job_id, job in self._jobs.items()
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.SKIPPED)
            ]
            
            for job_id in completed_jobs:
                del self._jobs[job_id]
        
        self.signals.queue_updated.emit()
        logger.info(f"Cleared {len(completed_jobs)} completed jobs")
    
    def get_job(self, job_id: str) -> Optional[ConversionJob]:
        """Get job by ID."""
        with self._lock:
            return self._jobs.get(job_id)
    
    def get_all_jobs(self) -> List[ConversionJob]:
        """Get all jobs (thread-safe copy)."""
        with self._lock:
            return list(self._jobs.values())
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        with self._lock:
            stats = {
                "total": len(self._jobs),
                "queued": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "skipped": 0,
            }
            
            for job in self._jobs.values():
                if job.status == JobStatus.QUEUED:
                    stats["queued"] += 1
                elif job.status == JobStatus.RUNNING:
                    stats["running"] += 1
                elif job.status == JobStatus.COMPLETED:
                    stats["completed"] += 1
                elif job.status == JobStatus.FAILED:
                    stats["failed"] += 1
                elif job.status == JobStatus.CANCELLED:
                    stats["cancelled"] += 1
                elif job.status == JobStatus.SKIPPED:
                    stats["skipped"] += 1
            
            return stats
    
    def start_processing(self) -> None:
        """Start the worker thread for processing jobs."""
        if self._is_running:
            return
        
        if not self._converter:
            self.initialize_converter()
        
        self._is_running = True
        self._is_paused = False
        self._shutdown_event.clear()
        self._completion_signaled = False  # Reset completion signal
        
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        
        logger.info("Worker started")
    
    def pause_processing(self) -> None:
        """Pause job processing."""
        self._is_paused = True
        logger.info("Worker paused")
    
    def resume_processing(self) -> None:
        """Resume job processing."""
        self._is_paused = False
        logger.info("Worker resumed")
    
    def stop_processing(self, timeout: float = 30.0) -> None:
        """Stop the worker thread and cleanup."""
        if not self._is_running:
            return
        
        logger.info("Stopping worker...")
        self._is_running = False
        self._shutdown_event.set()
        
        # Cancel all running jobs
        if self._executor:
            # Cancel futures
            for future in self._futures.values():
                future.cancel()
            
            # Shutdown executor
            self._executor.shutdown(wait=False)
        
        # Wait for worker thread
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        
        self._executor = None
        self._futures.clear()
        logger.info("Worker stopped")
    
    def _worker_loop(self) -> None:
        """Main worker loop that processes jobs."""
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        try:
            while self._is_running and not self._shutdown_event.is_set():
                # Wait if paused
                if self._is_paused:
                    time.sleep(0.1)
                    continue
                
                # Check for completed jobs
                self._check_completed_jobs()
                
                # Start new jobs if capacity available
                if len(self._futures) < self.max_workers:
                    self._start_next_job()
                
                # Check if all jobs are done
                if self._job_queue.empty() and not self._futures:
                    stats = self.get_queue_stats()
                    if stats["queued"] == 0 and stats["running"] == 0 and not self._completion_signaled:
                        self._completion_signaled = True
                        self.signals.all_jobs_completed.emit(stats)
                
                time.sleep(0.1)  # Prevent busy waiting
                
        except Exception as e:
            logger.error(f"Worker loop error: {str(e)}")
            self.signals.worker_error.emit(f"Worker error: {str(e)}")
        finally:
            if self._executor:
                self._executor.shutdown(wait=True)
    
    def _start_next_job(self) -> None:
        """Start the next job from the queue."""
        try:
            job_id = self._job_queue.get_nowait()
        except queue.Empty:
            return
        
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != JobStatus.QUEUED:
                return
            
            # Mark as running
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            
            # Submit job to executor
            future = self._executor.submit(self._execute_job, job)
            self._futures[job_id] = future
            
            # Only emit started signal once
            if "started" not in job._signals_sent:
                job._signals_sent.add("started")
                self.signals.job_started.emit(job_id)
        
        self.signals.queue_updated.emit()
    
    def _check_completed_jobs(self) -> None:
        """Check for completed futures and update job status."""
        completed_jobs = []
        
        for job_id, future in list(self._futures.items()):
            if future.done():
                completed_jobs.append(job_id)
                
                with self._lock:
                    job = self._jobs.get(job_id)
                    if not job:
                        continue
                    
                    job.completed_at = time.time()
                    
                    try:
                        result = future.result()
                        job.result = result
                        
                        if result.success:
                            job.status = JobStatus.COMPLETED
                            # Only emit if not already sent
                            if "completed" not in job._signals_sent:
                                job._signals_sent.add("completed")
                                self.signals.job_completed.emit(job_id, result)
                        else:
                            job.status = JobStatus.FAILED
                            job.error_message = result.message
                            # Only emit if not already sent
                            if "failed" not in job._signals_sent:
                                job._signals_sent.add("failed")
                                self.signals.job_failed.emit(job_id, result.message)
                    
                    except Exception as e:
                        job.status = JobStatus.FAILED
                        job.error_message = str(e)
                        # Only emit if not already sent
                        if "failed" not in job._signals_sent:
                            job._signals_sent.add("failed")
                            self.signals.job_failed.emit(job_id, str(e))
        
        # Remove completed futures
        for job_id in completed_jobs:
            self._futures.pop(job_id, None)
        
        if completed_jobs:
            self.signals.queue_updated.emit()
    
    def _execute_job(self, job: ConversionJob) -> JobResult:
        """Execute a single conversion job."""
        logger.info(f"Starting job {job.id}: {job.input_path} -> {job.output_path}")
        
        start_time = time.time()
        
        try:
            if not self._converter:
                raise ConversionError("Converter not initialized")
            
            # Create output directory if needed
            job.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Progress callback
            def progress_callback(progress: float) -> None:
                with self._lock:
                    job.progress = progress
                self.signals.job_progress.emit(job.id, progress)
            
            # Execute conversion
            self._converter.convert(
                job.input_path,
                job.output_path,
                job.params,
                progress_callback
            )
            
            duration = time.time() - start_time
            
            # Verify output file was created
            if not job.output_path.exists():
                raise ConversionError("Output file was not created")
            
            logger.info(f"Job {job.id} completed successfully in {duration:.1f}s")
            
            return JobResult(
                success=True,
                message="Conversion completed successfully",
                output_path=job.output_path,
                duration=duration
            )
            
        except ConversionError as e:
            error_msg = f"Conversion failed: {e.message}"
            logger.error(f"Job {job.id} failed: {error_msg}")
            
            return JobResult(
                success=False,
                message=error_msg,
                error_code="CONVERSION_ERROR",
                duration=time.time() - start_time
            )
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Job {job.id} failed: {error_msg}")
            
            return JobResult(
                success=False,
                message=error_msg,
                error_code="UNKNOWN_ERROR",
                duration=time.time() - start_time
            )