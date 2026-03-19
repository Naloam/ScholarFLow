from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from schemas.autoresearch import (
    AblationSpec,
    AcceptanceRule,
    BenchmarkSource,
    BaselineSpec,
    DatasetSpec,
    ExperimentSpec,
    MetricSpec,
    SweepConfig,
    TaskFamily,
)


TEXT_BENCHMARK = {
    "benchmark_name": "toy_cs_abstract_topic",
    "benchmark_description": (
        "A compact benchmark of short computer science abstracts labeled as retrieval, "
        "ml_systems, or program_analysis."
    ),
    "dataset": {
        "name": "Toy CS Abstract Topic",
        "description": (
            "Fifteen training abstracts and nine test abstracts covering retrieval, systems, "
            "and program analysis concepts."
        ),
        "train": [
            {
                "text": "Dense retrieval encoders learn passage representations from query pairs and hard negatives.",
                "label": "retrieval",
            },
            {
                "text": "BM25 ranking with lexical expansion improves first stage retrieval effectiveness.",
                "label": "retrieval",
            },
            {
                "text": "Pseudo relevance feedback improves document recall for ad hoc search.",
                "label": "retrieval",
            },
            {
                "text": "Cross encoder rerankers refine top k search results with token interaction.",
                "label": "retrieval",
            },
            {
                "text": "Approximate nearest neighbor indexing accelerates vector search in large corpora.",
                "label": "retrieval",
            },
            {
                "text": "Pipeline parallel training schedules micro batches across GPU stages.",
                "label": "ml_systems",
            },
            {
                "text": "KV cache quantization reduces memory footprint for large model serving.",
                "label": "ml_systems",
            },
            {
                "text": "Asynchronous checkpointing lowers tail latency in distributed training systems.",
                "label": "ml_systems",
            },
            {
                "text": "Scheduler aware data loading improves accelerator utilization in multi tenant clusters.",
                "label": "ml_systems",
            },
            {
                "text": "CUDA kernel fusion reduces memory bandwidth overhead in transformer inference.",
                "label": "ml_systems",
            },
            {
                "text": "Static taint analysis tracks untrusted data through program dependence graphs.",
                "label": "program_analysis",
            },
            {
                "text": "Abstract interpretation proves absence of integer overflow in low level code.",
                "label": "program_analysis",
            },
            {
                "text": "Symbolic execution generates path constraints for branch coverage improvement.",
                "label": "program_analysis",
            },
            {
                "text": "Control flow graph normalization simplifies compiler optimization passes.",
                "label": "program_analysis",
            },
            {
                "text": "Type state analysis detects protocol misuse in event driven software.",
                "label": "program_analysis",
            },
        ],
        "test": [
            {
                "text": "Query expansion improves ranking quality when the retriever misses exact lexical matches.",
                "label": "retrieval",
            },
            {
                "text": "Dual encoder retrieval can miss token level interactions without reranking.",
                "label": "retrieval",
            },
            {
                "text": "Vector search latency depends on the quality of the nearest neighbor index.",
                "label": "retrieval",
            },
            {
                "text": "Serving throughput improves when cache compression reduces GPU memory pressure.",
                "label": "ml_systems",
            },
            {
                "text": "Cluster schedulers stabilize training jobs by balancing pipeline stages.",
                "label": "ml_systems",
            },
            {
                "text": "Kernel level optimization shortens inference latency for batched requests.",
                "label": "ml_systems",
            },
            {
                "text": "Program analysis tools reason about control flow and taint propagation.",
                "label": "program_analysis",
            },
            {
                "text": "Compiler verification benefits from symbolic paths and abstract domains.",
                "label": "program_analysis",
            },
            {
                "text": "Static analyzers catch protocol violations before deployment.",
                "label": "program_analysis",
            },
        ],
        "keyword_map": {
            "retrieval": [
                "retrieval",
                "search",
                "ranking",
                "query",
                "document",
                "passage",
                "rerank",
                "vector",
                "bm25",
                "index",
            ],
            "ml_systems": [
                "gpu",
                "cache",
                "latency",
                "throughput",
                "scheduler",
                "cluster",
                "kernel",
                "memory",
                "training",
                "serving",
            ],
            "program_analysis": [
                "static",
                "symbolic",
                "control",
                "compiler",
                "taint",
                "abstract",
                "program",
                "flow",
                "type",
                "path",
            ],
        },
    },
}


