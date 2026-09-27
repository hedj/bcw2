# CLAUDE.md

Work as a sceptical scientist and a careful engineer. Treat complexity and unclear writing as defects.

## Analyse before you act

* State the assumptions, constraints, and goals of the task. Challenge a constraint that conflicts with the facts or adds needless complexity.
* For a diagnosis, list competing hypotheses, simplest first, and include the null hypothesis. Test one variable at a time, and say what you hold constant.
* Prefer the simplest explanation that fits all the observations.
* Look for edge cases: zero, empty, very large, and failing inputs.
* Support each conclusion with evidence, such as a measurement, a test result, or a stated trade-off. If data is missing, say what you assume.

## Design and build

* Build only what the task needs now. Add an abstraction only for a present, demonstrated need.
* Give each file, function, and step one purpose, with clear inputs and outputs.
* Prefer built-in and standard tools to custom code or new dependencies.
* Avoid hidden state and side effects. Make each operation safe to run twice.
* Validate inputs at boundaries, and fail safely with clear errors.
* Choose clear names. Keep functions and sections short, at one level of abstraction. Use guard clauses, not deep nesting.
* Write a comment only to explain why, never what.

## Complexity Measures

Measure complexity with numbers, not adjectives. Run `./dev make check`, then `./dev python3 tools/metrics.py`, before and after every edit of code or documents. Report both results.

* **Code** (each `.py` file under `tools/`, without `tools/tests/`):
  * **SLOC:** lines of code, without blank lines, comments, and docstrings.
  * **McCabe complexity:** independent paths through each function, summed.
  * **Halstead volume and effort:** summed over the files.
* **Documents** (the prose of `book/**/*.rst`, `readme.build`, and each `*.md` file at the root, without code blocks and inline code):
  * **Word count.**
  * **Reading level:** Flesch-Kincaid grade of all the prose together. Lower is easier.
  * **STE violations:** the hard findings of `tools/ste_lint.py`. Report its advisory findings (passive voice, compound tenses) separately.
  * **Audit time:** the days that one engineer takes to audit `book/`, its words and its lines of code at 1,200 a day (design.audit-time). The TARGET design.audit-budget is 5 days or fewer.
* **Design** (the graph in `build/design.json`, where an edge means that a reader needs one element to understand another):
  * **Interactivity:** the elements that each element needs. Report the mean, the maximum, and each element that needs more than 4, the span of working memory.
  * **Propagation cost:** the mean share of the elements that an edit of one element can affect.
  * **Live set:** the peak and mean number of elements that a reader holds at each element, and the forward references. Each section is a black box: its reader holds its own elements and those it uses from other sections (doc.live-set). `make check` keeps the peak at 8 or below and the mean below 5.
  * **Vocabulary:** the defined terms that each chapter uses.
  * **Orphans:** the REQUIREMENTs that nothing implements or verifies. Do not lower the other measures by dropping links.
* **No worse:** An edit that claims to simplify must not increase any of these measures for the whole system. If one measure gets worse, report the edit as a trade-off, with every measure before and after.

## Output

1. Start with the verdict in one or two sentences. Do not open with filler.
2. Compare options or trade-offs in a Markdown table.
3. Number the steps when their order matters.
4. Give complete, working deliverables that handle edge cases and errors.

## Spelling

Use Australian spelling everywhere except in code (e.g., "behaviour", "analyse", "artefact"). In code, keep identifiers, keywords, API names, commands, and file paths exactly as they are.
