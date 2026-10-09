# Development guidelines

Status: Task 4. Living document. Add a rule when we learn one. Do not collect rules we are not willing to follow.

These guidelines keep the draft assistant small, testable, and aligned with `docs/requirements.md` and `docs/planning.md`.

## 1. How we work

We build one task from the planning file at a time, in order, unless we explicitly reorder that file.

Before writing code for a task, plan that task with the user. The generic task in the planning file is the starting point, not the final design. The conversation confirms the approach, settles layout and naming choices that the task will lock in, and checks which functionality and data belong in this task versus a later one. Open items for that conversation are listed in `docs/planning.md`. Update the task in the planning file with what was agreed, then implement.

A task is finished only when its “Done when” check has been performed. For a screen, that means using the app. For stored data, that means looking at the database. For a formula, that means comparing it to a known example. After that check, plan the next task the same way before starting it.

When a task changes behavior, update the requirements or the plan in the same piece of work. These files are part of the task, not a cleanup step for later.

Task 0 is documentation only. Application code starts at Task 1.

## 2. Keep it simple

Prefer the smallest version that satisfies the current task.

- Do not add a feature because it would be nice during a draft. Position eligibility, projections, league-host sync, and accounts are already deferred. Leave them deferred.
- Do not add a second framework, a second data source, or a background job while the first choice still works.
- Do not generalize a function for formats we are not building. Season-long roto auction is the format.
- A short, obvious function is better than a configurable engine. If a rule has one version, write that version.
- Comments explain a non-obvious rule (percentage impact, max bid, punt recomputation). They do not restate the line of code.

If a task feels like it needs new infrastructure, stop and update the planning file first.

## 3. The user runs commands

The user runs every terminal command: installs, the app, tests, database inspection, and git.

When a command is needed, ask for it directly. Say what it is for and the exact command. Wait for the result before assuming it worked.

Do not run project commands on the user’s behalf. Do not tell the user a check passed unless they ran it or the output is in front of us.

Suggested commands should be copy-pasteable and should match the README once the README has run steps.

## 4. Every task is easy to test

Each task names one primary check:

- Open the app and do the action a manager would do, or
- Query the local database and see the new rows or values.

Design the task so that check is enough. Avoid work that can only be verified by reading a long diff.

Pure functions for prices, max bid, inflation, and balance are preferred, because they can be checked with a small example that does not need the full UI. The planning file calls for those examples on the math tasks.

A Streamlit control that writes a draft entry must survive a rerun and an app restart. If the only copy of a bid is in memory, the task is not done. Which league is open, and which dataset is on screen, last only while the app is running.

## 5. Where code goes

Follow the layout in the planning file.

- `db/` opens the database. It does not own a table.
- `stats/` reads `data/inbox/` and writes the player, season, projection, and import log tables. It does not decide what a player is worth.
- `valuation/` turns stat tables into z-scores and prices. No Streamlit imports. No reading environment variables.
- `leagues/` creates the `leagues` table, and later keepers, sales, budget, nominations, and balance. It may call valuation. It does not render widgets.
- `ui/` renders and forwards user actions. It is thin.

The database holds inputs. Prices, money left, max bid, and balance are computed from those inputs when the screen loads.

Several leagues can be saved. During a visit, one is open, held in the running app rather than on the league row. Players and imported files are shared. Hiding a league leaves its keepers, sales, and punts in the database.

## 6. Data and secrets

- An API key, if a later task needs one, lives in `.env` or the local secrets file already covered by `.gitignore`. Never commit it, never paste it into docs, never store it in SQLite.
- The database file and the inbox CSV files stay local and uncommitted. The database is the user’s draft. The inbox files are the prepared stat and projection data.
- Import a file once, by file name. Do not download data, and do not read the inbox from a valuation function on every widget rerun.
- If a file is missing or a required column is absent, keep the last good local data and say so on screen. Do not invent stats. Do not treat a blank percentage as zero.
- Deleting or resetting draft entries is an explicit user action. Importing files must not wipe keepers or sales.

## 7. Calculations

Match `docs/planning.md` sections 4 and 5. If the formula needs to change, change the plan first and then the code.

In particular:

- Percentages use the stored percentage, attempts, and volume-aware impact. Makes are not a stored column.
- Turnovers are reversed so fewer is better.
- A punt recomputes the total and the dollar scale. It does not subtract from a finished price.
- Max bid leaves $1 for each spot that remains after the current player. The final spot can use the last dollar.
- Another team’s purchase changes the pool and inflation. It does not change this team’s category balance.
- Category labels treat a punt as a punt, even when the total is low.

Show both the personal price and, once inflation exists, the adjusted price. Do not replace the personal price silently.

## 8. Interface

The draft screen should be readable on draft day: budget and max bid visible without scrolling past a long form, prices sortable, nomination reasons short.

Empty states should say what to do next. Examples: no season loaded yet, no punt selected, no keepers, no sales yet.

Errors from a bad entry (unknown player, price above max bid, a third punt category, a keeper who was already sold) should say what is wrong in plain language. Refuse the write.

Visual design stays plain. No theme work unless a screen is hard to use.

## 9. Dependencies and configuration

Add a dependency only when a task needs it. Prefer the standard library, then the tools already chosen: Python, pandas, numpy, SQLite, and Streamlit. Reading the inbox files uses the standard library. Do not add an HTTP client for stats or projections.

Tools for this stage are free, widely used, and under our control. A tool has to let us turn off anything that sends our data or usage data to a third party. Calls that leave the machine wait until a task needs one. Stat and projection files are local, so importing them does not. Streamlit stays the interface. Its usage statistics are off in `.streamlit/config.toml`. Whether a tool could later run outside a local machine is a low-priority preference, checked only when the other requirements are already met.

Pin versions in the project dependency file once Task 1 creates it, so the user’s machine and later work install the same stack.

Configuration that changes value (budget, categories, punt) is league data in SQLite. Configuration that changes the environment (API key, database path) is local config. Do not mix them.

## 10. Changing these documents

Update in place. Do not start a parallel spec.

- Behavior change → `docs/requirements.md`
- Architecture, formula, or task change → `docs/planning.md`
- A new working rule → this file

When a task is finished, set its status in the planning file to done and add a one-line note of anything the implementation clarified (a threshold, a column name, an API field). Strike or rewrite tasks that we drop. Leave a short history note rather than deleting the decision silently.

## 11. Asking before drifting

Ask the user before:

- Adding a feature that is not in the current task.
- Replacing Streamlit, SQLite, or the stats source.
- Introducing accounts, networking beyond the stats API, or anything that leaves the machine.
- Changing a formula that draft decisions will depend on.

Once the pre-task conversation has settled the task, implement that agreement. Do not reopen settled product text in the requirements file unless the conversation changed it.
