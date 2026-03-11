# Dify 接入配置草案（细化版）

> 目的：提供可直接填入 Dify Workflow 的 HTTP 节点模板、字段映射与示例 Transform。

## 0. 全局输入字段（Start 表单）

- topic: 论文主题（必填）
- scope: 研究范围（可选）
- language: 输出语言（默认 zh）
- year_from: 起始年份（可选）
- year_to: 截止年份（可选）
- k: 返回论文数量（默认 10）

## 1. HTTP 节点：Semantic Scholar

**Method**: GET

**URL**:
```
https://api.semanticscholar.org/graph/v1/paper/search
```

**Query Params**:
- `query`: `${topic} ${scope}`
- `limit`: `${k}`
- `fields`: `title,authors,year,abstract,doi,url`

**Headers**:
- `x-api-key`: `${SEMANTIC_SCHOLAR_API_KEY}`

**Response JSON 示例（节选）**:
```json
{
  "data": [
    {
      "title": "...",
      "authors": [{"name": "A"}, {"name": "B"}],
      "year": 2023,
      "abstract": "...",
      "doi": "10.xxxx/xxxx",
      "url": "https://..."
    }
  ]
}
```

**字段映射（JSONPath 示例）**:
- `ss_items`: `$.data[*]`
- `ss_title`: `$.data[*].title`
- `ss_authors`: `$.data[*].authors[*].name`
- `ss_year`: `$.data[*].year`
- `ss_abstract`: `$.data[*].abstract`
- `ss_doi`: `$.data[*].doi`
- `ss_url`: `$.data[*].url`

## 2. HTTP 节点：arXiv（可选）

**Method**: GET

**URL**:
```
http://export.arxiv.org/api/query
```

**Query Params**:
- `search_query`: `all:${topic}`
- `start`: `0`
- `max_results`: `${k}`

**说明**:
- arXiv 返回 Atom XML。
- 若 Dify 没有 XML 解析节点，建议先跳过该源，后续用自研后端补齐。

## 3. Transform 节点：Normalize / Merge / Dedup

> 若 Dify 支持 “代码节点/脚本节点”，用 JS 做结构化与去重；否则用内置 Transform 拼接字段。

**目标输出结构**:
```json
[
  {
    "title": "...",
    "authors": ["A", "B"],
    "year": 2023,
    "abstract": "...",
    "doi": "10.xxxx/xxxx",
    "url": "https://..."
  }
]
```

**示例 JS（去重优先 DOI，其次 title）**:
```js
const items = input.ss_items || [];
const seen = new Set();
const out = [];

for (const p of items) {
  const doi = (p.doi || "").toLowerCase().trim();
  const title = (p.title || "").toLowerCase().trim();
  const key = doi || title;
  if (!key || seen.has(key)) continue;
  seen.add(key);
  out.push({
    title: p.title || "",
    authors: (p.authors || []).map(a => a.name).filter(Boolean),
    year: p.year || null,
    abstract: p.abstract || "",
    doi: p.doi || "",
    url: p.url || ""
  });
}

return { papers: out };
```

## 4. HITL 选择节点

- 输入：`papers`
- 展示字段：`title` `authors` `year`
- 输出：`selected_papers`

## 5. LLM 节点：综述摘要

**System Prompt**：参考 `docs/mvp-workflow.md` 中“综述摘要节点”要求。

**User Input**:
```json
{
  "topic": "${topic}",
  "scope": "${scope}",
  "papers": ${selected_papers}
}
```

**Output**:
- `review_summary`

## 6. LLM 节点：草稿生成

**System Prompt**：`backend/prompts/writing/v0.1.0.md`

**User Input**:
```json
{
  "topic": "${topic}",
  "scope": "${scope}",
  "papers": ${selected_papers},
  "review_summary": "${review_summary}"
}
```

**Output**:
- `draft`
- `references`（若模型输出）

## 7. LLM 节点：简版 Review

**System Prompt**：`backend/prompts/review/v0.1.0.md`

**User Input**:
```json
{
  "draft": "${draft}",
  "references": ${references}
}
```

**Output**:
- `review_report`

## 8. 输出聚合

- 输出：`review_summary` + `draft` + `review_report` + `references`
- 明确提示用户对引用与断言进行复核，并标记 `[NEEDS_EVIDENCE]`

## 9. 错误处理建议

- Semantic Scholar 返回空：提示用户调整关键词或范围
- LLM 输出过长：限制长度或分段输出（先引言+相关工作）
- References 缺失：提示用户手动补充或回到检索节点
