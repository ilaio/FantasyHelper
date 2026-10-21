# Requirements — Fantasy NBA Draft Assistant

Status: Task 0. Living document. Update this file when a feature’s behavior changes.

This file describes the product. It explains what we are building, who it is for, and what each part of the draft assistant is supposed to do. Implementation order and technical choices live in `docs/planning.md`. How we write the code lives in `docs/development-guidelines.md`.

## 1. Product

FantasyHelper is a local draft assistant for one person’s NBA fantasy team.

The first release helps that person prepare a price list and run an auction draft. It turns last season’s stats into category values, adjusts those values when the manager chooses categories to punt, accounts for keepers, and tracks the draft as players are sold. After the draft, a Teams tab is where that person names the league’s teams, places players by hand, and reads each team’s averages and scores.

The person using it is already in their league on draft day. The app does not replace the league site. It sits beside it and answers four questions:

- What is this player worth to my build?
- What can I still afford?
- Who should I nominate, and who is left that fits my roster?
- Which categories am I actually winning or giving up?

Lineups, waivers, and trades are later work. They are outside the Teams tab.

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
- After the draft, name the teams in the league, place each player on one team, and read the averages and scores.

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

### Teams tab

- Named teams for the open league, entered by hand.
- One player on one team, or still on the Players list.
- Each team's category average, and a score that ranks those averages.
- Stored apart from draft sales. Hiding a league leaves the teams and the placements.

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

Roster needs in this stage mean open spots and category balance. The assistant does not enforce position eligibility. On Draft, Pos sits next to Name on every table that lists a player. The cell is every position from the projection files, kept when at least one file lists it, in the order PG, SG, SF, PF, C. A player with no projection leaves that cell blank. The Players tab still shows each file's own positions.

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

The user's price cannot exceed the user's max bid. Another team's price cannot exceed that team's budget. A sale that would leave the league short of $1 for every open spot is refused. Editing the price, moving the player to the other side, or unmarking the player recalculates the list. The row does not name which other team bought the player.

### 6.3 Budget tracker

The tracker has four figures for the league and the same four for the user: money left, money spent, spots left, and spots taken. League money starts at teams times the budget. League spots start at teams times the roster size. Money left and money spent are the first columns of the summary table in section 6.5. Spots left and spots taken stay in the calculation and are not columns.

The max bid is the most the user can offer for the player currently up for auction and still fill every remaining spot at $1:

`max bid = dollars left − $1 × (spots still open after this player)`

If one spot is left, the max bid is the entire remainder. This is the working rule. The shorthand “leave a dollar per remaining spot” means a dollar for each spot that still has to be filled after the current bid, not an extra dollar held back from the last spot.

Avoid bid is a lower ceiling for the same bid. It is the user's money left minus a reserve for every spot still open after this player. Counting from the last of those spots, the last four keep $2 each, the next two keep $4 each, and each earlier pair doubles. A $200 budget and 13 open spots gives $72 for the first player. The result stays between $1 and the max bid. With no spot left, there is no avoid bid.

Spent money includes every sale. The user's spots left start from the roster size and drop with each of the user's sales.

### 6.4 Live draft assistant

The user types each result as it happens: player, price, and “my team” or “another team.”

After each entry the app updates the pool, the budget, the price list, and the category picture. Players who are kept or sold no longer appear as targets.

Nominations and targets are two lists of five available players. They sit side by side under Still available, with targets on the right. Both lists use Name, Pos, TZ Price, TC Price or PC Price, and Category. A row opens that player. A player on the nomination list is left off the targets.

A nomination is ordered by how far TZ Price sits above TC Price. With a punt, TC Price is replaced by PC Price. Only a positive gap qualifies. The same gap is ordered by how far TZ Rank sits above TC Rank, or above PC Rank with a punt. When the user's summary is deep green in a category, a z of 2 or more, players who are green or deep green in one of those categories come first. The row names each of those shared categories. If fewer than five match, the rest of the list is filled by the gap and those categories stay blank. With no deep green category, and before any of the user's players are rostered, every category stays blank.

A target uses the kept category where the user is furthest behind the league. A punted category is never that category. The player has to be green there, a z of at least 1, and the price the user would pay has to be within the max bid. The order is TC Price, or PC Price when a punt is on. The same price is ordered by TC Rank, or by PC Rank when a punt is on. When the user is ahead in every kept category, the target category is the one where that lead is smallest. Before any of the user's players are rostered, there is no category to check, and the order is still TC Price or PC Price, then that rank.

