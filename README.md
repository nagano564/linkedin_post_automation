# LinkedIn Automation Tool
An automated Python tool designed to discover relevant articles, track history to avoid duplicate shares, and seamlessly publish content to LinkedIn.

## 📁 Project Structure
* `linkedin.py` - Core automation script for posting and interacting with LinkedIn.
* `find_url.py` - Script for sourcing and filtering new content or articles.
* `used_articles.json` - Local database tracking previously processed content.
* `.gitignore` - Safeguards private credentials (`.env`) from public tracking.

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python installed, then install any required dependencies (e.g., `requests`, `python-dotenv`, `selenium`, etc., depending on your setup).

### 2. Configuration
Create a `.env` file in the root directory of this project to store your sensitive credentials (this file is automatically ignored by Git):

```env
OPENAI_API_KEY=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_PERSON_URN=
```

## 🔑 How to Get Your API Keys & Credentials

### OpenAI API Key
1. Go to [https://platform.openai.com](https://platform.openai.com) and sign in or create an account.
2. Click your profile icon in the top-right corner and select **API keys**.
3. Click **Create new secret key**, give it a name, and copy it.
4. Paste it as the value for `OPENAI_API_KEY` in your `.env` file.

> ⚠️ You will only see the key once — save it immediately.

---

### LinkedIn API Credentials

You'll need a LinkedIn Developer App to get your `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`, `ACCESS_TOKEN`, and `PERSON_URN`.

#### Step 1 — Create a LinkedIn App
1. Go to [https://www.linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) and sign in.
2. Click **Create App**.
3. Fill in the required fields (App Name, LinkedIn Page, Logo) and click **Create App**.

#### Step 2 — Get Your Client ID & Secret
1. Open your newly created app and go to the **Auth** tab.
2. Copy the **Client ID** → paste into `LINKEDIN_CLIENT_ID`.
3. Click **Generate a new client secret**, copy it → paste into `LINKEDIN_CLIENT_SECRET`.

#### Step 3 — Set Your Redirect URI
1. Still on the **Auth** tab, scroll to **Authorized Redirect URLs for your App**.
2. Add your redirect URI (e.g., `http://localhost:8000/callback`) and save.
3. Paste that same URL as the value for `LINKEDIN_REDIRECT_URI`.

#### Step 4 — Get Your Access Token
1. Go to the **Auth** tab and use the **OAuth 2.0 tools** (or use an OAuth flow in your app) to authorize with the required scopes (e.g., `r_liteprofile`, `w_member_social`).
2. After authorizing, copy the returned **access token** → paste into `LINKEDIN_ACCESS_TOKEN`.

> ⚠️ Access tokens expire. You may need to refresh them periodically depending on your app's OAuth settings.

#### Step 5 — Get Your Person URN
Your `PERSON_URN` is your LinkedIn member ID in the format `urn:li:person:XXXXXXXX`.

1. Make a test API call using your access token:
   ```bash
   curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     https://api.linkedin.com/v2/me
   ```
2. Look for the `id` field in the response — your URN will be `urn:li:person:<id>`.
3. Paste the full URN as the value for `LINKEDIN_PERSON_URN`.

## ▶️ Running the App

### cd into the folder directory and then 

### Step 1 — Discover an article
```bash
python find_url.py
```
The script searches for a recent, relevant Microsoft Azure article, validates it, and automatically copies a ready-to-run command to your clipboard.

### Step 2 — Generate your post
python find_url will copy a command into your clipboard

Paste the copied command into your terminal and press **Enter** (Cmd+V on Mac, Ctrl+V on Windows/Linux):
```bash
python send_to_linkedin.py "Article Topic" "Your prompt instructions" "https://article-url.com"
```
The AI will read the article and generate a LinkedIn post in one of three writing styles.

### Step 3 — Review and refine
Once the draft appears, you'll see a menu with five options:

```
1) Adjustment Prompt (Refine this draft)
2) Try a different style
3) Manually edit this draft
4) Send to LinkedIn
5) Cancel
```

**Option 1 — Adjustment Prompt:** Type natural language feedback to refine the draft. For example:
- `"Make it shorter"`
- `"More professional tone"`
- `"Focus more on cost savings"`

The post is regenerated instantly using your feedback.

**Option 2 — Try a different style:** Switch between three AI writing styles:
- **Punchy Bullets** — Fast, scannable, hook + bullet points + CTA
- **Storytelling Narrative** — Human, reflective, flows as short paragraphs
- **Hot Take / Contrarian** — Bold opinion, challenges conventional wisdom

**Option 3 — Manually edit this draft:** Opens the post in your terminal's text editor (defaults to `nano`). Make any changes you like, save, and close to return to the menu.

> 💡 To use a different editor, set the `EDITOR` environment variable: `export EDITOR=vim`

**Option 4 — Send to LinkedIn:** Publishes the post directly to your LinkedIn profile. You'll be asked to confirm before anything goes live.

**Option 5 — Cancel:** Discards the draft without posting.

---
