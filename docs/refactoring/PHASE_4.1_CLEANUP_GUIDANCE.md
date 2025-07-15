# 重构计划：Phase 4.5 指导文档 - 历史冗余模块清理

**目标：** 在进入最终的全局标准化阶段之前，彻底移除项目中因架构演进而已被废弃的、冗余的服务和存储层代码。这将显著降低代码库的复杂性，使其更易于维护和理解。

---

## 1. 待清理的冗余模块

经过分析，以下模块的功能已被新的、在 Phase 3 中建立的 Celery 任务流所完全取代，应予以彻底删除。

| 目标文件/目录                               | 冗余原因                                                                                                                                                           |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/services/download_task_service.py`     | 下载任务的生命周期（创建、状态更新、结果记录）现在完全由 `src/tasks/download_tasks.py` 中的 Celery 任务直接管理。此服务层已被架空。                               |
| `src/services/fund_data_service.py`         | 解析后数据的保存职责，现在由原子任务 `save_report_chain` 承担。此服务层同样已被架空。                                                                                |
| `src/storage/` (整个目录)                   | 这是一个遗留的、基于对象存储（Minio）的方案。在当前架构中，文件下载和数据持久化由 `Downloader` 服务和 Celery 任务链处理，与此模块完全无关。 |

---

## 2. 清理执行步骤

### 任务 4.5.1: 移除 `DownloadTaskService`

1.  **分析依赖：** 搜索整个项目，查找任何对 `DownloadTaskService` 的导入和使用。最可能的位置是 `src/main.py` 的服务初始化部分。
2.  **移除引用：** 在 `src/main.py` 中，删除 `from src.services.download_task_service import DownloadTaskService` 以及任何创建其实例的代码（例如 `app.state.download_task_service = DownloadTaskService()`）。
3.  **删除文件：** 安全地删除 `src/services/download_task_service.py` 文件。
4.  **运行测试：** 执行 `poetry run pytest`，确保所有测试仍然通过。

### 任务 4.5.2: 移除 `FundDataService`

1.  **分析依赖：** 搜索整个项目，查找任何对 `FundDataService` 的导入和使用。
2.  **移除引用：** 在 `src/main.py` 或其他地方，删除对该服务的所有引用。
3.  **删除文件：** 安全地删除 `src/services/fund_data_service.py` 文件。
4.  **运行测试：** 再次执行 `poetry run pytest`，确保所有测试仍然通过。

### 任务 4.5.3: 移除 `storage` 模块

1.  **分析依赖：** 搜索整个项目，查找任何对 `storage` 目录中模块（如 `minio_client`）的导入。预期不会有任何有效的引用。
2.  **删除目录：** 安全地、完整地删除 `src/storage/` 目录。
3.  **运行测试：** 最后一次执行 `poetry run pytest`，确保测试套件依然 100% 通过。

---

## 3. 验收标准 (Acceptance Criteria)

1.  `src/services/download_task_service.py` 文件被彻底删除。
2.  `src/services/fund_data_service.py` 文件被彻底删除。
3.  `src/storage/` 目录被彻底删除。
4.  `src/main.py` 中不再包含对上述任何已删除模块的引用。
5.  在完成所有清理工作后，项目完整的 `pytest` 测试套件**必须 100% 通过**，以证明本次清理未对现有功能造成任何破坏。
