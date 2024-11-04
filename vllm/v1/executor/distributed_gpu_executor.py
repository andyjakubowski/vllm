import asyncio
from abc import abstractmethod
from typing import Any, Awaitable, Dict, List, Optional, Set, Tuple, Union

from vllm.v1.executor.gpu_executor import GPUExecutor
from vllm.logger import init_logger
from vllm.v1.outputs import ModelRunnerOutput
from vllm.v1.core.scheduler import SchedulerOutput

logger = init_logger(__name__)


class DistributedGPUExecutor(GPUExecutor):
    """Abstract superclass of multi-GPU executor implementations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def determine_num_available_blocks(self) -> Tuple[int, int]:
        """Determine the number of available KV blocks.

        This invokes `determine_num_available_blocks` on each worker and takes
        the min of the results, guaranteeing that the selected cache sizes are
        compatible with all workers.

        Returns:
            - tuple[num_gpu_blocks, num_cpu_blocks]
        """
        # Get the maximum number of blocks that can be allocated on GPU and CPU.
        num_blocks = self._run_workers("determine_num_available_blocks", )

        # Since we use a shared centralized controller, we take the minimum
        # number of blocks across all workers to make sure all the memory
        # operators can be applied to all workers.
        num_gpu_blocks = min(b[0] for b in num_blocks)
        return num_gpu_blocks, 0

    def initialize_cache(self, num_gpu_blocks: int) -> None:
        """Initialize the KV cache in all workers.
        """
        # NOTE: This is logged in the executor because there can be >1 worker
        # with other executors. We could log in the engine level, but work
        # remains to abstract away the device for non-GPU configurations.
        logger.info("# GPU blocks: %d", num_gpu_blocks)
        self._run_workers("initialize_cache", num_gpu_blocks)
        self._run_workers("compile_or_warm_up_model")

    @abstractmethod
    def execute_model(
        self,
        scheduler_output: SchedulerOutput,
    ) -> ModelRunnerOutput:
        raise NotImplementedError

    def save_sharded_state(
        self,
        path: str,
        pattern: Optional[str] = None,
        max_size: Optional[int] = None,
    ) -> None:
        self._run_workers("save_sharded_state",
                          path=path,
                          pattern=pattern,
                          max_size=max_size)

    @abstractmethod
    def _run_workers(
        self,
        method: str,
        *args,
        async_run_tensor_parallel_workers_only: bool = False,
        max_concurrent_workers: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """Runs the given method on all workers.

        Args:
            async_run_tensor_parallel_workers_only: If True the method will be
                run only in the remote TP workers, not the driver worker.
                It will also be run asynchronously and return a list of futures
                rather than blocking on the results.
        """
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> None:
        # SANG-TODO
        raise NotImplementedError

