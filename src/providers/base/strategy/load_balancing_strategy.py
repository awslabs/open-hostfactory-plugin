from src.domain.base.ports import LoggingPort
from src.domain.base.dependency_injection import injectable
"""Load Balancing Provider Strategy - Performance optimization and load distribution.

This module implements load balancing strategies for provider operations,
enabling optimal distribution of requests across multiple provider instances
for improved performance, scalability, and resource utilization.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
import secrets
import threading
from collections import deque

from src.providers.base.strategy.provider_strategy import (
    ProviderStrategy,
    ProviderOperation,
    ProviderResult,
    ProviderCapabilities,
    ProviderHealthStatus
)


@injectable
class LoadBalancingAlgorithm(str, Enum):
    """Load balancing algorithms."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    RANDOM = "random"
    WEIGHTED_RANDOM = "weighted_random"
    HASH_BASED = "hash_based"
    ADAPTIVE = "adaptive"


@injectable
class HealthCheckMode(str, Enum):
    """Health check modes for load balancing."""
    DISABLED = "disabled"
    PASSIVE = "passive"      # Monitor during regular operations
    ACTIVE = "active"        # Periodic health checks
    HYBRID = "hybrid"        # Both passive and active


@dataclass
class LoadBalancingConfig:
    """Configuration for load balancing strategy."""
    algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN
    health_check_mode: HealthCheckMode = HealthCheckMode.HYBRID
    health_check_interval_seconds: float = 30.0
    unhealthy_threshold: int = 3  # Consecutive failures before marking unhealthy
    recovery_threshold: int = 2   # Consecutive successes before marking healthy
    max_connections_per_strategy: int = 100
    response_time_window_size: int = 10  # Number of recent requests to track
    weight_adjustment_factor: float = 0.1  # For adaptive algorithms
    sticky_sessions: bool = False
    session_timeout_seconds: float = 300.0
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.health_check_interval_seconds <= 0:
            raise ValueError("health_check_interval_seconds must be positive")
        if self.unhealthy_threshold < 1:
            raise ValueError("unhealthy_threshold must be at least 1")
        if self.recovery_threshold < 1:
            raise ValueError("recovery_threshold must be at least 1")
        if self.max_connections_per_strategy < 1:
            raise ValueError("max_connections_per_strategy must be at least 1")
        if not 0 < self.weight_adjustment_factor <= 1:
            raise ValueError("weight_adjustment_factor must be between 0 and 1")


@dataclass
class StrategyStats:
    """Statistics for a single strategy in load balancing."""
    active_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    is_healthy: bool = True
    last_health_check: Optional[float] = None
    response_times: deque = None  # Recent response times
    average_response_time: float = 0.0
    weight: float = 1.0
    
    def __post_init__(self):
        """Initialize response times deque."""
        if self.response_times is None:
            self.response_times = deque(maxlen=10)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        return 100.0 - self.success_rate
    
    def record_request_start(self):
        """Record the start of a request."""
        self.active_connections += 1
        self.total_requests += 1
    
    def record_request_end(self, success: bool, response_time_ms: float):
        """Record the end of a request."""
        self.active_connections = max(0, self.active_connections - 1)
        
        if success:
            self.successful_requests += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
        
        # Update response time statistics
        self.response_times.append(response_time_ms)
        if self.response_times:
            self.average_response_time = sum(self.response_times) / len(self.response_times)


