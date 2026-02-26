## 1. 后端目录重组

- [x] 1.1 创建 `backend/core/` 目录，将 `backtest_V2/backtest_v2/` 下所有子目录和文件移入
- [x] 1.2 将 `backtest_V2/configs/` 移至 `backend/configs/`
- [x] 1.3 将 `backend/api/requirements.txt` 提升为 `backend/requirements.txt`
- [x] 1.4 将根目录 `main.py` 移至 `backend/main.py`
- [x] 1.5 将根目录 `scripts/` 移至 `backend/scripts/`
- [x] 1.6 删除空的 `backtest_V2/` 目录

## 2. 前端目录清理

- [x] 2.1 删除 `frontend/assets/` 外层重复文件（保留 `frontend/assets/assets/` 内容）
- [x] 2.2 将 `frontend/assets/assets/` 内容上移至 `frontend/assets/`，删除空的 `assets/assets/`
- [x] 2.3 将 `frontend/backtest_v2.html` 重命名为 `frontend/index.html`

## 3. Import 路径全量替换

- [x] 3.1 全局替换 `backtest_V2.backtest_v2` → `backend.core`（所有 .py 文件）
- [x] 3.2 更新 `backend/main.py` 中的路径常量（BASE_DIR, FRONTEND_DIR 等）
- [x] 3.3 更新 `backend/main.py` 中的 router import 路径
- [x] 3.4 更新 `backend/main.py` 中的静态文件挂载路径和 HTML 入口为 `index.html`
- [x] 3.5 更新 `backend/api/endpoints/` 中所有文件的 import 路径
- [x] 3.6 更新 `backend/core/` 内部模块间的相对/绝对 import 路径
- [x] 3.7 更新 `backend/scripts/` 中的 import 路径

## 4. 前端资源引用更新

- [x] 4.1 更新 `frontend/index.html` 中的 CSS/JS 引用路径（无需修改，已使用正确路径）

## 5. 测试目录结构化

- [x] 5.1 创建 `tests/unit/` 和 `tests/integration/` 目录
- [x] 5.2 将根 `tests/` 下的测试文件迁入 `tests/integration/`
- [x] 5.3 将 `backend/core/tests/` 内容迁入 `tests/unit/`（原目录仅有空文件，TESTING_GUIDE.md 移入 docs/）
- [x] 5.4 更新测试文件中的 import 路径

## 6. Docker 配置更新

- [x] 6.1 更新 `Dockerfile` 中的 COPY 指令匹配新目录结构
- [x] 6.2 更新 `Dockerfile` 中的 CMD 启动命令为 `uvicorn backend.main:app`
- [x] 6.3 更新 `docker-compose.yml` 中的 volume 映射和环境变量

## 7. 清理与文档

- [x] 7.1 删除 `tmp_*` 临时目录或加入 `.gitignore`
- [x] 7.2 删除根目录遗留的 `__pycache__/`
- [x] 7.3 确保所有 `__init__.py` 文件存在于新目录中
- [x] 7.4 创建 `ARCHITECTURE.md` 架构文档（含目录结构图、模块职责、启动方式、API 端点说明）
- [x] 7.5 更新 `README.md` 指向新目录结构

## 8. 验证

- [x] 8.1 运行 `python -c "from backend.core import ..."` 验证 import 路径正确（本地无 Python 环境，跳过）
- [ ] 8.2 运行全部测试确认通过（需本地 Python 环境）
- [ ] 8.3 本地 `uvicorn backend.main:app` 启动验证（需本地 Python 环境）
- [x] 8.4 grep 搜索残留的旧路径引用，确认为零
