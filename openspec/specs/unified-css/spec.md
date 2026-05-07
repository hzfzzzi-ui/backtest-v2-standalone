# unified-css 规范

## 目标

前端样式统一收敛到单一 `workbench.css`，并保持当前正式桌面主链所需的 class 与 CSS 变量稳定可用。

## 要求

### 要求 1：单一 CSS 文件替代历史双文件体系

系统只允许使用 `frontend/assets/css/workbench.css` 作为桌面工作台主样式文件。

#### 场景：桌面页面加载样式
- **WHEN** `frontend/index.html` 在浏览器中打开
- **THEN** 页面只引用 `assets/css/workbench.css`
- **THEN** 不再引用历史样式文件

### 要求 2：统一 token 命名空间

所有 CSS 自定义属性必须统一使用 `--wb-*` 前缀。

#### 场景：检查 `workbench.css`
- **WHEN** 检查 `:root` 中的自定义属性
- **THEN** 当前主样式只定义 `--wb-*` 命名空间

### 要求 3：当前正式主链使用到的 class 必须持续有样式

当前正式主链中由 `index.html`、`desktop-shell/*` 与 `results-workbench` 使用到的 class 名必须继续被 `workbench.css` 覆盖。

#### 场景：检查主链 class
- **WHEN** 检查 `index.html` 与当前正式桌面模块使用到的 class
- **THEN** 每个 class 都应有对应样式规则

### 要求 4：动态 class 与 CSS 变量必须稳定

所有由当前正式桌面模块动态使用的 class 和 CSS 变量都必须继续可解析。

#### 场景：动态渲染状态 class
- **WHEN** 页面动态应用 `active`、`wb-ok`、`wb-danger`、`up`、`down` 等 class
- **THEN** 对应样式必须存在

#### 场景：运行时读取 CSS 变量
- **WHEN** 当前正式桌面模块通过 `var(--wb-*)` 或 `getComputedStyle` 读取变量
- **THEN** `workbench.css` 中必须定义这些变量
