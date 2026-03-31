# Observius

Reliability and observability for browser automation agents.

**Before:**

```python
agent = Agent(task="Extract pricing", llm=llm, browser=browser)
result = await agent.run()
# Crashes on API errors. Loops forever. No idea what happened.
```

**After:**

```python
from computeruse import wrap
result = await wrap(agent).run()
# Auto-retry. Stuck detection. Screenshots. Cost tracking. Local dashboard.
```

Works with [browser-use](https://github.com/browser-use/browser-use) agents and raw Playwright scripts. One import, zero config changes.

## Install

```bash
pip install observius
```

## Quick Start: browser-use

```python
import asyncio
from browser_use import Agent
from langchain_anthropic import ChatAnthropic
from computeruse import wrap

async def main():
    llm = ChatAnthropic(model="claude-sonnet-4-5-20250514")
    agent = Agent(task="Find the top story on Hacker News", llm=llm)
    wrapped = wrap(agent)
    result = await wrapped.run()

    print(f"Cost: ${wrapped.cost_cents / 100:.4f}")
    print(f"Steps: {len(wrapped.steps)}")
    if wrapped.replay_path:
        print(f"Replay: {wrapped.replay_path}")

asyncio.run(main())
```

## Quick Start: Playwright

```python
import asyncio
from playwright.async_api import async_playwright
from computeruse import track

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        async with track(page) as t:
            await t.goto("https://example.com")
            await t.click("a")

        print(f"Steps: {len(t.steps)}")
        t.save_replay()
        await browser.close()

asyncio.run(main())
```

## View Results

```bash
pip install observius[dashboard]
computeruse dashboard
```

Or from the CLI:

```bash
computeruse info          # summary of runs, costs, screenshots
computeruse clean         # delete runs older than 7 days
computeruse replay .observius/replays/abc123.html
```

## Features

- **Auto-retry** with exponential backoff and error classification
- **Stuck detection** catches looping agents (repeated screenshots, actions, failures)
- **Cost tracking** from token counts or browser-use's built-in totals
- **Screenshot capture** at every step, saved to disk
- **HTML replay** generation for visual debugging
- **Run metadata** persisted as JSON for programmatic analysis
- **Session persistence** saves/restores cookies across runs
- **Error classification** maps exceptions to categories (transient, auth, timeout, etc.)
- **CLI tools** for inspecting runs, launching the dashboard, and cleanup

## Configuration

### WrapConfig (browser-use agents)

```python
from computeruse import wrap, WrapConfig

config = WrapConfig(
    max_retries=3,                   # retry on transient errors
    enable_stuck_detection=True,     # detect looping agents
    stuck_screenshot_threshold=4,    # consecutive identical screenshots
    stuck_action_threshold=5,        # consecutive identical actions
    stuck_failure_threshold=3,       # consecutive failures
    track_cost=True,                 # calculate cost from tokens
    session_key="github.com",        # persist cookies across runs
    save_screenshots=True,           # save step screenshots to disk
    output_dir=".observius",         # where to write all output
    generate_replay=True,            # create HTML replay file
    task_id=None,                    # custom task ID (auto-generated if None)
)

wrapped = wrap(agent, config=config)
result = await wrapped.run()
```

### TrackConfig (Playwright scripts)

```python
from computeruse import track, TrackConfig

config = TrackConfig(
    capture_screenshots=True,        # screenshot after each action
    retry_navigations=True,          # retry failed page.goto() calls
    max_navigation_retries=3,        # max retries per navigation
    session_key=None,                # persist cookies across runs
    output_dir=".observius",         # where to write all output
    task_id=None,                    # custom run ID (auto-generated if None)
)

async with track(page, config=config) as t:
    await t.goto("https://example.com")
```

## Architecture

```
Your Agent --> wrap() / track() --> Observius Layer ----> .observius/
                                    |                     |-- runs/*.json
                                    |-- Error Classifier  |-- screenshots/
                                    |-- Auto-Retry        '-- replays/*.html
                                    |-- Stuck Detector
                                    |-- Cost Tracker
                                    '-- Session Manager
                                             |
                                             v
                                    computeruse dashboard
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `computeruse run --url URL --task TASK` | Run a browser automation task |
| `computeruse info` | Show summary of run data |
| `computeruse dashboard` | Launch local debugging dashboard |
| `computeruse replay FILE` | Open a replay in the browser |
| `computeruse sessions` | List saved browser sessions |
| `computeruse clean` | Delete old run data |
| `computeruse version` | Print installed version |

## API Reference

### Exports from `computeruse`

| Export | Type | Description |
|--------|------|-------------|
| `wrap(agent, config=None, **kwargs)` | function | Add reliability layer to a browser-use Agent |
| `track(page, config=None, **kwargs)` | context manager | Track a Playwright Page with screenshots and timing |
| `WrapConfig` | dataclass | Configuration for `wrap()` |
| `TrackConfig` | dataclass | Configuration for `track()` |
| `WrappedAgent` | class | Returned by `wrap()`, call `.run()` on it |
| `TrackedPage` | class | Yielded by `track()`, use like a Playwright Page |
| `classify_error(exc)` | function | Classify an exception into an error category |
| `should_retry_task(category, attempt, max_retries)` | function | Decide whether to retry based on error category |
| `StuckDetector` | class | Detect looping agents from step history |
| `ReplayGenerator` | class | Generate HTML replay from step data |
| `calculate_cost_cents(tokens_in, tokens_out)` | function | Estimate cost from token counts |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
