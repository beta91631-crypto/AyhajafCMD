#include "player.hpp"

#include "console.hpp"
#include "media.hpp"
#include "pixel_window.hpp"
#include "stream.hpp"

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr double kMaxFps = 30.0;
constexpr auto kResizeDebounce = std::chrono::milliseconds(150);

struct Dimensions {
    int width;
    int height;
    bool operator==(const Dimensions& other) const {
        return width == other.width && height == other.height;
    }
    bool operator!=(const Dimensions& other) const { return !(*this == other); }
};

double qualityScale(Quality quality) {
    if (quality == Quality::Low) return 0.5;
    if (quality == Quality::High) return 1.0;
    return 0.75;
}

const char* qualityName(Quality quality) {
    if (quality == Quality::Low) return "LOW";
    if (quality == Quality::High) return "HIGH";
    return "NORMAL";
}

const char* modeName(RenderMode mode) {
    if (mode == RenderMode::Ascii) return "ASCII";
    if (mode == RenderMode::Color) return "ANSI_COLOR";
    if (mode == RenderMode::Pixel) return "RGB_PIXELS";
    return "HALF_BLOCK";
}

Dimensions renderDimensions(const StreamInfo& stream, const TerminalSize& terminal,
                           RenderMode mode, Quality quality) {
    const double scale = qualityScale(quality);
    const int maxWidth = std::max(1, static_cast<int>(terminal.columns * scale));
    const int rows = std::max(1, terminal.rows - (mode == RenderMode::Pixel ? 0 : 2));
    const int maxHeight = std::max(1, static_cast<int>(rows *
        ((mode == RenderMode::Ascii || mode == RenderMode::Pixel) ? 1.0 : 2.0) * scale));
    const double cellAspect = mode == RenderMode::Ascii ? 0.5 : 1.0;
    const double targetRatio = (static_cast<double>(stream.width) / stream.height) / cellAspect;
    int width;
    int height;
    if (static_cast<double>(maxWidth) / maxHeight > targetRatio) {
        height = maxHeight;
        width = std::max(1, static_cast<int>(std::lround(height * targetRatio)));
    } else {
        width = maxWidth;
        height = std::max(1, static_cast<int>(std::lround(width / targetRatio)));
    }
    return {std::min(width, maxWidth), std::min(height, maxHeight)};
}

std::string number(double value) {
    std::ostringstream result;
    result << std::fixed << std::setprecision(3) << std::max(0.0, value);
    return result.str();
}

std::string clockText(double seconds) {
    const int total = std::max(0, static_cast<int>(seconds));
    std::ostringstream result;
    result << std::setfill('0') << std::setw(2) << total / 60 << ':'
           << std::setw(2) << total % 60;
    return result.str();
}

std::string fitLine(std::string text, int columns) {
    if (columns < 1) return {};
    for (char& value : text) {
        const unsigned char byte = static_cast<unsigned char>(value);
        if (byte < 0x20 || byte == 0x7f) value = ' ';
    }
    if (text.size() > static_cast<size_t>(columns)) {
        size_t length = static_cast<size_t>(columns);
        if ((static_cast<unsigned char>(text[length]) & 0xc0) == 0x80) {
            while (length > 0 &&
                   (static_cast<unsigned char>(text[length]) & 0xc0) == 0x80) --length;
            if (length > 0) --length;
        }
        text.resize(length);
    }
    if (text.size() < static_cast<size_t>(columns)) text.append(static_cast<size_t>(columns) - text.size(), ' ');
    return text;
}

void writeStatus(Console& console, const StreamInfo& stream, const TerminalSize& terminal,
                 bool paused, double position, int volume, RenderMode mode,
                 Quality quality, Dimensions dimensions, double measuredFps) {
    std::string duration = stream.hasDuration ? clockText(stream.duration) : "--:--";
    const std::string title = fitLine(stream.title, terminal.columns);
    const std::string state = paused ? "PAUSED" : "PLAYING";
    std::string details = " " + state + "  " + clockText(position) + "/" + duration +
        "  " + std::to_string(static_cast<int>(measuredFps)) + " FPS  Vol " +
        std::to_string(volume) + "%  " + modeName(mode) + "  " + qualityName(quality) +
        "  " + std::to_string(dimensions.width) + "x" + std::to_string(dimensions.height);
    details = fitLine(details, terminal.columns);
    const int firstRow = std::max(1, terminal.rows - 1);
    console.write("\x1b[" + std::to_string(firstRow) + ";1H\x1b[2K" + title +
                  "\x1b[" + std::to_string(firstRow + 1) + ";1H\x1b[2K" + details);
}

