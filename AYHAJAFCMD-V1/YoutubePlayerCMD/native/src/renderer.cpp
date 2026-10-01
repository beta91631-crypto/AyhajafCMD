#include "renderer.hpp"

#include <stdexcept>

namespace {
constexpr char kRamp[] = "@%#*+=-:. ";
constexpr char kBlock[] = "\xe2\x96\x80";

void appendNumber(std::string& output, unsigned int value) {
    char digits[3];
    int count = 0;
    do {
        digits[count++] = static_cast<char>('0' + value % 10);
        value /= 10;
    } while (value != 0);
    while (count > 0) output.push_back(digits[--count]);
}

unsigned int luminance(const unsigned char* pixel, int channels) {
    if (channels == 1) return pixel[0];
    return (299U * pixel[0] + 587U * pixel[1] + 114U * pixel[2]) / 1000U;
}

void appendColor(std::string& output, const char* prefix,
                 unsigned int red, unsigned int green, unsigned int blue) {
    output.append(prefix);
    appendNumber(output, red);
    output.push_back(';');
    appendNumber(output, green);
    output.push_back(';');
    appendNumber(output, blue);
    output.push_back('m');
}
}

std::string renderFrame(const unsigned char* pixels, int width, int height,
                        int channels, RenderMode mode) {
    if (pixels == nullptr || width < 1 || height < 1 ||
        (channels != 1 && channels != 3)) {
        throw std::invalid_argument("Invalid frame dimensions or pixel format");
    }
    if ((mode == RenderMode::Color || mode == RenderMode::Pixel) && channels != 3) {
        throw std::invalid_argument("Color mode requires RGB frames");
    }

    std::string output;
    output.reserve(static_cast<size_t>(width) * static_cast<size_t>(height) *
                   (mode == RenderMode::Ascii ? 1U : 32U));
    if (mode == RenderMode::Ascii) {
        for (int row = 0; row < height; ++row) {
            for (int column = 0; column < width; ++column) {
                const auto offset = (static_cast<size_t>(row) * width + column) * channels;
                output.push_back(kRamp[luminance(pixels + offset, channels) * 9U / 255U]);
            }
            if (row + 1 < height) output.push_back('\n');
        }
        return output;
    }

    if (mode == RenderMode::Pixel) {
        for (int row = 0; row < height; ++row) {
            for (int column = 0; column < width; ++column) {
                const auto offset = (static_cast<size_t>(row) * width + column) * 3;
                appendColor(output, "\x1b[48;2;", pixels[offset],
                            pixels[offset + 1], pixels[offset + 2]);
                output.push_back(' ');
            }
            output.append("\x1b[0m");
            if (row + 1 < height) output.push_back('\n');
        }
        return output;
    }

    for (int row = 0; row < height; row += 2) {
        for (int column = 0; column < width; ++column) {
            const auto topOffset = (static_cast<size_t>(row) * width + column) * channels;
            const auto* top = pixels + topOffset;
            const bool hasBottom = row + 1 < height;
            const auto bottomOffset = (static_cast<size_t>(row + 1) * width + column) * channels;
            const auto* bottom = hasBottom ? pixels + bottomOffset : nullptr;
            unsigned int topR, topG, topB, bottomR, bottomG, bottomB;
            if (mode == RenderMode::Color) {
                topR = top[0]; topG = top[1]; topB = top[2];
                bottomR = hasBottom ? bottom[0] : 0;
                bottomG = hasBottom ? bottom[1] : 0;
                bottomB = hasBottom ? bottom[2] : 0;
            } else {
                topR = topG = topB = luminance(top, channels);
                bottomR = bottomG = bottomB = hasBottom ? luminance(bottom, channels) : 0;
            }
            appendColor(output, "\x1b[38;2;", topR, topG, topB);
            appendColor(output, "\x1b[48;2;", bottomR, bottomG, bottomB);
            output.append(kBlock);
        }
        output.append("\x1b[0m");
        if (row + 2 < height) output.push_back('\n');
    }
    return output;
}