#define DUCKDB_EXTENSION_MAIN

#include "duckhop_extension.hpp"
#include "duckdb/main/extension/extension_loader.hpp"

namespace duckdb {

void DuckhopExtension::Load(ExtensionLoader &) {
	// The bootstrap registers no SQL functions or storage behavior.
}

std::string DuckhopExtension::Name() {
	return "duckhop";
}

std::string DuckhopExtension::Version() const {
#ifdef EXT_VERSION_DUCKHOP
	return EXT_VERSION_DUCKHOP;
#else
	return "";
#endif
}

} // namespace duckdb

extern "C" {

DUCKDB_CPP_EXTENSION_ENTRY(duckhop, loader) {
	duckdb::DuckhopExtension extension;
	extension.Load(loader);
}
}
