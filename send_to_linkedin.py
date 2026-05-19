import os
import sys
import random
import hashlib
import subprocess
import tempfile
import requests
from dotenv import load_dotenv
from openai import OpenAI
from bs4 import BeautifulSoup

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LINKEDIN_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
PERSON_URN = os.getenv("LINKEDIN_PERSON_URN")

# --- Writing style definitions ---
STYLES = {
    1: {
        "name": "Punchy Bullets",
        "description": (
            "Classic LinkedIn punchy style. Bold hook line, then 3 tight bullet points "
            "with emoji, then a CTA question. Each bullet = one powerful idea. "
            "Feels fast and scannable."
        ),
        "format": (
            "FORMAT RULES:\n"
            "- Line 1: A bold, provocative one-liner as the hook (no emoji on this line).\n"
            "- Blank line.\n"
            "- 3 bullet points using → or ▸, each starting with a strong verb, max 2 lines each.\n"
            "- Blank line.\n"
            "- One short closing insight sentence.\n"
            "- End with a question directed at FSI/insurance leaders.\n"
            "- 3-5 hashtags on the last line.\n"
            "TONE: Sharp, confident, fast-paced."
        ),
    },
    2: {
        "name": "Storytelling Narrative",
        "description": (
            "Opens with a micro-story or specific scenario (real-feeling, not generic). "
            "Flows as short paragraphs, no bullet points. Feels human and reflective. "
            "Ends with an insight and a soft question."
        ),
        "format": (
            "FORMAT RULES:\n"
            "- Open with a 1-2 sentence scene or moment: 'A CTO walked into a room...' "
            "or 'Last week, a CFO asked me...' — grounded and specific.\n"
            "- 2-3 short paragraphs (2-3 sentences each) flowing naturally. NO bullet points.\n"
            "- A single-sentence punchline or insight before the close.\n"
            "- End with a soft, open question inviting conversation.\n"
            "- 3-5 hashtags on the last line.\n"
            "TONE: Warm, thoughtful, like a senior practitioner sharing a real lesson."
        ),
    },
    3: {
        "name": "Hot Take / Contrarian",
        "description": (
            "Starts with a statement that challenges conventional wisdom or a popular belief "
            "in the industry. Argues a counterintuitive point about AI or insurance tech. "
            "Feels like a bold opinion, not a product pitch."
        ),
        "format": (
            "FORMAT RULES:\n"
            "- Line 1: A counterintuitive or slightly controversial statement. "
            "Example pattern: 'Most [X] are wrong about [Y].' or 'The real reason [X] fails is not [Y].'\n"
            "- Blank line.\n"
            "- 2-3 short paragraphs defending the take with specific logic. No bullet points.\n"
            "- Acknowledge the opposing view briefly, then reaffirm.\n"
            "- Close with a direct challenge or question to peers.\n"
            "- 3-5 hashtags on the last line.\n"
            "TONE: Bold, opinionated, intellectually honest. Not arrogant — persuasive."
        ),
    },
}

# Track last used style in session to avoid exact repeats
_session_style_history = []


def pick_style(topic: str, force_style: int = None) -> dict:
    """Pick a style, rotating so the same one isn't used twice in a row."""
    if force_style and force_style in STYLES:
        return STYLES[force_style]

    available = [s for s in STYLES if s not in _session_style_history[-1:]]
    seed = int(hashlib.md5(topic.lower().encode()).hexdigest(), 16) + random.randint(0, 9999)
    chosen = (seed % len(available))
    style_id = available[chosen]
    _session_style_history.append(style_id)
    return STYLES[style_id]


def fetch_article_text(url):
    """Simple scraper to get text content from a URL."""
    try:
        print(f"📄 Reading article: {url}...")
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        return soup.get_text(separator=' ', strip=True)[:4000]
    except Exception as e:
        print(f"⚠️ Could not read article: {e}")
        return None


