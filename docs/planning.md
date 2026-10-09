# Planning — Fantasy NBA Draft Assistant

Status: Task 2 implemented, waiting for the user’s check. Living document. Update the task list as work moves. Product behavior is defined in `docs/requirements.md`. Working rules are in `docs/development-guidelines.md`.

## 1. Architecture

The app is one local Python program. The interface, the draft rules, and the database live in the same project. Nothing is hosted.

```text
FantasyHelper/
  app.py                 streamlit entry: streamlit run app.py
  src/fantasyhelper/
    ui/                  Streamlit screens
    valuation/           added with the price-list tasks
    draft/               added with the draft tasks
    stats/               reads data/inbox and writes SQLite
  data/                  local only, not committed
    inbox/               prepared stat and projection CSV files
    fantasyhelper.sqlite3
  pyproject.toml         package install and pinned dependencies
  docs/                  requirements, planning, guidelines
  README.md              how to run the app locally
```

The package lives at `src/fantasyhelper/`. `src` keeps the importable code separate from the README, docs, and database directory. The app is installed with `pip install -e .` so `app.py` can import `fantasyhelper` from that location. `valuation/` and `draft/` are created in the tasks that fill them. The `stats` package reads `data/inbox/` and writes SQLite. It is not named `data`, because `data/` at the repo root holds the inbox and the database. Turning a raw download into an inbox file happens outside the app.

Responsibilities stay separated:

- **Data** imports prepared files and stores them. It does not decide what a player is worth.
- **Valuation** is pure calculation. Given a player table, league settings, and a punt, it returns prices. It does not know whether the user clicked a button.
- **Draft** holds the league’s entered facts: settings, keepers, sales, money, spots. It asks valuation for prices.
- **UI** collects input and displays results. It does not hide formulas in widget callbacks. If a number is on screen, a function in `valuation` or `draft` produced it, and that function can be checked without the UI.

The database file is the memory of the app. Closing the window does not forget the draft.

```text
local CSV files  -->  SQLite  -->  valuation  -->  prices
                       ^              ^
                       |              |
                  user entries     draft state (budget, roster, balance)
                       ^
                       |
                     Streamlit
```

## 2. Tools

### Python, pandas, and numpy

The core of the product is a table of players and a few column-wise statistics: mean, spread, z-score, and a weighted sum. Python is the natural place to do that, and pandas is the natural way to do it on a table. Numpy backs the numeric steps. This is the calculation engine, not a general application framework.

### SQLite

One user, one machine, two kinds of rows: reference data (players, teams, stats) and draft data (settings, keepers, sales). SQLite is a single file, needs no server, and is easy to open when we want to test that a task wrote the right rows. The repository gitignore already ignores `db.sqlite3`. We will keep the real file under `data/` and ignore that directory the same way.

### Streamlit

The draft assistant is a local working screen: settings, a table, a few inputs, a budget summary. Streamlit serves that with one process and one command.

A separate React app and a FastAPI server would add a second runtime, a build step, and an API contract. That split pays off when there is a second client or a remote user. This stage has neither. Valuation and draft state will not import Streamlit, so a different interface can replace `ui/` later without rewriting prices or the database.

Streamlit’s usage statistics are turned off for this project in `.streamlit/config.toml` (`browser.gatherUsageStats = false`). Restart the app after changing that file.

### Inbox files

The app reads `data/inbox/` and nothing else for player data. It does not download files and does not convert raw workbooks or HTML. A file whose name is already in `import_log` is skipped. A file with the wrong name or the wrong header is refused, and the other files still import. Replacing the contents of a file that was already imported does not reload it. A changed file needs a new name, or the old log row has to be removed on purpose.

Stats files are named `stats-<season>.csv`. One file per season. A second stats file for a season that is already imported is refused. Counting stats and minutes are season totals. The current inbox files are `stats-2024-25.csv` (569 players) and `stats-2025-26.csv` (582 players). Older season files use the same shape and may be added later.

Projection files are named `projection-<season>-<source>.csv`. Several sources for one season are normal. Counting stats are per game. `games` is expected games played. The current inbox files are `projection-2026-27-bonus.csv`, `projection-2026-27-josh.csv`, and `projection-2026-27-fantasyedge.csv`.

Stats columns, in order:

`name`, `team`, `positions`, `games`, `minutes`, `points`, `threes`, `rebounds`, `assists`, `steals`, `blocks`, `turnovers`, `fg_pct`, `fga`, `ft_pct`, `fta`

Projection columns, in order:

