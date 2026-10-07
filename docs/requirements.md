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

- Set up the league once: budget, team count, roster size, categories, and the season.
- Let the app load players, teams, and stats.
- Choose one or two categories to punt, or choose none.
- Enter their keepers and locked prices before the draft. Enter other teams’ keepers so those players leave the pool.
- During the draft, record each sale: player, price, and whether the player went to them or to someone else.
- Read the updated prices, budget, max bid, category balance, and nomination ideas after each sale.

What they do not do:

- Sign in, share a database, or sync with another installation.
- Connect this app to Yahoo, ESPN, or any league host.
- Rely on the app for live injury alerts.

If the project is later opened up to other people, accounts, hosting, and shared data will be redesigned then. Until that decision, one installation is one user, and nothing they enter is sent anywhere except to the stats source when the app downloads public player data.

## 3. Scope

### In this stage

- Season-long rotisserie scoring.
- Auction draft, including a keeper auction.
- Draft day: prices, budget, nominations, and category balance.
- Local, single-user, free tooling. No hosting.

### Later

- Snake drafts, points leagues, and head-to-head formats.
- Lineups, waivers, streaming, and trades.
- Projections from a paid or custom model.
- Position-eligibility rules (PG, SG, and so on).
- Automatic draft sync from a league host.
- Multi-user access.

### Explicitly out of this stage

Live injury workflows. A status flag may be stored and shown when the stats source provides one. The app will not alert, auto-skip, or reprice a player because of an injury. The manager already has that information when they bid.

## 4. League rules the app assumes

These are editable settings, with defaults that match a common public league. The defaults are a starting point, not a rule of the sport.

| Setting | Default | Why it matters |
| --- | --- | --- |
| Teams | 12 | Total auction money is teams × budget. Dollar values are wrong if this is wrong. |
| Budget | $200 per team | Same reason. Keepers spend part of this before the draft starts. |
| Roster spots | 13 | Drives spots remaining, max bid, and how many players are “drafted” in the value model. |
| Categories | The standard 9 | The z-score uses only the categories the league scores. |
| Season | The season being drafted | Chooses which prior season is the valuation baseline. |
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

Roster needs in this stage mean open spots and category balance. The assistant does not enforce position eligibility. That keeps the draft screen about the build the user is drafting, which is categories and budget.

## 5. Data and when it is loaded

Three kinds of data, three timings.

### Once per season

Players, teams, and prior-season stats.

This is the baseline for prices. Auction drafts usually happen before the new season has meaningful stats, so last season is the valuation source. Loading it again in the same season should not be required. A new season, or a manual refresh, loads it again.

### On launch, at most daily

Current-season stats and simple status flags, when the source has them.

This keeps the database from going stale if the user opens the app during the season. On draft day, before games are played, this refresh may return little or nothing. The draft assistant still works from prior-season stats.

There is no background scheduler. Opening the app is the refresh.

### During the draft, typed by the user

Picks and prices. Which players were kept, and for how much. Who bought a nominated player.

The stats source does not know this league. The draft on screen is whatever the user has entered.

## 6. Solutions

Each subsection is the product behavior. The math and the task that builds it are in the planning file.

### 6.1 Punt-aware z-score valuation

Rotisserie rewards ranking across categories, not raw points. A player’s value is how much they move a team relative to the rest of the player pool, in each category the league scores.

The base list scores every relevant player on every active category, combines those scores into one value, and turns that value into an auction price. Turnovers count in reverse: fewer turnovers is the good direction. Percentages are not treated as ordinary counting stats. A player who shoots a high percentage on two shots a night is not as valuable as a player who shoots a slightly lower percentage on fifteen shots. The price list uses a volume-aware percentage score so shot volume is part of the value.

Punting means the user has decided not to compete in one or two categories. Those categories drop out of the personal price. Values are recalculated, not merely hidden, so a specialist in a punted category becomes cheap to this user and a contributor in the remaining categories becomes more expensive. The user can also leave the punt empty and use the base list.

The list is a guide for this build. It is not a prediction of what the room will pay.

