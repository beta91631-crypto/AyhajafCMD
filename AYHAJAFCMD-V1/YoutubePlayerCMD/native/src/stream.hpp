#pragma once

#include <string>

struct StreamInfo {
    std::string videoUrl;
    std::string audioUrl;
    std::string title;
    double duration = 0.0;
    bool hasDuration = false;
    double fps = 30.0;
    int width = 640;
    int height = 360;
};

bool loadStreamInfo(const std::string& path, StreamInfo& stream, std::string& error);