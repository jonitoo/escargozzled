# Escargozzled 🐌🍺

Ride your racing snail 🐌 down the road and collect drinks. A drink counts as hit
when it reaches the snail's height and overlaps with it sideways.

## Drinks

| Drink             | Points | Look                                   | Sound              | Frequency |
|-------------------|-------:|----------------------------------------|--------------------|----------:|
| Large beer        |   +1   | large brown bottle, yellow bottle cap  | pop + fizz         |    ≈29 %  |
| Medium beer       |   +2   | green bottle                           | pop + fizz         |    ≈20 %  |
| Small craft beer  |   +5   | small bottle with a golden shimmer     | pop + chime        |     ≈8 %  |
| Cola              |   −1   | dark bottle, red label                 | low buzz           |    ≈15 %  |
| Water             |   −2   | light blue bottle, blue cap            | low buzz           |    ≈12 %  |
| Fanta             |   −1   | orange bottle, blue label              | low buzz           |    ≈15 %  |

Small beers are rare and, being small, harder to hit.

## Display

Top center:

- **🍺 Score** – total points since the start of the game (can go negative).
- **Rate (P/min)** – total points of the last 60 seconds (rolling window).
- **Zeit** (time) – elapsed game time.
- **Leben** (lives) – remaining lives as hearts (❤️ = left, 🖤 = lost).

Every hit briefly shows the points, e.g. `+5 🍻` (yellow) or `-2 💧` (red).
Beer bottles foam when collected (the small beer also sprays stars); minus drinks
splash and shake the screen.

The track changes its look with the level zone:

| Zone   | Mood                                                 |
|--------|------------------------------------------------------|
| Green  | Day – blue sky, clouds, green meadow                 |
| Orange | Sunset – striped sun, first stars                    |
| Red    | Neon night – synthwave grid, glowing trees           |

## Lives & walls

You start with **5 lives**. Walls with hazard stripes keep showing up:

- **Short walls** stand somewhere on the road – just steer around them.
- **Wide walls** block the road from one edge; there is always a gap on the
  other side.

With every level the walls come a bit more often (shorter distance between
them), but never so close that the road is fully blocked.

Hitting a wall costs one life (crash sound, screen shake). Afterwards the snail
blinks for 1.5 s and is invulnerable during that time. At 0 lives the game ends
("💥 Keine Leben mehr!" – no lives left) and the score can be saved.

## Levels

15 levels in three zones. A colored bar below the top bar shows the level, goal
and progress. On level-up, `LEVEL n` appears with a fanfare.

| Level | Zone      | Goal                                                         |
|------:|-----------|--------------------------------------------------------------|
|     1 | 🟢 Green  | Collect 5 points within the level                            |
|     2 | 🟢 Green  | 10 points                                                    |
|     3 | 🟢 Green  | 15 points                                                    |
|     4 | 🟢 Green  | 20 points                                                    |
|     5 | 🟢 Green  | 30 points                                                    |
|     6 | 🟠 Orange | Hold ≥ 15 points/min for 30 s                                |
|     7 | 🟠 Orange | Hold ≥ 20 points/min for 30 s                                |
|     8 | 🟠 Orange | Hold ≥ 25 points/min for 30 s                                |
|     9 | 🟠 Orange | Hold ≥ 30 points/min for 30 s                                |
|    10 | 🟠 Orange | Hold ≥ 35 points/min for 30 s                                |
|    11 | 🔴 Red    | Hold ≥ 40 points/min for 30 s, **no minus points**           |
|    12 | 🔴 Red    | Hold ≥ 45 points/min for 30 s, **no minus points**           |
|    13 | 🔴 Red    | Hold ≥ 50 points/min for 30 s, **no minus points**           |
|    14 | 🔴 Red    | Hold ≥ 55 points/min for 30 s, **no minus points**           |
|    15 | 🔴 Red    | Hold ≥ 60 points/min for 30 s, **no minus points**           |

Rules:

- **Green:** only points collected in the current level count (minus points are
  subtracted here too).
- **Orange/Red:** the hold timer runs as long as the rate (last 60 s) meets the
  target. If the rate drops below it, the hold timer restarts at 0.
- **Red:** additionally, every minus point resets the hold timer to 0.
- After level 15, "Alle Level geschafft" (all levels completed) appears.

The level targets are defined in `LEVELS` in `index.html` (`target` for green,
`rate`/`holdSec`/`noMinus` for orange and red).

## Zombie sprints

Zombies randomly appear **behind** the snail with a roar. Higher levels make
attacks more frequent. The first 15 seconds and at least 18 seconds after each
rescue are attack-free; attacks only start while riding.

- A warning shows the distance to the horde, the required watts and the rescue
  countdown. The fixed sprint target is at least **175 W**, and otherwise at
  least **30% plus 40 W above your current/recent riding power**.
- Below that target the zombies close in; above it you build distance.
  Steering alone cannot escape them. The trainer measures **power**, not cadence:
  pedal harder/faster to raise watts.
- Getting caught costs **one life** and pushes the horde back; the chase continues.
  The usual brief invulnerability also applies.
- After **20 seconds of active gameplay**, a cannon blasts the whole horde away,
  with sound and a flash. Normal play resumes without changing your score or level.
- Ending/restarting the game clears the chase. Sounds require a click/key press.

Run the chase regression tests with `node --test tests/zombie-chase.test.cjs`
(no additional dependencies).

## Game time & highscores

- The game time runs from page load or "Neues Spiel" (new game).
- The game ends via **"Spiel beenden"** (end game), when all lives are lost, or
  automatically after level 15.
- Then enter a name → **"Score speichern"** (save score) → your rank and the top 10
  are shown.
- **Ranking:** higher score first; on equal scores the shorter time wins.
- Scores are stored in `scores.json` (name, score, level, time in seconds, date).

Start with the highscore server (Web Bluetooth works on `localhost`):

```bash
python3 server.py 8000
```

Then open `http://localhost:8000` in Chrome. Without the server the game still
runs, only saving scores fails.

## Controls

- **Speed** via the power of the Elite Avanti (watts).
- **Steering** with the Elite Sterzo Smart.
- Without hardware: arrow keys ↑/↓ for watts, ←/→ for steering.
  ↑ adds 25 W without an upper cap, so sprint targets remain reachable.
- Sounds only start after the first click or key press (browser policy).

## Customizing

Points, size (`scale`), frequency (`weight`) and colors of the drinks are defined
in `DRINKS` in `index.html`. The frequency is `weight` relative to the sum of all
weights (currently 98).

Lives and walls: `MAX_LIVES`, `INVULNERABLE_MS`, `spawnWall()` (width/position) and
`wallGap()` (distance between walls per level) in `index.html`.