`name`, `team`, `positions`, `games`, `minutes_per_game`, `points_per_game`, `threes_per_game`, `rebounds_per_game`, `assists_per_game`, `steals_per_game`, `blocks_per_game`, `turnovers_per_game`, `fg_pct`, `fga_per_game`, `ft_pct`, `fta_per_game`, `source_rank`, `source_dollars`

`fg_pct` and `ft_pct` are decimals with three digits after the decimal, so `0.553` is 55.3%. A blank percentage means the player had no attempts. It is not zero. Makes are not a column. `source_rank` and `source_dollars` belong to that projection. They are not our prices. Category values from a projection are not in the file.

`positions` on a projection may be several codes joined by slashes, such as `PG/SG`. On a stats file it is the single position from that season. `team` is the abbreviation that file used. The same player can have a different team on a projection than on a past season. Those abbreviations are stored as written. This task does not merge `CHO` with `CHA` or `BRK` with `BKN`.

Each inbox file is already one row per player. The app does not look for combined team rows.

### Player identity

The match key is built in code. It is not a column in the file.

1. Turn accented letters into their plain English letters. `č` becomes `c`.
2. Lowercase.
3. Remove periods and apostrophes.
4. Turn every remaining run of spaces or punctuation into one hyphen, and trim hyphens from the ends.

`Nikola Jokić` and `Nikola Jokic` both become `nikola-jokic`. `O.G. Anunoby` becomes `og-anunoby`. `Shai Gilgeous-Alexander` becomes `shai-gilgeous-alexander`.

A new key creates a player. The display name kept is the name from the file that created the player. A later file that matches the key adds rows and does not rename the player. The same key twice inside one file refuses that file.

An alias list in the project maps an alternate key to the canonical key before the match. The starting aliases are `trey-murphy` to `trey-murphy-iii`, `alex-sarr` to `alexandre-sarr`, and `cam-johnson` to `cameron-johnson`. A player who still matches nothing is stored anyway.

### No hosting

The user starts the app on localhost. The README will contain the commands when the app exists. This stage does not add an account system, a remote database, or a deploy step.

## 3. Data model

Names can change when we create the schema. The contents should not grow beyond this without a reason.

**players** — internal id, `name_key` unique, `name` as first imported. Aliases are not extra players. They point at a key this table already uses.

**season_stats** — one row per player per season. `player_id`, `season` (`2025-26`), `team`, `positions`, `games`, `minutes`, `points`, `threes`, `rebounds`, `assists`, `steals`, `blocks`, `turnovers`, `fg_pct`, `fga`, `ft_pct`, `fta`. Primary key `(player_id, season)`. Percentages may be blank. Counting stats are season totals.

**projections** — one row per player per season per source. The same counting fields as per-game columns, plus `games`, `source_rank`, and `source_dollars`. Primary key `(player_id, season, source)`.

**import_log** — `file_name` unique, `kind` (`stats` or `projection`), `season`, `source` or blank, `imported_at`. A file name in this table is skipped on the next launch.

**status_flags** — not created in Task 2. Inbox files have no injury column.

**league** — one row: name, season, team count, budget, roster size, which categories are on, which are punted (0–2).

**keepers** — player, price or null, `mine` or `other`.

**sales** — ordered list: player, price, `mine` or `other`, time. Undo deletes the last row.

Derived facts are calculated, not stored: dollars left, spots left, max bid, z-scores, prices, inflation, category balance. Storing them would create a second source of truth that can drift from the inputs.

## 4. Valuation approach

This is the method Task 6 and Task 7 implement. It is the standard rotisserie approach, kept small.

### Player pool

The comparison pool is the top group of players by a simple total of counting production, large enough to cover the league: `teams × roster spots`, plus a small bench of extra names so the edge of the pool is not brittle. The exact extra count is set in Task 6 and written back here once we see a real list. Players below that pool have no auction price.

Rates use per-game averages so a player who missed games is not punished twice. The stored percentage inputs are `fg_pct`, `ft_pct`, and the attempt columns. Makes are not stored. How those inputs become the volume-aware score is settled with the price list.

### Counting categories

For PTS, REB, AST, STL, BLK, 3PM, and TO:

`z = (player average − pool mean) / pool standard deviation`

Turnovers are multiplied by −1 after that, so a low-turnover player gets a positive score.

### Percentages

FG% and FT% use a volume-aware impact, then that impact is turned into a z-score across the pool:

- League average percentage from the pool’s stored percentages, weighted by attempts.
- A player’s impact is `(player percentage − league percentage) × player attempts`.
- That impact is z-scored like a counting stat.

A high percentage on very few attempts lands near zero. A high percentage on a large number of attempts lands high. The same idea applies to a poor percentage: it hurts in proportion to how many shots created it.