def append_read_more(content: str, url: str) -> str:
    """
    Append a 'Read more' link to the post content if a URL is provided.
    Strips any existing 'Read more' line first so it's never duplicated.
    """
    if not url:
        return content

    lines = content.splitlines()
    lines = [l for l in lines if not l.strip().lower().startswith("read more:")]
    clean = "\n".join(lines).rstrip()
    return f"{clean}\n\nRead more: {url}"


# Keyword → emoji map: order matters (more specific first)
_EMOJI_HINTS = [
    (["fraud", "risk", "compliance", "security", "breach"],      "🔒"),
    (["predict", "forecast", "model", "underwrite", "actuari"],  "📊"),
    (["claim", "settlement", "payout", "adjuster"],              "📋"),
    (["customer", "client", "policyholder", "experience"],       "🤝"),
    (["ai", "copilot", "machine learning", "llm", "gpt"],        "🤖"),
    (["azure", "cloud", "infrastructure", "platform"],           "☁️"),
    (["speed", "fast", "real-time", "latency", "instant"],       "⚡"),
    (["insight", "learn", "understand", "analys"],               "🧠"),
    (["data", "pipeline", "ingestion", "warehouse"],             "🔍"),
    (["growth", "scale", "revenue", "profit", "roi"],            "📈"),
    (["bank", "fsi", "financial", "insurance", "insurer"],       "🏦"),
    (["transform", "change", "shift", "moderniz", "reinvent"],   "🚀"),
    (["microsoft", "@microsoft"],                                 "💼"),
    (["idea", "solution", "answer", "strategy", "approach"],     "💡"),
    (["global", "world", "market", "industry", "sector"],        "🌐"),
]

_FALLBACK_EMOJIS = ["💡", "🚀", "🔍", "📊", "🤝", "🧠", "⚡", "🔒"]


def _pick_emoji_for_line(line: str) -> str | None:
    """Return the best-fit emoji for a line based on its content, or None."""
    lower = line.lower()
    for keywords, emoji in _EMOJI_HINTS:
        if any(kw in lower for kw in keywords):
            return emoji
    return None

def enforce_emoji_count(content: str, min_e: int = 4, max_e: int = 7) -> str:
    """
    Distribute UNIQUE emojis throughout the post.
    """
    import emoji as emoji_lib
    import random

    # 1. Strip existing emojis
    def strip_emojis(text: str) -> str:
        return "".join(ch for ch in text if not emoji_lib.is_emoji(ch)).strip()

    lines = [strip_emojis(l) for l in content.splitlines()]

    # 2. Identify candidate body lines
    def is_hashtag_line(line: str) -> bool:
        words = line.strip().split()
        return bool(words) and all(w.startswith("#") for w in words)

    def is_read_more_line(line: str) -> bool:
        return line.strip().lower().startswith("read more:")

    candidate_indices = [
        i for i, l in enumerate(lines)
        if l.strip()
        and not is_hashtag_line(l)
        and not is_read_more_line(l)
    ]

    # 3. Initialize pools and tracking
    assigned: dict[int, str] = {}
    used_emojis = set()
    
    # Create a mutable copy of fallbacks to pull from
    available_fallbacks = _FALLBACK_EMOJIS.copy()
    random.shuffle(available_fallbacks)

    # 4. First Pass: Specific Keyword Matches
    scored = []
    for i in candidate_indices:
        suggested = _pick_emoji_for_line(lines[i])
        scored.append((0 if suggested else 1, i, suggested))

    scored.sort(key=lambda x: x[0]) # Priority matches first

    for priority, i, suggested_emoji in scored:
        if len(assigned) >= max_e:
            break
            
        # If the suggested emoji is already used, or we don't have one, 
        # we'll skip to pass 2 for this line or use a fallback
        if suggested_emoji and suggested_emoji not in used_emojis:
            assigned[i] = suggested_emoji
            used_emojis.add(suggested_emoji)
            # Remove from fallbacks if it exists there to keep the pool clean
            if suggested_emoji in available_fallbacks:
                available_fallbacks.remove(suggested_emoji)

    # 5. Second Pass: Fill to min_e using unique fallbacks
    remaining_candidates = [i for i in candidate_indices if i not in assigned]
    
    for i in remaining_candidates:
        if len(assigned) >= min_e or not available_fallbacks:
            break
        
        new_emoji = available_fallbacks.pop(0)
        assigned[i] = new_emoji
        used_emojis.add(new_emoji)

    # 6. Reconstruct the lines
    for i, em in assigned.items():
        lines[i] = lines[i].rstrip() + f" {em}"

    return "\n".join(lines)

