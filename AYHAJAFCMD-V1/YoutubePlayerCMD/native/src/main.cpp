#include "console.hpp"
#include "player.hpp"
#include "renderer.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr double kTargetFps = 30.0;

bool parsePositiveInt(const char* text, int& result) {
    char* end = nullptr;
    long value = std::strtol(text, &end, 10);
    if (end == text || *end != '\0' || value < 1 || value > 10000) return false;
    result = static_cast<int>(value);
    return true;
}

bool parseFps(const char* text, double& result) {
    char* end = nullptr;
    result = std::strtod(text, &end);
    return end != text && *end == '\0' && std::isfinite(result) && result > 0.0 && result <= 60.0;
}

bool parseMode(const std::string& text, RenderMode& mode) {
    if (text == "ascii") mode = RenderMode::Ascii;
    else if (text == "halfblock" || text == "half-block") mode = RenderMode::HalfBlock;
    else if (text == "color") mode = RenderMode::Color;
    else if (text == "pixel") mode = RenderMode::Pixel;
    else return false;
    return true;
}

void printUsage() {
    std::cerr << "Usage:\n"
              << "  renderer.exe --info\n"
              << "  renderer.exe --selftest [ascii|halfblock|color|pixel]\n"
              << "  renderer.exe --raw WIDTH HEIGHT FPS [ascii|halfblock|color|pixel]\n"
              << "  renderer.exe --stream stream.json [--mode ascii|halfblock|color|pixel] [--quality low|normal|high]\n";
}

std::vector<unsigned char> makeTestFrame(int width, int height, int phase, RenderMode mode) {
    const int channels = mode == RenderMode::Color || mode == RenderMode::Pixel ? 3 : 1;
    std::vector<unsigned char> frame(static_cast<size_t>(width) * height * channels);
    for (int row = 0; row < height; ++row) {
        for (int column = 0; column < width; ++column) {
            const auto offset = (static_cast<size_t>(row) * width + column) * channels;
            const unsigned char horizontal = static_cast<unsigned char>((column * 255 / std::max(1, width - 1) + phase) % 256);
            const unsigned char vertical = static_cast<unsigned char>(row * 255 / std::max(1, height - 1));
            if (channels == 1) {
                frame[offset] = static_cast<unsigned char>((horizontal + vertical) / 2);
            } else {
                frame[offset] = horizontal;
                frame[offset + 1] = vertical;
                frame[offset + 2] = static_cast<unsigned char>(255 - horizontal);
            }
        }
    }
    return frame;
}

int runSelftest(RenderMode mode) {
    Console console;
    const auto terminal = console.size();
    const int width = std::max(1, std::min(terminal.columns, 120));
    const int height = std::max(1, std::min((terminal.rows - 2) *
        (mode == RenderMode::Ascii ? 1 : 2), 80));
    const int channels = mode == RenderMode::Color || mode == RenderMode::Pixel ? 3 : 1;
    const auto frameDuration = std::chrono::duration<double>(1.0 / kTargetFps);
    auto nextFrame = std::chrono::steady_clock::now();
    int phase = 0;
    int frames = 0;
    auto fpsStart = nextFrame;
    double measuredFps = 0.0;

    while (console.pollKey() != Key::Quit && !interruptionRequested()) {
        const auto currentSize = console.size();
        if (currentSize.columns != terminal.columns || currentSize.rows != terminal.rows) {
            console.clear();
        }
        auto frame = makeTestFrame(width, height, phase++, mode);
        std::string rendered = renderFrame(frame.data(), width, height, channels, mode);
        console.write("\x1b[H" + rendered + "\x1b[K\n");
        ++frames;
        const auto now = std::chrono::steady_clock::now();
        if (now - fpsStart >= std::chrono::seconds(1)) {
            measuredFps = frames / std::chrono::duration<double>(now - fpsStart).count();
            frames = 0;
            fpsStart = now;
        }
        console.write("\x1b[" + std::to_string(height + 2) + ";1H"
                      "Selftest 30 FPS  Measured " + std::to_string(static_cast<int>(measuredFps)) +
                      " FPS  Q quits\x1b[K");
        nextFrame += std::chrono::duration_cast<std::chrono::steady_clock::duration>(frameDuration);
        std::this_thread::sleep_until(nextFrame);
        if (std::chrono::steady_clock::now() > nextFrame + std::chrono::milliseconds(100)) {
            nextFrame = std::chrono::steady_clock::now();
        }
    }
    return 0;
}

