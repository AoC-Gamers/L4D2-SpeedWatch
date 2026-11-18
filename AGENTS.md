# SpeedWatch development

- SourcePawn owns configuration, detector thresholds, episodes, integrations, staff
  alerts and public API. The required C++ extension is the sole observation collector.
- Keep C++ aggregation/serialization SDK-independent in `extension/telemetry` and
  `extension/api`; engine hooks/adapters belong under `extension/hooks`/`engine`.
- Never alter game commands, bit readers, return values, tickbase, packets or
  protective ConVars. Never add automatic sanctions. A suspicion is not guilt.
- Preserve `SpeedWatchSample` and forwards. Public API changes require an
  explicit version/migration. Native diagnostics are separately versioned.
- Use SDK types/signatures first. Document runtime evidence before reading an
  internal field. Do not infer storage layout from sendprop bit count or force
  packing, copy raw structs into SourcePawn, or assume a post hook ran the original.
- Builds: `make deps-smx deps-exts-linux`, then `make build-smx build-api-test
  build-exts-linux test-exts-linux test-ci`. Windows uses x86 MSVC and the matching
  `deps-exts-windows build-exts-windows test-exts-windows` targets.
- Packaging uses existing outputs: `make package-smx package-exts-linux
  release-linux validate-artifact-linux`. Windows substitutes its platform and passes
  `validate-artifact-windows`. Build targets never fetch dependencies.
- Run `make check-ci` and `git diff --check`.
- Keep platform outputs separate. Never commit `.deps`, `.build`, `dist`, private
  reports, game binaries, or test plugins in production packages.
- Record local tests separately from SDK ABI checks, SRCDS acceptance, performance,
  deployment and publication. Local checks cannot certify engine behavior.

- Native API v2 owns monotonic window duration, interval, tick discontinuities and
  retention. SourcePawn owns processing/timescale and game exclusions. No second
  collector or comparison ConVar; missing evidence interrupts, never recovers.
- Keep `ReadNativeObservation` read-only, `EvaluateNativeWindow` the sole cadence
  cursor owner, and status/API output independent of evaluation. Do not charge a
  window twice. Core instance, userid/serial, participant/configuration generations
  and sample ID fence continuity. Use named wire cells; preserve uint64 pairs.
- Modules: state, context, observation, native_client, policy, episodes, notifications,
  public_api, integrations and logging. Update the explicit package manifest when
  moving sources. Replace source hashes with production-body behavior regressions.
- Preserve Demo persistence every 30 confirmed seconds and existing public layouts;
  BanSystem owns incident UUIDs and real SourceTV recording ticks. Never invent them.

- Movement context is an evaluation-local diagnostic snapshot, never policy input.
  Capture only with a usable log sink and samples debug or a due alert, before
  external episode forwards. Preserve native identity and unknown values; server
  ticks are not demo ticks. Drain state/persistence notifications with one FIFO
  cursor and one final clear, allowing append during guarded callbacks.

- Root Makefile is the sole local/CI entrypoint. Scripts are grouped under
  scripts/{deps,build,package,ci,tools}; package-map.json and artifact_contract.py
  live only in scripts/package. Keep paths independent of cwd and .git; preserve
  caller-relative TEST_OUTPUT and reject existing run directories.
- Product tests are in tests/python and tests/native, diagnostics in
  tests/diagnostics. Sonar/coverage tooling stays in tests/tooling and runs only
  via explicit local Make targets, never test-ci or Actions. No analysis upload,
  server setup, project creation or token provisioning is implied by source edits.
- Native filename is l4d2_speedwatch_core.ext.2.l4d2.{so,dll}. Preserve public
  includes/natives. Stage exactly one canonical extension per platform; document
  removal of old names without changing installed servers.
- Channel identity is shared by local tooling and CI: product-channel-platform.
  Both verified ZIPs must finish before publication. Local releases never publish;
  the explicit channel job uses draft/upload/publish with no automatic rollback.
- Preserve SDK locks; no dependency upgrades during directory migration. Native
  compile_commands.json comes from real AMBuild tasks. Coverage uses real counters,
  includes unexecuted product lines and rejects changed sources/reports.