def manual_edit(content: str) -> str:
    """Open the post in the system's default text editor for manual editing."""
    editor = os.environ.get("EDITOR", "nano")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        subprocess.call([editor, tmp_path])
        with open(tmp_path, "r") as f:
            edited = f.read()
        return edited.strip()
    except Exception as e:
        print(f"⚠️ Could not open editor ({editor}): {e}")
        print("Tip: Set your EDITOR environment variable (e.g. export EDITOR=nano)")
        return content
    finally:
        os.unlink(tmp_path)


def generate_post(topic, custom_prompt=None, existing_post=None, article_context=None,
                  style: dict = None):
    """Generates or adjusts a post using topic, prompt, style, and optional article context."""

    context_str = f"\nARTICLE CONTEXT:\n{article_context}\n" if article_context else ""

    system_instruction = (
        "You are a Cloud and AI Specialist at Microsoft, focusing on Enterprise Financial Services "
        "Insurance Customers. "
        "STRICT RULES:\n"
        "- Do NOT mention real estate or being a real estate agent.\n"
        "- Always reference @Microsoft naturally somewhere in the post body (not just in hashtags).\n"
        "- Output ONLY the final post content. No conversational filler, no 'Here is your post', "
        "and no labels like '---updated post---'.\n"
        "- Do NOT add a 'Read more' line — that will be appended separately."
    )

    if existing_post:
        print(f"🔄 Adjusting post based on feedback...")
        style_note = (
            f"\nThis post uses the '{style['name']}' writing style. "
            f"Keep the same style unless the feedback explicitly asks to change it.\n"
            f"Style description: {style['description']}\n"
            f"{style['format']}\n"
        ) if style else ""

        user_prompt = (
            f"Here is a LinkedIn post about '{topic}':\n\n"
            f"--- EXISTING POST ---\n{existing_post}\n------------------\n\n"
            f"{context_str}"
            f"{style_note}"
            f"Please ADJUST the post according to these instructions: {custom_prompt}\n"
            "Return ONLY the text of the new post. Do NOT include a 'Read more' line."
        )
    else:
        style = style or STYLES[1]
        print(f"🚀 Generating post about: {topic}...")
        print(f"   ✍️  Style: {style['name']}")

        user_prompt = (
            f"{context_str}\n"
            f"Write a LinkedIn post about '{topic}' for an audience of FSI and insurance "
            f"enterprise leaders.\n\n"
            f"WRITING STYLE: {style['name']}\n"
            f"{style['description']}\n\n"
            f"{style['format']}\n\n"
            f"CONTENT FOCUS (apply within the style above):\n"
            f"- Angle: Microsoft Azure AI, Copilot, or cloud transformation for insurance/FSI.\n"
            f"- Naturally mention @Microsoft somewhere in the post body.\n"
            f"- Hashtags must include: #Microsoft #AzureAI #Insurtech #FSI\n"
            f"- Do NOT include a 'Read more' line — that will be appended after.\n"
            + (f"- Additional instructions: {custom_prompt}\n" if custom_prompt else "")
        )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.75,
    )

    return response.choices[0].message.content.strip()


