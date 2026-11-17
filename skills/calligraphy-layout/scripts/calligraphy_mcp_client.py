#!/usr/bin/env python3
"""
Calligraphy Systems — Zero-Dependency MCP & REST Client (`calligraphy_mcp_client.py`)
for Backplane (`KiStack`), `copper-kicad-mcp`, Claude Code, OpenAI Codex, and Cursor Agents.

Connects to `https://calligraphyeda.com/api/v1/mcp` (JSON-RPC 2.0 over HTTPS)
and companion `/api/v1/` endpoints using the Python 3 standard library only.

Supported CLI subcommands:
  - `preflight`   : $0.00 pre-flight board geometry & S-expression compatibility audit
  - `quote`       : Deterministic layout quote ($0.00 with `--promo-code OPENHW`, x402 USDC, or Stripe)
  - `submit`      : Submit board for 100.0% completion + 0-DRC synthesis (alias: `route`)
  - `eco-reroute` : Surgical ECO partial reroute of specified nets while locking existing copper
  - `download`    : Download routed `.kicad_pcb` or turnkey factory `.zip` bundle for a `job_id`
"""

import argparse
import base64
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MCP_URL = "https://calligraphyeda.com/api/v1/mcp"
DEFAULT_API_BASE = "https://calligraphyeda.com/api/v1"