int runRaw(int width, int height, double fps, RenderMode mode) {
    const int channels = mode == RenderMode::Color || mode == RenderMode::Pixel ? 3 : 1;
    const auto frameBytes = static_cast<size_t>(width) * height * channels;
    if (frameBytes > 128U * 1024U * 1024U) {
        std::cerr << "Frame is too large.\n";
        return 2;
    }
    std::vector<unsigned char> frame(frameBytes);
    Console console;
    const auto interval = std::chrono::duration<double>(1.0 / fps);
    auto nextFrame = std::chrono::steady_clock::now();
    while (std::cin.read(reinterpret_cast<char*>(frame.data()), static_cast<std::streamsize>(frame.size()))) {
        if (console.pollKey() == Key::Quit || interruptionRequested()) break;
        const std::string rendered = renderFrame(frame.data(), width, height, channels, mode);
        console.write("\x1b[H" + rendered + "\x1b[K\n");
        nextFrame += std::chrono::duration_cast<std::chrono::steady_clock::duration>(interval);
        std::this_thread::sleep_until(nextFrame);
        if (std::chrono::steady_clock::now() > nextFrame + interval) {
            nextFrame = std::chrono::steady_clock::now();
        }
    }
    return 0;
}
}

int main(int argc, char** argv) {
    installInterruptHandler();
    if (argc == 2 && std::string(argv[1]) == "--info") {
        TerminalSize size{};
        {
            Console console(false);
            size = console.size();
        }
        std::cout << "YouTubeCMD native renderer\nTerminal: " << size.columns << 'x' << size.rows
                  << "\nTarget FPS: 30\n";
        return 0;
    }
    if ((argc == 2 || argc == 3) && std::string(argv[1]) == "--selftest") {
        RenderMode mode = RenderMode::HalfBlock;
        if (argc == 3 && !parseMode(argv[2], mode)) {
            printUsage();
            return 2;
        }
        return runSelftest(mode);
    }
    if (argc >= 5 && argc <= 6 && std::string(argv[1]) == "--raw") {
        int width = 0;
        int height = 0;
        double fps = 0.0;
        RenderMode mode = RenderMode::HalfBlock;
        if (!parsePositiveInt(argv[2], width) || !parsePositiveInt(argv[3], height) ||
            !parseFps(argv[4], fps) || (argc == 6 && !parseMode(argv[5], mode))) {
            printUsage();
            return 2;
        }
        return runRaw(width, height, fps, mode);
    }
    if (argc >= 3 && std::string(argv[1]) == "--stream") {
    #ifdef _WIN32
        RenderMode mode = RenderMode::Pixel;
    #else
        RenderMode mode = RenderMode::Color;
    #endif
        Quality quality = Quality::High;
        for (int index = 3; index < argc; ++index) {
            const std::string option = argv[index];
            if (option == "--mode" && index + 1 < argc) {
                if (!parseMode(argv[++index], mode)) {
                    printUsage();
                    return 2;
                }
            } else if (option == "--quality" && index + 1 < argc) {
                if (!parseQuality(argv[++index], quality)) {
                    printUsage();
                    return 2;
                }
            } else {
                printUsage();
                return 2;
            }
        }
        return runStreamPlayer(argv[2], mode, quality);
    }
    printUsage();
    return 2;
}