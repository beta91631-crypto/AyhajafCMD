#pragma once

#include "console.hpp"

#include <string>

struct PixelWindowState;

class PixelWindow {
public:
    PixelWindow();
    ~PixelWindow();
    PixelWindow(const PixelWindow&) = delete;
    PixelWindow& operator=(const PixelWindow&) = delete;

    bool create(const std::string& title);
    bool closed() const;
    TerminalSize size() const;
    Key pollKey();
    void drawFrame(const unsigned char* rgb, int width, int height);
    void setTitle(const std::string& title) const;
    void maximize(bool enabled) const;

private:
    PixelWindowState* state_;
};