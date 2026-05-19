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
# Heavily optimized to feel casual, narrative, and less uniform/robotic
STYLES = {
    1: {
        "name": "Punchy Conversation",
        "description": (
            "Fast, human, and easily scannable. Uses short blocks of text and sparse, "
            "intentional spacing instead of perfectly aligned textbook bullets."
        ),
        "format": (
            "FORMAT RULES:\n"
            "- Line 1: A casual, strong observation or counter-intuitive thought. No emoji.\n"
            "- Blank line.\n"
            "- Write in short, conversational paragraphs (1-2 sentences maximum per block).\n"
            "- Use at most 1 or 2 emojis in the entire post, and only if they feel completely natural.\n"
            "- End with a direct question aimed at insurance and enterprise tech leaders.\n"
            "- 3-5 hashtags on the last line.\n"
            "TONE: Plainspoken, sharp, practical."
        ),
    },
    2: {
        "name": "Storytelling Narrative",
        "description": (
            "Opens with an unpolished micro-story or a concrete engineering/business scenario. "
            "Flows like a natural conversation or slack message to a peer. No bullets."
        ),
        "format": (
            "FORMAT RULES:\n"
            "- Open with a 1-2 sentence real-world situation: 'Last week we were looking at...' "
            "or 'A common issue when migration hits...' — grounded and specific.\n"
            "- 2-3 short paragraphs flowing naturally. Absolute ban on bullet points.\n"
            "- A single-sentence realization or takeaway before closing.\n"
            "- End with an open-ended invitation for peer feedback.\n"
            "- 3-5 hashtags on the last line.\n"
            "TONE: Collaborative, transparent, senior practitioner voice."
        ),
    },
    3: {
        "name": "Direct Industry Take",
        "description": (
            "Challenges conventional wisdom or generic industry buzzwords directly. "
            "Argues an honest, logical point about enterprise tech architecture."
        ),
        "format": (
            "FORMAT RULES:\n"
            "- Line 1: A direct statement showing why a common approach fails. "
            "Example: 'The problem with scaling architecture right now isn't the data size—it's how we model it.'\n"
            "- Blank line.\n"
            "- 2-3 short, unpolished text sections defending the take with technical logic.\n"
            "- Speak directly to structural reality, skipping corporate jargon.\n"
            "- Close with a prompt asking how other teams tackle this constraint.\n"
            "- 3-5 hashtags on the last line.\n"
            "TONE: Opinionated, intellectually honest, grounded."
        ),
    },
}

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
    Append a link to the post content if a URL is provided.
    """
    if not url:
        return content

    lines = content.splitlines()
    lines = [l for l in lines if not l.strip().lower().startswith("read more:")]
    clean = "\n".join(lines).rstrip()
    return f"{clean}\n\nLink: {url}"


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
        return content
    finally:
        os.unlink(tmp_path)


def generate_post(topic, custom_prompt=None, existing_post=None, article_context=None,
                  style: dict = None):
    """Generates or adjusts a post utilizing a sharp, human system instruction set."""

    context_str = f"\nARTICLE CONTEXT:\n{article_context}\n" if article_context else ""

    # Humanizing System Guidelines: Blocks typical AI phrasing patterns completely
    system_instruction = (
        "You are a Cloud and AI Specialist at Microsoft, focusing on Enterprise Financial Services "
        "and Insurance architectures.\n\n"
        "STRICT ANTI-AI VOICE WRITING INSTRUCTIONS:\n"
        "- Absolute ban on corporate-bot words: delve, tapestry, game-changer, landscape, foster, testament, paradigm, bespoke, utilize, reshape.\n"
        "- Do NOT use uniform, heavily manicured multi-bullet emoji blocks. Write like a human talking to a respected industry colleague.\n"
        "- Never start with fake profound structures like 'It's not about X, it's about Y.'\n"
        "- Keep syntax variable. Mix short sentences with medium ones. Leave things a bit punchy and unpolished.\n"
        "- Do NOT mention real estate or being a real estate agent.\n"
        "- Always reference @Microsoft naturally within the post paragraph text.\n"
        "- Output ONLY the final post content. No conversational introduction or labels."
    )

    if existing_post:
        print(f"🔄 Adjusting post based on feedback...")
        style_note = (
            f"\nThis post uses the '{style['name']}' writing style. "
            f"Keep the same style unless requested otherwise.\n"
            f"Style description: {style['description']}\n"
            f"{style['format']}\n"
        ) if style else ""

        user_prompt = (
            f"Here is the current LinkedIn post draft about '{topic}':\n\n"
            f"--- EXISTING POST ---\n{existing_post}\n------------------\n\n"
            f"{context_str}"
            f"{style_note}"
            f"Please ADJUST the post text according to these instructions: {custom_prompt}\n"
            "Make sure it sounds completely human, natural, and free of typical AI catchphrases."
        )
    else:
        style = style or STYLES[1]
        print(f"🚀 Generating post about: {topic}...")
        print(f"   ✍️ Style: {style['name']}")

        user_prompt = (
            f"{context_str}\n"
            f"Write a raw, engaging LinkedIn post about '{topic}' for an audience of financial services and insurance enterprise leaders.\n\n"
            f"WRITING STYLE: {style['name']}\n"
            f"{style['description']}\n\n"
            f"{style['format']}\n\n"
            f"CONTENT STRATEGY:\n"
            f"- Theme: Microsoft Azure AI, Copilot engineering, or secure cloud infrastructure limits in FSI.\n"
            f"- Ensure @Microsoft is explicitly mentioned inside the text narrative naturally.\n"
            f"- Include hashtags: #Microsoft #AzureAI #Insurtech #FSI\n"
            + (f"- Additional nuances to add: {custom_prompt}\n" if custom_prompt else "")
        )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.72,
    )

    return response.choices[0].message.content.strip()


def trigger_linkedin_scraper_shortcut(url):
    """
    Forces LinkedIn's offsite sharing gateway to fetch and cache 
    the metadata/image for a URL before the API post is executed.
    """
    try:
        print(f"🔗 Triggering automated scraper shortcut for: {url}...")
        gateway_url = f"https://www.linkedin.com/sharing/share-offsite/?url={requests.utils.quote(url)}"
        requests.get(gateway_url, timeout=10)
    except Exception as e:
        print(f"⚠️ Warning: Scraper shortcut ping failed: {e}")


def post_to_linkedin(content, source_url=None):
    """
    Posts to the modern LinkedIn /posts API endpoint.
    Handles link/article object structure natively if a URL is attached.
    """
    # Base endpoint URL for the updated LinkedIn API engine
    url = "https://api.linkedin.com/v2/posts"
    
    headers = {
        "Authorization": f"Bearer {LINKEDIN_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    
    formatted_author = f"urn:li:person:{PERSON_URN}" if "urn:li:person:" not in PERSON_URN else PERSON_URN

    # Setup the structured payload map according to whether a URL preview is required
    post_data = {
        "author": formatted_author,
        "commentary": content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED"
    }

    if source_url:
        # Before sending, force LinkedIn's crawler to look at the URL and cache images
        trigger_linkedin_scraper_shortcut(source_url)
        
        # Inject the article mapping fields required for rich snippet attachment
        post_data["content"] = {
            "article": {
                "source": source_url,
                "title": "Article Update",  # Will be dynamically overwritten by LinkedIn if OG tags pull correctly
                "description": "Enterprise cloud insight update."
            }
        }

    res = requests.post(url, headers=headers, json=post_data)
    
    # LinkedIn /posts API returns 201 Created on success
    if res.status_code == 201:
        print("\n✅ POSTED TO LINKEDIN SUCCESSFULLY!")
    else:
        print(f"\n❌ FAILED TO POST: {res.status_code}\n{res.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python linkedin.py 'Topic' ['Prompt'] ['URL'] [--style 1|2|3]")
        sys.exit()

    current_topic = sys.argv[1]
    current_instr = None
    article_url = None
    force_style_id = None

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
    active_style = pick_style(current_topic, force_style=force_style_id)

    raw_content = generate_post(
        current_topic,
        custom_prompt=current_instr,
        article_context=article_text,
        style=active_style,
    )

    # Simple clean concatenation - no artificial emoji loops
    post_content = append_read_more(raw_content, article_url)

    while True:
        print(
            "\n" + "=" * 50
            + f"\nDRAFT POST PREVIEW [Style: {active_style['name']}]\n"
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
            feedback = input("\nWhat should I change?: ").strip()
            if feedback:
                if "http" in feedback:
                    parts = feedback.split()
                    new_url = next((p for p in parts if p.startswith("http")), None)
                    if new_url:
                        article_url = new_url
                        article_text = fetch_article_text(article_url)
                        feedback = feedback.replace(new_url, "(using new article context)")

                post_without_link = "\n".join(
                    l for l in post_content.splitlines()
                    if not l.strip().lower().startswith("link:")
                ).rstrip()

                raw_content = generate_post(
                    current_topic,
                    feedback,
                    existing_post=post_without_link,
                    article_context=article_text,
                    style=active_style,
                )
                post_content = append_read_more(raw_content, article_url)
            continue

        elif choice == "2":
            print("\nChoose a style:")
            for sid, s in STYLES.items():
                marker = " ← current" if s["name"] == active_style["name"] else ""
                print(f"  {sid}: {s['name']}{marker}")
            style_pick = input("Style number: ").strip()
            if style_pick.isdigit() and int(style_pick) in STYLES:
                active_style = STYLES[int(style_pick)]
                
            raw_content = generate_post(
                current_topic,
                current_instr,
                article_context=article_text,
                style=active_style,
            )
            post_content = append_read_more(raw_content, article_url)
            continue

        elif choice == "3":
            print("\n📝 Opening draft in editor...")
            edited = manual_edit(post_content)
            if edited != post_content:
                post_content = edited
                print("✅ Draft updated.")
            continue

        elif choice == "4":
            confirm = input("Confirm publish to LinkedIn? (y/n): ").lower().strip()
            if confirm == "y":
                # Passes the article_url forward down to the updated /posts payload function
                post_to_linkedin(post_content, source_url=article_url)
                break
            continue

        elif choice == "5":
            print("Post discarded.")
            break