import os
import requests
import pandas as pd
# pandas-ta is no longer needed!
import json
import time
import argparse
from typing import Dict, Any, Optional, List

# Optional: load environment variables from a local .env file when available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; if it's not installed, environment variables
    # will be read from the OS environment as usual.
    pass

# --- Configuration ---
# Your API key is read from an environment variable for security
# Read the API key from the expected env var name `GEMINI_API_KEY`.
API_KEY = os.environ.get("GEMINI_API_KEY")
# Build the base Gemini endpoint; the API key will be appended at call time so
# callers can supply the key via env, .env, or CLI arg without requiring import-time globals.
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# --- ANSI Color Codes for Readability ---
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# --- 1. Robust API Call Helpers ---

def fetch_with_backoff(url: str, method: str = 'GET', payload: Optional[Dict[str, Any]] = None, retries: int = 3, delay: int = 2) -> requests.Response:
    """
    A robust fetch function with exponential backoff for retries.
    Handles 'GET' and 'POST' requests.
    """
    headers = {'Content-Type': 'application/json'}
    for i in range(retries):
        try:
            if method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=payload)
            else:
                response = requests.get(url, headers=headers)
            
            # 429: Too Many Requests, 5xx: Server Errors
            if response.status_code == 429 or (response.status_code >= 500 and response.status_code <= 599):
                print(f"{Colors.YELLOW}Retryable error: {response.status_code}. Retrying in {delay}s...{Colors.ENDC}")
                time.sleep(delay)
                delay *= 2 # Exponential backoff
                continue
            
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx, 5xx)
            return response
        
        except requests.exceptions.RequestException as e:
            if i == retries - 1:
                print(f"{Colors.RED}Fetch failed after all retries: {e}{Colors.ENDC}")
                raise
            time.sleep(delay)
            delay *= 2
    raise Exception("Fetch failed after all retries.")