### Base value

`total z = sum of category z-scores` for active categories only.

Auction dollars: take the players with a positive total z inside the rostered portion of the pool (`teams × roster spots` players, after replacement). Scale those positive values so they sum to `teams × budget`. A player at replacement is worth about $1, and the scaling is adjusted so the drafted money is conserved. Task 6 writes down the exact scaling after it is checked against a small hand-computed example.

Players with a non-positive total are worth $0 to $1. They are not targets.

### Punt

Drop the punted categories from `total z`. Recompute the dollar scaling on the new totals. Do not take the base price and subtract a column after the fact. One or two categories. Zero categories leaves the base list unchanged.

### Inflation (Task 13)

`factor = dollars still unspent in the whole league / sum of model prices of players still available`

`adjusted price = model price × factor`

The user’s own remaining budget does not replace this factor. Inflation describes the room. The max bid still caps what this user can pay.

## 5. Draft calculations

**Money spent** — sum of the user’s keeper prices and the user’s purchases.

**Money left** — budget − money spent.

**Spots left** — roster size − user’s keepers − user’s purchases.

**Max bid** — money left − $1 × (spots left − 1), and never below $1 while a spot remains. When one spot remains, max bid equals money left.

**Category balance** — sum of per-game z-scores, by category, for the user’s keepers and purchases only. Punted categories are marked `punt`. Other categories are `strong` or `thin` by a simple threshold set in Task 12 (starting idea: above +0.5 combined z is strong, below −0.5 is thin, otherwise neutral). The threshold is written back here after we look at a real roster.

**Nomination ideas** — among available players this user should not buy (personal price well below a likely room price, or most of their positive z sitting in punted categories), rank by how much money they figure to extract from the room. Show a handful, each with the category that makes them a trap for other teams. Task 11 keeps this rule to one function and a short list, and we tighten it only if a mock draft shows it suggesting players the user would actually want.

## 6. Task list

Each task is one vertical slice. The next task starts only after the current one is checked the way its “Done when” line says, and only after that next task has been planned in detail with the user. Commands are run by the user. The agent asks for a command and waits.

The writeups below stay as the generic approach until that conversation. Confirmed choices are written into the task and into the sections above.

### Open conversations

Raise these before the task they affect. They do not change the text above until we decide.

- **Before Task 3.** Whether a current-season file belongs in this draft stage, or waits for day-to-day features. It would be another local CSV, not an API refresh.
- **Before the price list (Task 5).** When a player’s newer season has too few games, whether prices use the older season instead. Both seasons are stored either way.
- **Before league setup (Task 4).** Whether the user can create more than one league with the settings we already have, including a demo league or a demo draft inside a league.
- **Before the price list (Task 5).** Other ways to calculate z-scores. The method in section 4 stays until that conversation. The user will bring specific concerns then.
- **Before the price list is shown.** Whether the player table includes season averages next to the scores.

### Task 0 — Preparation files

Create `docs/requirements.md`, `docs/planning.md`, and `docs/development-guidelines.md`.

Done when: the three files exist and describe this stage. No application code.

Status: done.

### Task 1 — Project skeleton

Agreed layout and scope:

- Package at `src/fantasyhelper/`. No empty `valuation/`, `draft/`, or stats packages yet.
- `app.py` calls one screen: the app name, and the line “No league is loaded yet.”
- `pyproject.toml` pins Streamlit only and installs the package in editable mode. Pandas, NumPy, and the API client wait for the tasks that use them.
- README run steps: create `.venv`, activate it, `pip install -e .`, `streamlit run app.py`, open the local URL.
- `/data/` is gitignored. The directory and the API key wait until Task 2, when the app first stores data and calls the stats source.

Done when: the user can run the documented commands and see that screen in the browser.

Status: done. The user ran the app and saw the title and the empty-league line. `.streamlit/config.toml` turns Streamlit usage statistics off for this project.

### Task 2 — Import inbox files and show them

Agreed source and scope:

- Read only `data/inbox/`. Do not download files. Do not add an HTTP client. Do not read raw downloads.
- Import `stats-2024-25.csv`, `stats-2025-26.csv`, and the three `projection-2026-27-*.csv` files. Create `players`, `season_stats`, `projections`, and `import_log`. League settings, keepers, sales, and status flags wait.
- Build `name_key` in code, apply the starting aliases, and refuse a file that contains one key twice.
- Skip a file name already in `import_log`. Refuse a second stats file for a season that is already imported. A bad name or a bad header is an error for that file only.
- The screen says that no league is loaded, lists the imported datasets, and shows a player table for the one the user selects. A projection table includes that file’s rank and dollars, labeled as the file’s figures.
- Importing does not touch keepers or sales once those tables exist.
- On a fresh database, stats files are imported before projection files, and each group is imported by file name. The stored display name is the name from the file that creates the player.
- The scan reads `.csv` files in `data/inbox/` only. A csv with the wrong name is refused. Other files in that folder are left alone.
- The player table uses readable column headers. On a projection, rank and dollars are headed "File rank" and "File dollars".

