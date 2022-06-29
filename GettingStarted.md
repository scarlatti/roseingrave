# Getting Started

To run the script yourself, clone the repository into a folder of your choice:

```bash
root$ git clone https://github.com/josephlou5/roseingrave.git
```

Install the required Python packages in a virtual environment:

```bash
root$ python3 -m venv env
root$ source env/bin/activate
(env) root$ python3 -m pip install -r roseingrave/requirements.txt
```

_Note: This project was developed in Python 3.10.2. Not tested on other
versions._

In this folder, place your OAuth credentials file (see
[Credentials](README.md#credentials)), the optional `roseingrave.json` file (see
[Settings](README.md#settings)), and all required and optional input files.

See [Commands](README.md#commands) for detailed documentation on commands and
options.

## Basic Step-by-step

1. Create piece definitions and volunteer definitions.

1. Create volunteer spreadsheets from definitions:

   ```bash
   (env) root$ python3 -m roseingrave create_sheet
   ```

1. Have volunteers fill out their spreadsheets.

1. Export volunteer data from filled out spreadsheets:

   ```bash
   (env) root$ python3 -m roseingrave volunteer_summary
   ```

1. Extract piece data from volunteer JSON data files:

   ```bash
   (env) root$ python3 -m roseingrave piece_summary
   ```

1. Compile all piece data into the summary file:

   ```bash
   (env) root$ python3 -m roseingrave compile_pieces
   ```

1. Create master spreadsheet with data from summary file:

   ```bash
   (env) root$ python3 -m roseingrave import_master
   ```

1. Fill out summary columns as desired.

1. Export updated master spreadsheet into summary file:

   ```bash
   (env) root$ python3 -m roseingrave export_master
   ```
