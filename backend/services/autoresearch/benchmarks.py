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


def _text_benchmark(
    *,
    benchmark_name: str,
    benchmark_description: str,
    dataset_name: str,
    dataset_description: str,
    train: list[dict[str, str]],
    test: list[dict[str, str]],
    keyword_map: dict[str, list[str]],
    topic_keywords: list[str],
) -> dict[str, Any]:
    return {
        "benchmark_name": benchmark_name,
        "benchmark_description": benchmark_description,
        "topic_keywords": topic_keywords,
        "dataset": {
            "name": dataset_name,
            "description": dataset_description,
            "train": train,
            "test": test,
            "keyword_map": keyword_map,
            "label_space": list(keyword_map),
        },
    }


TEXT_BENCHMARK = _text_benchmark(
    benchmark_name="toy_cs_abstract_topic",
    benchmark_description=(
        "A compact benchmark of short computer science abstracts labeled as retrieval, "
        "ml_systems, or program_analysis."
    ),
    dataset_name="Toy CS Abstract Topic",
    dataset_description=(
        "Fifteen training abstracts and nine test abstracts covering retrieval, systems, "
        "and program analysis concepts."
    ),
    train=[
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
    test=[
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
    keyword_map={
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
    topic_keywords=[
        "retrieval",
        "search",
        "ranking",
        "gpu",
        "serving",
        "systems",
        "compiler",
        "program analysis",
        "static analysis",
    ],
)

TEXT_AGENT_BENCHMARK = _text_benchmark(
    benchmark_name="toy_agent_workflow_topic",
    benchmark_description=(
        "A compact benchmark of short agent-systems snippets labeled as planning, memory, or tool_use."
    ),
    dataset_name="Toy Agent Workflow Topic",
    dataset_description=(
        "Twelve training snippets and six test snippets covering agent planning, memory, and tool-use design."
    ),
    train=[
        {"text": "Task decomposition planners break user goals into executable subgoals for agents.", "label": "planning"},
        {"text": "Reflection loops let agent planners critique intermediate steps before execution.", "label": "planning"},
        {"text": "Hierarchical planning coordinates multi-step workflows across cooperating agents.", "label": "planning"},
        {"text": "Constraint-aware plan repair updates an agent action sequence after a failed step.", "label": "planning"},
        {"text": "Long-term memory stores past tasks and retrieves episodes for later agent decisions.", "label": "memory"},
        {"text": "Retrieval-augmented memory lets agents ground responses in prior observations.", "label": "memory"},
        {"text": "Episodic memory compression keeps important tool traces for future reuse.", "label": "memory"},
        {"text": "State tracking modules maintain working memory across multi-turn agent sessions.", "label": "memory"},
        {"text": "Tool selection policies decide when an agent should call search or code execution.", "label": "tool_use"},
        {"text": "Function calling schemas help agents invoke APIs with structured arguments.", "label": "tool_use"},
        {"text": "Execution monitors verify browser and shell outputs before the agent continues.", "label": "tool_use"},
        {"text": "Toolformer-style supervision teaches models to insert calculator and browser calls.", "label": "tool_use"},
    ],
    test=[
        {"text": "Multi-agent planners coordinate subtasks before assigning tools to workers.", "label": "planning"},
        {"text": "Search-tree planning helps an agent revise its strategy after tool failure.", "label": "planning"},
        {"text": "Shared memory lets an assistant recover prior observations across long tasks.", "label": "memory"},
        {"text": "Working-memory updates keep agent state consistent over multi-step conversations.", "label": "memory"},
        {"text": "API routing policies decide which external tool an agent should invoke next.", "label": "tool_use"},
        {"text": "Structured tool calls keep agent arguments valid for browser and code actions.", "label": "tool_use"},
    ],
    keyword_map={
        "planning": ["plan", "planning", "subgoal", "workflow", "hierarchical", "reflection", "repair", "coordination"],
        "memory": ["memory", "episodic", "working", "state", "retrieve", "observation", "context", "history"],
        "tool_use": ["tool", "function", "api", "browser", "shell", "execution", "call", "invoke"],
    },
    topic_keywords=[
        "agent",
        "agents",
        "multi-agent",
        "planner",
        "planning",
        "tool",
        "tool use",
        "memory",
        "llm",
        "workflow",
    ],
)

TEXT_ML_BENCHMARK = _text_benchmark(
    benchmark_name="toy_ml_nlp_robotics_topic",
    benchmark_description=(
        "A compact benchmark of short AI research snippets labeled as machine_learning, nlp, or robotics."
    ),
    dataset_name="Toy ML NLP Robotics Topic",
    dataset_description=(
        "Twelve training snippets and six test snippets covering machine learning, natural language processing, and robotics."
    ),
    train=[
        {"text": "Gradient boosting combines weak learners to improve supervised classification accuracy.", "label": "machine_learning"},
        {"text": "Contrastive representation learning aligns embeddings without explicit class labels.", "label": "machine_learning"},
        {"text": "Bayesian optimization tunes hyperparameters with sample-efficient surrogate models.", "label": "machine_learning"},
        {"text": "Metric learning shapes embedding space by pulling similar examples together.", "label": "machine_learning"},
        {"text": "Transformer language models use attention to predict the next token in context.", "label": "nlp"},
        {"text": "Subword tokenization improves open-vocabulary translation and summarization pipelines.", "label": "nlp"},
        {"text": "Instruction tuning aligns chat models with conversational language tasks.", "label": "nlp"},
        {"text": "Named entity recognition tags people, locations, and organizations in text.", "label": "nlp"},
        {"text": "Model predictive control stabilizes mobile robots under changing dynamics.", "label": "robotics"},
        {"text": "SLAM systems fuse lidar and camera signals to localize a robot while mapping.", "label": "robotics"},
        {"text": "Grasp planning chooses end-effector poses for manipulation tasks.", "label": "robotics"},
        {"text": "Reinforcement learning policies guide robot navigation in cluttered environments.", "label": "robotics"},
    ],
    test=[
        {"text": "Regularized linear models improve generalization when training data is limited.", "label": "machine_learning"},
        {"text": "Self-supervised pretraining learns useful embeddings before downstream fine-tuning.", "label": "machine_learning"},
        {"text": "Question answering models ground token predictions in retrieved passages.", "label": "nlp"},
        {"text": "Sequence labeling pipelines identify syntax and entities in documents.", "label": "nlp"},
        {"text": "Trajectory optimization generates smooth motions for robotic manipulators.", "label": "robotics"},
        {"text": "Robot localization uses sensor fusion and control loops during navigation.", "label": "robotics"},
    ],
    keyword_map={
        "machine_learning": ["learning", "embedding", "classification", "optimization", "representation", "model", "hyperparameter", "regularized"],
        "nlp": ["language", "token", "translation", "summarization", "question", "entity", "text", "sequence"],
        "robotics": ["robot", "slam", "navigation", "grasp", "trajectory", "sensor", "manipulation", "control"],
    },
    topic_keywords=[
        "machine learning",
        "ml",
        "nlp",
        "language model",
        "transformer",
        "chatbot",
        "robot",
        "robotics",
        "reinforcement learning",
    ],
)

TEXT_VISION_BENCHMARK = _text_benchmark(
    benchmark_name="toy_vision_graphics_hci_topic",
    benchmark_description=(
        "A compact benchmark of short visual-computing snippets labeled as computer_vision, graphics, or hci."
    ),
    dataset_name="Toy Vision Graphics HCI Topic",
    dataset_description=(
        "Twelve training snippets and six test snippets covering computer vision, graphics, and human-computer interaction."
    ),
    train=[
        {"text": "Image segmentation predicts a semantic label for every pixel in a scene.", "label": "computer_vision"},
        {"text": "Object detection pipelines localize cars and pedestrians in street images.", "label": "computer_vision"},
        {"text": "Visual tracking follows a target across video frames under occlusion.", "label": "computer_vision"},
        {"text": "Depth estimation recovers scene geometry from monocular camera views.", "label": "computer_vision"},
        {"text": "Physically based rendering simulates light transport for realistic images.", "label": "graphics"},
        {"text": "Mesh simplification reduces polygon count while preserving surface detail.", "label": "graphics"},
        {"text": "Shader pipelines control texture sampling and lighting in real-time graphics.", "label": "graphics"},
        {"text": "Differentiable rendering links 3D scene parameters to image-space losses.", "label": "graphics"},
        {"text": "Usability studies measure how quickly people complete tasks in an interface.", "label": "hci"},
        {"text": "Interaction design explores how menus and gestures affect user performance.", "label": "hci"},
        {"text": "Eye-tracking helps analyze attention patterns in user interfaces.", "label": "hci"},
        {"text": "Visualization systems help analysts explore multidimensional data interactively.", "label": "hci"},
    ],
    test=[
        {"text": "Video understanding models detect actions and objects across time.", "label": "computer_vision"},
        {"text": "Scene recognition uses image features to classify indoor and outdoor environments.", "label": "computer_vision"},
        {"text": "Ray tracing computes reflections and shadows for realistic 3D rendering.", "label": "graphics"},
        {"text": "Geometry processing repairs noisy meshes before animation or simulation.", "label": "graphics"},
        {"text": "Interface evaluation compares user task time across different menu layouts.", "label": "hci"},
        {"text": "Interactive dashboards support visual exploration and rapid analyst feedback.", "label": "hci"},
    ],
    keyword_map={
        "computer_vision": ["image", "video", "pixel", "detection", "segmentation", "tracking", "depth", "scene"],
        "graphics": ["rendering", "mesh", "shader", "ray", "geometry", "texture", "lighting", "3d"],
        "hci": ["user", "interface", "interaction", "usability", "visualization", "gesture", "dashboard", "attention"],
    },
    topic_keywords=[
        "vision",
        "image",
        "video",
        "graphics",
        "rendering",
        "3d",
        "mesh",
        "hci",
        "interface",
        "visualization",
    ],
)

TEXT_INFRA_BENCHMARK = _text_benchmark(
    benchmark_name="toy_security_network_database_topic",
    benchmark_description=(
        "A compact benchmark of infrastructure snippets labeled as security, networking, or databases."
    ),
    dataset_name="Toy Security Network Database Topic",
    dataset_description=(
        "Twelve training snippets and six test snippets covering computer security, networking, and database systems."
    ),
    train=[
        {"text": "Static malware detection flags suspicious binaries before execution.", "label": "security"},
        {"text": "Sandbox escape mitigation hardens browser processes against exploitation.", "label": "security"},
        {"text": "Differential privacy limits information leakage from released query results.", "label": "security"},
        {"text": "Vulnerability scanners identify injection flaws in web applications.", "label": "security"},
        {"text": "Congestion control adjusts packet sending rates to stabilize network throughput.", "label": "networking"},
        {"text": "Routing protocols choose paths across distributed network topologies.", "label": "networking"},
        {"text": "Transport protocols balance latency, loss recovery, and fairness.", "label": "networking"},
        {"text": "Datacenter fabrics optimize bandwidth for east-west traffic patterns.", "label": "networking"},
        {"text": "Query optimizers choose join orders to speed up relational execution plans.", "label": "databases"},
        {"text": "Transaction protocols preserve consistency during concurrent updates.", "label": "databases"},
        {"text": "LSM-tree storage engines trade write amplification against read latency.", "label": "databases"},
        {"text": "Vector indexes accelerate nearest-neighbor search in database systems.", "label": "databases"},
    ],
    test=[
        {"text": "Access-control policies restrict which principals can read private data.", "label": "security"},
        {"text": "Encrypted messaging protocols protect confidentiality and authenticity.", "label": "security"},
        {"text": "Queue management improves latency under bursty network traffic.", "label": "networking"},
        {"text": "Multipath routing spreads flows across redundant network links.", "label": "networking"},
        {"text": "SQL execution engines pipeline scans, filters, and aggregations.", "label": "databases"},
        {"text": "Index maintenance keeps database lookup latency low after inserts.", "label": "databases"},
    ],
    keyword_map={
        "security": ["security", "privacy", "malware", "vulnerability", "encryption", "access", "attack", "sandbox"],
        "networking": ["network", "routing", "packet", "congestion", "latency", "transport", "throughput", "bandwidth"],
        "databases": ["database", "query", "sql", "transaction", "join", "storage", "index", "relational"],
    },
    topic_keywords=[
        "security",
        "privacy",
        "network",
        "routing",
        "database",
        "sql",
        "transaction",
        "query optimization",
    ],
)

TEXT_THEORY_BENCHMARK = _text_benchmark(
    benchmark_name="toy_algorithms_crypto_software_topic",
    benchmark_description=(
        "A compact benchmark of software-and-theory snippets labeled as algorithms, cryptography, or software_engineering."
    ),
    dataset_name="Toy Algorithms Crypto Software Topic",
    dataset_description=(
        "Twelve training snippets and six test snippets covering algorithms, cryptography, and software engineering."
    ),
    train=[
        {"text": "Approximation algorithms trade exact optimality for bounded solution quality.", "label": "algorithms"},
        {"text": "Dynamic programming solves overlapping subproblems with memoized recurrences.", "label": "algorithms"},
        {"text": "Graph algorithms compute shortest paths and minimum spanning trees efficiently.", "label": "algorithms"},
        {"text": "Streaming algorithms summarize large inputs with compact sketches.", "label": "algorithms"},
        {"text": "Zero-knowledge proofs let verifiers confirm statements without revealing secrets.", "label": "cryptography"},
        {"text": "Homomorphic encryption supports computation on encrypted ciphertexts.", "label": "cryptography"},
        {"text": "Key exchange protocols establish shared secrets over untrusted channels.", "label": "cryptography"},
        {"text": "Digital signatures authenticate messages and prevent repudiation.", "label": "cryptography"},
        {"text": "Regression testing checks that code changes do not break existing behavior.", "label": "software_engineering"},
        {"text": "Continuous integration automates builds and test suites for every commit.", "label": "software_engineering"},
        {"text": "Refactoring improves code structure without changing observable behavior.", "label": "software_engineering"},
        {"text": "Fault localization ranks suspicious lines after a test failure.", "label": "software_engineering"},
    ],
    test=[
        {"text": "Greedy algorithms make locally optimal choices under structural constraints.", "label": "algorithms"},
        {"text": "Submodular optimization selects sets with diminishing marginal gains.", "label": "algorithms"},
        {"text": "Secure multiparty computation evaluates functions without exposing private inputs.", "label": "cryptography"},
        {"text": "Authenticated encryption combines confidentiality with integrity checks.", "label": "cryptography"},
        {"text": "Code review and automated testing help maintain software quality.", "label": "software_engineering"},
        {"text": "Program repair systems generate candidate patches for failing tests.", "label": "software_engineering"},
    ],
    keyword_map={
        "algorithms": ["algorithm", "graph", "dynamic", "approximation", "streaming", "optimization", "greedy", "submodular"],
        "cryptography": ["cryptography", "proof", "encryption", "signature", "ciphertext", "secret", "authenticated", "multiparty"],
        "software_engineering": ["testing", "integration", "refactoring", "fault", "patch", "review", "software", "quality"],
    },
    topic_keywords=[
        "algorithm",
        "approximation",
        "graph",
        "optimization",
        "cryptography",
        "encryption",
        "software engineering",
        "testing",
        "program repair",
    ],
)

TEXT_BENCHMARKS = [
    TEXT_BENCHMARK,
    TEXT_AGENT_BENCHMARK,
    TEXT_ML_BENCHMARK,
    TEXT_VISION_BENCHMARK,
    TEXT_INFRA_BENCHMARK,
    TEXT_THEORY_BENCHMARK,
]


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


def _normalize_topic_tokens(topic: str | None) -> set[str]:
    if not topic:
        return set()
    return {
        token
        for token in "".join(character.lower() if character.isalnum() else " " for character in topic).split()
        if len(token) >= 2
    }


def _explicit_builtin_name(source: BenchmarkSource | None) -> str | None:
    if source is None:
        return None
    return source.name or source.dataset_id


def _select_text_benchmark(topic: str | None = None, source: BenchmarkSource | None = None) -> dict[str, Any]:
    explicit_name = _explicit_builtin_name(source)
    if explicit_name:
        for benchmark in TEXT_BENCHMARKS:
            if explicit_name in {
                benchmark["benchmark_name"],
                benchmark["dataset"]["name"],
            }:
                return benchmark
    topic_tokens = _normalize_topic_tokens(topic)
    if not topic_tokens:
        return TEXT_BENCHMARK

    best_benchmark = TEXT_BENCHMARK
    best_score = 0
    for benchmark in TEXT_BENCHMARKS:
        keyword_tokens = _normalize_topic_tokens(" ".join(benchmark.get("topic_keywords", [])))
        label_tokens = _normalize_topic_tokens(" ".join(benchmark["dataset"].get("label_space", [])))
        score = len(topic_tokens & keyword_tokens) * 3 + len(topic_tokens & label_tokens)
        if score > best_score:
            best_score = score
            best_benchmark = benchmark
    return best_benchmark


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


def benchmark_payload_for(
    task_family: TaskFamily,
    topic: str | None = None,
    source: BenchmarkSource | None = None,
) -> dict[str, Any]:
    if task_family == "ir_reranking":
        return IR_BENCHMARK
    if task_family == "tabular_classification":
        return TABULAR_BENCHMARK
    return _select_text_benchmark(topic=topic, source=source)


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
    topic: str | None = None,
) -> ResolvedBenchmark:
    selected = benchmark_payload_for(task_family, topic=topic, source=source)
    effective_source = (source or BenchmarkSource(kind="builtin", task_family_hint=task_family)).model_copy(
        update={
            "task_family_hint": task_family,
            "name": source.name if source and source.name else selected["benchmark_name"],
        }
    )
    return ResolvedBenchmark(
        source=effective_source,
        task_family=task_family,
        payload=selected["dataset"],
        benchmark_name=selected["benchmark_name"],
        benchmark_description=selected["benchmark_description"],
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
        label_space = dataset_payload.get("label_space") or sorted(
            {
                item["label"]
                for item in [*dataset_payload.get("train", []), *dataset_payload.get("test", [])]
                if item.get("label")
            }
        )
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
            "Treat each example as a short single document or snippet classification problem.",
            "Compare probabilistic lexical modeling against rule based retrieval signals.",
            "If the benchmark is remote, snapshot the pulled dataset before execution.",
        ]
        hypothesis = (
            "A lightweight lexical probabilistic model should outperform majority and keyword "
            f"baselines on `{resolved.benchmark_name}` topic classification."
        )
        input_fields = ["text"]
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