### 6.5 Category summary

Draft opens with a two-row summary in the right column, in place of the budget line. The first row is the league. The second row is the user's team. That label column is 170 pixels wide, the same as Name. The category switches sit above it, in that same column.

The league row is every sold player, including the user's. The user's row is the user's sales only. A player who is still available is on neither row.

The first columns are money left and money spent. League money counts every sale. The user's money counts only the user's sales. Spots left and spots taken are calculated the same way and are not shown.

Each active category follows, in the same order as the price table. A counting cell is the average per-game rate of the players on that row. FG% and FT% are the attempt-weighted percentage and the average attempts per game, in the same cell as the lists. Each player counts once. A missing percentage is left out of that percentage. A sold player with no projection is left out of the category cells and still counts in the money.

The cell color is the average plain z of those same players, using the same six bands as one player. The z-score is not shown. The summary does not mark a punt. The switches above the table are what change the player row and the lists.

A row with no players leaves the category cells blank. Money still shows.

Another team's purchase changes the league row. It does not change the user's row.

### 6.6 Price inflation tracking

Not used. The auction reprice already makes the remaining prices add up to the money still in the league, so a second scale would be 1.

### 6.7 Teams

The Teams tab sits beside Players and Draft. It is the screen for the season after the auction. The user names the teams, places each player, and reads each team's category average and rotisserie score. Nothing on this tab comes from a league host.

Teams and placements are stored for the open league, apart from draft sales. A sale, an edit, or an unmark does not place or remove a player here. Placing a player does not create a sale. Hiding a league leaves these rows, the same way it leaves sales.

A league starts with no teams. The league's team count does not create them. The user adds a team by name and renames that team in place. The name is unique among that league's teams, ignoring case. Players is reserved for the unassigned list. Removing a team is outside this tab.

The Players list is every player on the price table who is not on a team. A player who is on a team and not on that table stays on the team, and the price cells stay blank. Each team has its own list. A player is in one of those places. Every player row has a Team choice. The choice shows where that player is now, Players or a team name. Picking another place moves the player there.

Both lists use Name, Team, Pos, TZ Price, TZ Rank, TC Rank, PZ Rank, PC Rank, Games, Minutes, then each active category. Team follows Name. TZ Price is the full-pool price from before any sale. Placing a player does not reprice anyone. With no punt, PZ Rank and PC Rank are empty. The lists are sorted by TZ Rank. A punt does not change that sort.

The category switches on this tab are the same unsaved punt choice as Draft. A switch starts on, at most two are off, and at least one stays on. On this tab a punt changes only PZ Rank and PC Rank, on the Players list and on every team list. It does not change the category columns, the averages, the scores, or the sort. A punted category is not faded on this tab. Draft keeps the display rules in section 6.1.

Each team list ends with an Average row. The name cell reads Average. Pos, the ranks, the prices, Games, and Minutes are empty, and that row has no Team choice. The category cells use the same averages as the draft summary in section 6.5. A counting stat is the per-game average. FG% and FT% are the attempt-weighted percentage and the average attempts. Each counted player counts once. A missing percentage is left out of that percentage. A player with no projection stays on the list and is left out of the category cells.

A team row has a Count checkbox beside Team. It starts on and is not saved. A refresh or a new visit turns every Count back on, the same way the category switches do. Turning it off keeps the player on the team and leaves them out of that team's average and out of the scores. A player who moves onto a team starts counted.

Under the team lists, two tables cover every team in the order the teams were added. The first table is each team's category averages. The second is the score. For each category, the teams that have an average are ranked. The best gets as many points as there are teams in that ranking, and each next place gets one point less. Fewer turnovers rank higher. Teams that tie split the points for the places they share. The total is the sum of the category points. A team with no counted players is blank in that category and is not ranked there.

## 7. Feature breakdown

### League setup

- Create, edit, and remove local leagues. One league is open during a visit.
- Each league has a name, season, team count, budget, roster size, and active categories.
- Save the leagues on this machine. Choosing a league or a dataset holds until the browser page is refreshed or the app stops. A browser refresh or a new visit starts on the first active league and the first dataset.
- Removing a league hides it. That league’s draft entries, teams, and placements stay.
- Changing a setting that affects money or categories refreshes the price list.

### Prepared data