TABULAR_BENCHMARK = {
    "benchmark_name": "toy_training_run_stability",
    "benchmark_description": (
        "A small tabular benchmark that predicts whether a model training configuration remains "
        "stable or diverges."
    ),
    "dataset": {
        "name": "Toy Training Run Stability",
        "description": (
            "Sixteen training runs and eight held out runs with numeric optimization and model "
            "configuration features."
        ),
        "feature_names": [
            "learning_rate",
            "batch_size",
            "dropout",
            "depth",
            "residual",
        ],
        "train": [
            {"features": [0.001, 64, 0.10, 8, 1], "label": "stable"},
            {"features": [0.002, 128, 0.20, 12, 1], "label": "stable"},
            {"features": [0.0008, 64, 0.15, 10, 1], "label": "stable"},
            {"features": [0.004, 32, 0.25, 6, 1], "label": "stable"},
            {"features": [0.003, 64, 0.05, 8, 1], "label": "stable"},
            {"features": [0.005, 48, 0.10, 7, 1], "label": "stable"},
            {"features": [0.020, 16, 0.00, 18, 0], "label": "unstable"},
            {"features": [0.030, 16, 0.05, 20, 0], "label": "unstable"},
            {"features": [0.015, 8, 0.00, 16, 0], "label": "unstable"},
            {"features": [0.025, 32, 0.40, 18, 0], "label": "unstable"},
            {"features": [0.018, 16, 0.35, 14, 0], "label": "unstable"},
            {"features": [0.012, 8, 0.30, 15, 0], "label": "unstable"},
            {"features": [0.006, 32, 0.15, 9, 1], "label": "stable"},
            {"features": [0.007, 32, 0.20, 11, 1], "label": "stable"},
            {"features": [0.010, 24, 0.30, 13, 0], "label": "unstable"},
            {"features": [0.0025, 96, 0.10, 9, 1], "label": "stable"},
        ],
        "test": [
            {"features": [0.0015, 64, 0.10, 8, 1], "label": "stable"},
            {"features": [0.0045, 48, 0.20, 10, 1], "label": "stable"},
            {"features": [0.019, 16, 0.05, 17, 0], "label": "unstable"},
            {"features": [0.022, 24, 0.35, 19, 0], "label": "unstable"},
            {"features": [0.008, 32, 0.25, 12, 1], "label": "stable"},
            {"features": [0.014, 16, 0.30, 14, 0], "label": "unstable"},
            {"features": [0.0035, 128, 0.05, 7, 1], "label": "stable"},
            {"features": [0.011, 24, 0.25, 13, 0], "label": "unstable"},
        ],
    },
}


