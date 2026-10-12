# Requirements — Fantasy NBA Draft Assistant

Status: Task 0. Living document. Update this file when a feature’s behavior changes.

This file describes the product. It explains what we are building, who it is for, and what each part of the draft assistant is supposed to do. Implementation order and technical choices live in `docs/planning.md`. How we write the code lives in `docs/development-guidelines.md`.

## 1. Product

FantasyHelper is a local draft assistant for one person’s NBA fantasy team.

The first release helps that person prepare a price list and run an auction draft. It turns last season’s stats into category values, adjusts those values when the manager chooses categories to punt, accounts for keepers, and tracks the draft as players are sold.

The person using it is already in their league on draft day. The app does not replace the league site. It sits beside it and answers four questions:

- What is this player worth to my build?
- What can I still afford?
- Who should I nominate, and who is left that fits my roster?
- Which categories am I actually winning or giving up?

Day-to-day lineup, waiver, and trade tools are later work. They are outside this stage.

## 2. Who uses it

There is one user: the person who runs the project on their own machine.

They are a manager in a season-long rotisserie league that drafts by auction. They know their league settings, they watch the draft happen, and they type in results as players are sold. They are close enough to the league that breaking news, such as a late injury, is already in front of them. The app does not need to chase that news for them.

What they do:

- Set up one or more leagues: name, budget, team count, roster size, categories, and the season. Open the league they are drafting.
- Let the app import the prepared stat and projection files, then look through the imported players.
- Choose one or two categories to punt, or choose none.
- Enter their keepers and locked prices before the draft. Enter other teams’ keepers so those players leave the pool.
- During the draft, record each sale: player, price, and whether the player went to them or to someone else.
- Read the updated prices, budget, max bid, category balance, and nomination ideas after each sale.

What they do not do:

- Sign in, share a database, or sync with another installation.
- Connect this app to Yahoo, ESPN, or any league host.
- Rely on the app for live injury alerts.

If the project is later opened up to other people, accounts, hosting, and shared data will be redesigned then. Until that decision, one installation is one user. League entries stay on this machine. Stat and projection numbers come from prepared files already on this machine. The app does not download them.

## 3. Scope

### In this stage

- Season-long rotisserie scoring.
- Auction draft, including a keeper auction.
- Draft day: prices, budget, nominations, and category balance.
- Local, single-user, free tooling. No hosting.

### Later

- Snake drafts, points leagues, and head-to-head formats.
- Lineups, waivers, streaming, and trades.
- Our own projection model. Prepared projection files from other people can be imported and shown before that.
- Enforcing position eligibility when a player is added to the roster. Position text is stored and shown before that.
- Automatic draft sync from a league host.
- Multi-user access.

### Explicitly out of this stage

Live injury workflows. The prepared files do not carry an injury flag. The app will not alert, auto-skip, or reprice a player because of an injury. The manager already has that information when they bid. Expected games and minutes on a projection are the place those files account for missed time.

## 4. League rules the app assumes

These are editable settings, with defaults that match a common public league. The defaults are a starting point, not a rule of the sport.

| Setting | Default | Why it matters |
| --- | --- | --- |
| Teams | 12 | Total auction money is teams × budget. Dollar values are wrong if this is wrong. |
| Budget | $200 per team | Same reason. Keepers spend part of this before the draft starts. |
| Roster spots | 13 | Drives spots remaining, max bid, and how many players are “drafted” in the value model. |
| Categories | The standard 9 | The z-score uses only the categories the league scores. |
| Season | 2026-27 | Names the season being drafted. The price baseline stays the newer completed season. |
| Punt categories | None until the user picks | 0, 1, or 2 categories. |

Standard 9 categories:

- Points (PTS)
- Rebounds (REB)
- Assists (AST)
- Steals (STL)
- Blocks (BLK)
- Threes made (3PM)
- Field goal percentage (FG%)
- Free throw percentage (FT%)
- Turnovers (TO). Lower is better.

An 8-category league is the same list without turnovers. The user can turn a category off. We will not invent extra categories in this stage.

Roster needs in this stage mean open spots and category balance. The assistant does not enforce position eligibility. Projection files may list more than one position, and that text is shown with the player. The draft screen stays about categories and budget.

## 5. Data and when it is loaded

Prepared files, then typed draft results. The app does not fetch either one.

### Prepared files, on launch

`data/inbox/` holds the only files the app reads. A file that is already recorded as imported is skipped. A new file is imported. There is no network call and no daily refresh.

Two kinds of files belong there:

- One stats file per season, named `stats-<season>.csv`, such as `stats-2025-26.csv`. Counting stats in that file are season totals. Seasons older than the last two may be present. They are imported and can be selected on screen. Prices do not have to use them.
- Any number of projection files for a season, named `projection-<season>-<source>.csv`, such as `projection-2026-27-bonus.csv`. Counting stats in that file are per game. A projection is for the season it names. When that season is over, those files can stay on disk and simply not be selected. The next season needs its own projection files.

