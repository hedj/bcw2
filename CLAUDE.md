# Working Method: Scientific and Engineering Practice

These rules apply to every task in this repository, as the Proportionality section specifies.

## Terms
- Imperative instructions and rules with "must" are mandatory.
- A **work commit** is a commit on your local branch while you work. A work commit can fail the tests.
- To **publish** is to push commits, or to hand them to a human at the end of the task.
- A **published commit** is a commit that you publish.
- The **base commit** is the commit on which your task starts.
- A **result** is the outcome of running code, a test, or a measurement.
- An **experiment** is a run of code or a test that tests a prediction.
- A **code location** is one file and one continuous line range in that file.
- A **single-cause hypothesis** blames one code location. A **multi-cause hypothesis** blames more than one.
- **Shared history** is published commits, commits made by others, branches, and tags.
- An **existing failure** is a test failure that also occurs on the base commit.
- A bug is **fixed** when its test passes and the full test suite has no new failures.
- The **current session** is the conversation that contains the current task.
- An action is **irreversible** if you cannot undo it with the tools in the current session.
- Examples of irreversible actions: deleting data outside version control, deploying, sending messages, and publishing packages.
- A push is not irreversible. To undo a push, push a commit that `git revert` creates.
- A **public interface** is an API, command, file format, or configuration that something outside the repository uses.
- **Complexity** is the set of concepts that a reader must understand to change the repository safely.
- A **concept** is one named thing that a reader must know.
- Concepts in code include functions, classes, parameters, branches, special cases, configuration options, layers of indirection, and copies of the same logic.
- Concepts in interfaces include each command, option, file format field, build output, and rule of a specification. A REQUIREMENT is a rule of a specification.
- A test is not a concept.
- A **mechanism** is a distinct way that the repository does one kind of job. For example, two ways to give the PARAMETER values to a tool are two mechanisms.
- The **system** is every file under version control, except generated files and vendored files.
- The **metrics** of the system are the four values that `tools/metrics.py` prints. They count the code of the system without its tests.
  - Lines of code: without blank lines, comments, and docstrings.
  - McCabe complexity: the number of independent paths through each function, summed.
  - Halstead volume.
  - Halstead effort.
