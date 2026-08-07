# quote0-desk

[中文](README.md) | **English**

**Turns the [Quote/0](https://dot.mindreset.tech/developers) e-ink display from a one-way panel into an NFC-interactive desk device.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](requirements.txt)
[![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](scripts/install_launchd.sh)

A local Python service that pushes custom content cards to a Quote/0 e-ink display: a **desktop pet**, **I-Ching hexagram casting**, **Qimen Dunjia divination**, a **proverb generator**, plus a conversational **status board** and **oracle follow-up** that you write to the screen just by talking to Claude. All of it is bidirectional over NFC — tap your phone, the server runs an action, new content is pushed back to the screen immediately. It's not a "push it and forget it" panel.

<p align="center">
<img src="docs/img/pet.png" width="130"> <img src="docs/img/liuyao.png" width="130"> <img src="docs/img/qimen.png" width="130"> <img src="docs/img/proverb.png" width="130"> <img src="docs/img/agent_board.png" width="130"> <img src="docs/img/oracle_review.png" width="130">
</p>

---

The official MindReset ecosystem already has 20+ third-party projects (Home Assistant integrations, usage dashboards, MCP servers, etc.), almost all one-way data panels: push content, done. What sets this project apart is putting the device's built-in NFC chip to work, closing the loop: tap your phone → it opens the callback URL tied to the currently displayed card → the server runs an action (feed the pet, draw a lot, check off a task, advance to the next proverb) → the new content is pushed back to the screen immediately.

## A day with it

- **Morning**: the screen shows the day's ganzhi (stems-and-branches) pushed the night before; a tap on the desktop pet flips it into an "energized" state via NFC.
- **While coding**: tell Claude "note this down — the bug was an upstream API response-order change," and a timestamped line appears on the screen — no window switch, no phone needed.
- **A focus block**: tap to start a Pomodoro; the screen shows start/end times, and the focus block won't get interrupted by auto-rotation while it's running.
- **An undecided call**: tell Claude "cast a hexagram on whether to scrap this plan and start over," and a few days later Quote/0 will remind you on its own to come back and check whether it "came true" — no need to remember to ask.
- **On the way home**: tap the lot-drawing card for a random I-Ching or Qimen reading — a small ritual that needs no reason.

These scenarios rest on two different input paths: **an NFC tap** (for instant triggers when you're already standing in front of the device) and **talking to Claude** (for "this thought is in my head right now, the screen should remember it" — see [MCP](#mcp-let-claude-operate-quote0-directly) below).

## Features

- **NFC closed loop**: tap your phone, the server runs an action, new content is pushed back immediately — not a "scan to see more" one-way redirect.
- **Web console**: `http://localhost:5252` gives you device status, a preview/push button per card, and the auto-rotation toggle — no need to remember CLI flags.
- **16 content cards**: desktop pet, I-Ching casting, Qimen Dunjia, lot-drawing box, daily ganzhi, proverb generator, today's one task, Pomodoro timer, status board, oracle follow-up, time capsule, trading beacon, Hermes task board, Hermes inbox, Claude Code usage status light, and wallpaper (upload your own image).
- **Pet state aligned with official semantics**: the ASCII art and state machine are ported from Anthropic's official [claude-desktop-buddy](https://github.com/anthropics/claude-desktop-buddy); wired into [buddy-bridge](#optional-integration-buddy-bridge) it's driven by real Claude Code session signals.
- **Runs in the background, tunnel self-heals**: `server.py` and the NFC public tunnel are registered as macOS LaunchAgents — they auto-restart on crash, and the tunnel address is rewritten to config automatically whenever it changes.
- **MCP tools**: concrete per-card tools like `draw_hexagram()`, `pat_pet()`, `set_today_task(...)`, not a generic text/image passthrough interface.
- **Official REST API only**: no jailbreaking, no privilege escalation, no firmware access — everything is built on the two official push paths, Text API and Image API.

## Screenshots

Tap your phone on NFC, and the screen instantly goes from the left image to the right — this is the project's one and only proof of the closed loop. The real-device verification record for NFC-triggered screen changes is in the M2 section of [`docs/DEVICE-FACTS.md`](docs/DEVICE-FACTS.md):

<p align="center">
  <img src="docs/img/pet_pat_before_after.png" width="80%" alt="Pet pat before/after: idle state on the left, energized state on the right after an NFC tap">
</p>

The rest of the cards (all data shown is fictional demo content):

<table align="center">
<tr>
<td align="center" width="20%"><img src="docs/img/pet_hero.png" width="100%" alt="Desktop pet card"><br><sub>Desktop pet<br>state driven by activity signal</sub></td>
<td align="center" width="20%"><img src="docs/img/pet_states.png" width="100%" alt="Pet six-state grid"><br><sub>Pet states<br>sleep/idle/busy/waiting/celebrate/pat</sub></td>
<td align="center" width="20%"><img src="docs/img/liuyao_hero.png" width="100%" alt="I-Ching casting card"><br><sub>I-Ching casting<br>hexagram lines + name</sub></td>
<td align="center" width="20%"><img src="docs/img/qimen_hero.png" width="100%" alt="Qimen Dunjia card"><br><sub>Qimen Dunjia<br>nine-palace chart</sub></td>
<td align="center" width="20%"><img src="docs/img/proverb_hero.png" width="100%" alt="Proverb card"><br><sub>Proverb generator<br>Text API layout</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/img/agent_board_hero.png" width="100%" alt="Status board card"><br><sub>Status board<br>say it, it becomes a line</sub></td>
<td align="center"><img src="docs/img/oracle_review_hero.png" width="100%" alt="Oracle follow-up card"><br><sub>Oracle follow-up<br>reminds you to check back</sub></td>
<td align="center"><img src="docs/img/pomodoro_hero.png" width="100%" alt="Pomodoro card"><br><sub>Pomodoro<br>start/end times</sub></td>
<td align="center"><img src="docs/img/wallpaper_hero.png" width="100%" alt="Wallpaper card"><br><sub>Wallpaper<br>upload or use the default art</sub></td>
<td align="center"><img src="docs/img/status_hero.png" width="100%" alt="Status light card"><br><sub>Status light<br>quota progress bars</sub></td>
</tr>
</table>

## Quickstart

```bash
pip install -r requirements.txt

export DOT_API_KEY=dot_xxx...     # create one via Dot App → More → API Key
# export DOT_DEVICE_ID=xxxxxxxx   # optional: auto-discovered if your account has only one device

python3 cli.py hello               # push the simplest card, verify the pipeline
python3 cli.py status              # check device online status
python3 cli.py snapshot out.png    # download the real rendered image currently on screen — the main self-check tool during development
python3 cli.py push <card_name>    # push a card from cards/, e.g. python3 cli.py push pet
python3 cli.py set-todo "today's task"
```

**Prerequisite**: add a **Text API** and an **Image API** content slot in the Dot App's "Content Studio" first, and attach them to the device's loop task. No need to configure their keys manually afterward — `GET /loop/list` auto-discovers them by `type`.

> **Slot limit**: a Quote/0 account has a hard cap of **3** loop slots. If you keep one for official content (weather/news), only **Text API** + **Image API** are actually available. This doesn't limit the number of cards (the scheduler handles rotating between them) — it limits how many content *types* can be on screen at any given instant. Full test notes in [`docs/DEVICE-FACTS.md`](docs/DEVICE-FACTS.md).

## Local console

After `python3 server.py` starts, open `http://localhost:5252` for the web console: device online status, what's actually on screen right now, a "preview" (runs `build()` without pushing) and "push" button per card, and the auto-rotation arm/disarm state — all on one page. The 16 cards are grouped by purpose (interactive / logging & reminders / info display / Hermes integration / custom), each with a one-line description — not an undifferentiated flat list. `/settings` is the config page, for editing the NFC callback URL, toggling auto-rotation, and picking which cards rotate, without hand-editing `config.json` or building `curl` commands.

<p align="center">
  <img src="docs/img/dashboard.png" width="45%" alt="Console home: device status, what's currently on screen, cards grouped by purpose">
  <img src="docs/img/settings_preview.png" width="45%" alt="Settings page: NFC callback URL, auto-rotation toggle and interval">
</p>

The console UI structure is modeled on the sibling project [pocket-prophet-dashboard](https://github.com/BruceLanLan/pocket-prophet-dashboard): `templates/*.html` plus a thin `/api/*` JSON layer, built on Flask's bundled Jinja2, no extra dependencies. If your phone is on the same LAN, `http://<your-LAN-IP>:5252` works from its browser too.

## Setting up NFC interaction

```bash
python3 server.py   # Flask, listens on 0.0.0.0:5252 by default
```

Every push sets the `link` field to the service's own address; tapping NFC opens that URL, which triggers the matching route to run an action and immediately pushes new content back to the screen. This address is controlled by a single setting:

```bash
export NFC_BASE_URL=http://192.168.1.23:5252   # when your phone is on the same LAN
```

Without it, cards ship with no `link` (they still display fine, a tap just does nothing). If your LAN IP changes, or your phone isn't on the same network, use a free public tunnel instead:

```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:5252
# one line of the output will read https://xxxx.trycloudflare.com — set that as NFC_BASE_URL
export NFC_BASE_URL=https://xxxx.trycloudflare.com
```

`nfc_base_url` can also be written directly into `config.json` (already in `.gitignore`, never enters version control), so you don't have to `export` it again in every new terminal.

### Running long-term: launch on boot

The problem with the manual flow is that both `server.py` and `cloudflared` die when the terminal closes or the machine restarts, taking NFC down with them. `scripts/install_launchd.sh` registers both as macOS LaunchAgents: they launch on boot/login, and `launchctl` restarts them automatically on crash; `scripts/tunnel_daemon.sh` parses the new address out of cloudflared's output every time a fresh tunnel comes up and writes it back into `config.json`'s `nfc_base_url`, so nothing needs manual updating.

```bash
cp .env.example .env
# edit .env, fill in your real DOT_API_KEY (.env is already in .gitignore;
# the key is not written into the launchd plist, since that's plaintext XML)

bash scripts/install_launchd.sh   # installs both LaunchAgents and starts them immediately
```

The install script prints the log paths; `data/tunnel_daemon.log` records the currently active tunnel address. To uninstall:

```bash
bash scripts/uninstall_launchd.sh
```

This approach needs no Cloudflare account, at the cost of the tunnel address changing on every restart — that change is written back to config automatically, no manual step required. That's the tradeoff versus a "named tunnel with a fixed domain" (needs an account, address never changes).

### NFC route reference

| Route | Effect |
|---|---|
| `/t/todo_toggle` | Toggle today's one task done/not-done |
| `/t/proverb_next` | Advance the proverb card to the next line |
| `/t/qiantong` | Draw a lot (randomly I-Ching or Qimen, true randomness) |
| `/t/pet_pat` | Pat the desktop pet, triggers a one-shot "energized" reaction |
| `/t/pomodoro` | Pomodoro: start a focus block when idle, end it early when running |
| `/t/oracle_verdict` | Oracle follow-up: mark as "it came true" |
| `/t/ping` | Diagnostic only, logs but does not push |

### Troubleshooting: tap does nothing

Known causes, ordered by likelihood:

1. **Phone has a VPN on.** The one confirmed cause of "NFC opens Dot App's internal preview instead of forwarding to this service's web page" — the app pops up a small, non-interactive window. Turning off the phone's VPN fixes it immediately.
2. **`NFC_BASE_URL` is stale.** LAN IP changes and tunnel process restarts both change the address, while `config.json` still holds the old value. Re-`export` it, or call `config.update()`.
3. **Phone and machine aren't on the same LAN.** Use the public tunnel approach above.
4. **The card's `link` is empty.** Check whether the corresponding `cards/*.py`'s `build()` calls `config.nfc_base_url()` to build the address — not every card needs NFC interaction (status light, time capsule, and beacon simply have no `/t/...` route; an empty `link` there is expected).

## All content cards

| Card | Command | Description |
|---|---|---|
| Proverb generator | `push proverb` | Picks a line from a seed cache, NFC advances to the next; doesn't call a model in real time, to avoid "call the model once per screen refresh" |
| Daily ganzhi | `push daily` | Current moment's four-pillar ganzhi (year/month/day/hour) + day-stem element, reuses the Qimen card's charting engine |
| I-Ching casting | `push liuyao` | True-random coin toss via `secrets` |
| Qimen Dunjia | `push qimen` | Nine-palace chart |
| Lot-drawing box | `push qiantong` | I-Ching or Qimen, chosen randomly; the NFC-triggered version |
| Claude Code status light | `push status` | 5h/7d quota as horizontal progress bars, falls back to a "today's tokens/cost" number when quota is unavailable (no fake progress bar drawn); auto-discovers multiple profiles, details in the header comment of [`render/status.py`](render/status.py) |
| Desktop pet | `push pet` | ASCII art and state semantics ported from the official [anthropics/claude-desktop-buddy](https://github.com/anthropics/claude-desktop-buddy) (MIT): sleep/idle/busy/attention/celebrate/heart. Prefers buddy-bridge's live running/waiting signal, falls back to scanning commit times when unavailable; an NFC tap triggers a pat (heart); `waiting` sustained over 5 minutes escalates from a generic "something's waiting on your approval" to naming the specific tool (requires buddy-bridge) |
| Today's one task | `push todo` / `set-todo "..."` | A single daily commitment, checked off via NFC |
| Pomodoro timer | `push pomodoro` | A tap starts a focus block (screen shows start/end time, no seconds ticking); won't be overwritten by auto-rotation while running, auto-pushes a notification when it ends, independent of whether auto-rotation is on |
| Status board | `push agent_board` | Tell Claude something (e.g. "note that I told Wang I'd have the proposal by Friday") and a timestamped line appears on screen, up to 5 lines shown at once; write-only via conversation, never scrapes anything on its own |
| Oracle follow-up | `push oracle_review` | Tell Claude a question and cast a hexagram on it (e.g. "cast on whether I'll pass this week's interview"), and after a while (7 days by default, configurable in settings) it automatically reminds you to come back and check "did it come true" — independent of auto-rotation; includes historical hit-rate stats |
| Time capsule | `push capsule` | Commits from local git repos made "a year ago / a month ago / a week ago today" |
| Trading beacon | `push beacon` | Read-only display of trading strategy positions + stock-picking signals; doesn't import the source project's code or credentials |
| Hermes task board | `push hermes` | Read-only display of the local [hermes-agent](https://github.com/NousResearch/hermes-agent) gateway's scheduled job list; optional integration, shows "not connected" if Hermes or the gateway isn't running |
| Hermes inbox | see "Hermes Agent Integration" below | Displays the latest message pushed by the Hermes agent (agent message or cron job result), passive receive only, never polls |
| Wallpaper | `push wallpaper` | Upload any image via the console; the server "cover"-fits and crops it to 296×152, then Floyd-Steinberg dithers it to black & white; shows a default image when nothing's uploaded — two Yunnan woodblock folk prints combined side by side (CC BY-SA 4.0, source and attribution in the header comment of [`render/wallpaper.py`](render/wallpaper.py)) |

See [`docs/ADDING-A-CARD.md`](docs/ADDING-A-CARD.md) for how to add a new content card.

### Optional integration: buddy-bridge

If a [buddy-bridge](https://github.com/anthropics/claude-desktop-buddy)-style hook-bridge daemon is running locally (`~/buddy-bridge`, `GET http://127.0.0.1:49431/status`, authenticated via `~/.buddy-bridge/token`), the status light and desktop pet prefer its live `running`/`waiting` signal — more accurate than inferring from transcript file mtime or git commit times. The pet card also gets an extra "something's waiting on your approval" expression from it. This integration is optional; both cards still work without the daemon deployed, just falling back to inference — see the degradation logic in `providers/buddy.py`.

## Project layout

```
quote0-desk/
  dot.py            # thin client for the official REST API: devices/status/settings/text/image/canvas
  config.py         # config read/write; API key comes in only via env var, never written to config.json
  cards/            # content sources: build() returns {"data", ...} (Text API) or {"png", ...} (Image API)
  canvas/           # data shape for text cards (title/message/footer, used by Text API)
  render/           # local PIL rendering for cards needing pixel-level control (hexagram lines, nine-palace chart, ASCII pet)
  providers/        # pure data logic, no rendering/pushing
  server.py         # Flask: NFC callback routes at /t/<action>
  push.py           # per-card push logic shared by cli.py and server.py
  scheduler.py      # background thread that rotates pushes on a schedule
```

All cards time-share 2 slots (Text + Image); `scheduler.py` decides which one should be showing right now. The device's own auto-rotation (`interval.powerMs`) is set to the official maximum (12 hours), so the device doesn't autonomously swap the screen in the gap between our own pushes. Reversing this — using the device's native rotation for a "two parallel channels" setup — was evaluated but rejected: the device's three slots (text/image/official content) rotate together, which would break the core NFC experience of "the result of a tap needs to stay stable on screen." Details in `docs/DEVICE-FACTS.md`.

## Auto-rotation

```bash
python3 cli.py auto-cards proverb daily status todo capsule beacon liuyao qimen pet
python3 cli.py arm            # turn auto-rotation on
python3 cli.py disarm         # turn it off
python3 server.py             # run persistently, the scheduler thread starts alongside Flask
```

Off by default, must be explicitly enabled. The CLI is convenient for one-time setup; for everyday use, prefer the [local console](#local-console)'s settings page, or call `GET/POST /api/config` directly to read/change config (`auto_push_enabled` / `auto_push_interval_minutes` / `auto_push_cards` / `nfc_base_url`).

## Config you'll want to change for your own deployment

Three cards read data from "elsewhere on this machine," and their defaults point at paths on the author's own machine — cloning and running as-is will likely find nothing there. That's not a bug: when data can't be found, these cards show "no data yet" instead of crashing, but you'll want to point them at your own sources:

**Time capsule / desktop pet's activity signal** — config keys `capsule_repos` / `pet_repos`, accept any local git repo path, don't depend on any special file inside the repo, just use `git log` to check for the day's code activity. Defaults point to two other projects on the author's machine; swap in your own repo paths, or point it at this project itself: `~/dev/quote0-desk`.

**Trading beacon** — config keys `beacon_lighter_dir` / `beacon_stock_radar_dir`. This card is a read-only display panel for two other unpublished trading/stock-picking tools of the author's (`lighter-scalper`, `stock-radar`), reading each tool's own local state file format (`data/positions.json`, `scripts/.scan_state/*.json`; see [`providers/beacon.py`](providers/beacon.py) for exact fields). Without a compatible tool deployed, this card won't show useful content — uncheck it in the [local console](#local-console)'s settings page under "auto-rotation." To wire up your own trading tool, adapt the read logic in `providers/beacon.py`; it's a small amount of code.

All of the above paths can be changed from the [local console](#local-console)'s settings page under "path config," or via `POST /api/config`, or by editing `config.json` directly — no Python source changes needed.

## MCP: let Claude operate Quote/0 directly

`mcp_server/` is a standalone MCP server that exposes specific cards as tools (`draw_hexagram()`, `pat_pet()`, `set_today_task(...)`, etc.), rather than a generic text/image passthrough interface — several implementations of the latter already exist in the MindReset ecosystem. See [`mcp_server/README.md`](mcp_server/README.md) for usage; this server needs Python 3.10+ (isolated from the main project's 3.9 environment) and only acts as an HTTP client to the main project's `/api/*` endpoints — it doesn't reach into the main project itself.

`board_note(label, value)` is the only tool whose content is "decided by the current conversation" — every other tool's content comes from computation (daily ganzhi/Qimen), reading existing data (status light/beacon), or randomness (proverb/lot-drawing). Its parameters are required, so Claude will ask a follow-up question when information is incomplete — no extra "ask for missing info" logic needed. `cast_with_question(question)` extends the same idea into the divination direction: tell Claude a specific question, cast a hexagram, and once the follow-up period is up, Quote/0 proactively reminds you to check whether it "came true" — that kind of reminder across time depends on an always-on screen, something a phone-based conversational app can't offer the same way.

## Hermes Agent / Hermes Studio integration

[Hermes Agent](https://github.com/NousResearch/hermes-agent) (NousResearch's open-source agent gateway) and [Hermes Studio](https://hermes-studio.ai) ([JPeetz/Hermes-Studio](https://github.com/JPeetz/Hermes-Studio), a self-hosted web console that runs on top of the gateway) are two different layers: the former is the backend gateway, the latter a browser UI running above it. Integration progress differs between the two:

**Gateway layer (done, verified on real hardware)**: [`hermes-quote0/`](hermes-quote0/) is a platform plugin for Hermes Agent that delivers agent messages or cron job results straight to the Quote/0 screen, using the same mechanism as the official Telegram/Discord delivery channels — no changes to Hermes core. See [`hermes-quote0/README.md`](hermes-quote0/README.md) for usage. The full path has been verified end to end on real hardware: after installing the plugin, a cron job with `deliver=quote0` reaches the screen (shown as the "Hermes inbox" card). The screen always carries a fixed `Hermes Agent` signature and never accepts an NFC link chosen by the agent itself — a hard constraint against prompt injection: agent-generated content isn't trustworthy, so it must never get to decide what a physical tap opens. This integration is optional; both "Hermes inbox" and "Hermes task board" simply stay empty if Hermes isn't installed, everything else keeps working.

**Studio layer (fix identified, not submitted as a PR yet)**: Hermes Studio's Cron job dialogs (`create-job-dialog.tsx` / `edit-job-dialog.tsx`) have a hardcoded delivery channel list, `DELIVERY_OPTIONS = ['local', 'telegram', 'discord']` — the quote0 gateway plugin already supports `deliver=quote0`, but the Studio UI has no way to select it, so a cron job with quote0 delivery can only be created from the command line right now. Fixing it means adding one line, `'quote0'`, to the array in each of those two files — a small, self-contained, verifiable change, and the diff is ready. The plan is to run this integration ourselves for a while first, confirm it's actually solid in daily use, and only then submit a PR to [JPeetz/Hermes-Studio](https://github.com/JPeetz/Hermes-Studio) — no rush to push it upstream yet.

## Documentation index

This README only covers "how to use it." Device interface details, the evidence behind every tested conclusion, and how to add a new card all live here:

| Doc | Contents |
|---|---|
| [`docs/DEVICE-FACTS.md`](docs/DEVICE-FACTS.md) | Tested facts about the official Quote/0 API — slot model, sleep-window behavior, NFC closed-loop verification records; "confirmed" and "unverified" are labeled separately, not guessed |
| [`docs/ADDING-A-CARD.md`](docs/ADDING-A-CARD.md) | Which files to touch to add a new content card, with a checklist |

## Project status

- ✅ M0 real-device contract verification — slot model, sleep window, NFC link semantics, all backed by real test evidence
- ✅ M1 skeleton — `dot.py` client + a minimal card pushing successfully
- ✅ M2 minimal viable NFC loop — a tap triggers an action, new content pushes back to the screen, the project's biggest risk point
- ✅ M3 ported I-Ching / Qimen Dunjia / lot-drawing box (relaid out for the 296×152 landscape screen)
- ✅ M4 Canvas/Text cards in bulk — daily ganzhi, status light, proverb generator, time capsule, trading beacon
- ✅ M5 desktop pet — ASCII art ported from the official claude-desktop-buddy, wired to buddy-bridge's live signal
- ✅ M6 scheduler polish + privacy audit — event-driven push priority queue, so time-sensitive content like focus blocks/oracle follow-ups doesn't get buried by auto-rotation
- ✅ Conversational write channel — status board / oracle follow-up, MCP tool params required so Claude asks follow-up questions when info is incomplete
- ✅ Hermes Agent gateway-layer integration — `hermes-quote0` plugin, cron delivery verified on real hardware
- ✅ Console rebuild — 16 cards grouped by purpose, NFC route table and troubleshooting guide filled in
- ✅ Wallpaper — upload auto-scales/crops + dithers to black & white; default image is real traditional woodblock art (CC BY-SA 4.0, see the "all content cards" table)
- ⬜ Hermes Studio-layer integration — the fix in the Cron delivery-channel dropdown is identified and the diff is ready; plan is to self-verify for a while before submitting a PR
- ⬜ Whether the `shortcuts://` scheme can trigger an iOS Shortcut directly via NFC — untested
- ⬜ Official Quote/0 co_create showcase submission — not submitted yet

## Scope: official capabilities only, no reverse engineering

**This project only uses Quote/0's already-public official REST API — no reverse engineering, no jailbreaking, no privilege escalation.**

- ✅ Uses: the official Text API / Image API push endpoints, the official device status and loop task query endpoints
- ❌ Doesn't: reverse-engineer the device's private protocol, dump or rewrite firmware, bypass Dot cloud authentication, or touch existing GENERAL content items in the Dot App (weather/news etc. — additions only, never modifications)

The device's slot limits, sleep window, and native rotation are all worked with — and around, within official capabilities (e.g. using the `image.key` direct CDN link to check pixels during the sleep window) — never worked around by breaking them open.

## Disclaimer

This project has no affiliation with the MindReset / Dot team. It's a personal extension of the author's own device, for personal use. All interaction goes through the officially published cloud REST API — no firmware exploitation, no authentication bypass, no access to anyone else's device.

## License

[MIT](LICENSE)
