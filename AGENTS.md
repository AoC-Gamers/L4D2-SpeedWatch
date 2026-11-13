# SpeedWatch development

- SourcePawn owns configuration, detector thresholds, episodes, integrations, staff
  alerts and legacy public API. The optional C++ extension only aggregates evidence.
- Keep C++ aggregation/serialization SDK-independent in `extension/telemetry` and
  `extension/api`; engine hooks/adapters belong under `extension/hooks`/`engine`.
- Never alter game commands, bit readers, return values, tickbase, packets or
  protective ConVars. Never add automatic sanctions. A suspicion is not guilt.
- Preserve legacy `SpeedWatchSample` and forwards. Public API changes require an
  explicit version/migration. Native diagnostics are separately versioned.
- Use SDK types/signatures first. Document runtime evidence before reading an
  internal field. Do not infer storage layout from sendprop bit count or force
  packing, copy raw structs into SourcePawn, or assume a post hook ran the original.
- Builds: `make deps-smx deps-exts-linux`, then `make build-smx build-api-test
  build-exts-linux test-exts-linux test-ci`. Windows uses x86 MSVC and the matching
  `deps-exts-windows build-exts-windows test-exts-windows` targets.
- Packaging uses existing outputs: `make package-smx package-exts-linux
  release-linux validate-artifact`. Windows substitutes its platform and passes
  `PLATFORM=windows`. Build targets never fetch dependencies.
- Run `actionlint .github/workflows/sourcemod-build.yml` and `git diff --check`.
- Keep platform outputs separate. Never commit `.deps`, `.build`, `dist`, private
  reports, game binaries, or test plugins in production packages.
- Record local tests separately from SDK ABI checks, SRCDS acceptance, performance,
  deployment and publication. Local checks cannot certify engine behavior.
