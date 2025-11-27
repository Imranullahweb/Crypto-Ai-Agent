# Crypto Agent

A small command-line crypto analysis agent that fetches market data from CoinGecko, computes simple technical indicators with pandas, and uses the Gemini generative API for short analysis.

**Location:** `crypto_agent.py`

**Quick summary:**
- Run directly with a GEMINI API key passed on the command line (no environment variables required):

  ```powershell
  py crypto_agent.py --api-key "YOUR_GEMINI_API_KEY"
  ```

- Or set the environment variable in PowerShell for the current session:

  ```powershell
  $env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
  py crypto_agent.py
  ```

- To persist across new terminals (requires opening a new terminal afterwards):

  ```powershell
  setx GEMINI_API_KEY "YOUR_GEMINI_API_KEY"
  ```

Notes: I do NOT recommend committing API keys to your repository. Use `--api-key` for quick runs or a local `.env` file for development (see below).

**Requirements / Dependencies**
- Python 3.8+ (the `py` launcher is used below for Windows)
- The script uses these Python packages:
  - `requests`
  - `pandas`
  - `python-dotenv` (optional — allows a local `.env` file)

Install them with:

```powershell
py -m pip install --upgrade pip
py -m pip install requests pandas python-dotenv
```

Or create and use a virtual environment (recommended):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install requests pandas python-dotenv
```

**Optional: Use a local `.env` file**
- Create a file named `.env` in the project root with the following line (DO NOT commit this file):

```
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

- The script will attempt to load `.env` automatically if `python-dotenv` is installed.

**Run examples**
- Run with CLI key (recommended for one-off runs):

```powershell
py crypto_agent.py --api-key "YOUR_GEMINI_API_KEY_HERE"
```

- Run using the session environment variable:

```powershell
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
py crypto_agent.py
```

When prompted, enter a crypto symbol or id (e.g., `btc`, `bitcoin`, `eth`, `ethereum`, `sol`, `solana`). The script resolves common symbols to CoinGecko IDs automatically.

**Troubleshooting**
- ModuleNotFoundError for `pandas` or `requests`: ensure you installed dependencies in the same Python interpreter used by `py`. Run `py -m pip show pandas` to verify.

- `404` from CoinGecko for market data: ensure you entered a valid CoinGecko coin ID or a supported symbol (e.g., `btc` => `bitcoin`). If a coin id is very new or not in CoinGecko, try the full CoinGecko id.

- If the Gemini API returns an error about the key or rate limits, verify the key is correct and has permission for the model. The script builds the Gemini request URL using the key you supply.

**Security recommendations**
- Do not commit `.env` or keys to source control.
- Add `.env` to `.gitignore` (see note below).

**Suggested `.gitignore` entry**
```
.env
.venv/
venv/
__pycache__/
*.pyc
```

**What I changed in the repository (developer notes)**
- `crypto_agent.py` now supports `--api-key` / `-k` cli argument and still supports `GEMINI_API_KEY` from env or `.env`.
- The Gemini request URL is built at runtime so you can pass the API key on the command line.

If you want, I can also:
- Add a `run.ps1` helper that runs the script with the key (keeps the key out of files if you prefer to type it once there), or
- Update `requirements.txt` to a clean list of dependencies (I can patch it now), or
- Create a `.env.example` (without real keys) to show the format.

Tell me which optional step you want next and I'll add it.