@injectable
class LoadBalancingProviderStrategy(ProviderStrategy):
    """
    Load balancing provider strategy for optimal request distribution.
    
    This class implements various load balancing algorithms to distribute
    requests across multiple provider strategies for improved performance,
    scalability, and fault tolerance.
    
    Features:
    - Multiple load balancing algorithms (round-robin, least connections, etc.)
    - Health monitoring and automatic failover
    - Adaptive weight adjustment based on performance
    - Connection limiting and throttling
    - Sticky sessions for stateful operations
    - Real-time performance metrics
    - Thread-safe concurrent operations
    """
    
    def __init__(self, logger: LoggingPort, strategies: List[ProviderStrategy],
                 weights: Optional[Dict[str, float]] = None,
                 config: LoadBalancingConfig = None):
        """
        Initialize load balancing provider strategy.
        
        Args:
            strategies: List of provider strategies to load balance
            weights: Optional weights for each strategy (by provider_type)
            config: Load balancing configuration
            logger: Optional logger instance
            
        Raises:
            ValueError: If strategies list is empty or weights are invalid
        """
        if not strategies:
            raise ValueError("At least one strategy is required for load balancing")
        
        # Create a dummy config for the parent class
        from src.infrastructure.interfaces.provider import BaseProviderConfig
        dummy_config = ProviderConfig(provider_type="load_balancer")
        super().__init__(dummy_config)
        
        self._strategies = {strategy.provider_type: strategy for strategy in strategies}
        self._config = config or LoadBalancingConfig()
        self._logger = logger
        
        # Initialize strategy statistics
        self._stats: Dict[str, StrategyStats] = {}
        for strategy_type in self._strategies:
            weight = weights.get(strategy_type, 1.0) if weights else 1.0
            self._stats[strategy_type] = StrategyStats(weight=weight)
        
        # Load balancing state
        self._round_robin_index = 0
        self._lock = threading.RLock()
        self._sessions: Dict[str, str] = {}  # session_id -> strategy_type
        self._session_timestamps: Dict[str, float] = {}
        
        # Health monitoring
        self._last_health_check = 0.0
        self._health_check_thread = None
        self._shutdown_event = threading.Event()
    
    @property
    def provider_type(self) -> str:
        """Get the provider type identifier."""
        strategy_types = sorted(self._strategies.keys())
        return f"load_balancer({'+'.join(strategy_types)})"
    
    @property
    def strategies(self) -> Dict[str, ProviderStrategy]:
        """Get the load balanced strategies."""
        return self._strategies.copy()
    
    @property
    def strategy_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all strategies."""
        with self._lock:
            return {
                strategy_type: {
                    "active_connections": stats.active_connections,
                    "total_requests": stats.total_requests,
                    "success_rate": stats.success_rate,
                    "failure_rate": stats.failure_rate,
                    "average_response_time": stats.average_response_time,
                    "is_healthy": stats.is_healthy,
                    "weight": stats.weight,
                    "consecutive_failures": stats.consecutive_failures,
                    "consecutive_successes": stats.consecutive_successes
                }
                for strategy_type, stats in self._stats.items()
            }
    
    @property
    def load_balancing_config(self) -> LoadBalancingConfig:
        """Get the load balancing configuration."""
        return self._config
    
    def add_strategy(self, strategy: ProviderStrategy, weight: float = 1.0) -> None:
        """
        Add a new strategy to the load balancer.
        
        Args:
            strategy: Provider strategy to add
            weight: Weight for load balancing
        """
        strategy_type = strategy.provider_type
        
        with self._lock:
            if strategy_type in self._strategies:
                self._self._logger.warning(f"Strategy {strategy_type} already exists, replacing")
            
            self._strategies[strategy_type] = strategy
            self._stats[strategy_type] = StrategyStats(weight=weight)
            
            self._self._logger.info(f"Added strategy {strategy_type} with weight {weight}")
    
    def remove_strategy(self, strategy_type: str) -> bool:
        """
        Remove a strategy from the load balancer.
        
        Args:
            strategy_type: Type of strategy to remove
            
        Returns:
            True if strategy was removed, False if not found
        """
        with self._lock:
            if strategy_type not in self._strategies:
                return False
            
            strategy = self._strategies[strategy_type]
            
            # Clean up strategy
            try:
                strategy.cleanup()
            except Exception as e:
                self._self._logger.warning(f"Error cleaning up strategy {strategy_type}: {e}")
            
            # Remove from load balancer
            del self._strategies[strategy_type]
            del self._stats[strategy_type]
            
            # Clean up sessions pointing to this strategy
            sessions_to_remove = [sid for sid, stype in self._sessions.items() if stype == strategy_type]
            for session_id in sessions_to_remove:
                del self._sessions[session_id]
                del self._session_timestamps[session_id]
            
            self._self._logger.info(f"Removed strategy {strategy_type}")
            return True
    
    def set_strategy_weight(self, strategy_type: str, weight: float) -> bool:
        """
        Set the weight for a specific strategy.
        
        Args:
            strategy_type: Type of strategy
            weight: Weight value (must be positive)
            
        Returns:
            True if weight was set, False if strategy not found
        """
        if weight <= 0:
            raise ValueError("Weight must be positive")
        
        with self._lock:
            if strategy_type not in self._stats:
                return False
            
            self._stats[strategy_type].weight = weight
            self._self._logger.debug(f"Set weight for {strategy_type}: {weight}")
            return True
    
    
    def initialize(self) -> bool:
        """
        Initialize all strategies in the load balancer.
        
        Returns:
            True if at least one strategy initializes successfully
        """
        if self._initialized:
            return True
        
        self._self._logger.info(f"Initializing load balancer with {len(self._strategies)} strategies")
        
        success_count = 0
        
        for strategy_type, strategy in self._strategies.items():
            try:
                if not strategy.is_initialized:
                    if strategy.initialize():
                        success_count += 1
                        self._self._logger.info(f"Initialized strategy: {strategy_type}")
                    else:
                        self._self._logger.error(f"Failed to initialize strategy: {strategy_type}")
                        with self._lock:
                            self._stats[strategy_type].is_healthy = False
                else:
                    success_count += 1
                    self._self._logger.debug(f"Strategy already initialized: {strategy_type}")
                    
            except Exception as e:
                self._self._logger.error(f"Error initializing strategy {strategy_type}: {e}")
                with self._lock:
                    self._stats[strategy_type].is_healthy = False
        
        self._initialized = success_count > 0
        
        if self._initialized:
            self._self._logger.info(f"Load balancer initialized: {success_count}/{len(self._strategies)} strategies ready")
            
            # Start health monitoring if configured
            if self._config.health_check_mode in [HealthCheckMode.ACTIVE, HealthCheckMode.HYBRID]:
                self._start_health_monitoring()
        else:
            self._self._logger.error("Load balancer initialization failed: no strategies available")
        
        return self._initialized
    
    
    def execute_operation(self, operation: ProviderOperation) -> ProviderResult:
        """
        Execute operation using load balancing algorithm.
        
        Args:
            operation: The operation to execute
            
        Returns:
            Result from the selected strategy
        """
        if not self._initialized:
            return ProviderResult.error_result(
                "Load balancer not initialized",
                "NOT_INITIALIZED"
            )
        
        start_time = time.time()
        
        try:
            # Clean up expired sessions
            self._cleanup_expired_sessions()
            
            # Select strategy based on algorithm
            selected_strategy_type = self._select_strategy(operation)
            
            if not selected_strategy_type:
                return ProviderResult.error_result(
                    "No healthy strategies available",
                    "NO_HEALTHY_STRATEGIES"
                )
            
            selected_strategy = self._strategies[selected_strategy_type]
            
            # Record request start
            with self._lock:
                self._stats[selected_strategy_type].record_request_start()
            
            # Execute operation
            try:
                result = selected_strategy.execute_operation(operation)
                execution_time_ms = (time.time() - start_time) * 1000
                
                # Record request end
                with self._lock:
                    self._stats[selected_strategy_type].record_request_end(result.success, execution_time_ms)
                    
                    # Update health status based on result
                    if self._config.health_check_mode in [HealthCheckMode.PASSIVE, HealthCheckMode.HYBRID]:
                        self._update_health_status(selected_strategy_type, result.success)
                
                # Add load balancing metadata
                result.metadata.update({
                    "load_balancer_algorithm": self._config.algorithm.value,
                    "selected_strategy": selected_strategy_type,
                    "execution_time_ms": execution_time_ms,
                    "strategy_stats": self._get_strategy_summary(selected_strategy_type)
                })
                
                return result
                
            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                
                # Record failure
                with self._lock:
                    self._stats[selected_strategy_type].record_request_end(False, execution_time_ms)
                    
                    if self._config.health_check_mode in [HealthCheckMode.PASSIVE, HealthCheckMode.HYBRID]:
                        self._update_health_status(selected_strategy_type, False)
                
                raise e
                
        except Exception as e:
            total_time_ms = (time.time() - start_time) * 1000
            self._self._logger.error(f"Load balancer operation {operation.operation_type} failed: {e}")
            return ProviderResult.error_result(
                f"Load balancer operation failed: {str(e)}",
                "LOAD_BALANCER_ERROR",
                {"total_execution_time_ms": total_time_ms}
            )
    
    def _select_strategy(self, operation: ProviderOperation) -> Optional[str]:
        """Select a strategy based on the configured algorithm."""
        # Get healthy strategies
        healthy_strategies = self._get_healthy_strategies()
        
        if not healthy_strategies:
            return None
        
        # Check for sticky session
        if self._config.sticky_sessions:
            session_id = operation.context.get('session_id') if operation.context else None
            if session_id and session_id in self._sessions:
                strategy_type = self._sessions[session_id]
                if strategy_type in healthy_strategies:
                    return strategy_type
        
        # Apply load balancing algorithm
        if self._config.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            return self._select_round_robin(healthy_strategies)
        elif self._config.algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            return self._select_weighted_round_robin(healthy_strategies)
        elif self._config.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            return self._select_least_connections(healthy_strategies)
        elif self._config.algorithm == LoadBalancingAlgorithm.LEAST_RESPONSE_TIME:
            return self._select_least_response_time(healthy_strategies)
        elif self._config.algorithm == LoadBalancingAlgorithm.RANDOM:
            return self._select_random(healthy_strategies)
        elif self._config.algorithm == LoadBalancingAlgorithm.WEIGHTED_RANDOM:
            return self._select_weighted_random(healthy_strategies)
        elif self._config.algorithm == LoadBalancingAlgorithm.HASH_BASED:
            return self._select_hash_based(healthy_strategies, operation)
        elif self._config.algorithm == LoadBalancingAlgorithm.ADAPTIVE:
            return self._select_adaptive(healthy_strategies)
        else:
            return self._select_round_robin(healthy_strategies)
    
    def _get_healthy_strategies(self) -> List[str]:
        """Get list of healthy strategy types."""
        with self._lock:
            return [
                strategy_type for strategy_type, stats in self._stats.items()
                if stats.is_healthy and stats.active_connections < self._config.max_connections_per_strategy
            ]
    
    def _select_round_robin(self, strategies: List[str]) -> str:
        """Select strategy using round-robin algorithm."""
        with self._lock:
            self._round_robin_index = (self._round_robin_index + 1) % len(strategies)
            return strategies[self._round_robin_index]
    
    def _select_weighted_round_robin(self, strategies: List[str]) -> str:
        """Select strategy using weighted round-robin algorithm."""
        # Simple weighted selection based on weights
        weights = []
        with self._lock:
            for strategy_type in strategies:
                weights.append(self._stats[strategy_type].weight)
        
        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            # Use secrets for cryptographically secure randomness
            return secrets.choice(strategies)
        
        # Use secrets for cryptographically secure randomness
        rand_val = secrets.SystemRandom().random() * total_weight
        cumulative = 0.0
        
        for i, weight in enumerate(weights):
            cumulative += weight
            if rand_val <= cumulative:
                return strategies[i]
        
        return strategies[-1]
    
    def _select_least_connections(self, strategies: List[str]) -> str:
        """Select strategy with least active connections."""
        with self._lock:
            return min(strategies, key=lambda s: self._stats[s].active_connections)
    
    def _select_least_response_time(self, strategies: List[str]) -> str:
        """Select strategy with lowest average response time."""
        with self._lock:
            return min(strategies, key=lambda s: self._stats[s].average_response_time)
    
    def _select_random(self, strategies: List[str]) -> str:
        """Select strategy randomly."""
        # Use secrets for cryptographically secure randomness
        return secrets.choice(strategies)
    
    def _select_weighted_random(self, strategies: List[str]) -> str:
        """Select strategy using weighted random selection."""
        return self._select_weighted_round_robin(strategies)  # Same implementation
    
    def _select_hash_based(self, strategies: List[str], operation: ProviderOperation) -> str:
        """Select strategy based on operation hash for consistency."""
        # Create hash from operation parameters
        hash_input = f"{operation.operation_type.value}_{str(sorted(operation.parameters.items()))}"
        hash_value = hash(hash_input)
        
        return strategies[hash_value % len(strategies)]
    
    def _select_adaptive(self, strategies: List[str]) -> str:
        """Select strategy using adaptive algorithm based on performance."""
        # Combine multiple factors: response time, success rate, connections
        best_strategy = None
        best_score = float('-inf')
        
        with self._lock:
            for strategy_type in strategies:
                stats = self._stats[strategy_type]
                
                # Calculate composite score
                success_factor = stats.success_rate / 100.0
                response_factor = 1.0 / (1.0 + stats.average_response_time / 1000.0)  # Normalize to seconds
                connection_factor = 1.0 / (1.0 + stats.active_connections)
                
                score = (success_factor * 0.4) + (response_factor * 0.4) + (connection_factor * 0.2)
                
                if score > best_score:
                    best_score = score
                    best_strategy = strategy_type
        
        return best_strategy or strategies[0]
    
    def _update_health_status(self, strategy_type: str, success: bool):
        """Update health status based on operation result."""
        stats = self._stats[strategy_type]
        
        if success:
            if stats.consecutive_successes >= self._config.recovery_threshold:
                if not stats.is_healthy:
                    stats.is_healthy = True
                    self._self._logger.info(f"Strategy {strategy_type} marked as healthy")
        else:
            if stats.consecutive_failures >= self._config.unhealthy_threshold:
                if stats.is_healthy:
                    stats.is_healthy = False
                    self._self._logger.warning(f"Strategy {strategy_type} marked as unhealthy")
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sticky sessions."""
        if not self._config.sticky_sessions:
            return
        
        current_time = time.time()
        expired_sessions = []
        
        with self._lock:
            for session_id, timestamp in self._session_timestamps.items():
                if current_time - timestamp > self._config.session_timeout_seconds:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._sessions[session_id]
                del self._session_timestamps[session_id]
    
    def _get_strategy_summary(self, strategy_type: str) -> Dict[str, Any]:
        """Get summary statistics for a strategy."""
        with self._lock:
            stats = self._stats[strategy_type]
            return {
                "active_connections": stats.active_connections,
                "success_rate": stats.success_rate,
                "average_response_time": stats.average_response_time,
                "is_healthy": stats.is_healthy
            }
    
    def _start_health_monitoring(self):
        """Start background health monitoring thread."""
        if self._health_check_thread and self._health_check_thread.is_alive():
            return
        
        def health_monitor():
            while not self._shutdown_event.is_set():
                try:
                    self._perform_health_checks()
                    self._shutdown_event.wait(self._config.health_check_interval_seconds)
                except Exception as e:
                    self._self._logger.error(f"Error in health monitoring: {e}")
        
        self._health_check_thread = threading.Thread(target=health_monitor, daemon=True)
        self._health_check_thread.start()
        self._self._logger.info("Started health monitoring thread")
    
    def _perform_health_checks(self):
        """Perform active health checks on all strategies."""
        for strategy_type, strategy in self._strategies.items():
            try:
                health = strategy.check_health()
                
                with self._lock:
                    stats = self._stats[strategy_type]
                    stats.last_health_check = time.time()
                    
                    # Update health status
                    if health.is_healthy != stats.is_healthy:
                        stats.is_healthy = health.is_healthy
                        status = "healthy" if health.is_healthy else "unhealthy"
                        self._self._logger.info(f"Strategy {strategy_type} health changed to {status}")
                        
            except Exception as e:
                self._self._logger.warning(f"Health check failed for {strategy_type}: {e}")
                with self._lock:
                    self._stats[strategy_type].is_healthy = False
    
    def get_capabilities(self) -> ProviderCapabilities:
        """
        Get combined capabilities from all load balanced strategies.
        
        Returns:
            Merged capabilities with load balancing information
        """
        all_operations = set()
        combined_features = {}
        combined_limitations = {}
        performance_metrics = {}
        
        for strategy_type, strategy in self._strategies.items():
            try:
                capabilities = strategy.get_capabilities()
                all_operations.update(capabilities.supported_operations)
                combined_features.update(capabilities.features)
                combined_limitations.update(capabilities.limitations)
                performance_metrics[strategy_type] = capabilities.performance_metrics
            except Exception as e:
                self._self._logger.warning(f"Error getting capabilities from {strategy_type}: {e}")
        
        # Add load balancing specific features
        combined_features.update({
            "load_balancing": True,
            "load_balancing_algorithm": self._config.algorithm.value,
            "health_monitoring": self._config.health_check_mode.value,
            "sticky_sessions": self._config.sticky_sessions,
            "adaptive_weights": self._config.algorithm == LoadBalancingAlgorithm.ADAPTIVE,
            "strategy_count": len(self._strategies),
            "max_connections_per_strategy": self._config.max_connections_per_strategy
        })
        
        return ProviderCapabilities(
            provider_type=self.provider_type,
            supported_operations=list(all_operations),
            features=combined_features,
            limitations=combined_limitations,
            performance_metrics=performance_metrics
        )
    
    def check_health(self) -> ProviderHealthStatus:
        """
        Check health of all load balanced strategies.
        
        Returns:
            Aggregated health status with load balancing metrics
        """
        start_time = time.time()
        healthy_count = 0
        total_count = len(self._strategies)
        health_details = {}
        
        with self._lock:
            for strategy_type, stats in self._stats.items():
                health_details[strategy_type] = {
                    "healthy": stats.is_healthy,
                    "active_connections": stats.active_connections,
                    "success_rate": stats.success_rate,
                    "average_response_time": stats.average_response_time,
                    "weight": stats.weight
                }
                if stats.is_healthy:
                    healthy_count += 1
        
        response_time_ms = (time.time() - start_time) * 1000
        healthy_count / total_count if total_count > 0 else 0.0
        
        # Consider load balancer healthy if at least one strategy is healthy
        is_healthy = healthy_count > 0
        
        if is_healthy:
            return ProviderHealthStatus.healthy(
                f"Load balancer healthy: {healthy_count}/{total_count} strategies operational",
                response_time_ms
            )
        else:
            return ProviderHealthStatus.unhealthy(
                f"Load balancer unhealthy: no strategies operational",
                health_details
            )
    
    def cleanup(self) -> None:
        """Clean up all strategies and resources."""
        try:
            # Stop health monitoring
            self._shutdown_event.set()
            if self._health_check_thread and self._health_check_thread.is_alive():
                self._health_check_thread.join(timeout=5.0)
            
            # Clean up all strategies
            for strategy_type, strategy in self._strategies.items():
                try:
                    strategy.cleanup()
                    self._self._logger.debug(f"Cleaned up strategy: {strategy_type}")
                except Exception as e:
                    self._self._logger.warning(f"Error cleaning up strategy {strategy_type}: {e}")
            
            # Clear state
            with self._lock:
                self._strategies.clear()
                self._stats.clear()
                self._sessions.clear()
                self._session_timestamps.clear()
            
            self._initialized = False
            
        except Exception as e:
            self._self._logger.warning(f"Error during load balancer cleanup: {e}")
    
    def __str__(self) -> str:
        """String representation for debugging."""
        strategy_types = list(self._strategies.keys())
        return f"LoadBalancingProviderStrategy(strategies={strategy_types}, algorithm={self._config.algorithm.value})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"LoadBalancingProviderStrategy("
            f"strategies={list(self._strategies.keys())}, "
            f"algorithm={self._config.algorithm.value}, "
            f"health_check={self._config.health_check_mode.value}, "
            f"initialized={self._initialized}"
            f")"
        )
