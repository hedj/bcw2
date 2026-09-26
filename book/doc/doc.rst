:kind: reference

=========================
Documentation conventions
=========================

Overview
========

These conventions govern every chapter in ``book/``. Each rule in them names the goal that it
supports.

The book holds reference text and explanation. The rules are the reference text, and the rest
of the book explains them. Each chapter declares its Diátaxis kind in a ``:kind:`` field on its
first line. A how-to guide is a chapter of the kind ``how-to``. The book has no how-to guides or
tutorials yet.

The chapters are written in reStructuredText. Each GOAL and each rule is a directive, such as
``.. requirement:: core.rotation``, whose argument is its anchor. Its options, such as
``:parent:``, stand on the lines below the directive. A twin stands inside its rule as a
``twin`` directive. ``tools/bcw.py`` is the Sphinx extension that defines these directives,
checks the rules and tangles the code. The tangle also writes the value of each PARAMETER as a
constant, which the Verilog and the twins read. A TARGET is a figure that the finished
hardware is measured against, so nothing in the design rests on it. A heading of level 1 has ``=`` above and below it. Level
2 has ``=`` below it, level 3 has ``-`` and level 4 has ``~``.

``make weave`` builds the reader edition, as HTML and as a PDF. It moves each RATIONALE and
DISCUSSION to an Explanation section at the end of its chapter.

``book/retired-anchors.txt`` lists the anchors that no chunk can use again, and
``book/general-words.txt`` lists the words that need no definition. ``make check`` also prints
the number of rules with more than two parents, because a long list of parents says little.

The goals come first. The later sections define the terms and state the rules.

Goals
=====

.. goal:: doc.one-reading

   Every rule has one meaning, so that two readers of the rule build the same machine.

.. goal:: doc.one-source

   Each rule is stated once. Its formal twin, its Verilog, its checks and every view of it
   are tied to that statement or generated from it.

.. goal:: doc.read-is-checked

   The English of a rule and its formal twin cannot drift apart without a check failing.

.. goal:: doc.traceable

   Every rule traces up to the goal or security property that it serves, and down to its
   checks and its implementation. A reference stays valid when the chapters change.

.. goal:: doc.one-engineer

   The chapters stay small and plain enough for one engineer to read completely, and their
   reading burden is measured.

.. goal:: doc.rules-apart

   A reader can tell at once which text is a rule, which is explanation, and which is an open
   question or a record.

.. goal:: doc.changes-reach-author

   A script finds each change to what the machine does, and sends it to the author for
   approval.

Terms and marking
=================

.. definition:: doc.chunk
   :parent: doc.rules-apart

   A :dfn:`chunk` is a directive of ``tools/bcw.py`` that carries a label, with the text
   inside it. Its label is the name of the directive in upper case: GOAL, REQUIREMENT,
   PARAMETER, DEFINITION, RATIONALE, DISCUSSION, TARGET or OPEN. The English of a chunk is the
   text of its own paragraphs.

.. definition:: doc.rule
   :parent: doc.rules-apart

   A :dfn:`rule` is a chunk labelled REQUIREMENT, PARAMETER or DEFINITION.

.. definition:: doc.normative
   :parent: doc.rules-apart

   The :dfn:`normative text` of the book is the English of its rules. Text outside a chunk
   states no rule.

.. definition:: doc.scripted
   :parent: doc.one-reading

   A :dfn:`documentation rule` is a rule in this chapter that a script checks when
   ``make check`` runs. The author drops a rule that no script can check, or reduces it to a
   part that a script can check.

.. definition:: doc.twin
   :parent: doc.read-is-checked

   A :dfn:`twin` is a ``twin`` directive.

.. definition:: doc.stamp
   :parent: doc.read-is-checked

   The :dfn:`stamp` of a rule is the first eight hexadecimal digits of the SHA-256 hash of its
   label, a space and its English.

.. definition:: doc.allowed-options
   :parent: doc.traceable

   The :dfn:`allowed options` of a GOAL are ``parent`` alone. A PARAMETER and a TARGET allow
   ``parent``, ``value`` and ``unit``, and a REQUIREMENT allows ``parent`` and ``impl``. A DEFINITION allows
   ``parent`` and ``never``, and no other label allows an option.

