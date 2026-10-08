PROJ_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

EXT_NAME = duckhop
EXT_CONFIG = $(PROJ_DIR)extension_config.cmake

# DuckHop has no vcpkg dependencies; ignore the toolchain supplied by distribution CI.
VCPKG_TOOLCHAIN_PATH =

# The prerelease CI tools also use the checkout SHA as DUCKDB_VERSION, but DuckDB expects a semantic version there.
ifneq ($(strip $(DUCKDB_VERSION)),)
ifeq ($(DUCKDB_VERSION),$(shell git -C "$(PROJ_DIR)duckdb" rev-parse HEAD))
unexport DUCKDB_VERSION
endif
endif

include extension-ci-tools/makefiles/duckdb_extension.Makefile
