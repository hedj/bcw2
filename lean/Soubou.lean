import Mathlib.Tactic.Ring

/-!
The root module of the Soubou library.

The example below is a smoke test. The build fails unless Mathlib loads and
its `ring` tactic works.
-/

example (a b : ℤ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2 := by ring
