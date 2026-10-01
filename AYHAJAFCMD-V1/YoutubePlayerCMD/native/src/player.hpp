#pragma once

#include "renderer.hpp"

#include <string>

enum class Quality {
    Low,
    Normal,
    High,
};

bool parseQuality(const std::string& value, Quality& quality);
int runStreamPlayer(const std::string& streamPath, RenderMode mode, Quality quality);