.. requirement:: doc.attribute-keys
   :parent: doc.traceable

   Each chunk shall carry only the allowed options of its label.

.. requirement:: doc.labels
   :parent: doc.rules-apart

   No chapter shall hold a directive that docutils, Sphinx or ``tools/bcw.py`` does not
   define.

.. requirement:: doc.one-shall
   :parent: doc.one-reading, doc.rules-apart

   Each chunk shall hold ``shall`` exactly once if it is a REQUIREMENT, and not at all
   otherwise.

.. definition:: doc.anchor
   :parent: doc.traceable

   An :dfn:`anchor` is two or more parts joined by dots, such as ``core.rotation``. Each part
   holds lower-case letters, digits and hyphens, and the first part starts with a letter. A
   chunk carries its anchor as the argument of its directive.

.. requirement:: doc.anchors
   :parent: doc.traceable

   Where a chunk is a rule or a GOAL or a TARGET, the chunk shall carry a unique anchor that
   is not retired.

.. requirement:: doc.stamps
   :parent: doc.read-is-checked

   Each twin shall stand inside a rule and carry the stamp of that rule in its ``stamp``
   option.

.. rationale::

   Judgement decides whether a rule is right. A script decides whether the text obeys it.

Trace
=====

.. requirement:: doc.implemented
   :parent: doc.traceable

   Where a rule is a REQUIREMENT, the rule shall appear in the ``implements`` option of a
   ``source`` directive or in an ``implements:`` comment, or carry ``impl`` with the value
   ``none``.

.. definition:: doc.reference
   :parent: doc.traceable

   A :dfn:`reference` is an entry in a ``parent`` or ``implements`` option, an
   ``implements:`` comment in ``tools/``, or a citation.

.. definition:: doc.citation
   :parent: doc.traceable

   A :dfn:`citation` is a use of the role ``rule`` or the role ``param``, which names an anchor.

.. requirement:: doc.references
   :parent: doc.traceable

   Each reference shall name an anchor in the book.

.. requirement:: doc.reaches-goal
   :parent: doc.traceable

   Where a chunk carries an anchor and is not a GOAL, the chunk shall reach a GOAL through its
   parents.

.. requirement:: doc.definition-parent
   :parent: doc.traceable

   Where a chunk is a DEFINITION, the chunk shall name at most one parent.

.. rationale::

   A ``source`` directive names the requirements that it implements in its ``implements``
   option. A check in ``tools/`` names its rule in an ``# implements:`` comment, so each
   documentation rule traces down to its script.

Sentences
=========

.. definition:: doc.requirement-sentence
   :parent: doc.one-reading

   A :dfn:`REQUIREMENT sentence` is a sentence of a REQUIREMENT that holds ``shall``.

.. definition:: doc.defined-term
   :parent: doc.one-reading

   A :dfn:`defined term` is the text of the first ``dfn`` role in a DEFINITION. In a
   REQUIREMENT sentence, it can follow The, A, An, Each, Every or No.

.. requirement:: doc.ears
   :parent: doc.one-reading, doc.traceable

   Each REQUIREMENT sentence shall have the form
   ``[Where F,] [While S,] [When T, | If C, then] X shall R.``, where ``X`` names a defined
   term.

.. requirement:: doc.linter
   :parent: doc.one-reading, doc.one-engineer

   Where a chunk carries an anchor, the chunk shall have no finding of level
   ``advisory-free`` from ``tools/ste_lint.py``.

.. requirement:: doc.vocabulary
   :parent: doc.one-reading

   Where a chunk carries an anchor, the chunk shall hold no word from the ``never`` option
   of a DEFINITION.

.. definition:: doc.general-word
   :parent: doc.one-reading

   A :dfn:`general word` is a word that ``book/general-words.txt`` lists, in upper or lower
   case.

.. definition:: doc.known-word
   :parent: doc.one-reading

   A :dfn:`known word` is a general word, or a word that is part of a whole defined term in the
   text. A known word can also take an ending: ``'s``, ``ies`` for a ``y`` at its end, ``es``
   after ``s``, ``x``, ``z``, ``ch`` or ``sh``, and ``s`` after any other end.