IR_BENCHMARK = {
    "benchmark_name": "toy_cs_reranking",
    "benchmark_description": (
        "A compact reranking benchmark with computer science queries, candidate passages, and a "
        "single relevant document for each query."
    ),
    "dataset": {
        "name": "Toy CS Reranking",
        "description": (
            "Three training queries and three held out queries spanning retrieval, systems, and "
            "program analysis topics."
        ),
        "train": [
            {
                "query": "dense retrieval with hard negatives",
                "candidates": [
                    {"id": "d1", "text": "Dense retrieval encoders use hard negatives to improve passage ranking."},
                    {"id": "d2", "text": "Pipeline parallelism schedules micro batches across GPUs."},
                    {"id": "d3", "text": "Static taint analysis reasons about untrusted data."},
                ],
                "relevant_ids": ["d1"],
            },
            {
                "query": "gpu serving memory cache compression",
                "candidates": [
                    {"id": "d4", "text": "KV cache quantization reduces serving memory footprint and latency."},
                    {"id": "d5", "text": "Approximate nearest neighbor indices accelerate vector search."},
                    {"id": "d6", "text": "Symbolic execution enumerates control-flow paths."},
                ],
                "relevant_ids": ["d4"],
            },
            {
                "query": "symbolic execution branch coverage",
                "candidates": [
                    {"id": "d7", "text": "Symbolic execution generates path constraints for branch coverage."},
                    {"id": "d8", "text": "Scheduler-aware input pipelines improve accelerator utilization."},
                    {"id": "d9", "text": "Query expansion improves lexical retrieval recall."},
                ],
                "relevant_ids": ["d7"],
            },
        ],
        "test": [
            {
                "query": "lexical and vector retrieval ranking",
                "candidates": [
                    {"id": "t1", "text": "Cross-encoder rerankers refine top-k search results with token interaction."},
                    {"id": "t2", "text": "Control-flow graph normalization simplifies compiler passes."},
                    {"id": "t3", "text": "GPU cache compression reduces serving overhead."},
                ],
                "relevant_ids": ["t1"],
            },
            {
                "query": "training throughput in multi-tenant gpu clusters",
                "candidates": [
                    {"id": "t4", "text": "Scheduler-aware data loading improves accelerator utilization in clusters."},
                    {"id": "t5", "text": "Abstract interpretation proves absence of overflow."},
                    {"id": "t6", "text": "Pseudo relevance feedback improves document recall."},
                ],
                "relevant_ids": ["t4"],
            },
            {
                "query": "program analysis for taint propagation",
                "candidates": [
                    {"id": "t7", "text": "Static taint analysis tracks untrusted data through dependence graphs."},
                    {"id": "t8", "text": "CUDA kernel fusion lowers transformer inference latency."},
                    {"id": "t9", "text": "Approximate nearest neighbor indexing accelerates search."},
                ],
                "relevant_ids": ["t7"],
            },
        ],
    },
}


@dataclass(frozen=True)
class ResolvedBenchmark:
    source: BenchmarkSource
    task_family: TaskFamily
    payload: dict[str, Any]
    benchmark_name: str
    benchmark_description: str


def infer_task_family(topic: str, task_family_hint: TaskFamily | None = None) -> TaskFamily:
    if task_family_hint:
        return task_family_hint
    normalized = topic.strip().lower()
    ir_hints = ["rerank", "retrieval benchmark", "ranking", "ir", "beir", "搜索排序", "信息检索"]
    if any(token in normalized for token in ir_hints):
        return "ir_reranking"
    tabular_hints = ["tabular", "table", "表格", "配置", "超参数", "stability", "feature"]
    if any(token in normalized for token in tabular_hints):
        return "tabular_classification"
    return "text_classification"


def benchmark_payload_for(task_family: TaskFamily) -> dict[str, Any]:
    if task_family == "ir_reranking":
        return IR_BENCHMARK
    if task_family == "tabular_classification":
        return TABULAR_BENCHMARK
    return TEXT_BENCHMARK


def default_search_strategies(task_family: TaskFamily) -> list[str]:
    if task_family == "ir_reranking":
        return [
            "overlap_baseline_search",
            "idf_reranker_search",
            "bigram_reranker_search",
        ]
    if task_family == "tabular_classification":
        return [
            "threshold_rule_search",
            "perceptron_unscaled_search",
            "perceptron_scaled_search",
        ]
    return [
        "keyword_rule_search",
        "naive_bayes_limited_vocab_search",
        "naive_bayes_search",
    ]


def default_seeds() -> list[int]:
    return [7, 13]


