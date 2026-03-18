from __future__ import annotations

import json
import re
from typing import Any

from schemas.autoresearch import ExperimentSpec, ResearchPlan
from services.autoresearch.benchmarks import benchmark_payload_for
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

    def _llm_code(self, plan: ResearchPlan, spec: ExperimentSpec, benchmark_payload: dict[str, Any]) -> str | None:
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

    def generate(self, plan: ResearchPlan, spec: ExperimentSpec) -> str:
        benchmark_payload = benchmark_payload_for(plan.task_family)
        llm_code = self._llm_code(plan, spec, benchmark_payload)
        if self._is_valid_code(llm_code):
            return llm_code or ""
        return self._fallback_code(plan, spec, benchmark_payload)

    def _fallback_code(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
    ) -> str:
        if plan.task_family == "tabular_classification":
            return self._tabular_template(plan, spec, benchmark_payload)
        return self._text_template(plan, spec, benchmark_payload)

    def _text_template(
        self,
        plan: ResearchPlan,
        spec: ExperimentSpec,
        benchmark_payload: dict[str, Any],
    ) -> str:
        dataset_json = json.dumps(benchmark_payload["dataset"], ensure_ascii=False, indent=2)
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


def tokenize(text):
    return re.findall(r"[a-z_]+", text.lower())


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


def keyword_predict(keyword_map, test):
    labels = sorted(keyword_map)
    outputs = []
    for item in test:
        tokens = tokenize(item["text"])
        counts = []
        for label in labels:
            score = sum(1 for token in tokens if token in keyword_map[label])
            counts.append((score, label))
        best = sorted(counts, key=lambda pair: (pair[0], pair[1]), reverse=True)[0]
        outputs.append(best[1])
    return outputs


def train_naive_bayes(train, vocab_limit=None):
    label_docs = Counter()
    label_tokens = Counter()
    token_counts = defaultdict(Counter)
    token_frequency = Counter()
    for item in train:
        label = item["label"]
        label_docs[label] += 1
        tokens = tokenize(item["text"])
        label_tokens[label] += len(tokens)
        for token in tokens:
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
    }}


def predict_naive_bayes(model, text):
    tokens = [token for token in tokenize(text) if token in model["vocab"]]
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

    keyword = keyword_predict(DATASET["keyword_map"], test)
    results.append(evaluate("keyword_rule", y_true, keyword))

    model = train_naive_bayes(train)
    naive_bayes = [predict_naive_bayes(model, item["text"]) for item in test]
    results.append(evaluate("naive_bayes", y_true, naive_bayes))

    small_model = train_naive_bayes(train, vocab_limit=18)
    small_vocab = [predict_naive_bayes(small_model, item["text"]) for item in test]
    results.append(evaluate("naive_bayes_limited_vocab", y_true, small_vocab))

    best = max(results, key=lambda item: item["metrics"][PRIMARY_METRIC])
    rows = []
    for item in results:
        rows.append([
            item["system"],
            f'{{item["metrics"]["accuracy"]:.4f}}',
            f'{{item["metrics"]["macro_f1"]:.4f}}',
        ])

    artifact = {{
        "summary": (
            f'{{TITLE}} executed on a built in text classification benchmark. '
            f'The best system was {{best["system"]}} with macro_f1='
            f'{{best["metrics"]["macro_f1"]:.4f}}.'
        ),
        "primary_metric": PRIMARY_METRIC,
        "best_system": best["system"],
        "key_findings": [
            f'Best system: {{best["system"]}}',
            f'Hypothesis under test: {{HYPOTHESIS}}',
            "The limited vocabulary ablation measures whether lexical coverage matters.",
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
    ) -> str:
        dataset_json = json.dumps(benchmark_payload["dataset"], ensure_ascii=False, indent=2)
        return f'''import json
import platform
import sys
import time
from collections import Counter

DATASET = {dataset_json}
PRIMARY_METRIC = "macro_f1"
TITLE = {plan.title!r}
HYPOTHESIS = {spec.hypothesis!r}


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


def threshold_rule(test):
    outputs = []
    for item in test:
        learning_rate, batch_size, dropout, depth, residual = item["features"]
        stable = learning_rate <= 0.008 and batch_size >= 32 and residual == 1 and depth <= 12
        outputs.append("stable" if stable else "unstable")
    return outputs


def standardize(train_rows, rows):
    columns = list(zip(*(row["features"] for row in train_rows)))
    means = [sum(col) / len(col) for col in columns]
    stds = []
    for idx, col in enumerate(columns):
        variance = sum((value - means[idx]) ** 2 for value in col) / len(col)
        stds.append(variance ** 0.5 or 1.0)
    transformed = []
    for row in rows:
        features = [
            (value - means[idx]) / stds[idx]
            for idx, value in enumerate(row["features"])
        ]
        transformed.append({{"features": features, "label": row["label"]}})
    return transformed


def train_perceptron(train_rows, scaled):
    rows = standardize(train_rows, train_rows) if scaled else train_rows
    weights = [0.0 for _ in rows[0]["features"]]
    bias = 0.0
    for _ in range(20):
        for row in rows:
            features = row["features"]
            target = 1 if row["label"] == "stable" else -1
            margin = sum(weight * value for weight, value in zip(weights, features)) + bias
            pred = 1 if margin >= 0 else -1
            if pred != target:
                for idx, value in enumerate(features):
                    weights[idx] += target * value
                bias += target
    return weights, bias


def predict_perceptron(train_rows, test_rows, scaled):
    weights, bias = train_perceptron(train_rows, scaled)
    rows = standardize(train_rows, test_rows) if scaled else test_rows
    outputs = []
    for row in rows:
        margin = sum(weight * value for weight, value in zip(weights, row["features"])) + bias
        outputs.append("stable" if margin >= 0 else "unstable")
    return outputs


def run():
    started = time.perf_counter()
    train = DATASET["train"]
    test = DATASET["test"]
    y_true = [item["label"] for item in test]
    results = []

    majority = majority_predict(train, test)
    results.append(evaluate("majority", y_true, majority))

    threshold = threshold_rule(test)
    results.append(evaluate("threshold_rule", y_true, threshold))

    perceptron_scaled = predict_perceptron(train, test, True)
    results.append(evaluate("perceptron_scaled", y_true, perceptron_scaled))

    perceptron_unscaled = predict_perceptron(train, test, False)
    results.append(evaluate("perceptron_unscaled", y_true, perceptron_unscaled))

    best = max(results, key=lambda item: item["metrics"][PRIMARY_METRIC])
    rows = []
    for item in results:
        rows.append([
            item["system"],
            f'{{item["metrics"]["accuracy"]:.4f}}',
            f'{{item["metrics"]["macro_f1"]:.4f}}',
        ])

    artifact = {{
        "summary": (
            f'{{TITLE}} executed on a built in tabular classification benchmark. '
            f'The best system was {{best["system"]}} with macro_f1='
            f'{{best["metrics"]["macro_f1"]:.4f}}.'
        ),
        "primary_metric": PRIMARY_METRIC,
        "best_system": best["system"],
        "key_findings": [
            f'Best system: {{best["system"]}}',
            f'Hypothesis under test: {{HYPOTHESIS}}',
            "The unscaled perceptron serves as the normalization ablation.",
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
        }},
    }}
    print("__RESULT__" + json.dumps(artifact))


if __name__ == "__main__":
    run()
'''
