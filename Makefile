PYTHON ?= python3
SM_SCRIPTING ?= deps/sourcemod-linux/addons/sourcemod/scripting
SPCOMP ?= $(SM_SCRIPTING)/spcomp64
SM_VERSION ?= 1.12
SOURCEMOD_VERSION ?= $(SM_VERSION)
SMX_BUILD_DIR ?= .build/smx
SMX_PACKAGE_DIR ?= .build/package-smx
RELEASE_BASENAME ?= l4d2-speedwatch-local

.PHONY: deps-smx build-smx package-smx validate-artifact release build-api-test test-ci clean

deps-smx:
	$(PYTHON) scripts/fetch-sourcemod.py --version "$(SOURCEMOD_VERSION)"

# Lista explícita de producción desde plugin-package-map.json; nunca compila el test.
build-smx:
	$(PYTHON) scripts/build-local.py --root . --spcomp "$(SPCOMP)" --output-root "$(SMX_BUILD_DIR)" --compile-log deps/build-smx-compile.log

package-smx:
	$(PYTHON) scripts/stage-artifact.py . "$(SMX_BUILD_DIR)" deps/build-smx-compile.log "$(SMX_PACKAGE_DIR)"

validate-artifact:
	bash scripts/ci-validate-artifact.sh

release: package-smx
	$(PYTHON) scripts/stage-artifact.py . "$(SMX_PACKAGE_DIR)" deps/build-smx-compile.log
	$(MAKE) validate-artifact
	$(PYTHON) scripts/package-release.py --root . --basename "$(RELEASE_BASENAME)"

# Diagnóstico manual, excluido del workflow y del paquete de producción.
build-api-test:
	mkdir -p .build/tests
	"$(SPCOMP)" addons/sourcemod/scripting/l4d2_speedwatch_test.sp -iaddons/sourcemod/scripting/include -i"$(SM_SCRIPTING)/include" -o.build/tests/l4d2_speedwatch_test.smx -E
	"$(SPCOMP)" addons/sourcemod/scripting/l4d2_speedwatch_test.sp -iaddons/sourcemod/scripting/include -i"$(SM_SCRIPTING)/include" -o.build/tests/l4d2_speedwatch_test_required.smx SPEEDWATCH_TEST_REQUIRED=1 -E

test-ci:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['.build', 'dist']]"