def default_sweeps(task_family: TaskFamily) -> list[SweepConfig]:
    if task_family == "ir_reranking":
        return [
            SweepConfig(
                label="default",
                params={"idf_smoothing": 1.0, "bigram_bonus": 0.5},
                description="Default rarity weighting with a modest bigram bonus.",
            ),
            SweepConfig(
                label="rarity_boosted",
                params={"idf_smoothing": 1.4, "bigram_bonus": 0.9},
                description="Increase IDF smoothing and emphasize bigram overlap.",
            ),
        ]
    if task_family == "tabular_classification":
        return [
            SweepConfig(
                label="default",
                params={
                    "perceptron_epochs": 15,
                    "perceptron_scaled_epochs": 20,
                    "perceptron_learning_rate": 1.0,
                },
                description="Baseline perceptron training budget.",
            ),
            SweepConfig(
                label="longer_training",
                params={
                    "perceptron_epochs": 24,
                    "perceptron_scaled_epochs": 32,
                    "perceptron_learning_rate": 0.8,
                },
                description="Longer training with a slightly smaller step size.",
            ),
        ]
    return [
        SweepConfig(
            label="default",
            params={"keyword_top_k": 8, "naive_bayes_order": 1, "limited_vocab_limit": 12},
            description="Unigram lexical baseline with compact limited vocabulary.",
        ),
        SweepConfig(
            label="higher_order_lexical",
            params={"keyword_top_k": 10, "naive_bayes_order": 2, "limited_vocab_limit": 16},
            description="Broader keyword coverage and bigram naive Bayes features.",
        ),
    ]


def default_acceptance_criteria(task_family: TaskFamily) -> list[AcceptanceRule]:
    baseline_name = "random_ranker" if task_family == "ir_reranking" else "majority"
    baseline_label = "random baseline" if task_family == "ir_reranking" else "majority baseline"
    return [
        AcceptanceRule(
            id="objective_primary_metric_beats_baseline",
            description=f"Objective system should outperform the {baseline_label} on mean primary metric.",
            kind="objective_metric_comparison",
            metric="primary_metric",
            target="objective_system",
            baseline_system=baseline_name,
            comparison="gt",
            required_statistics=["mean"],
        ),
        AcceptanceRule(
            id="selected_sweep_completes_all_requested_seeds",
            description="Selected sweep should execute successfully for every requested seed.",
            kind="seed_coverage",
        ),
        AcceptanceRule(
            id="primary_metric_reports_mean_std_and_ci",
            description=(
                "Aggregate reporting should include mean, standard deviation, and confidence interval "
                "for the primary metric."
            ),
            kind="aggregate_metric_reporting",
            metric="primary_metric",
            target="objective_system",
            required_statistics=["mean", "std", "confidence_interval"],
        ),
        AcceptanceRule(
            id="objective_vs_baseline_significance_reported",
            description="Selected configuration should record a significance comparison between the objective system and the baseline on the primary metric.",
            kind="significance_test_reporting",
            metric="primary_metric",
            target="objective_system",
            baseline_system=baseline_name,
            comparison_scope="system",
        ),
    ]


def builtin_benchmark(
    task_family: TaskFamily,
    source: BenchmarkSource | None = None,
) -> ResolvedBenchmark:
    payload = benchmark_payload_for(task_family)
    effective_source = source or BenchmarkSource(kind="builtin", task_family_hint=task_family)
    return ResolvedBenchmark(
        source=effective_source,
        task_family=task_family,
        payload=payload["dataset"],
        benchmark_name=payload["benchmark_name"],
        benchmark_description=payload["benchmark_description"],
    )


