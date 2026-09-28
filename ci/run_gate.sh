#!/usr/bin/env bash
# ci/run_gate.sh — what the CI job runs (P3-10, DEC-088). Runnable locally too.
#
#   ci/run_gate.sh <base-ref> [approved]
#
# 1. Decide whether the change can affect answer quality (pipeline paths). If not, report
#    "eval skipped: no pipeline change" and succeed.
# 2. Refuse to report a verdict without the OpenRouter key ("not verified" — a fork PR, or
#    a missing secret): exit 1, which blocks merge.
# 3. Print the cost estimate before any model call, then run `rag ci-eval`.
# 4. Map its exit code to a status: 0 PASS · 1 FAIL (quality) · 2 ERROR (infrastructure,
#    never a quality result) · 3 NEEDS APPROVAL (add the `eval-approved` label).
# Writes ci/out/status and appends to $GITHUB_STEP_SUMMARY when set.
set -uo pipefail
BASE="${1:-origin/main}"
APPROVED="${2:-}"
OUT=ci/out
mkdir -p "$OUT"
rm -f "$OUT/ci_eval.md" "$OUT/ci_eval.json" "$OUT/status"   # never report a stale verdict
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

# The paths whose change can move a gated metric. Docs never can.
PIPELINE_RE='^(rag/|configs/|prompts/|eval/golden/|data/authored/|ci/gate\.yaml|ci/baseline\.json|pyproject\.toml|uv\.lock)'

report() {  # status, message
  echo "$1" > "$OUT/status"
  printf '## RAG quality gate — %s\n\n%s\n' "$1" "$2" | tee "$OUT/ci_eval_status.md" >> "$SUMMARY"
  echo "$1: $2"
}

changed=$(git diff --name-only "$BASE"...HEAD 2>/dev/null | grep -E "$PIPELINE_RE" || true)
if [[ -z "$changed" && "${FORCE_EVAL:-}" != "1" ]]; then
  report "SKIPPED" "eval skipped: no pipeline change (docs-only or non-pipeline paths vs \`$BASE\`)."
  exit 0
fi
echo "pipeline paths changed:"; echo "$changed" | sed 's/^/  /'

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  report "NOT VERIFIED" "No OpenRouter key in this job (a fork PR, or the \`OPENROUTER_API_KEY\` secret is not set). No verdict can be given, so merge is blocked."
  exit 1
fi

echo "::group::cost estimate (before any model call)"
rag ci-eval --estimate-only || { report "ERROR" "cost estimate failed — infrastructure, not a quality result."; exit 2; }
echo "::endgroup::"

args=(--out "$OUT")
[[ -n "$APPROVED" ]] && args+=(--approve-cost "$APPROVED")
rag ci-eval "${args[@]}"
code=$?
case $code in
  0) status=PASS ;;
  1) status=FAIL ;;
  3) status="NEEDS APPROVAL" ;;
  *) status=ERROR ;;
esac
echo "$status" > "$OUT/status"
if [[ -f "$OUT/ci_eval.md" && $code -le 2 ]]; then
  cat "$OUT/ci_eval.md" >> "$SUMMARY"
elif [[ $code == 3 ]]; then
  report "NEEDS APPROVAL" "The estimate is above \`ci_budget_usd\` in ci/gate.yaml. A maintainer adds the \`eval-approved\` label to re-run with approval."
else
  report "ERROR" "rag ci-eval exited $code — infrastructure or configuration, not a quality result (not verified)."
fi
exit $code
