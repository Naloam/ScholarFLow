from __future__ import annotations

from typing import Any

from schemas.autoresearch import (
    AblationSpec,
    BaselineSpec,
    DatasetSpec,
    ExperimentSpec,
    MetricSpec,
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


def infer_task_family(topic: str, task_family_hint: TaskFamily | None = None) -> TaskFamily:
    if task_family_hint:
        return task_family_hint
    normalized = topic.strip().lower()
    tabular_hints = ["tabular", "table", "表格", "配置", "超参数", "stability", "feature"]
    if any(token in normalized for token in tabular_hints):
        return "tabular_classification"
    return "text_classification"


def benchmark_payload_for(task_family: TaskFamily) -> dict[str, Any]:
    if task_family == "tabular_classification":
        return TABULAR_BENCHMARK
    return TEXT_BENCHMARK


def build_experiment_spec(task_family: TaskFamily) -> ExperimentSpec:
    payload = benchmark_payload_for(task_family)
    dataset_payload = payload["dataset"]
    if task_family == "tabular_classification":
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
        ]
        hypothesis = (
            "A simple linear model with feature scaling should outperform majority voting and "
            "the hand written threshold rule on training run stability prediction."
        )
        input_fields = dataset_payload["feature_names"]
        label_space = ["stable", "unstable"]
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
        ]
        hypothesis = (
            "A lightweight lexical probabilistic model should outperform majority and keyword "
            "baselines on short computer science abstract classification."
        )
        input_fields = ["text"]
        label_space = ["retrieval", "ml_systems", "program_analysis"]

    return ExperimentSpec(
        task_family=task_family,
        benchmark_name=payload["benchmark_name"],
        benchmark_description=payload["benchmark_description"],
        dataset=DatasetSpec(
            name=dataset_payload["name"],
            description=dataset_payload["description"],
            train_size=len(dataset_payload["train"]),
            test_size=len(dataset_payload["test"]),
            input_fields=input_fields,
            label_space=label_space,
        ),
        baselines=baselines,
        metrics=metrics,
        hypothesis=hypothesis,
        ablations=ablations,
        implementation_notes=notes,
    )
