SHELL := bash
.DEFAULT_GOAL := help
# Resolve the one root Makefile before any includes; quoted dirname handles spaces.
ROOT_DIR := $(shell cd "$$(dirname "$(MAKEFILE_LIST)")" && pwd)
PYTHON ?= python3
SM_SCRIPTING ?= .deps/smx/sourcemod-linux/addons/sourcemod/scripting
SPCOMP ?= $(SM_SCRIPTING)/spcomp64
SM_VERSION ?= 1.12
SOURCEMOD_VERSION ?= $(SM_VERSION)
SMX_BUILD_DIR ?= .build/smx
SMX_PACKAGE_DIR ?= .build/package-smx
EXTS_LINUX_DEPS_DIR ?= .deps/exts-linux
EXTS_WINDOWS_DEPS_DIR ?= .deps/exts-windows
LINUX_BUILD_DIR ?= .build/exts-linux
WINDOWS_BUILD_DIR ?= .build/exts-windows
EXTS_PACKAGE_LINUX_DIR ?= .build/package-exts-linux
EXTS_PACKAGE_WINDOWS_DIR ?= .build/package-exts-windows
LINUX_ARTIFACT_DIR ?= dist/linux/artifact
WINDOWS_ARTIFACT_DIR ?= dist/windows/artifact
RELEASE_BASENAME ?= l4d2-speedwatch-local
LINUX_RELEASE_BASENAME ?= $(RELEASE_BASENAME)-linux
WINDOWS_RELEASE_BASENAME ?= $(RELEASE_BASENAME)-windows
PLATFORM ?= linux
RUN = cd "$(ROOT_DIR)" && $(PYTHON)
.PHONY: help deps-smx build-smx build-api-test package-smx deps-exts-linux deps-exts-windows build-exts-linux build-exts-windows package-exts-linux package-exts-windows release-linux release-windows validate-artifact-linux validate-artifact-windows validate-artifact release test test-ci test-exts-linux test-exts-windows test-native-sanitized check-ci setup-msvc clean clean-all clean-linux clean-windows sonar sonar-cppcheck sonar-tooling-test test-coverage test-python-coverage deps-test-coverage coverage-tooling-test
help:
	@$(RUN) -c "print('SpeedWatch: deps-smx; build-smx build-api-test; test-ci; deps/build/package-exts-{linux,windows}; test-exts-{linux,windows}; package-smx; release-{linux,windows}; validate-artifact-{linux,windows}; test TEST_OUTPUT=<new-dir>; check-ci; sonar-cppcheck; sonar; test-coverage TEST_OUTPUT=<new-dir>; clean-{linux,windows}. Build/test never fetch; release never publishes.')"
deps-smx:
	$(RUN) scripts/deps/fetch-sourcemod.py --version "$(SOURCEMOD_VERSION)" --destination "$(SM_SCRIPTING)/../../.."
build-smx:
	$(RUN) scripts/build/build-local.py --root . --spcomp "$(SPCOMP)" --output-root "$(SMX_BUILD_DIR)" --compile-log .build/smx-compile.log
build-api-test:
	$(RUN) scripts/build/build-api-tests.py --spcomp "$(SPCOMP)"
package-smx:
	$(RUN) scripts/package/stage-artifact.py . "$(SMX_BUILD_DIR)" .build/smx-compile.log "$(SMX_PACKAGE_DIR)"
deps-exts-linux:
	$(RUN) scripts/deps/fetch-extension-deps.py --platform linux --destination "$(EXTS_LINUX_DEPS_DIR)"
deps-exts-windows:
	$(RUN) scripts/deps/fetch-extension-deps.py --platform windows --destination "$(EXTS_WINDOWS_DEPS_DIR)"
build-exts-linux:
	$(RUN) scripts/build/build-extension.py --platform linux --deps "$(EXTS_LINUX_DEPS_DIR)" --output "$(LINUX_BUILD_DIR)"
build-exts-windows:
	$(RUN) scripts/build/build-extension.py --platform windows --deps "$(EXTS_WINDOWS_DEPS_DIR)" --output "$(WINDOWS_BUILD_DIR)"
package-exts-linux:
	$(RUN) scripts/package/package-native.py stage --platform linux --extension "$(LINUX_BUILD_DIR)" --output "$(EXTS_PACKAGE_LINUX_DIR)"
package-exts-windows:
	$(RUN) scripts/package/package-native.py stage --platform windows --extension "$(WINDOWS_BUILD_DIR)" --output "$(EXTS_PACKAGE_WINDOWS_DIR)"