void updatePixelTitle(PixelWindow& window, const StreamInfo& stream, bool paused,
                      double position, int volume, Quality quality,
                      Dimensions dimensions, double measuredFps) {
    const std::string duration = stream.hasDuration ? clockText(stream.duration) : "--:--";
    window.setTitle("YouTubeCMD | " + stream.title + " | " +
        (paused ? "PAUSED " : "PLAYING ") + clockText(position) + "/" + duration +
        " | " + std::to_string(static_cast<int>(measuredFps)) + " FPS | Vol " +
        std::to_string(volume) + "% | " + qualityName(quality) + " | " +
        std::to_string(dimensions.width) + "x" + std::to_string(dimensions.height));
}

std::string videoFilter(Dimensions dimensions, RenderMode mode, double fps) {
    std::ostringstream filter;
    const char* scaleFlags = mode == RenderMode::Pixel ? "neighbor" : "fast_bilinear";
    const bool fullColor = mode == RenderMode::Color || mode == RenderMode::Pixel;
    filter << "scale=" << dimensions.width << ':' << dimensions.height
           << ":force_original_aspect_ratio=decrease:flags=" << scaleFlags << ",pad="
           << dimensions.width << ':' << dimensions.height << ":(ow-iw)/2:(oh-ih)/2:black,fps="
           << std::fixed << std::setprecision(3) << fps << ",format="
           << (fullColor ? "rgb24" : "gray");
    return filter.str();
}

std::vector<std::string> videoCommand(const StreamInfo& stream, double position,
                                     Dimensions dimensions, RenderMode mode, double fps) {
    const bool fullColor = mode == RenderMode::Color || mode == RenderMode::Pixel;
    return {"ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-ss",
        number(position), "-i", stream.videoUrl, "-an", "-vf",
        videoFilter(dimensions, mode, fps), "-pix_fmt", fullColor ? "rgb24" : "gray",
        "-f", "rawvideo", "pipe:1"};
}

std::vector<std::string> audioCommand(const StreamInfo& stream, double position, int volume) {
    return {"ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume",
        std::to_string(volume), "-ss", number(position), "-i", stream.audioUrl};
}

void writeFrame(Console& console, const std::string& frame) {
    std::string output;
    output.reserve(frame.size() + frame.size() / 32 + 16);
    output.append("\x1b[H");
    for (char value : frame) {
        if (value == '\n') output.append("\x1b[K\r\n");
        else output.push_back(value);
    }
    output.append("\x1b[K");
    console.write(output);
}

void toggleFullscreen(bool enabled) {
#ifdef _WIN32
    const HWND window = GetConsoleWindow();
    if (window != nullptr) ShowWindow(window, enabled ? SW_MAXIMIZE : SW_RESTORE);
#else
    (void)enabled;
#endif
}

Quality lowerQuality(Quality quality) {
    if (quality == Quality::High) return Quality::Normal;
    return Quality::Low;
}
}

bool parseQuality(const std::string& value, Quality& quality) {
    if (value == "low") quality = Quality::Low;
    else if (value == "normal") quality = Quality::Normal;
    else if (value == "high") quality = Quality::High;
    else return false;
    return true;
}