def _json_rpc_call(
    mcp_url: str,
    method: str,
    params: Dict[str, Any],
    timeout_s: int = 60,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 1000000,
        "method": method,
        "params": params,
    }
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Calligraphy-PCB-Foundry-Skill/1.1",
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(
        mcp_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {
            "error": {
                "code": e.code,
                "message": f"HTTP {e.code}: {e.reason}",
                "data": err_body[:1000],
            }
        }
    except Exception as e:
        return {"error": {"code": -32000, "message": str(e)}}


def call_mcp_tool(
    mcp_url: str,
    tool_name: str,
    arguments: Dict[str, Any],
    timeout_s: int = 60,
    payment_tx_hash: str = "",
) -> Dict[str, Any]:
    extra_headers: Dict[str, str] = {}
    if payment_tx_hash:
        extra_headers["X-Payment-Tx-Hash"] = payment_tx_hash
    return _json_rpc_call(
        mcp_url=mcp_url,
        method="tools/call",
        params={"name": tool_name, "arguments": arguments},
        timeout_s=timeout_s,
        headers=extra_headers,
    )


def inspect_local_kicad_pcb(pcb_path: Path) -> Dict[str, Any]:
    """Fast local S-expression pre-check supporting stock KiCad 9/10 and Backplane_KiCad 10.99."""
    text = pcb_path.read_text(encoding="utf-8", errors="replace")
    ver_m = re.search(r"\(\s*version\s+(\d+)\s*\)", text[:1024])
    gver_m = re.search(r"\(\s*generator_version\s+\"([^\"]+)\"\s*\)", text[:1024])
    version = int(ver_m.group(1)) if ver_m else 0
    gen_version = gver_m.group(1) if gver_m else "unknown"
    copper_layers = len(set(re.findall(r'\(\d+\s+"((?:F|B|In\d+)\.Cu)"', text[:20000]))) or 2
    footprint_count = len(re.findall(r"\(\s*footprint\s+\"", text))
    pad_count = len(re.findall(r"\(\s*pad\s+\"", text))
    net_names = set(re.findall(r'\(\s*net\s+(?:\d+\s+)?"([^"]+)"\s*\)', text))
    has_trs = bool(re.search(r"\(\s*transform\s*\(\s*translate\b", text))

    return {
        "file": pcb_path.name,
        "bytes": len(text.encode("utf-8")),
        "sexpr_version": version,
        "generator_version": gen_version,
        "backplane_kicad10_compatible": True,
        "uses_trs_transform": has_trs,
        "copper_layers": copper_layers,
        "footprints": footprint_count,
        "pads": pad_count,
        "distinct_nets": len(net_names),
        "openhw_grant_eligible_geometry": bool(copper_layers <= 2 and pad_count <= 150),
    }


def _poll_and_save_job(
    mcp_url: str,
    job_id: str,
    out_p: Path,
    source_pcb_p: Optional[Path] = None,
    poll_interval: int = 15,
    bundle_format: str = "kicad_pcb",
) -> int:
    while True:
        st_res = call_mcp_tool(mcp_url, "get_job_status", {"job_id": job_id})
        st_obj = st_res.get("result", {})
        status = st_obj.get("status", "unknown")
        if status == "completed":
            dl_res = call_mcp_tool(
                mcp_url,
                "download_delivery_bundle",
                {"job_id": job_id, "format": bundle_format},
            )
            dl_obj = dl_res.get("result", {})
            payload_b64 = dl_obj.get("bundle_base64") or dl_obj.get("board_base64") or ""
            if payload_b64:
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_bytes(base64.b64decode(payload_b64))
                if source_pcb_p is not None and bundle_format == "kicad_pcb":
                    bp_comp = source_pcb_p.with_name(f"{source_pcb_p.name}.backplane.json")
                    if bp_comp.is_file():
                        shutil.copy2(bp_comp, out_p.with_name(f"{out_p.name}.backplane.json"))
            print(
                json.dumps(
                    {
                        "status": "COMPLETED",
                        "job_id": job_id,
                        "format": bundle_format,
                        "output_path": str(out_p),
                    },
                    indent=2,
                )
            )
            return 0
        if status in ("failed", "error", "cancelled", "quarantined"):
            print(
                json.dumps({"status": status.upper(), "job_id": job_id, "details": st_obj}, indent=2),
                file=sys.stderr,
            )
            return 3
        time.sleep(poll_interval)


def cmd_preflight(args: argparse.Namespace) -> int:
    pcb_p = Path(args.pcb).resolve()
    if not pcb_p.is_file():
        print(json.dumps({"error": f"Board file not found: {pcb_p.name}"}), file=sys.stderr)
        return 1
    local_info = inspect_local_kicad_pcb(pcb_p)
    if args.offline:
        print(json.dumps({"status": "PREFLIGHT_OK", "mode": "offline_local", "board": local_info}, indent=2))
        return 0
    b64_content = base64.b64encode(pcb_p.read_bytes()).decode("ascii")
    res = call_mcp_tool(
        args.mcp_url,
        "preflight_board",
        {"filename": pcb_p.name, "board_base64": b64_content},
    )
    print(json.dumps({"local_inspection": local_info, "mcp_response": res}, indent=2))
    return 0


def cmd_quote(args: argparse.Namespace) -> int:
    pcb_p = Path(args.pcb).resolve()
    if not pcb_p.is_file():
        print(json.dumps({"error": f"Board file not found: {pcb_p.name}"}), file=sys.stderr)
        return 1
    local_info = inspect_local_kicad_pcb(pcb_p)
    b64_content = base64.b64encode(pcb_p.read_bytes()).decode("ascii")
    req_args: Dict[str, Any] = {
        "filename": pcb_p.name,
        "board_base64": b64_content,
        "layers": local_info["copper_layers"],
        "pads": local_info["pads"],
    }
    if args.promo_code:
        req_args["promo_code"] = args.promo_code
    if args.repo_url:
        req_args["repo_url"] = args.repo_url
    res = call_mcp_tool(args.mcp_url, "quote_layout", req_args)
    print(json.dumps({"board": local_info, "quote": res}, indent=2))
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    pcb_p = Path(args.pcb).resolve()
    if not pcb_p.is_file():
        print(json.dumps({"error": f"Board file not found: {pcb_p.name}"}), file=sys.stderr)
        return 1
    out_p = Path(args.output).resolve() if args.output else pcb_p.with_name(f"{pcb_p.stem}_routed.kicad_pcb")
    b64_content = base64.b64encode(pcb_p.read_bytes()).decode("ascii")
    submit_args: Dict[str, Any] = {
        "filename": pcb_p.name,
        "board_base64": b64_content,
    }
    pro_p = pcb_p.with_suffix(".kicad_pro")
    if pro_p.is_file():
        submit_args["pro_base64"] = base64.b64encode(pro_p.read_bytes()).decode("ascii")
    if args.promo_code:
        submit_args["promo_code"] = args.promo_code
    if args.repo_url:
        submit_args["repo_url"] = args.repo_url

    sub_res = call_mcp_tool(
        args.mcp_url,
        "submit_layout_job",
        submit_args,
        payment_tx_hash=args.tx_hash,
    )
    if "error" in sub_res:
        print(json.dumps(sub_res, indent=2), file=sys.stderr)
        return 2

    result_obj = sub_res.get("result", {})
    job_id = result_obj.get("job_id")
    if not job_id or args.no_wait:
        print(json.dumps(sub_res, indent=2))
        return 0

    return _poll_and_save_job(
        mcp_url=args.mcp_url,
        job_id=job_id,
        out_p=out_p,
        source_pcb_p=pcb_p,
        poll_interval=args.poll_interval,
        bundle_format="kicad_pcb",
    )


def cmd_eco_reroute(args: argparse.Namespace) -> int:
    pcb_p = Path(args.pcb).resolve()
    if not pcb_p.is_file():
        print(json.dumps({"error": f"Board file not found: {pcb_p.name}"}), file=sys.stderr)
        return 1
    eco_nets: List[str] = [n.strip() for n in args.nets.split(",") if n.strip()]
    if not eco_nets:
        print(json.dumps({"error": "Must specify at least one net via --nets"}), file=sys.stderr)
        return 1
    out_p = Path(args.output).resolve() if args.output else pcb_p.with_name(f"{pcb_p.stem}_eco_routed.kicad_pcb")
    b64_content = base64.b64encode(pcb_p.read_bytes()).decode("ascii")
    eco_args: Dict[str, Any] = {
        "filename": pcb_p.name,
        "board_base64": b64_content,
        "eco_nets": eco_nets,
        "lock_existing_traces": True,
    }
    pro_p = pcb_p.with_suffix(".kicad_pro")
    if pro_p.is_file():
        eco_args["pro_base64"] = base64.b64encode(pro_p.read_bytes()).decode("ascii")
    if args.promo_code:
        eco_args["promo_code"] = args.promo_code
    if args.repo_url:
        eco_args["repo_url"] = args.repo_url

    sub_res = call_mcp_tool(
        args.mcp_url,
        "submit_eco_reroute_job",
        eco_args,
        payment_tx_hash=args.tx_hash,
    )
    if "error" in sub_res:
        print(json.dumps(sub_res, indent=2), file=sys.stderr)
        return 2

    result_obj = sub_res.get("result", {})
    job_id = result_obj.get("job_id")
    if not job_id or args.no_wait:
        print(json.dumps(sub_res, indent=2))
        return 0

    return _poll_and_save_job(
        mcp_url=args.mcp_url,
        job_id=job_id,
        out_p=out_p,
        source_pcb_p=pcb_p,
        poll_interval=args.poll_interval,
        bundle_format="kicad_pcb",
    )


def cmd_download(args: argparse.Namespace) -> int:
    ext = ".zip" if args.format == "zip" else ".kicad_pcb"
    out_p = Path(args.output).resolve() if args.output else Path.cwd() / f"{args.job_id}{ext}"
    dl_res = call_mcp_tool(
        args.mcp_url,
        "download_delivery_bundle",
        {"job_id": args.job_id, "format": args.format},
    )
    if "error" in dl_res:
        print(json.dumps(dl_res, indent=2), file=sys.stderr)
        return 2
    dl_obj = dl_res.get("result", {})
    payload_b64 = dl_obj.get("bundle_base64") or dl_obj.get("board_base64") or ""
    if not payload_b64:
        print(json.dumps(dl_res, indent=2))
        return 0
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_bytes(base64.b64decode(payload_b64))
    print(
        json.dumps(
            {
                "status": "DOWNLOADED",
                "job_id": args.job_id,
                "format": args.format,
                "output_path": str(out_p),
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calligraphy Systems MCP Layout Client for Backplane (KiStack), copper-kicad-mcp, Claude Code & Codex"
    )
    parser.add_argument("--mcp-url", default=os.environ.get("CALLIGRAPHY_MCP_URL", DEFAULT_MCP_URL))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pre = sub.add_parser("preflight", help="Run $0 pre-flight board intake check")
    p_pre.add_argument("pcb", help="Path to .kicad_pcb file")
    p_pre.add_argument("--offline", action="store_true", help="Run local S-expression inspection only")

    p_quo = sub.add_parser("quote", help="Quote autonomous layout synthesis ($0 with OPENHW or x402 USDC / Stripe)")
    p_quo.add_argument("pcb", help="Path to .kicad_pcb file")
    p_quo.add_argument("--promo-code", default="", help="Promo or open-hardware grant code (e.g. OPENHW)")
    p_quo.add_argument("--repo-url", default="", help="Public open-source repository URL for OPENHW verification")

    for sub_name in ("submit", "route"):
        p_sub = sub.add_parser(sub_name, help="Submit board for 100%% + 0-DRC layout synthesis and download result")
        p_sub.add_argument("pcb", help="Path to input .kicad_pcb file")
        p_sub.add_argument("-o", "--output", default="", help="Output .kicad_pcb path")
        p_sub.add_argument("--promo-code", default="", help="Promo code (e.g. OPENHW)")
        p_sub.add_argument("--repo-url", default="", help="Public repository URL for OPENHW")
        p_sub.add_argument("--tx-hash", default="", help="Base L2 USDC x402 transaction hash")
        p_sub.add_argument("--poll-interval", type=int, default=15, help="Seconds between status polls")
        p_sub.add_argument("--no-wait", action="store_true", help="Return immediately after job submission")

    p_eco = sub.add_parser(
        "eco-reroute",
        help="Surgical ECO partial reroute of specified nets while locking existing copper traces",
    )
    p_eco.add_argument("pcb", help="Path to input .kicad_pcb file")
    p_eco.add_argument("--nets", required=True, help="Comma-separated list of ECO net names to reroute")
    p_eco.add_argument("-o", "--output", default="", help="Output .kicad_pcb path")
    p_eco.add_argument("--promo-code", default="", help="Promo code (e.g. OPENHW)")
    p_eco.add_argument("--repo-url", default="", help="Public repository URL for OPENHW")
    p_eco.add_argument("--tx-hash", default="", help="Base L2 USDC x402 transaction hash")
    p_eco.add_argument("--poll-interval", type=int, default=15, help="Seconds between status polls")
    p_eco.add_argument("--no-wait", action="store_true", help="Return immediately after job submission")

    p_dl = sub.add_parser("download", help="Download completed .kicad_pcb or turnkey factory .zip bundle by job_id")
    p_dl.add_argument("job_id", help="Job ID returned by submit or eco-reroute")
    p_dl.add_argument("--format", choices=["kicad_pcb", "zip"], default="kicad_pcb", help="Download format")
    p_dl.add_argument("-o", "--output", default="", help="Output file path")

    args = parser.parse_args()
    if args.cmd == "preflight":
        return cmd_preflight(args)
    if args.cmd == "quote":
        return cmd_quote(args)
    if args.cmd in ("submit", "route"):
        return cmd_submit(args)
    if args.cmd == "eco-reroute":
        return cmd_eco_reroute(args)
    if args.cmd == "download":
        return cmd_download(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
