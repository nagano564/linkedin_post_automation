# LinkedIn Automation Tool
An automated Python tool designed to discover relevant articles, track history to avoid duplicate shares, and seamlessly publish content to LinkedIn.

## 📁 Project Structure
* `linkedin.py` - Core automation script for posting and interacting with LinkedIn.
* `discover.py` - Script for sourcing and filtering new content or articles.
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

1. Open your terminal and navigate to the project folder.

2. Run the discovery script:
   ```bash
   python discover.py
   ```

3. The script will generate a command and copy it to your clipboard automatically.

4. Paste the copied command into your terminal and press **Enter**:
   ```bash
   # Just press Cmd+V (Mac) or Ctrl+V (Windows/Linux) and hit Enter
   ```

5. Follow the on-screen prompts — and you're good to go! ✅

---

