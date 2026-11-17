# `calligraphy-pcb-foundry-skill` — Autonomous 0-DRC PCB Layout & 3D Sign-Off Skill for Backplane (`KiStack`), `copper-kicad-mcp`, Claude Code & Codex

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP: HTTP JSON-RPC 2.0](https://img.shields.io/badge/MCP-calligraphyeda.com-emerald)](https://calligraphyeda.com/api/v1/mcp)
[![Open-Source Hardware Grant: $0 OPENHW](https://img.shields.io/badge/Open_Hardware_Grant-$0_OPENHW-brightgreen)](https://calligraphyeda.com)

Universal MIT-licensed drop-in skill and zero-dependency Python 3 MCP client connecting **Backplane** (`KiStack`), **`copper-kicad-mcp`**, **Claude Code**, **OpenAI Codex**, and **Cursor** hardware agents to the **Calligraphy Systems Physical Synthesis Foundry** (`https://calligraphyeda.com/api/v1/mcp`).

> ### `$0.00` Free Pre-Flight DRC/Zone-Fill Audit + `$0.00` `OPENHW` Open-Source Hardware Grant
> - **Always-Free `$0.00` Pre-Flight Intake (`preflight_board`):** Instant layer/pad/netclass geometry inspection and zone-fill readiness check at zero cost.
> - **`$0.00` `OPENHW` Open-Source Hardware Grant:** Public open-source hardware repositories (`2L`, `<= 150` pads) qualify for **100% free autonomous routing and turnkey Gerber/IPC-D-356A sign-off** using promo code **`OPENHW`**.
> - **Fail-Closed Commercial Guarantee (`100.0% + 0 DRC ONLY`):** You are **never charged** unless the foundry closes your board to **100.0% geometric completion (`0` unconnected items) and `0` native KiCad copper DRC violations** after a fresh copper zone refill.

---

## 1-Command Installation

### Option A: Claude Code (HTTP MCP Server + Skill)

```bash
# 1. Register the remote HTTP MCP server (zero local dependencies)
claude mcp add --transport http calligraphy-eda https://calligraphyeda.com/api/v1/mcp

# 2. Install the drop-in layout & sign-off skill
npx skills add calligraphysystems/calligraphy-pcb-foundry-skill
```

### Option B: Backplane (`KiStack` Skill Integration)

```bash
npx skills add calligraphysystems/calligraphy-pcb-foundry-skill
```

Or copy `skills/calligraphy-layout/` directly into your project's `.claude/skills/calligraphy-layout/` or local `kistack/skills/` directory. Natively supports both stock KiCad 9/10 (`.kicad_pcb` `version 20241229` / `20260206`) and `Backplane_KiCad` (`version 20260901`, `10.99` with string-named `(net "...")` tokens and footprint TRS `(transform ...)` blocks) with `0.00000 mm` pad and outline coordinate drift.

### Option C: `copper-kicad-mcp` Companion Escalation Workflow

[`copper-kicad-mcp`](https://github.com/claynicholson/copper-kicad-mcp) excels at schematic entry, LCSC part selection, footprint placement, and local `Freerouting` passes. Register `calligraphy-eda` alongside `copper` as your **high-density routing & physics qualification escalation engine**:

```bash
claude mcp add --transport http calligraphy-eda https://calligraphyeda.com/api/v1/mcp
```

**When your agent automatically escalates from `copper-kicad-mcp` to `calligraphy-eda`:**
1. **Local `Freerouting` Stalls on Dense Boards:** Whenever local `Freerouting` stalls or leaves unrouted airwires / DRC shorts on tight 2-layer boards, fine-pitch QFNs (`<= 0.50 mm`), high-pin-count QFPs, or multi-layer BGAs (`2L`–`16L`).
2. **Legacy Altium `.PcbDoc` & Specctra `.dsn` Imports:** Directly ingest binary Altium Designer `.PcbDoc` archives or `.dsn` files without manual re-capture.
3. **Quantitative 3D DC IR-Drop & 50-Ohm RF Return-Path Sign-Off:** Solve the connected 3D copper resistive network across outer (`F.Cu`/`B.Cu`) and inner (`In1.Cu`/`In2.Cu`) layers plus plated through-hole vias between explicit source and load pads, and verify 50-ohm RF reference-plane continuity and stitching-via spacing.
4. **Surgical ECO Partial Rerouting (`eco-reroute`):** Rip up and re-synthesize only a specified list of modified ECO nets while preserving 100% of existing locked copper traces on your board.

### Option D: OpenAI Codex / Cursor / Windsurf (`mcp.json`)

Add `calligraphy-eda` to `.cursor/mcp.json` or `~/.codex/config.json`:

```json
{
  "mcpServers": {
    "calligraphy-eda": {
      "url": "https://calligraphyeda.com/api/v1/mcp"
    }
  }
}
```

---

## Zero-Dependency Python 3 CLI (`calligraphy_mcp_client.py`)

For headless CI pipelines, local shell scripts, or agents running without an HTTP MCP transport, `skills/calligraphy-layout/scripts/calligraphy_mcp_client.py` uses **only the Python 3 standard library** (`urllib.request`, `json`, `base64`):

```bash
# 1. $0 Free Pre-Flight Board Audit (layer count, pad count, net count, Backplane 10.99 compatibility)
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py preflight path/to/board.kicad_pcb

# 2. Instant Deterministic Quote ($0 with --promo-code OPENHW, or Base L2 x402 USDC / Stripe)
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py quote path/to/board.kicad_pcb --promo-code OPENHW

# 3. Submit Board for 100.0% Completion + 0-DRC Physical Synthesis
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py submit path/to/board.kicad_pcb \
  -o path/to/board_routed.kicad_pcb --promo-code OPENHW

# 4. Surgical ECO Partial Reroute (lock existing copper, reroute only specified ECO nets)
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py eco-reroute path/to/board.kicad_pcb \
  --nets "SPI_CLK,SPI_MOSI,SPI_MISO" -o path/to/board_eco.kicad_pcb --promo-code OPENHW

# 5. Download Verified .kicad_pcb or Turnkey Factory ZIP Bundle (Gerber X2, Excellon, IPC-D-356A, 3D Sign-Off)
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py download <job_id> \
  --format zip -o path/to/factory_bundle.zip
```

---

## Engineering Capabilities

- **High-Density BGA Escape Allocation & Fine-Pitch QFN Fanout** (`<= 0.40 mm` pitch, `2L`–`16L` stackups)
- **Global Multi-Layer Congestion Balancing & Clean `45°` Octilinear Copper Routing**
- **Impedance-Controlled Differential Pair Coupling & Phase-Matched Multi-Layer Via Tuning**
- **3D Return-Path Continuity, Loop-Inductance Control & Resistive DC Drop Verification**
- **Design-Rule Clearance Verification** (`100.0%` routed, `0` native KiCad copper DRC violations after fresh zone refill, `0.00000 mm` coordinate drift)
- **Full `Backplane_KiCad` (`KiCad 10` / `10.99`) & `copper-kicad-mcp` Compatibility**

---

## License

MIT License — Copyright (c) 2026 Calligraphy Systems LLC. See [LICENSE](LICENSE).
