import os
import sys
import re
import json
import requests
import subprocess
import random
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum


# -- Version guard -------------------------------------------------------------
try:
    import openai
    from packaging.version import Version
    MIN_VERSION = "1.56.0"
    if Version(openai.__version__) < Version(MIN_VERSION):
        print(f"openai {openai.__version__} is too old (need {MIN_VERSION}+).")
        print("   Run:  pip install --upgrade openai")
        sys.exit(1)
except ImportError:
    pass

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -- Constants -----------------------------------------------------------------

MAX_RETRIES = 10
STATE_FILE  = Path(__file__).parent / "used_articles.json"
FSI_EVERY_N = 4   # every Nth run is FSI/Insurance focused

# Sites rotate independently from keywords so every combo stays fresh.
SITE_ROTATION = [
    "techcommunity.microsoft.com",
    "azure.microsoft.com/en-us/blog",
    "microsoft.com/en-us/microsoft-cloud/blog",
    "microsoft.com/en-us/industry/blog",
    "venturebeat.com",
    "zdnet.com",
    "infoworld.com",
    "forbes.com",
    "theregister.com",
    "bloomberg.com",
]

# General keyword rotation — each run picks the next one in order.
KEYWORD_ROTATION = [
    # --- AI & Analytics (Original) ---
    "Azure AI agents",
    "Microsoft Copilot enterprise",
    "Microsoft Fabric analytics",
    "Azure OpenAI Service",
    "Microsoft Copilot Studio",
    "Azure AI Foundry",
    "Microsoft Fabric real-time intelligence",
    "Azure AI infrastructure",
    "Microsoft Copilot Wave 2",
    "Azure machine learning",
    "Microsoft Purview AI governance",
    "Azure Arc hybrid cloud",
    "Microsoft Copilot for Security",
    "Azure AI Search",
    "Microsoft Fabric OneLake",
    
    # --- Core Infrastructure (Compute, Networking, Governance) ---
    "Azure Virtual Machines",
    "Azure Kubernetes Service AKS",
    "Azure Virtual Network VNet",
    "Azure ExpressRoute",
    "Azure Landing Zones",
    "Azure Policy and Governance",
    "Azure FinOps and Cost Management",
    
    # --- SQL & Databases ---
    "Azure SQL Database",
    "Azure SQL Managed Instance",
    "SQL Server on Azure VMs",
    "Azure Cosmos DB",
    "Azure Database for PostgreSQL",
    "Azure Database for MySQL",
    
    # --- Platform as a Service (PaaS) & Integration ---
    "Azure App Services",
    "Azure Functions serverless",
    "Azure Container Apps",
    "Azure Logic Apps",
    "Azure API Management APIM",
    "Azure Event Hubs",
    "Azure Key Vault"
]

# FSI-specific keyword rotation — used every 4th run instead of general keywords.
FSI_KEYWORD_ROTATION = [
    "Microsoft AI financial services",
    "Azure AI insurance automation",
    "Microsoft Copilot banking",
    "Azure AI fraud detection",
    "Microsoft Cloud for financial services",
    "Azure AI insurance claims",
    "Microsoft Fabric financial analytics",
    "AI risk management Microsoft",
]

# URL path segments that indicate a product/landing page rather than a real article
BANNED_URL_PATTERNS = [
    r"/products/",
    r"/solutions/",
    r"/features/",
    r"/pricing/",
    r"/services/",
    r"/marketplace/",
    r"/en-us/azure/?$",
    r"/en-us/products/?$",
    r"azure\.microsoft\.com/?$",
]

PERSONA = (
    "You are a Microsoft employee and Cloud & AI specialist. "
    "Your goal is to find and share content that positively represents Microsoft technology. "
    "Only return articles that are favorable, educational, or celebratory about Microsoft products and strategy. "
    "Never return articles that are critical, negative, or damaging to Microsoft's reputation — "
    "including security incidents, layoffs, antitrust issues, or unfavorable comparisons."
)


