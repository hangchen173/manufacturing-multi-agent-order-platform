from typing import Optional
from threading import RLock

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
        self._initialization_lock = RLock()

    def initialize(self) -> None:
        with self._initialization_lock:
            if self._orchestrator is not None:
                return
            from application.agents import MatchingAgent
            from infrastructure.vector_store import FAISSManager
            from infrastructure.vector_store.catalog import load_material_catalog, validate_catalog_index

            self.config.require_model_api_key()
            documents = load_material_catalog(self.config.data.standard_materials_path)
            store = FAISSManager(self.config.data.faiss_index_path)
            if store.index.ntotal == 0 and not store.metadata:
                store.add_documents(documents)
            validate_catalog_index(documents, store.metadata, store.index)
            orchestrator = OrderProcessingOrchestrator(
                config=self.config,
                matching_agent=MatchingAgent(faiss_manager=store, config=self.config),
            )
            orchestrator.order_manager.fail_stale_processing_orders()
            self._orchestrator = orchestrator

    def readiness(self):
        from infrastructure.vector_store.catalog import load_material_catalog, validate_catalog_index

        self.initialize()
        orchestrator = self._orchestrator
        store = orchestrator.matching_agent.faiss_manager
        documents = load_material_catalog(self.config.data.standard_materials_path)
        validate_catalog_index(documents, store.metadata, store.index)
        orchestrator.order_manager.repository.load_index()
        orchestrator.order_manager.fail_stale_processing_orders()
        return {"materials": len(store.metadata), "database": "available"}

    @property
    def orchestrator(self) -> OrderProcessingOrchestrator:
        if self._orchestrator is None:
            self.initialize()
        return self._orchestrator
