from __future__ import annotations

import json
import logging
import re
from typing import Any

from schemas.autoresearch import ExperimentAttempt, ExperimentSpec, ResearchPlan
from services.llm.client import chat
from services.autoresearch.runtime_contract import missing_runtime_controls, runtime_contract_payload
from services.llm.prompting import load_prompt
from services.llm.response_utils import get_message_content

logger = logging.getLogger(__name__)


PROMPT_PATH = "backend/prompts/autoresearch/codegen/v0.1.1.md"


class ExperimentCodeGenerator:
    def _extract_code(self, text: str) -> str | None:
        if not text:
            return None
        fenced = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.S)
        if fenced:
            return fenced.group(1).strip()
        return text.strip() or None

    def _is_valid_code(self, code: str | None) -> bool:
        if not code or "__RESULT__" not in code:
            logger.debug("codegen reject: code empty or missing __RESULT__")
            return False
        missing = missing_runtime_controls(code)
        if missing:
            logger.warning("codegen reject: missing runtime controls: %s", missing)
            return False
        try:
            compile(code, "<autorresearch>", "exec")
        except SyntaxError as exc:
            logger.warning("codegen reject: syntax error at line %s: %s", exc.lineno, exc.msg)
            return False
        return True

    def _strategy_for(self, spec: ExperimentSpec, round_index: int) -> str:
        if not spec.search_strategies:
            return "default_search"
        idx = min(max(round_index - 1, 0), len(spec.search_strategies) - 1)
        return spec.search_strategies[idx]

    def _llm_code(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
        strategy: str,
        goal: str,
        prior_attempts: list[ExperimentAttempt],
    ) -> str | None:
        try:
            prompt = load_prompt(PROMPT_PATH)
            response = chat(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "plan": plan.model_dump(mode="json"),
                                "spec": spec.model_dump(mode="json"),
                                "benchmark_payload": benchmark_payload,
                                "strategy": strategy,
                                "goal": goal,
                                "prior_attempts": [item.model_dump(mode="json") for item in prior_attempts],
                                "runtime_contract": runtime_contract_payload(),
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                ]
            )
            content = get_message_content(response)
            if not content:
                logger.warning("codegen: LLM returned empty content")
                return None
            extracted = self._extract_code(content)
            if extracted is None:
                logger.warning("codegen: could not extract code block from LLM response (len=%d)", len(content))
            return extracted
        except Exception as exc:
            logger.error("codegen: LLM call failed: %s", exc)
            return None

    def generate(
        self,
        *,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
        round_index: int,
        goal: str,
        prior_attempts: list[ExperimentAttempt],
    ) -> tuple[str, str]:
        strategy = self._strategy_for(spec, round_index)
        llm_code = self._llm_code(plan, spec, benchmark_payload, strategy, goal, prior_attempts)
        if self._is_valid_code(llm_code):
            logger.info("codegen: using LLM-generated code (strategy=%s, %d lines)", strategy, len(llm_code.splitlines()))
            return strategy, llm_code or ""
        if llm_code:
            logger.warning("codegen: LLM code rejected, falling back to template (strategy=%s)", strategy)
        else:
            logger.warning("codegen: no LLM code produced, falling back to template (strategy=%s)", strategy)
        return strategy, self._fallback_code(plan, spec, benchmark_payload, strategy)

    def _fallback_code(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
        strategy: str,
    ) -> str:
        if plan.task_family == "ir_reranking":
            return self._ir_template(plan, spec, benchmark_payload, strategy)
        if plan.task_family == "tabular_classification":
            return self._tabular_template(plan, spec, benchmark_payload, strategy)
        if plan.task_family == "llm_evaluation":
            return self._llm_eval_template(plan, spec, benchmark_payload, strategy)
        return self._text_template(plan, spec, benchmark_payload, strategy)

    def _llm_eval_template(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
        strategy: str,
    ) -> str:
        dataset_json = json.dumps(benchmark_payload, ensure_ascii=False, indent=2)
        prompts_json = json.dumps(
            benchmark_payload.get("evaluation_prompts", [
                {"system": "You are a helpful assistant.", "user": "{{input}}"}
            ]),
            ensure_ascii=False, indent=2,
        )
        return f'''import json
import os
import platform
import sys
import time

DATASET = {dataset_json}
PROMPTS = {prompts_json}
PRIMARY_METRIC = "accuracy"
TITLE = {plan.title!r}
HYPOTHESIS = {spec.hypothesis!r}
STRATEGY = {strategy!r}
SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{{}}")

# --- SCHOLARFLOW_CONTRACT: do not modify lines containing SCHOLARFLOW_CONTRACT ---

def accuracy(y_true, y_pred):
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true) if y_true else 0.0


def exact_match_score(predictions, references):
    return accuracy(references, predictions)


def f1_score_single(y_true, y_pred):
    common = set(y_true.split()) & set(y_pred.split())
    if not common:
        return 0.0
    precision = len(common) / len(y_pred.split())
    recall = len(common) / len(y_true.split())
    return 2 * precision * recall / (precision + recall)


def build_prompt(template, input_text):
    """Replace {{{{input}}}} placeholder with actual input."""
    result = template
    result = result.replace("{{{{input}}}}", str(input_text))
    return result


def evaluate_system(system_fn, examples, references):
    predictions = []
    for ex in examples:
        pred = system_fn(ex)
        predictions.append(str(pred).strip().lower())
    ref_norm = [str(r).strip().lower() for r in references]
    acc = accuracy(ref_norm, predictions)
    f1 = 0.0
    if predictions and ref_norm:
        f1 = sum(f1_score_single(r, p) for r, p in zip(ref_norm, predictions)) / len(predictions)
    return {{"accuracy": acc, "f1": f1}}


def zero_shot_classifier(input_text):
    """Default baseline: returns the first label from the dataset label space."""
    labels = DATASET.get("label_space", ["unknown"])
    return labels[0]


def few_shot_classifier(input_text):
    """Few-shot baseline: uses a small number of examples for classification."""
    labels = DATASET.get("label_space", ["unknown"])
    # Simple heuristic: check if any label keyword appears in input
    text_lower = str(input_text).lower()
    for label in labels:
        if str(label).lower() in text_lower:
            return label
    return labels[0]


def rule_based_classifier(input_text):
    """Rule-based baseline: pattern matching on input."""
    labels = DATASET.get("label_space", ["unknown"])
    if not labels:
        return "unknown"
    # Map strategy to behavior
    if "keyword" in STRATEGY:
        text_lower = str(input_text).lower()
        scores = {{label: sum(1 for kw in str(label).lower().split() if kw in text_lower)
                    for label in labels}}
        return max(scores, key=scores.get) if any(scores.values()) else labels[0]
    return labels[0]


def run():
    started = time.perf_counter()
    random.seed(SEED)

    test_data = DATASET.get("test_examples", DATASET.get("examples", []))
    if not test_data:
        print("__RESULT__" + json.dumps({{"status": "failed", "summary": "No test examples found", "error": "empty dataset"}}))
        return

    inputs = [ex.get("input", ex.get("text", "")) for ex in test_data]
    references = [ex.get("label", ex.get("answer", ex.get("output", ""))) for ex in test_data]

    systems = {{
        "zero_shot": zero_shot_classifier,
        "few_shot": few_shot_classifier,
        "rule_based": rule_based_classifier,
    }}

    results = {{}}
    system_results = []
    all_tables = []
    best_system = None
    best_score = -1.0

    for name, fn in systems.items():
        metrics = evaluate_system(fn, inputs, references)
        results[name] = metrics
        acc = metrics["accuracy"]
        if acc > best_score:
            best_score = acc
            best_system = name
        system_results.append({{"system": name, "metrics": metrics, "notes": None}})

    table_rows = [[name, f"{{results[name]['accuracy']:.4f}}", f"{{results[name]['f1']:.4f}}"] for name in systems]

    artifact = {{
        "status": "done",
        "summary": f"Evaluated {{len(systems)}} LLM evaluation baselines on {{len(inputs)}} examples. Best: {{best_system}} (accuracy={{best_score:.4f}})",
        "key_findings": [
            f"Best system: {{best_system}} with accuracy={{best_score:.4f}}",
            f"Evaluated {{len(inputs)}} test examples across {{len(systems)}} systems",
        ],
        "primary_metric": PRIMARY_METRIC,
        "best_system": best_system,
        "objective_system": best_system,
        "objective_score": best_score,
        "system_results": system_results,
        "aggregate_system_results": [
            {{"system": name, "mean_metrics": results[name], "std_metrics": {{}}, "sample_count": 1}}
            for name in systems
        ],
        "per_seed_results": [],
        "sweep_results": [],
        "significance_tests": [],
        "power_analysis_notes": [],
        "negative_results": [],
        "failed_trials": [],
        "anomalous_trials": [],
        "acceptance_checks": [{{"criterion": "accuracy > 0", "passed": best_score > 0, "detail": f"Best accuracy: {{best_score:.4f}}"}}],
        "tables": [
            {{"title": "LLM Evaluation Results", "columns": ["System", "Accuracy", "F1"], "rows": table_rows}}
        ],
        "logs": None,
        "environment": {{
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "runtime_seconds": round(time.perf_counter() - started, 4),
            "task_family": "llm_evaluation",
            "strategy": STRATEGY,
            "seed": SEED,
            "sweep": SWEEP,
            "benchmark_name": DATASET.get("name"),
        }},
    }}
    print("__RESULT__" + json.dumps(artifact))


if __name__ == "__main__":
    run()
'''

    def _ir_template(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
        strategy: str,
    ) -> str:
        dataset_json = json.dumps(benchmark_payload, ensure_ascii=False, indent=2)
        return f'''import json
import math
import os
import platform
import random
import re
import sys
import time
from collections import Counter

DATASET = {dataset_json}
PRIMARY_METRIC = "mrr"
TITLE = {plan.title!r}
HYPOTHESIS = {spec.hypothesis!r}
STRATEGY = {strategy!r}
SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{{}}")


def tokenize(text):
    return re.findall(r"[a-z][a-z0-9_]+", text.lower())


def reciprocal_rank(relevant_ids, ranked_ids):
    for idx, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / idx
    return 0.0


def recall_at_1(relevant_ids, ranked_ids):
    if not ranked_ids:
        return 0.0
    return 1.0 if ranked_ids[0] in relevant_ids else 0.0


def evaluate(system_name, examples, ranking_fn):
    reciprocal_ranks = []
    recalls = []
    for example in examples:
        ranked = ranking_fn(example)
        reciprocal_ranks.append(reciprocal_rank(example["relevant_ids"], ranked))
        recalls.append(recall_at_1(example["relevant_ids"], ranked))
    return {{
        "system": system_name,
        "metrics": {{
            "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
            "recall_at_1": round(sum(recalls) / len(recalls), 4),
        }},
    }}


def random_ranker(example):
    ids = [candidate["id"] for candidate in example["candidates"]]
    rng = random.Random(SEED + len(example["query"]))
    rng.shuffle(ids)
    return ids


def overlap_score(query, text):
    q = tokenize(query)
    d = tokenize(text)
    return sum(1 for token in q if token in d)


def overlap_ranker(example):
    scored = [
        (overlap_score(example["query"], candidate["text"]), candidate["id"])
        for candidate in example["candidates"]
    ]
    return [doc_id for _, doc_id in sorted(scored, reverse=True)]


def build_idf(train, additive_smoothing):
    doc_freq = Counter()
    total_docs = 0
    for example in train:
        for candidate in example["candidates"]:
            total_docs += 1
            for token in set(tokenize(candidate["text"])):
                doc_freq[token] += 1
    return {{
        token: math.log((total_docs + additive_smoothing) / (freq + additive_smoothing)) + 1.0
        for token, freq in doc_freq.items()
    }}


def idf_ranker_factory(train, use_bigrams, additive_smoothing, bigram_bonus):
    idf = build_idf(train, additive_smoothing)
    def score(query, text):
        query_tokens = tokenize(query)
        doc_tokens = tokenize(text)
        total = sum(idf.get(token, 1.0) for token in query_tokens if token in doc_tokens)
        if use_bigrams:
            query_bigrams = set(zip(query_tokens, query_tokens[1:]))
            doc_bigrams = set(zip(doc_tokens, doc_tokens[1:]))
            total += bigram_bonus * len(query_bigrams & doc_bigrams)
        return total
    def rank(example):
        scored = [(score(example["query"], candidate["text"]), candidate["id"]) for candidate in example["candidates"]]
        return [doc_id for _, doc_id in sorted(scored, reverse=True)]
    return rank


def run():
    started = time.perf_counter()
    train = DATASET["train"]
    test = DATASET["test"]
    idf_smoothing = float(SWEEP.get("idf_smoothing", 1.0))
    bigram_bonus = float(SWEEP.get("bigram_bonus", 0.5))
    results = []

    results.append(evaluate("random_ranker", test, random_ranker))
    results.append(evaluate("overlap_ranker", test, overlap_ranker))
    candidate_system = "overlap_ranker"
    critique = "Search starts from simple lexical overlap between query and candidate text."

    if STRATEGY in {{"idf_reranker_search", "bigram_reranker_search"}}:
        idf_ranker = idf_ranker_factory(
            train,
            use_bigrams=False,
            additive_smoothing=idf_smoothing,
            bigram_bonus=bigram_bonus,
        )
        results.append(evaluate("idf_ranker", test, idf_ranker))
        candidate_system = "idf_ranker"
        critique = "The second round adds rarity-aware lexical weighting over training candidates."

    if STRATEGY == "bigram_reranker_search":
        bigram_ranker = idf_ranker_factory(
            train,
            use_bigrams=True,
            additive_smoothing=idf_smoothing,
            bigram_bonus=bigram_bonus,
        )
        results.append(evaluate("bigram_ranker", test, bigram_ranker))
        candidate_system = "bigram_ranker"
        critique = "The final round augments IDF scoring with bigram overlap for more precise reranking."

    objective = next(item for item in results if item["system"] == candidate_system)
    best = max(results, key=lambda item: item["metrics"][PRIMARY_METRIC])
    rows = [
        [item["system"], f'{{item["metrics"]["mrr"]:.4f}}', f'{{item["metrics"]["recall_at_1"]:.4f}}']
        for item in results
    ]

    artifact = {{
        "summary": (
            f'{{TITLE}} executed strategy {{STRATEGY}} on benchmark {{DATASET.get("name", "dataset")}}. '
            f'Best system: {{best["system"]}} with mrr={{best["metrics"]["mrr"]:.4f}}.'
        ),
        "primary_metric": PRIMARY_METRIC,
        "best_system": best["system"],
        "objective_system": objective["system"],
        "objective_score": objective["metrics"][PRIMARY_METRIC],
        "key_findings": [
            f'Best system: {{best["system"]}}',
            f'Search objective system: {{objective["system"]}}',
            critique,
            f'Hypothesis under test: {{HYPOTHESIS}}',
        ],
        "system_results": results,
        "tables": [
            {{
                "title": "Main Results",
                "columns": ["System", "MRR", "Recall@1"],
                "rows": rows,
            }}
        ],
        "environment": {{
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "runtime_seconds": round(time.perf_counter() - started, 4),
            "task_family": "ir_reranking",
            "strategy": STRATEGY,
            "seed": SEED,
            "sweep": SWEEP,
            "benchmark_name": DATASET.get("name"),
            "source_url": DATASET.get("source_url"),
        }},
    }}
    print("__RESULT__" + json.dumps(artifact))


if __name__ == "__main__":
    run()
'''

    def _text_template(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
        strategy: str,
    ) -> str:
        dataset_json = json.dumps(benchmark_payload, ensure_ascii=False, indent=2)
        return f'''import json
import math
import os
import platform
import re
import sys
import time
from collections import Counter, defaultdict

DATASET = {dataset_json}
PRIMARY_METRIC = "macro_f1"
TITLE = {plan.title!r}
HYPOTHESIS = {spec.hypothesis!r}
STRATEGY = {strategy!r}
SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{{}}")


def tokenize(text):
    return re.findall(r"[a-z][a-z0-9_]+", text.lower())


def to_features(text, order):
    tokens = tokenize(text)
    if order <= 1:
        return tokens
    features = list(tokens)
    for idx in range(len(tokens) - 1):
        features.append(tokens[idx] + "__" + tokens[idx + 1])
    return features


def accuracy(y_true, y_pred):
    correct = sum(1 for truth, pred in zip(y_true, y_pred) if truth == pred)
    return correct / len(y_true) if y_true else 0.0


def macro_f1(y_true, y_pred, labels):
    scores = []
    for label in labels:
        tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred == label)
        fp = sum(1 for truth, pred in zip(y_true, y_pred) if truth != label and pred == label)
        fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        if precision + recall == 0:
            scores.append(0.0)
        else:
            scores.append(2 * precision * recall / (precision + recall))
    return sum(scores) / len(scores) if scores else 0.0


def evaluate(system_name, y_true, y_pred):
    labels = sorted(set(y_true))
    return {{
        "system": system_name,
        "metrics": {{
            "accuracy": round(accuracy(y_true, y_pred), 4),
            "macro_f1": round(macro_f1(y_true, y_pred, labels), 4),
        }},
    }}


def majority_predict(train, test):
    label = Counter(item["label"] for item in train).most_common(1)[0][0]
    return [label for _ in test]


def build_keyword_map(train, top_k=8):
    manual = DATASET.get("keyword_map")
    if isinstance(manual, dict) and manual:
        return manual
    by_label = defaultdict(Counter)
    global_counter = Counter()
    for item in train:
        label = item["label"]
        tokens = tokenize(item["text"])
        global_counter.update(tokens)
        by_label[label].update(tokens)
    keyword_map = {{}}
    for label, counter in by_label.items():
        scored = []
        for token, count in counter.items():
            score = count - global_counter[token] / max(len(by_label), 1)
            scored.append((score, token))
        ranked = [token for _, token in sorted(scored, reverse=True)[:top_k]]
        keyword_map[label] = ranked
    return keyword_map


def keyword_predict(keyword_map, test):
    labels = sorted(keyword_map)
    outputs = []
    for item in test:
        tokens = tokenize(item["text"])
        counts = []
        for label in labels:
            score = sum(1 for token in tokens if token in keyword_map[label])
            counts.append((score, label))
        outputs.append(sorted(counts, key=lambda pair: (pair[0], pair[1]), reverse=True)[0][1])
    return outputs


def train_naive_bayes(train, order=1, vocab_limit=None):
    label_docs = Counter()
    label_tokens = Counter()
    token_counts = defaultdict(Counter)
    token_frequency = Counter()
    for item in train:
        label = item["label"]
        features = to_features(item["text"], order)
        label_docs[label] += 1
        label_tokens[label] += len(features)
        for token in features:
            token_counts[label][token] += 1
            token_frequency[token] += 1
    vocab = set(token_frequency)
    if vocab_limit is not None:
        vocab = set(token for token, _ in token_frequency.most_common(vocab_limit))
    return {{
        "label_docs": label_docs,
        "label_tokens": label_tokens,
        "token_counts": token_counts,
        "vocab": sorted(vocab),
        "order": order,
    }}


def predict_naive_bayes(model, text):
    tokens = [token for token in to_features(text, model["order"]) if token in model["vocab"]]
    vocab_size = max(len(model["vocab"]), 1)
    total_docs = sum(model["label_docs"].values())
    scores = {{}}
    for label, count in model["label_docs"].items():
        log_prob = math.log(count / total_docs)
        total_label_tokens = model["label_tokens"][label]
        for token in tokens:
            token_count = model["token_counts"][label][token]
            log_prob += math.log((token_count + 1) / (total_label_tokens + vocab_size))
        scores[label] = log_prob
    return max(scores.items(), key=lambda pair: pair[1])[0]


def run():
    started = time.perf_counter()
    train = DATASET["train"]
    test = DATASET["test"]
    keyword_top_k = int(SWEEP.get("keyword_top_k", 8))
    naive_bayes_order = int(SWEEP.get("naive_bayes_order", 1))
    limited_vocab_limit = int(SWEEP.get("limited_vocab_limit", max(12, len(train) // 2 + 4)))
    full_vocab_limit = SWEEP.get("full_vocab_limit")
    if full_vocab_limit is not None:
        full_vocab_limit = int(full_vocab_limit)
    y_true = [item["label"] for item in test]
    results = []

    majority = majority_predict(train, test)
    results.append(evaluate("majority", y_true, majority))

    keyword_map = build_keyword_map(train, top_k=keyword_top_k)
    keyword = keyword_predict(keyword_map, test)
    results.append(evaluate("keyword_rule", y_true, keyword))

    candidate_system = "keyword_rule"
    critique = "Search starts from a lexical heuristic baseline."

    if STRATEGY in {{"naive_bayes_limited_vocab_search", "naive_bayes_search"}}:
        limited_model = train_naive_bayes(train, order=naive_bayes_order, vocab_limit=limited_vocab_limit)
        limited_pred = [predict_naive_bayes(limited_model, item["text"]) for item in test]
        results.append(evaluate("naive_bayes_limited_vocab", y_true, limited_pred))
        candidate_system = "naive_bayes_limited_vocab"
        critique = "The second round adds a learned lexical model but restricts vocabulary for fast repairable training."

    if STRATEGY == "naive_bayes_search":
        full_model = train_naive_bayes(train, order=naive_bayes_order, vocab_limit=full_vocab_limit)
        full_pred = [predict_naive_bayes(full_model, item["text"]) for item in test]
        results.append(evaluate("naive_bayes", y_true, full_pred))
        candidate_system = "naive_bayes"
        critique = "The final search round removes the vocabulary cap to recover full lexical coverage."

    objective = next(item for item in results if item["system"] == candidate_system)
    best = max(results, key=lambda item: item["metrics"][PRIMARY_METRIC])
    rows = [
        [item["system"], f'{{item["metrics"]["accuracy"]:.4f}}', f'{{item["metrics"]["macro_f1"]:.4f}}']
        for item in results
    ]

    artifact = {{
        "summary": (
            f'{{TITLE}} executed strategy {{STRATEGY}} on benchmark {{DATASET.get("name", "dataset")}}. '
            f'Best system: {{best["system"]}} with macro_f1={{best["metrics"]["macro_f1"]:.4f}}.'
        ),
        "primary_metric": PRIMARY_METRIC,
        "best_system": best["system"],
        "objective_system": objective["system"],
        "objective_score": objective["metrics"][PRIMARY_METRIC],
        "key_findings": [
            f'Best system: {{best["system"]}}',
            f'Search objective system: {{objective["system"]}}',
            critique,
            f'Hypothesis under test: {{HYPOTHESIS}}',
        ],
        "system_results": results,
        "tables": [
            {{
                "title": "Main Results",
                "columns": ["System", "Accuracy", "Macro F1"],
                "rows": rows,
            }}
        ],
        "environment": {{
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "runtime_seconds": round(time.perf_counter() - started, 4),
            "task_family": "text_classification",
            "strategy": STRATEGY,
            "seed": SEED,
            "sweep": SWEEP,
            "benchmark_name": DATASET.get("name"),
            "source_url": DATASET.get("source_url"),
        }},
    }}
    print("__RESULT__" + json.dumps(artifact))


if __name__ == "__main__":
    run()
'''

    def _tabular_template(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
        strategy: str,
    ) -> str:
        dataset_json = json.dumps(benchmark_payload, ensure_ascii=False, indent=2)
        return f'''import json
import os
import platform
import sys
import time
from collections import Counter

DATASET = {dataset_json}
PRIMARY_METRIC = "macro_f1"
TITLE = {plan.title!r}
HYPOTHESIS = {spec.hypothesis!r}
STRATEGY = {strategy!r}
SEED = int(os.environ.get("SCHOLARFLOW_SEED", "0") or 0)
SWEEP = json.loads(os.environ.get("SCHOLARFLOW_SWEEP_JSON") or "{{}}")


def accuracy(y_true, y_pred):
    correct = sum(1 for truth, pred in zip(y_true, y_pred) if truth == pred)
    return correct / len(y_true) if y_true else 0.0


def macro_f1(y_true, y_pred, labels):
    scores = []
    for label in labels:
        tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred == label)
        fp = sum(1 for truth, pred in zip(y_true, y_pred) if truth != label and pred == label)
        fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        if precision + recall == 0:
            scores.append(0.0)
        else:
            scores.append(2 * precision * recall / (precision + recall))
    return sum(scores) / len(scores) if scores else 0.0


def evaluate(system_name, y_true, y_pred):
    labels = sorted(set(y_true))
    return {{
        "system": system_name,
        "metrics": {{
            "accuracy": round(accuracy(y_true, y_pred), 4),
            "macro_f1": round(macro_f1(y_true, y_pred, labels), 4),
        }},
    }}


def majority_predict(train, test):
    label = Counter(item["label"] for item in train).most_common(1)[0][0]
    return [label for _ in test]


def threshold_rule_search(train, test):
    best = (0.0, 0, 0.0, 1)
    labels = sorted({{item["label"] for item in train}})
    positive = labels[-1]
    for feature_index in range(len(train[0]["features"])):
        values = sorted({{row["features"][feature_index] for row in train}})
        for threshold in values:
            for direction in (-1, 1):
                preds = []
                for row in train:
                    score = row["features"][feature_index] * direction
                    thresh = threshold * direction
                    preds.append(positive if score >= thresh else labels[0])
                score = accuracy([row["label"] for row in train], preds)
                if score >= best[0]:
                    best = (score, feature_index, threshold, direction)
    _, feature_index, threshold, direction = best
    preds = []
    for row in test:
        score = row["features"][feature_index] * direction
        thresh = threshold * direction
        preds.append(positive if score >= thresh else labels[0])
    return preds


def standardize(train_rows, rows):
    columns = list(zip(*(row["features"] for row in train_rows)))
    means = [sum(col) / len(col) for col in columns]
    stds = []
    for idx, col in enumerate(columns):
        variance = sum((value - means[idx]) ** 2 for value in col) / len(col)
        stds.append(variance ** 0.5 or 1.0)
    transformed = []
    for row in rows:
        features = [(value - means[idx]) / stds[idx] for idx, value in enumerate(row["features"])]
        transformed.append({{"features": features, "label": row["label"]}})
    return transformed


def train_perceptron(train_rows, scaled, epochs, learning_rate):
    rows = standardize(train_rows, train_rows) if scaled else train_rows
    weights = [0.0 for _ in rows[0]["features"]]
    bias = 0.0
    ordered_rows = list(rows)
    if ordered_rows:
        rotation = SEED % len(ordered_rows)
        ordered_rows = ordered_rows[rotation:] + ordered_rows[:rotation]
    for _ in range(epochs):
        for row in ordered_rows:
            target = 1 if row["label"] == sorted({{r["label"] for r in train_rows}})[-1] else -1
            margin = sum(weight * value for weight, value in zip(weights, row["features"])) + bias
            pred = 1 if margin >= 0 else -1
            if pred != target:
                for idx, value in enumerate(row["features"]):
                    weights[idx] += learning_rate * target * value
                bias += learning_rate * target
    return weights, bias


def predict_perceptron(train_rows, test_rows, scaled, epochs, learning_rate):
    weights, bias = train_perceptron(train_rows, scaled, epochs, learning_rate)
    rows = standardize(train_rows, test_rows) if scaled else test_rows
    positive = sorted({{row["label"] for row in train_rows}})[-1]
    negative = sorted({{row["label"] for row in train_rows}})[0]
    outputs = []
    for row in rows:
        margin = sum(weight * value for weight, value in zip(weights, row["features"])) + bias
        outputs.append(positive if margin >= 0 else negative)
    return outputs


def run():
    started = time.perf_counter()
    train = DATASET["train"]
    test = DATASET["test"]
    unscaled_epochs = int(SWEEP.get("perceptron_epochs", 15))
    scaled_epochs = int(SWEEP.get("perceptron_scaled_epochs", 20))
    learning_rate = float(SWEEP.get("perceptron_learning_rate", 1.0))
    y_true = [item["label"] for item in test]
    results = []

    majority = majority_predict(train, test)
    results.append(evaluate("majority", y_true, majority))

    threshold = threshold_rule_search(train, test)
    results.append(evaluate("threshold_rule", y_true, threshold))
    candidate_system = "threshold_rule"
    critique = "Search starts from a tuned one-feature threshold baseline."

    if STRATEGY in {{"perceptron_unscaled_search", "perceptron_scaled_search"}}:
        unscaled = predict_perceptron(train, test, False, epochs=unscaled_epochs, learning_rate=learning_rate)
        results.append(evaluate("perceptron_unscaled", y_true, unscaled))
        candidate_system = "perceptron_unscaled"
        critique = "The second round adds a learned linear model without feature scaling."

    if STRATEGY == "perceptron_scaled_search":
        scaled = predict_perceptron(train, test, True, epochs=scaled_epochs, learning_rate=learning_rate)
        results.append(evaluate("perceptron_scaled", y_true, scaled))
        candidate_system = "perceptron_scaled"
        critique = "The final search round repairs the linear model with feature scaling and longer training."

    objective = next(item for item in results if item["system"] == candidate_system)
    best = max(results, key=lambda item: item["metrics"][PRIMARY_METRIC])
    rows = [
        [item["system"], f'{{item["metrics"]["accuracy"]:.4f}}', f'{{item["metrics"]["macro_f1"]:.4f}}']
        for item in results
    ]

    artifact = {{
        "summary": (
            f'{{TITLE}} executed strategy {{STRATEGY}} on benchmark {{DATASET.get("name", "dataset")}}. '
            f'Best system: {{best["system"]}} with macro_f1={{best["metrics"]["macro_f1"]:.4f}}.'
        ),
        "primary_metric": PRIMARY_METRIC,
        "best_system": best["system"],
        "objective_system": objective["system"],
        "objective_score": objective["metrics"][PRIMARY_METRIC],
        "key_findings": [
            f'Best system: {{best["system"]}}',
            f'Search objective system: {{objective["system"]}}',
            critique,
            f'Hypothesis under test: {{HYPOTHESIS}}',
        ],
        "system_results": results,
        "tables": [
            {{
                "title": "Main Results",
                "columns": ["System", "Accuracy", "Macro F1"],
                "rows": rows,
            }}
        ],
        "environment": {{
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "runtime_seconds": round(time.perf_counter() - started, 4),
            "task_family": "tabular_classification",
            "strategy": STRATEGY,
            "seed": SEED,
            "sweep": SWEEP,
            "benchmark_name": DATASET.get("name"),
            "source_url": DATASET.get("source_url"),
            "feature_names": DATASET.get("feature_names"),
        }},
    }}
    print("__RESULT__" + json.dumps(artifact))


if __name__ == "__main__":
    run()
'''