# -- State management ----------------------------------------------------------

class State:
    """
    Persists run counter, independent site/keyword rotation indexes,
    used article URLs, and used search combos — all in one JSON file.
    """

    def __init__(self, path: Path):
        self.path = path
        data = {}
        if path.exists():
            try:
                raw = json.loads(path.read_text())
                # migrate legacy format: plain list of URLs
                if isinstance(raw, list):
                    data = {"used_urls": raw, "run_count": 0}
                else:
                    data = raw
            except Exception:
                pass

        self.used_urls:     list[str] = data.get("used_urls", [])
        self.used_searches: list[str] = data.get("used_searches", [])
        self.run_count:     int       = data.get("run_count", 0)
        self.site_index:    int       = data.get("site_index", 0)
        self.keyword_index: int       = data.get("keyword_index", 0)
        self.fsi_kw_index:  int       = data.get("fsi_kw_index", 0)

    def save(self):
        self.path.write_text(json.dumps({
            "run_count":     self.run_count,
            "site_index":    self.site_index,
            "keyword_index": self.keyword_index,
            "fsi_kw_index":  self.fsi_kw_index,
            "used_searches": self.used_searches,
            "used_urls":     self.used_urls,
        }, indent=2))

    def mark_used_url(self, url: str):
        if url not in self.used_urls:
            self.used_urls.append(url)
        self.save()

    # keep old name as alias so nothing else breaks
    def mark_used(self, url: str):
        self.mark_used_url(url)

    def mark_used_search(self, combo: str):
        if combo not in self.used_searches:
            self.used_searches.append(combo)
        self.save()

    def advance_site(self):
        self.site_index = (self.site_index + 1) % len(SITE_ROTATION)
        self.save()

    # kept for callers that still say advance_source()
    def advance_source(self):
        self.advance_site()

    def advance_keyword(self):
        if self.is_fsi_run:
            self.fsi_kw_index = (self.fsi_kw_index + 1) % len(FSI_KEYWORD_ROTATION)
        else:
            self.keyword_index = (self.keyword_index + 1) % len(KEYWORD_ROTATION)
        self.save()

    @property
    def current_site(self) -> str:
        return SITE_ROTATION[self.site_index % len(SITE_ROTATION)]

    # kept for callers that still say current_source
    @property
    def current_source(self) -> str:
        return self.current_site

    @property
    def current_keyword(self) -> str:
        if self.is_fsi_run:
            return FSI_KEYWORD_ROTATION[self.fsi_kw_index % len(FSI_KEYWORD_ROTATION)]
        return KEYWORD_ROTATION[self.keyword_index % len(KEYWORD_ROTATION)]

    @property
    def current_search_combo(self) -> str:
        return f"site:{self.current_site} {self.current_keyword}"

    @property
    def is_fsi_run(self) -> bool:
        return self.run_count % FSI_EVERY_N == 0
    
    def increment_run(self):
        self.run_count += 1
        random.shuffle(KEYWORD_ROTATION)
        self.save()


# -- Validation ----------------------------------------------------------------

class ValidationResult(Enum):
    OK             = "ok"
    DEAD_URL       = "dead_url"
    TOO_OLD        = "too_old"
    NOT_AN_ARTICLE = "not_an_article"


def is_article_url(url: str) -> bool:
    """
    Returns False if the URL looks like a product/landing page rather than
    a dated blog post or news article. Checked before any HTTP request.
    """
    for pattern in BANNED_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return False
    return True


