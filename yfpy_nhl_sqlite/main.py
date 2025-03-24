import argparse
import contextlib
import logging
import os
import sqlite3
import sys
from importlib.metadata import version

from yfpy_nhl_sqlite.queries import YahooAPIImporter

logger = logging.getLogger(__name__)


def run():
    """Function called when the script is invoked from the cli."""
    args = _get_parsed_args(*sys.argv[1:])
    _configure_logging(args.debug)
    try:
        db_path, schema_path = _get_paths(args.league_id)
        if os.path.isfile(db_path):
            _handle_db_overwrite(db_path, force=args.force)
        with open(schema_path, "r") as f:
            schema = f.read()
            logger.debug("Loaded schema file")
        with _get_db_connection(db_path) as con:
            con.executescript(schema)
            con.commit()
            logger.info("DB tables created from schema")
            YahooAPIImporter(
                con,
                args.league_id,
                yahoo_consumer_key=args.yahoo_consumer_key,
                yahoo_consumer_secret=args.yahoo_consumer_secret,
            ).import_data()
            logger.info("Exiting...")
    except Exception:
        logger.critical("Fatal error. Aborting import.", exc_info=True)
        sys.exit(1)


def get_importer_for_db(
    league_id,
    db_path=None,
    *,
    yahoo_consumer_key=None,
    yahoo_consumer_secret=None,
    debug_logging=False,
):
    """Get an importer instance for an existing database. Useful for debugging."""
    _configure_logging(debug_logging)
    if db_path is None:
        db_path, _ = _get_paths(league_id)
    con = sqlite3.connect(db_path)
    return YahooAPIImporter(
        con,
        league_id,
        yahoo_consumer_key=yahoo_consumer_key,
        yahoo_consumer_secret=yahoo_consumer_secret,
    )


def _handle_db_overwrite(db_path, *, force):
    if not force:
        while True:
            user_input = input(f"Existing database {db_path} found. Overwrite [y/N]? ")
            valid_inputs = ["", "n", "y"]
            if user_input not in valid_inputs:
                logger.warning("Invalid input provided")
                continue
            overwrite = user_input == "y"
            if not overwrite:
                logger.info("Import aborted. Exiting...")
                sys.exit(0)
            break
    os.remove(db_path)
    logger.info(f"Deleted existing database {db_path}")


def _get_parsed_args(*args):
    parser = argparse.ArgumentParser(
        prog="yfpy-nhl-sqlite",
        description="""Build a sqlite db from a Yahoo NHL fantasy league using the NHL \
API and the Yahoo API via the yfpy library.

Authenticate with Yahoo by providing a Yahoo consumer key & secret either as \
command-line arguments or in an .env file in the current working directory. For more \
information on Yahoo authentication and the .env file format, see the yfpy docs.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("league_id", type=int, help="Yahoo league id to import")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force overwriting existing database for league",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="run with debug output",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        help="Show script version",
        version="%(prog)s v{}".format(version("yfpy-nhl-sqlite")),
    )
    parser.add_argument(
        "-k",
        "--yahoo-consumer-key",
        help="Yahoo consumer key for authentication. Falls backs to key in .env file if not provided.",
    )
    parser.add_argument(
        "-s",
        "--yahoo-consumer-secret",
        help="Yahoo consumer secret for authentication. Falls backs to secret in .env file if not provided.",
    )
    return parser.parse_args(args)


def _configure_logging(debug):
    level = logging.INFO
    if debug:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
    )


def _get_paths(league_id):
    db_path = os.path.join(os.getcwd(), f"yahoo-nhl-{league_id}.db")
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    return db_path, schema_path


@contextlib.contextmanager
def _get_db_connection(db_path):
    con = sqlite3.connect(db_path)
    try:
        yield con
    finally:
        con.close()


if __name__ == "__main__":
    run()
