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
RELEASE_BASENAME ?= l4d2-speedwatch-local
LINUX_RELEASE_BASENAME ?= $(RELEASE_BASENAME)-linux
WINDOWS_RELEASE_BASENAME ?= $(RELEASE_BASENAME)-windows
PLATFORM ?= linux
.DEFAULT_GOAL := help
.PHONY: help deps-smx build-smx package-smx deps-exts-linux deps-exts-windows build-exts-linux build-exts-windows package-exts-linux package-exts-windows test-exts-linux test-exts-windows build-api-test test-ci validate-artifact release release-linux release-windows clean clean-linux clean-windows
help:
	@$(PYTHON) -c "print('SpeedWatch: deps-smx build-smx package-smx; deps-exts-{linux,windows} build-exts-{linux,windows} package-exts-{linux,windows}; test-exts-{linux,windows} test-ci build-api-test; release-{linux,windows} validate-artifact clean-{linux,windows}. Builds never fetch dependencies; package/release use existing binaries.')"
deps-smx:
	$(PYTHON) scripts/fetch-sourcemod.py --version "$(SOURCEMOD_VERSION)"
build-smx:
	$(PYTHON) scripts/build-local.py --root . --spcomp "$(SPCOMP)" --output-root "$(SMX_BUILD_DIR)" --compile-log .build/smx-compile.log
package-smx:
	$(PYTHON) scripts/stage-artifact.py . "$(SMX_BUILD_DIR)" .build/smx-compile.log "$(SMX_PACKAGE_DIR)"
deps-exts-linux:
	$(PYTHON) scripts/fetch-extension-deps.py --platform linux --destination "$(EXTS_LINUX_DEPS_DIR)"
deps-exts-windows:
	$(PYTHON) scripts/fetch-extension-deps.py --platform windows --destination "$(EXTS_WINDOWS_DEPS_DIR)"
build-exts-linux:
	$(PYTHON) scripts/build-extension.py --platform linux --deps "$(EXTS_LINUX_DEPS_DIR)" --output "$(LINUX_BUILD_DIR)"
build-exts-windows:
	$(PYTHON) scripts/build-extension.py --platform windows --deps "$(EXTS_WINDOWS_DEPS_DIR)" --output "$(WINDOWS_BUILD_DIR)"
package-exts-linux:
	$(PYTHON) scripts/package-native.py stage --platform linux --extension "$(LINUX_BUILD_DIR)" --output "$(EXTS_PACKAGE_LINUX_DIR)"
package-exts-windows:
	$(PYTHON) scripts/package-native.py stage --platform windows --extension "$(WINDOWS_BUILD_DIR)" --output "$(EXTS_PACKAGE_WINDOWS_DIR)"
release-linux:
	$(PYTHON) scripts/package-native.py release --platform linux --extension "$(EXTS_PACKAGE_LINUX_DIR)" --smx "$(SMX_PACKAGE_DIR)" --basename "$(LINUX_RELEASE_BASENAME)"
release-windows:
	$(PYTHON) scripts/package-native.py release --platform windows --extension "$(EXTS_PACKAGE_WINDOWS_DIR)" --smx "$(SMX_PACKAGE_DIR)" --basename "$(WINDOWS_RELEASE_BASENAME)"
release: package-smx package-exts-linux release-linux
validate-artifact:
	$(PYTHON) scripts/package-native.py validate --platform "$(PLATFORM)"
build-api-test:
	$(PYTHON) scripts/build-api-tests.py --spcomp "$(SPCOMP)"
test-exts-linux:
	$(PYTHON) scripts/run-native-tests.py --platform linux --deps "$(EXTS_LINUX_DEPS_DIR)"
test-exts-windows:
	$(PYTHON) scripts/run-native-tests.py --platform windows --deps "$(EXTS_WINDOWS_DEPS_DIR)"
test-ci:
	$(PYTHON) -m unittest discover -s tests -v
clean: clean-linux clean-windows
clean-linux:
	$(PYTHON) scripts/clean-platform.py linux
clean-windows:
	$(PYTHON) scripts/clean-platform.py windows
