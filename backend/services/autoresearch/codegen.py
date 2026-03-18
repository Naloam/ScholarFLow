from __future__ import annotations

import json
import re
from typing import Any

from schemas.autoresearch import ExperimentAttempt, ExperimentSpec, ResearchPlan
from services.llm.client import chat
from services.llm.prompting import load_prompt


PROMPT_PATH = "backend/prompts/autoresearch/codegen/v0.1.0.md"


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
            return False
        try:
            compile(code, "<autorresearch>", "exec")
        except Exception:
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
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                ]
            )
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            return self._extract_code(content)
        except Exception:
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
            return strategy, llm_code or ""
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
        return self._text_template(plan, spec, benchmark_payload, strategy)

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
import platform
import re
import sys
import time
from collections import Counter

DATASET = {dataset_json}
PRIMARY_METRIC = "mrr"
TITLE = {plan.title!r}
HYPOTHESIS = {spec.hypothesis!r}
STRATEGY = {strategy!r}


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
    return [candidate["id"] for candidate in example["candidates"]]


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


def build_idf(train):
    doc_freq = Counter()
    total_docs = 0
    for example in train:
        for candidate in example["candidates"]:
            total_docs += 1
            for token in set(tokenize(candidate["text"])):
                doc_freq[token] += 1
    return {{
        token: math.log((total_docs + 1) / (freq + 1)) + 1.0
        for token, freq in doc_freq.items()
    }}


def idf_ranker_factory(train, use_bigrams):
    idf = build_idf(train)
    def score(query, text):
        query_tokens = tokenize(query)
        doc_tokens = tokenize(text)
        total = sum(idf.get(token, 1.0) for token in query_tokens if token in doc_tokens)
        if use_bigrams:
            query_bigrams = set(zip(query_tokens, query_tokens[1:]))
            doc_bigrams = set(zip(doc_tokens, doc_tokens[1:]))
            total += 0.5 * len(query_bigrams & doc_bigrams)
        return total
    def rank(example):
        scored = [(score(example["query"], candidate["text"]), candidate["id"]) for candidate in example["candidates"]]
        return [doc_id for _, doc_id in sorted(scored, reverse=True)]
    return rank


def run():
    started = time.perf_counter()
    train = DATASET["train"]
    test = DATASET["test"]
    results = []

    results.append(evaluate("random_ranker", test, random_ranker))
    results.append(evaluate("overlap_ranker", test, overlap_ranker))
    candidate_system = "overlap_ranker"
    critique = "Search starts from simple lexical overlap between query and candidate text."

    if STRATEGY in {{"idf_reranker_search", "bigram_reranker_search"}}:
        idf_ranker = idf_ranker_factory(train, use_bigrams=False)
        results.append(evaluate("idf_ranker", test, idf_ranker))
        candidate_system = "idf_ranker"
        critique = "The second round adds rarity-aware lexical weighting over training candidates."

    if STRATEGY == "bigram_reranker_search":
        bigram_ranker = idf_ranker_factory(train, use_bigrams=True)
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
    y_true = [item["label"] for item in test]
    results = []

    majority = majority_predict(train, test)
    results.append(evaluate("majority", y_true, majority))

    keyword_map = build_keyword_map(train)
    keyword = keyword_predict(keyword_map, test)
    results.append(evaluate("keyword_rule", y_true, keyword))

    candidate_system = "keyword_rule"
    critique = "Search starts from a lexical heuristic baseline."

    if STRATEGY in {{"naive_bayes_limited_vocab_search", "naive_bayes_search"}}:
        limited_model = train_naive_bayes(train, order=1, vocab_limit=max(12, len(keyword_map) * 4))
        limited_pred = [predict_naive_bayes(limited_model, item["text"]) for item in test]
        results.append(evaluate("naive_bayes_limited_vocab", y_true, limited_pred))
        candidate_system = "naive_bayes_limited_vocab"
        critique = "The second round adds a learned lexical model but restricts vocabulary for fast repairable training."

    if STRATEGY == "naive_bayes_search":
        full_model = train_naive_bayes(train, order=1, vocab_limit=None)
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
import platform
import sys
import time
from collections import Counter

DATASET = {dataset_json}
PRIMARY_METRIC = "macro_f1"
TITLE = {plan.title!r}
HYPOTHESIS = {spec.hypothesis!r}
STRATEGY = {strategy!r}


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


def train_perceptron(train_rows, scaled, epochs):
    rows = standardize(train_rows, train_rows) if scaled else train_rows
    weights = [0.0 for _ in rows[0]["features"]]
    bias = 0.0
    for _ in range(epochs):
        for row in rows:
            target = 1 if row["label"] == sorted({{r["label"] for r in train_rows}})[-1] else -1
            margin = sum(weight * value for weight, value in zip(weights, row["features"])) + bias
            pred = 1 if margin >= 0 else -1
            if pred != target:
                for idx, value in enumerate(row["features"]):
                    weights[idx] += target * value
                bias += target
    return weights, bias


def predict_perceptron(train_rows, test_rows, scaled, epochs):
    weights, bias = train_perceptron(train_rows, scaled, epochs)
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
    y_true = [item["label"] for item in test]
    results = []

    majority = majority_predict(train, test)
    results.append(evaluate("majority", y_true, majority))

    threshold = threshold_rule_search(train, test)
    results.append(evaluate("threshold_rule", y_true, threshold))
    candidate_system = "threshold_rule"
    critique = "Search starts from a tuned one-feature threshold baseline."

    if STRATEGY in {{"perceptron_unscaled_search", "perceptron_scaled_search"}}:
        unscaled = predict_perceptron(train, test, False, epochs=15)
        results.append(evaluate("perceptron_unscaled", y_true, unscaled))
        candidate_system = "perceptron_unscaled"
        critique = "The second round adds a learned linear model without feature scaling."

    if STRATEGY == "perceptron_scaled_search":
        scaled = predict_perceptron(train, test, True, epochs=20)
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
            "benchmark_name": DATASET.get("name"),
            "source_url": DATASET.get("source_url"),
            "feature_names": DATASET.get("feature_names"),
        }},
    }}
    print("__RESULT__" + json.dumps(artifact))


if __name__ == "__main__":
    run()
'''