release-linux:
	$(RUN) scripts/package/package-native.py release --platform linux --extension "$(EXTS_PACKAGE_LINUX_DIR)" --smx "$(SMX_PACKAGE_DIR)" --output "$(LINUX_ARTIFACT_DIR)" --basename "$(LINUX_RELEASE_BASENAME)"
release-windows:
	$(RUN) scripts/package/package-native.py release --platform windows --extension "$(EXTS_PACKAGE_WINDOWS_DIR)" --smx "$(SMX_PACKAGE_DIR)" --output "$(WINDOWS_ARTIFACT_DIR)" --basename "$(WINDOWS_RELEASE_BASENAME)"
# Aggregate waits for both independent stages even with make -j; no build/download.
release: package-smx package-exts-linux
	$(MAKE) --no-print-directory -f "$(ROOT_DIR)/Makefile" release-linux
validate-artifact-linux:
	$(RUN) scripts/package/package-native.py validate --platform linux --output "$(LINUX_ARTIFACT_DIR)"
validate-artifact-windows:
	$(RUN) scripts/package/package-native.py validate --platform windows --output "$(WINDOWS_ARTIFACT_DIR)"
validate-artifact:
	$(MAKE) --no-print-directory -f "$(ROOT_DIR)/Makefile" validate-artifact-$(PLATFORM)
test-ci:
	$(RUN) -m unittest discover -s tests/python -p 'test_*.py' -v
test-exts-linux:
	$(RUN) tests/runners/run-native-tests.py --platform linux --deps "$(EXTS_LINUX_DEPS_DIR)"
test-exts-windows:
	$(RUN) tests/runners/run-native-tests.py --platform windows --deps "$(EXTS_WINDOWS_DEPS_DIR)"
test-native-sanitized:
	$(RUN) tests/runners/run-native-tests.py --platform linux --sanitize
test:
	$(RUN) tests/runners/test-integration.py --output "$(TEST_OUTPUT)" --caller "$(CURDIR)" --make "$(MAKE)"
check-ci:
	cd "$(ROOT_DIR)" && actionlint .github/workflows/sourcemod-build.yml
setup-msvc:
	$(RUN) scripts/build/setup-msvc.py
clean-linux:
	$(RUN) scripts/tools/clean-platform.py linux
clean-windows:
	$(RUN) scripts/tools/clean-platform.py windows
clean: clean-linux clean-windows
clean-all: clean
sonar-cppcheck:
	@$(RUN) scripts/tools/make_sonar.py cppcheck --compile-commands "$(LINUX_BUILD_DIR)/compile_commands.json"
sonar:
	@$(RUN) scripts/tools/make_sonar.py analyze --compile-commands "$(LINUX_BUILD_DIR)/compile_commands.json"
sonar-tooling-test:
	$(RUN) -m unittest discover -s tests/tooling -p '*sonar*test.py' -v
test-coverage:
	$(RUN) tests/runners/test-coverage.py --output "$(TEST_OUTPUT)" --caller "$(CURDIR)" --compile-commands "$(LINUX_BUILD_DIR)/compile_commands.json"
deps-test-coverage:
	$(RUN) scripts/deps/fetch-test-coverage.py
test-python-coverage:
	$(RUN) tests/runners/test-python-coverage.py --output "$(TEST_OUTPUT)" --caller "$(CURDIR)"
coverage-tooling-test:
	$(RUN) -m unittest discover -s tests/tooling -p '*coverage*test.py' -v
RELEASE_REF ?= $(if $(GITHUB_REF_NAME),$(GITHUB_REF_NAME),local)
RELEASE_PLATFORM ?= linux
.PHONY: release-identity publish-channel
release-identity:
	$(RUN) scripts/ci/release-identity.py --ref "$(RELEASE_REF)" --sha "$(GITHUB_SHA)" --platform "$(RELEASE_PLATFORM)"
publish-channel:
	@test "$(PUBLISH)" = 1 || { echo 'Explicit PUBLISH=1 is required' >&2; exit 2; }
	$(RUN) scripts/ci/publish-channel.py --publish --ref "$(RELEASE_REF)" --sha "$(GITHUB_SHA)" --run-url "$(GITHUB_SERVER_URL)/$(GITHUB_REPOSITORY)/actions/runs/$(GITHUB_RUN_ID)" --attempt "$(GITHUB_RUN_ATTEMPT)"
