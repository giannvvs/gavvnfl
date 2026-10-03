import json
import pandas as pd

SEASONS = [2025, 2026]
BASES = [
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/",
    "https://github.com/nflverse/nflverse-data/releases/download/player_stats/",
]
NAMES = ["stats_player_week_{y}.csv", "stats_player_{y}.csv", "player_stats_{y}.csv"]
COLS = {
    "attempts": "pAtt", "completions": "pCmp", "passing_yards": "pYds",
    "passing_tds": "pTD", "passing_interceptions": "int",
    "carries": "car", "rushing_yards": "rYds", "rushing_tds": "rTD",
    "targets": "tgt", "receptions": "rec", "receiving_yards": "recYds",
    "receiving_tds": "recTD",
}
KEYS = list(COLS.values())
POS = ["QB", "RB", "WR", "TE"]

frames = []
for y in SEASONS:
    ok = False
    for base in BASES:
        for name in NAMES:
            url = base + name.format(y=y)
            try:
                d = pd.read_csv(url, low_memory=False)
                frames.append(d)
                print("OK", y, len(d), "filas ->", url)
                ok = True
                break
            except Exception as e:
                print("falla:", url, "->", e)
        if ok:
            break
    if not ok:
        print("No se encontró la temporada", y)
if not frames:
    raise SystemExit("Sin datos descargados")

df = pd.concat(frames, ignore_index=True)
if "season_type" in df.columns:
    df = df[df["season_type"] == "REG"]
team_col = "team" if "team" in df.columns else "recent_team"
name_col = "player_display_name" if "player_display_name" in df.columns else "player_name"
df = df[df["position"].isin(POS)].copy()
df = df.rename(columns=COLS)
for k in KEYS:
    df[k] = pd.to_numeric(df.get(k, 0), errors="coerce").fillna(0)
df["key"] = df["season"] * 100 + df["week"]
df = df.sort_values(["key"])

last_keys = sorted(df["key"].unique())[-3:]
players = {}
for pid, g in df.groupby("player_id"):
    g = g.sort_values("key")
    if g["key"].iloc[-1] not in last_keys or len(g) < 3:
        continue
    tail = g.tail(17)
    logs = [{
        "season": int(r["season"]), "week": int(r["week"]),
        "opp": str(r["opponent_team"]), "snapPct": None,
        "stats": {k: float(r[k]) for k in KEYS},
    } for _, r in tail.iterrows()]
    recent = g.tail(4)
    score = float((recent["car"] + recent["tgt"] + recent["pAtt"]).sum())
    players[str(pid)] = {
        "name": str(g[name_col].iloc[-1]), "pos": str(g["position"].iloc[-1]),
        "team": str(g[team_col].iloc[-1]), "score": score, "logs": logs,
    }

per_game = (df.groupby(["key", "opponent_team", "position"])[KEYS].sum().reset_index())
defense = {}
per_pos = {}
for (opp, pos), g in per_game.groupby(["opponent_team", "position"]):
    m = g.sort_values("key").tail(6)[KEYS].mean()
    per_pos.setdefault(pos, {})[opp] = m
for pos, teams in per_pos.items():
    league = pd.DataFrame(teams).T.mean()
    for opp, m in teams.items():
        defense.setdefault(opp, {})[pos] = {
            "allowed": {k: round(float(m[k]), 3) for k in KEYS},
            "league": {k: round(float(league[k]), 3) for k in KEYS},
        }

with open("nfl_data.json", "w") as f:
    json.dump({"players": players, "defense": defense}, f, separators=(",", ":"))
print("Listo:", len(players), "jugadores,", len(defense), "defensas -> nfl_data.json")