# User Guide

## 适用对象

本指南面向两类用户：

- 学生：创建项目、生成草稿、查看证据与审稿反馈、邀请导师
- 导师：只读进入学生项目、提交导师反馈、查看阶段进展

## 开始前

1. 打开 ScholarFlow 前端
2. 如果服务端启用了鉴权，先在左侧 `Session Panel` 登录
3. 选择角色：
   - `student`：可创建和编辑自己的项目
   - `tutor`：用于导师审阅模式

## 学生工作流

### 1. 创建项目

在 `Project Launcher` 中填写：

- `Project title`
- `Topic`
- `Template`

点击 `Create Project` 后，系统会创建项目并加载工作区。

### 2. 生成初稿

在中央编辑区点击 `Generate Draft`。系统会：

- 读取项目主题和模板
- 生成初稿
- 自动进入 evidence / review / export 后续链路

生成完成后，可在左侧 `File Manager` 看到版本化草稿。

### 3. 编辑与保存

中央 `Editor Surface` 支持：

- 富文本编辑
- 标记 `[NEEDS_EVIDENCE]`
- 导出 Markdown / TeX / DOCX

修改后点击 `Save Draft` 保存当前版本内容。

### 4. 查看证据与审稿结果

右侧面板提供：

- `Evidence Panel`：查看与当前段落相关的证据片段
- `Review Panel`：查看 7 维审稿评分与建议
- `Similarity screen`：查看本地重合度筛查状态

相似度检测当前会把草稿段落与：

- 项目内 evidence snippet
- 项目论文 abstract

进行重合比对。它是项目内重合度筛查，不是外部全网查重。

### 5. 邀请导师

在左侧 `Mentor Panel`：

1. 输入导师邮箱和显示名
2. 点击 `Invite Mentor`

导师登录后，会在 `Accessible projects` 里直接看到被授权项目。

## 导师工作流

### 1. 以 tutor 身份登录

导师需要在 `Session Panel` 中选择 `Tutor` 角色后登录。

### 2. 打开可访问项目

在 `Project Launcher` 的 `Accessible projects` 区块中：

- 带 `Mentor read-only` 标记的项目表示导师只读访问
- 点击 `Open` 可进入项目

导师不能：

- 生成新草稿
- 修改草稿内容
- 发起导出或学生侧编辑动作

### 3. 提交导师反馈

在 `Mentor Panel` 中填写：

- `Summary`
- `Strengths`
- `Concerns`
- `Next steps`

点击 `Submit Mentor Feedback` 后，学生即可在同一项目中看到反馈记录。

## 导出与交付

当前支持：

- Markdown
- LaTeX
- Word / DOCX

导出完成后，可在左侧 `File Manager` 下载最新导出文件。

## 常见问题

### 登录后看不到模板或项目

- 检查后端是否正常运行
- 检查 `AUTH_SECRET`、`API_TOKEN`、`AUTH_REQUIRED`
- 如果使用 Docker 部署，确认 `frontend` 和 `backend` 容器都健康

### 导师看不到学生项目

- 确认学生已在 `Mentor Panel` 中邀请对应邮箱
- 确认导师使用的是被邀请的邮箱登录
- 刷新页面后重试，项目列表会重新拉取授权项目

### 相似度筛查为什么没有命中

- 当前只检查项目内已有的论文摘要和 evidence snippet
- 如果项目还没导入论文或还没有 evidence，结果会显示 `Clear`
