# Scheduled Backup Plugin

A plugin for Bedrock Server Manager that provides automated backup scheduling capabilities for Minecraft Bedrock servers.

## Features

- Create, read, update, and delete backup schedules
- Support for cron-like scheduling expressions (e.g., "0 2 * * *" for daily at 2 AM)
- Server-specific schedule configuration
- Enable/disable schedules without deletion
- Manual backup trigger option
- Visual feedback for schedule execution status
- Integration with existing backup APIs

## Installation

The plugin is automatically detected when placed in the appropriate directory. No additional installation steps are required.

## Usage

1. Enable the plugin through the Web UI under "Plugins"
2. Navigate to "Scheduled Backup" from the main navigation
3. Create new backup schedules using the web interface
4. Configure schedules with specific servers, cron expressions, and backup types
5. Enable/disable schedules as needed
6. Manually trigger backups when required

## Configuration

### Schedule Options

- **Name**: A descriptive name for the backup schedule
- **Server**: Select the server to backup
- **Cron Expression**: Define when the backup should run (see examples below)
- **Backup Type**: Choose between "All", "World only", or "Config only"
- **Enabled**: Toggle the schedule on/off

### Cron Expression Examples

- `0 2 * * *` - Daily at 2:00 AM
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday at midnight
- `0 0 1 * *` - Monthly on the 1st at midnight

## API Endpoints

- `GET /scheduled_backup` - Display schedule management page
- `GET /api/scheduled_backup/schedules` - List all schedules
- `POST /api/scheduled_backup/schedules` - Create a new schedule
- `PUT /api/scheduled_backup/schedules/{id}` - Update an existing schedule
- `DELETE /api/scheduled_backup/schedules/{id}` - Delete a schedule
- `POST /api/scheduled_backup/schedules/{id}/execute` - Manually trigger a backup

## Requirements

- Python 3.9+
- croniter library (automatically installed with dependencies)
- Bedrock Server Manager 2.1.0+

## Troubleshooting

### Logs

Plugin logs can be found in the main application logs. Look for entries with "ScheduledBackupPlugin" prefix.

### Common Issues

1. **Backups not running**: 
   - Check that the schedule is enabled
   - Verify the cron expression is valid
   - Ensure the server exists and is accessible

2. **Permission errors**:
   - Verify the application has read/write permissions for backup directories
   - Check server configuration files for correct permissions

3. **Synchronization issues**:
   - Restart the application to reload plugin configuration
   - Check for error messages in the logs

## Limitations

- Currently uses in-memory storage for schedules (not persistent)
- Limited to one concurrent backup operation per schedule
- No automatic pruning of old backup files

## Future Enhancements

- Persistent storage using SQLite database
- Concurrent backup operations
- Automatic backup retention policies
- Email/SMS notifications for backup status
- Integration with external storage services

## Support

For issues or feature requests, please create an issue in the Bedrock Server Manager GitHub repository.
