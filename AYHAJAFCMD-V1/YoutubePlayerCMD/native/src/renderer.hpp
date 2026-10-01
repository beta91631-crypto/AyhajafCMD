#pragma once

#include <cstddef>
#include <string>

enum class RenderMode {
    Ascii,
    HalfBlock,
    Color,
    Pixel,
};

std::string renderFrame(const unsigned char* pixels, int width, int height,
                        int channels, RenderMode mode);