int runStreamPlayer(const std::string& streamPath, RenderMode mode, Quality quality) {
    StreamInfo stream;
    std::string error;
    if (!loadStreamInfo(streamPath, stream, error)) {
        std::cerr << error << '\n';
        return 1;
    }

    const bool pixelMode = mode == RenderMode::Pixel;
    Console console(!pixelMode);
    PixelWindow pixelWindow;
    if (pixelMode && !pixelWindow.create(stream.title)) {
        std::cerr << "Could not create the RGB pixel window. This mode requires Windows.\n";
        return 1;
    }
    auto displaySize = [&]() {
        return pixelMode ? pixelWindow.size() : console.size();
    };
    ChildProcess video;
    ChildProcess audio;
    const int channels = mode == RenderMode::Color || pixelMode ? 3 : 1;
    double fps = std::max(1.0, std::min(kMaxFps, stream.fps));
    auto frameInterval = std::chrono::duration<double>(1.0 / fps);
    int volume = 80;
    bool paused = false;
    bool fullscreen = false;
    double position = 0.0;
    auto playbackStarted = std::chrono::steady_clock::now();
    TerminalSize terminal = displaySize();
    Dimensions dimensions = renderDimensions(stream, terminal, mode, quality);
    auto resizeCandidate = dimensions;
    auto resizeStarted = std::chrono::steady_clock::now();
    auto nextFrame = playbackStarted;
    auto nextStatus = playbackStarted;
    auto fpsStarted = playbackStarted;
    int renderedFrames = 0;
    int slowFrames = 0;
    double measuredFps = 0.0;

    auto currentPosition = [&]() {
        if (paused) return position;
        return position + std::chrono::duration<double>(
            std::chrono::steady_clock::now() - playbackStarted).count();
    };
    auto startVideo = [&](double at) {
        return video.start(videoCommand(stream, at, dimensions, mode, fps), true);
    };
    auto startAudio = [&](double at) {
        return audio.start(audioCommand(stream, at, volume), false);
    };
    auto startAll = [&](double at) {
        video.stop();
        audio.stop();
        if (!startAudio(at) || !startVideo(at)) {
            video.stop();
            audio.stop();
            return false;
        }
        position = at;
        playbackStarted = std::chrono::steady_clock::now();
        nextFrame = playbackStarted;
        return true;
    };
    if (!startAll(position)) {
        std::cerr << "Could not start FFmpeg or FFplay. Check that both are installed in PATH.\n";
        return 1;
    }

    std::vector<unsigned char> frame(static_cast<size_t>(dimensions.width) *
        dimensions.height * channels);
    bool running = true;
    while (running) {
        const Key key = pixelMode ? pixelWindow.pollKey() : console.pollKey();
        if (key == Key::Quit || interruptionRequested() ||
            (pixelMode && pixelWindow.closed())) break;
        const double nowPosition = currentPosition();
        bool restartAll = false;
        bool restartVideo = false;
        bool restartAudio = false;
        if (key == Key::Pause) {
            if (paused) {
                paused = false;
                if (!startAll(position)) break;
            } else {
                position = nowPosition;
                video.stop();
                audio.stop();
                paused = true;
            }
        } else if (!paused && key == Key::Left) {
            position = std::max(0.0, nowPosition - 5.0);
            restartAll = true;
        } else if (!paused && key == Key::Right) {
            position = stream.hasDuration ? std::min(stream.duration, nowPosition + 5.0)
                                          : nowPosition + 5.0;
            restartAll = true;
        } else if (!paused && key == Key::Restart) {
            position = 0.0;
            restartAll = true;
        } else if (key == Key::Up || key == Key::Down) {
            const int updatedVolume = std::max(0, std::min(100, volume + (key == Key::Up ? 5 : -5)));
            if (!paused && updatedVolume != volume) {
                volume = updatedVolume;
                position = nowPosition;
                restartAudio = true;
            }
        } else if (!paused && (key == Key::QualityUp || key == Key::QualityDown)) {
            const Quality previousQuality = quality;
            if (key == Key::QualityUp && quality != Quality::High) {
                quality = quality == Quality::Low ? Quality::Normal : Quality::High;
            } else if (key == Key::QualityDown && quality != Quality::Low) {
                quality = lowerQuality(quality);
            }
            if (quality != previousQuality) {
                position = nowPosition;
                dimensions = renderDimensions(stream, displaySize(), mode, quality);
                restartVideo = true;
            }
        } else if (key == Key::Fullscreen) {
            fullscreen = !fullscreen;
            if (pixelMode) pixelWindow.maximize(fullscreen);
            else toggleFullscreen(fullscreen);
        }
        if (restartAll || restartVideo || restartAudio) {
            if (stream.hasDuration && position >= stream.duration) break;
            if (restartAll || restartVideo) {
                terminal = displaySize();
                dimensions = renderDimensions(stream, terminal, mode, quality);
                frame.resize(static_cast<size_t>(dimensions.width) * dimensions.height * channels);
            }
            if (restartAll) {
                if (!startAll(position)) break;
            } else if (restartVideo) {
                video.stop();
                if (!startVideo(position)) break;
                playbackStarted = std::chrono::steady_clock::now();
                nextFrame = playbackStarted;
            } else if (restartAudio) {
                audio.stop();
                if (!startAudio(position)) break;
                playbackStarted = std::chrono::steady_clock::now();
            }
            if (!pixelMode) console.clear();
        }
        if (paused) {
            if (pixelMode) {
                updatePixelTitle(pixelWindow, stream, true, position, volume, quality,
                                 dimensions, measuredFps);
            } else {
                writeStatus(console, stream, displaySize(), true, position, volume,
                            mode, quality, dimensions, measuredFps);
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
            continue;
        }

        const TerminalSize currentTerminal = displaySize();
        const Dimensions currentDimensions = renderDimensions(stream, currentTerminal, mode, quality);
        if (currentDimensions != dimensions) {
            const auto now = std::chrono::steady_clock::now();
            if (currentDimensions != resizeCandidate) {
                resizeCandidate = currentDimensions;
                resizeStarted = now;
            } else if (now - resizeStarted >= kResizeDebounce) {
                terminal = currentTerminal;
                dimensions = currentDimensions;
                frame.resize(static_cast<size_t>(dimensions.width) * dimensions.height * channels);
                video.stop();
                if (!startVideo(nowPosition)) break;
                resizeCandidate = dimensions;
                nextFrame = std::chrono::steady_clock::now();
                if (!pixelMode) console.clear();
            }
        } else {
            resizeCandidate = dimensions;
        }

        if (!video.readExact(frame.data(), frame.size())) {
            if (!video.running() &&
                (!stream.hasDuration || nowPosition + 1.0 < stream.duration)) {
                std::cerr << "FFmpeg stopped before finishing the video.\n";
            }
            break;
        }
        const auto frameStart = std::chrono::steady_clock::now();
        if (frameStart > nextFrame + std::chrono::duration_cast<std::chrono::steady_clock::duration>(frameInterval)) {
            ++slowFrames;
            nextFrame = frameStart;
        }
        if (stream.hasDuration && nowPosition >= stream.duration) break;

        if (pixelMode) {
            pixelWindow.drawFrame(frame.data(), dimensions.width, dimensions.height);
        } else {
            const std::string rendered = renderFrame(frame.data(), dimensions.width,
                                                      dimensions.height, channels, mode);
            writeFrame(console, rendered);
        }
        ++renderedFrames;
        const auto afterRender = std::chrono::steady_clock::now();
        if (afterRender - frameStart > frameInterval * 1.2) ++slowFrames;
        else slowFrames = std::max(0, slowFrames - 1);
        if (slowFrames >= 6 && quality != Quality::Low) {
            quality = lowerQuality(quality);
            dimensions = renderDimensions(stream, displaySize(), mode, quality);
            frame.resize(static_cast<size_t>(dimensions.width) * dimensions.height * channels);
            video.stop();
            if (!startVideo(currentPosition())) break;
            slowFrames = 0;
            if (!pixelMode) console.clear();
            nextFrame = std::chrono::steady_clock::now();
            continue;
        } else if (slowFrames >= 6 && fps > 15.0) {
            fps = std::max(15.0, fps - 5.0);
            frameInterval = std::chrono::duration<double>(1.0 / fps);
            video.stop();
            if (!startVideo(currentPosition())) break;
            slowFrames = 0;
            if (!pixelMode) console.clear();
            nextFrame = std::chrono::steady_clock::now();
            continue;
        }
        if (afterRender >= fpsStarted + std::chrono::seconds(1)) {
            measuredFps = renderedFrames / std::chrono::duration<double>(afterRender - fpsStarted).count();
            renderedFrames = 0;
            fpsStarted = afterRender;
        }
        if (afterRender >= nextStatus) {
            if (pixelMode) {
                updatePixelTitle(pixelWindow, stream, false, currentPosition(), volume,
                                 quality, dimensions, measuredFps);
            } else {
                writeStatus(console, stream, displaySize(), false, currentPosition(),
                            volume, mode, quality, dimensions, measuredFps);
            }
            nextStatus = afterRender + std::chrono::milliseconds(250);
        }
        nextFrame += std::chrono::duration_cast<std::chrono::steady_clock::duration>(frameInterval);
        std::this_thread::sleep_until(nextFrame);
        if (std::chrono::steady_clock::now() > nextFrame + frameInterval) {
            nextFrame = std::chrono::steady_clock::now();
        }
    }
    video.stop();
    audio.stop();
    if (pixelMode) pixelWindow.maximize(false);
    else toggleFullscreen(false);
    return 0;
}