- Import every accepted file in `data/inbox/` that has not been imported before.
- Skip a file that was already imported, even if the app is opened again.
- Show the imported players in a table. The user selects which dataset to view: a season’s stats, or one projection.
- On a projection, show that file’s rank and dollar figure as the file’s own numbers.
- Stay usable when a season or a projection file is absent. The datasets that did import are still shown.

### Price list

- One price table sorted by the plain rank. Headers are Name, Pos, TZ Rank, TC Rank, PC Rank, Games, Minutes, then each active category. PZ Rank and the price columns are not on this table. TZ is the plain total and TC is the curved total. PZ and PC are the personal rank and price. PC Rank stays on the table when nothing is punted, and its cells are empty. A missing price stays blank. Names stay on the left. Every other value is centered. The price columns show a dollar sign in front of the whole-dollar amount. Name is 170 pixels wide. Pos is 80. Rank columns and price columns are 65. Games and minutes are 60. FG% / FGA, FT% / FTA, and each counting category are 100. The table stops at those widths. Each category's projection is colored by its plain z. FG% and FT% share a cell with their attempts. Games under 60 and minutes under 25 are marked. Pos is every position from the projection files, kept when at least one file lists it, written PG/SG/SF/PF/C. A player with no projection leaves Pos blank. The score totals stay in the calculation and are not shown.
- One line above the summary table, in the right column, lists each category the league has turned on, with a switch. A switch starts on. Turning it off punts that category. A third off switch is refused. Turning the last switch off is refused. The choice is not saved.
- PC Rank follows TC Rank. PZ Rank and the price columns are not on the table. With a punt, the table sorts by PZ Rank. The base ranks stay. The personal numbers use the same price rule, with the punted categories left out of both totals. With no punt, PC Rank stays and its cells are empty. The punted category stays on the table and its header is marked `(p)`. Its cells use gray text and a paler color band. Counting headers are 3pt, Pts, Reb, Ast, Stl, Blk, and Tov.
- Leave sold players off the list, and reprice the players still available from the spots and money that are left.

### Draft

- Keep the league header. Under it, a Players tab for the dataset lists and a Draft tab for the auction. The selected tab has a light filled background.
- On Draft, two columns sit under the league header. The right column holds the category switches, then a two-row summary, then the player section. The first row is the league. The second row is the user's team. That label column is 170 pixels wide, the same as Name. The columns after it are money left, money spent, then each active category. Category cells show the average of the players on that row and use the same six color bands as one player. The max bid stays on the player view.
- The left column holds Your players, then Other teams. Each list shows the select checkbox, Name, Pos, and Price, and is the height of one roster. Your players are ordered PG, SG, SF, PF, C, and fewer positions come first. Other teams are newest first. The title counts the players in that list out of that side's spots. Still available sits under the player section in the right column, with the repriced amounts.
- The player section sits in the right column under the summary. One price-table row comes first, without the rank columns or the price columns. Under that row, one line reads TZ Price, TC Price, PC Price, Max bid, Avoid bid, and Higher ranked. Each value is bold, and a gap separates the values. TZ Price, TC Price, and PC Price show the price now, then the price from before any sale, as in $60 / $70. A missing price reads $--. Higher ranked is how many players still available have a better TC Rank, or a better PC Rank when a punt is on. With no player, that count reads --. PZ Price is not on that line. Under that line, "Search player" sits to the left of the select, which is about 50 characters wide. On that same line, the sale form keeps Draft or Keeper, a price, and three buttons. A player who is not sold can be added with Add to my team or Add to another. Unmark player stays off until the player is sold, and then removes that player from the list they are on. A player already on the user's team gets Edit my team and Switch to another. A player already on another team gets Switch to my team and Edit in another. An edit stays off until keeper or draft, or the price, changes. With no player chosen, the row is empty and those three prices read $--. Choosing a player, or a row in a list, fills that row. One player is open at a time. The list that contains that player has the row checked, and the other lists are clear. Choosing a row or a name in the search moves the check. Clearing the check clears the player. The lists stay on the page.
- Mark the player sold as a keeper or a draft sale, on the user's team or another team, with a price. Edit those values, move the player to the other side, or unmark the player.
- The category switches stay on Draft, above the summary table in the right column.
- Nominations and targets sit side by side under Still available, targets on the right. Both lists use Name, Pos, TZ Price, TC Price or PC Price, and Category. Each list has at most five available players. Nominations, Targets, Still available, Your players, and Other teams use a small title close to the list. Your players and Other teams sit in the left column, show Name, Pos, and Price, and are the height of one roster. Your players are ordered PG, SG, SF, PF, C, with fewer positions first. Other teams are newest first. Each title counts its players out of that side's spots. A nomination is the room's plain price above the curved price, using PC Price when a punt is on. The same gap uses TZ Rank above TC Rank, or above PC Rank with a punt. A target is green in the category where the user is furthest behind, ordered by TC Price or PC Price, and by that curved rank when the price matches, and within the max bid. A nomination is not also a target.