### 6.2 Keeper league support

Before the draft, the user records keepers.

Their own keepers are already on the roster at a locked price. That price is already spent, that spot is already filled, and that player’s category production already counts toward the team. The player is not in the bidding pool and is not nominated.

Other teams’ keepers are off the board. They leave the pool so the assistant does not recommend them. A price can be entered when the user knows it, because money already spent in the room matters for inflation. If the price is unknown, the player is still removed from the pool.

Keepers are entered before values and budget are trusted. Changing a keeper recalculates the remaining budget, the open spots, and the price list.

### 6.3 Budget tracker

The tracker shows money spent, money left, and roster spots left.

The max bid is the most the user can offer for the player currently up for auction and still fill every remaining spot at $1:

`max bid = dollars left − $1 × (spots still open after this player)`

If one spot is left, the max bid is the entire remainder. This is the working rule. The shorthand “leave a dollar per remaining spot” means a dollar for each spot that still has to be filled after the current bid, not an extra dollar held back from the last spot.

Spent money includes keeper prices. Spots left start from the roster size minus the user’s keepers, then drop as the user buys players.

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

Priority: low. Build it after the draft loop works.

Auction prices drift from a model because the room spends faster or slower than the price list. Inflation compares money still in the auction with the model value of players still available, then scales the remaining prices. The user can see the factor and the adjusted prices. Until this exists, the base personal prices are still the list the user drafts from.

## 7. Feature breakdown

### League setup

- Create and edit one local league profile: name, season, team count, budget, roster size, active categories.
- Save the profile on this machine.
- Changing a setting that affects money or categories refreshes the price list.

### Season data

- Download players, teams, and prior-season stats for the selected season, once.
- Show when that download last succeeded.
- On a later launch, refresh current-season stats and status flags if they were not refreshed today.
- Stay usable when current-season stats are empty.

### Price list

- Base z-score prices for the active categories.
- A punt control for zero, one, or two categories.
- A personal price column that reflects the punt.
- Rank and sort by personal price.
- Exclude kept and drafted players from the available list.

### Keepers

- Add and remove the user’s keepers with a locked price.
- Add and remove other teams’ kept players, with an optional price.
- Apply those facts to budget, spots, pool, and category balance immediately.

### Draft board

- Record a sale: player, price, my team or another team.
- Undo the last sale, in case of a mistype.
- Show spent, remaining, spots left, and max bid at all times during the draft.
- Filter the remaining pool.
- Show a short nomination list with a one-line reason tied to the punt.

### Category balance

- One row or card per active category.
- Value for the user’s current roster.
- A punt marker on punted categories.
- A simple read of strong versus thin for categories the user is keeping.

### Inflation

- A single inflation factor from money left versus value left.
- Adjusted prices for remaining players.
- Clearly secondary to the personal price. The user can ignore it.

## 8. Main flows

### First launch of a season

1. User opens the app and enters league settings.
2. App downloads players, teams, and prior-season stats if that season is not loaded yet.
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

1. User undoes the last sale.
2. The player returns to the pool and the budget returns to the previous numbers.

## 9. What “done” means for this stage

A user can, on one machine, with instructions from the README:

- Load a season of player data.
- Set a 9-category or 8-category auction league.
- Get a base price list and a price list with one or two punted categories.
- Enter keepers and see budget and roster effects.
- Run through a mock or real draft by typing sales.
- See max bid and category balance change after each of their own buys.
- Optionally see inflation-adjusted prices.

They cannot manage the season after the draft in this stage. That is a later scope.

## 10. Decisions already made

These are product decisions, so implementation should follow them unless we change this file.

- One local user. No accounts.
- Prior-season stats are the valuation baseline. Current-season stats are stored and shown. They do not replace the baseline in this stage.
- No projection model.
- No position eligibility.
- Punt means drop that category and recompute, for one or two categories.
- Max bid reserves $1 for every spot still open after the player being bid on.
- Other teams’ keepers come off the board even when their price is blank.
- Inflation is last and optional for the draft to be usable.
- The league host is not integrated. Draft results are manual.
