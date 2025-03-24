import datetime
import logging
import os
import pathlib
import unicodedata

import requests
from yfpy.query import YahooFantasySportsQuery

logger = logging.getLogger(__name__)


class YahooAPIImporter:
    STAT_ABBR_TO_EXTERNAL_NAME_MAP = {
        "A": "assists",
        "BLK": "blockedShots",
        "GWG": "gameWinningGoals",
        "G": "goals",
        "HIT": "hits",
        "PIM": "penaltyMinutes",
        "+/-": "plusMinus",
        "P": "points",
        "PPG": "ppGoals",
        "PPA": "",
        "PPP": "ppPoints",
        "SHG": "shGoals",
        "SHP": "shPoints",
        "SHA": "",
        "SH%": "shootingPct",
        "SOG": "shots",
        "FW": "totalFaceoffWins",
        "FL": "totalFaceoffLosses",
        "GS": "gamesStarted",
        "GA": "goalsAgainst",
        "GAA": "goalsAgainstAverage",
        "T": "ties",
        "L": "losses",
        "SV%": "savePct",
        "SV": "saves",
        "SA": "shotsAgainst",
        "SHO": "shutouts",
        "W": "wins",
        "GP": "gamesPlayed",
    }

    def __init__(
        self, con, league_id, *, yahoo_consumer_key=None, yahoo_consumer_secret=None
    ):
        self.con = con
        self.league_id = league_id
        self.game_id = None
        self.game_info = None
        self.league_info = None
        self.league_settings = None
        self.season_start_date = None
        self.season_end_date = None
        self._player_id_lookup = {}  # Map of NHL API player id to Yahoo player id
        self._skater_stat_id_lookup = {}  # Map of external stat name to Yahoo skater stat id
        self._goalie_stat_id_lookup = {}  # Map of external stat name to Yahoo goalie stat id
        self._skater_toi_id = None  # Yahoo API's stat id for skater TOI
        self._ppa_id = None  # Powerplay assists Yahoo id
        self._sha_id = None  # Shorthanded assists Yahoo id
        self._goalie_saves_id = None  # Yahoo API's stat id for goalie saves
        self._yahoo_consumer_key = yahoo_consumer_key
        self._yahoo_consumer_secret = yahoo_consumer_secret
        self._yahoo_access_token = None
        self.yq = None
        self._refresh_yahoo_query()

    def import_data(self):
        logger.info("Starting data import")
        self._load_metadata()
        self._import_league_data()
        self._import_player_data()
        self._import_team_data()
        self._import_transaction_data()
        self._import_external_player_data()
        logger.info("Data import complete")

    def _refresh_yahoo_query(self):
        logger.debug(f"Refreshing Yahoo query with game_id {self.game_id}")
        kwargs = {}
        if self._yahoo_access_token is not None:
            kwargs["yahoo_access_token_json"] = self._yahoo_access_token
            logger.debug("Refreshing with cached access token")
        elif (
            self._yahoo_consumer_key is not None
            and self._yahoo_consumer_secret is not None
        ):
            kwargs["yahoo_consumer_key"] = self._yahoo_consumer_key
            kwargs["yahoo_consumer_secret"] = self._yahoo_consumer_secret
            logger.debug("Refreshing with provided credentials")
        else:
            kwargs["env_file_location"] = pathlib.Path(os.getcwd())
            kwargs["save_token_data_to_env_file"] = True
            logger.debug("Refreshing with env file credentials")
        self.yq = YahooFantasySportsQuery(
            league_id=self.league_id, game_code="nhl", game_id=self.game_id, **kwargs
        )
        self._yahoo_access_token = self.yq._yahoo_access_token_dict

    def _load_metadata(self):
        self.game_info = self.yq.get_current_game_info()
        self.game_id = self.game_info.game_id
        logger.debug(f"Set game_id for league: {self.game_id}")
        # Refresh the yahoo query once we have the game_id. Queries without the game_id
        # set give superfluous yfpy logger warnings.
        self._refresh_yahoo_query()
        self.league_info = self.yq.get_league_info()
        self.league_settings = self.yq.get_league_settings()
        season_start_date, season_end_date = self._get_season_date_range()
        self.season_start_date = season_start_date
        self.season_end_date = season_end_date
        logger.debug(
            f"Set season start and end dates: {self.season_start_date} - {self.season_end_date}"
        )

    def _get_id_from_key(self, key):
        """Get a Yahoo id from a Yahoo key."""
        return int(key.split(".")[-1])

    def _get_external_season_id(self):
        """Get the NHL API's season id for the Yahoo game."""
        season_start = str(self.game_info.season)
        season_end = str(self.game_info.season + 1)
        id_ = int(season_start + season_end)
        return id_

    def _get_season_date_range(self):
        """Get the start and end dates of the regular season from the NHL API."""
        external_season_id = self._get_external_season_id()
        data = NHLAPI.get_season_data(external_season_id)
        start_str = data["startDate"].split("T")[0]
        end_str = data["regularSeasonEndDate"].split("T")[0]
        DATE_FMT = "%Y-%m-%d"
        start_date = datetime.datetime.strptime(start_str, DATE_FMT).date()
        end_date = datetime.datetime.strptime(end_str, DATE_FMT).date()
        return start_date, end_date

    def _import_league_data(self):
        logger.info("Importing league data...")
        params = {}
        params["metadata"] = self._get_metadata_rows()
        logger.debug("Generated metadata rows")
        params["weeks"] = self._get_week_rows()
        logger.debug("Generated week rows")
        params["positions"] = self._get_position_rows()
        logger.debug("Generated position rows")
        params["stats"], params["stat_position_types"] = self._get_stat_rows()
        logger.debug("Generated stat rows")
        self._write_league_data(params)
        logger.info("League data import complete")
        self._set_stat_id_lookups()

    def _get_metadata_rows(self):
        params = [
            ("game_id", self.game_info.game_id),
            ("game_key", self.game_info.game_key),
            ("league_id", self.league_id),
            ("league_key", self.league_info.league_key),
            ("league_name", self.league_info.name),
            ("start_date", self.league_info.start_date),
            ("end_date", self.league_info.end_date),
            ("start_week", self.league_info.start_week),
            ("end_week", self.league_info.end_week),
            ("num_playoff_teams", self.league_settings.num_playoff_teams),
            (
                "num_playoff_consolation_teams",
                self.league_settings.num_playoff_consolation_teams,
            ),
            ("playoff_start_week", self.league_settings.playoff_start_week),
            ("season_start_date", self.season_start_date),
            ("season_end_date", self.season_end_date),
        ]
        return params

    def _get_week_rows(self):
        rows = []
        weeks = self.game_info.game_weeks
        for week in weeks:
            rows.append((int(week.week), int(week.week), week.start, week.end))
        return rows

    def _get_position_rows(self):
        rows = []
        league_data = {}
        for position in self.league_settings.roster_positions:
            league_data[position.position] = {
                "is_starting_position": position.is_starting_position,
                "count": position.count,
                "enabled": 1,
            }
        for idx, position in enumerate(self.game_info.roster_positions):
            league_position = league_data.get(
                position.position, {"is_starting_position": 0, "count": 0, "enabled": 0}
            )
            rows.append(
                (
                    idx,
                    position.position,
                    position.display_name,
                    league_position["is_starting_position"],
                    position.position_type,
                    league_position["count"],
                    league_position["enabled"],
                )
            )
        return rows

    def _get_stat_rows(self):
        stat_rows, position_type_rows = [], []
        values = {}
        for stat in self.league_settings.stat_modifiers.stats:
            values[stat.stat_id] = stat.value
        for stat in self.game_info.stat_categories.stats:
            external_name = self.STAT_ABBR_TO_EXTERNAL_NAME_MAP.get(stat.display_name)
            if stat.display_name == "TOI":
                # TOI has a different id and external name if the position type is a
                # goalie or skater.
                if stat.position_types[0] == "G":
                    external_name = "timeOnIce"
                elif stat.position_types[0] == "P":
                    external_name = "timeOnIcePerGame"
            if external_name is None:
                continue
            stat_rows.append(
                (
                    stat.stat_id,
                    stat.display_name,
                    stat.name,
                    external_name,
                    values.get(stat.stat_id, 0),
                )
            )
            for position_type in stat.position_types:
                position_type_rows.append((stat.stat_id, position_type))
        return stat_rows, position_type_rows

    def _set_stat_id_lookups(self):
        """Get map of NHL API stat name to Yahoo API stat id."""
        sql = """
            SELECT s.external_name, s.name, s.rowid, s.abbr, spt.position_type 
            FROM stat s
            JOIN stat_position_type spt ON spt.stat_id = s.rowid
            WHERE spt.position_type IN ('G', 'P')
        """
        skater_lookup, goalie_lookup = {}, {}
        for external_name, yahoo_name, id_, abbr, position_type in self.con.execute(
            sql
        ).fetchall():
            lookup = skater_lookup if position_type == "P" else goalie_lookup
            if abbr == "TOI":
                if position_type == "P":
                    lookup["timeOnIcePerGame"] = id_  # skaters
                    self._skater_toi_id = id_
                    logger.debug("Cached Yahoo id for skater TOI")
                else:
                    lookup["timeOnIce"] = id_  # goalies
                continue
            elif abbr == "SV":
                self._goalie_saves_id = id_
                logger.debug("Cached Yahoo id for SV")
            elif abbr == "PPA":
                self._ppa_id = id_
                logger.debug("Cached Yahoo id for PPA")
                continue
            elif abbr == "SHA":
                self._sha_id = id_
                logger.debug("Cached Yahoo id for SHA")
                continue
            lookup[external_name] = id_
        self._skater_stat_id_lookup = skater_lookup
        logger.debug(
            f"External name to skater stat id map set with {len(skater_lookup)} entries"
        )
        self._goalie_stat_id_lookup = goalie_lookup
        logger.debug(
            f"External name to goalie stat id map set with {len(goalie_lookup)} entries"
        )

    def _write_league_data(self, params):
        metadata_cols = ("key_", "value")
        weeks_cols = ("rowid", "idx", "start_", "end_")
        positions_cols = (
            "rowid",
            "abbr",
            "display_name",
            "is_starting_position",
            "type_",
            "count_",
            "enabled",
        )
        stats_cols = (
            "rowid",
            "abbr",
            "name",
            "external_name",
            "value",
        )
        stat_position_types_cols = ("stat_id", "position_type")
        metadata_sql = f"""
            INSERT OR REPLACE INTO metadata ({",".join(metadata_cols)})
            VALUES ({",".join(("?") * len(metadata_cols))})
        """
        weeks_sql = f"""
            INSERT OR REPLACE INTO week ({",".join(weeks_cols)})
            VALUES ({",".join(("?") * len(weeks_cols))})
        """
        positions_sql = f"""
            INSERT OR REPLACE INTO position ({",".join(positions_cols)})
            VALUES ({",".join(("?") * len(positions_cols))})
        """
        stats_sql = f"""
            INSERT OR REPLACE INTO stat ({",".join(stats_cols)})
            VALUES ({",".join(("?") * len(stats_cols))})
        """
        stat_position_types_sql = f"""
            INSERT OR REPLACE INTO stat_position_type (
                {",".join(stat_position_types_cols)}
            )
            VALUES ({",".join(("?") * len(stat_position_types_cols))})
        """
        self.con.executemany(metadata_sql, params["metadata"])
        self.con.executemany(weeks_sql, params["weeks"])
        self.con.executemany(positions_sql, params["positions"])
        self.con.executemany(stats_sql, params["stats"])
        self.con.executemany(stat_position_types_sql, params["stat_position_types"])
        self.con.commit()
        logger.debug("League data committed to DB")

    def _import_player_data(self):
        logger.info("Importing player data...")
        params = {}
        params["players"], params["positions"] = self._get_player_rows()
        logger.debug("Generated player and player_position rows")
        self._write_player_data(params)
        logger.info("Player data import complete")

    def _get_player_rows(self):
        player_rows, position_rows = [], []
        position_id_lookup = self._get_position_id_lookup()
        players = self.yq.get_league_players()
        for player in players:
            player_rows.append(
                (
                    player.player_id,
                    player.player_key,
                    player.editorial_team_abbr,
                    player.position_type,
                    self._normalize_name(player.name.first),
                    self._normalize_name(player.name.last),
                )
            )
            positions = player.display_position.split(",")
            for position in positions:
                position_id = position_id_lookup[position]
                position_rows.append((player.player_id, position_id))
        return player_rows, position_rows

    def _get_position_id_lookup(self):
        """Get a map of Yahoo position abbr to position id."""
        lookup = {}
        sql = "SELECT abbr, rowid FROM position"
        rows = self.con.execute(sql).fetchall()
        for abbr, id_ in rows:
            lookup[abbr] = id_
        return lookup

    def _write_player_data(self, params):
        players_cols = (
            "rowid",
            "yahoo_key",
            "team_code",
            "position_type",
            "first_name",
            "last_name",
        )
        positions_cols = ("player_id", "position_id")
        players_sql = f"""
            INSERT OR REPLACE INTO player ({",".join(players_cols)})
            VALUES ({",".join(("?") * len(players_cols))})
        """
        positions_sql = f"""
            INSERT OR REPLACE INTO player_position ({",".join(positions_cols)})
            VALUES ({",".join(("?") * len(positions_cols))})
        """
        self.con.executemany(players_sql, params["players"])
        self.con.executemany(positions_sql, params["positions"])
        self.con.commit()
        logger.debug("Player data committed to DB")

    def _import_team_data(self):
        logger.info("Importing team data...")
        params = {}
        params["teams"] = self._get_team_rows()
        logger.debug("Generated team rows")
        params["matchups"], params["matchup_teams"] = self._get_matchup_rows()
        logger.debug("Generated matchup and matchup_team rows")
        params["draft"] = self._get_draft_rows()
        logger.debug("Generated draft rows")
        self._write_team_data(params)
        logger.info("Team data import complete")

    def _get_team_rows(self):
        rows = []
        teams = self.yq.get_league_teams()
        for team in teams:
            rows.append((team.team_id, team.team_key, team.name))
        return rows

    def _get_matchup_rows(self):
        matchup_rows, team_rows = [], []
        start_week, end_week = (
            int(self.league_info.start_week),
            int(self.league_info.end_week),
        )
        matchup_id = 1
        for week in range(start_week, end_week + 1):
            matchups = self.yq.get_league_matchups_by_week(week)
            for matchup in matchups:
                matchup_rows.append((matchup_id, week))
                for team in matchup.teams:
                    is_winner = int(matchup.winner_team_key == team.team_key)
                    team_rows.append(
                        (
                            team.team_id,
                            matchup_id,
                            team.team_points.total,
                            is_winner,
                            matchup.is_tied,
                        )
                    )
                matchup_id += 1
        return matchup_rows, team_rows

    def _get_draft_rows(self):
        rows = []
        draft_picks = self.yq.get_league_draft_results()
        for pick in draft_picks:
            team_id = self._get_id_from_key(pick.team_key)
            player_id = self._get_id_from_key(pick.player_key)
            rows.append((team_id, player_id, pick.pick))
        return rows

    def _write_team_data(self, params):
        teams_cols = ("rowid", "yahoo_key", "name")
        matchups_cols = ("rowid", "week_id")
        matchup_teams_cols = (
            "team_id",
            "matchup_id",
            "yahoo_points",
            "is_winner",
            "is_tied",
        )
        draft_cols = ("team_id", "player_id", "idx")
        teams_sql = f"""
            INSERT OR REPLACE INTO team ({",".join(teams_cols)})
            VALUES ({",".join(("?") * len(teams_cols))})
        """
        matchups_sql = f"""
            INSERT OR REPLACE INTO matchup ({",".join(matchups_cols)})
            VALUES ({",".join(("?") * len(matchups_cols))})
        """
        matchup_teams_sql = f"""
            INSERT OR REPLACE INTO matchup_team ({",".join(matchup_teams_cols)})
            VALUES ({",".join(("?") * len(matchup_teams_cols))})
        """
        draft_sql = f"""
            INSERT OR REPLACE INTO draft_pick ({",".join(draft_cols)})
            VALUES ({",".join(("?") * len(draft_cols))})
        """
        self.con.executemany(teams_sql, params["teams"])
        self.con.executemany(matchups_sql, params["matchups"])
        self.con.executemany(matchup_teams_sql, params["matchup_teams"])
        self.con.executemany(draft_sql, params["draft"])
        self.con.commit()
        logger.debug("Team data committed to DB")

    def _import_transaction_data(self):
        logger.info("Importing transaction data...")
        params = {}
        params["transactions"], params["transaction_players"] = (
            self._get_transaction_rows()
        )
        logger.debug("Generated transaction and transaction_player rows")
        self._write_transaction_data(params)
        logger.info("Transaction data import complete")

    def _get_transaction_rows(self):
        transaction_rows, player_rows = [], []
        transactions = self.yq.get_league_transactions()
        for transaction in transactions:
            if transaction.status != "successful":
                # Don't save failed transactions
                continue
            if transaction.type == "commish":
                continue
            transaction_rows.append(
                (
                    transaction.transaction_id,
                    transaction.transaction_key,
                    datetime.datetime.fromtimestamp(transaction.timestamp),
                    transaction.type,
                )
            )
            for player in transaction.players:
                to_team_id, from_team_id = None, None
                type = player.transaction_data.type
                if type == "drop" or type == "trade":
                    from_team_id = self._get_id_from_key(
                        player.transaction_data.source_team_key
                    )
                if type == "add" or type == "trade":
                    to_team_id = self._get_id_from_key(
                        player.transaction_data.destination_team_key
                    )
                player_rows.append(
                    (
                        transaction.transaction_id,
                        player.player_id,
                        to_team_id,
                        from_team_id,
                    )
                )
        return transaction_rows, player_rows

    def _write_transaction_data(self, params):
        transactions_cols = ("rowid", "yahoo_key", "timestamp_", "type_")
        transaction_players_cols = (
            "transaction_id",
            "player_id",
            "from_team_id",
            "to_team_id",
        )
        transactions_sql = f"""
            INSERT OR REPLACE INTO transaction_ ({",".join(transactions_cols)})
            VALUES ({",".join(("?") * len(transactions_cols))})
        """
        transaction_players_sql = f"""
            INSERT OR REPLACE INTO transaction_player ({",".join(transaction_players_cols)})
            VALUES ({",".join(("?") * len(transaction_players_cols))})
        """
        self.con.executemany(transactions_sql, params["transactions"])
        self.con.executemany(transaction_players_sql, params["transaction_players"])
        self.con.commit()
        logger.debug("Transaction data committed to DB")

    def _import_external_player_data(self):
        logger.info("Importing external player data...")
        params = {}
        season_days = (self.season_end_date - self.season_start_date).days + 1
        for i in range(0, season_days):
            date_ = self.season_start_date + datetime.timedelta(days=i)
            params["player_stats"] = self._get_player_stat_rows_for_date(date_)
            logger.debug(f"Generated player_stat rows for {date_}")
            self._write_player_stat_data(params)
            logger.debug(f"Player stat data for {date_} committed to DB")
            if date_.month != (date_ + datetime.timedelta(days=1)).month:
                month_str = date_.strftime("%B %Y")
                logger.info(f"Player stat data import for {month_str} complete")
        self._write_player_external_ids()
        logger.info("External player data import complete")

    def _get_player_stat_rows_for_date(self, date_):
        """Get all player stat rows for the given date from the NHL API.

        The Yahoo API provides no endpoint that per-player game log data can be queried
        for efficiently, so use the NHL API and match the players back to the Yahoo API.
        """
        rows = []
        for player_type in ("skater", "goalie"):
            if player_type == "skater":
                stat_id_lookup = self._skater_stat_id_lookup
                sample_stat_key = "timeOnIcePerGame"
                sample_stat_id = self._skater_toi_id
                full_name_key = "skaterFullName"
            else:
                stat_id_lookup = self._goalie_stat_id_lookup
                sample_stat_key = "saves"
                sample_stat_id = self._goalie_saves_id
                full_name_key = "goalieFullName"
            stats = NHLAPI.get_player_game_logs_for_date(date_, player_type)
            for player in stats:
                external_id = player["playerId"]
                sample_date_stat_value = player[sample_stat_key]
                full_name = player[full_name_key]
                player_id = self._get_player_id_from_external_data(
                    external_id,
                    full_name,
                    date_,
                    sample_stat_id,
                    sample_date_stat_value,
                )
                if player_id is None:
                    continue
                # Shorthanded & Powerplay assists aren't provided by the NHL API, so we
                # have to infer them ourselves
                cached_values = {
                    "ppPoints": 0,
                    "ppGoals": 0,
                    "shPoints": 0,
                    "shGoals": 0,
                }
                for entry_name, value in player.items():
                    if entry_name in cached_values.keys():
                        cached_values[entry_name] = value
                    else:
                        stat_id = stat_id_lookup.get(entry_name)
                    if stat_id is None or value == 0 or value is None:
                        continue
                    rows.append((stat_id, player_id, date_, value))
                if player_type == "goalie":
                    continue
                ppa = cached_values["ppPoints"] - cached_values["ppGoals"]
                if ppa > 0:
                    rows.append((self._ppa_id, player_id, date_, ppa))
                sha = cached_values["shPoints"] - cached_values["shGoals"]
                if sha > 0:
                    rows.append((self._sha_id, player_id, date_, sha))
        return rows

    def _get_player_id_from_external_data(
        self,
        external_id,
        external_name,
        sample_date,
        sample_stat_id,
        sample_date_stat_value,
    ):
        """Get a player's Yahoo player id from their full name and stat value on a
        given date in the NHL API.

        Attempt to match on name first, but if multiple matches are returned match on
        the date stat. Return -1 if no matches are found.
        """
        player_id = self._player_id_lookup.get(external_id)
        if player_id == -1:
            return None
        elif player_id is not None:
            return player_id
        logger.debug(
            f'Attempting to match NHL API player {external_id} "{external_name}" to Yahoo player...'
        )
        normalized_name = self._normalize_name(external_name)
        if external_name != normalized_name:
            logger.debug(f"{external_name} normalized to {normalized_name}")
        logger.debug("Attempting match by player name...")
        rows = self._select_players_by_name(normalized_name)
        id_ = None
        if len(rows) == 1:
            id_ = rows[0][0]
        elif len(rows) > 1:
            keys = [row[1] for row in rows]
            logger.debug(
                f"Attempting match by player stat on {sample_date} from {len(keys)} players {keys}..."
            )
            id_ = self._find_player_id_by_date_stat(
                keys, sample_date, sample_stat_id, sample_date_stat_value
            )
        else:
            id_ = -1
        if id_ == -1:
            logger.warning(f"Failed to match player {external_id} {external_name}")
        else:
            logger.debug(
                f'Matched NHL API player {external_id} "{external_name}" to Yahoo player id {id_}'
            )
        self._player_id_lookup[external_id] = id_
        if id_ == -1:
            return None
        return id_

    def _normalize_name(self, name):
        """Remove accents from player names."""
        # Double spacing exists on some names in the NHL API
        name = name.replace("  ", " ")
        nfkd_form = unicodedata.normalize("NFKD", name)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

    def _split_full_name(self, full_name):
        name_words = full_name.split(" ")
        first_name, last_name = name_words[0], " ".join(name_words[1:])
        return first_name, last_name

    def _select_players_by_name(self, full_name):
        """Find all Yahoo players that match a given name.

        Always attempt to return at least one player, so if there are no matches on the
        full name, return all matches on the last name. Passed first_name and last_name
        should be lower case with all accents removed.
        """
        first_name, last_name = self._split_full_name(full_name)
        sql = """
            SELECT rowid, yahoo_key FROM player
            WHERE LOWER(first_name) = (?)
            AND LOWER(last_name) = (?)
        """
        results = self.con.execute(
            sql, (first_name.lower(), last_name.lower())
        ).fetchall()
        matches = len(results)
        logger.debug(
            f'{matches} player(s) found with first name "{first_name}" and last name "{last_name}"'
        )
        if matches == 0:
            logger.debug("Attempting match by last name only...")
            sql = """
                SELECT rowid, yahoo_key FROM player
                WHERE LOWER(last_name) = (?)
            """
            results = self.con.execute(sql, (last_name.lower(),)).fetchall()
            logger.debug(f"{len(results)} player(s) found with last name {last_name}")
        return results

    def _find_player_id_by_date_stat(self, player_keys, date_, stat_id, stat_value):
        """Find Yahoo player with the given date stat value from a list of player keys."""
        for key in player_keys:
            player = self.yq.get_player_stats_by_date(
                key, date_, limit_to_league_stats=False
            )
            for stat in player.player_stats.stats:
                if stat.stat_id == stat_id and stat.value == stat_value:
                    return player.player_id
        return -1

    def _write_player_stat_data(self, params):
        player_stats_cols = ("stat_id", "player_id", "date_", "value")
        player_stats_sql = f"""
            INSERT OR REPLACE INTO player_stat ({",".join(player_stats_cols)})
            VALUES ({",".join(("?") * len(player_stats_cols))})
        """
        self.con.executemany(player_stats_sql, params["player_stats"])
        self.con.commit()

    def _write_player_external_ids(self):
        """Update players with their NHL API ids.

        NHL ids are matched to players and added to the `_player_id_lookup` cache
        during the `_import_external_player_data` import step. Note that any players
        without a regular season game played will not have a matched NHL id because
        matches are made based on regular season game log data.
        """
        for external_id, player_id in self._player_id_lookup.items():
            if player_id == -1:
                continue
            external_id_sql = "UPDATE player SET external_id = (?) WHERE rowid = (?)"
            self.con.execute(external_id_sql, (external_id, player_id))
        self.con.commit()


