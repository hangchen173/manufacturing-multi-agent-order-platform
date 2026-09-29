"""应用容器：装配 Supervisor + 全部 Agent + 黑板/任务/消息仓储。

设计文档 §3.2：容器负责把 DAG 调度器、10 个业务 Agent 与协作状态仓储装配成
一个可用的编排器。业务逻辑一律不在容器里。
"""
from __future__ import annotations

import logging
from threading import RLock
from typing import Optional

from config import Config


class ApplicationContainer:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._orchestrator = None
        self._initialization_lock = RLock()
        self.logger = logging.getLogger(self.__class__.__name__)

    def initialize(self) -> None:
        with self._initialization_lock:
            if self._orchestrator is not None:
                return

            from application.orchestrators import OrderProcessingOrchestrator
            from application.services import OrderManager
            from infrastructure.repositories import PostgresOrderRepository
            from infrastructure.vector_store import FAISSManager
            from infrastructure.vector_store.catalog import (
                load_material_catalog,
                validate_catalog_index,
            )

            self.config.require_model_api_key()
            documents = load_material_catalog(self.config.data.standard_materials_path)
            store = FAISSManager(self.config.data.faiss_index_path)
            if store.index.ntotal == 0 and not store.metadata:
                store.add_documents(documents)
            validate_catalog_index(documents, store.metadata, store.index)

            # 组合根只装配订单仓储；黑板/任务/消息由该适配器自行声明，保证四个仓储同源。
            order_manager = OrderManager(
                repository=PostgresOrderRepository(self.config.database.url),
                config=self.config,
            )
            orchestrator = OrderProcessingOrchestrator(
                order_manager=order_manager,
                config=self.config,
                faiss_manager=store,
            )
            orchestrator.order_manager.fail_stale_processing_orders()
            orchestrator.order_manager.recover_orphan_tasks()
            self._orchestrator = orchestrator

    def readiness(self):
        from infrastructure.vector_store.catalog import (
            load_material_catalog,
            validate_catalog_index,
        )

        self.initialize()
        orchestrator = self._orchestrator
        store = orchestrator.faiss_manager
        documents = load_material_catalog(self.config.data.standard_materials_path)
        validate_catalog_index(documents, store.metadata, store.index)
        orchestrator.order_manager.repository.load_index()
        orchestrator.order_manager.fail_stale_processing_orders()
        return {"materials": len(store.metadata), "database": "available"}

    @property
    def orchestrator(self):
        if self._orchestrator is None:
            self.initialize()
        return self._orchestrator