The valuation baseline is our projection for the season being drafted. Usage comes from the 2026-27 projection files. Counting rates stay on last season, 2025-26, when that season is long enough and the minutes are close to the projection. Percentages can come from 2024-25 when 2025-26 is not long enough. A player is included only when they appear on at least one projection file. A long last season with no projection file is left out. The planning file has the rule. A stats file for the season in progress can be imported and browsed. It is not the baseline. That use waits with day-to-day features.

A player is the same person across files when a normalized form of the name matches. The files do not share an id. The app builds that key when it creates a player and when it compares a new file with players it already has. The key turns accented letters into plain English letters, lowercases the name, removes periods and apostrophes, and turns spaces into hyphens. `Jokić` and `Jokic` meet. Deleting the accented letter instead would split them.

That key will not fix every spelling. A short alias list makes `Trey Murphy` and `Trey Murphy III` the same person, and does the same for Robert Williams, Jimmy Butler, Derrick Jones Jr., and Kelly Oubre Jr. Other spellings stay separate. Merging two imported players in the app is later work, and that merge recalculates prices once prices exist. A name that matches nobody is still imported: a rookie may exist only on a projection, and an old player may exist only on a past season. Two different players in one file must not collapse to one key. That file is refused and the clash is shown.

### During the draft, typed by the user

Picks and prices. Which players were kept, and for how much. Who bought a nominated player.

The prepared files do not know this league. The draft on screen is whatever the user has entered.

## 6. Solutions

Each subsection is the product behavior. The math and the task that builds it are in the planning file.

### 6.1 Punt-aware z-score valuation

Rotisserie rewards ranking across categories, not raw points. A player’s value is how much they move a team relative to the rest of the player pool, in each category the league scores.

The rates on that list are our projection for the draft season. The base list scores every player on that projection, on every active category. There are two totals. The plain total adds the category z-scores. The curved total squeezes each category z toward a limit of −1 and 1 before adding, so a huge lead in one category cannot count like several categories. Each total has its own rank. Each rank keeps the top `teams × roster spots` players and turns that same total into a price. A player in the group costs at least $1. Extra money above $1 goes to the top 10 players per team. The rest of the group stays at $1. A player outside the group costs $0 on that price. The two prices add up, each on its own, to the league’s auction money. Turnovers count in reverse: fewer turnovers is the good direction. Percentages are not treated as ordinary counting stats. A player who shoots a high percentage on two shots a night is not as valuable as a player who shoots a slightly lower percentage on fifteen shots. The volume for that score is projected games times attempts per game.

Punting means the user has decided not to compete in one or two categories. Those categories drop out of the personal price. Values are recalculated, not merely hidden, so a specialist in a punted category becomes cheap to this user and a contributor in the remaining categories becomes more expensive. The user can also leave the punt empty and use the base list.

The list is a guide for this build. It is not a prediction of what the room will pay.

### 6.2 Keepers and sales

A keeper and a draft sale are the same kind of entry. A keeper is entered before the draft. Both require a whole-dollar price of at least $1.

The entry records the player, the user's team or another team, the price, and keeper or draft. One player is sold once in a league. The keeper or draft mark does not change the price.

The player leaves the available list. That spot is no longer for sale, and the price comes out of the league pot. Category z-scores stay as they are. The same price rule runs again for the players still available, with the spots and money that are left. A punt uses that same remaining pot.

The user's price cannot exceed the user's max bid. Another team's price cannot exceed that team's budget. A sale that would leave the league short of $1 for every open spot is refused. Unmarking the player or editing the price recalculates the list. The row does not name which other team bought the player.

### 6.3 Budget tracker

The tracker shows four pairs: league money spent and left, league spots taken and left, the user's money spent and left, and the user's spots taken and left. League money starts at teams times the budget. League spots start at teams times the roster size.

The max bid is the most the user can offer for the player currently up for auction and still fill every remaining spot at $1:

`max bid = dollars left − $1 × (spots still open after this player)`

If one spot is left, the max bid is the entire remainder. This is the working rule. The shorthand “leave a dollar per remaining spot” means a dollar for each spot that still has to be filled after the current bid, not an extra dollar held back from the last spot.

Spent money includes every sale. The user's spots left start from the roster size and drop with each of the user's sales.

### 6.4 Live draft assistant

The user types each result as it happens: player, price, and “my team” or “another team.”

After each entry the app updates the pool, the budget, the price list, and the category picture. Players who are kept or sold no longer appear as targets.

The remaining pool can be narrowed by the current punt and by what the roster still needs. A player who only helps a punted category sinks on the personal list. A player who helps a category the team is short in rises as a target, within the max bid.

Nomination suggestions look for a different kind of player: someone this build does not want, who is expensive to managers who do want that category. Typical case: the user is punting blocks, so they nominate a high-priced blocks specialist and let the rest of the room spend. Suggestions are a short list with a reason, not an automatic bid.

### 6.5 Category balance tracker

As the user’s roster grows, the tracker shows each category as strong, thin, or intentionally punted.

It updates when a keeper is saved and when the user buys a player. Purchases by other teams do not change this roster’s balance. They only change who is left and, later, inflation.

A punted category is labeled as a punt even if the number is low. A low number in a category the user is trying to win is the warning.

