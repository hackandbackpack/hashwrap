"""
Notification service for sending job events to configured webhooks.
Integrates with existing webhook system and supports multiple notification channels.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import aiohttp

from sqlalchemy.orm import Session

from worker.utils.logging import get_task_logger
from worker.utils.database import get_db_session
from backend.app.models.job import Job
from backend.app.models.webhook import WebhookConfig
from backend.app.core.config import get_settings


logger = get_task_logger(__name__)


class NotificationService:
    """Service for sending notifications through configured webhooks."""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Event type mapping to webhook events
        self.event_mapping = {
            'job.created': 'job.created',
            'job.started': 'job.started',
            'job.progress': 'job.progress', 
            'job.paused': 'job.paused',
            'job.resumed': 'job.resumed',
            'job.completed': 'job.completed',
            'job.failed': 'job.failed',
            'job.cancelled': 'job.cancelled',
            'hash.cracked': 'hash.cracked',
            'system.error': 'system.error'
        }
    
    async def send_job_notification(self, job: Job, event_type: str, 
                                   extra_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Send notification for a job event."""
        logger.info(f"Sending notification for job {job.id}, event: {event_type}")
        
        try:
            # Get active webhooks for this event type
            webhooks = self._get_active_webhooks(event_type)
            
            if not webhooks:
                logger.debug(f"No webhooks configured for event type: {event_type}")
                return {'success': True, 'webhooks_sent': 0}
            
            # Build notification payload
            payload = self._build_notification_payload(job, event_type, extra_data)
            
            # Send to all configured webhooks
            results = []
            for webhook in webhooks:
                result = await self._send_webhook_notification(webhook, payload)
                results.append({
                    'webhook_id': webhook.id,
                    'webhook_name': webhook.name,
                    'success': result['success'],
                    'error': result.get('error')
                })
            
            successful_sends = sum(1 for r in results if r['success'])
            
            logger.info(f"Notification sent to {successful_sends}/{len(webhooks)} webhooks")
            
            return {
                'success': True,
                'webhooks_sent': successful_sends,
                'total_webhooks': len(webhooks),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error sending job notification: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def send_system_notification(self, event_type: str, message: str,
                                      metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Send system-level notification."""
        logger.info(f"Sending system notification: {event_type}")
        
        try:
            # Get active webhooks for system events
            webhooks = self._get_active_webhooks(event_type)
            
            if not webhooks:
                return {'success': True, 'webhooks_sent': 0}
            
            # Build system notification payload
            payload = {
                'event_type': event_type,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'hashwrap_worker',
                'metadata': metadata or {}
            }
            
            # Send to webhooks
            results = []
            for webhook in webhooks:
                result = await self._send_webhook_notification(webhook, payload)
                results.append({
                    'webhook_id': webhook.id,
                    'webhook_name': webhook.name,
                    'success': result['success'],
                    'error': result.get('error')
                })
            
            successful_sends = sum(1 for r in results if r['success'])
            
            return {
                'success': True,
                'webhooks_sent': successful_sends,
                'total_webhooks': len(webhooks),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error sending system notification: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _get_active_webhooks(self, event_type: str) -> List[WebhookConfig]:
        """Get active webhooks that should receive this event type."""
        try:
            with get_db_session() as db:
                webhooks = db.query(WebhookConfig).filter(
                    WebhookConfig.is_enabled == True
                ).all()
                
                # Filter webhooks that subscribe to this event type
                relevant_webhooks = []
                for webhook in webhooks:
                    if webhook.should_trigger(event_type):
                        relevant_webhooks.append(webhook)
                
                return relevant_webhooks
                
        except Exception as e:
            logger.error(f"Error getting active webhooks: {e}")
            return []
    
    def _build_notification_payload(self, job: Job, event_type: str, 
                                   extra_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Build notification payload for a job event."""
        payload = {
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'hashwrap_worker',
            'job': {
                'id': job.id,
                'name': job.name,
                'status': job.status.value,
                'hash_type': job.hash_type,
                'profile_name': job.profile_name,
                'total_hashes': job.total_hashes,
                'cracked_count': job.cracked_count,
                'progress_percentage': job.progress_percentage,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'runtime_seconds': job.runtime_seconds
            },
            'project': {
                'id': job.project.id if job.project else None,
                'name': job.project.name if job.project else None
            },
            'upload': {
                'id': job.upload.id if job.upload else None,
                'filename': job.upload.original_filename if job.upload else None,
                'file_size': job.upload.file_size if job.upload else None
            }
        }
        
        # Add extra data if provided
        if extra_data:
            payload['data'] = extra_data
        
        # Add event-specific data
        if event_type == 'job.progress':
            payload['progress'] = {
                'percentage': job.progress_percentage,
                'cracked_count': job.cracked_count,
                'total_hashes': job.total_hashes,
                'speed': extra_data.get('speed_human') if extra_data else None,
                'eta': extra_data.get('eta_human') if extra_data else None,
                'current_attack': extra_data.get('current_attack') if extra_data else None
            }
        
        elif event_type == 'hash.cracked':
            payload['crack_info'] = {
                'newly_cracked': extra_data.get('newly_cracked', 0) if extra_data else 0,
                'total_cracked': job.cracked_count,
                'remaining': (job.total_hashes or 0) - job.cracked_count
            }
        
        elif event_type in ['job.completed', 'job.failed', 'job.cancelled']:
            payload['completion'] = {
                'success_rate': job.progress_percentage,
                'runtime_seconds': job.runtime_seconds,
                'runtime_human': self._format_duration(job.runtime_seconds) if job.runtime_seconds else None
            }
        
        return payload
    
    async def _send_webhook_notification(self, webhook: WebhookConfig, 
                                        payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to a specific webhook."""
        try:
            headers = webhook.get_request_headers()
            timeout = aiohttp.ClientTimeout(total=webhook.timeout_seconds or 10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Add webhook signature if secret is configured
                if webhook.secret:
                    signature = self._generate_webhook_signature(payload, webhook.secret)
                    headers['X-HashWrap-Signature'] = signature
                
                # Attempt delivery with retries
                last_error = None
                
                for attempt in range(webhook.retry_attempts or 1):
                    try:
                        async with session.post(
                            webhook.webhook_url,
                            json=payload,
                            headers=headers
                        ) as response:
                            
                            if response.status < 400:
                                logger.debug(f"Webhook {webhook.name} delivered successfully")
                                return {'success': True, 'status_code': response.status}
                            else:
                                last_error = f"HTTP {response.status}: {await response.text()}"
                                logger.warning(f"Webhook {webhook.name} failed: {last_error}")
                                
                    except asyncio.TimeoutError:
                        last_error = "Request timeout"
                        logger.warning(f"Webhook {webhook.name} timed out")
                        
                    except aiohttp.ClientError as e:
                        last_error = f"Client error: {str(e)}"
                        logger.warning(f"Webhook {webhook.name} client error: {e}")
                    
                    # Wait before retry (except on last attempt)
                    if attempt < (webhook.retry_attempts or 1) - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
                return {'success': False, 'error': last_error}
                
        except Exception as e:
            logger.error(f"Error sending webhook notification to {webhook.name}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _generate_webhook_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate HMAC signature for webhook payload."""
        import hmac
        import hashlib
        
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def _format_duration(self, seconds: Optional[int]) -> Optional[str]:
        """Format duration in human-readable format."""
        if seconds is None:
            return None
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    async def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Send a test notification to a webhook."""
        try:
            with get_db_session() as db:
                webhook = db.query(WebhookConfig).filter(
                    WebhookConfig.id == webhook_id
                ).first()
                
                if not webhook:
                    return {'success': False, 'error': 'Webhook not found'}
                
                # Create test payload
                test_payload = {
                    'event_type': 'system.test',
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'hashwrap_worker',
                    'message': 'This is a test notification from HashWrap',
                    'webhook': {
                        'id': webhook.id,
                        'name': webhook.name
                    }
                }
                
                # Send test notification
                result = await self._send_webhook_notification(webhook, test_payload)
                
                return result
                
        except Exception as e:
            logger.error(f"Error testing webhook {webhook_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}


class DiscordNotificationFormatter:
    """Formatter for Discord webhook notifications."""
    
    @staticmethod
    def format_job_started(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Format job started notification for Discord."""
        job = payload['job']
        
        return {
            "embeds": [{
                "title": "🚀 Job Started",
                "description": f"Job `{job['name']}` has started processing",
                "color": 0x00ff00,  # Green
                "fields": [
                    {"name": "Hash Type", "value": job['hash_type'] or 'Unknown', "inline": True},
                    {"name": "Profile", "value": job['profile_name'] or 'Default', "inline": True},
                    {"name": "Total Hashes", "value": str(job['total_hashes'] or 0), "inline": True}
                ],
                "timestamp": payload['timestamp']
            }]
        }
    
    @staticmethod
    def format_job_progress(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Format job progress notification for Discord."""
        job = payload['job']
        progress = payload.get('progress', {})
        
        return {
            "embeds": [{
                "title": "⏳ Job Progress",
                "description": f"Progress update for `{job['name']}`",
                "color": 0xffff00,  # Yellow
                "fields": [
                    {"name": "Progress", "value": f"{progress.get('percentage', 0):.1f}%", "inline": True},
                    {"name": "Speed", "value": progress.get('speed', 'Unknown'), "inline": True},
                    {"name": "ETA", "value": progress.get('eta', 'Unknown'), "inline": True},
                    {"name": "Cracked", "value": f"{progress.get('cracked_count', 0)}", "inline": True},
                    {"name": "Attack", "value": progress.get('current_attack', 'Unknown'), "inline": True}
                ],
                "timestamp": payload['timestamp']
            }]
        }
    
    @staticmethod
    def format_job_completed(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Format job completed notification for Discord."""
        job = payload['job']
        completion = payload.get('completion', {})
        
        return {
            "embeds": [{
                "title": "✅ Job Completed",
                "description": f"Job `{job['name']}` has finished",
                "color": 0x0080ff,  # Blue
                "fields": [
                    {"name": "Results", "value": f"{job['cracked_count']}/{job['total_hashes']} cracked", "inline": True},
                    {"name": "Success Rate", "value": f"{completion.get('success_rate', 0):.1f}%", "inline": True},
                    {"name": "Duration", "value": completion.get('runtime_human', 'Unknown'), "inline": True}
                ],
                "timestamp": payload['timestamp']
            }]
        }


class SlackNotificationFormatter:
    """Formatter for Slack webhook notifications."""
    
    @staticmethod
    def format_job_started(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Format job started notification for Slack."""
        job = payload['job']
        
        return {
            "text": f"🚀 Job Started: `{job['name']}`",
            "attachments": [{
                "color": "good",
                "fields": [
                    {"title": "Hash Type", "value": job['hash_type'] or 'Unknown', "short": True},
                    {"title": "Profile", "value": job['profile_name'] or 'Default', "short": True},
                    {"title": "Total Hashes", "value": str(job['total_hashes'] or 0), "short": True}
                ],
                "ts": int(datetime.fromisoformat(payload['timestamp'].replace('Z', '+00:00')).timestamp())
            }]
        }
    
    @staticmethod
    def format_job_progress(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Format job progress notification for Slack."""
        job = payload['job']
        progress = payload.get('progress', {})
        
        return {
            "text": f"⏳ Job Progress: `{job['name']}` - {progress.get('percentage', 0):.1f}%",
            "attachments": [{
                "color": "warning",
                "fields": [
                    {"title": "Speed", "value": progress.get('speed', 'Unknown'), "short": True},
                    {"title": "ETA", "value": progress.get('eta', 'Unknown'), "short": True},
                    {"title": "Cracked", "value": str(progress.get('cracked_count', 0)), "short": True}
                ]
            }]
        }