def build_experiment_spec(
    task_family: TaskFamily,
    benchmark: ResolvedBenchmark | None = None,
) -> ExperimentSpec:
    resolved = benchmark or builtin_benchmark(task_family)
    dataset_payload = resolved.payload
    if task_family == "ir_reranking":
        baselines = [
            BaselineSpec(name="random_ranker", description="Return the candidates in their original order."),
            BaselineSpec(name="overlap_ranker", description="Rank by lexical overlap between query and document."),
            BaselineSpec(name="idf_ranker", description="Weight rare query terms higher during lexical scoring."),
        ]
        metrics = [
            MetricSpec(name="mrr", goal="maximize", description="Mean reciprocal rank."),
            MetricSpec(name="recall_at_1", goal="maximize", description="Whether the relevant document is ranked first."),
        ]
        ablations = [
            AblationSpec(
                name="bigram_ranker",
                description="Add query-document bigram overlap as a higher-order lexical reranking signal.",
            )
        ]
        notes = [
            "Use only Python standard library utilities.",
            "Treat each example as a query with a short candidate list.",
            "Report MRR and Recall@1 on the held-out split.",
            "Support BEIR-style normalized JSON as an external adapter target.",
        ]
        hypothesis = (
            "A lexical reranker with rarity-aware term weighting should outperform the random order "
            "and simple overlap baselines on a small computer science retrieval benchmark."
        )
        input_fields = []
        label_space = []
        query_fields = ["query"]
        candidate_count = max((len(item.get("candidates", [])) for item in dataset_payload["test"]), default=0)
    elif task_family == "tabular_classification":
        baselines = [
            BaselineSpec(name="majority", description="Predict the most frequent stability label."),
            BaselineSpec(
                name="threshold_rule",
                description="A hand written rule over learning rate and residual connections.",
            ),
            BaselineSpec(
                name="perceptron_scaled",
                description="A lightweight linear classifier trained on standardized features.",
            ),
        ]
        metrics = [
            MetricSpec(name="accuracy", goal="maximize", description="Overall classification accuracy."),
            MetricSpec(name="macro_f1", goal="maximize", description="Macro averaged F1 across labels."),
        ]
        ablations = [
            AblationSpec(
                name="perceptron_unscaled",
                description="Remove feature standardization to measure the effect of normalization.",
            )
        ]
        notes = [
            "Use only Python standard library utilities.",
            "Report accuracy and macro F1 on the held out split.",
            "Show whether scaling improves the learned linear model.",
            "If the benchmark is remote, snapshot the pulled dataset before execution.",
        ]
        hypothesis = (
            "A simple linear model with feature scaling should outperform majority voting and "
            "the hand written threshold rule on training run stability prediction."
        )
        input_fields = dataset_payload["feature_names"]
        label_space = ["stable", "unstable"]
        query_fields = []
        candidate_count = None
    else:
        baselines = [
            BaselineSpec(name="majority", description="Predict the most frequent topic label."),
            BaselineSpec(
                name="keyword_rule",
                description="A keyword overlap baseline built from domain specific lexicons.",
            ),
            BaselineSpec(
                name="naive_bayes",
                description="A multinomial naive Bayes classifier trained on unigram counts.",
            ),
        ]
        metrics = [
            MetricSpec(name="accuracy", goal="maximize", description="Overall topic accuracy."),
            MetricSpec(name="macro_f1", goal="maximize", description="Macro averaged F1 over topics."),
        ]
        ablations = [
            AblationSpec(
                name="naive_bayes_limited_vocab",
                description="Restrict the vocabulary to the top frequent tokens to test feature coverage.",
            )
        ]
        notes = [
            "Use only Python standard library tokenization and counting.",
            "Treat each abstract as a short single document example.",
            "Compare probabilistic lexical modeling against rule based retrieval signals.",
            "If the benchmark is remote, snapshot the pulled dataset before execution.",
        ]
        hypothesis = (
            "A lightweight lexical probabilistic model should outperform majority and keyword "
            "baselines on short computer science abstract classification."
        )
        input_fields = ["text"]
        label_space = ["retrieval", "ml_systems", "program_analysis"]
        query_fields = []
        candidate_count = None

    return ExperimentSpec(
        task_family=task_family,
        benchmark_name=resolved.benchmark_name,
        benchmark_description=resolved.benchmark_description,
        dataset=DatasetSpec(
            name=dataset_payload.get("name") or resolved.benchmark_name,
            description=dataset_payload.get("description") or resolved.benchmark_description,
            train_size=len(dataset_payload["train"]),
            test_size=len(dataset_payload["test"]),
            input_fields=input_fields,
            label_space=label_space,
            query_fields=query_fields,
            candidate_count=candidate_count,
        ),
        baselines=baselines,
        metrics=metrics,
        hypothesis=hypothesis,
        ablations=ablations,
        implementation_notes=notes,
        search_strategies=default_search_strategies(task_family),
        seeds=default_seeds(),
        sweeps=default_sweeps(task_family),
        acceptance_criteria=default_acceptance_criteria(task_family),
    )
