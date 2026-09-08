from typing import Optional

from config import Config
from application.orchestrators import OrderProcessingOrchestrator


class ApplicationContainer:
    def __init__(
        self,
        config: Optional[Config] = None,
        orchestrator: Optional[OrderProcessingOrchestrator] = None,
    ):
        self.config = config or Config()
        self._orchestrator = orchestrator

    @property
    def orchestrator(self) -> OrderProcessingOrchestrator:
        if self._orchestrator is None:
            self._orchestrator = OrderProcessingOrchestrator(config=self.config)
        return self._orchestrator