def call_gemini_api(user_prompt: str, 
                    system_prompt: Optional[str] = None, 
                    tools: Optional[List[Dict[str, Any]]] = None, 
                    schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    A generic function to call the Gemini API, handling tools, 
    system prompts, and structured output schemas.
    """
    if not API_KEY:
        raise ValueError(
            "GEMINI_API_KEY not set. Provide it as an argument: `py crypto_agent.py --api-key YOUR_KEY`,\n"
            "or set the environment variable GEMINI_API_KEY. For PowerShell: `$env:GEMINI_API_KEY=\"YOUR_KEY\"`.\n"
            "You can also create a local `.env` file with `GEMINI_API_KEY=...` and install `python-dotenv`.")

    # Build the full URL at call time so callers can provide the key via CLI/env
    gemini_url = f"{GEMINI_API_BASE}?key={API_KEY}"

    payload = {"contents": [{"parts": [{"text": user_prompt}]}]}

    if tools:
        payload["tools"] = tools
    
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    
    if schema:
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": schema
        }

    response = fetch_with_backoff(gemini_url, method='POST', payload=payload)
    result = response.json()

    candidate = result.get("candidates", [{}])[0]
    content_part = candidate.get("content", {}).get("parts", [{}])[0]
    
    if "text" not in content_part:
        raise Exception(f"Invalid API response structure: {result}")
        
    return content_part


# --- 2. RAG - Data Retrieval Functions ---

def fetch_market_data(crypto_id: str) -> Dict[str, Any]:
    """
    Fetches market data from CoinGecko and calculates technical indicators.
    Demonstrates the 'Retrieval' part of RAG with technical data.
    
    *** MODIFIED to manually calculate SMA and RSI ***
    """
    print(f"{Colors.BLUE}... 1. Fetching market data for '{crypto_id}'...{Colors.ENDC}")
    try:
        # 1. Fetch 90-day historical data
        history_url = f"{COINGECKO_BASE_URL}/coins/{crypto_id}/market_chart?vs_currency=usd&days=90&interval=daily"
        history_response = fetch_with_backoff(history_url)
        history_data = history_response.json()

        # 2. Fetch current price
        price_url = f"{COINGECKO_BASE_URL}/simple/price?ids={crypto_id}&vs_currencies=usd"
        price_response = fetch_with_backoff(price_url)
        price_data = price_response.json()

        # 3. Process data with Pandas
        df = pd.DataFrame(history_data['prices'], columns=['timestamp', 'close'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # 4. Calculate TA indicators using just pandas
        
        # Calculate 20-Day SMA
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        
        # Calculate 14-Day RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # Get the most recent non-NaN values for indicators
        latest_sma = df['SMA_20'].dropna().iloc[-1]
        latest_rsi = df['RSI_14'].dropna().iloc[-1]

        return {
            "current_price": price_data[crypto_id]['usd'],
            "latest_sma": latest_sma,
            "latest_rsi": latest_rsi,
        }
    except Exception as e:
        print(f"{Colors.RED}Error fetching market data: {e}{Colors.ENDC}")
        raise

def fetch_news_sentiment(crypto_name: str) -> str:
    """
    Fetches real-time news headlines using Gemini with Google Search.
    Demonstrates the 'Retrieval' part of RAG with real-world news.
    """
    print(f"{Colors.BLUE}... 2. Fetching news sentiment for '{crypto_name}'...{Colors.ENDC}")
    try:
        prompt = f"Find the top 3-5 recent news headlines for {crypto_name} and provide a one-sentence summary of the overall sentiment (positive, negative, or neutral)."
        tools = [{"google_search": {}}]
        
        response_part = call_gemini_api(prompt, tools=tools)
        return response_part['text']
    
    except Exception as e:
        print(f"{Colors.YELLOW}Warning: Could not fetch news sentiment. Proceeding without it. Error: {e}{Colors.ENDC}")
        return "News sentiment could not be retrieved."

# --- 3. Agent, RAG, and Structured Output Function ---

def get_ai_analysis(crypto_name: str, tech_data: Dict[str, Any], news_sentiment: str) -> Dict[str, str]:
    """
    Calls the Gemini API to perform the final analysis.
    
    Demonstrates:
    - Agent: Via the 'system_prompt'.
    - RAG: By 'augmenting' the prompt with 'tech_data' and 'news_sentiment'.
    - Structured Output: Via the 'schema'.
    """
    print(f"{Colors.BLUE}... 3. Consulting AI Analyst Agent...{Colors.ENDC}")

    # 1. Define the Agent's persona
    system_prompt = """
    You are an expert crypto analyst. Your analysis must be concise, unbiased, 
    and directly reference the data provided. Return your analysis *only*
    in the following JSON format. Do not include any other text or markdown formatting.
    """

    # 2. Define the RAG prompt
    user_prompt = f"""
    Analyze the market for {crypto_name}.

    Here is the live data:
    - Current Price: ${tech_data['current_price']:.2f}
    - 20-Day SMA: ${tech_data['latest_sma']:.2f}
    - 14-Day RSI: {tech_data['latest_rsi']:.2f}

    Here is the latest news sentiment:
    "{news_sentiment}"

    Analysis guidance:
    - If Price > SMA, it's a bullish signal. If Price < SMA, it's bearish.
    - If RSI > 70, it's overbought (bearish). If RSI < 30, it's oversold (bullish).
    - Synthesize these technical signals with the news sentiment for a final recommendation.
    """
    
    # 3. Define the Structured Output schema
    schema = {
        "type": "OBJECT",
        "properties": {
            "analysis": {
                "type": "STRING",
                "description": "A concise 2-3 sentence analysis synthesizing the technical data and news."
            },
            "recommendation": {
                "type": "STRING",
                "description": "A clear recommendation: 'Strong Buy', 'Buy', 'Hold', 'Sell', or 'Strong Sell'."
            },
            "confidence": {
                "type": "STRING",
                "description": "'High', 'Medium', or 'Low' confidence in the recommendation."
            }
        },
        "required": ["analysis", "recommendation", "confidence"]
    }

    try:
        response_part = call_gemini_api(user_prompt, system_prompt=system_prompt, schema=schema)
        # The API returns the JSON as a string, so we parse it.
        return json.loads(response_part['text'])
    
    except json.JSONDecodeError:
        print(f"{Colors.RED}Error: AI returned invalid JSON.{Colors.ENDC}")
        print(f"Raw response: {response_part.get('text', 'N/A')}")
        raise
    except Exception as e:
        print(f"{Colors.RED}Error during AI analysis: {e}{Colors.ENDC}")
        raise

# --- 4. Main Execution ---

def run_analysis():
    """
    Main function to run the crypto analysis agent.
    """
    # Simple mapping for user convenience: map common symbols to CoinGecko IDs
    # Each entry maps input -> (coin_id_for_api, DisplayName)
    crypto_map = {
        "bitcoin": ("bitcoin", "Bitcoin"),
        "btc": ("bitcoin", "Bitcoin"),
        "ethereum": ("ethereum", "Ethereum"),
        "eth": ("ethereum", "Ethereum"),
        "solana": ("solana", "Solana"),
        "sol": ("solana", "Solana"),
        "dogecoin": ("dogecoin", "Dogecoin"),
        "doge": ("dogecoin", "Dogecoin")
    }

    try:
        crypto_input = input(f"Enter a crypto ID or symbol (e.g., 'bitcoin' or 'btc'): ").lower().strip()
        if not crypto_input:
            print(f"{Colors.RED}No input provided. Exiting.{Colors.ENDC}")
            return

        # Resolve to CoinGecko id + display name (fallback: use the input as id)
        coin_id, crypto_name = crypto_map.get(crypto_input, (crypto_input, crypto_input.capitalize()))
        print(f"\n{Colors.BOLD}Analyzing {crypto_name}...{Colors.ENDC}")

        # 1. RAG - Get technical data (use resolved CoinGecko id)
        tech_data = fetch_market_data(coin_id)
        
        # 2. RAG - Get news data
        news_sentiment = fetch_news_sentiment(crypto_name)
        
        # 3. Agent + RAG + Structured Output - Get AI analysis
        ai_report = get_ai_analysis(crypto_name, tech_data, news_sentiment)
        
        # 4. Print the final report
        print(f"\n{Colors.GREEN}--- Live Technical Data ---{Colors.ENDC}")
        print(f"  {Colors.BOLD}Current Price:{Colors.ENDC} ${tech_data['current_price']:,.2f}")
        print(f"  {Colors.BOLD}20-Day SMA:{Colors.ENDC}    ${tech_data['latest_sma']:,.2f}")
        print(f"  {Colors.BOLD}14-Day RSI:{Colors.ENDC}     {tech_data['latest_rsi']:.2f}")
        
        print(f"\n{Colors.GREEN}--- AI Analyst Report ---{Colors.ENDC}")
        print(f"  {Colors.BOLD}Analysis:{Colors.ENDC}       {ai_report['analysis']}")
        print(f"  {Colors.BOLD}Recommendation:{Colors.ENDC}   {ai_report['recommendation']}")
        print(f"  {Colors.BOLD}Confidence:{Colors.ENDC}       {ai_report['confidence']}")

    except Exception as e:
        print(f"\n{Colors.RED}An error occurred during the analysis: {e}{Colors.ENDC}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the crypto analysis agent."
                                     )
    parser.add_argument('-k', '--api-key', help='Provide GEMINI API key directly (overrides env)')
    args = parser.parse_args()

    if args.api_key:
        API_KEY = args.api_key
        os.environ['GEMINI_API_KEY'] = args.api_key

    if not API_KEY:
        print(f"{Colors.RED}{Colors.BOLD}Error: GEMINI_API_KEY not provided.{Colors.ENDC}")
        print("Run with: `py crypto_agent.py --api-key YOUR_KEY` or set the environment variable GEMINI_API_KEY.")
    else:
        run_analysis()