# Planning — Fantasy NBA Draft Assistant

Status: Task 2 planned. Living document. Update the task list as work moves. Product behavior is defined in `docs/requirements.md`. Working rules are in `docs/development-guidelines.md`.

## 1. Architecture

The app is one local Python program. The interface, the draft rules, and the database live in the same project. Nothing is hosted.

```text
FantasyHelper/
  app.py                 streamlit entry: streamlit run app.py
  src/fantasyhelper/
    ui/                  Streamlit screens
    valuation/           added with the price-list tasks
    draft/               added with the draft tasks
    stats/               reads the local season files and writes SQLite
  data/                  local only, not committed
    external/            Basketball-Reference CSV files the user saves
    fantasyhelper.sqlite3
  pyproject.toml         package install and pinned dependencies
  docs/                  requirements, planning, guidelines
  README.md              how to run the app locally
```

The package lives at `src/fantasyhelper/`. `src` keeps the importable code separate from the README, docs, and database directory. The app is installed with `pip install -e .` so `app.py` can import `fantasyhelper` from that location. `valuation/` and `draft/` are created in the tasks that fill them. The `stats` package reads files and writes SQLite. It is not named `data`, because `data/` at the repo root holds the local files and the database.

Responsibilities stay separated:

- **Data** fetches public stats and stores them. It does not decide what a player is worth.
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

### Local season files

Public stats come from two CSV files the user saves from Basketball-Reference season-totals pages. The app does not download them and does not call a stats API. The files stay under `data/external/` and are not committed. Credit Basketball-Reference where the app shows that the numbers came from these files.

Checked files, both valid:

| File | Season | Data rows | Players | Combined rows |
| --- | --- | --- | --- | --- |
| `data/external/2024-25.csv` | 2024–25 regular season | 735 | 569 | 77 players on two teams, 4 on three |
| `data/external/2025-26.csv` | 2025–26 regular season | 733 | 582 | 66 on two teams, 5 on three, 1 on four |

Both files share one header, 33 columns, no repeated header rows, and no broken rows. Games run from 1 to 82. All 30 franchises appear. Counting stats on a combined row equal the sum of that player’s team rows. 464 players appear in both seasons.

The combined row is labeled `2TM`, `3TM`, or `4TM`, not `TOT`. It is the season total. The last team row under it is the team they finished with. `Player-additional` is the stable player id (`gilgesh01`). Names are not the id. Position is on each row and can differ across a player’s teams. Use the position on the combined row.

Columns kept from each file: `Player`, `Player-additional`, `Team`, `Pos`, `G`, `MP`, `FG`, `FGA`, `3P`, `FT`, `FTA`, `TRB`, `AST`, `STL`, `BLK`, `TOV`, `PTS`.

Columns dropped: `Rk`, `Age`, `GS`, `FG%`, `3PA`, `3P%`, `2P`, `2PA`, `2P%`, `eFG%`, `FT%`, `ORB`, `DRB`, `PF`, `Trp-Dbl`, `Awards`. Percentages are computed later from makes and attempts.

For a player with several rows in one season, store the combined row’s counting stats and position. Store the team abbreviation from the last team row. A player with one row is stored as that row.

### No hosting

The user starts the app on localhost. The README will contain the commands when the app exists. This stage does not add an account system, a remote database, or a deploy step.

## 3. Data model

Names can change when we create the schema. The contents should not grow beyond this without a reason.

**teams** — `abbreviation` text, primary key. The 30 franchise codes in the files (`CHO` for Charlotte, `BRK` for Brooklyn). No numeric team id and no full name in these files.

**players** — `id` text, primary key, the `Player-additional` value. `name` text.

**season_stats** — one row per player per season. `player_id`, `season_start_year` (`2024` or `2025`), `team_abbreviation`, `position`, `games`, `minutes`, `fgm`, `fga`, `fg3m`, `ftm`, `fta`, `pts`, `reb`, `ast`, `stl`, `blk`, `tov`. Primary key `(player_id, season_start_year)`. Percentages are computed from makes and attempts, not stored.

**import_log** — `season_start_year`, `source_file`, `imported_at`. Unique on `season_start_year`. A second launch skips a season that already has a row.

**status_flags** — not created in Task 2. These files have no injury or status column.

**league** — one row: name, season, team count, budget, roster size, which categories are on, which are punted (0–2).

**keepers** — player, price or null, `mine` or `other`.

**sales** — ordered list: player, price, `mine` or `other`, time. Undo deletes the last row.

Derived facts are calculated, not stored: dollars left, spots left, max bid, z-scores, prices, inflation, category balance. Storing them would create a second source of truth that can drift from the inputs.

## 4. Valuation approach

This is the method Task 6 and Task 7 implement. It is the standard rotisserie approach, kept small.

### Player pool

The comparison pool is the top group of players by a simple total of counting production, large enough to cover the league: `teams × roster spots`, plus a small bench of extra names so the edge of the pool is not brittle. The exact extra count is set in Task 6 and written back here once we see a real list. Players below that pool have no auction price.

Rates use per-game averages so a player who missed games is not punished twice. Percentages use season makes and attempts.

### Counting categories

For PTS, REB, AST, STL, BLK, 3PM, and TO:

`z = (player average − pool mean) / pool standard deviation`

Turnovers are multiplied by −1 after that, so a low-turnover player gets a positive score.

### Percentages

FG% and FT% use a volume-aware impact, then that impact is turned into a z-score across the pool:

- League average percentage from the pool’s total makes and attempts.
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

### Task 2 — Database and season import

Agreed source and scope:

- Read `data/external/2024-25.csv` and `data/external/2025-26.csv`. Do not download them. Do not add an HTTP client.
- Create `teams`, `players`, `season_stats`, and `import_log` only. League settings, keepers, sales, and status flags wait.
- Apply the column rules and the `2TM` / `3TM` / `4TM` rule in section 2.
- The `stats` package reads the files and writes `data/fantasyhelper.sqlite3`. The screen still says that no league is loaded, and it shows the imported player counts for both seasons.
- Skip a season that already has an `import_log` row. A missing file or a bad header is an error on screen. Do not invent rows. Importing stats does not touch keepers or sales once those tables exist.

Done when: the user opens the app, sees both seasons’ player counts, opens it again without a second import, and can query SQLite for games, minutes, and the counting stats, including makes and attempts. A traded player has one row per season, with the combined totals and the finishing team.

Status: planned. Not started.

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
- **CSV shape.** Task 2 imports the checked files. A later file with a different header stops and reports the error instead of guessing columns.
- **Streamlit reruns.** Widgets rerun the script often. Draft writes must be idempotent: saving the same sale twice must not double-charge. The database is the source of truth, not widget state.
