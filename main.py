import asyncio
import settings
import discord
from discord.ext import commands
import connections.firebase as fb
import time
import weakref
from typing import Dict, Set, Optional
from collections import defaultdict, deque
import logging
import traceback
import threading


# logger setup
logger = settings.logging.getLogger("bot")
cogs_logger = settings.logging.getLogger("cogs")
tree_logger = settings.logging.getLogger("tree")

# Import network utilities for TLS error handling
try:
    from network_utils import monitor_network_health, check_network_connectivity
    NETWORK_MONITORING_AVAILABLE = True
except ImportError:
    NETWORK_MONITORING_AVAILABLE = False
    logger.info("Network monitoring not available")

# Client class
class Client(commands.Bot):
    def __init__(self):
        # Enable only essential intents to reduce memory usage
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.presences = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix="'",
            intents=intents,
            help_command=None,
            case_insensitive=True,
            chunk_guilds_at_startup=False,  # Disable guild chunking for memory
            max_messages=1000,  # Limit message cache
            status=discord.Status.idle  # Set initial status
        )
        
        self.client = self
        
        # Performance monitoring
        self._start_time = time.time()
        self._command_stats = defaultdict(int)
        self._error_counts = defaultdict(int)
        self._active_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        
        # Rate limiting for admin commands
        self._rate_limiter = RateLimiter(max_calls=5, time_window=60)  # 5 calls per minute
        self._recent_admin_calls = deque(maxlen=20)
        
        # Memory management
        self._loaded_extensions: Set[str] = set()
        self._extension_load_times: Dict[str, float] = {}
        self._cog_cleanup_task: Optional[asyncio.Task] = None
        
        # Background monitoring
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def setup_hook(self):
        """Initialize the bot with optimized settings"""
        logger.info(f'Starting bot as {self.user} (ID: {self.user.id})')
        
        try:
            # Load cogs efficiently
            await self._load_cogs_optimized()
            
            # Start background tasks
            await self._start_background_tasks()
            
            tree_logger.info("Bot is Ready!")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            logger.error(traceback.format_exc())
            raise
        
    async def _load_cogs_optimized(self):
        """Load cogs with performance monitoring and error handling"""
        cogs_logger.info("Loading cogs...")
        
        loaded_count = 0
        failed_loads = []
        
        for cog_file in settings.COGS_DIR.glob("*.py"):
            if cog_file.name == "__init__.py":
                continue
            
            extension_name = f'cogs.{cog_file.name[:-3]}'
            
            try:
                start_time = time.time()
                
                # Check if extension was already loaded
                if extension_name in self._loaded_extensions:
                    cogs_logger.info(f"Extension {extension_name} already loaded, skipping")
                    continue
                
                await self.load_extension(extension_name)
                load_time = time.time() - start_time
                
                self._loaded_extensions.add(extension_name)
                self._extension_load_times[extension_name] = load_time
                
                loaded_count += 1
                cogs_logger.info(f'Loaded {cog_file.name} ({load_time:.2f}s)')
                
            except Exception as e:
                error_msg = f"Failed to load {extension_name}: {e}"
                cogs_logger.error(error_msg)
                failed_loads.append((extension_name, str(e)))
                self._error_counts[f"load_{extension_name}"] += 1
        
        # Log summary
        cogs_logger.info(f"Loaded {loaded_count} cogs successfully")
        if failed_loads:
            cogs_logger.warning(f"Failed to load {len(failed_loads)} cogs:")
            for ext, error in failed_loads:
                cogs_logger.warning(f"  - {ext}: {error}")
                
    async def _start_background_tasks(self):
        """Start background monitoring and cleanup tasks"""
        
        # Performance monitoring task
        self._monitor_task = asyncio.create_task(self._performance_monitor())
        self._active_tasks.add(self._monitor_task)
        
        # Cog cleanup task
        self._cog_cleanup_task = asyncio.create_task(self._cog_cleanup_worker())
        self._active_tasks.add(self._cog_cleanup_task)
        
        # Memory cleanup task
        cleanup_task = asyncio.create_task(self._memory_cleanup_worker())
        self._active_tasks.add(cleanup_task)
        
        # Network monitoring task for TLS error detection
        if NETWORK_MONITORING_AVAILABLE:
            self._network_monitor_task = asyncio.create_task(monitor_network_health())
            self._active_tasks.add(self._network_monitor_task)
            logger.info("Network monitoring started")
        
        cogs_logger.info("Background tasks started")
        
    async def _performance_monitor(self):
        """Monitor bot performance and log metrics"""
        await asyncio.sleep(5)  # Wait for bot to fully initialize
        
        while not self._shutdown_event.is_set():
            try:
                # Log performance metrics every 5 minutes
                uptime = time.time() - self._start_time
                
                # Command statistics
                total_commands = sum(self._command_stats.values())
                
                # Error statistics
                total_errors = sum(self._error_counts.values())
                
                # Memory usage (approximate)
                memory_info = self._get_memory_usage()
                
                # Guild statistics
                guild_count = len(self.guilds)
                member_count = sum(guild.member_count for guild in self.guilds)
                
                logger.info(f"Performance Report: "
                          f"Uptime: {uptime/3600:.1f}h, "
                          f"Guilds: {guild_count}, "
                          f"Members: {member_count}, "
                          f"Commands: {total_commands}, "
                          f"Errors: {total_errors}, "
                          f"Memory: {memory_info}")
                
                # Check for high error rates
                if total_errors > 10:
                    logger.warning(f"High error count detected: {total_errors} errors")
                
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")
                await asyncio.sleep(60)  # Wait longer on error
                
    async def _cog_cleanup_worker(self):
        """Clean up unused cogs and extensions"""
        await asyncio.sleep(30)  # Initial delay
        
        while not self._shutdown_event.is_set():
            try:
                # Check for cogs that haven't been used recently
                current_time = time.time()
                unused_extensions = []
                
                for ext, load_time in self._extension_load_times.items():
                    if current_time - load_time > 3600:  # 1 hour unused
                        unused_extensions.append(ext)
                
                # Log unused extensions (don't unload to avoid breaking functionality)
                if unused_extensions:
                    cogs_logger.debug(f"Found {len(unused_extensions)} potentially unused extensions")
                
                await asyncio.sleep(1800)  # 30 minutes
                
            except Exception as e:
                cogs_logger.error(f"Error in cog cleanup: {e}")
                await asyncio.sleep(300)
                
    async def _memory_cleanup_worker(self):
        """Background memory cleanup"""
        await asyncio.sleep(60)  # Initial delay
        
        while not self._shutdown_event.is_set():
            try:
                # Clear old rate limiting data
                current_time = time.time()
                self._recent_admin_calls = deque(
                    [call for call in self._recent_admin_calls 
                     if current_time - call < 300],  # Keep only last 5 minutes
                    maxlen=20
                )
                
                # Force garbage collection if available
                try:
                    import gc
                    gc.collect()
                except:
                    pass
                
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in memory cleanup: {e}")
                await asyncio.sleep(60)
                
    def _get_memory_usage(self) -> str:
        """Get approximate memory usage"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            return f"{memory_mb:.1f}MB"
        except:
            return "Unknown"
        
    async def _rate_limited_command(self, interaction: discord.Interaction) -> bool:
        """Check if command is rate limited"""
        current_time = time.time()
        
        # Clean old calls
        while self._recent_admin_calls and current_time - self._recent_admin_calls[0] > 60:
            self._recent_admin_calls.popleft()
        
        # Check rate limit
        if len(self._recent_admin_calls) >= 5:
            await interaction.response.send_message(
                "Rate limited. Please wait before using this command again.",
                ephemeral=True
            )
            return False
        
        self._recent_admin_calls.append(current_time)
        return True
    
    async def _safe_reload_extension(self, extension_name: str) -> tuple[bool, str]:
        """Safely reload an extension with error handling"""
        try:
            # Unload first
            if extension_name in self._loaded_extensions:
                await self.unload_extension(extension_name)
            
            # Load fresh
            start_time = time.time()
            await self.load_extension(extension_name)
            load_time = time.time() - start_time
            
            # Update tracking
            if extension_name in self._loaded_extensions:
                self._extension_load_times[extension_name] = load_time
            else:
                self._loaded_extensions.add(extension_name)
                self._extension_load_times[extension_name] = load_time
            
            return True, f"Successfully reloaded {extension_name} ({load_time:.2f}s)"
            
        except Exception as e:
            error_msg = f"Failed to reload {extension_name}: {str(e)}"
            self._error_counts[f"reload_{extension_name}"] += 1
            
    async def on_command_completion(self, ctx):
        """Track command usage for statistics"""
        self._command_stats[str(ctx.command)] += 1
        
    async def on_command_error(self, ctx: commands.Context, error):
        """Handle command errors with logging"""
        command_name = str(ctx.command) if ctx.command else "unknown"
        self._error_counts[command_name] += 1
        
        # Log error
        logger.error(f"Command error in {command_name}: {error}")
        
        # Send user-friendly error message
        try:
            await ctx.send(f"An error occurred while executing the command. Please try again later..", ephemeral=True)
        except:
            pass  # Ignore if user can't receive messages
        
    async def close(self):
        """Clean shutdown"""
        logger.info("Shutting down bot...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel background tasks
        for task in self._active_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete (with timeout)
        if self._active_tasks:
            await asyncio.wait_for(
                asyncio.gather(*self._active_tasks, return_exceptions=True),
                timeout=5.0
            )
        
        # Call parent close
        await super().close()

# Rate limiter class
class RateLimiter:
    """Rate limiter for commands"""
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = deque()
    
    async def acquire(self):
        now = time.time()
        # Remove old calls
        while self.calls and now - self.calls[0] > self.time_window:
            self.calls.popleft()
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.calls[0] + self.time_window - now
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                return await self.acquire()
        
        self.calls.append(now)
        
async def load_cogs():
    """Legacy function for compatibility - now handled by OptimizedClient"""
    logger.info("Legacy load_cogs called - using OptimizedClient instead")
        
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.presences = True
intents.guilds = True
intents.members = True
client = Client()

# Base client commands

@client.command(name = "rc", description = "Reload all commands (rate limited)", guild=discord.Object(id=1453320275864322171))
async def reload_commands(interaction):
    """Reload all cogs"""
    try:
        # Rate limiting
        if not await client._rate_limited_command(interaction):
            return
        
        reloaded_cogs = 0
        reload_results = []
        
        for cog_file in settings.COGS_DIR.glob("*.py"):
            if cog_file.name == "__init__.py":
                continue
            
            extension_name = f'cogs.{cog_file.name[:-3]}'
            
            success, message = await client._safe_reload_extension(extension_name)
            
            if success:
                reloaded_cogs += 1
                cogs_logger.info(f'Reloaded {cog_file.name}')
                reload_results.append(f"✅ {cog_file.name}")
            else:
                reload_results.append(f"❌ {cog_file.name}")
        
        # Send summary
        result_text = f"**Reload Summary:**\n"
        result_text += f"Successfully reloaded: {reloaded_cogs} cogs\n\n"
        result_text += "\n".join(reload_results[:10])  # Limit output
        
        if len(reload_results) > 10:
            result_text += f"\n... and {len(reload_results) - 10} more"
        
        await interaction.send(
            f"Successfully reloaded {len(reload_results)} cogs!",
        )
        
        await interaction.send(
            content=result_text
        )
        
        await asyncio.sleep(3)
        
    except Exception as e:
        error_msg = f"Error reloading cogs: {str(e)}"
        cogs_logger.error(error_msg)
        cogs_logger.error(traceback.format_exc())
        
        await interaction.send(
            f"Error: {str(e)}"
        )
        
@client.command(name = "sc", description = "Sync all commands", guild=discord.Object(id=1453320275864322171))
async def sync_commands(interaction):
    """Sync all commands"""
    try:        
        # Rate limiting
        if not await client._rate_limited_command(interaction):
            return
        
        tree_logger.info("Syncing commands...")
        start_time = time.time()
        
        # Sync commands
        synced = await client.tree.sync()
        sync_time = time.time() - start_time
        
        tree_logger.info(f"Synced {len(synced)} commands to global ({sync_time:.2f}s)")
        
        await interaction.send(
            f'Synced {len(synced)} commands. ({sync_time:.2f}s)'
        )
        
        await asyncio.sleep(5)
        
    except Exception as e:
        error_msg = f"Error syncing commands: {str(e)}"
        tree_logger.error(error_msg)
        
        await interaction.send(
            f"Error: {str(e)}"
        )
        
@client.tree.command(name="bot_stats", description="Show bot performance statistics")
async def bot_stats(interaction: discord.Interaction):
    """Show bot performance statistics"""
    try:
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True
            )
            return
        
        uptime = time.time() - client._start_time
        total_commands = sum(client._command_stats.values())
        total_errors = sum(client._error_counts.values())
        
        # Memory usage
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
        except:
            memory_mb = 0
            cpu_percent = 0
        
        # Guild statistics
        guild_count = len(client.guilds)
        total_members = sum(guild.member_count for guild in client.guilds)
        
        stats = f"**Bot Statistics**\n"
        stats += f"⏱️ Uptime: {uptime/3600:.1f} hours\n"
        stats += f"🏢 Guilds: {guild_count}\n"
        stats += f"👥 Total Members: {total_members}\n"
        stats += f"💾 Memory: {memory_mb:.1f}MB\n"
        stats += f"⚡ CPU: {cpu_percent:.1f}%\n"
        stats += f"📊 Commands: {total_commands}\n"
        stats += f"❌ Errors: {total_errors}\n"
        stats += f"🔌 Loaded Extensions: {len(client._loaded_extensions)}"
        
        # Add network health if monitoring is available
        if NETWORK_MONITORING_AVAILABLE:
            try:
                # Get network health (run in thread to avoid blocking)
                import concurrent.futures
                def get_network_health():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        health = loop.run_until_complete(check_network_connectivity())
                        return health
                    finally:
                        loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(get_network_health)
                    health = future.result(timeout=5)
                
                if health.get('overall_connectivity', False):
                    stats += f"\n🌐 Network: ✅ Healthy"
                else:
                    stats += f"\n🌐 Network: ❌ Issues Detected"
                    
                # Show service-specific status
                service_status = health.get('service_health', {})
                if service_status:
                    healthy_services = sum(1 for status in service_status.values() if status)
                    total_services = len(service_status)
                    stats += f" ({healthy_services}/{total_services} services)"
                    
            except Exception as e:
                stats += f"\n🌐 Network: ⚠️ Monitoring Error"
        
        await interaction.response.send_message(stats, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"Error getting stats: {str(e)}", ephemeral=True)
    
@client.tree.command(name="network_status", description="Check network connectivity and service health")
async def network_status(interaction: discord.Interaction):
    """Check network connectivity and service health"""
    try:
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True
            )
            return
        
        if not NETWORK_MONITORING_AVAILABLE:
            await interaction.response.send_message(
                "Network monitoring is not available. TLS error fixes may not be fully implemented.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Get network health
            import concurrent.futures
            def get_network_health():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    health = loop.run_until_complete(check_network_connectivity())
                    return health
                finally:
                    loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(get_network_health)
                health = future.result(timeout=10)
            
            # Format response
            if health.get('overall_connectivity', False):
                status_msg = "✅ **Network Connectivity: HEALTHY**"
            else:
                status_msg = "❌ **Network Connectivity: ISSUES DETECTED**"
            
            # Service status
            service_status = health.get('service_health', {})
            if service_status:
                status_msg += "\n\n**Service Status:**"
                for service, is_healthy in service_status.items():
                    icon = "✅" if is_healthy else "❌"
                    status_msg += f"\n{icon} {service.title()}"
            
            # Basic connectivity
            basic_ok = health.get('basic_connectivity', False)
            status_msg += f"\n\n**Basic Connectivity:** {'✅' if basic_ok else '❌'}"
            
            # Error details if any
            if 'error' in health:
                status_msg += f"\n\n**Error:** {health['error']}"
            
            await interaction.edit_original_response(content=status_msg)
            
        except concurrent.futures.TimeoutError:
            await interaction.edit_original_response(content="⚠️ **Network check timed out**")
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ **Error checking network:** {str(e)}")
        
    except Exception as e:
        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
    
@client.event
async def on_ready():
    """Handle bot ready event with optimized status"""
    try:
        logger.info(f'Bot ready: {client.user} (ID: {client.user.id})')
        logger.info(f'Connected to {len(client.guilds)} guilds')
        
        # Set status
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name=f"VelloImpact bot is ready in {len(client.guilds)} servers!"
        )
        await client.change_presence(
            activity=activity,
            status=discord.Status.online
        )
        
    except Exception as e:
        logger.error(f"Error in on_ready: {e}")

# Initialize Firebase
try:
    fb.initialize_app()
    logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")

if __name__ == "__main__":
    try:
        logger.info("Starting VelloImpact Discord Bot...")
        client.run(settings.DISCORD_API_SECRET, root_logger=True, reconnect=True)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("Bot process ended")