- The **measures** of complexity are the number of concepts, the number of mechanisms, and the four metrics.
- Measure complexity over the whole system. An edit that moves complexity from one file to another does not reduce it.
- The task neighbourhood still limits where to look for candidates and where to make them (see sections 11.2 and 11.3).
- A **simplification** is an edit that removes at least one concept, does not increase the number of mechanisms, and makes no metric larger (Occam's razor). Renames, reformatting, and moves alone are not simplifications.
- A simplification adds no concept, with two exceptions:
  - It can replace two or more mechanisms with one new mechanism. The concepts of that new mechanism are then allowed.
  - It can replace one mechanism with one new mechanism, if two or more other measures improve and no measure worsens.
- An edit that breaks one of these conditions is not a simplification. Report it as a change, with every measure before and after.
- A **generalisation** is a simplification that replaces two or more similar code paths with one code path. The one path can be one of the existing paths or a new path.
- **Replaced code** is code that serves only the state before a feature, and that the feature makes unreachable. Its removal is part of the feature, not a simplification.
- An edit is **behaviour-preserving** if it changes no output, error, side effect, or public interface.
- A performance change smaller than the spread across runs (see section 5) does not count as a change.
- A simplification has **functionality loss** if it is not behaviour-preserving.
- A **characterisation test** records what code does now, correct or not.
- The **task neighbourhood** is the code that the task reads or modifies, plus the code that directly calls it or that it directly calls.

## Proportionality
- A task is **read-only** if it modifies no files.
- State at the start whether the task is read-only.
- Read-only tasks skip the restatement (section 1) and sections 2, 4, 6, 7, 11.1, 11.3, and 11.4.
- Read-only tasks apply sections 11.2 and 11.5. They find and propose simplifications, but do not make them.
- If a read-only task starts to modify files, apply all rules from that point.

## Precedence
- Two rules conflict when no single action can follow both.
- An explicit instruction from the human for the current task takes precedence over this file. Exception: section 8.
- Between sections, apply the rule from the section that comes first in this order.
- Section order: 10, 7, 8, 6, 2, 5, 3, 4, 1, 11, 9.
- If two rules in the same section conflict, stop and ask (see section 10).
- Report every conflict that you resolve. State the two rules and the rule that applied.

## 1. Understand before acting
- Restate the task in one or two sentences before you start.
- Separate what you **know** (observed directly), what you **infer** (reasoned from evidence), and what you **assume** (unverified).
- In your reports, label inferred and assumed claims. An unlabeled claim is a known claim.

## 2. Observe and reproduce
- For bugs: reproduce the failure before you modify anything.
- Record the exact command, the input, and the output. Record the state (see section 8).
- If you cannot reproduce the failure, say so. Do not fix a bug that you have not observed.
- A failing run is an observation. A test that exposes the bug is also an observation.
- For bugs found by reading code, write that test first.
- Fix one bug at a time. Do not modify code for another bug until the current bug is fixed.
- Commit the fix and its test as a work commit before you start another bug.
- If you find another bug during a fix, record it.
- If you find complexity to remove during a fix, record it as a candidate (see section 11.2).
- If the cause of a bug is complexity (for example, two copies of logic that drifted apart), say so in the report.

## 3. Form and test hypotheses
- Before you fix a bug, write down one or more hypotheses: candidate explanations for the behavior.
- Each hypothesis must name the code locations that it blames.
- Test single-cause hypotheses before multi-cause hypotheses.
- For each hypothesis, state a prediction: "If X is the cause, then Y will happen when I do Z."
- Before each experiment, write down the outcome that would reject each hypothesis.
- Before you fix a bug, run at least one experiment that tests a prediction.
- Record the prediction, the outcome, and whether they match.
- Reject every hypothesis whose rejection outcome occurs.
- Record every difference between two runs that you compare.
- Do not report a cause unless an experiment tested its prediction and the outcome matched.

## 4. Do not hide failures
- When a test, a build, or a run fails, do not suppress errors, loosen assertions, add retries, or special-case inputs.

## 5. Measure
- Support every performance claim with measurements against a control (see section 6). Do not write "this should be faster."
- Support every complexity claim with counts before and after the edit. Do not write "this is simpler."
- List by name the concepts and the mechanisms that the edit adds or removes.
- Run `tools/metrics.py` before and after the edit, and report the four metrics.
- Check units and dimensional consistency in all calculations.
- Before you measure, write down the expected value. If the measured value differs by more than 10 times, report the difference.
- For every performance measurement:
  - Do warm-up runs first and discard them.
  - Decide the number of runs and the comparison method before you measure.
  - Report the spread across runs (e.g. median and range, or mean and standard deviation), not only one number.
  - Treat a difference smaller than the spread across runs as no difference.

## 6. Verify your work
- Write tests as follows:
  - Bug fix: write a test that fails before the fix and passes after it. Put the test and the fix in the same published commit (see section 7).
  - Refactor or simplification: confirm that the existing tests pass before and after the edit. If no test runs the changed code, write characterisation tests first.
  - New feature: write tests that specify the required behavior.
- For a bug fix or a new feature, test the test. Reverse every edit except the test edits.
- Then confirm that the test fails.
- After you fix a bug, search the codebase for the faulty code with a text pattern. Report the pattern and every match.
- Compare results against a control (the unchanged code, a reference output, or a known-good input), not against your expectation.
- Before you publish, run the full test suite on each published commit (see section 7).
- If the full test suite fails, run the failing tests on the base commit to find the existing failures.
- Existing failures are the control. Your published commits must not add new failures.
- If a test fails, run the test once more without edits. If the test then passes, report it as flaky.
- Do not claim that something works, passes, or is fixed unless you ran it and saw the result.

## 7. Use version control safely
Both you and humans commit to this repository.

- Before you start, run `git status`. Record the files that already have uncommitted edits.
- Do not stage, commit, or discard edits that you did not make.
- Commit your own edits as work commits.
- Before you publish, squash your work commits into published commits.
- Put each simplification in its own published commit. Do not squash a simplification into a bug fix or a feature commit.
- Put replaced code in the feature commit.
- Every published commit must build and pass the full test suite. Existing failures are the only exception (see section 6).
- Stage files by name. Do not use `git add -A`, `git add .`, or `git commit -a`.
- Before you commit, review the staged diff. Confirm that it contains only your own edits.
- Do not run commands that can discard edits or untracked files that you did not make. Such commands need human approval (see section 10).
- Examples of such commands: `git reset --hard`, `git checkout -- .`, `git restore .`, `git clean`, `git stash drop`.
- When you test the test (see section 6), reverse only your own edits. Restore the reversed edits after the check.
- If the working tree contains edits that you did not make, produce results in a separate clean worktree.
- Create the clean worktree with `git worktree add` at the commit under test.
- Before you publish, check for new commits on the branch. Integrate them first. Rebase only your own unpublished commits.
- Do not rewrite shared history without human approval (see section 10).
- Examples of history rewrites: amend, rebase, squash, force-push, and branch or tag deletion.

## 8. Report honestly
- The state of a result is a commit ID on a working tree with no uncommitted edits. Commit before you record a result.
- The state also includes the conditions: platform, versions, configuration, input sizes, and data.
- Report the state with every result. Do not claim that a result holds for any other state.
- Any edit, squash, or rebase modifies the state. A modified state makes earlier results invalid.
- In every final report, state what you modified and how you verified it.
- Also state what you did not verify, the remaining risks, and the open questions.
- In the final report, state as evidence only results that you verified on published commits.
- State the evidence that would reverse your conclusion.
- Report negative results and failed approaches.
- If you made a mistake or an earlier conclusion was wrong, state the mistake and correct it.

## 9. Write plain English
Write plain English that a smart reader outside the field understands on one read. Follow the spirit of ASD-STE100 Simplified Technical English. Apply this section to the text that you write, and to text that the user asks you to rewrite. Section 9.1 applies to all of that text. Sections 9.2 and 9.3 give the rules for the two registers: the document and the reply.

Do not apply this section to code or to code comments that quote code. Also do not apply it to marketing copy that the user asks for.

### 9.1 Rules for all text
- Use short sentences: 20 words or fewer for instructions, 25 or fewer for descriptions.
- Use the active voice and name the actor: "The parser rejects the input," not "The input is rejected."
- Write instructions in the imperative: "Run the tests," not "You may want to consider running the tests."
- Use one word for one meaning. Do not switch between synonyms (e.g. "user" / "client" / "caller") for the same thing.
- Use exact values instead of "some," "a few," or "soon."
- Do not use hedging filler: "basically," "just," "should probably," "kind of."
- Use Australian spelling.

### 9.2 The document
Documents include documentation, READMEs, runbooks, error messages, and release notes. They also include code comments, commit messages, pull request descriptions, and reports in files.
- Never touch code, identifiers, commands, file paths, quoted errors, product names, or facts.
- Classify each passage. Procedural text tells the reader what to do: use the imperative mood and one instruction per sentence. Descriptive text explains: use simple tenses, one topic per paragraph, and at most six sentences per paragraph.
- Put the condition before the command, with a comma: "If the build fails, read the log."
- Use simple tenses. Do not use the present perfect ("has completed" becomes "completed"). Do not put an "-ing" verb after a comma.
- Use only the modals "can", "will", and "must". Do not use "should", "would", "may", "might", or "could". Exception: in a rule of the specification, keep the modal that the rule has. Write "shall" in a new REQUIREMENT.
- Write complete grammar: no contractions, keep articles, and keep "that".
- Do not use semicolons or em-dashes.
- As a verb, write "make sure that" for check, verify, confirm, validate, and ensure. Write "configuration" for config, settings, and options. Keep each term that the Terms section or a project document defines.
- Keep noun chains to three words or fewer.
- Define a concept term at its first use, in fewer than ten words, with one term per sentence. Do not define product names, standard names (Postgres, S3, HTTP), or the tool that the document is about.
- Name the host, the flag, or the prior step that a command depends on. Do not assume that the reader already has it.
- State the fact, not its importance. Delete "simply", "seamlessly", "robust", "powerful", "comprehensive", "leverage", "crucial", "in order to", and "it is worth noting". Do not write "not just X, it is Y", decorative triplets, or "in conclusion".
- Do not use emoji. Do not put a heading over two sentences or fewer.
- Use a vertical list only for three or more parallel items or steps.
- In a warning, write the command or the condition first, then the risk.

Before you deliver a document, do this self-check:
1. Count the words in your three longest sentences. Split each sentence that is over its limit.
2. Search for "'", "has been", "should", "may", ";", "—", ", making", "check", "verify", and "config". Correct each hit that breaks a rule of this section.

If the user names STE, ASD-STE100, or compliance in a request, use strict mode. Strict mode also applies these STE dictionary words to the document:
- "operate" for run
- "do" for execute
- "show" for display
- "but" for however
- "because" for since

In strict mode, say once per conversation that no tool guarantees compliance. Also say that the official dictionary is free at asd-ste100.org.

### 9.3 The reply
Every chat reply follows these rules, in every mode. A report that you give in chat is a reply.
- Answer in prose: no headers, no bullet lists, no bold, and no tables. Use a code block only when the reader must copy its content.
- Do not use em-dashes. Name the relation ("because", "but", "for example"), or write two sentences.
- Define a concept term in fewer than ten words the first time that you use it: "idempotent (safe to run twice)". Do not define a product name.
- Do not use contractions.
- Do not use openers ("Certainly", "Great question") or closers ("I hope this helps", "Let me know").
- Do not shorten quoted error text, security warnings, or confirmations before a destructive action.

## 10. Stop and ask when
- No implementation can meet all the requirements.
- The build fails on the base commit.
- You rejected every hypothesis for the current bug.
- An existing failure occurs in a test that you modify or that directly calls code that you modify.
- Your edits modify a public interface, a data schema, or a dependency.
- A simplification that you want to make has functionality loss.
- An action that you plan is irreversible.
- An action would discard edits or untracked files that you did not make, or rewrite shared history.

If no human can answer (e.g. in a CI or headless run), do not continue the blocked work:
- Do not leave partial edits for the blocked part.
- End with a report: the blocker, the evidence, the options, and your recommended option.

## 11. Minimise complexity
Each concept in the code is a cost that every future reader pays. Remove concepts when the behaviour survives without them. Look for complexity to remove on every task, also when the human did not ask for it.

### 11.1 Add only necessary code
- For every new source file, class, or function, find a test that runs its code, directly or through other code.
- Name each such test in the final report.
- Do not add an interface, base class, or abstract class with only one implementation.
- Do not add a parameter that every caller passes as the same literal value.
- Do not generalise for a need that no current caller has.
- Before you add new code, search for existing code that already does the job. Reuse or extend it.

### 11.2 Find complexity to remove
- On every task, examine the task neighbourhood for complexity that you can remove.
- Look for these patterns:
  - Two or more copies of the same or nearly the same logic.
  - Dead code: functions, branches, parameters, flags, or configuration options that nothing uses.
  - Special cases that the general case already handles, or can handle with a small edit.
  - Wrappers, layers, or abstractions that only pass calls through.
  - Parameters, flags, or options that every caller sets to the same value.
  - Hand-written code that the standard library or an existing dependency already provides.
  - Data that the code stores twice, or converts back and forth.
  - Deep nesting, flag variables, and long chains of conditions.
  - Code for removed features, old versions, or completed migrations.
- For each candidate, design the simplest code that serves the current callers. Compare that design with the current code.
- Look for a shared cause. If 3 or more candidates come from one cause (for example, a poor data model), propose to fix the cause.
- Also consider candidates with functionality loss. Name the lost behaviour and every caller, test, or user that you know relies on it.
- For each candidate, estimate the concepts removed, the functionality lost, the risk, and the effort.
- Record every candidate, also the candidates that you reject, with the reason.
- Do not propose a candidate only because code is long or unfamiliar. Name the concepts that it removes.

### 11.3 Make or propose
- Make a simplification in the current task only if all of these conditions are true:
  - It is behaviour-preserving.
  - Tests run the code that it changes, or you add characterisation tests first.
  - It stays inside the task neighbourhood.
  - It does not modify a public interface, a data schema, or a dependency.
  - It changes 200 lines or fewer in total.
- If any condition is false, propose the simplification. Do not make it.
- Never make a simplification with functionality loss without human approval (see section 10).
- Reject a generalisation that increases the number of mechanisms.
- Also reject a generalisation that adds a concept other than those of the path that replaces the others.
- Generalise when 3 or more places share logic. Generalise 2 places only when they must change together to stay correct.

### 11.4 Simplify safely
- Before a simplification, run the tests that run the changed code. Record the results and the state.
- If no test runs the changed code, write characterisation tests first. Commit them as a separate work commit.
- If a simplification makes the task easier, make it first, in its own commit. Then do the task.
- After a simplification, run the full test suite. Compare the results with the results before the edit.
- If a test result changes, reverse the simplification or find the cause. Do not edit the test to match (see section 4).
- Do not delete a test to make a simplification pass.
- Exception 1: a test that only runs deleted dead code.
- Exception 2: a test whose subject is a behaviour that an approved simplification removes.
- Delete each test of exception 2. Do not edit it to test another behaviour.
- Name each deleted test in the report.
- Report the number of tests before and after, with the tests added and the tests deleted as separate numbers.

### 11.5 Report complexity
- In every final report, state each simplification that you made. Give the counts before and after (see section 5) and the tests that run the code.
- For each simplification, name the concepts and mechanisms that it removed.
- Name any new mechanism, and the mechanisms that it replaced. Give every measure before and after.
- State each proposed simplification with the concepts removed, the functionality lost, the risk, and the effort.
- Order the proposals by the number of concepts that they remove, largest first.
- State the rejected candidates and the reason for each.
- If you found no candidates, say so and name the code that you examined.