def post_to_linkedin(content):
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {LINKEDIN_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    post_data = {
        "author": (
            f"urn:li:person:{PERSON_URN}"
            if "urn:li:person:" not in PERSON_URN
            else PERSON_URN
        ),
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    res = requests.post(url, headers=headers, json=post_data)
    if res.status_code == 201:
        print("\n✅ POSTED SUCCESSFULLY!")
    else:
        print(f"\n❌ FAILED: {res.status_code}\n{res.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python linkedin.py 'Topic' ['Prompt'] ['URL'] [--style 1|2|3]")
        print("\nStyles:")
        for sid, s in STYLES.items():
            print(f"  {sid}: {s['name']}")
        sys.exit()

    current_topic = sys.argv[1]
    current_instr = None
    article_url = None
    force_style_id = None

    # Parse optional args
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--style" and i + 1 < len(args):
            try:
                force_style_id = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif args[i].startswith("http"):
            article_url = args[i]
            i += 1
        else:
            current_instr = args[i]
            i += 1

    article_text = fetch_article_text(article_url) if article_url else None

    # Pick style once for this session run
    active_style = pick_style(current_topic, force_style=force_style_id)

    raw_content = generate_post(
        current_topic,
        custom_prompt=current_instr,
        article_context=article_text,
        style=active_style,
    )

    # Apply persistent post-processing: @Microsoft + Read more link
    post_content = enforce_emoji_count(append_read_more(raw_content, article_url))

    while True:
        print(
            "\n" + "=" * 50
            + f"\nDRAFT POST PREVIEW  [Style: {active_style['name']}]\n"
            + "=" * 50
            + f"\n{post_content}\n"
            + "=" * 50
        )
        print("\n1) Adjustment Prompt (Refine this draft)")
        print("2) Try a different style")
        print("3) Manually edit this draft")
        print("4) Send to LinkedIn")
        print("5) Cancel")

        choice = input("\nSelect (1-5): ").strip()

        if choice == "1":
            feedback = input(
                "\nWhat should I change? (e.g. 'shorter', 'more professional'): "
            ).strip()
            if feedback:
                # Allow inline URL swap in feedback
                if "http" in feedback:
                    parts = feedback.split()
                    new_url = next((p for p in parts if p.startswith("http")), None)
                    if new_url:
                        article_url = new_url
                        article_text = fetch_article_text(article_url)
                        feedback = feedback.replace(new_url, "(using new article context)")

                # Strip the Read more line before sending to the model so it doesn't echo it back
                post_without_link = "\n".join(
                    l for l in post_content.splitlines()
                    if not l.strip().lower().startswith("read more:")
                ).rstrip()

                raw_content = generate_post(
                    current_topic,
                    feedback,
                    existing_post=post_without_link,
                    article_context=article_text,
                    style=active_style,
                )
                post_content = enforce_emoji_count(append_read_more(raw_content, article_url))
            continue

        elif choice == "2":
            print("\nChoose a style:")
            for sid, s in STYLES.items():
                marker = " ← current" if s["name"] == active_style["name"] else ""
                print(f"  {sid}: {s['name']}{marker}")
            style_pick = input("Style number (or Enter to rotate): ").strip()
            if style_pick.isdigit() and int(style_pick) in STYLES:
                active_style = STYLES[int(style_pick)]
            else:
                current_ids = list(STYLES.keys())
                current_idx = current_ids.index(
                    next(k for k, v in STYLES.items() if v["name"] == active_style["name"])
                )
                active_style = STYLES[current_ids[(current_idx + 1) % len(current_ids)]]

            raw_content = generate_post(
                current_topic,
                current_instr,
                article_context=article_text,
                style=active_style,
            )
            post_content = enforce_emoji_count(append_read_more(raw_content, article_url))
            continue

        elif choice == "3":
            print("\n📝 Opening draft in editor... (save and close to return)")
            edited = manual_edit(post_content)
            if edited != post_content:
                post_content = edited
                print("✅ Draft updated with your edits.")
            else:
                print("No changes detected.")
            continue

        elif choice == "4":
            confirm = input("Confirm publish to LinkedIn? (y/n): ").lower().strip()
            if confirm == "y":
                post_to_linkedin(post_content)
                break
            continue

        elif choice == "5":
            print("Post discarded.")
            break

        else:
            print("Invalid selection. Choose 1-5.")