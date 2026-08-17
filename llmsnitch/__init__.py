"""llmsnitch — local-only tracing and cost/health auditing for AI coding agents.

Own reimplementation of the ideas in luoyuctl/agenttrace (session health gates),
Siddhant-K-code/agent-trace (hook-based tool-call capture), and tensorstax/agenttrace
(cost telemetry) — all MIT, none vendored. Zero network code by design: grep the
package, there is no urllib/socket/http import anywhere.
"""

__version__ = "0.1.0"
