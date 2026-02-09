# Deploying to Cloudflare Pages

This repo is a **pnpm workspace**: the app is in `pokant-landing-page` (Next.js with static export). The build must run from the **repository root** so `pnpm install` and `pnpm run build` see the root `package.json` and workspace.

## Cloudflare Pages – Build configuration

Use these settings in **Workers & Pages → your project → Settings → Builds & deployments**.

| Setting | Value |
|--------|--------|
| **Root directory** | Leave **empty** (or `.`). Do not use `/`. |
| **Build command** | `cd /opt/buildhome/repo && bash scripts/build-cloudflare-pages.sh` |
| **Build output directory** | `pokant-landing-page/out` |
| **Deploy command** | `npx wrangler pages deploy pokant-landing-page/out --project-name=pokant-website` |

- Replace `pokant-website` with your actual **Pages project name** if different.
- The build script ensures the build runs from the repo root even if Cloudflare’s root directory setting is wrong.

## If deploy command can be left empty

If your project allows an empty deploy command, leave it blank. Cloudflare will deploy the build output directory automatically. Then use:

- **Build command:** `cd /opt/buildhome/repo && bash scripts/build-cloudflare-pages.sh`
- **Build output directory:** `pokant-landing-page/out`
- **Deploy command:** *(empty)*

## Local build (same output)

```bash
pnpm install
pnpm run build
```

Static files are written to `pokant-landing-page/out`.