Done when: the user opens the app, selects each imported dataset, and sees that dataset’s players and columns. Opening the app again does not import the same files again. SQLite shows one player for a name that appears in both a stats file and a projection, two season rows for a player who played both seasons, and separate projection rows for Bonus, Josh, and Fantasy Edge. A player who exists only on a projection is still in the table.

Status: implemented. Waiting for the user to open the app, select each dataset, and check SQLite.

### Task 3 — Current-season refresh

If this stage includes a current season, import another local CSV the same way as Task 2. There is no daily network refresh. If the file is absent, the two saved seasons remain available.

Done when: decided only if this task stays in the draft stage.

### Task 4 — League settings

A screen to save the one league profile: name, season, teams, budget, roster size, and category toggles. Defaults from the requirements file.

Done when: the user can change a setting, restart the app, and see the same settings in the database.

### Task 5 — Base price list

Implement section 4 without punts. Show a table of player, per-game stats, total z, and price. Include a tiny fixed example in tests or a script the user can run, with hand-computed z-scores, so the formula is checked apart from the full player list.

Done when: the example matches the hand calculation, and the app shows a sorted price list from the loaded season.

### Task 6 — Punts

Add the 0–2 category punt control. Recompute prices the way section 4 describes. Show base price and personal price.

Done when: choosing no punt matches Task 5, punting one category moves specialists in that category down the personal list, and a second punt is allowed while a third is refused.

### Task 7 — Keepers

Enter, edit, and remove the user’s keepers (player + price) and other teams’ keepers (player + optional price). Remove them from the available list. Apply the user’s keepers to money, spots, and category totals.

Done when: the user can enter a keeper, see the budget drop by that price and the spots drop by one, restart, and see the same keeper still applied.

### Task 8 — Budget and sales

Show spent, remaining, spots, and max bid. Record a sale to the user or to another team. Undo the last sale.

Done when: the user can enter a short sequence of sales, including one of their own, and the max bid matches the formula in section 5. Undo restores the previous numbers. Rows in `sales` match what was entered.

### Task 9 — Pool filters and nominations

Filter the remaining pool by personal price and by category fit. Show nomination suggestions from section 5.

Done when: after a few mock sales, kept and sold players are gone, a punted specialist is off the target list and can appear as a nomination, and the suggestion text names the category.

### Task 10 — Category balance

Show the user’s roster balance from section 5, updating with keepers and the user’s purchases.

Done when: buying a blocks specialist moves the blocks reading, a punted category stays marked as a punt, and another team’s purchase does not change the balance.

### Task 11 — Inflation

Implement the factor in section 4. Show it and the adjusted prices. Keep the unadjusted personal price visible.

Done when: a small example where the room has overspent produces a factor above 1, and the adjusted column moves while the personal price stays put.

### After this list

Day-to-day features wait until these tasks are done and the requirements file grows a new scope. Do not start them in the middle of the draft assistant.

## 7. Testing approach

Prefer a check the user can do in one sitting.

- Data tasks: query SQLite.
- Math tasks: a small example with a known answer, plus a look at the price table in the app.
- Draft tasks: enter a short mock draft in the app and confirm budget, pool, and balance.

We do not need a large automated suite before there is logic. Once valuation and draft functions exist, add focused tests for those functions so a formula change fails loudly. UI behavior is still checked by using the app.

## 8. Risks to watch

- **Percentage math.** Easy to z-score the raw percentage and overvalue low-volume shooters. The hand-computed example in Task 5 should include one low-volume shooter and one high-volume shooter.
- **Off-by-one max bid.** The last roster spot may spend the final dollar. The formula in section 5 is the one to test.
- **Preseason emptiness.** Current-season refresh must be allowed to succeed with no games.
- **CSV shape.** Task 2 imports the inbox files described in section 2. A file with a different header is refused instead of guessing columns.
- **Name match.** Normalization plus the three starting aliases will miss other spellings. Those players import as separate people until an alias is added. A key clash inside one file refuses that file.
- **Streamlit reruns.** Widgets rerun the script often. Draft writes must be idempotent: saving the same sale twice must not double-charge. The database is the source of truth, not widget state.
