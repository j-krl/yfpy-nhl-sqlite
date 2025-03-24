# yfpy-nhl-sqlite

Create a SQLite database from your Yahoo NHL fantasy league data in minutes.

View the [schema](yfpy_nhl_sqlite/schema.sql) to see what data is stored.

## Installation

The supported installation method is with [pipx](https://pipx.pypa.io/stable/). Install with `pipx install yfpy-nhl-sqlite`.

## Authentication

Authentication is required with the Yahoo API to retrieve private league data. To obtain a Yahoo consumer key and consumer secret, you must set up a Yahoo Developer Network App. See the [Setup section](https://yfpy.uberfastman.com/readme/#yahoo-developer-network-app) of the yfpy docs for details.

Once you have obtained a consumer key and secret, yfpy-nhl-sqlite provides two ways to authenticate:

1. Provide `--yahoo-consumer-key` and `--yahoo-consumer-secret` as command-line arguments.
2. Create an .env file in the directory yfpy-nhl-sqlite will be invoked with the variables `YAHOO_CONSUMER_KEY` and `YAHOO_CONSUMER_SECRET` set.

## Usage

Run the script with the following command, substituting in your Yahoo league's id:

```
yfpy-nhl-sqlite LEAGUE_ID
```

A SQLite database will be created in the directory the script is invoked from. Your Yahoo league's id can be found in league settings in the Yahoo fantasy web or mobile app.

## Limitations

- Any changes to the NHL and Yahoo APIs will likely cause breaking changes to this library.
- Not all data is ported that is available through the Yahoo API. If you'd like some data to be included that is missing, open an issue.
- The schema has only been tested with head-to-head private leagues. Other league types may work but are not officially supported, though there is desire to support them in the future.

## Acknowledgements

This package is just a small script that wraps the [yfpy library](https://github.com/uberfastman/yfpy). Thanks to uberfastman for the great work there.
