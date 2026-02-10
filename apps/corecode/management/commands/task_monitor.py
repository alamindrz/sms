# management/commands/task_monitor.py
import time
from django.core.management.base import BaseCommand
from celery.task.control import inspect
import redis
from tasks.config import TASK_CONFIG
import logging

logger = logging.getLogger('tasks')

class Command(BaseCommand):
    help = 'Monitor Celery tasks and queue status'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Monitoring interval in seconds'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['once']
        
        self.stdout.write("🚀 Starting Celery Task Monitor")
        self.stdout.write(f"   Interval: {interval} seconds")
        self.stdout.write(f"   Broker: {TASK_CONFIG['BROKER_URL']}")
        self.stdout.write("-" * 50)
        
        try:
            # Connect to Redis for queue info
            r = redis.from_url(TASK_CONFIG['BROKER_URL'])
            
            while True:
                self.print_queue_status(r)
                
                if run_once:
                    break
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.stdout.write("\n👋 Monitor stopped by user")
        except Exception as e:
            self.stdout.write(f"\n❌ Error: {str(e)}")
    
    def print_queue_status(self, redis_client):
        """Print current queue status"""
        try:
            # Get queue length
            queue_length = redis_client.llen('celery')
            
            # Get active tasks
            i = inspect()
            active_tasks = i.active() or {}
            
            # Format output
            output = []
            
            # Queue info
            if queue_length > 0:
                output.append(f"📊 Queue: {queue_length} task{'s' if queue_length > 1 else ''} waiting")
            else:
                output.append("📊 Queue: Empty")
            
            # Active workers/tasks
            if active_tasks:
                total_active = sum(len(tasks) for tasks in active_tasks.values())
                output.append(f"⚡ Active: {total_active} task{'s' if total_active > 1 else ''}")
                
                # Show what's running
                for worker, tasks in active_tasks.items():
                    if tasks:
                        task_names = [t['name'].split('.')[-1] for t in tasks]
                        unique_tasks = set(task_names)
                        
                        if len(unique_tasks) <= 3:
                            tasks_str = ', '.join(unique_tasks)
                        else:
                            tasks_str = f"{len(unique_tasks)} different tasks"
                        
                        output.append(f"   {worker.split('@')[0]}: {tasks_str}")
            else:
                output.append("⚡ Active: No active tasks")
            
            # Clear line and print
            self.stdout.write('\r' + ' | '.join(output) + ' ' * 10, ending='')
            
        except Exception as e:
            self.stdout.write(f"\r❌ Error getting queue status: {str(e)}")