### Category summary

- Two rows in the right column of Draft: the league, then the user's team. That label column is 170 pixels wide, the same as Name. The category switches sit above that table.
- Money left and money spent, then each active category. Spots left and spots taken are not columns.
- The league row averages every sold player. The user's row averages the user's players. The color is the average plain z, in the same six bands as one player.
- The summary does not mark a punt. The switches above it change the player row and the lists.

### Inflation

- Not used. The auction reprice is the price list during the draft.

### Teams

- A Teams tab beside Players and Draft. The category switches sit at the top. Under them, the user adds a team by name. The Players list follows, then one section per team, then the averages table, then the scores table.
- The Players list is everyone on the price table who is not on a team. A player on a team who is not on that table stays on the team, with the price cells blank. Each team section shows that team's name, which can be renamed in place, and that team's players. A league starts with no teams. The team count does not create them. A name is unique among that league's teams, ignoring case, and Players is reserved.
- A Team choice on the player row shows Players or a team name. Changing it moves the player. One player is in one place.
- The columns are Name, Team, Pos, TZ Price, TZ Rank, TC Rank, PZ Rank, PC Rank, Games, Minutes, then each active category. TZ Price is the full pool from before any sale. The sort is TZ Rank. With no punt, PZ Rank and PC Rank are empty.
- The switches are the same unsaved punt as Draft. On this tab they change only PZ Rank and PC Rank. The category columns stay, the sort stays, and a punted category is not faded.
- Each team list ends with an Average row for the players whose Count is on. Count sits beside Team, starts on, and is not saved. A refresh turns every Count back on. Turning it off keeps the player visible. Moving a player onto a team starts them counted.
- The averages table and the score table follow the teams, in the order the teams were added. The score gives the best team as many points as there are teams with an average in that category, then one less per place. A tie splits those places. Fewer turnovers rank higher. The total adds the categories. A team with nobody counted is blank and is not ranked.
- Placements are separate from sales. Hiding a league leaves the teams and the placements.

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

1. User edits the price or moves the player to the other side.
2. The list and the money match the sales that remain.

### During the season

1. User adds each team and names it.
2. User places players with the Team choice on the row.
3. User turns Count off for a player who should stay on the team and stay out of the average.
4. User reads the averages and the scores. A punt changes only the personal rank and price columns.

## 9. What “done” means for this stage

A user can, on one machine, with instructions from the README:

- Import prepared stat and projection files from `data/inbox/`, skip files already imported, and browse the players by dataset.
- Set a 9-category or 8-category auction league.
- Get a base price list and a price list with one or two punted categories.
- Enter keepers and see budget and roster effects.
- Run through a mock or real draft by typing sales.
- See max bid and category balance change after each of their own buys.
- See the repriced list for the players still available.
- Name the teams, place each player on one team, and see the same teams and placements after a restart.
- Read each team's average and a score that ranks the teams by those averages.

Lineups, waivers, and trades stay later. The Teams tab does not set a lineup or talk to a league host.

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
- Max bid reserves $1 for every spot still open after the player being bid on. Avoid bid reserves $2 for each of the last four of those spots, then doubles every two spots, and stays between $1 and the max bid.
- A keeper and a draft sale are the same row. Both require a price of at least $1.
- The auction reprice replaces a separate inflation factor.
- The league host is not integrated. Draft results are manual.
- Teams and placements are entered by hand and stored apart from draft sales. One player is on one team or on the Players list.
- The Teams tab shows TZ Price from before any sale, then TZ Rank, TC Rank, PZ Rank, and PC Rank. A punt on that tab changes only PZ Rank and PC Rank.
- A team's average counts the players whose Count is on. Count is not saved. The score ranks those averages, splits a tie, and treats fewer turnovers as better.
