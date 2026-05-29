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
from services.autoresearch.research_readiness import dataset_source_fingerprint


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


def _tabular_benchmark(
    *,
    benchmark_name: str,
    benchmark_description: str,
    dataset_name: str,
    dataset_description: str,
    feature_names: list[str],
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    topic_keywords: list[str],
) -> dict[str, Any]:
    label_space = sorted(
        {
            row["label"]
            for row in [*train, *test]
            if isinstance(row, dict) and row.get("label") is not None
        }
    )
    return {
        "benchmark_name": benchmark_name,
        "benchmark_description": benchmark_description,
        "topic_keywords": topic_keywords,
        "dataset": {
            "name": dataset_name,
            "description": dataset_description,
            "feature_names": feature_names,
            "train": train,
            "test": test,
            "label_space": label_space,
        },
    }


def _ir_benchmark(
    *,
    benchmark_name: str,
    benchmark_description: str,
    dataset_name: str,
    dataset_description: str,
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
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
        },
    }


def _tabular_benchmark(
    *,
    benchmark_name: str,
    benchmark_description: str,
    dataset_name: str,
    dataset_description: str,
    feature_names: list[str],
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    topic_keywords: list[str],
) -> dict[str, Any]:
    label_space = sorted(
        {
            row["label"]
            for row in [*train, *test]
            if isinstance(row, dict) and row.get("label") is not None
        }
    )
    return {
        "benchmark_name": benchmark_name,
        "benchmark_description": benchmark_description,
        "topic_keywords": topic_keywords,
        "dataset": {
            "name": dataset_name,
            "description": dataset_description,
            "feature_names": feature_names,
            "train": train,
            "test": test,
            "label_space": label_space,
        },
    }