def validate_article(url: str) -> ValidationResult:
    """Checks liveness then publication date in a single pass."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        )
    }

    # -- Liveness check --------------------------------------------------------
    try:
        res = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        if res.status_code != 200:
            return ValidationResult.DEAD_URL
    except Exception:
        return ValidationResult.DEAD_URL

    # -- Date check ------------------------------------------------------------
    cutoff = datetime.now() - timedelta(days=60)
    html   = res.text

    date_patterns = [
        r'datePublished["\s:]+(\d{4}-\d{2}-\d{2})',
        r'publishedDate["\s:]+(\d{4}-\d{2}-\d{2})',
        r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})',
        r'content="(\d{4}-\d{2}-\d{2})',
        r'(\d{4}-\d{2}-\d{2})',
    ]

    for pattern in date_patterns:
        for match in re.findall(pattern, html):
            try:
                pub_date = datetime.strptime(match, "%Y-%m-%d")
                if pub_date >= cutoff:
                    return ValidationResult.OK
                print(f"  📅 Article date {match} is older than 60 days — skipping.")
                return ValidationResult.TOO_OLD
            except ValueError:
                continue

    print("  📅 No date found in page — allowing through.")
    return ValidationResult.OK


# -- Discovery -----------------------------------------------------------------

def build_discovery_prompt(state: State, excluded_urls: list[str]) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) built from the current site+keyword rotation."""
    today          = datetime.now()
    sixty_days_ago = today - timedelta(days=60)
    date_range     = f"{sixty_days_ago.strftime('%B %d, %Y')} to {today.strftime('%B %d, %Y')}"
    site           = state.current_site
    keyword        = state.current_keyword
    search_combo   = state.current_search_combo  # e.g. "site:techcommunity.microsoft.com Azure AI agents"

    exclusion_note = ""
    if excluded_urls:
        exclusion_note = (
            "\n\nDo NOT return any of these already-used URLs:\n"
            + "\n".join(f"  - {u}" for u in excluded_urls[-20:])
        )

    system_prompt = (
        f"{PERSONA}\n\n"
        f"Today is {today.strftime('%B %d, %Y')}.\n"
        f"Run this exact web search: {search_combo}\n"
        f"Find a real editorial article from that search, published between {date_range}.\n\n"
        "REQUIREMENTS — the article must:\n"
        "- Be a real blog post, news story, or announcement (not a product or landing page)\n"
        "- Have a visible publication date within the last 60 days\n"
        "- Have a specific headline and narrative body content\n"
        "- Be positive or educational about Microsoft technology\n\n"
        "NEVER return URLs containing: /products/, /solutions/, /features/, /pricing/, "
        "/services/, /marketplace/, or a bare domain root.\n"
        "NEVER invent or guess a URL — only return one you have actually fetched and read.\n\n"
        "Return ONLY valid JSON with two fields 'topic' and 'url'. No extra text."
        + exclusion_note
    )

    user_prompt = (
        f"Run this search: {search_combo}\n"
        f"Return one real article published between {date_range} about '{keyword}'. "
        "It must be a blog post or news story with a date and headline — not a product page. "
        "Positive about Microsoft only. "
        f"{('Avoid these URLs: ' + ', '.join(excluded_urls[-5:])) if excluded_urls else ''} "
        "Return only JSON with 'topic' and 'url'. No other text."
    )

    return system_prompt, user_prompt
