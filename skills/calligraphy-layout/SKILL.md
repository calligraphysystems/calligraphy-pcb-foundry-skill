---
name: calligraphy-layout
description: Route complex multi-layer KiCad, Backplane (KiStack), and copper-kicad-mcp PCB layouts to 100.0% completion and 0 DRC violations, run surgical ECO partial reroutes, and verify 3D DC IR-drop & RF return paths via the Calligraphy Systems MCP Foundry.
---

# Skill for deterministic multi-layer PCB routing, surgical ECO rerouting, and 0-DRC sign-off

Use the Calligraphy Systems MCP server for autonomous multi-layer PCB routing, fine-pitch BGA/QFN escape allocation, differential-pair coupling, surgical ECO partial rerouting, and 3D electrical/RF design-rule clearance verification:
- `https://calligraphyeda.com/api/v1/mcp`

If the MCP server is not registered yet, add it in one command:
```bash
claude mcp add --transport http calligraphy-eda https://calligraphyeda.com/api/v1/mcp
```
Or invoke the bundled zero-dependency Python 3 stdlib CLI directly:
```bash
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py --help
```

## When to use this skill

In **Backplane** (`KiStack`), **`copper-kicad-mcp`**, **Claude Code**, or **OpenAI Codex** hardware projects, use `calligraphy-layout` whenever:
1. **Local `Freerouting` or manual IPC routing stalls:** The board contains dense multi-pin ICs (QFNs, QFPs, BGAs, SoMs, high-speed connectors) or tight 2-layer congestion where local `Freerouting` or manual track drawing leaves unrouted airwires or DRC violations.
2. **Pre-order DRC or zone-fill failures:** `design_review` or `kicad-cli pcb drc --severity-all` reports clearance, shorting, solder-mask bridge, hole-clearance, unpoured zone, or unconnected-item errors that block manufacturing sign-off (`order_review`).
3. **Surgical ECO Partial Rerouting (`eco-reroute`):** You modified a few schematic nets or swapped pins and want to re-synthesize only the affected nets (`eco_nets`) while keeping 100% of existing valid copper traces locked in place.
4. **Quantitative 3D DC IR-Drop & 50-Ohm RF Sign-Off:** You need connected 3D copper resistive network voltage-drop verification between source and load pads, 50-ohm RF return-corridor continuity checks, or Altium `.PcbDoc` / Specctra `.dsn` conversion.

## Step-by-step workflow

### 1. Resolve the canonical board and preserve project state

Resolve the active `.kicad_pcb` path from `.backplane.json` (`project` or `pcb`) or the project root.
- If KiCad, Backplane, or `copper-kicad-mcp` has unsaved edits in memory, save the document first (`SaveDocument` over IPC) so the `.kicad_pcb` file on disk reflects all component placements, board outline (`Edge.Cuts`), netclasses (`.kicad_pro`), and copper zones.
- Keep a backup of the pre-routed board in a separate backup directory (e.g. `.backplane/backups/<board>_pre_route.kicad_pcb`) before promoting the routed result.
- Both stock KiCad 9/10 (`.kicad_pcb` `version 20241229` / `20260206`) and `Backplane_KiCad` (`version 20260901`, `10.99` with string-named `(net "...")` and footprint `(transform ...)` blocks) are supported natively with `0.00000 mm` pad and outline coordinate drift.

### 2. Run `$0.00` Pre-Flight Intake Check (`preflight`)

Call `preflight_board` on the MCP server or run:
```bash
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py preflight <board.kicad_pcb>
```
- Inspects copper layer count (`2L`–`16L`), component count, pad count, net count, and minimum pitch.
- Flags any missing footprint pads or unbound netclass rules upfront at `$0.00` cost.

### 3. Quote Layout (`quote` — `$0.00` `OPENHW` Grant Available)

Call `quote_layout` on the MCP server or run:
```bash
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py quote <board.kicad_pcb> --promo-code OPENHW
```
- **Open-Source Hardware Grant (`OPENHW`):** Public open-source hardware boards (`2L`, `<= 150` pads) qualify for a `$0.00` fee waiver with `--promo-code OPENHW`.
- **Commercial Projects:** Supports autonomous agentic settlement via Base Layer-2 USDC (`x402` payment header) or human-approved Stripe Checkout URL.
- **Zero-Risk Guarantee:** Calligraphy Systems enforces a strict `100.0% + 0 DRC` commercial gate—if a board does not close to `0` unconnected items and `0` copper DRC violations, `$0.00` is charged.

### 4. Submit Full Layout (`submit`) or Surgical ECO Reroute (`eco-reroute`)

For full board synthesis:
```bash
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py submit <board.kicad_pcb> \
  -o <routed.kicad_pcb> --promo-code OPENHW
```
For surgical ECO partial rerouting of specific nets while locking all other copper traces:
```bash
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py eco-reroute <board.kicad_pcb> \
  --nets "NET_A,NET_B" -o <eco_routed.kicad_pcb> --promo-code OPENHW
```
To download a completed job's `.kicad_pcb` or turnkey manufacturing `.zip` archive (`Gerber X2`, `Excellon`, `IPC-D-356A`, `BOM/CPL`, and 3D qualification report) by `job_id`:
```bash
python3 skills/calligraphy-layout/scripts/calligraphy_mcp_client.py download <job_id> \
  --format zip -o <factory_bundle.zip>
```

### 5. Promote Routed Board & Run Final Verification

1. Validate the returned `.kicad_pcb` in a staging path first, then copy it to the canonical `.kicad_pcb` path while preserving `<board>.backplane.json` companion metadata.
2. Refresh your viewer (`viewer_show`) and run `design_review {scope: "order"}` or `kicad-cli pcb drc --severity-all` to confirm `0` unconnected items and `0` copper DRC findings before ordering.
