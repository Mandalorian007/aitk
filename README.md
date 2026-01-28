# aitk

Unified CLI for AI-powered development tools.

## Install

```bash
uv tool install git+https://github.com/Mandalorian007/aitk
```

## Update

```bash
uv tool upgrade aitk
```

## Configure

```bash
aitk config
```

Or set environment variables:

```bash
export OPENAI_API_KEY=sk-...        # image, video
export PERPLEXITY_API_KEY=pplx-...  # search
export FIRECRAWL_API_KEY=fc-...     # scrape
export NOTION_API_KEY=ntn_...       # notion
```

## Commands

| Command | Purpose |
|---------|---------|
| `aitk image` | Image generation (OpenAI GPT Image) |
| `aitk video` | Video generation (OpenAI Sora) |
| `aitk search` | Web search (Perplexity) |
| `aitk scrape` | Web scraping (Firecrawl) |
| `aitk browser` | Browser automation (Playwright) |
| `aitk notion` | Notion project boards |
| `aitk env` | Encrypted .env file management (age) |

## Usage

### Image Generation

```bash
aitk image generate "a cat wearing a top hat"
aitk image generate "app icon" -o icon.png -b transparent
aitk image edit -i photo.png "remove the background"
aitk image emojify large_icon.png
```

### Video Generation

```bash
aitk video create hero.png "walking forward"
aitk video status <job_id>
aitk video download <job_id> -o animation.mp4
aitk video webpify animation.mp4
```

### Web Search

```bash
aitk search "latest python 3.13 features"
```

### Web Scraping

```bash
aitk scrape page https://docs.example.com
aitk scrape map https://example.com --search "api"
```

### Browser Automation

```bash
aitk browser init                    # first-time setup
aitk browser start
aitk browser nav "https://example.com"
aitk browser screenshot -o page.png
aitk browser click "#login-button"
aitk browser type "#email" "user@example.com"
aitk browser a11y                    # accessibility tree
aitk browser close
```

### Notion

```bash
aitk notion dbs                              # list accessible databases
aitk notion board --db <id>                  # list items
aitk notion board --db <id> -s "In progress" # filter by status
aitk notion add "New task" --db <id>         # create item
aitk notion view <id> --db <id>              # view item details
aitk notion move <id> Done --db <id>         # change status
aitk notion delete <id> --db <id>            # delete (archive) item
```

Get your integration token at https://www.notion.com/my-integrations

### Env Store

Store age-encrypted .env files in a private GitHub repo. Useful for securely sharing secrets across machines and CI/CD.

**Setup (one-time):**

```bash
# 1. Install age
brew install age

# 2. Create empty private repo for env store
gh repo create my-env-store --private  # no --add-readme flag

# 3. Generate key pair
aitk env init

# 4. Add output to ~/.config/aitk/config:
#    ENV_STORE_KEY=AGE-SECRET-KEY-1...
#    ENV_STORE_PUBLIC_KEY=age1ql3z...
#    ENV_STORE_REPO=yourname/my-env-store
```

**Usage:**

```bash
aitk env push owner/repo      # encrypt & push .env files to store
aitk env pull owner/repo      # decrypt & pull .env files from store
aitk env diff owner/repo      # compare local vs store (masked)
aitk env list                 # list all repos in store
aitk env list owner/repo      # list .env files for a repo
```

## Help

```bash
aitk --help
aitk <command> --help
```