def _ir_benchmark(
    *,
    benchmark_name: str,
    benchmark_description: str,
    dataset_name: str,
    dataset_description: str,
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
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


TABULAR_BENCHMARK = _tabular_benchmark(
    benchmark_name="toy_training_run_stability",
    benchmark_description=(
        "A small tabular benchmark that predicts whether a model training configuration remains "
        "stable or diverges."
    ),
    dataset_name="Toy Training Run Stability",
    dataset_description=(
        "Sixteen training runs and eight held out runs with numeric optimization and model "
        "configuration features."
    ),
    feature_names=[
        "learning_rate",
        "batch_size",
        "dropout",
        "depth",
        "residual",
    ],
    train=[
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
    test=[
        {"features": [0.0015, 64, 0.10, 8, 1], "label": "stable"},
        {"features": [0.0045, 48, 0.20, 10, 1], "label": "stable"},
        {"features": [0.019, 16, 0.05, 17, 0], "label": "unstable"},
        {"features": [0.022, 24, 0.35, 19, 0], "label": "unstable"},
        {"features": [0.008, 32, 0.25, 12, 1], "label": "stable"},
        {"features": [0.014, 16, 0.30, 14, 0], "label": "unstable"},
        {"features": [0.0035, 128, 0.05, 7, 1], "label": "stable"},
        {"features": [0.011, 24, 0.25, 13, 0], "label": "unstable"},
    ],
    topic_keywords=[
        "training",
        "stability",
        "optimizer",
        "hyperparameter",
        "learning rate",
        "dropout",
        "batch size",
        "model configuration",
    ],
)

TABULAR_NETWORK_BENCHMARK = _tabular_benchmark(
    benchmark_name="toy_network_incident_risk",
    benchmark_description=(
        "A small tabular benchmark that predicts whether network telemetry indicates a healthy "
        "state or a degraded incident condition."
    ),
    dataset_name="Toy Network Incident Risk",
    dataset_description=(
        "Sixteen training and eight held out telemetry snapshots with packet loss, latency, flow, "
        "retransmission, and queue-depth features."
    ),
    feature_names=[
        "packet_loss_pct",
        "p95_latency_ms",
        "active_flows",
        "retransmit_rate",
        "queue_depth",
    ],
    train=[
        {"features": [0.2, 32, 1800, 0.01, 12], "label": "healthy"},
        {"features": [0.4, 40, 2200, 0.02, 16], "label": "healthy"},
        {"features": [0.3, 35, 2100, 0.01, 14], "label": "healthy"},
        {"features": [0.6, 48, 2500, 0.02, 18], "label": "healthy"},
        {"features": [0.5, 44, 2300, 0.02, 17], "label": "healthy"},
        {"features": [0.7, 52, 2700, 0.03, 20], "label": "healthy"},
        {"features": [4.8, 180, 4100, 0.12, 88], "label": "degraded"},
        {"features": [5.5, 210, 4300, 0.15, 96], "label": "degraded"},
        {"features": [3.9, 165, 3900, 0.10, 81], "label": "degraded"},
        {"features": [6.2, 240, 4600, 0.18, 105], "label": "degraded"},
        {"features": [4.4, 190, 4200, 0.13, 90], "label": "degraded"},
        {"features": [3.6, 150, 3600, 0.09, 74], "label": "degraded"},
        {"features": [0.8, 55, 2800, 0.03, 24], "label": "healthy"},
        {"features": [0.9, 60, 2950, 0.04, 28], "label": "healthy"},
        {"features": [2.9, 130, 3400, 0.08, 66], "label": "degraded"},
        {"features": [0.4, 38, 2050, 0.01, 15], "label": "healthy"},
    ],
    test=[
        {"features": [0.3, 34, 2000, 0.01, 13], "label": "healthy"},
        {"features": [0.9, 58, 2850, 0.03, 25], "label": "healthy"},
        {"features": [4.2, 185, 4150, 0.12, 87], "label": "degraded"},
        {"features": [5.8, 225, 4500, 0.16, 101], "label": "degraded"},
        {"features": [1.1, 62, 3000, 0.04, 30], "label": "healthy"},
        {"features": [3.4, 145, 3500, 0.09, 70], "label": "degraded"},
        {"features": [0.5, 42, 2350, 0.02, 18], "label": "healthy"},
        {"features": [4.9, 205, 4350, 0.14, 94], "label": "degraded"},
    ],
    topic_keywords=[
        "network",
        "networking",
        "incident",
        "latency",
        "packet",
        "congestion",
        "routing",
        "telemetry",
        "anomaly",
    ],
)

TABULAR_DATABASE_BENCHMARK = _tabular_benchmark(
    benchmark_name="toy_database_workload_regression",
    benchmark_description=(
        "A small tabular benchmark that predicts whether a database workload remains stable or "
        "regresses under changing query-plan conditions."
    ),
    dataset_name="Toy Database Workload Regression",
    dataset_description=(
        "Sixteen training and eight held out workload snapshots with join complexity, estimated "
        "rows, index coverage, cache hit rate, and concurrency features."
    ),
    feature_names=[
        "join_count",
        "estimated_rows_k",
        "index_coverage",
        "cache_hit_rate",
        "concurrency",
    ],
    train=[
        {"features": [2, 40, 0.92, 0.96, 18], "label": "stable"},
        {"features": [3, 55, 0.88, 0.94, 24], "label": "stable"},
        {"features": [2, 35, 0.95, 0.97, 15], "label": "stable"},
        {"features": [4, 80, 0.84, 0.92, 28], "label": "stable"},
        {"features": [3, 70, 0.86, 0.93, 26], "label": "stable"},
        {"features": [5, 95, 0.82, 0.91, 30], "label": "stable"},
        {"features": [8, 420, 0.38, 0.61, 72], "label": "regressed"},
        {"features": [9, 510, 0.32, 0.56, 80], "label": "regressed"},
        {"features": [7, 390, 0.45, 0.64, 68], "label": "regressed"},
        {"features": [10, 620, 0.28, 0.49, 92], "label": "regressed"},
        {"features": [8, 470, 0.35, 0.58, 75], "label": "regressed"},
        {"features": [6, 340, 0.50, 0.69, 60], "label": "regressed"},
        {"features": [4, 88, 0.83, 0.92, 29], "label": "stable"},
        {"features": [5, 110, 0.79, 0.89, 34], "label": "stable"},
        {"features": [7, 300, 0.54, 0.72, 58], "label": "regressed"},
        {"features": [3, 60, 0.90, 0.95, 22], "label": "stable"},
    ],
    test=[
        {"features": [2, 45, 0.91, 0.96, 19], "label": "stable"},
        {"features": [5, 120, 0.78, 0.88, 36], "label": "stable"},
        {"features": [8, 450, 0.36, 0.59, 74], "label": "regressed"},
        {"features": [9, 560, 0.30, 0.53, 84], "label": "regressed"},
        {"features": [4, 90, 0.82, 0.91, 31], "label": "stable"},
        {"features": [6, 320, 0.52, 0.70, 57], "label": "regressed"},
        {"features": [3, 58, 0.89, 0.95, 23], "label": "stable"},
        {"features": [8, 480, 0.34, 0.57, 78], "label": "regressed"},
    ],
    topic_keywords=[
        "database",
        "sql",
        "query",
        "workload",
        "regression",
        "join",
        "index",
        "transaction",
        "optimizer",
    ],
)

TABULAR_BENCHMARKS = [
    TABULAR_BENCHMARK,
    TABULAR_NETWORK_BENCHMARK,
    TABULAR_DATABASE_BENCHMARK,
]


IR_BENCHMARK = _ir_benchmark(
    benchmark_name="toy_cs_reranking",
    benchmark_description=(
        "A compact reranking benchmark with computer science queries, candidate passages, and a "
        "single relevant document for each query."
    ),
    dataset_name="Toy CS Reranking",
    dataset_description=(
        "Three training queries and three held out queries spanning retrieval, systems, and "
        "program analysis topics."
    ),
    train=[
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
    test=[
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
    topic_keywords=[
        "retrieval",
        "search",
        "ranking",
        "reranking",
        "query",
        "document",
        "program analysis",
        "systems",
    ],
)

IR_CODE_BENCHMARK = _ir_benchmark(
    benchmark_name="toy_code_search_reranking",
    benchmark_description=(
        "A compact reranking benchmark for code-search and software-maintenance queries over "
        "short implementation notes."
    ),
    dataset_name="Toy Code Search Reranking",
    dataset_description=(
        "Three training queries and three held out queries spanning code search, static analysis, "
        "program repair, and testing workflows."
    ),
    train=[
        {
            "query": "python detect sql injection in request handler",
            "candidates": [
                {"id": "c1", "text": "Prepared statements sanitize SQL parameters inside the request handler."},
                {"id": "c2", "text": "Breadth-first search visits graph layers in order."},
                {"id": "c3", "text": "CDN edge caches serve static assets with low latency."},
            ],
            "relevant_ids": ["c1"],
        },
        {
            "query": "compiler pass remove dead code",
            "candidates": [
                {"id": "c4", "text": "Dead-code elimination removes unused branches after constant propagation."},
                {"id": "c5", "text": "Token rerankers refine document results with interaction features."},
                {"id": "c6", "text": "Gradient clipping stabilizes transformer training."},
            ],
            "relevant_ids": ["c4"],
        },
        {
            "query": "program repair failing unit test assertion",
            "candidates": [
                {"id": "c7", "text": "Patch synthesis compares failing assertions against candidate fixes."},
                {"id": "c8", "text": "Vector indexes accelerate nearest-neighbor lookups."},
                {"id": "c9", "text": "KV cache compression lowers inference memory."},
            ],
            "relevant_ids": ["c7"],
        },
    ],
    test=[
        {
            "query": "static analysis null pointer bug localization",
            "candidates": [
                {"id": "u1", "text": "Static analyzers rank null-dereference paths for bug localization."},
                {"id": "u2", "text": "Instruction tuning aligns assistants to user preferences."},
                {"id": "u3", "text": "Congestion control adapts sending rates under loss."},
            ],
            "relevant_ids": ["u1"],
        },
        {
            "query": "code search refactor duplicated logic",
            "candidates": [
                {"id": "u4", "text": "Refactoring tools detect duplicate logic before extracting helpers."},
                {"id": "u5", "text": "Pseudo relevance feedback boosts ad hoc search recall."},
                {"id": "u6", "text": "SLAM systems fuse lidar and camera signals."},
            ],
            "relevant_ids": ["u4"],
        },
        {
            "query": "regression test flaky retry harness",
            "candidates": [
                {"id": "u7", "text": "Flaky-test harnesses isolate retries and report nondeterministic failures."},
                {"id": "u8", "text": "Approximation algorithms trade exactness for speed."},
                {"id": "u9", "text": "Database engines pipeline scans and joins."},
            ],
            "relevant_ids": ["u7"],
        },
    ],
    topic_keywords=[
        "code",
        "code search",
        "software",
        "program repair",
        "static analysis",
        "compiler",
        "bug",
        "testing",
        "refactor",
    ],
)

IR_PAPER_BENCHMARK = _ir_benchmark(
    benchmark_name="toy_paper_evidence_reranking",
    benchmark_description=(
        "A compact reranking benchmark for literature, citation, and evidence retrieval queries "
        "over short paper-style abstracts."
    ),
    dataset_name="Toy Paper Evidence Reranking",
    dataset_description=(
        "Three training queries and three held out queries covering related-work lookup, citation "
        "finding, and evidence retrieval."
    ),
    train=[
        {
            "query": "survey on retrieval augmented generation",
            "candidates": [
                {"id": "p1", "text": "A survey of retrieval-augmented generation compares grounding pipelines and indexing choices."},
                {"id": "p2", "text": "A compiler optimization pass removes dead stores."},
                {"id": "p3", "text": "Queue management controls bursty network latency."},
            ],
            "relevant_ids": ["p1"],
        },
        {
            "query": "paper on diffusion models for image generation",
            "candidates": [
                {"id": "p4", "text": "Diffusion probabilistic models synthesize images through iterative denoising."},
                {"id": "p5", "text": "Prepared statements mitigate SQL injection."},
                {"id": "p6", "text": "Threshold rules classify tabular workloads."},
            ],
            "relevant_ids": ["p4"],
        },
        {
            "query": "related work on benchmark reproducibility",
            "candidates": [
                {"id": "p7", "text": "Reproducibility checklists improve benchmark reporting across seeds and sweeps."},
                {"id": "p8", "text": "Trajectory optimization smooths robot motion."},
                {"id": "p9", "text": "Access-control policies constrain private data access."},
            ],
            "relevant_ids": ["p7"],
        },
    ],
    test=[
        {
            "query": "find evidence for long context evaluation",
            "candidates": [
                {"id": "v1", "text": "Long-context evaluation studies measure recall degradation across extended prompts."},
                {"id": "v2", "text": "Packet traces reveal congestion collapse under overload."},
                {"id": "v3", "text": "Refactoring reduces duplicate code paths."},
            ],
            "relevant_ids": ["v1"],
        },
        {
            "query": "citation on human feedback alignment",
            "candidates": [
                {"id": "v4", "text": "Human-feedback alignment papers compare preference optimization and reward modeling."},
                {"id": "v5", "text": "Shader pipelines implement lighting and texture sampling."},
                {"id": "v6", "text": "Vector indexes speed database retrieval."},
            ],
            "relevant_ids": ["v4"],
        },
        {
            "query": "benchmark paper for agent tool use",
            "candidates": [
                {"id": "v7", "text": "Agent benchmark reports evaluate planning, memory, and tool-use execution traces."},
                {"id": "v8", "text": "Perceptrons separate tabular classes with a linear boundary."},
                {"id": "v9", "text": "Multipath routing spreads flows across network links."},
            ],
            "relevant_ids": ["v7"],
        },
    ],
    topic_keywords=[
        "paper",
        "literature",
        "citation",
        "evidence",
        "related work",
        "survey",
        "abstract",
        "benchmark",
        "research",
    ],
)

IR_SECURITY_BENCHMARK = _ir_benchmark(
    benchmark_name="toy_security_incident_reranking",
    benchmark_description=(
        "A compact reranking benchmark for incident-response and security-alert triage queries."
    ),
    dataset_name="Toy Security Incident Reranking",
    dataset_description=(
        "Three training queries and three held out queries covering phishing, intrusion, malware, "
        "and host-compromise investigations."
    ),
    train=[
        {
            "query": "phishing login alert investigation playbook",
            "candidates": [
                {"id": "s1", "text": "Investigate suspicious login alerts by checking impossible travel and MFA resets."},
                {"id": "s2", "text": "Ray tracing simulates realistic reflections and shadows."},
                {"id": "s3", "text": "Bayesian optimization tunes learning rates efficiently."},
            ],
            "relevant_ids": ["s1"],
        },
        {
            "query": "dns tunneling beacon detection",
            "candidates": [
                {"id": "s4", "text": "DNS tunneling detection looks for long high-entropy TXT or subdomain queries."},
                {"id": "s5", "text": "Pseudo relevance feedback expands retrieval queries."},
                {"id": "s6", "text": "Join reordering reduces relational execution cost."},
            ],
            "relevant_ids": ["s4"],
        },
        {
            "query": "linux privilege escalation on host",
            "candidates": [
                {"id": "s7", "text": "Privilege-escalation triage checks sudoers changes, new setuid binaries, and suspicious services."},
                {"id": "s8", "text": "Mesh simplification reduces polygon count."},
                {"id": "s9", "text": "Long-term memory stores prior agent episodes."},
            ],
            "relevant_ids": ["s7"],
        },
    ],
    test=[
        {
            "query": "credential stuffing traffic spike",
            "candidates": [
                {"id": "w1", "text": "Credential-stuffing investigations correlate login failures, IP rotation, and password spraying."},
                {"id": "w2", "text": "Differentiable rendering links scenes to image losses."},
                {"id": "w3", "text": "Compiler passes normalize control-flow graphs."},
            ],
            "relevant_ids": ["w1"],
        },
        {
            "query": "lateral movement via remote admin tools",
            "candidates": [
                {"id": "w4", "text": "Lateral-movement triage traces remote admin tools, credential reuse, and suspicious east-west sessions."},
                {"id": "w5", "text": "Gradient boosting improves supervised classification."},
                {"id": "w6", "text": "Usability studies compare interface task completion."},
            ],
            "relevant_ids": ["w4"],
        },
        {
            "query": "malware sandbox escape investigation",
            "candidates": [
                {"id": "w7", "text": "Sandbox-escape response reviews kernel exploits, breakout logs, and process-tree anomalies."},
                {"id": "w8", "text": "Secure multiparty computation protects private inputs."},
                {"id": "w9", "text": "Vector search relies on nearest-neighbor indexing."},
            ],
            "relevant_ids": ["w7"],
        },
    ],
    topic_keywords=[
        "security",
        "incident",
        "alert",
        "intrusion",
        "phishing",
        "malware",
        "credential",
        "dns",
        "lateral movement",
    ],
)

IR_CLAIM_EVIDENCE_BENCHMARK = _ir_benchmark(
    benchmark_name="frozen_claim_evidence_reranking",
    benchmark_description=(
        "A frozen local reranking benchmark for claim-evidence retrieval in autonomous "
        "scientific writing. Queries contain claim, citation, ablation, and reviewer-support "
        "needs; candidate pools include near-miss passages so lexical overlap alone is not "
        "sufficient."
    ),
    dataset_name="Frozen Claim Evidence Reranking",
    dataset_description=(
        "Twelve training queries and twelve held-out queries with five candidate passages per "
        "query. The fixture is deterministic and synthetic, but designed to exercise real "
        "claim-evidence retrieval failure modes such as unsupported-claim distractors, citation "
        "near misses, and ablation/reporting ambiguity."
    ),
    train=[
        {
            "query": "claim evidence ledger unsupported claims",
            "candidates": [
                {
                    "id": "ce_tr_1_rel",
                    "text": "A claim evidence ledger links unsupported claims to cited paper passages before review.",
                },
                {
                    "id": "ce_tr_1_d1",
                    "text": "A ledger records project budgets and evidence fields but omits citation validation.",
                },
                {
                    "id": "ce_tr_1_d2",
                    "text": "Unsupported optimization claims can appear in benchmark summaries without an audit.",
                },
                {
                    "id": "ce_tr_1_d3",
                    "text": "Reviewer comments ask authors to clarify paper contributions and novelty risks.",
                },
                {
                    "id": "ce_tr_1_d4",
                    "text": "Artifact lineage stores code paths, result tables, and environment metadata.",
                },
            ],
            "relevant_ids": ["ce_tr_1_rel"],
        },
        {
            "query": "citation grounding for generated paper claims",
            "candidates": [
                {
                    "id": "ce_tr_2_d1",
                    "text": "Generated papers may contain fluent claims that are not tied to any bibliography entry.",
                },
                {
                    "id": "ce_tr_2_rel",
                    "text": "Citation grounding verifies generated paper claims against retrieved evidence passages.",
                },
                {
                    "id": "ce_tr_2_d2",
                    "text": "A citation graph clusters related work by venue, year, and author overlap.",
                },
                {
                    "id": "ce_tr_2_d3",
                    "text": "Paper formatting tools generate references, figures, and source archives.",
                },
                {
                    "id": "ce_tr_2_d4",
                    "text": "Claim templates can simplify abstract writing but do not prove factual support.",
                },
            ],
            "relevant_ids": ["ce_tr_2_rel"],
        },
        {
            "query": "ablation evidence in reranking experiment",
            "candidates": [
                {
                    "id": "ce_tr_3_d1",
                    "text": "A reranking experiment reports aggregate MRR without isolating the evidence feature.",
                },
                {
                    "id": "ce_tr_3_d2",
                    "text": "Ablation plans list model components but lack evidence from executed runs.",
                },
                {
                    "id": "ce_tr_3_rel",
                    "text": "Ablation evidence in reranking shows that removing citation features lowers MRR.",
                },
                {
                    "id": "ce_tr_3_d3",
                    "text": "Dataset cards describe train and test partitions for retrieval tasks.",
                },
                {
                    "id": "ce_tr_3_d4",
                    "text": "Failure replanning adds missing baselines when execution artifacts are incomplete.",
                },
            ],
            "relevant_ids": ["ce_tr_3_rel"],
        },
        {
            "query": "reviewer asks for baseline comparison evidence",
            "candidates": [
                {
                    "id": "ce_tr_4_rel",
                    "text": "Reviewer baseline comparison evidence requires candidate results against lexical and random systems.",
                },
                {
                    "id": "ce_tr_4_d1",
                    "text": "A reviewer asks for a clearer motivation paragraph and more concise related work.",
                },
                {
                    "id": "ce_tr_4_d2",
                    "text": "Baseline comparison tables can omit confidence intervals and seed coverage.",
                },
                {
                    "id": "ce_tr_4_d3",
                    "text": "Evidence ledgers track supported claims but do not automatically resolve reviewer comments.",
                },
                {
                    "id": "ce_tr_4_d4",
                    "text": "A paper checklist includes ethics, limitations, and artifact availability statements.",
                },
            ],
            "relevant_ids": ["ce_tr_4_rel"],
        },
        {
            "query": "literature gap citation supported novelty",
            "candidates": [
                {
                    "id": "ce_tr_5_d1",
                    "text": "Novelty statements should be scoped when literature coverage is incomplete.",
                },
                {
                    "id": "ce_tr_5_rel",
                    "text": "A literature gap is citation supported when retrieved papers establish missing evidence.",
                },
                {
                    "id": "ce_tr_5_d2",
                    "text": "Citation counts alone do not prove that a proposed novelty gap is real.",
                },
                {
                    "id": "ce_tr_5_d3",
                    "text": "A dataset gap can motivate benchmark creation without demonstrating method novelty.",
                },
                {
                    "id": "ce_tr_5_d4",
                    "text": "Known SOTA tables collect metrics, datasets, and reported results from papers.",
                },
            ],
            "relevant_ids": ["ce_tr_5_rel"],
        },
        {
            "query": "evidence constrained paper conclusion",
            "candidates": [
                {
                    "id": "ce_tr_6_d1",
                    "text": "Paper conclusions often overstate broader generalization beyond the benchmark.",
                },
                {
                    "id": "ce_tr_6_rel",
                    "text": "An evidence constrained paper conclusion only states claims supported by run artifacts.",
                },
                {
                    "id": "ce_tr_6_d2",
                    "text": "Conclusion sections can summarize experiments, limitations, and future work.",
                },
                {
                    "id": "ce_tr_6_d3",
                    "text": "Claim evidence matrices connect manuscript sentences to tables and citations.",
                },
                {
                    "id": "ce_tr_6_d4",
                    "text": "Publication gates block unsupported results when artifacts are missing.",
                },
            ],
            "relevant_ids": ["ce_tr_6_rel"],
        },
        {
            "query": "artifact lineage experiment evidence",
            "candidates": [
                {
                    "id": "ce_tr_7_d1",
                    "text": "Experiment evidence includes metrics, logs, and generated code snapshots.",
                },
                {
                    "id": "ce_tr_7_rel",
                    "text": "Artifact lineage connects experiment evidence to the exact run, benchmark, and paper claim.",
                },
                {
                    "id": "ce_tr_7_d2",
                    "text": "Lineage graphs can show ownership edges between projects and run assets.",
                },
                {
                    "id": "ce_tr_7_d3",
                    "text": "Evidence ledgers may record a failed job as missing support.",
                },
                {
                    "id": "ce_tr_7_d4",
                    "text": "A benchmark card documents source kind, license, revision, and split sizes.",
                },
            ],
            "relevant_ids": ["ce_tr_7_rel"],
        },
        {
            "query": "unsupported result claim repair action",
            "candidates": [
                {
                    "id": "ce_tr_8_d1",
                    "text": "Repair actions can rerun a failed job or add a missing ablation.",
                },
                {
                    "id": "ce_tr_8_rel",
                    "text": "An unsupported result claim repair action downgrades the manuscript until evidence is added.",
                },
                {
                    "id": "ce_tr_8_d2",
                    "text": "Result claims compare objective scores, baselines, and confidence intervals.",
                },
                {
                    "id": "ce_tr_8_d3",
                    "text": "Unsupported citations create reviewer issues that remain open after compilation.",
                },
                {
                    "id": "ce_tr_8_d4",
                    "text": "Failure-driven replanning classifies baseline, ablation, statistics, and runtime gaps.",
                },
            ],
            "relevant_ids": ["ce_tr_8_rel"],
        },
        {
            "query": "known sota metric from abstract",
            "candidates": [
                {
                    "id": "ce_tr_9_d1",
                    "text": "An abstract may mention benchmarks without giving enough metric detail.",
                },
                {
                    "id": "ce_tr_9_rel",
                    "text": "Known SOTA metric extraction from abstracts records datasets, methods, and reported scores.",
                },
                {
                    "id": "ce_tr_9_d2",
                    "text": "Metric tables should distinguish validation, test, and ablation measurements.",
                },
                {
                    "id": "ce_tr_9_d3",
                    "text": "Related work paragraphs summarize methods but can omit numerical results.",
                },
                {
                    "id": "ce_tr_9_d4",
                    "text": "Novelty validators compare candidate gaps with known papers and methods.",
                },
            ],
            "relevant_ids": ["ce_tr_9_rel"],
        },
        {
            "query": "claim support retrieval benchmark",
            "candidates": [
                {
                    "id": "ce_tr_10_rel",
                    "text": "A claim support retrieval benchmark ranks evidence passages for manuscript claims.",
                },
                {
                    "id": "ce_tr_10_d1",
                    "text": "Retrieval benchmark suites measure ranking quality across queries and candidates.",
                },
                {
                    "id": "ce_tr_10_d2",
                    "text": "Claim classifiers label sentences as supported, contradicted, or uncertain.",
                },
                {
                    "id": "ce_tr_10_d3",
                    "text": "Support tickets can be ranked by service priority and incident severity.",
                },
                {
                    "id": "ce_tr_10_d4",
                    "text": "Benchmark cards record source provenance but not paper claim alignment.",
                },
            ],
            "relevant_ids": ["ce_tr_10_rel"],
        },
        {
            "query": "revision loop resolves citation issue",
            "candidates": [
                {
                    "id": "ce_tr_11_d1",
                    "text": "A revision loop may rewrite claims, rerun experiments, or downgrade unsupported sections.",
                },
                {
                    "id": "ce_tr_11_rel",
                    "text": "The revision loop resolves a citation issue only after the paper cites valid evidence.",
                },
                {
                    "id": "ce_tr_11_d2",
                    "text": "Reviewer simulators create issue lists for paper clarity and reproducibility.",
                },
                {
                    "id": "ce_tr_11_d3",
                    "text": "Citation formatting issues can be fixed without changing scientific claims.",
                },
                {
                    "id": "ce_tr_11_d4",
                    "text": "Action indexes track pending, completed, and blocked revision work.",
                },
            ],
            "relevant_ids": ["ce_tr_11_rel"],
        },
        {
            "query": "paper package reproducibility evidence",
            "candidates": [
                {
                    "id": "ce_tr_12_rel",
                    "text": "A paper package reproducibility evidence index includes code, data snapshots, and ledgers.",
                },
                {
                    "id": "ce_tr_12_d1",
                    "text": "Reproducibility checklists ask authors to share artifacts and random seeds.",
                },
                {
                    "id": "ce_tr_12_d2",
                    "text": "Paper packages include source files, bibliography, figures, and supplementary material.",
                },
                {
                    "id": "ce_tr_12_d3",
                    "text": "Evidence indexes list claim identifiers and supporting source references.",
                },
                {
                    "id": "ce_tr_12_d4",
                    "text": "Submission archives can be stale when manifest hashes do not match files.",
                },
            ],
            "relevant_ids": ["ce_tr_12_rel"],
        },
    ],
    test=[
        {
            "query": "unsupported claim detection writing agent",
            "candidates": [
                {
                    "id": "ce_te_1_z1",
                    "text": "An agent stores writing notes about detection thresholds for unsupported research and a claim queue.",
                },
                {
                    "id": "ce_te_1_rel",
                    "text": "Unsupported claim detection in a writing agent compares draft claims with cited evidence.",
                },
                {
                    "id": "ce_te_1_d2",
                    "text": "Claim detection models may classify sentences without using citation context.",
                },
                {
                    "id": "ce_te_1_d3",
                    "text": "Agent memory stores previous review comments and revision plans.",
                },
                {
                    "id": "ce_te_1_d4",
                    "text": "Detection thresholds tune precision and recall for classification tasks.",
                },
            ],
            "relevant_ids": ["ce_te_1_rel"],
        },
        {
            "query": "citation evidence for novelty gap",
            "candidates": [
                {
                    "id": "ce_te_2_d1",
                    "text": "A novelty gap can be stated in the introduction without retrieved citations.",
                },
                {
                    "id": "ce_te_2_rel",
                    "text": "Citation evidence for a novelty gap compares the proposed claim with related papers.",
                },
                {
                    "id": "ce_te_2_d2",
                    "text": "Evidence tables report metrics but cannot alone establish literature novelty.",
                },
                {
                    "id": "ce_te_2_d3",
                    "text": "Gap mining narrows broad ideas into dataset and metric obligations.",
                },
                {
                    "id": "ce_te_2_d4",
                    "text": "Citation style rules determine author-year or numeric reference formatting.",
                },
            ],
            "relevant_ids": ["ce_te_2_rel"],
        },
        {
            "query": "reranking evidence ledger ablation",
            "candidates": [
                {
                    "id": "ce_te_3_z1",
                    "text": "A ledger lists ablation notes and evidence fragments for reranking without testing feature removal.",
                },
                {
                    "id": "ce_te_3_rel",
                    "text": "The reranking evidence ledger ablation shows which citation features drive MRR gains.",
                },
                {
                    "id": "ce_te_3_d2",
                    "text": "Ablation experiments can fail when seed coverage is too small.",
                },
                {
                    "id": "ce_te_3_d3",
                    "text": "Evidence ledgers are complete only when baseline artifacts are materialized.",
                },
                {
                    "id": "ce_te_3_d4",
                    "text": "Reranking models compare candidate passages under lexical and neural scoring.",
                },
            ],
            "relevant_ids": ["ce_te_3_rel"],
        },
        {
            "query": "paper reviewer requests evidence downgrade",
            "candidates": [
                {
                    "id": "ce_te_4_d1",
                    "text": "A paper reviewer requests stronger experiments and clearer motivation.",
                },
                {
                    "id": "ce_te_4_rel",
                    "text": "A reviewer requests evidence downgrade when the paper makes unsupported claims.",
                },
                {
                    "id": "ce_te_4_d2",
                    "text": "Evidence downgrade actions revise claims until result artifacts support them.",
                },
                {
                    "id": "ce_te_4_d3",
                    "text": "Reviewer forms score novelty, clarity, soundness, and reproducibility.",
                },
                {
                    "id": "ce_te_4_d4",
                    "text": "Paper drafts can be regenerated after section-level edit packets are applied.",
                },
            ],
            "relevant_ids": ["ce_te_4_rel"],
        },
        {
            "query": "experiment result claim supported by artifact",
            "candidates": [
                {
                    "id": "ce_te_5_d1",
                    "text": "Experiment result tables summarize candidate and baseline systems.",
                },
                {
                    "id": "ce_te_5_rel",
                    "text": "An experiment result claim is supported by an artifact when metrics and logs match.",
                },
                {
                    "id": "ce_te_5_d2",
                    "text": "Artifact registries include generated code, benchmark snapshots, and paper files.",
                },
                {
                    "id": "ce_te_5_d3",
                    "text": "Claim support labels may be missing when evidence references are stale.",
                },
                {
                    "id": "ce_te_5_d4",
                    "text": "A result claim can be contradicted by a later failed seed run.",
                },
            ],
            "relevant_ids": ["ce_te_5_rel"],
        },
        {
            "query": "known sota extraction citation metric",
            "candidates": [
                {
                    "id": "ce_te_6_rel",
                    "text": "Known SOTA extraction records citation, metric, dataset, and reported result fields.",
                },
                {
                    "id": "ce_te_6_d1",
                    "text": "Citation extraction finds paper identifiers, authors, and venue metadata.",
                },
                {
                    "id": "ce_te_6_d2",
                    "text": "Metric extraction can collect accuracy, MRR, nDCG, and macro F1 strings.",
                },
                {
                    "id": "ce_te_6_d3",
                    "text": "SOTA claims require comparing reported results across compatible datasets.",
                },
                {
                    "id": "ce_te_6_d4",
                    "text": "Known failure modes include missing abstracts and ambiguous venue names.",
                },
            ],
            "relevant_ids": ["ce_te_6_rel"],
        },
        {
            "query": "failure driven repair missing baseline evidence",
            "candidates": [
                {
                    "id": "ce_te_7_d1",
                    "text": "A missing baseline can make performance claims too weak for review.",
                },
                {
                    "id": "ce_te_7_rel",
                    "text": "Failure driven repair adds missing baseline evidence before promoting result claims.",
                },
                {
                    "id": "ce_te_7_d2",
                    "text": "Repair planning also handles missing ablations and insufficient statistics.",
                },
                {
                    "id": "ce_te_7_d3",
                    "text": "Baseline evidence should include matched datasets and metrics.",
                },
                {
                    "id": "ce_te_7_d4",
                    "text": "Runtime failures are classified separately from scientific negative results.",
                },
            ],
            "relevant_ids": ["ce_te_7_rel"],
        },
        {
            "query": "claim evidence matrix manuscript sentence",
            "candidates": [
                {
                    "id": "ce_te_8_rel",
                    "text": "A claim evidence matrix links each manuscript sentence to artifact or literature support.",
                },
                {
                    "id": "ce_te_8_d1",
                    "text": "Manuscript sentences may be rewritten to improve clarity and remove repetition.",
                },
                {
                    "id": "ce_te_8_d2",
                    "text": "Evidence matrices can expose unsupported claims before submission packaging.",
                },
                {
                    "id": "ce_te_8_d3",
                    "text": "Claim classifiers assign support labels to sentences using retrieved evidence.",
                },
                {
                    "id": "ce_te_8_d4",
                    "text": "A matrix factorization model is unrelated to paper evidence tracking.",
                },
            ],
            "relevant_ids": ["ce_te_8_rel"],
        },
        {
            "query": "review loop citation issue resolved",
            "candidates": [
                {
                    "id": "ce_te_9_d1",
                    "text": "A review loop can leave citation issues open when evidence is still missing.",
                },
                {
                    "id": "ce_te_9_rel",
                    "text": "A review loop citation issue is resolved only after valid evidence is attached.",
                },
                {
                    "id": "ce_te_9_d2",
                    "text": "Issue trackers record reviewer severity, category, and action priority.",
                },
                {
                    "id": "ce_te_9_d3",
                    "text": "Citation repair may update bibliography entries without fixing claim support.",
                },
                {
                    "id": "ce_te_9_d4",
                    "text": "Resolved actions should be reflected in the revision dossier.",
                },
            ],
            "relevant_ids": ["ce_te_9_rel"],
        },
        {
            "query": "submission package evidence index reproducibility",
            "candidates": [
                {
                    "id": "ce_te_10_rel",
                    "text": "A submission package evidence index ties reproducibility files to supported claims.",
                },
                {
                    "id": "ce_te_10_d1",
                    "text": "Submission packages contain manuscript sources, compiled PDFs, and archives.",
                },
                {
                    "id": "ce_te_10_d2",
                    "text": "Evidence indexes list artifact hashes, claim identifiers, and reviewer responses.",
                },
                {
                    "id": "ce_te_10_d3",
                    "text": "Reproducibility statements describe code availability and compute requirements.",
                },
                {
                    "id": "ce_te_10_d4",
                    "text": "Package manifests fail when archives are stale or incomplete.",
                },
            ],
            "relevant_ids": ["ce_te_10_rel"],
        },
        {
            "query": "literature scout structured paper metadata",
            "candidates": [
                {
                    "id": "ce_te_11_rel",
                    "text": "A literature scout returns structured paper metadata with methods, datasets, metrics, and risk signals.",
                },
                {
                    "id": "ce_te_11_d1",
                    "text": "Paper metadata includes title, authors, venue, DOI, and abstract fields.",
                },
                {
                    "id": "ce_te_11_d2",
                    "text": "Structured metadata can be cached before graph construction and novelty validation.",
                },
                {
                    "id": "ce_te_11_d3",
                    "text": "Scout queries should respect network settings and offline fixtures.",
                },
                {
                    "id": "ce_te_11_d4",
                    "text": "Risk signals estimate whether a proposed idea overlaps existing work.",
                },
            ],
            "relevant_ids": ["ce_te_11_rel"],
        },
        {
            "query": "paper false positive unsupported result audit",
            "candidates": [
                {
                    "id": "ce_te_12_d1",
                    "text": "A paper audit can find a false positive benchmark improvement.",
                },
                {
                    "id": "ce_te_12_rel",
                    "text": "Artifact checking downgrades hallucinated experimental statements after evidence review.",
                },
                {
                    "id": "ce_te_12_d2",
                    "text": "False positive unsupported result detectors may require adversarial examples.",
                },
                {
                    "id": "ce_te_12_d3",
                    "text": "Unsupported paper results often arise from missing baselines or incomplete seeds.",
                },
                {
                    "id": "ce_te_12_d4",
                    "text": "Audit logs should preserve reviewer issues and repair actions.",
                },
            ],
            "relevant_ids": ["ce_te_12_rel"],
        },
    ],
    topic_keywords=[
        "claim",
        "claims",
        "evidence",
        "retrieval",
        "reranking",
        "ledger",
        "unsupported",
        "grounding",
        "citation",
        "novelty",
        "autonomous",
        "review",
        "writing agent",
        "scientific writing",
        "ablation",
        "repair",
    ],
)
IR_CLAIM_EVIDENCE_BENCHMARK["dataset"].update(
    {
        "source_url": "local://scholarflow/fixtures/frozen_claim_evidence_reranking/v1",
        "source_dataset_id": "scholarflow:frozen_claim_evidence_reranking",
        "source_revision": "v1.0.0",
        "source_license": "synthetic-fixture",
    }
)

IR_BENCHMARKS = [
    IR_BENCHMARK,
    IR_CODE_BENCHMARK,
    IR_PAPER_BENCHMARK,
    IR_SECURITY_BENCHMARK,
    IR_CLAIM_EVIDENCE_BENCHMARK,
]


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


def _select_benchmark_from_catalog(
    benchmarks: list[dict[str, Any]],
    default_benchmark: dict[str, Any],
    *,
    topic: str | None = None,
    source: BenchmarkSource | None = None,
) -> dict[str, Any]:
    explicit_name = _explicit_builtin_name(source)
    if explicit_name:
        lowered_explicit = explicit_name.lower()
        for benchmark in benchmarks:
            if lowered_explicit in {
                str(benchmark["benchmark_name"]).lower(),
                str(benchmark["dataset"]["name"]).lower(),
            }:
                return benchmark
    topic_tokens = _normalize_topic_tokens(topic)
    if not topic_tokens:
        return default_benchmark

    best_benchmark = default_benchmark
    best_score = 0
    for benchmark in benchmarks:
        dataset = benchmark["dataset"]
        keyword_tokens = _normalize_topic_tokens(" ".join(benchmark.get("topic_keywords", [])))
        description_tokens = _normalize_topic_tokens(
            " ".join(
                [
                    str(benchmark.get("benchmark_description", "")),
                    str(dataset.get("description", "")),
                ]
            )
        )
        aux_tokens = _normalize_topic_tokens(
            " ".join(dataset.get("label_space", []) + dataset.get("feature_names", []))
        )
        score = (
            len(topic_tokens & keyword_tokens) * 4
            + len(topic_tokens & aux_tokens) * 2
            + len(topic_tokens & description_tokens)
        )
        if score > best_score:
            best_score = score
            best_benchmark = benchmark
    return best_benchmark


def _select_text_benchmark(topic: str | None = None, source: BenchmarkSource | None = None) -> dict[str, Any]:
    return _select_benchmark_from_catalog(
        TEXT_BENCHMARKS,
        TEXT_BENCHMARK,
        topic=topic,
        source=source,
    )


def _select_tabular_benchmark(topic: str | None = None, source: BenchmarkSource | None = None) -> dict[str, Any]:
    return _select_benchmark_from_catalog(
        TABULAR_BENCHMARKS,
        TABULAR_BENCHMARK,
        topic=topic,
        source=source,
    )


def _select_ir_benchmark(topic: str | None = None, source: BenchmarkSource | None = None) -> dict[str, Any]:
    return _select_benchmark_from_catalog(
        IR_BENCHMARKS,
        IR_BENCHMARK,
        topic=topic,
        source=source,
    )


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
        return _select_ir_benchmark(topic=topic, source=source)
    if task_family == "tabular_classification":
        return _select_tabular_benchmark(topic=topic, source=source)
    return _select_text_benchmark(topic=topic, source=source)


def default_search_strategies(task_family: TaskFamily) -> list[str]:
    if task_family == "ir_reranking":
        return [
            "overlap_baseline_search",
            "idf_reranker_search",
            "bigram_reranker_search",
            "ledger_aware_reranker_search",
        ]
    if task_family == "tabular_classification":
        return [
            "threshold_rule_search",
            "perceptron_unscaled_search",
            "perceptron_scaled_search",
        ]
    if task_family == "llm_evaluation":
        return [
            "zero_shot_search",
            "few_shot_search",
            "rule_based_search",
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
                params={"idf_smoothing": 1.0, "bigram_bonus": 0.5, "ledger_weight": 1.0},
                description="Default rarity weighting with modest bigram and ledger cue bonuses.",
            ),
            SweepConfig(
                label="rarity_boosted",
                params={"idf_smoothing": 1.4, "bigram_bonus": 0.9, "ledger_weight": 1.4},
                description="Increase IDF smoothing and emphasize bigram plus evidence-ledger cue alignment.",
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
    dataset_payload = selected["dataset"]
    effective_source = (source or BenchmarkSource(kind="builtin", task_family_hint=task_family)).model_copy(
        update={
            "task_family_hint": task_family,
            "name": source.name if source and source.name else selected["benchmark_name"],
            "url": source.url if source and source.url else dataset_payload.get("source_url"),
            "dataset_id": (
                source.dataset_id
                if source and source.dataset_id
                else dataset_payload.get("source_dataset_id")
            ),
            "revision": source.revision if source and source.revision else dataset_payload.get("source_revision"),
            "license": source.license if source and source.license else dataset_payload.get("source_license"),
        }
    )
    return ResolvedBenchmark(
        source=effective_source,
        task_family=task_family,
        payload=dataset_payload,
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
            MetricSpec(name="ndcg_at_10", goal="maximize", description="Binary-relevance nDCG over the top 10 ranked documents."),
            MetricSpec(name="recall_at_10", goal="maximize", description="Fraction of gold evidence documents recovered in the top 10."),
            MetricSpec(
                name="evidence_coverage",
                goal="maximize",
                description="Fraction of queries whose complete gold evidence set is covered in the top 10.",
            ),
            MetricSpec(
                name="verification_accuracy",
                goal="maximize",
                description="Exact supported/refuted/not-enough-info verdict accuracy when claim labels are present.",
            ),
            MetricSpec(
                name="unsupported_claim_precision",
                goal="maximize",
                description="Precision for detecting refuted or not-enough-info claims.",
            ),
            MetricSpec(
                name="unsupported_claim_recall",
                goal="maximize",
                description="Recall for detecting refuted or not-enough-info claims.",
            ),
            MetricSpec(
                name="abstention_accuracy",
                goal="maximize",
                description="Accuracy on not-enough-info claims.",
            ),
        ]
        ablations = [
            AblationSpec(
                name="bigram_ranker",
                description="Add query-document bigram overlap as a higher-order lexical reranking signal.",
            ),
            AblationSpec(
                name="ledger_aware_ranker",
                description=(
                    "Add claim, citation, artifact, experiment, and review-repair cue alignment "
                    "for evidence-ledger-aware reranking."
                ),
            )
        ]
        notes = [
            "Use only Python standard library utilities.",
            "Treat each example as a query with a short candidate list.",
            (
                "Report MRR, Recall@1, nDCG@10, Recall@10, evidence coverage, and when labels "
                "exist, claim-verification accuracy, unsupported-claim precision/recall, and abstention accuracy."
            ),
            "Support BEIR-style normalized JSON as an external adapter target.",
            "Use ledger-aware cue alignment only as a transparent text signal; do not inspect relevance labels.",
        ]
        hypothesis = (
            "A lexical reranker with rarity-aware term weighting should outperform the random order "
            f"and simple overlap baselines on `{resolved.benchmark_name}`."
        )
        input_fields = []
        label_space = []
        query_fields = ["query"]
        candidate_count = max((len(item.get("candidates", [])) for item in dataset_payload["test"]), default=0)
    elif task_family == "tabular_classification":
        label_space = dataset_payload.get("label_space") or sorted(
            {
                item["label"]
                for item in [*dataset_payload.get("train", []), *dataset_payload.get("test", [])]
                if item.get("label")
            }
        )
        baselines = [
            BaselineSpec(name="majority", description="Predict the most frequent class label."),
            BaselineSpec(
                name="threshold_rule",
                description="A hand written one-feature threshold rule over the benchmark features.",
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
            f"the hand written threshold rule on `{resolved.benchmark_name}`."
        )
        input_fields = dataset_payload["feature_names"]
        query_fields = []
        candidate_count = None
    elif task_family == "llm_evaluation":
        label_space = dataset_payload.get("label_space") or sorted(
            {
                item["label"]
                for item in [*dataset_payload.get("train", []), *dataset_payload.get("test", [])]
                if item.get("label")
            }
        )
        baselines = [
            BaselineSpec(name="zero_shot", description="Zero-shot classification using no examples."),
            BaselineSpec(name="few_shot", description="Few-shot classification using example-based heuristics."),
            BaselineSpec(name="rule_based", description="Rule-based keyword matching classifier."),
        ]
        metrics = [
            MetricSpec(name="accuracy", goal="maximize", description="Classification accuracy."),
            MetricSpec(name="f1", goal="maximize", description="Token-level F1 score."),
        ]
        ablations = []
        notes = [
            "Evaluate different prompting strategies against structured test examples.",
            "Compare zero-shot, few-shot, and rule-based approaches.",
            "Report accuracy and F1 on the held-out examples.",
        ]
        hypothesis = (
            "Few-shot prompting with example-based heuristics should outperform "
            f"zero-shot and rule-based baselines on `{resolved.benchmark_name}`."
        )
        input_fields = ["input"]
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
            source_kind=resolved.source.kind,
            source_url=dataset_payload.get("source_url") or resolved.source.url,
            source_dataset_id=resolved.source.dataset_id,
            source_revision=resolved.source.revision,
            source_license=resolved.source.license,
            source_fingerprint=dataset_source_fingerprint(dataset_payload),
            publication_grade=(
                resolved.source.kind != "builtin"
                and not resolved.benchmark_name.startswith("toy_")
                and not str(dataset_payload.get("name") or "").lower().startswith("toy ")
                and len(dataset_payload["train"]) + len(dataset_payload["test"]) >= 20
            ),
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