### 6.6 Price inflation tracking

Not used. The auction reprice already makes the remaining prices add up to the money still in the league, so a second scale would be 1.

## 7. Feature breakdown

### League setup

- Create, edit, and remove local leagues. One league is open during a visit.
- Each league has a name, season, team count, budget, roster size, and active categories.
- Save the leagues on this machine. Choosing a league or a dataset holds until the browser page is refreshed or the app stops. A browser refresh or a new visit starts on the first active league and the first dataset.
- Removing a league hides it. That league’s draft entries stay.
- Changing a setting that affects money or categories refreshes the price list.

### Prepared data

- Import every accepted file in `data/inbox/` that has not been imported before.
- Skip a file that was already imported, even if the app is opened again.
- Show the imported players in a table. The user selects which dataset to view: a season’s stats, or one projection.
- On a projection, show that file’s rank and dollar figure as the file’s own numbers.
- Stay usable when a season or a projection file is absent. The datasets that did import are still shown.

### Price list

- One price table sorted by the plain rank. Headers are Name, Z Rank, Z Price, C Rank, C Price, Games, Minutes, each active category, then Z Score and C Score. Z is the plain total and C is the curved total. Names stay on the left. Every other value is centered. Z Price and C Price show a dollar sign in front of the whole-dollar amount. Each column is as wide as its own header or values, and the table stops there. Each category's projection is colored by its plain z. FG% and FT% share a cell with their attempts. Games under 60 and minutes under 25 are marked. Positions are not shown.
- One line above the table lists each category the league has turned on, with a switch. A switch starts on. Turning it off punts that category. A third off switch is refused. Turning the last switch off is refused. The choice is not saved.
- With a punt, My Z Rank, My Z Price, My C Rank, and My C Price follow C Price. The table sorts by My Z Rank. The base ranks, prices, and score totals stay. The punted category stays on the table and its header is marked.
- Leave sold players off the list, and reprice the players still available from the spots and money that are left.

### Draft

- Keep the league header. Under it, a Players tab for the dataset lists and a Draft tab for the auction.
- On Draft, show league money, league spots, the user's money, and the user's spots, each as spent or taken and what is left, plus the max bid.
- Three lists: players still available with the repriced amounts, the user's taken players, and other teams' taken players.
- Search a player, or open the same view from a list row. The view shows that player's price-table line and the max bid.
- Mark the player sold as a keeper or a draft sale, on the user's team or another team, with a price. Edit the price or unmark the player.
- The punt switches stay on Draft. Category balance and nomination ideas stay later.

### Category balance

- One row or card per active category.
- Value for the user’s current roster.
- A punt marker on punted categories.
- A simple read of strong versus thin for categories the user is keeping.

### Inflation

- Not used. The auction reprice is the price list during the draft.

## 8. Main flows

### First launch of a season

1. User opens the app and enters league settings.
2. App imports any new files in `data/inbox/`. Files already imported are skipped.
3. User sees a base price list.

### Before the draft

1. User selects punt categories, if any, and the prices change.
2. User enters keepers.
3. Budget, spots, pool, and category balance match that keeper list.
4. User reviews prices and nomination ideas.

### During the draft

1. A player is nominated in the real league.
2. User checks personal price, max bid, and whether the player fits the build.
3. User records the sale.
4. Pool, budget, balance, and suggestions update.
5. Repeat until the roster is full or the user stops.

### A mistype

1. User edits the price or unmarks the player.
2. The list and the money match the sales that remain.

## 9. What “done” means for this stage

A user can, on one machine, with instructions from the README:

- Import prepared stat and projection files from `data/inbox/`, skip files already imported, and browse the players by dataset.
- Set a 9-category or 8-category auction league.
- Get a base price list and a price list with one or two punted categories.
- Enter keepers and see budget and roster effects.
- Run through a mock or real draft by typing sales.
- See max bid and category balance change after each of their own buys.
- See the repriced list for the players still available.

They cannot manage the season after the draft in this stage. That is a later scope.

## 10. Decisions already made

These are product decisions, so implementation should follow them unless we change this file.

- One local user. No accounts.
- More than one league can be saved. One is open during a visit. That choice lasts until the app stops. Players and imported files are shared. Removing a league hides it and leaves its draft entries in place.
- The app reads prepared files from `data/inbox/` and does not download them. The files are not committed.
- One stats file per season. Several projection files per season are allowed. Older seasons may be imported and left unselected.
- The valuation baseline is the newer completed season, currently 2025-26. A file for the season in progress can be browsed and is not the baseline. An older completed season is available for a low-games fallback, decided with the price list.
- Players are matched by a normalized name, plus a short alias list. The source files do not share an id.
- Projection rank and dollars can be shown for comparison. They are not our prices. We do not build our own projection model in this stage.
- Position text is stored and shown. The draft does not enforce position eligibility in this stage.
- Punt means drop that category and recompute, for one or two categories.
- Max bid reserves $1 for every spot still open after the player being bid on.
- A keeper and a draft sale are the same row. Both require a price of at least $1.
- The auction reprice replaces a separate inflation factor.
- The league host is not integrated. Draft results are manual.
