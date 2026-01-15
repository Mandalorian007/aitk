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
export OPENAI_API_KEY=sk-...      # image, video
export PERPLEXITY_API_KEY=pplx-...  # search
export FIRECRAWL_API_KEY=fc-...     # scrape
```

## Commands

| Command | Purpose |
|---------|---------|
| `aitk image` | Image generation (OpenAI GPT Image) |
| `aitk video` | Video generation (OpenAI Sora) |
| `aitk search` | Web search (Perplexity) |
| `aitk scrape` | Web scraping (Firecrawl) |
| `aitk browser` | Browser automation (Playwright) |

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

## Help

```bash
aitk --help
aitk <command> --help
```
