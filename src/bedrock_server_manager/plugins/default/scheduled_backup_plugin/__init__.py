"""
A plugin to provide scheduled backup functionality for Minecraft Bedrock servers.
"""

import os
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from croniter import croniter

from bedrock_server_manager import PluginBase
from bedrock_server_manager.web import get_admin_user


# Schedule model for API requests and responses
class ScheduleModel(BaseModel):
    server_name: str = Field(..., description="Name of the server to backup")
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    backup_type: str = Field(
        default="all", description="Type of backup: 'world', 'config', or 'all'"
    )
    enabled: bool = Field(default=True, description="Whether the schedule is enabled")
    name: str = Field(..., description="Name for this backup schedule")


# Schedule storage (in-memory for now, will be replaced with database)
schedules: Dict[str, Dict[str, Any]] = {}
schedule_counter = 0
scheduler_running = False


class ScheduledBackupPlugin(PluginBase):
    version = "1.0.0"

    def on_load(self):
        """Initialize the plugin and start the scheduler."""
        self.router = APIRouter(tags=["Scheduled Backup Plugin"])
        self._define_routes()

        # Start background scheduler
        self._start_scheduler()

        self.logger.info(
            f"ScheduledBackupPlugin v{self.version} initialized with routes and scheduler."
        )

    def _define_routes(self):
        """Define web API routes for the plugin."""

        @self.router.get(
            "/scheduled_backup",
            response_class=HTMLResponse,
            name="Scheduled Backup Management",
            summary="Manage Backup Schedules",
            tags=["plugin-ui"],
        )
        async def get_schedules_page(
            request: Request,
            current_user: Dict[str, Any] = Depends(get_admin_user),
        ):
            """Display the schedule management page."""
            templates_env = self.api.app_context.templates
            return templates_env.TemplateResponse(
                "schedule_management.html", {"request": request}
            )

        @self.router.get(
            "/api/scheduled_backup/schedules", response_model=List[ScheduleModel]
        )
        async def get_schedules():
            """Get all backup schedules."""
            return list(schedules.values())

        @self.router.post(
            "/api/scheduled_backup/schedules", response_model=ScheduleModel
        )
        async def create_schedule(schedule: ScheduleModel):
            """Create a new backup schedule."""
            global schedule_counter
            schedule_id = f"schedule_{schedule_counter}"
            schedule_counter += 1

            schedules[schedule_id] = {
                **schedule.dict(),
                "id": schedule_id,
                "created_at": datetime.now().isoformat(),
                "last_run": None,
                "next_run": None,
            }

            self.logger.info(
                f"Created new backup schedule: {schedule_id} for server {schedule.server_name}"
            )
            return schedules[schedule_id]

        @self.router.put(
            "/api/scheduled_backup/schedules/{schedule_id}",
            response_model=ScheduleModel,
        )
        async def update_schedule(schedule_id: str, schedule: ScheduleModel):
            """Update an existing backup schedule."""
            if schedule_id not in schedules:
                raise HTTPException(status_code=404, detail="Schedule not found")

            schedules[schedule_id].update(schedule.dict())
            schedules[schedule_id]["updated_at"] = datetime.now().isoformat()

            self.logger.info(f"Updated backup schedule: {schedule_id}")
            return schedules[schedule_id]

        @self.router.delete("/api/scheduled_backup/schedules/{schedule_id}")
        async def delete_schedule(schedule_id: str):
            """Delete a backup schedule."""
            if schedule_id not in schedules:
                raise HTTPException(status_code=404, detail="Schedule not found")

            del schedules[schedule_id]
            self.logger.info(f"Deleted backup schedule: {schedule_id}")
            return {"message": "Schedule deleted successfully"}

        @self.router.post("/api/scheduled_backup/schedules/{schedule_id}/execute")
        async def execute_schedule(schedule_id: str):
            """Manually trigger a backup for a schedule."""
            if schedule_id not in schedules:
                raise HTTPException(status_code=404, detail="Schedule not found")

            schedule = schedules[schedule_id]
            self.logger.info(f"Manually triggering backup for schedule: {schedule_id}")

            # Run the backup
            await self._execute_backup(schedule)

            return {"message": "Backup execution started"}

    async def _execute_backup(self, schedule: Dict[str, Any]):
        """Execute a backup based on the schedule configuration."""
        server_name = schedule["server_name"]
        backup_type = schedule["backup_type"]

        try:
            self.logger.info(
                f"Starting backup for server '{server_name}', type: {backup_type}"
            )

            if backup_type == "world":
                result = self.api.backup_world(server_name=server_name)
            elif backup_type == "config":
                result = self.api.backup_config_file(
                    server_name=server_name, file_to_backup="server.properties"
                )
            else:  # "all"
                result = self.api.backup_all(server_name=server_name)

            if result.get("status") == "success":
                self.logger.info(
                    f"Backup completed successfully for server '{server_name}'"
                )
                # Update last run time
                schedule["last_run"] = datetime.now().isoformat()
            else:
                self.logger.error(
                    f"Backup failed for server '{server_name}': {result.get('message', 'Unknown error')}"
                )

        except Exception as e:
            self.logger.error(
                f"Error executing backup for server '{server_name}': {e}", exc_info=True
            )

    def _calculate_next_run(self, cron_expression: str) -> Optional[str]:
        """Calculate the next run time based on a cron expression."""
        try:
            cron = croniter(cron_expression, datetime.now())
            next_run = cron.get_next(datetime)
            return next_run.isoformat()
        except Exception as e:
            self.logger.error(f"Error parsing cron expression '{cron_expression}': {e}")
            return None

    def _scheduler_loop(self):
        """Background thread for checking and executing scheduled backups."""
        global scheduler_running

        while scheduler_running:
            try:
                now = datetime.now()

                for schedule_id, schedule in list(schedules.items()):
                    if schedule.get("enabled", False):
                        # Calculate next run time if not already set
                        if "next_run" not in schedule or not schedule["next_run"]:
                            schedule["next_run"] = self._calculate_next_run(
                                schedule["cron_expression"]
                            )

                        # Check if it's time to run the backup
                        if schedule.get("next_run") and now >= datetime.fromisoformat(
                            schedule["next_run"]
                        ):
                            # Run the backup in a separate thread to avoid blocking
                            asyncio.run(self._execute_backup(schedule))

                            # Calculate next run time
                            schedule["next_run"] = self._calculate_next_run(
                                schedule["cron_expression"]
                            )

                # Sleep for 60 seconds
                threading.Event().wait(60)

            except Exception as e:
                self.logger.error(f"Error in scheduler thread: {e}", exc_info=True)
                threading.Event().wait(60)  # Continue even if there's an error

    def _start_scheduler(self):
        """Start the scheduler in a separate thread."""
        global scheduler_running

        if scheduler_running:
            return

        scheduler_running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self.scheduler_thread.start()
        self.logger.info("Scheduler started in background thread")

    def _stop_scheduler(self):
        """Stop the scheduler."""
        global scheduler_running

        scheduler_running = False
        if hasattr(self, "scheduler_thread") and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        self.logger.info("Scheduler stopped")

    def on_unload(self):
        """Clean up when the plugin is unloaded."""
        # Stop the scheduler
        self._stop_scheduler()

        self.logger.info(f"ScheduledBackupPlugin v{self.version} unloaded.")

    def get_fastapi_routers(self):
        """Return the FastAPI router for this plugin."""
        return [self.router]

    def get_template_paths(self):
        """Return the path to the plugin's templates directory."""
        plugin_dir = Path(__file__).parent
        return [plugin_dir / "templates"]

    def get_static_mounts(self):
        """Return the configuration for static file mounts."""
        plugin_dir = Path(__file__).parent
        static_dir = plugin_dir / "static"
        return [("/static/scheduled_backup", static_dir, "scheduled_backup_static")]