def discover_azure_news(state: State) -> dict:
    """
    Uses gpt-4o-search-preview to find a real, recent, positive Microsoft article.
    Returns {'topic': ..., 'url': ...}
    """
    today          = datetime.now()
    sixty_days_ago = today - timedelta(days=60)
    date_range     = f"{sixty_days_ago.strftime('%B %d, %Y')} to {today.strftime('%B %d, %Y')}"
    run_label      = "FSI/Insurance" if state.is_fsi_run else "General Azure"

    print(f"🌐 [{run_label}] {state.current_search_combo} — run #{state.run_count} ...")
    if state.used_urls:
        print(f"  ⏭️  Skipping {len(state.used_urls)} previously used article(s).")

    system_prompt, user_prompt = build_discovery_prompt(state, state.used_urls)

    response = client.chat.completions.create(
        model="gpt-4o-search-preview",
        web_search_options={},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    if "topic" not in result or "url" not in result:
        raise ValueError(f"Unexpected response format: {raw}")

    return result


# -- LinkedIn command builder --------------------------------------------------

def build_linkedin_command(topic: str, url: str) -> str:
    static_prompt = (
        f"Create a short LinkedIn post with emojis. Focus on enterprise value "
        f"regarding {topic}. End the post with 'read more: {url}'"
    )
    return f'python send_to_linkedin.py "{topic}" "{static_prompt}" "{url}"'


# -- Terminal utilities --------------------------------------------------------

def hyperlink(url: str, label: str = None) -> str:
    """OSC 8 terminal hyperlink — falls back gracefully in unsupported terminals."""
    label = label or url
    OSC, ST = "\033]", "\033\\"
    return f"{OSC}8;;{url}{ST}{label}{OSC}8;;{ST}"


def print_preview(topic: str, url: str, cli_command: str):
    divider = "─" * 62
    print(f"\n{divider}")
    print("  CLIPBOARD PREVIEW")
    print(divider)
    print(f"  Topic   : {topic}")
    print(f"  Source  : {hyperlink(url)}")
    print(f"\n  Command :\n  {cli_command}")
    print(divider)


def copy_to_clipboard(text: str) -> bool:
    try:
        process = subprocess.Popen("pbcopy", stdin=subprocess.PIPE, text=True)
        process.communicate(input=text)
        return True
    except Exception:
        return False


# -- Entry point ---------------------------------------------------------------

def main():
    state = State(STATE_FILE)
    state.increment_run()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Skip if we've already used this exact site+keyword combo
            if state.current_search_combo in state.used_searches:
                print(f"  ⏭️  Search combo already used — advancing. ({attempt}/{MAX_RETRIES})")
                state.advance_site()
                state.advance_keyword()
                continue

            article    = discover_azure_news(state)
            topic, url = article["topic"], article["url"]

            print(f"  📄 Found : {topic}")
            print(f"  🔗 URL   : {url}")

            if url in state.used_urls:
                print(f"  ⚠️  Already used. Advancing and retrying... ({attempt}/{MAX_RETRIES})")
                state.advance_site()
                state.advance_keyword()
                continue

            if not is_article_url(url):
                print(f"  ⚠️  Product/landing page — blacklisting, advancing. ({attempt}/{MAX_RETRIES})")
                state.mark_used_url(url)
                state.advance_site()
                state.advance_keyword()
                continue

            result = validate_article(url)

            if result == ValidationResult.DEAD_URL:
                print(f"  ⚠️  URL not reachable. Advancing and retrying... ({attempt}/{MAX_RETRIES})")
                state.advance_site()
                state.advance_keyword()
                continue

            if result == ValidationResult.TOO_OLD:
                print(f"  ⚠️  Article too old — blacklisting, advancing. ({attempt}/{MAX_RETRIES})")
                state.mark_used_url(url)
                state.advance_site()
                state.advance_keyword()
                continue

            print("  ✅ URL and date validated.")

            cli_command = build_linkedin_command(topic, url)
            state.mark_used_url(url)
            state.mark_used_search(state.current_search_combo)
            state.advance_site()
            state.advance_keyword()

            copied = copy_to_clipboard(cli_command)
            print_preview(topic, url, cli_command)
            print("  ✅ Copied to clipboard — Cmd+V in your terminal.\n" if copied
                  else "  ⚠️  Clipboard copy failed — run the command above manually.\n")
            return

        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️  Parsing error: {e}. Advancing and retrying... ({attempt}/{MAX_RETRIES})")
            state.advance_site()
            state.advance_keyword()

        except Exception as e:
            err = str(e)
            if "unexpected keyword argument" in err and "web_search_options" in err:
                print("❌ Your openai package is too old.\n   Run:  pip install --upgrade openai")
                sys.exit(1)
            print(f"⚠️  Error: {e}. Advancing and retrying... ({attempt}/{MAX_RETRIES})")
            state.advance_site()
            state.advance_keyword()

    print(f"❌ Failed after {MAX_RETRIES} attempts. Exiting.")


if __name__ == "__main__":
    main()