class NHLAPI:
    """Methods for querying the NHL API.

    This class is not intended to be instantiated. Functions are grouped into a class
    for organizational purposes.
    """

    BASE_URL = "https://api.nhle.com/stats/rest/en"

    @classmethod
    def get_season_data(cls, season_id):
        url = cls.BASE_URL + "/season"
        params = {"cayenneExp": f"id=={season_id}"}
        logger.debug(f"Querying NHL API season data for season id {season_id}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        season = data["data"][0]
        return season

    @classmethod
    def get_player_game_logs_for_date(cls, date_, type_):
        if type_ not in ("skater", "goalie"):
            raise ValueError("Invalid player type")
        players = []
        LIMIT = 100
        start = 0
        total = None
        url = cls.BASE_URL + f"/{type_}/summary"
        params = {
            "start": str(start),
            "limit": str(LIMIT),
            "cayenneExp": f'gameDate=="{date_}"',
        }
        page = 1
        while True:
            logger.debug(
                f"Querying NHL API {type_} game log data on {date_} (page {page})"
            )
            response = requests.get(url, params)
            response.raise_for_status()
            data = response.json()
            player_data = data["data"]
            if total is None:
                total = data["total"]
            start += len(player_data)
            players.extend(player_data)
            if start >= total:
                break
            params["start"] = str(start)
            page += 1
        logger.debug(f"Retrieved {len(players)} total {type_}s")
        return players

    def __init__(self):
        raise NotImplementedError("Instantiation not supported for NHLAPI")