.. requirement:: doc.known-words
   :parent: doc.one-reading

   Where a chunk carries an anchor, the chunk shall hold only known words in its English
   outside quotations.

.. requirement:: doc.general-words
   :parent: doc.one-reading

   No general word shall be a defined term, with or without the ending of a known word.

.. definition:: doc.quotation
   :parent: doc.one-reading

   A :dfn:`quotation` is an inline literal, such as ``Q8.4``, or a citation. The rules on
   words and sentences ignore the text inside it.

.. definition:: doc.dotted-word
   :parent: doc.one-reading

   A :dfn:`dotted word` is a word with a full stop between two letters or digits, such as
   ``Q8.4``, ``9.09`` or ``e.g.``. The words ``etc.``, ``vs.``, ``cf.``, ``approx.``,
   ``incl.``, ``esp.``, ``resp.`` and ``ca.`` are dotted words too.

.. requirement:: doc.dotted-words
   :parent: doc.one-reading

   Where a rule is a REQUIREMENT, the rule shall hold each dotted word inside a quotation.

.. rationale::

   EARS gives each REQUIREMENT a fixed form with a defined actor. The linter keeps rules short
   and plain, and a ``never`` option keeps one word for each meaning. A quotation keeps a full
   stop from splitting a sentence.

Layout
======

.. requirement:: doc.overview-first
   :parent: doc.rules-apart, doc.one-engineer

   Each chunk shall stand after the second heading of level 2 in its chapter.

.. definition:: doc.section
   :parent: doc.one-engineer

   A :dfn:`section` is the text after a heading of level 2, 3 or 4, up to the next heading of
   those levels.

.. requirement:: doc.argument-budget
   :parent: doc.one-engineer, doc.rules-apart

   Where a section holds a chunk that carries an anchor, the section shall hold at most one
   RATIONALE or
   DISCUSSION, of 40 words or fewer.

.. definition:: doc.code-block
   :parent: doc.rules-apart

   A :dfn:`code block` is a block of code in a chapter, such as a literal block after ``::``
   or a ``code-block`` directive.

.. requirement:: doc.code-kinds
   :parent: doc.rules-apart

   Each code block shall be a ``twin``, ``source`` or ``check`` directive.

.. rationale::

   A reader meets the purpose of a chapter before its rules, as Diátaxis keeps explanation
   apart from reference. The budget keeps argument short. A code block is part of the machine
   or a check of it.

Chapters
========

.. definition:: doc.chapter
   :parent: doc.one-engineer

   A :dfn:`chapter` is a reStructuredText file in ``book/`` other than ``book/index.rst``. The
   name of a chapter is the name of its file without ``.rst``.

.. requirement:: doc.chapter-path
   :parent: doc.one-engineer

   Each chapter shall have the path ``book/<name>/<name>.rst``.

.. requirement:: doc.chapter-title
   :parent: doc.one-engineer

   Each chapter shall hold exactly one heading of level 1, and no text before it.

.. requirement:: doc.chapter-kind
   :parent: doc.rules-apart

   Each chapter shall start with the field ``:kind:``, whose value is ``tutorial``,
   ``how-to``, ``reference`` or ``explanation``.

.. requirement:: doc.anchor-prefix
   :parent: doc.traceable

   Where a chunk carries an anchor, the chunk shall carry the name of its chapter as the first
   part of the anchor.

.. definition:: doc.chapter-order
   :parent: doc.one-engineer

   The :dfn:`chapter order` puts the chapters of each kind together, in the order tutorial,
   how-to, reference and explanation. Within a kind, it puts each chapter after every other
   chapter of that kind that holds a parent of one of its chunks. Where two or more chapters
   can come next, the order takes the first name in alphabetical order.

.. requirement:: doc.chapters-ordered
   :parent: doc.one-engineer

   The chapter order shall hold every chapter.

.. definition:: doc.section-number
   :parent: doc.one-source

   A :dfn:`section number` is a number at the start of a heading that holds a full stop, such as
   ``2.`` or ``4.2``. A number that ends the heading, or that a word with a capital letter
   follows, such as the ``1`` of ``1 Core``, is a section number too. A count, such as the ``8``
   of ``8 threads``, is not.

