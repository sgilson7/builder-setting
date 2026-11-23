# Glossary

The source of truth for what each word in this tool means. Strings, tests, the plan and the README use a term in the sense given here. The page shows a definition when a reader hovers the term.

Write each entry as a `### Term` heading, then one or two plain sentences, then an optional `Not:` line listing words that must not be used for it. A number a rule decides is a `{placeholder}` the core fills, so the glossary cannot disagree with the rules. Keep entries in alphabetical order. `crates/core/tests/copy.rs` checks the format, the placeholders and the `Not:` words; `TONE.md` governs the prose.

<!--
An example entry. It sits inside this comment, so it does not count.

### Spout

Where slush comes out. Each line has up to {line.spouts} spouts.

Not: tap, dispenser, nozzle
-->

### Borrow

In column subtraction, taking one from the next column to the left so that the column being worked has ten more. The digit lent from is crossed out and its new value written small above it.

Not: regroup, exchange, trade

### Carry

In column addition, the tens of a column's sum, written small above the next column to the left and added in with it.

Not: regroup, overflow

### Column

The digits in one place value, written one above another: the ones, the tens, the hundreds and so on.

Not: slot, cell

### Partial product

In long multiplication, the row made by multiplying the top number by one digit of the bottom number, with zeros on the right for the tens, hundreds and so on.

Not: subtotal, sub-product

### Quotient

The answer of a division: how many times the second number goes into the first, written on top of the bracket in long division.

Not: ratio

### Remainder

What is left over when the second number does not go into the first an exact number of times. A remainder is less than the number divided by.

Not: leftover, rest, modulus

### Step

One part of a worked method, shown on its own with a sentence saying what it does. Play shows the steps in turn.

Not: frame, slide, stage

### Worked example

A sum chosen ahead of time and rendered with Manim, showing the same steps as the calculator's own animation.

Not: demo, sample, tutorial
