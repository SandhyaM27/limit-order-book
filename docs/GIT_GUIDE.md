# Git & GitHub Guide

## One-time setup
```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
cd limit-order-book
git init -b main
git add . && git status          # check nothing unwanted (.venv, __pycache__) is staged
git commit -m "chore: initial project scaffold"
```

## Recommended commit history (small, meaningful, one idea each)
1. `chore: project scaffold, pyproject, .gitignore`
2. `feat(models): Order/Trade dataclasses with validation` (+ tests)
3. `feat(book): OrderBook with price levels, heaps, lazy cancel` (+ tests)
4. `feat(engine): price-time priority matching` (+ tests)
5. `feat(sim): Poisson order-flow simulator`
6. `feat(analytics): spread, imbalance, VWAP, slippage, impact`
7. `feat(dashboard): Streamlit dashboard`
8. `perf: benchmark script`
9. `docs: README, interview prep`

Style: `type(scope): imperative summary` (feat, fix, test, docs, refactor, perf, chore).

## Branching
```bash
git switch -c feature/order-modification
# work, commit
git switch main && git merge --no-ff feature/order-modification
git branch -d feature/order-modification
```
Rule: `main` always passes `pytest`. Do risky work on a branch.

## GitHub
```bash
# create an EMPTY repo on github.com (no README), then:
git remote add origin git@github.com:<you>/limit-order-book.git
git push -u origin main
```
Organisation tips: pin the repo; add topics (`python`, `market-microstructure`,
`order-book`); put the benchmark table and a dashboard screenshot in the README;
add a GitHub Actions workflow running `pytest` (`.github/workflows/ci.yml`);
open Issues for future improvements and use PRs even when working alone.

Minimal CI:
```yaml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install -e ".[dev]"
      - run: pytest -q
```