.. requirement:: doc.heading-numbers
   :parent: doc.one-source

   No chapter shall hold a heading that starts with a section number.

.. rationale::

   The weave numbers the chapters and their sections, so a new section never changes a number
   in the source. The kinds keep tutorial, guide, reference and explanation apart, and the
   trace sets the order within a kind.

Parameters
==========

.. definition:: doc.parameter-value
   :parent: doc.one-source

   A :dfn:`parameter value` is the ``value`` option of a PARAMETER or a TARGET. It is an
   integer, or an expression of integers, the anchors of PARAMETERs and parentheses. It can use the
   operators ``+``, ``-``, ``*``, ``//``, ``%`` and ``**``, and the functions ``clog2``, ``min``
   and ``max``. An exponent is 1024 or less, and a minus sign has a space on each side.

.. requirement:: doc.parameter-values
   :parent: doc.one-source

   Where a rule is a PARAMETER, the rule shall carry a parameter value that evaluates to an
   integer.

.. definition:: doc.constant-name
   :parent: doc.one-source

   The :dfn:`constant name` of a PARAMETER is its anchor in upper case, with each dot and hyphen
   written as an underscore, such as ``CORE_TURN_WIDTH``.

.. requirement:: doc.constant-names
   :parent: doc.one-source

   No constant name shall belong to more than one PARAMETER.

.. requirement:: doc.param-citations
   :parent: doc.traceable

   Where a citation uses the role ``param``, the citation shall name a PARAMETER or a TARGET.

.. rationale::

   The tangle writes each PARAMETER as a constant in ``build/rtl/bcw_params.sv`` and
   ``build/model/bcw_params.py``, so the Verilog and the twins read one value. The weave shows the
   value where the text cites it.

Targets
=======

.. requirement:: doc.target-values
   :parent: doc.one-source

   Where a chunk is a TARGET, the chunk shall carry a parameter value that evaluates to an
   integer.

.. requirement:: doc.target-parents
   :parent: doc.traceable

   No chunk shall name a TARGET in its ``parent`` option.

.. rationale::

   A measurement of the finished hardware decides a TARGET. No design decision can rest on a
   goal that nobody has met yet, so no chunk serves a TARGET and no value names one. The tangle
   writes no TARGET.

Fragments
=========

.. definition:: doc.fragment-name
   :parent: doc.one-source

   A :dfn:`fragment name` is the argument of a ``source`` directive when it is a ``:`` before
   the form of an anchor, such as ``:core.rotation-logic``. The ``:`` sets it apart from an
   anchor. A ``source`` directive whose argument holds a ``/`` names a file.

.. definition:: doc.fragment
   :parent: doc.one-source

   A :dfn:`fragment` is the code of the ``source`` directives with one fragment name, joined in
   the chapter order. Within a chapter, the directives join in the order of their lines. The
   code blocks of one file join in the same order.

.. definition:: doc.fragment-use
   :parent: doc.one-source

   A :dfn:`fragment use` is a line of a ``source`` directive that holds only a fragment name
   between ``<<`` and ``>>``, after spaces. ``make tangle`` puts the fragment in place of the
   line, with those spaces before each line of the fragment.

.. requirement:: doc.source-targets
   :parent: doc.traceable

   Where a code block is a ``source`` directive, the code block shall name a file in ``build/``
   or a fragment name.

.. requirement:: doc.fragment-uses
   :parent: doc.traceable

   Each fragment use shall name a fragment.

.. requirement:: doc.fragments-used
   :parent: doc.one-source

   Each fragment shall reach a file through fragment uses.

.. requirement:: doc.fragment-cycles
   :parent: doc.one-source

   No fragment shall reach itself through fragment uses.

.. requirement:: doc.whole-twins
   :parent: doc.one-source

   No twin shall hold a line with the form of a fragment use.

.. rationale::

   A fragment lets the code of a rule stand next to the rule, while a skeleton puts a module in
   order. ``make tangle`` writes ``build/tangle.json``, which traces each tangled line to its
   chapter line.
