# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Voxture is a voice AI evaluation platform that tests voice bots with real-world data (construction sites, factories) combined with synthetic variations to catch failures that clean synthetic-only testing misses.

## Tech Stack

- Plain HTML + Tailwind CSS (via CDN)
- Vanilla JavaScript (no frameworks)
- No build tools required - open HTML files directly in browser

## Development

Open any HTML file directly in a browser to view. No server or build step needed.

## Architecture

Multi-page static dashboard with hardcoded demo data. Each page shares a consistent layout:
- Fixed top nav (h-14): Logo, connected bot indicator, settings
- Fixed left sidebar (w-56): Navigation with active state highlighting
- Scrollable main content area
- Fixed right sidebar (w-80 on dashboard, w-72 on test-runs): Contextual widgets

### Pages

- `dashboard.html` - Home page with latest test run results, failure categories, detailed failures list
- `test-runs.html` - Test history table with expandable row details, filters
- `settings.html` - API integration, connected bots, test configuration, account settings

### Shared Patterns

Each page duplicates the Tailwind config, common styles (scrollbar, animations), nav, and sidebar. When modifying shared elements, update all three files.

Collapsible sections use `toggleCollapse(id)` pattern with `.collapse-content.expanded` CSS class and chevron rotation.

## Design System

- Dark theme: Background `#0a0a0a`, Cards `#1a1a1a`, Borders `zinc-800`
- Accent: Blue `#3b82f6`
- Severity colors: Red (critical), Amber (moderate), Green (low)
- Monospace font for numerical data: `.mono` class (JetBrains Mono)
- Active nav items: `bg-blue-500/10 text-blue-400 border border-blue-500/20`
- Status indicators use `.pulse-dot` animation for live states
