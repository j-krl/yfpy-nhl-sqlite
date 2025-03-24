-- The rowid represents the Yahoo id for each entity it's available
CREATE TABLE metadata (key_ TEXT NOT NULL UNIQUE, value TEXT NOT NULL);

CREATE TABLE week (
  idx INTEGER NOT NULL UNIQUE,
  start_ TEXT NOT NULL,
  end_ TEXT NOT NULL
);

CREATE TABLE position(
  abbr TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL UNIQUE,
  is_starting_position INTEGER NOT NULL,
  type_ TEXT NOT NULL,
  count_ INTEGER NOT NULL,
  enabled INTEGER NOT NULL
);

CREATE TABLE stat (
  abbr TEXT NOT NULL,
  name TEXT NOT NULL,
  external_name TEXT,
  value REAL NOT NULL
);

CREATE TABLE stat_position_type (
  stat_id INTEGER NOT NULL,
  position_type TEXT NOT NULL,
  FOREIGN KEY (stat_id) REFERENCES stat (rowid)
);

CREATE TABLE player (
  external_id INTEGER UNIQUE,
  yahoo_key TEXT NOT NULL UNIQUE,
  team_code TEXT NOT NULL,
  position_type TEXT NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL
);

CREATE TABLE player_position (
  player_id INTEGER NOT NULL,
  position_id INTEGER NOT NULL,
  FOREIGN KEY (player_id) REFERENCES player (rowid),
  FOREIGN KEY (position_id) REFERENCES position(rowid)
);

CREATE TABLE player_stat (
  stat_id INTEGER NOT NULL,
  player_id INTEGER NOT NULL,
  date_ TEXT NOT NULL,
  value REAL NOT NULL,
  FOREIGN KEY (stat_id) REFERENCES stat (rowid),
  FOREIGN KEY (player_id) REFERENCES player (rowid)
);

CREATE TABLE team (
  yahoo_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL
);

CREATE TABLE matchup (
  week_id INTEGER NOT NULL,
  FOREIGN KEY (week_id) REFERENCES week (rowid)
);

CREATE TABLE matchup_team (
  team_id INTEGER NOT NULL,
  matchup_id INTEGER NOT NULL,
  yahoo_points REAL NOT NULL,
  is_winner INTEGER NOT NULL,
  is_tied INTEGER NOT NULL,
  FOREIGN KEY (team_id) REFERENCES team (rowid),
  FOREIGN KEY (matchup_id) REFERENCES matchup (rowid)
);

CREATE TABLE draft_pick (
  team_id INTEGER NOT NULL,
  player_id INTEGER NOT NULL,
  idx INTEGER NOT NULL,
  FOREIGN KEY (team_id) REFERENCES team (rowid),
  FOREIGN KEY (player_id) REFERENCES player (rowid)
);

CREATE TABLE transaction_ (
  yahoo_key TEXT NOT NULL UNIQUE,
  timestamp_ TEXT NOT NULL,
  type_ TEXT NOT NULL
);

CREATE TABLE transaction_player (
  transaction_id INTEGER NOT NULL,
  player_id INTEGER NOT NULL,
  from_team_id INTEGER,
  to_team_id INTEGER,
  FOREIGN KEY (transaction_id) REFERENCES trade (rowid),
  FOREIGN KEY (player_id) REFERENCES player (rowid),
  FOREIGN KEY (from_team_id) REFERENCES team (rowid),
  FOREIGN KEY (to_team_id) REFERENCES team (rowid)
);
